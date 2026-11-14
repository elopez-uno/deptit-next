"""6A-B3 (aceptacion humana, ronda 2): el acto de la DESIGNACION original y el acto propio de cada MODIFICACION
(movimiento) son vinculos distintos que coexisten:

    Designacion A -> R1   (``documentos_respaldo_designaciones``, una fila por designacion)
    Modificacion 1 de A -> movimiento M1 -> R2   (``documentos_respaldo_movimientos``, una fila por movimiento)
    Modificacion 2 de A -> movimiento M2 -> R3

Ninguno sobrescribe a otro.  El modelo certificado (v266/v267) ya funciona asi: estos tests lo DEMUESTRAN sin cambiar
codigo de produccion.  Tambien fijan el comportamiento actual de la Disposicion (cita el acto de la designacion, R1),
que es una regla de redaccion que NO se cambia aca (decision del owner).

Datos sinteticos ``ZZNEXT`` dentro de la transaccion del test (ROLLBACK)."""

from __future__ import annotations

import pytest

from designaciones import rules
from designaciones_support import audit_store, db_conn, designaciones, session_for  # noqa: F401
from disposiciones.lecturas import Lecturas as DLecturas
from disposiciones.repository import DisposicionesRepository
from periodos_support import FIXED_TODAY

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")
ABIERTO = 9


@pytest.fixture
def rec(service, repo):
    return session_for(service, repo, 3)[0]


def _doc(db_conn, numero):
    return db_conn.execute(
        "INSERT INTO documentos_respaldo (institucion_id,departamento_id,tipo_documento,categoria,numero,fecha,"
        "archivo_nombre,archivo_pdf,archivo_bytes,dependencia_nombre) VALUES (1,1,'Resolución','Designación docente',%s,"
        "'2026-08-01','',''::bytea,0,"
        "'Rectorado') "
        "RETURNING id", [numero]).fetchone()[0]


def _fila(svc, rec, did):
    return next(f for f in svc.periodo(rec, ABIERTO)["designaciones"] if f["id"] == did)


def _acto_designacion(db_conn, did):
    r = db_conn.execute("SELECT documento_id FROM documentos_respaldo_designaciones WHERE designacion_id=%s",
                        [did]).fetchone()
    return None if r is None else r[0]


def _ultimo_movimiento(db_conn, cuil):
    return db_conn.execute("SELECT id, tipo_movimiento FROM movimientos WHERE cuil=%s AND institucion_id=1 AND "
                           "departamento_id=1 ORDER BY id DESC LIMIT 1", [cuil]).fetchone()


def _acto_movimiento(db_conn, mid):
    r = db_conn.execute("SELECT documento_id FROM documentos_respaldo_movimientos WHERE movimiento_id=%s",
                        [mid]).fetchone()
    return None if r is None else r[0]


def test_alta_y_dos_modificaciones_con_actos_distintos_coexisten(designaciones, rec, db_conn):
    r1, r2, r3 = (_doc(db_conn, n) for n in ("ZZNEXT-R1/2026", "ZZNEXT-R2/2026", "ZZNEXT-R3/2026"))
    cuil = db_conn.execute("SELECT cuil FROM docentes WHERE institucion_id=1 AND departamento_id=1 ORDER BY id "
                           "LIMIT 1").fetchone()[0]
    alta = designaciones.alta(rec, {
        "cuil": cuil, "cargo": "JTP", "dedicacion": "Simple", "tipo_designacion": "Interino", "ad_honorem": "No",
        "fecha_desde": "2026-08-03", "fecha_hasta": "2026-12-31", "estado": "Activa", "observaciones": "ZZNEXT",
        "acto": {"modo": "existente", "documento_id": r1}, "abierto_huella": designaciones.overview(rec)["abierto_huella"],
        "confirmar_duplicada": True})
    did = alta["id"]
    assert _acto_designacion(db_conn, did) == r1  # designacion nueva + acto existente -> vinculo real
    m0, tipo0 = _ultimo_movimiento(db_conn, cuil)
    assert tipo0 == "Alta de designación" and _acto_movimiento(db_conn, m0) == r1

    # Modificacion 1 (cambio de cargo) con SU acto R2 -> movimiento M1; la designacion conserva R1
    f = _fila(designaciones, rec, did)
    designaciones.modificar(rec, {"id": did, "huella": f["huella"], "tipo_cambio": "Cambio de cargo", "cargo": "Adjunto",
                                  "observaciones": "ZZNEXT mod 1", "acto": {"modo": "existente", "documento_id": r2}})
    m1, tipo1 = _ultimo_movimiento(db_conn, cuil)
    assert tipo1 == "Cambio de cargo" and m1 != m0
    assert _acto_movimiento(db_conn, m1) == r2
    assert _acto_designacion(db_conn, did) == r1

    # Modificacion 2 (aumento de dedicacion) con OTRO acto R3 -> movimiento M2
    f = _fila(designaciones, rec, did)
    assert f["cargo"] == "Adjunto" and f["acto_documento_id"] == r1
    mayor = next(d for d in rules.DEDICACIONES if rules.HORAS_POR_DEDICACION[d] > rules.HORAS_POR_DEDICACION["Simple"])
    designaciones.modificar(rec, {"id": did, "huella": f["huella"], "tipo_cambio": "Aumento de dedicación",
                                  "dedicacion": mayor, "observaciones": "ZZNEXT mod 2",
                                  "acto": {"modo": "existente", "documento_id": r3}})
    m2, tipo2 = _ultimo_movimiento(db_conn, cuil)
    assert tipo2 == "Aumento de dedicación" and m2 not in (m0, m1)
    # R1, R2 y R3 intactos y sin confundirse
    assert _acto_designacion(db_conn, did) == r1
    assert (_acto_movimiento(db_conn, m0), _acto_movimiento(db_conn, m1), _acto_movimiento(db_conn, m2)) == (r1, r2, r3)
    assert db_conn.execute("SELECT count(*) FROM documentos_respaldo_designaciones WHERE designacion_id=%s",
                           [did]).fetchone()[0] == 1

    # Comportamiento ACTUAL de la Disposicion (no se cambia: regla de redaccion a decidir por el owner): cita el acto
    # vinculado a la designacion (R1), no el de la modificacion.
    datos = DLecturas(DisposicionesRepository(db_conn, 1, 1), FIXED_TODAY, "").datos_designaciones(cuil, ABIERTO)
    fila = next((x for x in datos if x["designacion_id"] == did), None)
    if fila is not None:  # la designacion entra al padron de la Disposicion (Activa, Interino)
        assert fila["resolucion"] == "ZZNEXT-R1/2026"


def test_modificacion_sin_acto_no_toca_el_acto_de_la_designacion(designaciones, rec, db_conn):
    r1 = _doc(db_conn, "ZZNEXT-R1b/2026")
    cuil = db_conn.execute("SELECT cuil FROM docentes WHERE institucion_id=1 AND departamento_id=1 ORDER BY id "
                           "LIMIT 1 OFFSET 1").fetchone()[0]
    did = designaciones.alta(rec, {
        "cuil": cuil, "cargo": "JTP", "dedicacion": "Simple", "tipo_designacion": "Interino", "ad_honorem": "No",
        "fecha_desde": "2026-08-04", "fecha_hasta": "2026-12-31", "estado": "Activa", "observaciones": "ZZNEXT",
        "acto": {"modo": "existente", "documento_id": r1}, "abierto_huella": designaciones.overview(rec)["abierto_huella"],
        "confirmar_duplicada": True})["id"]
    f = _fila(designaciones, rec, did)
    designaciones.modificar(rec, {"id": did, "huella": f["huella"], "tipo_cambio": "Cambio de cargo", "cargo": "Titular",
                                  "observaciones": "ZZNEXT", "acto": {"modo": "pendiente"}})
    m1, _ = _ultimo_movimiento(db_conn, cuil)
    assert _acto_movimiento(db_conn, m1) is None
    assert _acto_designacion(db_conn, did) == r1
