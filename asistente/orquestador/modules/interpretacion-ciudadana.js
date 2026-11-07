/**
 * Validación previa a ejecutar una consulta.
 * No usa IDs EC. No genera SQL. No afirma vigencia normativa.
 */
const { extraerIdContrato, normalizar, pistaModalidad, periodoFueraDePublicacion } = require('./nlq');

function aclarar(mensaje, regla) {
  return { accion: 'aclarar', mensaje, regla };
}

function rechazar(mensaje, regla) {
  return { accion: 'rechazar', mensaje, regla };
}

function ejecutar() {
  return { accion: 'ejecutar' };
}

function hablaModelo(q) {
  return q.includes('isolation') || q.includes('atipic') || q.includes('anomalia') ||
    q.includes('puntuacion') || q.includes('score') ||
    (q.includes('modelo') && (q.includes('contrato') || q.includes('anomal') || q.includes('marque')));
}

function acusacion(q) {
  return /\b(fraude|fraudulent|corruptos?|corrupcion|trampa|delito|ilegales?)\b/.test(q) ||
    q.includes('se robo') || q.includes('robo la plata') || q.includes('se robaron');
}

function preguntaAnalitica(q) {
  if (q.includes('cuantos contratos') || q.includes('cuantas contratos')) return true;
  if (q.includes('cuanta plata') || q.includes('cuanto dinero') || q.includes('cuanto se contrato')) {
    return true;
  }
  if ((q.includes('cuales') || q.includes('lista') || q.includes('muestr')) &&
      (q.includes('contrato') || q.includes('atipic') || q.includes('proveedor'))) {
    return true;
  }
  return false;
}

function preguntaModeloC1(q) {
  if (q.includes('n_estimators') || q.includes('contamination')) return true;
  if (q.includes('matriz c1') || (/\bc1\b/.test(q) && (q.includes('variable') || q.includes('incluye') || q.includes('plazo')))) {
    return true;
  }
  if (q.includes('isolation forest') &&
      (q.includes('que es') || q.includes('que significa') || q.includes('arbol') ||
        q.includes('variable') || q.includes('irregular') || q.includes('puntuacion alta'))) {
    return true;
  }
  return false;
}

function definicionDocumental(q) {
  if (preguntaAnalitica(q) && !preguntaModeloC1(q)) return false;
  if (preguntaModeloC1(q)) return true;
  const def = q.includes('que es') || q.includes('que significa') ||
    q.includes('que quiere decir') || q.includes('que diferencia') ||
    q.includes('que requisitos') || q.includes('como se determina') ||
    q.includes('deben acreditar') || q.includes('hay que presentar') ||
    q.includes('estan obligadas') || q.includes('acreditar el rup') ||
    q.includes('acreditar rup') || q.includes('diccionario de datos') ||
    q.includes('sancionatorio') || q.includes('sisben') ||
    q.includes('plena prueba');
  if (!def && q.includes('minima cuantia') &&
      (q.includes('valor') || q.includes('peso') || q.includes('rup') ||
        q.includes('oferente') || q.includes('garant'))) {
    return true;
  }
  if (!def) return false;
  return q.includes('rup') || q.includes('minima cuantia') || q.includes('requisito') ||
    q.includes('habilitante') || q.includes('contratacion directa') ||
    q.includes('licitacion') || q.includes('contratar con el estado') ||
    q.includes('proceso de un contrato') || q.includes('un proceso de un contrato') ||
    q.includes('diccionario') || q.includes('sancionatorio') || q.includes('sisben') ||
    q.includes('isolation') || q.includes('c1') || q.includes('manual');
}

function coloquialModalidad(q) {
  return q.includes('a dedo') || q.includes('sin concurso') || q.includes('a dedazo');
}

function tamanoAmbiguo(q) {
  if (q.includes('atipic') || /\braros?\b/.test(q) || q.includes('anomalia')) return false;
  if (/\b\d/.test(q) || q.includes('smlmv') || q.includes('minima cuantia')) return false;
  return /\bpequenos?\b/.test(q) || /\bgrandes?\b/.test(q);
}

function gastoEjecutado(q) {
  return q.includes('realmente') || q.includes('ejecutado') || q.includes('pagado') ||
    q.includes('desembols') || q.includes('girado');
}

function ciudadVaga(q) {
  if (q.includes('bogota')) return false;
  if (/\bque ciudad\b/.test(q) && (q.includes('invirt') || q.includes('gasta') || q.includes('invert'))) {
    return false;
  }
  return /\bla ciudad\b/.test(q) || q.includes('de la ciudad') || q.includes('en la ciudad');
}

function deixisSinContexto(q, prev, id) {
  const hayPrev = Boolean(prev && (prev.idContrato || prev.entidad || prev.territorio || prev.operacion));
  if (id || (prev && prev.idContrato)) return false;
  if (q.includes('ese contrato') || q.includes('este contrato')) return true;
  if (!hayPrev && (/\bsolo los\b/.test(q) || q.includes('solo de bogota') || q.includes('solo los de'))) {
    return true;
  }
  return false;
}

function listadoPorModalidad(q) {
  if (q.includes('cuantos') || q.includes('cuantas') || q.includes('porcentaje')) return false;
  if (q.includes('atipic') || /\braros?\b/.test(q) || q.includes('anomalia') || q.includes('puntuacion')) {
    return false;
  }
  if (!pistaModalidad(q)) return false;
  return q.includes('cuales se hicieron') || q.includes('que contratos') ||
    (q.includes('cuales') && !q.includes('modalidad') && !q.includes('entidad'));
}

function listadoPorEntidad(q) {
  if (q.includes('cuantos') || q.includes('cuantas') || q.includes('valor') || q.includes('plata')) {
    return false;
  }
  if (q.includes('atipic') || /\braros?\b/.test(q)) return false;
  return /que contratos (hizo|tiene|firmo|registro)/.test(q);
}

function rankingContratosValor(q) {
  if (q.includes('entidad') || q.includes('proveedor') || q.includes('contratista')) return false;
  return (q.includes('mas caro') || q.includes('mayor valor') || q.includes('mas caros')) &&
    (q.includes('contrato') || q.includes('cuales'));
}

function rankingSinMetrica(q) {
  if (!q.includes('entidad')) return false;
  if (q.includes('contrato') || q.includes('valor') || q.includes('gasto') ||
      q.includes('plata') || q.includes('dinero') || q.includes('contrat')) {
    return false;
  }
  return q.includes('tiene mas') || (q.includes('tiene') && q.includes('mas'));
}

function calidadDatos(q) {
  return q.includes('sin departamento') || q.includes('no definido') ||
    q.includes('registros repetidos') || q.includes('sin valor registrado') ||
    q.includes('duplicado') || q.includes('calidad de dato');
}

function interpretarCiudadano(query, contexto) {
  const q = normalizar(query);
  const prev = contexto && typeof contexto === 'object' ? contexto : {};
  const id = extraerIdContrato(query);

  if (acusacion(q)) {
    return rechazar(
      'No puedo establecer delitos ni irregularidades. El Isolation Forest solo marca atipicidad estadística, no fraude ni corrupción.',
      'acusacion'
    );
  }
  if (definicionDocumental(q)) {
    return { accion: 'documental', regla: 'documental' };
  }
  if (coloquialModalidad(q)) {
    return aclarar(
      '«A dedo» o «sin concurso» no se traducen solos a una modalidad ni a una irregularidad. Precise si se refiere a contratación directa u otra modalidad publicada.',
      'coloquial_modalidad'
    );
  }
  if (tamanoAmbiguo(q)) {
    return aclarar(
      '«Pequeños» o «grandes» no tienen umbral en este prototipo. Indique un valor, o si se refiere a mínima cuantía u otra modalidad.',
      'tamano'
    );
  }
  if (gastoEjecutado(q)) {
    return aclarar(
      'Solo puedo consultar el valor contratado publicado, no el dinero ejecutado o pagado. Precise si desea el valor contratado de septiembre de 2026.',
      'gasto_ejecutado'
    );
  }
  if (periodoFueraDePublicacion(q)) {
    return aclarar(
      'Este prototipo solo puede consultar septiembre de 2026. Precise si desea esa cifra de septiembre de 2026; no uso otro periodo en silencio.',
      'periodo'
    );
  }
  if (ciudadVaga(q)) {
    return aclarar(
      'No identifiqué el municipio. En este prototipo el filtro territorial disponible es Bogotá (sede de la entidad). Indique el municipio o si desea Bogotá.',
      'ciudad'
    );
  }
  if (deixisSinContexto(q, prev, id)) {
    return aclarar(
      'Falta el contrato o el recorte de la pregunta anterior. Indique un identificador CO1.PCCNTR. o repita la consulta completa.',
      'seguimiento'
    );
  }
  if (listadoPorModalidad(q)) {
    return aclarar(
      'No listo contratos individuales por modalidad. Puedo contar esa modalidad o mostrar la distribución. Indique si desea el recuento.',
      'listado_modalidad'
    );
  }
  if (listadoPorEntidad(q)) {
    return aclarar(
      'No listo los contratos de una entidad. Puedo contarlos o sumar su valor. Indique si desea el número o el valor contratado.',
      'listado_entidad'
    );
  }
  if (rankingContratosValor(q)) {
    return aclarar(
      'No ordeno contratos individuales por valor. Puedo ordenar entidades o consultar el valor contratado. Indique cuál de esas consultas desea.',
      'ranking_contratos'
    );
  }
  if (rankingSinMetrica(q)) {
    return aclarar(
      'No está dicha la métrica. Precise si «más» es número de contratos o valor contratado.',
      'metrica_ambigua'
    );
  }
  if (calidadDatos(q)) {
    return rechazar(
      'No consulto calidad de datos (nulos, duplicados o «No Definido») desde el chat. Esa revisión está en el EDA, no en una consulta analítica.',
      'calidad'
    );
  }
  return ejecutar();
}

module.exports = {
  interpretarCiudadano,
  acusacion,
  definicionDocumental,
  coloquialModalidad,
  periodoFueraDePublicacion,
  preguntaModeloC1
};
