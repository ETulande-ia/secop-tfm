const { test } = require('node:test');
const assert = require('node:assert/strict');
const { processUserQuery } = require('../orchestration/query.orchestrator');

test('el flujo de chat rechaza fraude antes del especial PORQUE_ATIPICO', async () => {
  const r = await processUserQuery('¿Este contrato es fraude?');
  assert.equal(r.intent, 'NO_SOPORTADO');
  assert.match(r.text, /delitos|fraude|corrupción|corrupcion/i);
  assert.equal(r.data, null);
});

test('el flujo de chat no cuenta el total nacional ante «a dedo»', async () => {
  const r = await processUserQuery('¿Cuántos contratos dieron a dedo?');
  assert.equal(r.intent, 'NO_SOPORTADO');
  assert.match(r.text, /contrataci[oó]n directa/i);
});

test('el flujo de chat no explica el RUP con una consulta SQL', async () => {
  const rag = require('../modules/rag-documental');
  rag.setDependencias({
    recuperar: async () => ({
      hits: [{
        fragment_id: 'cce-requisitos-habilitantes-v3-2023-p009-029',
        doc_id: 'cce-requisitos-habilitantes-v3-2023',
        titulo: 'Manual de requisitos habilitantes v3',
        seccion: 'RUP',
        pagina_inicio: 9,
        pagina_fin: 9,
        texto: 'El RUP es el certificado de plena prueba de los requisitos habilitantes.'
      }],
      cobertura_lexica: { cobertura: 'suficiente' },
      informacion_insuficiente_umbral: false
    }),
    completar: async () => JSON.stringify({
      puede_responder: true,
      cobertura: 'suficiente',
      texto: 'El RUP es el certificado de plena prueba de los requisitos habilitantes.',
      fragment_ids: ['cce-requisitos-habilitantes-v3-2023-p009-029'],
      limitaciones: ''
    })
  });
  try {
    const r = await processUserQuery('¿Qué es el RUP?');
    assert.equal(r.intent, 'RAG_DOCUMENTAL');
    assert.match(r.text, /RUP/i);
    assert.equal(r.data, null);
  } finally {
    rag.restaurarDependencias();
  }
});

test('el flujo de chat no usa septiembre en silencio para el mes pasado', async () => {
  const r = await processUserQuery('¿Cuántos contratos hubo el mes pasado?');
  assert.equal(r.intent, 'NO_SOPORTADO');
  assert.match(r.text, /septiembre de 2026/i);
});
