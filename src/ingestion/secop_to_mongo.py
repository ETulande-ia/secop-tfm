
"""
Ingesta por lotes de SECOP II hacia MongoDB, con offset reanudable y upsert.

Funciones:
- get_last_offset(): Lee el último offset procesado.
- save_offset(): Guarda el punto de control.
- save_to_mongo(): Inserta o actualiza un lote.
- ingest_dataset(): Descarga un conjunto y lo persiste.
- ingestar_periodo(): Ingesta procesos y contratos de un periodo.
- ingest(): Lanza la ingesta configurada por variables de entorno.
"""

import os
import time
from datetime import datetime

from pymongo import MongoClient, UpdateOne, errors
from secop_api import (
    api_parece_muestra_limitada,
    asegurar_id_fila,
    count_secop_records,
    fetch_secop_data,
    select_fields_con_row_id,
    verificar_row_id,
)

# ========================
# Configuración por ENV
# ========================
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("MONGO_DB")
COLLECTION_NAME = os.getenv("MONGO_COLLECTION")

STATE_COLLECTION = "ingestion_state"

DATASET_ID = os.getenv("DATASET_ID", "p6dx-8zbt")
START_DATE = os.getenv("START_DATE", "2025-01-01")
END_DATE = os.getenv("END_DATE") or None

BATCH_SIZE = int(os.getenv("BATCH_SIZE", "5000"))
SLEEP_SECONDS = int(os.getenv("SLEEP_SECONDS", "1"))

SOURCE_NAME = DATASET_ID   # clave lógica del checkpoint


RAW_DATE_FIELD = os.getenv("DATE_FIELD")

# Normalizar: NONE / vacío / null → None
DATE_FIELD = None
if RAW_DATE_FIELD and RAW_DATE_FIELD.upper() != "NONE":
    DATE_FIELD = RAW_DATE_FIELD


# ========================
# Checkpoint helpers
# ========================
def get_last_offset(state_collection, source=None, date_field=None):
    source = SOURCE_NAME if source is None else source
    date_field = DATE_FIELD if date_field is None else date_field
    state = state_collection.find_one({
        "source": source,
        "date_field": date_field
    })
    return state["last_offset"] if state else 0


def save_offset(state_collection, offset, source=None, date_field=None):
    source = SOURCE_NAME if source is None else source
    date_field = DATE_FIELD if date_field is None else date_field
    state_collection.update_one(
        {
            "source": source,
            "date_field": date_field
        },
        {
            "$set": {
                "last_offset": offset,
                "updated_at": datetime.utcnow()
            }
        },
        upsert=True
    )


# ========================
# Persistencia de datos
# ========================
def save_to_mongo(collection, records, pk="id_del_proceso"):
    now = datetime.utcnow()
    ops = []
    for r in records:
        r["_ingestion_ts"] = now
        key = r.get(pk)
        if key is None:
            continue
        ops.append(UpdateOne({pk: key}, {"$set": r}, upsert=True))
    if not ops:
        return
    try:
        collection.bulk_write(ops, ordered=False)
    except errors.BulkWriteError as e:
        print(f"[ERROR] Fallo Mongo en lote: {e.details.get('writeErrors', [])[:3]}")
    except errors.PyMongoError as e:
        print(f"[ERROR] Fallo Mongo: {e}")


def ensure_unique_index(collection, pk):
    collection.create_index(pk, unique=True, sparse=True)


def ingest_dataset(
    data_collection,
    state_collection,
    dataset_id,
    pk,
    date_field=None,
    start_date="2025-01-01",
    end_date=None,
    batch_size=None,
    sleep_seconds=None,
    source_name=None,
    extra_fields=None,
    order_field=None,
    expected_count=None,
    select_fields=None,
    include_row_id=False,
    usar_socrata_id=True,
    resume=True,
    dataset_capped=False,
):
    """Ingesta paginada con upsert por fila. No limpia ni agrega."""
    batch_size = BATCH_SIZE if batch_size is None else batch_size
    sleep_seconds = SLEEP_SECONDS if sleep_seconds is None else sleep_seconds
    source_name = dataset_id if source_name is None else source_name
    extra_fields = extra_fields or {}
    cap_anonimo = 1000

    if include_row_id and not select_fields:
        peek = fetch_secop_data(
            dataset_id=dataset_id,
            limit=1,
            offset=0,
            date_field=date_field,
            start_date=start_date,
            end_date=end_date,
        )
        select_fields = select_fields_con_row_id(peek if isinstance(peek, list) else [])
        if order_field is None and usar_socrata_id:
            order_field = ":id"

    if order_field is None:
        order_field = pk

    ensure_unique_index(data_collection, pk)
    offset = get_last_offset(state_collection, source_name, date_field) if resume else 0
    if not resume:
        save_offset(state_collection, 0, source_name, date_field)
    total = 0
    skipped = 0
    paginas = 0
    ultimo_lote = 0
    error = False
    truncado = False
    ids_repetidos_lote = 0
    contador_hash = {}

    print(
        f"[INFO] Iniciando ingesta "
        f"(dataset={dataset_id}, campo_fecha={date_field}, "
        f"start_date={start_date}, end_date={end_date}) "
        f"desde offset={offset}"
    )

    while True:
        try:
            records = fetch_secop_data(
                dataset_id=dataset_id,
                limit=batch_size,
                offset=offset,
                date_field=date_field,
                start_date=start_date,
                end_date=end_date,
                order_field=order_field,
                select_fields=select_fields,
            )

            if not isinstance(records, list):
                print("[FATAL] La API no devolvió una lista.")
                error = True
                break

            if not records:
                print("[INFO] No hay más registros. Fin del proceso.")
                break

            paginas += 1
            ultimo_lote = len(records)

            valid = []
            vistos = set()
            for r in records:
                if include_row_id:
                    r = asegurar_id_fila(r, usar_socrata_id, contador_hash)
                if not r.get(pk):
                    skipped += 1
                    continue
                clave = r.get(pk)
                if clave in vistos:
                    ids_repetidos_lote += 1
                vistos.add(clave)
                fila = dict(r)
                fila.update(extra_fields)
                valid.append(fila)

            if valid:
                save_to_mongo(data_collection, valid, pk=pk)

            offset += len(records)
            total += len(valid)
            save_offset(state_collection, offset, source_name, date_field)

            print(f"[OK] Upsert lote={len(valid)} acumulado={total} offset={offset}")

            tope_mil = ultimo_lote == cap_anonimo and batch_size > cap_anonimo
            if tope_mil:
                siguiente = fetch_secop_data(
                    dataset_id=dataset_id,
                    limit=1,
                    offset=offset,
                    date_field=date_field,
                    start_date=start_date,
                    end_date=end_date,
                    order_field=order_field,
                    select_fields=select_fields,
                )
                if not siguiente:
                    if (expected_count or 0) > cap_anonimo:
                        truncado = True
                        print(
                            "[WARN] Respuesta truncada: la API devolvió "
                            f"{cap_anonimo} filas y no hay página siguiente."
                        )
                    elif dataset_capped:
                        truncado = True
                        print(
                            "[WARN] Cobertura parcial: la fuente parece limitada "
                            f"a {cap_anonimo} filas publicadas."
                        )
                    print("[INFO] Se almacenan todas las filas accesibles.")
                    break

            if ultimo_lote < batch_size and not tope_mil:
                print("[INFO] Última página (lote menor que el tamaño pedido).")
                break

            time.sleep(sleep_seconds)

        except Exception as e:
            print(f"[FATAL] Error en offset={offset}: {e}")
            print("[FATAL] Proceso detenido de forma controlada.")
            error = True
            break

    completo = (not error) and (not truncado)
    return {
        "upserted": total,
        "skipped_sin_pk": skipped,
        "offset": offset,
        "paginas": paginas,
        "ultimo_lote": ultimo_lote,
        "error": error,
        "truncado": truncado,
        "completo": completo,
        "ids_repetidos_lote": ids_repetidos_lote,
        "pk": pk,
        "order_field": order_field,
    }


def contar_distintos(collection, campo, filtro):
    pipeline = [
        {"$match": filtro},
        {"$group": {"_id": f"${campo}"}},
        {"$count": "n"},
    ]
    filas = list(collection.aggregate(pipeline, allowDiskUse=True))
    return int(filas[0]["n"]) if filas else 0


def ingestar_periodo(
    db,
    fuente,
    dataset_id,
    date_field,
    coleccion,
    pk_negocio,
    start_date,
    end_date,
    periodo,
    nombre=None,
    pk_fila="socrata_id",
    state_col="ingestion_state",
    batch_size=None,
    sleep_seconds=None,
    cap_anonimo=1000,
    proteger=("procesos_raw", "contratos_raw"),
    resume=False,
):
    """Valida :id, pagina y guarda todas las filas. No limpia ni consolida."""
    if coleccion in proteger:
        raise RuntimeError(f"La colección de destino no puede ser {coleccion}.")

    batch_size = BATCH_SIZE if batch_size is None else batch_size
    sleep_seconds = SLEEP_SECONDS if sleep_seconds is None else sleep_seconds
    nombre = dataset_id if nombre is None else nombre

    muestra = fetch_secop_data(
        dataset_id=dataset_id,
        limit=3,
        offset=0,
        date_field=date_field,
        start_date=start_date,
        end_date=end_date,
    )
    n_api = count_secop_records(
        dataset_id=dataset_id,
        date_field=date_field,
        start_date=start_date,
        end_date=end_date,
    )
    tope = api_parece_muestra_limitada(dataset_id, cap=cap_anonimo)
    pagina_1k = fetch_secop_data(
        dataset_id=dataset_id,
        limit=1,
        offset=cap_anonimo,
        date_field=date_field,
        start_date=start_date,
        end_date=end_date,
    )
    pk_ok = bool(muestra) and pk_negocio in muestra[0]
    fecha_ok = bool(muestra) and date_field in muestra[0]
    row_id = verificar_row_id(
        dataset_id=dataset_id,
        date_field=date_field,
        start_date=start_date,
        end_date=end_date,
    )

    print("=" * 60)
    print(fuente, "|", nombre, "|", dataset_id)
    print("count API del mes:", f"{n_api:,}".replace(",", "."))
    print("count API sin filtro:", f"{tope['count_sin_filtro']:,}".replace(",", "."))
    print("Muestra publicada limitada:", tope["limitada"])
    print("muestra mes:", 0 if not muestra else len(muestra), "| PK negocio ok:", pk_ok, "| fecha ok:", fecha_ok)
    print("Fila mes en offset 1000:", bool(pagina_1k))
    print("Identificador de fila:", row_id["motivo"])
    print(
        "  :id disponible:", row_id["disponible"],
        "| único:", row_id["unico_en_pagina"],
        "| estable:", row_id["estable"],
        "| sin solape:", row_id["sin_solape"],
    )

    resultado = {
        "fuente": fuente,
        "dataset_id": dataset_id,
        "coleccion": coleccion,
        "n_api": n_api,
        "recuperadas": 0,
        "almacenadas": 0,
        "pk_fila": pk_fila,
        "id_usado": "socrata_id (:id)" if row_id["usar"] else "clave técnica",
        "estado": "OMITIDA",
        "motivo": "",
        "n_negocio": 0,
    }
    problemas = []
    if not muestra and n_api > 0:
        problemas.append("count(*) > 0 pero no hay muestra.")
    if muestra and (not pk_ok or not fecha_ok):
        problemas.append(f"No aparecen {pk_negocio} o {date_field}.")
    if problemas:
        resultado["motivo"] = "; ".join(problemas)
        print("VALIDACIÓN: no se inicia esta fuente.")
        for item in problemas:
            print("-", item)
        return resultado

    stats = ingest_dataset(
        data_collection=db[coleccion],
        state_collection=db[state_col],
        dataset_id=dataset_id,
        pk=pk_fila,
        date_field=date_field,
        start_date=start_date,
        end_date=end_date,
        batch_size=batch_size,
        sleep_seconds=sleep_seconds,
        source_name=f"{dataset_id}:{periodo}:{date_field}:filas",
        extra_fields={
            "_dataset_id": dataset_id,
            "_periodo": periodo,
            "_fuente": fuente,
            "_nivel": "filas",
        },
        order_field=":id" if row_id["usar"] else pk_negocio,
        expected_count=n_api,
        select_fields=row_id.get("select_fields"),
        include_row_id=True,
        usar_socrata_id=row_id["usar"],
        resume=resume,
        dataset_capped=tope["limitada"],
    )

    filtro = {"_periodo": periodo, "_fuente": fuente}
    n_mongo = db[coleccion].count_documents(filtro)
    n_pk = contar_distintos(db[coleccion], pk_fila, filtro)
    n_negocio = contar_distintos(db[coleccion], pk_negocio, filtro)
    recuperadas = stats.get("offset") or 0
    coinciden = n_mongo == recuperadas == n_pk
    if stats.get("error"):
        estado = "ERROR"
        motivo = "fallo durante la paginación"
    elif not coinciden:
        estado = "INCOMPLETA"
        motivo = (
            "Mongo no coincide con las filas recuperadas; "
            "posible identificador repetido. No se consolida por id de negocio."
        )
        print("[WARN]", motivo)
        print("  recuperadas:", recuperadas, "| almacenadas:", n_mongo, "| pk distintas:", n_pk)
        print("  ids repetidos en lote:", stats.get("ids_repetidos_lote"))
    elif stats.get("truncado") or tope["limitada"]:
        estado = "PARCIAL"
        motivo = (
            "Se almacenaron todas las filas accesibles, "
            "pero la cobertura completa no se puede confirmar "
            f"(tope publicado {cap_anonimo})."
        )
    elif n_api > 0 and recuperadas != n_api:
        estado = "INCOMPLETA"
        motivo = f"count(*)={n_api} distinto de filas recuperadas={recuperadas}"
    else:
        estado = "COMPLETA"
        motivo = "Filas recuperadas = almacenadas = count(*) del mes."

    resultado.update({
        "recuperadas": recuperadas,
        "almacenadas": n_mongo,
        "n_negocio": n_negocio,
        "n_pk": n_pk,
        "paginas": stats.get("paginas"),
        "skipped": stats.get("skipped_sin_pk"),
        "estado": estado,
        "motivo": motivo,
        "truncado": stats.get("truncado"),
        "error": stats.get("error"),
        "filtro": filtro,
    })
    print("Upsert esta ejecución:", f"{stats.get('upserted', 0):,}".replace(",", "."))
    print(
        "Recuperadas:", f"{recuperadas:,}".replace(",", "."),
        "| almacenadas:", f"{n_mongo:,}".replace(",", "."),
        "| pk fila:", f"{n_pk:,}".replace(",", "."),
    )
    print("Claves de negocio distintas:", f"{n_negocio:,}".replace(",", "."))
    print("Estado:", estado, "|", motivo)
    return resultado


# ========================
# Proceso principal
# ========================
def ingest():
    client = MongoClient(MONGO_URI)

    db = client[DB_NAME]
    data_collection = db[COLLECTION_NAME]
    state_collection = db[STATE_COLLECTION]

    ingest_dataset(
        data_collection=data_collection,
        state_collection=state_collection,
        dataset_id=DATASET_ID,
        pk="id_del_proceso",
        date_field=DATE_FIELD,
        start_date=START_DATE,
        end_date=END_DATE,
        source_name=SOURCE_NAME,
    )


if __name__ == "__main__":
    ingest()
    print("Ingesta finalizada.")
