"""Etapa 6A-B1: configuracion centralizada por entorno, guardas de base, prohibicion de DDL, storage y zona horaria
(docs/ETAPA6_6AB1_PRODUCTIVE_SOFTWARE_HARDENING.md).  Las validaciones se prueban con entornos explicitos (sin tocar
``os.environ``); las guardas reales, contra deptit_next_dev en solo lectura."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import psycopg
import pytest

import db
import main  # noqa: F401  (registra el validador del gate de backup, como en el arranque real)
import settings as S

BACKEND = Path(__file__).resolve().parents[1]

DEV = {"DEPTIT_ENTORNO": "desarrollo", "DEPTIT_DB_HOST": "127.0.0.1", "DEPTIT_DB_NAME": "deptit_next_dev",
       "DEPTIT_DB_USER": "deptit_next_app", "DEPTIT_EXPECTED_DATABASE": "deptit_next_dev",
       "DEPTIT_EXPECTED_DB_USER": "deptit_next_app"}


def _prod(tmp_path, entorno="produccion", **extra):
    base = {"preproduccion": "deptit_next_preprod", "produccion": "deptit_next_prod"}[entorno]
    env = {"DEPTIT_ENTORNO": entorno, "DEPTIT_DB_HOST": "127.0.0.1", "DEPTIT_DB_NAME": base,
           "DEPTIT_DB_USER": f"{base}_app", "DEPTIT_DB_SSLMODE": "prefer", "DEPTIT_EXPECTED_DATABASE": base,
           "DEPTIT_EXPECTED_DB_USER": f"{base}_app", "DEPTIT_DOCUMENTS_DIR": str(tmp_path)}
    env.update(extra)
    return env


def _falla(env, fragmento):
    with pytest.raises(S.ConfigError) as exc:
        S.load(env)
    assert fragmento in str(exc.value), str(exc.value)
    return str(exc.value)


# ------------------------------------------------------------------------------------------ entornos
def test_desarrollo_con_defaults_seguros():
    s = S.load(dict(DEV))
    assert (s.entorno, s.db.name, s.db.user, s.db.sslmode) == ("desarrollo", "deptit_next_dev", "deptit_next_app",
                                                                "prefer")
    assert s.cookie_secure is False and s.api_docs is True
    assert s.documents_dir == S.REPO_DIR / "storage" / "documents"
    assert (s.timezone, s.db_timezone) == ("America/Argentina/Buenos_Aires", "UTC")
    assert (s.backend_host, s.backend_port, s.trusted_frontend_ips) == ("127.0.0.1", 8001, ("127.0.0.1", "::1"))


@pytest.mark.parametrize("entorno", ["preproduccion", "produccion"])
def test_preproduccion_y_produccion_exigen_valores_seguros(tmp_path, entorno):
    s = S.load(_prod(tmp_path, entorno))
    assert s.entorno == entorno and s.cookie_secure is True and s.api_docs is False
    assert s.documents_dir == tmp_path


@pytest.mark.parametrize("valor", ["", "  ", "Desarrollo", "prod", "test", "desarrollo2"])
def test_entorno_ausente_o_desconocido(valor):
    env = dict(DEV, DEPTIT_ENTORNO=valor)
    _falla(env, "DEPTIT_ENTORNO")


# ------------------------------------------------------------------------------------------ base de datos
@pytest.mark.parametrize("base", ["deptit", "DEPTIT", "postgres", "template1"])
def test_base_deptit_y_de_sistema_prohibidas(base):
    _falla(dict(DEV, DEPTIT_DB_NAME=base), "prohibida")
    _falla(dict(DEV, DEPTIT_EXPECTED_DATABASE=base), "prohibida")


def test_desarrollo_no_puede_apuntar_a_otra_base_del_mapa(tmp_path):
    _falla(dict(DEV, DEPTIT_DB_NAME="deptit_next_prod", DEPTIT_EXPECTED_DATABASE="deptit_next_prod"),
           "se exige exactamente 'deptit_next_dev'")
    _falla(_prod(tmp_path, DEPTIT_DB_NAME="deptit_next_dev", DEPTIT_EXPECTED_DATABASE="deptit_next_dev"),
           "se exige exactamente 'deptit_next_prod'")
    _falla(_prod(tmp_path, "preproduccion", DEPTIT_DB_NAME="deptit_next_prod"), "deptit_next_preprod")


def test_base_real_distinta_de_la_esperada():
    _falla(dict(DEV, DEPTIT_DB_NAME="deptit_next_otra"), "deptit_next_dev")


def test_roles():
    _falla(dict(DEV, DEPTIT_DB_USER="otro"), "se exige exactamente 'deptit_next_app'")
    _falla(dict(DEV, DEPTIT_EXPECTED_DB_USER="otro"), "rol esperado")
    for prohibido in ("postgres", "deptit_app"):
        _falla(dict(DEV, DEPTIT_DB_USER=prohibido, DEPTIT_EXPECTED_DB_USER=prohibido), "no puede ser postgres")
    _falla(dict(DEV, DEPTIT_EXPECTED_DB_USER=""), "DEPTIT_EXPECTED_DB_USER")


def test_produccion_no_reutiliza_el_rol_de_desarrollo(tmp_path):
    _falla(_prod(tmp_path, DEPTIT_DB_USER="deptit_next_app", DEPTIT_EXPECTED_DB_USER="deptit_next_app"),
           "rol de desarrollo")


@pytest.mark.parametrize("faltante", ["DEPTIT_DB_HOST", "DEPTIT_DB_NAME", "DEPTIT_DB_USER"])
def test_variables_de_conexion_obligatorias(faltante):
    env = dict(DEV)
    env.pop(faltante)
    _falla(env, "conexion incompleta")


def test_sslmode(tmp_path):
    _falla(_prod(tmp_path, DEPTIT_DB_SSLMODE=""), "DEPTIT_DB_SSLMODE es obligatoria")
    _falla(dict(DEV, DEPTIT_DB_SSLMODE="quizas"), "no es valido")
    _falla(_prod(tmp_path, DEPTIT_DB_HOST="db.interna.example", DEPTIT_DB_SSLMODE="prefer"), "base remota")
    assert S.load(_prod(tmp_path, DEPTIT_DB_HOST="db.interna.example", DEPTIT_DB_SSLMODE="verify-full")).db.sslmode \
        == "verify-full"


def test_database_url_alternativa_y_excluyente():
    url = "postgresql://deptit_next_app:placeholder@127.0.0.1:5432/deptit_next_dev"
    env = {k: v for k, v in DEV.items() if not k.startswith("DEPTIT_DB_")}
    s = S.load(dict(env, DATABASE_URL=url))
    assert (s.db.name, s.db.user, s.db.source) == ("deptit_next_dev", "deptit_next_app", "DATABASE_URL")
    _falla(dict(DEV, DATABASE_URL=url), "excluyentes")
    _falla(dict(env, DATABASE_URL="postgresql://deptit_next_app:placeholder@127.0.0.1/deptit"), "prohibida")
    msg = _falla(dict(env, DATABASE_URL="service=prod"), "service")
    assert "placeholder" not in msg


def test_los_mensajes_no_incluyen_la_contrasena():
    for env in (dict(DEV, DEPTIT_DB_PASSWORD="clave-secreta-xyz", DEPTIT_DB_NAME="deptit"),
                dict(DEV, DEPTIT_DB_PASSWORD="clave-secreta-xyz", DEPTIT_ENTORNO="x")):
        with pytest.raises(S.ConfigError) as exc:
            S.load(env)
        assert "clave-secreta-xyz" not in str(exc.value)
    assert "clave-secreta-xyz" not in repr(S.load(dict(DEV, DEPTIT_DB_PASSWORD="clave-secreta-xyz")))


# ------------------------------------------------------------------------------------------ seguridad por entorno
def test_cookie_insegura_y_docs_publicas_fuera_de_desarrollo(tmp_path):
    _falla(_prod(tmp_path, DEPTIT_SESSION_COOKIE_SECURE="0"), "DEPTIT_SESSION_COOKIE_SECURE=0")
    _falla(_prod(tmp_path, "preproduccion", DEPTIT_API_DOCS="1"), "DEPTIT_API_DOCS=1")
    _falla(dict(DEV, DEPTIT_API_DOCS="tal vez"), "1/0")
    assert S.load(dict(DEV, DEPTIT_SESSION_COOKIE_SECURE="1", DEPTIT_API_DOCS="0")).cookie_secure is True


def test_configuracion_contradictoria_o_invalida(tmp_path):
    _falla(dict(DEV, DEPTIT_SESSION_IDLE_TIMEOUT_MINUTES="9999"), "DEPTIT_SESSION_IDLE_TIMEOUT_MINUTES")
    _falla(dict(DEV, DEPTIT_LOGIN_IP_MAX_FAILED_ATTEMPTS="0"), "DEPTIT_LOGIN_IP_MAX_FAILED_ATTEMPTS")
    _falla(dict(DEV, DEPTIT_TRUSTED_FRONTEND_IPS="127.0.0.1,next-local"), "no es una IP")
    _falla(_prod(tmp_path, DEPTIT_BACKUP_GATE_CREAR_PERIODO="desactivado"), "solo se admite")
    _falla(dict(DEV, DEPTIT_BACKEND_HOST="0.0.0.0"), "loopback")
    assert S.load(dict(DEV, DEPTIT_BACKEND_HOST="10.0.0.5", DEPTIT_BACKEND_ALLOW_NON_LOOPBACK="1")).backend_host \
        == "10.0.0.5"
    _falla(dict(DEV, DEPTIT_TIMEZONE="Marte/Olimpo"), "zona horaria")
    _falla(dict(DEV, DEPTIT_BACKEND_PORT="70000"), "DEPTIT_BACKEND_PORT")


# ------------------------------------------------------------------------------------------ storage
def test_storage_fuera_de_desarrollo(tmp_path):
    _falla(_prod(tmp_path, DEPTIT_DOCUMENTS_DIR=""), "DEPTIT_DOCUMENTS_DIR es obligatoria")
    _falla(_prod(tmp_path, DEPTIT_DOCUMENTS_DIR="documentos/relativos"), "absoluta")
    _falla(_prod(tmp_path, DEPTIT_DOCUMENTS_DIR=str(tmp_path / "no-existe")), "no existe")
    _falla(_prod(tmp_path, DEPTIT_DOCUMENTS_DIR=str(BACKEND / "storage")), "codigo del backend")
    if sys.platform == "win32":
        for protegida in (r"C:\DEPTIT_PROD", r"C:\DEPTIT_PROD\documentos", r"C:\DEPTIT_REFACTOR_B13",
                          r"C:\DEPTIT_NEXT\reference_fix02\x"):
            _falla(dict(DEV, DEPTIT_DOCUMENTS_DIR=protegida), "arbol protegido")
    extra = tmp_path / "prohibida"
    extra.mkdir()
    _falla(_prod(tmp_path, DEPTIT_DOCUMENTS_DIR=str(extra), DEPTIT_FORBIDDEN_DIRS=str(tmp_path)), "arbol protegido")


def test_variable_obsoleta_de_storage_rechazada():
    _falla(dict(DEV, DEPTIT_NEXT_DOCUMENT_STORAGE_ROOT=r"C:\x"), "reemplazada por DEPTIT_DOCUMENTS_DIR")


def test_storage_portable_con_pathlib(tmp_path):
    s = S.load(dict(DEV, DEPTIT_DOCUMENTS_DIR=str(tmp_path / "docs")))
    assert isinstance(s.documents_dir, Path) and s.documents_dir == tmp_path / "docs"
    assert S.DEFAULT_DOCUMENTS_DIR == S.REPO_DIR / "storage" / "documents"
    from disposiciones import storage as ST
    assert ST.DocumentStorage(str(tmp_path)).root == str(tmp_path)


# ------------------------------------------------------------------------------------------ zona horaria
def test_zona_horaria_del_proceso(monkeypatch):
    s = S.load(dict(DEV))
    if hasattr(__import__("time"), "tzset"):
        monkeypatch.setenv("TZ", "UTC")
    assert S.apply_timezone(s) == ""  # en esta PC (y en POSIX tras tzset) coincide con Buenos Aires
    otra = S.load(dict(DEV, DEPTIT_TIMEZONE="Asia/Tokyo"))
    if not hasattr(__import__("time"), "tzset"):  # Windows: no se puede fijar; se detecta y falla fuera de desarrollo
        assert "no coincide" in S.apply_timezone(otra)
        prod = S.Settings(**{**otra.__dict__, "entorno": "produccion"})
        with pytest.raises(S.ConfigError):
            S.apply_timezone(prod)
        S.apply_timezone(s)


def test_zona_de_la_sesion_postgresql_fijada():
    pool = db.create_pool()
    try:
        with pool.connection() as conn:
            assert conn.execute("SELECT current_setting('TimeZone')").fetchone()[0] == "UTC"
    finally:
        pool.close()


# ------------------------------------------------------------------------------------------ guardas reales
def test_guardas_de_identidad_y_privilegios_contra_deptit_next_dev():
    d = db.load_settings()
    db.check_config(d)
    with psycopg.connect(d["database_url"], application_name="deptit_next_tests") as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        assert db.verify_identity(conn) == ("deptit_next_dev", "deptit_next_app")
        db.verify_privileges(conn)
        with pytest.raises(db.DatabaseGuardError):
            db.verify_identity(conn, ("deptit_next_prod", "deptit_next_app"))
        conn.rollback()


class _Conn:
    def __init__(self, row):
        self.row = row

    def execute(self, *_a):
        return self

    def fetchone(self):
        return self.row


@pytest.mark.parametrize("row,falta", [
    ((True, False, False, False, False, False, 0), "SUPERUSER"),
    ((False, True, False, False, False, False, 0), "CREATEDB"),
    ((False, False, False, False, True, False, 0), "CREATE en public"),
    ((False, False, False, False, False, True, 0), "CREATE en la base"),
    ((False, False, False, False, False, False, 3), "dueño de objetos"),
])
def test_guarda_de_privilegios_rechaza_un_rol_capaz_de_ddl(row, falta):
    with pytest.raises(db.DatabaseGuardError) as exc:
        db.verify_privileges(_Conn(row))
    assert falta in str(exc.value)
    db.verify_privileges(_Conn((False, False, False, False, False, False, 0)))


@pytest.mark.parametrize("real", [("deptit", "deptit_next_app"), ("deptit_next_dev", "postgres"),
                                  ("DEPTIT_NEXT_DEV", "deptit_next_app")])
def test_guarda_post_conexion(real):
    with pytest.raises(db.DatabaseGuardError):
        db.verify_identity(_Conn(real))


# ------------------------------------------------------------------------------------------ sin DDL automatico
DDL = re.compile(r"\b(CREATE\s+(UNIQUE\s+)?(TABLE|INDEX|EXTENSION|SCHEMA|VIEW|SEQUENCE|TRIGGER|FUNCTION|TYPE)|"
                 r"ALTER\s+(TABLE|SEQUENCE|INDEX|SCHEMA|TYPE)|DROP\s+(TABLE|INDEX|VIEW|SEQUENCE|SCHEMA|TYPE)|"
                 r"TRUNCATE\s|COMMENT\s+ON)", re.I)
# Texto DDL vendorizado del certificado, neutralizado por B12F (tareas ``schema`` = no-op; sentencias mutantes
# rechazadas antes de la base en el motor de lectura) y, ademas, imposible para el rol (sin CREATE ni ownership).
DDL_VENDORIZADO = {"analisis/motor/certificado.py", "integraciones/ciclo_periodos/motor/complemento.py"}


def _literales_ejecutables(path: Path) -> list[str]:
    import ast
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                docs.add(id(first.value))
    return [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in docs]


def test_ddl_solo_en_texto_vendorizado_neutralizado():
    con_ddl = set()
    for p in BACKEND.rglob("*.py"):
        rel = p.relative_to(BACKEND).as_posix()
        if rel.startswith((".venv/", "tests/", "tools_")) or "__pycache__" in rel or rel == "tests_guard_negative.py":
            continue
        if any(DDL.search(t) for t in _literales_ejecutables(p)):
            con_ddl.add(rel)
    assert con_ddl == DDL_VENDORIZADO
    entornos = {"analisis/motor/entorno.py": ("schema", "_MUTANTE"),
                "integraciones/ciclo_periodos/entorno.py": ('categoria == "schema"', "noop")}
    for rel, marcas in entornos.items():
        texto = (BACKEND / rel).read_text(encoding="utf-8")
        assert all(m in texto for m in marcas), rel


def test_el_arranque_no_ejecuta_ddl(monkeypatch):
    """El lifespan completo (configuracion, pool, guardas y todos los servicios) contra deptit_next_dev: se registran
    TODAS las sentencias y ninguna es DDL.  El arranque no es un mecanismo de migracion."""
    from fastapi.testclient import TestClient
    import main
    ejecutadas = []
    original = psycopg.Cursor.execute

    def espia(self, query, *a, **k):
        ejecutadas.append(query.as_string(self) if hasattr(query, "as_string") else str(query))
        return original(self, query, *a, **k)

    monkeypatch.setattr(psycopg.Cursor, "execute", espia)
    nombres = set(re.findall(r"app\.state\.(\w+) = ", (BACKEND / "main.py").read_text(encoding="utf-8-sig")))
    previo = {n: getattr(main.app.state, n) for n in nombres if hasattr(main.app.state, n)}
    try:
        with TestClient(main.app) as client:
            assert client.get("/health").json() == {"status": "ok", "service": "deptit-next-backend"}
    finally:
        for n in nombres:
            if n in previo:
                setattr(main.app.state, n, previo[n])
            elif hasattr(main.app.state, n):
                delattr(main.app.state, n)
    assert ejecutadas, "el arranque debe verificar identidad y privilegios"
    assert [q for q in ejecutadas if DDL.search(q)] == []
    assert any("rolsuper" in q for q in ejecutadas) and any("current_database()" in q for q in ejecutadas)


def test_el_rol_real_no_puede_crear_tablas():
    """Defensa en profundidad: aunque un bug intentara DDL, PostgreSQL lo rechaza (transaccion revertida)."""
    d = db.load_settings()
    with psycopg.connect(d["database_url"], application_name="deptit_next_tests") as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("CREATE TABLE public.zznext_e6_ddl_prohibido (id int)")
        conn.rollback()
        assert conn.execute("SELECT to_regclass('public.zznext_e6_ddl_prohibido')").fetchone()[0] is None
        conn.rollback()


# ------------------------------------------------------------------------------------------ secretos / hardcoding
def test_sin_bases_ni_rutas_productivas_fijadas_en_runtime():
    for p in BACKEND.rglob("*.py"):
        rel = p.relative_to(BACKEND).as_posix()
        if rel.startswith((".venv/", "tests/", "tools_")) or "__pycache__" in rel or rel in (
                "settings.py", "tests_guard_negative.py"):
            continue
        texto = p.read_text(encoding="utf-8-sig")
        assert not re.search(r"REQUIRED_DATABASE\s*=|REQUIRED_DB_USER\s*=", texto), rel
        assert r"C:\DEPTIT_NEXT\storage" not in texto and "C:\\\\DEPTIT_NEXT\\\\storage" not in texto, rel
        assert not re.search(r"postgres(ql)?://[^:/\s]+:[^@\s]+@", texto), rel


def test_sin_material_de_credenciales_en_el_arbol():
    repo = BACKEND.parent
    assert not (repo / "migration" / "db_setup" / "02_create_role_and_grants.generated.sql").exists()
    plantilla = (repo / "migration" / "db_setup" / "02_create_role_and_grants.template.sql").read_text(
        encoding="utf-8")
    assert plantilla.count("__SCRAM_VERIFIER__") == 1  # solo en PASSWORD, no en comentarios
    gitignore = (repo / ".gitignore").read_text(encoding="utf-8")
    for patron in (".env", "migration/db_setup/*.generated.sql", "pgpass.conf", "storage/"):
        assert patron in gitignore
    verificador = re.compile(r"SCRAM-SHA-256\$\d+:[A-Za-z0-9+/=]{16,}\$[A-Za-z0-9+/=]{20,}:[A-Za-z0-9+/=]{20,}")
    for p in list((repo / "migration").rglob("*")) + list((repo / "docs").rglob("*.md")) + list(BACKEND.glob("*.py")):
        if p.is_file():
            assert not verificador.search(p.read_text(encoding="utf-8", errors="ignore")), p
