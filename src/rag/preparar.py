"""
Inventaria, extrae, fragmenta y guarda el corpus RAG en Parquet.

Funciones:
- verificar_dependencias(): Comprueba pypdf y pyarrow.
- inventariar(): Lista los documentos del catálogo y su hash.
- procesar_documento(): Extrae páginas y fragmentos de un archivo.
- preparar_corpus(): Genera páginas, fragmentos y el manifiesto.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .catalogo import DOCUMENTOS, EXCLUIDOS
from .extraer import extraer_documento
from .fragmentar import fragmentar_paginas
from .limpiar import marcar_calidad
from .rutas import ruta_originales, ruta_salidas_rag, sincronizar_originales

COLUMNAS_FRAGMENTO = [
    "fragment_id",
    "doc_id",
    "archivo",
    "titulo",
    "entidad",
    "version",
    "fecha_documento",
    "fuente",
    "url",
    "alcance",
    "advertencia_vigencia",
    "seccion",
    "pagina_inicio",
    "pagina_fin",
    "orden",
    "n_caracteres",
    "calidad",
    "tipo",
    "texto",
]


def verificar_dependencias() -> dict:
    estado = {}
    for nombre in ("pandas", "pypdf", "pyarrow"):
        try:
            __import__(nombre)
            estado[nombre] = "ok"
        except ImportError:
            estado[nombre] = "ausente"
    return estado


def _sha256_archivo(ruta: Path) -> str:
    h = hashlib.sha256()
    with Path(ruta).open("rb") as fh:
        for bloque in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(bloque)
    return h.hexdigest()


def asegurar_ficha() -> Path:
    origen = Path(__file__).with_name("ficha_c1_isolation_forest.md")
    destino = ruta_originales() / "ficha_c1_isolation_forest.md"
    destino.parent.mkdir(parents=True, exist_ok=True)
    if not origen.is_file():
        raise FileNotFoundError(f"Falta la ficha C1 en {origen}")
    if not destino.exists() or origen.read_bytes() != destino.read_bytes():
        shutil.copy2(origen, destino)
    return destino


def _meta_archivo(ruta: Path) -> dict:
    if not ruta.is_file():
        return {"existe": False, "bytes": None, "sha256": None}
    return {
        "existe": True,
        "bytes": ruta.stat().st_size,
        "sha256": _sha256_archivo(ruta),
    }


def inventariar() -> list[dict]:
    dest = ruta_originales()
    filas = []
    for doc in (*DOCUMENTOS, *EXCLUIDOS):
        ruta = dest / doc["archivo"]
        meta = _meta_archivo(ruta)
        filas.append({
            **doc,
            "ruta": str(ruta),
            **meta,
        })
    return filas


def _tipo(archivo: str) -> str:
    suf = Path(archivo).suffix.lower()
    if suf == ".pdf":
        return "pdf"
    if suf in {".md", ".txt"}:
        return "markdown"
    return suf.lstrip(".") or "desconocido"


def procesar_documento(doc: dict, originales: Path) -> tuple[list[dict], list[dict]]:
    ruta = originales / doc["archivo"]
    paginas_raw = extraer_documento(ruta)
    paginas = []
    for p in paginas_raw:
        paginas.append({
            "doc_id": doc["doc_id"],
            "archivo": doc["archivo"],
            "titulo": doc["titulo"],
            "pagina": p["pagina"],
            "n_caracteres_crudo": p["n_caracteres_crudo"],
            "n_caracteres": p["n_caracteres"],
            "calidad": p["calidad"],
            "texto": p["texto"],
            "vista_previa": (p["texto"] or "")[:180],
        })
    fragmentos = []
    for f in fragmentar_paginas(paginas_raw, doc["doc_id"]):
        texto = f["texto"]
        fragmentos.append({
            "fragment_id": f["fragment_id"],
            "doc_id": doc["doc_id"],
            "archivo": doc["archivo"],
            "titulo": doc["titulo"],
            "entidad": doc["entidad"],
            "version": doc.get("version"),
            "fecha_documento": doc.get("fecha_documento"),
            "fuente": doc["fuente"],
            "url": doc.get("url"),
            "alcance": doc.get("alcance"),
            "advertencia_vigencia": doc.get("advertencia_vigencia"),
            "seccion": f.get("seccion"),
            "pagina_inicio": f.get("pagina_inicio"),
            "pagina_fin": f.get("pagina_fin"),
            "orden": f["orden"],
            "n_caracteres": len(texto),
            "calidad": marcar_calidad(texto),
            "tipo": _tipo(doc["archivo"]),
            "texto": texto,
        })
    return paginas, fragmentos


def preparar_corpus(reescribir: bool = True) -> dict:
    deps = verificar_dependencias()
    faltan = [k for k, v in deps.items() if v != "ok"]
    if faltan:
        raise ImportError(
            "Dependencias ausentes: " + ", ".join(faltan)
            + ". En Jupyter: pip install --user pypdf pyarrow"
        )

    originales = ruta_originales()
    originales.mkdir(parents=True, exist_ok=True)
    salidas = ruta_salidas_rag()
    salidas.mkdir(parents=True, exist_ok=True)

    sync = sincronizar_originales()
    ficha = asegurar_ficha()
    inventario = inventariar()

    paginas_todas: list[dict] = []
    fragmentos_todos: list[dict] = []
    resumen_docs = []

    for doc in DOCUMENTOS:
        if not doc.get("incluir", True):
            continue
        ruta = originales / doc["archivo"]
        fila = {
            "doc_id": doc["doc_id"],
            "archivo": doc["archivo"],
            "titulo": doc["titulo"],
            "tipo": _tipo(doc["archivo"]),
            "incluir": True,
        }
        if not ruta.is_file():
            fila["error"] = "archivo ausente en data/corpus/originales"
            fila["n_paginas"] = 0
            fila["n_fragmentos"] = 0
            resumen_docs.append(fila)
            continue
        paginas, fragmentos = procesar_documento(doc, originales)
        paginas_todas.extend(paginas)
        fragmentos_todos.extend(fragmentos)
        cal = pd.Series([p["calidad"] for p in paginas])
        fila.update({
            "error": None,
            "n_paginas": len(paginas),
            "n_paginas_ok": int((cal == "ok").sum()),
            "n_paginas_vacias": int((cal == "vacia").sum()),
            "n_paginas_cortas": int((cal == "corta").sum()),
            "n_paginas_sospechosas": int((cal == "sospechosa").sum()),
            "n_fragmentos": len(fragmentos),
            "n_caracteres": int(sum(p["n_caracteres"] for p in paginas)),
            "sha256": _sha256_archivo(ruta),
            "bytes": ruta.stat().st_size,
        })
        resumen_docs.append(fila)

    excluidos_ok = []
    for doc in EXCLUIDOS:
        ruta = originales / doc["archivo"]
        excluidos_ok.append({
            **doc,
            "conservado": ruta.is_file(),
            "bytes": ruta.stat().st_size if ruta.is_file() else None,
            "procesado": False,
        })

    df_pag = pd.DataFrame(paginas_todas)
    df_frag = pd.DataFrame(fragmentos_todos, columns=COLUMNAS_FRAGMENTO)
    df_res = pd.DataFrame(resumen_docs)

    if reescribir:
        if not df_pag.empty:
            df_pag.to_parquet(salidas / "paginas.parquet", index=False)
            df_pag.drop(columns=["texto"], errors="ignore").to_csv(
                salidas / "calidad_paginas.csv", index=False, encoding="utf-8"
            )
        if not df_frag.empty:
            df_frag.to_parquet(salidas / "fragmentos.parquet", index=False)
            df_frag.drop(columns=["texto"], errors="ignore").to_csv(
                salidas / "indice_fragmentos.csv", index=False, encoding="utf-8"
            )
        df_res.to_csv(salidas / "resumen_documentos.csv", index=False, encoding="utf-8")

    informe = {
        "generado_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "reescribir": reescribir,
        "dependencias": deps,
        "sincronizacion": sync,
        "ficha": str(ficha),
        "originales": str(originales),
        "salidas": str(salidas),
        "n_documentos_incluidos": int(sum(1 for d in resumen_docs if not d.get("error"))),
        "n_paginas": int(len(paginas_todas)),
        "n_fragmentos": int(len(fragmentos_todos)),
        "documentos": resumen_docs,
        "excluidos": excluidos_ok,
        "inventario": inventario,
        "archivos_salida": [
            "fragmentos.parquet",
            "paginas.parquet",
            "calidad_paginas.csv",
            "indice_fragmentos.csv",
            "resumen_documentos.csv",
            "informe_preparacion.json",
        ],
    }
    if reescribir:
        (salidas / "informe_preparacion.json").write_text(
            json.dumps(informe, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return {
        **informe,
        "paginas": df_pag,
        "fragmentos": df_frag,
        "resumen": df_res,
    }
