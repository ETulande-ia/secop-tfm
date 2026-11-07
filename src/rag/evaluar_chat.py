"""
Evalúa el chat documental sobre las preguntas de desarrollo.

Funciones:
- puntuar(): Contrasta intención, cobertura, cita y anclas de una respuesta.
- evaluar_chat_documental(): Consulta el chat y guarda métricas y resultados.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from nlq_eval.cliente import diagnosticar_chat, preguntar_chat
from nlq_eval.particion import IDS_RESERVADOS
from .preguntas_chat import PREGUNTAS_CHAT
from .rutas import ruta_salidas_rag


def _plegar(texto: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFD", str(texto or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _guardar(ruta: Path, obj: dict) -> None:
    ruta.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def puntuar(esp: dict, body: dict, segundos: float) -> dict:
    text = str(body.get("text") or "")
    plegado = _plegar(text)
    intent = str(body.get("intent") or "")
    evid = body.get("evidencia") or {}
    refs = body.get("referencias") or []
    cob = evid.get("cobertura")
    anclas_ok = all(_plegar(a) in plegado for a in esp["anclas"])
    prohibido = [p for p in esp["prohibido"] if _plegar(p) in plegado]
    cita_ok = True
    if esp["debe_citar"]:
        cita_ok = bool(refs) and all(
            r.get("fragment_id") and r.get("documento") for r in refs
        )
        if esp["doc_id_esperado"]:
            cita_ok = cita_ok and any(
                r.get("doc_id") == esp["doc_id_esperado"] for r in refs
            )
    else:
        cita_ok = len(refs) == 0 or cob == "parcial"
    if esp["ruta"] == "documental":
        intent_ok = intent == "RAG_DOCUMENTAL"
        cob_ok = cob == esp["cobertura_esperada"]
    else:
        intent_ok = intent == esp["intent_esperado"]
        cob_ok = True
    recupera = bool(refs) if esp["debe_citar"] else (cob == "no_cubierta" or esp["ruta"] != "documental")
    ok = intent_ok and cob_ok and anclas_ok and not prohibido and cita_ok
    return {
        "id": esp["id"],
        "caso": esp["caso"],
        "pregunta": esp["pregunta"],
        "ruta": esp["ruta"],
        "intent_esperado": esp["intent_esperado"],
        "intent_observado": intent,
        "cobertura_esperada": esp["cobertura_esperada"],
        "cobertura_observada": cob,
        "n_referencias": len(refs),
        "fragment_ids": [r.get("fragment_id") for r in refs],
        "doc_ids": [r.get("doc_id") for r in refs],
        "intent_ok": intent_ok,
        "cobertura_ok": cob_ok,
        "anclas_ok": anclas_ok,
        "citas_ok": cita_ok,
        "recuperacion_ok": recupera,
        "prohibido_hit": prohibido,
        "ok": ok,
        "segundos": segundos,
        "texto": text[:400],
    }


def evaluar_chat_documental(
    salidas: Path | None = None,
    timeout: float = 60.0,
) -> dict:
    dest = Path(salidas) if salidas else ruta_salidas_rag()
    dest.mkdir(parents=True, exist_ok=True)
    ids = [p["id"] for p in PREGUNTAS_CHAT]
    if any(i in IDS_RESERVADOS for i in ids):
        raise RuntimeError("La evaluación de chat usó un ID reservado.")
    diag = diagnosticar_chat()
    if not diag["disponible"]:
        return {"bloqueo": True, "metricas": {"motivo": "chat no alcanzable", "diagnostico": diag}, "salidas": dest}

    url = diag["url"]
    filas = []
    for esp in PREGUNTAS_CHAT:
        resp = preguntar_chat(esp["pregunta"], url, timeout=timeout)
        body = resp["body"] or {}
        filas.append(puntuar(esp, body, resp["segundos"]))
    res = pd.DataFrame(filas)
    res.to_csv(dest / "evaluacion_chat_rag_v1.csv", index=False, encoding="utf-8")
    n = len(res)
    metricas = {
        "generado_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "version": "chat_rag_v1",
        "aviso": (
            "Evaluación inicial de desarrollo. No usa los 26 EC reservados ni RAG-H. "
            "No pisa metricas de los notebooks 11, 12, 12b, 12c ni 14."
        ),
        "n": n,
        "url": url,
        "n_ok": int(res["ok"].sum()),
        "exactitud": round(float(res["ok"].mean()), 4) if n else None,
        "recuperacion": round(float(res["recuperacion_ok"].mean()), 4) if n else None,
        "citas": round(float(res["citas_ok"].mean()), 4) if n else None,
        "latencia_media_s": round(float(res["segundos"].mean()), 3) if n else None,
        "latencia_max_s": round(float(res["segundos"].max()), 3) if n else None,
        "ids_ok": res.loc[res["ok"], "id"].tolist(),
        "ids_error": res.loc[~res["ok"], "id"].tolist(),
        "por_caso": (
            res.groupby("caso")
            .agg(n=("id", "size"), ok=("ok", "sum"), segundos=("segundos", "mean"))
            .reset_index()
            .to_dict(orient="records")
        ),
    }
    _guardar(dest / "metricas_chat_rag_v1.json", metricas)
    return {
        "bloqueo": False,
        "metricas": metricas,
        "resultados": res,
        "salidas": dest,
    }
