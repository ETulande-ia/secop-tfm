"""
Marca ausencia, ceros y valores extremos. No imputa ni borra registros.

Funciones:
- marcar_ausencia(): Añade indicadores de valor ausente.
- a_numerico(): Convierte una columna a numérica.
- marcar_valor_numerico(): Marca cero, negativo y extremo.
"""

from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from .territorio import normalizar_texto

_AUSENTES = ["", "NO DEFINIDO", "NONE", "NULL", "NAN", "NA", "ND"]


def col_ausente(columna):
    """True si nulo, vacío, No Definido, None o null (tras normalizar)."""
    n = F.coalesce(normalizar_texto(columna), F.lit(""))
    return columna.isNull() | n.isin(_AUSENTES)


def marcar_ausencia(df: DataFrame, columnas) -> DataFrame:
    out = df
    for c in columnas:
        if c not in out.columns:
            continue
        out = out.withColumn(f"{c}_ausente", col_ausente(F.col(c)))
    return out


def a_numerico(df: DataFrame, columna: str, alias: str | None = None) -> DataFrame:
    nombre = alias or columna
    return df.withColumn(nombre, F.col(columna).cast("double"))


def marcar_valor_numerico(df: DataFrame, columna: str, umbral_extremo: float = 1e12) -> DataFrame:
    """Marca 0, negativo y > umbral. No interpreta irregularidad. No imputa."""
    if columna not in df.columns:
        raise ValueError(f"No está la columna {columna}")
    num = F.col(columna).cast("double")
    return (
        df.withColumn(columna, num)
        .withColumn(f"{columna}_cero", num.isNotNull() & (num == F.lit(0.0)))
        .withColumn(f"{columna}_negativo", num.isNotNull() & (num < F.lit(0.0)))
        .withColumn(
            f"{columna}_extremo",
            num.isNotNull() & (num > F.lit(float(umbral_extremo))),
        )
    )
