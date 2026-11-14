"""B11 — identidad de base de datos y entorno libpq SIN exponer la contraseña.

* ``parse_database_url``: acepta ``postgresql://`` / ``postgres://`` / ``postgresql+psycopg2://`` (el mismo
  ``DATABASE_URL`` que usa la app).  Devuelve la identidad saneada (host, puerto, base, usuario) y, por separado, la
  contraseña: la identidad es lo único que se persiste/loguea.
* ``libpq_environment``: context manager que arma el entorno de un proceso hijo (pg_dump/pg_restore/createdb/dropdb)
  con ``PGHOST/PGPORT/PGUSER/PGDATABASE`` y la contraseña en un **passfile temporal** privado (``PGPASSFILE``), nunca
  en argv ni en ``PGPASSWORD``.  Se eliminan del entorno heredado ``DATABASE_URL``, ``PGPASSWORD`` y cualquier
  ``PG*`` previo.  El passfile se borra al salir, aun ante errores.
* ``redact``: elimina la contraseña (y el URL completo) de cualquier texto antes de mostrarlo/guardarlo.
"""
from __future__ import annotations

import contextlib
import os
import re
import shutil
import stat
import tempfile
from dataclasses import dataclass
from typing import Dict, Iterator, Mapping, Optional, Tuple
from urllib.parse import parse_qsl, unquote, urlsplit

SCHEMES = ("postgresql", "postgres", "postgresql+psycopg2")
DEFAULT_PORT = 5432
# Parámetros de conexión del URL que se trasladan a variables libpq (nunca contienen la contraseña).
QUERY_TO_ENV = {"sslmode": "PGSSLMODE", "sslrootcert": "PGSSLROOTCERT", "sslcert": "PGSSLCERT", "sslkey": "PGSSLKEY",
                "connect_timeout": "PGCONNECT_TIMEOUT", "application_name": "PGAPPNAME",
                "target_session_attrs": "PGTARGETSESSIONATTRS", "options": "PGOPTIONS"}
SECRET_ENV = re.compile(r"^(PG\w*|DATABASE_URL|DEPTIT_\w*PASSWORD\w*)$", re.I)
_IDENT = re.compile(r"^[A-Za-z0-9_.\-]{1,63}$")


class DatabaseUrlError(ValueError):
    """``DATABASE_URL`` ausente o no interpretable.  El mensaje nunca incluye el URL ni la contraseña."""


@dataclass(frozen=True)
class DatabaseIdentity:
    host: str
    port: int
    name: str
    user: str

    def sanitized(self) -> dict:
        return {"host": self.host, "port": self.port, "name": self.name, "user": self.user}

    def same_database(self, other: "DatabaseIdentity") -> bool:
        """Misma base: host (sin mayúsculas), puerto y nombre.  El usuario puede diferir (rol de backup)."""
        return (_norm_host(self.host), int(self.port), self.name) == (_norm_host(other.host), int(other.port), other.name)


def _norm_host(host: str) -> str:
    h = str(host or "").strip().lower()
    return "localhost" if h in ("", "127.0.0.1", "::1", "[::1]") else h


def parse_database_url(url) -> Tuple[DatabaseIdentity, Optional[str], Dict[str, str]]:
    """(identidad, contraseña|None, parámetros libpq extra).  ``DatabaseUrlError`` si no es un URL PostgreSQL."""
    text = str(url or "").strip()
    if not text:
        raise DatabaseUrlError("DATABASE_URL no está definido.")
    try:
        parts = urlsplit(text)
        scheme = parts.scheme.lower()
        port = parts.port
    except ValueError:
        raise DatabaseUrlError("DATABASE_URL no es un URL válido.") from None
    if scheme not in SCHEMES:
        raise DatabaseUrlError("DATABASE_URL debe empezar con postgresql:// (o postgres://).")
    name = unquote(parts.path.lstrip("/"))
    if not name or "/" in name:
        raise DatabaseUrlError("DATABASE_URL no indica el nombre de la base.")
    user = unquote(parts.username or "")
    if not user:
        raise DatabaseUrlError("DATABASE_URL no indica el usuario.")
    host = parts.hostname or "localhost"
    password = unquote(parts.password) if parts.password is not None else None
    extra = {}
    for key, value in parse_qsl(parts.query, keep_blank_values=False):
        if key.lower() in ("password", "passfile"):
            raise DatabaseUrlError("DATABASE_URL no debe llevar la contraseña como parámetro de consulta.")
        env = QUERY_TO_ENV.get(key.lower())
        if env:
            extra[env] = value
    return DatabaseIdentity(host=host, port=int(port or DEFAULT_PORT), name=name, user=user), password, extra


def identity_from_url(url) -> DatabaseIdentity:
    return parse_database_url(url)[0]


def safe_identifier(name: str) -> bool:
    return bool(_IDENT.match(str(name or "")))


def redact(text, *secrets) -> str:
    """Quita del texto cada secreto (y su forma URL-encoded) y cualquier ``user:password@`` de URLs."""
    out = str(text if text is not None else "")
    for s in secrets:
        if s:
            from urllib.parse import quote
            for variant in {str(s), quote(str(s), safe="")}:
                out = out.replace(variant, "***")
    return re.sub(r"(postgres(?:ql)?(?:\+\w+)?://[^:/@\s]*):[^@\s]*@", r"\1:***@", out)


def _passfile_escape(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace(":", "\\:")


def base_child_environment(base: Optional[Mapping[str, str]] = None) -> Dict[str, str]:
    """Entorno heredado sin secretos de conexión (DATABASE_URL, PGPASSWORD, PG* previos)."""
    src = dict(os.environ if base is None else base)
    return {k: v for k, v in src.items() if not SECRET_ENV.match(k)}


@contextlib.contextmanager
def libpq_environment(identity: DatabaseIdentity, password: Optional[str], extra: Optional[Mapping[str, str]] = None,
                      *, database: Optional[str] = None, base: Optional[Mapping[str, str]] = None) -> Iterator[Dict[str, str]]:
    """Entorno para un binario libpq.  ``database`` permite apuntar a otra base del mismo servidor (restore drill)."""
    env = base_child_environment(base)
    env.update({"PGHOST": identity.host, "PGPORT": str(identity.port), "PGUSER": identity.user,
                "PGDATABASE": database or identity.name, "PGCONNECT_TIMEOUT": "15"})
    env.update(dict(extra or {}))
    tmpdir = None
    try:
        if password:
            tmpdir = tempfile.mkdtemp(prefix="deptit_pgpass_")  # 0700 en POSIX; perfil privado en Windows
            path = os.path.join(tmpdir, "pgpass.conf")
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(f"*:*:*:*:{_passfile_escape(password)}\n")
            if os.name != "nt":
                os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
            env["PGPASSFILE"] = path
        yield env
    finally:
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)
