const express = require('express');
const router = express.Router();
const orchestrator = require('../orchestration/query.orchestrator');

/**
 * Endpoint de chat analítico general
 * Ejemplos:
 * - ¿Qué ciudad invierte más?
 * - ¿Qué entidad se demora más en ejecutar?
 * - ¿Dónde hay más riesgo?
 */
router.post('/chat', async (req, res) => {
  try {
    const { query, contexto, modoRag } = req.body;

    if (!query || typeof query !== 'string' || query.trim().length < 3) {
      return res.status(400).json({
        error: 'Se requiere una pregunta válida en "query"'
      });
    }

    const ctx = contexto && typeof contexto === 'object' ? contexto : undefined;
    const result = await orchestrator.processUserQuery(query, ctx, { modoRag });
    res.json(result);

  } catch (error) {
    console.error('Error en orquestación:', error.message);
    res.status(500).json({
      error: 'Error interno al procesar la solicitud'
    });
  }
});

/**
 * Endpoint RAG específico para explicar un contrato
 * Entrada:
 * { "idContrato": "CO1.PCCNTR.9673418" }
 */
router.post('/explicar-contrato', async (req, res) => {
  try {
    const { idContrato } = req.body;

    if (!idContrato || typeof idContrato !== 'string') {
      return res.status(400).json({
        error: 'Se requiere un idContrato válido'
      });
    }

    const result = await orchestrator.explainContract(idContrato);
    res.json(result);

  } catch (error) {
    console.error('Error al explicar contrato:', error.message);
    if (error.message === 'Contrato no encontrado') {
      return res.status(404).json({ error: error.message });
    }
    res.status(500).json({
      error: 'Error al explicar contrato'
    });
  }
});

module.exports = router;
