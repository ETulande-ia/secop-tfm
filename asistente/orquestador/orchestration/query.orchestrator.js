const intentConfig = require('./intent-config');
const { detectIntentLLM } = require('../modules/intent-detector');
const analyticalQuery = require('../modules/analytical-query');
const narrativeExplainer = require('../modules/narrative-explainer');
const ragRetriever = require('../modules/rag-retriever');
const nlq = require('../modules/nlq');
const { interpretarCiudadano } = require('../modules/interpretacion-ciudadana');
const ragDocumental = require('../modules/rag-documental');
const {
  normalizarModoRag,
  ragPermitido,
  respuestaDocumentalDeshabilitada,
  anotar
} = require('../modules/modo-rag');
const {
  validarLecturaMapa,
  respuestaMapa
} = require('../modules/mapa-territorial-intent');

function normalizeQuery(query) {
  return query
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/contrastos/g, 'contratos')
    .replace(/proveedoras/g, 'proveedores')
    .replace(/\s+/g, ' ')
    .trim();
}

const extraerIdContrato = nlq.extraerIdContrato;

function rechazar(mensaje) {
  return {
    intent: 'NO_SOPORTADO',
    text: mensaje,
    data: null,
    visualization: null
  };
}

function intentNlq(slots) {
  if (slots.operacion === 'contar' && slots.territorio === 'bogota' && !slots.entidad && !slots.modalidad) {
    return 'BOGOTA_CONTRATACION';
  }
  if (slots.operacion === 'ranking' && !slots.territorio && !slots.entidad && !slots.modalidad) {
    return 'TOP_ENTIDADES';
  }
  if (slots.operacion === 'distribucion' && !slots.territorio && !slots.entidad) {
    return 'MODALIDADES';
  }
  return 'NLQ';
}

async function ejecutarNlq(userQuery, menciones, contexto) {
  const slots = nlq.fusionar(menciones, contexto);
  const resuelto = await nlq.resolver(slots, userQuery);
  if (resuelto.tipo === 'error') {
    return rechazar(resuelto.mensaje);
  }
  const result = await analyticalQuery.consultar(resuelto.slots);
  return {
    intent: intentNlq(resuelto.slots),
    description: 'Consulta analítica parametrizada',
    text: nlq.textoNlq(resuelto.slots, result),
    data: nlq.mapearFilas(resuelto.slots, result.rows),
    visualization: nlq.visualizacionNlq(resuelto.slots),
    slots: {
      operacion: resuelto.slots.operacion,
      metrica: resuelto.slots.metrica,
      territorio: resuelto.slots.territorio || null,
      entidad: resuelto.slots.entidad || null,
      modalidad: resuelto.slots.modalidad || null,
      periodo: resuelto.slots.periodo
    }
  };
}

function opcionesDe(opciones) {
  if (typeof opciones === 'string') return { modoRag: opciones };
  return opciones && typeof opciones === 'object' ? opciones : {};
}

async function clasificarPregunta(userQuery) {
  try {
    const r = await detectIntentLLM(userQuery);
    if (r && typeof r === 'object' && r.intent) return r;
    if (typeof r === 'string' && r.trim()) {
      return { intent: r.trim(), indicador: null, codigo_dane: null };
    }
  } catch (error) {
    console.error('Clasificador LLM no disponible:', error.message);
  }
  return { intent: 'UNKNOWN', indicador: null, codigo_dane: null };
}

async function processUserQuery(userQuery, contexto, opciones) {
  const modoRag = normalizarModoRag(opcionesDe(opciones).modoRag);
  const civico = interpretarCiudadano(userQuery, contexto);
  if (civico.accion === 'documental') {
    if (!ragPermitido(modoRag)) {
      return anotar(respuestaDocumentalDeshabilitada(), modoRag, 'documental_deshabilitada');
    }
    const documental = await ragDocumental.responderDocumental(userQuery);
    return anotar(documental, modoRag, 'documental');
  }
  if (civico.accion === 'aclarar' || civico.accion === 'rechazar') {
    const ruta = civico.accion === 'rechazar' ? 'rechazar' : 'aclarar';
    return anotar(rechazar(civico.mensaje), modoRag, ruta);
  }

  const menciones = nlq.extraerMenciones(userQuery, contexto);

  if (menciones.especial) {
    const extras = Boolean(
      menciones.territorio ||
      menciones.entidadTexto ||
      nlq.pistaModalidad(userQuery)
    );
    if (extras && menciones.especial !== 'PORQUE_ATIPICO' && menciones.especial !== 'EXPLAIN_CONTRACT') {
      return anotar(rechazar(
        'No puedo aplicar ese filtro de ciudad, entidad o modalidad a esta consulta. Para no mostrar otro resultado, no consulto una pregunta distinta.'
      ), modoRag, 'rechazar');
    }
    return anotar(await ejecutarEspecial(menciones.especial, userQuery, menciones), modoRag, 'especial');
  }

  const clasificacion = await clasificarPregunta(userQuery);
  if (clasificacion.intent === 'MAPA_TERRITORIAL') {
    const mapa = validarLecturaMapa(clasificacion);
    if (mapa.aclarar) {
      return anotar(rechazar(mapa.mensaje), modoRag, 'aclarar');
    }
    return anotar(respuestaMapa(mapa), modoRag, 'mapa');
  }

  if (
    menciones.operacion ||
    menciones.seguimiento ||
    menciones.territorio ||
    menciones.entidadTexto ||
    menciones.mencionaModalidad ||
    menciones.periodoInvalido ||
    menciones.territorioDesconocido
  ) {
    return anotar(await ejecutarNlq(userQuery, menciones, contexto), modoRag, 'sql');
  }

  const normalizedQuery = normalizeQuery(userQuery);
  let intentType = clasificacion.intent;
  const fallback = fallbackIntent(normalizedQuery);
  if (intentType === 'UNKNOWN' || !intentType || !intentConfig[intentType]) {
    intentType = fallback || intentType;
  }

  if (intentType === 'PORQUE_ATIPICO' || intentType === 'EXPLAIN_CONTRACT') {
    return anotar(await ejecutarEspecial(intentType, userQuery, {
      idContrato: extraerIdContrato(userQuery),
      ampliarAtipico: nlq.pideExplicacionAtipicidad(normalizedQuery)
    }), modoRag, 'especial');
  }

  if (intentType === 'MAPA_TERRITORIAL') {
    return anotar(rechazar(
      'No pude construir el mapa territorial. Indique el indicador que desea visualizar.'
    ), modoRag, 'aclarar');
  }

  const config = intentConfig[intentType];
  if (!config) {
    return anotar({
      text: 'No pude identificar claramente tu pregunta. ¿Puedes reformularla?',
      data: null
    }, modoRag, 'aclarar');
  }

  const result = await analyticalQuery.execute(intentType);
  const data = config.mapRow ? result.rows.map(config.mapRow) : result.rows;
  const text = await narrativeExplainer.explainAnalyticalResult(intentType, result);

  return anotar({
    intent: intentType,
    description: config.description,
    text,
    data,
    visualization: config.visualization || null
  }, modoRag, 'sql');
}

function filaScore(context) {
  if (!context || !context.contrato) return null;
  const s = context.puntuacion_if;
  const fila = {
    id_contrato: context.contrato.id_contrato,
    entidad: context.contrato.entidad
  };
  if (!s) return [fila];
  fila.rank = Number(s.rank_if);
  fila.score = Number(s.score_if);
  return [fila];
}

async function ejecutarEspecial(intentType, userQuery, menciones) {
  if (intentType === 'PORQUE_ATIPICO') {
    const idContrato = extraerIdContrato(userQuery) ||
      (menciones && menciones.idContrato) || null;
    const ampliar = Boolean(menciones && menciones.ampliarAtipico);
    const universo = ampliar ? await ragRetriever.contarUniversoIf() : null;
    if (!idContrato) {
      return {
        intent: 'PORQUE_ATIPICO',
        text: narrativeExplainer.explicarPorqueAtipico(null, null, universo, ampliar),
        data: null,
        visualization: null
      };
    }
    try {
      const context = await ragRetriever.retrieveContractContext(idContrato);
      return {
        intent: 'PORQUE_ATIPICO',
        idContrato,
        text: narrativeExplainer.explicarPorqueAtipico(context, idContrato, universo, ampliar),
        data: filaScore(context),
        visualization: null,
        slots: { idContrato }
      };
    } catch (error) {
      if (error.message === 'Contrato no encontrado') {
        return {
          intent: 'PORQUE_ATIPICO',
          text: `No encontré el contrato ${idContrato} en el periodo publicado.`,
          data: null,
          visualization: null
        };
      }
      throw error;
    }
  }

  if (intentType === 'EXPLAIN_CONTRACT') {
    const idContrato = extraerIdContrato(userQuery) ||
      (menciones && menciones.idContrato) || null;
    if (!idContrato) {
      return {
        text: 'Indique un identificador de contrato SECOP II (formato CO1.PCCNTR. seguido de números).',
        data: null
      };
    }
    const explained = await explainContract(idContrato);
    explained.slots = { idContrato };
    return explained;
  }

  const config = intentConfig[intentType];
  if (!config) {
    return {
      text: 'No pude identificar claramente tu pregunta. ¿Puedes reformularla?',
      data: null
    };
  }

  const result = await analyticalQuery.execute(intentType);
  const data = config.mapRow ? result.rows.map(config.mapRow) : result.rows;
  const text = await narrativeExplainer.explainAnalyticalResult(intentType, result);

  return {
    intent: intentType,
    description: config.description,
    text,
    data,
    visualization: config.visualization || null
  };
}

async function explainContract(idContrato) {
  const context = await ragRetriever.retrieveContractContext(idContrato);
  const explanation = await narrativeExplainer.explainContract(context);

  return {
    intent: 'EXPLAIN_CONTRACT',
    idContrato,
    text: explanation,
    explanation,
    context
  };
}

function fallbackIntent(query) {
  const id = extraerIdContrato(query);
  const q = String(query || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '');
  const hablaAtipico = q.includes('atipic') || q.includes('anomalia') ||
    q.includes('isolation') || q.includes('puntuacion');
  const pideExplicacion = q.includes('por que') || q.includes('porque') ||
    q.includes('caracteristic') || q.includes('significa') ||
    q.includes('puntuacion') || q.includes('que es');

  if (id && (hablaAtipico || pideExplicacion || q.includes('presenta'))) {
    return 'PORQUE_ATIPICO';
  }
  if (id && (q.includes('explic') || q.includes('detalle') || q.includes('contrato'))) {
    return 'EXPLAIN_CONTRACT';
  }
  if (pideExplicacion && hablaAtipico) {
    return 'PORQUE_ATIPICO';
  }

  if (q.includes('modalidad')) {
    return 'MODALIDADES';
  }

  if (
    q.includes('bogota') &&
    (q.includes('contrat') || q.includes('cuanto') || q.includes('valor') || q.includes('invirt'))
  ) {
    return 'BOGOTA_CONTRATACION';
  }

  if (
    q.includes('entidad') &&
    (q.includes('demora') || q.includes('tarda') || q.includes('tiempo'))
  ) {
    return 'EXECUTION_TIME_ENTITY';
  }

  if (
    q.includes('entidad') &&
    (q.includes('mayor') || q.includes('mas') || q.includes('contrat'))
  ) {
    return 'TOP_ENTIDADES';
  }

  if (
    (q.includes('proveedor') || q.includes('empresa') || q.includes('contratista')) &&
    (q.includes('mas') || q.includes('mayor') || q.includes('frecuente') || q.includes('concentra')) &&
    q.includes('contrato')
  ) {
    return 'TOP_PROVIDERS';
  }

  if (
    (q.includes('ciudad') || q.includes('municipio')) &&
    (q.includes('invierte') || q.includes('invirt') || q.includes('gasta') ||
      q.includes('presupuesto') || q.includes('valor') || q.includes('contrat'))
  ) {
    return 'INVESTMENT_CITY';
  }

  if (
    q.includes('contrato') &&
    (q.includes('dura') || q.includes('duracion') || q.includes('largo'))
  ) {
    return 'LONGEST_CONTRACTS';
  }

  if (
    q.includes('top 1') ||
    q.includes('top1') ||
    q.includes('mas atipic') ||
    q.includes('isolation forest') ||
    ((q.includes('atipic') || q.includes('anomalia') || q.includes('comportamiento')) &&
      (q.includes('cuales') || q.includes('contratos') || q.includes('muestr')))
  ) {
    return 'TOP1_IF';
  }

  if (
    q.includes('departamento') &&
    (q.includes('riesgo') || q.includes('anomalia') || q.includes('atipic') || q.includes('score'))
  ) {
    return 'RISK_ANALYSIS';
  }

  return null;
}

module.exports = {
  processUserQuery,
  explainContract,
  extraerIdContrato,
  fallbackIntent,
  normalizarModoRag
};
