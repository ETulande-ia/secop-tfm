"""
Job de población municipal del CNPV 2018. Escribe en PostgreSQL solo si se pide y los controles cuadran.

Funciones:
- ejecutar(): Transforma y, opcionalmente, publica la población.
- main(): Crea la sesión Spark y lanza el job.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from transformation.spark_sesion import _asegurar_pyspark, crear_spark

_asegurar_pyspark()
from pyspark.sql import functions as F  # noqa: E402
from pyspark.sql.types import (  # noqa: E402
    BooleanType,
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

from transformation.controles import (  # noqa: E402
    CONTROLES_CRITICOS_DANE,
    controles_criticos_ok,
    cuadro_control,
)
from transformation.dane import (  # noqa: E402
    ANIO_CENSO,
    invariantes_poblacion,
    transformar_dane,
)
from transformation.io import (  # noqa: E402
    leer_cnpv_parquet,
    leer_dim_municipio,
    persistir_poblacion,
    verificar_persistencia,
)


def _bool_env(nombre: str, default: str = "false") -> bool:
    return os.environ.get(nombre, default).strip().lower() in {"1", "true", "yes", "si"}


def ejecutar(spark, anio: int = ANIO_CENSO, escribir: bool = False) -> dict:
    personas = leer_cnpv_parquet(spark)
    n_personas = personas.count()

    dim = leer_dim_municipio(spark)
    n_dim = dim.select("cod_municipio").distinct().count()
    pob, cats = transformar_dane(personas, dim)
    pob = pob.persist()

    n_mun = pob.count()
    n_id = pob.select("anio", "cod_municipio").distinct().count()
    n_dup = n_mun - n_id
    n_vacio = pob.filter(
        F.col("cod_municipio").isNull() | (F.trim(F.col("cod_municipio")) == "")
    ).count()
    n_neg = pob.filter(F.col("poblacion") < 0).count()
    suma = int(pob.agg(F.sum("poblacion").alias("s")).collect()[0]["s"] or 0)
    n_hom = pob.filter(F.col("en_divipola")).count()
    n_noh = pob.filter(~F.col("en_divipola")).count()
    per_hom = int(
        pob.filter(F.col("en_divipola")).agg(F.sum("poblacion").alias("s")).collect()[0]["s"] or 0
    )
    per_noh = int(
        pob.filter(~F.col("en_divipola")).agg(F.sum("poblacion").alias("s")).collect()[0]["s"] or 0
    )
    n_bog = pob.filter(F.col("es_bogota")).count()
    pob_bog = int(
        pob.filter(F.col("es_bogota")).agg(F.sum("poblacion").alias("s")).collect()[0]["s"] or 0
    )

    dim_cod = dim.select(
        F.lpad(F.col("cod_municipio").cast("string"), 5, "0").alias("cod_municipio")
    ).distinct()
    sin_censo = dim_cod.join(pob.select("cod_municipio"), "cod_municipio", "left_anti")
    n_sin_censo = sin_censo.count()
    no_hom = pob.filter(~F.col("en_divipola")).select(
        "cod_municipio", "poblacion", "via_codigo"
    )
    fallos_invariante = invariantes_poblacion(pob, n_personas)

    observado = {
        "personas_parquet": n_personas,
        "personas_agregadas": suma,
        "municipios": n_mun,
        "municipios_homologados": n_hom,
        "municipios_no_homologados": n_noh,
        "personas_homologadas": per_hom,
        "personas_no_homologadas": per_noh,
        "poblacion_negativa": n_neg,
        "codigos_vacios": n_vacio,
        "municipios_duplicados": n_dup,
        "divipola_sin_censo": n_sin_censo,
        "dim_municipio": n_dim,
        "municipios_bogota": n_bog,
        "personas_bogota": pob_bog,
        "categorias_sexo_ok": int(bool(cats["categorias_sexo_ok"])),
        "categorias_edad_ok": int(bool(cats["categorias_edad_ok"])),
        "categorias_zona_ok": int(bool(cats["categorias_zona_ok"])),
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
                "anio": int(anio),
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
            StructField("anio", IntegerType(), False),
            StructField("corrida_ts", TimestampType(), True),
            StructField("escribir", BooleanType(), False),
        ]
    )
    control_df = spark.createDataFrame(filas_ctrl, schema=esquema_ctrl)

    verificacion_pg = None
    persist_res = None
    if escribir:
        if not controles_criticos_ok(cuadro, CONTROLES_CRITICOS_DANE):
            raise SystemExit(
                "Control crítico distinto del EDA. No se publica. Revise el cuadro."
            )
        if fallos_invariante:
            raise SystemExit(
                "Invariantes de población fallidas. No se publica: "
                + "; ".join(fallos_invariante)
            )
        try:
            persist_res = persistir_poblacion(pob, control_df, int(anio), n_personas)
        except RuntimeError as exc:
            raise SystemExit(
                "Publicación abortada. Estado anterior de tfm.poblacion_municipal "
                "conservado. " + str(exc)
            ) from exc
        verificacion_pg = verificar_persistencia(
            spark,
            str(anio),
            {"poblacion_municipal": n_mun},
            pks={"poblacion_municipal": ["anio", "cod_municipio"]},
            col_tiempo="anio",
        )
        if not all(f["ok_conteo"] and f["ok_nulos"] and f["ok_unicas"] for f in verificacion_pg):
            raise SystemExit(
                "Verificación PostgreSQL distinta de Spark. Revise "
                f"tfm.poblacion_municipal {anio}: {verificacion_pg}"
            )

    return {
        "personas": personas,
        "poblacion": pob,
        "categorias": cats,
        "no_homologados": no_hom,
        "divipola_sin_censo": sin_censo,
        "control": control_df,
        "cuadro": cuadro,
        "observado": observado,
        "fallos_invariante": fallos_invariante,
        "verificacion_pg": verificacion_pg,
        "persist_res": persist_res,
    }


def main() -> None:
    anio = int(os.environ.get("ANIO", str(ANIO_CENSO)))
    escribir = _bool_env("ESCRIBIR", "false")
    spark = crear_spark("tfm-transformacion-dane")
    try:
        res = ejecutar(spark, anio=anio, escribir=escribir)
        print("ESCRIBIR:", escribir)
        print("Año censal:", anio)
        print("Categorías:", {k: res["categorias"][k] for k in (
            "sexo_columna", "edad_columna", "zona_columna",
            "categorias_sexo_ok", "categorias_edad_ok", "categorias_zona_ok",
            "sexo", "zona",
        )})
        for c in res["cuadro"]:
            print(
                f"{c['control']}: observado={c['observado']} "
                f"esperado={c['esperado']} ok={c['ok']}"
            )
        if res["fallos_invariante"]:
            print("Invariantes:", "; ".join(res["fallos_invariante"]))
        else:
            print("Invariantes de población: ok")
        if res.get("persist_res"):
            print("Publicado:", res["persist_res"].get("publicado"))
            print("SECOP intacto:", res["persist_res"].get("secop_intactos"))
            for v in res["persist_res"].get("validacion_stg") or []:
                print(
                    f"stg {v['control']}: observado={v['observado']} "
                    f"esperado={v['esperado']} ok={v['ok']}"
                )
        if res["verificacion_pg"] is not None:
            print("Verificación PostgreSQL:", res["verificacion_pg"])
        elif not escribir:
            print("Sin escritura (ESCRIBIR=false).")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
