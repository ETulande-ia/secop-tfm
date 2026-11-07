const { test } = require('node:test');
const assert = require('node:assert/strict');
const { fallbackIntent, extraerIdContrato } = require('../orchestration/query.orchestrator');

function clasificar(texto) {
  const q = texto
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '');
  return fallbackIntent(q);
}

test('Bogotá no se clasifica como ranking de ciudades', () => {
  assert.equal(clasificar('¿Cuánto se contrató en Bogotá?'), 'BOGOTA_CONTRATACION');
  assert.equal(clasificar('Valor de la contratación en Bogota'), 'BOGOTA_CONTRATACION');
});

test('Entidades contratantes no se clasifican como proveedores', () => {
  assert.equal(
    clasificar('¿Cuáles fueron las entidades con mayor contratación?'),
    'TOP_ENTIDADES'
  );
  assert.equal(clasificar('Entidades que más contrataron'), 'TOP_ENTIDADES');
  assert.equal(
    clasificar('¿Qué proveedores tienen más contratos con el Estado?'),
    'TOP_PROVIDERS'
  );
});

test('Modalidades y atípicos tienen intención propia', () => {
  assert.equal(
    clasificar('¿Qué modalidades de contratación se utilizaron?'),
    'MODALIDADES'
  );
  assert.equal(
    clasificar('¿Cuáles son los contratos con comportamientos atípicos?'),
    'TOP1_IF'
  );
  assert.equal(
    clasificar('¿Por qué se considera atípico un contrato?'),
    'PORQUE_ATIPICO'
  );
  assert.equal(
    extraerIdContrato('¿Por qué es atípico CO1.PCCNTR.9673418?'),
    'CO1.PCCNTR.9673418'
  );
});
