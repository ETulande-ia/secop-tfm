"""
Genera embeddings con OpenAI y los guarda en caché local. No imprime la clave.

Funciones:
- clave_disponible(): Indica si hay una API key.
- huella_indexacion(): Resume fragmentos y modelo para decidir si la caché sirve.
- generar_embeddings(): Calcula o reutiliza los vectores del corpus.
- embeber_consulta(): Calcula el embedding de una pregunta.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .rutas import ruta_salidas_rag

MODELO_DEFECTO = "text-embedding-3-small"
TAMANO_LOTE = 64
REINTENTOS = 3
ARCHIVO_VECTORES = "embeddings_text-embedding-3-small.npz"
ARCHIVO_META = "embeddings_meta.json"


def clave_disponible() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY"))


def huella_indexacion(df: pd.DataFrame, modelo: str) -> str:
    h = hashlib.sha256()
    h.update(modelo.encode("utf-8"))
    h.update(b"\n")
    orden = df.sort_values("fragment_id")
    for _, row in orden.iterrows():
        h.update(str(row["fragment_id"]).encode("utf-8"))
        h.update(b"\0")
        h.update(str(row["texto"]).encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def _cliente():
    if not clave_disponible():
        raise RuntimeError(
            "Falta OPENAI_API_KEY en el entorno de Jupyter. "
            "No se escribe la clave en el notebook ni en git."
        )
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise ImportError(
            "Instalar en el kernel: pip install --user openai"
        ) from exc
    return OpenAI(default_headers={"Accept-Encoding": "gzip, deflate"})


def _embeber_lote(cliente, textos: list[str], modelo: str) -> list[list[float]]:
    ultimo = None
    for intento in range(1, REINTENTOS + 1):
        try:
            resp = cliente.embeddings.create(model=modelo, input=textos)
            ordenados = sorted(resp.data, key=lambda d: d.index)
            return [list(d.embedding) for d in ordenados]
        except Exception as exc:
            ultimo = exc
            nombre = type(exc).__name__
            if "Auth" in nombre or "Permission" in nombre:
                raise
            if "RateLimit" in nombre or "APIStatus" in nombre or "APIError" in nombre or "APIConnection" in nombre:
                time.sleep(2 ** intento)
                continue
            raise
    raise RuntimeError(f"Embeddings: agotados reintentos ({REINTENTOS}).") from ultimo


def cargar_cache(salidas: Path, huella: str, modelo: str) -> dict | None:
    meta_p = salidas / ARCHIVO_META
    vec_p = salidas / ARCHIVO_VECTORES
    if not meta_p.is_file() or not vec_p.is_file():
        return None
    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    if meta.get("huella") != huella or meta.get("modelo") != modelo:
        return None
    datos = np.load(vec_p, allow_pickle=False)
    return {
        "vectores": datos["vectores"],
        "fragment_ids": [str(x) for x in datos["fragment_ids"]],
        "meta": meta,
        "desde_cache": True,
    }


def generar_embeddings(
    df: pd.DataFrame,
    modelo: str = MODELO_DEFECTO,
    reutilizar: bool = True,
    salidas: Path | None = None,
) -> dict:
    dest = Path(salidas) if salidas else ruta_salidas_rag()
    dest.mkdir(parents=True, exist_ok=True)
    trabajo = df.sort_values("fragment_id").reset_index(drop=True)
    huella = huella_indexacion(trabajo, modelo)
    if reutilizar:
        cache = cargar_cache(dest, huella, modelo)
        if cache is not None:
            cache["df"] = trabajo
            return cache

    cliente = _cliente()
    textos = trabajo["texto"].astype(str).tolist()
    ids = trabajo["fragment_id"].astype(str).tolist()
    vectores: list[list[float]] = []
    t0 = time.perf_counter()
    for i in range(0, len(textos), TAMANO_LOTE):
        lote = textos[i : i + TAMANO_LOTE]
        vectores.extend(_embeber_lote(cliente, lote, modelo))
    segundos = time.perf_counter() - t0
    mat = np.asarray(vectores, dtype=np.float32)
    dim = int(mat.shape[1]) if mat.ndim == 2 else 0
    meta = {
        "modelo": modelo,
        "dimension": dim,
        "n_vectores": int(mat.shape[0]),
        "huella": huella,
        "generado_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "segundos": round(segundos, 3),
        "lote": TAMANO_LOTE,
        "desde_cache": False,
    }
    np.savez_compressed(
        dest / ARCHIVO_VECTORES,
        vectores=mat,
        fragment_ids=np.array(ids),
    )
    (dest / ARCHIVO_META).write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "vectores": mat,
        "fragment_ids": ids,
        "meta": meta,
        "desde_cache": False,
        "df": trabajo,
    }


def embeber_consulta(texto: str, modelo: str = MODELO_DEFECTO) -> np.ndarray:
    cliente = _cliente()
    vec = _embeber_lote(cliente, [texto], modelo)[0]
    return np.asarray(vec, dtype=np.float32)
