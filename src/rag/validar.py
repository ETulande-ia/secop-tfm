"""
Valida fragmentos del corpus antes de indexarlos. No altera fragmentos.parquet.

Funciones:
- cargar_fragmentos(): Lee el Parquet de fragmentos.
- controles_integridad(): Comprueba columnas, identificadores y duplicados.
- artefactos_texto(): Detecta restos de extracción.
- motivo_exclusion(): Indica por qué un fragmento no debe indexarse.
- validar_fragmentos(): Resume integridad, exclusiones y artefactos.
"""

from __future__ import annotations

import re

import pandas as pd

from .rutas import ruta_salidas_rag

COLUMNAS_OBLIGATORIAS = (
    "fragment_id",
    "doc_id",
    "archivo",
    "titulo",
    "texto",
    "pagina_inicio",
    "pagina_fin",
    "n_caracteres",
    "calidad",
)

_SECCION_TOC = {"TABLA DE CONTENIDO", "CONTENIDO"}
_PAGINA_DOC = re.compile(r"P[aá]gina\s+\d+\s+de\s+\d+", re.I)
_CODIGO_CCE = re.compile(r"C[OÓ]DIGO:\s*CCE-", re.I)
_FIN_NUMERO = re.compile(r"\d{1,3}$")
_URL_PARTIDA = re.compile(r"https?://\S+\.\s*$", re.M)
_ESPACIO = re.compile(
    r"\be l\b|c ontratar|op tar|sintetizar se|deb en |bi enes|c ontratar",
    re.I,
)


def cargar_fragmentos(ruta=None) -> pd.DataFrame:
    path = ruta or (ruta_salidas_rag() / "fragmentos.parquet")
    if not path.is_file():
        raise FileNotFoundError(
            f"No está {path}. Ejecute antes 11_preparacion_corpus_rag.ipynb."
        )
    return pd.read_parquet(path)


def controles_integridad(df: pd.DataFrame) -> pd.DataFrame:
    filas = []
    filas.append({
        "control": "n_filas",
        "observado": int(len(df)),
        "esperado": 254,
        "ok": len(df) == 254,
    })
    unicos = df["fragment_id"].nunique() if "fragment_id" in df.columns else 0
    filas.append({
        "control": "fragment_id_unico",
        "observado": int(unicos),
        "esperado": int(len(df)),
        "ok": unicos == len(df) and unicos > 0,
    })
    faltan = [c for c in COLUMNAS_OBLIGATORIAS if c not in df.columns]
    filas.append({
        "control": "columnas_obligatorias",
        "observado": ",".join(faltan) if faltan else "ok",
        "esperado": "todas",
        "ok": not faltan,
    })
    if "texto" in df.columns:
        vacios = int(df["texto"].fillna("").astype(str).str.strip().eq("").sum())
    else:
        vacios = len(df)
    filas.append({
        "control": "texto_no_vacio",
        "observado": vacios,
        "esperado": 0,
        "ok": vacios == 0,
    })
    docs = set(df["doc_id"]) if "doc_id" in df.columns else set()
    esperados = {
        "cce-minima-cuantia-2024",
        "cce-requisitos-habilitantes-v3-2023",
        "diccionario-datos-abiertos-secop",
        "ficha-c1-if-v1",
    }
    filas.append({
        "control": "documentos_v1",
        "observado": ",".join(sorted(docs)),
        "esperado": "4 documentos v1",
        "ok": docs == esperados,
    })
    return pd.DataFrame(filas)


def artefactos_texto(texto: str) -> list[str]:
    t = texto or ""
    flags = []
    if "datos.gov." in t or _URL_PARTIDA.search(t):
        flags.append("url_partida")
    if _ESPACIO.search(t):
        flags.append("espacio_interior")
    return flags


def es_tabla_contenido(texto: str, seccion: str | None) -> bool:
    sec = (seccion or "").strip().upper()
    if sec in _SECCION_TOC:
        return True
    t = texto or ""
    lineas = [ln.strip() for ln in t.splitlines() if ln.strip()]
    fin_num = sum(
        1 for ln in lineas if _FIN_NUMERO.search(ln) and len(ln) < 140
    )
    if "TABLA DE CONTENIDO" in t.upper() and fin_num >= 5:
        return True
    if len(lineas) >= 6 and fin_num / len(lineas) >= 0.7:
        return True
    return False


def es_encabezado_pagina(texto: str) -> bool:
    t = texto or ""
    if not (_PAGINA_DOC.search(t) and _CODIGO_CCE.search(t)):
        return False
    cuerpo = re.sub(
        r"MANUAL PARA DETERMINAR[\s\S]{0,120}CONTRATACI[OÓ]N",
        " ",
        t,
        flags=re.I,
    )
    cuerpo = re.sub(r"C[OÓ]DIGO:.*", " ", cuerpo)
    cuerpo = re.sub(r"Versi[oó]n:.*", " ", cuerpo)
    cuerpo = re.sub(r"P[aá]gina\s+\d+\s+de\s+\d+", " ", cuerpo, flags=re.I)
    cuerpo = re.sub(r"\s+", " ", cuerpo).strip()
    return len(cuerpo) < 80


def motivo_exclusion(row: pd.Series) -> str | None:
    if es_tabla_contenido(row.get("texto") or "", row.get("seccion")):
        return "tabla_contenido"
    if es_encabezado_pagina(row.get("texto") or ""):
        return "encabezado_pagina"
    return None


def validar_fragmentos(ruta=None) -> dict:
    df = cargar_fragmentos(ruta)
    controles = controles_integridad(df)
    out = df.copy()
    out["artefactos"] = out["texto"].map(
        lambda t: ",".join(artefactos_texto(t)) if artefactos_texto(t) else None
    )
    out["motivo_exclusion"] = out.apply(motivo_exclusion, axis=1)
    out["indexar"] = out["motivo_exclusion"].isna()
    excluidos = out.loc[~out["indexar"]].copy()
    indexar = out.loc[out["indexar"]].copy()
    return {
        "todos": out,
        "indexar": indexar,
        "excluidos": excluidos,
        "controles": controles,
        "n_total": int(len(out)),
        "n_indexar": int(len(indexar)),
        "n_excluidos": int(len(excluidos)),
    }
