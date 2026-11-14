"""Conexion a PostgreSQL con guardas fail-closed (Etapa 6A-B1: parametrizada por entorno).

La base y el rol permitidos los decide ``settings`` segun ``DEPTIT_ENTORNO`` (desarrollo -> ``deptit_next_dev``,
preproduccion -> ``deptit_next_preprod``, produccion -> ``deptit_next_prod``; ``deptit`` prohibida siempre).  No hay
fallback a ninguna otra base.  Guardas:
* pre-conexion: ``settings.load`` (configuracion completa y coherente);
* post-conexion: ``current_database()`` / ``current_user`` exactos, en la conexion inicial y en CADA conexion nueva
  del pool (``verify_identity``);
* privilegios: el rol no es superusuario, no tiene CREATE en el esquema ni es dueño de objetos, es decir, no puede
  ejecutar DDL (``verify_privileges``): el arranque nunca puede convertirse en un mecanismo de migracion.
"""

from __future__ import annotations

from typing import Optional

from psycopg import Connection
from psycopg_pool import ConnectionPool

import settings as cfg

ENV_FILE = cfg.ENV_FILE


class DatabaseGuardError(RuntimeError):
    """La configuracion o la conexion no apuntan a la base/usuario requeridos."""


def load_settings() -> dict[str, str]:
    """Contrato historico (tests y herramientas): conninfo + valores esperados del entorno activo."""
    try:
        s = cfg.get()
    except cfg.ConfigError as exc:
        raise DatabaseGuardError(str(exc)) from None
    return {"database_url": s.db.conninfo, "expected_database": s.expected_database,
            "expected_db_user": s.expected_db_user}


def check_config(settings: dict[str, str]) -> None:
    """Pre-guarda: valida la configuracion SIN abrir ninguna conexion (la valida ``settings.load``)."""
    s = cfg.get()
    if settings.get("expected_database") != s.expected_database or settings.get("expected_db_user") != s.expected_db_user:
        raise DatabaseGuardError("la configuracion no coincide con la del entorno activo")


def _expected() -> tuple[str, str]:
    s = cfg.get()
    return s.expected_database, s.expected_db_user


def verify_identity(conn: Connection, expected: Optional[tuple[str, str]] = None) -> tuple[str, str]:
    """Guarda post-conexion: current_database() y current_user exactos."""
    required_db, required_user = expected or _expected()
    database, db_user = conn.execute("SELECT current_database(), current_user").fetchone()
    if database != required_db or database.lower() in cfg.BASES_PROHIBIDAS:
        raise DatabaseGuardError(f"current_database()={database!r}; se exige exactamente {required_db!r}")
    if db_user != required_user:
        raise DatabaseGuardError(f"current_user={db_user!r}; se exige exactamente {required_user!r}")
    return database, db_user


PRIVILEGIOS_SQL = """
    SELECT r.rolsuper, r.rolcreatedb, r.rolcreaterole, r.rolbypassrls,
           has_schema_privilege(current_user, 'public', 'CREATE'),
           has_database_privilege(current_database(), 'CREATE'),
           (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE c.relowner = r.oid AND n.nspname NOT IN ('pg_catalog', 'information_schema')
               AND n.nspname NOT LIKE 'pg\\_temp%%' AND n.nspname NOT LIKE 'pg\\_toast%%')
      FROM pg_roles r WHERE r.rolname = current_user
"""


def verify_privileges(conn: Connection) -> None:
    """El rol de la aplicacion no puede hacer DDL: sin superusuario, CREATEDB/CREATEROLE/BYPASSRLS, CREATE en
    ``public`` ni en la base, ni objetos propios (el dueño puede ALTER/DROP).  Si no, el backend no arranca."""
    row = conn.execute(PRIVILEGIOS_SQL).fetchone()
    if row is None:
        raise DatabaseGuardError("no se pudieron leer los privilegios del rol")
    superuser, createdb, createrole, bypassrls, create_schema, create_db, owned = row
    problemas = [n for n, v in (("SUPERUSER", superuser), ("CREATEDB", createdb), ("CREATEROLE", createrole),
                                ("BYPASSRLS", bypassrls), ("CREATE en public", create_schema),
                                ("CREATE en la base", create_db), ("dueño de objetos", owned)) if v]
    if problemas:
        raise DatabaseGuardError("el rol de la aplicacion tiene privilegios de DDL/administracion: "
                                 + ", ".join(problemas))


def _configure(conn: Connection) -> None:
    # Cada conexion nueva del pool se vuelve a verificar antes de usarse; la zona de la sesion queda fijada.
    verify_identity(conn)
    conn.execute("SELECT set_config('TimeZone', %s, false)", [cfg.get().db_timezone])
    conn.commit()


def create_pool() -> ConnectionPool:
    """Pre-guarda + conexion + guardas; si algo falla, lanza DatabaseGuardError."""
    try:
        s = cfg.get()
    except cfg.ConfigError as exc:
        raise DatabaseGuardError(str(exc)) from None
    pool = ConnectionPool(
        s.db.conninfo,
        min_size=1,
        max_size=5,
        open=False,
        configure=_configure,
        kwargs={"connect_timeout": 5, "application_name": "deptit_next_backend"},
    )
    try:
        pool.open(wait=True, timeout=10)
        with pool.connection() as conn:
            verify_identity(conn)
            verify_privileges(conn)
    except Exception as exc:
        pool.close()
        if isinstance(exc, DatabaseGuardError):
            raise
        raise DatabaseGuardError(f"no se pudo verificar la conexion: {type(exc).__name__}") from None
    return pool
