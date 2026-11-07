"""
Deriva la tabla de contratos desde SECOP II Contratos.

Funciones:
- conjunto_contrato(): Agrega una fila por contrato.
- invariantes_contrato(): Comprueba unicidad y campos obligatorios.
- transformar_contratos(): Homologa el territorio y devuelve el conjunto final.
"""

from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from .calidad import col_ausente, marcar_ausencia, marcar_valor_numerico
from .territorio import homologar_municipio

CAMPOS_ESTABLES = [
    "nombre_entidad",
    "nit_entidad",
    "departamento",
    "ciudad",
    "proveedor_adjudicado",
    "documento_proveedor",
    "tipodocproveedor",
    "modalidad_de_contratacion",
    "tipo_de_contrato",
    "estado_contrato",
    "fecha_de_firma",
    "fecha_de_inicio_del_contrato",
    "fecha_de_fin_del_contrato",
    "valor_del_contrato",
    "referencia_del_contrato",
    "descripcion_del_proceso",
    "codigo_de_categoria_principal",
    "duracion_del_contrato",
    "es_pyme",
    "es_grupo",
]

CAMPOS_AUSENCIA = [
    "departamento",
    "ciudad",
    "nombre_entidad",
    "proveedor_adjudicado",
    "modalidad_de_contratacion",
]


def _socrata_join():
    return F.array_join(F.array_sort(F.collect_set(F.col("socrata_id").cast("string"))), "|")


def _nuniq_expr(columna: str):
    return F.countDistinct(F.coalesce(F.col(columna).cast("string"), F.lit("_nulo")))


def _a_timestamp(columna: str):
    c = F.col(columna).cast("string")
    return F.coalesce(
        F.to_timestamp(F.col(columna)),
        F.to_timestamp(c),
        F.to_timestamp(c, "yyyy-MM-dd'T'HH:mm:ss.SSSX"),
        F.to_timestamp(c, "yyyy-MM-dd HH:mm:ss"),
        F.to_timestamp(c, "yyyy-MM-dd"),
    )


def conjunto_contrato(filas: DataFrame) -> DataFrame:
    """Una fila por id_contrato. Si un campo varía entre filas API, se lista."""
    if "id_contrato" not in filas.columns:
        raise RuntimeError("Falta id_contrato.")
    if "socrata_id" not in filas.columns:
        raise RuntimeError("Falta socrata_id (trazabilidad).")

    estables = [c for c in CAMPOS_ESTABLES if c in filas.columns]
    base = filas
    if "valor_del_contrato" in base.columns:
        base = base.withColumn("valor_del_contrato", F.col("valor_del_contrato").cast("double"))

    agg_n = [_nuniq_expr(c).alias(f"_n_{c}") for c in estables]
    nuniq = base.groupBy("id_contrato").agg(*agg_n) if estables else base.select("id_contrato").distinct()
    if estables:
        casos = ", ".join([f"CASE WHEN `_n_{c}` > 1 THEN '{c}' END" for c in estables])
        nuniq = nuniq.withColumn(
            "campos_variables",
            F.concat_ws(",", F.expr(f"filter(array({casos}), x -> x is not null)")),
        )
    else:
        nuniq = nuniq.withColumn("campos_variables", F.lit(""))

    w = Window.partitionBy("id_contrato").orderBy(F.col("socrata_id").asc())
    ranked = base.withColumn("_rn", F.row_number().over(w))
    uno = ranked.filter(F.col("_rn") == 1).drop("_rn")

    extra = [
        c
        for c in ["urlproceso", "urlcontrato", "_periodo", "_dataset_id", "_fuente"]
        if c in uno.columns
    ]
    keep = ["id_contrato", "socrata_id"] + estables + extra
    keep = [c for c in keep if c in uno.columns]
    uno = uno.select(*keep)

    trazas = base.groupBy("id_contrato").agg(
        F.count("*").alias("n_filas_api"),
        F.countDistinct("socrata_id").alias("n_socrata_id"),
        _socrata_join().alias("socrata_ids"),
    )
    out = uno.join(trazas, "id_contrato", "inner").join(
        nuniq.select("id_contrato", "campos_variables"), "id_contrato", "left"
    )
    out = out.withColumn("hay_campos_variables", F.col("campos_variables") != F.lit(""))

    for url_col, dest in (("urlcontrato", "url_contrato"), ("urlproceso", "url_contrato")):
        if url_col not in out.columns:
            continue
        if dest in out.columns:
            out = out.drop(url_col)
            continue
        dtype = dict(out.dtypes).get(url_col, "")
        if dtype.startswith("struct"):
            out = out.withColumn(dest, F.col(f"{url_col}.url")).drop(url_col)
        else:
            out = out.withColumn(dest, F.col(url_col).cast("string")).drop(url_col)
    if "url_contrato" not in out.columns:
        out = out.withColumn("url_contrato", F.lit(None).cast("string"))

    for fecha_col in (
        "fecha_de_firma",
        "fecha_de_inicio_del_contrato",
        "fecha_de_fin_del_contrato",
    ):
        if fecha_col in out.columns:
            out = out.withColumn(fecha_col, _a_timestamp(fecha_col))

    if "_periodo" in out.columns:
        out = out.withColumn("periodo", F.col("_periodo"))
    for c in (
        "nit_entidad",
        "documento_proveedor",
        "es_pyme",
        "es_grupo",
        "duracion_del_contrato",
        "referencia_del_contrato",
        "codigo_de_categoria_principal",
    ):
        if c in out.columns:
            out = out.withColumn(c, F.col(c).cast("string"))
    return out


def invariantes_contrato(contrato: DataFrame) -> list[str]:
    fallos = []
    if contrato.filter(F.col("id_contrato").isNull() | (F.trim(F.col("id_contrato")) == "")).count() > 0:
        fallos.append("id_contrato vacío")
    if contrato.filter(F.col("socrata_ids").isNull() | (F.trim(F.col("socrata_ids")) == "")).count() > 0:
        fallos.append("socrata_ids vacío")
    n = contrato.count()
    n_id = contrato.select("id_contrato").distinct().count()
    if n != n_id:
        fallos.append(f"id_contrato no único: {n} filas, {n_id} claves")
    if "valor_del_contrato" in contrato.columns:
        if contrato.filter(F.col("valor_del_contrato") < 0).count() > 0:
            fallos.append("valor_del_contrato negativo")
        if contrato.filter(F.col("valor_usable") & F.col("valor_del_contrato").isNull()).count() > 0:
            fallos.append("valor_usable sin monto")
    return fallos


def transformar_contratos(filas: DataFrame, dim_municipio: DataFrame) -> DataFrame:
    """Pipeline de contratos. Notebook y job llaman a esta función."""
    contrato = conjunto_contrato(filas)
    contrato = homologar_municipio(contrato, "departamento", "ciudad", dim_municipio)
    contrato = marcar_ausencia(contrato, CAMPOS_AUSENCIA)
    if "valor_del_contrato" in contrato.columns:
        contrato = marcar_valor_numerico(contrato, "valor_del_contrato")
        valor = F.col("valor_del_contrato")
        contrato = contrato.withColumn("valor_usable", valor.isNotNull())
        contrato = contrato.withColumn(
            "valor_apto_modelo",
            valor.isNotNull()
            & (valor > F.lit(0.0))
            & (~F.col("valor_del_contrato_extremo")),
        )
    else:
        contrato = contrato.withColumn("valor_usable", F.lit(False))
        contrato = contrato.withColumn("valor_apto_modelo", F.lit(False))
    return contrato
