"""
Reconcilia conteos observados con los esperados del periodo.

Funciones:
- reconciliar(): Compara un conteo observado con el esperado.
- cuadro_control(): Arma el cuadro de controles.
- controles_ok(): Indica si todos los controles cuadran.
- controles_criticos_ok(): Indica si los controles críticos cuadran.
"""

from __future__ import annotations

ESPERADO = {
    "filas_api_procesos": 158_830,
    "socrata_id": 158_830,
    "procesos": 146_947,
    "pares_adjudicacion_confiables": 147_075,
    "pares_adjudicacion_ambiguos": 60,
    "pares_adjudicacion_cartesianos": 60,
    "filas_adjudicacion_confiable": 147_075,
    "filas_adjudicacion_ambigua": 60,
    "adjudicaciones_tipo_revisar": 0,
    "adjudicaciones_valor_usable": 147_003,
    "adjudicaciones_solapadas": 0,
    "adjudicaciones_usable_sin_monto": 0,
    "adjudicaciones_monto_negativo": 0,
    "contratos": 82_964,
    "filas_api_contratos": 82_964,
    "socrata_id_contratos": 82_964,
    "contratos_id_unicos": 82_964,
    "contratos_duplicados_id": 0,
    "contratos_valor_negativo": 0,
    "contratos_valor_cero": 506,
    "contratos_valor_extremo": 1,
    "contratos_fecha_nula": 0,
    "personas_parquet": 44_164_417,
    "personas_agregadas": 44_164_417,
    "poblacion_negativa": 0,
    "codigos_vacios": 0,
    "municipios_duplicados": 0,
}

CONTROLES_CRITICOS_PROCESOS = (
    "filas_api_procesos",
    "socrata_id",
    "procesos",
    "pares_adjudicacion_confiables",
    "pares_adjudicacion_ambiguos",
    "pares_adjudicacion_cartesianos",
    "filas_adjudicacion_confiable",
    "filas_adjudicacion_ambigua",
    "adjudicaciones_tipo_revisar",
    "adjudicaciones_valor_usable",
    "adjudicaciones_solapadas",
    "adjudicaciones_usable_sin_monto",
    "adjudicaciones_monto_negativo",
)

CONTROLES_CRITICOS_CONTRATOS = (
    "filas_api_contratos",
    "socrata_id_contratos",
    "contratos",
    "contratos_id_unicos",
    "contratos_duplicados_id",
    "contratos_valor_negativo",
    "contratos_valor_cero",
    "contratos_valor_extremo",
    "contratos_fecha_nula",
)

CONTROLES_CRITICOS_DANE = (
    "personas_parquet",
    "personas_agregadas",
    "poblacion_negativa",
    "codigos_vacios",
    "municipios_duplicados",
)

# Compatibilidad: el job de procesos usa esta tupla.
CONTROLES_CRITICOS = CONTROLES_CRITICOS_PROCESOS


def reconciliar(nombre: str, observado: int, esperado: int | None = None) -> dict:
    if esperado is None:
        esperado = ESPERADO.get(nombre)
    if esperado is None:
        return {
            "control": nombre,
            "observado": int(observado),
            "esperado": None,
            "diferencia": None,
            "ok": None,
            "nota": "sin cifra EDA",
        }
    obs = int(observado)
    exp = int(esperado)
    return {
        "control": nombre,
        "observado": obs,
        "esperado": exp,
        "diferencia": obs - exp,
        "ok": obs == exp,
        "nota": "coincide con EDA" if obs == exp else "discrepancia: no se fuerza el resultado",
    }


def cuadro_control(observado: dict) -> list:
    """Lista de controles para las claves presentes en `observado`."""
    filas = []
    for nombre, valor in observado.items():
        esperado = ESPERADO.get(nombre)
        filas.append(reconciliar(nombre, valor, esperado))
    return filas


def controles_ok(cuadro: list) -> bool:
    return all(f["ok"] in (True, None) for f in cuadro)


def controles_criticos_ok(cuadro: list, criticos: tuple | None = None) -> bool:
    nombres = criticos if criticos is not None else CONTROLES_CRITICOS
    por_nombre = {f["control"]: f for f in cuadro}
    for nombre in nombres:
        fila = por_nombre.get(nombre)
        if fila is None or fila["ok"] is not True:
            return False
    return True
