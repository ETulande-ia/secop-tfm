"""
Homologa nombres de SECOP a DIVIPOLA. El territorio corresponde a la sede de la entidad.

Funciones:
- normalizar_str(): Normaliza un nombre territorial.
- es_bogota_str(): Indica si el texto corresponde a Bogotá.
- depto_canon_str(): Devuelve el nombre canónico del departamento.
- homologar_municipio(): Une departamento y municipio con dim_municipio.
"""

from __future__ import annotations

import unicodedata

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

# Mayúsculas y sin tildes, igual que en el notebook 05.
_AUSENTES = frozenset({"", "NO DEFINIDO", "NONE", "NULL", "NAN", "NA", "ND"})

ALIAS_DEPTO = {
    "DISTRITO CAPITAL DE BOGOTA": "BOGOTA D C",
    "BOGOTA": "BOGOTA D C",
    "BOGOTA D C": "BOGOTA D C",
    "BOGOTA DC": "BOGOTA D C",
    "ARCHIPIELAGO DE SAN ANDRES PROVIDENCIA Y SANTA CATALINA": (
        "ARCHIPIELAGO DE SAN ANDRES"
    ),
    "SAN ANDRES PROVIDENCIA Y SANTA CATALINA": "ARCHIPIELAGO DE SAN ANDRES",
    "SAN ANDRES": "ARCHIPIELAGO DE SAN ANDRES",
}

# Alias puntuales documentados en docs/04 y docs/05.
ALIAS_MPIO = {
    "GUADALAJARA DE BUGA": "BUGA",
    "VILLA DE SAN DIEGO DE UBATE": "UBATE",
    "LEGUIZAMO": "PUERTO LEGUIZAMO",
    "EL SANTUARIO": "SANTUARIO",
}

_ACC = "ÁÀÄÂÉÈËÊÍÌÏÎÓÒÖÔÚÙÜÛÝáàäâéèëêíìïîóòöôúùüûýÑñ"
_PLAIN = "AAAAEEEEIIIIOOOOUUUUYaaaaeeeeiiiioooouuuuyNn"

def _mapa(alias: dict):
    pares = []
    for k, v in alias.items():
        pares.extend([F.lit(k), F.lit(v)])
    return F.create_map(*pares)


def normalizar_str(valor) -> str:
    """Mayúsculas, sin tildes ni puntuación. Cadena Python (UDF / driver)."""
    if valor is None:
        return ""
    txt = str(valor).strip()
    if not txt:
        return ""
    txt = unicodedata.normalize("NFKD", txt)
    txt = "".join(ch for ch in txt if not unicodedata.combining(ch)).upper()
    out = []
    for ch in txt:
        if ("A" <= ch <= "Z") or ("0" <= ch <= "9") or ch == " ":
            out.append(ch)
        else:
            out.append(" ")
    return " ".join("".join(out).split())


def es_ausente_str(valor) -> bool:
    return normalizar_str(valor) in _AUSENTES


def es_bogota_str(valor) -> bool:
    n = normalizar_str(valor)
    return ("BOGOTA" in n) or ("DISTRITO CAPITAL" in n)


def depto_canon_str(nombre) -> str | None:
    n = normalizar_str(nombre)
    if es_ausente_str(n):
        return None
    if es_bogota_str(n):
        return "BOGOTA D C"
    return ALIAS_DEPTO.get(n, n)


def normalizar_texto(columna):
    """Versión columna Spark: mayúsculas, sin tildes ni puntuación."""
    limpio = F.trim(F.translate(columna.cast("string"), _ACC, _PLAIN))
    mayus = F.upper(limpio)
    alnum = F.regexp_replace(mayus, "[^A-Z0-9 ]+", " ")
    return F.trim(F.regexp_replace(alnum, "\\s+", " "))


def col_es_bogota(col_depto, col_mpio):
    d = F.coalesce(normalizar_texto(F.col(col_depto)), F.lit(""))
    m = F.coalesce(normalizar_texto(F.col(col_mpio)), F.lit(""))
    return (
        d.contains("BOGOTA")
        | d.contains("DISTRITO CAPITAL")
        | m.contains("BOGOTA")
        | m.contains("DISTRITO CAPITAL")
    )


def homologar_municipio(df: DataFrame, col_depto: str, col_mpio: str, dim_municipio: DataFrame) -> DataFrame:
    """Añade cod_municipio, estado_homologacion, via_homologacion y nombres DIVIPOLA.

    Joins Spark, sin UDF: los workers no importan el paquete transformation.
    """
    ausentes = list(_AUSENTES)
    alias_d = _mapa(ALIAS_DEPTO)
    alias_m = _mapa(ALIAS_MPIO)
    d0 = F.coalesce(normalizar_texto(F.col(col_depto)), F.lit(""))
    m0 = F.coalesce(normalizar_texto(F.col(col_mpio)), F.lit(""))
    aus_d = F.col(col_depto).isNull() | d0.isin(ausentes)
    aus_m = F.col(col_mpio).isNull() | m0.isin(ausentes)
    bog = (
        d0.contains("BOGOTA")
        | d0.contains("DISTRITO CAPITAL")
        | m0.contains("BOGOTA")
        | m0.contains("DISTRITO CAPITAL")
    )
    depto_c = (
        F.when(aus_d, F.lit(None).cast("string"))
        .when(bog, F.lit("BOGOTA D C"))
        .otherwise(F.coalesce(alias_d[d0], d0))
    )
    mpio_c = F.when(aus_m, F.lit(None).cast("string")).otherwise(F.coalesce(alias_m[m0], m0))

    work = (
        df.withColumn("_depto_c", depto_c)
        .withColumn("_mpio_c", mpio_c)
        .withColumn("_aus_d", aus_d)
        .withColumn("_aus_m", aus_m)
        .withColumn("es_bogota", bog)
    )

    dim_n = dim_municipio.select(
        F.col("cod_municipio").alias("_cod_exact"),
        normalizar_texto(F.col("nombre_departamento")).alias("_d_dim"),
        normalizar_texto(F.col("nombre_municipio")).alias("_m_dim"),
    )
    uniq = (
        dim_n.groupBy("_m_dim")
        .agg(F.countDistinct("_cod_exact").alias("_n_cod"), F.first("_cod_exact").alias("_cod_unico"))
        .filter(F.col("_n_cod") == 1)
        .select(F.col("_m_dim").alias("_m_unico"), "_cod_unico")
    )

    out = work.join(
        F.broadcast(dim_n),
        (work["_depto_c"] == dim_n["_d_dim"]) & (work["_mpio_c"] == dim_n["_m_dim"]),
        "left",
    ).join(F.broadcast(uniq), work["_mpio_c"] == uniq["_m_unico"], "left")

    cod = (
        F.when(F.col("es_bogota") | (F.col("_depto_c") == F.lit("BOGOTA D C")), F.lit("11001"))
        .when(F.col("_cod_exact").isNotNull(), F.col("_cod_exact"))
        .when(F.col("_cod_unico").isNotNull(), F.col("_cod_unico"))
    )
    estado = (
        F.when(F.col("_aus_d") & F.col("_aus_m"), F.lit("no_definido"))
        .when(F.col("_aus_m") & (F.col("_depto_c") == F.lit("BOGOTA D C")), F.lit("homologado"))
        .when(F.col("_aus_m") & F.col("_aus_d"), F.lit("no_definido"))
        .when(F.col("_aus_m"), F.lit("sin_municipio"))
        .when(cod.isNotNull(), F.lit("homologado"))
        .when(F.col("_aus_d"), F.lit("no_definido"))
        .otherwise(F.lit("no_homologado"))
    )
    via = (
        F.when(F.col("_aus_d") & F.col("_aus_m"), F.lit("ambos_ausentes"))
        .when(F.col("_aus_m") & (F.col("_depto_c") == F.lit("BOGOTA D C")), F.lit("bogota_depto"))
        .when(F.col("es_bogota"), F.lit("bogota"))
        .when(F.col("_cod_exact").isNotNull(), F.lit("depto_mpio"))
        .when(F.col("_cod_unico").isNotNull(), F.lit("mpio_unico_nacional"))
        .when(F.col("_aus_m"), F.lit("solo_depto"))
        .when(F.col("_aus_d"), F.lit("depto_ausente"))
        .otherwise(F.lit("sin_cruce"))
    )
    out = (
        out.withColumn("cod_municipio", F.when(estado == F.lit("homologado"), cod))
        .withColumn("estado_homologacion", estado)
        .withColumn("via_homologacion", via)
        .drop("_depto_c", "_mpio_c", "_aus_d", "_aus_m", "_cod_exact", "_d_dim", "_m_dim", "_m_unico", "_cod_unico")
    )
    dim_nombres = dim_municipio.select(
        F.col("cod_municipio").alias("_cod_dim"),
        F.col("nombre_municipio").alias("nombre_municipio_divipola"),
        F.col("nombre_departamento").alias("nombre_departamento_divipola"),
    )
    out = out.join(dim_nombres, out["cod_municipio"] == dim_nombres["_cod_dim"], "left").drop("_cod_dim")
    if "id_del_proceso" in out.columns:
        out = out.dropDuplicates(["id_del_proceso"])
    elif "id_contrato" in out.columns:
        out = out.dropDuplicates(["id_contrato"])
    return out

