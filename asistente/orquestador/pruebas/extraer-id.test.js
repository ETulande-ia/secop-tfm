const { test } = require('node:test');
const assert = require('node:assert/strict');
const { extraerIdContrato } = require('../orchestration/query.orchestrator');

test('extrae el identificador de un contrato SECOP', () => {
  assert.equal(
    extraerIdContrato('Explícame el contrato CO1.PCCNTR.9673418 por favor'),
    'CO1.PCCNTR.9673418'
  );
});

test('sin identificador devuelve null', () => {
  assert.equal(extraerIdContrato('¿Qué ciudad invierte más?'), null);
});
