"""
Transformación PySpark de SECOP II y del CNPV 2018.

Funciones:
- crear_spark(): Abre la sesión Spark local.
- reconciliar(): Compara un conteo con su valor esperado.
- cuadro_control(): Arma el cuadro de controles.
- controles_criticos_ok(): Indica si los controles críticos cuadran.
"""

from .controles import (
    CONTROLES_CRITICOS,
    CONTROLES_CRITICOS_CONTRATOS,
    CONTROLES_CRITICOS_DANE,
    CONTROLES_CRITICOS_PROCESOS,
    ESPERADO,
    controles_criticos_ok,
    cuadro_control,
    reconciliar,
)
from .spark_sesion import crear_spark

__all__ = [
    "CONTROLES_CRITICOS",
    "CONTROLES_CRITICOS_CONTRATOS",
    "CONTROLES_CRITICOS_DANE",
    "CONTROLES_CRITICOS_PROCESOS",
    "ESPERADO",
    "controles_criticos_ok",
    "cuadro_control",
    "crear_spark",
    "reconciliar",
]
