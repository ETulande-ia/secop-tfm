const { periodo: PERIODO_PUBLICADO } = require('../config');
const { queryDB } = require('../db/postgres');
const { entero, pesos } = require('./narrative-explainer');

const STOP = new Set([
  'cuantos', 'cuantas', 'cuanto', 'contratos', 'contrato', 'registro', 'registraron',
  'registro', 'tuvo', 'tuvieron', 'utilizo', 'utilizaron', 'fueron', 'tiene',
  'entidad', 'entidades', 'durante', 'septiembre', 'junio', 'colombia', 'publica',
  'contratacion', 'mas', 'mayor', 'esa', 'ese', 'esos', 'las', 'los', 'una', 'del',
  'por', 'con', 'que', 'como', 'cuales', 'cual', 'se', 'de', 'la', 'el', 'en', 'y'
]);

let cacheModalidades = null;

function normalizar(texto) {
  return String(texto || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[().,;:¿?¡!]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function extraerIdContrato(texto) {
  const m = String(texto || '').match(/CO1\.[A-Za-z]+\.\d+/i);
  return m ? m[0].toUpperCase() : null;
}

function pideExplicacionAtipicidad(q) {
  return q.includes('por que') || q.includes('porque') ||
    q.includes('caracteristic') || q.includes('significa') ||
    q.includes('puntuacion') || q.includes('que es') ||
    q.includes('que quiere decir') || q.includes('como se interpreta');
}

function pideListaAtipicos(q) {
  if (q.includes('por que') || q.includes('porque')) return false;
  const lista = q.includes('cuales') || q.includes('lista') || q.includes('muestr') ||
    q.includes('contratos');
  if (pideExplicacionAtipicidad(q) && !lista) return false;
  if (q.includes('top 1') || q.includes('top1') || q.includes('mas atipic')) {
    return true;
  }
  if (q.includes('isolation forest') && lista) return true;
  const atip = q.includes('atipic') || q.includes('anomalia') || q.includes('comportamiento') ||
    /\braros?\b/.test(q) || q.includes('puntuacion') || q.includes('se salen');
  return atip && lista;
}

function pideValor(q) {
  if (q.includes('cuantos') || q.includes('cuantas') || q.includes('numero de contrato')) {
    return false;
  }
  return q.includes('valor') || q.includes('peso') || q.includes('invert') ||
    q.includes('gasto') || q.includes('cop') || q.includes('cuanto') ||
    q.includes('plata') || q.includes('dinero');
}

function periodoFueraDePublicacion(q) {
  const n = typeof q === 'string' && q === q.toLowerCase() ? q : normalizar(q);
  if (n.includes('septiembre') || n.includes('2026-09')) return false;
  return /\b(enero|febrero|marzo|abril|mayo|junio|julio|agosto|octubre|noviembre|diciembre|2025|2024)\b/.test(n) ||
    n.includes('mes pasado') || n.includes('mes anterior') ||
    n.includes('este ano') || n.includes('ano pasado') || n.includes('este anio');
}

function extraerMenciones(query, contexto) {
  const q = normalizar(query);
  const prev = contexto && typeof contexto === 'object' ? contexto : {};
  const out = {
    especial: null,
    operacion: null,
    metrica: 'n_contratos',
    territorio: null,
    entidadTexto: null,
    modalidadTexto: null,
    periodo: PERIODO_PUBLICADO,
    periodoInvalido: false,
    seguimiento: false,
    mencionaModalidad: false,
    territorioDesconocido: null,
    idContrato: extraerIdContrato(query),
    ampliarAtipico: pideExplicacionAtipicidad(q)
  };

  out.metrica = pideValor(q) ? 'valor' : 'n_contratos';

  if (q.includes('esa entidad') || q.includes('esa secretaria') ||
      q.includes('y cuantos') || q.includes('y las ') || q.includes('la misma') ||
      q.includes('y el valor') || q.includes('y cuanto') || q.includes('y el monto')) {
    out.seguimiento = true;
  }
  if (q.includes('ese contrato') || q.includes('este contrato') ||
      (q.includes('ese') && (q.includes('atipic') || q.includes('anomalia') ||
        q.includes('porque') || q.includes('por que') || q.includes('score')))) {
    out.seguimiento = true;
    if (!out.idContrato && prev.idContrato) out.idContrato = prev.idContrato;
  }

  if (q.includes('bogota')) out.territorio = 'bogota';
  const otrasCiudades = [
    'medellin', 'cali', 'barranquilla', 'cartagena', 'bucaramanga',
    'cucuta', 'pereira', 'manizales', 'villavicencio', 'pasto'
  ];
  const otra = otrasCiudades.find(c => q.includes(c));
  if (otra) out.territorioDesconocido = otra;

  if (periodoFueraDePublicacion(q)) out.periodoInvalido = true;
  if (q.includes('septiembre') || q.includes('2026-09')) out.periodo = PERIODO_PUBLICADO;
  out.modalidadTexto = pistaModalidad(q);

  const org = q.match(
    /((?:secretaria|alcaldia|instituto|ministerio|departamento|fondo|subred|empresa|distrito|camara)[a-z\s*]{3,})/
  );
  if (org) {
    out.entidadTexto = org[1].replace(/\s+(durante|en|con|de contratacion).*$/, '').trim();
  }

  if (q.includes('modalidad') || q.includes('distribuy')) {
    out.mencionaModalidad = true;
    if (!/\bde contratacion directa\b/.test(q) && !q.includes('minima cuantia')) {
      out.operacion = 'distribucion';
    }
  }

  if (q.includes('entidad') && (q.includes('mayor') || q.includes('mas') || q.includes('top'))) {
    out.operacion = 'ranking';
    if (q.includes('mas contratos') || q.includes('con mas') || q.includes('mas contrato')) {
      out.metrica = 'n_contratos';
    } else {
      out.metrica = 'valor';
    }
  }

  if (!out.operacion && /\bquien(es)?\b/.test(q) &&
      (q.includes('mas contrato') || q.includes('hizo mas') || q.includes('hicieron mas')) &&
      !q.includes('dieron') && !q.includes('gano') && !q.includes('proveedor') &&
      !q.includes('contratista')) {
    out.operacion = 'ranking';
    out.metrica = (q.includes('mas contrato') || q.includes('hizo mas') || q.includes('hicieron mas')) &&
      !q.includes('valor') && !q.includes('plata') && !q.includes('gasto')
      ? 'n_contratos'
      : (pideValor(q) ? 'valor' : 'n_contratos');
  }

  if (!out.operacion && (q.includes('cuantos') || q.includes('cuantas') ||
      q.includes('cuanto') || q.includes('cuanta'))) {
    out.operacion = 'contar';
  }
  if (!out.operacion && out.metrica === 'valor' &&
      (q.includes('valor total') || q.includes('valor contratado') || q.includes('total contratado'))) {
    out.operacion = 'contar';
  }
  if (!out.operacion && out.territorio) out.operacion = 'contar';

  const hablaAtipico = q.includes('atipic') || q.includes('anomalia') ||
    q.includes('isolation') || q.includes('puntuacion');

  if (out.idContrato && (hablaAtipico || q.includes('por que') || q.includes('porque') ||
      q.includes('presenta') || q.includes('identific'))) {
    out.especial = 'PORQUE_ATIPICO';
  } else if (out.idContrato && (q.includes('explic') || q.includes('detalle') || q.includes('contrato'))) {
    out.especial = 'EXPLAIN_CONTRACT';
  } else if (pideListaAtipicos(q)) {
    out.especial = 'TOP1_IF';
  } else if (pideExplicacionAtipicidad(q) && hablaAtipico) {
    out.especial = 'PORQUE_ATIPICO';
  } else if ((q.includes('modelo') || q.includes('isolation')) &&
      (q.includes('significa') || q.includes('marque') || q.includes('detect') || q.includes('que es')) &&
      (q.includes('contrato') || q.includes('anomal') || q.includes('atipic') || q.includes('isolation'))) {
    out.especial = 'PORQUE_ATIPICO';
  } else if (out.seguimiento && (q.includes('ese contrato') || q.includes('este contrato'))) {
    out.especial = 'PORQUE_ATIPICO';
  } else if (q.includes('departamento') && (q.includes('score') || q.includes('riesgo') || q.includes('atipic'))) {
    out.especial = 'RISK_ANALYSIS';
  } else if ((q.includes('proveedor') || q.includes('contratista')) &&
      (q.includes('mas') || q.includes('mayor'))) {
    out.especial = 'TOP_PROVIDERS';
  } else if (q.includes('entidad') && (q.includes('demora') || q.includes('tarda') || q.includes('tiempo'))) {
    out.especial = 'EXECUTION_TIME_ENTITY';
  } else if (q.includes('contrato') &&
      (q.includes('duracion') || q.includes('largo') || /\bdura\b/.test(q)) &&
      !q.includes('cuantos') && !q.includes('cuanto') && !out.idContrato) {
    out.especial = 'LONGEST_CONTRACTS';
  } else if ((q.includes('ciudad') || q.includes('municipio')) &&
      (q.includes('invirt') || q.includes('gasta') || q.includes('valor') || q.includes('mas'))) {
    out.especial = 'INVESTMENT_CITY';
  }

  return out;
}

function fusionar(menciones, contexto) {
  const prev = contexto && typeof contexto === 'object' ? contexto : {};
  const slots = {
    operacion: menciones.operacion,
    metrica: menciones.metrica,
    territorio: menciones.territorio,
    entidadTexto: menciones.entidadTexto,
    modalidadTexto: menciones.modalidadTexto,
    periodo: menciones.periodo,
    periodoInvalido: menciones.periodoInvalido,
    mencionaModalidad: menciones.mencionaModalidad,
    seguimiento: menciones.seguimiento,
    territorioDesconocido: menciones.territorioDesconocido,
    entidad: null,
    modalidad: null
  };

  if (menciones.seguimiento) {
    if (!slots.territorio) slots.territorio = prev.territorio || null;
    if (!slots.entidadTexto) slots.entidad = prev.entidad || null;
    if (!slots.operacion) {
      slots.operacion = prev.operacion === 'ranking' ? 'ranking' : 'contar';
    }
  }
  return slots;
}

function pistaModalidad(q) {
  const n = normalizar(q);
  if (n.includes('minima cuantia')) return 'minima cuantia';
  if (n.includes('contratacion directa') && n.includes('ofertas')) return 'contratacion directa (con ofertas)';
  if (n.includes('contratacion directa')) return 'contratacion directa';
  if (n.includes('regimen especial') && n.includes('ofertas')) return 'contratacion regimen especial (con ofertas)';
  if (n.includes('regimen especial')) return 'contratacion regimen especial';
  if (n.includes('licitacion publica') && n.includes('obra')) return 'licitacion publica obra publica';
  if (n.includes('licitacion')) return 'licitacion publica';
  if (n.includes('subasta inversa')) return 'seleccion abreviada subasta inversa';
  if (n.includes('menor cuantia')) return 'seleccion abreviada de menor cuantia';
  if (n.includes('concurso de meritos')) return 'concurso de meritos abierto';
  return null;
}

async function listaModalidades(periodo) {
  if (cacheModalidades) return cacheModalidades;
  const rows = await queryDB(
    `
    SELECT DISTINCT modalidad_de_contratacion AS m
    FROM tfm.contrato
    WHERE periodo = $1 AND modalidad_de_contratacion IS NOT NULL
    `,
    [periodo]
  );
  cacheModalidades = rows.map(r => r.m);
  return cacheModalidades;
}

function elegirModalidad(pista, lista) {
  const np = normalizar(pista);
  const scored = lista
    .map((m) => {
      const nm = normalizar(m);
      if (nm === np) return { m, pts: 100 };
      if (np.includes(nm) || nm.includes(np)) {
        const extra = Math.abs(nm.length - np.length);
        return { m, pts: 80 - extra };
      }
      return null;
    })
    .filter(Boolean)
    .sort((a, b) => b.pts - a.pts);
  if (!scored.length) return null;
  if (!np.includes('ofertas')) {
    const sinOfertas = scored.filter(s => !normalizar(s.m).includes('ofertas'));
    if (sinOfertas.length) return sinOfertas[0].m;
  }
  return scored[0].m;
}

async function resolverEntidad(texto, periodo) {
  const n = normalizar(texto);
  const tokens = n.split(' ').filter(t => t.length > 3 && !STOP.has(t));
  if (!tokens.length) return { error: 'No identifiqué el nombre de la entidad.' };
  const like = `%${tokens.join('%')}%`;
  const rows = await queryDB(
    `
    SELECT nombre_entidad AS entidad, COUNT(*) AS n
    FROM tfm.contrato
    WHERE periodo = $1
      AND translate(lower(nombre_entidad),
        'áéíóúüñàèìòùÁÉÍÓÚÜÑ',
        'aeiouunaeiouaeiouun') LIKE $2
    GROUP BY 1
    ORDER BY n DESC
    LIMIT 8
    `,
    [periodo, like]
  );
  const candidatos = rows.filter((r) => {
    const ne = normalizar(r.entidad);
    return tokens.every(t => ne.includes(t));
  });
  if (candidatos.length === 1) return { entidad: candidatos[0].entidad };
  if (candidatos.length > 1) {
    const nombres = candidatos.slice(0, 5).map(c => c.entidad).join('; ');
    return {
      error: `Hay varias entidades que coinciden. Precise el nombre: ${nombres}.`
    };
  }
  return { error: `No encontré la entidad «${texto.trim()}» en el periodo ${periodo}.` };
}

async function resolver(slots, textoOriginal) {
  if (slots.periodoInvalido) {
    return {
      tipo: 'error',
      mensaje: 'Este prototipo solo puede consultar septiembre de 2026. Precise si desea esa cifra de septiembre de 2026; no uso otro periodo en silencio.'
    };
  }
  if (slots.territorioDesconocido) {
    return {
      tipo: 'error',
      mensaje: 'No puedo filtrar por ese municipio o ciudad. En este prototipo solo está disponible Bogotá (sede de la entidad).'
    };
  }
  const q = normalizar(textoOriginal);
  if (
    (q.includes('esa entidad') || q.includes('esa secretaria')) &&
    !slots.entidad && !slots.entidadTexto
  ) {
    return {
      tipo: 'error',
      mensaje: 'No tengo una entidad de la pregunta anterior. Indique el nombre de la entidad.'
    };
  }
  if (slots.seguimiento && !slots.entidad && !slots.entidadTexto && !slots.territorio) {
    return {
      tipo: 'error',
      mensaje: 'No tengo una consulta anterior en esta conversación. Indique el nombre de la entidad o el territorio.'
    };
  }
  slots.periodo = PERIODO_PUBLICADO;
  const pista = pistaModalidad(q);
  if (pista) {
    const lista = await listaModalidades(slots.periodo);
    const mod = elegirModalidad(pista, lista);
    if (!mod) {
      return {
        tipo: 'error',
        mensaje: 'No identifiqué esa modalidad de contratación. Para no mostrar una cifra incorrecta, no consulto otro recuento.'
      };
    }
    slots.modalidad = mod;
    if (slots.operacion === 'distribucion' && pista) {
      slots.operacion = 'contar';
    }
  } else if (
    /\b(directa|cuantia|licitacion|regimen especial|subasta|meritos|concesion|convenio)\b/.test(q) &&
    slots.operacion !== 'distribucion'
  ) {
    return {
      tipo: 'error',
      mensaje: 'No identifiqué esa modalidad de contratación. Para no mostrar una cifra incorrecta, no consulto otro recuento.'
    };
  }

  if (slots.entidadTexto) {
    const r = await resolverEntidad(slots.entidadTexto, slots.periodo);
    if (r.error) return { tipo: 'error', mensaje: r.error };
    slots.entidad = r.entidad;
  }

  if (!slots.operacion) {
    return {
      tipo: 'error',
      mensaje: 'No identifiqué una consulta analítica que pueda ejecutar con los filtros indicados.'
    };
  }

  if (slots.operacion === 'distribucion') {
    slots.modalidad = null;
  }

  return { tipo: 'ok', slots };
}

function refFiltros(slots) {
  const partes = [`periodo ${slots.periodo}`];
  if (slots.territorio === 'bogota') {
    partes.push('sede de la entidad en Bogotá, no necesariamente el lugar de ejecución');
  }
  if (slots.entidad) partes.push(`entidad ${slots.entidad}`);
  if (slots.modalidad) partes.push(`modalidad ${slots.modalidad}`);
  return partes.join('; ');
}

function textoNlq(slots, result) {
  const ref = refFiltros(slots);
  const rows = result.rows || [];

  if (slots.operacion === 'contar') {
    const r = rows[0] || {};
    if (slots.metrica === 'valor') {
      return `El valor contratado es ${pesos(r.valor)} (${ref}).`;
    }
    return `Se registraron ${entero(r.n)} contratos (${ref}).`;
  }

  if (slots.operacion === 'ranking') {
    const porValor = slots.metrica === 'valor';
    const lineas = rows.map((r, i) => porValor
      ? `${i + 1}. ${r.entidad}: ${pesos(r.total_contratado)}.`
      : `${i + 1}. ${r.entidad}: ${entero(r.num_contratos)} contratos.`
    );
    return [`Entidades ordenadas por ${porValor ? 'valor contratado' : 'número de contratos'} (${ref}).`, ...lineas].join('\n');
  }

  const lineas = rows.map(r =>
    `${r.modalidad}: ${entero(r.n)} contratos (${entero(r.pct)} %).`
  );
  return [`Modalidades (${ref}).`, ...lineas].join('\n');
}

function sufijoFiltros(slots) {
  const partes = [];
  if (slots.territorio === 'bogota') partes.push('Bogotá');
  if (slots.entidad) {
    const nombre = String(slots.entidad).replace(/^\(|\)$/g, '').trim();
    partes.push(nombre.length > 48 ? `${nombre.slice(0, 47)}…` : nombre);
  }
  return partes.length ? ` — ${partes.join(', ')}` : '';
}

function visualizacionNlq(slots) {
  const ambito = sufijoFiltros(slots);
  if (slots.operacion === 'ranking') {
    return {
      type: 'bar',
      x: 'entidad',
      y: slots.metrica === 'valor' ? 'total_contratado' : 'num_contratos',
      indexAxis: 'y',
      title: slots.metrica === 'valor'
        ? `Valor contratado por entidad (COP)${ambito}`
        : `Número de contratos por entidad${ambito}`
    };
  }
  if (slots.operacion === 'distribucion') {
    return {
      type: 'bar',
      x: 'modalidad',
      y: 'n',
      indexAxis: 'y',
      title: `Número de contratos por modalidad${ambito}`
    };
  }
  return null;
}

function mapearFilas(slots, rows) {
  if (slots.operacion === 'ranking') {
    return rows.map((r) => {
      const fila = { entidad: String(r.entidad || '').slice(0, 80) };
      if (slots.metrica === 'valor') fila.total_contratado = Number(r.total_contratado);
      else fila.num_contratos = Number(r.num_contratos);
      return fila;
    });
  }
  if (slots.operacion === 'distribucion') {
    return rows.map(r => ({
      modalidad: r.modalidad,
      n: Number(r.n),
      pct: Number(r.pct)
    }));
  }
  return rows.map((r) => (
    slots.metrica === 'valor' ? { valor: Number(r.valor) } : { n: Number(r.n) }
  ));
}

module.exports = {
  extraerIdContrato,
  extraerMenciones,
  fusionar,
  resolver,
  pistaModalidad,
  elegirModalidad,
  pideExplicacionAtipicidad,
  periodoFueraDePublicacion,
  textoNlq,
  visualizacionNlq,
  mapearFilas,
  normalizar
};
