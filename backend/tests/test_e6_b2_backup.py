"""Etapa 6A-B2: backup de base propio de NEXT (formato certificado B11) y gate de Crear periodo
(docs/ETAPA6_6AB2_OPERATION_RECOVERY.md).

Un backup REAL de deptit_next_dev (pg_dump + pg_restore --list + lector independiente) en un directorio temporal, con el
rol de la aplicacion: ese rol no lee 12 tablas heredadas sin uso, que se excluyen SOLO en estas pruebas (el backup
operativo usa el rol de backup, que lee todas).  Las variantes negativas copian ese backup y lo alteran."""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import os
import re
import shutil
from pathlib import Path

import psycopg
import pytest

import main  # noqa: F401  (registra el validador del gate, como en el arranque)
import settings as S
from integraciones.ciclo_periodos import backup_gate as G
from integraciones.ciclo_periodos.ref_b11 import backup as B
from integraciones.ciclo_periodos.ref_b11 import backup_gate as B11
from integraciones.ciclo_periodos.ref_b11.backup_manifest import list_manifests, verify_backup
from operacion import backup_db, config

BACKEND = Path(__file__).resolve().parents[1]
REF = Path(r"C:\DEPTIT_NEXT\reference_fix02\deptit_refactor\operations")
PG_BIN = r"C:\Program Files\PostgreSQL\18\bin"
NOW = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)  # el backup real se crea "ahora"


def _env_real(backup_dir: Path, **extra) -> dict:
    S.load_env_file()
    env = {k: v for k, v in os.environ.items() if k.startswith(("DEPTIT_", "DATABASE_URL"))}
    for k in ("DEPTIT_BACKUP_DB_USER", "DEPTIT_BACKUP_DB_PASSWORD", "DEPTIT_RESTORE_DB_USER",
              "DEPTIT_RESTORE_DB_PASSWORD"):
        env.pop(k, None)
    env.update({"DEPTIT_BACKUP_DIR": str(backup_dir), "DEPTIT_PG_BIN_DIR": PG_BIN,
                "DEPTIT_CRITICAL_BACKUP_MAX_AGE_HOURS": "24", **extra})
    return env


def _sin_select(cfg) -> list:
    with psycopg.connect(cfg.app.db.conninfo) as conn:
        return [r[0] for r in conn.execute(
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'public' "
            "AND c.relkind IN ('r', 'p', 'S') AND NOT has_table_privilege(c.oid, 'SELECT') ORDER BY 1").fetchall()]


def _runner_app(excluir):
    """pg_dump real con ``--exclude-table`` para lo que el rol de la app no puede leer (solo en pruebas)."""
    import subprocess

    def run(cmd, **kw):
        if os.path.basename(cmd[0]).lower().startswith("pg_dump") and "--version" not in cmd:
            cmd = cmd[:-2] + [f"--exclude-table=public.{t}" for t in excluir] + cmd[-2:]
        return subprocess.run(cmd, **kw)
    return run


@pytest.fixture(scope="module")
def respaldo(tmp_path_factory):
    d = tmp_path_factory.mktemp("b2_backups")
    cfg = config.load(_env_real(d), read_files=False)
    cred = config.Credencial(cfg.app.db.user, cfg.app.db.password)
    rep = backup_db.respaldar(cfg, now=NOW, cred=cred, runner=_runner_app(_sin_select(cfg)), set_id=None)
    assert rep["result"] == "PASS", rep
    return cfg, d, rep


def _copia(respaldo, tmp_path) -> tuple:
    cfg, d, rep = respaldo
    nuevo = tmp_path / "backups"
    shutil.copytree(d, nuevo)
    cfg2 = dataclasses.replace(cfg, backup_dir=nuevo, env={**cfg.env, "DEPTIT_BACKUP_DIR": str(nuevo)})
    return cfg2, nuevo, nuevo / Path(rep["manifest"]).name, nuevo / Path(rep["dump"]).name


def _evaluar(cfg, now=None, **extra):
    """Decision completa del gate (B11 + entorno NEXT) con el reloj del gate fijado en ``now``."""
    e = {**cfg.env, G.GATE_ENV: G.ACTIVO, **extra}
    original = B11.utc_now
    B11.utc_now = lambda: now or NOW
    try:
        return G.evaluar(cfg.identity_url(), env=e)
    finally:
        B11.utc_now = original


# ------------------------------------------------------------------ formato certificado y herramienta
def test_copias_literales_b11():
    for nombre in ("backup.py", "pg_archive.py", "retention.py", "restore_drill.py", "backup_gate.py",
                   "backup_manifest.py", "db_identity.py"):
        assert (BACKEND / "integraciones/ciclo_periodos/ref_b11" / nombre).read_bytes() == (REF / nombre).read_bytes()


def test_backup_real_valido_y_sin_secretos(respaldo):
    cfg, d, rep = respaldo
    assert rep["steps"] == ["tools", "pg_dump", "pg_restore_list", "archive_inspection", "publish_dump",
                            "publish_manifest"]
    assert rep["verificacion"]["code"] == "VALID" and rep["conexion"]["database"] == "deptit_next_dev"
    m = json.loads(Path(rep["manifest"]).read_text(encoding="utf-8"))
    assert m["format_version"] == 1 and m["kind"] == "deptit-postgresql-backup"
    assert m["database"] == {"host": cfg.app.db.host, "port": cfg.app.db.port, "name": "deptit_next_dev",
                             "user": cfg.app.db.user}
    assert m["deptit"]["entorno"] == "desarrollo" and m["deptit"]["producto"] == "deptit-next"
    assert m["deptit"]["backup_id"] == Path(rep["manifest"]).name[:-len(".manifest.json")]
    assert len(m["deptit"]["esquema_sha256"]) == 64 and m["tools"]["pg_dump_version"].startswith("pg_dump")
    assert m["validation"]["status"] == "PASS" and m["validation"]["missing_critical_tables"] == []
    assert m["dump"]["archive_dbname"] == "deptit_next_dev" and m["dump"]["tables"] >= 19
    texto = Path(rep["manifest"]).read_text(encoding="utf-8") + json.dumps(rep)
    assert cfg.app.db.password and cfg.app.db.password not in texto
    assert "password" not in texto.lower()
    assert [p.name for p in d.iterdir() if p.name.endswith(".partial")] == []


def test_backup_rechaza_base_o_rol_incorrecto(respaldo, tmp_path):
    cfg, _, _ = respaldo
    otro = dataclasses.replace(cfg.app, expected_database="deptit_next_prod")
    rep = backup_db.respaldar(dataclasses.replace(cfg, app=otro, backup_dir=tmp_path), now=NOW,
                              cred=config.Credencial(cfg.app.db.user, cfg.app.db.password))
    assert rep["result"] == "FAIL" and rep["code"] == "CONNECTION_CHECK_FAILED" and not list(tmp_path.iterdir())
    rep = backup_db.respaldar(cfg, now=NOW, cred=config.Credencial("deptit_next_backup_inexistente", "x"))
    assert rep["result"] == "FAIL" and rep["code"] == "CONNECTION_CHECK_FAILED"
    assert backup_db.respaldar(dataclasses.replace(cfg, backup=None), now=NOW)["code"] == "BACKUP_ROLE_MISSING"


def test_backup_vacio_o_fallido_no_publica(respaldo, tmp_path):
    cfg, _, _ = respaldo
    cfg2 = dataclasses.replace(cfg, backup_dir=tmp_path)
    cred = config.Credencial(cfg.app.db.user, cfg.app.db.password)
    import subprocess

    def vacio(cmd, **kw):
        if "--version" in cmd:
            return subprocess.run(cmd, **kw)
        return subprocess.CompletedProcess(cmd, 0, "", "")  # pg_dump "exitoso" sin contenido

    def falla(cmd, **kw):
        if "--version" in cmd:
            return subprocess.run(cmd, **kw)
        return subprocess.CompletedProcess(cmd, 1, "", "error simulado")
    for runner, codigo in ((vacio, "DUMP_EMPTY"), (falla, "PG_DUMP_FAILED")):
        rep = backup_db.respaldar(cfg2, now=NOW, cred=cred, runner=runner)
        assert rep["result"] == "FAIL" and rep["code"] == codigo, rep
        assert list(tmp_path.iterdir()) == []  # ni dump, ni manifest, ni temporales


def test_config_backup_dir(tmp_path):
    env = _env_real(tmp_path / "b")
    assert config.load(env, read_files=False).backup_dir == tmp_path / "b"
    for valor, fragmento in (("", "obligatoria"), ("relativo\\b", "absoluta"),
                             (str(BACKEND / "x"), "codigo del backend"),
                             (str(S.REPO_DIR / "frontend" / "b"), "frontend/"),
                             (str(S.REPO_DIR / ".git"), ".git/"),
                             (r"C:\DEPTIT_PROD\backups_next", "protegido"),
                             (str(S.REPO_DIR), "raiz del proyecto")):
        with pytest.raises(config.OpsConfigError) as exc:
            config.load({**env, "DEPTIT_BACKUP_DIR": valor}, read_files=False)
        assert fragmento in str(exc.value), (valor, str(exc.value))
    docs = tmp_path / "docs"
    with pytest.raises(config.OpsConfigError, match="raiz documental"):
        config.load({**env, "DEPTIT_DOCUMENTS_DIR": str(docs), "DEPTIT_BACKUP_DIR": str(docs / "bk")},
                    read_files=False)
    with pytest.raises(config.OpsConfigError, match="no puede ser"):
        config.load({**env, "DEPTIT_BACKUP_DB_USER": "deptit_next_app"}, read_files=False)
    with pytest.raises(config.OpsConfigError, match="distintos"):
        config.load({**env, "DEPTIT_BACKUP_DB_USER": "x_ops", "DEPTIT_RESTORE_DB_USER": "x_ops"}, read_files=False)


def test_credenciales_operativas_no_se_exponen(tmp_path):
    cfg = config.load({**_env_real(tmp_path), "DEPTIT_BACKUP_DB_USER": "x_backup",
                       "DEPTIT_BACKUP_DB_PASSWORD": "secreto-de-prueba-123"}, read_files=False)
    assert "secreto-de-prueba-123" not in repr(cfg.backup) and "secreto-de-prueba-123" not in cfg.identity_url()
    assert "x_backup:secreto-de-prueba-123@" in cfg.url(cfg.backup)  # solo en memoria, para el passfile B11


# ------------------------------------------------------------------ gate de Crear periodo
def test_main_pasa_al_gate_la_url_de_identidad():
    s = S.get()
    url = s.db.identity_url
    assert s.db.password not in url and url.startswith("postgresql://deptit_next_app@")
    from integraciones.ciclo_periodos.ref_b11.db_identity import identity_from_url
    assert identity_from_url(url).name == "deptit_next_dev"
    assert "identity_url" in (BACKEND / "main.py").read_text(encoding="utf-8-sig")
    with pytest.raises(Exception):
        identity_from_url(s.db.conninfo)  # la conninfo libpq NO es una URL: B11 la rechazaria siempre


def test_gate_acepta_backup_real_vigente(respaldo):
    cfg, _, _ = respaldo
    d = _evaluar(cfg, now=NOW + dt.timedelta(hours=1))
    assert d.permitido and d.codigo == B11.ALLOW


def test_gate_rechaza_sin_backup_y_configuracion_invalida(respaldo, tmp_path):
    cfg, _, _ = respaldo
    vacio = tmp_path / "vacio"
    vacio.mkdir()
    casos = (({"DEPTIT_BACKUP_DIR": str(vacio)}, "DENY_NO_BACKUP"),
             ({"DEPTIT_BACKUP_DIR": ""}, "DENY_CONFIG_BACKUP_DIR"),
             ({"DEPTIT_BACKUP_DIR": str(tmp_path / "no_existe")}, "DENY_CONFIG_BACKUP_DIR"),
             ({"DEPTIT_CRITICAL_BACKUP_MAX_AGE_HOURS": "0"}, "DENY_CONFIG_MAX_AGE"),
             ({"DEPTIT_CRITICAL_BACKUP_MAX_AGE_HOURS": ""}, "DENY_CONFIG_MAX_AGE"),
             ({"DEPTIT_CRITICAL_BACKUP_MAX_AGE_HOURS": "1000"}, "DENY_CONFIG_MAX_AGE"))
    for extra, codigo in casos:
        d = _evaluar(cfg, **extra)
        assert not d.permitido and d.codigo == codigo, (extra, d)
        assert "No se realizó ningún cambio." in d.mensaje
    with pytest.raises(G.GateConfigError):
        G.validar_arranque({"DEPTIT_ENTORNO": "produccion", G.GATE_ENV: G.DESACTIVADO})


def test_gate_rechaza_vencido_y_futuro(respaldo):
    cfg, _, _ = respaldo
    assert _evaluar(cfg, now=NOW + dt.timedelta(hours=25)).codigo == "DENY_EXPIRED"
    assert _evaluar(cfg, now=NOW - dt.timedelta(hours=1)).codigo == "DENY_FUTURE_TIMESTAMP"


def test_gate_rechaza_backups_manipulados(respaldo, tmp_path):
    def caso(nombre, alterar, codigo):
        cfg, d, man, dump = _copia(respaldo, tmp_path / nombre)
        alterar(man, dump, d)
        r = _evaluar(cfg)
        assert not r.permitido and r.codigo == codigo, (nombre, r)

    def editar(cambio):
        def f(man, dump, d):
            doc = json.loads(man.read_text(encoding="utf-8"))
            cambio(doc)
            man.write_text(json.dumps(doc), encoding="utf-8")
        return f

    def flip(man, dump, d):  # mismo tamaño, otro contenido
        datos = bytearray(dump.read_bytes())
        datos[-10] ^= 0xFF
        dump.write_bytes(bytes(datos))

    caso("hash", lambda m, du, d: flip(m, du, d), "DENY_HASH_MISMATCH")
    caso("dump_ausente", lambda m, du, d: du.unlink(), "DENY_DUMP_MISSING")
    caso("truncado", lambda m, du, d: du.write_bytes(du.read_bytes()[:-100]), "DENY_SIZE_MISMATCH")
    caso("manifest_roto", lambda m, du, d: m.write_text("{no json", encoding="utf-8"), "DENY_MANIFEST_INVALID")
    caso("manifest_clave", editar(lambda doc: doc.pop("tools")), "DENY_MANIFEST_INVALID")
    caso("otra_base", editar(lambda doc: doc["database"].update(name="deptit_next_prod")), "DENY_OTHER_DATABASE")
    caso("otro_servidor", editar(lambda doc: doc["database"].update(host="10.0.0.9")), "DENY_OTHER_DATABASE")
    caso("incompleto", editar(lambda doc: doc["validation"].update(status="FAIL")), "DENY_VALIDATION_NOT_PASSED")
    caso("otro_entorno", editar(lambda doc: doc["deptit"].update(entorno="produccion")), G.DENY_OTHER_ENVIRONMENT)
    caso("sin_entorno", editar(lambda doc: doc["deptit"].pop("entorno")), G.DENY_OTHER_ENVIRONMENT)
    caso("solo_partial", lambda m, du, d: (m.unlink(), du.rename(d / f".{du.name}.partial")), "DENY_NO_BACKUP")
    caso("dump_sin_manifest", lambda m, du, d: m.unlink(), "DENY_NO_BACKUP")


def test_gate_otro_entorno_mensaje_certificado(respaldo, tmp_path):
    cfg, d, man, dump = _copia(respaldo, tmp_path)
    doc = json.loads(man.read_text(encoding="utf-8"))
    doc["deptit"]["entorno"] = "preproduccion"
    man.write_text(json.dumps(doc), encoding="utf-8")
    r = _evaluar(cfg)
    assert r.mensaje.startswith("No se puede crear el período: falta un backup reciente y verificado")
    assert "el backup es de otro entorno" in r.mensaje and "código DENY_OTHER_ENVIRONMENT" in r.mensaje
    assert str(d) not in r.mensaje


def test_gate_crear_periodo_deniega_otro_entorno_sin_sql(respaldo, tmp_path):
    """Servicio real de Crear periodo con el gate activo y un backup de otro entorno: 409 BACKUP antes de abrir la
    transaccion (la funcion de transaccion no se invoca)."""
    from integraciones.ciclo_periodos.service import CicloPeriodosService
    from periodos.service import PeriodosError
    cfg, d, man, _ = _copia(respaldo, tmp_path)
    doc = json.loads(man.read_text(encoding="utf-8"))
    doc["deptit"]["entorno"] = "produccion"
    man.write_text(json.dumps(doc), encoding="utf-8")

    class Periodos:
        def scope(self, record):
            return None

    abiertas = []
    svc = CicloPeriodosService(None, Periodos(), None, database_url=cfg.identity_url(),
                               transaction=lambda: abiertas.append(1),
                               env={**cfg.env, G.GATE_ENV: G.ACTIVO})
    svc._op = lambda *a, **k: object()
    svc._separate = lambda *a, **k: None
    with pytest.raises(PeriodosError) as exc:
        svc.crear(object(), {"anio": 2031, "semestre": 1})
    assert exc.value.status == 409 and "DENY_OTHER_ENVIRONMENT" in exc.value.message and abiertas == []


def test_verify_db_cli_usa_el_gate(respaldo, capsys):
    from operacion.__main__ import main as cli
    cfg, d, _ = respaldo
    rc = cli(["verify-db"], env={**cfg.env})
    out = json.loads(capsys.readouterr().out)
    assert out["code"] == B11.ALLOW and out["result"] == "PASS" and rc == 0
    assert list_manifests(d) and verify_backup(list_manifests(d)[0]).ok


HERRAMIENTAS_OPERATIVAS = ("integraciones.ciclo_periodos.ref_b11.backup",
                           "integraciones.ciclo_periodos.ref_b11.restore_drill",
                           "integraciones.ciclo_periodos.ref_b11.retention",
                           "integraciones.ciclo_periodos.ref_b11.pg_archive")


def test_runtime_no_carga_herramientas_operativas():
    """La app (``main`` + todas sus rutas) NO carga la CLI ``operacion`` ni las herramientas B11 que lanzan procesos
    (pg_dump / pg_restore): el gate solo LEE manifests.  Es la contraparte de las exclusiones de alcance de
    ``test_analisis_motor::test_sin_instalacion_dinamica...`` y ``test_e4_01::test_composicion_solo_lectura...``.
    Interprete NUEVO (este proceso de pytest ya las importo)."""
    import subprocess
    import sys
    codigo = ("import sys, main; assert type(main.app).__name__ == 'FastAPI'; "
              "print(' '.join(sorted(sys.modules)))")
    p = subprocess.run([sys.executable, "-B", "-c", codigo], cwd=BACKEND, capture_output=True, text=True,
                       stdin=subprocess.DEVNULL, timeout=120)
    assert p.returncode == 0, p.stderr[-2000:]
    cargados = set(p.stdout.split())
    assert "integraciones.ciclo_periodos.backup_gate" in cargados  # el gate SI es runtime
    assert not {m for m in cargados if m == "operacion" or m.startswith("operacion.")}
    assert not cargados & set(HERRAMIENTAS_OPERATIVAS)
    # y ningun modulo de runtime importa la CLI operativa
    for py in BACKEND.rglob("*.py"):
        rel = py.relative_to(BACKEND).as_posix()
        if rel.startswith((".venv/", "tests/", "operacion/")) or "__pycache__" in rel:
            continue
        assert not re.search(r"^\s*(from|import)\s+operacion\b", py.read_text(encoding="utf-8", errors="ignore"),
                             re.M), rel
