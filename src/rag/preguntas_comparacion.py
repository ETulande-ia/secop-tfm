"""
Preguntas fijadas para comparar el asistente con y sin recuperación documental.

Constantes:
- PREGUNTAS_COMPARACION: Pregunta, cobertura esperada y criterio de respuesta.

Funciones:
- validar_preguntas(): Comprueba identificadores y excluye los casos reservados.
"""

from __future__ import annotations

from nlq_eval.particion import IDS_RESERVADOS

PREGUNTAS_COMPARACION = [
    {
        "id": "COMP-01",
        "familia": "respondible",
        "tema": "minima_cuantia",
        "pregunta": "¿Qué es la modalidad de mínima cuantía?",
        "cobertura_esperada": "suficiente",
        "doc_id_esperado": "cce-minima-cuantia-2024",
        "fragmentos_gold": [
            "cce-minima-cuantia-2024-p004-004-601acaff",
            "cce-minima-cuantia-2024-p005-009-9e9f94b4",
        ],
        "hechos": ["mínima cuantía", "menor cuantía"],
        "prohibido": ["similitud"],
        "debe_reconocer_insuficiencia": False,
        "vigencia_no_acreditable": False,
        "criterio": (
            "El manual 2024 define la modalidad como convocatoria cuyo valor no "
            "excede el 10 % de la menor cuantía. No exige vigencia 2026."
        ),
    },
    {
        "id": "COMP-02",
        "familia": "respondible",
        "tema": "rup",
        "pregunta": "¿Qué es el Registro Único de Proponentes (RUP)?",
        "cobertura_esperada": "suficiente",
        "doc_id_esperado": "cce-requisitos-habilitantes-v3-2023",
        "fragmentos_gold": [
            "cce-requisitos-habilitantes-v3-2023-p009-029-8f2e777a",
            "cce-requisitos-habilitantes-v3-2023-p009-031-e5f06d7a",
        ],
        "hechos": ["RUP", "plena prueba"],
        "prohibido": ["similitud"],
        "debe_reconocer_insuficiencia": False,
        "vigencia_no_acreditable": False,
        "criterio": (
            "El manual de requisitos habilitantes v3 identifica el RUP como "
            "certificado de plena prueba (Ley 1150). No confundir con la "
            "excepción de mínima cuantía."
        ),
    },
    {
        "id": "COMP-03",
        "familia": "respondible",
        "tema": "c1_isolation_forest",
        "pregunta": "¿Cuántos árboles (n_estimators) usa Isolation Forest en c1_if_v1?",
        "cobertura_esperada": "suficiente",
        "doc_id_esperado": "ficha-c1-if-v1",
        "fragmentos_gold": ["ficha-c1-if-v1-p001-005-eb9b4376"],
        "hechos": ["200"],
        "prohibido": ["fraude"],
        "debe_reconocer_insuficiencia": False,
        "vigencia_no_acreditable": False,
        "criterio": (
            "La ficha publicada fija n_estimators = 200. El valor por defecto "
            "de sklearn (100) no es la respuesta del prototipo."
        ),
    },
    {
        "id": "COMP-04",
        "familia": "respondible",
        "tema": "c1_isolation_forest",
        "pregunta": "¿Qué variables usa la matriz C1 de Isolation Forest?",
        "cobertura_esperada": "suficiente",
        "doc_id_esperado": "ficha-c1-if-v1",
        "fragmentos_gold": ["ficha-c1-if-v1-p001-004-e68cbf43"],
        "hechos": ["log1p"],
        "prohibido": ["plazo de ejecución entra a C1"],
        "debe_reconocer_insuficiencia": False,
        "vigencia_no_acreditable": False,
        "criterio": (
            "C1 usa log1p_valor, log_valor_vs_modalidad y dummies de "
            "modalidad_grupo. No usa plazo ni n_entidad."
        ),
    },
    {
        "id": "COMP-05",
        "familia": "respondible",
        "tema": "c1_isolation_forest",
        "pregunta": "¿Una puntuación alta de Isolation Forest demuestra una irregularidad comprobada?",
        "cobertura_esperada": "suficiente",
        "doc_id_esperado": "ficha-c1-if-v1",
        "fragmentos_gold": ["ficha-c1-if-v1-p001-002-63fbcd8d"],
        "hechos": ["irregularidad"],
        "prohibido": ["es un fraude", "es una irregularidad comprobada"],
        "debe_reconocer_insuficiencia": False,
        "vigencia_no_acreditable": False,
        "requiere_negacion": True,
        "criterio": (
            "La ficha afirma que una puntuación alta no es irregularidad "
            "comprobada ni probabilidad de fraude."
        ),
    },
    {
        "id": "COMP-06",
        "familia": "parcial",
        "tema": "minima_cuantia",
        "pregunta": "¿Cuál es el valor en pesos de la mínima cuantía de Bogotá en 2026?",
        "cobertura_esperada": "parcial",
        "doc_id_esperado": "cce-minima-cuantia-2024",
        "fragmentos_gold": ["cce-minima-cuantia-2024-p005-010-612d9d78"],
        "hechos": [],
        "prohibido": [],
        "debe_reconocer_insuficiencia": True,
        "vigencia_no_acreditable": True,
        "criterio": (
            "El manual trae el 10 % de la menor cuantía, no el valor en pesos "
            "de Bogotá en 2026. Debe declarar el hueco y no inventar la cifra."
        ),
    },
    {
        "id": "COMP-07",
        "familia": "parcial",
        "tema": "c1_isolation_forest",
        "pregunta": "¿Cuántos contratos de Bogotá se puntuaron en c1_if_v1?",
        "cobertura_esperada": "parcial",
        "doc_id_esperado": "ficha-c1-if-v1",
        "fragmentos_gold": ["ficha-c1-if-v1-p001-003-d79b01ae"],
        "hechos": [],
        "prohibido": [],
        "debe_reconocer_insuficiencia": True,
        "vigencia_no_acreditable": False,
        "criterio": (
            "La ficha da 82.457 aptos nacionales de 2026-09, no el recorte de "
            "Bogotá. Usar 82.457 como si fuera Bogotá es un error factual."
        ),
    },
    {
        "id": "COMP-08",
        "familia": "fuera_corpus",
        "tema": "fuera",
        "pregunta": "¿Qué es el SISBÉN IV?",
        "cobertura_esperada": "no_cubierta",
        "doc_id_esperado": None,
        "fragmentos_gold": [],
        "hechos": [],
        "prohibido": ["sisben iv es un"],
        "debe_reconocer_insuficiencia": True,
        "vigencia_no_acreditable": False,
        "criterio": (
            "SISBÉN no está en el corpus v1. Con RAG debe declarar evidencia "
            "insuficiente. Sin RAG no debe venderse como respuesta del corpus."
        ),
    },
    {
        "id": "COMP-09",
        "familia": "fuera_corpus",
        "tema": "excluido",
        "pregunta": (
            "¿Cuál es el procedimiento sancionatorio de Colombia Compra Eficiente?"
        ),
        "cobertura_esperada": "no_cubierta",
        "doc_id_esperado": None,
        "fragmentos_gold": [],
        "hechos": [],
        "prohibido": ["la multa máxima es"],
        "debe_reconocer_insuficiencia": True,
        "vigencia_no_acreditable": False,
        "criterio": (
            "La guía sancionatoria está excluida del corpus v1. No hay gold."
        ),
    },
    {
        "id": "COMP-10",
        "familia": "minima_rup",
        "tema": "rup",
        "pregunta": "¿Los oferentes deben acreditar el RUP en un proceso de mínima cuantía?",
        "cobertura_esperada": "suficiente",
        "doc_id_esperado": "cce-minima-cuantia-2024",
        "fragmentos_gold": [
            "cce-minima-cuantia-2024-p010-027-e5bf81f3",
            "cce-minima-cuantia-2024-p012-035-8d0c5423",
        ],
        "hechos": ["acreditar"],
        "prohibido": ["plena prueba"],
        "debe_reconocer_insuficiencia": False,
        "vigencia_no_acreditable": False,
        "requiere_negacion": True,
        "criterio": (
            "Excepción del manual de mínima cuantía: no es obligatorio acreditar "
            "el RUP. La regla general del manual de habilitantes no responde esto."
        ),
    },
    {
        "id": "COMP-11",
        "familia": "vigencia",
        "tema": "minima_cuantia",
        "pregunta": (
            "¿El manual de mínima cuantía de 2024 está vigente para los contratos "
            "de septiembre de 2026?"
        ),
        "cobertura_esperada": "parcial",
        "doc_id_esperado": "cce-minima-cuantia-2024",
        "fragmentos_gold": [
            "cce-minima-cuantia-2024-p004-004-601acaff",
            "cce-minima-cuantia-2024-p005-009-9e9f94b4",
        ],
        "hechos": [],
        "prohibido": ["está vigente para 2026", "sí está vigente"],
        "debe_reconocer_insuficiencia": True,
        "vigencia_no_acreditable": True,
        "criterio": (
            "El PDF es de 2024 y el extracto analítico es 2026-09. El corpus no "
            "acredita vigencia normativa actual. No debe afirmar que rige 2026."
        ),
    },
    {
        "id": "COMP-12",
        "familia": "vigencia",
        "tema": "fuera",
        "pregunta": (
            "¿Qué artículos de la Ley 80 de 2026 modifican la mínima cuantía?"
        ),
        "cobertura_esperada": "no_cubierta",
        "doc_id_esperado": None,
        "fragmentos_gold": [],
        "hechos": [],
        "prohibido": ["el artículo"],
        "debe_reconocer_insuficiencia": True,
        "vigencia_no_acreditable": True,
        "criterio": (
            "No hay Ley 80 de 2026 en el corpus. Inventar artículos es un error. "
            "Debe reconocer que no hay evidencia documental."
        ),
    },
]


def validar_preguntas() -> None:
    ids = [p["id"] for p in PREGUNTAS_COMPARACION]
    if len(ids) != len(set(ids)):
        raise ValueError("Hay IDs repetidos en PREGUNTAS_COMPARACION.")
    choque = [i for i in ids if i in IDS_RESERVADOS]
    if choque:
        raise RuntimeError(f"El experimento usó IDs reservados: {choque}")
    if any(str(i).startswith("EC-") for i in ids):
        raise RuntimeError("No se usan IDs EC en este experimento.")
    if any(str(i).startswith("RAG-H") for i in ids):
        raise RuntimeError("No se usa el holdout RAG-H.")
