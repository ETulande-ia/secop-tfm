"""
Recuperación por similitud coseno, fragmentos adyacentes, BM25 y fusión RRF.

Funciones:
- similitud_coseno(): Calcula el coseno entre la consulta y la matriz.
- ampliar_adyacentes(): Añade fragmentos vecinos del mismo documento.
- preparar_bm25(): Construye el índice léxico.
- puntajes_bm25(): Puntúa la pregunta con BM25.
- detectar_alcance(): Identifica el documento al que apunta la pregunta.
- fusion_rrf(): Combina los rankings denso y léxico.
- buscar(): Devuelve los fragmentos según la estrategia pedida.
"""

from __future__ import annotations

import math
import re
import time
from collections import Counter

import numpy as np
import pandas as pd

from .embeddings import MODELO_DEFECTO, embeber_consulta
from .evidencia import ACRONIMOS, STOP, plegar

COLS_MOSTRAR = [
    "fragment_id",
    "doc_id",
    "titulo",
    "seccion",
    "pagina_inicio",
    "pagina_fin",
    "fuente",
    "version",
    "n_caracteres",
]


def similitud_coseno(consulta: np.ndarray, matriz: np.ndarray) -> np.ndarray:
    q = consulta.astype(np.float32)
    qn = np.linalg.norm(q) + 1e-12
    q = q / qn
    n = np.linalg.norm(matriz, axis=1) + 1e-12
    return (matriz @ q) / n


def ampliar_adyacentes(
    hits: pd.DataFrame,
    df_index: pd.DataFrame,
    ventana: int = 1,
) -> pd.DataFrame:
    """Añade orden ±1 del mismo documento. No cruza a otro PDF/ficha."""
    if hits is None or hits.empty:
        return hits
    out = hits.copy()
    out["origen"] = "coseno"
    out["semilla"] = out["fragment_id"]
    vistos = set(out["fragment_id"])
    extras = []
    for _, h in out.iterrows():
        semilla = df_index[df_index["fragment_id"] == h["fragment_id"]]
        if semilla.empty:
            continue
        s = semilla.iloc[0]
        doc = s["doc_id"]
        orden = int(s["orden"])
        for delta in range(-int(ventana), int(ventana) + 1):
            if delta == 0:
                continue
            cand = df_index[
                (df_index["doc_id"] == doc) & (df_index["orden"] == orden + delta)
            ]
            if cand.empty:
                continue
            c = cand.iloc[0]
            fid = c["fragment_id"]
            if fid in vistos:
                continue
            vistos.add(fid)
            item = {col: (c[col] if col in c.index else None) for col in COLS_MOSTRAR}
            item["rango"] = None
            item["similitud"] = None
            item["texto"] = c["texto"]
            item["origen"] = "adyacente"
            item["semilla"] = h["fragment_id"]
            extras.append(item)
    if extras:
        out = pd.concat([out, pd.DataFrame(extras)], ignore_index=True)
    return out


RRF_K = 60
BM25_K1 = 1.2
BM25_B = 0.75


def tokens_busqueda(texto: str) -> list[str]:
    """Términos para BM25. Conserva dígitos y acrónimos; no usa el clasificador de evidencia."""
    crudos = re.findall(r"[a-z0-9_]+", plegar(texto))
    out = []
    for t in crudos:
        if t in STOP:
            continue
        if t.isdigit() or "_" in t or t in ACRONIMOS or len(t) >= 4:
            if t not in out:
                out.append(t)
    return out


def preparar_bm25(df: pd.DataFrame) -> dict:
    docs = [tokens_busqueda(t) for t in df["texto"].astype(str)]
    n = len(docs)
    df_t: dict[str, int] = {}
    for toks in docs:
        for t in set(toks):
            df_t[t] = df_t.get(t, 0) + 1
    idf = {
        t: math.log((n - c + 0.5) / (c + 0.5) + 1.0)
        for t, c in df_t.items()
    }
    longitudes = np.array([len(toks) for toks in docs], dtype=np.float32)
    avgdl = float(longitudes.mean()) if n else 1.0
    return {"docs": docs, "idf": idf, "avgdl": max(avgdl, 1.0), "n": n}


def puntajes_bm25(pregunta: str, cache: dict) -> np.ndarray:
    q = tokens_busqueda(pregunta)
    n = cache["n"]
    if not q or n == 0:
        return np.zeros(n, dtype=np.float32)
    idf = cache["idf"]
    avgdl = cache["avgdl"]
    out = np.zeros(n, dtype=np.float32)
    for i, toks in enumerate(cache["docs"]):
        tf = Counter(toks)
        dl = max(len(toks), 1)
        s = 0.0
        for t in q:
            if t not in tf:
                continue
            freq = tf[t]
            denom = freq + BM25_K1 * (1.0 - BM25_B + BM25_B * dl / avgdl)
            s += idf.get(t, 0.0) * (freq * (BM25_K1 + 1.0)) / denom
        out[i] = s
    return out


def detectar_alcance(pregunta: str) -> str | None:
    """Documento preferente según el marco de la pregunta. No usa IDs de prueba.

    Si nombra una modalidad o procedimiento del catálogo, se prioriza ese PDF/ficha
    frente a una regla general de otro documento (p. ej. RUP vs mínima cuantía).
    """
    q = plegar(pregunta)
    if "minima cuantia" in q:
        return "cce-minima-cuantia-2024"
    if (
        "isolation forest" in q
        or "c1_if" in q
        or "matriz c1" in q
        or re.search(r"\bc1\b", q)
    ):
        return "ficha-c1-if-v1"
    if "diccionario" in q or "datos abiertos" in q:
        return "diccionario-datos-abiertos-secop"
    if "requisitos habilitantes" in q or re.search(r"\brup\b", q):
        return "cce-requisitos-habilitantes-v3-2023"
    return None


def indices_con_alcance(
    pregunta: str,
    sims: np.ndarray,
    indice: dict,
    k: int,
    preferir_alcance: bool,
) -> np.ndarray:
    orden = np.argsort(-sims)
    if not preferir_alcance:
        return orden[:k]
    doc = detectar_alcance(pregunta)
    if not doc:
        return orden[:k]
    id_doc = {
        str(fid): str(d)
        for fid, d in zip(indice["df"]["fragment_id"], indice["df"]["doc_id"])
    }
    ids = indice["fragment_ids"]
    en_doc = [int(i) for i in orden if id_doc.get(str(ids[int(i)])) == doc]
    otros = [int(i) for i in orden if id_doc.get(str(ids[int(i)])) != doc]
    mezclado = (en_doc + otros)[:k]
    return np.asarray(mezclado, dtype=np.int64)


def fusion_rrf(sims: np.ndarray, lex: np.ndarray, k: int = RRF_K) -> np.ndarray:
    """Reciprocal Rank Fusion de ranking coseno y ranking léxico. k=60, no se ajusta a las preguntas."""
    n = len(sims)
    rrf = np.zeros(n, dtype=np.float64)
    orden_c = np.argsort(-sims)
    orden_l = np.argsort(-lex)
    rango_c = np.empty(n, dtype=np.int32)
    rango_l = np.empty(n, dtype=np.int32)
    rango_c[orden_c] = np.arange(1, n + 1)
    rango_l[orden_l] = np.arange(1, n + 1)
    rrf += 1.0 / (k + rango_c)
    rrf += 1.0 / (k + rango_l)
    return rrf


def buscar(
    pregunta: str,
    indice: dict,
    top_k: int = 5,
    umbral: float = 0.30,
    modelo: str = MODELO_DEFECTO,
    ampliar: bool = False,
    ventana: int = 1,
    consulta_vec: np.ndarray | None = None,
    hibrido: bool = False,
    preferir_alcance: bool = False,
) -> dict:
    t0 = time.perf_counter()
    if consulta_vec is None:
        qvec = embeber_consulta(pregunta, modelo=modelo)
        t_emb = time.perf_counter() - t0
    else:
        qvec = np.asarray(consulta_vec, dtype=np.float32)
        t_emb = 0.0
    t1 = time.perf_counter()
    sims = similitud_coseno(qvec, indice["vectores"])
    k = max(int(top_k), 1)
    origen_semilla = "hibrido" if hibrido else "coseno"
    if hibrido:
        if "_bm25" not in indice:
            indice["_bm25"] = preparar_bm25(indice["df"])
        lex = puntajes_bm25(pregunta, indice["_bm25"])
        scores = fusion_rrf(sims, lex)
        orden = np.argsort(-scores)[:k]
    else:
        orden = indices_con_alcance(
            pregunta, sims, indice, k, preferir_alcance=preferir_alcance
        )
    t_bus = time.perf_counter() - t1
    df = indice["df"].set_index("fragment_id", drop=False)
    ids = indice["fragment_ids"]
    filas = []
    for rango, i in enumerate(orden, start=1):
        fid = ids[int(i)]
        row = df.loc[fid]
        item = {c: row[c] if c in row.index else None for c in COLS_MOSTRAR}
        item["rango"] = rango
        item["similitud"] = round(float(sims[int(i)]), 4)
        item["texto"] = row["texto"]
        filas.append(item)
    hits = pd.DataFrame(filas)
    if ampliar:
        hits = ampliar_adyacentes(hits, indice["df"], ventana=ventana)
        if origen_semilla == "hibrido" and not hits.empty:
            hits.loc[hits["origen"] == "coseno", "origen"] = "hibrido"
    elif not hits.empty:
        hits["origen"] = origen_semilla
        hits["semilla"] = hits["fragment_id"]
    if len(hits) and "origen" in hits.columns:
        sem = hits[hits["origen"].isin(["coseno", "hibrido"])]
        if sem.empty:
            sem = hits[hits["similitud"].notna()]
        top1 = float(sem["similitud"].iloc[0]) if len(sem) else 0.0
    else:
        top1 = float(hits["similitud"].iloc[0]) if len(hits) else 0.0
    insuficiente_umbral = top1 < float(umbral)
    return {
        "pregunta": pregunta,
        "top_k": k,
        "umbral": float(umbral),
        "similitud_max": round(top1, 4),
        "informacion_insuficiente": insuficiente_umbral,
        "hits": hits,
        "segundos_embedding": round(t_emb, 3),
        "segundos_busqueda": round(t_bus, 4),
        "hibrido": bool(hibrido),
        "alcance": detectar_alcance(pregunta) if preferir_alcance else None,
        "aviso": (
            "Similitud alta no garantiza que el fragmento responda. "
            "Los adyacentes aportan contexto del mismo documento; no mezclan PDFs."
        ),
    }
