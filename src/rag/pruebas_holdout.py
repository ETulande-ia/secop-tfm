"""
Preguntas de reserva RAG-H para comprobar reglas no usadas en el ajuste.

Constantes:
- PREGUNTAS_HOLDOUT: Pregunta, cobertura esperada y fragmentos relevantes.

Funciones:
- comprobar_holdout(): Verifica que no reutilicen identificadores reservados.
"""

from __future__ import annotations

from .pruebas_ampliadas import IDS_RESERVADOS_EXCEL, comprobar_reservados

PREGUNTAS_HOLDOUT = [
    {
        "id": "RAG-H-01",
        "tema": "minima_cuantia",
        "pregunta": "¿Hay que presentar el certificado del RUP si el proceso es de mínima cuantía?",
        "tipo": "excepcion",
        "cobertura_esperada": "suficiente",
        "doc_id": "cce-minima-cuantia-2024",
        "en_corpus": True,
        "relevantes": [
            "cce-minima-cuantia-2024-p010-027-e5bf81f3",
            "cce-minima-cuantia-2024-p012-035-8d0c5423",
        ],
        "justificacion_gold": (
            "Misma excepción que el manual de mínima cuantía: no acreditar RUP. "
            "No se usa el certificado de plena prueba del manual de requisitos."
        ),
        "nota": "Comprueba alcance: modalidad nombrada prima sobre la regla general.",
        "regla": "alcance_modalidad",
    },
    {
        "id": "RAG-H-02",
        "tema": "c1_isolation_forest",
        "pregunta": "¿El Isolation Forest publicado en c1_if_v1 fija n_estimators en 200?",
        "tipo": "cifra",
        "cobertura_esperada": "suficiente",
        "doc_id": "ficha-c1-if-v1",
        "en_corpus": True,
        "relevantes": ["ficha-c1-if-v1-p001-005-eb9b4376"],
        "justificacion_gold": "La tabla del algoritmo publicado fija n_estimators = 200.",
        "nota": "Identificador técnico en la pregunta, sin verbo incidental.",
        "regla": "termino_tecnico",
    },
    {
        "id": "RAG-H-03",
        "tema": "c1_isolation_forest",
        "pregunta": "¿Cuántos contratos de Cali recibieron score_if en c1_if_v1?",
        "tipo": "parcial",
        "cobertura_esperada": "parcial",
        "doc_id": "ficha-c1-if-v1",
        "en_corpus": True,
        "relevantes": [],
        "justificacion_gold": (
            "La ficha da 82.457 aptos nacionales, no el recorte de Cali. "
            "Cali no se usó en las 40 preguntas de ajuste."
        ),
        "nota": "Calificador de instancia distinto de Bogotá.",
        "regla": "calificador_instancia",
    },
    {
        "id": "RAG-H-04",
        "tema": "diccionario_secop",
        "pregunta": "¿Qué significa el campo Precio Base en el diccionario de datos abiertos?",
        "tipo": "definicion",
        "cobertura_esperada": "suficiente",
        "doc_id": "diccionario-datos-abiertos-secop",
        "en_corpus": True,
        "relevantes": ["diccionario-datos-abiertos-secop-p002-005-0ad57a0b"],
        "justificacion_gold": "Campo 21: Precio base del proceso de compra.",
        "nota": "Campo exacto; no el campo inexistente «valor del contrato».",
        "regla": "campo_exacto",
    },
    {
        "id": "RAG-H-05",
        "tema": "fuera_de_corpus",
        "pregunta": "¿Qué requisitos habilitantes exige SECOP 3?",
        "tipo": "fuera",
        "cobertura_esperada": "no_cubierta",
        "doc_id": None,
        "en_corpus": False,
        "relevantes": [],
        "justificacion_gold": (
            "SECOP 3 / III no está en el corpus. El manual de 2023 describe SECOP II."
        ),
        "nota": "Versión de plataforma distinta de RAG-D-40 (SECOP III).",
        "regla": "version_producto",
    },
    {
        "id": "RAG-H-06",
        "tema": "minima_cuantia",
        "pregunta": "¿Cuál es la menor cuantía en pesos de la Gobernación de Antioquia en 2026?",
        "tipo": "parcial",
        "cobertura_esperada": "parcial",
        "doc_id": "cce-minima-cuantia-2024",
        "en_corpus": True,
        "relevantes": [],
        "justificacion_gold": (
            "Hay tabla de SMLMV y regla del 10 %, no el presupuesto de esa gobernación."
        ),
        "nota": "Entidad distinta de Bogotá.",
        "regla": "calificador_instancia",
    },
    {
        "id": "RAG-H-07",
        "tema": "minima_cuantia",
        "pregunta": "¿En mínima cuantía se acepta la oferta hábil de menor precio?",
        "tipo": "definicion",
        "cobertura_esperada": "suficiente",
        "doc_id": "cce-minima-cuantia-2024",
        "en_corpus": True,
        "relevantes": [
            "cce-minima-cuantia-2024-p010-024-2fe4e22b",
            "cce-minima-cuantia-2024-p010-025-1019b858",
            "cce-minima-cuantia-2024-p010-026-8405dec0",
        ],
        "justificacion_gold": "El precio es el factor de selección; se revisa la de menor precio.",
        "nota": "Formulación nueva del factor de selección.",
        "regla": "alcance_modalidad",
    },
    {
        "id": "RAG-H-08",
        "tema": "requisitos_habilitantes",
        "pregunta": "¿El RUP es plena prueba para las entidades sometidas al EGCAP?",
        "tipo": "definicion",
        "cobertura_esperada": "suficiente",
        "doc_id": "cce-requisitos-habilitantes-v3-2023",
        "en_corpus": True,
        "relevantes": [
            "cce-requisitos-habilitantes-v3-2023-p009-029-8f2e777a",
            "cce-requisitos-habilitantes-v3-2023-p009-030-6b7a48ca",
            "cce-requisitos-habilitantes-v3-2023-p009-031-e5f06d7a",
        ],
        "justificacion_gold": (
            "Regla general del manual de requisitos. No nombra mínima cuantía, "
            "así que no debe preferirse la excepción de ese manual."
        ),
        "nota": "Control: el alcance no debe forzar mínima cuantía si no se nombra.",
        "regla": "regla_general_sin_modalidad",
    },
]


def comprobar_holdout() -> list[str]:
    choques = comprobar_reservados(PREGUNTAS_HOLDOUT)
    ids = [q["id"] for q in PREGUNTAS_HOLDOUT]
    if any(i.startswith("RAG-D-") for i in ids):
        choques.append("ids_rag_d")
    for rid in IDS_RESERVADOS_EXCEL:
        if any(rid in q["id"] or rid in q["pregunta"] for q in PREGUNTAS_HOLDOUT):
            choques.append(rid)
    return sorted(set(choques))
