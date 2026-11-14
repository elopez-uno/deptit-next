-- DEPTIT NEXT - 6A-B2: roles OPERATIVOS de desarrollo local (backup y restore drill), SOLO sobre deptit_next_dev.
-- Plantilla: los marcadores de PASSWORD se reemplazan por verificadores SCRAM-SHA-256 (nunca texto plano).
-- El SQL generado contiene material de credencial: se escribe FUERA del repositorio y se borra tras aplicarlo.
--   deptit_next_backup : LOGIN, solo lectura (SELECT en tablas y secuencias de public de deptit_next_dev). pg_dump.
--   deptit_next_restore: LOGIN + CREATEDB, sin acceso a deptit_next_dev. Crea/borra SOLO sus bases de prueba
--                        (deptit_next_restore_test_*): PostgreSQL solo deja borrar bases propias.
-- No modifica owners ni roles existentes, no toca la base deptit ni su ACL.
\pset pager off
\pset footer off
BEGIN;

DO $$
BEGIN
  IF current_database() <> 'deptit_next_dev' THEN
    RAISE EXCEPTION 'ABORT: conectado a % (se esperaba deptit_next_dev)', current_database();
  END IF;
  IF current_user <> 'postgres' THEN
    RAISE EXCEPTION 'ABORT: usuario % (se esperaba postgres)', current_user;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname IN ('deptit_next_backup', 'deptit_next_restore')) THEN
    RAISE EXCEPTION 'ABORT: algun rol operativo ya existe';
  END IF;
END $$;

CREATE ROLE deptit_next_backup
  LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT
  CONNECTION LIMIT 3
  PASSWORD '__BACKUP_VERIFIER__';

CREATE ROLE deptit_next_restore
  LOGIN NOSUPERUSER CREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT
  CONNECTION LIMIT 5
  PASSWORD '__RESTORE_VERIFIER__';

GRANT CONNECT ON DATABASE deptit_next_dev TO deptit_next_backup;
GRANT USAGE ON SCHEMA public TO deptit_next_backup;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO deptit_next_backup;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO deptit_next_backup;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT SELECT ON TABLES TO deptit_next_backup;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT SELECT ON SEQUENCES TO deptit_next_backup;

-- Verificaciones obligatorias: si alguna falla, se revierte todo.
DO $$
DECLARE n int;
BEGIN
  SELECT count(*) INTO n FROM pg_class c JOIN pg_namespace s ON s.oid = c.relnamespace
   WHERE s.nspname = 'public' AND c.relkind IN ('r', 'p', 'S')
     AND NOT has_table_privilege('deptit_next_backup', c.oid, 'SELECT');
  IF n <> 0 THEN RAISE EXCEPTION 'ABORT: % relaciones sin SELECT para deptit_next_backup', n; END IF;
  SELECT count(*) INTO n FROM pg_class c JOIN pg_namespace s ON s.oid = c.relnamespace
   WHERE s.nspname = 'public' AND c.relkind IN ('r', 'p')
     AND (has_table_privilege('deptit_next_backup', c.oid, 'INSERT')
          OR has_table_privilege('deptit_next_backup', c.oid, 'UPDATE')
          OR has_table_privilege('deptit_next_backup', c.oid, 'DELETE')
          OR has_table_privilege('deptit_next_backup', c.oid, 'TRUNCATE'));
  IF n <> 0 THEN RAISE EXCEPTION 'ABORT: deptit_next_backup tiene privilegios de escritura'; END IF;
  IF has_database_privilege('deptit_next_backup', 'deptit', 'CONNECT')
     OR has_database_privilege('deptit_next_restore', 'deptit', 'CONNECT') THEN
    RAISE EXCEPTION 'ABORT: un rol operativo puede conectarse a deptit';
  END IF;
  IF has_database_privilege('deptit_next_restore', 'deptit_next_dev', 'CONNECT')
     AND has_schema_privilege('deptit_next_restore', 'public', 'USAGE')
     AND EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace s ON s.oid = c.relnamespace
                  WHERE s.nspname = 'public' AND c.relkind = 'r'
                    AND has_table_privilege('deptit_next_restore', c.oid, 'SELECT')) THEN
    RAISE EXCEPTION 'ABORT: deptit_next_restore puede leer deptit_next_dev';
  END IF;
END $$;

COMMIT;

SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolcanlogin, rolconnlimit
  FROM pg_roles WHERE rolname IN ('deptit_next_backup', 'deptit_next_restore') ORDER BY 1;
