"""
Crea la SparkSession local de los notebooks y los jobs.

Funciones:
- crear_spark(): Abre la sesión con los conectores de MongoDB y PostgreSQL.
"""

from __future__ import annotations

import os
import sys


def _asegurar_pyspark() -> None:
    """Añade SPARK_HOME/python al path si el kernel no trae PySpark."""
    try:
        import pyspark  # noqa: F401

        return
    except ImportError:
        pass
    spark_home = os.environ.get("SPARK_HOME", "/usr/local/spark")
    py_dir = os.path.join(spark_home, "python")
    if py_dir not in sys.path:
        sys.path.insert(0, py_dir)
    lib = os.path.join(py_dir, "lib")
    if os.path.isdir(lib):
        for nombre in os.listdir(lib):
            if nombre.startswith("py4j") and nombre.endswith(".zip"):
                ruta = os.path.join(lib, nombre)
                if ruta not in sys.path:
                    sys.path.insert(0, ruta)


def _paquetes_jars() -> str:
    """Conector Mongo y JDBC alineados con la versión de Spark del contenedor."""
    import pyspark

    partes = pyspark.__version__.split(".")
    mayor_menor = f"{partes[0]}.{partes[1]}" if len(partes) >= 2 else "3.4"
    if mayor_menor >= "3.5":
        mongo = "org.mongodb.spark:mongo-spark-connector_2.12:10.4.0"
    else:
        mongo = "org.mongodb.spark:mongo-spark-connector_2.12:10.1.1"
    jdbc = "org.postgresql:postgresql:42.7.3"
    extra = os.environ.get("SPARK_JARS_PACKAGES", "").strip()
    base = f"{mongo},{jdbc}"
    return f"{base},{extra}" if extra else base


def crear_spark(app_name: str):
    """Crea una SparkSession con Mongo y JDBC según el entorno.

    SPARK_MASTER vacío o ausente → local[*] (Jupyter).
    MONGO_URI, PGHOST, PGPASSWORD → conexiones. Nada de credenciales en el código.
    """
    _asegurar_pyspark()
    from pyspark.sql import SparkSession

    master = (os.environ.get("SPARK_MASTER") or "").strip() or "local[*]"
    memoria = os.environ.get("SPARK_DRIVER_MEMORY", "4g")
    uri = os.environ.get("MONGO_URI", "")
    paquetes = _paquetes_jars()

    activa = SparkSession.getActiveSession()
    if activa is not None:
        activa.stop()

    builder = (
        SparkSession.builder.appName(app_name)
        .master(master)
        .config("spark.driver.memory", memoria)
        .config("spark.sql.session.timeZone", "America/Bogota")
        .config("spark.ui.showConsoleProgress", "true")
        .config("spark.jars.packages", paquetes)
    )
    if uri:
        builder = builder.config("spark.mongodb.read.connection.uri", uri)
    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel(os.environ.get("SPARK_LOG_LEVEL", "WARN"))
    return spark
