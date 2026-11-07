"""
Conjunto ampliado de preguntas de desarrollo. El gold se fija por el texto.

Constantes:
- PREGUNTAS_AMPLIADAS: Preguntas originales más las añadidas.
- METRICAS_12B: Métricas conservadas de la evaluación intermedia.
- METRICAS_12C_B: Métricas conservadas de la estrategia B.

Funciones:
- comprobar_reservados(): Detecta identificadores del Excel reservado.
- resumen_conjunto(): Resume tamaño, temas y cobertura del conjunto.
"""

from __future__ import annotations

from .pruebas import METRICAS_ORIGINALES, PREGUNTAS, mrr, recall_at_k

# IDs reservados del Excel: no aparecen en este conjunto.
IDS_RESERVADOS_EXCEL = frozenset({
    "EC-005", "EC-006", "EC-011", "EC-012", "EC-017", "EC-018",
    "EC-023", "EC-024", "EC-029", "EC-030", "EC-035", "EC-036",
    "EC-041", "EC-042", "EC-046", "EC-047", "EC-052", "EC-053",
    "EC-058", "EC-059", "EC-064", "EC-065", "EC-070", "EC-071",
    "EC-076", "EC-077",
})

METRICAS_12B = {
    "recall_at_5_gold_verificado": 0.7083,
    "recall_gold_verificado_con_adyacentes": 0.9375,
    "mrr_gold_verificado": 0.75,
    "mrr_verificado_con_contexto": 0.7917,
    "n_suficiente": 7,
    "n_parcial": 1,
    "n_no_cubierta": 3,
    "fuera_rechazados_evidencia": 3,
    "n_preguntas": 11,
}

# Notebook 12c, estrategia B, antes del ajuste de evidencia/alcance.
METRICAS_12C_B = {
    "recall_at_5": 0.9655,
    "mrr": 0.7787,
    "aciertos": 29,
    "n_con_gold": 29,
    "aciertos_cobertura": 28,
    "falsos_positivos": 0,
    "falsos_positivos_suaves": 1,
    "falsos_negativos": 3,
    "parcial_pred_ok": 0,
    "fuera_rechazados_evidencia": 7,
    "fuera_n": 8,
    "n_preguntas": 40,
}

_META_ORIG = {
    "RAG-D-01": ("definicion", "suficiente", "cce-minima-cuantia-2024"),
    "RAG-D-02": ("definicion", "suficiente", "cce-minima-cuantia-2024"),
    "RAG-D-03": ("definicion", "suficiente", "cce-requisitos-habilitantes-v3-2023"),
    "RAG-D-04": ("definicion", "suficiente", "cce-requisitos-habilitantes-v3-2023"),
    "RAG-D-05": ("definicion", "suficiente", "diccionario-datos-abiertos-secop"),
    "RAG-D-06": ("repartida", "suficiente", "ficha-c1-if-v1"),
    "RAG-D-07": ("definicion", "suficiente", "ficha-c1-if-v1"),
    "RAG-D-08": ("repartida", "suficiente", "ficha-c1-if-v1"),
    "RAG-D-09": ("fuera", "no_cubierta", None),
    "RAG-D-10": ("fuera", "no_cubierta", None),
    "RAG-D-11": ("fuera", "no_cubierta", None),
}


def _q(
    id_,
    tema,
    pregunta,
    tipo,
    cobertura_esperada,
    doc_id,
    relevantes,
    justificacion,
    nota,
    en_corpus=None,
):
    if en_corpus is None:
        en_corpus = cobertura_esperada != "no_cubierta" or bool(relevantes)
    if cobertura_esperada == "no_cubierta":
        en_corpus = False
    return {
        "id": id_,
        "tema": tema,
        "pregunta": pregunta,
        "tipo": tipo,
        "cobertura_esperada": cobertura_esperada,
        "doc_id": doc_id,
        "en_corpus": en_corpus,
        "relevantes": list(relevantes),
        "justificacion_gold": justificacion,
        "nota": nota,
    }


def _originales() -> list[dict]:
    out = []
    for q in PREGUNTAS:
        tipo, cob, doc = _META_ORIG[q["id"]]
        n = dict(q)
        n["tipo"] = tipo
        n["cobertura_esperada"] = cob
        n["doc_id"] = doc
        n["relevantes"] = list(q["relevantes"])
        out.append(n)
    return out


PREGUNTAS_NUEVAS = [
    _q(
        "RAG-D-12",
        "minima_cuantia",
        "¿En qué consiste el procedimiento de selección de mínima cuantía?",
        "parafraseo",
        "suficiente",
        "cce-minima-cuantia-2024",
        [
            "cce-minima-cuantia-2024-p004-004-601acaff",
            "cce-minima-cuantia-2024-p005-009-9e9f94b4",
        ],
        "Misma evidencia que RAG-D-01: p004-004 (procedimiento de selección, 10 % de la menor cuantía) y p005-009 (convocatoria cuyo valor no excede ese tope; el elemento es la cuantía, no el objeto).",
        "Parafraseo de la definición; no se cambia el gold.",
    ),
    _q(
        "RAG-D-13",
        "minima_cuantia",
        "¿Las entidades estatales están obligadas a exigir garantías en mínima cuantía?",
        "excepcion",
        "suficiente",
        "cce-minima-cuantia-2024",
        ["cce-minima-cuantia-2024-p012-034-d5be6243"],
        "p012-034 afirma que no están obligadas a exigir garantías; si las piden, es por el riesgo del proceso y del sector.",
        "Excepción de formalidad, no la definición de la modalidad.",
    ),
    _q(
        "RAG-D-14",
        "minima_cuantia",
        "¿Los oferentes deben acreditar el RUP en un proceso de mínima cuantía?",
        "repartida",
        "suficiente",
        "cce-minima-cuantia-2024",
        [
            "cce-minima-cuantia-2024-p010-027-e5bf81f3",
            "cce-minima-cuantia-2024-p012-035-8d0c5423",
        ],
        "p010-027: los oferentes no están obligados a acreditar inscripción en el RUP. p012-035: no es obligatorio el RUP y la entidad verifica capacidad jurídica, experiencia y financiera. Orden 27 y 35 no son vecinos. El RUP del manual de requisitos habilitantes describe la regla general, no esta excepción.",
        "Respuesta repartida en dos fragmentos no adyacentes del mismo PDF.",
    ),
    _q(
        "RAG-D-15",
        "minima_cuantia",
        "¿Cuál es el factor de selección de la oferta en mínima cuantía?",
        "definicion",
        "suficiente",
        "cce-minima-cuantia-2024",
        [
            "cce-minima-cuantia-2024-p010-024-2fe4e22b",
            "cce-minima-cuantia-2024-p010-025-1019b858",
            "cce-minima-cuantia-2024-p010-026-8405dec0",
        ],
        "7.1: el precio es el factor de selección. p010-025 precisa menor valor de la oferta económica. p010-026 describe la revisión sucesiva de la oferta de menor precio.",
        "Tres fragmentos consecutivos del mismo apartado.",
    ),
    _q(
        "RAG-D-16",
        "minima_cuantia",
        "¿Qué modalidad aplica si concurren mínima cuantía y contratación directa?",
        "repartida",
        "suficiente",
        "cce-minima-cuantia-2024",
        [
            "cce-minima-cuantia-2024-p015-048-c9b0b239",
            "cce-minima-cuantia-2024-p016-049-accf536d",
        ],
        "p015-048 define cuándo concurren. p016-049 concluye que aplica contratación directa por el principio de economía. Son vecinos (orden 48 y 49).",
        "La respuesta completa está partida entre dos páginas.",
    ),
    _q(
        "RAG-D-17",
        "minima_cuantia",
        "¿Durante cuánto tiempo debe publicarse el informe de evaluación en mínima cuantía?",
        "cifra",
        "suficiente",
        "cce-minima-cuantia-2024",
        ["cce-minima-cuantia-2024-p009-021-a444b73e"],
        "p009-021: mínimo un día hábil para observaciones antes de aceptar la oferta.",
        "Plazo concreto del manual.",
    ),
    _q(
        "RAG-D-18",
        "minima_cuantia",
        "¿Cuál es el valor en pesos de la mínima cuantía de Bogotá en 2026?",
        "parcial",
        "parcial",
        "cce-minima-cuantia-2024",
        [],
        "El manual trae una tabla de SMLMV (p006-011) y el 10 % de la menor cuantía, pero no el presupuesto de Bogotá ni un valor en pesos de 2026. Hay tema relacionado y no la cifra pedida.",
        "Parcial: hay umbral genérico, no la cifra local.",
        en_corpus=True,
    ),
    _q(
        "RAG-D-19",
        "c1_isolation_forest",
        "¿La matriz C1 incluye el plazo de ejecución o el conteo de contratos por entidad?",
        "definicion",
        "suficiente",
        "ficha-c1-if-v1",
        ["ficha-c1-if-v1-p001-004-e68cbf43"],
        "Solo «Matriz C1» niega plazo y n_entidad. «Por qué C1 y no C3» habla de plazo_invalido en C2/C3, no lista la matriz publicada.",
        "Otra formulación de las variables de C1 (RAG-D-06).",
    ),
    _q(
        "RAG-D-20",
        "c1_isolation_forest",
        "¿Cuántos árboles (n_estimators) usa Isolation Forest en c1_if_v1?",
        "cifra",
        "suficiente",
        "ficha-c1-if-v1",
        ["ficha-c1-if-v1-p001-005-eb9b4376"],
        "La tabla del algoritmo publicado fija n_estimators = 200. Ningún otro fragmento da ese número.",
        "Hiperparámetro de la ficha, no de los manuales CCE.",
    ),
    _q(
        "RAG-D-21",
        "c1_isolation_forest",
        "¿Por qué se publicó C1 y no C3?",
        "definicion",
        "suficiente",
        "ficha-c1-if-v1",
        ["ficha-c1-if-v1-p001-007-c29ae57d"],
        "«Por qué C1 y no C3»: C2/C3 concentraban el top 1 % en plazo_invalido (51,4 %). C1 no premia ese artefacto. LOF no se publica.",
        "No se marca Matriz C1: no explica la elección de versión.",
    ),
    _q(
        "RAG-D-22",
        "c1_isolation_forest",
        "¿Qué contrato quedó con rank_if igual a 1 en c1_if_v1?",
        "cifra",
        "suficiente",
        "ficha-c1-if-v1",
        ["ficha-c1-if-v1-p001-008-2a27f6af"],
        "Cifras de la publicación: CO1.PCCNTR.9673418, régimen especial, valor 79.008.765.934, score_if 0,098194.",
        "Identificador concreto; no está en Universo.",
    ),
    _q(
        "RAG-D-23",
        "c1_isolation_forest",
        "¿DANE entra al ajuste de Isolation Forest en c1_if_v1?",
        "definicion",
        "suficiente",
        "ficha-c1-if-v1",
        ["ficha-c1-if-v1-p001-009-e6b29bc0"],
        "Limitaciones: «DANE no entra al ajuste». Eso responde esta pregunta. No hay población municipal; esa otra pregunta es RAG-D-11.",
        "Misma ficha que RAG-D-11, pregunta distinta.",
    ),
    _q(
        "RAG-D-24",
        "c1_isolation_forest",
        "¿El modelo c1_if_v1 tiene precisión o AUC de fraude?",
        "definicion",
        "suficiente",
        "ficha-c1-if-v1",
        ["ficha-c1-if-v1-p001-009-e6b29bc0"],
        "Limitaciones: un mes, un modelo, sin etiquetas de fraude: no hay precisión ni AUC.",
        "La ausencia de métrica está documentada; no es información insuficiente.",
    ),
    _q(
        "RAG-D-25",
        "c1_isolation_forest",
        "¿Cuántos contratos de Bogotá se puntuaron en c1_if_v1?",
        "parcial",
        "parcial",
        "ficha-c1-if-v1",
        [],
        "Universo y Cifras dan 82.457 aptos del periodo nacional 2026-09, no el recorte de Bogotá. Hay cifra relacionada y no la pedida.",
        "Parcial: el n nacional no responde el n distrital.",
        en_corpus=True,
    ),
    _q(
        "RAG-D-26",
        "c1_isolation_forest",
        "¿Cuántos contratos se excluyeron de c1_if_v1 y por qué?",
        "repartida",
        "suficiente",
        "ficha-c1-if-v1",
        ["ficha-c1-if-v1-p001-003-d79b01ae"],
        "Universo: 506 valor_cero y 1 valor_extremo (INDER Medellín); 507 en ml_contrato_excluido. Cifras repite 507 sin el desglose; no se añade como gold.",
        "El porqué solo está en Universo.",
    ),
    _q(
        "RAG-D-27",
        "diccionario_secop",
        "¿Qué significa el campo Ciudad Entidad en el diccionario de datos abiertos de SECOP II?",
        "definicion",
        "suficiente",
        "diccionario-datos-abiertos-secop",
        ["diccionario-datos-abiertos-secop-p001-002-9839836f"],
        "Campo 4: Municipio en el que está registrada la entidad. Mismo fragmento que Nit Entidad (RAG-D-05).",
        "Consulta de campo, formulación distinta de RAG-D-05.",
    ),
    _q(
        "RAG-D-28",
        "diccionario_secop",
        "¿Qué indica el campo Adjudicado en el diccionario de datos abiertos de SECOP II?",
        "definicion",
        "suficiente",
        "diccionario-datos-abiertos-secop",
        ["diccionario-datos-abiertos-secop-p003-009-dbae246d"],
        "Campo 42: indica si el proceso ha sido ya adjudicado. Solo está en la página 3.",
        "Campo de estado, no de entidad.",
    ),
    _q(
        "RAG-D-29",
        "diccionario_secop",
        "¿Cuál es la URL del conjunto de datos SECOP II Procesos de Contratación?",
        "cifra",
        "suficiente",
        "diccionario-datos-abiertos-secop",
        ["diccionario-datos-abiertos-secop-p001-001-40e28679"],
        "Cabecera del diccionario: datos.gov.co .../p6dx-8zbt. Ningún otro fragmento trae esa URL.",
        "Identificador del dataset de procesos, no de contratos.",
    ),
    _q(
        "RAG-D-30",
        "diccionario_secop",
        "¿Qué significa el campo valor del contrato en el diccionario de SECOP II Procesos?",
        "parcial",
        "parcial",
        "diccionario-datos-abiertos-secop",
        [],
        "El diccionario describe Precio Base y Valor Total Adjudicacion, no un campo «valor del contrato» de SECOP II Contratos. Hay campos monetarios próximos y no la definición pedida.",
        "Parcial: vocabulario cercano, campo inexistente.",
        en_corpus=True,
    ),
    _q(
        "RAG-D-31",
        "requisitos_habilitantes",
        "¿Los requisitos habilitantes se califican con puntaje?",
        "parafraseo",
        "suficiente",
        "cce-requisitos-habilitantes-v3-2023",
        [
            "cce-requisitos-habilitantes-v3-2023-p005-013-02ffd2a2",
            "cce-requisitos-habilitantes-v3-2023-p005-014-c8f76b14",
        ],
        "p005-013 los diferencia de los criterios de evaluación/puntaje. p005-014 cierra que no se valoran con puntaje. No se añade p005-012 (título).",
        "Parafraseo de RAG-D-03 centrado en el puntaje.",
    ),
    _q(
        "RAG-D-32",
        "requisitos_habilitantes",
        "¿Cómo deben establecer las entidades los requisitos habilitantes?",
        "definicion",
        "suficiente",
        "cce-requisitos-habilitantes-v3-2023",
        ["cce-requisitos-habilitantes-v3-2023-p006-016-4e63af65"],
        "p006-016: adecuados y proporcionales a la naturaleza y valor del contrato; relación directa con el objeto, sin limitar la libre concurrencia.",
        "Apartado 1.2, no la definición del 1.1.",
    ),
    _q(
        "RAG-D-33",
        "requisitos_habilitantes",
        "¿Qué es la capacidad financiera como requisito habilitante?",
        "definicion",
        "suficiente",
        "cce-requisitos-habilitantes-v3-2023",
        ["cce-requisitos-habilitantes-v3-2023-p021-084-5638e912"],
        "p021-084: condiciones mínimas de salud financiera (liquidez, endeudamiento, cobertura de intereses), adecuadas y proporcionales al contrato.",
        "Capítulo 4 del manual. No se usa el RUP como gold.",
    ),
    _q(
        "RAG-D-34",
        "requisitos_habilitantes",
        "¿Qué es la capacidad organizacional de un proponente?",
        "definicion",
        "suficiente",
        "cce-requisitos-habilitantes-v3-2023",
        ["cce-requisitos-habilitantes-v3-2023-p025-101-06227d93"],
        "p025-101: aptitud para cumplir el contrato en función de la organización interna; indicadores de rentabilidad del Decreto 1082 de 2015.",
        "Capítulo 5. No se mezclan indicadores financieros del capítulo 4.",
    ),
    _q(
        "RAG-D-35",
        "requisitos_habilitantes",
        "¿Qué se entiende por experiencia del proponente en requisitos habilitantes?",
        "definicion",
        "suficiente",
        "cce-requisitos-habilitantes-v3-2023",
        ["cce-requisitos-habilitantes-v3-2023-p015-056-acf72659"],
        "p015-056: conocimiento derivado de participación previa en actividades iguales o similares; incluye proponentes plurales.",
        "Apartado de experiencia, no de capacidad jurídica.",
    ),
    _q(
        "RAG-D-36",
        "fuera_de_corpus",
        "¿Cuál es la multa máxima en un proceso sancionatorio de Colombia Compra Eficiente?",
        "fuera",
        "no_cubierta",
        None,
        [],
        "La guía sancionatoria está excluida del corpus v1. No hay cuantía de multa en los 254 fragmentos.",
        "OOD con vocabulario institucional (CCE, proceso).",
    ),
    _q(
        "RAG-D-37",
        "fuera_de_corpus",
        "¿Qué dice la Ley 80 de 1993 sobre el fraude en la contratación pública?",
        "fuera",
        "no_cubierta",
        None,
        [],
        "La ficha niega que el score sea fraude; no reproduce la Ley 80 sobre fraude. Términos próximos no equivalen a la norma pedida.",
        "Trampa: «fraude» aparece en la ficha C1.",
    ),
    _q(
        "RAG-D-38",
        "fuera_de_corpus",
        "¿Cuál es la población DANE de Medellín en 2026?",
        "fuera",
        "no_cubierta",
        None,
        [],
        "INDER Medellín aparece como exclusión por valor extremo; DANE «no entra al ajuste». No hay población municipal.",
        "Trampa: Medellín y DANE sí ocurren, no la serie demográfica.",
    ),
    _q(
        "RAG-D-39",
        "fuera_de_corpus",
        "¿Cómo se calcula el SISBÉN IV para las entidades contratantes?",
        "fuera",
        "no_cubierta",
        None,
        [],
        "SISBÉN no aparece en el corpus. Fuera del alcance del TFM.",
        "OOD léxico, variante de RAG-D-10.",
    ),
    _q(
        "RAG-D-40",
        "fuera_de_corpus",
        "¿Qué requisitos habilitantes exige la plataforma SECOP III?",
        "fuera",
        "no_cubierta",
        None,
        [],
        "El corpus cubre SECOP II y el manual de requisitos de 2023, no SECOP III. Responder con el manual vigente sería una alucinación de alcance.",
        "Trampa: requisitos habilitantes sí están; SECOP III no.",
    ),
]


PREGUNTAS_AMPLIADAS = _originales() + PREGUNTAS_NUEVAS


def comprobar_reservados(preguntas: list[dict] | None = None) -> list[str]:
    qs = preguntas if preguntas is not None else PREGUNTAS_AMPLIADAS
    choques = []
    for q in qs:
        if q["id"] in IDS_RESERVADOS_EXCEL:
            choques.append(q["id"])
        texto = (q["id"] + " " + q["pregunta"]).upper()
        for rid in IDS_RESERVADOS_EXCEL:
            if rid in texto:
                choques.append(q["id"])
    return sorted(set(choques))


def resumen_conjunto(preguntas: list[dict] | None = None) -> dict:
    qs = preguntas if preguntas is not None else PREGUNTAS_AMPLIADAS
    cob = {}
    tipo = {}
    tema = {}
    n_gold = 0
    for q in qs:
        cob[q["cobertura_esperada"]] = cob.get(q["cobertura_esperada"], 0) + 1
        tipo[q["tipo"]] = tipo.get(q["tipo"], 0) + 1
        tema[q["tema"]] = tema.get(q["tema"], 0) + 1
        if q["relevantes"]:
            n_gold += 1
    return {
        "n_preguntas": len(qs),
        "n_con_gold": n_gold,
        "n_sin_gold": len(qs) - n_gold,
        "cobertura_esperada": cob,
        "tipo": tipo,
        "tema": tema,
        "choques_reservados": comprobar_reservados(qs),
        "incluye_rag_d_01_11": [q["id"] for q in qs[:11]],
    }


__all__ = [
    "PREGUNTAS_AMPLIADAS",
    "METRICAS_ORIGINALES",
    "METRICAS_12B",
    "IDS_RESERVADOS_EXCEL",
    "comprobar_reservados",
    "resumen_conjunto",
    "mrr",
    "recall_at_k",
]
