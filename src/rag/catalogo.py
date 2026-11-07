"""
Catálogo de documentos locales verificados del corpus.

Constantes:
- DOCUMENTOS: Ficha, alcance y vigencia de cada archivo incluido.
- EXCLUIDOS: Archivos presentes que no entran al corpus.
"""

DOCUMENTOS = [
    {
        "doc_id": "cce-minima-cuantia-2024",
        "archivo": "CCE-MINIMA-CUANTIA-2024.pdf",
        "incluir": True,
        "titulo": "Manual de mínima cuantía (Colombia Compra Eficiente, 2024)",
        "entidad": "Colombia Compra Eficiente",
        "version": "2024",
        "fecha_documento": "2024",
        "fuente": "PDF local del corpus del TFM",
        "url": None,
        "alcance": "Explica la modalidad de mínima cuantía. No actualiza por sí mismo el régimen de 2026.",
        "advertencia_vigencia": "Documento de 2024; los contratos publicados son de septiembre de 2026.",
    },
    {
        "doc_id": "cce-requisitos-habilitantes-v3-2023",
        "archivo": "cce-eicp-ma-04._manual_requisitos_habilitantes_v3_29-09-2023.pdf",
        "incluir": True,
        "titulo": "Manual de requisitos habilitantes v3 (29 de septiembre de 2023)",
        "entidad": "Colombia Compra Eficiente",
        "version": "v3",
        "fecha_documento": "2023-09-29",
        "fuente": "PDF local del corpus del TFM",
        "url": None,
        "alcance": "Requisitos habilitantes y RUP. Carácter orientativo.",
        "advertencia_vigencia": "Versión de 2023; no sustituye la norma aplicable a cada proceso de 2026.",
    },
    {
        "doc_id": "diccionario-datos-abiertos-secop",
        "archivo": "DiccionarioDeDatosAbiertos.pdf",
        "incluir": True,
        "titulo": "Diccionario de datos abiertos SECOP",
        "entidad": "Colombia Compra Eficiente / datos abiertos",
        "version": "01",
        "fecha_documento": "2021-06-24",
        "fuente": "PDF local del corpus del TFM",
        "url": None,
        "alcance": "Definiciones de campos de datos abiertos. No explica modalidades ni el modelo C1.",
        "advertencia_vigencia": "Cabecera del PDF: versión 01, vigencia desde 24 de junio de 2021.",
    },
    {
        "doc_id": "ficha-c1-if-v1",
        "archivo": "ficha_c1_isolation_forest.md",
        "incluir": True,
        "titulo": "Ficha metodológica C1 + Isolation Forest (c1_if_v1)",
        "entidad": "TFM — especificación publicada",
        "version": "c1_if_v1",
        "fecha_documento": "2026-09",
        "fuente": "docs/10_experimentos_anomalias_contratos.md; docs/11_publicacion_resultados_ml.md; spark-apps/src/ml/scoring.py",
        "url": None,
        "alcance": "Describe el modelo publicado. No es un documento oficial de contratación.",
        "advertencia_vigencia": "Cifras del extracto septiembre 2026 ya documentado. No reentrena el modelo.",
    },
]

EXCLUIDOS = [
    {
        "doc_id": "guia-proceso-sancionatorio-vs2",
        "archivo": "Guia-Proceso-Sancionatorio-Vs2-OrigFirmado-2.pdf",
        "incluir": False,
        "motivo": "Excluido de la v1: proceso sancionatorio, archivo firmado de 25,8 MB con indicios de escaneo.",
    }
]
