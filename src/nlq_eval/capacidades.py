"""
Inventario de capacidades del orquestador usado como referencia de la evaluación.

Constantes:
- CAPACIDADES: Periodo, operaciones, filtros, intenciones y límites del NLQ.
"""

CAPACIDADES = {
    "periodo": "2026-09",
    "territorio_filtro": "solo bogota (es_bogota = sede de la entidad, no lugar de ejecución)",
    "operaciones_nlq": ["contar", "ranking", "distribucion"],
    "metricas_nlq": ["n_contratos", "valor"],
    "filtros_nlq": ["territorio=bogota", "entidad (resolución por nombre)", "modalidad (pista léxica)"],
    "intenciones_cerradas": [
        "BOGOTA_CONTRATACION",
        "TOP_ENTIDADES",
        "MODALIDADES",
        "TOP1_IF",
        "PORQUE_ATIPICO",
        "EXPLAIN_CONTRACT",
        "TOP_PROVIDERS",
        "INVESTMENT_CITY",
        "EXECUTION_TIME_ENTITY",
        "LONGEST_CONTRACTS",
        "RISK_ANALYSIS",
        "NLQ",
        "NO_SOPORTADO",
        "UNKNOWN",
    ],
    "especiales_sin_filtro_extra": [
        "TOP1_IF",
        "TOP_PROVIDERS",
        "INVESTMENT_CITY",
        "EXECUTION_TIME_ENTITY",
        "LONGEST_CONTRACTS",
        "RISK_ANALYSIS",
    ],
    "no_soportado_hoy": [
        "RAG documental en POST /api/chat",
        "listado de contratos por entidad o modalidad",
        "filtro de ciudad distinto de Bogotá",
        "periodo distinto de 2026-09",
        "TOP1_IF filtrado por ciudad o entidad",
        "proveedores filtrados por entidad",
        "contrato más caro / ranking de contratos por valor",
        "conteo de nulos o calidad de datos",
        "afirmación de corrupción, fraude o ilegalidad",
        "glosario ciudadano (a dedo, plata, raros, pequeños)",
    ],
    "contrato_chat": {
        "metodo": "POST",
        "ruta": "/api/chat",
        "cuerpo": {"query": "str", "contexto": "object opcional"},
        "respuesta": ["intent", "text", "data", "visualization", "slots"],
    },
    "flujo": (
        "extraerMenciones → especial | NLQ parametrizado | "
        "detectIntentLLM + fallback léxico → analyticalQuery.execute"
    ),
}
