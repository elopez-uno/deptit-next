-- DEPTIT NEXT - 6A-B3: PREPRODUCCION LOCAL. Crea los roles de preproduccion y la base VACIA deptit_next_preprod.
-- Plantilla: los marcadores de PASSWORD se reemplazan por verificadores SCRAM-SHA-256 (nunca texto plano).
-- El SQL generado contiene material de credencial: se escribe FUERA del repositorio y se borra tras aplicarlo.
-- Lo ejecuta el owner del cluster (postgres) con run_as_postgres.ps1, que conecta a deptit_next_dev SOLO como base de
-- mantenimiento: este script no lee ni escribe NADA en deptit_next_dev (roles y bases son objetos del cluster).
--   deptit_next_preprod_owner : LOGIN, owner de la base y de todos sus objetos. Solo la siembra inicial y los GRANT.
--   deptit_next_preprod_app   : LOGIN, rol de la aplicacion. Sin DDL: privilegios DML replicados de deptit_next_app
--                               por el owner DESPUES de la siembra (python -m operacion preprod-seed).
--   deptit_next_preprod_backup: LOGIN, solo lectura (pg_dump), otorgada por el owner despues de la siembra.
-- La base nace vacia (template0, misma codificacion/collation que deptit_next_dev) y SIN CONNECT para PUBLIC.
-- No crea deptit_next_prod. No toca la base deptit, ni deptit_next_dev, ni roles existentes.
\pset pager off
\pset footer off
BEGIN;

DO $$
BEGIN
  IF current_database() <> 'deptit_next_dev' THEN
    RAISE EXCEPTION 'ABORT: conectado a % (se esperaba deptit_next_dev como base de mantenimiento)', current_database();
  END IF;
  IF current_user <> 'postgres' THEN
    RAISE EXCEPTION 'ABORT: usuario % (se esperaba postgres)', current_user;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname LIKE 'deptit\_next\_preprod%') THEN
    RAISE EXCEPTION 'ABORT: algun rol de preproduccion ya existe';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_database WHERE datname IN ('deptit_next_preprod', 'deptit_next_prod')) THEN
    RAISE EXCEPTION 'ABORT: deptit_next_preprod (o deptit_next_prod) ya existe';
  END IF;
END $$;

CREATE ROLE deptit_next_preprod_owner
  LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT
  CONNECTION LIMIT 5
  PASSWORD '__OWNER_VERIFIER__';

CREATE ROLE deptit_next_preprod_app
  LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS INHERIT
  CONNECTION LIMIT 20
  PASSWORD '__APP_VERIFIER__';

CREATE ROLE deptit_next_preprod_backup
  LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT
  CONNECTION LIMIT 3
  PASSWORD '__BACKUP_VERIFIER__';

COMMIT;

-- CREATE DATABASE no admite transaccion. Misma codificacion y collation que deptit_next_dev.
CREATE DATABASE deptit_next_preprod
  OWNER deptit_next_preprod_owner
  TEMPLATE template0
  ENCODING 'UTF8'
  LOCALE_PROVIDER libc
  LC_COLLATE 'Spanish_Mexico.1252'
  LC_CTYPE 'Spanish_Mexico.1252';

REVOKE ALL ON DATABASE deptit_next_preprod FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE deptit_next_preprod TO deptit_next_preprod_owner;
GRANT CONNECT ON DATABASE deptit_next_preprod TO deptit_next_preprod_app;
GRANT CONNECT ON DATABASE deptit_next_preprod TO deptit_next_preprod_backup;

\connect deptit_next_preprod

BEGIN;
DO $$
BEGIN
  IF current_database() <> 'deptit_next_preprod' OR current_user <> 'postgres' THEN
    RAISE EXCEPTION 'ABORT: conexion inesperada (% / %)', current_database(), current_user;
  END IF;
END $$;

-- El esquema public de la base nueva pasa a ser del owner (sin privilegios para PUBLIC).
ALTER SCHEMA public OWNER TO deptit_next_preprod_owner;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO deptit_next_preprod_app;
GRANT USAGE ON SCHEMA public TO deptit_next_preprod_backup;

-- Verificaciones obligatorias: si alguna falla, se revierte (y la base vacia se borra a mano, ver runbook).
DO $$
BEGIN
  IF (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'public') <> 0 THEN
    RAISE EXCEPTION 'ABORT: la base nueva no esta vacia';
  END IF;
  IF pg_get_userbyid((SELECT datdba FROM pg_database WHERE datname = 'deptit_next_preprod')) <> 'deptit_next_preprod_owner' THEN
    RAISE EXCEPTION 'ABORT: owner inesperado de deptit_next_preprod';
  END IF;
  IF has_schema_privilege('deptit_next_preprod_app', 'public', 'CREATE')
     OR has_schema_privilege('deptit_next_preprod_backup', 'public', 'CREATE')
     OR has_database_privilege('deptit_next_preprod_app', 'deptit_next_preprod', 'CREATE')
     OR has_database_privilege('deptit_next_preprod_backup', 'deptit_next_preprod', 'CREATE') THEN
    RAISE EXCEPTION 'ABORT: el rol de la app o de backup tendria privilegios de DDL';
  END IF;
  IF has_database_privilege('deptit_next_preprod_owner', 'deptit', 'CONNECT')
     OR has_database_privilege('deptit_next_preprod_app', 'deptit', 'CONNECT')
     OR has_database_privilege('deptit_next_preprod_backup', 'deptit', 'CONNECT') THEN
    RAISE EXCEPTION 'ABORT: un rol de preproduccion puede conectarse a deptit';
  END IF;
  IF has_database_privilege('deptit_next_app', 'deptit_next_preprod', 'CONNECT')
     OR has_database_privilege('deptit_next_backup', 'deptit_next_preprod', 'CONNECT')
     OR has_database_privilege('deptit_next_restore', 'deptit_next_preprod', 'CONNECT') THEN
    RAISE EXCEPTION 'ABORT: un rol de desarrollo puede conectarse a deptit_next_preprod';
  END IF;
END $$;
COMMIT;

\echo '== Roles de preproduccion'
SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolinherit, rolcanlogin, rolconnlimit
  FROM pg_roles WHERE rolname LIKE 'deptit\_next\_preprod%' ORDER BY 1;
\echo '== Base'
SELECT datname, pg_get_userbyid(datdba) AS owner, pg_encoding_to_char(encoding) AS encoding, datcollate, datctype,
       datacl::text
  FROM pg_database WHERE datname = 'deptit_next_preprod';
