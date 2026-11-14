"""Etapa 6A-B2: restore de base (reglas de destino, plan, proteccion de deptit_next_dev, limpieza) y comparacion
semantica.  Sin crear bases: la prueba real de punta a punta (con los roles operativos) esta en
``test_e6_b2_recuperacion_real.py``."""

from __future__ import annotations

import dataclasses
import subprocess

import psycopg
import pytest

from operacion import comparacion, config, restore_db as R

from test_e6_b2_backup import NOW, respaldo  # noqa: F401  (fixture: backup real en un directorio temporal)


def _cfg(respaldo, **cambios):
    cfg, _, _ = respaldo
    return dataclasses.replace(cfg, **cambios)


@pytest.mark.parametrize("target,codigo", [
    ("deptit", "TARGET_FORBIDDEN"), ("postgres", "TARGET_FORBIDDEN"), ("template1", "TARGET_FORBIDDEN"),
    ("deptit_next_dev", "TARGET_NOT_ISOLATED"), ("deptit_next_prod", "TARGET_NOT_ISOLATED"),
    ("deptit_next_preprod", "TARGET_NOT_ISOLATED"), ("deptit_restore_drill_x", "TARGET_NOT_ISOLATED"),
    ("deptit_next_restore_test_", "TARGET_NOT_ISOLATED"), ("deptit_next_restore_test_A", "TARGET_NOT_ISOLATED"),
    ("deptit_next_restore_test_x;drop", "TARGET_NOT_ISOLATED"), ("", "TARGET_NOT_ISOLATED")])
def test_destinos_de_prueba_prohibidos(respaldo, target, codigo):
    p = R.problemas_destino(target, modo=R.PRUEBA, cfg=respaldo[0], source_name="deptit_next_dev")
    assert p and p[0].startswith(codigo), p


def test_destino_de_prueba_valido_y_recuperacion(respaldo):
    cfg = respaldo[0]
    assert R.problemas_destino("deptit_next_restore_test_20261103", modo=R.PRUEBA, cfg=cfg,
                               source_name="deptit_next_dev") == []
    assert R.problemas_destino("deptit_next_dev", modo=R.RECUPERACION, cfg=cfg, source_name="deptit_next_dev") == []
    for t in ("deptit_next_prod", "deptit", "deptit_next_restore_test_x"):
        assert R.problemas_destino(t, modo=R.RECUPERACION, cfg=cfg, source_name="deptit_next_dev"), t
    assert R.problemas_destino("x", modo="otro", cfg=cfg, source_name="x")[0].startswith("MODE_INVALID")


def _sin_efectos(*a, **k):
    raise AssertionError("no debia ejecutar ningun comando")


def test_plan_sin_efectos(respaldo):
    cfg, _, rep = respaldo
    cfg = dataclasses.replace(cfg, restore=config.Credencial("x_restore", "x"))
    r = R.restaurar(cfg, rep["manifest"], target="deptit_next_restore_test_plan", runner=_sin_efectos, now=NOW)
    assert r["result"] == "PLANNED" and r["steps"] == ["backup_verified", "target_validated"], r
    assert r["cleanup"]["dropped"] is False


def test_rechaza_destino_prohibido_antes_de_ejecutar(respaldo):
    cfg, _, rep = respaldo
    cfg = dataclasses.replace(cfg, restore=config.Credencial("x_restore", "x"))
    for target in ("deptit", "deptit_next_dev"):
        r = R.restaurar(cfg, rep["manifest"], target=target, execute=True, runner=_sin_efectos, now=NOW)
        assert r["result"] == "FAIL" and r["code"] in ("TARGET_FORBIDDEN", "TARGET_NOT_ISOLATED"), r
    r = R.restaurar(dataclasses.replace(cfg, restore=None), rep["manifest"], execute=True, runner=_sin_efectos)
    assert r["code"] == "RESTORE_ROLE_MISSING"


def test_rechaza_backup_invalido_u_otro_entorno(respaldo, tmp_path):
    import json
    import shutil
    cfg, d, rep = respaldo
    cfg = dataclasses.replace(cfg, restore=config.Credencial("x_restore", "x"))
    copia = tmp_path / "bk"
    shutil.copytree(d, copia)
    man = copia / rep["manifest"].split("\\")[-1]
    doc = json.loads(man.read_text(encoding="utf-8"))
    doc["deptit"]["entorno"] = "produccion"
    man.write_text(json.dumps(doc), encoding="utf-8")
    assert R.restaurar(cfg, man, execute=True, runner=_sin_efectos, now=NOW)["code"] == "OTHER_ENVIRONMENT"
    (copia / doc["dump"]["filename"]).write_bytes(b"PGDMP basura")
    assert R.restaurar(cfg, man, execute=True, runner=_sin_efectos, now=NOW)["code"] == "BACKUP_INVALID"


def test_recuperacion_nunca_restaura_sobre_dev_con_datos(respaldo):
    """deptit_next_dev real (con datos): la recuperacion exige confirmacion y una base VACIA -> siempre rechazada."""
    cfg, _, rep = respaldo
    app = config.Credencial(cfg.app.db.user, cfg.app.db.password)
    cfg = dataclasses.replace(cfg, restore=app)
    r = R.restaurar(cfg, rep["manifest"], modo=R.RECUPERACION, target="deptit_next_dev", execute=True,
                    runner=_sin_efectos, now=NOW)
    assert r["code"] == "CONFIRMATION_REQUIRED", r
    r = R.restaurar(cfg, rep["manifest"], modo=R.RECUPERACION, target="deptit_next_dev", execute=True,
                    confirm="deptit_next_dev", runner=_sin_efectos, now=NOW)
    assert r["result"] == "FAIL" and r["code"] == "TARGET_NOT_EMPTY", r
    assert r["cleanup"] == {"dropped": False, "reason": "esta corrida no creo ninguna base"}


def test_limpieza_solo_de_la_base_creada_y_confirmada(respaldo):
    cfg = dataclasses.replace(respaldo[0], restore=config.Credencial("x_restore", "x"))
    llamadas = []

    def runner(cmd, **kw):
        llamadas.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")
    which = lambda name, path=None: name  # noqa: E731
    t = "deptit_next_restore_test_limpieza"
    assert R._cleanup(cfg, False, t, True, t, runner, which)["dropped"] is False
    assert R._cleanup(cfg, True, t, False, t, runner, which)["dropped"] is False
    assert R._cleanup(cfg, True, t, True, "otro_nombre", runner, which)["dropped"] is False
    assert R._cleanup(cfg, True, "deptit_next_dev", True, "deptit_next_dev", runner, which)["dropped"] is False
    assert llamadas == []
    assert R._cleanup(cfg, True, t, True, t, runner, which)["dropped"] is True
    assert llamadas == [["dropdb", "--no-password", "--maintenance-db=postgres", t]]


def test_comparacion_semantica(respaldo):
    cfg = respaldo[0]
    tablas = ["app_usuarios", "periodos", "materias", "docentes"]
    with psycopg.connect(cfg.app.db.conninfo) as conn:
        conn.read_only = True
        a = {"esquema": comparacion.huella_esquema(conn), "datos": comparacion.huella_datos(conn, solo=tablas)}
        b = {"esquema": comparacion.huella_esquema(conn), "datos": comparacion.huella_datos(conn, solo=tablas)}
    assert comparacion.diferencias(a, b) == [] and a["datos"]["sha256"] == b["datos"]["sha256"]
    assert len(a["esquema"]["tablas"]) >= 42 and a["datos"]["tablas"]["app_usuarios"]["filas"] == 9
    import copy
    c = copy.deepcopy(b)
    c["datos"]["tablas"]["periodos"]["md5"] = "0" * 32
    c["esquema"]["indices"] = c["esquema"]["indices"][1:]
    c["datos"]["tablas"].pop("materias")
    d = comparacion.diferencias(a, c)
    assert "esquema.indices distinto" in d and any(x.startswith("datos.periodos") and "contenido distinto" in x
                                                    for x in d) and any(x.startswith("datos.materias") for x in d)
    texto = " ".join(d)
    assert "@" not in texto  # sin valores de filas
