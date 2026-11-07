/**
 * Ruta documental del chat. Recupera con el servicio Python congelado
 * y genera solo a partir de esos fragmentos. No duplica el ranking.
 */
const axios = require('axios');
const OpenAI = require('openai');
const { ragUrl } = require('../config');

const MODELO_GENERACION = 'gpt-4o-mini';
const TEMPERATURA_GENERACION = 0;

const AVISO_VIGENCIA =
  'Los manuales del corpus no acreditan por sí mismos la vigencia normativa actual. ' +
  'El extracto analítico es de septiembre de 2026; los PDF son de 2021–2024 y la ficha C1 es metodológica.';

const TEXTO_INSUFICIENTE =
  'No encontré en los cuatro documentos del corpus v1 evidencia suficiente para responder. ' +
  'El corpus cubre el manual de mínima cuantía (2024), el de requisitos habilitantes/RUP (2023), ' +
  'el diccionario de datos abiertos SECOP y la ficha C1 + Isolation Forest. ' +
  'La guía de proceso sancionatorio está excluida. No invento artículos, requisitos ni cifras. ' +
  AVISO_VIGENCIA;

let recuperarFn = recuperarHttp;
let completarFn = completarOpenAi;

function setDependencias(deps) {
  if (deps && typeof deps.recuperar === 'function') recuperarFn = deps.recuperar;
  if (deps && typeof deps.completar === 'function') completarFn = deps.completar;
}

function restaurarDependencias() {
  recuperarFn = recuperarHttp;
  completarFn = completarOpenAi;
}

function cliente() {
  return new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
}

async function recuperarHttp(pregunta) {
  const base = String(ragUrl || process.env.RAG_URL || 'http://rag-documental:8091').replace(/\/$/, '');
  try {
    const res = await axios.post(
      `${base}/recuperar`,
      { pregunta },
      { timeout: 25000, headers: { 'Content-Type': 'application/json' } }
    );
    return res.data;
  } catch (exc) {
    const detalle = (exc.response && exc.response.data && exc.response.data.error) || exc.message;
    const err = new Error(`Servicio documental no disponible: ${detalle}`);
    err.codigo = exc.response ? 'rag_http' : 'rag_caido';
    throw err;
  }
}

async function completarOpenAi(prompt) {
  const response = await cliente().chat.completions.create({
    model: MODELO_GENERACION,
    messages: [{ role: 'user', content: prompt }],
    temperature: TEMPERATURA_GENERACION
  });
  return response.choices[0].message.content;
}

function limpiarLimitacion(texto) {
  const t = String(texto || '').replace(/\s+/g, ' ').trim();
  if (!t) return '';
  const p = t
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[.:;¡!¿?'"]+/g, '')
    .trim();
  const vacios = new Set([
    'ninguna', 'ninguno', 'n/a', 'na', 'none', 'nil', '-',
    'no aplica', 'no hay', 'sin limitaciones', 'null', 'undefined', ''
  ]);
  if (vacios.has(p) || p.length < 4) return '';
  return t;
}

function fusionarCobertura(recuperado, llm) {
  const lex = String((recuperado.cobertura_lexica || {}).cobertura || '');
  const n = Array.isArray(recuperado.hits) ? recuperado.hits.length : 0;
  const umbralBajo = Boolean(recuperado.informacion_insuficiente_umbral);
  const llmCubre = llm && llm.cobertura;
  const llmNo = !llm || llm.puede_responder === false || llmCubre === 'insuficiente';

  if (n === 0) return 'no_cubierta';
  if (llmNo) return 'no_cubierta';
  if (lex === 'no_cubierta') {
    return llmCubre === 'parcial' ? 'parcial' : 'no_cubierta';
  }
  if (lex === 'parcial' || llmCubre === 'parcial' || umbralBajo) return 'parcial';
  return 'suficiente';
}

function citasDeHits(ids, hits) {
  const byId = new Map((hits || []).map((h) => [String(h.fragment_id), h]));
  const vistos = new Set();
  const out = [];
  for (const id of ids || []) {
    const key = String(id);
    if (vistos.has(key)) continue;
    const h = byId.get(key);
    if (!h) continue;
    vistos.add(key);
    const pIni = h.pagina_inicio;
    const pFin = h.pagina_fin;
    const pagina = (pIni != null && pFin != null && Number(pIni) !== Number(pFin))
      ? `${pIni}–${pFin}`
      : (pIni != null ? String(pIni) : null);
    out.push({
      fragment_id: key,
      documento: h.titulo || h.doc_id || null,
      seccion: h.seccion || null,
      pagina,
      pagina_inicio: pIni == null ? null : Number(pIni),
      pagina_fin: pFin == null ? null : Number(pFin),
      doc_id: h.doc_id || null
    });
  }
  return out;
}

function textoCitas(referencias) {
  if (!referencias.length) return '';
  const lineas = referencias.map((r) => {
    const seccion = r.seccion ? `, sección «${r.seccion}»` : '';
    const pag = r.pagina ? `, p. ${r.pagina}` : '';
    return `- ${r.documento}${seccion}${pag}`;
  });
  return ['Fuentes (corpus v1):', ...lineas].join('\n');
}

function parsearLlm(raw) {
  const t = String(raw || '').trim();
  const ini = t.indexOf('{');
  const fin = t.lastIndexOf('}');
  if (ini < 0 || fin <= ini) {
    return { puede_responder: false, cobertura: 'insuficiente', texto: '', fragment_ids: [] };
  }
  try {
    const obj = JSON.parse(t.slice(ini, fin + 1));
    const ids = Array.isArray(obj.fragment_ids)
      ? obj.fragment_ids.map((x) => String(x))
      : [];
    return {
      puede_responder: obj.puede_responder !== false,
      cobertura: ['suficiente', 'parcial', 'insuficiente'].includes(obj.cobertura)
        ? obj.cobertura
        : (obj.puede_responder === false ? 'insuficiente' : 'parcial'),
      texto: String(obj.texto || '').trim(),
      fragment_ids: ids,
      limitaciones: limpiarLimitacion(obj.limitaciones)
    };
  } catch {
    return { puede_responder: false, cobertura: 'insuficiente', texto: '', fragment_ids: [] };
  }
}

function promptGeneracion(pregunta, hits) {
  const bloques = (hits || []).map((h, i) => {
    const pag = h.pagina_inicio != null ? `p. ${h.pagina_inicio}` : 'p. s/d';
    return [
      `FRAGMENTO ${i + 1}`,
      `fragment_id: ${h.fragment_id}`,
      `documento: ${h.titulo || h.doc_id}`,
      `seccion: ${h.seccion || 's/d'}`,
      `pagina: ${pag}`,
      `texto: ${h.texto || ''}`
    ].join('\n');
  }).join('\n\n');

  return `Eres un asistente de contratación pública. Responde SOLO con JSON válido.

Pregunta del ciudadano:
${pregunta}

Fragmentos recuperados del corpus v1 (únicas fuentes permitidas):
${bloques || '(ninguno)'}

Reglas:
- Usa únicamente estos fragmentos. No inventes artículos, requisitos, plazos, umbrales ni cifras.
- No afirmes vigencia normativa actual. Los manuales no actualizan el régimen de 2026.
- Distingue lo que dice el documento de lo que rige hoy.
- Atipicidad estadística no es fraude ni irregularidad.
- Si los fragmentos no cubren la pregunta, puede_responder=false.
- Si tratan el tema general pero no el recorte pedido (municipio, año, cifra en pesos),
  puede_responder=true, cobertura="parcial": di qué sí está en el texto y qué falta. No inventes la cifra.
- No uses conocimiento externo para completar huecos.
- fragment_ids solo de la lista anterior.
- texto: respuesta breve en español, sin puntuaciones de similitud.
- limitaciones: solo si hay un recorte real (falta cifra, año o municipio). Si no hay, usa "".

JSON:
{
  "puede_responder": true,
  "cobertura": "suficiente" | "parcial" | "insuficiente",
  "texto": "...",
  "fragment_ids": ["..."],
  "limitaciones": "..."
}`;
}

function respuestaInsuficiente(recuperado, motivo) {
  const refs = [];
  return {
    intent: 'RAG_DOCUMENTAL',
    description: 'Consulta documental sin evidencia suficiente',
    text: TEXTO_INSUFICIENTE,
    data: null,
    visualization: null,
    referencias: refs,
    evidencia: {
      cobertura: 'no_cubierta',
      motivo: motivo || (recuperado && recuperado.cobertura_lexica && recuperado.cobertura_lexica.razon) || null,
      n_hits: recuperado && Array.isArray(recuperado.hits) ? recuperado.hits.length : 0,
      alcance: recuperado && recuperado.alcance,
      similitud_max: recuperado && recuperado.similitud_max,
      estrategia: recuperado && recuperado.estrategia
    },
    slots: { ruta: 'documental' }
  };
}

function componerTexto(llm, cobertura, referencias) {
  const partes = [llm.texto];
  if (cobertura === 'parcial') {
    partes.push(
      'La documentación recuperada cubre solo parte de la pregunta; no completo el resto con información externa.'
    );
  }
  if (llm.limitaciones) partes.push(llm.limitaciones);
  partes.push(AVISO_VIGENCIA);
  const citas = textoCitas(referencias);
  if (citas) partes.push(citas);
  return partes.filter(Boolean).join('\n\n');
}

async function responderDocumental(pregunta) {
  let recuperado;
  try {
    recuperado = await recuperarFn(pregunta);
  } catch (exc) {
    return {
      intent: 'NO_SOPORTADO',
      text: 'No pude consultar los manuales en este momento. No sustituyo esa explicación por una cifra SQL.',
      data: null,
      visualization: null,
      evidencia: { cobertura: 'error_infra', motivo: exc.message },
      slots: { ruta: 'documental' }
    };
  }

  const lex = String((recuperado.cobertura_lexica || {}).cobertura || '');
  if (!recuperado.hits || recuperado.hits.length === 0) {
    return respuestaInsuficiente(recuperado, 'sin_hits');
  }

  const crudo = await completarFn(promptGeneracion(pregunta, recuperado.hits));
  const llm = parsearLlm(crudo);
  const idsValidos = citasDeHits(llm.fragment_ids, recuperado.hits).map((r) => r.fragment_id);
  const cobertura = fusionarCobertura(recuperado, {
    ...llm,
    puede_responder: llm.puede_responder && idsValidos.length > 0 && Boolean(llm.texto)
  });

  if (cobertura === 'no_cubierta') {
    return respuestaInsuficiente(recuperado, 'generacion_sin_evidencia');
  }

  const referencias = citasDeHits(idsValidos, recuperado.hits);
  return {
    intent: 'RAG_DOCUMENTAL',
    description: 'Respuesta documental a partir del corpus v1',
    text: componerTexto(llm, cobertura, referencias),
    data: null,
    visualization: null,
    referencias,
    evidencia: {
      cobertura,
      lexical: lex,
      n_hits: recuperado.hits.length,
      alcance: recuperado.alcance,
      similitud_max: recuperado.similitud_max,
      estrategia: recuperado.estrategia,
      segundos_embedding: recuperado.segundos_embedding,
      segundos_busqueda: recuperado.segundos_busqueda
    },
    slots: { ruta: 'documental' }
  };
}

module.exports = {
  responderDocumental,
  fusionarCobertura,
  citasDeHits,
  parsearLlm,
  limpiarLimitacion,
  promptGeneracion,
  MODELO_GENERACION,
  TEMPERATURA_GENERACION,
  TEXTO_INSUFICIENTE,
  AVISO_VIGENCIA,
  setDependencias,
  restaurarDependencias
};
