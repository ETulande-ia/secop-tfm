const { queryDB } = require('../db/postgres');
const { periodo, versionModelo } = require('../config');

/**
 * Recupera un contrato y su score publicado.
 * No usa fact_contrato_risk ni reentrena Isolation Forest.
 */
async function retrieveContractContext(idContrato) {
  const p = periodo;
  const v = versionModelo;

  const contratos = await queryDB(
    `
    SELECT
      c.id_contrato,
      c.valor_del_contrato,
      c.modalidad_de_contratacion,
      c.nombre_entidad AS entidad,
      COALESCE(c.nombre_departamento_divipola, c.departamento) AS nombre_departamento,
      c.ciudad
    FROM tfm.contrato c
    WHERE c.periodo = $1
      AND c.id_contrato = $2
    `,
    [p, idContrato]
  );

  if (contratos.length === 0) {
    throw new Error('Contrato no encontrado');
  }

  const scores = await queryDB(
    `
    SELECT
      score_if,
      rank_if,
      top1_if,
      top5_if,
      flag_p99_modalidad,
      rank_logvalor,
      top1_logvalor,
      modalidad_grupo
    FROM tfm.ml_contrato_score
    WHERE periodo = $1
      AND version_modelo = $2
      AND id_contrato = $3
    `,
    [p, v, idContrato]
  );

  const excluidos = await queryDB(
    `
    SELECT motivo_exclusion
    FROM tfm.ml_contrato_excluido
    WHERE periodo = $1
      AND version_modelo = $2
      AND id_contrato = $3
    `,
    [p, v, idContrato]
  );

  return {
    contrato: contratos[0],
    puntuacion_if: scores[0] || null,
    exclusion: excluidos[0] || null
  };
}

let cacheUniverso = null;

async function contarUniversoIf() {
  if (cacheUniverso) return cacheUniverso;
  const p = periodo;
  const v = versionModelo;
  const rows = await queryDB(
    `
    SELECT
      COUNT(*)::int AS n_aptos,
      COUNT(*) FILTER (WHERE top1_if)::int AS n_top1
    FROM tfm.ml_contrato_score
    WHERE periodo = $1
      AND version_modelo = $2
    `,
    [p, v]
  );
  cacheUniverso = {
    n_aptos: Number(rows[0].n_aptos),
    n_top1: Number(rows[0].n_top1)
  };
  return cacheUniverso;
}

module.exports = {
  retrieveContractContext,
  contarUniversoIf
};
