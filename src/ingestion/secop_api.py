
"""
Consulta la API Socrata de datos.gov.co con paginación, filtro de fecha y reintentos.

Funciones:
- get_headers(): Arma los encabezados, incluido el App Token.
- build_date_where(): Construye el filtro de fechas.
- fetch_secop_data(): Descarga una página del conjunto.
- select_fields_con_row_id(): Elige campos e incluye el identificador de fila.
- attach_socrata_id(): Copia el identificador de Socrata al registro.
- clave_tecnica_fila(): Construye la clave técnica de la fila.
- asegurar_id_fila(): Garantiza un identificador de fila.
- verificar_row_id(): Comprueba si el identificador de Socrata es utilizable.
- api_parece_muestra_limitada(): Detecta el tope publicado de filas.
- count_secop_records(): Cuenta los registros que cumplen el filtro.
"""

import hashlib
import json
import os
import time

import requests


#BASE_URL = "https://www.datos.gov.co/resource/p6dx-8zbt.json"

BASE_URL_TEMPLATE = "https://www.datos.gov.co/resource/{dataset_id}.json"


def get_headers():
    """Lee el App Token en cada llamada para no fijarlo al importar el módulo."""
    headers = {
        "User-Agent": "secop-ingestion-tfm/1.0",
        "Accept": "application/json",
    }
    token = os.getenv("SOCRATA_APP_TOKEN")
    if token:
        headers["X-App-Token"] = token
    return headers


# Compatibilidad con importaciones previas.
HEADERS = get_headers()


def build_date_where(
    date_field: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> str | None:
    """Filtro $where de Socrata: start inclusivo, end exclusivo."""
    if not date_field:
        return None
    clauses = []
    if start_date:
        clauses.append(f"{date_field} >= '{start_date}T00:00:00'")
    if end_date:
        clauses.append(f"{date_field} < '{end_date}T00:00:00'")
    return " AND ".join(clauses) if clauses else None


def _socrata_get(dataset_id: str, params: dict, retries: int = 3):
    base_url = BASE_URL_TEMPLATE.format(dataset_id=dataset_id)
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(
                base_url,
                headers=get_headers(),
                params=params,
                timeout=120,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            wait = 2 ** attempt
            print(f"[WARN] Error API (intento {attempt}/{retries}): {e}")
            time.sleep(wait)
    raise RuntimeError("Fallo permanente al consultar la API Socrata")


def fetch_secop_data(
    dataset_id: str,
    limit: int = 5000,
    offset: int = 0,
    date_field: str | None = None,
    start_date: str = "2025-01-01",
    retries: int = 3,
    end_date: str | None = None,
    order_field: str | None = None,
    select_fields=None,
    extra_where: str | None = None,
):
    params = {
        "$limit": limit,
        "$offset": offset,
    }

    clauses = []
    where_clause = build_date_where(date_field, start_date, end_date)
    if where_clause:
        clauses.append(where_clause)
    if extra_where:
        clauses.append(extra_where)
    if clauses:
        params["$where"] = " AND ".join(clauses)
    if order_field:
        params["$order"] = order_field
    if select_fields:
        if isinstance(select_fields, (list, tuple)):
            params["$select"] = ",".join(select_fields)
        else:
            params["$select"] = select_fields

    return _socrata_get(dataset_id, params, retries=retries)


def select_fields_con_row_id(muestra: list) -> list[str]:
    """`:id,*` no es válido en datos.gov.co; se listan columnas + :id."""
    if not muestra:
        return [":id"]
    cols = [k for k in muestra[0].keys() if k not in (":id", "socrata_id")]
    return [":id"] + cols


def attach_socrata_id(record: dict) -> dict:
    rid = record.get(":id") or record.get("socrata_id")
    if rid:
        record[":id"] = rid
        record["socrata_id"] = rid
    return record


def clave_tecnica_fila(record: dict, ocurrencia: int = 1) -> str:
    """Hash estable del contenido original. La ocurrencia distingue copias idénticas."""
    payload = {
        k: v
        for k, v in record.items()
        if not str(k).startswith("_") and k not in (":id", "socrata_id")
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return digest if ocurrencia <= 1 else f"{digest}:{ocurrencia}"


def asegurar_id_fila(record: dict, usar_socrata_id: bool, contador: dict) -> dict:
    """Asigna socrata_id desde :id o, si no es usable, una clave técnica."""
    rec = attach_socrata_id(dict(record))
    if usar_socrata_id and rec.get("socrata_id"):
        return rec
    base = clave_tecnica_fila(rec, 1)
    contador[base] = contador.get(base, 0) + 1
    rec["socrata_id"] = clave_tecnica_fila(rec, contador[base])
    rec["_clave_tecnica"] = True
    return rec


def verificar_row_id(
    dataset_id: str,
    date_field: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    page_size: int = 2000,
) -> dict:
    """Comprueba si :id es único, estable entre ejecuciones y sin solape entre páginas."""
    out = {
        "disponible": False,
        "unico_en_pagina": False,
        "estable": False,
        "sin_solape": False,
        "usar": False,
        "nulos": 0,
        "n_pagina_0": 0,
        "n_pagina_1": 0,
        "motivo": "",
        "select_fields": None,
    }
    peek = fetch_secop_data(
        dataset_id=dataset_id,
        limit=1,
        offset=0,
        date_field=date_field,
        start_date=start_date,
        end_date=end_date,
    )
    if not isinstance(peek, list) or not peek:
        out["motivo"] = "La API no devolvió muestra para inspeccionar :id."
        return out

    cols = select_fields_con_row_id(peek)
    out["select_fields"] = cols
    try:
        p0 = fetch_secop_data(
            dataset_id=dataset_id,
            limit=page_size,
            offset=0,
            date_field=date_field,
            start_date=start_date,
            end_date=end_date,
            order_field=":id",
            select_fields=cols,
        )
        p0b = fetch_secop_data(
            dataset_id=dataset_id,
            limit=page_size,
            offset=0,
            date_field=date_field,
            start_date=start_date,
            end_date=end_date,
            order_field=":id",
            select_fields=cols,
        )
        p1 = fetch_secop_data(
            dataset_id=dataset_id,
            limit=page_size,
            offset=page_size,
            date_field=date_field,
            start_date=start_date,
            end_date=end_date,
            order_field=":id",
            select_fields=cols,
        )
    except Exception as exc:
        out["motivo"] = f":id no se pudo consultar ({exc})."
        return out

    ids0 = [(r or {}).get(":id") for r in (p0 or [])]
    ids0b = [(r or {}).get(":id") for r in (p0b or [])]
    ids1 = [(r or {}).get(":id") for r in (p1 or [])]
    out["n_pagina_0"] = len(ids0)
    out["n_pagina_1"] = len(ids1)
    out["nulos"] = sum(1 for x in ids0 if not x)
    out["disponible"] = bool(ids0) and out["nulos"] == 0
    out["unico_en_pagina"] = out["disponible"] and len(ids0) == len(set(ids0))
    out["estable"] = ids0 == ids0b
    out["sin_solape"] = set(x for x in ids0 if x).isdisjoint(set(x for x in ids1 if x))
    out["usar"] = (
        out["disponible"]
        and out["unico_en_pagina"]
        and out["estable"]
        and (out["sin_solape"] or not ids1)
    )
    if out["usar"]:
        out["motivo"] = "Se usa :id de Socrata (socrata_id)."
    else:
        out["motivo"] = " :id no es usable; se genera clave técnica por fila."
    return out


def api_parece_muestra_limitada(
    dataset_id: str,
    cap: int = 1000,
) -> dict:
    """Detecta el tope publicado de 1.000 filas (sin filtro de mes)."""
    n = count_secop_records(dataset_id=dataset_id)
    siguiente = fetch_secop_data(dataset_id=dataset_id, limit=1, offset=cap)
    limitada = n <= cap and not siguiente
    return {"limitada": limitada, "count_sin_filtro": n, "hay_offset_cap": bool(siguiente)}


def count_secop_records(
    dataset_id: str,
    date_field: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    retries: int = 3,
) -> int:
    """Cuenta registros con count(*). Sin App Token el resultado puede estar capado."""
    params = {"$select": "count(*)"}
    where_clause = build_date_where(date_field, start_date, end_date)
    if where_clause:
        params["$where"] = where_clause
    data = _socrata_get(dataset_id, params, retries=retries)
    if isinstance(data, list) and data:
        return int(data[0].get("count", 0))
    return 0
