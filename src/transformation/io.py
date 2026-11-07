"""
Lee MongoDB y DIVIPOLA, y escribe el esquema tfm tras validar el staging.

Funciones:
- leer_procesos_filas(): Lee las filas de procesos del periodo.
- leer_contratos(): Lee los contratos del periodo.
- leer_cnpv_parquet(): Lee el Parquet del CNPV.
- leer_dim_municipio(): Lee el catálogo DIVIPOLA.
- escribir_tabla_tfm(): Escribe una tabla del esquema tfm.
- publicar_periodo_procesos(): Publica procesos si el staging es válido.
- publicar_periodo_contratos(): Publica contratos si el staging es válido.
- publicar_poblacion(): Publica la población si el staging es válido.
- verificar_integridad_pg(): Contrasta los conteos persistidos.
"""

from __future__ import annotations

import os
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

COLECCION_PROCESOS = "procesos_filas_api"
COLECCION_CONTRATOS = "contratos_electronicos_raw"
DB_MONGO = os.getenv("MONGO_DB", "secop")

SQL_ESQUEMA_PROCESOS = (
    Path(__file__).resolve().parents[2] / "sql" / "001_esquema_tfm_procesos.sql"
)
SQL_ESQUEMA_CONTRATOS = (
    Path(__file__).resolve().parents[2] / "sql" / "002_esquema_tfm_contratos.sql"
)
SQL_ESQUEMA_POBLACION = (
    Path(__file__).resolve().parents[2] / "sql" / "003_esquema_tfm_poblacion.sql"
)

TABLAS_TFM = {
    "proceso",
    "adjudicacion",
    "adjudicacion_ambigua",
    "proceso_control",
    "stg_proceso",
    "stg_adjudicacion",
    "stg_adjudicacion_ambigua",
    "contrato",
    "contrato_control",
    "stg_contrato",
    "poblacion_municipal",
    "poblacion_control",
    "stg_poblacion_municipal",
}

TABLAS_STAGING = ("stg_adjudicacion", "stg_adjudicacion_ambigua", "stg_proceso")
TABLAS_STAGING_CONTRATOS = ("stg_contrato",)
TABLAS_STAGING_POBLACION = ("stg_poblacion_municipal",)
TABLAS_PERIODO = (
    "adjudicacion",
    "adjudicacion_ambigua",
    "proceso",
    "contrato",
    "poblacion_municipal",
)
STG_A_DEFINITIVA = {
    "stg_proceso": "proceso",
    "stg_adjudicacion": "adjudicacion",
    "stg_adjudicacion_ambigua": "adjudicacion_ambigua",
    "stg_contrato": "contrato",
    "stg_poblacion_municipal": "poblacion_municipal",
}

COLUMNAS = {
    "proceso": [
        "periodo",
        "id_del_proceso",
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
        "referencia_del_proceso",
        "duracion",
        "unidad_de_duracion",
        "ciudad_de_la_unidad_de",
        "url_proceso",
        "n_filas_api",
        "n_socrata_id",
        "socrata_ids",
        "campos_variables",
        "hay_campos_variables",
        "es_bogota",
        "cod_municipio",
        "estado_homologacion",
        "via_homologacion",
        "nombre_municipio_divipola",
        "nombre_departamento_divipola",
        "departamento_entidad_ausente",
        "ciudad_entidad_ausente",
        "entidad_ausente",
        "adjudicado_ausente",
        "precio_base_cero",
        "precio_base_negativo",
        "precio_base_extremo",
    ],
    "adjudicacion": [
        "periodo",
        "id_del_proceso",
        "id_adjudicacion",
        "tipo_grano",
        "n_proveedores",
        "n_valores",
        "n_filas_api",
        "codigo_proveedor",
        "nombre_del_proveedor",
        "valor_total_adjudicacion",
        "valor_usable",
        "proveedores",
        "valores",
        "socrata_ids",
        "valor_total_adjudicacion_cero",
        "valor_total_adjudicacion_negativo",
        "valor_total_adjudicacion_extremo",
    ],
    "adjudicacion_ambigua": [
        "periodo",
        "id_del_proceso",
        "id_adjudicacion",
        "n_filas_api",
        "n_proveedores",
        "n_valores",
        "n_filas",
        "n_prov",
        "n_val",
        "proveedores",
        "valores",
        "socrata_ids",
        "cartesiano",
        "sin_awd",
        "motivo",
        "suma_valores",
    ],
    "proceso_control": [
        "periodo",
        "corrida_ts",
        "control",
        "observado",
        "esperado",
        "diferencia",
        "ok",
        "nota",
        "escribir",
    ],
    "contrato": [
        "periodo",
        "id_contrato",
        "socrata_id",
        "n_filas_api",
        "n_socrata_id",
        "socrata_ids",
        "campos_variables",
        "hay_campos_variables",
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
        "valor_del_contrato_cero",
        "valor_del_contrato_negativo",
        "valor_del_contrato_extremo",
        "valor_usable",
        "valor_apto_modelo",
        "referencia_del_contrato",
        "descripcion_del_proceso",
        "codigo_de_categoria_principal",
        "duracion_del_contrato",
        "es_pyme",
        "es_grupo",
        "url_contrato",
        "es_bogota",
        "cod_municipio",
        "estado_homologacion",
        "via_homologacion",
        "nombre_municipio_divipola",
        "nombre_departamento_divipola",
        "departamento_ausente",
        "ciudad_ausente",
        "nombre_entidad_ausente",
        "proveedor_adjudicado_ausente",
        "modalidad_de_contratacion_ausente",
    ],
    "contrato_control": [
        "periodo",
        "corrida_ts",
        "control",
        "observado",
        "esperado",
        "diferencia",
        "ok",
        "nota",
        "escribir",
    ],
    "poblacion_municipal": [
        "anio",
        "cod_municipio",
        "poblacion",
        "en_divipola",
        "estado_homologacion",
        "via_codigo",
        "fuente",
        "origen",
        "nombre_municipio_divipola",
        "nombre_departamento_divipola",
        "es_bogota",
        "pob_hombres",
        "pob_mujeres",
        "pob_sexo_nulo",
        "pob_sexo_otro",
        "pob_0_14",
        "pob_15_64",
        "pob_65_mas",
        "pob_edad_nulo",
        "pob_edad_otro",
        "pob_cabecera",
        "pob_centro_poblado",
        "pob_rural_disperso",
        "pob_resto",
        "pob_zona_nulo",
        "pob_zona_otro",
        "categorias_sexo_ok",
        "categorias_edad_ok",
        "categorias_zona_ok",
    ],
    "poblacion_control": [
        "anio",
        "corrida_ts",
        "control",
        "observado",
        "esperado",
        "diferencia",
        "ok",
        "nota",
        "escribir",
    ],
}


def mongo_uri() -> str:
    uri = os.environ.get("MONGO_URI", "").strip()
    if not uri:
        raise RuntimeError("Falta MONGO_URI en el entorno.")
    return uri


def mongo_db() -> str:
    return os.environ.get("MONGO_DB", DB_MONGO)


def opciones_jdbc() -> dict:
    """Opciones JDBC desde el entorno. No hay contraseñas en el código."""
    host = os.environ.get("PGHOST", "tfm-postgres-db")
    port = os.environ.get("PGPORT", "5432")
    db = os.environ.get("PGDATABASE", "analytics")
    user = os.environ.get("PGUSER", "").strip()
    password = os.environ.get("PGPASSWORD", "")
    if not user:
        raise RuntimeError("Falta PGUSER en el entorno (no se usan credenciales del prototipo).")
    if not password:
        raise RuntimeError("Falta PGPASSWORD en el entorno.")
    return {
        "url": f"jdbc:postgresql://{host}:{port}/{db}",
        "user": user,
        "password": password,
        "driver": "org.postgresql.Driver",
    }


def leer_mongo(spark: SparkSession, coleccion: str, periodo: str | None = None) -> DataFrame:
    if coleccion in {"procesos_raw", "contratos_raw", "cnpv2018_personas"}:
        raise ValueError(f"Colección no permitida como fuente de transformación: {coleccion}")
    df = (
        spark.read.format("mongodb")
        .option("spark.mongodb.read.connection.uri", mongo_uri())
        .option("spark.mongodb.read.database", mongo_db())
        .option("spark.mongodb.read.collection", coleccion)
        .load()
    )
    if "_id" in df.columns:
        df = df.drop("_id")
    if periodo is not None:
        if "_periodo" not in df.columns:
            raise RuntimeError(f"{coleccion} no tiene _periodo; no se filtra a ciegas.")
        df = df.filter(F.col("_periodo") == periodo)
    return df


def leer_procesos_filas(spark: SparkSession, periodo: str) -> DataFrame:
    return leer_mongo(spark, COLECCION_PROCESOS, periodo)


def leer_contratos(spark: SparkSession, periodo: str) -> DataFrame:
    return leer_mongo(spark, COLECCION_CONTRATOS, periodo)


def leer_cnpv_parquet(spark: SparkSession) -> DataFrame:
    """Lee el parquet CNPV 2018. No usa Mongo ni fact_poblacion."""
    ruta = os.environ.get("CNPV_PARQUET", "/datalake/cnpv2018/personas").strip()
    if not ruta:
        raise RuntimeError("Falta CNPV_PARQUET.")
    return spark.read.parquet(ruta)


def leer_dim_municipio(spark: SparkSession) -> DataFrame:
    opts = opciones_jdbc()
    df = (
        spark.read.format("jdbc")
        .option("url", opts["url"])
        .option("dbtable", "public.dim_municipio")
        .option("user", opts["user"])
        .option("password", opts["password"])
        .option("driver", opts["driver"])
        .load()
    )
    return df.filter(F.col("cod_municipio") != "00000")


def _credenciales_pg() -> dict:
    host = os.environ.get("PGHOST", "tfm-postgres-db")
    port = os.environ.get("PGPORT", "5432")
    db = os.environ.get("PGDATABASE", "analytics")
    user = os.environ.get("PGUSER", "").strip()
    password = os.environ.get("PGPASSWORD", "")
    if not user or not password:
        raise RuntimeError("Faltan PGUSER/PGPASSWORD para PostgreSQL.")
    return {"host": host, "port": port, "dbname": db, "user": user, "password": password}


def _conexion_pg():
    import psycopg2

    return psycopg2.connect(**_credenciales_pg())


def _tabla_tfm(nombre_tabla: str) -> str:
    if "." in nombre_tabla:
        esquema, tabla = nombre_tabla.split(".", 1)
    else:
        esquema, tabla = "tfm", nombre_tabla
    if esquema != "tfm":
        raise ValueError(f"Solo se escribe en el esquema tfm, no en {esquema}.")
    if tabla not in TABLAS_TFM:
        raise ValueError(f"Tabla no prevista: {tabla}")
    return tabla


def asegurar_esquema_tfm() -> None:
    """CREATE SCHEMA IF NOT EXISTS tfm. No toca public."""
    conn = _conexion_pg()
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("CREATE SCHEMA IF NOT EXISTS tfm")
    finally:
        conn.close()


def aplicar_sql_tfm(ruta: Path | None = None) -> None:
    """Crea esquema y tablas del script versionado. Idempotente. No toca public."""
    path = Path(ruta) if ruta is not None else SQL_ESQUEMA_PROCESOS
    if not path.is_file():
        raise FileNotFoundError(f"No está el script SQL: {path}")
    sql_txt = path.read_text(encoding="utf-8")
    conn = _conexion_pg()
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(sql_txt)
    finally:
        conn.close()


def vaciar_staging_procesos() -> None:
    """TRUNCATE de staging. No toca tablas definitivas ni public."""
    conn = _conexion_pg()
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                "TRUNCATE tfm.stg_adjudicacion, tfm.stg_adjudicacion_ambigua, tfm.stg_proceso"
            )
    finally:
        conn.close()


def _tipo_spark_col(nombre: str) -> str:
    """Tipo Spark para columnas ausentes. JDBC no acepta void (NullType)."""
    if nombre in {
        "hay_campos_variables",
        "valor_usable",
        "valor_apto_modelo",
        "es_bogota",
        "adjudicado",
        "cartesiano",
        "sin_awd",
        "escribir",
        "ok",
        "en_divipola",
        "categorias_sexo_ok",
        "categorias_edad_ok",
        "categorias_zona_ok",
    } or nombre.endswith(
        ("_ausente", "_cero", "_negativo", "_extremo")
    ):
        return "boolean"
    if nombre in {
        "n_filas_api",
        "n_socrata_id",
        "n_proveedores",
        "n_valores",
        "n_filas",
        "n_prov",
        "n_val",
        "observado",
        "esperado",
        "diferencia",
        "poblacion",
        "anio",
    } or nombre.startswith("pob_"):
        return "long"
    if nombre in {
        "valor_del_contrato",
        "precio_base",
        "valor_total_adjudicacion",
        "suma_valores",
    }:
        return "double"
    if "fecha" in nombre or nombre == "corrida_ts":
        return "timestamp"
    return "string"


def seleccionar_columnas(df: DataFrame, tabla: str, periodo: str) -> DataFrame:
    """Alinea el DataFrame a las columnas del script SQL."""
    nombre = _tabla_tfm(tabla)
    clave = STG_A_DEFINITIVA.get(nombre, nombre)
    cols = COLUMNAS[clave]
    out = df
    if "periodo" in cols and "periodo" not in out.columns:
        if "_periodo" in out.columns:
            out = out.withColumnRenamed("_periodo", "periodo")
        else:
            out = out.withColumn("periodo", F.lit(periodo))
    if "anio" in cols and "anio" not in out.columns:
        anio = int(str(periodo)[:4]) if str(periodo)[:4].isdigit() else 2018
        out = out.withColumn("anio", F.lit(anio))
    for c in cols:
        if c not in out.columns:
            out = out.withColumn(c, F.lit(None).cast(_tipo_spark_col(c)))
    nulos = [f.name for f in out.schema.fields if f.dataType.simpleString() == "void"]
    for c in nulos:
        out = out.withColumn(c, F.col(c).cast(_tipo_spark_col(c)))
    return out.select(*cols)


def escribir_tabla_tfm(df: DataFrame, nombre_tabla: str, modo: str = "append") -> None:
    """Append JDBC solo a staging o a proceso_control. Nunca overwrite."""
    if modo != "append":
        raise ValueError(
            "Solo se permite append. Las definitivas se publican con persistir_periodo_procesos."
        )
    tabla = _tabla_tfm(nombre_tabla)
    if tabla in TABLAS_PERIODO:
        raise ValueError(
            f"No se escribe JDBC en tfm.{tabla}. Use staging y tfm.publicar_periodo_procesos."
        )
    opts = opciones_jdbc()
    (
        df.write.format("jdbc")
        .option("url", opts["url"])
        .option("dbtable", f"tfm.{tabla}")
        .option("user", opts["user"])
        .option("password", opts["password"])
        .option("driver", opts["driver"])
        .option("batchsize", "10000")
        .mode("append")
        .save()
    )


def validar_staging_procesos(
    periodo: str, n_proceso: int, n_adj: int, n_amb: int
) -> list[dict]:
    conn = _conexion_pg()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT control, observado, esperado, ok, nota "
                "FROM tfm.validar_stg_procesos(%s, %s, %s, %s)",
                (periodo, n_proceso, n_adj, n_amb),
            )
            filas = []
            for control, observado, esperado, ok, nota in cur.fetchall():
                filas.append(
                    {
                        "control": control,
                        "observado": None if observado is None else int(observado),
                        "esperado": None if esperado is None else int(esperado),
                        "ok": ok,
                        "nota": nota,
                    }
                )
            return filas
    finally:
        conn.close()


def staging_ok(filas: list[dict]) -> bool:
    return all(f["ok"] is True for f in filas)


def _filas_control(control: DataFrame) -> list[tuple]:
    out = []
    for row in control.collect():
        d = row.asDict()
        out.append(
            (
                d.get("periodo"),
                d.get("corrida_ts"),
                d.get("control"),
                d.get("observado"),
                d.get("esperado"),
                d.get("diferencia"),
                d.get("ok"),
                d.get("nota"),
                d.get("escribir"),
            )
        )
    return out


def _tuples_validacion(periodo, corrida_ts, escribir, validacion: list[dict]) -> list[tuple]:
    filas = []
    for f in validacion:
        obs = f["observado"]
        exp = f["esperado"]
        dif = None if obs is None or exp is None else obs - exp
        filas.append(
            (
                periodo,
                corrida_ts,
                f["control"],
                obs,
                exp,
                dif,
                f["ok"],
                f["nota"],
                escribir,
            )
        )
    return filas


def publicar_periodo_procesos(
    periodo: str,
    control: DataFrame,
    validacion: list[dict] | None = None,
    n_proceso: int | None = None,
    n_adj: int | None = None,
    n_amb: int | None = None,
) -> None:
    """Reemplaza solo el periodo en definitivas. Rollback si algo falla."""
    filas_ctrl = _filas_control(control)
    if validacion and filas_ctrl:
        filas_ctrl.extend(
            _tuples_validacion(
                periodo, filas_ctrl[0][1], filas_ctrl[0][8], validacion
            )
        )
    conn = _conexion_pg()
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute("SELECT tfm.publicar_periodo_procesos(%s)", (periodo,))
            if n_proceso is not None:
                cur.execute(
                    "SELECT count(*) FROM tfm.proceso WHERE periodo = %s", (periodo,)
                )
                if int(cur.fetchone()[0]) != int(n_proceso):
                    raise RuntimeError("conteo tfm.proceso distinto de Spark tras INSERT")
            if n_adj is not None:
                cur.execute(
                    "SELECT count(*) FROM tfm.adjudicacion WHERE periodo = %s",
                    (periodo,),
                )
                if int(cur.fetchone()[0]) != int(n_adj):
                    raise RuntimeError("conteo tfm.adjudicacion distinto de Spark tras INSERT")
            if n_amb is not None:
                cur.execute(
                    "SELECT count(*) FROM tfm.adjudicacion_ambigua WHERE periodo = %s",
                    (periodo,),
                )
                if int(cur.fetchone()[0]) != int(n_amb):
                    raise RuntimeError(
                        "conteo tfm.adjudicacion_ambigua distinto de Spark tras INSERT"
                    )
            cur.executemany(
                """
                INSERT INTO tfm.proceso_control
                    (periodo, corrida_ts, control, observado, esperado,
                     diferencia, ok, nota, escribir)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                filas_ctrl,
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def persistir_periodo_procesos(
    proceso: DataFrame,
    adjudicacion: DataFrame,
    ambigua: DataFrame,
    control: DataFrame,
    periodo: str,
) -> dict:
    """Staging JDBC → validar → publicación transaccional del periodo.

    Si la validación o el INSERT fallan, las tablas definitivas no cambian.
    """
    aplicar_sql_tfm()
    vaciar_staging_procesos()
    escribir_tabla_tfm(seleccionar_columnas(proceso, "proceso", periodo), "stg_proceso")
    escribir_tabla_tfm(
        seleccionar_columnas(adjudicacion, "adjudicacion", periodo), "stg_adjudicacion"
    )
    escribir_tabla_tfm(
        seleccionar_columnas(ambigua, "adjudicacion_ambigua", periodo),
        "stg_adjudicacion_ambigua",
    )
    n_proceso = proceso.count()
    n_adj = adjudicacion.count()
    n_amb = ambigua.count()
    validacion = validar_staging_procesos(periodo, n_proceso, n_adj, n_amb)
    if not staging_ok(validacion):
        fallos = [f["control"] for f in validacion if f["ok"] is not True]
        raise RuntimeError(
            "Validación de staging fallida. No se publica: " + ", ".join(fallos)
        )
    publicar_periodo_procesos(
        periodo, control, validacion, n_proceso, n_adj, n_amb
    )
    return {"validacion_stg": validacion, "publicado": True}


def vaciar_staging_contratos() -> None:
    conn = _conexion_pg()
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("TRUNCATE tfm.stg_contrato")
    finally:
        conn.close()


def validar_staging_contratos(periodo: str, n_contrato: int) -> list[dict]:
    conn = _conexion_pg()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT control, observado, esperado, ok, nota "
                "FROM tfm.validar_stg_contratos(%s, %s)",
                (periodo, n_contrato),
            )
            filas = []
            for control, observado, esperado, ok, nota in cur.fetchall():
                filas.append(
                    {
                        "control": control,
                        "observado": None if observado is None else int(observado),
                        "esperado": None if esperado is None else int(esperado),
                        "ok": ok,
                        "nota": nota,
                    }
                )
            return filas
    finally:
        conn.close()


def _conteos_procesos_tfm() -> dict:
    conn = _conexion_pg()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  (SELECT count(*) FROM tfm.proceso) AS proceso,
                  (SELECT count(*) FROM tfm.adjudicacion) AS adjudicacion,
                  (SELECT count(*) FROM tfm.adjudicacion_ambigua) AS ambigua
                """
            )
            p, a, b = cur.fetchone()
            return {"proceso": int(p), "adjudicacion": int(a), "adjudicacion_ambigua": int(b)}
    finally:
        conn.close()


def publicar_periodo_contratos(
    periodo: str,
    control: DataFrame,
    validacion: list[dict] | None = None,
    n_contrato: int | None = None,
) -> None:
    filas_ctrl = _filas_control(control)
    if validacion and filas_ctrl:
        filas_ctrl.extend(
            _tuples_validacion(periodo, filas_ctrl[0][1], filas_ctrl[0][8], validacion)
        )
    conn = _conexion_pg()
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute("SELECT tfm.publicar_periodo_contratos(%s)", (periodo,))
            if n_contrato is not None:
                cur.execute(
                    "SELECT count(*) FROM tfm.contrato WHERE periodo = %s", (periodo,)
                )
                if int(cur.fetchone()[0]) != int(n_contrato):
                    raise RuntimeError("conteo tfm.contrato distinto de Spark tras INSERT")
            cur.executemany(
                """
                INSERT INTO tfm.contrato_control
                    (periodo, corrida_ts, control, observado, esperado,
                     diferencia, ok, nota, escribir)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                filas_ctrl,
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def persistir_periodo_contratos(
    contrato: DataFrame,
    control: DataFrame,
    periodo: str,
) -> dict:
    """Staging JDBC → validar → publicar solo tfm.contrato del periodo.

    No toca tfm.proceso / adjudicacion. Si falla, el estado anterior se conserva.
    """
    antes = _conteos_procesos_tfm()
    aplicar_sql_tfm(SQL_ESQUEMA_CONTRATOS)
    vaciar_staging_contratos()
    escribir_tabla_tfm(seleccionar_columnas(contrato, "contrato", periodo), "stg_contrato")
    n_contrato = contrato.count()
    validacion = validar_staging_contratos(periodo, n_contrato)
    if not staging_ok(validacion):
        fallos = [f["control"] for f in validacion if f["ok"] is not True]
        raise RuntimeError(
            "Validación de staging contratos fallida. No se publica: " + ", ".join(fallos)
        )
    publicar_periodo_contratos(periodo, control, validacion, n_contrato)
    despues = _conteos_procesos_tfm()
    if antes != despues:
        raise RuntimeError(
            "Las tablas de procesos cambiaron al persistir contratos: "
            f"antes={antes} despues={despues}"
        )
    return {"validacion_stg": validacion, "publicado": True, "procesos_intactos": despues}


def vaciar_staging_poblacion() -> None:
    conn = _conexion_pg()
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("TRUNCATE tfm.stg_poblacion_municipal")
    finally:
        conn.close()


def validar_staging_poblacion(anio: int, n_personas: int) -> list[dict]:
    conn = _conexion_pg()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT control, observado, esperado, ok, nota "
                "FROM tfm.validar_stg_poblacion(%s, %s)",
                (anio, n_personas),
            )
            filas = []
            for control, observado, esperado, ok, nota in cur.fetchall():
                filas.append(
                    {
                        "control": control,
                        "observado": None if observado is None else int(observado),
                        "esperado": None if esperado is None else int(esperado),
                        "ok": ok,
                        "nota": nota,
                    }
                )
            return filas
    finally:
        conn.close()


def _conteos_secop_tfm() -> dict:
    """Conteos de procesos y contratos. DANE no debe modificarlos."""
    conn = _conexion_pg()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  (SELECT count(*) FROM tfm.proceso) AS proceso,
                  (SELECT count(*) FROM tfm.adjudicacion) AS adjudicacion,
                  (SELECT count(*) FROM tfm.adjudicacion_ambigua) AS ambigua,
                  (SELECT count(*) FROM tfm.contrato) AS contrato
                """
            )
            p, a, b, c = cur.fetchone()
            return {
                "proceso": int(p),
                "adjudicacion": int(a),
                "adjudicacion_ambigua": int(b),
                "contrato": int(c),
            }
    finally:
        conn.close()


def _filas_control_anio(control: DataFrame) -> list[tuple]:
    out = []
    for row in control.collect():
        d = row.asDict()
        out.append(
            (
                int(d.get("anio")),
                d.get("corrida_ts"),
                d.get("control"),
                d.get("observado"),
                d.get("esperado"),
                d.get("diferencia"),
                d.get("ok"),
                d.get("nota"),
                d.get("escribir"),
            )
        )
    return out


def _tuples_validacion_anio(anio, corrida_ts, escribir, validacion: list[dict]) -> list[tuple]:
    filas = []
    for f in validacion:
        obs = f["observado"]
        exp = f["esperado"]
        dif = None if obs is None or exp is None else obs - exp
        filas.append(
            (
                anio,
                corrida_ts,
                f["control"],
                obs,
                exp,
                dif,
                f["ok"],
                f["nota"],
                escribir,
            )
        )
    return filas


def publicar_poblacion(
    anio: int,
    control: DataFrame,
    validacion: list[dict] | None = None,
    n_municipios: int | None = None,
) -> None:
    filas_ctrl = _filas_control_anio(control)
    if validacion and filas_ctrl:
        filas_ctrl.extend(
            _tuples_validacion_anio(anio, filas_ctrl[0][1], filas_ctrl[0][8], validacion)
        )
    conn = _conexion_pg()
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute("SELECT tfm.publicar_poblacion(%s)", (anio,))
            if n_municipios is not None:
                cur.execute(
                    "SELECT count(*) FROM tfm.poblacion_municipal WHERE anio = %s",
                    (anio,),
                )
                if int(cur.fetchone()[0]) != int(n_municipios):
                    raise RuntimeError(
                        "conteo tfm.poblacion_municipal distinto de Spark tras INSERT"
                    )
            cur.executemany(
                """
                INSERT INTO tfm.poblacion_control
                    (anio, corrida_ts, control, observado, esperado,
                     diferencia, ok, nota, escribir)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                filas_ctrl,
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def persistir_poblacion(
    poblacion: DataFrame,
    control: DataFrame,
    anio: int,
    n_personas: int,
) -> dict:
    """Staging JDBC → validar → publicar solo tfm.poblacion_municipal del año.

    No toca procesos ni contratos. Si falla, el estado anterior se conserva.
    """
    antes = _conteos_secop_tfm()
    aplicar_sql_tfm(SQL_ESQUEMA_POBLACION)
    vaciar_staging_poblacion()
    escribir_tabla_tfm(
        seleccionar_columnas(poblacion, "poblacion_municipal", str(anio)),
        "stg_poblacion_municipal",
    )
    n_mun = poblacion.count()
    validacion = validar_staging_poblacion(anio, n_personas)
    if not staging_ok(validacion):
        fallos = [f["control"] for f in validacion if f["ok"] is not True]
        raise RuntimeError(
            "Validación de staging población fallida. No se publica: " + ", ".join(fallos)
        )
    publicar_poblacion(anio, control, validacion, n_mun)
    despues = _conteos_secop_tfm()
    if antes != despues:
        raise RuntimeError(
            "Las tablas SECOP cambiaron al persistir DANE: "
            f"antes={antes} despues={despues}"
        )
    return {"validacion_stg": validacion, "publicado": True, "secop_intactos": despues}


def leer_tabla_tfm(
    spark: SparkSession,
    tabla: str,
    periodo: str | None = None,
    col_tiempo: str = "periodo",
) -> DataFrame:
    nombre = _tabla_tfm(tabla)
    opts = opciones_jdbc()
    df = (
        spark.read.format("jdbc")
        .option("url", opts["url"])
        .option("dbtable", f"tfm.{nombre}")
        .option("user", opts["user"])
        .option("password", opts["password"])
        .option("driver", opts["driver"])
        .load()
    )
    if periodo is not None and col_tiempo in df.columns:
        if col_tiempo == "anio":
            df = df.filter(F.col(col_tiempo) == int(periodo))
        else:
            df = df.filter(F.col(col_tiempo) == periodo)
    return df


def verificar_integridad_pg(periodo: str) -> list[dict]:
    """Solape, huérfanos y conteo de periodos ajenos en tablas definitivas."""
    conn = _conexion_pg()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  (SELECT count(*) FROM tfm.adjudicacion a
                     JOIN tfm.adjudicacion_ambigua b
                       ON a.periodo = b.periodo
                      AND a.id_del_proceso = b.id_del_proceso
                      AND a.id_adjudicacion = b.id_adjudicacion
                    WHERE a.periodo = %s) AS solape,
                  (SELECT count(*) FROM tfm.adjudicacion a
                     LEFT JOIN tfm.proceso p
                       ON a.periodo = p.periodo AND a.id_del_proceso = p.id_del_proceso
                    WHERE a.periodo = %s AND p.id_del_proceso IS NULL) AS adj_huerfanas,
                  (SELECT count(*) FROM tfm.adjudicacion_ambigua a
                     LEFT JOIN tfm.proceso p
                       ON a.periodo = p.periodo AND a.id_del_proceso = p.id_del_proceso
                    WHERE a.periodo = %s AND p.id_del_proceso IS NULL) AS amb_huerfanas,
                  (SELECT count(*) FROM tfm.proceso WHERE periodo IS DISTINCT FROM %s) AS otros_proceso,
                  (SELECT count(*) FROM tfm.adjudicacion WHERE periodo IS DISTINCT FROM %s) AS otros_adj,
                  (SELECT count(*) FROM tfm.adjudicacion_ambigua WHERE periodo IS DISTINCT FROM %s) AS otros_amb
                """,
                (periodo, periodo, periodo, periodo, periodo, periodo),
            )
            row = cur.fetchone()
    finally:
        conn.close()
    nombres = [
        "solape_confiable_ambigua",
        "adjudicacion_sin_proceso",
        "ambigua_sin_proceso",
        "proceso_otros_periodos",
        "adjudicacion_otros_periodos",
        "ambigua_otros_periodos",
    ]
    esperados = [0, 0, 0, None, None, None]
    filas = []
    for nombre, obs, exp in zip(nombres, row, esperados):
        filas.append(
            {
                "control": nombre,
                "observado": int(obs),
                "esperado": exp,
                "ok": True if exp is None else int(obs) == exp,
                "nota": "integridad referencial / periodo",
            }
        )
    return filas


def verificar_persistencia(
    spark: SparkSession,
    periodo: str,
    esperado: dict,
    pks: dict | None = None,
    col_tiempo: str = "periodo",
) -> list[dict]:
    """Compara conteos, nulos de PK y unicidad en PostgreSQL vs Spark."""
    if pks is None:
        pks = {
            "proceso": ["periodo", "id_del_proceso"],
            "adjudicacion": ["periodo", "id_del_proceso", "id_adjudicacion"],
            "adjudicacion_ambigua": ["periodo", "id_del_proceso", "id_adjudicacion"],
        }
    filas = []
    for tabla, pk in pks.items():
        df = leer_tabla_tfm(spark, tabla, periodo, col_tiempo=col_tiempo)
        n = df.count()
        n_esp = int(esperado[tabla])
        nulos = 0
        for c in pk:
            nulos += df.filter(F.col(c).isNull() | (F.trim(F.col(c).cast("string")) == "")).count()
        n_clave = df.select(*pk).distinct().count()
        filas.append(
            {
                "tabla": tabla,
                "periodo": periodo,
                "filas_pg": n,
                "filas_spark": n_esp,
                "ok_conteo": n == n_esp,
                "nulos_pk": nulos,
                "ok_nulos": nulos == 0,
                "claves_distintas": n_clave,
                "ok_unicas": n_clave == n,
            }
        )
    return filas
