"""
Prepara, valida y publica las puntuaciones. No modifica contrato, proceso ni población.

Funciones:
- generar(): Calcula puntuaciones y excluidos del periodo.
- guardar_csv(): Escribe los resultados en CSV.
- validar_staging_ml(): Contrasta el staging antes de publicar.
- ensayar_rollback(): Comprueba que la publicación pueda revertirse.
- verificar_pg(): Relee lo publicado y las demás tablas.
- persistir(): Escribe el staging y las tablas ML si la validación pasa.
- ejecutar(): Genera y, solo si se indica, persiste.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from transformation.io import _conexion_pg, aplicar_sql_tfm, staging_ok

from .features import a_pandas, enriquecer, partir_universo
from .lectura import leer_contratos_modelo
from .modelos import CONTAMINACION, N_ESTIMADORES, SEMILLA
from .scoring import (
    ALGORITMO,
    DOCUMENTACION,
    MATRIZ_ID,
    N_APTOS,
    N_EXCLUIDOS,
    N_TOTAL,
    VARIABLES_C1,
    VERSION_MODELO,
    huella_especificacion,
    huella_vector_scores,
    id_ejecucion,
    puntuar_c1,
    tabla_excluidos,
    tabla_scores,
    validar_cobertura,
    versiones_librerias,
)

SQL_ESQUEMA_ML = Path(__file__).resolve().parents[2] / "sql" / "004_esquema_tfm_ml.sql"

COLS_SCORE = [
    "periodo",
    "version_modelo",
    "id_ejecucion",
    "id_contrato",
    "socrata_id",
    "score_if",
    "rank_if",
    "top1_if",
    "top5_if",
    "score_logvalor",
    "rank_logvalor",
    "top1_logvalor",
    "top5_logvalor",
    "flag_p99_modalidad",
    "valor_del_contrato",
    "modalidad_grupo",
    "modalidad_de_contratacion",
    "nombre_entidad",
    "cod_municipio",
    "es_bogota",
    "estado_homologacion",
]
COLS_EXCL = [
    "periodo",
    "version_modelo",
    "id_ejecucion",
    "id_contrato",
    "socrata_id",
    "motivo_exclusion",
    "valor_del_contrato",
    "modalidad_de_contratacion",
    "nombre_entidad",
    "cod_municipio",
    "es_bogota",
]


def _py(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if hasattr(v, "item"):
        v = v.item()
    if isinstance(v, (bool, int, float, str)):
        return v
    return str(v)


def generar(spark, periodo: str, semilla: int = SEMILLA) -> dict:
    """Lee tfm.contrato (solo lectura) y arma tablas de publicación. No escribe."""
    df = leer_contratos_modelo(spark, periodo)
    pdf = a_pandas(df)
    partes = partir_universo(pdf)
    aptos = enriquecer(partes["aptos"])
    scored, meta = puntuar_c1(aptos, semilla=semilla)
    id_ej = id_ejecucion(periodo)
    scores = tabla_scores(scored, periodo, id_ej)
    excluidos = tabla_excluidos(partes["ceros"], partes["extremos"], periodo, id_ej)
    if len(pdf) != N_TOTAL:
        raise RuntimeError(f"Universo={len(pdf)}, esperado {N_TOTAL}.")
    cob = validar_cobertura(scores, excluidos, len(pdf))
    mal = [f["control"] for f in cob if not f["ok"]]
    if mal:
        raise RuntimeError("Cobertura inválida: " + ", ".join(mal))
    vers = versiones_librerias()
    ejecucion = {
        "id_ejecucion": id_ej,
        "version_modelo": VERSION_MODELO,
        "periodo": periodo,
        "corrida_ts": datetime.now(timezone.utc).isoformat(),
        "n_aptos": int(len(scores)),
        "n_excluidos": int(len(excluidos)),
        "n_top1_if": meta["n_top1_if"],
        "n_top5_if": meta["n_top5_if"],
        "n_p99_modalidad": meta["n_p99_modalidad"],
        "sklearn_version": vers.get("sklearn"),
        "pandas_version": vers.get("pandas"),
        "numpy_version": vers.get("numpy"),
        "escribir": False,
        "nota": VARIABLES_C1,
        "matriz": MATRIZ_ID,
        "algoritmo": ALGORITMO,
        "semilla": semilla,
        "n_estimators": N_ESTIMADORES,
        "contamination": CONTAMINACION,
        "variables_ajustadas": " + ".join(meta["variables"]),
        "if_s": meta["if_s"],
        "n_ambos_top5": meta["n_ambos_top5"],
        "n_top1_logvalor": meta["n_top1_logvalor"],
        "n_top5_logvalor": meta["n_top5_logvalor"],
        "huella": meta["huella"],
        "huella_scores": huella_vector_scores(scores),
        "n_universo": int(len(pdf)),
        "estado": "generado",
    }
    return {
        "scores": scores,
        "excluidos": excluidos,
        "ejecucion": ejecucion,
        "meta": meta,
    }


def guardar_csv(res: dict, salidas: Path) -> Path:
    salidas = Path(salidas)
    salidas.mkdir(parents=True, exist_ok=True)
    res["scores"].to_csv(salidas / "publicacion_scores.csv", index=False)
    res["excluidos"].to_csv(salidas / "publicacion_excluidos.csv", index=False)
    (salidas / "publicacion_ejecucion.json").write_text(
        json.dumps(res["ejecucion"], ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return salidas


def _conteos_otras_tablas() -> dict:
    conn = _conexion_pg()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  (SELECT count(*) FROM tfm.contrato) AS contrato,
                  (SELECT count(*) FROM tfm.proceso) AS proceso,
                  (SELECT count(*) FROM tfm.adjudicacion) AS adjudicacion,
                  (SELECT count(*) FROM tfm.adjudicacion_ambigua) AS ambigua,
                  (SELECT count(*) FROM tfm.poblacion_municipal) AS poblacion
                """
            )
            row = cur.fetchone()
            return {
                "contrato": int(row[0]),
                "proceso": int(row[1]),
                "adjudicacion": int(row[2]),
                "adjudicacion_ambigua": int(row[3]),
                "poblacion": int(row[4]),
            }
    finally:
        conn.close()


def vaciar_staging_ml() -> None:
    conn = _conexion_pg()
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                "TRUNCATE tfm.stg_ml_contrato_score, tfm.stg_ml_contrato_excluido"
            )
    finally:
        conn.close()


def _insertar_stg(cur, tabla: str, cols: list[str], pdf: pd.DataFrame) -> None:
    from psycopg2.extras import execute_values

    filas = []
    for rec in pdf[cols].itertuples(index=False, name=None):
        filas.append(tuple(_py(v) for v in rec))
    cols_sql = ", ".join(cols)
    execute_values(
        cur,
        f"INSERT INTO tfm.{tabla} ({cols_sql}) VALUES %s",
        filas,
        page_size=5000,
    )


def validar_staging_ml(periodo: str, version: str, n_score: int, n_exc: int) -> list[dict]:
    conn = _conexion_pg()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT control, observado, esperado, ok, nota "
                "FROM tfm.validar_stg_ml(%s, %s, %s, %s)",
                (periodo, version, n_score, n_exc),
            )
            filas = []
            for control, observado, esperado, ok, nota in cur.fetchall():
                filas.append(
                    {
                        "control": control,
                        "observado": None if observado is None else int(observado),
                        "esperado": None if esperado is None else int(esperado),
                        "ok": ok,
                        "nota": nota,
                    }
                )
            return filas
    finally:
        conn.close()


def _asegurar_modelo(cur, ejecucion: dict) -> None:
    huella = ejecucion["huella"]
    cur.execute(
        "SELECT huella FROM tfm.ml_modelo WHERE version_modelo = %s",
        (ejecucion["version_modelo"],),
    )
    row = cur.fetchone()
    if row is None:
        cur.execute(
            """
            INSERT INTO tfm.ml_modelo (
                version_modelo, matriz, algoritmo, semilla, n_estimators,
                contamination, variables, huella, documentacion, vigente, actualizado_ts
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, now())
            """,
            (
                ejecucion["version_modelo"],
                ejecucion["matriz"],
                ejecucion["algoritmo"],
                ejecucion["semilla"],
                ejecucion["n_estimators"],
                ejecucion["contamination"],
                ejecucion["nota"],
                huella,
                DOCUMENTACION,
            ),
        )
        return
    if row[0] != huella:
        raise RuntimeError(
            f"{ejecucion['version_modelo']} es inmutable. "
            f"huella guardada={row[0]} huella actual={huella}"
        )
    cur.execute(
        """
        UPDATE tfm.ml_modelo
           SET vigente = TRUE, actualizado_ts = now()
         WHERE version_modelo = %s
        """,
        (ejecucion["version_modelo"],),
    )


def ensayar_rollback(periodo: str, version: str) -> dict:
    """Publicar con staging vacío debe fallar y no cambiar tablas definitivas."""
    conn = _conexion_pg()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM tfm.ml_contrato_score")
            n0 = int(cur.fetchone()[0])
            cur.execute("SELECT count(*) FROM tfm.ml_contrato_excluido")
            n0e = int(cur.fetchone()[0])
            cur.execute("SELECT count(*) FROM tfm.contrato")
            n0c = int(cur.fetchone()[0])
    finally:
        conn.close()

    conn = _conexion_pg()
    conn.autocommit = False
    fallo_esperado = False
    mensaje = ""
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s))",
                (f"{periodo}\x1f{version}",),
            )
            cur.execute("SELECT tfm.publicar_ml_contratos(%s, %s)", (periodo, version))
        conn.commit()
    except Exception as exc:
        conn.rollback()
        fallo_esperado = True
        mensaje = str(exc).split("\n")[0]
    finally:
        conn.close()
    if not fallo_esperado:
        raise RuntimeError("Ensayo de rollback: publicar con staging vacío no falló.")

    conn = _conexion_pg()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM tfm.ml_contrato_score")
            if int(cur.fetchone()[0]) != n0:
                raise RuntimeError("Ensayo de rollback: ml_contrato_score cambió.")
            cur.execute("SELECT count(*) FROM tfm.ml_contrato_excluido")
            if int(cur.fetchone()[0]) != n0e:
                raise RuntimeError("Ensayo de rollback: ml_contrato_excluido cambió.")
            cur.execute("SELECT count(*) FROM tfm.contrato")
            if int(cur.fetchone()[0]) != n0c:
                raise RuntimeError("Ensayo de rollback: tfm.contrato cambió.")
    finally:
        conn.close()
    return {
        "ok": True,
        "n_score_antes": n0,
        "n_contrato": n0c,
        "error": mensaje,
    }


def verificar_pg(periodo: str, version: str) -> dict:
    conn = _conexion_pg()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  (SELECT count(*) FROM tfm.ml_contrato_score
                    WHERE periodo = %s AND version_modelo = %s) AS n_score,
                  (SELECT count(*) FROM tfm.ml_contrato_excluido
                    WHERE periodo = %s AND version_modelo = %s) AS n_exc,
                  (SELECT count(*) FROM tfm.ml_contrato_score
                    WHERE periodo = %s AND version_modelo = %s AND top1_if) AS n_top1,
                  (SELECT count(*) FROM tfm.ml_contrato_score
                    WHERE periodo = %s AND version_modelo = %s AND top5_if) AS n_top5,
                  (SELECT count(*) FROM tfm.ml_contrato_score
                    WHERE periodo = %s AND version_modelo = %s
                      AND flag_p99_modalidad) AS n_p99,
                  (SELECT count(DISTINCT id_contrato) FROM tfm.ml_contrato_score
                    WHERE periodo = %s AND version_modelo = %s) AS ids_score,
                  (SELECT count(*) FROM tfm.ml_ejecucion
                    WHERE periodo = %s AND version_modelo = %s
                      AND estado = 'publicado') AS n_ejecuciones,
                  (SELECT count(*) FROM tfm.ml_contrato_score s
                     JOIN tfm.ml_contrato_excluido e
                       ON s.periodo = e.periodo AND s.id_contrato = e.id_contrato
                      AND s.version_modelo = e.version_modelo
                    WHERE s.periodo = %s AND s.version_modelo = %s) AS solape,
                  (SELECT score_if FROM tfm.ml_contrato_score
                    WHERE periodo = %s AND version_modelo = %s AND rank_if = 1) AS score_rank1,
                  (SELECT max(score_if) FROM tfm.ml_contrato_score
                    WHERE periodo = %s AND version_modelo = %s) AS score_max,
                  (SELECT huella FROM tfm.ml_modelo WHERE version_modelo = %s) AS huella
                """,
                (periodo, version) * 9 + (periodo, version, version),
            )
            row = cur.fetchone()
            otras = _conteos_otras_tablas()
            return {
                "n_score": int(row[0]),
                "n_excluidos": int(row[1]),
                "n_top1_if": int(row[2]),
                "n_top5_if": int(row[3]),
                "n_p99_modalidad": int(row[4]),
                "ids_score": int(row[5]),
                "n_ejecuciones": int(row[6]),
                "solape": int(row[7]),
                "score_rank1": float(row[8]) if row[8] is not None else None,
                "score_max": float(row[9]) if row[9] is not None else None,
                "huella": row[10],
                "otras_tablas": otras,
            }
    finally:
        conn.close()


def persistir(scores: pd.DataFrame, excluidos: pd.DataFrame, ejecucion: dict) -> dict:
    """Staging → validar → publica solo tablas ML del par periodo+versión."""
    if not ejecucion.get("escribir"):
        raise RuntimeError("persistir exige escribir=True en la ejecución.")
    n_score, n_exc = len(scores), len(excluidos)
    if n_score != N_APTOS or n_exc != N_EXCLUIDOS:
        raise RuntimeError(f"Conteos inesperados scores={n_score} excluidos={n_exc}.")
    if ejecucion.get("huella") != huella_especificacion():
        raise RuntimeError("La huella de c1_if_v1 no coincide con la especificación.")
    periodo = ejecucion["periodo"]
    version = ejecucion["version_modelo"]
    antes = _conteos_otras_tablas()
    aplicar_sql_tfm(SQL_ESQUEMA_ML)
    vaciar_staging_ml()
    ensayo = ensayar_rollback(periodo, version)

    conn = _conexion_pg()
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            _insertar_stg(cur, "stg_ml_contrato_score", COLS_SCORE, scores)
            _insertar_stg(cur, "stg_ml_contrato_excluido", COLS_EXCL, excluidos)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    validacion = validar_staging_ml(periodo, version, n_score, n_exc)
    if not staging_ok(validacion):
        fallos = [f["control"] for f in validacion if f["ok"] is not True]
        raise RuntimeError(
            "Validación staging ML fallida. No se publica: " + ", ".join(fallos)
        )

    corrida = datetime.now(timezone.utc)
    conn = _conexion_pg()
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s))",
                (f"{periodo}\x1f{version}",),
            )
            cur.execute(
                """
                SELECT version_modelo, count(*)
                  FROM tfm.ml_contrato_score
                 WHERE NOT (periodo = %s AND version_modelo = %s)
                 GROUP BY 1
                """,
                (periodo, version),
            )
            otras_versiones = {r[0]: int(r[1]) for r in cur.fetchall()}
            _asegurar_modelo(cur, ejecucion)
            cur.execute("SELECT tfm.publicar_ml_contratos(%s, %s)", (periodo, version))
            cur.execute(
                """
                SELECT count(*) FROM tfm.ml_contrato_score
                 WHERE periodo = %s AND version_modelo = %s
                """,
                (periodo, version),
            )
            if int(cur.fetchone()[0]) != n_score:
                raise RuntimeError("conteo tfm.ml_contrato_score distinto tras INSERT")
            cur.execute(
                """
                SELECT count(*) FROM tfm.ml_contrato_excluido
                 WHERE periodo = %s AND version_modelo = %s
                """,
                (periodo, version),
            )
            if int(cur.fetchone()[0]) != n_exc:
                raise RuntimeError("conteo tfm.ml_contrato_excluido distinto tras INSERT")
            cur.execute(
                """
                SELECT
                  count(*) FILTER (WHERE top1_if),
                  count(*) FILTER (WHERE top5_if),
                  count(*) FILTER (WHERE flag_p99_modalidad),
                  count(*) FILTER (WHERE rank_if = 1 AND score_if IS DISTINCT FROM (
                      SELECT max(score_if) FROM tfm.ml_contrato_score
                       WHERE periodo = %s AND version_modelo = %s
                  )),
                  (SELECT count(*) FROM tfm.ml_contrato_score s
                     JOIN tfm.ml_contrato_excluido e
                       ON s.periodo = e.periodo AND s.id_contrato = e.id_contrato
                      AND s.version_modelo = e.version_modelo
                    WHERE s.periodo = %s AND s.version_modelo = %s)
                FROM tfm.ml_contrato_score
                WHERE periodo = %s AND version_modelo = %s
                """,
                (periodo, version, periodo, version, periodo, version),
            )
            n_top1, n_top5, n_p99, n_orden, n_solape = cur.fetchone()
            if int(n_top1) != 825 or int(n_top5) != 4123 or int(n_p99) != 828:
                raise RuntimeError(
                    f"tops inesperados top1={n_top1} top5={n_top5} p99={n_p99}"
                )
            if int(n_orden) != 0 or int(n_solape) != 0:
                raise RuntimeError(
                    f"orden/solape inválidos orden={n_orden} solape={n_solape}"
                )
            cur.execute(
                """
                SELECT version_modelo, count(*)
                  FROM tfm.ml_contrato_score
                 WHERE NOT (periodo = %s AND version_modelo = %s)
                 GROUP BY 1
                """,
                (periodo, version),
            )
            otras_despues = {r[0]: int(r[1]) for r in cur.fetchall()}
            if otras_despues != otras_versiones:
                raise RuntimeError(
                    "La publicación alteró otra versión: "
                    f"antes={otras_versiones} despues={otras_despues}"
                )
            cur.execute(
                """
                SELECT
                  (SELECT count(*) FROM tfm.contrato),
                  (SELECT count(*) FROM tfm.proceso),
                  (SELECT count(*) FROM tfm.adjudicacion),
                  (SELECT count(*) FROM tfm.adjudicacion_ambigua),
                  (SELECT count(*) FROM tfm.poblacion_municipal)
                """
            )
            ahora = cur.fetchone()
            esperado = (
                antes["contrato"],
                antes["proceso"],
                antes["adjudicacion"],
                antes["adjudicacion_ambigua"],
                antes["poblacion"],
            )
            if tuple(int(x) for x in ahora) != esperado:
                raise RuntimeError(
                    "Tablas de contratos/procesos/población cambiaron; rollback."
                )
            cur.execute(
                """
                INSERT INTO tfm.ml_ejecucion (
                    id_ejecucion, version_modelo, periodo, corrida_ts,
                    n_aptos, n_excluidos, n_top1_if, n_top5_if, n_p99_modalidad,
                    sklearn_version, pandas_version, numpy_version,
                    escribir, estado, nota
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                          TRUE, 'publicado', %s)
                """,
                (
                    ejecucion["id_ejecucion"],
                    version,
                    periodo,
                    corrida,
                    n_score,
                    n_exc,
                    ejecucion["n_top1_if"],
                    ejecucion["n_top5_if"],
                    ejecucion["n_p99_modalidad"],
                    ejecucion.get("sklearn_version"),
                    ejecucion.get("pandas_version"),
                    ejecucion.get("numpy_version"),
                    ejecucion.get("nota"),
                ),
            )
            for f in validacion:
                obs, exp = f["observado"], f["esperado"]
                dif = None if obs is None or exp is None else obs - exp
                cur.execute(
                    """
                    INSERT INTO tfm.ml_control (
                        periodo, corrida_ts, version_modelo, id_ejecucion,
                        control, observado, esperado, diferencia, ok, nota, escribir
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                    """,
                    (
                        periodo,
                        corrida,
                        version,
                        ejecucion["id_ejecucion"],
                        f["control"],
                        obs,
                        exp,
                        dif,
                        f["ok"],
                        f["nota"],
                    ),
                )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    verif = verificar_pg(periodo, version)
    ejecucion["estado"] = "publicado"
    return {
        "validacion_stg": validacion,
        "publicado": True,
        "ensayo_rollback": ensayo,
        "otras_tablas_intactas": verif["otras_tablas"],
        "verificacion": verif,
    }


def ejecutar(
    spark,
    periodo: str = "2026-09",
    escribir: bool = False,
    salidas: Path | None = None,
) -> dict:
    res = generar(spark, periodo)
    res["ejecucion"]["escribir"] = bool(escribir)
    if salidas is not None:
        guardar_csv(res, salidas)
    publicado = None
    if escribir:
        publicado = persistir(res["scores"], res["excluidos"], res["ejecucion"])
    return {**res, "publicado": publicado}
