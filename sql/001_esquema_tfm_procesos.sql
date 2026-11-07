--Este script SQL crea y configura el esquema analítico tfm en PostgreSQL para almacenar 
-- los procesos de contratación y sus adjudicaciones provenientes de SECOP II.

-- Define tablas para procesos, adjudicaciones confiables, adjudicaciones ambiguas 
-- y controles de calidad. También incorpora tablas temporales de preparación (staging) 
-- y funciones que verifican la integridad, unicidad y consistencia de los datos antes de publicarlos.

CREATE SCHEMA IF NOT EXISTS tfm;

CREATE TABLE IF NOT EXISTS tfm.proceso (
    periodo                         varchar(7)  NOT NULL,
    id_del_proceso                  text        NOT NULL,
    estado_del_procedimiento        text,
    fecha_de_publicacion_del        text,
    fecha_de_ultima_publicaci       text,
    modalidad_de_contratacion       text,
    entidad                         text,
    nit_entidad                     text,
    departamento_entidad            text,
    ciudad_entidad                  text,
    precio_base                     numeric,
    adjudicado                      text,
    referencia_del_proceso          text,
    duracion                        text,
    unidad_de_duracion              text,
    ciudad_de_la_unidad_de          text,
    url_proceso                     text,
    n_filas_api                     bigint,
    n_socrata_id                    bigint,
    socrata_ids                     text        NOT NULL,
    campos_variables                text,
    hay_campos_variables            boolean,
    es_bogota                       boolean,
    cod_municipio                   varchar(5),
    estado_homologacion             text,
    via_homologacion                text,
    nombre_municipio_divipola       text,
    nombre_departamento_divipola    text,
    departamento_entidad_ausente    boolean,
    ciudad_entidad_ausente          boolean,
    entidad_ausente                 boolean,
    adjudicado_ausente              boolean,
    precio_base_cero                boolean,
    precio_base_negativo            boolean,
    precio_base_extremo             boolean,
    PRIMARY KEY (periodo, id_del_proceso)
);

CREATE INDEX IF NOT EXISTS proceso_cod_municipio_idx
    ON tfm.proceso (periodo, cod_municipio);
CREATE INDEX IF NOT EXISTS proceso_homologacion_idx
    ON tfm.proceso (periodo, estado_homologacion);

CREATE TABLE IF NOT EXISTS tfm.adjudicacion (
    periodo                     varchar(7)  NOT NULL,
    id_del_proceso              text        NOT NULL,
    id_adjudicacion             text        NOT NULL,
    tipo_grano                  text        NOT NULL,
    n_proveedores               bigint,
    n_valores                   bigint,
    n_filas_api                 bigint,
    codigo_proveedor            text,
    nombre_del_proveedor        text,
    valor_total_adjudicacion    numeric,
    valor_usable                boolean     NOT NULL,
    proveedores                 text,
    valores                     text,
    socrata_ids                 text        NOT NULL,
    valor_total_adjudicacion_cero      boolean,
    valor_total_adjudicacion_negativo  boolean,
    valor_total_adjudicacion_extremo   boolean,
    PRIMARY KEY (periodo, id_del_proceso, id_adjudicacion),
    FOREIGN KEY (periodo, id_del_proceso)
        REFERENCES tfm.proceso (periodo, id_del_proceso)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS adjudicacion_usable_idx
    ON tfm.adjudicacion (periodo, valor_usable);

CREATE TABLE IF NOT EXISTS tfm.adjudicacion_ambigua (
    periodo             varchar(7)  NOT NULL,
    id_del_proceso      text        NOT NULL,
    id_adjudicacion     text        NOT NULL,
    n_filas_api         bigint,
    n_proveedores       bigint,
    n_valores           bigint,
    n_filas             bigint,
    n_prov              bigint,
    n_val               bigint,
    proveedores         text,
    valores             text,
    socrata_ids         text        NOT NULL,
    cartesiano          boolean,
    sin_awd             boolean,
    motivo              text,
    suma_valores        text        NOT NULL DEFAULT 'no aplicada',
    PRIMARY KEY (periodo, id_del_proceso, id_adjudicacion),
    FOREIGN KEY (periodo, id_del_proceso)
        REFERENCES tfm.proceso (periodo, id_del_proceso)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS tfm.proceso_control (
    periodo     varchar(7)      NOT NULL,
    corrida_ts  timestamptz     NOT NULL,
    control     text            NOT NULL,
    observado   bigint,
    esperado    bigint,
    diferencia  bigint,
    ok          boolean,
    nota        text,
    escribir    boolean,
    PRIMARY KEY (periodo, corrida_ts, control)
);

-- Staging: mismas columnas, sin PK/FK. Spark puede cargar a medias;
-- las definitivas no se tocan hasta tfm.publicar_periodo_procesos.
CREATE TABLE IF NOT EXISTS tfm.stg_proceso (LIKE tfm.proceso INCLUDING DEFAULTS);
CREATE TABLE IF NOT EXISTS tfm.stg_adjudicacion (LIKE tfm.adjudicacion INCLUDING DEFAULTS);
CREATE TABLE IF NOT EXISTS tfm.stg_adjudicacion_ambigua (LIKE tfm.adjudicacion_ambigua INCLUDING DEFAULTS);

CREATE INDEX IF NOT EXISTS stg_proceso_periodo_idx
    ON tfm.stg_proceso (periodo, id_del_proceso);
CREATE INDEX IF NOT EXISTS stg_adjudicacion_periodo_idx
    ON tfm.stg_adjudicacion (periodo, id_del_proceso, id_adjudicacion);
CREATE INDEX IF NOT EXISTS stg_adjudicacion_ambigua_periodo_idx
    ON tfm.stg_adjudicacion_ambigua (periodo, id_del_proceso, id_adjudicacion);

DROP FUNCTION IF EXISTS tfm.validar_stg_procesos(varchar, bigint, bigint, bigint);
CREATE OR REPLACE FUNCTION tfm.validar_stg_procesos(
    p_periodo varchar,
    p_n_proceso bigint,
    p_n_adj bigint,
    p_n_amb bigint
)
RETURNS TABLE(control text, observado bigint, esperado bigint, ok boolean, nota text)
LANGUAGE sql
STABLE
AS $tfm$
WITH proc AS (
    SELECT * FROM tfm.stg_proceso WHERE periodo = p_periodo
), adj AS (
    SELECT * FROM tfm.stg_adjudicacion WHERE periodo = p_periodo
), amb AS (
    SELECT * FROM tfm.stg_adjudicacion_ambigua WHERE periodo = p_periodo
)
SELECT * FROM (
    -- Unicidad
    SELECT 'unicidad_proceso_filas'::text,
           (SELECT count(*) FROM proc),
           p_n_proceso,
           (SELECT count(*) FROM proc) = p_n_proceso,
           'unicidad: filas staging vs Spark'::text
    UNION ALL
    SELECT 'unicidad_proceso_dup',
           (SELECT count(*) FROM proc) - (SELECT count(DISTINCT id_del_proceso) FROM proc),
           0,
           (SELECT count(*) FROM proc) = (SELECT count(DISTINCT id_del_proceso) FROM proc),
           'unicidad: duplicados de id_del_proceso'
    UNION ALL
    SELECT 'unicidad_adjudicacion_filas',
           (SELECT count(*) FROM adj),
           p_n_adj,
           (SELECT count(*) FROM adj) = p_n_adj,
           'unicidad: filas staging vs Spark'
    UNION ALL
    SELECT 'unicidad_adjudicacion_dup',
           (SELECT count(*) FROM adj)
             - (SELECT count(DISTINCT (id_del_proceso, id_adjudicacion)) FROM adj),
           0,
           (SELECT count(*) FROM adj)
             = (SELECT count(DISTINCT (id_del_proceso, id_adjudicacion)) FROM adj),
           'unicidad: duplicados de par proceso+award'
    UNION ALL
    SELECT 'unicidad_ambigua_filas',
           (SELECT count(*) FROM amb),
           p_n_amb,
           (SELECT count(*) FROM amb) = p_n_amb,
           'unicidad: filas staging vs Spark'
    UNION ALL
    SELECT 'unicidad_ambigua_dup',
           (SELECT count(*) FROM amb)
             - (SELECT count(DISTINCT (id_del_proceso, id_adjudicacion)) FROM amb),
           0,
           (SELECT count(*) FROM amb)
             = (SELECT count(DISTINCT (id_del_proceso, id_adjudicacion)) FROM amb),
           'unicidad: duplicados en ambigua'
    UNION ALL
    SELECT 'unicidad_solape_confiable_ambigua',
           (SELECT count(*)
            FROM adj a
            JOIN amb b
              ON a.id_del_proceso = b.id_del_proceso
             AND a.id_adjudicacion = b.id_adjudicacion),
           0,
           (SELECT count(*)
            FROM adj a
            JOIN amb b
              ON a.id_del_proceso = b.id_del_proceso
             AND a.id_adjudicacion = b.id_adjudicacion) = 0,
           'unicidad: el par no puede estar en ambas tablas'
    UNION ALL
    SELECT 'unicidad_adj_sin_proceso',
           (SELECT count(*)
            FROM adj a
            LEFT JOIN proc p ON a.id_del_proceso = p.id_del_proceso
            WHERE p.id_del_proceso IS NULL),
           0,
           (SELECT count(*)
            FROM adj a
            LEFT JOIN proc p ON a.id_del_proceso = p.id_del_proceso
            WHERE p.id_del_proceso IS NULL) = 0,
           'unicidad: FK staging adjudicacion → proceso'
    UNION ALL
    SELECT 'unicidad_amb_sin_proceso',
           (SELECT count(*)
            FROM amb a
            LEFT JOIN proc p ON a.id_del_proceso = p.id_del_proceso
            WHERE p.id_del_proceso IS NULL),
           0,
           (SELECT count(*)
            FROM amb a
            LEFT JOIN proc p ON a.id_del_proceso = p.id_del_proceso
            WHERE p.id_del_proceso IS NULL) = 0,
           'unicidad: FK staging ambigua → proceso'
    UNION ALL
    SELECT 'unicidad_periodo_ajeno_stg',
           (SELECT count(*) FROM tfm.stg_proceso WHERE periodo IS DISTINCT FROM p_periodo)
             + (SELECT count(*) FROM tfm.stg_adjudicacion WHERE periodo IS DISTINCT FROM p_periodo)
             + (SELECT count(*) FROM tfm.stg_adjudicacion_ambigua WHERE periodo IS DISTINCT FROM p_periodo),
           0,
           (
             (SELECT count(*) FROM tfm.stg_proceso WHERE periodo IS DISTINCT FROM p_periodo)
           + (SELECT count(*) FROM tfm.stg_adjudicacion WHERE periodo IS DISTINCT FROM p_periodo)
           + (SELECT count(*) FROM tfm.stg_adjudicacion_ambigua WHERE periodo IS DISTINCT FROM p_periodo)
           ) = 0,
           'unicidad: staging solo del periodo a publicar'
    UNION ALL
    -- Disponibilidad del monto
    SELECT 'disponibilidad_usable_sin_monto',
           (SELECT count(*) FROM adj WHERE valor_usable AND valor_total_adjudicacion IS NULL),
           0,
           (SELECT count(*) FROM adj WHERE valor_usable AND valor_total_adjudicacion IS NULL) = 0,
           'disponibilidad: valor_usable exige monto'
    UNION ALL
    SELECT 'disponibilidad_monto_no_usable',
           (SELECT count(*) FROM adj WHERE (NOT valor_usable) AND valor_total_adjudicacion IS NOT NULL),
           0,
           (SELECT count(*) FROM adj WHERE (NOT valor_usable) AND valor_total_adjudicacion IS NOT NULL) = 0,
           'disponibilidad: varios montos → valor nulo'
    UNION ALL
    SELECT 'disponibilidad_usable_n_valores',
           (SELECT count(*) FROM adj WHERE valor_usable <> (n_valores = 1)),
           0,
           (SELECT count(*) FROM adj WHERE valor_usable <> (n_valores = 1)) = 0,
           'disponibilidad: valor_usable <=> n_valores = 1'
    UNION ALL
    SELECT 'disponibilidad_socrata_vacio',
           (SELECT count(*) FROM adj WHERE socrata_ids IS NULL OR btrim(socrata_ids) = '')
             + (SELECT count(*) FROM amb WHERE socrata_ids IS NULL OR btrim(socrata_ids) = ''),
           0,
           (
             (SELECT count(*) FROM adj WHERE socrata_ids IS NULL OR btrim(socrata_ids) = '')
           + (SELECT count(*) FROM amb WHERE socrata_ids IS NULL OR btrim(socrata_ids) = '')
           ) = 0,
           'disponibilidad: trazabilidad socrata_id'
    UNION ALL
    -- Positividad (negativos abortan; ceros y positivos se registran)
    SELECT 'positividad_monto_negativo',
           (SELECT count(*) FROM adj WHERE valor_usable AND valor_total_adjudicacion < 0),
           0,
           (SELECT count(*) FROM adj WHERE valor_usable AND valor_total_adjudicacion < 0) = 0,
           'positividad: monto usable negativo'
    UNION ALL
    SELECT 'positividad_monto_cero',
           (SELECT count(*) FROM adj WHERE valor_usable AND valor_total_adjudicacion = 0),
           NULL,
           TRUE,
           'positividad: monto usable = 0 (no aborta)'
    UNION ALL
    SELECT 'positividad_monto_positivo',
           (SELECT count(*) FROM adj WHERE valor_usable AND valor_total_adjudicacion > 0),
           NULL,
           TRUE,
           'positividad: monto usable > 0 (no aborta)'
    UNION ALL
    -- Aptitud para agregaciones
    SELECT 'aptitud_agregar',
           (SELECT count(*) FROM adj WHERE valor_usable AND valor_total_adjudicacion > 0),
           NULL,
           TRUE,
           'aptitud: usable y positivo; cartesianos no entran'
    UNION ALL
    SELECT 'aptitud_tipo_revisar',
           (SELECT count(*) FROM adj WHERE tipo_grano = 'revisar'),
           0,
           (SELECT count(*) FROM adj WHERE tipo_grano = 'revisar') = 0,
           'aptitud: no cartesianos en confiables'
    UNION ALL
    SELECT 'aptitud_ambigua_sin_suma',
           (SELECT count(*) FROM amb WHERE suma_valores IS DISTINCT FROM 'no aplicada'),
           0,
           (SELECT count(*) FROM amb WHERE suma_valores IS DISTINCT FROM 'no aplicada') = 0,
           'aptitud: ambiguas no se suman'
) q
$tfm$;

DROP FUNCTION IF EXISTS tfm.publicar_periodo_procesos(varchar);
CREATE OR REPLACE FUNCTION tfm.publicar_periodo_procesos(p_periodo varchar)
RETURNS void
LANGUAGE plpgsql
AS $tfm$
DECLARE
    n_fail integer;
BEGIN
    IF p_periodo IS NULL OR btrim(p_periodo) = '' THEN
        RAISE EXCEPTION 'periodo vacio';
    END IF;

    LOCK TABLE tfm.proceso, tfm.adjudicacion, tfm.adjudicacion_ambigua
        IN EXCLUSIVE MODE;

    SELECT count(*) INTO n_fail
    FROM tfm.validar_stg_procesos(p_periodo, NULL, NULL, NULL)
    WHERE ok IS NOT TRUE
      AND control NOT IN (
          'unicidad_proceso_filas',
          'unicidad_adjudicacion_filas',
          'unicidad_ambigua_filas'
      );

    IF n_fail > 0 THEN
        RAISE EXCEPTION
            'validacion staging fallida (% controles). No se publica periodo %',
            n_fail, p_periodo;
    END IF;

    DELETE FROM tfm.adjudicacion WHERE periodo = p_periodo;
    DELETE FROM tfm.adjudicacion_ambigua WHERE periodo = p_periodo;
    DELETE FROM tfm.proceso WHERE periodo = p_periodo;

    INSERT INTO tfm.proceso
    SELECT * FROM tfm.stg_proceso WHERE periodo = p_periodo;

    INSERT INTO tfm.adjudicacion
    SELECT * FROM tfm.stg_adjudicacion WHERE periodo = p_periodo;

    INSERT INTO tfm.adjudicacion_ambigua
    SELECT * FROM tfm.stg_adjudicacion_ambigua WHERE periodo = p_periodo;
END;
$tfm$;
