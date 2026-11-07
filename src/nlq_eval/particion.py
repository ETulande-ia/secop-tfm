"""
Carga el Excel de 77 expresiones y separa 51 de desarrollo y 26 reservadas.

Funciones:
- cargar_excel(): Lee la hoja de expresiones simuladas.
- partir(): Separa desarrollo, reservadas y conteos por categoría.
"""

from __future__ import annotations

from .rutas import ruta_excel

IDS_RESERVADOS = frozenset({
    "EC-005", "EC-006", "EC-011", "EC-012", "EC-017", "EC-018",
    "EC-023", "EC-024", "EC-029", "EC-030", "EC-035", "EC-036",
    "EC-041", "EC-042", "EC-046", "EC-047", "EC-052", "EC-053",
    "EC-058", "EC-059", "EC-064", "EC-065", "EC-070", "EC-071",
    "EC-076", "EC-077",
})

COLS = {
    "id": "ID",
    "categoria": "Categoría",
    "pregunta": "Expresión ciudadana simulada",
    "intencion_excel": "Intención esperada",
    "filtros_excel": "Filtros o entidades",
    "ambigua_excel": "¿Ambigua?",
    "comportamiento_excel": "Comportamiento esperado",
    "concepto": "Concepto asociado",
    "precaucion": "Precaución / criterio",
}


def cargar_excel(path=None) -> list[dict]:
    import pandas as pd

    p = path or ruta_excel()
    df = pd.read_excel(p, sheet_name="Expresiones simuladas")
    filas = []
    for _, row in df.iterrows():
        item = {k: (None if pd.isna(row[c]) else str(row[c]).strip()) for k, c in COLS.items()}
        filas.append(item)
    return filas


def partir(filas: list[dict]) -> dict:
    ids = [f["id"] for f in filas]
    reservadas = [f for f in filas if f["id"] in IDS_RESERVADOS]
    desarrollo = [f for f in filas if f["id"] not in IDS_RESERVADOS]
    cats = {}
    for f in filas:
        cats.setdefault(f["categoria"], 0)
        cats[f["categoria"]] += 1
    return {
        "n_excel": len(filas),
        "n_desarrollo": len(desarrollo),
        "n_reservadas": len(reservadas),
        "ids_excel": ids,
        "ids_desarrollo": [f["id"] for f in desarrollo],
        "ids_reservadas": [f["id"] for f in reservadas],
        "categorias": cats,
        "desarrollo": desarrollo,
        "reservadas": reservadas,
        "faltan_reservados": sorted(IDS_RESERVADOS - set(ids)),
    }
