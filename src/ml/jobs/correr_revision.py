"""
Ejecuta la revisión metodológica de C0–C5. Solo lee tfm.contrato.

Funciones:
- main(): Lanza la revisión del periodo indicado.
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

from ml.revision import revisar  # noqa: E402


def main() -> None:
    periodo = os.environ.get("PERIODO", "2026-09")
    work = Path("/home/jovyan/work/spark-apps/notebooks")
    if not work.exists():
        work = Path(__file__).resolve().parents[3] / "notebooks"
    salidas = work / "salidas" / "ml" / periodo / "contratos"
    spark = crear_spark("ml-revision-contratos")
    try:
        res = revisar(spark, periodo, salidas)
    finally:
        spark.stop()
    print(res["coincidencias"].to_string(index=False))
    print(res["pares"].to_string(index=False))
    print("versiones:", res["versiones"])
    print("salidas:", salidas)


if __name__ == "__main__":
    main()
