"""
Orquesta los experimentos C0–C5 sobre la misma matriz y el mismo universo.

Funciones:
- correr(): Ejecuta un experimento.
- elegir_ganador(): Elige C1 o C3 según el solape del extremo superior.
- ficha_ceros(): Resume los contratos de valor cero.
- ficha_extremo(): Resume los registros de valor extremo.
- correr_fase(): Corre la fase completa y guarda el resumen.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .evaluacion import (
    composicion,
    conteo_venn,
    correlacion_rankings,
    estabilidad_if,
    estabilidad_submuestra,
    importancia_permutacion,
    inspeccion,
    jaccard,
    sensibilidad_vecinos,
    solape_tops,
    top_ids,
)
from .features import (
    a_pandas,
    conteo_entidad_mes,
    enriquecer,
    informe_plazo,
    matriz,
    partir_universo,
    redundancia,
)
from .graficos import (
    barras_composicion,
    barras_permutacion,
    barras_solape,
    box_modalidad,
    histograma_log10,
    scatter_ranks,
)
from .lectura import leer_contratos_modelo
from .modelos import SEMILLA, ajustar_tres

N_APTOS = 82457
N_CEROS = 506
N_EXTREMOS = 1
SEMILLAS_EST = [42, 7, 13, 99, 2026]


def _guardar(df: pd.DataFrame, ruta: Path) -> Path:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(ruta, index=False)
    return ruta


def correr(
    pdf,
    numericas,
    dummies=False,
    imputar_plazo=False,
    incluir_flag_plazo=True,
    semilla=SEMILLA,
    vecinos=20,
):
    X, nombres, scaler = matriz(
        pdf,
        numericas,
        dummies_modalidad=dummies,
        imputar_plazo_mediana=imputar_plazo,
        incluir_flag_plazo=incluir_flag_plazo,
    )
    scored, tiempos, modelo_if, modelo_lof = ajustar_tres(
        X, pdf, random_state=semilla, n_neighbors=vecinos
    )
    return {
        "X": X,
        "nombres": nombres,
        "scaler": scaler,
        "scored": scored,
        "tiempos": tiempos,
        "modelo_if": modelo_if,
        "modelo_lof": modelo_lof,
        "solape": solape_tops(scored),
        "spearman": correlacion_rankings(scored),
        "composicion": composicion(scored),
        "venn": conteo_venn(scored),
        "casos": inspeccion(scored),
    }


def _metricas_exp(eid: str, res: dict) -> dict:
    s05 = res["solape"][res["solape"]["frac"] == 0.05].iloc[0]
    s01 = res["solape"][res["solape"]["frac"] == 0.01].iloc[0]
    sp = {r["par"]: r["spearman"] for _, r in res["spearman"].iterrows()}
    return {
        "experimento": eid,
        "matriz": " + ".join(res["nombres"]),
        "n_vars": len(res["nombres"]),
        "if_s": res["tiempos"]["if_s"],
        "lof_s": res["tiempos"]["lof_s"],
        "jaccard_if_lof_1": float(s01["jaccard_if_lof"]),
        "jaccard_base_if_1": float(s01["jaccard_base_if"]),
        "jaccard_base_lof_1": float(s01["jaccard_base_lof"]),
        "n_if_lof_1": int(s01["n_if_lof"]),
        "jaccard_if_lof_5": float(s05["jaccard_if_lof"]),
        "jaccard_base_if_5": float(s05["jaccard_base_if"]),
        "jaccard_base_lof_5": float(s05["jaccard_base_lof"]),
        "n_if_lof_5": int(s05["n_if_lof"]),
        "spearman_base_if": sp.get("score_base vs score_if"),
        "spearman_base_lof": sp.get("score_base vs score_lof"),
        "spearman_if_lof": sp.get("score_if vs score_lof"),
    }


def elegir_ganador(corridos: dict, plazo_confiable: bool) -> tuple[str, str]:
    """Heurística de la corrida C0–C5: si C3 se aparta de C1, se usó C3.

    No es un criterio de calidad. La revisión metodológica (docs/10)
    recomienda C1 para la fase siguiente: el apartamiento de C3 lo explica
    `plazo_invalido`, no un mejor ranking contractual.
    """
    if "C1" not in corridos:
        raise RuntimeError("C1 es obligatorio para elegir matriz.")
    c1 = corridos["C1"]["scored"]
    rica = "C3" if "C3" in corridos else ("C2" if "C2" in corridos else "C1")
    if rica == "C1":
        nota = "Solo C1 disponible."
        return "C1", nota
    jac = jaccard(top_ids(c1, "score_if", 0.05), top_ids(corridos[rica]["scored"], "score_if", 0.05))
    if jac >= 0.85:
        nota = (
            f"El top 5 % IF de {rica} coincide con C1 (Jaccard={jac:.3f}); "
            "se elige C1 por parsimonia."
        )
        return "C1", nota
    extra = ""
    if not plazo_confiable and rica == "C3":
        extra = " El plazo no se consideró confiable y no entra en C3."
    nota = (
        f"{rica} mueve el ranking IF respecto de C1 (Jaccard top 5 %={jac:.3f}). "
        f"Se usa {rica} en C4 e inspección.{extra}"
    )
    return rica, nota


def ficha_ceros(ceros: pd.DataFrame) -> pd.DataFrame:
    filas = [
        {"campo": "n", "valor": len(ceros)},
        {
            "campo": "modalidad_mas_frecuente",
            "valor": (
                ceros["modalidad_de_contratacion"].value_counts().index[0]
                if len(ceros)
                else None
            ),
        },
        {
            "campo": "n_entidades",
            "valor": int(ceros["nombre_entidad"].nunique()) if len(ceros) else 0,
        },
        {
            "campo": "n_bogota",
            "valor": int(ceros["es_bogota"].sum()) if "es_bogota" in ceros.columns else None,
        },
    ]
    if "estado_contrato" in ceros.columns and len(ceros):
        top = ceros["estado_contrato"].value_counts().head(5)
        for est, n in top.items():
            filas.append({"campo": f"estado:{est}", "valor": int(n)})
    return pd.DataFrame(filas)


def ficha_extremo(extremos: pd.DataFrame) -> pd.DataFrame:
    cols = [
        c
        for c in [
            "id_contrato",
            "socrata_id",
            "nombre_entidad",
            "ciudad",
            "proveedor_adjudicado",
            "modalidad_de_contratacion",
            "valor_del_contrato",
            "estado_contrato",
            "fecha_de_firma",
        ]
        if c in extremos.columns
    ]
    return extremos[cols].copy()


def correr_fase(spark, periodo: str, salidas: Path, semilla: int = SEMILLA) -> dict:
    """Lee tfm.contrato (solo lectura), corre C0–C5 y escribe CSV/PNG."""
    salidas = Path(salidas)
    figuras = salidas / "figuras"
    salidas.mkdir(parents=True, exist_ok=True)
    figuras.mkdir(parents=True, exist_ok=True)

    df = leer_contratos_modelo(spark, periodo)
    pdf = a_pandas(df)
    partes = partir_universo(pdf)
    aptos_raw, ceros, extremos = partes["aptos"], partes["ceros"], partes["extremos"]
    if len(aptos_raw) != N_APTOS:
        raise RuntimeError(f"Aptos={len(aptos_raw)}, esperado {N_APTOS}. No se entrena.")
    if len(ceros) != N_CEROS or len(extremos) != N_EXTREMOS:
        raise RuntimeError(
            f"Ceros={len(ceros)} extremos={len(extremos)}; "
            f"esperados {N_CEROS} y {N_EXTREMOS}."
        )

    n_ent = conteo_entidad_mes(pdf)
    aptos = enriquecer(aptos_raw, n_entidad=n_ent)
    plazo = informe_plazo(aptos)
    cols_red = [
        c
        for c in ["log1p_valor", "log_valor_vs_modalidad", "dias_ejecucion", "log1p_n_entidad"]
        if c in aptos.columns
    ]
    red = redundancia(aptos, cols_red)

    universo = pd.DataFrame(
        [
            {"conjunto": "tfm.contrato", "n": len(pdf), "uso": "descriptivo"},
            {"conjunto": "valor_apto_modelo", "n": len(aptos), "uso": "entrenamiento y ranking"},
            {"conjunto": "valor_cero", "n": len(ceros), "uso": "ficha C5, fuera del ajuste"},
            {"conjunto": "valor_extremo", "n": len(extremos), "uso": "ficha C5, fuera del ajuste"},
            {
                "conjunto": "es_bogota y apto",
                "n": int(aptos["es_bogota"].sum()),
                "uso": "recorte C4",
            },
        ]
    )
    _guardar(universo, salidas / "universo.csv")
    _guardar(pd.DataFrame([plazo]), salidas / "informe_plazo.csv")
    _guardar(red.reset_index().rename(columns={"index": "variable"}), salidas / "redundancia.csv")

    corridos = {}
    print("C0: log1p_valor", flush=True)
    corridos["C0"] = correr(aptos, ["log1p_valor"], dummies=False, semilla=semilla)
    print("C0 tiempos", corridos["C0"]["tiempos"], flush=True)

    numericas_c1 = ["log1p_valor", "log_valor_vs_modalidad"]
    if abs(float(red.loc["log1p_valor", "log_valor_vs_modalidad"])) >= 0.95:
        numericas_c1 = ["log_valor_vs_modalidad"]
    print("C1:", numericas_c1, "+ dummies", flush=True)
    corridos["C1"] = correr(aptos, numericas_c1, dummies=True, semilla=semilla)
    print("C1 tiempos", corridos["C1"]["tiempos"], flush=True)

    if plazo["plazo_confiable"]:
        print("C2: + dias_ejecucion", flush=True)
        corridos["C2"] = correr(
            aptos,
            numericas_c1 + ["dias_ejecucion"],
            dummies=True,
            imputar_plazo=True,
            semilla=semilla,
        )
        print("C2 tiempos", corridos["C2"]["tiempos"], flush=True)
        num_c3 = numericas_c1 + ["dias_ejecucion", "log1p_n_entidad"]
        print("C3:", num_c3, flush=True)
        corridos["C3"] = correr(
            aptos, num_c3, dummies=True, imputar_plazo=True, semilla=semilla
        )
        print("C3 tiempos", corridos["C3"]["tiempos"], flush=True)
    else:
        print("C2 omitido: plazo no confiable", flush=True)
        print("C3: C1 + log1p_n_entidad", flush=True)
        corridos["C3"] = correr(
            aptos,
            numericas_c1 + ["log1p_n_entidad"],
            dummies=True,
            semilla=semilla,
        )
        print("C3 tiempos", corridos["C3"]["tiempos"], flush=True)

    ganador, nota_ganador = elegir_ganador(corridos, plazo["plazo_confiable"])
    print("ganador", ganador, nota_ganador, flush=True)
    g = corridos[ganador]
    bog = aptos[aptos["es_bogota"]].copy()
    num_g = [c for c in g["nombres"] if not c.startswith("mod_") and c != "plazo_invalido"]
    usa_plazo = "dias_ejecucion" in num_g
    corridos["C4"] = correr(
        bog,
        num_g,
        dummies=True,
        imputar_plazo=usa_plazo,
        semilla=semilla,
    )

    metricas = pd.DataFrame([_metricas_exp(k, v) for k, v in corridos.items()])
    _guardar(metricas, salidas / "metricas_experimentos.csv")

    for eid, res in corridos.items():
        pref = salidas / eid.lower()
        _guardar(res["solape"], pref.with_name(f"{eid.lower()}_solape.csv"))
        _guardar(res["spearman"], pref.with_name(f"{eid.lower()}_spearman.csv"))
        _guardar(res["composicion"], pref.with_name(f"{eid.lower()}_composicion.csv"))
        _guardar(res["venn"], pref.with_name(f"{eid.lower()}_venn.csv"))
        _guardar(res["casos"], pref.with_name(f"{eid.lower()}_inspeccion.csv"))
        pd.Series(res["nombres"], name="variable").to_csv(
            pref.with_name(f"{eid.lower()}_variables.csv"), index=False
        )

    ids = aptos["id_contrato"]
    print("estabilidad IF semillas", flush=True)
    est_sem = estabilidad_if(g["X"], ids, SEMILLAS_EST)
    print("estabilidad submuestra", flush=True)
    est_sub = estabilidad_submuestra(g["X"], ids)
    print("sensibilidad LOF 20 vs 50", flush=True)
    sens_k = sensibilidad_vecinos(g["X"], ids, vecinos=(20, 50))
    print("permutacion IF", flush=True)
    imp = importancia_permutacion(
        g["X"], g["nombres"], g["scored"]["score_if"].to_numpy(), g["modelo_if"]
    )
    casos = inspeccion(g["scored"], n_if=12, n_lof=12)
    _guardar(est_sem, salidas / "estabilidad_semillas.csv")
    _guardar(est_sub, salidas / "estabilidad_submuestra.csv")
    _guardar(sens_k, salidas / "sensibilidad_vecinos.csv")
    _guardar(imp, salidas / "importancia_permutacion.csv")
    _guardar(casos, salidas / "inspeccion_20.csv")
    _guardar(g["scored"][["id_contrato", "score_base", "score_if", "score_lof", "flag_p99_mod"]],
             salidas / "puntuaciones_ganador.csv")

    top_nac = top_ids(g["scored"][g["scored"]["es_bogota"]], "score_if", 0.05)
    top_c4 = top_ids(corridos["C4"]["scored"], "score_if", 0.05)
    solape_c4 = pd.DataFrame(
        [
            {
                "n_bogota_aptos": int(aptos["es_bogota"].sum()),
                "n_top5_nacional_en_bogota": len(top_nac),
                "n_top5_c4": len(top_c4),
                "jaccard_if_nacional_vs_c4": round(jaccard(top_nac, top_c4), 4),
                "n_comun": len(top_nac & top_c4),
            }
        ]
    )
    _guardar(solape_c4, salidas / "c4_vs_nacional.csv")

    ficha_c = ficha_ceros(ceros)
    ficha_e = ficha_extremo(extremos)
    _guardar(ficha_c, salidas / "c5_ceros.csv")
    _guardar(ficha_e, salidas / "c5_extremo.csv")
    if len(ceros):
        _guardar(
            ceros["modalidad_de_contratacion"].value_counts().rename("n").reset_index(),
            salidas / "c5_ceros_modalidad.csv",
        )
        _guardar(
            ceros["nombre_entidad"].value_counts().head(15).rename("n").reset_index(),
            salidas / "c5_ceros_entidad.csv",
        )

    histograma_log10(aptos, figuras / "hist_log10_valor.png")
    box_modalidad(aptos, figuras / "box_log10_modalidad.png")
    scatter_ranks(g["scored"], figuras / "scatter_ranks_if_lof.png")
    barras_solape(g["scored"], figuras / "solape_top5.png")
    barras_composicion(g["composicion"], figuras / "composicion_modalidad.png")
    barras_permutacion(imp, figuras / "permutacion_if.png")

    decisiones = pd.DataFrame(
        [
            {"decision": "universo", "detalle": f"{len(aptos)} aptos; ceros y extremo fuera del ajuste"},
            {"decision": "plazo_confiable", "detalle": str(plazo["plazo_confiable"])},
            {"decision": "pct_plazo_valido", "detalle": str(plazo["pct_validos"])},
            {
                "decision": "C2",
                "detalle": "ejecutado" if "C2" in corridos else "omitido: plazo no confiable",
            },
            {
                "decision": "numericas_c1",
                "detalle": " + ".join(numericas_c1),
            },
            {"decision": "ganador", "detalle": ganador},
            {"decision": "nota_ganador", "detalle": nota_ganador},
            {"decision": "semilla", "detalle": str(semilla)},
            {"decision": "escribir_pg", "detalle": "false"},
        ]
    )
    _guardar(decisiones, salidas / "decisiones.csv")

    resumen = {
        "periodo": periodo,
        "n_aptos": int(len(aptos)),
        "n_ceros": int(len(ceros)),
        "n_extremos": int(len(extremos)),
        "plazo": plazo,
        "ganador": ganador,
        "nota_ganador": nota_ganador,
        "metricas": metricas.to_dict(orient="records"),
        "estabilidad_semillas_jaccard_medio": float(est_sem["jaccard_top5"].mean()),
        "estabilidad_semillas_spearman_medio": float(est_sem["spearman"].mean()),
        "estabilidad_submuestra_jaccard_medio": float(est_sub["jaccard_top5"].mean()),
        "lof_20_vs_50": sens_k.to_dict(orient="records")[0],
        "c4": solape_c4.to_dict(orient="records")[0],
        "n_inspeccion": int(len(casos)),
    }
    (salidas / "resumen.json").write_text(
        json.dumps(resumen, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return {
        "aptos": aptos,
        "ceros": ceros,
        "extremos": extremos,
        "plazo": plazo,
        "redundancia": red,
        "corridos": corridos,
        "ganador": ganador,
        "nota_ganador": nota_ganador,
        "metricas": metricas,
        "estabilidad_semillas": est_sem,
        "estabilidad_submuestra": est_sub,
        "sensibilidad_vecinos": sens_k,
        "importancia": imp,
        "casos": casos,
        "ficha_ceros": ficha_c,
        "ficha_extremo": ficha_e,
        "solape_c4": solape_c4,
        "resumen": resumen,
        "salidas": salidas,
    }
