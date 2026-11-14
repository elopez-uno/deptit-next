#!/usr/bin/env bash
# DEPTIT NEXT - inicializacion del cluster PostgreSQL del stack Docker (UNICA vez, primer arranque).
#
# Lo ejecuta el entrypoint de postgres:18 con /docker-entrypoint-initdb.d VACIO (volumen nuevo) y
# `postgres` (superusuario) conectado por socket a la base de mantenimiento `$POSTGRES_DB`.
# Si CUALQUIER paso falla el script aborta y el contenedor muere: el stack no llega a levantarse
# con una base a medias (fail-closed; Docker/README.md seccion "Primer arranque").
#
# Entrada (db.env del servidor; NADA de esto vive en el repositorio):
#   DEPTIT_ENTORNO                 desarrollo | produccion (preproduccion no existe en Docker)
#   DEPTIT_DB_NAME                 deptit_next_dev (desarrollo) | deptit_next_prod (produccion)
#   DEPTIT_APP_DB_USER/PASSWORD    rol de la aplicacion (DML, sin DDL)
#   DEPTIT_OWNER_DB_USER/PASSWORD  owner de la base y de todos sus objetos
#   DEPTIT_BACKUP_DB_USER/PASSWORD   solo lectura (pg_dump)
#   DEPTIT_RESTORE_DB_USER/PASSWORD  CREATEDB para restore drills
#
# El script REEMPLAZA a Docker/migration/db_setup/*.template.sql para Docker (mismo modelo: roles
# operativos de 03, base vacia de 04, esquema versionado de runbook 2.5, grants de
# operacion/preprod.py::otorgar_app / otorgar_backup). Las contrasenas viajan solo como variables
# de entorno del contenedor db y entran a PostgreSQL citadas por psql con :'nombre' (SQL plano:
# psql las escapa como literal) para que PostgreSQL guarde el verificador SCRAM-SHA-256.
#
# NOTA tecnica: los bloques DO $$...$$ NO interpolan variables de psql (psql las deshabilita
# dentro de dollar-quotes), por eso los IDENTIFICADORES van interpolados por este script tras
# validarlos con IDENT_RE (minusculas/digitos/_), y solo las CONTRASENAS se pasan como :-vars.
#
# Modelo de privilegios (la app NUNCA es owner ni tiene DDL: backend/db.py::verify_privileges):
#   owner    : duenio de la base, del esquema public y de todos los objetos. Solo init y GRANT.
#   app      : CONNECT + USAGE(public) + DML en todo + EXECUTE en routines. Sin DDL.
#   backup   : CONNECT + USAGE + SELECT en todo (incluidas default privileges del owner).
#   restore  : CREATEDB, solo CONNECT a la base de mantenimiento postgres (para dropdb/createdb
#              de bases deptit_next_restore_test_*; restore_db.py usa MAINTENANCE_DB=postgres).
set -euo pipefail

die() { echo "INITDB DEPTIT: ERROR: $*" >&2; exit 1; }
note() { echo "INITDB DEPTIT: $*"; }

# --------------------------------------------------------------------- 0. validacion de entrada
[ "$(id -un)" = postgres ] || die "este script lo ejecuta el entrypoint de postgres (uid postgres), no $(id -un)"
[ "${POSTGRES_USER:-}" = postgres ] || die "POSTGRES_USER debe ser exactamente 'postgres' (superuser del cluster)"
: "${POSTGRES_PASSWORD:?db.env debe definir POSTGRES_PASSWORD}"
for v in DEPTIT_ENTORNO DEPTIT_DB_NAME DEPTIT_APP_DB_USER DEPTIT_APP_DB_PASSWORD \
         DEPTIT_OWNER_DB_USER DEPTIT_OWNER_DB_PASSWORD \
         DEPTIT_BACKUP_DB_USER DEPTIT_BACKUP_DB_PASSWORD \
         DEPTIT_RESTORE_DB_USER DEPTIT_RESTORE_DB_PASSWORD; do
    eval "val=\${$v:-}"
    [ -n "$val" ] || die "db.env debe definir $v"
done

ENTORNO="$DEPTIT_ENTORNO"
DB_NAME="$DEPTIT_DB_NAME"
APP_USER="$DEPTIT_APP_DB_USER"
OWNER_USER="$DEPTIT_OWNER_DB_USER"
BACKUP_USER="$DEPTIT_BACKUP_DB_USER"
RESTORE_USER="$DEPTIT_RESTORE_DB_USER"

# Contrasenas >= 48 caracteres (mismo criterio de Docker/migration/db_setup/generate_role_secret.py:
# 48 bytes aleatorios -> 64 caracteres URL-safe, 384 bits).
for v in DEPTIT_APP_DB_PASSWORD DEPTIT_OWNER_DB_PASSWORD DEPTIT_BACKUP_DB_PASSWORD DEPTIT_RESTORE_DB_PASSWORD; do
    eval "val=\${$v}"
    [ "${#val}" -ge 48 ] || die "$v: menos de 48 caracteres"
done

# Identificadores: estrictamente [a-z_][a-z0-9_]{0,62}. Con esto la interpolacion de bash en el
# SQL es segura (no puede escapar un literal ni inyectar sintaxis).
IDENT_RE='^[a-z_][a-z0-9_]{0,62}$'
for r in "$DB_NAME" "$APP_USER" "$OWNER_USER" "$BACKUP_USER" "$RESTORE_USER"; do
    printf '%s' "$r" | grep -Eq "$IDENT_RE" || die "identificador invalido: $r (minusculas, digitos, _)"
done
for r in "$APP_USER" "$OWNER_USER" "$BACKUP_USER" "$RESTORE_USER"; do
    [ "$r" != postgres ] && [ "$r" != deptit_app ] || die "rol prohibido (settings.ROLES_PROHIBIDOS): $r"
done
# Los roles operativos deben ser distintos entre si y del rol de la app (operacion/config.py).
[ "$APP_USER" != "$OWNER_USER" ] && [ "$APP_USER" != "$BACKUP_USER" ] && [ "$APP_USER" != "$RESTORE_USER" ] \
    && [ "$OWNER_USER" != "$BACKUP_USER" ] && [ "$OWNER_USER" != "$RESTORE_USER" ] \
    && [ "$BACKUP_USER" != "$RESTORE_USER" ] || die "app, owner, backup y restore deben ser roles distintos"

# Guardas de entorno del propio backend (settings.py: BASES / ROL_DESARROLLO / BASES_PROHIBIDAS):
# el init no debe poder crear una combinacion que la aplicacion rechazaria al arrancar.
case "$ENTORNO" in
    desarrollo)
        [ "$DB_NAME" = deptit_next_dev ] || die "desarrollo exige la base deptit_next_dev"
        [ "$APP_USER" = deptit_next_app ] || die "desarrollo exige el rol exactamente deptit_next_app (settings.ROL_DESARROLLO)"
        ;;
    produccion)
        [ "$DB_NAME" = deptit_next_prod ] || die "produccion exige la base deptit_next_prod"
        [ "$APP_USER" != deptit_next_app ] || die "produccion exige un rol propio: deptit_next_app es el rol de desarrollo (settings)"
        ;;
    *) die "DEPTIT_ENTORNO=$ENTORNO no es valido en el stack Docker (desarrollo | produccion)" ;;
esac
case "$DB_NAME" in deptit | postgres | template0 | template1) die "base prohibida: $DB_NAME" ;; esac

SCHEMA_SQL=/schema/0001_baseline_schema.sql
SCHEMA_MANIFEST=/schema/0001_baseline_schema.sql.manifest.json
[ -f "$SCHEMA_SQL" ] && [ -f "$SCHEMA_MANIFEST" ] \
    || die "falta $SCHEMA_SQL (+ manifest): el mount ./migration/schema no esta en compose"

# Del manifest versionado: SHA-256 del archivo (integridad de lo que se aplica) y huella/conteos
# esperados del esquema resultante (verificacion post-aplicacion). Sin python3 en la imagen: sed/grep.
manifest_num() { sed -n "s/.*\"$1\": *\([0-9]\+\).*/\1/p" "$SCHEMA_MANIFEST" | head -1; }
SCHEMA_SHA256=$(sed -n 's/.*"sha256": *"\([0-9a-f]\{64\}\)".*/\1/p' "$SCHEMA_MANIFEST" | head -1)
TABLAS=$(manifest_num tablas)
SECUENCIAS=$(manifest_num secuencias)
RESTRICCIONES=$(manifest_num restricciones)
INDICES=$(manifest_num indices)
for v in SCHEMA_SHA256 TABLAS SECUENCIAS RESTRICCIONES INDICES; do
    eval "val=\${$v:-}"
    [ -n "$val" ] || die "manifest del esquema incompleto (falta $v)"
done

# El esquema que se va a aplicar debe ser el certificado (SHA-256 contra el manifest versionado).
ACTUAL=$(sha256sum "$SCHEMA_SQL" | awk '{print $1}')
[ "$ACTUAL" = "$SCHEMA_SHA256" ] || die "el esquema no coincide con el manifest versionado (sha256): no se aplica nada"

MAINTENANCE_DB="${POSTGRES_DB:-$POSTGRES_USER}"
PSQL="psql -X -v ON_ERROR_STOP=1 --username $POSTGRES_USER"

note "entorno=$ENTORNO base=$DB_NAME (app=$APP_USER owner=$OWNER_USER backup=$BACKUP_USER restore=$RESTORE_USER)"
note "esquema certificado: sha256=${ACTUAL:0:16}... tablas=$TABLAS secuencias=$SECUENCIAS restricciones=$RESTRICCIONES indices=$INDICES"

# ---------------------------------------------------------------- 1. roles del cluster (en transaccion)
# Contrasenas: :-vars de psql citadas con :'nombre' en SQL plano (fuera de dollar-quotes).
$PSQL --dbname "$MAINTENANCE_DB" \
    -v app_pw="$DEPTIT_APP_DB_PASSWORD" -v owner_pw="$DEPTIT_OWNER_DB_PASSWORD" \
    -v backup_pw="$DEPTIT_BACKUP_DB_PASSWORD" -v restore_pw="$DEPTIT_RESTORE_DB_PASSWORD" <<EOSQL
BEGIN;
DO \$\$
BEGIN
  IF current_user <> 'postgres' THEN
    RAISE EXCEPTION 'ABORT: usuario % (se esperaba postgres)', current_user;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname IN ('$APP_USER', '$OWNER_USER', '$BACKUP_USER', '$RESTORE_USER')) THEN
    RAISE EXCEPTION 'ABORT: algun rol del entorno ya existe';
  END IF;
END \$\$;
-- app: INHERIT, DML, sin DDL (backend/db.py::verify_privileges exige exactamente esto).
CREATE ROLE $APP_USER LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS INHERIT
  CONNECTION LIMIT 20 PASSWORD :'app_pw';
-- owner: NOINHERIT, duenio de la base y sus objetos (solo init/GRANT; la app nunca conecta como el).
CREATE ROLE $OWNER_USER LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT
  CONNECTION LIMIT 5 PASSWORD :'owner_pw';
-- backup: solo lectura para pg_dump (modelo: 03_create_ops_roles.template.sql).
CREATE ROLE $BACKUP_USER LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT
  CONNECTION LIMIT 3 PASSWORD :'backup_pw';
-- restore: CREATEDB para restore drills; SIN CONNECT a la base del entorno.
CREATE ROLE $RESTORE_USER LOGIN NOSUPERUSER CREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT
  CONNECTION LIMIT 5 PASSWORD :'restore_pw';
COMMIT;
EOSQL
note "roles creados"

# ------------------------------------------------------- 2. base del entorno (CREATE DATABASE no es transaccion)
$PSQL --dbname "$MAINTENANCE_DB" <<EOSQL
DO \$\$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_database WHERE datname = '$DB_NAME') THEN
    RAISE EXCEPTION 'ABORT: la base $DB_NAME ya existe';
  END IF;
END \$\$;
-- Misma codificacion que template0 (UTF8); locale del cluster (en_US.utf8 en la imagen postgres).
CREATE DATABASE $DB_NAME OWNER $OWNER_USER TEMPLATE template0 ENCODING 'UTF8';
-- Solo los roles del entorno se conectan; PUBLIC sin CONNECT (modelo: 04_create_preprod.template.sql).
REVOKE ALL ON DATABASE $DB_NAME FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE $DB_NAME TO $OWNER_USER;
GRANT CONNECT ON DATABASE $DB_NAME TO $APP_USER;
GRANT CONNECT ON DATABASE $DB_NAME TO $BACKUP_USER;
-- restore drills: createdb/dropdb corren contra la base de mantenimiento (postgres). OJO: initdb
-- deja CONNECT para PUBLIC en TODA base, incluida postgres; hay que retirarlo o la verificacion de
-- la fase 5 (ni app ni backup conectan a la de mantenimiento) fallaria siempre.
REVOKE ALL ON DATABASE postgres FROM PUBLIC;
GRANT CONNECT ON DATABASE postgres TO $RESTORE_USER;
EOSQL
note "base $DB_NAME creada"

# --------------------------------------- 3. esquema public: owner + ACL base (transaccion, como postgres)
$PSQL --dbname "$DB_NAME" <<EOSQL
BEGIN;
DO \$\$
BEGIN
  IF current_database() <> '$DB_NAME' OR current_user <> 'postgres' THEN
    RAISE EXCEPTION 'ABORT: conexion inesperada (% / %)', current_database(), current_user;
  END IF;
  IF (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
       WHERE n.nspname = 'public') <> 0 THEN
    RAISE EXCEPTION 'ABORT: la base nueva no esta vacia';
  END IF;
END \$\$;
-- El esquema public de la base nueva pasa a ser del owner (sin privilegios para PUBLIC).
ALTER SCHEMA public OWNER TO $OWNER_USER;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO $APP_USER;
GRANT USAGE ON SCHEMA public TO $BACKUP_USER;
COMMIT;
EOSQL
note "esquema public: owner=$OWNER_USER, ACL base aplicada"

# ------------------------------------- 4. esquema certificado (UNA transaccion, ejecutandolo como el owner)
# SET ROLE desde postgres: los objetos quedan del owner sin usar su contrasena. La transaccion
# unica garantiza base-vacia-o-esquema-completo. El dump trae su propio par \restrict/\unrestrict.
$PSQL --dbname "$DB_NAME" --single-transaction <<EOSQL
SET ROLE $OWNER_USER;
\\i $SCHEMA_SQL
DO \$\$
DECLARE n int;
BEGIN
  -- Esquema aplicado INTEGRO: mismos objetos que certifico el manifest versionado.
  SELECT count(*) INTO n FROM pg_class c JOIN pg_namespace s ON s.oid = c.relnamespace
    WHERE s.nspname = 'public' AND c.relkind IN ('r', 'p');
  IF n <> $TABLAS THEN RAISE EXCEPTION 'ABORT: se esperaban $TABLAS tablas/particiones y hay %', n; END IF;
  SELECT count(*) INTO n FROM pg_class c JOIN pg_namespace s ON s.oid = c.relnamespace
    WHERE s.nspname = 'public' AND c.relkind = 'S';
  IF n <> $SECUENCIAS THEN RAISE EXCEPTION 'ABORT: se esperaban $SECUENCIAS secuencias y hay %', n; END IF;
  -- Restricciones e indices: mismas consultas de operacion/comparacion.py (huella_esquema) que
  -- generaron el manifest versionado.
  SELECT count(*) INTO n
    FROM pg_constraint k JOIN pg_class c ON c.oid = k.conrelid JOIN pg_namespace s ON s.oid = c.relnamespace
   WHERE s.nspname = 'public';
  IF n <> $RESTRICCIONES THEN RAISE EXCEPTION 'ABORT: se esperaban $RESTRICCIONES restricciones y hay %', n; END IF;
  SELECT count(*) INTO n FROM pg_indexes WHERE schemaname = 'public';
  IF n <> $INDICES THEN RAISE EXCEPTION 'ABORT: se esperaban $INDICES indices y hay %', n; END IF;
  -- Nace SIN cuentas: el primer superadmin se crea con bootstrap (runbook 6).
  IF (SELECT count(*) FROM public.app_usuarios) <> 0 THEN
    RAISE EXCEPTION 'ABORT: el esquema certificado no puede contener datos';
  END IF;
  -- Todo objeto quedo del owner (la app nunca es owner: db.py::verify_privileges).
  IF EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
              WHERE n.nspname = 'public' AND pg_get_userbyid(c.relowner) <> '$OWNER_USER') THEN
    RAISE EXCEPTION 'ABORT: hay objetos que no quedaron del owner';
  END IF;
END \$\$;
EOSQL
note "esquema certificado aplicado como owner ($TABLAS tablas, $SECUENCIAS secuencias)"

# ------------------------------------------------- 5. grants de la app y de backup (transaccion, como owner)
# Replica el modelo de operacion/preprod.py (otorgar_app / otorgar_backup) sobre el esquema
# recien creado: DML en tablas + SELECT,USAGE en secuencias (los INSERT con bigint identity las
# necesitan), EXECUTE en routines, SELECT total para backup y default privileges del owner.
$PSQL --dbname "$DB_NAME" --single-transaction <<EOSQL
SET ROLE $OWNER_USER;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO $APP_USER;
GRANT SELECT, USAGE ON ALL SEQUENCES IN SCHEMA public TO $APP_USER;
GRANT EXECUTE ON ALL ROUTINES IN SCHEMA public TO $APP_USER;
-- b12h_audit_log es append-only (triggers b12h_audit_log_no_update_delete / no_truncate): la app
-- solo INSERT+SELECT, como deptit_next_app en desarrollo (docs/periodos_analysis.md §B12H).
REVOKE UPDATE, DELETE, TRUNCATE ON public.b12h_audit_log FROM $APP_USER;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO $BACKUP_USER;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO $BACKUP_USER;
ALTER DEFAULT PRIVILEGES FOR ROLE $OWNER_USER IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO $APP_USER;
ALTER DEFAULT PRIVILEGES FOR ROLE $OWNER_USER IN SCHEMA public
  GRANT SELECT, USAGE ON SEQUENCES TO $APP_USER;
ALTER DEFAULT PRIVILEGES FOR ROLE $OWNER_USER IN SCHEMA public
  GRANT SELECT ON TABLES TO $BACKUP_USER;
ALTER DEFAULT PRIVILEGES FOR ROLE $OWNER_USER IN SCHEMA public
  GRANT SELECT ON SEQUENCES TO $BACKUP_USER;
-- Verificaciones obligatorias: si alguna falla, se revierte todo.
DO \$\$
DECLARE n int;
BEGIN
  -- La app tiene DML en todo y no tiene DDL en ningun lado.
  SELECT count(*) INTO n FROM pg_class c JOIN pg_namespace s ON s.oid = c.relnamespace
   WHERE s.nspname = 'public' AND c.relkind IN ('r', 'p', 'S')
     AND NOT has_table_privilege('$APP_USER', c.oid, 'SELECT');
  IF n <> 0 THEN RAISE EXCEPTION 'ABORT: % relaciones sin SELECT para la app', n; END IF;
  SELECT count(*) INTO n FROM pg_class c JOIN pg_namespace s ON s.oid = c.relnamespace
   WHERE s.nspname = 'public' AND c.relkind IN ('r', 'p')
     AND NOT has_any_column_privilege('$APP_USER', c.oid, 'INSERT');
  IF n <> 0 THEN RAISE EXCEPTION 'ABORT: % tablas sin INSERT para la app', n; END IF;
  IF has_schema_privilege('$APP_USER', 'public', 'CREATE')
     OR has_database_privilege('$APP_USER', '$DB_NAME', 'CREATE') THEN
    RAISE EXCEPTION 'ABORT: el rol de la app tendria privilegios de DDL';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
              WHERE n.nspname = 'public' AND pg_get_userbyid(c.relowner) = '$APP_USER') THEN
    RAISE EXCEPTION 'ABORT: la app es owner de objetos';
  END IF;
  -- Auditoria append-only: la app escribe pero no modifica ni borra.
  IF NOT has_table_privilege('$APP_USER', 'public.b12h_audit_log', 'SELECT, INSERT')
     OR has_table_privilege('$APP_USER', 'public.b12h_audit_log', 'UPDATE')
     OR has_table_privilege('$APP_USER', 'public.b12h_audit_log', 'DELETE')
     OR has_table_privilege('$APP_USER', 'public.b12h_audit_log', 'TRUNCATE') THEN
    RAISE EXCEPTION 'ABORT: privilegios incorrectos de la app sobre b12h_audit_log (append-only)';
  END IF;
  -- backup: SELECT en todo, sin escritura (modelo: preprod.problemas_backup).
  SELECT count(*) INTO n FROM pg_class c JOIN pg_namespace s ON s.oid = c.relnamespace
   WHERE s.nspname = 'public' AND c.relkind IN ('r', 'p', 'S')
     AND NOT has_table_privilege('$BACKUP_USER', c.oid, 'SELECT');
  IF n <> 0 THEN RAISE EXCEPTION 'ABORT: % relaciones sin SELECT para backup', n; END IF;
  SELECT count(*) INTO n FROM pg_class c JOIN pg_namespace s ON s.oid = c.relnamespace
   WHERE s.nspname = 'public' AND c.relkind IN ('r', 'p')
     AND (has_table_privilege('$BACKUP_USER', c.oid, 'INSERT')
          OR has_table_privilege('$BACKUP_USER', c.oid, 'UPDATE')
          OR has_table_privilege('$BACKUP_USER', c.oid, 'DELETE')
          OR has_table_privilege('$BACKUP_USER', c.oid, 'TRUNCATE'));
  IF n <> 0 THEN RAISE EXCEPTION 'ABORT: el rol de backup tiene privilegios de escritura'; END IF;
  -- restore: sin acceso a la base del entorno (solo la de mantenimiento, para drills).
  IF has_database_privilege('$RESTORE_USER', '$DB_NAME', 'CONNECT')
     AND has_schema_privilege('$RESTORE_USER', 'public', 'USAGE') THEN
    RAISE EXCEPTION 'ABORT: el rol de restore tiene acceso a la base del entorno';
  END IF;
  -- Aislamiento de la base de mantenimiento: ni app ni backup conectan a postgres.
  IF has_database_privilege('$APP_USER', 'postgres', 'CONNECT')
     OR has_database_privilege('$BACKUP_USER', 'postgres', 'CONNECT') THEN
    RAISE EXCEPTION 'ABORT: la app o backup pueden conectarse a la base de mantenimiento';
  END IF;
END \$\$;
EOSQL
note "grants aplicados y verificados"

# ------------------------------------------------------------------------ 6. resumen (sin secretos)
$PSQL --dbname "$DB_NAME" <<'EOSQL'
\pset pager off
\echo '== Roles del entorno'
SELECT rolname, rolcanlogin, rolsuper, rolcreatedb, rolconnlimit
  FROM pg_roles WHERE rolname LIKE 'deptit_%' ORDER BY 1;
\echo '== Base'
SELECT datname, pg_get_userbyid(datdba) AS owner, pg_encoding_to_char(encoding) AS encoding
  FROM pg_database WHERE datname = current_database();
\echo '== Objetos de public por owner'
SELECT pg_get_userbyid(relowner) AS owner, relkind, count(*)
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname = 'public' GROUP BY 1, 2 ORDER BY 1, 2;
EOSQL
note "INITDB COMPLETO: entorno=$ENTORNO base=$DB_NAME (los servicios arrancan con depends_on healthy)"
