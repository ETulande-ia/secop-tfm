// server.js
const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
require('dotenv').config();

const chatRoutes = require('./routes/chat.route');
const territorialRoutes = require('./routes/territorial.route');

const app = express();
const PORT = process.env.PORT || 3001;

app.use(helmet());
app.use(cors());
app.use(express.json({ limit: '10mb' }));

// Rutas
app.use('/api', chatRoutes);
app.use('/api/territorial', territorialRoutes);

// Ruta de salud
app.get('/', (req, res) => {
  res.json({ status: 'OK', message: 'Capa de orquestación activa' });
});

app.listen(PORT, () => {
  console.log(`✅ Orquestador corriendo en http://localhost:${PORT}`);
});