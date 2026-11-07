const OpenAI = require('openai');

const INTENTS = Object.freeze([
  'BOGOTA_CONTRATACION',
  'TOP_ENTIDADES',
  'MODALIDADES',
  'TOP1_IF',
  'PORQUE_ATIPICO',
  'INVESTMENT_CITY',
  'EXECUTION_TIME_ENTITY',
  'LONGEST_CONTRACTS',
  'RISK_ANALYSIS',
  'TOP_PROVIDERS',
  'EXPLAIN_CONTRACT',
  'MAPA_TERRITORIAL',
  'UNKNOWN'
]);

const INTENTS_SET = new Set(INTENTS);

function cliente() {
  return new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
}

function vacio() {
  return { intent: 'UNKNOWN', indicador: null, codigo_dane: null };
}

function textoONulo(valor) {
  if (valor == null || valor === '') return null;
  const t = String(valor).trim();
  if (!t || t === 'null' || t === 'none' || t === 'undefined') return null;
  return t;
}

function parsearRespuesta(texto) {
  const crudo = String(texto || '').trim();
  let obj = null;
  const cerca = crudo.match(/\{[\s\S]*\}/);
  if (cerca) {
    try {
      obj = JSON.parse(cerca[0]);
    } catch (_) {
      obj = null;
    }
  }
  if (!obj) {
    const etiqueta = crudo.split(/\s+/)[0];
    obj = { intent: etiqueta, indicador: null, codigo_dane: null };
  }
  const intent = INTENTS_SET.has(obj.intent) ? obj.intent : 'UNKNOWN';
  if (intent !== 'MAPA_TERRITORIAL') {
    return { intent, indicador: null, codigo_dane: null };
  }
  return {
    intent,
    indicador: textoONulo(obj.indicador),
    codigo_dane: textoONulo(obj.codigo_dane)
  };
}

function promptClasificacion(userQuery) {
  const pregunta = String(userQuery || '').replace(/"/g, "'");
  return `
Eres un clasificador de intenciones para un asistente de contratación pública en Colombia (SECOP II).

Clasifica la pregunta con exactamente una etiqueta. Responde SOLO un JSON:
{"intent":"ETIQUETA","indicador":null,"codigo_dane":null}

Etiquetas:

1. BOGOTA_CONTRATACION
   Total o valor de contratación con sede de la entidad en Bogotá, no un mapa nacional.
   Ejemplo: ¿Cuántos contratos hay en Bogotá?

2. TOP_ENTIDADES
   Entidades contratantes del Estado con mayor contratación.
   NO uses TOP_PROVIDERS si habla de entidades.

3. MODALIDADES
   Modalidades de contratación (contratación directa, mínima cuantía, etc.).

4. TOP1_IF
   Lista de contratos atípicos (top 1 % Isolation Forest).

5. PORQUE_ATIPICO
   Por qué un contrato se considera atípico. Si hay identificador CO1... y preguntan por qué es atípico, usa esta etiqueta.

6. INVESTMENT_CITY
   Comparar municipios o ciudades. No es el mapa por departamento ni una pregunta solo sobre Bogotá.

7. EXECUTION_TIME_ENTITY
   Duración o demora de ejecución por entidad.

8. LONGEST_CONTRACTS
   Contratos individuales con mayor duración en días.

9. RISK_ANALYSIS
   Atipicidad Isolation Forest agregada por departamento, no la lista de contratos ni un mapa de contratación o población.

10. TOP_PROVIDERS
    Proveedores, empresas privadas o contratistas. Si dice "entidades", usa TOP_ENTIDADES.

11. EXPLAIN_CONTRACT
    Detalle de un contrato con identificador CO1..., salvo que pregunten por qué es atípico.

12. MAPA_TERRITORIAL
    El ciudadano quiere ver cómo se reparte un indicador por los departamentos de Colombia (vista nacional).
    No es el total de una sola ciudad, ni un ranking de municipios, ni atipicidad Isolation Forest, ni ranking de entidades o proveedores.
    indicador debe ser uno de:
    n_contratos, valor_total, poblacion_total, total_hombres, total_mujeres, contratos_por_100k, valor_por_habitante
    codigo_dane: código DANE de dos dígitos si nombra un departamento; si no, null.
    Si pide el mapa o la distribución territorial sin decir qué indicador, usa MAPA_TERRITORIAL e indicador null.

13. UNKNOWN
    No encaja con claridad.

Criterios de MAPA_TERRITORIAL:
- Distribución nacional por departamento → MAPA_TERRITORIAL.
- Si el fenómeno es la contratación, los contratos, la contratación pública o SECOP, y no habla de valor, población, sexo ni “por habitante”, indicador = n_contratos. No lo dejes en null.
- Visualizar o ver cómo se reparte la contratación, sin nombrar modalidad, es el mapa con n_contratos. No uses MODALIDADES salvo que pregunte por contratación directa, mínima cuantía u otra modalidad.
- Si habla de valor, plata o inversión territorial, indicador = valor_total.
- Contratos por habitante o por 100.000 habitantes → contratos_por_100k.
- Valor contratado por habitante → valor_por_habitante.
- Población femenina o mujeres → total_mujeres.
- Población masculina u hombres → total_hombres.
- Población total → poblacion_total.
- Preguntar dónde se contrata más en el país, en sentido de distribución territorial, → MAPA_TERRITORIAL con n_contratos.
- Solo deja indicador en null si pide el mapa o la vista territorial sin ninguna pista de qué fenómeno pintar.
- Pedir ver o pintar cómo está la contratación en el país → n_contratos.
- Un recuento de cuántos contratos hay en Colombia o en el país, sin pedir verlos por departamento ni un mapa, no es MAPA_TERRITORIAL. Usa UNKNOWN.
- Un recuento de Bogotá como sede → BOGOTA_CONTRATACION, no mapa.
- Qué ciudad o municipio invierte más → INVESTMENT_CITY, no mapa.
- Departamento con mayor score IF o riesgo atípico → RISK_ANALYSIS, no mapa.

Reglas:
- Devuelve SOLO el JSON.
- Entidad contratante ≠ proveedor.
- Atípico no es irregularidad; igual usa TOP1_IF o PORQUE_ATIPICO según la pregunta.
- indicador y codigo_dane van en null salvo que intent sea MAPA_TERRITORIAL.

PREGUNTA DEL USUARIO:
"${pregunta}"
`;
}

async function detectarConOpenAi(userQuery) {
  const response = await cliente().chat.completions.create({
    model: 'gpt-4o-mini',
    messages: [
      { role: 'system', content: 'Responde solo con un objeto JSON válido.' },
      { role: 'user', content: promptClasificacion(userQuery) }
    ],
    temperature: 0,
    response_format: { type: 'json_object' }
  });
  const texto = (response.choices[0].message.content || '').trim();
  const clasificacion = parsearRespuesta(texto);
  console.log(
    'Intención detectada:',
    clasificacion.intent,
    clasificacion.indicador || '',
    clasificacion.codigo_dane || ''
  );
  return clasificacion;
}

let detectarFn = detectarConOpenAi;

function setDetectarIntencion(fn) {
  detectarFn = typeof fn === 'function' ? fn : detectarConOpenAi;
}

function restaurarDetectarIntencion() {
  detectarFn = detectarConOpenAi;
}

async function detectIntentLLM(userQuery) {
  return detectarFn(userQuery);
}

module.exports = {
  INTENTS,
  detectIntentLLM,
  parsearRespuesta,
  vacio,
  setDetectarIntencion,
  restaurarDetectarIntencion
};
