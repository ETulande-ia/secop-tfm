"""
Matriz de características de contratos.

Funciones:
- a_pandas(): Convierte el DataFrame de Spark a pandas.
- partir_universo(): Separa aptos, ceros y extremos.
- informe_plazo(): Resume la cobertura del plazo de ejecución.
- enriquecer(): Añade variables derivadas.
- matriz(): Escala las variables numéricas y arma la matriz del modelo.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.preprocessing import RobustScaler

DIAS_MAX = 3650  # 10 años; por encima se considera plazo no usable
N_MODALIDADES = 6
COLS_META = [
    "id_contrato",
    "socrata_id",
    "nombre_entidad",
    "departamento",
    "ciudad",
    "proveedor_adjudicado",
    "modalidad_de_contratacion",
    "es_bogota",
    "estado_homologacion",
    "valor_del_contrato",
]


def a_pandas(df_spark) -> pd.DataFrame:
    pdf = df_spark.toPandas()
    for c in (
        "valor_apto_modelo",
        "valor_del_contrato_cero",
        "valor_del_contrato_extremo",
        "es_bogota",
    ):
        if c in pdf.columns:
            pdf[c] = pdf[c].astype(bool)
    pdf["valor_del_contrato"] = pd.to_numeric(pdf["valor_del_contrato"], errors="coerce")
    return pdf


def partir_universo(pdf: pd.DataFrame) -> dict[str, pd.DataFrame]:
    aptos = pdf[pdf["valor_apto_modelo"]].copy()
    ceros = pdf[pdf["valor_del_contrato_cero"]].copy()
    extremos = pdf[pdf["valor_del_contrato_extremo"]].copy()
    return {"todos": pdf, "aptos": aptos, "ceros": ceros, "extremos": extremos}


def informe_plazo(pdf: pd.DataFrame) -> dict:
    """Cobertura de fechas de ejecución. No imputa."""
    ini = pd.to_datetime(pdf["fecha_de_inicio_del_contrato"], errors="coerce")
    fin = pd.to_datetime(pdf["fecha_de_fin_del_contrato"], errors="coerce")
    firma = pd.to_datetime(pdf["fecha_de_firma"], errors="coerce")
    dias = (fin - ini).dt.days
    n = len(pdf)
    nulo = dias.isna().sum()
    neg_cero = int(((dias <= 0) & dias.notna()).sum())
    excesivo = int((dias > DIAS_MAX).sum())
    valido = (dias > 0) & (dias <= DIAS_MAX)
    n_ok = int(valido.sum())
    firma_ini = (ini - firma).dt.days
    return {
        "n": n,
        "fecha_inicio_nula": int(ini.isna().sum()),
        "fecha_fin_nula": int(fin.isna().sum()),
        "dias_nulos": int(nulo),
        "dias_le_0": neg_cero,
        "dias_gt_10a": excesivo,
        "dias_validos": n_ok,
        "pct_validos": round(100.0 * n_ok / max(n, 1), 2),
        "mediana_validos": None if n_ok == 0 else float(dias[valido].median()),
        "p95_validos": None if n_ok == 0 else float(dias[valido].quantile(0.95)),
        "firma_inicio_mediana": None
        if firma_ini.notna().sum() == 0
        else float(firma_ini.median()),
        "plazo_confiable": n_ok / max(n, 1) >= 0.70,
    }


def _modalidad_grupo(pdf: pd.DataFrame) -> pd.Series:
    top = (
        pdf["modalidad_de_contratacion"]
        .fillna("sin_dato")
        .astype(str)
        .value_counts()
        .head(N_MODALIDADES)
        .index
    )
    m = pdf["modalidad_de_contratacion"].fillna("sin_dato").astype(str)
    return m.where(m.isin(top), "otras")


def enriquecer(pdf: pd.DataFrame, n_entidad: pd.Series | None = None) -> pd.DataFrame:
    """Añade log-valor, residuo por modalidad, plazo y tamaño de entidad."""
    out = pdf.copy()
    out["log1p_valor"] = np.log1p(out["valor_del_contrato"].astype(float))
    out["log10_valor"] = np.log10(out["valor_del_contrato"].astype(float))
    out["modalidad_grupo"] = _modalidad_grupo(out)
    med = out.groupby("modalidad_grupo")["log1p_valor"].transform("median")
    out["log_valor_vs_modalidad"] = out["log1p_valor"] - med
    ini = pd.to_datetime(out["fecha_de_inicio_del_contrato"], errors="coerce")
    fin = pd.to_datetime(out["fecha_de_fin_del_contrato"], errors="coerce")
    dias = (fin - ini).dt.days
    valido = (dias > 0) & (dias <= DIAS_MAX)
    out["dias_ejecucion"] = np.where(valido, dias, np.nan)
    out["plazo_invalido"] = (~valido).astype(int)
    if n_entidad is None:
        n_map = out.groupby("nombre_entidad").size()
    else:
        n_map = n_entidad
    out["n_entidad"] = out["nombre_entidad"].map(n_map).fillna(1).astype(int)
    out["log1p_n_entidad"] = np.log1p(out["n_entidad"].astype(float))
    out["homologado"] = (out["estado_homologacion"] == "homologado").astype(int)
    out["es_bogota_int"] = out["es_bogota"].astype(int)
    return out


def conteo_entidad_mes(pdf_todos: pd.DataFrame) -> pd.Series:
    """Contratos por entidad en el mes completo (incluidos ceros). Índice: nombre."""
    return pdf_todos.groupby("nombre_entidad").size()


def redundancia(pdf: pd.DataFrame, columnas: list[str]) -> pd.DataFrame:
    num = pdf[columnas].apply(pd.to_numeric, errors="coerce")
    return num.corr(method="spearman")


def matriz(
    pdf: pd.DataFrame,
    numericas: list[str],
    dummies_modalidad: bool = False,
    imputar_plazo_mediana: bool = False,
    incluir_flag_plazo: bool = True,
) -> tuple[np.ndarray, list[str], RobustScaler | None]:
    """Escala solo numéricas (RobustScaler). No rellena plazos con 0.

    Si hay `dias_ejecucion` nulos y imputar_plazo_mediana, se usa la mediana
    de los válidos. `plazo_invalido` se añade solo si incluir_flag_plazo.
    """
    work = pdf.copy()
    nombres_num = []
    bloques = []
    for c in numericas:
        serie = pd.to_numeric(work[c], errors="coerce")
        if c == "dias_ejecucion" and imputar_plazo_mediana:
            med = float(serie.dropna().median()) if serie.notna().any() else 0.0
            serie = serie.fillna(med)
        if serie.isna().any():
            raise ValueError(f"Hay nulos en {c}; no se imputa 0.")
        nombres_num.append(c)
        bloques.append(serie.to_numpy().reshape(-1, 1))
    X_num = np.hstack(bloques) if bloques else np.zeros((len(work), 0))
    scaler = None
    if X_num.shape[1] > 0:
        scaler = RobustScaler()
        X_num = scaler.fit_transform(X_num)
    nombres = list(nombres_num)
    X = X_num
    if dummies_modalidad:
        dum = pd.get_dummies(work["modalidad_grupo"], prefix="mod", dtype=float)
        X = np.hstack([X, dum.to_numpy()]) if X.size else dum.to_numpy()
        nombres.extend(list(dum.columns))
    if (
        incluir_flag_plazo
        and "plazo_invalido" in work.columns
        and "dias_ejecucion" in numericas
    ):
        flag = work["plazo_invalido"].to_numpy().reshape(-1, 1).astype(float)
        X = np.hstack([X, flag])
        nombres.append("plazo_invalido")
    return X, nombres, scaler
