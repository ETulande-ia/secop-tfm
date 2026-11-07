"""
Preguntas de desarrollo para medir la recuperación. No usa los 26 casos reservados.

Constantes:
- PREGUNTAS: Pregunta, tema y fragmentos relevantes.
- METRICAS_ORIGINALES: Recall y MRR de referencia.

Funciones:
- mrr(): Calcula el recíproco medio del rango.
- recall_at_k(): Calcula el recall en los primeros k resultados.
"""

from __future__ import annotations

# IDs RAG-D-* independientes de EC-005, 006, 011, 012, 017, 018, 023, 024,
# 029, 030, 035, 036, 041, 042, 046, 047, 052, 053, 058, 059, 064, 065,
# 070, 071, 076 y 077 del Excel de expresiones ciudadanas.

# Métricas de la corrida original del notebook 12 (no se sustituyen).
METRICAS_ORIGINALES = {
    "recall_at_k_medio": 0.625,
    "mrr": 0.4,
    "aciertos_con_referencia": 5,
    "n_con_referencia": 8,
    "fuera_marcados_insuficiente": 0,
    "n_fuera_de_corpus": 3,
    "top_k": 5,
    "umbral": 0.3,
}

PREGUNTAS = [
    {
        "id": "RAG-D-01",
        "tema": "minima_cuantia",
        "pregunta": "¿Qué es la modalidad de mínima cuantía?",
        "en_corpus": True,
        "relevantes_originales": ["cce-minima-cuantia-2024-p004-004-601acaff"],
        "relevantes": [
            "cce-minima-cuantia-2024-p004-004-601acaff",
            "cce-minima-cuantia-2024-p005-009-9e9f94b4",
        ],
        "justificacion_gold": (
            "Se añade p005-009 porque el manual formula ahí una segunda definición "
            "completa (convocatoria pública cuyo valor no excede el 10 % de la menor "
            "cuantía; el elemento central es la cuantía, no el objeto). p004-004 ya "
            "definía el procedimiento de selección con el mismo tope. No se añade "
            "p005-010: ese fragmento explica cómo se determina el valor y cita el "
            "presupuesto anual, que es otra pregunta (RAG-D-02)."
        ),
        "nota": "Dos definiciones independientes en el manual; no un único fragmento.",
    },
    {
        "id": "RAG-D-02",
        "tema": "minima_cuantia",
        "pregunta": "¿Cómo se determina el valor de la mínima cuantía?",
        "en_corpus": True,
        "relevantes_originales": ["cce-minima-cuantia-2024-p005-010-612d9d78"],
        "relevantes": ["cce-minima-cuantia-2024-p005-010-612d9d78"],
        "justificacion_gold": (
            "Se conserva solo p005-010: es el apartado «¿Cómo se determina el valor "
            "de la Mínima Cuantía?» y precisa que equivale al 10 % o menos de la "
            "menor cuantía, determinada en función del presupuesto anual, con remisión "
            "a la Ley 1150 de 2007. p004-004 y p005-009 mencionan el 10 % como "
            "definición de la modalidad, no el procedimiento de determinación. No se "
            "amplía el gold para no confundir definición y cálculo."
        ),
        "nota": "El manual responde: 10 % o menos de la menor cuantía según presupuesto anual.",
    },
    {
        "id": "RAG-D-03",
        "tema": "requisitos_habilitantes",
        "pregunta": "¿Qué son los requisitos habilitantes y para qué sirven?",
        "en_corpus": True,
        "relevantes_originales": [
            "cce-requisitos-habilitantes-v3-2023-p005-011-e72dfb74",
            "cce-requisitos-habilitantes-v3-2023-p005-013-02ffd2a2",
        ],
        "relevantes": [
            "cce-requisitos-habilitantes-v3-2023-p005-011-e72dfb74",
            "cce-requisitos-habilitantes-v3-2023-p005-013-02ffd2a2",
            "cce-requisitos-habilitantes-v3-2023-p005-014-c8f76b14",
        ],
        "justificacion_gold": (
            "Se añade p005-014 porque continúa la misma frase de p005-013: los "
            "requisitos «no se valoran con un puntaje» sino como criterios previos. "
            "Eso completa «para qué sirven» frente a los criterios de evaluación. "
            "No se añade p005-012: solo arrastra el título 1.1 y texto introductorio, "
            "sin definir. El TOC (p002-002) está excluido del índice y no define."
        ),
        "nota": "Condiciones mínimas de participación; no son puntaje de evaluación.",
    },
    {
        "id": "RAG-D-04",
        "tema": "requisitos_habilitantes",
        "pregunta": "¿Qué es el Registro Único de Proponentes (RUP)?",
        "en_corpus": True,
        "relevantes_originales": ["cce-requisitos-habilitantes-v3-2023-p009-029-8f2e777a"],
        "relevantes": [
            "cce-requisitos-habilitantes-v3-2023-p009-029-8f2e777a",
            "cce-requisitos-habilitantes-v3-2023-p009-030-6b7a48ca",
            "cce-requisitos-habilitantes-v3-2023-p009-031-e5f06d7a",
        ],
        "justificacion_gold": (
            "p009-029 identifica el RUP como certificado de plena prueba (Ley 1150, "
            "art. 6.1). p009-030 es el corte de esa misma frase. p009-031 precisa que "
            "capacidad jurídica, experiencia, financiera y organizacional se verifican "
            "exclusivamente por ese documento, que es plena prueba. No se añade el "
            "fragmento de mínima cuantía p010-027: ahí se dice que en esa modalidad "
            "no hay que acreditar RUP, que es una excepción de uso, no una definición."
        ),
        "nota": "Certificado de plena prueba; las entidades del EGCAP verifican por ese medio.",
    },
    {
        "id": "RAG-D-05",
        "tema": "diccionario_secop",
        "pregunta": "¿Qué significa el campo Nit Entidad en el diccionario de datos abiertos de SECOP II?",
        "en_corpus": True,
        "relevantes_originales": ["diccionario-datos-abiertos-secop-p001-002-9839836f"],
        "relevantes": ["diccionario-datos-abiertos-secop-p001-002-9839836f"],
        "justificacion_gold": (
            "Único fragmento que lista el campo 2 «Nit Entidad / NIT de la Entidad». "
            "No hay otra evidencia equivalente en el corpus."
        ),
        "nota": "Campo 2: NIT de la Entidad.",
    },
    {
        "id": "RAG-D-06",
        "tema": "c1_isolation_forest",
        "pregunta": "¿Qué variables usa la matriz C1 de Isolation Forest?",
        "en_corpus": True,
        "relevantes_originales": ["ficha-c1-if-v1-p001-004-e68cbf43"],
        "relevantes": ["ficha-c1-if-v1-p001-004-e68cbf43"],
        "justificacion_gold": (
            "Solo «Matriz C1» enumera log1p_valor, log_valor_vs_modalidad y dummies, "
            "y niega plazo y n_entidad. «Qué mide el modelo» habla de C1 e Isolation "
            "Forest pero no lista variables. «Por qué C1 y no C3» explica sensibilidad "
            "al plazo, no la matriz. No se marcan como gold por haber salido en el "
            "ranking: no responden la pregunta."
        ),
        "nota": "log1p_valor, log_valor_vs_modalidad y dummies de modalidad_grupo.",
    },
    {
        "id": "RAG-D-07",
        "tema": "c1_isolation_forest",
        "pregunta": "¿Una puntuación alta de Isolation Forest es una irregularidad o un fraude?",
        "en_corpus": True,
        "relevantes_originales": ["ficha-c1-if-v1-p001-002-63fbcd8d"],
        "relevantes": ["ficha-c1-if-v1-p001-002-63fbcd8d"],
        "justificacion_gold": (
            "Único fragmento que afirma: puntuación alta no es irregularidad comprobada "
            "ni probabilidad de fraude. «Limitaciones» dice que no hay etiquetas de "
            "fraude ni AUC; no responde si el score es una irregularidad."
        ),
        "nota": "No: atípico estadístico; no demuestra ilegalidad.",
    },
    {
        "id": "RAG-D-08",
        "tema": "c1_isolation_forest",
        "pregunta": "¿Cuántos contratos aptos se puntuaron en c1_if_v1?",
        "en_corpus": True,
        "relevantes_originales": ["ficha-c1-if-v1-p001-003-d79b01ae"],
        "relevantes": [
            "ficha-c1-if-v1-p001-003-d79b01ae",
            "ficha-c1-if-v1-p001-008-2a27f6af",
        ],
        "justificacion_gold": (
            "«Universo» da 82.457 aptos con score y 507 excluidos. «Cifras de la "
            "publicación» repite 82.457 en ml_contrato_score y 507 excluidos. Ambos "
            "responden el conteo. No se añade «Limitaciones»: no informa n aptos."
        ),
        "nota": "82.457 aptos; 507 excluidos. La cifra está en Universo y en Cifras.",
    },
    {
        "id": "RAG-D-09",
        "tema": "fuera_de_corpus",
        "pregunta": "¿Cuál es el procedimiento sancionatorio de Colombia Compra Eficiente?",
        "en_corpus": False,
        "relevantes_originales": [],
        "relevantes": [],
        "justificacion_gold": (
            "La guía sancionatoria se excluyó del corpus v1. «sancionatorio» no aparece "
            "en los 254 fragmentos. Sin gold."
        ),
        "nota": "La guía sancionatoria se excluyó del corpus v1.",
    },
    {
        "id": "RAG-D-10",
        "tema": "fuera_de_corpus",
        "pregunta": "¿Qué dice el SISBÉN sobre la contratación pública?",
        "en_corpus": False,
        "relevantes_originales": [],
        "relevantes": [],
        "justificacion_gold": (
            "SISBÉN no aparece en el corpus. Fuera de alcance del TFM. Sin gold."
        ),
        "nota": "SISBÉN está fuera del alcance del TFM y del corpus.",
    },
    {
        "id": "RAG-D-11",
        "tema": "fuera_de_corpus",
        "pregunta": "¿Cuál es la población DANE de cada municipio en 2026?",
        "en_corpus": False,
        "relevantes_originales": [],
        "relevantes": [],
        "justificacion_gold": (
            "El corpus solo dice «DANE no entra al ajuste» en limitaciones de C1. "
            "No hay población municipal ni serie 2026. Sin gold."
        ),
        "nota": "El corpus documental no incluye DANE de población municipal.",
    },
]


def mrr(ranks: list[int | None]) -> float | None:
    if not ranks:
        return None
    vals = [1.0 / r for r in ranks if r]
    return round(sum(vals) / len(ranks), 4)


def recall_at_k(recuperados: list[str], relevantes: list[str], k: int) -> float | None:
    if not relevantes:
        return None
    top = set(recuperados[:k])
    aciertos = sum(1 for r in relevantes if r in top)
    return round(aciertos / len(relevantes), 4)
