// config/index.js
require('dotenv').config();

module.exports = {
  port: process.env.PORT || 3001,
  mongoUri: process.env.MONGO_URI || 'mongodb://localhost:27017/secop_analytical_db',
  openaiApiKey: process.env.OPENAI_API_KEY,
  // Periodo y versión publicados en tfm (docs/11). No reentrena el modelo.
  periodo: process.env.PERIODO || '2026-09',
  versionModelo: process.env.VERSION_MODELO || 'c1_if_v1',
  ragUrl: process.env.RAG_URL || 'http://rag-documental:8091'
};