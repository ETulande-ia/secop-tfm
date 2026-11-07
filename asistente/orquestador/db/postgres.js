const { Pool } = require('pg');

const pool = new Pool({
  host: process.env.DB_HOST,
  port: process.env.DB_PORT || 5432,
  user: process.env.DB_USER,
  password: process.env.DB_PASSWORD,
  database: process.env.DB_NAME,
  max: 10,               // conexiones máximas
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 2000
});

/**
 * Ejecuta una consulta SQL y devuelve las filas
 * @param {string} sql
 * @param {Array} params
 * @returns {Promise<Array>}
 */
async function queryDB(sql, params = []) {
  const client = await pool.connect();
  try {
    const result = await client.query(sql, params);
    return result.rows;
  } catch (error) {
    console.error('Error ejecutando query:', error.message);
    throw error;
  } finally {
    client.release();
  }
}

module.exports = {
  queryDB
};
