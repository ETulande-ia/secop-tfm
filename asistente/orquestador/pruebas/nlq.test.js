const { test } = require('node:test');
const assert = require('node:assert/strict');
const {
  extraerMenciones,
  fusionar,
  elegirModalidad,
  visualizacionNlq,
  textoNlq,
  mapearFilas
} = require('../modules/nlq');

test('Q1 cuenta contratos en Bogotá, sin modalidad ni entidad', () => {
  const m = extraerMenciones('¿Cuántos contratos se registraron en Bogotá durante septiembre 2026?');
  assert.equal(m.especial, null);
  assert.equal(m.operacion, 'contar');
  assert.equal(m.territorio, 'bogota');
  assert.equal(m.entidadTexto, null);
  assert.equal(m.modalidadTexto, null);
  assert.equal(m.periodoInvalido, false);
  assert.equal(m.metrica, 'n_contratos');
});

test('Q2 no se desplaza a un recuento de Bogotá sin modalidad', () => {
  const m = extraerMenciones('¿Cuántos contratos de contratación directa se registraron en Bogotá?');
  assert.equal(m.operacion, 'contar');
  assert.equal(m.territorio, 'bogota');
  assert.equal(m.modalidadTexto, 'contratacion directa');
  assert.notEqual(m.operacion, 'distribucion');
});

test('Q3 pide distribución de Bogotá, no el recuento nacional', () => {
  const m = extraerMenciones('¿Cómo se distribuyen los contratos de Bogotá por modalidad?');
  assert.equal(m.operacion, 'distribucion');
  assert.equal(m.territorio, 'bogota');
  assert.equal(m.modalidadTexto, null);
});

test('Q4 ordena entidades de Bogotá por número de contratos', () => {
  const m = extraerMenciones('¿Cuáles son las entidades de Bogotá con más contratos?');
  assert.equal(m.operacion, 'ranking');
  assert.equal(m.metrica, 'n_contratos');
  assert.equal(m.territorio, 'bogota');
});

test('Q5 extrae el nombre de la entidad', () => {
  const m = extraerMenciones(
    '¿Cuántos contratos registró la Secretaría Distrital de Integración Social?'
  );
  assert.equal(m.operacion, 'contar');
  assert.ok(m.entidadTexto && m.entidadTexto.includes('secretaria'));
});

test('seguimiento copia entidad solo del contexto de la petición', () => {
  const prev = {
    entidad: '(Secretaría Distrital de Integración Social)',
    territorio: 'bogota',
    modalidad: null,
    periodo: '2026-09'
  };
  const q6 = extraerMenciones('¿Qué modalidades utilizó esa entidad?');
  assert.equal(q6.seguimiento, true);
  assert.equal(q6.operacion, 'distribucion');
  const s6 = fusionar(q6, prev);
  assert.equal(s6.entidad, '(Secretaría Distrital de Integración Social)');
  assert.equal(s6.territorio, 'bogota');

  const q7 = extraerMenciones('¿Cuántos contratos de contratación directa tuvo esa entidad?');
  assert.equal(q7.seguimiento, true);
  assert.equal(q7.operacion, 'contar');
  assert.equal(q7.modalidadTexto, 'contratacion directa');
  const s7 = fusionar(q7, prev);
  assert.equal(s7.entidad, '(Secretaría Distrital de Integración Social)');

  const q8 = extraerMenciones('¿Y cuántos fueron de mínima cuantía?');
  assert.equal(q8.seguimiento, true);
  assert.equal(q8.operacion, 'contar');
  assert.equal(q8.modalidadTexto, 'minima cuantia');
  const s8 = fusionar(q8, prev);
  assert.equal(s8.entidad, '(Secretaría Distrital de Integración Social)');

  const sinPrev = fusionar(q6, null);
  assert.equal(sinPrev.entidad, null);
  assert.equal(sinPrev.territorio, null);
});

test('el título del gráfico incluye el filtro de Bogotá', () => {
  const vis = visualizacionNlq({
    operacion: 'distribucion',
    territorio: 'bogota',
    entidad: null
  });
  assert.match(vis.title, /Bogotá/);
  assert.equal(vis.y, 'n');
  const nacional = visualizacionNlq({ operacion: 'distribucion' });
  assert.equal(nacional.title.includes('Bogotá'), false);
});

test('periodo no publicado se marca inválido', () => {
  const m = extraerMenciones('¿Cuántos contratos hubo en julio de 2025?');
  assert.equal(m.periodoInvalido, true);
});

test('territorio no soportado no se sustituye por Bogotá', () => {
  const m = extraerMenciones('¿Cuántos contratos se registraron en Medellín?');
  assert.equal(m.territorioDesconocido, 'medellin');
  assert.notEqual(m.territorio, 'bogota');
});

test('consulta no soportada: atípicos con filtro territorial', () => {
  const m = extraerMenciones('¿Cuáles son los contratos atípicos en Bogotá?');
  assert.equal(m.especial, 'TOP1_IF');
  assert.equal(m.territorio, 'bogota');
});

test('elige la modalidad exacta y evita la variante con ofertas', () => {
  const lista = [
    'Contratación Directa (con ofertas)',
    'Contratación Directa',
    'Mínima cuantía'
  ];
  assert.equal(elegirModalidad('contratacion directa', lista), 'Contratación Directa');
  assert.equal(elegirModalidad('minima cuantia', lista), 'Mínima cuantía');
});

test('preguntas ciudadanas simples siguen siendo parametrizables', () => {
  const valor = extraerMenciones('¿Cuánto se contrató en Bogotá?');
  assert.equal(valor.operacion, 'contar');
  assert.equal(valor.metrica, 'valor');
  const ranking = extraerMenciones('¿Cuáles fueron las entidades con mayor contratación?');
  assert.equal(ranking.operacion, 'ranking');
  assert.equal(ranking.metrica, 'valor');
  assert.equal(ranking.periodoInvalido, false);
  assert.equal(extraerMenciones('Entidades que más contrataron').operacion, 'ranking');
  assert.equal(extraerMenciones('¿Qué modalidades de contratación se utilizaron?').operacion, 'distribucion');
  assert.equal(extraerMenciones('¿Cuáles son los contratos con comportamientos atípicos?').especial, 'TOP1_IF');
});

test('el recuento no añade valor, C1 ni gráfico', () => {
  const slots = {
    operacion: 'contar',
    metrica: 'n_contratos',
    periodo: '2026-09',
    territorio: 'bogota'
  };
  const texto = textoNlq(slots, { rows: [{ n: 11272, valor: 999, n_aptos: 100 }] });
  assert.match(texto, /11\.272/);
  assert.equal(texto.includes('COP'), false);
  assert.equal(/apto|C1/i.test(texto), false);
  const filas = mapearFilas(slots, [{ n: 11272, valor: 999, n_aptos: 100 }]);
  assert.deepEqual(Object.keys(filas[0]), ['n']);
  assert.equal(visualizacionNlq(slots), null);
});

test('el valor no añade el recuento de contratos', () => {
  const slots = { operacion: 'contar', metrica: 'valor', periodo: '2026-09', territorio: 'bogota' };
  const texto = textoNlq(slots, { rows: [{ valor: 1500 }] });
  assert.match(texto, /COP/);
  assert.equal(/se registraron/i.test(texto), false);
  assert.deepEqual(Object.keys(mapearFilas(slots, [{ valor: 1500 }])[0]), ['valor']);
});

test('el ranking solo incluye la métrica pedida', () => {
  const slots = { operacion: 'ranking', metrica: 'n_contratos', periodo: '2026-09', territorio: 'bogota' };
  const filas = mapearFilas(slots, [{ entidad: 'A', num_contratos: 10, total_contratado: 99 }]);
  assert.deepEqual(Object.keys(filas[0]), ['entidad', 'num_contratos']);
  const texto = textoNlq(slots, { rows: [{ entidad: 'A', num_contratos: 10, total_contratado: 99 }] });
  assert.equal(texto.includes('COP'), false);
});

test('seguimiento de valor conserva filtros y cambia la métrica', () => {
  const prev = { territorio: 'bogota', entidad: null, operacion: 'contar', periodo: '2026-09' };
  const m = extraerMenciones('¿Y el valor?');
  assert.equal(m.seguimiento, true);
  assert.equal(m.metrica, 'valor');
  const s = fusionar(m, prev);
  assert.equal(s.territorio, 'bogota');
  assert.equal(s.operacion, 'contar');
  assert.equal(s.metrica, 'valor');
});
