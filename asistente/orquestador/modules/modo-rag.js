/**
 * Modo operativo de recuperación documental.
 * No es la comparación experimental GPT-4o-mini sin fragmentos (notebook 13).
 *
 * auto / on: RAG en preguntas documentales; SQL en analíticas.
 * off: no llama al servicio de recuperación; las cifras SQL se conservan.
 */
const MODOS_RAG = Object.freeze(['auto', 'on', 'off']);

const TEXTO_RAG_OFF =
  'La consulta a los manuales está desactivada. Puedo responder cifras de contratación ' +
  'publicadas en septiembre de 2026. No sustituyo esa explicación por una consulta SQL ' +
  'ni por conocimiento general del modelo.';

function normalizarModoRag(valor) {
  const v = String(valor == null || valor === '' ? 'auto' : valor)
    .toLowerCase()
    .trim();
  return MODOS_RAG.includes(v) ? v : 'auto';
}

function ragPermitido(modoRag) {
  return normalizarModoRag(modoRag) !== 'off';
}

function respuestaDocumentalDeshabilitada() {
  return {
    intent: 'RAG_DESHABILITADO',
    description: 'Recuperación documental desactivada',
    text: TEXTO_RAG_OFF,
    data: null,
    visualization: null,
    referencias: [],
    evidencia: { cobertura: 'deshabilitada' }
  };
}

function anotar(res, modoRag, ruta) {
  const base = res && typeof res === 'object' ? res : { text: String(res || ''), data: null };
  return Object.assign({}, base, {
    modoRag: normalizarModoRag(modoRag),
    ruta
  });
}

module.exports = {
  MODOS_RAG,
  TEXTO_RAG_OFF,
  normalizarModoRag,
  ragPermitido,
  respuestaDocumentalDeshabilitada,
  anotar
};
