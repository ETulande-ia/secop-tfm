# SECOP TFM

Repositorio de entrega del Trabajo Fin de Máster. Prepara y publica la contratación pública de SECOP II de septiembre de 2026, la agrega con la población municipal del CNPV 2018 y ofrece un asistente para consultarla.

Los datos masivos, las credenciales y las dependencias instaladas no están en este repositorio. El detalle de cada resultado está en los notebooks, con las salidas de la ejecución ya realizada.

## Componentes

- **Ingesta y exploración.** Notebooks `01` a `04` y `src/ingestion/`. Descargan procesos y contratos electrónicos y describen el extracto.
- **Transformación.** Notebooks `06` a `08`, `src/transformation/` y `sql/001` a `sql/003`. Homologan el territorio, agregan el censo y publican el esquema `tfm`.
- **Anomalías.** Notebooks `09` y `10`, `src/ml/` y `sql/004` y `sql/005`. Comparan Isolation Forest, LOF y el valor, y publican la versión `c1_if_v1`.
- **Evaluación RAG.** `notebooks/11_evaluacion_rag.ipynb` y `src/rag/`. Prepara el corpus, mide la recuperación y compara el asistente con y sin documentos. `src/rag/servicio.py` expone el recuperador.
- **Evaluación de lenguaje.** `notebooks/12_evaluacion_lenguaje.ipynb` y `src/nlq_eval/`. Miden cómo el asistente interpreta 51 expresiones ciudadanas.
- **Asistente.** `asistente/orquestador/` responde las consultas. `asistente/interfaz/` muestra el chat, los gráficos y el mapa.

## Ejecución

Copie `.env.example` a `.env` y complete los valores. Abra Jupyter con el directorio de trabajo en `notebooks/`. Instale las dependencias de Python con `requirements.txt`. En cada carpeta del asistente, instale con `npm install`: el orquestador arranca con `npm start` y la interfaz con `npm start`.

La reproducción usa MongoDB, PostgreSQL, el parquet del CNPV, los documentos del corpus, el Excel de expresiones y las claves de los servicios externos. Esas piezas no se versionan aquí.
