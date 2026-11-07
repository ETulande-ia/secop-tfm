const { test } = require('node:test');
const assert = require('node:assert/strict');
const { extraerMenciones } = require('../modules/nlq');
const { interpretarCiudadano } = require('../modules/interpretacion-ciudadana');

test('plata en contratación pide valor, no el recuento', () => {
  const m = extraerMenciones('¿Cuánta plata contrataron en Bogotá?');
  assert.equal(m.metrica, 'valor');
  assert.equal(m.operacion, 'contar');
  assert.equal(m.territorio, 'bogota');
  assert.equal(m.especial, null);
});

test('durante no se confunde con duración de contratos', () => {
  const m = extraerMenciones('¿Cuánto se gastó en contratos durante septiembre?');
  assert.notEqual(m.especial, 'LONGEST_CONTRACTS');
  assert.equal(m.operacion, 'contar');
  assert.equal(m.metrica, 'valor');
});

test('quién hizo más contratos en Bogotá es ranking, no el total de la ciudad', () => {
  const m = extraerMenciones('¿Quién hizo más contratos en Bogotá?');
  assert.equal(m.operacion, 'ranking');
  assert.equal(m.metrica, 'n_contratos');
  assert.equal(m.territorio, 'bogota');
  assert.equal(m.especial, null);
});

test('a quién le dieron más contratos no se vuelve ranking de entidades', () => {
  const m = extraerMenciones('¿A quién le dieron más contratos?');
  assert.notEqual(m.operacion, 'ranking');
});

test('cuáles + puntuación lista atípicos; no explica el modelo', () => {
  const m = extraerMenciones('¿Cuáles tienen una puntuación extraña?');
  assert.equal(m.especial, 'TOP1_IF');
});

test('el modelo que marca un contrato se explica, no se consulta SQL', () => {
  const m = extraerMenciones('¿Qué significa que el modelo marque un contrato?');
  assert.equal(m.especial, 'PORQUE_ATIPICO');
});

test('mes pasado no se toma como septiembre', () => {
  const m = extraerMenciones('¿Cuántos contratos hubo el mes pasado?');
  assert.equal(m.periodoInvalido, true);
  const d = interpretarCiudadano('¿Cuántos contratos hubo el mes pasado?');
  assert.equal(d.accion, 'aclarar');
  assert.equal(d.regla, 'periodo');
});

test('septiembre de 2026 sigue siendo el periodo publicado', () => {
  const q = '¿Cuántos contratos hicieron en Bogotá en septiembre de 2026?';
  const m = extraerMenciones(q);
  assert.equal(m.periodoInvalido, false);
  assert.equal(interpretarCiudadano(q).accion, 'ejecutar');
});

test('acusación no se traduce a anomalía', () => {
  for (const q of [
    '¿Cuáles contratos son corruptos?',
    '¿Ese contratista se robó la plata?',
    '¿Este contrato es fraude?'
  ]) {
    const d = interpretarCiudadano(q);
    assert.equal(d.accion, 'rechazar', q);
    assert.equal(d.regla, 'acusacion');
  }
});

test('definiciones documentales no ejecutan SQL', () => {
  for (const q of [
    '¿Qué es el RUP?',
    '¿Qué significa mínima cuantía?',
    '¿Qué es contratación directa?',
    '¿Qué requisitos piden para contratar con el Estado?'
  ]) {
    const d = interpretarCiudadano(q);
    assert.equal(d.accion, 'documental', q);
    assert.equal(d.regla, 'documental');
  }
});

test('qué es Isolation Forest va a la ficha, no al listado', () => {
  const d = interpretarCiudadano('¿Qué es Isolation Forest?');
  assert.equal(d.accion, 'documental');
});

test('a dedo y sin concurso piden aclaración', () => {
  assert.equal(interpretarCiudadano('¿Cuántos contratos dieron a dedo?').accion, 'aclarar');
  assert.equal(interpretarCiudadano('¿Qué contratos se hicieron sin concurso?').accion, 'aclarar');
});

test('pequeños y grandes piden umbral', () => {
  assert.equal(interpretarCiudadano('¿Qué contratos pequeños hicieron?').accion, 'aclarar');
  assert.equal(interpretarCiudadano('¿Cuántos contratos pequeños hubo?').accion, 'aclarar');
});

test('la ciudad sin municipio se aclara; Bogotá no', () => {
  assert.equal(interpretarCiudadano('¿Qué pasó con los contratos de la ciudad?').accion, 'aclarar');
  assert.equal(interpretarCiudadano('¿Cuántos contratos hay en Bogotá?').accion, 'ejecutar');
});

test('ese contrato sin identificador pide el CO1', () => {
  const d = interpretarCiudadano('¿Quién se ganó ese contrato?');
  assert.equal(d.accion, 'aclarar');
  assert.equal(d.regla, 'seguimiento');
  const conId = interpretarCiudadano('¿Por qué es atípico CO1.PCCNTR.9673418?');
  assert.equal(conId.accion, 'ejecutar');
});

test('listado por licitación no se sustituye por la distribución nacional', () => {
  const d = interpretarCiudadano('¿Cuáles se hicieron por licitación pública?');
  assert.equal(d.accion, 'aclarar');
  assert.equal(d.regla, 'listado_modalidad');
});

test('gasto realmente no se vende como valor contratado', () => {
  const d = interpretarCiudadano('¿Cuánto se gastó realmente?');
  assert.equal(d.accion, 'aclarar');
  assert.equal(d.regla, 'gasto_ejecutado');
});

test('qué es Isolation Forest no se lista como top 1 %', () => {
  const m = extraerMenciones('¿Qué es Isolation Forest?');
  assert.equal(m.especial, 'PORQUE_ATIPICO');
});

test('valor total contratado se cuenta, no se deja al LLM', () => {
  const m = extraerMenciones('¿Cuál fue el valor total contratado?');
  assert.equal(m.operacion, 'contar');
  assert.equal(m.metrica, 'valor');
  assert.equal(m.especial, null);
});

test('puntuación alta de Isolation Forest se explica con la ficha', () => {
  assert.equal(
    interpretarCiudadano('¿Una puntuación alta de Isolation Forest demuestra una irregularidad comprobada?').accion,
    'documental'
  );
});

test('n_estimators y SISBÉN no se van a SQL', () => {
  assert.equal(
    interpretarCiudadano('¿Cuántos árboles (n_estimators) usa Isolation Forest en c1_if_v1?').accion,
    'documental'
  );
  assert.equal(interpretarCiudadano('¿Qué es el SISBÉN IV?').accion, 'documental');
  assert.equal(
    interpretarCiudadano('¿Los oferentes deben acreditar el RUP en un proceso de mínima cuantía?').accion,
    'documental'
  );
});

test('consultas analíticas previas siguen ejecutables', () => {
  for (const q of [
    '¿Cuántos contratos hicieron en Bogotá en septiembre de 2026?',
    'Muéstrame las modalidades de contratación',
    '¿Qué entidad contrató más?',
    '¿Cuáles son los contratos con comportamientos atípicos?',
    '¿A quién le dieron más contratos?'
  ]) {
    assert.equal(interpretarCiudadano(q).accion, 'ejecutar', q);
  }
});
