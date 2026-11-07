"""
Detección de anomalías en contratos. Una puntuación atípica no afirma una irregularidad.

Funciones:
- leer_contratos_modelo(): Lee el universo del periodo.
- partir_universo(): Separa aptos, ceros y extremos.
- matriz(): Construye la matriz de características.
- ajustar_tres(): Entrena el baseline, Isolation Forest y LOF.
- correr_fase(): Ejecuta los experimentos C0–C5.
- generar_publicacion(): Genera la puntuación publicable.
"""

from .evaluacion import correlacion_rankings, inspeccion, solape_tops
from .experimentos import correr_fase
from .features import enriquecer, informe_plazo, matriz, partir_universo
from .lectura import leer_contratos_modelo
from .modelos import ajustar_tres
from .publicacion import ejecutar as generar_publicacion
from .scoring import VERSION_MODELO

__all__ = [
    "ajustar_tres",
    "correr_fase",
    "correlacion_rankings",
    "enriquecer",
    "generar_publicacion",
    "informe_plazo",
    "inspeccion",
    "leer_contratos_modelo",
    "matriz",
    "partir_universo",
    "solape_tops",
    "VERSION_MODELO",
]
