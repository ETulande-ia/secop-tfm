"""
Puntuación C1 con Isolation Forest para publicación. No reentrena C3 ni LOF.

Funciones:
- huella_especificacion(): Huella de la especificación c1_if_v1.
- id_ejecucion(): Identificador de la corrida por periodo y versión.
- puntuar_c1(): Ajusta Isolation Forest y asigna puntuación y ranking.
- validar_puntuacion(): Comprueba puntuaciones, rangos y nulos.
- validar_cobertura(): Comprueba que el universo quede cubierto.
- tabla_scores(): Arma la tabla de puntuaciones.
- tabla_excluidos(): Arma la tabla de ceros y extremos.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .features import N_MODALIDADES, matriz
from .modelos import (
    CONTAMINACION,
    N_ESTIMADORES,
    SEMILLA,
    entrenar_isolation_forest,
    score_baseline_modalidad,
)

VERSION_MODELO = "c1_if_v1"
MATRIZ_ID = "C1"
ALGORITMO = "isolation_forest"
NUMERICAS_C1 = ["log1p_valor", "log_valor_vs_modalidad"]
DOCUMENTACION = "docs/10_experimentos_anomalias_contratos.md; docs/11_publicacion_resultados_ml.md"
N_APTOS = 82457
N_CEROS = 506
N_EXTREMOS = 1
N_EXCLUIDOS = N_CEROS + N_EXTREMOS
N_TOTAL = N_APTOS + N_EXCLUIDOS
VARIABLES_C1 = (
    "log1p_valor + log_valor_vs_modalidad + dummies modalidad_grupo "
    "(6 más frecuentes + otras). RobustScaler en numéricas. Sin plazo ni n_entidad."
)
ESPECIFICACION = {
    "version_modelo": VERSION_MODELO,
    "matriz": MATRIZ_ID,
    "algoritmo": ALGORITMO,
    "numericas": list(NUMERICAS_C1),
    "dummies_modalidad": True,
    "n_modalidades": N_MODALIDADES,
    "plazo": False,
    "n_entidad": False,
    "semilla": SEMILLA,
    "n_estimators": N_ESTIMADORES,
    "contamination": CONTAMINACION,
    "max_samples": "auto",
    "score_if": "-decision_function",
    "direccion": "mayor score_if = mas atipico",
    "rank": "score desc, id_contrato asc, 1..n unico",
    "top_k": "rank <= round(n*frac)",
    "n_aptos": N_APTOS,
}


def huella_especificacion() -> str:
    payload = json.dumps(ESPECIFICACION, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def id_ejecucion(periodo: str, version: str = VERSION_MODELO) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{version}_{periodo}_{ts}"


def ranking_unico(pdf: pd.DataFrame, col_score: str) -> np.ndarray:
    """1..n sin empates. Desempate: id_contrato ascendente."""
    score = -pd.to_numeric(pdf[col_score], errors="coerce").to_numpy()
    ids = pdf["id_contrato"].astype(str).to_numpy()
    orden = np.lexsort((ids, score))
    ranks = np.empty(len(pdf), dtype=np.int64)
    ranks[orden] = np.arange(1, len(pdf) + 1)
    return ranks


def puntuar_c1(aptos: pd.DataFrame, semilla: int = SEMILLA) -> tuple[pd.DataFrame, dict]:
    """Ajusta Isolation Forest sobre C1. Controles log-valor y P99 aparte."""
    if len(aptos) != N_APTOS:
        raise RuntimeError(f"Aptos={len(aptos)}, esperado {N_APTOS}. No se puntúa.")
    if semilla != SEMILLA:
        raise RuntimeError(f"c1_if_v1 exige semilla {SEMILLA}, no {semilla}.")
    X, nombres, _ = matriz(aptos, NUMERICAS_C1, dummies_modalidad=True)
    base = score_baseline_modalidad(aptos)
    _, score_if, t_if = entrenar_isolation_forest(X, random_state=semilla)
    out = base.copy()
    out["score_if"] = score_if
    out["score_logvalor"] = out["log1p_valor"]
    out["rank_if"] = ranking_unico(out, "score_if")
    out["rank_logvalor"] = ranking_unico(out, "score_logvalor")
    k1 = int(round(len(out) * 0.01))
    k5 = int(round(len(out) * 0.05))
    out["top1_if"] = out["rank_if"] <= k1
    out["top5_if"] = out["rank_if"] <= k5
    out["top1_logvalor"] = out["rank_logvalor"] <= k1
    out["top5_logvalor"] = out["rank_logvalor"] <= k5
    out["flag_p99_modalidad"] = out["flag_p99_mod"].astype(bool)
    fallos = validar_puntuacion(out)
    mal = [f["control"] for f in fallos if not f["ok"]]
    if mal:
        raise RuntimeError("Validación de puntuación fallida: " + ", ".join(mal))
    meta = {
        "variables": nombres,
        "if_s": round(t_if, 3),
        "n_top1_if": int(out["top1_if"].sum()),
        "n_top5_if": int(out["top5_if"].sum()),
        "n_top1_logvalor": int(out["top1_logvalor"].sum()),
        "n_top5_logvalor": int(out["top5_logvalor"].sum()),
        "n_p99_modalidad": int(out["flag_p99_modalidad"].sum()),
        "n_ambos_top5": int((out["top5_if"] & out["top5_logvalor"]).sum()),
        "huella": huella_especificacion(),
        "k1": k1,
        "k5": k5,
    }
    return out, meta


def validar_puntuacion(pdf: pd.DataFrame) -> list[dict]:
    n = len(pdf)
    k1 = int(round(n * 0.01))
    k5 = int(round(n * 0.05))
    sc = pd.to_numeric(pdf["score_if"], errors="coerce")
    r = pdf["rank_if"].astype(int)
    top = pdf.loc[r == 1, "score_if"]
    filas = [
        {"control": "n_aptos", "observado": n, "esperado": N_APTOS, "ok": n == N_APTOS},
        {
            "control": "score_if_finito",
            "observado": int(np.isfinite(sc.to_numpy(dtype=float)).sum()),
            "esperado": n,
            "ok": bool(np.isfinite(sc.to_numpy(dtype=float)).all()),
        },
        {
            "control": "rank_if_unicos",
            "observado": int(r.nunique()),
            "esperado": n,
            "ok": int(r.nunique()) == n and int(r.min()) == 1 and int(r.max()) == n,
        },
        {
            "control": "rank_logvalor_unicos",
            "observado": int(pdf["rank_logvalor"].nunique()),
            "esperado": n,
            "ok": int(pdf["rank_logvalor"].nunique()) == n,
        },
        {
            "control": "top1_if",
            "observado": int(pdf["top1_if"].sum()),
            "esperado": k1,
            "ok": int(pdf["top1_if"].sum()) == k1,
        },
        {
            "control": "top5_if",
            "observado": int(pdf["top5_if"].sum()),
            "esperado": k5,
            "ok": int(pdf["top5_if"].sum()) == k5,
        },
        {
            "control": "top1_en_top5",
            "observado": int((pdf["top1_if"] & ~pdf["top5_if"]).sum()),
            "esperado": 0,
            "ok": not bool((pdf["top1_if"] & ~pdf["top5_if"]).any()),
        },
        {
            "control": "rank1_es_max_score",
            "observado": None if top.empty else float(top.iloc[0]),
            "esperado": float(sc.max()),
            "ok": (not top.empty) and float(top.iloc[0]) == float(sc.max()),
        },
    ]
    return filas


def validar_cobertura(scores: pd.DataFrame, excluidos: pd.DataFrame, n_universo: int) -> list[dict]:
    ids_s = set(scores["id_contrato"].astype(str))
    ids_e = set(excluidos["id_contrato"].astype(str))
    return [
        {
            "control": "solape_score_excluido",
            "observado": len(ids_s & ids_e),
            "esperado": 0,
            "ok": not (ids_s & ids_e),
        },
        {
            "control": "cobertura_universo",
            "observado": len(ids_s) + len(ids_e),
            "esperado": n_universo,
            "ok": len(ids_s) + len(ids_e) == n_universo == N_TOTAL and not (ids_s & ids_e),
        },
        {
            "control": "n_excluidos",
            "observado": len(excluidos),
            "esperado": N_EXCLUIDOS,
            "ok": len(excluidos) == N_EXCLUIDOS,
        },
    ]


def _col(pdf: pd.DataFrame, nombre: str):
    if nombre in pdf.columns:
        return pdf[nombre]
    return pd.Series([None] * len(pdf), index=pdf.index)


def tabla_scores(
    scored: pd.DataFrame,
    periodo: str,
    id_ej: str,
    version: str = VERSION_MODELO,
) -> pd.DataFrame:
    cols = {
        "periodo": periodo,
        "version_modelo": version,
        "id_ejecucion": id_ej,
        "id_contrato": scored["id_contrato"].astype(str),
        "socrata_id": _col(scored, "socrata_id"),
        "score_if": scored["score_if"].astype(float),
        "rank_if": scored["rank_if"].astype(int),
        "top1_if": scored["top1_if"].astype(bool),
        "top5_if": scored["top5_if"].astype(bool),
        "score_logvalor": scored["score_logvalor"].astype(float),
        "rank_logvalor": scored["rank_logvalor"].astype(int),
        "top1_logvalor": scored["top1_logvalor"].astype(bool),
        "top5_logvalor": scored["top5_logvalor"].astype(bool),
        "flag_p99_modalidad": scored["flag_p99_modalidad"].astype(bool),
        "valor_del_contrato": scored["valor_del_contrato"],
        "modalidad_grupo": scored["modalidad_grupo"].astype(str),
        "modalidad_de_contratacion": scored["modalidad_de_contratacion"],
        "nombre_entidad": scored["nombre_entidad"],
        "cod_municipio": _col(scored, "cod_municipio"),
        "es_bogota": _col(scored, "es_bogota"),
        "estado_homologacion": _col(scored, "estado_homologacion"),
    }
    return pd.DataFrame(cols)


def tabla_excluidos(
    ceros: pd.DataFrame,
    extremos: pd.DataFrame,
    periodo: str,
    id_ej: str,
    version: str = VERSION_MODELO,
) -> pd.DataFrame:
    if len(ceros) != N_CEROS or len(extremos) != N_EXTREMOS:
        raise RuntimeError(
            f"Excluidos ceros={len(ceros)} extremos={len(extremos)}; "
            f"esperados {N_CEROS} y {N_EXTREMOS}."
        )

    def _bloque(pdf: pd.DataFrame, motivo: str) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "periodo": periodo,
                "version_modelo": version,
                "id_ejecucion": id_ej,
                "id_contrato": pdf["id_contrato"].astype(str),
                "socrata_id": _col(pdf, "socrata_id"),
                "motivo_exclusion": motivo,
                "valor_del_contrato": pdf["valor_del_contrato"],
                "modalidad_de_contratacion": pdf["modalidad_de_contratacion"],
                "nombre_entidad": pdf["nombre_entidad"],
                "cod_municipio": _col(pdf, "cod_municipio"),
                "es_bogota": _col(pdf, "es_bogota"),
            }
        )

    return pd.concat(
        [_bloque(ceros, "valor_cero"), _bloque(extremos, "valor_extremo")],
        ignore_index=True,
    )


def versiones_librerias() -> dict:
    out = {}
    for paq in ("sklearn", "numpy", "pandas", "scipy"):
        mod = __import__(paq)
        out[paq] = getattr(mod, "__version__", "")
    return out


def huella_vector_scores(scores: pd.DataFrame) -> str:
    orden = scores.sort_values("id_contrato")
    raw = orden["score_if"].to_numpy(dtype=np.float64).tobytes()
    return hashlib.sha256(raw).hexdigest()
