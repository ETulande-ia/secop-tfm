const { OpenAI } = require('openai');

function cliente() {
  return new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
}

const REGLAS = `
Eres un asistente de contratación pública en Colombia.
Explica los resultados con claridad para un ciudadano no técnico.
No infieras causas ni irregularidades.
No hagas juicios de valor.
Si hay score Isolation Forest: mayor valor = más atípico respecto al modelo C1; eso no significa fraude ni ilegalidad.
Usa pesos colombianos cuando haya valores monetarios.
`;

async function completar(prompt) {
  const response = await cliente().chat.completions.create({
    model: 'gpt-4o-mini',
    messages: [{ role: 'user', content: prompt }],
    temperature: 0.2
  });
  return response.choices[0].message.content;
}

function entero(n) {
  const x = Number(n);
  if (!Number.isFinite(x)) return 'sin dato';
  return new Intl.NumberFormat('es-CO').format(x);
}

function pesos(n) {
  const x = Number(n);
  if (!Number.isFinite(x)) return 'sin dato';
  return `${new Intl.NumberFormat('es-CO', { maximumFractionDigits: 0 }).format(x)} COP`;
}

function siNo(v) {
  if (v === true || v === 't' || v === 'true') return 'sí';
  if (v === false || v === 'f' || v === 'false') return 'no';
  return 'sin dato';
}

function textoFijo(intentType, data) {
  const rows = (data && data.rows) || [];

  if (intentType === 'BOGOTA_CONTRATACION') {
    const r = rows[0] || {};
    return `Se registraron ${entero(r.n)} contratos (periodo 2026-09; sede de la entidad en Bogotá, no necesariamente el lugar de ejecución).`;
  }

  if (intentType === 'TOP_ENTIDADES') {
    const lineas = rows.slice(0, 10).map((r, i) =>
      `${i + 1}. ${r.entidad}: ${pesos(r.total_contratado)}.`
    );
    return ['Entidades ordenadas por valor contratado (periodo 2026-09).', ...lineas].join('\n');
  }

  if (intentType === 'MODALIDADES') {
    const lineas = rows.map((r) =>
      `${r.modalidad}: ${entero(r.n)} contratos (${entero(r.pct)} %).`
    );
    return [
      'Modalidades de contratación en el periodo 2026-09:',
      ...lineas
    ].join('\n');
  }

  if (intentType === 'TOP1_IF') {
    const lineas = rows.slice(0, 10).map((r) =>
      `Puesto ${entero(r.rank_if)}: ${r.id_contrato} — ${r.nombre_entidad}.`
    );
    return [
      'Contratos del top 1 % Isolation Forest (c1_if_v1, periodo 2026-09). No es irregularidad comprobada.',
      ...lineas
    ].join('\n');
  }

  return null;
}

function metodoAtipico(universo) {
  const nAptos = universo && universo.n_aptos != null ? entero(universo.n_aptos) : 'sin dato';
  const nTop1 = universo && universo.n_top1 != null ? entero(universo.n_top1) : 'sin dato';
  return [
    'Isolation Forest, en la versión publicada c1_if_v1 (periodo 2026-09), identifica contratos estadísticamente atípicos respecto al modelo C1.',
    'C1 usa el valor del contrato (transformado con log1p), su comparación con la modalidad y el grupo de modalidad. No usa plazo ni conteo por entidad.',
    'Una puntuación alta no es una irregularidad comprobada ni una probabilidad de fraude. El modelo no demuestra ilegalidad.',
    `El universo puntuado son ${nAptos} contratos aptos; ${nTop1} están en el top 1 %.`
  ].join(' ');
}

function explicarPorqueAtipico(context, idContrato, universo, ampliar = true) {
  const general = metodoAtipico(universo);
  const nAptos = universo && universo.n_aptos != null ? entero(universo.n_aptos) : 'sin dato';

  if (!idContrato) {
    if (!ampliar) {
      return 'Indique un identificador de contrato SECOP II (formato CO1.PCCNTR. seguido de números).';
    }
    return `${general} Indique un identificador de contrato SECOP II para ver el score y el puesto de ese contrato.`;
  }

  if (!context || !context.contrato) {
    return `No encontré el contrato ${idContrato} en el periodo publicado.`;
  }

  const c = context.contrato;
  const s = context.puntuacion_if;
  const ex = context.exclusion;

  if (ex && ex.motivo_exclusion) {
    const hecho = `El contrato ${c.id_contrato} no tiene score Isolation Forest: fue excluido del modelo (${ex.motivo_exclusion}).`;
    return ampliar ? `${general} ${hecho}` : hecho;
  }

  if (!s) {
    const hecho = `El contrato ${c.id_contrato} no tiene score publicado en c1_if_v1.`;
    return ampliar ? `${general} ${hecho}` : hecho;
  }

  if (!ampliar) {
    return [
      `Contrato ${c.id_contrato}. Entidad: ${c.entidad || 'sin dato'}.`,
      `Score Isolation Forest: ${Number(s.score_if).toFixed(6)} (puesto ${entero(s.rank_if)}).`,
      `Top 1 %: ${siNo(s.top1_if)}.`,
      'Eso no es una irregularidad comprobada.'
    ].join(' ');
  }

  return [
    general,
    `Contrato ${c.id_contrato}. Entidad: ${c.entidad || 'sin dato'}. Modalidad: ${c.modalidad_de_contratacion || 'sin dato'}. Valor: ${pesos(c.valor_del_contrato)}.`,
    `Score Isolation Forest: ${Number(s.score_if).toFixed(6)} (puesto ${entero(s.rank_if)} de ${nAptos} contratos puntuados).`,
    `Top 5 %: ${siNo(s.top5_if)}. Valor por encima del percentil 99 de su grupo de modalidad: ${siNo(s.flag_p99_modalidad)}.`,
    `Top 1 % por valor (logaritmo): ${siNo(s.top1_logvalor)}. Grupo de modalidad: ${s.modalidad_grupo || 'sin dato'}.`,
    'Estas cifras son las publicadas. No se infiere una causa concreta distinta de las variables de C1 (valor y modalidad).'
  ].join(' ');
}

async function explainAnalyticalResult(intentType, data) {
  const fijo = textoFijo(intentType, data);
  if (fijo) return fijo;

  return completar(`
${REGLAS}

Tipo de análisis: ${intentType}

Resultados:
${JSON.stringify(data, null, 2)}
`);
}

async function explainContract(context) {
  return completar(`
${REGLAS}

Explica este contrato con los datos recuperados. Si no tiene score, dilo (puede estar excluido del modelo por valor cero o extremo).

Datos:
${JSON.stringify(context, null, 2)}
`);
}

module.exports = {
  explainAnalyticalResult,
  explainContract,
  explicarPorqueAtipico,
  entero,
  pesos
};
