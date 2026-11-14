"""Diferenciales de ESCRITURA de Actividades Especiales: misma operacion de pantalla, certificado vs NEXT, desde el mismo
estado.

Lado certificado: la secuencia de la pagina (entry l. 66418-66603, transcrita) llamando a los writers certificados
(``certified_actividades``).  Lado NEXT: el servicio con una sesion real del AuthService (FakeRepo).  Entre ambos,
ROLLBACK al SAVEPOINT.  Se comparan las tablas que tocan los writers (actividades, participaciones y ``movimientos``,
que NO debe cambiar; ids nuevos normalizados) y la secuencia de COMMITs por operacion B12H."""

from __future__ import annotations

import json
import pprint

import psycopg
import pytest

from actividades_especiales.service import ActividadesError
from actividades_support import (  # noqa: F401  (fixtures)
    FIXED_TODAY, actividades, audit_rows, audit_store, baseline, certified_actividades, db_conn, session_for, state,
)

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")

INST = 1
USERS = {1: 3, 2: 6}  # departamento -> usuario_departamento del FakeRepo


def _record(service, repo, dep=1, superadmin=False):
    if not superadmin:
        return session_for(service, repo, USERS[dep])[0]
    sup = session_for(service, repo, 1)[0]
    service.set_context(sup, INST, dep, False)
    return sup


def _correr(fn):
    try:
        return fn(), None
    except psycopg.Error:
        raise
    except Exception as exc:
        if isinstance(exc.__context__, psycopg.Error) or isinstance(exc.__cause__, psycopg.Error):
            raise
        return None, exc


def comparar(db_conn, audit_store, certificado, siguiente, dep=1, rol="usuario_departamento", preparar=None):
    if preparar is not None:
        preparar()
    baseline(db_conn)
    ns = certified_actividades(db_conn, INST, dep, rol=rol)
    with db_conn.transaction() as tx:
        res_c, err_c = _correr(lambda: certificado(ns))
        st_c = state(db_conn, INST)
        ops_c = list(ns["_frames"].ops)
        raise psycopg.Rollback(tx)
    with db_conn.transaction() as tx:
        n = len(audit_store.events)
        res_n, err_n = _correr(siguiente)
        st_n = state(db_conn, INST)
        eventos = audit_rows(db_conn)
        nuevos = audit_store.events[n:]
        raise psycopg.Rollback(tx)
    for tabla in st_c:
        if st_c[tabla] != st_n[tabla]:
            a, b = st_c[tabla], st_n[tabla]
            raise AssertionError(f"{tabla}: certificado {len(a)} / NEXT {len(b)}\nsolo cert: "
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
    con_commits = [o for o in ops_c if o["commits"]]
    assert con_commits == ops_n, f"cert:\n{pprint.pformat(ops_c)}\nNEXT:\n{pprint.pformat(ops_n)}"
    return res_c, err_c, res_n, err_n, nuevos, eventos


def _per(db_conn, dep, nombre):
    return db_conn.execute("SELECT id FROM periodos WHERE institucion_id=1 AND departamento_id=%s AND nombre=%s",
                           [dep, nombre]).fetchone()[0]


def _fila(filas, aid):
    return next(f for f in filas if f["id"] == aid)


# ------------------------------------------------------------------------------------------ Pestaña 2: nueva actividad
@pytest.mark.parametrize("periodo", ["2026-2", "2026-1"])  # 2026-1 esta Cerrado: se permite (G3)
def test_crear_actividad(service, repo, db_conn, audit_store, actividades, periodo):
    rec = _record(service, repo)
    ov = actividades.overview(rec)
    pid = _per(db_conn, 1, periodo)
    _, _, res, err, nuevos, eventos = comparar(
        db_conn, audit_store, lambda ns: ns["guardar_actividad_especial"](pid, "  ZZNEXT   Taller  ", "desc", "obs"),
        lambda: actividades.crear(rec, {"periodo_id": pid, "titulo": "  ZZNEXT   Taller  ", "descripcion": "desc",
                                        "observaciones": "obs", "huella_periodos": ov["huella_periodos"]}))
    assert err is None and res["mensaje"] == "Actividad Especial creada correctamente."
    assert [(e["operation"], e["action"], e["action_scope"], e["entity_type"], e["entity_id"], e["audit_mode"])
            for e in eventos] == [("guardar_actividad_especial", "actividades_especiales.write", "department",
                                   "actividad_especial", str(pid), "IN_TRANSACTION")]
    assert eventos[0]["metadata"]["commit_seq"] == 1


def test_crear_titulo_vacio_failed_sin_escrituras(service, repo, db_conn, audit_store, actividades):
    rec = _record(service, repo)
    ov = actividades.overview(rec)
    pid = _per(db_conn, 1, "2026-2")
    _, err_c, _, err, nuevos, _ = comparar(
        db_conn, audit_store, lambda ns: ns["guardar_actividad_especial"](pid, "   "),
        lambda: actividades.crear(rec, {"periodo_id": pid, "titulo": "   ", "huella_periodos": ov["huella_periodos"]}))
    assert str(err_c) == err.message == "Ingresá el título de la actividad."
    assert [(e.operation, e.outcome, e.error_code) for e in nuevos] == [("guardar_actividad_especial", "FAILED", "ValueError")]


# ------------------------------------------------------------------------------------------ Pestaña 3: asignar docentes
def _pagina_asignar(ns, act_id, configs):
    """l. 66513-66527."""
    creadas, errores = 0, []
    for cuil, rol, obs in configs:
        try:
            ns["asignar_docente_actividad_especial"](act_id, cuil, rol, obs)
            creadas += 1
        except Exception as e:
            errores.append(f"{cuil}: {e}")
    return creadas, errores


def test_asignar_n_operaciones_y_error_intermedio_sigue(service, repo, db_conn, audit_store, actividades):
    """3 docentes, el del medio ya participa (CUIL literal): 2 COMMITs independientes y un aviso; el bucle sigue."""
    rec = _record(service, repo)
    pid = _per(db_conn, 1, "2026-2")
    datos = actividades.asignar_datos(rec, {"periodo_id": pid})
    act = datos["actividades"][0]
    ya = db_conn.execute("SELECT cuil FROM actividad_especial_docente WHERE actividad_id=%s ORDER BY id LIMIT 1",
                         [act["id"]]).fetchone()[0]
    libres = [o["cuil"] for o in datos["docentes"] if o["cuil"] != ya][:2]
    configs = [(libres[0], "Coordinadora", "o1"), (ya, "Evaluador", ""), (libres[1], " Organizador ", "")]
    res_c, _, res, err, _, eventos = comparar(
        db_conn, audit_store, lambda ns: _pagina_asignar(ns, act["id"], configs),
        lambda: actividades.asignar(rec, {"periodo_id": pid, "actividad_id": act["id"], "huella": act["huella"],
                                          "docentes": [{"cuil": c, "rol": r, "observaciones": o} for c, r, o in configs]}))
    assert err is None and res["mensaje"] == "Participaciones registradas: 2." and res_c[0] == 2
    assert res["avisos"] == res_c[1] == [f"{ya}: El docente ya está asignado a esta actividad."]
    assert len({e["correlation_id"] for e in eventos}) == 2


def test_duplicado_por_cuil_literal(service, repo, db_conn, audit_store, actividades):
    """El duplicado compara el CUIL literal: el mismo docente sin guiones NO es duplicado (G3)."""
    rec = _record(service, repo)
    pid = _per(db_conn, 1, "2026-2")
    datos = actividades.asignar_datos(rec, {"periodo_id": pid})
    act = datos["actividades"][0]
    ya = db_conn.execute("SELECT cuil FROM actividad_especial_docente WHERE actividad_id=%s ORDER BY id LIMIT 1",
                         [act["id"]]).fetchone()[0]
    sin_guiones = ya.replace("-", "")

    def cert(ns):
        return ns["asignar_docente_actividad_especial"](act["id"], sin_guiones, "Rol", "")

    def nxt():
        from actividades_especiales import escrituras as E
        from actividades_especiales.service import SPEC_ASIGNAR
        return actividades._op(rec, actividades.scope(rec), SPEC_ASIGNAR, lambda u: E.asignar_docente_actividad_especial(
            u, act["id"], sin_guiones, "Rol", ""), entity_raw=act["id"])
    _, err_c, _, err, _, _ = comparar(db_conn, audit_store, cert, nxt)
    assert err_c is None and err is None


def test_asignar_validaciones_de_pantalla(service, repo, db_conn, audit_store, actividades):
    rec = _record(service, repo)
    pid = _per(db_conn, 1, "2026-2")
    datos = actividades.asignar_datos(rec, {"periodo_id": pid})
    act, d = datos["actividades"][0], datos["docentes"][0]
    base = {"periodo_id": pid, "actividad_id": act["id"], "huella": act["huella"]}
    with pytest.raises(ActividadesError, match="Seleccioná al menos un docente."):
        actividades.asignar(rec, {**base, "docentes": []})
    with pytest.raises(ActividadesError, match="Indicá el rol de cada docente."):
        actividades.asignar(rec, {**base, "docentes": [{"cuil": d["cuil"], "rol": "  "}]})
    with pytest.raises(ActividadesError):  # docente fuera de la base maestra del departamento
        actividades.asignar(rec, {**base, "docentes": [{"cuil": "20-00000000-0", "rol": "X"}]})
    assert audit_store.events == []


def test_asignar_en_actividad_finalizada_no_se_ofrece_y_periodo_cerrado_si(service, repo, db_conn, audit_store, actividades):
    rec = _record(service, repo)
    per1 = _per(db_conn, 1, "2026-1")
    db_conn.execute("UPDATE actividades_especiales SET estado='Finalizada' WHERE id=1")
    assert actividades.asignar_datos(rec, {"periodo_id": _per(db_conn, 1, "2026-2")})["actividades"] == []
    aid = db_conn.execute("INSERT INTO actividades_especiales (institucion_id, departamento_id, periodo_id, titulo, estado, "
                          "fecha_carga) VALUES (1, 1, %s, 'ZZNEXT cerrado', 'Activa', 'x') RETURNING id", [per1]).fetchone()[0]
    datos = actividades.asignar_datos(rec, {"periodo_id": per1})
    act = _fila(datos["actividades"], aid)
    d = datos["docentes"][0]
    res_c, _, res, err, _, _ = comparar(
        db_conn, audit_store, lambda ns: _pagina_asignar(ns, aid, [(d["cuil"], "Rol", "")]),
        lambda: actividades.asignar(rec, {"periodo_id": per1, "actividad_id": aid, "huella": act["huella"],
                                          "docentes": [{"cuil": d["cuil"], "rol": "Rol"}]}))
    assert err is None and res["mensaje"] == "Participaciones registradas: 1."


# ------------------------------------------------------------------------------------------ Pestaña 5: editar / eliminar
@pytest.mark.parametrize("titulo,estado", [("ZZNEXT editado", "Finalizada"), ("   ", "Suspendida")])
def test_editar_sin_rowcount_y_titulo_vacio(service, repo, db_conn, audit_store, actividades, titulo, estado):
    rec = _record(service, repo)
    f = _fila(actividades.editar_datos(rec)["filas"], 1)
    _, err_c, res, err, _, eventos = comparar(
        db_conn, audit_store, lambda ns: ns["actualizar_actividad_especial"](1, titulo, "d", estado, "o"),
        lambda: actividades.editar(rec, {"actividad_id": 1, "huella": f["huella"], "titulo": titulo, "descripcion": "d",
                                         "estado": estado, "observaciones": "o"}))
    assert err_c is None and err is None and res["mensaje"] == "Actividad actualizada."
    assert eventos[0]["entity_id"] == "1" and eventos[0]["metadata"]["mutating_statements"] == 1


def test_writer_de_otro_departamento_no_valida_rowcount(service, repo, db_conn, audit_store, actividades):
    """La actividad 2 es del dep 2: desde el dep 1 el UPDATE/DELETE afecta 0 filas y el writer igual confirma (sin
    efecto sobre el otro departamento)."""
    from actividades_especiales import escrituras as E
    from actividades_especiales.service import SPEC_ACTUALIZAR
    rec = _record(service, repo)
    antes = db_conn.execute("SELECT titulo FROM actividades_especiales WHERE id=2").fetchone()[0]
    _, err_c, _, err, _, eventos = comparar(
        db_conn, audit_store, lambda ns: ns["actualizar_actividad_especial"](2, "ZZNEXT", "", "Activa", ""),
        lambda: actividades._op(rec, actividades.scope(rec), SPEC_ACTUALIZAR, lambda u: E.actualizar_actividad_especial(
            u, 2, "ZZNEXT", "", "Activa", ""), entity_raw=2))
    assert err_c is None and err is None and [e["audit_mode"] for e in eventos] == ["IN_TRANSACTION"]
    assert db_conn.execute("SELECT titulo FROM actividades_especiales WHERE id=2").fetchone()[0] == antes
    with pytest.raises(ActividadesError):  # la pantalla no la ofrece
        actividades.editar(rec, {"actividad_id": 2, "huella": "x", "titulo": "t", "estado": "Activa"})


def test_quitar_participacion_superadmin_sin_confirmacion(service, repo, db_conn, audit_store, actividades):
    sup = _record(service, repo, superadmin=True)
    f = _fila(actividades.editar_datos(sup)["filas"], 1)
    p = actividades.participaciones_actividad(sup, {"actividad_id": 1})["filas"][0]
    _, _, res, err, _, eventos = comparar(
        db_conn, audit_store, lambda ns: ns["eliminar_asignacion_actividad_especial"](p["id"]),
        lambda: actividades.quitar_participacion(sup, {"actividad_id": 1, "huella": f["huella"], "asignacion_id": p["id"],
                                                       "huella_participacion": p["huella"]}), rol="superadmin")
    assert err is None and res["mensaje"] == "Participación eliminada."
    assert (eventos[0]["action"], eventos[0]["entity_id"]) == ("actividades_especiales.delete", str(p["id"]))


def test_eliminar_actividad_y_participaciones(service, repo, db_conn, audit_store, actividades):
    sup = _record(service, repo, superadmin=True)
    f = _fila(actividades.editar_datos(sup)["filas"], 1)
    with pytest.raises(ActividadesError, match="Confirmá la eliminación por error."):
        actividades.eliminar(sup, {"actividad_id": 1, "huella": f["huella"], "confirmar": False})
    _, _, res, err, _, eventos = comparar(
        db_conn, audit_store, lambda ns: ns["eliminar_actividad_especial"](1),
        lambda: actividades.eliminar(sup, {"actividad_id": 1, "huella": f["huella"], "confirmar": True}), rol="superadmin")
    assert err is None and res["mensaje"] == "Actividad y participaciones eliminadas."
    assert eventos[0]["metadata"]["mutating_statements"] == 2 and eventos[0]["metadata"]["commit_seq"] == 1


@pytest.mark.parametrize("accion", ["quitar", "eliminar"])
def test_eliminaciones_denegadas_a_usuario_departamento(service, repo, db_conn, audit_store, actividades, accion):
    rec = _record(service, repo)
    f = _fila(actividades.editar_datos(rec)["filas"], 1)
    p = actividades.participaciones_actividad(rec, {"actividad_id": 1})["filas"][0]
    antes = db_conn.execute("SELECT (SELECT count(*) FROM actividades_especiales), "
                            "(SELECT count(*) FROM actividad_especial_docente)").fetchone()
    with pytest.raises(ActividadesError) as e:
        if accion == "quitar":
            actividades.quitar_participacion(rec, {"actividad_id": 1, "huella": f["huella"], "asignacion_id": p["id"],
                                                   "huella_participacion": p["huella"]})
        else:
            actividades.eliminar(rec, {"actividad_id": 1, "huella": f["huella"], "confirmar": True})
    assert e.value.status == 403
    assert [(x.outcome, x.audit_mode) for x in audit_store.events] == [("DENIED", "SEPARATE_TRANSACTION")]
    assert db_conn.execute("SELECT (SELECT count(*) FROM actividades_especiales), "
                           "(SELECT count(*) FROM actividad_especial_docente)").fetchone() == antes
