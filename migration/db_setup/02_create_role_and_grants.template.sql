-- DEPTIT NEXT - Fase 2: crear deptit_next_app y otorgar permisos SOLO en deptit_next_dev.
-- Plantilla: el marcador de PASSWORD se reemplaza por un verificador SCRAM-SHA-256 (nunca texto plano).
-- El SQL generado contiene material de credencial: se escribe FUERA del repositorio y se borra tras aplicarlo.
-- Privilegios: replica exacta de los que tiene deptit_app en deptit_next_dev (minimo privilegio).
-- No modifica owners, no toca la base deptit ni su ACL.
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
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'deptit_next_app') THEN
    RAISE EXCEPTION 'ABORT: el rol deptit_next_app ya existe';
  END IF;
END $$;

CREATE ROLE deptit_next_app
  LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS INHERIT
  CONNECTION LIMIT 20
  PASSWORD '__SCRAM_VERIFIER__';

GRANT CONNECT ON DATABASE deptit_next_dev TO deptit_next_app;
GRANT USAGE ON SCHEMA public TO deptit_next_app;

-- Replica de privilegios de deptit_app sobre tablas, vistas y secuencias (y columnas, si las hubiera).
DO $$
DECLARE
  r record;
  src oid := 'deptit_app'::regrole;
BEGIN
  FOR r IN
    SELECT n.nspname, c.relname, c.relkind,
           string_agg(DISTINCT a.privilege_type, ', ') AS privs
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    CROSS JOIN LATERAL aclexplode(c.relacl) a
    WHERE a.grantee = src AND c.relkind IN ('r', 'p', 'v', 'm', 'f', 'S')
    GROUP BY 1, 2, 3
  LOOP
    EXECUTE format('GRANT %s ON %s %I.%I TO deptit_next_app',
                   r.privs, CASE WHEN r.relkind = 'S' THEN 'SEQUENCE' ELSE 'TABLE' END,
                   r.nspname, r.relname);
  END LOOP;

  FOR r IN
    SELECT n.nspname, c.relname, at.attname, string_agg(DISTINCT a.privilege_type, ', ') AS privs
    FROM pg_attribute at
    JOIN pg_class c ON c.oid = at.attrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    CROSS JOIN LATERAL aclexplode(at.attacl) a
    WHERE a.grantee = src AND at.attnum > 0 AND NOT at.attisdropped
    GROUP BY 1, 2, 3
  LOOP
    EXECUTE format('GRANT %s (%I) ON TABLE %I.%I TO deptit_next_app',
                   r.privs, r.attname, r.nspname, r.relname);
  END LOOP;
END $$;

-- Funciones del esquema public: EXECUTE explicito (PUBLIC ya lo tiene por defecto).
DO $$
DECLARE f record;
BEGIN
  FOR f IN SELECT p.oid::regprocedure AS sig FROM pg_proc p
           JOIN pg_namespace n ON n.oid = p.pronamespace
           WHERE n.nspname = 'public' AND p.prokind IN ('f', 'p')
  LOOP
    EXECUTE format('GRANT EXECUTE ON ROUTINE %s TO deptit_next_app', f.sig);
  END LOOP;
END $$;

-- Verificaciones obligatorias: si alguna falla, se revierte todo.
DO $$
DECLARE mismatches int;
BEGIN
  IF has_database_privilege('deptit_next_app', 'deptit', 'CONNECT') THEN
    RAISE EXCEPTION 'ABORT: deptit_next_app tendria CONNECT sobre deptit';
  END IF;
  IF NOT has_database_privilege('deptit_next_app', 'deptit_next_dev', 'CONNECT') THEN
    RAISE EXCEPTION 'ABORT: deptit_next_app no tiene CONNECT sobre deptit_next_dev';
  END IF;
  SELECT count(*) INTO mismatches FROM (
    SELECT c.oid, p.priv,
           has_table_privilege('deptit_app', c.oid, p.priv) AS src,
           has_table_privilege('deptit_next_app', c.oid, p.priv) AS dst
    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    CROSS JOIN unnest(ARRAY['SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER']) p(priv)
    WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
    UNION ALL
    SELECT c.oid, p.priv,
           has_sequence_privilege('deptit_app', c.oid, p.priv),
           has_sequence_privilege('deptit_next_app', c.oid, p.priv)
    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    CROSS JOIN unnest(ARRAY['SELECT','USAGE','UPDATE']) p(priv)
    WHERE n.nspname = 'public' AND c.relkind = 'S'
  ) x WHERE src IS DISTINCT FROM dst;
  IF mismatches <> 0 THEN
    RAISE EXCEPTION 'ABORT: % diferencias de privilegios entre deptit_app y deptit_next_app', mismatches;
  END IF;
END $$;

COMMIT;

\echo '== Rol creado'
SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls, rolcanlogin, rolconnlimit,
       left(rolpassword, 14) AS password_method
FROM pg_authid WHERE rolname = 'deptit_next_app';

\echo '== CONNECT por base para deptit_next_app'
SELECT datname, has_database_privilege('deptit_next_app', datname, 'CONNECT') AS can_connect
FROM pg_database WHERE datname IN ('deptit', 'deptit_next_dev') ORDER BY 1;

\echo '== Privilegios de deptit_next_app en tablas/secuencias (resumen)'
SELECT c.relkind, c.relacl::text ~ 'deptit_next_app=' AS has_grant,
       (SELECT string_agg(DISTINCT a.privilege_type, ',') FROM aclexplode(c.relacl) a
         WHERE a.grantee = 'deptit_next_app'::regrole) AS privs,
       count(*)
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind IN ('r', 'S')
GROUP BY 1, 2, 3 ORDER BY 1, 2, 3;

\echo '== Tablas solo-insert/select (ar)'
SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind = 'r'
  AND has_table_privilege('deptit_next_app', c.oid, 'INSERT') AND NOT has_table_privilege('deptit_next_app', c.oid, 'UPDATE');

\echo '== Tablas/secuencias SIN acceso para deptit_next_app (igual que deptit_app)'
SELECT c.relkind, c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind IN ('r', 'S')
  AND CASE WHEN c.relkind = 'S'
           THEN NOT has_sequence_privilege('deptit_next_app', c.oid, 'SELECT, USAGE, UPDATE')
           ELSE NOT has_any_column_privilege('deptit_next_app', c.oid, 'SELECT, INSERT, UPDATE, REFERENCES')
                AND NOT has_table_privilege('deptit_next_app', c.oid, 'DELETE, TRUNCATE, TRIGGER') END
ORDER BY 1, 2;

\echo '== Funciones'
SELECT p.oid::regprocedure AS routine, p.proacl FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE n.nspname = 'public';

\echo '== Datos academicos (sin cambios esperados)'
SELECT (SELECT count(*) FROM public.app_usuarios) AS app_usuarios,
       (SELECT count(*) FROM public.instituciones) AS instituciones,
       (SELECT count(*) FROM public.departamentos) AS departamentos;

\echo '== Estadisticas de escritura por base'
SELECT now() AS ts, datname, numbackends, xact_commit, xact_rollback, tup_inserted, tup_updated, tup_deleted, sessions
FROM pg_stat_database WHERE datname IN ('deptit', 'deptit_next_dev') ORDER BY datname;
