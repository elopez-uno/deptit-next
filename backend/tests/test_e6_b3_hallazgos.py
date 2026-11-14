"""Etapa 6A-B3: regresiones de los hallazgos del piloto local (docs/ETAPA6_6AB3_LOCAL_PILOT.md, hallazgos).

H-B3-1  La clave del limite por origen (6A-B1) medía 72 caracteres y ``auth_login_throttle`` exige 70
        (``CHECK length(subject_key) = 70``): con un proxy confiable (preproduccion) cada login fallido terminaba en
        CheckViolation -> 503.  Los tests de B1 usaban un repositorio en memoria; aca se lee la restriccion REAL del
        catalogo de deptit_next_dev (solo lectura) y se escribe de verdad en una transaccion revertida.
H-B3-4  ~15.000 ``UserWarning`` de pandas ("pandas only supports SQLAlchemy connectable") por las lecturas del motor
        certificado de Analisis llenaban stderr: filtro acotado a ese mensaje y a ``analisis.motor``."""

from __future__ import annotations

import re
import warnings

import psycopg

import settings as S
from auth import core
from auth.repository import THROTTLE_TABLE


def _longitud_exigida(conn) -> int:
    defs = [r[0] for r in conn.execute(
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid = %s::regclass AND contype = 'c'",
        (THROTTLE_TABLE,)).fetchall()]
    m = [re.search(r"length\(subject_key\) = (\d+)", d) for d in defs]
    largos = [int(x.group(1)) for x in m if x]
    assert len(largos) == 1, defs
    return largos[0]


def test_claves_de_throttle_cumplen_la_restriccion_real():
    with psycopg.connect(S.get().db.conninfo) as conn:
        conn.read_only = True
        n = _longitud_exigida(conn)
        conn.rollback()
    for ip in ("127.0.0.1", "::1", "203.0.113.77", "2001:db8::1"):
        assert len(core.ip_subject_key(ip)) == n
        assert ip not in core.ip_subject_key(ip)
    assert len(core.subject_key("alguien@universidad.edu.ar")) == n
    assert core.IP_SUBJECT_PREFIX != core.SUBJECT_PREFIX and len(core.IP_SUBJECT_PREFIX) == len(core.SUBJECT_PREFIX)
    # espacios de claves disjuntos: una clave de cuenta nunca empieza con el prefijo de IP ni al reves
    assert not core.subject_key("x@y.z").startswith(core.IP_SUBJECT_PREFIX)
    assert not core.ip_subject_key("127.0.0.1").startswith(core.SUBJECT_PREFIX)


def test_insert_real_de_la_clave_ip_en_transaccion_revertida():
    """El INSERT que hace el limite por origen, contra la tabla real (CHECK incluido); ROLLBACK: dev no cambia."""
    clave = core.ip_subject_key("203.0.113.77")
    with psycopg.connect(S.get().db.conninfo, autocommit=False) as conn:
        antes = conn.execute(f"SELECT count(*) FROM {THROTTLE_TABLE}").fetchone()[0]
        conn.execute(f"INSERT INTO {THROTTLE_TABLE} (subject_key, failures, window_started_epoch, locked_until_epoch, "
                     "updated_epoch) VALUES (%s, 1, 0, NULL, 0)", (clave,))
        assert conn.execute(f"SELECT count(*) FROM {THROTTLE_TABLE} WHERE subject_key = %s",
                            (clave,)).fetchone()[0] == 1
        conn.rollback()
        assert conn.execute(f"SELECT count(*) FROM {THROTTLE_TABLE}").fetchone()[0] == antes
        conn.rollback()


MSG_PANDAS = ("pandas only supports SQLAlchemy connectable (engine/connection) or database string URI or sqlite3 "
              "DBAPI2 connection. Other DBAPI2 objects are not tested. Please consider using SQLAlchemy.")


def _registrados(modulo: str, mensaje: str = MSG_PANDAS, categoria=UserWarning) -> int:
    import analisis.motor  # noqa: F401  (instala el filtro)
    with warnings.catch_warnings(record=True) as w:  # conserva los filtros vigentes; solo registra
        warnings.warn_explicit(mensaje, categoria, "x.py", 1, module=modulo)
    return len(w)


def test_warning_de_pandas_del_motor_silenciado_y_solo_ese():
    assert _registrados("analisis.motor.certificado") == 0
    assert _registrados("analisis.motor.ref.extracted_batch03.readonly_queries") == 0
    # el mismo mensaje desde OTRO paquete se sigue viendo; y cualquier otro warning del motor tambien
    assert _registrados("docentes.service") == 1
    assert _registrados("analisis.motor.certificado", mensaje="otro aviso del motor") == 1


LECTURA_REAL = r'''
import datetime as dt, psycopg, main, settings as S
from analisis import pagina as P
from analisis.motor import entorno
with psycopg.connect(S.get().db.conninfo, autocommit=False) as conn:
    conn.execute("SET TRANSACTION READ ONLY")
    ns = entorno.construir(conn, 1, 3, usuario={"email": "t@x.edu", "rol": "superadmin", "departamento_nombre": ""},
                           hoy=lambda: dt.date(2026, 11, 4), ahora=lambda: dt.datetime(2026, 11, 4, 12, 0))
    per = P.periodos(ns)
    pid = ns["get_periodo_abierto"]()
    ns["get_metricas_analisis_periodo"](int(pid["id"]) if isinstance(pid, dict) else int(pid))
    conn.rollback()
print("LECTURA_OK")
'''


def test_lectura_real_del_motor_sin_warning_de_pandas():
    """Como en produccion: interprete NUEVO que importa ``main`` (igual que serve.py) y lee con el motor de Analisis
    sobre deptit_next_dev (READ ONLY).  stderr no contiene el warning de pandas (antes: uno por lectura).  Subproceso:
    pytest restaura los filtros de warnings al terminar cada test, y el filtro se instala una vez, al importar."""
    import subprocess
    import sys
    from pathlib import Path
    p = subprocess.run([sys.executable, "-B", "-c", LECTURA_REAL], cwd=Path(__file__).resolve().parents[1],
                       capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=300)
    assert p.returncode == 0 and "LECTURA_OK" in p.stdout, p.stderr[-1500:]
    assert "pandas only supports SQLAlchemy" not in p.stderr, p.stderr[-800:]
