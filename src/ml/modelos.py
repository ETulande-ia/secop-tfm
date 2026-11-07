"""
Isolation Forest, LOF y baseline por modalidad. Una puntuación mayor indica más atípico.

Funciones:
- score_baseline_modalidad(): Puntúa el valor dentro de cada modalidad.
- entrenar_isolation_forest(): Ajusta Isolation Forest.
- entrenar_lof(): Ajusta Local Outlier Factor.
- ajustar_tres(): Entrena los tres modelos sobre la misma matriz.
"""

from __future__ import annotations

from time import perf_counter

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor

SEMILLA = 42
N_ESTIMADORES = 200
N_VECINOS = 20
CONTAMINACION = 0.05


def score_baseline_modalidad(pdf: pd.DataFrame) -> pd.DataFrame:
    """P99 de log1p_valor dentro de cada modalidad + ranking por log-valor.

    `score_base` es el log-valor (mayor = más atípico).
    `flag_p99_mod` marca si supera el P99 de su grupo.
    """
    out = pdf.copy()
    p99 = out.groupby("modalidad_grupo")["log1p_valor"].transform(
        lambda s: s.quantile(0.99)
    )
    out["score_base"] = out["log1p_valor"]
    out["flag_p99_mod"] = (out["log1p_valor"] >= p99).astype(int)
    out["p99_mod"] = p99
    return out


def entrenar_isolation_forest(
    X: np.ndarray,
    random_state: int = SEMILLA,
    contamination: float = CONTAMINACION,
    n_estimators: int = N_ESTIMADORES,
):
    t0 = perf_counter()
    modelo = IsolationForest(
        n_estimators=n_estimators,
        contamination=contamination,
        random_state=random_state,
        n_jobs=-1,
    )
    modelo.fit(X)
    score = -modelo.decision_function(X)
    return modelo, score, perf_counter() - t0


def entrenar_lof(
    X: np.ndarray,
    n_neighbors: int = N_VECINOS,
    contamination: float = CONTAMINACION,
):
    t0 = perf_counter()
    modelo = LocalOutlierFactor(
        n_neighbors=n_neighbors,
        contamination=contamination,
        n_jobs=-1,
    )
    modelo.fit(X)
    score = -modelo.negative_outlier_factor_
    return modelo, score, perf_counter() - t0


def ajustar_tres(
    X: np.ndarray,
    pdf: pd.DataFrame,
    random_state: int = SEMILLA,
    contamination: float = CONTAMINACION,
    n_neighbors: int = N_VECINOS,
):
    """Misma matriz: baseline + IF + LOF. Devuelve puntuaciones, tiempos y modelos."""
    base = score_baseline_modalidad(pdf)
    modelo_if, score_if, t_if = entrenar_isolation_forest(
        X, random_state=random_state, contamination=contamination
    )
    modelo_lof, score_lof, t_lof = entrenar_lof(
        X, n_neighbors=n_neighbors, contamination=contamination
    )
    out = base.copy()
    out["score_if"] = score_if
    out["score_lof"] = score_lof
    tiempos = {"if_s": round(t_if, 3), "lof_s": round(t_lof, 3)}
    return out, tiempos, modelo_if, modelo_lof
