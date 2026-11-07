"""
Agrega la población municipal del CNPV 2018 y la une a DIVIPOLA.

Funciones:
- codigo_municipio(): Construye el código DIVIPOLA.
- inspeccionar_categorias(): Resume las categorías del censo.
- poblacion_municipal(): Agrega personas por municipio.
- transformar_dane(): Produce la tabla de población y su inspección.
- invariantes_poblacion(): Comprueba totales y códigos.
"""

from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

ANIO_CENSO = 2018
FUENTE = "cnpv2018_parquet"
RUTA_PARQUET_DEFAULT = "/datalake/cnpv2018/personas"

# Diccionarios DANE. Los indicadores solo se publican si las categorías
# observadas están contenidas en estos conjuntos.
SEXO_DANE = frozenset({"1", "2"})
EDAD_DANE = frozenset(str(i) for i in range(1, 22))
ZONA_DANE = frozenset({"1", "2", "3"})
ZONA_CABECERA_RESTO = frozenset({"1", "4"})

EDAD_0_14 = frozenset(str(i) for i in range(1, 4))
EDAD_15_64 = frozenset(str(i) for i in range(4, 14))
EDAD_65_MAS = frozenset(str(i) for i in range(14, 22))


def _primera_columna(df: DataFrame, nombres: tuple[str, ...]) -> str | None:
    for n in nombres:
        if n in df.columns:
            return n
    return None


def codigo_municipio(df: DataFrame) -> DataFrame:
    """Código DIVIPOLA de 5 dígitos. No se inventan códigos.

    Si están `U_DPTO` y `U_MPIO`, se concatenan (2+3). El parquet del TFM
    ya materializó esa concatenación en `cod_mpio`; en ese caso se rellena
    a 5 dígitos y se deja constancia del origen.
    """
    tiene_dpto = "U_DPTO" in df.columns
    tiene_mpio = "U_MPIO" in df.columns
    if tiene_dpto and tiene_mpio:
        out = df.withColumn(
            "cod_municipio",
            F.concat(_digitos(F.col("U_DPTO"), 2), _digitos(F.col("U_MPIO"), 3)),
        )
        return out.withColumn("via_codigo", F.lit("U_DPTO+U_MPIO"))
    col_cod = _primera_columna(df, ("cod_mpio", "cod_municipio"))
    if col_cod is None:
        raise RuntimeError(
            "El parquet no tiene U_DPTO/U_MPIO ni cod_mpio. "
            "No se asignan códigos simulados."
        )
    out = df.withColumn("cod_municipio", _digitos(F.col(col_cod), 5))
    return out.withColumn("via_codigo", F.lit("cod_mpio_parquet"))


def _digitos(columna, ancho: int):
    """Entero sin decimales, relleno a la izquierda. No inventa valores."""
    num = columna.cast("int")
    txt = F.when(num.isNotNull(), num.cast("string")).otherwise(
        F.trim(columna.cast("string"))
    )
    return F.lpad(txt, ancho, "0")


def _norm_cat(columna: str):
    c = F.col(columna)
    num = c.cast("int")
    return F.trim(F.when(num.isNotNull(), num.cast("string")).otherwise(c.cast("string")))


def inspeccionar_categorias(personas: DataFrame) -> dict:
    """Valores observados de sexo, edad y zona. No imputa."""
    sexo_c = _primera_columna(personas, ("P_SEXO", "sexo"))
    edad_c = _primera_columna(personas, ("P_EDADR", "edad_grupo"))
    zona_c = _primera_columna(personas, ("UA_CLASE", "zona"))
    out = {
        "sexo_columna": sexo_c,
        "edad_columna": edad_c,
        "zona_columna": zona_c,
        "sexo": {},
        "edad": {},
        "zona": {},
    }

    def _conteo(columna: str | None) -> dict[str, int]:
        if columna is None:
            return {}
        filas = (
            personas.groupBy(_norm_cat(columna).alias("v"))
            .count()
            .collect()
        )
        return {("" if r["v"] is None else str(r["v"])): int(r["count"]) for r in filas}

    out["sexo"] = _conteo(sexo_c)
    out["edad"] = _conteo(edad_c)
    out["zona"] = _conteo(zona_c)

    def _ok(obs: dict, permitidos: frozenset) -> bool:
        presentes = {k for k in obs if k not in {"", "None", "null", "nan"}}
        return bool(presentes) and presentes <= permitidos

    sexo_ok = _ok(out["sexo"], SEXO_DANE)
    edad_ok = _ok(out["edad"], EDAD_DANE)
    zona_vals = {k for k in out["zona"] if k not in {"", "None", "null", "nan"}}
    zona_ok = bool(zona_vals) and (
        zona_vals <= ZONA_DANE or zona_vals <= ZONA_CABECERA_RESTO or zona_vals <= (ZONA_DANE | ZONA_CABECERA_RESTO)
    )
    out["categorias_sexo_ok"] = sexo_ok
    out["categorias_edad_ok"] = edad_ok
    out["categorias_zona_ok"] = zona_ok
    return out


def _sumas_categoria(columna: str | None, pares: list[tuple[str, object]]):
    """pares: (alias, condición o conjunto de códigos)."""
    exprs = []
    if columna is None:
        for alias, _ in pares:
            exprs.append(F.lit(0).cast("long").alias(alias))
        return exprs
    v = _norm_cat(columna)
    nulo = v.isNull() | (v == "") | v.isin("None", "null", "nan")
    cubiertos = []
    for alias, cond in pares:
        if cond == "nulo":
            exprs.append(F.sum(F.when(nulo, 1).otherwise(0)).cast("long").alias(alias))
        elif cond == "otro":
            continue
        elif isinstance(cond, (set, frozenset)):
            cubiertos.extend(list(cond))
            exprs.append(
                F.sum(F.when((~nulo) & v.isin(list(cond)), 1).otherwise(0))
                .cast("long")
                .alias(alias)
            )
        else:
            cubiertos.append(str(cond))
            exprs.append(
                F.sum(F.when((~nulo) & (v == F.lit(str(cond))), 1).otherwise(0))
                .cast("long")
                .alias(alias)
            )
    otros_alias = [a for a, c in pares if c == "otro"]
    if otros_alias:
        exprs.append(
            F.sum(
                F.when((~nulo) & (~v.isin(cubiertos if cubiertos else ["__ninguno__"])), 1).otherwise(0)
            )
            .cast("long")
            .alias(otros_alias[0])
        )
    return exprs


def poblacion_municipal(personas_parquet: DataFrame, dim_municipio: DataFrame) -> DataFrame:
    """Una fila por municipio 2018. LEFT JOIN a DIVIPOLA. No tira códigos huérfanos."""
    base = codigo_municipio(personas_parquet)
    sexo_c = _primera_columna(base, ("P_SEXO", "sexo"))
    edad_c = _primera_columna(base, ("P_EDADR", "edad_grupo"))
    zona_c = _primera_columna(base, ("UA_CLASE", "zona"))

    aggs = [F.count(F.lit(1)).cast("long").alias("poblacion")]
    aggs += _sumas_categoria(
        sexo_c,
        [("pob_hombres", "1"), ("pob_mujeres", "2"), ("pob_sexo_nulo", "nulo"), ("pob_sexo_otro", "otro")],
    )
    aggs += _sumas_categoria(
        edad_c,
        [
            ("pob_0_14", EDAD_0_14),
            ("pob_15_64", EDAD_15_64),
            ("pob_65_mas", EDAD_65_MAS),
            ("pob_edad_nulo", "nulo"),
            ("pob_edad_otro", "otro"),
        ],
    )
    aggs += _sumas_categoria(
        zona_c,
        [
            ("pob_cabecera", "1"),
            ("pob_centro_poblado", "2"),
            ("pob_rural_disperso", "3"),
            ("pob_resto", "4"),
            ("pob_zona_nulo", "nulo"),
            ("pob_zona_otro", "otro"),
        ],
    )
    via = F.first("via_codigo")
    mun = (
        base.groupBy("cod_municipio")
        .agg(*aggs, via.alias("via_codigo"))
        .withColumn("anio", F.lit(ANIO_CENSO).cast("int"))
        .withColumn("fuente", F.lit(FUENTE))
        .withColumn("origen", F.lit(RUTA_PARQUET_DEFAULT))
    )

    dim = (
        dim_municipio.select(
            F.lpad(F.col("cod_municipio").cast("string"), 5, "0").alias("_cod_dim"),
            F.col("nombre_municipio").alias("nombre_municipio_divipola"),
            F.col("nombre_departamento").alias("nombre_departamento_divipola"),
        )
        .dropDuplicates(["_cod_dim"])
    )
    out = mun.join(F.broadcast(dim), mun["cod_municipio"] == dim["_cod_dim"], "left").drop("_cod_dim")
    out = out.withColumn("en_divipola", F.col("nombre_municipio_divipola").isNotNull())
    out = out.withColumn(
        "estado_homologacion",
        F.when(F.col("cod_municipio").isNull() | (F.trim(F.col("cod_municipio")) == ""), "codigo_vacio")
        .when(F.col("en_divipola"), F.lit("homologado"))
        .otherwise(F.lit("no_homologado")),
    )
    out = out.withColumn("es_bogota", F.col("cod_municipio") == F.lit("11001"))
    return out


def transformar_dane(personas: DataFrame, dim_municipio: DataFrame) -> tuple[DataFrame, dict]:
    """Pipeline completo. Devuelve el derivado municipal y la inspección de categorías."""
    cats = inspeccionar_categorias(personas)
    pob = poblacion_municipal(personas, dim_municipio)
    pob = (
        pob.withColumn("categorias_sexo_ok", F.lit(bool(cats["categorias_sexo_ok"])))
        .withColumn("categorias_edad_ok", F.lit(bool(cats["categorias_edad_ok"])))
        .withColumn("categorias_zona_ok", F.lit(bool(cats["categorias_zona_ok"])))
    )
    if not cats["categorias_sexo_ok"]:
        for c in ("pob_hombres", "pob_mujeres", "pob_sexo_nulo", "pob_sexo_otro"):
            pob = pob.withColumn(c, F.lit(None).cast("long"))
    if not cats["categorias_edad_ok"]:
        for c in ("pob_0_14", "pob_15_64", "pob_65_mas", "pob_edad_nulo", "pob_edad_otro"):
            pob = pob.withColumn(c, F.lit(None).cast("long"))
    if not cats["categorias_zona_ok"]:
        for c in (
            "pob_cabecera",
            "pob_centro_poblado",
            "pob_rural_disperso",
            "pob_resto",
            "pob_zona_nulo",
            "pob_zona_otro",
        ):
            pob = pob.withColumn(c, F.lit(None).cast("long"))
    return pob, cats


def invariantes_poblacion(pob: DataFrame, n_personas: int) -> list[str]:
    fallos = []
    n = pob.count()
    n_id = pob.select("anio", "cod_municipio").distinct().count()
    if n != n_id:
        fallos.append(f"municipio no único: {n} filas, {n_id} claves")
    if pob.filter(F.col("cod_municipio").isNull() | (F.trim(F.col("cod_municipio")) == "")).count() > 0:
        fallos.append("cod_municipio vacío")
    if pob.filter(F.col("poblacion") < 0).count() > 0:
        fallos.append("población negativa")
    suma = pob.agg(F.sum("poblacion").alias("s")).collect()[0]["s"]
    if int(suma or 0) != int(n_personas):
        fallos.append(f"suma población {suma} ≠ personas parquet {n_personas}")
    if pob.filter(F.col("anio") != F.lit(ANIO_CENSO)).count() > 0:
        fallos.append("anio distinto de 2018")
    return fallos
