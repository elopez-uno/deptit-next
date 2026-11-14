--
-- PostgreSQL database dump
--

\restrict 9oMaUDkKZlHODd2y1wYniVQoMs25cB32mEb5pX6MLNzFo2AY4JKCduGvUIgP6qC

-- Dumped from database version 18.4
-- Dumped by pg_dump version 18.4

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: public; Type: SCHEMA; Schema: -; Owner: -
--

-- *not* creating schema, since initdb creates it


--
-- Name: SCHEMA public; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA public IS '';


--
-- Name: b12h_audit_log_append_only(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.b12h_audit_log_append_only() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    RAISE EXCEPTION 'b12h_audit_log es append-only (%)', TG_OP USING ERRCODE = '42501';
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: acciones_gestion; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.acciones_gestion (
    id bigint NOT NULL,
    institucion_id bigint NOT NULL,
    departamento_id bigint,
    periodo_id bigint,
    fingerprint text NOT NULL,
    gravedad text,
    categoria text,
    titulo text,
    detalle text,
    accion_sugerida text,
    responsable_email text,
    fecha_objetivo date,
    estado text DEFAULT 'Pendiente'::text,
    pospuesta_hasta date,
    origen text DEFAULT 'Regla'::text,
    entidad_tipo text,
    entidad_clave text,
    fecha_deteccion timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    fecha_resolucion timestamp without time zone,
    resolucion text
);


--
-- Name: acciones_gestion_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.acciones_gestion_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: acciones_gestion_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.acciones_gestion_id_seq OWNED BY public.acciones_gestion.id;


--
-- Name: actividad_especial_docente; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.actividad_especial_docente (
    id bigint NOT NULL,
    institucion_id bigint NOT NULL,
    departamento_id bigint,
    actividad_id bigint NOT NULL,
    periodo_id bigint NOT NULL,
    cuil text NOT NULL,
    rol text NOT NULL,
    estado_asignacion text DEFAULT 'Activa'::text,
    observaciones text,
    fecha_carga text
);


--
-- Name: actividad_especial_docente_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.actividad_especial_docente_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: actividad_especial_docente_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.actividad_especial_docente_id_seq OWNED BY public.actividad_especial_docente.id;


--
-- Name: actividades_especiales; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.actividades_especiales (
    id bigint NOT NULL,
    institucion_id bigint NOT NULL,
    departamento_id bigint,
    periodo_id bigint NOT NULL,
    titulo text NOT NULL,
    descripcion text,
    estado text DEFAULT 'Activa'::text,
    observaciones text,
    fecha_carga text
);


--
-- Name: actividades_especiales_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.actividades_especiales_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: actividades_especiales_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.actividades_especiales_id_seq OWNED BY public.actividades_especiales.id;


--
-- Name: app_usuarios; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.app_usuarios (
    id bigint NOT NULL,
    sqlite_id integer,
    source_db text,
    institucion_id bigint,
    departamento_id bigint,
    nombre text,
    email text NOT NULL,
    rol text NOT NULL,
    salt text,
    password_hash text,
    estado text DEFAULT 'Activo'::text,
    fecha_alta text,
    observaciones text
);


--
-- Name: app_usuarios_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.app_usuarios_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: app_usuarios_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.app_usuarios_id_seq OWNED BY public.app_usuarios.id;


--
-- Name: asignaciones_docentes_comision; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.asignaciones_docentes_comision (
    id bigint NOT NULL,
    sqlite_id integer,
    source_db text,
    institucion_id bigint,
    departamento_id bigint,
    comision_id bigint,
    cuil text,
    rol text,
    horas_asignadas numeric,
    estado text,
    observaciones text,
    usa_horario_personalizado boolean DEFAULT false
);


--
-- Name: asignaciones_docentes_comision_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.asignaciones_docentes_comision_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: asignaciones_docentes_comision_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.asignaciones_docentes_comision_id_seq OWNED BY public.asignaciones_docentes_comision.id;


--
-- Name: auditoria_eventos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auditoria_eventos (
    id bigint NOT NULL,
    institucion_id bigint NOT NULL,
    departamento_id bigint,
    fecha_hora timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    usuario_email text,
    usuario_rol text,
    modulo text,
    accion text,
    entidad_tipo text,
    entidad_clave text,
    detalle text,
    datos_json text,
    resultado text DEFAULT 'OK'::text
);


--
-- Name: auditoria_eventos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.auditoria_eventos_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: auditoria_eventos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.auditoria_eventos_id_seq OWNED BY public.auditoria_eventos.id;


--
-- Name: auth_login_throttle; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_login_throttle (
    subject_key text NOT NULL,
    failures integer DEFAULT 0 NOT NULL,
    window_started_epoch double precision NOT NULL,
    locked_until_epoch double precision,
    updated_epoch double precision NOT NULL,
    CONSTRAINT auth_login_throttle_failures_nonneg CHECK ((failures >= 0)),
    CONSTRAINT auth_login_throttle_subject_key_len CHECK ((length(subject_key) = 70))
);


--
-- Name: b12h_audit_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.b12h_audit_log (
    audit_id uuid NOT NULL,
    occurred_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    correlation_id uuid NOT NULL,
    event_seq integer NOT NULL,
    event_version smallint NOT NULL,
    subsystem text NOT NULL,
    app_batch text NOT NULL,
    actor_kind text NOT NULL,
    actor_source text NOT NULL,
    actor_user_id bigint,
    actor_email_normalized text,
    actor_role text,
    actor_is_superadmin boolean DEFAULT false NOT NULL,
    actor_home_institucion_id bigint,
    actor_home_departamento_id bigint,
    institucion_id bigint,
    departamento_id bigint,
    scope_source text NOT NULL,
    session_ref text,
    operation text NOT NULL,
    action text NOT NULL,
    action_scope text NOT NULL,
    entity_type text NOT NULL,
    entity_id text,
    outcome text NOT NULL,
    audit_mode text NOT NULL,
    error_code text,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    CONSTRAINT b12h_audit_log_action_scope_ck CHECK ((action_scope = ANY (ARRAY['department'::text, 'institution'::text, 'global'::text]))),
    CONSTRAINT b12h_audit_log_actor_kind_ck CHECK ((actor_kind = ANY (ARRAY['USER'::text, 'SYSTEM'::text, 'UNVERIFIED'::text, 'ANONYMOUS'::text]))),
    CONSTRAINT b12h_audit_log_actor_source_ck CHECK ((actor_source = ANY (ARRAY['B12G_REVALIDATED_DB'::text, 'B10_SYSTEM_ELEVATION'::text, 'NONE'::text]))),
    CONSTRAINT b12h_audit_log_event_seq_pos CHECK ((event_seq >= 1)),
    CONSTRAINT b12h_audit_log_lengths_ck CHECK (((length(operation) <= 128) AND (length(action) <= 64) AND (length(entity_type) <= 64) AND ((entity_id IS NULL) OR (length(entity_id) <= 64)) AND ((error_code IS NULL) OR (length(error_code) <= 105)) AND ((actor_email_normalized IS NULL) OR (length(actor_email_normalized) <= 320)) AND ((session_ref IS NULL) OR (length(session_ref) = 32)))),
    CONSTRAINT b12h_audit_log_metadata_ck CHECK ((jsonb_typeof(metadata) = 'object'::text)),
    CONSTRAINT b12h_audit_log_mode_ck CHECK ((audit_mode = ANY (ARRAY['IN_TRANSACTION'::text, 'POST_OPERATION'::text, 'SEPARATE_TRANSACTION'::text]))),
    CONSTRAINT b12h_audit_log_nonuser_actor_ck CHECK (((actor_kind = 'USER'::text) OR ((actor_user_id IS NULL) AND (actor_email_normalized IS NULL) AND (actor_source <> 'B12G_REVALIDATED_DB'::text)))),
    CONSTRAINT b12h_audit_log_other_mode_ck CHECK (((outcome = 'SUCCESS'::text) OR (audit_mode = 'SEPARATE_TRANSACTION'::text))),
    CONSTRAINT b12h_audit_log_outcome_ck CHECK ((outcome = ANY (ARRAY['SUCCESS'::text, 'DENIED'::text, 'FAILED'::text]))),
    CONSTRAINT b12h_audit_log_scope_source_ck CHECK ((scope_source = ANY (ARRAY['ACTOR_HOME'::text, 'SUPERADMIN_SELECTED'::text, 'SESSION_FOR_SYSTEM_TASK'::text, 'NONE'::text]))),
    CONSTRAINT b12h_audit_log_success_actor_ck CHECK (((outcome <> 'SUCCESS'::text) OR (actor_kind = ANY (ARRAY['USER'::text, 'SYSTEM'::text])))),
    CONSTRAINT b12h_audit_log_success_error_ck CHECK (((outcome <> 'SUCCESS'::text) OR (error_code IS NULL))),
    CONSTRAINT b12h_audit_log_success_mode_ck CHECK (((outcome <> 'SUCCESS'::text) OR (audit_mode = ANY (ARRAY['IN_TRANSACTION'::text, 'POST_OPERATION'::text])))),
    CONSTRAINT b12h_audit_log_superadmin_ck CHECK ((actor_is_superadmin = ((actor_kind = 'USER'::text) AND (actor_role = 'superadmin'::text)))),
    CONSTRAINT b12h_audit_log_user_actor_ck CHECK (((actor_kind <> 'USER'::text) OR ((actor_user_id IS NOT NULL) AND (actor_user_id > 0) AND (actor_source = 'B12G_REVALIDATED_DB'::text))))
);


--
-- Name: carreras; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.carreras (
    id bigint NOT NULL,
    sqlite_id integer,
    source_db text,
    institucion_id bigint,
    escuela text,
    nombre text,
    codigo text,
    titulo_otorga text,
    plan_version text,
    duracion text,
    estado text DEFAULT 'Activa'::text,
    observaciones text
);


--
-- Name: carreras_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.carreras_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: carreras_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.carreras_id_seq OWNED BY public.carreras.id;


--
-- Name: checklist_periodo; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.checklist_periodo (
    id bigint NOT NULL,
    institucion_id bigint NOT NULL,
    departamento_id bigint,
    periodo_id bigint NOT NULL,
    item_clave text NOT NULL,
    estado_manual text,
    observaciones text,
    actualizado_por text,
    fecha_actualizacion timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: checklist_periodo_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.checklist_periodo_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: checklist_periodo_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.checklist_periodo_id_seq OWNED BY public.checklist_periodo.id;


--
-- Name: comision_materias; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.comision_materias (
    id bigint NOT NULL,
    institucion_id bigint NOT NULL,
    departamento_id bigint,
    comision_id bigint NOT NULL,
    materia_id bigint NOT NULL,
    carrera_id_snapshot bigint,
    carrera_snapshot text,
    escuela_snapshot text,
    plan_version_snapshot text,
    anio_snapshot text,
    cuatrimestre_snapshot text,
    dictado_snapshot text,
    carga_semanal_snapshot text,
    carga_total_snapshot text,
    codigo_snapshot text,
    asignatura_snapshot text,
    fecha_vinculacion text,
    origen text
);


--
-- Name: comision_materias_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.comision_materias_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: comision_materias_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.comision_materias_id_seq OWNED BY public.comision_materias.id;


--
-- Name: comisiones; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.comisiones (
    id bigint NOT NULL,
    sqlite_id integer,
    source_db text,
    institucion_id bigint,
    departamento_id bigint,
    periodo_id bigint,
    materia_id bigint,
    nombre_comision text,
    turno text,
    sede text,
    modalidad text,
    estado text DEFAULT 'Activa'::text,
    observaciones text,
    fecha_creacion text,
    materia_especifica text,
    opcion_curricular_id bigint
);


--
-- Name: comisiones_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.comisiones_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: comisiones_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.comisiones_id_seq OWNED BY public.comisiones.id;


--
-- Name: config_disposiciones; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.config_disposiciones (
    id bigint NOT NULL,
    sqlite_id integer,
    source_db text,
    institucion_id bigint,
    departamento_id bigint,
    universidad text,
    departamento text,
    ciudad text,
    lema text,
    rector_nombre text,
    rector_dni text,
    rector_periodo_desde text,
    rector_periodo_hasta text,
    director_nombre text,
    director_dni text,
    resolucion_director_tipo text,
    resolucion_director_numero text,
    resolucion_director_anio text,
    expediente_cudap text,
    secretaria_notificacion text,
    observaciones text
);


--
-- Name: config_disposiciones_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.config_disposiciones_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: config_disposiciones_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.config_disposiciones_id_seq OWNED BY public.config_disposiciones.id;


--
-- Name: config_integraciones; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.config_integraciones (
    id bigint NOT NULL,
    institucion_id bigint NOT NULL,
    departamento_id bigint,
    clave text NOT NULL,
    estado text DEFAULT 'Inactiva'::text,
    valor_json text,
    fecha_actualizacion timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    actualizado_por text
);


--
-- Name: config_integraciones_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.config_integraciones_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: config_integraciones_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.config_integraciones_id_seq OWNED BY public.config_integraciones.id;


--
-- Name: config_productividad_departamento; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.config_productividad_departamento (
    id bigint NOT NULL,
    institucion_id bigint NOT NULL,
    departamento_id bigint NOT NULL,
    porcentaje_horas_no_lectivas double precision DEFAULT 0 CONSTRAINT config_productividad_depart_porcentaje_horas_no_lectiv_not_null NOT NULL,
    fecha_actualizacion timestamp without time zone
);


--
-- Name: config_productividad_departamento_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.config_productividad_departamento_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: config_productividad_departamento_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.config_productividad_departamento_id_seq OWNED BY public.config_productividad_departamento.id;


--
-- Name: correcciones_historial_horas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.correcciones_historial_horas (
    id bigint NOT NULL,
    institucion_id bigint NOT NULL,
    departamento_id bigint NOT NULL,
    periodo_id bigint NOT NULL,
    cuil text NOT NULL,
    horas_inicio_reales real NOT NULL,
    motivo text,
    fecha_actualizacion text
);


--
-- Name: correcciones_historial_horas_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.correcciones_historial_horas_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: correcciones_historial_horas_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.correcciones_historial_horas_id_seq OWNED BY public.correcciones_historial_horas.id;


--
-- Name: departamentos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.departamentos (
    id bigint NOT NULL,
    sqlite_id integer,
    source_db text,
    institucion_id bigint,
    nombre text NOT NULL,
    slug text NOT NULL,
    estado text DEFAULT 'Activo'::text,
    observaciones text
);


--
-- Name: departamentos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.departamentos_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: departamentos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.departamentos_id_seq OWNED BY public.departamentos.id;


--
-- Name: dependencias_documentales; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dependencias_documentales (
    id bigint NOT NULL,
    institucion_id bigint NOT NULL,
    nombre text NOT NULL,
    estado text DEFAULT 'Activa'::text,
    observaciones text,
    fecha_creacion timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: dependencias_documentales_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.dependencias_documentales_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: dependencias_documentales_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.dependencias_documentales_id_seq OWNED BY public.dependencias_documentales.id;


--
-- Name: designaciones; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.designaciones (
    id bigint NOT NULL,
    sqlite_id integer,
    source_db text,
    institucion_id bigint,
    departamento_id bigint,
    cuil text,
    cargo text,
    dedicacion text,
    horas integer,
    tipo_designacion text,
    ad_honorem text,
    fecha_desde text,
    fecha_hasta text,
    estado text,
    observaciones text,
    periodo_id bigint,
    resolucion_id bigint,
    fecha_hasta_prevista text,
    fecha_finalizacion_efectiva text,
    fecha_registro_finalizacion text,
    motivo_finalizacion text,
    numero_resolucion text,
    funcion_no_docente integer DEFAULT 0,
    texto_funcion_no_docente text
);


--
-- Name: designaciones_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.designaciones_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: designaciones_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.designaciones_id_seq OWNED BY public.designaciones.id;


--
-- Name: disposicion_docente_designaciones; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.disposicion_docente_designaciones (
    id bigint NOT NULL,
    institucion_id bigint NOT NULL,
    designacion_id bigint,
    cuil text NOT NULL,
    departamento_id bigint,
    tipo_designacion text,
    cargo text,
    dedicacion text,
    resolucion text,
    fecha_desde text,
    fecha_hasta text,
    observaciones text,
    fecha_actualizacion text
);


--
-- Name: disposicion_docente_designaciones_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.disposicion_docente_designaciones_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: disposicion_docente_designaciones_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.disposicion_docente_designaciones_id_seq OWNED BY public.disposicion_docente_designaciones.id;


--
-- Name: disposicion_docente_parametros; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.disposicion_docente_parametros (
    id bigint NOT NULL,
    sqlite_id integer,
    source_db text,
    institucion_id bigint,
    departamento_id bigint,
    cuil text,
    resolucion_cs_concursado text,
    fecha_desde_concursado text,
    fecha_hasta_concursado text,
    resolucion_cs_interino text,
    fecha_desde_interino text,
    fecha_hasta_interino text,
    codigo_proyecto text,
    instituto_proyecto text,
    observaciones text,
    texto_funcion_disposicion text
);


--
-- Name: disposicion_docente_parametros_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.disposicion_docente_parametros_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: disposicion_docente_parametros_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.disposicion_docente_parametros_id_seq OWNED BY public.disposicion_docente_parametros.id;


--
-- Name: disposicion_parametros; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.disposicion_parametros (
    id bigint NOT NULL,
    sqlite_id integer,
    source_db text,
    institucion_id bigint,
    departamento_id bigint,
    clave text,
    valor text
);


--
-- Name: disposicion_parametros_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.disposicion_parametros_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: disposicion_parametros_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.disposicion_parametros_id_seq OWNED BY public.disposicion_parametros.id;


--
-- Name: disposiciones; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.disposiciones (
    id bigint NOT NULL,
    sqlite_id integer,
    source_db text,
    institucion_id bigint,
    departamento_id bigint,
    periodo_id bigint,
    fecha text,
    tipo text,
    numero text,
    detalle text,
    observaciones text,
    anio integer,
    docente_cuil text,
    estado text DEFAULT 'Borrador'::text,
    texto text,
    fecha_carga text,
    cuil text,
    docente text,
    archivo_word text,
    plantilla_usada text,
    variables_json text,
    fecha_creacion text
);


--
-- Name: disposiciones_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.disposiciones_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: disposiciones_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.disposiciones_id_seq OWNED BY public.disposiciones.id;


--
-- Name: docentes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.docentes (
    id bigint NOT NULL,
    sqlite_id integer,
    source_db text,
    institucion_id bigint,
    departamento_id bigint,
    cuil text,
    nombre text,
    legajo text,
    titulo text,
    ref_legajo_fisico text,
    apellido text,
    nombres text,
    email text,
    telefono text,
    estado text DEFAULT 'Activo'::text,
    fecha_alta text,
    fecha_finalizacion text,
    tipo_docente text DEFAULT 'Propio'::text,
    observaciones text,
    titulo_posgrado text,
    antiguedad_anios integer,
    nivel_posgrado_salarial text
);


--
-- Name: docentes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.docentes_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: docentes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.docentes_id_seq OWNED BY public.docentes.id;


--
-- Name: documentos_respaldo; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.documentos_respaldo (
    id bigint NOT NULL,
    institucion_id bigint NOT NULL,
    departamento_id bigint NOT NULL,
    tipo_documento text NOT NULL,
    categoria text NOT NULL,
    numero text,
    fecha date,
    periodo_id bigint,
    cuil text,
    docente_nombre text,
    proyecto_tipo text,
    proyecto_id bigint,
    referencia_texto text,
    titulo text,
    detalle text,
    observaciones text,
    archivo_nombre text NOT NULL,
    archivo_mime text DEFAULT 'application/pdf'::text,
    archivo_pdf bytea NOT NULL,
    archivo_bytes bigint DEFAULT 0,
    fecha_carga timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    usuario_carga text,
    tipo_resolucion text,
    dependencia_id bigint,
    dependencia_nombre text
);


--
-- Name: documentos_respaldo_designaciones; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.documentos_respaldo_designaciones (
    id bigint NOT NULL,
    institucion_id bigint NOT NULL,
    departamento_id bigint NOT NULL,
    documento_id bigint NOT NULL,
    designacion_id bigint NOT NULL,
    fecha_vinculacion timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    usuario_vinculacion text
);


--
-- Name: documentos_respaldo_designaciones_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.documentos_respaldo_designaciones_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: documentos_respaldo_designaciones_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.documentos_respaldo_designaciones_id_seq OWNED BY public.documentos_respaldo_designaciones.id;


--
-- Name: documentos_respaldo_docentes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.documentos_respaldo_docentes (
    id bigint NOT NULL,
    institucion_id bigint NOT NULL,
    departamento_id bigint NOT NULL,
    documento_id bigint NOT NULL,
    cuil text NOT NULL,
    docente_nombre text,
    fecha_vinculacion timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    tipo_movimiento text,
    detalle_vinculo text
);


--
-- Name: documentos_respaldo_docentes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.documentos_respaldo_docentes_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: documentos_respaldo_docentes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.documentos_respaldo_docentes_id_seq OWNED BY public.documentos_respaldo_docentes.id;


--
-- Name: documentos_respaldo_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.documentos_respaldo_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: documentos_respaldo_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.documentos_respaldo_id_seq OWNED BY public.documentos_respaldo.id;


--
-- Name: documentos_respaldo_movimientos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.documentos_respaldo_movimientos (
    id bigint NOT NULL,
    institucion_id bigint NOT NULL,
    departamento_id bigint NOT NULL,
    documento_id bigint NOT NULL,
    movimiento_id bigint NOT NULL,
    fecha_vinculacion timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    usuario_vinculacion text
);


--
-- Name: documentos_respaldo_movimientos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.documentos_respaldo_movimientos_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: documentos_respaldo_movimientos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.documentos_respaldo_movimientos_id_seq OWNED BY public.documentos_respaldo_movimientos.id;


--
-- Name: documentos_respaldo_proyectos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.documentos_respaldo_proyectos (
    id bigint NOT NULL,
    institucion_id bigint NOT NULL,
    departamento_id bigint NOT NULL,
    documento_id bigint NOT NULL,
    proyecto_tipo text NOT NULL,
    proyecto_id bigint NOT NULL,
    proyecto_nombre text,
    codigo_proyecto text,
    fecha_vinculacion timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: documentos_respaldo_proyectos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.documentos_respaldo_proyectos_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: documentos_respaldo_proyectos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.documentos_respaldo_proyectos_id_seq OWNED BY public.documentos_respaldo_proyectos.id;


--
-- Name: escalas_salariales_docentes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.escalas_salariales_docentes (
    id bigint NOT NULL,
    institucion_id bigint NOT NULL,
    mes_referencia text NOT NULL,
    cargo text NOT NULL,
    basico_simple numeric(16,2) DEFAULT 0 NOT NULL,
    fecha_actualizacion timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    usuario_actualizacion text
);


--
-- Name: escalas_salariales_docentes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.escalas_salariales_docentes_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: escalas_salariales_docentes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.escalas_salariales_docentes_id_seq OWNED BY public.escalas_salariales_docentes.id;


--
-- Name: estado_consulta_designacion; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.estado_consulta_designacion (
    id bigint NOT NULL,
    institucion_id bigint NOT NULL,
    departamento_id bigint NOT NULL,
    periodo_id bigint NOT NULL,
    cuil text NOT NULL,
    estado text NOT NULL,
    fecha_actualizacion text
);


--
-- Name: estado_consulta_designacion_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.estado_consulta_designacion_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: estado_consulta_designacion_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.estado_consulta_designacion_id_seq OWNED BY public.estado_consulta_designacion.id;


--
-- Name: eventos_producto; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.eventos_producto (
    id bigint NOT NULL,
    institucion_id bigint NOT NULL,
    departamento_id bigint,
    fecha_hora timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    usuario_email text,
    modulo text,
    evento text,
    entidad_tipo text,
    entidad_clave text,
    duracion_ms double precision,
    exito integer DEFAULT 1,
    metadata_json text
);


--
-- Name: eventos_producto_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.eventos_producto_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: eventos_producto_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.eventos_producto_id_seq OWNED BY public.eventos_producto.id;


--
-- Name: extension_docente; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.extension_docente (
    id bigint NOT NULL,
    institucion_id bigint NOT NULL,
    departamento_id bigint,
    proyecto_id bigint,
    periodo_id bigint,
    cuil text,
    nombre_proyecto text,
    rol text,
    anio_llamado integer,
    periodo_ejecucion text,
    horas_asignadas real,
    observaciones text,
    fecha_carga text,
    codigo_proyecto text,
    instituto_proyecto text,
    estado_asignacion text DEFAULT 'Activa'::text,
    fecha_baja text,
    motivo_baja text
);


--
-- Name: extension_docente_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.extension_docente_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: extension_docente_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.extension_docente_id_seq OWNED BY public.extension_docente.id;


--
-- Name: horarios_asignacion_docente_comision; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.horarios_asignacion_docente_comision (
    id bigint NOT NULL,
    institucion_id bigint NOT NULL,
    departamento_id bigint,
    asignacion_id bigint NOT NULL,
    horario_comision_id bigint,
    dia text NOT NULL,
    hora_inicio text NOT NULL,
    hora_fin text NOT NULL,
    horas real DEFAULT 0,
    observaciones text
);


--
-- Name: horarios_asignacion_docente_comision_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.horarios_asignacion_docente_comision_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: horarios_asignacion_docente_comision_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.horarios_asignacion_docente_comision_id_seq OWNED BY public.horarios_asignacion_docente_comision.id;


--
-- Name: horarios_comision; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.horarios_comision (
    id bigint NOT NULL,
    sqlite_id integer,
    source_db text,
    institucion_id bigint,
    departamento_id bigint,
    comision_id bigint,
    dia text,
    hora_inicio text,
    hora_fin text,
    horas numeric,
    observaciones text
);


--
-- Name: horarios_comision_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.horarios_comision_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: horarios_comision_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.horarios_comision_id_seq OWNED BY public.horarios_comision.id;


--
-- Name: inscriptos_asignatura_periodo; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.inscriptos_asignatura_periodo (
    id bigint NOT NULL,
    institucion_id bigint NOT NULL,
    departamento_id bigint,
    periodo_id bigint NOT NULL,
    materia_id bigint NOT NULL,
    opcion_curricular_id bigint DEFAULT 0 NOT NULL,
    cantidad integer DEFAULT 0,
    cantidad_final integer,
    fecha_actualizacion text,
    fecha_actualizacion_final text,
    observaciones text
);


--
-- Name: inscriptos_asignatura_periodo_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.inscriptos_asignatura_periodo_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: inscriptos_asignatura_periodo_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.inscriptos_asignatura_periodo_id_seq OWNED BY public.inscriptos_asignatura_periodo.id;


--
-- Name: inscriptos_comision; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.inscriptos_comision (
    id bigint NOT NULL,
    institucion_id bigint NOT NULL,
    departamento_id bigint,
    comision_id bigint NOT NULL,
    cantidad integer DEFAULT 0,
    fecha_actualizacion text,
    observaciones text,
    cantidad_final integer,
    fecha_actualizacion_final text
);


--
-- Name: inscriptos_comision_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.inscriptos_comision_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: inscriptos_comision_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.inscriptos_comision_id_seq OWNED BY public.inscriptos_comision.id;


--
-- Name: inscriptos_comision_materia; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.inscriptos_comision_materia (
    id bigint NOT NULL,
    institucion_id bigint NOT NULL,
    departamento_id bigint,
    comision_id bigint NOT NULL,
    materia_id bigint NOT NULL,
    cantidad integer DEFAULT 0,
    cantidad_final integer,
    fecha_actualizacion text,
    fecha_actualizacion_final text,
    observaciones text
);


--
-- Name: inscriptos_comision_materia_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.inscriptos_comision_materia_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: inscriptos_comision_materia_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.inscriptos_comision_materia_id_seq OWNED BY public.inscriptos_comision_materia.id;


--
-- Name: instituciones; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.instituciones (
    id bigint NOT NULL,
    sqlite_id integer,
    source_db text,
    nombre text NOT NULL,
    slug text NOT NULL,
    max_usuarios integer DEFAULT 5,
    estado text DEFAULT 'Activa'::text,
    plan text DEFAULT 'Institucional'::text,
    fecha_alta text,
    fecha_vencimiento text,
    estado_pago text DEFAULT 'Activo'::text,
    suscripcion text DEFAULT 'Activa'::text,
    fecha_ultima_actualizacion_comercial text,
    observaciones text
);


--
-- Name: instituciones_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.instituciones_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: instituciones_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.instituciones_id_seq OWNED BY public.instituciones.id;


--
-- Name: investigacion_docente; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.investigacion_docente (
    id bigint NOT NULL,
    sqlite_id integer,
    source_db text,
    institucion_id bigint,
    departamento_id bigint,
    periodo_id bigint,
    cuil text,
    nombre_proyecto text,
    rol text,
    anio_llamado integer,
    periodo_ejecucion text,
    horas_asignadas numeric,
    observaciones text,
    fecha_carga text,
    codigo_proyecto text,
    instituto_proyecto text,
    proyecto_id bigint,
    estado_asignacion text DEFAULT 'Activa'::text,
    fecha_baja text,
    motivo_baja text
);


--
-- Name: investigacion_docente_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.investigacion_docente_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: investigacion_docente_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.investigacion_docente_id_seq OWNED BY public.investigacion_docente.id;


--
-- Name: materias; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.materias (
    id bigint NOT NULL,
    sqlite_id integer,
    source_db text,
    institucion_id bigint,
    carrera_id bigint,
    codigo text,
    asignatura text,
    carrera text,
    escuela text,
    anio text,
    dictado text,
    carga_semanal numeric,
    carga_total numeric,
    cuatrimestre text,
    duracion text,
    plan_version text,
    orden integer,
    estado text DEFAULT 'Activa'::text,
    observaciones text,
    en_plan integer DEFAULT 1,
    comparticion_modo text DEFAULT 'Automática'::text,
    comparticion_grupo text
);


--
-- Name: materias_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.materias_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: materias_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.materias_id_seq OWNED BY public.materias.id;


--
-- Name: movimientos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.movimientos (
    id bigint NOT NULL,
    sqlite_id integer,
    source_db text,
    institucion_id bigint,
    departamento_id bigint,
    fecha text,
    tipo_movimiento text,
    cuil text,
    nombre text,
    legajo text,
    titulo text,
    cargo text,
    dedicacion text,
    horas integer,
    tipo_designacion text,
    motivo text,
    ref_legajo_fisico text,
    obs text,
    detalle text,
    observaciones text,
    periodo_id bigint,
    horas_variacion numeric DEFAULT 0
);


--
-- Name: movimientos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.movimientos_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: movimientos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.movimientos_id_seq OWNED BY public.movimientos.id;


--
-- Name: opcion_curricular_materias; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.opcion_curricular_materias (
    id bigint NOT NULL,
    institucion_id bigint NOT NULL,
    opcion_id bigint NOT NULL,
    materia_id bigint NOT NULL,
    fecha_vinculacion text
);


--
-- Name: opcion_curricular_materias_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.opcion_curricular_materias_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: opcion_curricular_materias_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.opcion_curricular_materias_id_seq OWNED BY public.opcion_curricular_materias.id;


--
-- Name: opciones_curriculares; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.opciones_curriculares (
    id bigint NOT NULL,
    institucion_id bigint NOT NULL,
    tipo text NOT NULL,
    codigo text,
    nombre text NOT NULL,
    escuela_oferente text,
    estado text DEFAULT 'Activa'::text,
    observaciones text,
    fecha_creacion text,
    fecha_actualizacion text
);


--
-- Name: opciones_curriculares_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.opciones_curriculares_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: opciones_curriculares_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.opciones_curriculares_id_seq OWNED BY public.opciones_curriculares.id;


--
-- Name: parametros_sueldos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.parametros_sueldos (
    id bigint NOT NULL,
    sqlite_id integer,
    source_db text,
    institucion_id bigint,
    departamento_id bigint,
    fecha_desde text,
    cargo text,
    dedicacion text,
    antiguedad text,
    importe numeric,
    observaciones text
);


--
-- Name: parametros_sueldos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.parametros_sueldos_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: parametros_sueldos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.parametros_sueldos_id_seq OWNED BY public.parametros_sueldos.id;


--
-- Name: periodos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.periodos (
    id bigint NOT NULL,
    sqlite_id integer,
    source_db text,
    institucion_id bigint,
    departamento_id bigint,
    nombre text,
    anio integer,
    semestre integer,
    fecha_inicio text,
    fecha_fin text,
    estado text,
    observaciones text
);


--
-- Name: periodos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.periodos_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: periodos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.periodos_id_seq OWNED BY public.periodos.id;


--
-- Name: portal_docente_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.portal_docente_tokens (
    id bigint NOT NULL,
    institucion_id bigint NOT NULL,
    departamento_id bigint,
    periodo_id bigint NOT NULL,
    cuil text NOT NULL,
    token_hash text NOT NULL,
    estado text DEFAULT 'Activo'::text,
    fecha_creacion timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    fecha_vencimiento timestamp without time zone,
    fecha_respuesta timestamp without time zone,
    respuesta text,
    observaciones_docente text,
    creado_por text
);


--
-- Name: portal_docente_tokens_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.portal_docente_tokens_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: portal_docente_tokens_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.portal_docente_tokens_id_seq OWNED BY public.portal_docente_tokens.id;


--
-- Name: prestamos_docentes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.prestamos_docentes (
    id bigint NOT NULL,
    institucion_id bigint NOT NULL,
    departamento_id bigint NOT NULL,
    periodo_id bigint NOT NULL,
    cuil text NOT NULL,
    departamento_origen text,
    fecha_desde date,
    fecha_hasta date,
    estado text DEFAULT 'Activo'::text NOT NULL,
    observaciones text,
    fecha_registro text,
    fecha_finalizacion text
);


--
-- Name: prestamos_docentes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.prestamos_docentes_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: prestamos_docentes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.prestamos_docentes_id_seq OWNED BY public.prestamos_docentes.id;


--
-- Name: proyectos_extension; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.proyectos_extension (
    id bigint NOT NULL,
    institucion_id bigint NOT NULL,
    departamento_id bigint,
    nombre_proyecto text NOT NULL,
    codigo_proyecto text,
    instituto_proyecto text,
    anio_llamado integer,
    fecha_inicio date,
    fecha_fin date,
    periodo_ejecucion text,
    observaciones text,
    estado text DEFAULT 'Activo'::text,
    fecha_carga text,
    fecha_suspension date,
    motivo_suspension text
);


--
-- Name: proyectos_extension_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.proyectos_extension_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: proyectos_extension_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.proyectos_extension_id_seq OWNED BY public.proyectos_extension.id;


--
-- Name: proyectos_investigacion; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.proyectos_investigacion (
    id bigint NOT NULL,
    institucion_id bigint NOT NULL,
    departamento_id bigint,
    nombre_proyecto text NOT NULL,
    codigo_proyecto text,
    instituto_proyecto text,
    anio_llamado integer,
    periodo_ejecucion text,
    observaciones text,
    estado text DEFAULT 'Activo'::text,
    fecha_carga text,
    fecha_inicio date,
    fecha_fin date,
    fecha_suspension date,
    motivo_suspension text
);


--
-- Name: proyectos_investigacion_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.proyectos_investigacion_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: proyectos_investigacion_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.proyectos_investigacion_id_seq OWNED BY public.proyectos_investigacion.id;


--
-- Name: resoluciones; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.resoluciones (
    id bigint NOT NULL,
    sqlite_id integer,
    source_db text,
    institucion_id bigint,
    departamento_id bigint,
    tipo text,
    numero text,
    anio integer,
    fecha text,
    expediente text,
    detalle text,
    observaciones text
);


--
-- Name: resoluciones_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.resoluciones_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: resoluciones_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.resoluciones_id_seq OWNED BY public.resoluciones.id;


--
-- Name: roadmap_funciones; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.roadmap_funciones (
    id bigint NOT NULL,
    institucion_id bigint NOT NULL,
    departamento_id bigint,
    idea_id integer NOT NULL,
    categoria text,
    funcion text,
    prioridad text,
    complejidad text,
    estado text DEFAULT 'Idea'::text,
    responsable text,
    fecha_objetivo date,
    notas text,
    fecha_actualizacion timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: roadmap_funciones_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.roadmap_funciones_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: roadmap_funciones_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.roadmap_funciones_id_seq OWNED BY public.roadmap_funciones.id;


--
-- Name: saneamiento_v279_designaciones_backup; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.saneamiento_v279_designaciones_backup (
    id bigint NOT NULL,
    institucion_id bigint NOT NULL,
    departamento_id bigint NOT NULL,
    original_id bigint NOT NULL,
    fila jsonb NOT NULL,
    motivo text,
    fecha_backup timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: saneamiento_v279_designaciones_backup_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.saneamiento_v279_designaciones_backup_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: saneamiento_v279_designaciones_backup_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.saneamiento_v279_designaciones_backup_id_seq OWNED BY public.saneamiento_v279_designaciones_backup.id;


--
-- Name: saneamiento_v279_ejecuciones; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.saneamiento_v279_ejecuciones (
    id bigint NOT NULL,
    institucion_id bigint NOT NULL,
    departamento_id bigint NOT NULL,
    fecha timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    estado text NOT NULL,
    designaciones_detectadas integer DEFAULT 0,
    movimientos_detectados integer DEFAULT 0,
    detalle text
);


--
-- Name: saneamiento_v279_ejecuciones_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.saneamiento_v279_ejecuciones_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: saneamiento_v279_ejecuciones_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.saneamiento_v279_ejecuciones_id_seq OWNED BY public.saneamiento_v279_ejecuciones.id;


--
-- Name: saneamiento_v279_movimientos_backup; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.saneamiento_v279_movimientos_backup (
    id bigint NOT NULL,
    institucion_id bigint NOT NULL,
    departamento_id bigint NOT NULL,
    original_id bigint NOT NULL,
    fila jsonb NOT NULL,
    motivo text,
    fecha_backup timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: saneamiento_v279_movimientos_backup_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.saneamiento_v279_movimientos_backup_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: saneamiento_v279_movimientos_backup_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.saneamiento_v279_movimientos_backup_id_seq OWNED BY public.saneamiento_v279_movimientos_backup.id;


--
-- Name: sedes_institucion; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sedes_institucion (
    id bigint NOT NULL,
    institucion_id bigint NOT NULL,
    nombre text NOT NULL,
    direccion text,
    localidad text,
    estado text DEFAULT 'Activa'::text,
    observaciones text,
    fecha_creacion text,
    fecha_actualizacion text
);


--
-- Name: sedes_institucion_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sedes_institucion_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sedes_institucion_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sedes_institucion_id_seq OWNED BY public.sedes_institucion.id;


--
-- Name: sistema_flags; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sistema_flags (
    clave text NOT NULL,
    valor text
);


--
-- Name: vistas_guardadas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vistas_guardadas (
    id bigint NOT NULL,
    institucion_id bigint NOT NULL,
    departamento_id bigint,
    usuario_email text NOT NULL,
    modulo text NOT NULL,
    nombre text NOT NULL,
    configuracion_json text,
    fecha_creacion timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: vistas_guardadas_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vistas_guardadas_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vistas_guardadas_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vistas_guardadas_id_seq OWNED BY public.vistas_guardadas.id;


--
-- Name: acciones_gestion id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acciones_gestion ALTER COLUMN id SET DEFAULT nextval('public.acciones_gestion_id_seq'::regclass);


--
-- Name: actividad_especial_docente id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.actividad_especial_docente ALTER COLUMN id SET DEFAULT nextval('public.actividad_especial_docente_id_seq'::regclass);


--
-- Name: actividades_especiales id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.actividades_especiales ALTER COLUMN id SET DEFAULT nextval('public.actividades_especiales_id_seq'::regclass);


--
-- Name: app_usuarios id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.app_usuarios ALTER COLUMN id SET DEFAULT nextval('public.app_usuarios_id_seq'::regclass);


--
-- Name: asignaciones_docentes_comision id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.asignaciones_docentes_comision ALTER COLUMN id SET DEFAULT nextval('public.asignaciones_docentes_comision_id_seq'::regclass);


--
-- Name: auditoria_eventos id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auditoria_eventos ALTER COLUMN id SET DEFAULT nextval('public.auditoria_eventos_id_seq'::regclass);


--
-- Name: carreras id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.carreras ALTER COLUMN id SET DEFAULT nextval('public.carreras_id_seq'::regclass);


--
-- Name: checklist_periodo id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.checklist_periodo ALTER COLUMN id SET DEFAULT nextval('public.checklist_periodo_id_seq'::regclass);


--
-- Name: comision_materias id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comision_materias ALTER COLUMN id SET DEFAULT nextval('public.comision_materias_id_seq'::regclass);


--
-- Name: comisiones id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comisiones ALTER COLUMN id SET DEFAULT nextval('public.comisiones_id_seq'::regclass);


--
-- Name: config_disposiciones id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.config_disposiciones ALTER COLUMN id SET DEFAULT nextval('public.config_disposiciones_id_seq'::regclass);


--
-- Name: config_integraciones id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.config_integraciones ALTER COLUMN id SET DEFAULT nextval('public.config_integraciones_id_seq'::regclass);


--
-- Name: config_productividad_departamento id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.config_productividad_departamento ALTER COLUMN id SET DEFAULT nextval('public.config_productividad_departamento_id_seq'::regclass);


--
-- Name: correcciones_historial_horas id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.correcciones_historial_horas ALTER COLUMN id SET DEFAULT nextval('public.correcciones_historial_horas_id_seq'::regclass);


--
-- Name: departamentos id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departamentos ALTER COLUMN id SET DEFAULT nextval('public.departamentos_id_seq'::regclass);


--
-- Name: dependencias_documentales id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dependencias_documentales ALTER COLUMN id SET DEFAULT nextval('public.dependencias_documentales_id_seq'::regclass);


--
-- Name: designaciones id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.designaciones ALTER COLUMN id SET DEFAULT nextval('public.designaciones_id_seq'::regclass);


--
-- Name: disposicion_docente_designaciones id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.disposicion_docente_designaciones ALTER COLUMN id SET DEFAULT nextval('public.disposicion_docente_designaciones_id_seq'::regclass);


--
-- Name: disposicion_docente_parametros id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.disposicion_docente_parametros ALTER COLUMN id SET DEFAULT nextval('public.disposicion_docente_parametros_id_seq'::regclass);


--
-- Name: disposicion_parametros id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.disposicion_parametros ALTER COLUMN id SET DEFAULT nextval('public.disposicion_parametros_id_seq'::regclass);


--
-- Name: disposiciones id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.disposiciones ALTER COLUMN id SET DEFAULT nextval('public.disposiciones_id_seq'::regclass);


--
-- Name: docentes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.docentes ALTER COLUMN id SET DEFAULT nextval('public.docentes_id_seq'::regclass);


--
-- Name: documentos_respaldo id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documentos_respaldo ALTER COLUMN id SET DEFAULT nextval('public.documentos_respaldo_id_seq'::regclass);


--
-- Name: documentos_respaldo_designaciones id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documentos_respaldo_designaciones ALTER COLUMN id SET DEFAULT nextval('public.documentos_respaldo_designaciones_id_seq'::regclass);


--
-- Name: documentos_respaldo_docentes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documentos_respaldo_docentes ALTER COLUMN id SET DEFAULT nextval('public.documentos_respaldo_docentes_id_seq'::regclass);


--
-- Name: documentos_respaldo_movimientos id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documentos_respaldo_movimientos ALTER COLUMN id SET DEFAULT nextval('public.documentos_respaldo_movimientos_id_seq'::regclass);


--
-- Name: documentos_respaldo_proyectos id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documentos_respaldo_proyectos ALTER COLUMN id SET DEFAULT nextval('public.documentos_respaldo_proyectos_id_seq'::regclass);


--
-- Name: escalas_salariales_docentes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.escalas_salariales_docentes ALTER COLUMN id SET DEFAULT nextval('public.escalas_salariales_docentes_id_seq'::regclass);


--
-- Name: estado_consulta_designacion id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.estado_consulta_designacion ALTER COLUMN id SET DEFAULT nextval('public.estado_consulta_designacion_id_seq'::regclass);


--
-- Name: eventos_producto id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.eventos_producto ALTER COLUMN id SET DEFAULT nextval('public.eventos_producto_id_seq'::regclass);


--
-- Name: extension_docente id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.extension_docente ALTER COLUMN id SET DEFAULT nextval('public.extension_docente_id_seq'::regclass);


--
-- Name: horarios_asignacion_docente_comision id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.horarios_asignacion_docente_comision ALTER COLUMN id SET DEFAULT nextval('public.horarios_asignacion_docente_comision_id_seq'::regclass);


--
-- Name: horarios_comision id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.horarios_comision ALTER COLUMN id SET DEFAULT nextval('public.horarios_comision_id_seq'::regclass);


--
-- Name: inscriptos_asignatura_periodo id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inscriptos_asignatura_periodo ALTER COLUMN id SET DEFAULT nextval('public.inscriptos_asignatura_periodo_id_seq'::regclass);


--
-- Name: inscriptos_comision id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inscriptos_comision ALTER COLUMN id SET DEFAULT nextval('public.inscriptos_comision_id_seq'::regclass);


--
-- Name: inscriptos_comision_materia id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inscriptos_comision_materia ALTER COLUMN id SET DEFAULT nextval('public.inscriptos_comision_materia_id_seq'::regclass);


--
-- Name: instituciones id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.instituciones ALTER COLUMN id SET DEFAULT nextval('public.instituciones_id_seq'::regclass);


--
-- Name: investigacion_docente id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.investigacion_docente ALTER COLUMN id SET DEFAULT nextval('public.investigacion_docente_id_seq'::regclass);


--
-- Name: materias id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.materias ALTER COLUMN id SET DEFAULT nextval('public.materias_id_seq'::regclass);


--
-- Name: movimientos id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movimientos ALTER COLUMN id SET DEFAULT nextval('public.movimientos_id_seq'::regclass);


--
-- Name: opcion_curricular_materias id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.opcion_curricular_materias ALTER COLUMN id SET DEFAULT nextval('public.opcion_curricular_materias_id_seq'::regclass);


--
-- Name: opciones_curriculares id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.opciones_curriculares ALTER COLUMN id SET DEFAULT nextval('public.opciones_curriculares_id_seq'::regclass);


--
-- Name: parametros_sueldos id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parametros_sueldos ALTER COLUMN id SET DEFAULT nextval('public.parametros_sueldos_id_seq'::regclass);


--
-- Name: periodos id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.periodos ALTER COLUMN id SET DEFAULT nextval('public.periodos_id_seq'::regclass);


--
-- Name: portal_docente_tokens id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.portal_docente_tokens ALTER COLUMN id SET DEFAULT nextval('public.portal_docente_tokens_id_seq'::regclass);


--
-- Name: prestamos_docentes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prestamos_docentes ALTER COLUMN id SET DEFAULT nextval('public.prestamos_docentes_id_seq'::regclass);


--
-- Name: proyectos_extension id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proyectos_extension ALTER COLUMN id SET DEFAULT nextval('public.proyectos_extension_id_seq'::regclass);


--
-- Name: proyectos_investigacion id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proyectos_investigacion ALTER COLUMN id SET DEFAULT nextval('public.proyectos_investigacion_id_seq'::regclass);


--
-- Name: resoluciones id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resoluciones ALTER COLUMN id SET DEFAULT nextval('public.resoluciones_id_seq'::regclass);


--
-- Name: roadmap_funciones id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.roadmap_funciones ALTER COLUMN id SET DEFAULT nextval('public.roadmap_funciones_id_seq'::regclass);


--
-- Name: saneamiento_v279_designaciones_backup id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.saneamiento_v279_designaciones_backup ALTER COLUMN id SET DEFAULT nextval('public.saneamiento_v279_designaciones_backup_id_seq'::regclass);


--
-- Name: saneamiento_v279_ejecuciones id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.saneamiento_v279_ejecuciones ALTER COLUMN id SET DEFAULT nextval('public.saneamiento_v279_ejecuciones_id_seq'::regclass);


--
-- Name: saneamiento_v279_movimientos_backup id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.saneamiento_v279_movimientos_backup ALTER COLUMN id SET DEFAULT nextval('public.saneamiento_v279_movimientos_backup_id_seq'::regclass);


--
-- Name: sedes_institucion id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sedes_institucion ALTER COLUMN id SET DEFAULT nextval('public.sedes_institucion_id_seq'::regclass);


--
-- Name: vistas_guardadas id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vistas_guardadas ALTER COLUMN id SET DEFAULT nextval('public.vistas_guardadas_id_seq'::regclass);


--
-- Name: acciones_gestion acciones_gestion_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acciones_gestion
    ADD CONSTRAINT acciones_gestion_pkey PRIMARY KEY (id);


--
-- Name: actividad_especial_docente actividad_especial_docente_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.actividad_especial_docente
    ADD CONSTRAINT actividad_especial_docente_pkey PRIMARY KEY (id);


--
-- Name: actividades_especiales actividades_especiales_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.actividades_especiales
    ADD CONSTRAINT actividades_especiales_pkey PRIMARY KEY (id);


--
-- Name: app_usuarios app_usuarios_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.app_usuarios
    ADD CONSTRAINT app_usuarios_email_key UNIQUE (email);


--
-- Name: app_usuarios app_usuarios_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.app_usuarios
    ADD CONSTRAINT app_usuarios_pkey PRIMARY KEY (id);


--
-- Name: asignaciones_docentes_comision asignaciones_docentes_comisio_institucion_id_departamento_i_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.asignaciones_docentes_comision
    ADD CONSTRAINT asignaciones_docentes_comisio_institucion_id_departamento_i_key UNIQUE (institucion_id, departamento_id, sqlite_id);


--
-- Name: asignaciones_docentes_comision asignaciones_docentes_comision_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.asignaciones_docentes_comision
    ADD CONSTRAINT asignaciones_docentes_comision_pkey PRIMARY KEY (id);


--
-- Name: auditoria_eventos auditoria_eventos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auditoria_eventos
    ADD CONSTRAINT auditoria_eventos_pkey PRIMARY KEY (id);


--
-- Name: auth_login_throttle auth_login_throttle_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_login_throttle
    ADD CONSTRAINT auth_login_throttle_pkey PRIMARY KEY (subject_key);


--
-- Name: b12h_audit_log b12h_audit_log_correlation_seq_uq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b12h_audit_log
    ADD CONSTRAINT b12h_audit_log_correlation_seq_uq UNIQUE (correlation_id, event_seq);


--
-- Name: b12h_audit_log b12h_audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.b12h_audit_log
    ADD CONSTRAINT b12h_audit_log_pkey PRIMARY KEY (audit_id);


--
-- Name: carreras carreras_institucion_id_source_db_sqlite_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.carreras
    ADD CONSTRAINT carreras_institucion_id_source_db_sqlite_id_key UNIQUE (institucion_id, source_db, sqlite_id);


--
-- Name: carreras carreras_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.carreras
    ADD CONSTRAINT carreras_pkey PRIMARY KEY (id);


--
-- Name: checklist_periodo checklist_periodo_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.checklist_periodo
    ADD CONSTRAINT checklist_periodo_pkey PRIMARY KEY (id);


--
-- Name: comision_materias comision_materias_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comision_materias
    ADD CONSTRAINT comision_materias_pkey PRIMARY KEY (id);


--
-- Name: comisiones comisiones_institucion_id_departamento_id_sqlite_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comisiones
    ADD CONSTRAINT comisiones_institucion_id_departamento_id_sqlite_id_key UNIQUE (institucion_id, departamento_id, sqlite_id);


--
-- Name: comisiones comisiones_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comisiones
    ADD CONSTRAINT comisiones_pkey PRIMARY KEY (id);


--
-- Name: config_disposiciones config_disposiciones_institucion_id_departamento_id_sqlite__key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.config_disposiciones
    ADD CONSTRAINT config_disposiciones_institucion_id_departamento_id_sqlite__key UNIQUE (institucion_id, departamento_id, sqlite_id);


--
-- Name: config_disposiciones config_disposiciones_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.config_disposiciones
    ADD CONSTRAINT config_disposiciones_pkey PRIMARY KEY (id);


--
-- Name: config_integraciones config_integraciones_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.config_integraciones
    ADD CONSTRAINT config_integraciones_pkey PRIMARY KEY (id);


--
-- Name: config_productividad_departamento config_productividad_departam_institucion_id_departamento_i_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.config_productividad_departamento
    ADD CONSTRAINT config_productividad_departam_institucion_id_departamento_i_key UNIQUE (institucion_id, departamento_id);


--
-- Name: config_productividad_departamento config_productividad_departamento_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.config_productividad_departamento
    ADD CONSTRAINT config_productividad_departamento_pkey PRIMARY KEY (id);


--
-- Name: correcciones_historial_horas correcciones_historial_horas_institucion_id_departamento_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.correcciones_historial_horas
    ADD CONSTRAINT correcciones_historial_horas_institucion_id_departamento_id_key UNIQUE (institucion_id, departamento_id, periodo_id, cuil);


--
-- Name: correcciones_historial_horas correcciones_historial_horas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.correcciones_historial_horas
    ADD CONSTRAINT correcciones_historial_horas_pkey PRIMARY KEY (id);


--
-- Name: departamentos departamentos_institucion_id_slug_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departamentos
    ADD CONSTRAINT departamentos_institucion_id_slug_key UNIQUE (institucion_id, slug);


--
-- Name: departamentos departamentos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departamentos
    ADD CONSTRAINT departamentos_pkey PRIMARY KEY (id);


--
-- Name: dependencias_documentales dependencias_documentales_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dependencias_documentales
    ADD CONSTRAINT dependencias_documentales_pkey PRIMARY KEY (id);


--
-- Name: designaciones designaciones_institucion_id_departamento_id_sqlite_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.designaciones
    ADD CONSTRAINT designaciones_institucion_id_departamento_id_sqlite_id_key UNIQUE (institucion_id, departamento_id, sqlite_id);


--
-- Name: designaciones designaciones_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.designaciones
    ADD CONSTRAINT designaciones_pkey PRIMARY KEY (id);


--
-- Name: disposicion_docente_designaciones disposicion_docente_designaciones_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.disposicion_docente_designaciones
    ADD CONSTRAINT disposicion_docente_designaciones_pkey PRIMARY KEY (id);


--
-- Name: disposicion_docente_parametros disposicion_docente_parametro_institucion_id_departamento_i_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.disposicion_docente_parametros
    ADD CONSTRAINT disposicion_docente_parametro_institucion_id_departamento_i_key UNIQUE (institucion_id, departamento_id, cuil);


--
-- Name: disposicion_docente_parametros disposicion_docente_parametros_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.disposicion_docente_parametros
    ADD CONSTRAINT disposicion_docente_parametros_pkey PRIMARY KEY (id);


--
-- Name: disposicion_parametros disposicion_parametros_institucion_id_departamento_id_clave_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.disposicion_parametros
    ADD CONSTRAINT disposicion_parametros_institucion_id_departamento_id_clave_key UNIQUE (institucion_id, departamento_id, clave);


--
-- Name: disposicion_parametros disposicion_parametros_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.disposicion_parametros
    ADD CONSTRAINT disposicion_parametros_pkey PRIMARY KEY (id);


--
-- Name: disposiciones disposiciones_b12e_owner_chk; Type: CHECK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE public.disposiciones
    ADD CONSTRAINT disposiciones_b12e_owner_chk CHECK (((institucion_id IS NOT NULL) AND (departamento_id IS NOT NULL))) NOT VALID;


--
-- Name: disposiciones disposiciones_institucion_id_departamento_id_sqlite_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.disposiciones
    ADD CONSTRAINT disposiciones_institucion_id_departamento_id_sqlite_id_key UNIQUE (institucion_id, departamento_id, sqlite_id);


--
-- Name: disposiciones disposiciones_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.disposiciones
    ADD CONSTRAINT disposiciones_pkey PRIMARY KEY (id);


--
-- Name: docentes docentes_institucion_id_departamento_id_cuil_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.docentes
    ADD CONSTRAINT docentes_institucion_id_departamento_id_cuil_key UNIQUE (institucion_id, departamento_id, cuil);


--
-- Name: docentes docentes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.docentes
    ADD CONSTRAINT docentes_pkey PRIMARY KEY (id);


--
-- Name: documentos_respaldo_designaciones documentos_respaldo_designaci_institucion_id_departamento_i_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documentos_respaldo_designaciones
    ADD CONSTRAINT documentos_respaldo_designaci_institucion_id_departamento_i_key UNIQUE (institucion_id, departamento_id, designacion_id);


--
-- Name: documentos_respaldo_designaciones documentos_respaldo_designaciones_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documentos_respaldo_designaciones
    ADD CONSTRAINT documentos_respaldo_designaciones_pkey PRIMARY KEY (id);


--
-- Name: documentos_respaldo_docentes documentos_respaldo_docentes_institucion_id_departamento_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documentos_respaldo_docentes
    ADD CONSTRAINT documentos_respaldo_docentes_institucion_id_departamento_id_key UNIQUE (institucion_id, departamento_id, documento_id, cuil);


--
-- Name: documentos_respaldo_docentes documentos_respaldo_docentes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documentos_respaldo_docentes
    ADD CONSTRAINT documentos_respaldo_docentes_pkey PRIMARY KEY (id);


--
-- Name: documentos_respaldo_movimientos documentos_respaldo_movimient_institucion_id_departamento_i_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documentos_respaldo_movimientos
    ADD CONSTRAINT documentos_respaldo_movimient_institucion_id_departamento_i_key UNIQUE (institucion_id, departamento_id, movimiento_id);


--
-- Name: documentos_respaldo_movimientos documentos_respaldo_movimientos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documentos_respaldo_movimientos
    ADD CONSTRAINT documentos_respaldo_movimientos_pkey PRIMARY KEY (id);


--
-- Name: documentos_respaldo documentos_respaldo_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documentos_respaldo
    ADD CONSTRAINT documentos_respaldo_pkey PRIMARY KEY (id);


--
-- Name: documentos_respaldo_proyectos documentos_respaldo_proyectos_institucion_id_departamento_i_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documentos_respaldo_proyectos
    ADD CONSTRAINT documentos_respaldo_proyectos_institucion_id_departamento_i_key UNIQUE (institucion_id, departamento_id, documento_id, proyecto_tipo, proyecto_id);


--
-- Name: documentos_respaldo_proyectos documentos_respaldo_proyectos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documentos_respaldo_proyectos
    ADD CONSTRAINT documentos_respaldo_proyectos_pkey PRIMARY KEY (id);


--
-- Name: escalas_salariales_docentes escalas_salariales_docentes_institucion_id_mes_referencia_c_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.escalas_salariales_docentes
    ADD CONSTRAINT escalas_salariales_docentes_institucion_id_mes_referencia_c_key UNIQUE (institucion_id, mes_referencia, cargo);


--
-- Name: escalas_salariales_docentes escalas_salariales_docentes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.escalas_salariales_docentes
    ADD CONSTRAINT escalas_salariales_docentes_pkey PRIMARY KEY (id);


--
-- Name: estado_consulta_designacion estado_consulta_designacion_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.estado_consulta_designacion
    ADD CONSTRAINT estado_consulta_designacion_pkey PRIMARY KEY (id);


--
-- Name: eventos_producto eventos_producto_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.eventos_producto
    ADD CONSTRAINT eventos_producto_pkey PRIMARY KEY (id);


--
-- Name: extension_docente extension_docente_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.extension_docente
    ADD CONSTRAINT extension_docente_pkey PRIMARY KEY (id);


--
-- Name: horarios_asignacion_docente_comision horarios_asignacion_docente_comision_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.horarios_asignacion_docente_comision
    ADD CONSTRAINT horarios_asignacion_docente_comision_pkey PRIMARY KEY (id);


--
-- Name: horarios_comision horarios_comision_institucion_id_departamento_id_sqlite_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.horarios_comision
    ADD CONSTRAINT horarios_comision_institucion_id_departamento_id_sqlite_id_key UNIQUE (institucion_id, departamento_id, sqlite_id);


--
-- Name: horarios_comision horarios_comision_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.horarios_comision
    ADD CONSTRAINT horarios_comision_pkey PRIMARY KEY (id);


--
-- Name: inscriptos_asignatura_periodo inscriptos_asignatura_periodo_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inscriptos_asignatura_periodo
    ADD CONSTRAINT inscriptos_asignatura_periodo_pkey PRIMARY KEY (id);


--
-- Name: inscriptos_comision_materia inscriptos_comision_materia_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inscriptos_comision_materia
    ADD CONSTRAINT inscriptos_comision_materia_pkey PRIMARY KEY (id);


--
-- Name: inscriptos_comision inscriptos_comision_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inscriptos_comision
    ADD CONSTRAINT inscriptos_comision_pkey PRIMARY KEY (id);


--
-- Name: instituciones instituciones_nombre_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.instituciones
    ADD CONSTRAINT instituciones_nombre_key UNIQUE (nombre);


--
-- Name: instituciones instituciones_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.instituciones
    ADD CONSTRAINT instituciones_pkey PRIMARY KEY (id);


--
-- Name: instituciones instituciones_slug_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.instituciones
    ADD CONSTRAINT instituciones_slug_key UNIQUE (slug);


--
-- Name: investigacion_docente investigacion_docente_institucion_id_departamento_id_sqlite_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.investigacion_docente
    ADD CONSTRAINT investigacion_docente_institucion_id_departamento_id_sqlite_key UNIQUE (institucion_id, departamento_id, sqlite_id);


--
-- Name: investigacion_docente investigacion_docente_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.investigacion_docente
    ADD CONSTRAINT investigacion_docente_pkey PRIMARY KEY (id);


--
-- Name: materias materias_institucion_id_source_db_sqlite_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.materias
    ADD CONSTRAINT materias_institucion_id_source_db_sqlite_id_key UNIQUE (institucion_id, source_db, sqlite_id);


--
-- Name: materias materias_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.materias
    ADD CONSTRAINT materias_pkey PRIMARY KEY (id);


--
-- Name: movimientos movimientos_institucion_id_departamento_id_sqlite_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movimientos
    ADD CONSTRAINT movimientos_institucion_id_departamento_id_sqlite_id_key UNIQUE (institucion_id, departamento_id, sqlite_id);


--
-- Name: movimientos movimientos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movimientos
    ADD CONSTRAINT movimientos_pkey PRIMARY KEY (id);


--
-- Name: opcion_curricular_materias opcion_curricular_materias_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.opcion_curricular_materias
    ADD CONSTRAINT opcion_curricular_materias_pkey PRIMARY KEY (id);


--
-- Name: opciones_curriculares opciones_curriculares_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.opciones_curriculares
    ADD CONSTRAINT opciones_curriculares_pkey PRIMARY KEY (id);


--
-- Name: parametros_sueldos parametros_sueldos_institucion_id_departamento_id_sqlite_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parametros_sueldos
    ADD CONSTRAINT parametros_sueldos_institucion_id_departamento_id_sqlite_id_key UNIQUE (institucion_id, departamento_id, sqlite_id);


--
-- Name: parametros_sueldos parametros_sueldos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parametros_sueldos
    ADD CONSTRAINT parametros_sueldos_pkey PRIMARY KEY (id);


--
-- Name: periodos periodos_institucion_id_departamento_id_sqlite_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.periodos
    ADD CONSTRAINT periodos_institucion_id_departamento_id_sqlite_id_key UNIQUE (institucion_id, departamento_id, sqlite_id);


--
-- Name: periodos periodos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.periodos
    ADD CONSTRAINT periodos_pkey PRIMARY KEY (id);


--
-- Name: portal_docente_tokens portal_docente_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.portal_docente_tokens
    ADD CONSTRAINT portal_docente_tokens_pkey PRIMARY KEY (id);


--
-- Name: portal_docente_tokens portal_docente_tokens_token_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.portal_docente_tokens
    ADD CONSTRAINT portal_docente_tokens_token_hash_key UNIQUE (token_hash);


--
-- Name: prestamos_docentes prestamos_docentes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prestamos_docentes
    ADD CONSTRAINT prestamos_docentes_pkey PRIMARY KEY (id);


--
-- Name: proyectos_extension proyectos_extension_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proyectos_extension
    ADD CONSTRAINT proyectos_extension_pkey PRIMARY KEY (id);


--
-- Name: proyectos_investigacion proyectos_investigacion_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proyectos_investigacion
    ADD CONSTRAINT proyectos_investigacion_pkey PRIMARY KEY (id);


--
-- Name: resoluciones resoluciones_institucion_id_departamento_id_sqlite_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resoluciones
    ADD CONSTRAINT resoluciones_institucion_id_departamento_id_sqlite_id_key UNIQUE (institucion_id, departamento_id, sqlite_id);


--
-- Name: resoluciones resoluciones_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resoluciones
    ADD CONSTRAINT resoluciones_pkey PRIMARY KEY (id);


--
-- Name: roadmap_funciones roadmap_funciones_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.roadmap_funciones
    ADD CONSTRAINT roadmap_funciones_pkey PRIMARY KEY (id);


--
-- Name: saneamiento_v279_designaciones_backup saneamiento_v279_designacione_institucion_id_departamento_i_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.saneamiento_v279_designaciones_backup
    ADD CONSTRAINT saneamiento_v279_designacione_institucion_id_departamento_i_key UNIQUE (institucion_id, departamento_id, original_id);


--
-- Name: saneamiento_v279_designaciones_backup saneamiento_v279_designaciones_backup_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.saneamiento_v279_designaciones_backup
    ADD CONSTRAINT saneamiento_v279_designaciones_backup_pkey PRIMARY KEY (id);


--
-- Name: saneamiento_v279_ejecuciones saneamiento_v279_ejecuciones_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.saneamiento_v279_ejecuciones
    ADD CONSTRAINT saneamiento_v279_ejecuciones_pkey PRIMARY KEY (id);


--
-- Name: saneamiento_v279_movimientos_backup saneamiento_v279_movimientos__institucion_id_departamento_i_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.saneamiento_v279_movimientos_backup
    ADD CONSTRAINT saneamiento_v279_movimientos__institucion_id_departamento_i_key UNIQUE (institucion_id, departamento_id, original_id);


--
-- Name: saneamiento_v279_movimientos_backup saneamiento_v279_movimientos_backup_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.saneamiento_v279_movimientos_backup
    ADD CONSTRAINT saneamiento_v279_movimientos_backup_pkey PRIMARY KEY (id);


--
-- Name: sedes_institucion sedes_institucion_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sedes_institucion
    ADD CONSTRAINT sedes_institucion_pkey PRIMARY KEY (id);


--
-- Name: sistema_flags sistema_flags_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sistema_flags
    ADD CONSTRAINT sistema_flags_pkey PRIMARY KEY (clave);


--
-- Name: vistas_guardadas vistas_guardadas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vistas_guardadas
    ADD CONSTRAINT vistas_guardadas_pkey PRIMARY KEY (id);


--
-- Name: auth_login_throttle_updated_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX auth_login_throttle_updated_idx ON public.auth_login_throttle USING btree (updated_epoch);


--
-- Name: b12h_audit_log_actor_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX b12h_audit_log_actor_idx ON public.b12h_audit_log USING btree (actor_user_id, occurred_at);


--
-- Name: b12h_audit_log_entity_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX b12h_audit_log_entity_idx ON public.b12h_audit_log USING btree (entity_type, entity_id);


--
-- Name: b12h_audit_log_occurred_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX b12h_audit_log_occurred_idx ON public.b12h_audit_log USING btree (occurred_at);


--
-- Name: b12h_audit_log_operation_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX b12h_audit_log_operation_idx ON public.b12h_audit_log USING btree (operation, occurred_at);


--
-- Name: b12h_audit_log_tenant_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX b12h_audit_log_tenant_idx ON public.b12h_audit_log USING btree (institucion_id, departamento_id, occurred_at);


--
-- Name: idx_acciones_gestion_estado; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_acciones_gestion_estado ON public.acciones_gestion USING btree (institucion_id, departamento_id, periodo_id, estado, gravedad);


--
-- Name: idx_asignaciones_comision; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_asignaciones_comision ON public.asignaciones_docentes_comision USING btree (comision_id);


--
-- Name: idx_auditoria_scope_fecha; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_auditoria_scope_fecha ON public.auditoria_eventos USING btree (institucion_id, departamento_id, fecha_hora DESC);


--
-- Name: idx_comisiones_dep_materia; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_comisiones_dep_materia ON public.comisiones USING btree (institucion_id, departamento_id, materia_id);


--
-- Name: idx_config_productividad_departamento_scope; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_config_productividad_departamento_scope ON public.config_productividad_departamento USING btree (institucion_id, departamento_id);


--
-- Name: idx_deptit_actesp_doc_periodo; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deptit_actesp_doc_periodo ON public.actividad_especial_docente USING btree (institucion_id, departamento_id, cuil, periodo_id);


--
-- Name: idx_deptit_actesp_periodo; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deptit_actesp_periodo ON public.actividades_especiales USING btree (institucion_id, departamento_id, periodo_id);


--
-- Name: idx_deptit_asig_comision_estado; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deptit_asig_comision_estado ON public.asignaciones_docentes_comision USING btree (comision_id, estado);


--
-- Name: idx_deptit_asig_cuil_estado; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deptit_asig_cuil_estado ON public.asignaciones_docentes_comision USING btree (cuil, estado);


--
-- Name: idx_deptit_asig_scope_periodo_cuil_v191; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deptit_asig_scope_periodo_cuil_v191 ON public.asignaciones_docentes_comision USING btree (institucion_id, departamento_id, cuil, estado);


--
-- Name: idx_deptit_comision_materias_comision; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deptit_comision_materias_comision ON public.comision_materias USING btree (institucion_id, departamento_id, comision_id);


--
-- Name: idx_deptit_comision_materias_comision_perf; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deptit_comision_materias_comision_perf ON public.comision_materias USING btree (institucion_id, departamento_id, comision_id);


--
-- Name: idx_deptit_comision_materias_materia; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deptit_comision_materias_materia ON public.comision_materias USING btree (institucion_id, materia_id);


--
-- Name: idx_deptit_comision_materias_materia_perf; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deptit_comision_materias_materia_perf ON public.comision_materias USING btree (institucion_id, materia_id);


--
-- Name: idx_deptit_comisiones_materia; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deptit_comisiones_materia ON public.comisiones USING btree (materia_id);


--
-- Name: idx_deptit_comisiones_opcion_curricular_v120; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deptit_comisiones_opcion_curricular_v120 ON public.comisiones USING btree (institucion_id, opcion_curricular_id);


--
-- Name: idx_deptit_comisiones_scope_periodo_estado; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deptit_comisiones_scope_periodo_estado ON public.comisiones USING btree (institucion_id, departamento_id, periodo_id, estado);


--
-- Name: idx_deptit_designaciones_cuil_periodo_estado; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deptit_designaciones_cuil_periodo_estado ON public.designaciones USING btree (cuil, periodo_id, estado);


--
-- Name: idx_deptit_docentes_cuil; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deptit_docentes_cuil ON public.docentes USING btree (cuil);


--
-- Name: idx_deptit_ext_doc_cuil_periodo; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deptit_ext_doc_cuil_periodo ON public.extension_docente USING btree (institucion_id, cuil, periodo_id);


--
-- Name: idx_deptit_ext_doc_proyecto; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deptit_ext_doc_proyecto ON public.extension_docente USING btree (proyecto_id);


--
-- Name: idx_deptit_ext_periodo_cuil_estado_v191; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deptit_ext_periodo_cuil_estado_v191 ON public.extension_docente USING btree (institucion_id, departamento_id, periodo_id, cuil, estado_asignacion);


--
-- Name: idx_deptit_hor_asig_asignacion; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deptit_hor_asig_asignacion ON public.horarios_asignacion_docente_comision USING btree (asignacion_id);


--
-- Name: idx_deptit_hor_asig_horario; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deptit_hor_asig_horario ON public.horarios_asignacion_docente_comision USING btree (horario_comision_id);


--
-- Name: idx_deptit_hor_asig_scope_asig_v191; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deptit_hor_asig_scope_asig_v191 ON public.horarios_asignacion_docente_comision USING btree (institucion_id, departamento_id, asignacion_id);


--
-- Name: idx_deptit_horarios_comision; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deptit_horarios_comision ON public.horarios_comision USING btree (comision_id);


--
-- Name: idx_deptit_inscriptos_asignatura_periodo_periodo_v248; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deptit_inscriptos_asignatura_periodo_periodo_v248 ON public.inscriptos_asignatura_periodo USING btree (institucion_id, departamento_id, periodo_id);


--
-- Name: idx_deptit_inscriptos_comision_materia_comision_v123; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deptit_inscriptos_comision_materia_comision_v123 ON public.inscriptos_comision_materia USING btree (institucion_id, departamento_id, comision_id);


--
-- Name: idx_deptit_inv_doc_cuil_periodo; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deptit_inv_doc_cuil_periodo ON public.investigacion_docente USING btree (institucion_id, cuil, periodo_id);


--
-- Name: idx_deptit_inv_doc_proyecto; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deptit_inv_doc_proyecto ON public.investigacion_docente USING btree (proyecto_id);


--
-- Name: idx_deptit_inv_periodo_cuil_estado_v191; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deptit_inv_periodo_cuil_estado_v191 ON public.investigacion_docente USING btree (institucion_id, departamento_id, periodo_id, cuil, estado_asignacion);


--
-- Name: idx_deptit_materias_carrera_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deptit_materias_carrera_id ON public.materias USING btree (carrera_id);


--
-- Name: idx_deptit_materias_comparticion; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deptit_materias_comparticion ON public.materias USING btree (institucion_id, comparticion_modo, comparticion_grupo);


--
-- Name: idx_deptit_materias_en_plan; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deptit_materias_en_plan ON public.materias USING btree (institucion_id, carrera_id, en_plan);


--
-- Name: idx_deptit_materias_inst_codigo_asig; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deptit_materias_inst_codigo_asig ON public.materias USING btree (institucion_id, codigo, asignatura);


--
-- Name: idx_deptit_mov_periodo_cuil_fecha_v191; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deptit_mov_periodo_cuil_fecha_v191 ON public.movimientos USING btree (institucion_id, departamento_id, periodo_id, cuil, fecha);


--
-- Name: idx_deptit_opcion_materias_materia_v120; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deptit_opcion_materias_materia_v120 ON public.opcion_curricular_materias USING btree (institucion_id, materia_id);


--
-- Name: idx_deptit_opcion_materias_opcion_v120; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deptit_opcion_materias_opcion_v120 ON public.opcion_curricular_materias USING btree (institucion_id, opcion_id);


--
-- Name: idx_deptit_opciones_codigo_nombre_v127; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deptit_opciones_codigo_nombre_v127 ON public.opciones_curriculares USING btree (institucion_id, codigo, nombre);


--
-- Name: idx_deptit_opciones_tipo_estado_v120; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deptit_opciones_tipo_estado_v120 ON public.opciones_curriculares USING btree (institucion_id, tipo, estado);


--
-- Name: idx_deptit_periodos_scope_nombre; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deptit_periodos_scope_nombre ON public.periodos USING btree (institucion_id, departamento_id, nombre, anio, semestre);


--
-- Name: idx_deptit_prestamo_cuil_periodo_estado_v191; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deptit_prestamo_cuil_periodo_estado_v191 ON public.prestamos_docentes USING btree (institucion_id, departamento_id, cuil, periodo_id, estado);


--
-- Name: idx_deptit_prestamo_periodo_estado; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deptit_prestamo_periodo_estado ON public.prestamos_docentes USING btree (institucion_id, departamento_id, periodo_id, estado);


--
-- Name: idx_deptit_proyectos_ext_codigo; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deptit_proyectos_ext_codigo ON public.proyectos_extension USING btree (institucion_id, upper(TRIM(BOTH FROM codigo_proyecto)));


--
-- Name: idx_deptit_proyectos_ext_fechas; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deptit_proyectos_ext_fechas ON public.proyectos_extension USING btree (fecha_inicio, fecha_fin);


--
-- Name: idx_deptit_proyectos_ext_institucion; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deptit_proyectos_ext_institucion ON public.proyectos_extension USING btree (institucion_id);


--
-- Name: idx_deptit_proyectos_inv_codigo_institucional; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_deptit_proyectos_inv_codigo_institucional ON public.proyectos_investigacion USING btree (institucion_id, upper(TRIM(BOTH FROM codigo_proyecto))) WHERE (TRIM(BOTH FROM COALESCE(codigo_proyecto, ''::text)) <> ''::text);


--
-- Name: idx_deptit_proyectos_inv_fechas; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deptit_proyectos_inv_fechas ON public.proyectos_investigacion USING btree (fecha_inicio, fecha_fin);


--
-- Name: idx_deptit_proyectos_inv_institucion; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deptit_proyectos_inv_institucion ON public.proyectos_investigacion USING btree (institucion_id);


--
-- Name: idx_deptit_proyectos_inv_sin_codigo_institucional; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_deptit_proyectos_inv_sin_codigo_institucional ON public.proyectos_investigacion USING btree (institucion_id, upper(TRIM(BOTH FROM nombre_proyecto)), COALESCE(anio_llamado, '-1'::integer), fecha_inicio, fecha_fin) WHERE (TRIM(BOTH FROM COALESCE(codigo_proyecto, ''::text)) = ''::text);


--
-- Name: idx_designaciones_cuil; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_designaciones_cuil ON public.designaciones USING btree (cuil);


--
-- Name: idx_docentes_cuil; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_docentes_cuil ON public.docentes USING btree (cuil);


--
-- Name: idx_docresp_dep_fecha_v249; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_docresp_dep_fecha_v249 ON public.documentos_respaldo USING btree (institucion_id, departamento_id, fecha DESC, id DESC);


--
-- Name: idx_docresp_designaciones_desig_v266; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_docresp_designaciones_desig_v266 ON public.documentos_respaldo_designaciones USING btree (institucion_id, departamento_id, designacion_id);


--
-- Name: idx_docresp_designaciones_doc_v266; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_docresp_designaciones_doc_v266 ON public.documentos_respaldo_designaciones USING btree (institucion_id, departamento_id, documento_id);


--
-- Name: idx_docresp_docente_v249; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_docresp_docente_v249 ON public.documentos_respaldo USING btree (institucion_id, departamento_id, cuil);


--
-- Name: idx_docresp_docentes_cuil_v251; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_docresp_docentes_cuil_v251 ON public.documentos_respaldo_docentes USING btree (institucion_id, departamento_id, cuil);


--
-- Name: idx_docresp_docentes_documento_v251; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_docresp_docentes_documento_v251 ON public.documentos_respaldo_docentes USING btree (institucion_id, departamento_id, documento_id);


--
-- Name: idx_docresp_movimientos_doc_v266; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_docresp_movimientos_doc_v266 ON public.documentos_respaldo_movimientos USING btree (institucion_id, departamento_id, documento_id);


--
-- Name: idx_docresp_movimientos_mov_v266; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_docresp_movimientos_mov_v266 ON public.documentos_respaldo_movimientos USING btree (institucion_id, departamento_id, movimiento_id);


--
-- Name: idx_docresp_proyecto_v249; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_docresp_proyecto_v249 ON public.documentos_respaldo USING btree (institucion_id, proyecto_tipo, proyecto_id);


--
-- Name: idx_docresp_proyectos_documento_v261; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_docresp_proyectos_documento_v261 ON public.documentos_respaldo_proyectos USING btree (institucion_id, departamento_id, documento_id);


--
-- Name: idx_docresp_proyectos_proyecto_v261; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_docresp_proyectos_proyecto_v261 ON public.documentos_respaldo_proyectos USING btree (institucion_id, proyecto_tipo, proyecto_id);


--
-- Name: idx_escala_salarial_inst_mes_v256; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_escala_salarial_inst_mes_v256 ON public.escalas_salariales_docentes USING btree (institucion_id, mes_referencia DESC);


--
-- Name: idx_eventos_producto_scope_fecha; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_eventos_producto_scope_fecha ON public.eventos_producto USING btree (institucion_id, departamento_id, fecha_hora DESC);


--
-- Name: idx_materias_inst_codigo; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_materias_inst_codigo ON public.materias USING btree (institucion_id, codigo);


--
-- Name: idx_portal_tokens_scope; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_portal_tokens_scope ON public.portal_docente_tokens USING btree (institucion_id, departamento_id, periodo_id, cuil, estado);


--
-- Name: idx_v199_actividad_doc_periodo_cuil; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_v199_actividad_doc_periodo_cuil ON public.actividad_especial_docente USING btree (institucion_id, departamento_id, periodo_id, cuil, estado_asignacion);


--
-- Name: idx_v199_actividad_periodo_estado; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_v199_actividad_periodo_estado ON public.actividades_especiales USING btree (institucion_id, departamento_id, periodo_id, estado);


--
-- Name: idx_v199_asig_comision_scope_estado_cuil; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_v199_asig_comision_scope_estado_cuil ON public.asignaciones_docentes_comision USING btree (institucion_id, departamento_id, comision_id, estado, cuil);


--
-- Name: idx_v199_comision_materias_scope_comision; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_v199_comision_materias_scope_comision ON public.comision_materias USING btree (institucion_id, departamento_id, comision_id, materia_id);


--
-- Name: idx_v199_comisiones_scope_periodo_estado; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_v199_comisiones_scope_periodo_estado ON public.comisiones USING btree (institucion_id, departamento_id, periodo_id, estado, materia_id);


--
-- Name: idx_v199_designaciones_scope_periodo_estado_cuil; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_v199_designaciones_scope_periodo_estado_cuil ON public.designaciones USING btree (institucion_id, departamento_id, periodo_id, estado, cuil);


--
-- Name: idx_v199_disposiciones_periodo_cuil; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_v199_disposiciones_periodo_cuil ON public.disposiciones USING btree (institucion_id, departamento_id, periodo_id, cuil);


--
-- Name: idx_v199_ext_proyecto_estado; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_v199_ext_proyecto_estado ON public.extension_docente USING btree (institucion_id, proyecto_id, estado_asignacion, cuil);


--
-- Name: idx_v199_horarios_comision_scope; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_v199_horarios_comision_scope ON public.horarios_comision USING btree (institucion_id, departamento_id, comision_id);


--
-- Name: idx_v199_inscriptos_comision_scope; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_v199_inscriptos_comision_scope ON public.inscriptos_comision USING btree (institucion_id, departamento_id, comision_id);


--
-- Name: idx_v199_inv_proyecto_estado; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_v199_inv_proyecto_estado ON public.investigacion_docente USING btree (institucion_id, proyecto_id, estado_asignacion, cuil);


--
-- Name: idx_v199_periodos_scope_estado; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_v199_periodos_scope_estado ON public.periodos USING btree (institucion_id, departamento_id, estado, anio, semestre);


--
-- Name: ix_dependencias_documentales_estado_v262; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_dependencias_documentales_estado_v262 ON public.dependencias_documentales USING btree (institucion_id, estado, nombre);


--
-- Name: ix_dispo_doc_desig_cuil; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_dispo_doc_desig_cuil ON public.disposicion_docente_designaciones USING btree (institucion_id, cuil);


--
-- Name: ix_sedes_institucion_estado; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sedes_institucion_estado ON public.sedes_institucion USING btree (institucion_id, estado);


--
-- Name: uq_acciones_gestion_scope_fp; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_acciones_gestion_scope_fp ON public.acciones_gestion USING btree (institucion_id, COALESCE(departamento_id, (0)::bigint), COALESCE(periodo_id, (0)::bigint), fingerprint);


--
-- Name: uq_checklist_periodo_scope; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_checklist_periodo_scope ON public.checklist_periodo USING btree (institucion_id, COALESCE(departamento_id, (0)::bigint), periodo_id, item_clave);


--
-- Name: uq_config_integraciones_scope; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_config_integraciones_scope ON public.config_integraciones USING btree (institucion_id, COALESCE(departamento_id, (0)::bigint), clave);


--
-- Name: uq_dependencias_documentales_nombre_v262; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_dependencias_documentales_nombre_v262 ON public.dependencias_documentales USING btree (institucion_id, lower(TRIM(BOTH FROM nombre)));


--
-- Name: uq_deptit_comision_materia_v118; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_deptit_comision_materia_v118 ON public.comision_materias USING btree (institucion_id, comision_id, materia_id);


--
-- Name: uq_deptit_inscriptos_asignatura_periodo_v248; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_deptit_inscriptos_asignatura_periodo_v248 ON public.inscriptos_asignatura_periodo USING btree (institucion_id, departamento_id, periodo_id, materia_id, opcion_curricular_id);


--
-- Name: uq_deptit_inscriptos_comision_materia_v123; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_deptit_inscriptos_comision_materia_v123 ON public.inscriptos_comision_materia USING btree (institucion_id, departamento_id, comision_id, materia_id);


--
-- Name: uq_deptit_inscriptos_comision_scope; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_deptit_inscriptos_comision_scope ON public.inscriptos_comision USING btree (institucion_id, departamento_id, comision_id);


--
-- Name: uq_deptit_opcion_materia_v120; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_deptit_opcion_materia_v120 ON public.opcion_curricular_materias USING btree (institucion_id, opcion_id, materia_id);


--
-- Name: uq_deptit_prestamo_periodo_cuil; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_deptit_prestamo_periodo_cuil ON public.prestamos_docentes USING btree (institucion_id, departamento_id, periodo_id, cuil);


--
-- Name: uq_dispo_doc_desig_institucion_designacion; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_dispo_doc_desig_institucion_designacion ON public.disposicion_docente_designaciones USING btree (institucion_id, designacion_id) WHERE (designacion_id IS NOT NULL);


--
-- Name: uq_disposiciones_b12e_archivo_ref; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_disposiciones_b12e_archivo_ref ON public.disposiciones USING btree (archivo_word) WHERE (archivo_word ~~ 'b12e:%'::text);


--
-- Name: uq_estado_consulta_designacion; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_estado_consulta_designacion ON public.estado_consulta_designacion USING btree (institucion_id, departamento_id, periodo_id, cuil);


--
-- Name: uq_roadmap_funciones_scope; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_roadmap_funciones_scope ON public.roadmap_funciones USING btree (institucion_id, COALESCE(departamento_id, (0)::bigint), idea_id);


--
-- Name: uq_sedes_institucion_nombre_normalizado; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_sedes_institucion_nombre_normalizado ON public.sedes_institucion USING btree (institucion_id, lower(TRIM(BOTH FROM nombre)));


--
-- Name: uq_vistas_guardadas_scope; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_vistas_guardadas_scope ON public.vistas_guardadas USING btree (institucion_id, COALESCE(departamento_id, (0)::bigint), usuario_email, modulo, nombre);


--
-- Name: b12h_audit_log b12h_audit_log_no_truncate; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER b12h_audit_log_no_truncate BEFORE TRUNCATE ON public.b12h_audit_log FOR EACH STATEMENT EXECUTE FUNCTION public.b12h_audit_log_append_only();


--
-- Name: b12h_audit_log b12h_audit_log_no_update_delete; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER b12h_audit_log_no_update_delete BEFORE DELETE OR UPDATE ON public.b12h_audit_log FOR EACH ROW EXECUTE FUNCTION public.b12h_audit_log_append_only();


--
-- Name: app_usuarios app_usuarios_departamento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.app_usuarios
    ADD CONSTRAINT app_usuarios_departamento_id_fkey FOREIGN KEY (departamento_id) REFERENCES public.departamentos(id) ON DELETE SET NULL;


--
-- Name: app_usuarios app_usuarios_institucion_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.app_usuarios
    ADD CONSTRAINT app_usuarios_institucion_id_fkey FOREIGN KEY (institucion_id) REFERENCES public.instituciones(id) ON DELETE CASCADE;


--
-- Name: asignaciones_docentes_comision asignaciones_docentes_comision_comision_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.asignaciones_docentes_comision
    ADD CONSTRAINT asignaciones_docentes_comision_comision_id_fkey FOREIGN KEY (comision_id) REFERENCES public.comisiones(id) ON DELETE CASCADE;


--
-- Name: asignaciones_docentes_comision asignaciones_docentes_comision_departamento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.asignaciones_docentes_comision
    ADD CONSTRAINT asignaciones_docentes_comision_departamento_id_fkey FOREIGN KEY (departamento_id) REFERENCES public.departamentos(id) ON DELETE CASCADE;


--
-- Name: asignaciones_docentes_comision asignaciones_docentes_comision_institucion_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.asignaciones_docentes_comision
    ADD CONSTRAINT asignaciones_docentes_comision_institucion_id_fkey FOREIGN KEY (institucion_id) REFERENCES public.instituciones(id) ON DELETE CASCADE;


--
-- Name: carreras carreras_institucion_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.carreras
    ADD CONSTRAINT carreras_institucion_id_fkey FOREIGN KEY (institucion_id) REFERENCES public.instituciones(id) ON DELETE CASCADE;


--
-- Name: comisiones comisiones_departamento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comisiones
    ADD CONSTRAINT comisiones_departamento_id_fkey FOREIGN KEY (departamento_id) REFERENCES public.departamentos(id) ON DELETE CASCADE;


--
-- Name: comisiones comisiones_institucion_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comisiones
    ADD CONSTRAINT comisiones_institucion_id_fkey FOREIGN KEY (institucion_id) REFERENCES public.instituciones(id) ON DELETE CASCADE;


--
-- Name: comisiones comisiones_materia_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comisiones
    ADD CONSTRAINT comisiones_materia_id_fkey FOREIGN KEY (materia_id) REFERENCES public.materias(id) ON DELETE SET NULL;


--
-- Name: comisiones comisiones_periodo_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comisiones
    ADD CONSTRAINT comisiones_periodo_id_fkey FOREIGN KEY (periodo_id) REFERENCES public.periodos(id) ON DELETE SET NULL;


--
-- Name: config_disposiciones config_disposiciones_departamento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.config_disposiciones
    ADD CONSTRAINT config_disposiciones_departamento_id_fkey FOREIGN KEY (departamento_id) REFERENCES public.departamentos(id) ON DELETE CASCADE;


--
-- Name: config_disposiciones config_disposiciones_institucion_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.config_disposiciones
    ADD CONSTRAINT config_disposiciones_institucion_id_fkey FOREIGN KEY (institucion_id) REFERENCES public.instituciones(id) ON DELETE CASCADE;


--
-- Name: departamentos departamentos_institucion_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departamentos
    ADD CONSTRAINT departamentos_institucion_id_fkey FOREIGN KEY (institucion_id) REFERENCES public.instituciones(id) ON DELETE CASCADE;


--
-- Name: designaciones designaciones_departamento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.designaciones
    ADD CONSTRAINT designaciones_departamento_id_fkey FOREIGN KEY (departamento_id) REFERENCES public.departamentos(id) ON DELETE CASCADE;


--
-- Name: designaciones designaciones_institucion_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.designaciones
    ADD CONSTRAINT designaciones_institucion_id_fkey FOREIGN KEY (institucion_id) REFERENCES public.instituciones(id) ON DELETE CASCADE;


--
-- Name: designaciones designaciones_periodo_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.designaciones
    ADD CONSTRAINT designaciones_periodo_id_fkey FOREIGN KEY (periodo_id) REFERENCES public.periodos(id) ON DELETE SET NULL;


--
-- Name: designaciones designaciones_resolucion_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.designaciones
    ADD CONSTRAINT designaciones_resolucion_id_fkey FOREIGN KEY (resolucion_id) REFERENCES public.resoluciones(id) ON DELETE SET NULL;


--
-- Name: disposicion_docente_parametros disposicion_docente_parametros_departamento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.disposicion_docente_parametros
    ADD CONSTRAINT disposicion_docente_parametros_departamento_id_fkey FOREIGN KEY (departamento_id) REFERENCES public.departamentos(id) ON DELETE CASCADE;


--
-- Name: disposicion_docente_parametros disposicion_docente_parametros_institucion_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.disposicion_docente_parametros
    ADD CONSTRAINT disposicion_docente_parametros_institucion_id_fkey FOREIGN KEY (institucion_id) REFERENCES public.instituciones(id) ON DELETE CASCADE;


--
-- Name: disposicion_parametros disposicion_parametros_departamento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.disposicion_parametros
    ADD CONSTRAINT disposicion_parametros_departamento_id_fkey FOREIGN KEY (departamento_id) REFERENCES public.departamentos(id) ON DELETE CASCADE;


--
-- Name: disposicion_parametros disposicion_parametros_institucion_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.disposicion_parametros
    ADD CONSTRAINT disposicion_parametros_institucion_id_fkey FOREIGN KEY (institucion_id) REFERENCES public.instituciones(id) ON DELETE CASCADE;


--
-- Name: disposiciones disposiciones_departamento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.disposiciones
    ADD CONSTRAINT disposiciones_departamento_id_fkey FOREIGN KEY (departamento_id) REFERENCES public.departamentos(id) ON DELETE CASCADE;


--
-- Name: disposiciones disposiciones_institucion_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.disposiciones
    ADD CONSTRAINT disposiciones_institucion_id_fkey FOREIGN KEY (institucion_id) REFERENCES public.instituciones(id) ON DELETE CASCADE;


--
-- Name: disposiciones disposiciones_periodo_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.disposiciones
    ADD CONSTRAINT disposiciones_periodo_id_fkey FOREIGN KEY (periodo_id) REFERENCES public.periodos(id) ON DELETE SET NULL;


--
-- Name: docentes docentes_departamento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.docentes
    ADD CONSTRAINT docentes_departamento_id_fkey FOREIGN KEY (departamento_id) REFERENCES public.departamentos(id) ON DELETE CASCADE;


--
-- Name: docentes docentes_institucion_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.docentes
    ADD CONSTRAINT docentes_institucion_id_fkey FOREIGN KEY (institucion_id) REFERENCES public.instituciones(id) ON DELETE CASCADE;


--
-- Name: documentos_respaldo_designaciones documentos_respaldo_designaciones_designacion_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documentos_respaldo_designaciones
    ADD CONSTRAINT documentos_respaldo_designaciones_designacion_id_fkey FOREIGN KEY (designacion_id) REFERENCES public.designaciones(id) ON DELETE CASCADE;


--
-- Name: documentos_respaldo_designaciones documentos_respaldo_designaciones_documento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documentos_respaldo_designaciones
    ADD CONSTRAINT documentos_respaldo_designaciones_documento_id_fkey FOREIGN KEY (documento_id) REFERENCES public.documentos_respaldo(id) ON DELETE CASCADE;


--
-- Name: documentos_respaldo_docentes documentos_respaldo_docentes_documento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documentos_respaldo_docentes
    ADD CONSTRAINT documentos_respaldo_docentes_documento_id_fkey FOREIGN KEY (documento_id) REFERENCES public.documentos_respaldo(id) ON DELETE CASCADE;


--
-- Name: documentos_respaldo_movimientos documentos_respaldo_movimientos_documento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documentos_respaldo_movimientos
    ADD CONSTRAINT documentos_respaldo_movimientos_documento_id_fkey FOREIGN KEY (documento_id) REFERENCES public.documentos_respaldo(id) ON DELETE CASCADE;


--
-- Name: documentos_respaldo_movimientos documentos_respaldo_movimientos_movimiento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documentos_respaldo_movimientos
    ADD CONSTRAINT documentos_respaldo_movimientos_movimiento_id_fkey FOREIGN KEY (movimiento_id) REFERENCES public.movimientos(id) ON DELETE CASCADE;


--
-- Name: documentos_respaldo_proyectos documentos_respaldo_proyectos_documento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documentos_respaldo_proyectos
    ADD CONSTRAINT documentos_respaldo_proyectos_documento_id_fkey FOREIGN KEY (documento_id) REFERENCES public.documentos_respaldo(id) ON DELETE CASCADE;


--
-- Name: horarios_comision horarios_comision_comision_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.horarios_comision
    ADD CONSTRAINT horarios_comision_comision_id_fkey FOREIGN KEY (comision_id) REFERENCES public.comisiones(id) ON DELETE CASCADE;


--
-- Name: horarios_comision horarios_comision_departamento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.horarios_comision
    ADD CONSTRAINT horarios_comision_departamento_id_fkey FOREIGN KEY (departamento_id) REFERENCES public.departamentos(id) ON DELETE CASCADE;


--
-- Name: horarios_comision horarios_comision_institucion_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.horarios_comision
    ADD CONSTRAINT horarios_comision_institucion_id_fkey FOREIGN KEY (institucion_id) REFERENCES public.instituciones(id) ON DELETE CASCADE;


--
-- Name: investigacion_docente investigacion_docente_departamento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.investigacion_docente
    ADD CONSTRAINT investigacion_docente_departamento_id_fkey FOREIGN KEY (departamento_id) REFERENCES public.departamentos(id) ON DELETE CASCADE;


--
-- Name: investigacion_docente investigacion_docente_institucion_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.investigacion_docente
    ADD CONSTRAINT investigacion_docente_institucion_id_fkey FOREIGN KEY (institucion_id) REFERENCES public.instituciones(id) ON DELETE CASCADE;


--
-- Name: investigacion_docente investigacion_docente_periodo_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.investigacion_docente
    ADD CONSTRAINT investigacion_docente_periodo_id_fkey FOREIGN KEY (periodo_id) REFERENCES public.periodos(id) ON DELETE SET NULL;


--
-- Name: materias materias_carrera_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.materias
    ADD CONSTRAINT materias_carrera_id_fkey FOREIGN KEY (carrera_id) REFERENCES public.carreras(id) ON DELETE SET NULL;


--
-- Name: materias materias_institucion_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.materias
    ADD CONSTRAINT materias_institucion_id_fkey FOREIGN KEY (institucion_id) REFERENCES public.instituciones(id) ON DELETE CASCADE;


--
-- Name: movimientos movimientos_departamento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movimientos
    ADD CONSTRAINT movimientos_departamento_id_fkey FOREIGN KEY (departamento_id) REFERENCES public.departamentos(id) ON DELETE CASCADE;


--
-- Name: movimientos movimientos_institucion_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movimientos
    ADD CONSTRAINT movimientos_institucion_id_fkey FOREIGN KEY (institucion_id) REFERENCES public.instituciones(id) ON DELETE CASCADE;


--
-- Name: movimientos movimientos_periodo_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movimientos
    ADD CONSTRAINT movimientos_periodo_id_fkey FOREIGN KEY (periodo_id) REFERENCES public.periodos(id) ON DELETE SET NULL;


--
-- Name: parametros_sueldos parametros_sueldos_departamento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parametros_sueldos
    ADD CONSTRAINT parametros_sueldos_departamento_id_fkey FOREIGN KEY (departamento_id) REFERENCES public.departamentos(id) ON DELETE CASCADE;


--
-- Name: parametros_sueldos parametros_sueldos_institucion_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.parametros_sueldos
    ADD CONSTRAINT parametros_sueldos_institucion_id_fkey FOREIGN KEY (institucion_id) REFERENCES public.instituciones(id) ON DELETE CASCADE;


--
-- Name: periodos periodos_departamento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.periodos
    ADD CONSTRAINT periodos_departamento_id_fkey FOREIGN KEY (departamento_id) REFERENCES public.departamentos(id) ON DELETE CASCADE;


--
-- Name: periodos periodos_institucion_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.periodos
    ADD CONSTRAINT periodos_institucion_id_fkey FOREIGN KEY (institucion_id) REFERENCES public.instituciones(id) ON DELETE CASCADE;


--
-- Name: resoluciones resoluciones_departamento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resoluciones
    ADD CONSTRAINT resoluciones_departamento_id_fkey FOREIGN KEY (departamento_id) REFERENCES public.departamentos(id) ON DELETE CASCADE;


--
-- Name: resoluciones resoluciones_institucion_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resoluciones
    ADD CONSTRAINT resoluciones_institucion_id_fkey FOREIGN KEY (institucion_id) REFERENCES public.instituciones(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict 9oMaUDkKZlHODd2y1wYniVQoMs25cB32mEb5pX6MLNzFo2AY4JKCduGvUIgP6qC

