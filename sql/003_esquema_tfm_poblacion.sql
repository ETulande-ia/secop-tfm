-- Este script SQL crea y configura las tablas de población municipal del CNPV 2018 en el esquema analítico `tfm` de PostgreSQL,
--  permitiendo almacenar información por municipio, desagregada por sexo, edad y zona de residencia, 
-- con homologación de códigos DIVIPOLA. Incluye tablas de preparación (*staging*) y funciones para validar 
-- la integridad y consistencia de los datos antes de publicarlos por año censal, mediante una transacción 
-- que garantiza que, ante errores de validación, los datos definitivos permanezcan sin cambios. 
-- No modifica el esquema `public` ni las tablas de SECOP II.

CREATE SCHEMA IF NOT EXISTS tfm;

CREATE TABLE IF NOT EXISTS tfm.poblacion_municipal (
    anio                            integer     NOT NULL,
    cod_municipio                   varchar(5)  NOT NULL,
    poblacion                       bigint      NOT NULL,
    en_divipola                     boolean     NOT NULL,
    estado_homologacion             text        NOT NULL,
    via_codigo                      text,
    fuente                          text        NOT NULL,
    origen                          text,
    nombre_municipio_divipola       text,
    nombre_departamento_divipola    text,
    es_bogota                       boolean,
    pob_hombres                     bigint,
    pob_mujeres                     bigint,
    pob_sexo_nulo                   bigint,
    pob_sexo_otro                   bigint,
    pob_0_14                        bigint,
    pob_15_64                       bigint,
    pob_65_mas                      bigint,
    pob_edad_nulo                   bigint,
    pob_edad_otro                   bigint,
    pob_cabecera                    bigint,
    pob_centro_poblado              bigint,
    pob_rural_disperso              bigint,
    pob_resto                       bigint,
    pob_zona_nulo                   bigint,
    pob_zona_otro                   bigint,
    categorias_sexo_ok              boolean,
    categorias_edad_ok              boolean,
    categorias_zona_ok              boolean,
    PRIMARY KEY (anio, cod_municipio)
);

CREATE INDEX IF NOT EXISTS poblacion_homologacion_idx
    ON tfm.poblacion_municipal (anio, estado_homologacion);
CREATE INDEX IF NOT EXISTS poblacion_divipola_idx
    ON tfm.poblacion_municipal (anio, en_divipola);

CREATE TABLE IF NOT EXISTS tfm.poblacion_control (
    anio        integer         NOT NULL,
    corrida_ts  timestamptz     NOT NULL,
    control     text            NOT NULL,
    observado   bigint,
    esperado    bigint,
    diferencia  bigint,
    ok          boolean,
    nota        text,
    escribir    boolean,
    PRIMARY KEY (anio, corrida_ts, control)
);

CREATE TABLE IF NOT EXISTS tfm.stg_poblacion_municipal
    (LIKE tfm.poblacion_municipal INCLUDING DEFAULTS);
CREATE INDEX IF NOT EXISTS stg_poblacion_anio_idx
    ON tfm.stg_poblacion_municipal (anio, cod_municipio);

DROP FUNCTION IF EXISTS tfm.validar_stg_poblacion(integer, bigint);
CREATE OR REPLACE FUNCTION tfm.validar_stg_poblacion(
    p_anio integer,
    p_n_personas bigint
)
RETURNS TABLE(control text, observado bigint, esperado bigint, ok boolean, nota text)
LANGUAGE sql
STABLE
AS $tfm$
WITH c AS (
    SELECT * FROM tfm.stg_poblacion_municipal WHERE anio = p_anio
)
SELECT * FROM (
    SELECT 'unicidad_municipio_filas'::text,
           (SELECT count(*) FROM c),
           (SELECT count(DISTINCT cod_municipio) FROM c),
           (SELECT count(*) FROM c) = (SELECT count(DISTINCT cod_municipio) FROM c),
           'unicidad: 1 fila por municipio'::text
    UNION ALL
    SELECT 'unicidad_anio_ajeno_stg',
           (SELECT count(*) FROM tfm.stg_poblacion_municipal WHERE anio IS DISTINCT FROM p_anio),
           0,
           (SELECT count(*) FROM tfm.stg_poblacion_municipal WHERE anio IS DISTINCT FROM p_anio) = 0,
           'unicidad: staging solo del año a publicar'
    UNION ALL
    SELECT 'disponibilidad_codigo_vacio',
           (SELECT count(*) FROM c WHERE cod_municipio IS NULL OR btrim(cod_municipio) = ''),
           0,
           (SELECT count(*) FROM c WHERE cod_municipio IS NULL OR btrim(cod_municipio) = '') = 0,
           'disponibilidad: cod_municipio'
    UNION ALL
    SELECT 'consistencia_suma_personas',
           (SELECT coalesce(sum(poblacion), 0) FROM c),
           p_n_personas,
           (SELECT coalesce(sum(poblacion), 0) FROM c) IS NOT DISTINCT FROM p_n_personas
             OR p_n_personas IS NULL,
           'consistencia: suma municipal = personas parquet'
    UNION ALL
    SELECT 'consistencia_poblacion_negativa',
           (SELECT count(*) FROM c WHERE poblacion < 0),
           0,
           (SELECT count(*) FROM c WHERE poblacion < 0) = 0,
           'consistencia: población negativa'
    UNION ALL
    SELECT 'consistencia_homologada_mas_no',
           (SELECT coalesce(sum(poblacion) FILTER (WHERE en_divipola), 0)
                 + coalesce(sum(poblacion) FILTER (WHERE NOT en_divipola), 0) FROM c),
           p_n_personas,
           (SELECT coalesce(sum(poblacion), 0) FROM c) IS NOT DISTINCT FROM p_n_personas
             OR p_n_personas IS NULL,
           'consistencia: homologada + no homologada = total'
    UNION ALL
    SELECT 'integridad_anio',
           (SELECT count(*) FROM c WHERE anio IS DISTINCT FROM p_anio),
           0,
           (SELECT count(*) FROM c WHERE anio IS DISTINCT FROM p_anio) = 0,
           'integridad: año censal 2018'
    UNION ALL
    SELECT 'stg_personas_no_homologadas',
           (SELECT coalesce(sum(poblacion), 0) FROM c WHERE NOT en_divipola),
           NULL,
           TRUE,
           'reporta códigos sin DIVIPOLA; no aborta'
) q
$tfm$;

DROP FUNCTION IF EXISTS tfm.publicar_poblacion(integer);
CREATE OR REPLACE FUNCTION tfm.publicar_poblacion(p_anio integer)
RETURNS void
LANGUAGE plpgsql
AS $tfm$
DECLARE
    n_fail integer;
BEGIN
    IF p_anio IS NULL THEN
        RAISE EXCEPTION 'anio vacio';
    END IF;

    LOCK TABLE tfm.poblacion_municipal IN EXCLUSIVE MODE;

    SELECT count(*) INTO n_fail
    FROM tfm.validar_stg_poblacion(p_anio, NULL)
    WHERE ok IS NOT TRUE
      AND control NOT IN ('consistencia_suma_personas', 'consistencia_homologada_mas_no');

    IF n_fail > 0 THEN
        RAISE EXCEPTION
            'validacion staging poblacion fallida (% controles). No se publica anio %',
            n_fail, p_anio;
    END IF;

    DELETE FROM tfm.poblacion_municipal WHERE anio = p_anio;
    INSERT INTO tfm.poblacion_municipal
    SELECT * FROM tfm.stg_poblacion_municipal WHERE anio = p_anio;
END;
$tfm$;
