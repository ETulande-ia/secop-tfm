const { test, beforeEach, afterEach, describe } = require('node:test');
const assert = require('node:assert/strict');
const rag = require('../modules/rag-documental');
const detector = require('../modules/intent-detector');
const {
  MODOS_RAG,
  TEXTO_RAG_OFF,
  normalizarModoRag,
  ragPermitido,
  respuestaDocumentalDeshabilitada
} = require('../modules/modo-rag');
const { processUserQuery } = require('../orchestration/query.orchestrator');
const { interpretarCiudadano } = require('../modules/interpretacion-ciudadana');

beforeEach(() => {
  detector.setDetectarIntencion(async () => ({
    intent: 'UNKNOWN',
    indicador: null,
    codigo_dane: null
  }));
});

afterEach(() => {
  rag.restaurarDependencias();
  detector.restaurarDetectarIntencion();
});

const HIT_MINIMA = {
  fragment_id: 'cce-minima-cuantia-2024-p004-004-601acaff',
  doc_id: 'cce-minima-cuantia-2024',
  titulo: 'Manual de mínima cuantía (Colombia Compra Eficiente, 2024)',
  seccion: '¿Qué es la mínima cuantía?',
  pagina_inicio: 4,
  pagina_fin: 4,
  texto: 'La mínima cuantía es un procedimiento de selección cuyo valor no excede el 10 % de la menor cuantía.'
};

function recu(hits) {
  return {
    estrategia: 'B_coseno_top5_adyacentes_alcance',
    hits,
    cobertura_lexica: { cobertura: 'suficiente', razon: 'prueba' },
    informacion_insuficiente_umbral: false,
    similitud_max: 0.72,
    alcance: null
  };
}

function spies() {
  const estado = { recuperar: 0, completar: 0 };
  rag.setDependencias({
    recuperar: async () => {
      estado.recuperar += 1;
      return recu([HIT_MINIMA]);
    },
    completar: async () => {
      estado.completar += 1;
      return JSON.stringify({
        puede_responder: true,
        cobertura: 'suficiente',
        texto: 'La mínima cuantía no excede el 10 % de la menor cuantía.',
        fragment_ids: [HIT_MINIMA.fragment_id],
        limitaciones: ''
      });
    }
  });
  return estado;
}

const DOC = '¿Qué es la modalidad de mínima cuantía?';
const SQL = '¿Cuántos contratos hay en Bogotá?';
const AMBIGUA = '¿Cuántos contratos dieron a dedo?';
const FRAUDE = '¿Este contrato es fraude?';

describe('normalización de modoRag', () => {
  test('auto es el valor predeterminado y los desconocidos no habilitan un modo nuevo', () => {
    assert.deepEqual(MODOS_RAG, ['auto', 'on', 'off']);
    assert.equal(normalizarModoRag(undefined), 'auto');
    assert.equal(normalizarModoRag(null), 'auto');
    assert.equal(normalizarModoRag(''), 'auto');
    assert.equal(normalizarModoRag('AUTO'), 'auto');
    assert.equal(normalizarModoRag('On'), 'on');
    assert.equal(normalizarModoRag('off'), 'off');
    assert.equal(normalizarModoRag('pgvector'), 'auto');
    assert.equal(ragPermitido('auto'), true);
    assert.equal(ragPermitido('on'), true);
    assert.equal(ragPermitido('off'), false);
  });

  test('la plantilla off no genera con el modelo ni cita corpus', () => {
    const r = respuestaDocumentalDeshabilitada();
    assert.equal(r.intent, 'RAG_DESHABILITADO');
    assert.equal(r.text, TEXTO_RAG_OFF);
    assert.equal(r.referencias.length, 0);
    assert.doesNotMatch(r.text, /gpt-4o-mini|fragment_id/i);
  });
});

describe('compatibilidad: sin modoRag el flujo actual se conserva', () => {
  test('un valor desconocido se trata como auto y sí recupera', async () => {
    const estado = spies();
    const r = await processUserQuery(DOC, undefined, { modoRag: 'pgvector' });
    assert.equal(r.modoRag, 'auto');
    assert.equal(r.ruta, 'documental');
    assert.equal(estado.recuperar, 1);
  });

  test('pregunta documental sigue en RAG y anota auto', async () => {
    const estado = spies();
    const r = await processUserQuery(DOC);
    assert.equal(r.modoRag, 'auto');
    assert.equal(r.ruta, 'documental');
    assert.equal(r.intent, 'RAG_DOCUMENTAL');
    assert.equal(estado.recuperar, 1);
    assert.equal(estado.completar, 1);
    assert.match(r.text, /10 %/);
  });
});

for (const modo of ['auto', 'on']) {
  describe(`modo ${modo}: RAG documental, SQL analítico`, () => {
    test('pregunta documental llama al recuperador', async () => {
      const estado = spies();
      const r = await processUserQuery(DOC, undefined, { modoRag: modo });
      assert.equal(r.modoRag, modo);
      assert.equal(r.ruta, 'documental');
      assert.equal(r.intent, 'RAG_DOCUMENTAL');
      assert.equal(estado.recuperar, 1);
      assert.equal(r.referencias[0].fragment_id, HIT_MINIMA.fragment_id);
    });

    test('pregunta analítica no se sustituye por RAG', () => {
      const d = interpretarCiudadano(SQL);
      assert.equal(d.accion, 'ejecutar');
    });

    test('pregunta analítica no llama al recuperador', async () => {
      const estado = spies();
      const r = await processUserQuery(SQL, undefined, { modoRag: modo });
      assert.equal(estado.recuperar, 0);
      assert.equal(estado.completar, 0);
      assert.equal(r.modoRag, modo);
      assert.equal(r.ruta, 'sql');
      assert.notEqual(r.intent, 'RAG_DOCUMENTAL');
      assert.notEqual(r.intent, 'RAG_DESHABILITADO');
    });

    test('pregunta ambigua sigue pidiendo aclaración', async () => {
      const estado = spies();
      const r = await processUserQuery(AMBIGUA, undefined, { modoRag: modo });
      assert.equal(estado.recuperar, 0);
      assert.equal(r.modoRag, modo);
      assert.equal(r.ruta, 'aclarar');
      assert.equal(r.intent, 'NO_SOPORTADO');
      assert.match(r.text, /contrataci[oó]n directa/i);
    });

    test('fraude no entra a RAG', async () => {
      const estado = spies();
      const r = await processUserQuery(FRAUDE, undefined, { modoRag: modo });
      assert.equal(estado.recuperar, 0);
      assert.equal(r.modoRag, modo);
      assert.equal(r.ruta, 'rechazar');
      assert.match(r.text, /delitos|fraude/i);
    });
  });
}

describe('modo off: sin recuperación documental, con SQL', () => {
  test('pregunta documental no llama al servicio ni genera con GPT', async () => {
    const estado = spies();
    const r = await processUserQuery(DOC, undefined, { modoRag: 'off' });
    assert.equal(estado.recuperar, 0);
    assert.equal(estado.completar, 0);
    assert.equal(r.modoRag, 'off');
    assert.equal(r.ruta, 'documental_deshabilitada');
    assert.equal(r.intent, 'RAG_DESHABILITADO');
    assert.equal(r.text, TEXTO_RAG_OFF);
    assert.deepEqual(r.referencias, []);
    assert.doesNotMatch(r.text, /10 %|menor cuantía|Fuentes \(corpus v1\)/);
  });

  test('pregunta analítica sigue en SQL', async () => {
    const estado = spies();
    const r = await processUserQuery(SQL, undefined, { modoRag: 'off' });
    assert.equal(estado.recuperar, 0);
    assert.equal(r.modoRag, 'off');
    assert.equal(r.ruta, 'sql');
    assert.notEqual(r.intent, 'RAG_DESHABILITADO');
    assert.notEqual(r.intent, 'RAG_DOCUMENTAL');
  });

  test('pregunta ambigua no se convierte en generación sin RAG', async () => {
    const estado = spies();
    const r = await processUserQuery(AMBIGUA, undefined, { modoRag: 'off' });
    assert.equal(estado.recuperar, 0);
    assert.equal(r.ruta, 'aclarar');
    assert.match(r.text, /contrataci[oó]n directa/i);
  });

  test('fraude sigue rechazado', async () => {
    const estado = spies();
    const r = await processUserQuery(FRAUDE, undefined, { modoRag: 'off' });
    assert.equal(estado.recuperar, 0);
    assert.equal(r.ruta, 'rechazar');
    assert.match(r.text, /delitos|fraude/i);
  });
});
