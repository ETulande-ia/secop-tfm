const express = require('express');
const router = express.Router();
const territorial = require('../modules/territorial');

router.get('/departamentos', async (req, res) => {
  try {
    const data = await territorial.departamentos({ periodo: req.query.periodo });
    res.json(data);
  } catch (error) {
    const codigo = error.codigo || 500;
    if (codigo === 400) {
      return res.status(400).json({ error: error.message });
    }
    console.error('Error en consulta territorial:', error.message);
    res.status(500).json({ error: 'Error al consultar indicadores territoriales' });
  }
});

module.exports = router;
