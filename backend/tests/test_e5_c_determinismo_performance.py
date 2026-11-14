"""Etapa 5 / Tanda C — determinismo, huellas y performance (READ ONLY / ROLLBACK).

- C1 ``detalle_designaciones`` del Plantel (D-AO6): el orden era el de llegada de las filas y cambiaba con una edicion
  comun (UPDATE sin cambio de valores: 29 de 44 docentes con 2+ designaciones, ``c1_orden_tras_edicion.txt``).  Ahora
  ``STRING_AGG ... ORDER BY d.id``: orden de alta, invariante ante ediciones.  El plantel historico (filas de
  ``get_designaciones``) desempata por ``d.id``.
- C2 huella de contenido canonica (``tools_snapshot_contenido.py``): estable, detecta cambios de valor y del PDF, y no
  cambia por el movimiento fisico de las filas.
- C3 ``cargo_prioritario`` calcula solo la entrada del CUIL pedido: identica al mapa completo para TODO CUIL.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from periodos_support import db_conn  # noqa: F401

BACKEND = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")  # pandas read_sql con DBAPI (motor certificado)


def _abiertos(conn):
    return conn.execute("SELECT institucion_id, departamento_id, id FROM periodos WHERE estado = 'Abierto' AND "
                        "EXISTS (SELECT 1 FROM designaciones d WHERE d.periodo_id = periodos.id) ORDER BY 2").fetchall()


# ------------------------------------------------------------------------------------------ C1
def _detalles(conn, inst, dep, pid) -> dict:
    from comisiones import plantel as CP
    return {f[0]: f[-1] for f in conn.execute(CP.PLANTEL_BASE_SQL, [inst, dep, pid, inst, dep]).fetchall()}


def test_c1_detalle_designaciones_en_orden_de_alta(db_conn):
    revisados = 0
    for inst, dep, pid in _abiertos(db_conn):
        for cuil, detalle in _detalles(db_conn, inst, dep, pid).items():
            if not detalle or " | " not in detalle:
                continue
            cargos = [r[0] for r in db_conn.execute(
                "SELECT cargo FROM designaciones WHERE institucion_id = %s AND departamento_id = %s AND periodo_id = %s "
                "AND cuil = %s ORDER BY id", [inst, dep, pid, cuil])]
            assert [p.split(" - ")[0] for p in detalle.split(" | ")] == cargos
            revisados += 1
    assert revisados >= 30


def test_c1_detalle_invariante_ante_una_edicion(db_conn):
    """Lo que antes cambiaba el orden visible (nueva version fisica de la fila) ya no lo cambia."""
    cambiados = multi = 0
    for inst, dep, pid in _abiertos(db_conn):
        antes = _detalles(db_conn, inst, dep, pid)
        claves = [k for k, v in antes.items() if v and " | " in v]
        for cuil in claves:
            db_conn.execute("UPDATE designaciones SET observaciones = observaciones WHERE id = (SELECT min(id) FROM "
                            "designaciones WHERE institucion_id = %s AND departamento_id = %s AND periodo_id = %s AND "
                            "cuil = %s)", [inst, dep, pid, cuil])
        despues = _detalles(db_conn, inst, dep, pid)
        cambiados += sum(1 for k in claves if antes[k] != despues[k])
        multi += len(claves)
    assert multi >= 30 and cambiados == 0


def test_c1_designaciones_del_plantel_historico_desempatan_por_id(db_conn):
    from comisiones.repository import ComisionesRepository
    for inst, dep, pid in _abiertos(db_conn):
        filas = ComisionesRepository(db_conn, inst, dep).designaciones(pid)
        por_docente: dict = {}
        for f in filas:
            por_docente.setdefault(f["cuil"], []).append(int(f["id"]))
        assert all(ids == sorted(ids) for ids in por_docente.values())


# ------------------------------------------------------------------------------------------ C2
def test_c2_huella_canonica_estable_y_sensible(db_conn):
    sys.path.insert(0, str(BACKEND))
    import tools_snapshot_contenido as T
    a, b = T.huella(db_conn), T.huella(db_conn)
    assert a == b and len(a["tables"]) == 42
    db_conn.execute("UPDATE designaciones SET observaciones = observaciones WHERE id = (SELECT min(id) FROM designaciones)")
    assert T.huella(db_conn)["tables"]["designaciones"] == a["tables"]["designaciones"]  # movimiento fisico: igual
    db_conn.execute("UPDATE designaciones SET horas = horas + 1 WHERE id = (SELECT min(id) FROM designaciones)")
    assert T.huella(db_conn)["tables"]["designaciones"] != a["tables"]["designaciones"]
    if db_conn.execute("SELECT count(*) FROM documentos_respaldo WHERE archivo_pdf IS NOT NULL").fetchone()[0]:
        db_conn.execute("UPDATE documentos_respaldo SET archivo_pdf = archivo_pdf || decode('00', 'hex') WHERE id = "
                        "(SELECT min(id) FROM documentos_respaldo WHERE archivo_pdf IS NOT NULL)")
        assert T.huella(db_conn)["tables"]["documentos_respaldo"] != a["tables"]["documentos_respaldo"]
    import inspect
    codigo = inspect.getsource(T.huella)
    assert "md5(" in codigo and "::text)" not in codigo.replace('"::text', "")  # sin md5(fila::text)


# ------------------------------------------------------------------------------------------ C3
@pytest.mark.parametrize("dep", [1, 2, 3, 4, 9])
def test_c3_cargo_prioritario_por_cuil_igual_al_mapa_completo(db_conn, dep):
    from designaciones import escrituras as E
    from designaciones import rules
    from designaciones.repository import DesignacionesRepository
    repo = DesignacionesRepository(db_conn, 1, dep)
    pid = db_conn.execute("SELECT id FROM periodos WHERE institucion_id = 1 AND departamento_id = %s ORDER BY anio DESC, "
                          "semestre DESC, id DESC LIMIT 1", [dep]).fetchone()[0]
    completo = E.mapa_cargos_prioritarios(repo, pid, dep)
    cuiles = {r[0] for r in db_conn.execute(
        "SELECT cuil FROM docentes WHERE institucion_id = 1 AND departamento_id = %s UNION SELECT cuil FROM "
        "designaciones WHERE institucion_id = 1", [dep])} | {"20-99119911-9"}

    class _U:
        def read(self, fn):
            return fn(repo)

    for cuil in cuiles:
        esperado = dict(completo.get(rules.clave_cuil(cuil)) or {"cargo": ""})
        assert E.cargo_prioritario(_U(), cuil, pid, dep) == esperado, cuil
    assert len(cuiles) >= 50
