"""
Revisión metodológica de C0–C5. No escribe en PostgreSQL ni cambia las reglas.

Funciones:
- cuadro_desde_solape(): Resume coincidencias entre experimentos.
- perfil_top(): Describe el extremo superior de un ranking.
- comparar_variantes(): Compara variantes sobre el mismo universo.
- revisar(): Ejecuta la revisión y guarda sus cuadros.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from .evaluacion import jaccard, solape_tops, top_ids
from .experimentos import _guardar, correr
from .features import a_pandas, conteo_entidad_mes, enriquecer, informe_plazo, partir_universo
from .lectura import leer_contratos_modelo
from .modelos import SEMILLA


def coincidencia(n_inter: int, k: int) -> float:
    """|A ∩ B| / k, con |A| = |B| = k. Distinto de Jaccard."""
    return 0.0 if k == 0 else n_inter / k


def jaccard_iguales(n_inter: int, k: int) -> float:
    """Jaccard de dos conjuntos del mismo tamaño k."""
    union = 2 * k - n_inter
    return 0.0 if union == 0 else n_inter / union


def cuadro_desde_solape(salidas: Path) -> pd.DataFrame:
    """Recalcula coincidencia y Jaccard a partir de los CSV ya guardados."""
    filas = []
    for eid in ("C0", "C1", "C2", "C3", "C4"):
        ruta = salidas / f"{eid.lower()}_solape.csv"
        if not ruta.exists():
            continue
        df = pd.read_csv(ruta)
        for _, r in df.iterrows():
            k = int(r["k"])
            for par, col in (
                ("base_if", "n_base_if"),
                ("base_lof", "n_base_lof"),
                ("if_lof", "n_if_lof"),
            ):
                n = int(r[col])
                filas.append(
                    {
                        "experimento": eid,
                        "frac": float(r["frac"]),
                        "k": k,
                        "par": par,
                        "n_interseccion": n,
                        "coincidencia": round(coincidencia(n, k), 4),
                        "jaccard": round(jaccard_iguales(n, k), 4),
                        "jaccard_guardado": float(r[f"jaccard_{par}"]),
                        "jaccard_ok": abs(
                            round(jaccard_iguales(n, k), 4)
                            - round(float(r[f"jaccard_{par}"]), 4)
                        )
                        <= 0.0002,
                    }
                )
    return pd.DataFrame(filas)


def perfil_top(scored: pd.DataFrame, col: str, frac: float, universo: pd.DataFrame) -> dict:
    k = max(1, int(round(len(scored) * frac)))
    top = scored.nlargest(k, col)
    med_u = float(universo["valor_del_contrato"].median())
    med_t = float(top["valor_del_contrato"].median())
    return {
        "modelo": col.replace("score_", ""),
        "frac": frac,
        "k": k,
        "mediana_valor": med_t,
        "mediana_valor_universo": med_u,
        "ratio_mediana": None if med_u == 0 else round(med_t / med_u, 3),
        "pct_plazo_invalido": round(100 * float(top["plazo_invalido"].mean()), 2),
        "pct_plazo_invalido_universo": round(100 * float(universo["plazo_invalido"].mean()), 2),
        "pct_directa": round(
            100 * float((top["modalidad_de_contratacion"] == "Contratación directa").mean()),
            2,
        ),
        "pct_directa_universo": round(
            100
            * float((universo["modalidad_de_contratacion"] == "Contratación directa").mean()),
            2,
        ),
        "pct_p99mod": round(100 * float(top["flag_p99_mod"].mean()), 2),
        "n_p99mod": int(top["flag_p99_mod"].sum()),
        "mediana_n_entidad": float(top["n_entidad"].median()),
        "mediana_n_entidad_universo": float(universo["n_entidad"].median()),
    }


def comparar_variantes(variantes: dict, frac: float = 0.05) -> pd.DataFrame:
    nombres = list(variantes)
    filas = []
    for i, a in enumerate(nombres):
        for b in nombres[i + 1 :]:
            sa, sb = variantes[a]["scored"], variantes[b]["scored"]
            for col in ("score_if", "score_lof"):
                ia = top_ids(sa, col, frac)
                ib = top_ids(sb, col, frac)
                rho, _ = spearmanr(sa[col], sb[col])
                filas.append(
                    {
                        "matriz_a": a,
                        "matriz_b": b,
                        "modelo": col.replace("score_", ""),
                        "frac": frac,
                        "n_interseccion": len(ia & ib),
                        "coincidencia": round(len(ia & ib) / max(len(ia), 1), 4),
                        "jaccard": round(jaccard(ia, ib), 4),
                        "spearman": round(float(rho), 4),
                    }
                )
    return pd.DataFrame(filas)


def revisar(spark, periodo: str, salidas: Path, semilla: int = SEMILLA) -> dict:
    """Ablación de plazo/calidad y métricas de solape. No pisa C0–C5 salvo archivos revision_*."""
    salidas = Path(salidas)
    coinc = cuadro_desde_solape(salidas)
    _guardar(coinc, salidas / "revision_coincidencias.csv")

    df = leer_contratos_modelo(spark, periodo)
    pdf = a_pandas(df)
    partes = partir_universo(pdf)
    aptos = enriquecer(partes["aptos"], n_entidad=conteo_entidad_mes(pdf))
    plazo = informe_plazo(aptos)
    numericas_c1 = ["log1p_valor", "log_valor_vs_modalidad"]

    specs = [
        ("C1", numericas_c1, False, True),
        ("C2", numericas_c1 + ["dias_ejecucion"], True, True),
        ("C3", numericas_c1 + ["dias_ejecucion", "log1p_n_entidad"], True, True),
        ("C3_sin_flag", numericas_c1 + ["dias_ejecucion", "log1p_n_entidad"], True, False),
        ("C1_entidad", numericas_c1 + ["log1p_n_entidad"], False, True),
    ]
    variantes = {}
    for nombre, nums, imputar, flag in specs:
        print("revision", nombre, nums, "flag", flag, flush=True)
        variantes[nombre] = correr(
            aptos,
            nums,
            dummies=True,
            imputar_plazo=imputar,
            incluir_flag_plazo=flag,
            semilla=semilla,
        )
        print("  vars", variantes[nombre]["nombres"], variantes[nombre]["tiempos"], flush=True)

    pares = comparar_variantes(variantes, 0.01)
    pares = pd.concat([pares, comparar_variantes(variantes, 0.05)], ignore_index=True)
    _guardar(pares, salidas / "revision_ablacion_matrices.csv")

    perfiles = []
    for nombre, res in variantes.items():
        for col in ("score_base", "score_if", "score_lof"):
            for frac in (0.01, 0.05):
                p = perfil_top(res["scored"], col, frac, aptos)
                p["matriz"] = nombre
                perfiles.append(p)
    perfil = pd.DataFrame(perfiles)
    _guardar(perfil, salidas / "revision_perfil_tops.csv")

    p99_filas = []
    for nombre, res in variantes.items():
        s = solape_tops(res["scored"])
        s.insert(0, "matriz", nombre)
        p99_filas.append(s)
    p99 = pd.concat(p99_filas, ignore_index=True)
    _guardar(p99, salidas / "revision_solape_p99.csv")

    vers = {}
    for paq in ("sklearn", "numpy", "pandas", "scipy", "matplotlib"):
        mod = __import__(paq)
        vers[paq] = getattr(mod, "__version__", "")
    try:
        import pyspark

        vers["pyspark"] = pyspark.__version__
    except Exception:
        vers["pyspark"] = ""
    (salidas / "revision_versiones.json").write_text(
        json.dumps(
            {
                "periodo": periodo,
                "n_aptos": int(len(aptos)),
                "semilla": semilla,
                "n_estimators": 200,
                "n_neighbors": 20,
                "contamination": 0.05,
                "plazo": plazo,
                "versiones": vers,
                "variables": {k: v["nombres"] for k, v in variantes.items()},
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    return {"coincidencias": coinc, "pares": pares, "perfil": perfil, "p99": p99, "versiones": vers}
