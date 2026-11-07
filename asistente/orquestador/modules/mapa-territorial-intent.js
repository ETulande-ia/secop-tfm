const { ANIO_POBLACION, NOTA, validarPeriodo } = require('./territorial');
const { periodo: PERIODO } = require('../config');

const INDICADORES = Object.freeze({
  n_contratos: 'Número de contratos',
  valor_total: 'Valor total contratado',
  poblacion_total: 'Población total',
  total_hombres: 'Total de hombres',
  total_mujeres: 'Total de mujeres',
  contratos_por_100k: 'Contratos por cada 100.000 habitantes',
  valor_por_habitante: 'Valor contratado por habitante'
});

const CODIGOS_DANE = Object.freeze({
  '05': 'Antioquia',
  '08': 'Atlántico',
  '11': 'Bogotá D.C.',
  '13': 'Bolívar',
  '15': 'Boyacá',
  '17': 'Caldas',
  '18': 'Caquetá',
  '19': 'Cauca',
  '20': 'Cesar',
  '23': 'Córdoba',
  '25': 'Cundinamarca',
  '27': 'Chocó',
  '41': 'Huila',
  '44': 'La Guajira',
  '47': 'Magdalena',
  '50': 'Meta',
  '52': 'Nariño',
  '54': 'Norte de Santander',
  '63': 'Quindío',
  '66': 'Risaralda',
  '68': 'Santander',
  '70': 'Sucre',
  '73': 'Tolima',
  '76': 'Valle del Cauca',
  '81': 'Arauca',
  '85': 'Casanare',
  '86': 'Putumayo',
  '88': 'Archipiélago de San Andrés',
  '91': 'Amazonas',
  '94': 'Guainía',
  '95': 'Guaviare',
  '97': 'Vaupés',
  '99': 'Vichada'
});

const MENSAJE_INDICADOR =
  'Indique el indicador del mapa: número de contratos, valor contratado, población, hombres, mujeres, contratos por 100.000 habitantes o valor por habitante.';

function aclarar(mensaje) {
  return { aclarar: true, mensaje };
}

function periodoPublicadoValido() {
  try {
    validarPeriodo(PERIODO);
    return true;
  } catch (_) {
    return false;
  }
}

function codigoDaneNormalizado(valor) {
  if (valor == null || valor === '') return null;
  const codigo = String(valor).trim().padStart(2, '0');
  return Object.prototype.hasOwnProperty.call(CODIGOS_DANE, codigo) ? codigo : null;
}

function validarLecturaMapa(lectura) {
  if (!lectura || lectura.intent !== 'MAPA_TERRITORIAL') {
    return aclarar('No pude identificar una consulta territorial.');
  }
  if (!periodoPublicadoValido()) {
    return aclarar('El periodo publicado no tiene un formato válido. No puedo mostrar el mapa.');
  }
  const indicador = lectura.indicador;
  if (indicador == null || indicador === '') {
    return aclarar(MENSAJE_INDICADOR);
  }
  if (!Object.prototype.hasOwnProperty.call(INDICADORES, indicador)) {
    return aclarar(
      'El indicador solicitado no está disponible. ' + MENSAJE_INDICADOR
    );
  }
  let codigo_dane = null;
  if (lectura.codigo_dane != null && lectura.codigo_dane !== '') {
    codigo_dane = codigoDaneNormalizado(lectura.codigo_dane);
    if (!codigo_dane) {
      return aclarar(
        'No reconocí el departamento indicado. Puede nombrar uno de los 32 departamentos o Bogotá D.C., o pedir el mapa nacional.'
      );
    }
  }
  return { indicador, codigo_dane };
}

function textoMapa(lectura) {
  const titulo = INDICADORES[lectura.indicador] || lectura.indicador;
  const nombre = lectura.codigo_dane ? CODIGOS_DANE[lectura.codigo_dane] : null;
  const foco = nombre ? ` Quedó marcado ${nombre}.` : '';
  return `El mapa muestra ${titulo.toLowerCase()} por departamento. ${NOTA}${foco} Puede pulsar un departamento o cambiar el indicador.`;
}

function respuestaMapa(lectura) {
  const indicador = lectura.indicador;
  return {
    intent: 'MAPA_TERRITORIAL',
    description: 'Mapa temático por departamento (SECOP II y DANE)',
    text: textoMapa(lectura),
    data: null,
    visualization: {
      type: 'mapa_territorial',
      indicador,
      titulo: INDICADORES[indicador],
      periodo: PERIODO,
      anio_poblacion: ANIO_POBLACION,
      codigo_dane: lectura.codigo_dane || null
    }
  };
}

module.exports = {
  INDICADORES,
  CODIGOS_DANE,
  MENSAJE_INDICADOR,
  validarLecturaMapa,
  respuestaMapa
};
