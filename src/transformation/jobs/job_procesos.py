"""
Job de procesos SECOP II. Escribe en PostgreSQL solo si se pide y los controles cuadran.

Funciones:
- ejecutar(): Transforma y, opcionalmente, publica los procesos.
- main(): Crea la sesión Spark y lanza el job.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Permite ejecutar el archivo como script.
_SRC = Path(__file__).resolve().parents[2]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from transformation.spark_sesion import _asegurar_pyspark, crear_spark

_asegurar_pyspark()
from pyspark.sql import functions as F  # noqa: E402
from pyspark.sql.types import (  # noqa: E402
    BooleanType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

from transformation.controles import controles_criticos_ok, cuadro_control  # noqa: E402
from transformation.io import (  # noqa: E402
    leer_dim_municipio,
    leer_procesos_filas,
    persistir_periodo_procesos,
    verificar_integridad_pg,
    verificar_persistencia,
)
from transformation.procesos import invariantes_adjudicacion, transformar_procesos  # noqa: E402


def _bool_env(nombre: str, default: str = "false") -> bool:
    return os.environ.get(nombre, default).strip().lower() in {"1", "true", "yes", "si"}


def ejecutar(spark, periodo: str = "2026-09", escribir: bool = False) -> dict:
    filas = leer_procesos_filas(spark, periodo)
    n_filas = filas.count()
    n_sid = filas.select("socrata_id").distinct().count() if "socrata_id" in filas.columns else 0
    n_proc_bruto = filas.select("id_del_proceso").distinct().count()

    dim = leer_dim_municipio(spark)
    out = transformar_procesos(filas, dim)
    proceso, adj, amb, pares = (
        out["proceso"],
        out["adjudicacion"],
        out["adjudicacion_ambigua"],
        out["pares"],
    )

    proceso = proceso.persist()
    adj = adj.persist()
    amb = amb.persist()
    pares = pares.persist()

    n_proceso = proceso.count()
    n_ok = pares.filter(F.col("confiable")).count()
    n_amb = pares.filter(F.col("ambiguo")).count()
    n_cart = pares.filter(F.col("cartesiano")).count()
    n_sin_awd = pares.filter(F.col("sin_awd") & (~F.col("ambiguo"))).count()
    n_adj_filas = adj.count()
    n_amb_filas = amb.count()
    n_var = proceso.filter(F.col("hay_campos_variables")).count()
    n_revisar = adj.filter(F.col("tipo_grano") == "revisar").count()
    n_usable = adj.filter(F.col("valor_usable")).count()
    n_solape = adj.join(amb, ["id_del_proceso", "id_adjudicacion"], "inner").count()
    n_usable_sin = adj.filter(
        F.col("valor_usable") & F.col("valor_total_adjudicacion").isNull()
    ).count()
    n_neg = adj.filter(
        F.col("valor_usable") & (F.col("valor_total_adjudicacion") < 0)
    ).count()
    n_cero = adj.filter(
        F.col("valor_usable") & (F.col("valor_total_adjudicacion") == 0)
    ).count()
    n_pos = adj.filter(
        F.col("valor_usable") & (F.col("valor_total_adjudicacion") > 0)
    ).count()
    fallos_invariante = invariantes_adjudicacion(adj, amb)

    observado = {
        "filas_api_procesos": n_filas,
        "socrata_id": n_sid,
        "procesos": n_proceso,
        "pares_adjudicacion_confiables": n_ok,
        "pares_adjudicacion_ambiguos": n_amb,
        "pares_adjudicacion_cartesianos": n_cart,
        "pares_sin_awd_no_ambiguos": n_sin_awd,
        "filas_adjudicacion_confiable": n_adj_filas,
        "filas_adjudicacion_ambigua": n_amb_filas,
        "adjudicaciones_tipo_revisar": n_revisar,
        "adjudicaciones_valor_usable": n_usable,
        "adjudicaciones_solapadas": n_solape,
        "adjudicaciones_usable_sin_monto": n_usable_sin,
        "adjudicaciones_monto_negativo": n_neg,
        "adjudicaciones_monto_cero": n_cero,
        "adjudicaciones_monto_positivo": n_pos,
        "adjudicaciones_apto_agregar": n_pos,
        "procesos_campos_variables": n_var,
        "procesos_unicos_en_filas": n_proc_bruto,
    }
    cuadro = cuadro_control(observado)

    ts = datetime.now(timezone.utc)
    filas_ctrl = []
    for c in cuadro:
        filas_ctrl.append(
            {
                "control": c["control"],
                "observado": c["observado"],
                "esperado": c["esperado"],
                "diferencia": c["diferencia"],
                "ok": None if c["ok"] is None else bool(c["ok"]),
                "nota": c["nota"],
                "periodo": periodo,
                "corrida_ts": ts,
                "escribir": escribir,
            }
        )
    esquema_ctrl = StructType(
        [
            StructField("control", StringType(), False),
            StructField("observado", LongType(), True),
            StructField("esperado", LongType(), True),
            StructField("diferencia", LongType(), True),
            StructField("ok", BooleanType(), True),
            StructField("nota", StringType(), True),
            StructField("periodo", StringType(), True),
            StructField("corrida_ts", TimestampType(), True),
            StructField("escribir", BooleanType(), False),
        ]
    )
    control_df = spark.createDataFrame(filas_ctrl, schema=esquema_ctrl)

    verificacion_pg = None
    integridad_pg = None
    persist_res = None
    if escribir:
        if not controles_criticos_ok(cuadro):
            raise SystemExit(
                "Control crítico distinto del EDA. No se publica. Revise el cuadro."
            )
        if fallos_invariante:
            raise SystemExit(
                "Invariantes de adjudicación fallidas. No se publica: "
                + "; ".join(fallos_invariante)
            )
        try:
            persist_res = persistir_periodo_procesos(
                proceso, adj, amb, control_df, periodo
            )
        except RuntimeError as exc:
            raise SystemExit(
                "Publicación abortada. Estado anterior de tfm conservado. " + str(exc)
            ) from exc
        verificacion_pg = verificar_persistencia(
            spark,
            periodo,
            {
                "proceso": n_proceso,
                "adjudicacion": n_adj_filas,
                "adjudicacion_ambigua": n_amb_filas,
            },
        )
        integridad_pg = verificar_integridad_pg(periodo)
        if not all(f["ok_conteo"] and f["ok_nulos"] and f["ok_unicas"] for f in verificacion_pg):
            raise SystemExit(
                "Verificación PostgreSQL distinta de Spark. Revise tfm del periodo "
                f"{periodo}: {verificacion_pg}"
            )
        if not all(f["ok"] for f in integridad_pg):
            raise SystemExit(
                "Integridad referencial fallida tras publicar: " + str(integridad_pg)
            )

    return {
        "filas": filas,
        "proceso": proceso,
        "adjudicacion": adj,
        "adjudicacion_ambigua": amb,
        "pares": pares,
        "control": control_df,
        "cuadro": cuadro,
        "observado": observado,
        "fallos_invariante": fallos_invariante,
        "verificacion_pg": verificacion_pg,
        "integridad_pg": integridad_pg,
        "persist_res": persist_res,
    }


def main() -> None:
    periodo = os.environ.get("PERIODO", "2026-09")
    escribir = _bool_env("ESCRIBIR", "false")
    spark = crear_spark("tfm-transformacion-procesos")
    try:
        res = ejecutar(spark, periodo=periodo, escribir=escribir)
        print("ESCRIBIR:", escribir)
        print("Periodo:", periodo)
        for c in res["cuadro"]:
            print(
                f"{c['control']}: observado={c['observado']} "
                f"esperado={c['esperado']} ok={c['ok']}"
            )
        if res["fallos_invariante"]:
            print("Invariantes:", "; ".join(res["fallos_invariante"]))
        else:
            print("Invariantes de adjudicación: ok")
        if res.get("persist_res"):
            print("Publicado:", res["persist_res"].get("publicado"))
            for v in res["persist_res"].get("validacion_stg") or []:
                print(
                    f"stg {v['control']}: observado={v['observado']} "
                    f"esperado={v['esperado']} ok={v['ok']}"
                )
        if res["verificacion_pg"] is not None:
            print("Verificación PostgreSQL:", res["verificacion_pg"])
        if res.get("integridad_pg") is not None:
            print("Integridad PostgreSQL:", res["integridad_pg"])
        elif not escribir:
            print("Sin escritura (ESCRIBIR=false).")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
