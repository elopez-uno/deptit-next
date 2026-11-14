"""Diferenciales de ESCRITURA de Sueldos: ``guardar_escala_salarial_v256`` certificado vs el servicio NEXT, desde el
mismo estado (ROLLBACK al SAVEPOINT entre ambos).  Se comparan ``escalas_salariales_docentes`` de la institucion (y que
``movimientos`` no cambie) y la secuencia de COMMITs por operacion B12H (6 UPSERT + 1 COMMIT, atomico)."""

from __future__ import annotations

import pprint

import psycopg
import pytest

from sueldos import escrituras as E
from sueldos import rules as SR
from sueldos.service import SPEC_GUARDAR_ESCALA, SueldosError
from sueldos_support import (  # noqa: F401  (fixtures)
    audit_rows, audit_store, certified_sueldos, db_conn, session_for, state, sueldos,
)

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")


def _correr(fn):
    try:
        return fn(), None
    except psycopg.Error:
        raise
    except Exception as exc:
        if isinstance(exc.__context__, psycopg.Error) or isinstance(exc.__cause__, psycopg.Error):
            raise
        return None, exc


def comparar(db_conn, audit_store, certificado, siguiente, inst=1, dep=1, email="info@test.local", nombre="Usuario 3"):
    ns = certified_sueldos(db_conn, inst, dep, email=email, nombre=nombre)
    with db_conn.transaction() as tx:
        res_c, err_c = _correr(lambda: certificado(ns))
        st_c = state(db_conn, inst)
        ops_c = list(ns["_frames"].ops)
        raise psycopg.Rollback(tx)
    with db_conn.transaction() as tx:
        n = len(audit_store.events)
        res_n, err_n = _correr(siguiente)
        st_n = state(db_conn, inst)
        eventos = audit_rows(db_conn)
        nuevos = audit_store.events[n:]
        raise psycopg.Rollback(tx)
    assert st_c == st_n, f"cert:\n{pprint.pformat(st_c)}\nNEXT:\n{pprint.pformat(st_n)}"
    ops_n, vistos = [], {}
    for e in eventos:
        cid = str(e["correlation_id"])
        if cid not in vistos:
            vistos[cid] = {"op": e["operation"], "commits": []}
            ops_n.append(vistos[cid])
        m = e["metadata"]
        vistos[cid]["commits"].append({k: m.get(k) for k in ("commit_seq", "mutating_statements", "committing_writer",
                                                            "nested_system_task")})
    assert [o for o in ops_c if o["commits"]] == ops_n, f"cert:\n{pprint.pformat(ops_c)}\nNEXT:\n{pprint.pformat(ops_n)}"
    return res_c, err_c, res_n, err_n, nuevos, eventos, st_n


def _valores(factor=1.0, **cambios):
    v = {c: round(b * factor, 2) for c, b in SR.BASICOS_JUNIO_2026_V256.items()}
    v.update(cambios)
    return v


def _rec(service, repo, uid=3, inst=1, dep=1):
    rec = session_for(service, repo, uid)[0]
    if uid == 1:
        service.set_context(rec, inst, dep, False)
    return rec


@pytest.mark.parametrize("mes,anio,factor", [(10, 2026, 1.05), (6, 2026, 1.0), (6, 2026, 1.1), (1, 2025, 0.8),
                                             (12, 2100, 2.0)])
def test_guardar_escala_alta_y_actualizacion(service, repo, db_conn, audit_store, sueldos, mes, anio, factor):
    rec = _rec(service, repo)
    mes_ref = f"{anio:04d}-{mes:02d}"
    valores = _valores(factor)
    _, err_c, res, err, nuevos, eventos, st = comparar(
        db_conn, audit_store, lambda ns: ns["guardar_escala_salarial_v256"](mes_ref, valores),
        lambda: sueldos.guardar_escala(rec, {"anio": anio, "mes": mes, "valores": valores}))
    assert err_c is None and err is None
    assert res == {"mensaje": f"Escala {mes:02d}/{anio:04d} guardada correctamente.", "tono": "success"}
    assert [(e["operation"], e["action"], e["action_scope"], e["entity_type"], e["entity_id"], e["outcome"],
             e["audit_mode"], e["institucion_id"], e["departamento_id"]) for e in eventos] == [
        ("guardar_escala_salarial_v256", "sueldos.write", "institution", "escala_salarial", None, "SUCCESS",
         "IN_TRANSACTION", 1, 1)]
    assert eventos[0]["metadata"] == {"commit_seq": 1, "mutating_statements": 6,
                                      "committing_writer": "guardar_escala_salarial_v256"}
    assert nuevos == []
    assert sum(f'"mes_referencia": "{mes_ref}"' in x and '"usuario_actualizacion": "Usuario 3"' in x for x in st) == 6


@pytest.mark.parametrize("cambios,mensaje", [
    ({"Adjunto": 0}, "El básico de Adjunto debe ser mayor a cero."),
    ({"Titular": 0.004}, "El básico de Titular debe ser mayor a cero."),
    ({"Ayudante 2da": 0.0}, "El básico de Ayudante 2da debe ser mayor a cero."),
])
def test_error_intermedio_es_atomico(service, repo, db_conn, audit_store, sueldos, cambios, mensaje):
    """Un basico <= 0 en el 1º, 3º o 6º cargo: los UPSERT previos se revierten (0 COMMIT), mismo texto."""
    rec = _rec(service, repo)
    valores = _valores(1.2, **cambios)
    antes = state(db_conn, 1)
    _, err_c, _, err, nuevos, eventos, st = comparar(
        db_conn, audit_store, lambda ns: ns["guardar_escala_salarial_v256"]("2026-06", valores),
        lambda: sueldos.guardar_escala(rec, {"anio": 2026, "mes": 6, "valores": valores}))
    assert str(err_c) == mensaje and err.message == f"No se pudo guardar la escala: {mensaje}"
    assert st == antes and eventos == []
    assert [(e.operation, e.outcome, e.audit_mode, e.error_code) for e in nuevos] == [
        ("guardar_escala_salarial_v256", "FAILED", "SEPARATE_TRANSACTION", "ValueError")]


def test_cargo_faltante_y_redondeo(service, repo, db_conn, audit_store, sueldos):
    rec = _rec(service, repo)
    sin_jtp = {c: v for c, v in _valores().items() if c != "JTP"}
    _, err_c, _, err, _, _, _ = comparar(
        db_conn, audit_store, lambda ns: ns["guardar_escala_salarial_v256"]("2026-11", sin_jtp),
        lambda: sueldos.guardar_escala(rec, {"anio": 2026, "mes": 11, "valores": sin_jtp}))
    assert str(err_c) == "El básico de JTP debe ser mayor a cero." and err.message.endswith(str(err_c))
    raros = _valores(1.0, Titular=1234.565, Asociado=1000.005, Adjunto=3, JTP=99999999999999.99)
    _, err_c, _, err, _, _, st = comparar(
        db_conn, audit_store, lambda ns: ns["guardar_escala_salarial_v256"]("2026-11", raros),
        lambda: sueldos.guardar_escala(rec, {"anio": 2026, "mes": 11, "valores": raros}))
    assert err_c is None and err is None


def test_mes_invalido_en_el_writer(service, repo, db_conn, audit_store, sueldos):
    """El servicio arma ``AAAA-MM`` desde los selectores; el writer conserva su validacion (mismo texto, 0 SQL)."""
    rec = _rec(service, repo)
    scope = sueldos.reader(rec)
    for mes in ("2026-1", "26-06", "", None, "2026-06-01"):
        _, err_c, _, err, nuevos, eventos, _ = comparar(
            db_conn, audit_store, lambda ns: ns["guardar_escala_salarial_v256"](mes, _valores()),
            lambda: sueldos._op(rec, scope, SPEC_GUARDAR_ESCALA, lambda u: E.guardar_escala_salarial_v256(
                u, mes, _valores())))
        assert str(err_c) == "Mes de referencia inválido." and err.message.endswith("Mes de referencia inválido.")
        assert eventos == [] and [e.outcome for e in nuevos] == ["FAILED"]


def test_usuario_actualizacion_nombre_o_email(service, repo, db_conn, audit_store, sueldos):
    """H5: nombre del usuario de la sesion; vacio -> email.  El cliente no puede imponerlo."""
    next(u for u in repo.users if u["id"] == 3)["nombre"] = ""
    rec = _rec(service, repo)
    _, _, _, err, _, _, st = comparar(
        db_conn, audit_store, lambda ns: ns["guardar_escala_salarial_v256"]("2026-10", _valores()),
        lambda: sueldos.guardar_escala(rec, {"anio": 2026, "mes": 10, "valores": _valores(),
                                             "usuario_actualizacion": "hacker", "institucion_id": 2}),
        nombre="")
    assert err is None and sum('"usuario_actualizacion": "info@test.local"' in x for x in st) == 6
    sup = _rec(service, repo, uid=1, inst=1, dep=2)
    _, _, _, err, _, eventos, st = comparar(
        db_conn, audit_store, lambda ns: ns["guardar_escala_salarial_v256"]("2026-10", _valores()),
        lambda: sueldos.guardar_escala(sup, {"anio": 2026, "mes": 10, "valores": _valores()}), dep=2,
        email="super@test.local", nombre="Usuario 1")
    assert err is None and sum('"usuario_actualizacion": "Usuario 1"' in x for x in st) == 6
    assert (eventos[0]["institucion_id"], eventos[0]["departamento_id"], eventos[0]["actor_role"]) == (1, 2, "superadmin")


def test_escala_institucional_otra_institucion_no_se_toca(service, repo, db_conn, audit_store, sueldos):
    """usuario_departamento de la institucion 2 modifica SOLO la escala de su institucion (H11)."""
    rec = _rec(service, repo, uid=4)
    antes_1 = state(db_conn, 1)
    _, _, _, err, _, eventos, _ = comparar(
        db_conn, audit_store, lambda ns: ns["guardar_escala_salarial_v256"]("2026-06", _valores(1.3)),
        lambda: sueldos.guardar_escala(rec, {"anio": 2026, "mes": 6, "valores": _valores(1.3)}), inst=2, dep=5,
        email="uba@test.local", nombre="Usuario 4")
    assert err is None and eventos[0]["institucion_id"] == 2
    assert state(db_conn, 1) == antes_1


def test_superadmin_institucion_sin_departamentos_escribe_su_escala(service, repo, db_conn, audit_store, sueldos):
    """Institucion 5: sin departamentos ni escala.  La escala es institucional: el superadmin puede crearla
    (alcance institution, B10 ALLOW) y el evento B12H queda sin departamento."""
    sup = _rec(service, repo, uid=1, inst=5, dep=None)
    _, err_c, _, err, _, eventos, st = comparar(
        db_conn, audit_store, lambda ns: ns["guardar_escala_salarial_v256"]("2026-10", _valores()),
        lambda: sueldos.guardar_escala(sup, {"anio": 2026, "mes": 10, "valores": _valores()}), inst=5, dep=None,
        email="super@test.local", nombre="Usuario 1")
    assert err_c is None and err is None and (eventos[0]["institucion_id"], eventos[0]["departamento_id"]) == (5, None)
    assert db_conn.execute("SELECT count(*) FROM escalas_salariales_docentes WHERE institucion_id=5").fetchone()[0] == 0


@pytest.mark.parametrize("payload", [
    {"anio": 2026, "mes": 13}, {"anio": 1999, "mes": 6}, {"anio": "2026", "mes": 6}, {"anio": 2026, "mes": True},
    {"anio": 2026, "mes": 6, "valores": {"Titular": -1}}, {"anio": 2026, "mes": 6, "valores": {"Titular": "1"}},
    {"anio": 2026, "mes": 6, "valores": {"Decano": 1}}, {"anio": 2026, "mes": 6, "valores": {"Titular": float("nan")}},
    {"anio": 2026, "mes": 6, "valores": [1, 2]}, {"anio": 2026, "mes": 6, "valores": {"Titular": True}},
])
def test_valores_invalidos_sin_escrituras_ni_eventos(service, repo, db_conn, audit_store, sueldos, payload):
    """Lo que el formulario certificado no puede enviar (``number_input`` min 0, selectores) -> 422 antes de B10."""
    rec = _rec(service, repo)
    antes = state(db_conn, 1)
    with pytest.raises(SueldosError) as e:
        sueldos.guardar_escala(rec, payload)
    assert e.value.status == 422 and state(db_conn, 1) == antes and audit_store.events == []
