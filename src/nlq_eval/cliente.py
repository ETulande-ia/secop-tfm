"""
Cliente HTTP de POST /api/chat. No modifica el contrato del asistente.

Funciones:
- diagnosticar_chat(): Prueba las URL candidatas y elige una disponible.
- preguntar_chat(): Envía una consulta y devuelve estado, cuerpo y latencia.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

CANDIDATOS = (
    os.environ.get("CHAT_API"),
    "http://orchestration-layer:3000/api/chat",
    "http://172.25.0.3:3000/api/chat",
)


def _candidatos() -> list[str]:
    out = []
    for u in CANDIDATOS:
        if u and u not in out:
            out.append(u)
    return out


def diagnosticar_chat(timeout: float = 5.0) -> dict:
    intentos = []
    for url in _candidatos():
        t0 = time.perf_counter()
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps({"query": "Cuantos contratos hay en Bogota"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                body = json.loads(raw.decode("utf-8"))
                ok = resp.status == 200 and isinstance(body, dict) and "text" in body
                intentos.append({
                    "url": url,
                    "status": resp.status,
                    "segundos": round(time.perf_counter() - t0, 3),
                    "ok": ok,
                    "intent": body.get("intent"),
                    "claves": sorted(body.keys()),
                })
                if ok:
                    return {"disponible": True, "url": url, "intentos": intentos}
        except Exception as exc:
            intentos.append({
                "url": url,
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "segundos": round(time.perf_counter() - t0, 3),
            })
    return {"disponible": False, "url": None, "intentos": intentos}


def preguntar_chat(query: str, url: str, timeout: float = 45.0) -> dict:
    t0 = time.perf_counter()
    payload = json.dumps({"query": query}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            body = json.loads(raw.decode("utf-8"))
            return {
                "http": resp.status,
                "body": body if isinstance(body, dict) else {"text": str(body)},
                "segundos": round(time.perf_counter() - t0, 3),
                "error_infra": None,
            }
    except urllib.error.HTTPError as exc:
        detalle = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(detalle)
        except json.JSONDecodeError:
            body = {"error": detalle[:400]}
        return {
            "http": exc.code,
            "body": body if isinstance(body, dict) else {"error": str(body)},
            "segundos": round(time.perf_counter() - t0, 3),
            "error_infra": None if exc.code < 500 else f"HTTP {exc.code}",
        }
    except Exception as exc:
        return {
            "http": None,
            "body": {},
            "segundos": round(time.perf_counter() - t0, 3),
            "error_infra": f"{type(exc).__name__}: {exc}",
        }
