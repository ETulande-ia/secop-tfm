-- Este script SQL crea y configura las tablas para almacenar los resultados del modelo de detección de anomalías Isolation Forest 
-- sobre contratos electrónicos de SECOP II, en el esquema `tfm` de PostgreSQL. Permite registrar las versiones del modelo, las puntuaciones
--  y clasificaciones de los contratos, los registros excluidos y la trazabilidad de las ejecuciones. Incluye tablas de preparación (staging) 
-- y controles de calidad para validar los resultados antes de publicarlos por periodo y versión, mediante una transacción que evita modificaciones
--  parciales ante errores. No modifica el esquema `public` ni las tablas originales de contratación y población.

CREATE SCHEMA IF NOT EXISTS tfm;

-- Catálogo de la especificación del modelo (no cada corrida).
CREATE TABLE IF NOT EXISTS tfm.ml_modelo (
    version_modelo      text        PRIMARY KEY,
    matriz              text        NOT NULL,
    algoritmo           text        NOT NULL,
    semilla             integer     NOT NULL,
    n_estimators        integer     NOT NULL,
    contamination       double precision NOT NULL,
    variables           text        NOT NULL,
    huella              text        NOT NULL,
    documentacion       text,
    vigente             boolean     NOT NULL DEFAULT true,
    actualizado_ts      timestamptz NOT NULL DEFAULT now()
);

-- Auditoría de cada intento de publicación (append-only).
CREATE TABLE IF NOT EXISTS tfm.ml_ejecucion (
    id_ejecucion        text        PRIMARY KEY,
    version_modelo      text        NOT NULL REFERENCES tfm.ml_modelo (version_modelo),
    periodo             varchar(7)  NOT NULL,
    corrida_ts          timestamptz NOT NULL,
    n_aptos             bigint      NOT NULL,
    n_excluidos         bigint      NOT NULL,
    n_top1_if           bigint,
    n_top5_if           bigint,
    n_p99_modalidad     bigint,
    sklearn_version     text,
    pandas_version      text,
    numpy_version       text,
    escribir            boolean     NOT NULL,
    estado              text        NOT NULL,
    nota                text,
    CONSTRAINT ml_ejecucion_estado_chk
        CHECK (estado IN ('publicado'))
);

CREATE INDEX IF NOT EXISTS ml_ejecucion_periodo_idx
    ON tfm.ml_ejecucion (periodo, version_modelo, corrida_ts);

-- Un resultado por contrato apto. PK impide duplicar el mismo experimento.
CREATE TABLE IF NOT EXISTS tfm.ml_contrato_score (
    periodo                     varchar(7)  NOT NULL,
    version_modelo              text        NOT NULL REFERENCES tfm.ml_modelo (version_modelo),
    id_ejecucion                text        NOT NULL,
    id_contrato                 text        NOT NULL,
    socrata_id                  text,
    score_if                    double precision NOT NULL,
    rank_if                     integer     NOT NULL,
    top1_if                     boolean     NOT NULL,
    top5_if                     boolean     NOT NULL,
    score_logvalor              double precision NOT NULL,
    rank_logvalor               integer     NOT NULL,
    top1_logvalor               boolean     NOT NULL,
    top5_logvalor               boolean     NOT NULL,
    flag_p99_modalidad          boolean     NOT NULL,
    valor_del_contrato          numeric     NOT NULL,
    modalidad_grupo             text        NOT NULL,
    modalidad_de_contratacion   text,
    nombre_entidad              text,
    cod_municipio               varchar(5),
    es_bogota                   boolean,
    estado_homologacion         text,
    PRIMARY KEY (periodo, version_modelo, id_contrato),
    UNIQUE (periodo, version_modelo, rank_if),
    UNIQUE (periodo, version_modelo, rank_logvalor),
    FOREIGN KEY (periodo, id_contrato)
        REFERENCES tfm.contrato (periodo, id_contrato)
);

CREATE INDEX IF NOT EXISTS ml_score_top1_idx
    ON tfm.ml_contrato_score (periodo, version_modelo, top1_if);
CREATE INDEX IF NOT EXISTS ml_score_top5_idx
    ON tfm.ml_contrato_score (periodo, version_modelo, top5_if);
CREATE INDEX IF NOT EXISTS ml_score_p99_idx
    ON tfm.ml_contrato_score (periodo, version_modelo, flag_p99_modalidad);
CREATE INDEX IF NOT EXISTS ml_score_rank_if_idx
    ON tfm.ml_contrato_score (periodo, version_modelo, rank_if);
CREATE INDEX IF NOT EXISTS ml_score_entidad_idx
    ON tfm.ml_contrato_score (periodo, version_modelo, nombre_entidad);
CREATE INDEX IF NOT EXISTS ml_score_municipio_idx
    ON tfm.ml_contrato_score (periodo, version_modelo, cod_municipio);
CREATE INDEX IF NOT EXISTS ml_score_modalidad_idx
    ON tfm.ml_contrato_score (periodo, version_modelo, modalidad_grupo);

-- Ceros y extremo: consultables, sin puntuación del modelo.
CREATE TABLE IF NOT EXISTS tfm.ml_contrato_excluido (
    periodo                     varchar(7)  NOT NULL,
    version_modelo              text        NOT NULL REFERENCES tfm.ml_modelo (version_modelo),
    id_ejecucion                text        NOT NULL,
    id_contrato                 text        NOT NULL,
    socrata_id                  text,
    motivo_exclusion            text        NOT NULL,
    valor_del_contrato          numeric,
    modalidad_de_contratacion   text,
    nombre_entidad              text,
    cod_municipio               varchar(5),
    es_bogota                   boolean,
    PRIMARY KEY (periodo, version_modelo, id_contrato),
    FOREIGN KEY (periodo, id_contrato)
        REFERENCES tfm.contrato (periodo, id_contrato),
    CONSTRAINT ml_excluido_motivo_chk
        CHECK (motivo_exclusion IN ('valor_cero', 'valor_extremo'))
);

CREATE TABLE IF NOT EXISTS tfm.ml_control (
    periodo         varchar(7)      NOT NULL,
    corrida_ts      timestamptz     NOT NULL,
    version_modelo  text            NOT NULL,
    id_ejecucion    text            NOT NULL,
    control         text            NOT NULL,
    observado       bigint,
    esperado        bigint,
    diferencia      bigint,
    ok              boolean,
    nota            text,
    escribir        boolean,
    PRIMARY KEY (periodo, corrida_ts, control)
);

CREATE TABLE IF NOT EXISTS tfm.stg_ml_contrato_score
    (LIKE tfm.ml_contrato_score INCLUDING DEFAULTS);
CREATE TABLE IF NOT EXISTS tfm.stg_ml_contrato_excluido
    (LIKE tfm.ml_contrato_excluido INCLUDING DEFAULTS);

DROP FUNCTION IF EXISTS tfm.validar_stg_ml(varchar, text, bigint, bigint);
CREATE OR REPLACE FUNCTION tfm.validar_stg_ml(
    p_periodo varchar,
    p_version text,
    p_n_score bigint,
    p_n_excluidos bigint
)
RETURNS TABLE(control text, observado bigint, esperado bigint, ok boolean, nota text)
LANGUAGE sql
STABLE
AS $tfm$
WITH s AS (
    SELECT * FROM tfm.stg_ml_contrato_score
    WHERE periodo = p_periodo AND version_modelo = p_version
),
e AS (
    SELECT * FROM tfm.stg_ml_contrato_excluido
    WHERE periodo = p_periodo AND version_modelo = p_version
)
SELECT * FROM (
    SELECT 'unicidad_score_filas'::text,
           (SELECT count(*) FROM s),
           p_n_score,
           (SELECT count(*) FROM s) = p_n_score,
           'filas staging vs esperadas (aptos)'::text
    UNION ALL
    SELECT 'unicidad_score_dup',
           (SELECT count(*) FROM s) - (SELECT count(DISTINCT id_contrato) FROM s),
           0,
           (SELECT count(*) FROM s) = (SELECT count(DISTINCT id_contrato) FROM s),
           'duplicados id_contrato en scores'
    UNION ALL
    SELECT 'unicidad_periodo_ajeno_score',
           (SELECT count(*) FROM tfm.stg_ml_contrato_score
             WHERE periodo IS DISTINCT FROM p_periodo
                OR version_modelo IS DISTINCT FROM p_version),
           0,
           (SELECT count(*) FROM tfm.stg_ml_contrato_score
             WHERE periodo IS DISTINCT FROM p_periodo
                OR version_modelo IS DISTINCT FROM p_version) = 0,
           'staging scores solo del par a publicar'
    UNION ALL
    SELECT 'unicidad_excluido_filas',
           (SELECT count(*) FROM e),
           p_n_excluidos,
           (SELECT count(*) FROM e) = p_n_excluidos,
           'filas staging vs esperadas (excluidos)'
    UNION ALL
    SELECT 'unicidad_excluido_dup',
           (SELECT count(*) FROM e) - (SELECT count(DISTINCT id_contrato) FROM e),
           0,
           (SELECT count(*) FROM e) = (SELECT count(DISTINCT id_contrato) FROM e),
           'duplicados id_contrato en excluidos'
    UNION ALL
    SELECT 'solape_score_excluido',
           (SELECT count(*) FROM s JOIN e USING (id_contrato)),
           0,
           (SELECT count(*) FROM s JOIN e USING (id_contrato)) = 0,
           'un contrato no puede estar en scores y excluidos'
    UNION ALL
    SELECT 'disponibilidad_score_nulo',
           (SELECT count(*) FROM s WHERE score_if IS NULL OR rank_if IS NULL),
           0,
           (SELECT count(*) FROM s WHERE score_if IS NULL OR rank_if IS NULL) = 0,
           'score_if y rank_if obligatorios en aptos'
    UNION ALL
    SELECT 'disponibilidad_id_vacio',
           (SELECT count(*) FROM s WHERE id_contrato IS NULL OR btrim(id_contrato) = ''),
           0,
           (SELECT count(*) FROM s WHERE id_contrato IS NULL OR btrim(id_contrato) = '') = 0,
           'id_contrato en scores'
    UNION ALL
    SELECT 'top1_implica_top5',
           (SELECT count(*) FROM s WHERE top1_if AND NOT top5_if),
           0,
           (SELECT count(*) FROM s WHERE top1_if AND NOT top5_if) = 0,
           'top 1 % IF contenido en top 5 %'
    UNION ALL
    SELECT 'conteo_top1_if',
           (SELECT count(*) FROM s WHERE top1_if),
           round(p_n_score * 0.01),
           (SELECT count(*) FROM s WHERE top1_if) = round(p_n_score * 0.01),
           'top 1 % IF = round(n*0.01)'
    UNION ALL
    SELECT 'conteo_top5_if',
           (SELECT count(*) FROM s WHERE top5_if),
           round(p_n_score * 0.05),
           (SELECT count(*) FROM s WHERE top5_if) = round(p_n_score * 0.05),
           'top 5 % IF = round(n*0.05)'
    UNION ALL
    SELECT 'fk_score_contrato',
           (SELECT count(*) FROM s s0
              LEFT JOIN tfm.contrato c
                ON c.periodo = s0.periodo AND c.id_contrato = s0.id_contrato
             WHERE c.id_contrato IS NULL),
           0,
           (SELECT count(*) FROM s s0
              LEFT JOIN tfm.contrato c
                ON c.periodo = s0.periodo AND c.id_contrato = s0.id_contrato
             WHERE c.id_contrato IS NULL) = 0,
           'todo score referencia tfm.contrato'
    UNION ALL
    SELECT 'fk_excluido_contrato',
           (SELECT count(*) FROM e e0
              LEFT JOIN tfm.contrato c
                ON c.periodo = e0.periodo AND c.id_contrato = e0.id_contrato
             WHERE c.id_contrato IS NULL),
           0,
           (SELECT count(*) FROM e e0
              LEFT JOIN tfm.contrato c
                ON c.periodo = e0.periodo AND c.id_contrato = e0.id_contrato
             WHERE c.id_contrato IS NULL) = 0,
           'todo excluido referencia tfm.contrato'
    UNION ALL
    SELECT 'aptos_en_scores',
           (SELECT count(*) FROM s s0
              JOIN tfm.contrato c
                ON c.periodo = s0.periodo AND c.id_contrato = s0.id_contrato
             WHERE c.valor_apto_modelo IS NOT TRUE),
           0,
           (SELECT count(*) FROM s s0
              JOIN tfm.contrato c
                ON c.periodo = s0.periodo AND c.id_contrato = s0.id_contrato
             WHERE c.valor_apto_modelo IS NOT TRUE) = 0,
           'scores solo sobre valor_apto_modelo'
    UNION ALL
    SELECT 'excluidos_marcados',
           (SELECT count(*) FROM e e0
              JOIN tfm.contrato c
                ON c.periodo = e0.periodo AND c.id_contrato = e0.id_contrato
             WHERE NOT (c.valor_del_contrato_cero OR c.valor_del_contrato_extremo)),
           0,
           (SELECT count(*) FROM e e0
              JOIN tfm.contrato c
                ON c.periodo = e0.periodo AND c.id_contrato = e0.id_contrato
             WHERE NOT (c.valor_del_contrato_cero OR c.valor_del_contrato_extremo)) = 0,
           'excluidos son cero o extremo en tfm.contrato'
    UNION ALL
    SELECT 'cobertura_universo',
           (SELECT count(*) FROM s) + (SELECT count(*) FROM e),
           (SELECT count(*) FROM tfm.contrato WHERE periodo = p_periodo),
           ((SELECT count(*) FROM s) + (SELECT count(*) FROM e))
             = (SELECT count(*) FROM tfm.contrato WHERE periodo = p_periodo),
           'scores + excluidos = tfm.contrato del periodo'
    UNION ALL
    SELECT 'score_if_finito',
           (SELECT count(*) FROM s
             WHERE score_if IS NULL
                OR score_if <> score_if
                OR score_if IN ('Infinity'::float8, '-Infinity'::float8)),
           0,
           (SELECT count(*) FROM s
             WHERE score_if IS NULL
                OR score_if <> score_if
                OR score_if IN ('Infinity'::float8, '-Infinity'::float8)) = 0,
           'score_if finito (mayor = más atípico)'
    UNION ALL
    SELECT 'rank_if_unicos',
           (SELECT count(DISTINCT rank_if) FROM s),
           p_n_score,
           (SELECT count(DISTINCT rank_if) FROM s) = p_n_score,
           'rank_if único'
    UNION ALL
    SELECT 'rank_if_rango',
           (SELECT COALESCE(min(rank_if), -1) FROM s),
           1,
           (SELECT COALESCE(min(rank_if), -1) FROM s) = 1
             AND (SELECT COALESCE(max(rank_if), -1) FROM s) = p_n_score,
           'rank_if consecutivo 1..n'
    UNION ALL
    SELECT 'rank_logvalor_unicos',
           (SELECT count(DISTINCT rank_logvalor) FROM s),
           p_n_score,
           (SELECT count(DISTINCT rank_logvalor) FROM s) = p_n_score,
           'rank_logvalor único'
    UNION ALL
    SELECT 'orden_score_if',
           (SELECT count(*) FROM s
             WHERE rank_if = 1
               AND score_if IS DISTINCT FROM (SELECT max(score_if) FROM s)),
           0,
           (SELECT count(*) FROM s
             WHERE rank_if = 1
               AND score_if IS DISTINCT FROM (SELECT max(score_if) FROM s)) = 0,
           'rank_if=1 es el máximo score_if'
) q
$tfm$;

DROP FUNCTION IF EXISTS tfm.publicar_ml_contratos(varchar, text);
CREATE OR REPLACE FUNCTION tfm.publicar_ml_contratos(
    p_periodo varchar,
    p_version text
)
RETURNS void
LANGUAGE plpgsql
AS $tfm$
DECLARE
    n_fail integer;
BEGIN
    IF p_periodo IS NULL OR btrim(p_periodo) = '' THEN
        RAISE EXCEPTION 'periodo vacio';
    END IF;
    IF p_version IS NULL OR btrim(p_version) = '' THEN
        RAISE EXCEPTION 'version_modelo vacia';
    END IF;

    PERFORM pg_advisory_xact_lock(hashtext(p_periodo || chr(31) || p_version));
    LOCK TABLE tfm.ml_contrato_score, tfm.ml_contrato_excluido IN EXCLUSIVE MODE;

    SELECT count(*) INTO n_fail
    FROM tfm.validar_stg_ml(p_periodo, p_version, NULL, NULL)
    WHERE ok IS NOT TRUE
      AND control NOT IN (
            'unicidad_score_filas', 'unicidad_excluido_filas',
            'conteo_top1_if', 'conteo_top5_if',
            'rank_if_unicos', 'rank_if_rango', 'rank_logvalor_unicos'
          );

    IF n_fail > 0 THEN
        RAISE EXCEPTION
            'validacion staging ML fallida (% controles). No se publica % %',
            n_fail, p_periodo, p_version;
    END IF;

    DELETE FROM tfm.ml_contrato_score
     WHERE periodo = p_periodo AND version_modelo = p_version;
    DELETE FROM tfm.ml_contrato_excluido
     WHERE periodo = p_periodo AND version_modelo = p_version;

    INSERT INTO tfm.ml_contrato_score
    SELECT * FROM tfm.stg_ml_contrato_score
     WHERE periodo = p_periodo AND version_modelo = p_version;

    INSERT INTO tfm.ml_contrato_excluido
    SELECT * FROM tfm.stg_ml_contrato_excluido
     WHERE periodo = p_periodo AND version_modelo = p_version;
END;
$tfm$;

COMMENT ON COLUMN tfm.ml_contrato_score.score_if IS
    'Isolation Forest: -decision_function. Mayor = más atípico. rank_if=1 es el máximo.';
COMMENT ON COLUMN tfm.ml_modelo.huella IS
    'SHA-256 canónica de c1_if_v1. Si cambia, se aborta; no se actualizan parámetros.';
COMMENT ON TABLE tfm.ml_ejecucion IS
    'Append-only. Cada publicación inserta una fila con estado=publicado.';
