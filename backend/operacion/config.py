"""Configuracion de las herramientas operativas (6A-B2).

* La configuracion de la aplicacion (``settings.load``: entorno, base, rol de la app, storage, guardas) se valida
  igual que al arrancar el backend: una herramienta nunca opera con una configuracion que la app rechazaria.
* Credenciales operativas aparte: ``DEPTIT_BACKUP_DB_USER/PASSWORD`` (solo lectura, ``pg_dump``) y
  ``DEPTIT_RESTORE_DB_USER/PASSWORD`` (CREATEDB, restore drill).  6A-B3: ``DEPTIT_OWNER_DB_USER/PASSWORD`` (owner de
  la base de preproduccion; solo la siembra inicial y los GRANT lo usan, nunca la app).  En desarrollo se leen de ``backend/.env.ops`` (la app
  nunca carga ese archivo); en preproduccion/produccion, del entorno del proceso de la tarea/servicio operativo.
* ``DEPTIT_BACKUP_DIR``: obligatoria y absoluta en todos los entornos, fuera del codigo, de ``.git`` y de los arboles
  protegidos, y distinta de la raiz documental (ni dentro ni conteniendola).
* Nunca se registra una contrasena: ``Credencial`` la oculta en ``repr`` y los reportes solo llevan el usuario.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Optional
from urllib.parse import quote

from dotenv import dotenv_values

import settings as app_settings

OPS_ENV_FILE = app_settings.BACKEND_DIR / ".env.ops"
BACKUP_DIR_ENV = "DEPTIT_BACKUP_DIR"
PG_BIN_DIR_ENV = "DEPTIT_PG_BIN_DIR"
SUBDIR_DOCUMENTOS = "documents"
SUBDIR_SETS = "sets"
# Bases temporales de prueba de restore: unico nombre que la herramienta crea o borra.
RESTORE_TEST_PREFIX = "deptit_next_restore_test_"
RESTORE_TEST_RE = re.compile(r"^deptit_next_restore_test_[a-z0-9_]{1,40}$")
# Rutas del proyecto donde nunca puede haber backups (codigo, control de versiones, artefactos).
DIRS_CODIGO = ("backend", "frontend", ".git", "migration", "ops", "docs", "dist", "reference_fix02")


class OpsConfigError(RuntimeError):
    """Configuracion operativa invalida.  El mensaje nunca incluye secretos."""


@dataclass(frozen=True)
class Credencial:
    user: str
    password: Optional[str] = field(default=None, repr=False)


@dataclass(frozen=True)
class OpsConfig:
    app: app_settings.Settings
    backup_dir: Path
    pg_bin_dir: Optional[str]
    backup: Optional[Credencial]
    restore: Optional[Credencial]
    owner: Optional[Credencial] = None
    env: Mapping[str, str] = field(default_factory=dict, repr=False)

    @property
    def entorno(self) -> str:
        return self.app.entorno

    @property
    def documentos_dir(self) -> Path:
        return self.backup_dir / SUBDIR_DOCUMENTOS

    @property
    def sets_dir(self) -> Path:
        return self.backup_dir / SUBDIR_SETS

    def url(self, cred: Credencial, database: Optional[str] = None) -> str:
        """URL libpq EN MEMORIA para las herramientas B11 (que la parsean y usan un passfile temporal)."""
        db = self.app.db
        auth = quote(cred.user, safe="") + (":" + quote(cred.password, safe="") if cred.password else "")
        return (f"postgresql://{auth}@{db.host}:{db.port}/{quote(database or db.name, safe='')}"
                f"?sslmode={db.sslmode}")

    def identity_url(self) -> str:
        """URL SIN credenciales que identifica la base de la app (host+puerto+nombre): la que compara el gate."""
        return identity_url(self.app)


def identity_url(app: app_settings.Settings) -> str:
    return app.db.identity_url


def backup_dir_problem(path: Path, app: app_settings.Settings, env: Mapping[str, str]) -> Optional[str]:
    """Motivo por el que ``path`` no puede ser el directorio de backups (o None).  No crea nada."""
    if not path.is_absolute():
        return "debe ser una ruta absoluta"
    if (motivo := app_settings.documents_dir_problem(path, env)) is not None:
        return motivo
    norm = os.path.normcase(os.path.normpath(str(path)))
    for nombre in DIRS_CODIGO:
        raiz = os.path.normcase(str(app_settings.REPO_DIR / nombre))
        if norm == raiz or norm.startswith(raiz + os.sep):
            return f"no puede estar dentro de {nombre}/ del proyecto"
    if norm == os.path.normcase(str(app_settings.REPO_DIR)):
        return "no puede ser la raiz del proyecto"
    docs = os.path.normcase(os.path.normpath(str(app.documents_dir)))
    if norm == docs or norm.startswith(docs + os.sep) or docs.startswith(norm + os.sep):
        return "no puede coincidir con la raiz documental ni contenerla"
    return None


def _credencial(env: Mapping[str, str], prefijo: str, prohibidos: set) -> Optional[Credencial]:
    user = str(env.get(f"{prefijo}_USER") or "").strip()
    if not user:
        return None
    if user in prohibidos:
        raise OpsConfigError(f"{prefijo}_USER no puede ser {user!r}")
    return Credencial(user, env.get(f"{prefijo}_PASSWORD") or None)


def load(env: Optional[Mapping[str, str]] = None, *, read_files: bool = True) -> OpsConfig:
    """Configuracion completa.  ``env`` permite probar sin tocar ``os.environ`` ni leer archivos."""
    if env is None:
        if read_files:
            app_settings.load_env_file()
        base = dict(os.environ)
        # ``backend/.env.ops`` es de desarrollo: un proceso de preproduccion/produccion nunca lo completa (6A-B3).
        if read_files and app_settings.proceso_de_desarrollo() and OPS_ENV_FILE.is_file():
            for k, v in dotenv_values(OPS_ENV_FILE).items():
                base.setdefault(k, v or "")
        env = base
    try:
        app = app_settings.load(env, read_env_file=False)
    except app_settings.ConfigError as exc:
        raise OpsConfigError(f"configuracion de la aplicacion invalida: {exc}") from None
    raw = str(env.get(BACKUP_DIR_ENV) or "").strip()
    if not raw:
        raise OpsConfigError(f"{BACKUP_DIR_ENV} es obligatoria (ruta absoluta fuera del codigo)")
    backup_dir = Path(os.path.normpath(raw))
    if (motivo := backup_dir_problem(backup_dir, app, env)) is not None:
        raise OpsConfigError(f"{BACKUP_DIR_ENV} {motivo}")
    prohibidos = set(app_settings.ROLES_PROHIBIDOS) | {app.expected_db_user}
    backup = _credencial(env, "DEPTIT_BACKUP_DB", prohibidos)
    restore = _credencial(env, "DEPTIT_RESTORE_DB", prohibidos)
    owner = _credencial(env, "DEPTIT_OWNER_DB", prohibidos)
    usuarios = [c.user for c in (backup, restore, owner) if c]
    if len(usuarios) != len(set(usuarios)):
        raise OpsConfigError("los roles operativos (backup, restore, owner) deben ser distintos")
    return OpsConfig(app=app, backup_dir=backup_dir, pg_bin_dir=str(env.get(PG_BIN_DIR_ENV) or "").strip() or None,
                     backup=backup, restore=restore, owner=owner, env=env)


def preparar_backup_dir(cfg: OpsConfig, *, crear: bool) -> None:
    """El directorio de backups (y sus subdirectorios) deben existir; en desarrollo se pueden crear."""
    for d in (cfg.backup_dir, cfg.documentos_dir, cfg.sets_dir):
        if d.is_symlink():
            raise OpsConfigError(f"{d.name}: el directorio de backups no puede ser un enlace")
        if not d.is_dir():
            if not crear:
                raise OpsConfigError(f"{BACKUP_DIR_ENV}: falta el directorio {d.name!r}")
            d.mkdir(parents=True, exist_ok=True)
