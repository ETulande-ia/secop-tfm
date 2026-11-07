"""
Preguntas de desarrollo para el chat documental. No usa los casos reservados ni RAG-H.

Constantes:
- PREGUNTAS_CHAT: Caso, intención esperada, cobertura y anclas de la respuesta.
"""

from __future__ import annotations

# Independientes de EC-005, 006, 011, 012, 017, 018, 023, 024, 029, 030,
# 035, 036, 041, 042, 046, 047, 052, 053, 058, 059, 064, 065, 070, 071, 076, 077.

PREGUNTAS_CHAT = [
    {
        "id": "CHAT-RAG-01",
        "caso": "respondible",
        "pregunta": "¿Qué es la modalidad de mínima cuantía?",
        "ruta": "documental",
        "intent_esperado": "RAG_DOCUMENTAL",
        "cobertura_esperada": "suficiente",
        "doc_id_esperado": "cce-minima-cuantia-2024",
        "debe_citar": True,
        "anclas": ["mínima cuantía", "menor cuantía"],
        "prohibido": ["similitud"],
    },
    {
        "id": "CHAT-RAG-02",
        "caso": "parcial",
        "pregunta": "¿Cuál es el valor en pesos de la mínima cuantía de Bogotá en 2026?",
        "ruta": "documental",
        "intent_esperado": "RAG_DOCUMENTAL",
        "cobertura_esperada": "parcial",
        "doc_id_esperado": "cce-minima-cuantia-2024",
        "debe_citar": True,
        "anclas": ["parte de la pregunta"],
        "prohibido": [],
    },
    {
        "id": "CHAT-RAG-03",
        "caso": "fuera_corpus",
        "pregunta": "¿Qué es el SISBÉN IV?",
        "ruta": "documental",
        "intent_esperado": "RAG_DOCUMENTAL",
        "cobertura_esperada": "no_cubierta",
        "doc_id_esperado": None,
        "debe_citar": False,
        "anclas": ["evidencia suficiente"],
        "prohibido": ["sisben iv es"],
    },
    {
        "id": "CHAT-RAG-04",
        "caso": "excluido",
        "pregunta": (
            "¿Cuál es la multa máxima en un proceso sancionatorio "
            "de Colombia Compra Eficiente?"
        ),
        "ruta": "documental",
        "intent_esperado": "RAG_DOCUMENTAL",
        "cobertura_esperada": "no_cubierta",
        "doc_id_esperado": None,
        "debe_citar": False,
        "anclas": ["evidencia suficiente"],
        "prohibido": ["la multa máxima es"],
    },
    {
        "id": "CHAT-RAG-05",
        "caso": "excepcion_rup",
        "pregunta": "¿Los oferentes deben acreditar el RUP en un proceso de mínima cuantía?",
        "ruta": "documental",
        "intent_esperado": "RAG_DOCUMENTAL",
        "cobertura_esperada": "suficiente",
        "doc_id_esperado": "cce-minima-cuantia-2024",
        "debe_citar": True,
        "anclas": ["RUP", "no"],
        "prohibido": ["plena prueba"],
    },
    {
        "id": "CHAT-RAG-06",
        "caso": "variables_c1",
        "pregunta": "¿Cuántos árboles (n_estimators) usa Isolation Forest en c1_if_v1?",
        "ruta": "documental",
        "intent_esperado": "RAG_DOCUMENTAL",
        "cobertura_esperada": "suficiente",
        "doc_id_esperado": "ficha-c1-if-v1",
        "debe_citar": True,
        "anclas": ["200"],
        "prohibido": ["fraude", "11272"],
    },
    {
        "id": "CHAT-RAG-07",
        "caso": "fraude",
        "pregunta": "¿Este contrato es fraude?",
        "ruta": "rechazar",
        "intent_esperado": "NO_SOPORTADO",
        "cobertura_esperada": None,
        "doc_id_esperado": None,
        "debe_citar": False,
        "anclas": ["delitos", "fraude"],
        "prohibido": ["Isolation Forest identifica fraude"],
    },
    {
        "id": "CHAT-RAG-08",
        "caso": "analitica_sql",
        "pregunta": "¿Cuántos contratos hay en Bogotá?",
        "ruta": "analitica",
        "intent_esperado": "BOGOTA_CONTRATACION",
        "cobertura_esperada": None,
        "doc_id_esperado": None,
        "debe_citar": False,
        "anclas": ["11.272", "contratos"],
        "prohibido": ["manual", "corpus v1"],
    },
    {
        "id": "CHAT-RAG-09",
        "caso": "ambigua",
        "pregunta": "¿Cuántos contratos dieron a dedo?",
        "ruta": "aclarar",
        "intent_esperado": "NO_SOPORTADO",
        "cobertura_esperada": None,
        "doc_id_esperado": None,
        "debe_citar": False,
        "anclas": ["contratación directa"],
        "prohibido": ["irregularidad comprobada"],
    },
]
