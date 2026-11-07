"""
Compara respuestas de GPT-4o-mini con y sin fragmentos recuperados.

Funciones:
- generar_sin_rag(): Responde la pregunta sin documentos.
- generar_con_rag(): Pide la respuesta al chat con recuperación.
- puntuar(): Evalúa suficiencia, vigencia, citas y respaldo.
- ejecutar_comparacion(): Corre ambas condiciones y guarda la comparación.
"""

from __future__ import annotations

import json
import os
import re
import time
import unicodedata
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from nlq_eval.cliente import diagnosticar_chat, preguntar_chat
from .embeddings import MODELO_DEFECTO, clave_disponible
from .preguntas_comparacion import PREGUNTAS_COMPARACION, validar_preguntas
from .rutas import ruta_salidas_rag

MODELO = "gpt-4o-mini"
TEMPERATURA = 0
ESTRATEGIA = "B_coseno_top5_adyacentes_alcance"
RAG_URL = os.environ.get("RAG_URL", "http://rag-documental:8091")

ARCHIVOS_PROTEGIDOS = (
    "metricas_recuperacion.json",
    "metricas_recuperacion_original.json",
    "metricas_recuperacion_v2.json",
    "metricas_recuperacion_v3.json",
    "metricas_recuperacion_v4.json",
    "metricas_chat_rag_v1.json",
)

CUE_INSUF = (
    "no encontre", "evidencia suficiente", "no esta en el corpus",
    "no cubre", "no dispongo", "no tengo evidencia", "no figura",
    "no proporciona", "no especifica", "no hay evidencia",
    "parte de la pregunta", "no completo", "hueco", "no acredita",
    "no puedo acreditar", "fuera del corpus", "no esta en los documentos",
)


def plegar(texto: str) -> str:
    s = unicodedata.normalize("NFD", str(texto or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def texto_util(texto: str) -> str:
    t = str(texto or "")
    for sep in (
        "Los manuales del corpus no acreditan",
        "Fuentes (corpus v1):",
    ):
        i = t.find(sep)
        if i > 0:
            t = t[:i]
    return t.strip()


def _guardar(ruta: Path, obj) -> None:
    ruta.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def meta_corpus(salidas: Path) -> dict:
    meta = json.loads((salidas / "embeddings_meta.json").read_text(encoding="utf-8"))
    v4 = json.loads((salidas / "metricas_recuperacion_v4.json").read_text(encoding="utf-8"))
    return {
        "modelo_embedding": meta.get("modelo"),
        "n_vectores": meta.get("n_vectores"),
        "dimension": meta.get("dimension"),
        "huella": meta.get("huella"),
        "embeddings_utc": meta.get("generado_utc"),
        "estrategia_congelada": v4.get("estrategia"),
        "v4_utc": v4.get("generado_utc"),
    }


def prompt_sin_rag(pregunta: str) -> str:
    return f"""Eres un asistente de contratación pública en Colombia. Responde SOLO con JSON válido.

Pregunta del ciudadano:
{pregunta}

Condición experimental: NO se te entrega ningún fragmento documental. No tienes el corpus v1 del TFM. No recibas ni inventes fragment_id, páginas ni citas de manuales recuperados.

Reglas:
- Puedes usar conocimiento general de tu entrenamiento.
- No inventes artículos, requisitos, plazos ni cifras si no las sabes.
- No afirmes vigencia normativa actual para 2026.
- Atipicidad estadística no es fraude ni irregularidad.
- Si no sabes un dato específico de un prototipo o de un manual concreto, puede_responder=false.
- No cites fuentes que no tienes.
- texto: respuesta breve en español.
- limitaciones: solo un recorte real; si no hay, "".

JSON:
{{
  "puede_responder": true,
  "cobertura": "suficiente" | "parcial" | "insuficiente",
  "texto": "...",
  "limitaciones": "...",
  "fragment_ids": []
}}
"""


def parsear_json_llm(raw: str) -> dict:
    t = str(raw or "").strip()
    ini, fin = t.find("{"), t.rfind("}")
    if ini < 0 or fin <= ini:
        return {
            "puede_responder": False,
            "cobertura": "insuficiente",
            "texto": t,
            "limitaciones": "",
            "fragment_ids": [],
        }
    try:
        obj = json.loads(t[ini : fin + 1])
    except json.JSONDecodeError:
        return {
            "puede_responder": False,
            "cobertura": "insuficiente",
            "texto": t[:800],
            "limitaciones": "",
            "fragment_ids": [],
        }
    ids = obj.get("fragment_ids") or []
    if not isinstance(ids, list):
        ids = []
    return {
        "puede_responder": obj.get("puede_responder") is not False,
        "cobertura": obj.get("cobertura") or "insuficiente",
        "texto": str(obj.get("texto") or "").strip(),
        "limitaciones": str(obj.get("limitaciones") or "").strip(),
        "fragment_ids": [str(x) for x in ids],
    }


def generar_sin_rag(pregunta: str) -> dict:
    """GPT-4o-mini sin fragmentos. No llama al recuperador."""
    if not clave_disponible():
        raise RuntimeError("Falta OPENAI_API_KEY para la condición sin RAG.")
    from openai import OpenAI

    prompt = prompt_sin_rag(pregunta)
    t0 = time.perf_counter()
    cliente = OpenAI(default_headers={"Accept-Encoding": "gzip, deflate"})
    resp = cliente.chat.completions.create(
        model=MODELO,
        messages=[{"role": "user", "content": prompt}],
        temperature=TEMPERATURA,
    )
    crudo = resp.choices[0].message.content
    parsed = parsear_json_llm(crudo)
    partes = [parsed["texto"]]
    lim = parsed["limitaciones"].strip()
    if lim and plegar(lim) not in {"ninguna", "n/a", "na", "none", "no aplica"}:
        partes.append(lim)
    texto = "\n\n".join(p for p in partes if p)
    return {
        "condicion": "sin_rag",
        "modelo": MODELO,
        "temperatura": TEMPERATURA,
        "prompt": prompt,
        "crudo": crudo,
        "texto": texto,
        "cobertura_modelo": parsed["cobertura"],
        "puede_responder": parsed["puede_responder"],
        "referencias": [],
        "fragment_ids_modelo": parsed["fragment_ids"],
        "hits": [],
        "n_hits": 0,
        "segundos": round(time.perf_counter() - t0, 3),
        "recibio_fragmentos": False,
    }


def recuperar_hits(pregunta: str, timeout: float = 25.0) -> dict:
    url = RAG_URL.rstrip("/") + "/recuperar"
    req = urllib.request.Request(
        url,
        data=json.dumps({"pregunta": pregunta}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def generar_con_rag(pregunta: str, url_chat: str, timeout: float = 60.0) -> dict:
    resp = preguntar_chat(pregunta, url_chat, timeout=timeout)
    body = resp["body"] or {}
    hits = []
    rec = {}
    try:
        rec = recuperar_hits(pregunta)
        hits = rec.get("hits") or []
    except Exception as exc:
        rec = {"error": f"{type(exc).__name__}: {exc}"}
    return {
        "condicion": "con_rag",
        "modelo": MODELO,
        "temperatura": TEMPERATURA,
        "prompt": None,
        "crudo": None,
        "texto": str(body.get("text") or ""),
        "intent": body.get("intent"),
        "cobertura_modelo": (body.get("evidencia") or {}).get("cobertura"),
        "referencias": body.get("referencias") or [],
        "evidencia": body.get("evidencia") or {},
        "hits": hits,
        "n_hits": len(hits),
        "segundos": resp["segundos"],
        "error_infra": resp["error_infra"],
        "recibio_fragmentos": True,
        "recuperacion": rec if "error" in rec else {
            "n_hits": len(hits),
            "alcance": rec.get("alcance"),
            "similitud_max": rec.get("similitud_max"),
            "cobertura_lexica": (rec.get("cobertura_lexica") or {}).get("cobertura"),
            "fragment_ids": [h.get("fragment_id") for h in hits],
        },
    }


def reconoce_insuficiencia(texto: str) -> bool:
    p = plegar(texto_util(texto))
    return any(c in p for c in CUE_INSUF)


def afirma_vigencia_actual(texto: str) -> bool:
    p = plegar(texto_util(texto))
    if "no acreditan" in p or "no acredita" in p or "no actualizan" in p:
        return False
    return any(
        f in p for f in (
            "esta vigente para 2026", "si esta vigente", "rige en 2026",
            "aplica en 2026", "esta vigente",
        )
    )


def inventa_citas(texto: str, fragment_ids: list) -> bool:
    if fragment_ids:
        return True
    p = plegar(texto)
    return "fuentes (corpus v1)" in p or "fragment_id" in p


def oraciones_utiles(texto: str) -> list[str]:
    t = texto_util(texto)
    t = re.sub(r"\s+", " ", t)
    partes = re.split(r"(?<=[\.!?])\s+", t)
    return [x.strip() for x in partes if len(x.strip()) > 25]


def respaldo_oracion(oracion: str, hits_texto: str) -> bool | None:
    toks = [w for w in re.findall(r"[a-z0-9_]+", plegar(oracion)) if len(w) >= 5 or w.isdigit()]
    stop = {
        "para", "como", "entre", "desde", "hasta", "sobre", "puede", "pueden",
        "debe", "deben", "contrato", "contratos", "publica", "estado",
        "manuales", "documento", "respuesta",
    }
    toks = [t for t in toks if t not in stop]
    if len(toks) < 2:
        return None
    blob = plegar(hits_texto)
    cub = sum(1 for t in toks if t in blob)
    return (cub / len(toks)) >= 0.45


def puntuar(esp: dict, corrida: dict) -> dict:
    texto = corrida.get("texto") or ""
    util = texto_util(texto)
    p = plegar(util)
    hechos_ok = all(plegar(h) in p for h in esp["hechos"]) if esp["hechos"] else True
    if esp.get("requiere_negacion"):
        hechos_ok = hechos_ok and bool(re.search(r"\bno\b", p))
    prohibido = [x for x in esp["prohibido"] if plegar(x) in p]
    insuf = reconoce_insuficiencia(texto)
    vigencia_mal = esp["vigencia_no_acreditable"] and afirma_vigencia_actual(texto)
    if esp["debe_reconocer_insuficiencia"]:
        insuf_ok = insuf
    else:
        insuf_ok = True
    factual = hechos_ok and not prohibido and insuf_ok and not vigencia_mal

    refs = corrida.get("referencias") or []
    hits = corrida.get("hits") or []
    ids_hits = {str(h.get("fragment_id")) for h in hits if h.get("fragment_id")}
    ids_ref = [str(r.get("fragment_id")) for r in refs if r.get("fragment_id")]
    if corrida["condicion"] == "sin_rag":
        citas_validas = len(refs) == 0
        citas_pertinentes = True
        inventa = inventa_citas(texto, corrida.get("fragment_ids_modelo") or [])
        n_sin_respaldo = None
        n_oraciones = None
        respaldo_ok = not inventa
    else:
        citas_validas = bool(ids_ref) and all(i in ids_hits for i in ids_ref) if esp["cobertura_esperada"] == "suficiente" else (
            all(i in ids_hits for i in ids_ref)
        )
        if esp["cobertura_esperada"] == "no_cubierta":
            citas_validas = len(refs) == 0
            citas_pertinentes = True
        else:
            esper = esp.get("doc_id_esperado")
            citas_pertinentes = (not esper) or any(r.get("doc_id") == esper for r in refs) or not refs
        inventa = any(i not in ids_hits for i in ids_ref)
        blob = "\n".join(str(h.get("texto") or "") for h in hits)
        ors_ = oraciones_utiles(util)
        flags = [respaldo_oracion(o, blob) for o in ors_]
        utiles = [f for f in flags if f is not None]
        n_sin_respaldo = sum(1 for f in utiles if f is False)
        n_oraciones = len(utiles)
        respaldo_ok = (n_sin_respaldo == 0) if utiles else (len(hits) > 0 or esp["cobertura_esperada"] == "no_cubierta")

    if esp["cobertura_esperada"] == "no_cubierta" and corrida["condicion"] == "con_rag":
        factual = insuf_ok and not prohibido

    return {
        "factual_ok": factual,
        "hechos_ok": hechos_ok,
        "prohibido_hit": prohibido,
        "reconoce_insuficiencia": insuf,
        "insuficiencia_ok": insuf_ok,
        "afirma_vigencia_actual": vigencia_mal,
        "citas_validas": citas_validas,
        "citas_pertinentes": citas_pertinentes,
        "inventa_citas": inventa,
        "n_oraciones": n_oraciones,
        "n_sin_respaldo": n_sin_respaldo,
        "respaldo_ok": respaldo_ok,
        "parcial_ok": (
            (insuf and not prohibido)
            if esp["familia"] == "parcial"
            else None
        ),
    }


def ejecutar_comparacion(
    salidas: Path | None = None,
    timeout: float = 60.0,
) -> dict:
    dest = Path(salidas) if salidas else ruta_salidas_rag()
    dest.mkdir(parents=True, exist_ok=True)
    validar_preguntas()
    for nombre in ARCHIVOS_PROTEGIDOS:
        if not (dest / nombre).is_file() and nombre.startswith("metricas_recuperacion"):
            continue
    corpus = meta_corpus(dest)
    if corpus["n_vectores"] != 234:
        raise RuntimeError(f"El índice no está congelado: {corpus}")

    diag = diagnosticar_chat()
    if not diag["disponible"]:
        return {"bloqueo": True, "motivo": "chat no alcanzable", "diagnostico": diag, "salidas": dest}

    filas = []
    detalle = []
    for esp in PREGUNTAS_COMPARACION:
        sin = generar_sin_rag(esp["pregunta"])
        con = generar_con_rag(esp["pregunta"], diag["url"], timeout=timeout)
        if sin["recibio_fragmentos"] or sin["n_hits"]:
            raise RuntimeError(f"{esp['id']}: la condición sin RAG recibió fragmentos.")
        for corrida in (sin, con):
            ev = puntuar(esp, corrida)
            filas.append({
                "id": esp["id"],
                "familia": esp["familia"],
                "tema": esp["tema"],
                "pregunta": esp["pregunta"],
                "condicion": corrida["condicion"],
                "cobertura_esperada": esp["cobertura_esperada"],
                "cobertura_observada": corrida.get("cobertura_modelo"),
                "intent": corrida.get("intent"),
                "segundos": corrida["segundos"],
                "n_hits": corrida.get("n_hits") or 0,
                "n_referencias": len(corrida.get("referencias") or []),
                "recibio_fragmentos": corrida["recibio_fragmentos"],
                **ev,
                "texto": corrida.get("texto") or "",
            })
            detalle.append({
                "id": esp["id"],
                "pregunta": esp["pregunta"],
                "criterio": esp["criterio"],
                "familia": esp["familia"],
                "condicion": corrida["condicion"],
                "corrida": {
                    k: corrida[k] for k in corrida
                    if k not in {"prompt", "crudo", "hits"}
                },
                "prompt": corrida.get("prompt"),
                "hits": [
                    {
                        "fragment_id": h.get("fragment_id"),
                        "doc_id": h.get("doc_id"),
                        "titulo": h.get("titulo"),
                        "seccion": h.get("seccion"),
                        "pagina_inicio": h.get("pagina_inicio"),
                        "pagina_fin": h.get("pagina_fin"),
                        "origen": h.get("origen"),
                        "texto": h.get("texto"),
                    }
                    for h in (corrida.get("hits") or [])
                ],
                "referencias": corrida.get("referencias") or [],
                "evaluacion_auto": ev,
                "revision_manual": "",
            })

    res = pd.DataFrame(filas)
    res.to_csv(dest / "resultados_comparacion_con_sin_rag_v1.csv", index=False, encoding="utf-8")
    _guardar(dest / "detalle_comparacion_con_sin_rag_v1.json", detalle)

    def _resumen(sub: pd.DataFrame) -> dict:
        n = len(sub)
        def media(col):
            s = sub[col].dropna()
            return round(float(s.mean()), 4) if len(s) else None
        return {
            "n": n,
            "exactitud_factual": media("factual_ok"),
            "respaldo": media("respaldo_ok"),
            "reconoce_insuficiencia": media("insuficiencia_ok"),
            "citas_validas": media("citas_validas"),
            "citas_pertinentes": media("citas_pertinentes"),
            "inventa_citas": media("inventa_citas"),
            "parcial_ok": media("parcial_ok"),
            "n_sin_respaldo_medio": media("n_sin_respaldo"),
            "latencia_media_s": round(float(sub["segundos"].mean()), 3) if n else None,
            "latencia_max_s": round(float(sub["segundos"].max()), 3) if n else None,
            "ids_ok_factual": sub.loc[sub["factual_ok"], "id"].tolist(),
            "ids_error_factual": sub.loc[~sub["factual_ok"], "id"].tolist(),
        }

    por_cond = {
        "sin_rag": _resumen(res[res["condicion"] == "sin_rag"]),
        "con_rag": _resumen(res[res["condicion"] == "con_rag"]),
    }
    por_fam = []
    for fam, g in res.groupby("familia"):
        por_fam.append({
            "familia": fam,
            "sin_rag": _resumen(g[g["condicion"] == "sin_rag"]),
            "con_rag": _resumen(g[g["condicion"] == "con_rag"]),
        })

    metricas = {
        "generado_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "version": "comparacion_con_sin_rag_v1",
        "aviso": (
            "Condición A: GPT-4o-mini sin fragmentos. Condición B: chat real con "
            "recuperador congelado. No se usaron rechazos históricos como si fueran "
            "generación sin RAG. No se usaron los 26 EC reservados ni RAG-H. "
            "No se pisaron métricas de 11, 12, 12b, 12c, 14 ni 15."
        ),
        "modelo": MODELO,
        "temperatura": TEMPERATURA,
        "estrategia_rag": ESTRATEGIA,
        "n_preguntas": len(PREGUNTAS_COMPARACION),
        "ids": [p["id"] for p in PREGUNTAS_COMPARACION],
        "distribucion": (
            pd.Series([p["familia"] for p in PREGUNTAS_COMPARACION])
            .value_counts()
            .to_dict()
        ),
        "corpus": corpus,
        "url_chat": diag["url"],
        "por_condicion": por_cond,
        "por_familia": por_fam,
        "evaluacion": {
            "automatica": [
                "exactitud_factual", "respaldo", "reconoce_insuficiencia",
                "citas_validas", "citas_pertinentes", "inventa_citas", "parcial_ok",
                "latencia",
            ],
            "manual": (
                "El CSV/JSON deja revision_manual vacío. Una cita válida no implica "
                "que toda la respuesta sea correcta."
            ),
        },
    }
    _guardar(dest / "metricas_comparacion_con_sin_rag_v1.json", metricas)
    man = res[[
        "id", "familia", "condicion", "pregunta", "factual_ok", "respaldo_ok",
        "reconoce_insuficiencia", "citas_validas", "inventa_citas", "texto",
    ]].copy()
    man["revision_manual"] = ""
    man["notas_manual"] = ""
    man.to_csv(dest / "revision_manual_comparacion_v1.csv", index=False, encoding="utf-8")
    return {
        "bloqueo": False,
        "metricas": metricas,
        "resultados": res,
        "detalle": detalle,
        "salidas": dest,
    }
