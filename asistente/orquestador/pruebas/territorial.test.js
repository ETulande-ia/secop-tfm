const { test, afterEach } = require('node:test');
const assert = require('node:assert/strict');
const territorial = require('../modules/territorial');

afterEach(() => territorial.setConsultar());

test('rechaza un periodo que no es AAAA-MM', () => {
  assert.throws(() => territorial.validarPeriodo('2026'), { codigo: 400 });
  assert.throws(() => territorial.validarPeriodo('2026-9'), { codigo: 400 });
  assert.throws(() => territorial.validarPeriodo('2026-09; drop'), { codigo: 400 });
});

test('acepta el periodo por defecto o AAAA-MM', () => {
  assert.equal(territorial.validarPeriodo('2026-09'), '2026-09');
  assert.match(territorial.validarPeriodo(), /^\d{4}-\d{2}$/);
});

test('los indicadores derivados evitan la división por cero', () => {
  assert.deepEqual(territorial.indicadoresDerivados(10, 200, 0), {
    contratos_por_100k: null,
    valor_por_habitante: null
  });
  const ok = territorial.indicadoresDerivados(50, 200000, 100000);
  assert.equal(ok.contratos_por_100k, 50);
  assert.equal(ok.valor_por_habitante, 2);
});

test('la cobertura suma el total sin duplicar contratos', () => {
  const res = territorial.armarRespuesta(
    [{
      codigo_dane: '11',
      nombre_departamento: 'BOGOTÁ D.C.',
      poblacion_total: 100,
      total_hombres: 40,
      total_mujeres: 60,
      n_contratos_por_codigo: 8,
      n_contratos_por_nombre: 2,
      n_contratos: 10,
      valor_total: 1000,
      contratos_por_100k: 10000,
      valor_por_habitante: 10
    }],
    { total: 20, por_codigo: 12, por_nombre: 5 },
    '2026-09'
  );
  const c = res.cobertura;
  assert.equal(c.por_codigo + c.por_nombre + c.sin_departamento, c.total);
  assert.equal(c.sin_departamento, 3);
  assert.equal(res.departamentos[0].n_contratos, 10);
  assert.equal(res.anio_poblacion, 2018);
});

test('departamentos consulta Postgres con el periodo parametrizado', async () => {
  const vistos = [];
  territorial.setConsultar(async (sql, params) => {
    vistos.push({ sql, params });
    if (sql.includes('poblacion_total')) {
      return [{
        codigo_dane: '05',
        nombre_departamento: 'ANTIOQUIA',
        poblacion_total: '100000',
        total_hombres: '48000',
        total_mujeres: '52000',
        n_contratos_por_codigo: '9',
        n_contratos_por_nombre: '1',
        n_contratos: '10',
        valor_total: '200000',
        contratos_por_100k: '10',
        valor_por_habitante: '2'
      }];
    }
    return [{ total: '15', por_codigo: '9', por_nombre: '1' }];
  });
  const res = await territorial.departamentos({ periodo: '2026-09' });
  assert.equal(vistos.length, 2);
  assert.deepEqual(vistos[0].params, ['2026-09']);
  assert.deepEqual(vistos[1].params, ['2026-09']);
  assert.ok(vistos[0].sql.includes('$1'));
  assert.equal(res.departamentos.length, 1);
  assert.equal(res.departamentos[0].poblacion_total, 100000);
  assert.equal(res.cobertura.sin_departamento, 5);
});
