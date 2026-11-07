const { test } = require('node:test');
const assert = require('node:assert/strict');
const { extraerMenciones, extraerIdContrato } = require('../modules/nlq');
const { fallbackIntent } = require('../orchestration/query.orchestrator');
const { explicarPorqueAtipico } = require('../modules/narrative-explainer');

test('el identificador se extrae del texto original, con puntos', () => {
  assert.equal(
    extraerIdContrato('Explícame el contrato CO1.PCCNTR.9673418'),
    'CO1.PCCNTR.9673418'
  );
  assert.equal(extraerMenciones('Explícame el contrato CO1.PCCNTR.9673418').idContrato, 'CO1.PCCNTR.9673418');
});

test('listar atípicos no se confunde con explicar el método', () => {
  assert.equal(extraerMenciones('¿Cuáles son los contratos con comportamientos atípicos?').especial, 'TOP1_IF');
  assert.equal(extraerMenciones('¿Cuáles son los contratos más atípicos?').especial, 'TOP1_IF');
  assert.equal(extraerMenciones('Muéstrame el top 1 Isolation Forest').especial, 'TOP1_IF');
});

test('explicar anomalía o puntuación no lista contratos ni va a departamentos', () => {
  assert.equal(extraerMenciones('¿Por qué se considera atípico un contrato?').especial, 'PORQUE_ATIPICO');
  assert.equal(extraerMenciones('¿Qué características hacen atípico un contrato?').especial, 'PORQUE_ATIPICO');
  assert.equal(extraerMenciones('¿Qué significa la puntuación de anomalía?').especial, 'PORQUE_ATIPICO');
  assert.notEqual(extraerMenciones('¿Qué significa la puntuación de anomalía?').especial, 'RISK_ANALYSIS');
  assert.equal(fallbackIntent('qué significa la puntuación de anomalía'), 'PORQUE_ATIPICO');
});

test('un identificador tiene prioridad sobre el listado', () => {
  const a = extraerMenciones('¿El contrato CO1.PCCNTR.9673418 presenta anomalías?');
  assert.equal(a.especial, 'PORQUE_ATIPICO');
  assert.equal(a.idContrato, 'CO1.PCCNTR.9673418');
  const b = extraerMenciones('¿Por qué es atípico CO1.PCCNTR.1111111?');
  assert.equal(b.especial, 'PORQUE_ATIPICO');
  assert.equal(b.idContrato, 'CO1.PCCNTR.1111111');
  const c = extraerMenciones('Explícame el contrato CO1.PCCNTR.9673418');
  assert.equal(c.especial, 'EXPLAIN_CONTRACT');
  assert.equal(c.idContrato, 'CO1.PCCNTR.9673418');
});

test('seguimiento usa idContrato del contexto y no infiere desde una lista', () => {
  const conId = extraerMenciones('¿Y por qué ese contrato?', { idContrato: 'CO1.PCCNTR.2222222' });
  assert.equal(conId.especial, 'PORQUE_ATIPICO');
  assert.equal(conId.idContrato, 'CO1.PCCNTR.2222222');

  const lista = extraerMenciones('¿Cuáles son los contratos más atípicos?', { idContrato: 'CO1.PCCNTR.2222222' });
  assert.equal(lista.especial, 'TOP1_IF');

  const sinId = extraerMenciones('¿Y ese contrato?');
  assert.equal(sinId.idContrato, null);
  assert.equal(sinId.especial, 'PORQUE_ATIPICO');
});

test('la plantilla no contiene cifras quemadas ni afirma fraude', () => {
  const texto = explicarPorqueAtipico(null, null, { n_aptos: 82457, n_top1: 825 });
  assert.match(texto, /82\.457/);
  assert.match(texto, /825/);
  assert.equal(texto.includes('82.457 contratos aptos; 825 están'), true);
  assert.equal(/fraude comprobado|es un fraude/i.test(texto), false);
  const sinUniverso = explicarPorqueAtipico(null, null, null);
  assert.equal(sinUniverso.includes('82457'), false);
  assert.match(sinUniverso, /sin dato/);
});

test('sin pedir el método no se añade la explicación de C1', () => {
  const corto = explicarPorqueAtipico(null, null, { n_aptos: 82457, n_top1: 825 }, false);
  assert.equal(corto.includes('82.457'), false);
  assert.equal(/log1p|C1 usa/i.test(corto), false);
  const conId = explicarPorqueAtipico({
    contrato: { id_contrato: 'CO1.PCCNTR.1', entidad: 'A', valor_del_contrato: 10 },
    puntuacion_if: { score_if: 0.5, rank_if: 1, top1_if: true }
  }, 'CO1.PCCNTR.1', { n_aptos: 82457, n_top1: 825 }, false);
  assert.match(conId, /CO1\.PCCNTR\.1/);
  assert.equal(/percentil 99|log1p/i.test(conId), false);
});
