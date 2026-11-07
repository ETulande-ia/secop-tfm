"""
Rutas del corpus documental y de las salidas RAG, relativas a secop-tfm.

Funciones:
- raiz_repo(): Resuelve la raíz del repositorio.
- ruta_originales(): Directorio de los documentos originales.
- ruta_salidas_rag(): Directorio de salidas RAG.
- sincronizar_originales(): Copia los originales desde el corpus de Windows, si existe.
"""

from __future__ import annotations

from pathlib import Path

ORIGEN_WINDOWS = Path(r"C:\Repositorios\tfm\corpus")
ARCHIVOS_ORIGEN = (
    "CCE-MINIMA-CUANTIA-2024.pdf",
    "cce-eicp-ma-04._manual_requisitos_habilitantes_v3_29-09-2023.pdf",
    "DiccionarioDeDatosAbiertos.pdf",
    "Guia-Proceso-Sancionatorio-Vs2-OrigFirmado-2.pdf",
    "expresiones_ciudadanas_simuladas_TFM.xlsx",
)


def raiz_repo() -> Path:
    # src/rag/rutas.py → rag, src, raíz del proyecto.
    return Path(__file__).resolve().parents[2]


def ruta_originales() -> Path:
    return raiz_repo() / "data" / "corpus" / "originales"


def ruta_salidas_rag() -> Path:
    return raiz_repo() / "notebooks" / "salidas" / "rag"


def sincronizar_originales(origen: Path | None = None) -> dict:
    """Copia los archivos fuente al árbol del repo, sin alterar el directorio de origen."""
    import shutil

    dest = ruta_originales()
    dest.mkdir(parents=True, exist_ok=True)
    src = Path(origen) if origen else ORIGEN_WINDOWS
    copiados = []
    ausentes = []
    if src.exists():
        for nombre in ARCHIVOS_ORIGEN:
            f = src / nombre
            if not f.is_file():
                ausentes.append(nombre)
                continue
            shutil.copy2(f, dest / nombre)
            copiados.append(nombre)
    existentes = sorted(p.name for p in dest.iterdir() if p.is_file())
    return {
        "origen": str(src),
        "origen_existe": src.exists(),
        "destino": str(dest),
        "copiados": copiados,
        "ausentes_en_origen": ausentes,
        "en_destino": existentes,
    }
