const { test, afterEach } = require('node:test');
const assert = require('node:assert/strict');
const { interpretarCiudadano } = require('../modules/interpretacion-ciudadana');
const rag = require('../modules/rag-documental');
const { processUserQuery } = require('../orchestration/query.orchestrator');

afterEach(() => rag.restaurarDependencias());

const HIT_MINIMA = {
  fragment_id: 'cce-minima-cuantia-2024-p004-004-601acaff',
  doc_id: 'cce-minima-cuantia-2024',
  titulo: 'Manual de mínima cuantía (Colombia Compra Eficiente, 2024)',
  seccion: '¿Qué es la mínima cuantía?',
  pagina_inicio: 4,
  pagina_fin: 4,
  texto: 'La mínima cuantía es un procedimiento de selección cuyo valor no excede el 10 % de la menor cuantía.'
};

const HIT_RUP = {
  fragment_id: 'cce-minima-cuantia-2024-p010-027-e5bf81f3',
  doc_id: 'cce-minima-cuantia-2024',
  titulo: 'Manual de mínima cuantía (Colombia Compra Eficiente, 2024)',
  seccion: 'RUP',
  pagina_inicio: 10,
  pagina_fin: 10,
  texto: 'Los oferentes no están obligados a acreditar inscripción en el RUP.'
};

const HIT_C1 = {
  fragment_id: 'ficha-c1-if-v1-p001-005-eb9b4376',
  doc_id: 'ficha-c1-if-v1',
  titulo: 'Ficha metodológica C1 + Isolation Forest (c1_if_v1)',
  seccion: 'Algoritmo',
  pagina_inicio: 1,
  pagina_fin: 1,
  texto: 'Isolation Forest en c1_if_v1 usa n_estimators = 200.'
};

function recu(hits, lex) {
  return {
    estrategia: 'B_coseno_top5_adyacentes_alcance',
    hits,
    cobertura_lexica: { cobertura: lex, razon: 'prueba' },
    informacion_insuficiente_umbral: false,
    similitud_max: 0.72,
    alcance: null
  };
}

test('pregunta documental respondible cita documento, sección y página reales', async () => {
  rag.setDependencias({
    recuperar: async () => recu([HIT_MINIMA], 'suficiente'),
    completar: async () => JSON.stringify({
      puede_responder: true,
      cobertura: 'suficiente',
      texto: 'La mínima cuantía es un procedimiento cuyo valor no supera el 10 % de la menor cuantía.',
      fragment_ids: [HIT_MINIMA.fragment_id],
      limitaciones: ''
    })
  });
  const r = await processUserQuery('¿Qué es la modalidad de mínima cuantía?');
  assert.equal(r.intent, 'RAG_DOCUMENTAL');
  assert.equal(r.evidencia.cobertura, 'suficiente');
  assert.equal(r.referencias[0].fragment_id, HIT_MINIMA.fragment_id);
  assert.match(r.text, /mínima cuantía/i);
  assert.match(r.text, /p\. 4/);
  assert.doesNotMatch(r.text, /similitud|0\.72/);
  assert.equal(r.data, null);
});

test('pregunta parcialmente cubierta declara el hueco', async () => {
  rag.setDependencias({
    recuperar: async () => recu([HIT_MINIMA], 'parcial'),
    completar: async () => JSON.stringify({
      puede_responder: true,
      cobertura: 'parcial',
      texto: 'El manual explica el 10 % de la menor cuantía, no el valor en pesos de Bogotá en 2026.',
      fragment_ids: [HIT_MINIMA.fragment_id],
      limitaciones: 'No hay cifra local de 2026.'
    })
  });
  const r = await processUserQuery(
    '¿Cuál es el valor en pesos de la mínima cuantía de Bogotá en 2026?'
  );
  assert.equal(r.intent, 'RAG_DOCUMENTAL');
  assert.equal(r.evidencia.cobertura, 'parcial');
  assert.match(r.text, /parte de la pregunta/i);
});

test('pregunta fuera del corpus no se inventa', async () => {
  rag.setDependencias({
    recuperar: async () => recu([], 'no_cubierta'),
    completar: async () => {
      throw new Error('no debe generar si no hay evidencia');
    }
  });
  const r = await processUserQuery('¿Qué es el SISBÉN IV?');
  assert.equal(r.intent, 'RAG_DOCUMENTAL');
  assert.equal(r.evidencia.cobertura, 'no_cubierta');
  assert.match(r.text, /evidencia suficiente/i);
  assert.equal(r.referencias.length, 0);
});

test('documento excluido (sancionatorio) se rechaza por falta de evidencia', async () => {
  assert.equal(
    interpretarCiudadano('¿Cuál es la multa máxima en un proceso sancionatorio de Colombia Compra Eficiente?').accion,
    'documental'
  );
  rag.setDependencias({
    recuperar: async () => recu([{
      fragment_id: 'otro',
      doc_id: 'cce-minima-cuantia-2024',
      titulo: 'Manual de mínima cuantía',
      seccion: 'Introducción',
      pagina_inicio: 1,
      texto: 'Manual de mínima cuantía. No trata el proceso sancionatorio.'
    }], 'no_cubierta'),
    completar: async () => JSON.stringify({
      puede_responder: false,
      cobertura: 'insuficiente',
      texto: '',
      fragment_ids: [],
      limitaciones: 'El corpus no incluye la guía sancionatoria.'
    })
  });
  const r = await processUserQuery(
    '¿Cuál es la multa máxima en un proceso sancionatorio de Colombia Compra Eficiente?'
  );
  assert.equal(r.evidencia.cobertura, 'no_cubierta');
  assert.match(r.text, /excluida|evidencia suficiente/i);
});

test('excepción RUP en mínima cuantía usa el manual de mínima cuantía', async () => {
  rag.setDependencias({
    recuperar: async () => recu([HIT_RUP], 'suficiente'),
    completar: async () => JSON.stringify({
      puede_responder: true,
      cobertura: 'suficiente',
      texto: 'En mínima cuantía los oferentes no están obligados a acreditar el RUP.',
      fragment_ids: [HIT_RUP.fragment_id],
      limitaciones: ''
    })
  });
  const r = await processUserQuery(
    '¿Los oferentes deben acreditar el RUP en un proceso de mínima cuantía?'
  );
  assert.equal(r.intent, 'RAG_DOCUMENTAL');
  assert.match(r.text, /no están obligados/i);
  assert.equal(r.referencias[0].doc_id, 'cce-minima-cuantia-2024');
});

test('variables C1 se responden con la ficha, no con SQL', async () => {
  rag.setDependencias({
    recuperar: async () => recu([HIT_C1], 'suficiente'),
    completar: async () => JSON.stringify({
      puede_responder: true,
      cobertura: 'suficiente',
      texto: 'En c1_if_v1, Isolation Forest usa n_estimators = 200.',
      fragment_ids: [HIT_C1.fragment_id],
      limitaciones: ''
    })
  });
  const r = await processUserQuery(
    '¿Cuántos árboles (n_estimators) usa Isolation Forest en c1_if_v1?'
  );
  assert.equal(r.intent, 'RAG_DOCUMENTAL');
  assert.match(r.text, /200/);
  assert.equal(r.referencias[0].doc_id, 'ficha-c1-if-v1');
});

test('fraude no entra a RAG ni a Isolation Forest', async () => {
  rag.setDependencias({
    recuperar: async () => {
      throw new Error('fraude no recupera');
    }
  });
  const r = await processUserQuery('¿Este contrato es fraude?');
  assert.equal(r.intent, 'NO_SOPORTADO');
  assert.match(r.text, /delitos|fraude/i);
});

test('consulta analítica de Bogotá sigue en SQL', async () => {
  const d = interpretarCiudadano('¿Cuántos contratos hay en Bogotá?');
  assert.equal(d.accion, 'ejecutar');
});

test('pregunta ambigua a dedo sigue pidiendo aclaración', async () => {
  const r = await processUserQuery('¿Cuántos contratos dieron a dedo?');
  assert.equal(r.intent, 'NO_SOPORTADO');
  assert.match(r.text, /contrataci[oó]n directa/i);
});

test('no se aceptan citas inventadas por el modelo', () => {
  const refs = rag.citasDeHits(
    ['inventado', HIT_MINIMA.fragment_id],
    [HIT_MINIMA]
  );
  assert.equal(refs.length, 1);
  assert.equal(refs[0].fragment_id, HIT_MINIMA.fragment_id);
  assert.equal(refs[0].pagina, '4');
});

test('el clasificador léxico no autoriza solo una respuesta', () => {
  const rec = recu([HIT_MINIMA], 'suficiente');
  const cob = rag.fusionarCobertura(rec, {
    puede_responder: false,
    cobertura: 'insuficiente'
  });
  assert.equal(cob, 'no_cubierta');
});

test('si hay hits y el léxico dice no cubierta, una respuesta parcial sí se admite', () => {
  const rec = recu([HIT_MINIMA], 'no_cubierta');
  const cob = rag.fusionarCobertura(rec, {
    puede_responder: true,
    cobertura: 'parcial'
  });
  assert.equal(cob, 'parcial');
});

test('no se pega «Ninguna» como limitación vacía', async () => {
  assert.equal(rag.limpiarLimitacion('Ninguna'), '');
  assert.equal(rag.limpiarLimitacion('N/A'), '');
  assert.match(rag.limpiarLimitacion('No hay cifra de Bogotá en 2026'), /Bogotá/);
  rag.setDependencias({
    recuperar: async () => recu([HIT_C1], 'suficiente'),
    completar: async () => JSON.stringify({
      puede_responder: true,
      cobertura: 'suficiente',
      texto: 'Isolation Forest usa 200 árboles.',
      fragment_ids: [HIT_C1.fragment_id],
      limitaciones: 'Ninguna'
    })
  });
  const r = await processUserQuery(
    '¿Cuántos árboles (n_estimators) usa Isolation Forest en c1_if_v1?'
  );
  assert.doesNotMatch(r.text, /Ninguna/);
  assert.match(r.text, /200/);
});

test('un léxico no cubierta no se convierte en suficiente', () => {
  const rec = recu([HIT_MINIMA], 'no_cubierta');
  const cob = rag.fusionarCobertura(rec, {
    puede_responder: true,
    cobertura: 'suficiente'
  });
  assert.equal(cob, 'no_cubierta');
});
