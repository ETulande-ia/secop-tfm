const { queryDB } = require('../db/postgres');
const { periodo, versionModelo } = require('../config');

/**
 * Consultas controladas sobre el esquema tfm.
 * No genera SQL a partir del texto del usuario.
 * Isolation Forest se lee de tfm.ml_contrato_score (c1_if_v1); no se reentrena.
 */
async function execute(intentType, params = {}) {
  const limit = params.limit || 10;
  const p = params.periodo || periodo;
  const v = params.versionModelo || versionModelo;

  switch (intentType) {
    case 'INVESTMENT_CITY': {
      const rows = await queryDB(
        `
        SELECT
          COALESCE(nombre_municipio_divipola, ciudad, 'sin municipio') AS nombre_municipio,
          SUM(valor_del_contrato) AS total_invertido
        FROM tfm.contrato
        WHERE periodo = $1
          AND valor_apto_modelo
        GROUP BY 1
        ORDER BY total_invertido DESC
        LIMIT $2
        `,
        [p, limit]
      );
      return {
        intent: 'INVESTMENT_CITY',
        description: 'Municipios con mayor valor de contratos aptos (septiembre 2026)',
        rows
      };
    }

    case 'EXECUTION_TIME_ENTITY': {
      const rows = await queryDB(
        `
        SELECT
          nombre_entidad AS entidad,
          AVG(EXTRACT(EPOCH FROM (fecha_de_fin_del_contrato - fecha_de_inicio_del_contrato)) / 86400)
            AS duracion_promedio
        FROM tfm.contrato
        WHERE periodo = $1
          AND fecha_de_inicio_del_contrato IS NOT NULL
          AND fecha_de_fin_del_contrato IS NOT NULL
          AND fecha_de_fin_del_contrato > fecha_de_inicio_del_contrato
          AND (fecha_de_fin_del_contrato - fecha_de_inicio_del_contrato) <= INTERVAL '10 years'
        GROUP BY nombre_entidad
        HAVING COUNT(*) >= 3
        ORDER BY duracion_promedio DESC
        LIMIT $2
        `,
        [p, limit]
      );
      return {
        intent: 'EXECUTION_TIME_ENTITY',
        description: 'Entidades con mayor duración media (solo plazos entre 1 día y 10 años)',
        rows
      };
    }

    case 'LONGEST_CONTRACTS': {
      const rows = await queryDB(
        `
        SELECT
          id_contrato,
          EXTRACT(EPOCH FROM (fecha_de_fin_del_contrato - fecha_de_inicio_del_contrato)) / 86400
            AS duracion_dias,
          valor_del_contrato
        FROM tfm.contrato
        WHERE periodo = $1
          AND fecha_de_inicio_del_contrato IS NOT NULL
          AND fecha_de_fin_del_contrato IS NOT NULL
          AND fecha_de_fin_del_contrato > fecha_de_inicio_del_contrato
          AND (fecha_de_fin_del_contrato - fecha_de_inicio_del_contrato) <= INTERVAL '10 years'
        ORDER BY duracion_dias DESC
        LIMIT $2
        `,
        [p, limit]
      );
      return {
        intent: 'LONGEST_CONTRACTS',
        description: 'Contratos con mayor duración en días (plazos válidos)',
        rows
      };
    }

    case 'RISK_ANALYSIS': {
      const rows = await queryDB(
        `
        SELECT
          COALESCE(c.nombre_departamento_divipola, c.departamento, 'sin departamento')
            AS nombre_departamento,
          AVG(s.score_if) AS riesgo_promedio
        FROM tfm.ml_contrato_score s
        JOIN tfm.contrato c
          ON c.periodo = s.periodo AND c.id_contrato = s.id_contrato
        WHERE s.periodo = $1
          AND s.version_modelo = $2
        GROUP BY 1
        ORDER BY riesgo_promedio DESC
        LIMIT $3
        `,
        [p, v, limit]
      );
      return {
        intent: 'RISK_ANALYSIS',
        description:
          'Atipicidad media Isolation Forest (c1_if_v1) por departamento. Mayor score = más atípico; no es irregularidad.',
        rows
      };
    }

    case 'TOP_PROVIDERS': {
      const rows = await queryDB(
        `
        SELECT
          proveedor_adjudicado AS proveedor,
          COUNT(*) AS num_contratos,
          SUM(valor_del_contrato) AS total_contratado
        FROM tfm.contrato
        WHERE periodo = $1
          AND proveedor_adjudicado IS NOT NULL
          AND btrim(proveedor_adjudicado) <> ''
          AND valor_apto_modelo
        GROUP BY 1
        ORDER BY num_contratos DESC
        LIMIT $2
        `,
        [p, limit]
      );
      return {
        intent: 'TOP_PROVIDERS',
        description: 'Proveedores con más contratos electrónicos (septiembre 2026)',
        rows
      };
    }

    case 'BOGOTA_CONTRATACION': {
      const rows = await queryDB(
        `
        SELECT COUNT(*) AS n
        FROM tfm.contrato
        WHERE periodo = $1
          AND es_bogota IS TRUE
        `,
        [p]
      );
      return {
        intent: 'BOGOTA_CONTRATACION',
        description:
          'Contratación de entidades con sede en Bogotá (septiembre 2026). No es el lugar de ejecución.',
        periodo: p,
        rows
      };
    }

    case 'TOP_ENTIDADES': {
      const rows = await queryDB(
        `
        SELECT
          nombre_entidad AS entidad,
          COUNT(*) AS num_contratos,
          SUM(valor_del_contrato) AS total_contratado
        FROM tfm.contrato
        WHERE periodo = $1
          AND nombre_entidad IS NOT NULL
          AND btrim(nombre_entidad) <> ''
        GROUP BY 1
        ORDER BY total_contratado DESC
        LIMIT $2
        `,
        [p, limit]
      );
      return {
        intent: 'TOP_ENTIDADES',
        description: 'Entidades contratantes con mayor valor (septiembre 2026)',
        rows
      };
    }

    case 'MODALIDADES': {
      const rows = await queryDB(
        `
        SELECT
          COALESCE(modalidad_de_contratacion, 'sin dato') AS modalidad,
          COUNT(*) AS n,
          ROUND(
            100.0 * COUNT(*) / NULLIF(SUM(COUNT(*)) OVER (), 0),
            2
          ) AS pct
        FROM tfm.contrato
        WHERE periodo = $1
        GROUP BY 1
        ORDER BY n DESC
        LIMIT $2
        `,
        [p, params.limit || 20]
      );
      return {
        intent: 'MODALIDADES',
        description: 'Modalidades de contratación (septiembre 2026)',
        rows
      };
    }

    case 'TOP1_IF': {
      const rows = await queryDB(
        `
        SELECT
          rank_if,
          id_contrato,
          nombre_entidad,
          score_if
        FROM tfm.ml_contrato_score
        WHERE periodo = $1
          AND version_modelo = $2
          AND top1_if
        ORDER BY rank_if
        LIMIT $3
        `,
        [p, v, limit]
      );
      return {
        intent: 'TOP1_IF',
        description:
          'Contratos del top 1 % Isolation Forest (c1_if_v1). Mayor score_if = más atípico; no es irregularidad.',
        rows
      };
    }

    default:
      throw new Error(`Intención analítica no soportada: ${intentType}`);
  }
}

function armarWhere(slots) {
  const args = [slots.periodo];
  const parts = ['periodo = $1'];
  if (slots.territorio === 'bogota') parts.push('es_bogota IS TRUE');
  if (slots.entidad) {
    args.push(slots.entidad);
    parts.push(`nombre_entidad = $${args.length}`);
  }
  if (slots.modalidad) {
    args.push(slots.modalidad);
    parts.push(`modalidad_de_contratacion = $${args.length}`);
  }
  return { where: parts.join(' AND '), args };
}

async function consultar(slots, params = {}) {
  const limit = params.limit || (slots.operacion === 'distribucion' ? 20 : 10);
  const { where, args } = armarWhere(slots);

  if (slots.operacion === 'contar') {
    const select = slots.metrica === 'valor'
      ? 'COALESCE(SUM(valor_del_contrato), 0) AS valor'
      : 'COUNT(*) AS n';
    const rows = await queryDB(
      `SELECT ${select} FROM tfm.contrato WHERE ${where}`,
      args
    );
    return { operacion: 'contar', rows };
  }

  if (slots.operacion === 'ranking') {
    const porValor = slots.metrica === 'valor';
    const select = porValor
      ? 'SUM(valor_del_contrato) AS total_contratado'
      : 'COUNT(*) AS num_contratos';
    const orden = porValor ? 'total_contratado DESC' : 'num_contratos DESC';
    args.push(limit);
    const rows = await queryDB(
      `
      SELECT
        nombre_entidad AS entidad,
        ${select}
      FROM tfm.contrato
      WHERE ${where}
        AND nombre_entidad IS NOT NULL
        AND btrim(nombre_entidad) <> ''
      GROUP BY 1
      ORDER BY ${orden}
      LIMIT $${args.length}
      `,
      args
    );
    return { operacion: 'ranking', rows };
  }

  if (slots.operacion === 'distribucion') {
    args.push(limit);
    const rows = await queryDB(
      `
      SELECT
        COALESCE(modalidad_de_contratacion, 'sin dato') AS modalidad,
        COUNT(*) AS n,
        ROUND(100.0 * COUNT(*) / NULLIF(SUM(COUNT(*)) OVER (), 0), 2) AS pct
      FROM tfm.contrato
      WHERE ${where}
      GROUP BY 1
      ORDER BY n DESC
      LIMIT $${args.length}
      `,
      args
    );
    return { operacion: 'distribucion', rows };
  }

  throw new Error(`Operación NLQ no soportada: ${slots.operacion}`);
}

module.exports = { execute, consultar };
