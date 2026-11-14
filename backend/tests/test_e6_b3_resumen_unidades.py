"""6A-B3 (R-B3-9): Resumen docente con la MISMA regla de unidades académicas que Disposiciones.

- Fuente común: ``materias.rules.formatear_nombre_escuela`` (Disposiciones la reexporta; es el mismo objeto).
- La copia certificada literal (``analisis.motor.ref`` y el complemento generado) NO se modifica: conserva su
  comportamiento ("Escuela de Facultad de ...") para comparación; el namespace del Resumen usa la fuente común.
- Tablas visibles "Comisiones asignadas al docente" (columna ``escuela``) y "Materias históricas" (``escuelas``): cada
  unidad se presenta con la regla; el dato almacenado no cambia (todo en una transacción que se deshace).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import psycopg
import pytest

from comisiones_support import FIXED_NOW  # noqa: F401
from periodos_support import FIXED_TODAY, audit_store, db_conn, savepoint  # noqa: F401
from saas_support import auth_db  # noqa: F401
from test_e4_02_plantel import superadmin_en
from test_e4_05_resumen import make_resumen

from analisis.motor.ref.domain import materias as ref_mat
from disposiciones import rules as R
from materias import rules as M

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning", "ignore::DeprecationWarning")
BACKEND = Path(__file__).resolve().parents[1]
PROHIBIDO = re.compile(r"(?i)escuela de (facultad|escuela|instituto|departamento)\b")
CASOS = {
    "historico": ("Ciencias Tecnológicas", "Escuela de Ciencias Tecnológicas"),
    "facultad": ("Facultad de Pelotudismo", "Facultad de Pelotudismo"),
    "escuela": ("Escuela de Arquitectura", "Escuela de Arquitectura"),
    "instituto": ("Instituto de Tecnología", "Instituto de Tecnología"),
    "departamento": ("Departamento de Ciencias Básicas", "Departamento de Ciencias Básicas"),
}


def test_fuente_comun_unica_y_certificado_intacto():
    assert R.formatear_nombre_escuela is M.formatear_nombre_escuela
    assert R.es_denominacion_institucional is M.es_denominacion_institucional
    assert "def formatear_nombre_escuela" not in (BACKEND / "disposiciones" / "rules.py").read_text(encoding="utf-8")
    # la referencia certificada conserva su comportamiento (comparación), la app usa la regla nueva
    assert ref_mat.formatear_nombre_escuela("Facultad de Pelotudismo") == "Escuela de Facultad de Pelotudismo"
    assert M.formatear_nombre_escuela("Facultad de Pelotudismo") == "Facultad de Pelotudismo"
    complemento = (BACKEND / "integraciones" / "resumen_motor" / "complemento.py").read_text(encoding="utf-8")
    assert "from analisis.motor.ref.domain.materias import formatear_nombre_escuela" in complemento


@pytest.mark.parametrize("valor, esperado", [
    ("Ciencias Tecnológicas", "Escuela de Ciencias Tecnológicas"), ("Humanidades", "Escuela de Humanidades"),
    ("Facultad de Ingeniería | Humanidades", "Facultad de Ingeniería | Escuela de Humanidades"),
    ("Instituto de Tecnología / Escuela de Salud", "Instituto de Tecnología / Escuela de Salud"),
    ("Posgrado", "Posgrado"), ("", ""), (None, ""), (float("nan"), ""),
])
def test_presentar_varias_unidades(valor, esperado):
    assert M.presentar_unidades_academicas(valor) == esperado


def _cuil_con_comisiones(conn) -> str:
    return conn.execute(
        "SELECT a.cuil FROM asignaciones_docentes_comision a JOIN comisiones co ON co.id=a.comision_id "
        "JOIN docentes d ON d.cuil=a.cuil AND d.institucion_id=1 AND d.departamento_id=1 "
        "JOIN materias m ON m.id=co.materia_id WHERE co.periodo_id=9 AND m.carrera_id IS NOT NULL "
        "AND COALESCE(a.estado,'Activa')='Activa' GROUP BY a.cuil ORDER BY count(*) DESC, a.cuil LIMIT 1").fetchone()[0]


@pytest.mark.parametrize("caso", sorted(CASOS))
def test_resumen_docente_presenta_la_regla(caso, auth_db, audit_store, db_conn):
    valor, esperado = CASOS[caso]
    svc = make_resumen(auth_db, audit_store, db_conn)
    record, _ = superadmin_en(auth_db, db_conn, 1, 1)
    with db_conn.transaction() as tx:
        cuil = _cuil_con_comisiones(db_conn)
        for tabla, col in (("materias", "escuela"), ("carreras", "escuela"), ("comision_materias", "escuela_snapshot")):
            db_conn.execute(f"UPDATE {tabla} SET {col}=%s WHERE coalesce({col}, '') <> ''", [valor])
        r = svc.resumen(record, cuil, 9)
        com = r["secciones"]["comisiones"]["tabla"]
        i = com["columnas"].index("escuela")
        assert com["filas"] and {f[i] for f in com["filas"]} == {esperado}
        hist = r["secciones"]["materias_historicas"]["tabla"]
        j = hist["columnas"].index("escuelas")
        assert hist["filas"] and all(set(f[j].split(" | ")) == {esperado} for f in hist["filas"])
        assert not PROHIBIDO.search(json.dumps(r, ensure_ascii=False, default=str))
        # el namespace del Resumen (complemento literal) presenta con la fuente común
        scope = svc._reader(record)
        assert svc._motor(record, scope, lambda ns: ns["formatear_nombre_escuela"](valor)) == esperado
        # el dato almacenado no se modificó por la presentación
        assert db_conn.execute("SELECT DISTINCT escuela FROM carreras WHERE coalesce(escuela,'')<>''").fetchall() == [(valor,)]
        raise psycopg.Rollback(tx)
