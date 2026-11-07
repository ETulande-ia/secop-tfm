"""
Corpus documental y recuperación semántica local. No modifica los PDF ni el orquestador.

Funciones:
- preparar_corpus(): Extrae y fragmenta el corpus.
- validar_fragmentos(): Controla los fragmentos antes de indexar.
- indexar_corpus(): Genera el índice de embeddings.
- buscar(): Recupera fragmentos por similitud.
- evaluar_revision(): Compara estrategias de recuperación.
- evaluar_ampliada(): Evalúa el conjunto ampliado.
- evaluar_cierre(): Cierra la evaluación de la estrategia publicada.
"""

from .evaluar_ampliada import evaluar_ampliada, evaluar_cierre
from .indexar import (
    cargar_indice_embeddings,
    ejecutar_etapa12,
    evaluar_revision,
    indexar_corpus,
)
from .preparar import preparar_corpus
from .recuperar import buscar
from .rutas import raiz_repo, ruta_originales, ruta_salidas_rag
from .validar import validar_fragmentos

__all__ = [
    "preparar_corpus",
    "validar_fragmentos",
    "indexar_corpus",
    "buscar",
    "ejecutar_etapa12",
    "evaluar_revision",
    "evaluar_ampliada",
    "evaluar_cierre",
    "cargar_indice_embeddings",
    "raiz_repo",
    "ruta_originales",
    "ruta_salidas_rag",
]
