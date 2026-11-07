"""
Evalúa la interpretación del asistente sobre las 51 expresiones.

Funciones:
- tipo_respuesta(): Clasifica la respuesta en ejecutar, aclarar, rechazar o error.
- riesgo_enganoso(): Señala una ejecución no soportada o engañosa.
- evaluar_linea_base(): Calcula la línea base v1 sin sobrescribir el JSON existente.
- evaluar_v2(): Repite la evaluación, escribe solo artefactos v2 y conserva v1.
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .capacidades import CAPACIDADES
from .cliente import diagnosticar_chat, preguntar_chat
from .etiquetas import comprobar_etiquetas, por_id
from .particion import IDS_RESERVADOS, cargar_excel, partir
from .rutas import ruta_salidas_nlq

ESPECIALES = frozenset({
    "TOP1_IF", "PORQUE_ATIPICO", "EXPLAIN_CONTRACT", "TOP_PROVIDERS",
    "INVESTMENT_CITY", "EXECUTION_TIME_ENTITY", "LONGEST_CONTRACTS",
    "RISK_ANALYSIS", "BOGOTA_CONTRATACION", "TOP_ENTIDADES", "MODALIDADES",
    "NLQ",
})
DELITO = re.compile(r"\b(corrupto|corrupcion|fraude|ilegal|robo|trampa|delito)\b")
NEGACION = re.compile(r"\bno\s+(es|significa|implica|equivale)|no es irregular")


def _plegar(texto: str) -> str:
    s = unicodedata.normalize("NFD", str(texto or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def tipo_respuesta(http, body: dict, error_infra: str | None) -> str:
    if error_infra or (http and http >= 500):
        return "error_infra"
    text = _plegar(body.get("text") or body.get("error") or "")
    intent = str(body.get("intent") or "")
    if intent == "NO_SOPORTADO":
        if any(p in text for p in (
            "precise", "indique", "reformular", "no tengo una entidad",
            "no tengo una consulta anterior", "hay varias entidades",
        )):
            return "aclarar"
        return "rechazar"
    if any(p in text for p in (
        "puedes reformularla", "no pude identificar", "precise el nombre",
        "indique el nombre", "no tengo una entidad", "no tengo una consulta anterior",
        "se requiere una pregunta",
    )):
        return "aclarar"
    if any(p in text for p in (
        "solo puedo consultar", "solo esta disponible", "no puedo filtrar",
        "no identifique esa modalidad", "no identifique una consulta",
        "no encontre la entidad", "no encontré el contrato",
    )):
        return "rechazar"
    if intent in ESPECIALES or body.get("slots") or body.get("data"):
        return "ejecutar"
    if text:
        return "ejecutar"
    return "aclarar"


def _filtros_ok(esp: dict, body: dict) -> tuple[bool, str | None]:
    esperados = esp.get("filtros_esperados") or {}
    if not esperados:
        return True, None
    if esp["comportamiento_esperado"] != "ejecutar":
        return True, None
    slots = body.get("slots") or {}
    text = _plegar(body.get("text") or "")
    if esperados.get("territorio") == "bogota":
        terr = slots.get("territorio")
        if terr not in (None, "bogota") and terr != "bogota":
            return False, f"territorio={terr}"
        if terr != "bogota" and "bogota" not in text and "es_bogota" not in text:
            if body.get("intent") != "BOGOTA_CONTRATACION":
                return False, "sin_filtro_bogota"
    if esperados.get("modalidad"):
        pista = _plegar(esperados["modalidad"])
        mod = _plegar(slots.get("modalidad") or "")
        if pista not in mod and pista not in text:
            return False, "sin_modalidad"
    if esperados.get("entidad"):
        pista = _plegar(esperados["entidad"])
        ent = _plegar(slots.get("entidad") or "")
        if pista not in ent and pista not in text:
            return False, "sin_entidad"
    return True, None


def _metrica_ok(esp: dict, body: dict) -> bool:
    want = esp.get("metrica_esperada")
    if not want or esp["comportamiento_esperado"] != "ejecutar":
        return True
    slots = body.get("slots") or {}
    got = slots.get("metrica")
    if not got:
        text = _plegar(body.get("text") or "")
        if want == "valor":
            return "cop" in text or "valor" in text
        return True
    return got == want


def _intencion_ok(esp: dict, body: dict, tipo: str) -> bool:
    if esp["comportamiento_esperado"] != "ejecutar":
        return tipo in {"aclarar", "rechazar"}
    intent = str(body.get("intent") or "")
    if intent in esp["intents_aceptados"]:
        return True
    if esp.get("operacion_esperada") and (body.get("slots") or {}).get("operacion") == esp["operacion_esperada"]:
        return True
    return False


def riesgo_enganoso(esp: dict, body: dict, tipo: str) -> str | None:
    text = _plegar(body.get("text") or "")
    intent = str(body.get("intent") or "")
    if tipo in {"aclarar", "rechazar", "error_infra"}:
        return None
    if tipo == "ejecutar" and esp["comportamiento_esperado"] in {"aclarar", "rechazar"}:
        if esp["familia"] in {"sensible", "conceptual", "calidad"}:
            return "ejecuto_consulta_no_soportada"
        if esp["familia"] in {"coloquial", "ambigua", "seguimiento"}:
            return "ejecuto_sin_aclarar"
    if esp["familia"] == "sensible" and DELITO.search(text) and not NEGACION.search(text):
        return "afirma_delito"
    if esp["familia"] == "conceptual" and tipo == "ejecutar":
        return "concepto_con_consulta_analitica"
    if esp["id"] == "EC-039" and intent == "TOP1_IF":
        return "atipicos_sin_filtro_ciudad"
    if esp["id"] in {"EC-043", "EC-044", "EC-045"} and intent in {"TOP1_IF", "PORQUE_ATIPICO", "RISK_ANALYSIS"}:
        return "anomalia_como_delito"
    return None


def _tipo_error(esp, tipo, intent_ok, filtros_ok, infra) -> str:
    if infra:
        return "infra"
    if tipo == esp["comportamiento_esperado"] and intent_ok and filtros_ok:
        return "ninguno"
    if esp["capacidad"] in {"no_soportada", "requiere_aclaracion"} and tipo == "ejecutar":
        return "no_implementada" if esp["capacidad"] == "no_soportada" else "intencion"
    if not intent_ok:
        return "intencion"
    if not filtros_ok:
        return "filtros"
    if tipo != esp["comportamiento_esperado"]:
        return "ejecucion"
    return "intencion"


def _recortar(texto: str, n: int = 280) -> str:
    t = re.sub(r"\s+", " ", str(texto or "")).strip()
    return t if len(t) <= n else t[: n - 1] + "…"


def _cargar_v1_si_existe(dest: Path) -> dict | None:
    v1 = dest / "metricas_lenguaje_ciudadano_v1.json"
    csv = dest / "resultados_lenguaje_ciudadano_v1.csv"
    ref = dest / "etiquetas_referencia_v1.csv"
    if not (v1.is_file() and csv.is_file() and ref.is_file()):
        return None
    metricas = json.loads(v1.read_text(encoding="utf-8"))
    resultados = pd.read_csv(csv)
    referencia = pd.read_csv(ref)
    por = dest / "resumen_categoria_v1.csv"
    return {
        "bloqueo": False,
        "conservado": True,
        "metricas": metricas,
        "resultados": resultados,
        "referencia": referencia,
        "por_categoria": pd.read_csv(por) if por.is_file() else None,
        "salidas": dest,
        "v1": str(v1),
    }


def evaluar_linea_base(salidas: Path | None = None, timeout: float = 45.0) -> dict:
    dest = Path(salidas) if salidas else ruta_salidas_nlq()
    dest.mkdir(parents=True, exist_ok=True)
    v1 = dest / "metricas_lenguaje_ciudadano_v1.json"
    existente = _cargar_v1_si_existe(dest)
    if existente:
        existente["metricas"] = dict(existente["metricas"])
        existente["metricas"]["aviso_archivo"] = "v1 conservada; no se reconsulta ni se sobrescribe."
        return existente
    filas_excel = cargar_excel()
    part = partir(filas_excel)
    if part["n_excel"] != 77:
        raise AssertionError(f"Se esperaban 77 filas; hay {part['n_excel']}.")
    if part["n_reservadas"] != 26 or part["n_desarrollo"] != 51:
        raise AssertionError(part)
    if part["faltan_reservados"]:
        raise AssertionError(f"Faltan reservados en el Excel: {part['faltan_reservados']}")
    errores_et = comprobar_etiquetas(part["ids_desarrollo"])
    if errores_et:
        raise AssertionError(errores_et)

    etiquetas = por_id()
    ref_rows = []
    for f in part["desarrollo"]:
        e = dict(etiquetas[f["id"]])
        e.update({
            "pregunta": f["pregunta"],
            "categoria": f["categoria"],
            "intencion_excel": f["intencion_excel"],
            "filtros_excel": f["filtros_excel"],
            "ambigua_excel": f["ambigua_excel"],
            "comportamiento_excel": f["comportamiento_excel"],
        })
        ref_rows.append(e)
    ref = pd.DataFrame(ref_rows)
    ref.to_csv(dest / "etiquetas_referencia_v1.csv", index=False, encoding="utf-8")

    diag = diagnosticar_chat()
    if not diag["disponible"]:
        informe = {
            "generado_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "bloqueo": True,
            "motivo": "POST /api/chat no está alcanzable desde Jupyter.",
            "diagnostico": diag,
            "n_excel": 77,
            "n_desarrollo": 51,
            "n_reservadas": 26,
            "aviso": "No se inventan métricas. Hay que revisar la red tesis-network sin cambiar el contrato.",
        }
        _guardar(dest / "diagnostico_chat_v1.json", informe)
        return {"bloqueo": True, "metricas": informe, "salidas": dest, "referencia": ref}

    url = diag["url"]
    resultados = []
    for e in ref_rows:
        if e["id"] in IDS_RESERVADOS:
            raise RuntimeError(f"Se intentó evaluar un reservado: {e['id']}")
        resp = preguntar_chat(e["pregunta"], url, timeout=timeout)
        body = resp["body"] or {}
        tipo = tipo_respuesta(resp["http"], body, resp["error_infra"])
        infra = tipo == "error_infra"
        intent = body.get("intent")
        slots = body.get("slots") or {}
        iok = False if infra else _intencion_ok(e, body, tipo)
        fok, fdet = (False, "infra") if infra else _filtros_ok(e, body)
        mok = False if infra else _metrica_ok(e, body)
        riesgo = None if infra else riesgo_enganoso(e, body, tipo)
        interp = (not infra) and iok and fok and mok and tipo == e["comportamiento_esperado"]
        resultados.append({
            "id": e["id"],
            "categoria": e["categoria"],
            "familia": e["familia"],
            "pregunta": e["pregunta"],
            "intencion_excel": e["intencion_excel"],
            "intencion_esperada": e["intencion_esperada"],
            "operacion_esperada": e["operacion_esperada"],
            "metrica_esperada": e["metrica_esperada"],
            "capacidad": e["capacidad"],
            "comportamiento_esperado": e["comportamiento_esperado"],
            "http": resp["http"],
            "segundos": resp["segundos"],
            "error_infra": resp["error_infra"],
            "intent_observado": intent,
            "operacion_observada": slots.get("operacion"),
            "metrica_observada": slots.get("metrica"),
            "territorio_observado": slots.get("territorio"),
            "entidad_observada": slots.get("entidad"),
            "modalidad_observada": slots.get("modalidad"),
            "n_data": len(body["data"]) if isinstance(body.get("data"), list) else (1 if body.get("data") else 0),
            "tipo_respuesta": tipo,
            "intencion_ok": iok,
            "filtros_ok": fok,
            "filtros_detalle": fdet,
            "metrica_ok": mok,
            "interpretacion_ok": interp,
            "riesgo_enganoso": riesgo,
            "tipo_error": _tipo_error(e, tipo, iok, fok, infra),
            "aclaro": tipo == "aclarar",
            "rechazo": tipo == "rechazar",
            "ejecuto": tipo == "ejecutar",
            "texto": _recortar(body.get("text") or body.get("error") or resp["error_infra"]),
        })

    res = pd.DataFrame(resultados)
    res.to_csv(dest / "resultados_lenguaje_ciudadano_v1.csv", index=False, encoding="utf-8")
    validos = res[res["tipo_respuesta"] != "error_infra"]
    n_ok = int(len(validos))
    def _pct(serie) -> float | None:
        if n_ok == 0:
            return None
        return round(float(serie.sum()) / n_ok, 4)

    eje = validos[validos["comportamiento_esperado"] == "ejecutar"]
    acl = validos[validos["comportamiento_esperado"] == "aclarar"]
    rec = validos[validos["comportamiento_esperado"] == "rechazar"]
    ejec_val = eje[eje["tipo_respuesta"] == "ejecutar"] if len(eje) else eje

    matriz = {}
    for esp in ("ejecutar", "aclarar", "rechazar"):
        sub = validos[validos["comportamiento_esperado"] == esp]
        matriz[esp] = {
            t: int((sub["tipo_respuesta"] == t).sum())
            for t in ("ejecutar", "aclarar", "rechazar", "error_infra")
        }

    por_cat = (
        validos.groupby("categoria", dropna=False)
        .agg(
            n=("id", "size"),
            interpretacion_ok=("interpretacion_ok", "sum"),
            riesgo=("riesgo_enganoso", lambda s: int(s.notna().sum())),
            aclaro=("aclaro", "sum"),
            rechazo=("rechazo", "sum"),
            ejecuto=("ejecuto", "sum"),
        )
        .reset_index()
    )
    por_cat["exactitud"] = (por_cat["interpretacion_ok"] / por_cat["n"]).round(4)

    por_fam = (
        validos.groupby("familia", dropna=False)
        .agg(n=("id", "size"), interpretacion_ok=("interpretacion_ok", "sum"))
        .reset_index()
    )
    por_fam["exactitud"] = (por_fam["interpretacion_ok"] / por_fam["n"]).round(4)

    errores = (
        validos[validos["tipo_error"] != "ninguno"]
        .groupby("tipo_error")["id"].count()
        .to_dict()
    )

    metricas = {
        "generado_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "version": "v1_linea_base",
        "aviso": (
            "Línea base del prototipo actual, sin glosario ni cambios de NLQ. "
            "Las 26 EC reservadas no se usaron. No es validación final."
        ),
        "n_excel": 77,
        "n_desarrollo": 51,
        "n_reservadas": 26,
        "n_evaluadas": int(len(res)),
        "n_infra": int((res["tipo_respuesta"] == "error_infra").sum()),
        "n_validas": n_ok,
        "url": url,
        "diagnostico": diag,
        "capacidades": CAPACIDADES,
        "exactitud_interpretacion": _pct(validos["interpretacion_ok"]),
        "exactitud_intencion": _pct(validos["intencion_ok"]),
        "exactitud_filtros": (
            round(float(ejec_val["filtros_ok"].mean()), 4) if len(ejec_val) else None
        ),
        "exactitud_comportamiento": round(
            float((validos["tipo_respuesta"] == validos["comportamiento_esperado"]).mean()), 4
        ) if n_ok else None,
        "pct_aclaraciones_adecuadas": (
            round(float((acl["tipo_respuesta"] == "aclarar").mean()), 4) if len(acl) else None
        ),
        "pct_rechazo_correcto": (
            round(float((rec["tipo_respuesta"] == "rechazar").mean()), 4) if len(rec) else None
        ),
        "n_riesgo_enganoso": int(validos["riesgo_enganoso"].notna().sum()),
        "n_esperado_ejecutar": int(len(eje)),
        "n_esperado_aclarar": int(len(acl)),
        "n_esperado_rechazar": int(len(rec)),
        "segundos_medio": round(float(validos["segundos"].mean()), 3) if n_ok else None,
        "errores_por_tipo": errores,
        "matriz_confusion_comportamiento": matriz,
        "por_categoria": por_cat.to_dict(orient="records"),
        "por_familia": por_fam.to_dict(orient="records"),
        "ids_riesgo": validos.loc[validos["riesgo_enganoso"].notna(), "id"].tolist(),
        "ids_ok": validos.loc[validos["interpretacion_ok"], "id"].tolist(),
        "ids_error": validos.loc[~validos["interpretacion_ok"], "id"].tolist(),
    }
    if v1.exists():
        metricas["aviso_archivo"] = "v1 ya existía; se conserva el archivo previo y se escribe v1_reejecucion."
        _guardar(dest / "metricas_lenguaje_ciudadano_v1_reejecucion.json", metricas)
    else:
        _guardar(v1, metricas)
    _guardar(dest / "matriz_confusion_comportamiento_v1.json", matriz)
    por_cat.to_csv(dest / "resumen_categoria_v1.csv", index=False, encoding="utf-8")
    return {
        "bloqueo": False,
        "metricas": metricas,
        "resultados": res,
        "referencia": ref,
        "por_categoria": por_cat,
        "salidas": dest,
        "v1": str(v1),
    }


def _guardar(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def evaluar_v2(salidas: Path | None = None, timeout: float = 45.0) -> dict:
    """Misma 51 y mismas etiquetas. Escribe v2; no pisa v1."""
    dest = Path(salidas) if salidas else ruta_salidas_nlq()
    v1 = _cargar_v1_si_existe(dest)
    if not v1:
        raise FileNotFoundError("Falta la línea base v1; no se evalúa v2 sin ella.")
    ref = v1["referencia"]
    if "id" not in ref.columns:
        raise ValueError("etiquetas_referencia_v1.csv no tiene id")
    etiquetas = por_id()
    ref_rows = []
    for _, row in ref.iterrows():
        eid = str(row["id"])
        if eid in IDS_RESERVADOS:
            raise RuntimeError(f"v2 usó un reservado: {eid}")
        e = dict(etiquetas[eid])
        e.update({
            "pregunta": row["pregunta"],
            "categoria": row["categoria"],
            "intencion_excel": row.get("intencion_excel"),
            "filtros_excel": row.get("filtros_excel"),
            "ambigua_excel": row.get("ambigua_excel"),
            "comportamiento_excel": row.get("comportamiento_excel"),
        })
        ref_rows.append(e)
    diag = diagnosticar_chat()
    if not diag["disponible"]:
        return {"bloqueo": True, "metricas": {"motivo": "chat no alcanzable", "diagnostico": diag}, "salidas": dest}

    url = diag["url"]
    resultados = []
    for e in ref_rows:
        resp = preguntar_chat(e["pregunta"], url, timeout=timeout)
        body = resp["body"] or {}
        tipo = tipo_respuesta(resp["http"], body, resp["error_infra"])
        infra = tipo == "error_infra"
        slots = body.get("slots") or {}
        iok = False if infra else _intencion_ok(e, body, tipo)
        fok, fdet = (False, "infra") if infra else _filtros_ok(e, body)
        mok = False if infra else _metrica_ok(e, body)
        riesgo = None if infra else riesgo_enganoso(e, body, tipo)
        interp = (not infra) and iok and fok and mok and tipo == e["comportamiento_esperado"]
        resultados.append({
            "id": e["id"],
            "categoria": e["categoria"],
            "familia": e["familia"],
            "pregunta": e["pregunta"],
            "intencion_esperada": e["intencion_esperada"],
            "operacion_esperada": e["operacion_esperada"],
            "metrica_esperada": e["metrica_esperada"],
            "capacidad": e["capacidad"],
            "comportamiento_esperado": e["comportamiento_esperado"],
            "http": resp["http"],
            "segundos": resp["segundos"],
            "error_infra": resp["error_infra"],
            "intent_observado": body.get("intent"),
            "operacion_observada": slots.get("operacion"),
            "metrica_observada": slots.get("metrica"),
            "territorio_observado": slots.get("territorio"),
            "entidad_observada": slots.get("entidad"),
            "modalidad_observada": slots.get("modalidad"),
            "n_data": len(body["data"]) if isinstance(body.get("data"), list) else (1 if body.get("data") else 0),
            "tipo_respuesta": tipo,
            "intencion_ok": iok,
            "filtros_ok": fok,
            "filtros_detalle": fdet,
            "metrica_ok": mok,
            "interpretacion_ok": interp,
            "riesgo_enganoso": riesgo,
            "tipo_error": _tipo_error(e, tipo, iok, fok, infra),
            "aclaro": tipo == "aclarar",
            "rechazo": tipo == "rechazar",
            "ejecuto": tipo == "ejecutar",
            "texto": _recortar(body.get("text") or body.get("error") or resp["error_infra"]),
        })
    res = pd.DataFrame(resultados)
    res.to_csv(dest / "resultados_lenguaje_ciudadano_v2.csv", index=False, encoding="utf-8")
    validos = res[res["tipo_respuesta"] != "error_infra"]
    n_ok = int(len(validos))

    def _pct(serie):
        if n_ok == 0:
            return None
        return round(float(serie.sum()) / n_ok, 4)

    eje = validos[validos["comportamiento_esperado"] == "ejecutar"]
    acl = validos[validos["comportamiento_esperado"] == "aclarar"]
    rec = validos[validos["comportamiento_esperado"] == "rechazar"]
    ejec_val = eje[eje["tipo_respuesta"] == "ejecutar"] if len(eje) else eje
    matriz = {}
    for esp in ("ejecutar", "aclarar", "rechazar"):
        sub = validos[validos["comportamiento_esperado"] == esp]
        matriz[esp] = {t: int((sub["tipo_respuesta"] == t).sum()) for t in ("ejecutar", "aclarar", "rechazar", "error_infra")}
    por_cat = (
        validos.groupby("categoria", dropna=False)
        .agg(n=("id", "size"), interpretacion_ok=("interpretacion_ok", "sum"),
             riesgo=("riesgo_enganoso", lambda s: int(s.notna().sum())))
        .reset_index()
    )
    por_cat["exactitud"] = (por_cat["interpretacion_ok"] / por_cat["n"]).round(4)
    v1m = v1["metricas"]
    v1res = v1["resultados"]
    ok1 = set(v1m.get("ids_ok") or [])
    ok2 = set(validos.loc[validos["interpretacion_ok"], "id"].tolist())
    metricas = {
        "generado_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "version": "v2_glosario_minimo",
        "aviso": (
            "Comparación con v1. Mismas 51 etiquetas. No se usaron los 26 reservados. "
            "No se pisó metricas_lenguaje_ciudadano_v1.json."
        ),
        "n_excel": 77,
        "n_desarrollo": 51,
        "n_reservadas": 26,
        "n_evaluadas": int(len(res)),
        "n_infra": int((res["tipo_respuesta"] == "error_infra").sum()),
        "n_validas": n_ok,
        "url": url,
        "diagnostico": diag,
        "exactitud_interpretacion": _pct(validos["interpretacion_ok"]),
        "exactitud_intencion": _pct(validos["intencion_ok"]),
        "exactitud_filtros": round(float(ejec_val["filtros_ok"].mean()), 4) if len(ejec_val) else None,
        "exactitud_comportamiento": round(float((validos["tipo_respuesta"] == validos["comportamiento_esperado"]).mean()), 4) if n_ok else None,
        "pct_aclaraciones_adecuadas": round(float((acl["tipo_respuesta"] == "aclarar").mean()), 4) if len(acl) else None,
        "pct_rechazo_correcto": round(float((rec["tipo_respuesta"] == "rechazar").mean()), 4) if len(rec) else None,
        "n_riesgo_enganoso": int(validos["riesgo_enganoso"].notna().sum()),
        "matriz_confusion_comportamiento": matriz,
        "por_categoria": por_cat.to_dict(orient="records"),
        "ids_ok": sorted(ok2),
        "ids_error": validos.loc[~validos["interpretacion_ok"], "id"].tolist(),
        "ids_riesgo": validos.loc[validos["riesgo_enganoso"].notna(), "id"].tolist(),
        "comparacion_v1": {
            "exactitud_interpretacion_v1": v1m.get("exactitud_interpretacion"),
            "exactitud_interpretacion_v2": _pct(validos["interpretacion_ok"]),
            "aclaraciones_v1": v1m.get("pct_aclaraciones_adecuadas"),
            "aclaraciones_v2": round(float((acl["tipo_respuesta"] == "aclarar").mean()), 4) if len(acl) else None,
            "rechazo_v1": v1m.get("pct_rechazo_correcto"),
            "rechazo_v2": round(float((rec["tipo_respuesta"] == "rechazar").mean()), 4) if len(rec) else None,
            "riesgo_v1": v1m.get("n_riesgo_enganoso"),
            "riesgo_v2": int(validos["riesgo_enganoso"].notna().sum()),
            "corregidos": sorted(ok2 - ok1),
            "regresiones": sorted(ok1 - ok2),
        },
    }
    _guardar(dest / "metricas_lenguaje_ciudadano_v2.json", metricas)
    _guardar(dest / "matriz_confusion_comportamiento_v2.json", matriz)
    por_cat.to_csv(dest / "resumen_categoria_v2.csv", index=False, encoding="utf-8")
    return {
        "bloqueo": False,
        "metricas": metricas,
        "resultados": res,
        "referencia": ref,
        "por_categoria": por_cat,
        "v1": v1res,
        "salidas": dest,
    }
