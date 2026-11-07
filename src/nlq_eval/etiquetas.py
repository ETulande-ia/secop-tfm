"""
Etiquetas de referencia de las 51 expresiones de desarrollo, alineadas al NLQ.

Constantes:
- ETIQUETAS: Intención, filtros, comportamiento y capacidad esperados.

Funciones:
- por_id(): Devuelve las etiquetas indexadas por identificador.
- comprobar_etiquetas(): Detecta faltantes, sobrantes o uso de identificadores reservados.
"""

from __future__ import annotations


def _e(
    id_,
    intencion,
    aceptados,
    operacion,
    metrica,
    filtros,
    comportamiento,
    capacidad,
    familia,
    justificacion,
):
    return {
        "id": id_,
        "intencion_esperada": intencion,
        "intents_aceptados": list(aceptados),
        "operacion_esperada": operacion,
        "metrica_esperada": metrica,
        "filtros_esperados": filtros,
        "comportamiento_esperado": comportamiento,
        "capacidad": capacidad,
        "familia": familia,
        "justificacion": justificacion,
    }


# Las etiquetas del Excel no se copian: se contrastan en el notebook.
ETIQUETAS = [
    _e(
        "EC-001", "BOGOTA_CONTRATACION", ["BOGOTA_CONTRATACION", "NLQ"],
        "contar", "n_contratos", {"territorio": "bogota", "periodo": "2026-09"},
        "ejecutar", "soportada", "analitica",
        "Cuántos + Bogotá + septiembre. NLQ cuenta con es_bogota en 2026-09.",
    ),
    _e(
        "EC-002", "NO_SOPORTADO", ["NO_SOPORTADO"],
        None, None, {},
        "aclarar", "requiere_aclaracion", "ambigua",
        "«El mes pasado» no es un periodo del prototipo. No debe usarse 2026-09 en silencio.",
    ),
    _e(
        "EC-003", "NLQ", ["NLQ"],
        "contar", "n_contratos", {"periodo": "2026-09"},
        "ejecutar", "soportada", "analitica",
        "Septiembre sí; no nombra ciudad. No se inventa filtro de Bogotá. «Firmaron» se trata como registrados.",
    ),
    _e(
        "EC-004", "BOGOTA_CONTRATACION", ["BOGOTA_CONTRATACION", "NLQ"],
        "contar", "n_contratos", {"territorio": "bogota"},
        "ejecutar", "soportada", "analitica",
        "Número de contratos de Bogotá. Territorio basta para contar.",
    ),
    _e(
        "EC-007", "NLQ", ["NLQ", "BOGOTA_CONTRATACION"],
        "contar", "valor", {"territorio": "bogota"},
        "ejecutar", "soportada", "coloquial",
        "«Plata» debería mapear a valor contratado en Bogotá. Hoy el NLQ no tiene esa palabra.",
    ),
    _e(
        "EC-008", "NLQ", ["NLQ"],
        "contar", "valor", {"periodo": "2026-09"},
        "ejecutar", "parcial", "analitica",
        "«Gastó» activa valor; no hay gasto ejecutado distinto del valor contratado. Sin ciudad: recuento nacional.",
    ),
    _e(
        "EC-009", "NLQ", ["NLQ"],
        "contar", "valor", {"periodo": "2026-09"},
        "ejecutar", "soportada", "analitica",
        "Valor total contratado del periodo publicado, sin filtros. Hace falta reconocer la operación contar.",
    ),
    _e(
        "EC-010", "NO_SOPORTADO", ["NO_SOPORTADO"],
        None, None, {},
        "aclarar", "requiere_aclaracion", "seguimiento",
        "«Esa entidad» sin turno previo. El NLQ pide el nombre; no debe inventar una entidad.",
    ),
    _e(
        "EC-013", "NLQ", ["NLQ"],
        "contar", "n_contratos", {"modalidad": "contratacion directa"},
        "ejecutar", "soportada", "analitica",
        "Conteo con pista de contratación directa, sin ofertas.",
    ),
    _e(
        "EC-014", "NLQ", ["NLQ", "MODALIDADES"],
        "contar", "n_contratos", {"modalidad": "minima cuantia"},
        "ejecutar", "parcial", "analitica",
        "Pide un porcentaje de una modalidad. Lo soportado es contar esa modalidad o devolver la distribución con pct.",
    ),
    _e(
        "EC-015", "NO_SOPORTADO", ["NO_SOPORTADO"],
        None, None, {"modalidad": "licitacion publica"},
        "aclarar", "no_soportada", "analitica",
        "«Cuáles se hicieron» pide listado de contratos. El prototipo no lista contratos por modalidad.",
    ),
    _e(
        "EC-016", "MODALIDADES", ["MODALIDADES", "NLQ"],
        "distribucion", None, {"periodo": "2026-09"},
        "ejecutar", "soportada", "analitica",
        "Distribución nacional por modalidad_de_contratacion.",
    ),
    _e(
        "EC-019", "NO_SOPORTADO", ["NO_SOPORTADO"],
        None, None, {},
        "aclarar", "requiere_aclaracion", "coloquial",
        "«A dedo» no debe convertirse sola en contratación directa ni en irregularidad.",
    ),
    _e(
        "EC-020", "NO_SOPORTADO", ["NO_SOPORTADO"],
        None, None, {},
        "aclarar", "requiere_aclaracion", "coloquial",
        "«Sin concurso» es ambiguo (directa, mínima, régimen especial). Hay que aclarar.",
    ),
    _e(
        "EC-021", "NO_SOPORTADO", ["NO_SOPORTADO"],
        None, None, {},
        "aclarar", "requiere_aclaracion", "coloquial",
        "«Pequeños» no es un umbral ni equivale a mínima cuantía.",
    ),
    _e(
        "EC-022", "NO_SOPORTADO", ["NO_SOPORTADO"],
        None, None, {},
        "aclarar", "requiere_aclaracion", "coloquial",
        "«Grandes» no es un umbral de valor. No listar el top 1 % IF como si fueran contratos grandes.",
    ),
    _e(
        "EC-025", "TOP_ENTIDADES", ["TOP_ENTIDADES", "NLQ"],
        "ranking", "valor", {},
        "ejecutar", "parcial", "analitica",
        "Ranking de entidades. La métrica no está dicha; el prototipo usa valor si no dice «más contratos».",
    ),
    _e(
        "EC-026", "NLQ", ["NLQ"],
        "ranking", "n_contratos", {"territorio": "bogota"},
        "ejecutar", "soportada", "analitica",
        "Quién hizo más contratos en Bogotá: ranking por n, filtro es_bogota. «Quién» debe leerse como entidad.",
    ),
    _e(
        "EC-027", "TOP_ENTIDADES", ["TOP_ENTIDADES", "NLQ"],
        "ranking", "valor", {},
        "ejecutar", "soportada", "coloquial",
        "Entidad + gastó + más: ranking por valor. «Plata» es coloquial del valor contratado.",
    ),
    _e(
        "EC-028", "NO_SOPORTADO", ["NO_SOPORTADO"],
        None, None, {"entidad": "integracion social"},
        "aclarar", "no_soportada", "analitica",
        "Pide los contratos de Integración Social, no el conteo. No hay listado por entidad.",
    ),
    _e(
        "EC-031", "NO_SOPORTADO", ["NO_SOPORTADO"],
        None, None, {},
        "aclarar", "requiere_aclaracion", "seguimiento",
        "«Ese contrato» sin identificador CO1. No hay contexto previo en esta línea base.",
    ),
    _e(
        "EC-032", "TOP_PROVIDERS", ["TOP_PROVIDERS"],
        None, None, {},
        "ejecutar", "soportada", "especial",
        "Quién recibió más contratos: intención cerrada de proveedores. No es ranking de entidades.",
    ),
    _e(
        "EC-033", "NO_SOPORTADO", ["NO_SOPORTADO"],
        None, None, {},
        "aclarar", "no_soportada", "seguimiento",
        "Proveedores de «esa entidad»: no hay contexto y TOP_PROVIDERS no admite filtro de entidad.",
    ),
    _e(
        "EC-034", "NO_SOPORTADO", ["NO_SOPORTADO"],
        None, None, {},
        "aclarar", "requiere_aclaracion", "seguimiento",
        "Proveedor de «ese contrato» sin CO1. EXPLAIN_CONTRACT exige el identificador.",
    ),
    _e(
        "EC-037", "TOP1_IF", ["TOP1_IF"],
        None, None, {},
        "ejecutar", "soportada", "coloquial",
        "«Raros» como atípicos del top 1 % Isolation Forest. No es corrupción.",
    ),
    _e(
        "EC-038", "TOP1_IF", ["TOP1_IF"],
        None, None, {},
        "ejecutar", "soportada", "coloquial",
        "«Se salen de lo normal» apunta a la lista IF, no a un juicio de ilegalidad.",
    ),
    _e(
        "EC-039", "NO_SOPORTADO", ["NO_SOPORTADO"],
        None, None, {"territorio": "bogota"},
        "rechazar", "no_soportada", "especial",
        "TOP1_IF no admite filtro de ciudad. Debe rechazar, no devolver el top nacional.",
    ),
    _e(
        "EC-040", "TOP1_IF", ["TOP1_IF"],
        None, None, {},
        "ejecutar", "soportada", "especial",
        "«Cuáles» + puntuación: lista de atípicos, no la plantilla PORQUE_ATIPICO.",
    ),
    _e(
        "EC-043", "NO_SOPORTADO", ["NO_SOPORTADO"],
        None, None, {},
        "rechazar", "no_soportada", "sensible",
        "Corrupción no es una consulta del prototipo. No listar Isolation Forest como contratos corruptos.",
    ),
    _e(
        "EC-044", "NO_SOPORTADO", ["NO_SOPORTADO"],
        None, None, {},
        "rechazar", "no_soportada", "sensible",
        "Robo no se infiere. Debe rechazar sin afirmar delito.",
    ),
    _e(
        "EC-045", "NO_SOPORTADO", ["NO_SOPORTADO"],
        None, None, {},
        "rechazar", "no_soportada", "sensible",
        "Fraude no está en el modelo. No explicar un contrato atípico como si fuera fraude.",
    ),
    _e(
        "EC-048", "NO_SOPORTADO", ["NO_SOPORTADO"],
        None, None, {},
        "rechazar", "no_soportada", "conceptual",
        "Definición de contratación directa. RAG no está en POST /api/chat. No responder con el recuento SQL.",
    ),
    _e(
        "EC-049", "NO_SOPORTADO", ["NO_SOPORTADO"],
        None, None, {},
        "rechazar", "no_soportada", "conceptual",
        "Definición de mínima cuantía. El chat no sirve el recuperador documental.",
    ),
    _e(
        "EC-050", "NO_SOPORTADO", ["NO_SOPORTADO"],
        None, None, {},
        "rechazar", "no_soportada", "conceptual",
        "Requisitos para contratar con el Estado: documentación, no SQL.",
    ),
    _e(
        "EC-051", "NO_SOPORTADO", ["NO_SOPORTADO"],
        None, None, {},
        "rechazar", "no_soportada", "conceptual",
        "Qué es el RUP: concepto documental, no consulta analítica.",
    ),
    _e(
        "EC-054", "PORQUE_ATIPICO", ["PORQUE_ATIPICO"],
        None, None, {},
        "ejecutar", "soportada", "especial",
        "Qué significa que el modelo marque un contrato: plantilla C1 + Isolation Forest.",
    ),
    _e(
        "EC-055", "PORQUE_ATIPICO", ["PORQUE_ATIPICO"],
        None, None, {},
        "ejecutar", "parcial", "especial",
        "«Qué es Isolation Forest» puede caer en PORQUE_ATIPICO. Eso explica atipicidad, no el algoritmo.",
    ),
    _e(
        "EC-056", "PORQUE_ATIPICO", ["PORQUE_ATIPICO"],
        None, None, {},
        "ejecutar", "soportada", "especial",
        "Puntuación de anomalía alta: explicación general sin identificador.",
    ),
    _e(
        "EC-057", "PORQUE_ATIPICO", ["PORQUE_ATIPICO"],
        None, None, {},
        "ejecutar", "soportada", "especial",
        "Cómo se decide que un contrato es atípico: misma plantilla metodológica.",
    ),
    _e(
        "EC-060", "NO_SOPORTADO", ["NO_SOPORTADO"],
        None, None, {},
        "aclarar", "requiere_aclaracion", "seguimiento",
        "Seguimiento «esa entidad» + directa, evaluado como primer turno. Debe pedir la entidad.",
    ),
    _e(
        "EC-061", "NO_SOPORTADO", ["NO_SOPORTADO"],
        None, None, {},
        "aclarar", "requiere_aclaracion", "seguimiento",
        "«El mes anterior» no está publicado. No debe consultar 2026-09 ni otro mes.",
    ),
    _e(
        "EC-062", "NO_SOPORTADO", ["NO_SOPORTADO"],
        None, None, {},
        "aclarar", "no_soportada", "seguimiento",
        "«Los más caros» serían contratos individuales. No hay ranking de contratos por valor.",
    ),
    _e(
        "EC-063", "NO_SOPORTADO", ["NO_SOPORTADO"],
        None, None, {},
        "aclarar", "requiere_aclaracion", "seguimiento",
        "«Solo los de Bogotá» recorta un resultado previo. Sin contexto no debe contar Bogotá por su cuenta.",
    ),
    _e(
        "EC-066", "NO_SOPORTADO", ["NO_SOPORTADO"],
        None, None, {},
        "aclarar", "requiere_aclaracion", "ambigua",
        "«Qué entidad tiene más» no dice si es número o valor. No asumir ranking.",
    ),
    _e(
        "EC-067", "NO_SOPORTADO", ["NO_SOPORTADO"],
        None, None, {},
        "aclarar", "requiere_aclaracion", "ambigua",
        "«Contratos pequeños» sin umbral. No filtrar mínima cuantía.",
    ),
    _e(
        "EC-068", "NO_SOPORTADO", ["NO_SOPORTADO"],
        None, None, {},
        "aclarar", "requiere_aclaracion", "ambigua",
        "«Gastó realmente» no es valor contratado. No devolver SUM(valor_del_contrato) como gasto.",
    ),
    _e(
        "EC-069", "NO_SOPORTADO", ["NO_SOPORTADO"],
        None, None, {},
        "aclarar", "requiere_aclaracion", "ambigua",
        "«La ciudad» no identifica municipio. Bogotá no se infiere.",
    ),
    _e(
        "EC-072", "NO_SOPORTADO", ["NO_SOPORTADO"],
        None, None, {},
        "rechazar", "no_soportada", "calidad",
        "Calidad territorial («sin departamento») no tiene consulta analítica.",
    ),
    _e(
        "EC-073", "NO_SOPORTADO", ["NO_SOPORTADO"],
        None, None, {},
        "rechazar", "no_soportada", "calidad",
        "No hay conteo de contratos sin valor. No inventar nulos.",
    ),
    _e(
        "EC-074", "NO_SOPORTADO", ["NO_SOPORTADO"],
        None, None, {},
        "rechazar", "no_soportada", "calidad",
        "«No Definido» es un hallazgo del EDA, no una intención del chat.",
    ),
    _e(
        "EC-075", "NO_SOPORTADO", ["NO_SOPORTADO"],
        None, None, {},
        "rechazar", "no_soportada", "calidad",
        "Duplicados de ingesta: fuera del alcance funcional del asistente.",
    ),
]


def por_id() -> dict[str, dict]:
    return {e["id"]: e for e in ETIQUETAS}


def comprobar_etiquetas(ids_desarrollo: list[str]) -> list[str]:
    faltan = [i for i in ids_desarrollo if i not in por_id()]
    extra = [e["id"] for e in ETIQUETAS if e["id"] not in ids_desarrollo]
    errores = []
    if faltan:
        errores.append("sin_etiqueta:" + ",".join(faltan))
    if extra:
        errores.append("etiqueta_fuera_de_desarrollo:" + ",".join(extra))
    from .particion import IDS_RESERVADOS
    choque = [e["id"] for e in ETIQUETAS if e["id"] in IDS_RESERVADOS]
    if choque:
        errores.append("usa_reservados:" + ",".join(choque))
    if len(ETIQUETAS) != 51:
        errores.append(f"n_etiquetas={len(ETIQUETAS)}")
    return errores
