"""Diferenciales de ESCRITURA de Movimientos: misma accion de pantalla, certificado vs NEXT, mismo estado.

Lado certificado: los botones de la pagina (l. 67800-67809 y l. 55628-55639, transcritos) llamando a los writers
certificados (``certified_movimientos``).  Lado NEXT: el servicio con una sesion real del AuthService (superadmin en el
departamento 1).  Entre ambos, ROLLBACK al SAVEPOINT.  Se comparan ``movimientos`` y ``documentos_respaldo_movimientos``
(sin la marca de tiempo de vinculacion), el mensaje y la secuencia de COMMITs por operacion B12H (``commit_seq``,
``mutating_statements``, ``committing_writer``): eliminar = 1 COMMIT con 2 DELETE; masivos = 1 COMMIT.
"""

from __future__ import annotations

import json
import pprint

import psycopg
import pytest

from movimientos import rules as R
from movimientos_support import (  # noqa: F401  (fixtures)
    audit_rows, audit_store, certified_movimientos, db_conn, movimientos, session_for, state,
)

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")

INST, DEP = 1, 1
EMAIL = "super@test.local"


@pytest.fixture
def sup(service, repo):
    rec = session_for(service, repo, 1)[0]
    service.set_context(rec, INST, DEP, False)
    return rec


def comparar(db_conn, audit_store, certificado, siguiente, preparar=None):
    with db_conn.transaction() as outer:
        extra = preparar() if preparar is not None else None
        ns = certified_movimientos(db_conn, INST, DEP, rol="superadmin", email=EMAIL)
        with db_conn.transaction() as tx:
            res_c = certificado(ns, extra)
            st_c = state(db_conn, INST)
            ops_c = list(ns["_frames"].ops)
            raise psycopg.Rollback(tx)
        with db_conn.transaction() as tx:
            n = len(audit_store.events)
            res_n = siguiente(extra)
            st_n = state(db_conn, INST)
            eventos = audit_rows(db_conn)
            nuevos = audit_store.events[n:]
            raise psycopg.Rollback(tx)
        raise psycopg.Rollback(outer)
    for tabla in st_c:
        a, b = st_c[tabla], st_n[tabla]
        assert a == b, (f"{tabla}: certificado {len(a)} / NEXT {len(b)}\nsolo cert: "
                        f"{pprint.pformat([json.loads(x) for x in a if x not in b][:3])}\nsolo NEXT: "
                        f"{pprint.pformat([json.loads(x) for x in b if x not in a][:3])}")
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
    assert res_c == res_n
    return {"eventos": eventos, "nuevos": nuevos, "ops": ops_n, "st_n": st_n, "st_c": st_c}


# ------------------------------------------------------------------------------------------ transcripcion de pantalla
def pagina_eliminar(ns, id_mov, confirmar=True):
    if confirmar:
        ns["eliminar_movimiento"](id_mov)
        return "Movimiento eliminado."
    return "Primero confirmá la eliminación."


def pagina_vincular(ns, ids, nuevo):
    cantidad = ns["vincular_acto_movimientos_masivo_v267"](ids, int(nuevo))
    return f"Acto administrativo vinculado a {cantidad} movimiento/s."


def pagina_quitar(ns, ids):
    cantidad = ns["desvincular_acto_movimientos_masivo_v267"](ids)
    return f"Se quitaron {cantidad} vínculo/s de movimiento."


def _filas(movimientos, sup, ids):
    filas = {f["id"]: f for f in movimientos.listado(sup, {"periodo": R.TODOS})["filas"]}
    return [{"id": i, "huella": filas[i]["huella"]} for i in ids]


def _doc(conn, numero):
    return conn.execute(
        "INSERT INTO documentos_respaldo (institucion_id,departamento_id,tipo_documento,categoria,numero,fecha,"
        "dependencia_nombre,archivo_nombre,archivo_mime,archivo_pdf,archivo_bytes) VALUES (1,1,'Resolución','Otro',%s,"
        "'2026-10-01','ZZNEXT Rectorado','','','',0) RETURNING id", [numero]).fetchone()[0]


def _link(conn, doc, mov):
    conn.execute("INSERT INTO documentos_respaldo_movimientos (institucion_id,departamento_id,documento_id,movimiento_id,"
                 "usuario_vinculacion) VALUES (1,1,%s,%s,'zz')", [doc, mov])


def _movs(conn, condicion, n):
    return [r[0] for r in conn.execute(f"SELECT id FROM movimientos WHERE institucion_id=1 AND departamento_id=1 AND "
                                       f"{condicion} ORDER BY id LIMIT {int(n)}")]


def _eventos_ok(r, operation, entity_id, mutating, action):
    ev = [e for e in r["eventos"] if e["operation"] == operation]
    assert [(e["outcome"], e["audit_mode"], e["action"], e["entity_id"], e["metadata"]["commit_seq"],
             e["metadata"]["mutating_statements"]) for e in ev] == [
        ("SUCCESS", "IN_TRANSACTION", action, entity_id, 1, mutating)]


# ------------------------------------------------------------------------------------------ eliminar (1 COMMIT, 2 DELETE)
def test_eliminar_con_vinculo_al_acto(db_conn, audit_store, movimientos, sup):
    # Mantenimiento de tests (cierre de Etapa 4): el total se mide en la base persistente antes de operar (antes 7071 fijo).
    antes = db_conn.execute("SELECT count(*) FROM movimientos WHERE institucion_id=%s", [INST]).fetchone()[0]
    vinculos_antes = db_conn.execute("SELECT count(*) FROM documentos_respaldo_movimientos WHERE institucion_id=%s",
                                     [INST]).fetchone()[0]
    eliminado = {}

    def preparar():
        mov = _movs(db_conn, "tipo_movimiento='Alta de designación'", 1)[0]
        _link(db_conn, _doc(db_conn, "ZZNEXT-1"), mov)
        eliminado["id"] = mov
        return mov
    r = comparar(db_conn, audit_store, lambda ns, mov: pagina_eliminar(ns, mov),
                 lambda mov: movimientos.eliminar(sup, {"id": mov, "huella": _filas(movimientos, sup, [mov])[0]["huella"],
                                                        "confirmar": True})["mensaje"], preparar)
    _eventos_ok(r, "eliminar_movimiento", None, 2, "movimientos.delete")  # D-AL16: entity_id NULL
    assert r["eventos"][0]["entity_type"] == "movimiento"
    assert r["eventos"][0]["metadata"]["committing_writer"] == "eliminar_movimiento"
    # el vinculo sintetico se agrego en ``preparar`` y el DELETE certificado lo quita: quedan los vinculos reales previos
    assert len(r["st_n"]["movimientos"]) == antes - 1
    assert len(r["st_n"]["documentos_respaldo_movimientos"]) == vinculos_antes
    assert all(json.loads(x)["movimiento_id"] != eliminado["id"] for x in r["st_n"]["documentos_respaldo_movimientos"])
    assert all(json.loads(x)["id"] != eliminado["id"] for x in r["st_n"]["movimientos"])


@pytest.mark.parametrize("condicion", ["tipo_movimiento='Generación de disposición'", "source_db IS NOT NULL",
                                       "tipo_movimiento='Finalización automática por cierre de período'",
                                       "COALESCE(cuil,'')=''"])
def test_eliminar_sin_restriccion_por_tipo(db_conn, audit_store, movimientos, sup, condicion):
    """D-AL15: cualquier tipo (disposicion, legacy, automatico de periodo, sin CUIL); sin vinculo: el DELETE del vinculo
    afecta 0 filas y cuenta igual como sentencia mutante (2)."""
    mov = _movs(db_conn, condicion, 1)[0]
    r = comparar(db_conn, audit_store, lambda ns, _: pagina_eliminar(ns, mov),
                 lambda _: movimientos.eliminar(sup, {"id": mov, "huella": _filas(movimientos, sup, [mov])[0]["huella"],
                                                      "confirmar": True})["mensaje"])
    _eventos_ok(r, "eliminar_movimiento", None, 2, "movimientos.delete")


def test_eliminar_sin_confirmar_no_escribe(db_conn, audit_store, movimientos, sup):
    from movimientos.service import MovimientosError
    mov = _movs(db_conn, "TRUE", 1)[0]
    n = len(audit_store.events)
    with pytest.raises(MovimientosError) as exc:
        movimientos.eliminar(sup, {"id": mov, "huella": "x", "confirmar": False})
    assert exc.value.message == pagina_eliminar(None, mov, confirmar=False)
    assert audit_store.events[n:] == [] and audit_rows(db_conn) == []


# ------------------------------------------------------------------------------------------ vinculos masivos (1 COMMIT)
def test_vincular_masivo(db_conn, audit_store, movimientos, sup):
    def preparar():
        return {"doc": _doc(db_conn, "ZZNEXT-2"), "ids": _movs(db_conn, "tipo_movimiento IN ('Alta de designación',"
                                                                       "'Cambio de cargo','Baja de designación')", 3)}
    r = comparar(db_conn, audit_store, lambda ns, x: pagina_vincular(ns, x["ids"], x["doc"]),
                 lambda x: movimientos.vincular(sup, {"documento_id": x["doc"],
                                                      "seleccion": _filas(movimientos, sup, x["ids"])}, False)["mensaje"],
                 preparar)
    assert len(r["st_n"]["documentos_respaldo_movimientos"]) == 3
    ev = r["eventos"][0]
    assert (ev["operation"], ev["action"], ev["entity_type"], ev["metadata"]["mutating_statements"]) == (
        "vincular_acto_movimientos_masivo_v267", "documentos.write", "acto_administrativo", 3)
    assert ev["entity_id"] is not None and ev["metadata"]["entity_param"] == "documento_id"


def test_cambiar_acto(db_conn, audit_store, movimientos, sup):
    def preparar():
        a, b = _doc(db_conn, "ZZNEXT-A"), _doc(db_conn, "ZZNEXT-B")
        ids = _movs(db_conn, "tipo_movimiento='Alta de designación'", 2)
        for i in ids:
            _link(db_conn, a, i)
        return {"doc": b, "ids": ids}
    r = comparar(db_conn, audit_store, lambda ns, x: pagina_vincular(ns, x["ids"], x["doc"]),
                 lambda x: movimientos.vincular(sup, {"documento_id": x["doc"],
                                                      "seleccion": _filas(movimientos, sup, x["ids"])}, False)["mensaje"],
                 preparar)
    assert {json.loads(x)["documento_id"] for x in r["st_n"]["documentos_respaldo_movimientos"]} == \
        {json.loads(x)["documento_id"] for x in r["st_c"]["documentos_respaldo_movimientos"]}
    assert len({json.loads(x)["documento_id"] for x in r["st_n"]["documentos_respaldo_movimientos"]}) == 1


def test_quitar_vinculo_masivo(db_conn, audit_store, movimientos, sup):
    def preparar():
        a = _doc(db_conn, "ZZNEXT-Q")
        ids = _movs(db_conn, "tipo_movimiento='Alta de designación'", 3)
        for i in ids[:2]:
            _link(db_conn, a, i)
        return ids
    r = comparar(db_conn, audit_store, lambda ns, ids: pagina_quitar(ns, ids),
                 lambda ids: movimientos.vincular(sup, {"seleccion": _filas(movimientos, sup, ids)}, True)["mensaje"],
                 preparar)
    _eventos_ok(r, "desvincular_acto_movimientos_masivo_v267", None, 1, "documentos.delete")
    assert r["st_n"]["documentos_respaldo_movimientos"] == []


def test_quitar_vinculo_sin_vinculos_es_mutante(db_conn, audit_store, movimientos, sup):
    """DELETE de 0 filas: SUCCESS por la deteccion textual certificada; "Se quitaron 0 vínculo/s de movimiento."."""
    ids = _movs(db_conn, "tipo_movimiento='Cambio de cargo'", 2)
    r = comparar(db_conn, audit_store, lambda ns, _: pagina_quitar(ns, ids),
                 lambda _: movimientos.vincular(sup, {"seleccion": _filas(movimientos, sup, ids)}, True)["mensaje"])
    _eventos_ok(r, "desvincular_acto_movimientos_masivo_v267", None, 1, "documentos.delete")
