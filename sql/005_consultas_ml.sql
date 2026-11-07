-- Este script SQL contiene consultas de ejemplo para analizar los resultados del modelo Isolation Forest
--  aplicado a contratos electrónicos de SECOP II. - 
-- Permite identificar los contratos más atípicos (top 1 % y 5 %), comparar sus resultados con indicadores estadísticos de valor,
--  aplicar filtros por entidad, modalidad y municipio, consultar los contratos excluidos y verificar la trazabilidad de las ejecuciones 
-- y versiones del modelo. Todas las consultas son de solo lectura y no modifican los datos almacenados.

-- 1. Top 1 % Isolation Forest
SELECT rank_if, id_contrato, nombre_entidad, modalidad_grupo,
       valor_del_contrato, score_if, top1_logvalor, flag_p99_modalidad
FROM tfm.ml_contrato_score
WHERE periodo = '2026-09' AND version_modelo = 'c1_if_v1' AND top1_if
ORDER BY rank_if;

-- 2. Top 5 % Isolation Forest
SELECT rank_if, id_contrato, nombre_entidad, modalidad_grupo,
       valor_del_contrato, score_if
FROM tfm.ml_contrato_score
WHERE periodo = '2026-09' AND version_modelo = 'c1_if_v1' AND top5_if
ORDER BY rank_if;

-- 3. Comparación IF vs ranking global de log-valor (top 5 %)
SELECT
    count(*) FILTER (WHERE top5_if) AS n_top5_if,
    count(*) FILTER (WHERE top5_logvalor) AS n_top5_logvalor,
    count(*) FILTER (WHERE top5_if AND top5_logvalor) AS n_ambos,
    count(*) FILTER (WHERE top5_if AND NOT top5_logvalor) AS n_solo_if,
    count(*) FILTER (WHERE top5_logvalor AND NOT top5_if) AS n_solo_logvalor
FROM tfm.ml_contrato_score
WHERE periodo = '2026-09' AND version_modelo = 'c1_if_v1';

-- 4. Contratos P99 por modalidad (control estadístico, no es IF)
SELECT id_contrato, modalidad_grupo, valor_del_contrato,
       rank_logvalor, rank_if, top1_if
FROM tfm.ml_contrato_score
WHERE periodo = '2026-09' AND version_modelo = 'c1_if_v1'
  AND flag_p99_modalidad
ORDER BY modalidad_grupo, valor_del_contrato DESC;

-- 5. Filtro por entidad, modalidad y municipio
SELECT s.rank_if, s.id_contrato, s.nombre_entidad, s.modalidad_grupo,
       s.cod_municipio, s.valor_del_contrato, s.score_if, c.ciudad
FROM tfm.ml_contrato_score s
JOIN tfm.contrato c
  ON c.periodo = s.periodo AND c.id_contrato = s.id_contrato
WHERE s.periodo = '2026-09' AND s.version_modelo = 'c1_if_v1'
  AND s.top5_if
  AND s.nombre_entidad ILIKE '%CARTAGENA%'
  AND s.modalidad_grupo <> 'Contratación directa'
  AND s.cod_municipio = '13001'
ORDER BY s.rank_if;

-- 6. Excluidos del entrenamiento (sin score del modelo)
SELECT motivo_exclusion, count(*) AS n
FROM tfm.ml_contrato_excluido
WHERE periodo = '2026-09' AND version_modelo = 'c1_if_v1'
GROUP BY motivo_exclusion
ORDER BY motivo_exclusion;

SELECT id_contrato, motivo_exclusion, nombre_entidad,
       valor_del_contrato, modalidad_de_contratacion
FROM tfm.ml_contrato_excluido
WHERE periodo = '2026-09' AND version_modelo = 'c1_if_v1'
ORDER BY motivo_exclusion, valor_del_contrato DESC NULLS LAST;

-- 7. Trazabilidad de la ejecución publicada
SELECT * FROM tfm.ml_ejecucion
WHERE periodo = '2026-09' AND version_modelo = 'c1_if_v1'
ORDER BY corrida_ts DESC;

SELECT * FROM tfm.ml_modelo WHERE version_modelo = 'c1_if_v1';
