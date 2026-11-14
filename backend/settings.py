"""Configuracion centralizada por entorno (Etapa 6A-B1, docs/ETAPA6_6AB1_PRODUCTIVE_SOFTWARE_HARDENING.md).

Selector unico: ``DEPTIT_ENTORNO`` = ``desarrollo`` | ``preproduccion`` | ``produccion`` (obligatorio, sin default).
Toda la configuracion del proceso se lee y valida aca, una vez, al arrancar; un valor invalido o contradictorio lanza
``ConfigError`` y el backend no arranca (fail-closed).  Desarrollo admite defaults seguros; preproduccion y produccion
exigen los valores criticos de forma explicita y rechazan las relajaciones de desarrollo.

Base de datos: cada entorno tiene UNA base permitida (``BASES``) y la base ``deptit`` (sistema local actual) esta
prohibida en todos.  La conexion se describe con ``DEPTIT_DB_*`` o, alternativamente, con ``DATABASE_URL`` (nunca
ambas).  Las guardas post-conexion (``db.verify_identity``, ``db.verify_privileges``) comparan contra estos valores.
"""

from __future__ import annotations

import ipaddress
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path, PureWindowsPath
from typing import Callable, Mapping, Optional
from urllib.parse import quote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv
from psycopg.conninfo import conninfo_to_dict, make_conninfo

BACKEND_DIR = Path(__file__).resolve().parent
REPO_DIR = BACKEND_DIR.parent
ENV_FILE = BACKEND_DIR / ".env"

DESARROLLO, PREPRODUCCION, PRODUCCION = "desarrollo", "preproduccion", "produccion"
ENTORNOS = (DESARROLLO, PREPRODUCCION, PRODUCCION)
BASES = {DESARROLLO: "deptit_next_dev", PREPRODUCCION: "deptit_next_preprod", PRODUCCION: "deptit_next_prod"}
ROL_DESARROLLO = "deptit_next_app"
# ``deptit`` es la base del sistema local actual: prohibida en todos los entornos (ademas de las de sistema).
BASES_PROHIBIDAS = frozenset({"deptit", "postgres", "template0", "template1"})
ROLES_PROHIBIDOS = frozenset({"postgres", "deptit_app"})
SSLMODES = ("disable", "allow", "prefer", "require", "verify-ca", "verify-full")
SSLMODES_CIFRADOS = ("require", "verify-ca", "verify-full")

TIMEZONE_APP = "America/Argentina/Buenos_Aires"
# Zona de la SESION PostgreSQL: el valor efectivo del servidor sobre el que se certifico NEXT (GMT/UTC).  Fijarla
# explicitamente hace que CURRENT_DATE / CURRENT_TIMESTAMP no dependan de la configuracion del servidor futuro.
TIMEZONE_DB = "UTC"

LOOPBACK = ("127.0.0.1", "::1", "localhost")
DEFAULT_DOCUMENTS_DIR = REPO_DIR / "storage" / "documents"
# Arboles que nunca pueden ser raiz documental (protegidos en esta PC); se agregan los de DEPTIT_FORBIDDEN_DIRS.
RAICES_PROTEGIDAS_WINDOWS = (r"C:\DEPTIT_PROD", r"C:\DEPTIT_REFACTOR_B13", r"C:\DEPTIT_NEXT\reference_fix02")

VERDADERO, FALSO = ("1", "true", "yes", "on", "si"), ("0", "false", "no", "off")
# Variables reemplazadas en 6A-B1: si aparecen, la configuracion es ambigua y se rechaza.
OBSOLETAS = {"DEPTIT_NEXT_DOCUMENT_STORAGE_ROOT": "DEPTIT_DOCUMENTS_DIR"}


class ConfigError(RuntimeError):
    """Configuracion invalida o contradictoria: el proceso no debe arrancar.  El mensaje nunca incluye secretos."""


_VALIDADORES: list[Callable[[Mapping[str, str]], object]] = []


def registrar_validador(validador: Callable[[Mapping[str, str]], object]) -> None:
    """La capa de composicion agrega validaciones de contratos propios (p. ej. el gate de backup), sin que
    ``settings`` dependa de ``integraciones``.  Idempotente."""
    if validador not in _VALIDADORES:
        _VALIDADORES.append(validador)


@dataclass(frozen=True)
class DatabaseConfig:
    host: str
    port: int
    name: str
    user: str
    sslmode: str
    password: Optional[str] = field(default=None, repr=False)
    source: str = "DEPTIT_DB_*"

    @property
    def conninfo(self) -> str:
        params = {"host": self.host, "port": str(self.port), "dbname": self.name, "user": self.user,
                  "sslmode": self.sslmode}
        if self.password:
            params["password"] = self.password
        return make_conninfo(**params)

    @property
    def identity_url(self) -> str:
        """URL SIN credenciales (host+puerto+base+usuario): identidad que compara el gate de backup B11 (6A-B2)."""
        return f"postgresql://{quote(self.user, safe='')}@{self.host}:{self.port}/{quote(self.name, safe='')}"


@dataclass(frozen=True)
class Settings:
    entorno: str
    db: DatabaseConfig
    expected_database: str
    expected_db_user: str
    cookie_secure: bool
    api_docs: bool
    documents_dir: Path
    timezone: str
    db_timezone: str
    backend_host: str
    backend_port: int
    trusted_frontend_ips: tuple = ()
    login_ip_max_failed: int = 20
    login_ip_window_minutes: int = 15
    login_ip_lockout_minutes: int = 15

    @property
    def es_desarrollo(self) -> bool:
        return self.entorno == DESARROLLO


# ------------------------------------------------------------------------------------------ lectura
def load_env_file() -> None:
    """``backend/.env`` (solo desarrollo local; nunca viaja en un artefacto).  El entorno del proceso tiene prioridad.
    6A-B3: si el PROCESO ya declara otro entorno (preproduccion / produccion), el archivo de desarrollo no se lee: con
    ``override=False`` completaria en silencio las variables que falten con valores de desarrollo."""
    if not proceso_de_desarrollo():
        return
    load_dotenv(ENV_FILE, override=False)


def proceso_de_desarrollo(env: Optional[Mapping[str, str]] = None) -> bool:
    """True si el entorno del proceso no declara ``DEPTIT_ENTORNO`` o declara ``desarrollo``."""
    valor = str((os.environ if env is None else env).get("DEPTIT_ENTORNO", "") or "").strip()
    return valor in ("", DESARROLLO)


def _txt(env: Mapping[str, str], name: str) -> str:
    return str(env.get(name, "") or "").strip()


def _bool(env: Mapping[str, str], name: str, default: bool) -> bool:
    raw = _txt(env, name).lower()
    if not raw:
        return default
    if raw in VERDADERO:
        return True
    if raw in FALSO:
        return False
    raise ConfigError(f"{name} debe ser 1/0 (true/false)")


def _int(env: Mapping[str, str], name: str, default: int, low: int, high: int) -> int:
    raw = _txt(env, name)
    if not raw:
        return default
    if not raw.isdigit() or not low <= int(raw) <= high:
        raise ConfigError(f"{name} debe ser un entero entre {low} y {high}")
    return int(raw)


def entorno_de(env: Optional[Mapping[str, str]] = None) -> str:
    env = os.environ if env is None else env
    valor = _txt(env, "DEPTIT_ENTORNO")
    if not valor:
        raise ConfigError("DEPTIT_ENTORNO es obligatoria (desarrollo, preproduccion o produccion)")
    if valor not in ENTORNOS:
        raise ConfigError(f"DEPTIT_ENTORNO={valor!r} no es un entorno valido ({', '.join(ENTORNOS)})")
    return valor


def _es_loopback(host: str) -> bool:
    if host in LOOPBACK:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _database(env: Mapping[str, str], entorno: str) -> DatabaseConfig:
    url = _txt(env, "DATABASE_URL")
    discretas = [n for n in ("DEPTIT_DB_HOST", "DEPTIT_DB_PORT", "DEPTIT_DB_NAME", "DEPTIT_DB_USER",
                             "DEPTIT_DB_PASSWORD", "DEPTIT_DB_SSLMODE") if _txt(env, n)]
    if url and discretas:
        raise ConfigError("DATABASE_URL y DEPTIT_DB_* son excluyentes: definir la conexion de una sola forma")
    if url:
        try:
            params = conninfo_to_dict(url)
        except Exception:
            # Sin detalle: podria contener la URL con la contrasena.
            raise ConfigError("DATABASE_URL no es una cadena de conexion valida") from None
        if "service" in params or "servicefile" in params:
            raise ConfigError("DATABASE_URL no puede usar service/servicefile")
        host, port = str(params.get("host") or ""), str(params.get("port") or "5432")
        name, user = str(params.get("dbname") or ""), str(params.get("user") or "")
        sslmode, password, source = str(params.get("sslmode") or ""), params.get("password"), "DATABASE_URL"
    else:
        host, port = _txt(env, "DEPTIT_DB_HOST"), _txt(env, "DEPTIT_DB_PORT") or "5432"
        name, user = _txt(env, "DEPTIT_DB_NAME"), _txt(env, "DEPTIT_DB_USER")
        sslmode, password, source = _txt(env, "DEPTIT_DB_SSLMODE"), env.get("DEPTIT_DB_PASSWORD") or None, "DEPTIT_DB_*"
    if not host or not name or not user:
        raise ConfigError("conexion incompleta: se exigen host, base y usuario (DEPTIT_DB_HOST/NAME/USER)")
    if "," in host:
        raise ConfigError("se admite un solo host de base de datos")
    if not port.isdigit() or not 1 <= int(port) <= 65535:
        raise ConfigError("DEPTIT_DB_PORT debe ser un puerto valido")
    if not sslmode:
        if entorno != DESARROLLO:
            raise ConfigError("DEPTIT_DB_SSLMODE es obligatoria fuera de desarrollo")
        sslmode = "prefer"
    if sslmode not in SSLMODES:
        raise ConfigError(f"DEPTIT_DB_SSLMODE={sslmode!r} no es valido")
    if entorno != DESARROLLO and not _es_loopback(host) and sslmode not in SSLMODES_CIFRADOS:
        raise ConfigError("una base remota fuera de desarrollo exige DEPTIT_DB_SSLMODE require/verify-ca/verify-full")
    return DatabaseConfig(host, int(port), name, user, sslmode, password, source)


def _documents_dir(env: Mapping[str, str], entorno: str) -> Path:
    for vieja, nueva in OBSOLETAS.items():
        if _txt(env, vieja):
            raise ConfigError(f"{vieja} fue reemplazada por {nueva}")
    raw = _txt(env, "DEPTIT_DOCUMENTS_DIR")
    if not raw:
        if entorno != DESARROLLO:
            raise ConfigError("DEPTIT_DOCUMENTS_DIR es obligatoria fuera de desarrollo")
        return DEFAULT_DOCUMENTS_DIR
    if "\x00" in raw:
        raise ConfigError("DEPTIT_DOCUMENTS_DIR invalida")
    path = Path(raw)
    if not path.is_absolute():
        raise ConfigError("DEPTIT_DOCUMENTS_DIR debe ser una ruta absoluta")
    return Path(os.path.normpath(path))


def documents_dir_problem(path: Path, env: Optional[Mapping[str, str]] = None) -> Optional[str]:
    """Motivo por el que ``path`` no puede ser la raiz documental (o None).  No crea ni escribe nada."""
    env = os.environ if env is None else env
    norm = os.path.normcase(os.path.normpath(str(path)))
    prohibidas = list(RAICES_PROTEGIDAS_WINDOWS) + [p for p in _txt(env, "DEPTIT_FORBIDDEN_DIRS").split(os.pathsep) if p]
    if os.name == "nt" or isinstance(path, PureWindowsPath):
        candidatas = prohibidas
    else:
        candidatas = [p for p in prohibidas if not p[1:3] == ":\\"]
    for raiz in candidatas:
        r = os.path.normcase(os.path.normpath(raiz))
        if norm == r or norm.startswith(r.rstrip("\\/") + os.sep):
            return "esta dentro de un arbol protegido"
    codigo = os.path.normcase(str(BACKEND_DIR))
    if norm == codigo or norm.startswith(codigo + os.sep):
        return "no puede estar dentro del codigo del backend"
    return None


def _timezone(env: Mapping[str, str], name: str, default: str) -> str:
    valor = _txt(env, name) or default
    try:
        ZoneInfo(valor)
    except (ZoneInfoNotFoundError, ValueError):
        raise ConfigError(f"{name}={valor!r} no es una zona horaria IANA valida") from None
    return valor


def _ips(env: Mapping[str, str], name: str, default: str) -> tuple:
    out = []
    for item in (_txt(env, name) or default).split(","):
        item = item.strip()
        if not item:
            continue
        try:
            out.append(str(ipaddress.ip_address(item)))
        except ValueError:
            raise ConfigError(f"{name}: {item!r} no es una IP") from None
    return tuple(out)


def load(env: Optional[Mapping[str, str]] = None, *, read_env_file: bool = True) -> Settings:
    """Lee y valida TODA la configuracion.  ``env`` permite probar sin tocar ``os.environ``."""
    if env is None:
        if read_env_file:
            load_env_file()
        env = os.environ
    entorno = entorno_de(env)
    db = _database(env, entorno)
    esperado = BASES[entorno]
    for nombre in {db.name, _txt(env, "DEPTIT_EXPECTED_DATABASE")}:
        if nombre.lower() in BASES_PROHIBIDAS:
            raise ConfigError(f"la base {nombre!r} esta prohibida para DEPTIT NEXT")
    expected_database = _txt(env, "DEPTIT_EXPECTED_DATABASE")
    if expected_database != esperado:
        raise ConfigError(f"DEPTIT_EXPECTED_DATABASE={expected_database!r}; en {entorno} se exige exactamente "
                          f"{esperado!r}")
    if db.name != esperado:
        raise ConfigError(f"la conexion apunta a la base {db.name!r}; en {entorno} se exige exactamente {esperado!r}")
    expected_user = _txt(env, "DEPTIT_EXPECTED_DB_USER")
    if not expected_user:
        raise ConfigError("DEPTIT_EXPECTED_DB_USER es obligatoria")
    if expected_user in ROLES_PROHIBIDOS or db.user in ROLES_PROHIBIDOS:
        raise ConfigError("el rol de la aplicacion no puede ser postgres ni el rol del sistema local (deptit_app)")
    if entorno == DESARROLLO and expected_user != ROL_DESARROLLO:
        raise ConfigError(f"en desarrollo el rol esperado es exactamente {ROL_DESARROLLO!r}")
    if entorno != DESARROLLO and expected_user == ROL_DESARROLLO:
        raise ConfigError(f"{ROL_DESARROLLO!r} es el rol de desarrollo: preproduccion/produccion usan un rol propio")
    if db.user != expected_user:
        raise ConfigError(f"la conexion usa el usuario {db.user!r}; se exige exactamente {expected_user!r}")

    cookie_secure = _bool(env, "DEPTIT_SESSION_COOKIE_SECURE", entorno != DESARROLLO)
    if entorno != DESARROLLO and not cookie_secure:
        raise ConfigError("DEPTIT_SESSION_COOKIE_SECURE=0 solo se admite en desarrollo")
    api_docs = _bool(env, "DEPTIT_API_DOCS", entorno == DESARROLLO)
    if entorno != DESARROLLO and api_docs:
        raise ConfigError("DEPTIT_API_DOCS=1 (Swagger/ReDoc/OpenAPI) solo se admite en desarrollo")

    documents_dir = _documents_dir(env, entorno)
    if (motivo := documents_dir_problem(documents_dir, env)) is not None:
        raise ConfigError(f"DEPTIT_DOCUMENTS_DIR {motivo}")
    if entorno != DESARROLLO:
        if not documents_dir.is_dir():
            raise ConfigError("DEPTIT_DOCUMENTS_DIR no existe o no es un directorio")
        if not os.access(documents_dir, os.R_OK | os.W_OK | os.X_OK):
            raise ConfigError("DEPTIT_DOCUMENTS_DIR no tiene permisos de lectura/escritura para el servicio")

    timezone = _timezone(env, "DEPTIT_TIMEZONE", TIMEZONE_APP)
    db_timezone = _timezone(env, "DEPTIT_DB_TIMEZONE", TIMEZONE_DB)

    backend_host = _txt(env, "DEPTIT_BACKEND_HOST") or "127.0.0.1"
    backend_port = _int(env, "DEPTIT_BACKEND_PORT", 8001, 1, 65535)
    if not _es_loopback(backend_host) and not _bool(env, "DEPTIT_BACKEND_ALLOW_NON_LOOPBACK", False):
        raise ConfigError("DEPTIT_BACKEND_HOST debe ser loopback: FastAPI nunca se expone (solo Next.js le habla); "
                          "una red privada exige DEPTIT_BACKEND_ALLOW_NON_LOOPBACK=1")

    # La sesion y el limite por cuenta siguen en auth.core (contrato B12G); se validan aca para fallar al arrancar.
    from auth import core as auth_core
    try:
        auth_core.load_config(env.get)
    except auth_core.ConfigError as exc:
        raise ConfigError(str(exc)) from None
    # Validadores de la capa de composicion (D-E4-01: settings no importa ``integraciones``); ``main.py`` registra el
    # gate de backup de Crear periodo (D-E4-04).  Cualquier rechazo es una configuracion invalida.
    for validador in _VALIDADORES:
        try:
            validador(env)
        except Exception as exc:
            raise ConfigError(str(exc)) from None

    return Settings(
        entorno=entorno, db=db, expected_database=expected_database, expected_db_user=expected_user,
        cookie_secure=cookie_secure, api_docs=api_docs, documents_dir=documents_dir, timezone=timezone,
        db_timezone=db_timezone, backend_host=backend_host, backend_port=backend_port,
        trusted_frontend_ips=_ips(env, "DEPTIT_TRUSTED_FRONTEND_IPS", "127.0.0.1,::1"),
        login_ip_max_failed=_int(env, "DEPTIT_LOGIN_IP_MAX_FAILED_ATTEMPTS", 20, 5, 1000),
        login_ip_window_minutes=_int(env, "DEPTIT_LOGIN_IP_FAILURE_WINDOW_MINUTES", 15, 1, 1440),
        login_ip_lockout_minutes=_int(env, "DEPTIT_LOGIN_IP_LOCKOUT_MINUTES", 15, 1, 1440),
    )


_actual: Optional[Settings] = None


def get() -> Settings:
    """Configuracion del proceso (cargada y validada una vez)."""
    global _actual
    if _actual is None:
        _actual = load()
    return _actual


def reset() -> None:
    """Solo para tests: fuerza una nueva lectura."""
    global _actual
    _actual = None


def api_docs_habilitada() -> bool:
    """Decision de import de ``main`` (antes del lifespan): Swagger/ReDoc/OpenAPI solo en desarrollo explicito."""
    load_env_file()
    try:
        entorno = entorno_de()
        return entorno == DESARROLLO and _bool(os.environ, "DEPTIT_API_DOCS", True)
    except ConfigError:
        return False


# ------------------------------------------------------------------------------------------ zona horaria
def _offsets(zona: Callable[[datetime], object]) -> list:
    anio = datetime.now().year
    return [zona(datetime(anio, mes, 15, 12)) for mes in (1, 4, 7, 10)]


def apply_timezone(settings: Settings) -> str:
    """Fija la zona horaria del PROCESO.  POSIX: ``TZ`` + ``time.tzset()`` (afecta ``datetime.now()`` y
    ``date.today()`` en todo el codigo, incluidos los motores vendorizados).  Windows no tiene ``tzset``: se verifica
    que la zona del sistema coincida con la configurada en todo el año; fuera de desarrollo, si no coincide, falla."""
    zona = ZoneInfo(settings.timezone)
    if hasattr(time, "tzset"):
        os.environ["TZ"] = settings.timezone
        time.tzset()
    local = _offsets(lambda d: d.astimezone().utcoffset())
    esperado = _offsets(lambda d: d.replace(tzinfo=zona).utcoffset())
    if local != esperado:
        mensaje = f"la zona horaria del sistema no coincide con DEPTIT_TIMEZONE={settings.timezone!r}"
        if settings.entorno != DESARROLLO:
            raise ConfigError(mensaje)
        return mensaje
    return ""
