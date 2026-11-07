"""
Extrae el texto por página. No modifica el archivo fuente.

Funciones:
- extraer_pdf(): Lee cada página de un PDF.
- extraer_markdown(): Lee un Markdown como documento de una página.
- extraer_documento(): Elige el extractor según la extensión.
"""

from __future__ import annotations

from pathlib import Path

from .limpiar import limpiar_texto, marcar_calidad


def extraer_pdf(ruta: Path) -> list[dict]:
    from pypdf import PdfReader

    reader = PdfReader(str(ruta))
    meta = reader.metadata
    titulo = getattr(meta, "title", None) if meta is not None else None
    autor = getattr(meta, "author", None) if meta is not None else None
    paginas = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            crudo = page.extract_text() or ""
        except Exception:
            crudo = ""
        texto = limpiar_texto(crudo)
        calidad = marcar_calidad(texto)
        if not crudo and calidad == "vacia":
            calidad = "vacia"
        paginas.append({
            "pagina": i,
            "texto_crudo": crudo,
            "texto": texto,
            "n_caracteres_crudo": len(crudo),
            "n_caracteres": len(texto),
            "calidad": calidad,
            "titulo_pdf": titulo or None,
            "autor_pdf": autor or None,
        })
    return paginas


def extraer_markdown(ruta: Path) -> list[dict]:
    crudo = Path(ruta).read_text(encoding="utf-8")
    texto = limpiar_texto(crudo)
    return [{
        "pagina": 1,
        "texto_crudo": crudo,
        "texto": texto,
        "n_caracteres_crudo": len(crudo),
        "n_caracteres": len(texto),
        "calidad": marcar_calidad(texto),
        "titulo_pdf": None,
        "autor_pdf": None,
    }]


def extraer_documento(ruta: Path) -> list[dict]:
    suf = Path(ruta).suffix.lower()
    if suf == ".pdf":
        return extraer_pdf(ruta)
    if suf in {".md", ".txt"}:
        return extraer_markdown(ruta)
    raise ValueError(f"Formato no soportado en esta etapa: {ruta.name}")
