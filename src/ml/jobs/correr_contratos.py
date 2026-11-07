"""
Ejecuta los experimentos C0–C5 de contratos. No escribe en PostgreSQL.

Funciones:
- main(): Corre la fase experimental del periodo indicado.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2]
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from transformation.spark_sesion import _asegurar_pyspark, crear_spark  # noqa: E402

_asegurar_pyspark()

from ml.experimentos import correr_fase  # noqa: E402


def main() -> None:
    periodo = os.environ.get("PERIODO", "2026-09")
    work = Path("/home/jovyan/work/spark-apps/notebooks")
    if not work.exists():
        work = Path(__file__).resolve().parents[3] / "notebooks"
    salidas = work / "salidas" / "ml" / periodo / "contratos"
    spark = crear_spark("ml-experimentos-contratos")
    try:
        res = correr_fase(spark, periodo, salidas)
    finally:
        spark.stop()
    print("ganador:", res["ganador"])
    print("nota:", res["nota_ganador"])
    print(res["metricas"].to_string(index=False))
    print("salidas:", salidas)


if __name__ == "__main__":
    main()
