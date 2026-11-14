-- DEPTIT NEXT - Fase 1: auditoria SOLO LECTURA de deptit_next_dev.
-- Se ejecuta con default_transaction_read_only=on y dentro de BEGIN READ ONLY.
\pset pager off
\pset footer off
BEGIN TRANSACTION READ ONLY;

DO $$
BEGIN
  IF current_database() <> 'deptit_next_dev' THEN
    RAISE EXCEPTION 'ABORT: conectado a % (se esperaba deptit_next_dev)', current_database();
  END IF;
END $$;

\echo '== Sesion'
SELECT version(), current_database(), current_user, current_setting('transaction_read_only') AS tx_read_only;

\echo '== Bases de datos'
SELECT d.datname, pg_get_userbyid(d.datdba) AS owner, d.datacl, pg_size_pretty(pg_database_size(d.oid)) AS size
FROM pg_database d ORDER BY d.datname;

\echo '== Roles (no sistema)'
SELECT rolname, rolsuper, rolinherit, rolcreaterole, rolcreatedb, rolcanlogin, rolreplication, rolbypassrls, rolconnlimit
FROM pg_roles WHERE rolname !~ '^pg_' ORDER BY rolname;

\echo '== deptit_next_app existe?'
SELECT count(*) AS deptit_next_app_exists FROM pg_roles WHERE rolname = 'deptit_next_app';

\echo '== Membresias de roles'
SELECT r.rolname AS role, m.rolname AS member FROM pg_auth_members am
JOIN pg_roles r ON r.oid = am.roleid JOIN pg_roles m ON m.oid = am.member
WHERE r.rolname !~ '^pg_' ORDER BY 1, 2;

\echo '== Settings por rol/base'
SELECT coalesce(d.datname, '*') AS db, coalesce(r.rolname, '*') AS role, s.setconfig
FROM pg_db_role_setting s LEFT JOIN pg_database d ON d.oid = s.setdatabase LEFT JOIN pg_roles r ON r.oid = s.setrole;

\echo '== Esquemas'
SELECT n.nspname, pg_get_userbyid(n.nspowner) AS owner, n.nspacl
FROM pg_namespace n WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema' ORDER BY 1;

\echo '== Extensiones'
SELECT extname, extversion, n.nspname AS schema FROM pg_extension e JOIN pg_namespace n ON n.oid = e.extnamespace ORDER BY 1;

\echo '== Relaciones por esquema/tipo/owner'
SELECT n.nspname, c.relkind, pg_get_userbyid(c.relowner) AS owner, count(*)
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema' AND c.relkind IN ('r','p','v','m','S','f')
GROUP BY 1, 2, 3 ORDER BY 1, 2, 3;

\echo '== ACLs distintos en tablas/vistas/secuencias'
SELECT n.nspname, c.relkind, c.relacl::text AS acl, count(*)
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema' AND c.relkind IN ('r','p','v','m','S','f')
GROUP BY 1, 2, 3 ORDER BY 1, 2, 3;

\echo '== Tablas con RLS'
SELECT n.nspname, c.relname, c.relrowsecurity, c.relforcerowsecurity
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind IN ('r','p') AND (c.relrowsecurity OR c.relforcerowsecurity);

\echo '== Funciones/procedimientos por esquema/tipo/owner'
SELECT n.nspname, p.prokind, pg_get_userbyid(p.proowner) AS owner, p.prosecdef AS security_definer, count(*)
FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
GROUP BY 1, 2, 3, 4 ORDER BY 1, 2, 3, 4;

\echo '== ACLs distintos en funciones'
SELECT n.nspname, p.proacl::text AS acl, count(*)
FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
GROUP BY 1, 2 ORDER BY 1, 2;

\echo '== Tipos/dominios definidos por usuario'
SELECT n.nspname, t.typtype, pg_get_userbyid(t.typowner) AS owner, count(*)
FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema' AND t.typtype IN ('d','e','c','r','m')
  AND NOT EXISTS (SELECT 1 FROM pg_class c WHERE c.oid = t.typrelid AND c.relkind <> 'c')
GROUP BY 1, 2, 3 ORDER BY 1, 2, 3;

\echo '== Default privileges'
SELECT pg_get_userbyid(d.defaclrole) AS role, n.nspname, d.defaclobjtype, d.defaclacl
FROM pg_default_acl d LEFT JOIN pg_namespace n ON n.oid = d.defaclnamespace;

\echo '== Large objects'
SELECT count(*) AS large_objects FROM pg_largeobject_metadata;

\echo '== Ubicacion de tablas clave'
SELECT table_schema, table_name FROM information_schema.tables
WHERE table_name IN ('app_usuarios', 'instituciones', 'departamentos') ORDER BY 2, 1;

\echo '== Columnas de tablas clave'
SELECT table_schema, table_name, string_agg(column_name, ', ' ORDER BY ordinal_position) AS columns
FROM information_schema.columns
WHERE table_name IN ('app_usuarios', 'instituciones', 'departamentos') GROUP BY 1, 2 ORDER BY 2, 1;

\echo '== Estadisticas de escritura por base (baseline)'
SELECT now() AS ts, datname, numbackends, xact_commit, xact_rollback, tup_inserted, tup_updated, tup_deleted, sessions
FROM pg_stat_database WHERE datname IN ('deptit', 'deptit_next_dev') ORDER BY datname;

\echo '== Sesiones activas por base/usuario'
SELECT datname, usename, application_name, count(*) FROM pg_stat_activity
WHERE datname IS NOT NULL GROUP BY 1, 2, 3 ORDER BY 1, 2, 3;

ROLLBACK;
