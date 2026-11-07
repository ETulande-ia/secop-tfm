"""
Deriva proceso y adjudicación desde las filas de SECOP II Procesos.

Funciones:
- conjunto_proceso(): Agrega una fila por proceso.
- clasificar_pares(): Clasifica los pares proceso-proveedor.
- conjuntos_adjudicacion(): Separa adjudicaciones únicas y ambiguas.
- invariantes_adjudicacion(): Comprueba las reglas de adjudicación.
- transformar_procesos(): Produce las tablas de proceso y adjudicación.
"""

from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from .calidad import col_ausente, marcar_ausencia, marcar_valor_numerico
from .territorio import homologar_municipio

CAMPOS_ESTABLES = [
    "estado_del_procedimiento",
    "fecha_de_publicacion_del",
    "fecha_de_ultima_publicaci",
    "modalidad_de_contratacion",
    "entidad",
    "nit_entidad",
    "departamento_entidad",
    "ciudad_entidad",
    "precio_base",
    "adjudicado",
    "descripcion_del_procedimiento",
    "referencia_del_proceso",
    "duracion",
    "unidad_de_duracion",
    "codigo_de_categoria_principal",
    "proceso_de_compra",
]

CAMPOS_AUSENCIA = ["departamento_entidad", "ciudad_entidad", "entidad", "adjudicado"]


def _socrata_join():
    return F.array_join(F.array_sort(F.collect_set(F.col("socrata_id").cast("string"))), "|")


def _nuniq_expr(columna: str):
    return F.countDistinct(F.coalesce(F.col(columna).cast("string"), F.lit("_nulo")))


def conjunto_proceso(filas: DataFrame) -> DataFrame:
    """Una fila por id_del_proceso con campos estables. No es deduplicación arbitraria:

    se comprueba que los campos de proceso no varíen; si alguno varía se lista
    en campos_variables. Las adjudicaciones no entran aquí.
    """
    if "id_del_proceso" not in filas.columns:
        raise RuntimeError("Falta id_del_proceso.")
    if "socrata_id" not in filas.columns:
        raise RuntimeError("Falta socrata_id (trazabilidad).")

    estables = [c for c in CAMPOS_ESTABLES if c in filas.columns]
    base = filas.withColumn("precio_base", F.col("precio_base").cast("double")) if "precio_base" in filas.columns else filas

    agg_n = [_nuniq_expr(c).alias(f"_n_{c}") for c in estables]
    nuniq = base.groupBy("id_del_proceso").agg(*agg_n)
    casos = ", ".join([f"CASE WHEN `_n_{c}` > 1 THEN '{c}' END" for c in estables])
    nuniq = nuniq.withColumn(
        "campos_variables",
        F.concat_ws(",", F.expr(f"filter(array({casos}), x -> x is not null)"))
        if estables
        else F.lit(""),
    )

    w = Window.partitionBy("id_del_proceso").orderBy(F.col("socrata_id").asc())
    ranked = base.withColumn("_rn", F.row_number().over(w))
    uno = ranked.filter(F.col("_rn") == 1).drop("_rn")

    extra = [
        c
        for c in [
            "urlproceso",
            "ciudad_de_la_unidad_de",
            "_periodo",
            "_dataset_id",
            "_fuente",
        ]
        if c in uno.columns
    ]
    keep = ["id_del_proceso"] + estables + extra
    keep = [c for c in keep if c in uno.columns]
    uno = uno.select(*keep)

    trazas = base.groupBy("id_del_proceso").agg(
        F.count("*").alias("n_filas_api"),
        F.countDistinct("socrata_id").alias("n_socrata_id"),
        _socrata_join().alias("socrata_ids"),
    )
    out = uno.join(trazas, "id_del_proceso", "inner").join(
        nuniq.select("id_del_proceso", "campos_variables"), "id_del_proceso", "left"
    )
    out = out.withColumn("hay_campos_variables", F.col("campos_variables") != F.lit(""))
    if "urlproceso" in out.columns:
        # En Mongo viene como {url: ...}; se deja la URL como texto.
        dtype = dict(out.dtypes).get("urlproceso", "")
        if dtype.startswith("struct"):
            out = out.withColumn("url_proceso", F.col("urlproceso.url")).drop("urlproceso")
        else:
            out = out.withColumn("url_proceso", F.col("urlproceso").cast("string")).drop("urlproceso")
    if "_periodo" in out.columns:
        out = out.withColumn("periodo", F.col("_periodo"))
    return out


def _clave_proveedor(filas: DataFrame):
    tiene_cod = "codigoproveedor" in filas.columns
    tiene_nom = "nombre_del_proveedor" in filas.columns
    if tiene_cod:
        cod = F.trim(F.col("codigoproveedor").cast("string"))
        vac_cod = col_ausente(F.col("codigoproveedor"))
        if tiene_nom:
            nom = F.trim(F.col("nombre_del_proveedor").cast("string"))
            return F.when(vac_cod, F.coalesce(nom, F.lit("_sin_proveedor"))).otherwise(cod)
        return F.when(vac_cod, F.lit("_sin_proveedor")).otherwise(cod)
    if tiene_nom:
        nom = F.trim(F.col("nombre_del_proveedor").cast("string"))
        return F.when(col_ausente(F.col("nombre_del_proveedor")), F.lit("_sin_proveedor")).otherwise(nom)
    return F.lit("_sin_proveedor")


def clasificar_pares(filas: DataFrame) -> DataFrame:
    """Pares proceso + id_adjudicacion con banderas cartesiano / ambiguo / confiable.

    Misma regla que el EDA (notebook 02):
    - cartesiano: ≥2 proveedores y ≥2 valores.
    - ambiguo: cartesiano, o sin id_adjudicacion con más de un proveedor o valor.
    - confiable: no ambiguo y con id_adjudicacion.
    """
    if "id_adjudicacion" not in filas.columns:
        base = filas.withColumn("id_adjudicacion", F.lit(None).cast("string"))
    else:
        base = filas
    awd = F.trim(F.col("id_adjudicacion").cast("string"))
    awd_vacio = col_ausente(F.col("id_adjudicacion"))
    valor = F.col("valor_total_adjudicacion").cast("double") if "valor_total_adjudicacion" in base.columns else F.lit(None).cast("double")
    marked = (
        base.withColumn("_awd", F.when(awd_vacio, F.lit("_sin_awd")).otherwise(awd))
        .withColumn("_prov", _clave_proveedor(base))
        .withColumn("valor_num", valor)
        .withColumn(
            "_valor_clave",
            F.coalesce(F.col("valor_num").cast("string"), F.lit("_nulo")),
        )
    )
    vac_prov = F.col("_prov").isNull() | (F.trim(F.col("_prov")) == "") | F.upper(F.col("_prov")).isin(
        ["NO DEFINIDO", "NONE", "NULL", "NAN", "NA", "ND"]
    )
    marked = marked.withColumn(
        "_prov", F.when(vac_prov, F.lit("_sin_proveedor")).otherwise(F.col("_prov"))
    )
    agg_pares = [
        F.count("*").alias("n_filas"),
        F.countDistinct("_prov").alias("n_prov"),
        F.countDistinct("_valor_clave").alias("n_val"),
    ]
    if "nombre_del_proveedor" in marked.columns:
        agg_pares.append(
            F.countDistinct(
                F.coalesce(F.col("nombre_del_proveedor").cast("string"), F.lit("_nulo"))
            ).alias("n_prov_nom")
        )
    pares = marked.groupBy("id_del_proceso", "_awd").agg(*agg_pares)
    if "n_prov_nom" not in pares.columns:
        pares = pares.withColumn("n_prov_nom", F.lit(0))
    pares = (
        pares.withColumn("cartesiano", (F.col("n_prov") >= 2) & (F.col("n_val") >= 2))
        .withColumn("sin_awd", F.col("_awd") == F.lit("_sin_awd"))
        .withColumn(
            "ambiguo",
            F.col("cartesiano")
            | (
                F.col("sin_awd")
                & ((F.col("n_prov") > 1) | (F.col("n_val") > 1))
            ),
        )
        .withColumn("confiable", (~F.col("ambiguo")) & (~F.col("sin_awd")))
    )
    return pares


def conjuntos_adjudicacion(filas: DataFrame) -> tuple[DataFrame, DataFrame]:
    """Adjudicaciones confiables y ambiguas. No suma cartesianos.

    Confiable persistible: 1 fila por proceso + id_adjudicacion (par EDA).
    Si un par tiene varios montos o varios proveedores, se listan; no se
    materializan como adjudicaciones independientes ni se suman.
    Ambigua: 1 fila por par no 1:1 (cartesianos).
    """
    pares = clasificar_pares(filas)
    awd_vacio = col_ausente(F.col("id_adjudicacion")) if "id_adjudicacion" in filas.columns else F.lit(True)
    awd = F.trim(F.col("id_adjudicacion").cast("string")) if "id_adjudicacion" in filas.columns else F.lit("_sin_awd")
    valor = F.col("valor_total_adjudicacion").cast("double") if "valor_total_adjudicacion" in filas.columns else F.lit(None).cast("double")
    marked = (
        filas.withColumn("_awd", F.when(awd_vacio, F.lit("_sin_awd")).otherwise(awd))
        .withColumn("_prov", _clave_proveedor(filas))
        .withColumn("valor_num", valor)
    )
    vac_prov = F.col("_prov").isNull() | (F.trim(F.col("_prov")) == "") | F.upper(F.col("_prov")).isin(
        ["NO DEFINIDO", "NONE", "NULL", "NAN", "NA", "ND"]
    )
    marked = marked.withColumn(
        "_prov", F.when(vac_prov, F.lit("_sin_proveedor")).otherwise(F.col("_prov"))
    )

    agg_adj = [
        F.count("*").alias("n_filas_api"),
        F.countDistinct("_prov").alias("n_proveedores"),
        F.countDistinct(F.coalesce(F.col("valor_num").cast("string"), F.lit("_nulo"))).alias(
            "n_valores"
        ),
        F.first("_prov", ignorenulls=True).alias("_prov_uno"),
        F.array_join(F.array_sort(F.collect_set("_prov")), " | ").alias("proveedores"),
        F.array_join(
            F.array_sort(
                F.collect_set(F.coalesce(F.col("valor_num").cast("string"), F.lit("_nulo")))
            ),
            " | ",
        ).alias("valores"),
        F.first("valor_num", ignorenulls=True).alias("_valor_uno"),
        _socrata_join().alias("socrata_ids"),
    ]
    if "nombre_del_proveedor" in marked.columns:
        agg_adj.append(
            F.first("nombre_del_proveedor", ignorenulls=True).alias("_nombre_uno")
        )
    if "_periodo" in marked.columns:
        agg_adj.append(F.first("_periodo", ignorenulls=True).alias("periodo"))

    ok = pares.filter(F.col("confiable")).select("id_del_proceso", "_awd")
    adj = (
        marked.join(ok, ["id_del_proceso", "_awd"], "inner")
        .groupBy("id_del_proceso", "_awd")
        .agg(*agg_adj)
        .withColumnRenamed("_awd", "id_adjudicacion")
        .withColumn(
            "tipo_grano",
            F.when((F.col("n_proveedores") == 1) & (F.col("n_valores") == 1), F.lit("unico"))
            .when(
                (F.col("n_proveedores") == 1) & (F.col("n_valores") > 1),
                F.lit("un_proveedor_varios_valores"),
            )
            .when(
                (F.col("n_proveedores") > 1) & (F.col("n_valores") == 1),
                F.lit("varios_proveedores_un_valor"),
            )
            .otherwise(F.lit("revisar")),
        )
        .withColumn(
            "codigo_proveedor",
            F.when(F.col("n_proveedores") == 1, F.col("_prov_uno")),
        )
        .withColumn(
            "valor_total_adjudicacion",
            F.when(F.col("n_valores") == 1, F.col("_valor_uno")),
        )
        .withColumn("valor_usable", F.col("n_valores") == 1)
    )
    if "_nombre_uno" in adj.columns:
        adj = adj.withColumn(
            "nombre_del_proveedor",
            F.when(F.col("n_proveedores") == 1, F.col("_nombre_uno")),
        )
    else:
        adj = adj.withColumn("nombre_del_proveedor", F.lit(None).cast("string"))
    adj = adj.drop(*[c for c in ("_prov_uno", "_valor_uno", "_nombre_uno") if c in adj.columns])
    adj = marcar_valor_numerico(adj, "valor_total_adjudicacion")

    amb_keys = pares.filter(F.col("ambiguo")).select(
        "id_del_proceso", "_awd", "cartesiano", "sin_awd", "n_filas", "n_prov", "n_val"
    )
    agg_amb = [
        F.count("*").alias("n_filas_api"),
        F.countDistinct("_prov").alias("n_proveedores"),
        F.countDistinct(F.coalesce(F.col("valor_num").cast("string"), F.lit("_nulo"))).alias(
            "n_valores"
        ),
        F.array_join(F.array_sort(F.collect_set("_prov")), " | ").alias("proveedores"),
        F.array_join(
            F.array_sort(
                F.collect_set(F.coalesce(F.col("valor_num").cast("string"), F.lit("_nulo")))
            ),
            " | ",
        ).alias("valores"),
        _socrata_join().alias("socrata_ids"),
    ]
    if "_periodo" in marked.columns:
        agg_amb.append(F.first("_periodo", ignorenulls=True).alias("periodo"))
    amb = (
        marked.join(amb_keys.select("id_del_proceso", "_awd"), ["id_del_proceso", "_awd"], "inner")
        .groupBy("id_del_proceso", "_awd")
        .agg(*agg_amb)
        .join(amb_keys, ["id_del_proceso", "_awd"], "inner")
        .withColumnRenamed("_awd", "id_adjudicacion")
        .withColumn(
            "motivo",
            F.when(F.col("cartesiano"), F.lit("cartesiano_proveedor_valor")).otherwise(
                F.lit("ambiguo_sin_id_adjudicacion")
            ),
        )
        .withColumn("suma_valores", F.lit("no aplicada"))
    )
    return adj, amb


def invariantes_adjudicacion(adj: DataFrame, amb: DataFrame) -> list[str]:
    """Reglas de grano. Lista vacía = se puede persistir."""
    fallos = []
    if adj.filter(F.col("tipo_grano") == "revisar").count() > 0:
        fallos.append("tipo_grano=revisar en confiables (no debería haber cartesianos)")
    if adj.filter((F.col("n_valores") > 1) & F.col("valor_usable")).count() > 0:
        fallos.append("valor_usable con n_valores > 1")
    if adj.filter(F.col("valor_usable") & F.col("valor_total_adjudicacion").isNull()).count() > 0:
        fallos.append("valor_usable sin monto")
    if adj.filter((~F.col("valor_usable")) & F.col("valor_total_adjudicacion").isNotNull()).count() > 0:
        fallos.append("monto informado con valor_usable=false")
    if adj.filter((F.col("n_proveedores") > 1) & F.col("codigo_proveedor").isNotNull()).count() > 0:
        fallos.append("codigo_proveedor informado con varios proveedores")
    if adj.filter(F.col("socrata_ids").isNull() | (F.trim(F.col("socrata_ids")) == "")).count() > 0:
        fallos.append("socrata_ids vacío en adjudicacion")
    if amb.filter(F.col("socrata_ids").isNull() | (F.trim(F.col("socrata_ids")) == "")).count() > 0:
        fallos.append("socrata_ids vacío en adjudicacion_ambigua")
    if amb.filter(F.col("suma_valores") != F.lit("no aplicada")).count() > 0:
        fallos.append("suma aplicada en ambiguas")
    solape = adj.join(amb, ["id_del_proceso", "id_adjudicacion"], "inner").count()
    if solape > 0:
        fallos.append(f"pares en adjudicacion y ambigua: {solape}")
    return fallos


def transformar_procesos(filas: DataFrame, dim_municipio: DataFrame) -> dict:
    """Pipeline de procesos. Notebook y job llaman a esta función."""
    proceso = conjunto_proceso(filas)
    proceso = homologar_municipio(
        proceso, "departamento_entidad", "ciudad_entidad", dim_municipio
    )
    proceso = marcar_ausencia(proceso, CAMPOS_AUSENCIA)
    if "precio_base" in proceso.columns:
        proceso = marcar_valor_numerico(proceso, "precio_base")
    adj, amb = conjuntos_adjudicacion(filas)
    pares = clasificar_pares(filas)
    return {
        "proceso": proceso,
        "adjudicacion": adj,
        "adjudicacion_ambigua": amb,
        "pares": pares,
    }
