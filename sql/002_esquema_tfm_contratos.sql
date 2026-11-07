-- Este script SQL crea y configura las tablas de contratos electrónicos de SECOP II en el esquema analítico tfm de PostgreSQL.

-- Define la estructura para almacenar los contratos, sus características y los controles de calidad. 
-- Incluye una tabla de preparación o staging y funciones que validan la unicidad, integridad y consistencia de los datos antes de publicarlos.

--La publicación se realiza por periodo y dentro de una transacción, garantizando que, si alguna validación falla,
--  los datos definitivos permanezcan sin cambios. No modifica el esquema `public` ni las tablas de procesos.

CREATE SCHEMA IF NOT EXISTS tfm;

CREATE TABLE IF NOT EXISTS tfm.contrato (
    periodo                         varchar(7)  NOT NULL,
    id_contrato                     text        NOT NULL,
    socrata_id                      text,
    n_filas_api                     bigint,
    n_socrata_id                    bigint,
    socrata_ids                     text        NOT NULL,
    campos_variables                text,
    hay_campos_variables            boolean,
    nombre_entidad                  text,
    nit_entidad                     text,
    departamento                    text,
    ciudad                          text,
    proveedor_adjudicado            text,
    documento_proveedor             text,
    tipodocproveedor                text,
    modalidad_de_contratacion       text,
    tipo_de_contrato                text,
    estado_contrato                 text,
    fecha_de_firma                  timestamp,
    fecha_de_inicio_del_contrato    timestamp,
    fecha_de_fin_del_contrato       timestamp,
    valor_del_contrato              numeric,
    valor_del_contrato_cero         boolean,
    valor_del_contrato_negativo     boolean,
    valor_del_contrato_extremo      boolean,
    valor_usable                    boolean     NOT NULL,
    valor_apto_modelo               boolean     NOT NULL,
    referencia_del_contrato         text,
    descripcion_del_proceso         text,
    codigo_de_categoria_principal   text,
    duracion_del_contrato           text,
    es_pyme                         text,
    es_grupo                        text,
    url_contrato                    text,
    es_bogota                       boolean,
    cod_municipio                   varchar(5),
    estado_homologacion             text,
    via_homologacion                text,
    nombre_municipio_divipola       text,
    nombre_departamento_divipola    text,
    departamento_ausente            boolean,
    ciudad_ausente                  boolean,
    nombre_entidad_ausente          boolean,
    proveedor_adjudicado_ausente    boolean,
    modalidad_de_contratacion_ausente boolean,
    PRIMARY KEY (periodo, id_contrato)
);

CREATE INDEX IF NOT EXISTS contrato_cod_municipio_idx
    ON tfm.contrato (periodo, cod_municipio);
CREATE INDEX IF NOT EXISTS contrato_homologacion_idx
    ON tfm.contrato (periodo, estado_homologacion);
CREATE INDEX IF NOT EXISTS contrato_valor_apto_idx
    ON tfm.contrato (periodo, valor_apto_modelo);

CREATE TABLE IF NOT EXISTS tfm.contrato_control (
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

CREATE TABLE IF NOT EXISTS tfm.stg_contrato (LIKE tfm.contrato INCLUDING DEFAULTS);
CREATE INDEX IF NOT EXISTS stg_contrato_periodo_idx
    ON tfm.stg_contrato (periodo, id_contrato);

DROP FUNCTION IF EXISTS tfm.validar_stg_contratos(varchar, bigint);
CREATE OR REPLACE FUNCTION tfm.validar_stg_contratos(
    p_periodo varchar,
    p_n_contrato bigint
)
RETURNS TABLE(control text, observado bigint, esperado bigint, ok boolean, nota text)
LANGUAGE sql
STABLE
AS $tfm$
WITH c AS (
    SELECT * FROM tfm.stg_contrato WHERE periodo = p_periodo
)
SELECT * FROM (
    SELECT 'unicidad_contrato_filas'::text,
           (SELECT count(*) FROM c),
           p_n_contrato,
           (SELECT count(*) FROM c) = p_n_contrato,
           'unicidad: filas staging vs Spark'::text
    UNION ALL
    SELECT 'unicidad_contrato_dup',
           (SELECT count(*) FROM c) - (SELECT count(DISTINCT id_contrato) FROM c),
           0,
           (SELECT count(*) FROM c) = (SELECT count(DISTINCT id_contrato) FROM c),
           'unicidad: duplicados de id_contrato'
    UNION ALL
    SELECT 'unicidad_periodo_ajeno_stg',
           (SELECT count(*) FROM tfm.stg_contrato WHERE periodo IS DISTINCT FROM p_periodo),
           0,
           (SELECT count(*) FROM tfm.stg_contrato WHERE periodo IS DISTINCT FROM p_periodo) = 0,
           'unicidad: staging solo del periodo a publicar'
    UNION ALL
    SELECT 'disponibilidad_id_vacio',
           (SELECT count(*) FROM c WHERE id_contrato IS NULL OR btrim(id_contrato) = ''),
           0,
           (SELECT count(*) FROM c WHERE id_contrato IS NULL OR btrim(id_contrato) = '') = 0,
           'disponibilidad: id_contrato'
    UNION ALL
    SELECT 'disponibilidad_socrata_vacio',
           (SELECT count(*) FROM c WHERE socrata_ids IS NULL OR btrim(socrata_ids) = ''),
           0,
           (SELECT count(*) FROM c WHERE socrata_ids IS NULL OR btrim(socrata_ids) = '') = 0,
           'disponibilidad: trazabilidad socrata_id'
    UNION ALL
    SELECT 'disponibilidad_usable_sin_monto',
           (SELECT count(*) FROM c WHERE valor_usable AND valor_del_contrato IS NULL),
           0,
           (SELECT count(*) FROM c WHERE valor_usable AND valor_del_contrato IS NULL) = 0,
           'disponibilidad: valor_usable exige monto'
    UNION ALL
    SELECT 'positividad_monto_negativo',
           (SELECT count(*) FROM c WHERE valor_del_contrato < 0),
           0,
           (SELECT count(*) FROM c WHERE valor_del_contrato < 0) = 0,
           'positividad: monto negativo'
    UNION ALL
    SELECT 'positividad_monto_cero',
           (SELECT count(*) FROM c WHERE valor_del_contrato_cero),
           NULL,
           TRUE,
           'positividad: monto = 0 (no aborta)'
    UNION ALL
    SELECT 'positividad_monto_extremo',
           (SELECT count(*) FROM c WHERE valor_del_contrato_extremo),
           NULL,
           TRUE,
           'positividad: monto > 1e12 (no aborta; se marca)'
    UNION ALL
    SELECT 'aptitud_modelo',
           (SELECT count(*) FROM c WHERE valor_apto_modelo),
           NULL,
           TRUE,
           'aptitud: usable, > 0 y no extremo'
    UNION ALL
    SELECT 'aptitud_fecha_firma_nula',
           (SELECT count(*) FROM c WHERE fecha_de_firma IS NULL),
           0,
           (SELECT count(*) FROM c WHERE fecha_de_firma IS NULL) = 0,
           'aptitud: fecha_de_firma (C3)'
) q
$tfm$;

DROP FUNCTION IF EXISTS tfm.publicar_periodo_contratos(varchar);
CREATE OR REPLACE FUNCTION tfm.publicar_periodo_contratos(p_periodo varchar)
RETURNS void
LANGUAGE plpgsql
AS $tfm$
DECLARE
    n_fail integer;
BEGIN
    IF p_periodo IS NULL OR btrim(p_periodo) = '' THEN
        RAISE EXCEPTION 'periodo vacio';
    END IF;

    LOCK TABLE tfm.contrato IN EXCLUSIVE MODE;

    SELECT count(*) INTO n_fail
    FROM tfm.validar_stg_contratos(p_periodo, NULL)
    WHERE ok IS NOT TRUE
      AND control NOT IN ('unicidad_contrato_filas');

    IF n_fail > 0 THEN
        RAISE EXCEPTION
            'validacion staging contratos fallida (% controles). No se publica periodo %',
            n_fail, p_periodo;
    END IF;

    DELETE FROM tfm.contrato WHERE periodo = p_periodo;
    INSERT INTO tfm.contrato
    SELECT * FROM tfm.stg_contrato WHERE periodo = p_periodo;
END;
$tfm$;
