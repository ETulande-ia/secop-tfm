"""
Solape, estabilidad, sensibilidad e inspección. No calcula métricas de fraude.

Funciones:
- solape_tops(): Mide el solape de los extremos entre puntuaciones.
- correlacion_rankings(): Correlación de Spearman entre rankings.
- estabilidad_if(): Estabilidad de Isolation Forest al cambiar la semilla.
- estabilidad_submuestra(): Estabilidad al retirar una submuestra.
- sensibilidad_vecinos(): Sensibilidad de LOF al número de vecinos.
- importancia_permutacion(): Importancia de variables por permutación.
- inspeccion(): Arma la muestra de casos extremos.
- composicion(): Describe la composición del extremo superior.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from .modelos import entrenar_isolation_forest, entrenar_lof


def top_ids(pdf: pd.DataFrame, col_score: str, frac: float) -> set[str]:
    k = max(1, int(round(len(pdf) * frac)))
    return set(pdf.nlargest(k, col_score)["id_contrato"].astype(str))


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    u = len(a | b)
    return 0.0 if u == 0 else len(a & b) / u


def solape_tops(pdf: pd.DataFrame, fracs=(0.01, 0.05)) -> pd.DataFrame:
    filas = []
    pares = [
        ("base", "if", "score_base", "score_if"),
        ("base", "lof", "score_base", "score_lof"),
        ("if", "lof", "score_if", "score_lof"),
    ]
    n = len(pdf)
    for frac in fracs:
        k = max(1, int(round(n * frac)))
        sets = {}
        for nombre, col in (
            ("base", "score_base"),
            ("if", "score_if"),
            ("lof", "score_lof"),
            ("p99mod", "flag_p99_mod"),
        ):
            if nombre == "p99mod":
                sets[nombre] = set(
                    pdf.loc[pdf[col] == 1, "id_contrato"].astype(str)
                )
            else:
                sets[nombre] = top_ids(pdf, col, frac)
        fila = {"frac": frac, "k": k, "n_p99mod": len(sets["p99mod"])}
        for a, b, _, _ in pares:
            inter = sets[a] & sets[b]
            n_inter = len(inter)
            fila[f"jaccard_{a}_{b}"] = round(jaccard(sets[a], sets[b]), 4)
            fila[f"n_{a}_{b}"] = n_inter
            fila[f"coinc_{a}_{b}"] = round(n_inter / k, 4)
        for nombre in ("base", "if", "lof"):
            inter_p = sets[nombre] & sets["p99mod"]
            fila[f"n_{nombre}_p99"] = len(inter_p)
            fila[f"coinc_{nombre}_p99"] = round(len(inter_p) / k, 4)
            fila[f"jaccard_{nombre}_p99"] = round(jaccard(sets[nombre], sets["p99mod"]), 4)
        fila["jaccard_if_lof_p99"] = round(
            jaccard(sets["if"] & sets["lof"], sets["p99mod"]), 4
        )
        fila["n_if_lof_p99"] = len(sets["if"] & sets["lof"] & sets["p99mod"])
        filas.append(fila)
    return pd.DataFrame(filas)


def correlacion_rankings(pdf: pd.DataFrame) -> pd.DataFrame:
    filas = []
    for a, b in (("score_base", "score_if"), ("score_base", "score_lof"), ("score_if", "score_lof")):
        rho, p = spearmanr(pdf[a], pdf[b])
        filas.append({"par": f"{a} vs {b}", "spearman": round(float(rho), 4), "p": float(p)})
    return pd.DataFrame(filas)


def estabilidad_if(
    X: np.ndarray,
    ids: pd.Series,
    semillas: list[int],
    frac: float = 0.05,
) -> pd.DataFrame:
    scores = {}
    tops = {}
    for s in semillas:
        _, sc, _ = entrenar_isolation_forest(X, random_state=s)
        scores[s] = sc
        k = max(1, int(round(len(ids) * frac)))
        orden = np.argsort(-sc)[:k]
        tops[s] = set(ids.iloc[orden].astype(str))
    filas = []
    pares = [(semillas[i], semillas[j]) for i in range(len(semillas)) for j in range(i + 1, len(semillas))]
    for a, b in pares:
        rho, _ = spearmanr(scores[a], scores[b])
        filas.append(
            {
                "semilla_a": a,
                "semilla_b": b,
                "spearman": round(float(rho), 4),
                "jaccard_top5": round(jaccard(tops[a], tops[b]), 4),
            }
        )
    return pd.DataFrame(filas)


def estabilidad_submuestra(
    X: np.ndarray,
    ids: pd.Series,
    n_rep: int = 5,
    frac_muestra: float = 0.8,
    frac_top: float = 0.05,
    semilla: int = 42,
) -> pd.DataFrame:
    rng = np.random.default_rng(semilla)
    n = X.shape[0]
    m = max(2, int(round(n * frac_muestra)))
    tops = []
    for i in range(n_rep):
        idx = rng.choice(n, size=m, replace=False)
        _, sc, _ = entrenar_isolation_forest(X[idx], random_state=semilla + i)
        k = max(1, int(round(m * frac_top)))
        orden = np.argsort(-sc)[:k]
        tops.append(set(ids.iloc[idx[orden]].astype(str)))
    filas = []
    for i in range(n_rep):
        for j in range(i + 1, n_rep):
            filas.append(
                {
                    "rep_a": i,
                    "rep_b": j,
                    "jaccard_top5": round(jaccard(tops[i], tops[j]), 4),
                }
            )
    return pd.DataFrame(filas)


def sensibilidad_vecinos(
    X: np.ndarray,
    ids: pd.Series,
    vecinos=(20, 50),
    frac: float = 0.05,
) -> pd.DataFrame:
    tops = {}
    for k in vecinos:
        _, sc, t = entrenar_lof(X, n_neighbors=k)
        tops[k] = (top_ids(pd.DataFrame({"id_contrato": ids, "s": sc}), "s", frac), t, sc)
    a, b = vecinos[0], vecinos[1]
    rho, _ = spearmanr(tops[a][2], tops[b][2])
    return pd.DataFrame(
        [
            {
                "vecinos_a": a,
                "vecinos_b": b,
                "jaccard_top5": round(jaccard(tops[a][0], tops[b][0]), 4),
                "spearman": round(float(rho), 4),
                "tiempo_a_s": round(tops[a][1], 3),
                "tiempo_b_s": round(tops[b][1], 3),
            }
        ]
    )


def importancia_permutacion(
    X: np.ndarray,
    nombres: list[str],
    score_orig: np.ndarray,
    modelo_if,
    semilla: int = 42,
    n_rep: int = 3,
) -> pd.DataFrame:
    """Caída de Spearman del score IF al barajar cada columna. No es causal."""
    rng = np.random.default_rng(semilla)
    filas = []
    for j, nombre in enumerate(nombres):
        rhos = []
        for _ in range(n_rep):
            Xs = X.copy()
            rng.shuffle(Xs[:, j])
            sc = -modelo_if.decision_function(Xs)
            rho, _ = spearmanr(score_orig, sc)
            rhos.append(float(rho))
        filas.append(
            {
                "variable": nombre,
                "spearman_medio_barajada": round(float(np.mean(rhos)), 4),
                "caida": round(1.0 - float(np.mean(rhos)), 4),
            }
        )
    return pd.DataFrame(filas).sort_values("caida", ascending=False)


def inspeccion(pdf: pd.DataFrame, n_if: int = 10, n_lof: int = 10) -> pd.DataFrame:
    cols = [
        c
        for c in [
            "id_contrato",
            "socrata_id",
            "nombre_entidad",
            "departamento",
            "ciudad",
            "proveedor_adjudicado",
            "modalidad_de_contratacion",
            "valor_del_contrato",
            "log1p_valor",
            "dias_ejecucion",
            "plazo_invalido",
            "n_entidad",
            "es_bogota",
            "estado_homologacion",
            "score_base",
            "score_if",
            "score_lof",
            "flag_p99_mod",
        ]
        if c in pdf.columns
    ]
    ranked = pdf.assign(
        rank_base=pdf["score_base"].rank(ascending=False, method="min").astype(int),
        rank_if=pdf["score_if"].rank(ascending=False, method="min").astype(int),
        rank_lof=pdf["score_lof"].rank(ascending=False, method="min").astype(int),
    )
    top_if = ranked.nlargest(n_if, "score_if")
    top_lof = ranked.nlargest(n_lof, "score_lof")
    out = pd.concat([top_if, top_lof]).drop_duplicates("id_contrato")
    if len(out) < 20:
        resto = ranked[~ranked["id_contrato"].isin(out["id_contrato"])].nlargest(
            20 - len(out), "score_if"
        )
        out = pd.concat([out, resto])
    extra = [c for c in ("rank_base", "rank_if", "rank_lof") if c not in cols]
    return out[cols + extra].sort_values("rank_if")


def conteo_venn(pdf: pd.DataFrame, frac: float = 0.05) -> pd.DataFrame:
    a = top_ids(pdf, "score_base", frac)
    b = top_ids(pdf, "score_if", frac)
    c = top_ids(pdf, "score_lof", frac)
    k = max(1, int(round(len(pdf) * frac)))
    return pd.DataFrame(
        [
            {"conjunto": "solo_base", "n": len(a - b - c), "k": k, "frac": frac},
            {"conjunto": "solo_if", "n": len(b - a - c), "k": k, "frac": frac},
            {"conjunto": "solo_lof", "n": len(c - a - b), "k": k, "frac": frac},
            {"conjunto": "base_if", "n": len((a & b) - c), "k": k, "frac": frac},
            {"conjunto": "base_lof", "n": len((a & c) - b), "k": k, "frac": frac},
            {"conjunto": "if_lof", "n": len((b & c) - a), "k": k, "frac": frac},
            {"conjunto": "tres", "n": len(a & b & c), "k": k, "frac": frac},
        ]
    )


def composicion(pdf: pd.DataFrame, frac: float = 0.05) -> pd.DataFrame:
    k = max(1, int(round(len(pdf) * frac)))
    filas = []
    base_mod = pdf["modalidad_de_contratacion"].value_counts(normalize=True)
    base_bog = float(pdf["es_bogota"].mean()) if "es_bogota" in pdf.columns else None
    for nombre, col in (("base", "score_base"), ("if", "score_if"), ("lof", "score_lof")):
        top = pdf.nlargest(k, col)
        mods = top["modalidad_de_contratacion"].value_counts(normalize=True)
        for mod, pct in mods.items():
            filas.append(
                {
                    "modelo": nombre,
                    "modalidad": mod,
                    "pct_top": round(100 * float(pct), 2),
                    "pct_universo": round(100 * float(base_mod.get(mod, 0)), 2),
                }
            )
        filas.append(
            {
                "modelo": nombre,
                "modalidad": "_es_bogota",
                "pct_top": round(100 * float(top["es_bogota"].mean()), 2)
                if "es_bogota" in top.columns
                else None,
                "pct_universo": round(100 * base_bog, 2) if base_bog is not None else None,
            }
        )
    return pd.DataFrame(filas)
