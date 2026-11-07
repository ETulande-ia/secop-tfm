const { queryDB } = require('../db/postgres');
const { periodo: periodoDefecto } = require('../config');

const ANIO_POBLACION = 2018;
const NOTA =
  'La población corresponde al CNPV 2018. Los contratos son de septiembre de 2026 y se refieren a la sede de la entidad contratante, no al lugar de ejecución.';

const SQL_NORM = (col) => `
  regexp_replace(
    regexp_replace(
      upper(normalize(regexp_replace(trim(${col}), '[[:punct:]]+', ' ', 'g'), NFKD)),
      '[^A-Z0-9 ]', '', 'g'
    ),
    '\\s+', ' ', 'g'
  )`;

const SQL_CANON = (expr) => `
  CASE
    WHEN ${expr} IN ('BOGOTA', 'BOGOTA D C', 'BOGOTA DC', 'DISTRITO CAPITAL DE BOGOTA')
      THEN 'BOGOTA D C'
    WHEN ${expr} LIKE 'SAN ANDRES%' OR ${expr} LIKE 'ARCHIPIELAGO DE SAN ANDRES%'
      THEN 'ARCHIPIELAGO DE SAN ANDRES'
    ELSE ${expr}
  END`;

const CTE_CATALOGO = `
cat AS (
  SELECT
    codigo_dane,
    nombre_departamento,
    ${SQL_CANON('n')} AS canon
  FROM (
    SELECT
      left(lpad(cod_municipio, 5, '0'), 2) AS codigo_dane,
      max(nombre_departamento) AS nombre_departamento,
      ${SQL_NORM('max(nombre_departamento)')} AS n
    FROM public.dim_municipio
    WHERE cod_municipio IS NOT NULL
      AND btrim(cod_municipio) <> ''
      AND cod_municipio <> '00000'
    GROUP BY 1
  ) s
),
canon_unico AS (
  SELECT canon, min(codigo_dane) AS codigo_dane
  FROM cat
  GROUP BY canon
  HAVING count(DISTINCT codigo_dane) = 1
)`;

const SQL_DEPARTAMENTOS = `
WITH ${CTE_CATALOGO},
poblacion AS (
  SELECT
    left(cod_municipio, 2) AS codigo_dane,
    sum(poblacion)::bigint AS poblacion_total,
    sum(pob_hombres)::bigint AS total_hombres,
    sum(pob_mujeres)::bigint AS total_mujeres
  FROM tfm.poblacion_municipal
  WHERE anio = ${ANIO_POBLACION}
  GROUP BY 1
),
por_codigo AS (
  SELECT
    left(cod_municipio, 2) AS codigo_dane,
    count(*)::bigint AS n_contratos,
    coalesce(sum(valor_del_contrato), 0) AS valor_total
  FROM tfm.contrato
  WHERE periodo = $1
    AND estado_homologacion = 'homologado'
    AND cod_municipio IS NOT NULL
    AND btrim(cod_municipio) <> ''
  GROUP BY 1
),
por_nombre AS (
  SELECT
    u.codigo_dane,
    count(*)::bigint AS n_contratos,
    coalesce(sum(c.valor_del_contrato), 0) AS valor_total
  FROM (
    SELECT
      valor_del_contrato,
      ${SQL_CANON('n')} AS canon
    FROM (
      SELECT
        valor_del_contrato,
        ${SQL_NORM('departamento')} AS n
      FROM tfm.contrato
      WHERE periodo = $1
        AND estado_homologacion IN ('sin_municipio', 'no_homologado')
    ) s
  ) c
  JOIN canon_unico u ON u.canon = c.canon
  GROUP BY u.codigo_dane
)
SELECT
  cat.codigo_dane,
  cat.nombre_departamento,
  pob.poblacion_total,
  pob.total_hombres,
  pob.total_mujeres,
  coalesce(cod.n_contratos, 0)::bigint AS n_contratos_por_codigo,
  coalesce(nom.n_contratos, 0)::bigint AS n_contratos_por_nombre,
  (coalesce(cod.n_contratos, 0) + coalesce(nom.n_contratos, 0))::bigint AS n_contratos,
  (coalesce(cod.valor_total, 0) + coalesce(nom.valor_total, 0)) AS valor_total,
  CASE
    WHEN pob.poblacion_total IS NULL OR pob.poblacion_total <= 0 THEN NULL
    ELSE (coalesce(cod.n_contratos, 0) + coalesce(nom.n_contratos, 0))::numeric
         / pob.poblacion_total * 100000
  END AS contratos_por_100k,
  CASE
    WHEN pob.poblacion_total IS NULL OR pob.poblacion_total <= 0 THEN NULL
    ELSE (coalesce(cod.valor_total, 0) + coalesce(nom.valor_total, 0))
         / pob.poblacion_total
  END AS valor_por_habitante
FROM cat
LEFT JOIN poblacion pob ON pob.codigo_dane = cat.codigo_dane
LEFT JOIN por_codigo cod ON cod.codigo_dane = cat.codigo_dane
LEFT JOIN por_nombre nom ON nom.codigo_dane = cat.codigo_dane
ORDER BY cat.codigo_dane
`;

const SQL_COBERTURA = `
WITH ${CTE_CATALOGO},
asignados_nombre AS (
  SELECT c.id_contrato
  FROM (
    SELECT
      id_contrato,
      ${SQL_CANON('n')} AS canon
    FROM (
      SELECT
        id_contrato,
        ${SQL_NORM('departamento')} AS n
      FROM tfm.contrato
      WHERE periodo = $1
        AND estado_homologacion IN ('sin_municipio', 'no_homologado')
    ) s
  ) c
  JOIN canon_unico u ON u.canon = c.canon
)
SELECT
  (SELECT count(*) FROM tfm.contrato WHERE periodo = $1)::bigint AS total,
  (
    SELECT count(*) FROM tfm.contrato
    WHERE periodo = $1
      AND estado_homologacion = 'homologado'
      AND cod_municipio IS NOT NULL
      AND btrim(cod_municipio) <> ''
  )::bigint AS por_codigo,
  (SELECT count(*) FROM asignados_nombre)::bigint AS por_nombre
`;

function validarPeriodo(valor) {
  const p = valor == null || valor === '' ? periodoDefecto : String(valor).trim();
  if (!/^\d{4}-\d{2}$/.test(p)) {
    const err = new Error('Periodo inválido. Use AAAA-MM.');
    err.codigo = 400;
    throw err;
  }
  return p;
}

function numero(valor) {
  if (valor == null) return null;
  const n = Number(valor);
  return Number.isFinite(n) ? n : null;
}

function indicadoresDerivados(nContratos, valorTotal, poblacion) {
  if (poblacion == null || poblacion <= 0) {
    return { contratos_por_100k: null, valor_por_habitante: null };
  }
  return {
    contratos_por_100k: nContratos / poblacion * 100000,
    valor_por_habitante: valorTotal / poblacion
  };
}

function armarRespuesta(filas, cobertura, periodo) {
  const total = Number(cobertura.total) || 0;
  const porCodigo = Number(cobertura.por_codigo) || 0;
  const porNombre = Number(cobertura.por_nombre) || 0;
  const sinDepartamento = total - porCodigo - porNombre;
  return {
    periodo,
    anio_poblacion: ANIO_POBLACION,
    nota: NOTA,
    cobertura: {
      total,
      por_codigo: porCodigo,
      por_nombre: porNombre,
      sin_departamento: sinDepartamento
    },
    departamentos: filas.map((f) => ({
      codigo_dane: f.codigo_dane,
      nombre_departamento: f.nombre_departamento,
      poblacion_total: numero(f.poblacion_total),
      total_hombres: numero(f.total_hombres),
      total_mujeres: numero(f.total_mujeres),
      n_contratos_por_codigo: Number(f.n_contratos_por_codigo) || 0,
      n_contratos_por_nombre: Number(f.n_contratos_por_nombre) || 0,
      n_contratos: Number(f.n_contratos) || 0,
      valor_total: numero(f.valor_total),
      contratos_por_100k: numero(f.contratos_por_100k),
      valor_por_habitante: numero(f.valor_por_habitante)
    }))
  };
}

let consultar = queryDB;

function setConsultar(fn) {
  consultar = fn || queryDB;
}

async function departamentos(params = {}) {
  const p = validarPeriodo(params.periodo);
  const [filas, cob] = await Promise.all([
    consultar(SQL_DEPARTAMENTOS, [p]),
    consultar(SQL_COBERTURA, [p])
  ]);
  const cobertura = cob[0] || { total: 0, por_codigo: 0, por_nombre: 0 };
  return armarRespuesta(filas, cobertura, p);
}

module.exports = {
  ANIO_POBLACION,
  NOTA,
  SQL_DEPARTAMENTOS,
  SQL_COBERTURA,
  validarPeriodo,
  indicadoresDerivados,
  armarRespuesta,
  departamentos,
  setConsultar
};
