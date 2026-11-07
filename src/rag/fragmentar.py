"""
Divide el texto en fragmentos por sección o por tamaño, conservando la página.

Funciones:
- fragmentar_paginas(): Produce fragmentos con identificador, página y orden.
"""

from __future__ import annotations

import hashlib
import re

_TITULO = re.compile(
    r"^(?:(?:capítulo|capitulo|artículo|articulo|sección|seccion|anexo)\b|"
    r"\d+(?:\.\d+){0,3}\.?\s+[A-ZÁÉÍÓÚÑ]|[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s]{8,})$",
    re.IGNORECASE,
)
_MD_H = re.compile(r"^#{1,3}\s+(.+)$")


def _id_fragmento(doc_id: str, pagina: int, orden: int, texto: str) -> str:
    huella = hashlib.sha1(texto.encode("utf-8")).hexdigest()[:8]
    return f"{doc_id}-p{pagina:03d}-{orden:03d}-{huella}"


def _es_titulo(linea: str) -> bool:
    s = linea.strip()
    if len(s) < 6 or len(s) > 140:
        return False
    if _MD_H.match(s):
        return True
    return bool(_TITULO.match(s))


def _partir_tamano(texto: str, max_car: int, solape: int) -> list[str]:
    t = texto.strip()
    if not t:
        return []
    if len(t) <= max_car:
        return [t]
    partes = []
    i = 0
    while i < len(t):
        fin = min(len(t), i + max_car)
        if fin < len(t):
            corte = t.rfind(". ", i + max_car // 2, fin)
            if corte == -1:
                corte = t.rfind("\n", i + max_car // 2, fin)
            if corte != -1:
                fin = corte + 1
        trozo = t[i:fin].strip()
        if trozo:
            partes.append(trozo)
        if fin >= len(t):
            break
        i = max(fin - solape, i + 1)
    return partes


def _fusionar_cortos(fragmentos: list[dict], doc_id: str, min_car: int) -> list[dict]:
    if not fragmentos:
        return []
    out = [fragmentos[0].copy()]
    for f in fragmentos[1:]:
        if out[-1]["n_caracteres"] < min_car or f["n_caracteres"] < min_car:
            out[-1]["texto"] = (out[-1]["texto"] + "\n\n" + f["texto"]).strip()
            out[-1]["pagina_fin"] = f["pagina_fin"]
            out[-1]["n_caracteres"] = len(out[-1]["texto"])
            if f.get("seccion") and not out[-1].get("seccion"):
                out[-1]["seccion"] = f["seccion"]
            continue
        out.append(f.copy())
    for i, f in enumerate(out, start=1):
        f["orden"] = i
        f["fragment_id"] = _id_fragmento(
            doc_id, int(f["pagina_inicio"] or 1), i, f["texto"]
        )
        f["n_caracteres"] = len(f["texto"])
    return out


def fragmentar_paginas(
    paginas: list[dict],
    doc_id: str,
    max_car: int = 900,
    solape: int = 120,
    min_car: int = 200,
) -> list[dict]:
    fragmentos = []
    seccion = ""
    orden = 0
    buffer = ""
    pag_ini = None
    pag_fin = None

    def flush():
        nonlocal buffer, pag_ini, pag_fin, orden
        texto = buffer.strip()
        buffer = ""
        if not texto:
            pag_ini = pag_fin = None
            return
        for trozo in _partir_tamano(texto, max_car, solape):
            if len(trozo) < min_car and fragmentos:
                fragmentos[-1]["texto"] = (fragmentos[-1]["texto"] + "\n\n" + trozo).strip()
                fragmentos[-1]["pagina_fin"] = pag_fin
                fragmentos[-1]["n_caracteres"] = len(fragmentos[-1]["texto"])
                continue
            orden += 1
            fragmentos.append({
                "fragment_id": _id_fragmento(doc_id, pag_ini or 1, orden, trozo),
                "doc_id": doc_id,
                "seccion": seccion or None,
                "pagina_inicio": pag_ini,
                "pagina_fin": pag_fin,
                "orden": orden,
                "n_caracteres": len(trozo),
                "texto": trozo,
            })
        pag_ini = pag_fin = None

    for pag in paginas:
        texto = pag.get("texto") or ""
        pagina = int(pag["pagina"])
        if pag.get("calidad") == "vacia":
            continue
        bloques = [b.strip() for b in re.split(r"\n\s*\n", texto) if b.strip()]
        if not bloques:
            bloques = [texto] if texto.strip() else []
        for bloque in bloques:
            primera = bloque.split("\n", 1)[0].strip()
            md = _MD_H.match(primera)
            if md or _es_titulo(primera):
                flush()
                seccion = md.group(1).strip() if md else primera
            if pag_ini is None:
                pag_ini = pagina
            pag_fin = pagina
            buffer = f"{buffer}\n\n{bloque}".strip() if buffer else bloque
            if len(buffer) >= max_car:
                flush()
                pag_ini = pagina
                pag_fin = pagina
        if buffer and len(buffer) >= max_car:
            flush()
    flush()
    return _fusionar_cortos(fragmentos, doc_id, min_car)
