"""
Servidor HTTP del recuperador con la estrategia B ya definida.

Funciones:
- cargar(): Carga el índice de embeddings desde la caché.
- recuperar(): Busca fragmentos y clasifica la cobertura de la pregunta.
- main(): Publica /salud y /recuperar.

Clase Manejador:
- do_GET(): Responde el estado del servicio.
- do_POST(): Recibe la pregunta y devuelve los fragmentos.
"""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .evidencia import clasificar_evidencia
from .indexar import cargar_indice_embeddings
from .recuperar import buscar

ESTRATEGIA = "B_coseno_top5_adyacentes_alcance"
TOP_K = 5
UMBRAL = 0.30
VENTANA = 1
HOST = os.environ.get("RAG_HOST", "0.0.0.0")
PORT = int(os.environ.get("RAG_PORT", "8091"))

_ESTADO: dict[str, Any] = {}


def _jsonable(obj: Any) -> Any:
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if hasattr(obj, "item"):
        try:
            return obj.item()
        except Exception:
            pass
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(x) for x in obj]
    return str(obj)


def cargar() -> dict:
    idx = cargar_indice_embeddings(reutilizar=True)
    if not idx.get("desde_cache"):
        raise RuntimeError(
            "El índice no se reutilizó. El servicio no regenera embeddings."
        )
    vectores = idx["indice"]["vectores"]
    if tuple(vectores.shape) != (234, 1536):
        raise RuntimeError(
            f"Se esperaban embeddings (234, 1536); hay {vectores.shape}."
        )
    return idx


def recuperar(pregunta: str) -> dict:
    indice = _ESTADO["indice"]
    corpus = indice["df"]
    res = buscar(
        pregunta,
        indice,
        top_k=TOP_K,
        umbral=UMBRAL,
        ampliar=True,
        ventana=VENTANA,
        preferir_alcance=True,
        hibrido=False,
    )
    hits_df = res["hits"]
    textos = [] if hits_df is None or hits_df.empty else hits_df["texto"].astype(str).tolist()
    lex = clasificar_evidencia(pregunta, textos, corpus)
    hits = []
    if hits_df is not None and not hits_df.empty:
        cols = [
            "fragment_id", "doc_id", "titulo", "seccion", "pagina_inicio",
            "pagina_fin", "fuente", "version", "rango", "similitud",
            "origen", "semilla", "texto",
        ]
        for _, row in hits_df.iterrows():
            item = {c: _jsonable(row[c]) if c in row.index else None for c in cols}
            hits.append(item)
    return {
        "pregunta": pregunta,
        "estrategia": ESTRATEGIA,
        "top_k": TOP_K,
        "umbral": UMBRAL,
        "alcance": res.get("alcance"),
        "similitud_max": res.get("similitud_max"),
        "informacion_insuficiente_umbral": bool(res.get("informacion_insuficiente")),
        "cobertura_lexica": _jsonable(lex),
        "hits": hits,
        "n_hits": len(hits),
        "segundos_embedding": res.get("segundos_embedding"),
        "segundos_busqueda": res.get("segundos_busqueda"),
        "n_vectores": 234,
        "modelo": "text-embedding-3-small",
        "aviso": (
            "La similitud no es prueba jurídica. "
            "El clasificador léxico no decide solo si se responde."
        ),
    }


def _cuerpo(handler: BaseHTTPRequestHandler) -> dict:
    n = int(handler.headers.get("Content-Length") or 0)
    raw = handler.rfile.read(n) if n else b"{}"
    try:
        data = json.loads(raw.decode("utf-8") or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON inválido: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("El cuerpo debe ser un objeto JSON.")
    return data


def _responder(handler: BaseHTTPRequestHandler, codigo: int, cuerpo: dict) -> None:
    raw = json.dumps(cuerpo, ensure_ascii=False).encode("utf-8")
    handler.send_response(codigo)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(raw)))
    handler.end_headers()
    handler.wfile.write(raw)


class Manejador(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def do_GET(self) -> None:  # noqa: N802
        if self.path.split("?", 1)[0] in {"/", "/salud"}:
            _responder(self, 200, {
                "ok": True,
                "estrategia": ESTRATEGIA,
                "n_vectores": 234,
                "dimension": 1536,
                "modelo": "text-embedding-3-small",
                "desde_cache": True,
            })
            return
        _responder(self, 404, {"ok": False, "error": "ruta no encontrada"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path.split("?", 1)[0] not in {"/recuperar", "/api/recuperar"}:
            _responder(self, 404, {"ok": False, "error": "ruta no encontrada"})
            return
        try:
            data = _cuerpo(self)
        except ValueError as exc:
            _responder(self, 400, {"ok": False, "error": str(exc)})
            return
        pregunta = str(data.get("pregunta") or data.get("query") or "").strip()
        if len(pregunta) < 3:
            _responder(self, 400, {"ok": False, "error": "Falta una pregunta válida."})
            return
        try:
            cuerpo = recuperar(pregunta)
        except Exception as exc:
            _responder(self, 500, {"ok": False, "error": f"{type(exc).__name__}: {exc}"})
            return
        _responder(self, 200, cuerpo)


def main() -> None:
    idx = cargar()
    _ESTADO["idx"] = idx
    _ESTADO["indice"] = idx["indice"]
    print(
        "rag-documental",
        ESTRATEGIA,
        "vectores", idx["indice"]["vectores"].shape,
        "cache", idx["desde_cache"],
        f"http://{HOST}:{PORT}/salud",
        flush=True,
    )
    httpd = ThreadingHTTPServer((HOST, PORT), Manejador)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()


if __name__ == "__main__":
    main()
