"""
Indexa embeddings locales y evalúa la recuperación. No usa pgvector ni un LLM.

Funciones:
- indexar_corpus(): Genera o reutiliza embeddings y guarda el índice.
- evaluar_recuperacion(): Mide recall y MRR sobre las preguntas de desarrollo.
- evaluar_revision(): Compara estrategias de recuperación.
- cargar_indice_embeddings(): Lee vectores y metadatos ya generados.
- ejecutar_etapa12(): Encadena indexación, evaluación e informe.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .embeddings import MODELO_DEFECTO, generar_embeddings
from .evidencia import clasificar_evidencia
from .pruebas import METRICAS_ORIGINALES, PREGUNTAS, mrr, recall_at_k
from .recuperar import buscar
from .rutas import ruta_salidas_rag
from .validar import validar_fragmentos


def _guardar_json(ruta: Path, obj: dict) -> None:
    ruta.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def indexar_corpus(
    reutilizar: bool = True,
    modelo: str = MODELO_DEFECTO,
    salidas: Path | None = None,
) -> dict:
    dest = Path(salidas) if salidas else ruta_salidas_rag()
    dest.mkdir(parents=True, exist_ok=True)
    val = validar_fragmentos()
    val["todos"].to_csv(dest / "validacion_fragmentos.csv", index=False, encoding="utf-8")
    excl = val["excluidos"][
        [
            "fragment_id",
            "doc_id",
            "seccion",
            "pagina_inicio",
            "n_caracteres",
            "motivo_exclusion",
        ]
    ].copy()
    excl["conservado_en_parquet"] = True
    excl.to_csv(dest / "exclusiones_indexacion.csv", index=False, encoding="utf-8")
    val["controles"].to_csv(dest / "controles_validacion.csv", index=False, encoding="utf-8")

    emb = generar_embeddings(
        val["indexar"], modelo=modelo, reutilizar=reutilizar, salidas=dest
    )
    meta_idx = val["indexar"][
        [
            "fragment_id",
            "doc_id",
            "archivo",
            "titulo",
            "seccion",
            "pagina_inicio",
            "pagina_fin",
            "fuente",
            "version",
            "n_caracteres",
            "artefactos",
        ]
    ].copy()
    meta_idx.to_csv(dest / "indice_embeddings.csv", index=False, encoding="utf-8")
    return {
        "validacion": val,
        "embeddings": emb,
        "salidas": dest,
        "modelo": modelo,
    }


def evaluar_recuperacion(
    indice: dict,
    top_k: int = 5,
    umbral: float = 0.30,
    modelo: str = MODELO_DEFECTO,
    salidas: Path | None = None,
) -> dict:
    dest = Path(salidas) if salidas else ruta_salidas_rag()
    filas = []
    detalle = []
    ranks_mrr = []
    recalls = []
    t_emb = []
    t_bus = []
    for q in PREGUNTAS:
        res = buscar(
            q["pregunta"], indice, top_k=top_k, umbral=umbral, modelo=modelo
        )
        hits = res["hits"]
        rec_ids = hits["fragment_id"].tolist() if len(hits) else []
        gold = list(q.get("relevantes_originales") or q["relevantes"])
        rec_k = recall_at_k(rec_ids, gold, top_k) if q["en_corpus"] else None
        rango_gold = None
        for i, fid in enumerate(rec_ids, start=1):
            if fid in gold:
                rango_gold = i
                break
        if q["en_corpus"]:
            ranks_mrr.append(rango_gold)
            if rec_k is not None:
                recalls.append(rec_k)
        if q["en_corpus"]:
            observada = "relevante" if rango_gold else "no_recuperado"
        else:
            observada = (
                "fuera_de_corpus_ok"
                if res["informacion_insuficiente"]
                else "falso_positivo_posible"
            )
        t_emb.append(res["segundos_embedding"])
        t_bus.append(res["segundos_busqueda"])
        filas.append({
            "id": q["id"],
            "tema": q["tema"],
            "pregunta": q["pregunta"],
            "en_corpus": q["en_corpus"],
            "relevancia_esperada": ";".join(gold) if gold else "(ninguna; no está en el corpus)",
            "relevancia_observada": observada,
            "top1_id": rec_ids[0] if rec_ids else None,
            "top1_doc": hits["doc_id"].iloc[0] if len(hits) else None,
            "top1_pagina": hits["pagina_inicio"].iloc[0] if len(hits) else None,
            "top1_similitud": res["similitud_max"],
            "informacion_insuficiente": res["informacion_insuficiente"],
            "recall_at_k": rec_k,
            "rango_primer_relevante": rango_gold,
            "nota": q["nota"],
        })
        for _, h in hits.iterrows():
            detalle.append({
                "id_pregunta": q["id"],
                "pregunta": q["pregunta"],
                "rango": h["rango"],
                "fragment_id": h["fragment_id"],
                "doc_id": h["doc_id"],
                "pagina_inicio": h["pagina_inicio"],
                "seccion": h["seccion"],
                "similitud": h["similitud"],
                "es_relevante": h["fragment_id"] in gold,
                "texto_500": (h["texto"] or "")[:500],
            })
    resumen = pd.DataFrame(filas)
    det = pd.DataFrame(detalle)
    con_ref = resumen[resumen["en_corpus"]]
    metricas = {
        "n_preguntas": int(len(PREGUNTAS)),
        "n_con_referencia": int(len(con_ref)),
        "n_fuera_de_corpus": int((~resumen["en_corpus"]).sum()),
        "top_k": top_k,
        "umbral": umbral,
        "recall_at_k_medio": round(float(sum(recalls) / len(recalls)), 4) if recalls else None,
        "mrr": mrr(ranks_mrr),
        "aciertos_con_referencia": int((con_ref["relevancia_observada"] == "relevante").sum()),
        "fuera_marcados_insuficiente": int(
            ((~resumen["en_corpus"]) & resumen["informacion_insuficiente"]).sum()
        ),
        "segundos_embedding_consulta_medio": round(float(sum(t_emb) / max(len(t_emb), 1)), 3),
        "segundos_busqueda_medio": round(float(sum(t_bus) / max(len(t_bus), 1)), 4),
    }
    resumen.to_csv(dest / "pruebas_recuperacion.csv", index=False, encoding="utf-8")
    det.to_csv(dest / "pruebas_recuperacion_detalle.csv", index=False, encoding="utf-8")
    _guardar_json(dest / "metricas_recuperacion.json", metricas)
    return {"resumen": resumen, "detalle": det, "metricas": metricas}


def escribir_informe(val: dict, embeddings: dict, ev: dict, dest: Path) -> dict:
    informe = {
        "generado_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "n_total": val["n_total"],
        "n_indexados": val["n_indexar"],
        "n_excluidos": val["n_excluidos"],
        "modelo": embeddings["meta"]["modelo"],
        "dimension": embeddings["meta"]["dimension"],
        "embeddings_desde_cache": embeddings["desde_cache"],
        "segundos_embeddings": embeddings["meta"].get("segundos"),
        "metricas": ev["metricas"],
        "salidas": str(dest),
    }
    _guardar_json(Path(dest) / "informe_indexacion.json", informe)
    return informe


def _rango_gold(ids_coseno: list[str], ids_contexto: list[str], gold: list[str]) -> tuple:
    rango_cos = None
    for i, fid in enumerate(ids_coseno, start=1):
        if fid in gold:
            rango_cos = i
            break
    encontrado_ctx = any(fid in ids_contexto for fid in gold)
    return rango_cos, encontrado_ctx


def _rango_contexto(hits: pd.DataFrame, gold: list[str]) -> int | None:
    if hits is None or hits.empty or not gold:
        return None
    cos = hits[hits["origen"] == "coseno"] if "origen" in hits.columns else hits
    ids_cos = cos["fragment_id"].tolist()
    for i, fid in enumerate(ids_cos, start=1):
        if fid in gold:
            return i
    if "origen" not in hits.columns:
        return None
    adj = hits[(hits["origen"] == "adyacente") & hits["fragment_id"].isin(gold)]
    if adj.empty:
        return None
    sem = adj.iloc[0].get("semilla")
    if sem in ids_cos:
        return ids_cos.index(sem) + 1
    return None


def evaluar_revision(
    indice: dict,
    top_k: int = 5,
    umbral: float = 0.30,
    modelo: str = MODELO_DEFECTO,
    salidas: Path | None = None,
) -> dict:
    """Compara gold original vs verificado y añade evidencia + adyacentes.

    No pisa pruebas_recuperacion.csv ni metricas_recuperacion.json de la etapa 12.
    """
    dest = Path(salidas) if salidas else ruta_salidas_rag()
    dest.mkdir(parents=True, exist_ok=True)
    orig = dest / "pruebas_recuperacion.csv"
    bak = dest / "pruebas_recuperacion_original.csv"
    if orig.is_file() and not bak.is_file():
        shutil.copy(orig, bak)
    met = dest / "metricas_recuperacion.json"
    met_bak = dest / "metricas_recuperacion_original.json"
    if met.is_file() and not met_bak.is_file():
        shutil.copy(met, met_bak)
    corpus = indice["df"]
    filas = []
    detalle = []
    rec_orig, rec_ver, rec_ctx = [], [], []
    ranks_orig, ranks_ver, ranks_ctx = [], [], []
    t_emb, t_bus = [], []

    for q in PREGUNTAS:
        res = buscar(
            q["pregunta"],
            indice,
            top_k=top_k,
            umbral=umbral,
            modelo=modelo,
            ampliar=True,
            ventana=1,
        )
        hits = res["hits"]
        cos = hits[hits["origen"] == "coseno"] if "origen" in hits.columns else hits
        ctx = hits
        ids_cos = cos["fragment_id"].tolist() if len(cos) else []
        ids_ctx = ctx["fragment_id"].tolist() if len(ctx) else []
        gold_o = list(q.get("relevantes_originales", q.get("relevantes", [])))
        gold_v = list(q["relevantes"])
        textos = ctx["texto"].tolist() if len(ctx) else []
        evd = clasificar_evidencia(q["pregunta"], textos, corpus)

        r_o, _ = _rango_gold(ids_cos, ids_ctx, gold_o)
        r_v, en_ctx = _rango_gold(ids_cos, ids_ctx, gold_v)
        rec_o = recall_at_k(ids_cos, gold_o, top_k) if q["en_corpus"] else None
        rec_v = recall_at_k(ids_cos, gold_v, top_k) if q["en_corpus"] else None
        rec_c = recall_at_k(ids_ctx, gold_v, max(len(ids_ctx), 1)) if q["en_corpus"] else None

        if q["en_corpus"]:
            rec_orig.append(rec_o)
            rec_ver.append(rec_v)
            rec_ctx.append(rec_c)
            ranks_orig.append(r_o)
            ranks_ver.append(r_v)
            ranks_ctx.append(_rango_contexto(hits, gold_v))

        if q["en_corpus"]:
            observada = "relevante" if r_v else ("relevante_por_contexto" if en_ctx else "no_recuperado")
        else:
            observada = (
                "fuera_de_corpus_ok"
                if evd["cobertura"] == "no_cubierta"
                else "falso_positivo_posible"
            )

        t_emb.append(res["segundos_embedding"])
        t_bus.append(res["segundos_busqueda"])
        filas.append({
            "id": q["id"],
            "tema": q["tema"],
            "pregunta": q["pregunta"],
            "en_corpus": q["en_corpus"],
            "gold_original": ";".join(gold_o) if gold_o else "(ninguna)",
            "gold_verificado": ";".join(gold_v) if gold_v else "(ninguna)",
            "justificacion_gold": q.get("justificacion_gold"),
            "top1_id": ids_cos[0] if ids_cos else None,
            "top1_doc": cos["doc_id"].iloc[0] if len(cos) else None,
            "top1_pagina": cos["pagina_inicio"].iloc[0] if len(cos) else None,
            "top1_similitud": res["similitud_max"],
            "umbral_legado_0_30": res["informacion_insuficiente"],
            "cobertura": evd["cobertura"],
            "razon_evidencia": evd["razon"],
            "recall_original": rec_o,
            "recall_verificado": rec_v,
            "recall_con_contexto": rec_c,
            "rango_gold_original": r_o,
            "rango_gold_verificado": r_v,
            "gold_en_adyacentes": bool(en_ctx and not r_v),
            "n_hits_coseno": len(ids_cos),
            "n_hits_contexto": len(ids_ctx),
            "relevancia_observada": observada,
            "nota": q.get("nota"),
        })
        for _, h in hits.iterrows():
            gid = gold_v
            detalle.append({
                "id_pregunta": q["id"],
                "pregunta": q["pregunta"],
                "origen": h.get("origen"),
                "semilla": h.get("semilla"),
                "rango": h.get("rango"),
                "fragment_id": h["fragment_id"],
                "doc_id": h["doc_id"],
                "pagina_inicio": h["pagina_inicio"],
                "seccion": h.get("seccion"),
                "similitud": h.get("similitud"),
                "es_relevante_verificado": h["fragment_id"] in gid,
                "es_relevante_original": h["fragment_id"] in gold_o,
                "texto_500": (h["texto"] or "")[:500],
            })

    resumen = pd.DataFrame(filas)
    det = pd.DataFrame(detalle)
    con = resumen[resumen["en_corpus"]]
    fuera = resumen[~resumen["en_corpus"]]
    metricas = {
        "original_congelado": METRICAS_ORIGINALES,
        "n_preguntas": int(len(PREGUNTAS)),
        "top_k": top_k,
        "recall_at_5_estricto_original_congelado": METRICAS_ORIGINALES["recall_at_k_medio"],
        "recall_at_5_gold_original_recalculado": (
            round(float(sum(rec_orig) / len(rec_orig)), 4) if rec_orig else None
        ),
        "recall_at_5_gold_verificado": (
            round(float(sum(rec_ver) / len(rec_ver)), 4) if rec_ver else None
        ),
        "recall_gold_verificado_con_adyacentes": (
            round(float(sum(rec_ctx) / len(rec_ctx)), 4) if rec_ctx else None
        ),
        "mrr_gold_original": mrr(ranks_orig),
        "mrr_gold_verificado": mrr(ranks_ver),
        "mrr_verificado_con_contexto": mrr(ranks_ctx),
        "aciertos_gold_verificado": int(
            con["relevancia_observada"].isin(["relevante", "relevante_por_contexto"]).sum()
        ),
        "n_suficiente": int((resumen["cobertura"] == "suficiente").sum()),
        "n_parcial": int((resumen["cobertura"] == "parcial").sum()),
        "n_no_cubierta": int((resumen["cobertura"] == "no_cubierta").sum()),
        "fuera_rechazados_evidencia": int(
            (fuera["cobertura"] == "no_cubierta").sum()
        ),
        "fuera_falsos_positivos_evidencia": int(
            (fuera["cobertura"] != "no_cubierta").sum()
        ),
        "fuera_rechazados_umbral_0_30": int(fuera["umbral_legado_0_30"].sum()),
        "aviso_muestra": (
            "Once preguntas de desarrollo no generalizan el rechazo. "
            "No se afirma que el detector de evidencia funcione fuera de RAG-D."
        ),
        "segundos_embedding_consulta_medio": round(float(sum(t_emb) / max(len(t_emb), 1)), 3),
        "segundos_busqueda_medio": round(float(sum(t_bus) / max(len(t_bus), 1)), 4),
        "embeddings_reutilizados": True,
    }
    resumen.to_csv(dest / "pruebas_recuperacion_v2.csv", index=False, encoding="utf-8")
    det.to_csv(dest / "pruebas_recuperacion_detalle_v2.csv", index=False, encoding="utf-8")
    _guardar_json(dest / "metricas_recuperacion_v2.json", metricas)
    _guardar_json(dest / "revision_gold.json", [
        {
            "id": q["id"],
            "pregunta": q["pregunta"],
            "original": q.get("relevantes_originales", []),
            "verificado": q["relevantes"],
            "justificacion": q.get("justificacion_gold"),
        }
        for q in PREGUNTAS
    ])
    return {"resumen": resumen, "detalle": det, "metricas": metricas}


def cargar_indice_embeddings(
    reutilizar: bool = True,
    modelo: str = MODELO_DEFECTO,
    salidas: Path | None = None,
) -> dict:
    dest = Path(salidas) if salidas else ruta_salidas_rag()
    val = validar_fragmentos()
    emb = generar_embeddings(
        val["indexar"], modelo=modelo, reutilizar=reutilizar, salidas=dest
    )
    return {
        "validacion": val,
        "embeddings": emb,
        "indice": {
            "vectores": emb["vectores"],
            "fragment_ids": emb["fragment_ids"],
            "df": emb["df"],
        },
        "salidas": dest,
        "modelo": modelo,
        "desde_cache": emb["desde_cache"],
    }


def ejecutar_etapa12(
    reutilizar: bool = True,
    top_k: int = 5,
    umbral: float = 0.30,
    modelo: str = MODELO_DEFECTO,
) -> dict:
    idx = indexar_corpus(reutilizar=reutilizar, modelo=modelo)
    indice = {
        "vectores": idx["embeddings"]["vectores"],
        "fragment_ids": idx["embeddings"]["fragment_ids"],
        "df": idx["embeddings"]["df"],
    }
    ev = evaluar_recuperacion(
        indice, top_k=top_k, umbral=umbral, modelo=modelo, salidas=idx["salidas"]
    )
    informe = escribir_informe(
        idx["validacion"], idx["embeddings"], ev, idx["salidas"]
    )
    return {
        "validacion": idx["validacion"],
        "embeddings": idx["embeddings"],
        "evaluacion": ev,
        "informe": informe,
        "salidas": idx["salidas"],
    }
