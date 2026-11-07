const { test, afterEach } = require('node:test');
const assert = require('node:assert/strict');
const detector = require('../modules/intent-detector');
const {
  validarLecturaMapa,
  respuestaMapa,
  INDICADORES
} = require('../modules/mapa-territorial-intent');
const { processUserQuery } = require('../orchestration/query.orchestrator');

afterEach(() => detector.restaurarDetectarIntencion());

function simular(intent, indicador, codigo_dane) {
  let llamadas = 0;
  detector.setDetectarIntencion(async () => {
    llamadas += 1;
    return {
      intent,
      indicador: indicador === undefined ? null : indicador,
      codigo_dane: codigo_dane === undefined ? null : codigo_dane
    };
  });
  return () => llamadas;
}

function recuRup() {
  return {
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
  };
}

test('parsea JSON del modelo y descarta indicador si la intención no es mapa', () => {
  const mapa = detector.parsearRespuesta(
    '{"intent":"MAPA_TERRITORIAL","indicador":"n_contratos","codigo_dane":"05"}'
  );
  assert.deepEqual(mapa, {
    intent: 'MAPA_TERRITORIAL',
    indicador: 'n_contratos',
    codigo_dane: '05'
  });
  const sql = detector.parsearRespuesta(
    '{"intent":"BOGOTA_CONTRATACION","indicador":"n_contratos","codigo_dane":"11"}'
  );
  assert.deepEqual(sql, {
    intent: 'BOGOTA_CONTRATACION',
    indicador: null,
    codigo_dane: null
  });
});

test('acepta la etiqueta suelta del formato anterior y un código DANE numérico', () => {
  assert.equal(detector.parsearRespuesta('TOP_ENTIDADES').intent, 'TOP_ENTIDADES');
  assert.equal(detector.parsearRespuesta('NO_EXISTE').intent, 'UNKNOWN');
  const r = detector.parsearRespuesta(
    '{"intent":"MAPA_TERRITORIAL","indicador":"n_contratos","codigo_dane":5}'
  );
  assert.equal(r.codigo_dane, '5');
  assert.equal(validarLecturaMapa(r).codigo_dane, '05');
});

test('valida indicador, código DANE y periodo sin mirar la redacción', () => {
  const ok = validarLecturaMapa({
    intent: 'MAPA_TERRITORIAL',
    indicador: 'total_mujeres',
    codigo_dane: '05'
  });
  assert.equal(ok.indicador, 'total_mujeres');
  assert.equal(ok.codigo_dane, '05');

  const sinIndicador = validarLecturaMapa({
    intent: 'MAPA_TERRITORIAL',
    indicador: null,
    codigo_dane: null
  });
  assert.equal(sinIndicador.aclarar, true);

  const indicadorInventado = validarLecturaMapa({
    intent: 'MAPA_TERRITORIAL',
    indicador: 'pib',
    codigo_dane: null
  });
  assert.equal(indicadorInventado.aclarar, true);

  const daneInvalido = validarLecturaMapa({
    intent: 'MAPA_TERRITORIAL',
    indicador: 'n_contratos',
    codigo_dane: '11001'
  });
  assert.equal(daneInvalido.aclarar, true);
});

test('respuestaMapa conserva el contrato de visualización', () => {
  const r = respuestaMapa({ indicador: 'n_contratos', codigo_dane: null });
  assert.equal(r.intent, 'MAPA_TERRITORIAL');
  assert.equal(r.visualization.type, 'mapa_territorial');
  assert.equal(r.visualization.indicador, 'n_contratos');
  assert.equal(r.visualization.titulo, INDICADORES.n_contratos);
  assert.equal(r.data, null);
});

test('1. contratos por departamento abre el mapa', async () => {
  const n = simular('MAPA_TERRITORIAL', 'n_contratos', null);
  const r = await processUserQuery('Contratos por departamento');
  assert.equal(n(), 1);
  assert.equal(r.ruta, 'mapa');
  assert.equal(r.intent, 'MAPA_TERRITORIAL');
  assert.equal(r.visualization.type, 'mapa_territorial');
  assert.equal(r.visualization.indicador, 'n_contratos');
  assert.equal(r.data, null);
});

test('2. dónde se contrata más en Colombia', async () => {
  simular('MAPA_TERRITORIAL', 'n_contratos', null);
  const r = await processUserQuery('¿Dónde se contrata más en Colombia?');
  assert.equal(r.ruta, 'mapa');
  assert.equal(r.visualization.indicador, 'n_contratos');
});

test('3. distribución de la contratación pública', async () => {
  simular('MAPA_TERRITORIAL', 'n_contratos', null);
  const r = await processUserQuery('Quiero ver cómo se distribuye la contratación pública');
  assert.equal(r.ruta, 'mapa');
  assert.equal(r.intent, 'MAPA_TERRITORIAL');
});

test('4. contratos por habitante', async () => {
  simular('MAPA_TERRITORIAL', 'contratos_por_100k', null);
  const r = await processUserQuery('¿Qué departamentos tienen más contratos por habitante?');
  assert.equal(r.ruta, 'mapa');
  assert.equal(r.visualization.indicador, 'contratos_por_100k');
});

test('5. población femenina por departamento', async () => {
  simular('MAPA_TERRITORIAL', 'total_mujeres', null);
  const r = await processUserQuery('Muéstrame la población femenina por departamento');
  assert.equal(r.ruta, 'mapa');
  assert.equal(r.visualization.indicador, 'total_mujeres');
});

test('6. mapa territorial sin indicador pide aclaración', async () => {
  simular('MAPA_TERRITORIAL', null, null);
  const r = await processUserQuery('Muéstrame un mapa territorial');
  assert.equal(r.ruta, 'aclarar');
  assert.equal(r.intent, 'NO_SOPORTADO');
  assert.equal(r.visualization, null);
  assert.match(r.text, /indicador/i);
});

test('variaciones de redacción usan la misma clasificación del modelo', async () => {
  simular('MAPA_TERRITORIAL', 'valor_total', '76');
  const r = await processUserQuery('Quisiera ver en el país cómo quedó la plata contratada, sobre todo el Valle');
  assert.equal(r.ruta, 'mapa');
  assert.equal(r.visualization.indicador, 'valor_total');
  assert.equal(r.visualization.codigo_dane, '76');
});

test('indicador inválido del modelo no abre el mapa', async () => {
  simular('MAPA_TERRITORIAL', 'pib_departamental', null);
  const r = await processUserQuery('Muéstrame el PIB por departamento');
  assert.equal(r.ruta, 'aclarar');
  assert.notEqual(r.visualization && r.visualization.type, 'mapa_territorial');
});

test('código DANE inválido no abre el mapa', async () => {
  simular('MAPA_TERRITORIAL', 'n_contratos', '999');
  const r = await processUserQuery('Mapa de contratos en un departamento');
  assert.equal(r.ruta, 'aclarar');
  assert.notEqual(r.visualization && r.visualization.type, 'mapa_territorial');
});

test('7. contratos en Bogotá no abre el mapa', async () => {
  const n = simular('BOGOTA_CONTRATACION', null, null);
  const pregunta = '¿Cuántos contratos hay en Bogotá?';
  try {
    const r = await processUserQuery(pregunta);
    assert.equal(n(), 1);
    assert.equal(r.ruta, 'sql');
    assert.notEqual(r.intent, 'MAPA_TERRITORIAL');
    assert.notEqual(r.visualization && r.visualization.type, 'mapa_territorial');
  } catch (err) {
    assert.equal(n(), 1);
    assert.match(String(err.message), /ECONNREFUSED|connect|postgres|query|timeout/i);
  }
});

test('8. pregunta documental RAG no llama al clasificador ni se vuelve mapa', async () => {
  const n = simular('MAPA_TERRITORIAL', 'n_contratos', null);
  const rag = require('../modules/rag-documental');
  rag.setDependencias({
    recuperar: async () => recuRup(),
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
    assert.equal(n(), 0);
    assert.equal(r.ruta, 'documental');
    assert.equal(r.intent, 'RAG_DOCUMENTAL');
    assert.equal(r.visualization, null);
  } finally {
    rag.restaurarDependencias();
  }
});

test('9. Isolation Forest no llama al clasificador ni cambia de ruta', async () => {
  const n = simular('MAPA_TERRITORIAL', 'n_contratos', null);
  const pregunta = 'Muéstrame los contratos atípicos';
  try {
    const r = await processUserQuery(pregunta);
    assert.equal(n(), 0);
    assert.equal(r.ruta, 'especial');
    assert.notEqual(r.visualization && r.visualization.type, 'mapa_territorial');
  } catch (err) {
    assert.equal(n(), 0);
    assert.match(String(err.message), /ECONNREFUSED|connect|postgres|query|timeout/i);
  }
});
