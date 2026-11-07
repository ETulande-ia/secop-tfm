"""
Genera la puntuación C1 con Isolation Forest y la publica solo si se pide.

Funciones:
- main(): Lee el periodo y ejecuta la publicación sin escribir por defecto.
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

from ml.publicacion import ejecutar  # noqa: E402


def _bool_env(nombre: str, default: str = "false") -> bool:
    return os.environ.get(nombre, default).strip().lower() in {"1", "true", "yes", "si"}


def main() -> None:
    periodo = os.environ.get("PERIODO", "2026-09")
    escribir = _bool_env("ESCRIBIR", "false")
    work = Path("/home/jovyan/work/spark-apps/notebooks")
    if not work.exists():
        work = Path(__file__).resolve().parents[3] / "notebooks"
    salidas = work / "salidas" / "ml" / periodo / "contratos"
    spark = crear_spark("ml-publicacion-contratos")
    try:
        res = ejecutar(spark, periodo=periodo, escribir=escribir, salidas=salidas)
    finally:
        spark.stop()
    ej = res["ejecucion"]
    print("version:", ej["version_modelo"])
    print("id_ejecucion:", ej["id_ejecucion"])
    print("huella:", ej.get("huella"))
    print("huella_scores:", ej.get("huella_scores"))
    print("n_aptos:", ej["n_aptos"], "n_excluidos:", ej["n_excluidos"])
    print("top1_if:", ej["n_top1_if"], "top5_if:", ej["n_top5_if"])
    print("p99_modalidad:", ej["n_p99_modalidad"])
    print("n_universo:", ej.get("n_universo"))
    print("ESCRIBIR:", escribir, "publicado:", res["publicado"] is not None)
    print("salidas:", salidas)
    pub = res.get("publicado")
    if pub:
        print("ensayo_rollback:", pub.get("ensayo_rollback"))
        print("otras_tablas:", pub.get("otras_tablas_intactas"))
        print("verificacion:", pub.get("verificacion"))


if __name__ == "__main__":
    main()
