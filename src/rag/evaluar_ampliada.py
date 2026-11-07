"""
Validación ampliada de recuperación. No sobrescribe las salidas de las evaluaciones previas.

Funciones:
- evaluar_ampliada(): Mide recall, MRR y cobertura sobre el conjunto ampliado.
- evaluar_cierre(): Evalúa la estrategia B y escribe el cierre sin pisar las salidas anteriores.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .embeddings import MODELO_DEFECTO, embeber_consulta
from .evidencia import clasificar_evidencia
from .indexar import _rango_contexto
from .pruebas import METRICAS_ORIGINALES, mrr, recall_at_k
from .pruebas_ampliadas import (
    METRICAS_12B,
    METRICAS_12C_B,
    PREGUNTAS_AMPLIADAS,
    comprobar_reservados,
    resumen_conjunto,
)
from .pruebas_holdout import PREGUNTAS_HOLDOUT, comprobar_holdout
from .recuperar import buscar
from .rutas import ruta_salidas_rag

SALIDAS_PROHIBIDAS = frozenset({
    "pruebas_recuperacion.csv",
    "pruebas_recuperacion_detalle.csv",
    "metricas_recuperacion.json",
    "pruebas_recuperacion_original.csv",
    "metricas_recuperacion_original.json",
    "pruebas_recuperacion_v2.csv",
    "pruebas_recuperacion_detalle_v2.csv",
    "metricas_recuperacion_v2.json",
    "revision_gold.json",
    "embeddings_text-embedding-3-small.npz",
    "embeddings_meta.json",
    "fragmentos.parquet",
})

SALIDAS_V3 = (
    "pruebas_recuperacion_v3.csv",
    "pruebas_recuperacion_detalle_v3.csv",
    "metricas_recuperacion_v3.json",
    "comparacion_estrategias_v3.json",
    "comparacion_estrategias_v3.csv",
    "cobertura_evidencia_v3.csv",
    "gold_ampliado.json",
)

ESTRATEGIAS = (
    {"id": "A", "nombre": "coseno_top5", "ampliar": False, "hibrido": False},
    {"id": "B", "nombre": "coseno_top5_adyacentes", "ampliar": True, "hibrido": False},
    {"id": "C", "nombre": "hibrido_rrf_top5", "ampliar": False, "hibrido": True},
)


def _guardar_json(ruta: Path, obj) -> None:
    ruta.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _ids_semilla(hits: pd.DataFrame) -> list[str]:
    if hits is None or hits.empty:
        return []
    if "origen" in hits.columns:
        sem = hits[hits["origen"].isin(["coseno", "hibrido"])]
        if len(sem):
            return sem["fragment_id"].tolist()
    return hits["fragment_id"].tolist()


def _ids_todos(hits: pd.DataFrame) -> list[str]:
    if hits is None or hits.empty:
        return []
    return hits["fragment_id"].tolist()


def _confusion(esperado: str, observado: str) -> str:
    if esperado == observado:
        return "acierto"
    if esperado == "no_cubierta" and observado == "suficiente":
        return "falso_positivo"
    if esperado == "suficiente" and observado == "no_cubierta":
        return "falso_negativo"
    if esperado == "no_cubierta" and observado == "parcial":
        return "falso_positivo_suave"
    if esperado == "suficiente" and observado == "parcial":
        return "subestimacion"
    if esperado == "parcial" and observado == "suficiente":
        return "sobreestimacion"
    if esperado == "parcial" and observado == "no_cubierta":
        return "falso_negativo_suave"
    return "desacuerdo"


def evaluar_ampliada(
    indice: dict,
    top_k: int = 5,
    umbral: float = 0.30,
    modelo: str = MODELO_DEFECTO,
    salidas: Path | None = None,
    preguntas: list[dict] | None = None,
) -> dict:
    dest = Path(salidas) if salidas else ruta_salidas_rag()
    dest.mkdir(parents=True, exist_ok=True)
    v3_json = dest / "metricas_recuperacion_v3.json"
    v3_csv = dest / "pruebas_recuperacion_v3.csv"
    if v3_json.is_file() and v3_csv.is_file():
        resumen = pd.read_csv(v3_csv)
        det_p = dest / "pruebas_recuperacion_detalle_v3.csv"
        det = pd.read_csv(det_p) if det_p.is_file() else pd.DataFrame()
        metricas = json.loads(v3_json.read_text(encoding="utf-8"))
        return {
            "resumen": resumen,
            "detalle": det,
            "metricas": metricas,
            "conjunto": resumen_conjunto(preguntas or PREGUNTAS_AMPLIADAS),
            "salidas": dest,
            "v3_conservado": True,
        }
    qs = preguntas if preguntas is not None else PREGUNTAS_AMPLIADAS
    choques = comprobar_reservados(qs)
    if choques:
        raise ValueError(f"Las preguntas chocan con IDs reservados: {choques}")

    vectores = indice["vectores"]
    if tuple(vectores.shape) != (234, 1536):
        raise AssertionError(
            f"Se esperaban embeddings (234, 1536); hay {vectores.shape}."
        )

    cache_vec = {}
    t_emb = []
    filas = []
    detalle = []
    corpus = indice["df"]

    for q in qs:
        if q["pregunta"] not in cache_vec:
            t0 = time.perf_counter()
            cache_vec[q["pregunta"]] = embeber_consulta(q["pregunta"], modelo=modelo)
            t_emb.append(time.perf_counter() - t0)
        qvec = cache_vec[q["pregunta"]]
        gold = list(q.get("relevantes") or [])
        esperado = q["cobertura_esperada"]
        fila = {
            "id": q["id"],
            "tema": q["tema"],
            "tipo": q["tipo"],
            "pregunta": q["pregunta"],
            "en_corpus": q["en_corpus"],
            "doc_id": q.get("doc_id"),
            "cobertura_esperada": esperado,
            "n_gold": len(gold),
            "gold": ";".join(gold) if gold else "(ninguna)",
            "justificacion_gold": q.get("justificacion_gold"),
            "nota": q.get("nota"),
        }
        for est in ESTRATEGIAS:
            res = buscar(
                q["pregunta"],
                indice,
                top_k=top_k,
                umbral=umbral,
                modelo=modelo,
                ampliar=est["ampliar"],
                hibrido=est["hibrido"],
                consulta_vec=qvec,
            )
            hits = res["hits"]
            ids_sem = _ids_semilla(hits)
            ids_all = _ids_todos(hits)
            rec = recall_at_k(ids_sem, gold, top_k) if gold else None
            rec_ctx = recall_at_k(ids_all, gold, max(len(ids_all), 1)) if gold else None
            rango = None
            for i, fid in enumerate(ids_sem, start=1):
                if fid in gold:
                    rango = i
                    break
            if gold and rango is None and est["ampliar"]:
                rango = _rango_contexto(hits, gold)
            textos = hits["texto"].tolist() if len(hits) else []
            evd = clasificar_evidencia(q["pregunta"], textos, corpus)
            pref = est["id"].lower()
            fila[f"{pref}_top1_id"] = ids_sem[0] if ids_sem else None
            fila[f"{pref}_top1_doc"] = (
                hits["doc_id"].iloc[0] if len(hits) else None
            )
            fila[f"{pref}_top1_similitud"] = res["similitud_max"]
            fila[f"{pref}_recall"] = rec
            fila[f"{pref}_recall_ctx"] = rec_ctx
            fila[f"{pref}_rango"] = rango
            fila[f"{pref}_cobertura"] = evd["cobertura"]
            fila[f"{pref}_razon"] = evd["razon"]
            fila[f"{pref}_confusion"] = _confusion(esperado, evd["cobertura"])
            fila[f"{pref}_umbral_0_30"] = res["informacion_insuficiente"]
            fila[f"{pref}_n_hits"] = len(ids_all)
            for _, h in hits.iterrows():
                detalle.append({
                    "id_pregunta": q["id"],
                    "estrategia": est["id"],
                    "estrategia_nombre": est["nombre"],
                    "pregunta": q["pregunta"],
                    "origen": h.get("origen"),
                    "semilla": h.get("semilla"),
                    "rango": h.get("rango"),
                    "fragment_id": h["fragment_id"],
                    "doc_id": h["doc_id"],
                    "pagina_inicio": h["pagina_inicio"],
                    "seccion": h.get("seccion"),
                    "similitud": h.get("similitud"),
                    "es_gold": h["fragment_id"] in gold,
                    "texto_400": (h["texto"] or "")[:400],
                })
        filas.append(fila)

    resumen = pd.DataFrame(filas)
    det = pd.DataFrame(detalle)
    metricas = _metricas(resumen, t_emb, top_k, umbral, indice)
    gold_audit = [
        {
            "id": q["id"],
            "pregunta": q["pregunta"],
            "tipo": q["tipo"],
            "cobertura_esperada": q["cobertura_esperada"],
            "doc_id": q.get("doc_id"),
            "relevantes": q["relevantes"],
            "justificacion": q.get("justificacion_gold"),
        }
        for q in qs
    ]

    escritos = {
        "pruebas_recuperacion_v3.csv": resumen,
        "pruebas_recuperacion_detalle_v3.csv": det,
    }
    for nombre, df in escritos.items():
        if nombre in SALIDAS_PROHIBIDAS:
            raise RuntimeError(f"Intento de pisar {nombre}")
        df.to_csv(dest / nombre, index=False, encoding="utf-8")
    for nombre, obj in (
        ("metricas_recuperacion_v3.json", metricas),
        ("gold_ampliado.json", gold_audit),
        ("comparacion_estrategias_v3.json", metricas["estrategias"]),
    ):
        if nombre in SALIDAS_PROHIBIDAS:
            raise RuntimeError(f"Intento de pisar {nombre}")
        _guardar_json(dest / nombre, obj)

    por_est = pd.DataFrame(metricas["estrategias"])
    por_est.to_csv(dest / "comparacion_estrategias_v3.csv", index=False, encoding="utf-8")
    cob_rows = []
    for est in ESTRATEGIAS:
        pref = est["id"].lower()
        for _, r in resumen.iterrows():
            cob_rows.append({
                "id": r["id"],
                "estrategia": est["id"],
                "esperado": r["cobertura_esperada"],
                "observado": r[f"{pref}_cobertura"],
                "confusion": r[f"{pref}_confusion"],
                "tema": r["tema"],
                "tipo": r["tipo"],
            })
    cob_df = pd.DataFrame(cob_rows)
    cob_df.to_csv(dest / "cobertura_evidencia_v3.csv", index=False, encoding="utf-8")

    return {
        "resumen": resumen,
        "detalle": det,
        "metricas": metricas,
        "conjunto": resumen_conjunto(qs),
        "salidas": dest,
    }


def _agg_recall_mrr(resumen: pd.DataFrame, rec_col: str, rango_col: str) -> dict:
    con = resumen[resumen["n_gold"] > 0]
    recs = [x for x in con[rec_col].tolist() if x is not None and pd.notna(x)]
    ranks = []
    for _, r in con.iterrows():
        v = r[rango_col]
        ranks.append(int(v) if pd.notna(v) else None)
    hits = int(sum(1 for v in ranks if v))
    return {
        "n_con_gold": int(len(con)),
        "recall_at_5": round(float(sum(recs) / len(recs)), 4) if recs else None,
        "mrr": mrr(ranks),
        "aciertos": hits,
    }


def _metricas(resumen: pd.DataFrame, t_emb: list, top_k: int, umbral: float, indice: dict) -> dict:
    estrategias = []
    for est in ESTRATEGIAS:
        pref = est["id"].lower()
        rec_col = f"{pref}_recall_ctx" if est["ampliar"] else f"{pref}_recall"
        base = _agg_recall_mrr(resumen, rec_col, f"{pref}_rango")
        cob = resumen[f"{pref}_cobertura"]
        conf = resumen[f"{pref}_confusion"]
        fuera = resumen[resumen["cobertura_esperada"] == "no_cubierta"]
        suf = resumen[resumen["cobertura_esperada"] == "suficiente"]
        par = resumen[resumen["cobertura_esperada"] == "parcial"]
        umbral_fuera = int(fuera[f"{pref}_umbral_0_30"].sum()) if len(fuera) else 0
        item = {
            "id": est["id"],
            "nombre": est["nombre"],
            **base,
            "n_suficiente_pred": int((cob == "suficiente").sum()),
            "n_parcial_pred": int((cob == "parcial").sum()),
            "n_no_cubierta_pred": int((cob == "no_cubierta").sum()),
            "aciertos_cobertura": int((conf == "acierto").sum()),
            "falsos_positivos": int((conf == "falso_positivo").sum()),
            "falsos_positivos_suaves": int((conf == "falso_positivo_suave").sum()),
            "falsos_negativos": int((conf == "falso_negativo").sum()),
            "falsos_negativos_suaves": int((conf == "falso_negativo_suave").sum()),
            "subestimacion": int((conf == "subestimacion").sum()),
            "sobreestimacion": int((conf == "sobreestimacion").sum()),
            "fuera_n": int(len(fuera)),
            "fuera_rechazados_evidencia": int((fuera[f"{pref}_cobertura"] == "no_cubierta").sum()),
            "fuera_falsos_positivos": int((fuera[f"{pref}_cobertura"] == "suficiente").sum()),
            "fuera_marcados_parcial": int((fuera[f"{pref}_cobertura"] == "parcial").sum()),
            "fuera_rechazados_umbral_0_30": umbral_fuera,
            "suficiente_n": int(len(suf)),
            "suficiente_pred_ok": int((suf[f"{pref}_cobertura"] == "suficiente").sum()),
            "parcial_n": int(len(par)),
            "parcial_pred_ok": int((par[f"{pref}_cobertura"] == "parcial").sum()),
        }
        por_tema = []
        con = resumen[resumen["n_gold"] > 0]
        for tema, g in con.groupby("tema"):
            recs = [x for x in g[rec_col].tolist() if x is not None and pd.notna(x)]
            por_tema.append({
                "tema": tema,
                "n": int(len(g)),
                "recall_at_5": round(float(sum(recs) / len(recs)), 4) if recs else None,
            })
        item["por_tema"] = por_tema
        por_tipo = []
        for tipo, g in con.groupby("tipo"):
            recs = [x for x in g[rec_col].tolist() if x is not None and pd.notna(x)]
            por_tipo.append({
                "tipo": tipo,
                "n": int(len(g)),
                "recall_at_5": round(float(sum(recs) / len(recs)), 4) if recs else None,
            })
        item["por_tipo"] = por_tipo
        estrategias.append(item)

    foco_ids = ["RAG-D-01", "RAG-D-02", "RAG-D-06", "RAG-D-08"]
    foco = resumen[resumen["id"].isin(foco_ids)][
        [
            "id", "pregunta",
            "a_recall", "a_rango", "a_top1_id",
            "b_recall_ctx", "b_rango", "b_top1_id",
            "c_recall", "c_rango", "c_top1_id",
            "a_cobertura", "b_cobertura", "c_cobertura",
        ]
    ].to_dict(orient="records")

    return {
        "generado_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "n_preguntas": int(len(resumen)),
        "top_k": top_k,
        "umbral_legado": umbral,
        "embeddings_shape": [int(indice["vectores"].shape[0]), int(indice["vectores"].shape[1])],
        "embeddings_reutilizados": True,
        "hibrido": "RRF k=60 de coseno y BM25 (k1=1.2, b=0.75); no se ajustó a las preguntas.",
        "original_congelado_notebook12": METRICAS_ORIGINALES,
        "revision_congelada_notebook12b": METRICAS_12B,
        "aviso_muestra": (
            "Cuarenta preguntas de desarrollo no generalizan el rechazo ni el ranking. "
            "No se afirma que el detector de evidencia ni la fusión RRF funcionen fuera de RAG-D."
        ),
        "conjunto": resumen_conjunto(),
        "segundos_embedding_consulta_medio": round(float(sum(t_emb) / max(len(t_emb), 1)), 3),
        "estrategias": estrategias,
        "foco_d01_d02_d06_d08": foco,
    }


def _matriz_confusion(resumen: pd.DataFrame, col: str) -> dict:
    clases = ("suficiente", "parcial", "no_cubierta")
    mat = {}
    for esperado in clases:
        mat[esperado] = {}
        for observado in clases:
            mat[esperado][observado] = int(
                (
                    (resumen["cobertura_esperada"] == esperado)
                    & (resumen[col] == observado)
                ).sum()
            )
    return mat


def _correr_estrategia_b(
    qs: list[dict],
    indice: dict,
    cache_vec: dict,
    t_emb: list,
    top_k: int,
    umbral: float,
    modelo: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    corpus = indice["df"]
    filas = []
    detalle = []
    for q in qs:
        if q["pregunta"] not in cache_vec:
            t0 = time.perf_counter()
            cache_vec[q["pregunta"]] = embeber_consulta(q["pregunta"], modelo=modelo)
            t_emb.append(time.perf_counter() - t0)
        qvec = cache_vec[q["pregunta"]]
        gold = list(q.get("relevantes") or [])
        res = buscar(
            q["pregunta"],
            indice,
            top_k=top_k,
            umbral=umbral,
            modelo=modelo,
            ampliar=True,
            hibrido=False,
            consulta_vec=qvec,
            preferir_alcance=True,
        )
        hits = res["hits"]
        ids_sem = _ids_semilla(hits)
        ids_all = _ids_todos(hits)
        rec = recall_at_k(ids_sem, gold, top_k) if gold else None
        rec_ctx = recall_at_k(ids_all, gold, max(len(ids_all), 1)) if gold else None
        rango = None
        for i, fid in enumerate(ids_sem, start=1):
            if fid in gold:
                rango = i
                break
        if gold and rango is None:
            rango = _rango_contexto(hits, gold)
        textos = hits["texto"].tolist() if len(hits) else []
        evd = clasificar_evidencia(q["pregunta"], textos, corpus)
        top1_doc = hits["doc_id"].iloc[0] if len(hits) else None
        filas.append({
            "id": q["id"],
            "tema": q["tema"],
            "tipo": q["tipo"],
            "pregunta": q["pregunta"],
            "en_corpus": q["en_corpus"],
            "doc_id": q.get("doc_id"),
            "cobertura_esperada": q["cobertura_esperada"],
            "n_gold": len(gold),
            "gold": ";".join(gold) if gold else "(ninguna)",
            "justificacion_gold": q.get("justificacion_gold"),
            "regla": q.get("regla"),
            "alcance": res.get("alcance"),
            "top1_id": ids_sem[0] if ids_sem else None,
            "top1_doc": top1_doc,
            "top1_similitud": res["similitud_max"],
            "recall": rec,
            "recall_ctx": rec_ctx,
            "rango": rango,
            "cobertura": evd["cobertura"],
            "razon": evd["razon"],
            "confusion": _confusion(q["cobertura_esperada"], evd["cobertura"]),
            "umbral_0_30": res["informacion_insuficiente"],
            "n_hits": len(ids_all),
            "doc_esperado_ok": (
                None if not q.get("doc_id")
                else bool(top1_doc == q.get("doc_id"))
            ),
        })
        for _, h in hits.iterrows():
            detalle.append({
                "id_pregunta": q["id"],
                "pregunta": q["pregunta"],
                "origen": h.get("origen"),
                "rango": h.get("rango"),
                "fragment_id": h["fragment_id"],
                "doc_id": h["doc_id"],
                "similitud": h.get("similitud"),
                "es_gold": h["fragment_id"] in gold,
                "texto_400": (h["texto"] or "")[:400],
            })
    return pd.DataFrame(filas), pd.DataFrame(detalle)


def _resumen_b(resumen: pd.DataFrame) -> dict:
    recs = _agg_recall_mrr(resumen, "recall_ctx", "rango")
    cob = resumen["cobertura"]
    conf = resumen["confusion"]
    fuera = resumen[resumen["cobertura_esperada"] == "no_cubierta"]
    suf = resumen[resumen["cobertura_esperada"] == "suficiente"]
    par = resumen[resumen["cobertura_esperada"] == "parcial"]
    por_tipo = []
    for tipo, g in resumen.groupby("tipo"):
        por_tipo.append({
            "tipo": tipo,
            "n": int(len(g)),
            "aciertos_cobertura": int((g["confusion"] == "acierto").sum()),
            "recall_at_5": _agg_recall_mrr(g, "recall_ctx", "rango")["recall_at_5"],
        })
    return {
        **recs,
        "n_preguntas": int(len(resumen)),
        "n_suficiente_pred": int((cob == "suficiente").sum()),
        "n_parcial_pred": int((cob == "parcial").sum()),
        "n_no_cubierta_pred": int((cob == "no_cubierta").sum()),
        "aciertos_cobertura": int((conf == "acierto").sum()),
        "exactitud_cobertura": round(float((conf == "acierto").mean()), 4) if len(resumen) else None,
        "falsos_positivos": int((conf == "falso_positivo").sum()),
        "falsos_positivos_suaves": int((conf == "falso_positivo_suave").sum()),
        "falsos_negativos": int((conf == "falso_negativo").sum()),
        "falsos_negativos_suaves": int((conf == "falso_negativo_suave").sum()),
        "subestimacion": int((conf == "subestimacion").sum()),
        "sobreestimacion": int((conf == "sobreestimacion").sum()),
        "fuera_n": int(len(fuera)),
        "fuera_rechazados_evidencia": int((fuera["cobertura"] == "no_cubierta").sum()) if len(fuera) else 0,
        "fuera_falsos_positivos": int((fuera["cobertura"] == "suficiente").sum()) if len(fuera) else 0,
        "fuera_marcados_parcial": int((fuera["cobertura"] == "parcial").sum()) if len(fuera) else 0,
        "suficiente_n": int(len(suf)),
        "suficiente_pred_ok": int((suf["cobertura"] == "suficiente").sum()) if len(suf) else 0,
        "parcial_n": int(len(par)),
        "parcial_pred_ok": int((par["cobertura"] == "parcial").sum()) if len(par) else 0,
        "matriz_confusion": _matriz_confusion(resumen, "cobertura"),
        "por_tipo": por_tipo,
    }


def evaluar_cierre(
    indice: dict,
    top_k: int = 5,
    umbral: float = 0.30,
    modelo: str = MODELO_DEFECTO,
    salidas: Path | None = None,
) -> dict:
    """Estrategia B + evidencia revisada. Escribe v4; no pisa v3 ni v2."""
    dest = Path(salidas) if salidas else ruta_salidas_rag()
    dest.mkdir(parents=True, exist_ok=True)
    if tuple(indice["vectores"].shape) != (234, 1536):
        raise AssertionError(
            f"Se esperaban embeddings (234, 1536); hay {indice['vectores'].shape}."
        )
    choques = comprobar_reservados(PREGUNTAS_AMPLIADAS) + comprobar_holdout()
    if choques:
        raise ValueError(f"Choque con IDs reservados: {choques}")

    cache_vec: dict = {}
    t_emb: list = []
    muestra, det_m = _correr_estrategia_b(
        PREGUNTAS_AMPLIADAS, indice, cache_vec, t_emb, top_k, umbral, modelo
    )
    holdout, det_h = _correr_estrategia_b(
        PREGUNTAS_HOLDOUT, indice, cache_vec, t_emb, top_k, umbral, modelo
    )
    met_muestra = _resumen_b(muestra)
    met_holdout = _resumen_b(holdout)
    excepciones = muestra[muestra["id"].isin(["RAG-D-14"])].copy()
    excepciones_h = holdout[holdout["id"].isin(["RAG-H-01", "RAG-H-08"])]
    metricas = {
        "generado_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "estrategia": "B_coseno_top5_adyacentes_alcance",
        "embeddings_reutilizados": True,
        "embeddings_shape": [234, 1536],
        "aviso": (
            "Las 40 preguntas RAG-D se usaron para observar fallos y no son "
            "validación independiente. RAG-H-* no se usó para diseñar las "
            "reglas; el primer holdout detectó que «cali» casaba como "
            "subcadena de «calidad» y se añadió una sola regla general de "
            "borde de token. Tras esa corrección no hay más ajustes del "
            "recuperador."
        ),
        "original_congelado_notebook12": METRICAS_ORIGINALES,
        "revision_congelada_notebook12b": METRICAS_12B,
        "antes_12c_estrategia_B": METRICAS_12C_B,
        "despues_muestra_40": met_muestra,
        "holdout_8": met_holdout,
        "segundos_embedding_consulta_medio": round(
            float(sum(t_emb) / max(len(t_emb), 1)), 3
        ),
        "excepcion_d14": excepciones.to_dict(orient="records"),
        "excepcion_holdout": excepciones_h.to_dict(orient="records"),
    }
    muestra.to_csv(dest / "pruebas_recuperacion_v4.csv", index=False, encoding="utf-8")
    holdout.to_csv(dest / "pruebas_holdout_v4.csv", index=False, encoding="utf-8")
    pd.concat([det_m, det_h], ignore_index=True).to_csv(
        dest / "pruebas_recuperacion_detalle_v4.csv", index=False, encoding="utf-8"
    )
    _guardar_json(dest / "metricas_recuperacion_v4.json", metricas)
    _guardar_json(dest / "matriz_confusion_v4.json", {
        "muestra_40": met_muestra["matriz_confusion"],
        "holdout_8": met_holdout["matriz_confusion"],
    })
    v3 = dest / "metricas_recuperacion_v3.json"
    if not v3.is_file():
        raise FileNotFoundError("Falta metricas_recuperacion_v3.json; no se debe recalcular.")
    return {
        "muestra": muestra,
        "holdout": holdout,
        "metricas": metricas,
        "salidas": dest,
        "v3_intactas": True,
    }
