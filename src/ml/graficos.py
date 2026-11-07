"""
Figuras PNG de la evaluación de anomalías.

Funciones:
- histograma_log10(): Distribución del valor en escala log10.
- box_modalidad(): Diagramas de caja del valor por modalidad.
- scatter_ranks(): Rangos de Isolation Forest frente a LOF.
- barras_solape(): Solape de los extremos entre modelos.
- barras_composicion(): Composición del extremo superior.
- barras_permutacion(): Importancia por permutación.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .evaluacion import top_ids


def _guardar(fig, ruta: Path) -> Path:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(ruta, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return ruta


def histograma_log10(pdf: pd.DataFrame, ruta: Path) -> Path:
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.hist(pdf["log10_valor"].dropna(), bins=60, color="#3b6d8c", edgecolor="white")
    ax.set_xlabel("log10(valor del contrato)")
    ax.set_ylabel("Contratos")
    ax.set_title("Valor de contratos aptos (septiembre 2026)")
    return _guardar(fig, ruta)


def box_modalidad(pdf: pd.DataFrame, ruta: Path, n=6) -> Path:
    top = pdf["modalidad_de_contratacion"].value_counts().head(n).index
    datos = [
        pdf.loc[pdf["modalidad_de_contratacion"] == m, "log10_valor"].dropna()
        for m in top
    ]
    fig, ax = plt.subplots(figsize=(10, 5))
    nombres = [m[:40] for m in top]
    try:
        ax.boxplot(datos, vert=True, tick_labels=nombres, showfliers=False)
    except TypeError:
        ax.boxplot(datos, vert=True, labels=nombres, showfliers=False)
    ax.set_ylabel("log10(valor)")
    ax.set_title("Valor por modalidad (top 6, sin atípicos del boxplot)")
    plt.setp(ax.get_xticklabels(), rotation=25, ha="right")
    return _guardar(fig, ruta)


def scatter_ranks(pdf: pd.DataFrame, ruta: Path) -> Path:
    r_if = pdf["score_if"].rank(ascending=False, method="average")
    r_lof = pdf["score_lof"].rank(ascending=False, method="average")
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(r_if, r_lof, s=4, alpha=0.15, c="#3b6d8c")
    lim = [1, len(pdf)]
    ax.plot(lim, lim, color="#b4552a", linewidth=1)
    ax.set_xlabel("Rango Isolation Forest (1 = más atípico)")
    ax.set_ylabel("Rango LOF (1 = más atípico)")
    ax.set_title("Acuerdo de ranking IF vs LOF")
    ax.set_xlim(lim)
    ax.set_ylim(lim)
    return _guardar(fig, ruta)


def barras_solape(pdf: pd.DataFrame, ruta: Path, frac: float = 0.05) -> Path:
    a = top_ids(pdf, "score_base", frac)
    b = top_ids(pdf, "score_if", frac)
    c = top_ids(pdf, "score_lof", frac)
    etiquetas = [
        "solo baseline",
        "solo IF",
        "solo LOF",
        "baseline ∩ IF (no LOF)",
        "baseline ∩ LOF (no IF)",
        "IF ∩ LOF (no baseline)",
        "los tres",
    ]
    valores = [
        len(a - b - c),
        len(b - a - c),
        len(c - a - b),
        len((a & b) - c),
        len((a & c) - b),
        len((b & c) - a),
        len(a & b & c),
    ]
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(etiquetas, valores, color="#3b6d8c")
    ax.set_ylabel("Contratos")
    ax.set_title(f"Solape del top {int(frac * 100)} % (baseline, IF, LOF)")
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right")
    return _guardar(fig, ruta)


def barras_composicion(comp: pd.DataFrame, ruta: Path) -> Path:
    sub = comp[comp["modalidad"] != "_es_bogota"].copy()
    top_mod = (
        sub.groupby("modalidad")["pct_universo"].max().sort_values(ascending=False).head(6).index
    )
    sub = sub[sub["modalidad"].isin(top_mod)]
    modelos = ["base", "if", "lof"]
    x = np.arange(len(top_mod))
    ancho = 0.25
    fig, ax = plt.subplots(figsize=(10, 5))
    for i, modelo in enumerate(modelos):
        vals = []
        for m in top_mod:
            fila = sub[(sub["modelo"] == modelo) & (sub["modalidad"] == m)]
            vals.append(float(fila["pct_top"].iloc[0]) if len(fila) else 0.0)
        ax.bar(x + i * ancho, vals, ancho, label=modelo)
    univ = [float(sub[sub["modalidad"] == m]["pct_universo"].iloc[0]) for m in top_mod]
    ax.plot(x + ancho, univ, color="#b4552a", marker="o", label="universo")
    ax.set_xticks(x + ancho)
    ax.set_xticklabels([m[:32] for m in top_mod], rotation=25, ha="right")
    ax.set_ylabel("% del top 5 %")
    ax.set_title("Modalidad en el top 5 % frente al universo")
    ax.legend()
    return _guardar(fig, ruta)


def barras_permutacion(imp: pd.DataFrame, ruta: Path) -> Path:
    fig, ax = plt.subplots(figsize=(8, 4))
    y = np.arange(len(imp))
    ax.barh(y, imp["caida"], color="#3b6d8c")
    ax.set_yticks(y)
    ax.set_yticklabels(imp["variable"])
    ax.invert_yaxis()
    ax.set_xlabel("Caída de Spearman al barajar")
    ax.set_title("Importancia por permutación (Isolation Forest)")
    return _guardar(fig, ruta)
