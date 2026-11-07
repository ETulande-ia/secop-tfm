"""
Rutas del Excel de expresiones y de las salidas de la evaluación de lenguaje.

Funciones:
- raiz_repo(): Resuelve la raíz de secop-tfm.
- ruta_excel(): Ruta del Excel de expresiones ciudadanas.
- ruta_salidas_nlq(): Directorio de salidas; lo crea si no existe.
"""

from __future__ import annotations

from pathlib import Path


def raiz_repo() -> Path:
    # src/nlq_eval/rutas.py → nlq_eval, src, raíz del proyecto.
    return Path(__file__).resolve().parents[2]


def ruta_excel() -> Path:
    return (
        raiz_repo()
        / "data"
        / "corpus"
        / "originales"
        / "expresiones_ciudadanas_simuladas_TFM.xlsx"
    )


def ruta_salidas_nlq() -> Path:
    dest = raiz_repo() / "notebooks" / "salidas" / "nlq"
    dest.mkdir(parents=True, exist_ok=True)
    return dest
