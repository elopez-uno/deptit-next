"""6A-B3: el "Mensaje para consultar la designación" (Docentes → Resumen docente) nombra la institución ACTIVA.

El complemento literal del certificado (``institucion_actual_nombre``) usa primero la institución de PERTENENCIA del
usuario (``current_user()``) y, si no, un valor fijo "Universidad Nacional del Oeste". En NEXT el namespace del
request usa el nombre de la institución del contexto activo; el complemento sigue literal.
"""
from __future__ import annotations

from pathlib import Path

import psycopg
import pytest

from comisiones_support import FIXED_NOW  # noqa: F401
from periodos_support import FIXED_TODAY, audit_store, db_conn, savepoint  # noqa: F401
from saas_support import auth_db  # noqa: F401
from test_e4_02_plantel import superadmin_en
from test_e4_05_resumen import candidatos, make_resumen

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning", "ignore::DeprecationWarning")
BACKEND = Path(__file__).resolve().parents[1]
UNO = "Universidad Nacional del Oeste"


def _nombre_en_mensaje(svc, record) -> str:
    return svc._motor(record, svc._reader(record), lambda ns: ns["institucion_actual_nombre"](), mensaje=True)


def test_complemento_certificado_sigue_literal():
    texto = (BACKEND / "integraciones" / "resumen_motor" / "complemento_mensaje.py").read_text(encoding="utf-8")
    assert f'return "{UNO}"' in texto  # el certificado no se toca; la corrección está en el namespace del request


@pytest.mark.parametrize("inst, dep", [(1, 1), (2, 5)])
def test_toma_la_institucion_activa_y_no_la_de_pertenencia(inst, dep, auth_db, audit_store, db_conn):
    svc = make_resumen(auth_db, audit_store, db_conn)
    esperado = db_conn.execute("SELECT nombre FROM instituciones WHERE id=%s", [inst]).fetchone()[0]
    record, _ = superadmin_en(auth_db, db_conn, inst, dep)
    assert _nombre_en_mensaje(svc, record) == esperado
    if inst != 1:
        assert esperado != UNO


def test_institucion_renombrada_universidad_de_prueba(auth_db, audit_store, db_conn):
    """Con otro nombre institucional (p. ej. "Universidad de Prueba") el mensaje usa ese nombre, no uno fijo."""
    svc = make_resumen(auth_db, audit_store, db_conn)
    with db_conn.transaction() as tx:
        db_conn.execute("UPDATE instituciones SET nombre='Universidad de Prueba' WHERE id=2")
        record, _ = superadmin_en(auth_db, db_conn, 2, 5)
        assert _nombre_en_mensaje(svc, record) == "Universidad de Prueba"
        raise psycopg.Rollback(tx)


def test_mensaje_completo_en_uno(auth_db, audit_store, db_conn):
    svc = make_resumen(auth_db, audit_store, db_conn)
    record, _ = superadmin_en(auth_db, db_conn, 1, 1)
    cuil = next(iter(candidatos(db_conn, 1, 1).values()))
    pid = db_conn.execute("SELECT id FROM periodos WHERE institucion_id=1 AND departamento_id=1 AND estado='Abierto'"
                          ).fetchone()[0]
    cuerpo = svc.mensaje(record, cuil, pid)["cuerpo"]
    assert f" de la {UNO}." in cuerpo
