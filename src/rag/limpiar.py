"""
Limpia artefactos de extracción sin reescribir el contenido jurídico.

Funciones:
- limpiar_texto(): Quita controles, marcas CID, guiones de corte y espacios sobrantes.
- ratio_letras(): Mide la proporción de letras del texto.
- marcar_calidad(): Clasifica el texto como ok, corto, vacío o sospechoso.
"""

from __future__ import annotations

import re

_CID = re.compile(r"\(cid:\d+\)")
_GUION = re.compile(r"(\w)-\n(\w)")
_SALTOS = re.compile(r"[ \t]+\n")
_ESPACIOS = re.compile(r"[ \t]{2,}")
_LINEAS = re.compile(r"\n{3,}")
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_PUNTOS_GUIA = re.compile(r"(?:\.\s*){4,}")


def limpiar_texto(texto: str) -> str:
    t = str(texto or "")
    t = t.replace("\u00ad", "")
    t = _CTRL.sub(" ", t)
    t = _CID.sub(" ", t)
    t = _PUNTOS_GUIA.sub(" ", t)
    t = _GUION.sub(r"\1\2", t)
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = _SALTOS.sub("\n", t)
    t = _ESPACIOS.sub(" ", t)
    t = _LINEAS.sub("\n\n", t)
    lineas = [ln.strip() for ln in t.split("\n")]
    return "\n".join(lineas).strip()


def ratio_letras(texto: str) -> float:
    t = str(texto or "")
    if not t:
        return 0.0
    letras = sum(ch.isalpha() for ch in t)
    return letras / max(len(t), 1)


def marcar_calidad(texto: str) -> str:
    t = (texto or "").strip()
    if not t:
        return "vacia"
    if len(t) < 80:
        return "corta"
    if ratio_letras(t) < 0.35:
        return "sospechosa"
    if "cid:" in t.lower():
        return "sospechosa"
    return "ok"
