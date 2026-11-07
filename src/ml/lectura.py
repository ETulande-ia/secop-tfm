"""
Lectura de tfm.contrato para los experimentos. No escribe.

Funciones:
- leer_contratos_modelo(): Trae los contratos del periodo con las columnas del modelo.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyspark.sql import DataFrame, SparkSession

COLUMNAS = [
    "periodo",
    "id_contrato",
    "socrata_id",
    "nombre_entidad",
    "departamento",
    "ciudad",
    "proveedor_adjudicado",
    "modalidad_de_contratacion",
    "tipo_de_contrato",
    "estado_contrato",
    "fecha_de_firma",
    "fecha_de_inicio_del_contrato",
    "fecha_de_fin_del_contrato",
    "valor_del_contrato",
    "valor_del_contrato_cero",
    "valor_del_contrato_extremo",
    "valor_apto_modelo",
    "duracion_del_contrato",
    "es_pyme",
    "es_grupo",
    "es_bogota",
    "cod_municipio",
    "estado_homologacion",
]


FECHAS = (
    "fecha_de_firma",
    "fecha_de_inicio_del_contrato",
    "fecha_de_fin_del_contrato",
)


def leer_contratos_modelo(spark: SparkSession, periodo: str = "2026-09") -> DataFrame:
    """JDBC de solo lectura a tfm.contrato. No toca Mongo ni escribe.

    Las fechas se leen como texto: hay al menos un timestamp fuera del
    rango de pandas (año 202) y no se corrige en origen.
    """
    from pyspark.sql import functions as F
    from transformation.io import leer_tabla_tfm

    df = leer_tabla_tfm(spark, "contrato", periodo, col_tiempo="periodo")
    hay = [c for c in COLUMNAS if c in df.columns]
    df = df.select(*hay)
    for c in FECHAS:
        if c in df.columns:
            df = df.withColumn(c, F.col(c).cast("string"))
    return df
