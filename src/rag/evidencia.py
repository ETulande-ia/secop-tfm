"""
Clasifica si los fragmentos recuperados cubren la pregunta, sin usar el umbral de similitud.

Funciones:
- plegar(): Normaliza mayúsculas y tildes.
- terminos(): Extrae los términos útiles de la pregunta.
- clasificar_evidencia(): Devuelve suficiente, parcial o no cubierta.
"""

from __future__ import annotations

import re
import unicodedata

import pandas as pd

STOP = frozenset({
    "para", "como", "que", "cual", "cuales", "donde", "sobre", "cada", "dice",
    "una", "uno", "unos", "unas", "los", "las", "del", "por", "con", "sin",
    "son", "esta", "este", "estos", "estas", "entre", "hacia", "hasta", "desde",
    "cuando", "mucho", "muy", "mas", "menos", "el", "la", "un", "al", "lo",
    "se", "su", "sus", "es", "en", "de", "y", "o", "a", "e", "u", "no", "si",
    "le", "les", "hay", "tiene", "tienen", "debe", "deben", "ser", "fue",
    "usa", "usan", "alta", "alto", "cada", "cual", "significa", "campo",
    "publica", "publico", "publicas", "contratacion", "contrato", "contratos",
    "cuanto", "cuantos", "cuanta", "cuantas", "tiempo", "manera", "forma",
})
VERBOS = frozenset({
    "usa", "usan", "dice", "dicen", "significa", "puntuaron", "puntuado",
    "determina", "determinan", "responder", "contiene", "consiste", "consisten",
    "entiende", "entienden", "indicar", "indica", "indican", "exige", "exigen",
    "presentar", "presenta", "acreditar", "acredita", "califican", "calificar",
    "publicarse", "publicar", "publicado", "excluyeron", "excluir", "recibio",
    "recibieron", "quedó", "quedo", "incluye", "incluyen",
})
PREDICADOS = frozenset({
    "consiste", "consisten", "entiende", "entienden", "califican", "publicarse",
    "excluyeron",
})
ACRONIMOS = frozenset({
    "c1", "rup", "nit", "dane", "sisben", "secop", "if", "cce", "lof",
    "iii", "ii", "iv", "egcap",
})
DF_DISTINTIVO = 5
_SUF_VERBO = re.compile(r"(ifican|aron|ieron|arse|irse|ados|adas)$")
_CAMPO = re.compile(
    r"campo\s+(.+?)\s+(?:en el diccionario|en el|del diccionario|de los datos|de datos)"
)
_CAMPO_CORTO = re.compile(r"campo\s+([a-z0-9 _áéíóúñ]+?)(?:\s+\?|\?|$)")
_PRODUCTO = re.compile(r"\b(secop|sisben)\s*(iii|ii|iv|[2-9])?\b")
_INSTANCIA = re.compile(
    r"\b(?:de|en)\s+((?:la|el)\s+)?([A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚáéíóúñ]+"
    r"(?:\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚáéíóúñ]+){0,3})"
)


def plegar(texto: str) -> str:
    s = unicodedata.normalize("NFD", str(texto or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _es_predicado(token: str) -> bool:
    if token in VERBOS or token in PREDICADOS or token in STOP:
        return True
    if token in ACRONIMOS or "_" in token or token.isdigit():
        return False
    return bool(len(token) >= 7 and _SUF_VERBO.search(token))


def terminos(texto: str) -> list[str]:
    crudos = re.findall(r"[a-z0-9_]+", plegar(texto))
    out = []
    for t in crudos:
        if t.isdigit():
            continue
        if _es_predicado(t):
            continue
        if len(t) >= 4 or t in ACRONIMOS or "_" in t:
            if t not in out:
                out.append(t)
    return out


def _freq(df: pd.DataFrame, termino: str) -> int:
    col = df["texto"].map(plegar)
    return int(col.str.contains(re.escape(termino), regex=True).sum())


def _tiene_frase(df: pd.DataFrame, frase: str) -> bool:
    """Coincidencia de frase con borde de token. Evita que «cali» case con «calidad»."""
    if not frase:
        return False
    col = df["texto"].map(plegar)
    nucleo = re.escape(plegar(frase).strip())
    pat = r"(^|[^a-z0-9_])" + nucleo + r"([^a-z0-9_]|$)"
    return bool(col.str.contains(pat, regex=True).any())


def _coocurre(df: pd.DataFrame, terms: list[str]) -> bool:
    if not terms:
        return False
    for texto in df["texto"].astype(str):
        blob = plegar(texto)
        if all(t in blob for t in terms):
            return True
    return False


def _alias_parentesis(pregunta: str) -> set[str]:
    """«árboles (n_estimators)»: el término externo no ancla si el interno existe."""
    alias = set()
    for m in re.finditer(r"([a-z0-9_]+)\s*\(([a-z0-9_]+)\)", plegar(pregunta)):
        alias.add(m.group(1))
    return alias


def _campo_preguntado(pregunta: str) -> str | None:
    q = plegar(pregunta)
    m = _CAMPO.search(q)
    if not m:
        m = _CAMPO_CORTO.search(q)
    if not m:
        return None
    campo = re.sub(r"\s+", " ", m.group(1)).strip(" ?.")
    return campo or None


def _productos(pregunta: str) -> list[str]:
    q = plegar(pregunta)
    out = []
    for m in _PRODUCTO.finditer(q):
        nombre, ver = m.group(1), m.group(2) or ""
        if ver in {"iii", "iv", "3", "4"}:
            out.append(f"{nombre} {ver}".strip())
    return out


def _calificadores_instancia(pregunta: str) -> list[str]:
    """Nombres propios tras de/en. No es una lista de ciudades ni de IDs."""
    skip = {
        "colombia", "compra", "eficiente", "ley", "decreto", "entidad",
        "proceso", "contratacion", "modalidad", "registro", "unico",
        "proponentes", "isolation", "forest", "diccionario", "datos",
        "secop", "manual", "agencia",
    }
    found = []
    for m in _INSTANCIA.finditer(pregunta or ""):
        nombre = plegar(m.group(2) or "")
        tok = nombre.split()[0] if nombre else ""
        if len(tok) >= 4 and tok not in skip and tok not in STOP:
            if tok not in found:
                found.append(tok)
    return found


def clasificar_evidencia(
    pregunta: str,
    textos: list[str],
    corpus: pd.DataFrame,
) -> dict:
    """suficiente | parcial | no_cubierta. Independiente de la similitud coseno."""
    terms = terminos(pregunta)
    hits = plegar("\n".join(textos or []))
    alias = _alias_parentesis(pregunta)
    campo = _campo_preguntado(pregunta)
    productos = _productos(pregunta)
    instancias = _calificadores_instancia(pregunta)
    freq = {t: _freq(corpus, t) for t in terms}
    distintivos = [t for t in terms if 0 < freq[t] <= DF_DISTINTIVO]
    cubiertos = [t for t in terms if t in hits]
    dist_hits = [t for t in distintivos if t in hits]
    ratio = round(len(cubiertos) / max(len(terms), 1), 3)
    base = {
        "terminos": terms,
        "distintivos": distintivos,
        "cubiertos": cubiertos,
        "ratio": ratio,
        "campo": campo,
        "productos": productos,
        "instancias": instancias,
    }

    productos_ausentes = [p for p in productos if not _tiene_frase(corpus, p)]
    if productos_ausentes:
        return {
            "cobertura": "no_cubierta",
            "razon": (
                "El corpus no cubre la versión o plataforma: "
                + ", ".join(productos_ausentes)
                + "."
            ),
            **base,
        }

    ausentes = [
        t for t in terms
        if freq[t] == 0
        and t not in alias
        and (t in ACRONIMOS or len(t) >= 6 or "_" in t)
    ]
    tema_en_corpus = any(freq[t] > 0 for t in terms)
    inst_ausentes = [t for t in instancias if not _tiene_frase(corpus, t)]

    if ausentes and not tema_en_corpus:
        return {
            "cobertura": "no_cubierta",
            "razon": "El corpus no menciona: " + ", ".join(ausentes) + ".",
            **base,
        }

    if inst_ausentes and tema_en_corpus:
        if any(t in hits for t in terms if freq.get(t, 0) > 0):
            return {
                "cobertura": "parcial",
                "razon": (
                    "Hay evidencia del tema, pero no del recorte pedido: "
                    + ", ".join(inst_ausentes)
                    + "."
                ),
                **base,
            }
        return {
            "cobertura": "no_cubierta",
            "razon": (
                "Falta el recorte pedido y los hits no cubren el tema: "
                + ", ".join(inst_ausentes)
                + "."
            ),
            **base,
        }

    if ausentes and not inst_ausentes:
        return {
            "cobertura": "no_cubierta",
            "razon": "El corpus no menciona: " + ", ".join(ausentes) + ".",
            **base,
        }

    anclas = [t for t in distintivos if freq[t] <= 2]
    if len(anclas) >= 2 and not _coocurre(corpus, anclas):
        return {
            "cobertura": "no_cubierta",
            "razon": (
                "Ningún fragmento del corpus reúne a la vez: "
                + ", ".join(anclas)
                + "."
            ),
            **base,
        }

    if campo:
        frase = plegar(campo)
        if frase and frase not in hits:
            return {
                "cobertura": "parcial",
                "razon": (
                    "Los hits no contienen el campo preguntado («"
                    + campo
                    + "»); compartir vocabulario del diccionario no basta."
                ),
                **base,
            }

    if distintivos and not dist_hits:
        return {
            "cobertura": "parcial" if cubiertos else "no_cubierta",
            "razon": (
                "Los hits no incluyen los términos distintivos ("
                + ", ".join(distintivos)
                + ") aunque el corpus sí los tiene."
            ),
            **base,
        }

    if distintivos and set(distintivos) <= set(dist_hits):
        return {
            "cobertura": "suficiente",
            "razon": "Los hits contienen los términos distintivos de la pregunta.",
            **base,
        }

    if distintivos:
        return {
            "cobertura": "parcial",
            "razon": "Solo parte de los términos distintivos aparece en los hits.",
            **base,
        }

    if ratio >= 0.7:
        cobertura = "suficiente"
        razon = "La pregunta no tiene términos raros; los hits cubren la mayoría de los restantes."
    elif ratio >= 0.4:
        cobertura = "parcial"
        razon = "Cobertura léxica parcial; no hay término distintivo que ancle la respuesta."
    else:
        cobertura = "no_cubierta"
        razon = "Los hits no cubren los términos de la pregunta."
    return {"cobertura": cobertura, "razon": razon, **base}
