"""Diferenciales de ESCRITURA de Investigacion: misma operacion de pantalla, certificado vs NEXT, desde el mismo estado.

Lado certificado: la secuencia de la pagina (entry l. 64859-65647 y v217 l. 48390-49290, transcrita) llamando a los
writers certificados (``certified_investigacion``).  Lado NEXT: el servicio con una sesion real del AuthService
(FakeRepo).  Entre ambos, ROLLBACK al SAVEPOINT.  Se comparan las tablas que tocan los writers (proyectos,
asignaciones, movimientos, vinculos de actos; ids nuevos normalizados) y la secuencia de COMMITs por operacion B12H
(``commit_seq``, ``mutating_statements``, ``committing_writer``); las operaciones sin COMMIT deben quedar como SUCCESS
POST_OPERATION en NEXT."""

from __future__ import annotations

import json
import pprint
from datetime import date
from io import BytesIO

import pandas as pd
import psycopg
import pytest

from investigacion import excel as X
from investigacion.lecturas import Lecturas
from investigacion.repository import InvestigacionRepository
from investigacion.service import InvestigacionError
from investigacion_support import (  # noqa: F401  (fixtures)
    FIXED_TODAY, audit_rows, audit_store, baseline, certified_investigacion, db_conn, investigacion, lock_conn,
    session_for, state,
)

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")

INST = 1
USERS = {1: 3, 2: 6}  # departamento -> usuario_departamento del FakeRepo


def _record(service, repo, dep=2, superadmin=False):
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


def comparar(db_conn, audit_store, certificado, siguiente, dep=2, rol="usuario_departamento", preparar=None):
    if preparar is not None:
        preparar()
    baseline(db_conn)
    ns = certified_investigacion(db_conn, INST, dep, rol=rol)
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
    post = [e.operation for e in nuevos if e.outcome == "SUCCESS" and e.audit_mode == "POST_OPERATION"]
    fallidas = [e.operation for e in nuevos if e.outcome == "FAILED"]
    sin_commits = [o["op"] for o in ops_c if not o["commits"]]
    assert sorted(sin_commits) == sorted(post + [f for f in fallidas if f in sin_commits]), (sin_commits, post, fallidas)
    return res_c, err_c, res_n, err_n, nuevos


def _L(db_conn, dep=1):
    return Lecturas(InvestigacionRepository(db_conn, INST, dep), FIXED_TODAY, "usuario_departamento")


def _abierto(db_conn, dep=1):
    return _L(db_conn, dep).periodo_abierto()


def _proyecto_multidep(db_conn, creador=2):
    """Proyecto vigente del departamento creador con asignaciones activas en 2+ departamentos (2026-2)."""
    row = db_conn.execute("""
        SELECT pr.id FROM proyectos_investigacion pr JOIN investigacion_docente i ON i.proyecto_id=pr.id
        JOIN periodos p ON p.id=i.periodo_id
        WHERE pr.institucion_id=1 AND pr.departamento_id=%s AND pr.estado='Activo' AND p.nombre='2026-2'
          AND i.estado_asignacion='Activa'
        GROUP BY pr.id ORDER BY count(DISTINCT i.departamento_id) DESC, pr.id LIMIT 1""", [creador]).fetchone()
    return int(row[0])


def _fila(svc_lista, pid):
    return next(f for f in svc_lista if f["id"] == pid)


def _documento(db_conn, dep=2):
    row = db_conn.execute("SELECT id FROM documentos_respaldo WHERE institucion_id=1 AND departamento_id=%s "
                          "ORDER BY id LIMIT 1", [dep]).fetchone()
    if row is None:
        pytest.skip("sin actos en el repositorio")
    return int(row[0])


# ------------------------------------------------------------------------------------------ Pestaña 2: nuevo proyecto
@pytest.mark.parametrize("codigo,con_acto", [("ZZNEXT-001", False), ("", False), ("ZZNEXT-002", True)])
def test_alta_proyecto(service, repo, db_conn, audit_store, investigacion, codigo, con_acto):
    rec = _record(service, repo, dep=1)
    acto = _documento(db_conn, dep=1) if con_acto else None
    datos = dict(nombre="ZZNEXT Proyecto prueba", codigo=codigo, instituto="Departamento de Informática e Ingeniería",
                 anio_llamado=2025, fecha_inicio="2025-03-01", fecha_fin="2027-02-28", estado="Activo",
                 observaciones="obs", documento_id=acto)

    def cert(ns):
        pid, creado = ns["guardar_proyecto_investigacion"](datos["nombre"], codigo, datos["instituto"], 2025,
                                                           date(2025, 3, 1), date(2027, 2, 28), "obs", "Activo")
        if creado and acto is not None:
            ns["_vincular_proyectos_documento_v261"](acto, [{"tipo": "investigacion", "id": int(pid),
                                                             "nombre": datos["nombre"], "codigo": codigo}])
        return creado
    _, _, res, err, _ = comparar(db_conn, audit_store, cert, lambda: investigacion.guardar_proyecto(rec, datos), dep=1)
    assert err is None and res["tono"] == "success"


def test_alta_proyecto_duplicado_post_operation(service, repo, db_conn, audit_store, investigacion):
    rec = _record(service, repo)
    codigo = db_conn.execute("SELECT codigo_proyecto FROM proyectos_investigacion WHERE institucion_id=1 "
                             "AND departamento_id=2 ORDER BY id LIMIT 1").fetchone()[0]

    def cert(ns):
        return ns["guardar_proyecto_investigacion"]("Otro", codigo, "", 2025, date(2025, 1, 1), date(2025, 12, 31))
    _, _, res, err, eventos = comparar(db_conn, audit_store, cert, lambda: investigacion.guardar_proyecto(rec, dict(
        nombre="Otro", codigo=codigo, instituto="", anio_llamado=2025, fecha_inicio="2025-01-01",
        fecha_fin="2025-12-31", estado="Activo", observaciones="")))
    assert res["sin_cambios"] and res["mensaje"] == "Ya existe un proyecto con ese código o con esos mismos datos."
    assert [(e.operation, e.audit_mode) for e in eventos] == [("guardar_proyecto_investigacion", "POST_OPERATION")]


def test_alta_proyecto_validaciones_ui(service, repo, investigacion):
    rec = _record(service, repo)
    base = dict(nombre="X", codigo="", instituto="", anio_llamado=2025, fecha_inicio="2025-01-01",
                fecha_fin="2025-12-31", estado="Activo", observaciones="")
    with pytest.raises(InvestigacionError, match="Completá el nombre del proyecto."):
        investigacion.guardar_proyecto(rec, {**base, "nombre": "  "})
    with pytest.raises(InvestigacionError, match="anterior a la fecha de inicio"):
        investigacion.guardar_proyecto(rec, {**base, "fecha_fin": "2024-12-31"})


# ------------------------------------------------------------------------------------------ Pestaña 6: editar proyecto
def test_editar_proyecto_multidepartamento(service, repo, db_conn, audit_store, investigacion):
    rec = _record(service, repo)
    pid = _proyecto_multidep(db_conn)
    fila = _fila(investigacion.editar_proyectos(rec)["filas"], pid)
    nuevo = dict(nombre=fila["nombre_proyecto"] + " ZZNEXT", codigo=fila["codigo_proyecto"] + "-Z",
                 instituto="Instituto ZZNEXT", anio_llamado=int(fila["anio_llamado"]), fecha_inicio=fila["fecha_inicio"],
                 fecha_fin=fila["fecha_fin"], estado="Activo", observaciones="cambio")

    def cert(ns):
        return ns["actualizar_proyecto_investigacion"](pid, nuevo["nombre"], nuevo["codigo"], nuevo["instituto"],
                                                       nuevo["anio_llamado"], date.fromisoformat(nuevo["fecha_inicio"]),
                                                       date.fromisoformat(nuevo["fecha_fin"]), "cambio", "Activo")
    res_c, _, res, err, _ = comparar(db_conn, audit_store, cert, lambda: investigacion.editar_proyecto(
        rec, {"proyecto_id": pid, "huella": fila["huella"], **nuevo}))
    assert res_c[0] and err is None


def test_editar_proyecto_a_suspendido_rechazado(service, repo, db_conn, audit_store, investigacion):
    rec = _record(service, repo)
    pid = _proyecto_multidep(db_conn)
    fila = _fila(investigacion.editar_proyectos(rec)["filas"], pid)
    with pytest.raises(InvestigacionError):  # "Suspendido" no se ofrece si el proyecto no lo estaba
        investigacion.editar_proyecto(rec, {"proyecto_id": pid, "huella": fila["huella"], "nombre": "x", "codigo": "",
                                            "instituto": "", "anio_llamado": 2025, "fecha_inicio": "2025-01-01",
                                            "fecha_fin": "2025-12-31", "estado": "Suspendido", "observaciones": ""})


def test_editar_proyecto_duplicado_post_operation(service, repo, db_conn, audit_store, investigacion):
    rec = _record(service, repo)
    pid = _proyecto_multidep(db_conn)
    fila = _fila(investigacion.editar_proyectos(rec)["filas"], pid)
    otro = db_conn.execute("SELECT codigo_proyecto FROM proyectos_investigacion WHERE institucion_id=1 AND id<>%s "
                           "AND coalesce(codigo_proyecto,'')<>'' LIMIT 1", [pid]).fetchone()[0]

    def cert(ns):
        return ns["actualizar_proyecto_investigacion"](pid, "N", otro, "", 2025, date(2025, 1, 1), date(2025, 12, 31))
    res_c, _, _, err, eventos = comparar(db_conn, audit_store, cert, lambda: investigacion.editar_proyecto(rec, {
        "proyecto_id": pid, "huella": fila["huella"], "nombre": "N", "codigo": otro, "instituto": "",
        "anio_llamado": 2025, "fecha_inicio": "2025-01-01", "fecha_fin": "2025-12-31", "estado": "Activo",
        "observaciones": ""}))
    assert err.message == res_c[1] and err.tone == "warning"
    assert [e.audit_mode for e in eventos] == ["POST_OPERATION"]


def test_proyecto_de_otro_departamento_no_administrable(service, repo, db_conn, investigacion):
    rec = _record(service, repo, dep=1)
    ajeno = int(db_conn.execute("SELECT id FROM proyectos_investigacion WHERE institucion_id=1 AND departamento_id=2 "
                                "LIMIT 1").fetchone()[0])
    assert all(f["id"] != ajeno for f in investigacion.editar_proyectos(rec)["filas"])
    assert all(f["id"] != ajeno for f in investigacion.archivar_proyectos(rec)["filas"])
    with pytest.raises(InvestigacionError):
        investigacion.editar_proyecto(rec, {"proyecto_id": ajeno, "huella": "x"})
    sup = _record(service, repo, dep=1, superadmin=True)
    assert any(f["id"] == ajeno for f in investigacion.editar_proyectos(sup)["filas"])


# ------------------------------------------------------------------------------------------ Pestaña 7: bajas / suspension
def test_suspender_proyecto_multidepartamento(service, repo, db_conn, audit_store, investigacion):
    rec = _record(service, repo)
    pid = _proyecto_multidep(db_conn)
    ov = investigacion.overview(rec)
    fila = _fila(investigacion.suspender_proyectos(rec)["filas"], pid)
    per = ov["abierto"]["id"]

    def cert(ns):
        return ns["suspender_proyecto_investigacion"](pid, per, "Motivo ZZNEXT", date(2026, 10, 20))
    res_c, _, res, err, _ = comparar(db_conn, audit_store, cert, lambda: investigacion.suspender(rec, {
        "proyecto_id": pid, "huella": fila["huella"], "huella_periodo": ov["huella_periodo"], "confirmar": True,
        "motivo": "Motivo ZZNEXT", "fecha_suspension": "2026-10-20"}))
    assert err is None and res["mensaje"] == res_c[1] and res_c[2] > 1


def test_suspender_validaciones_ui(service, repo, investigacion):
    rec = _record(service, repo)
    with pytest.raises(InvestigacionError, match="Primero confirmá la suspensión."):
        investigacion.suspender(rec, {"confirmar": False, "motivo": "x", "fecha_suspension": "2026-10-20"})
    with pytest.raises(InvestigacionError, match="Completá el motivo de la suspensión."):
        investigacion.suspender(rec, {"confirmar": True, "motivo": " ", "fecha_suspension": "2026-10-20"})
    with pytest.raises(InvestigacionError, match="Seleccioná un proyecto desde la tabla."):
        investigacion.suspender(rec, {"confirmar": True, "motivo": "x", "fecha_suspension": "2026-10-20"})


def test_archivar_proyecto(service, repo, db_conn, audit_store, investigacion):
    rec = _record(service, repo)
    pid = _proyecto_multidep(db_conn)
    fila = _fila(investigacion.archivar_proyectos(rec)["filas"], pid)

    def cert(ns):
        return ns["archivar_proyecto_investigacion"](pid, "por prueba")
    res_c, _, res, err, _ = comparar(db_conn, audit_store, cert, lambda: investigacion.archivar(rec, {
        "proyecto_id": pid, "huella": fila["huella"], "confirmar": True, "motivo": "por prueba"}))
    assert err is None and res["mensaje"] == res_c[1]


def test_eliminar_proyecto_superadmin_deja_huerfanos(service, repo, db_conn, audit_store, investigacion):
    sup = _record(service, repo, superadmin=True)
    pid = _proyecto_multidep(db_conn)
    fila = _fila(investigacion.editar_proyectos(sup)["filas"], pid)
    texto = fila["codigo_proyecto"] or fila["nombre_proyecto"]
    res_c, _, res, err, _ = comparar(db_conn, audit_store, lambda ns: ns["eliminar_proyecto_investigacion"](pid),
                                     lambda: investigacion.eliminar_proyecto(sup, {
                                         "proyecto_id": pid, "huella": fila["huella"], "confirmar": True,
                                         "confirmacion": texto}), rol="superadmin")
    assert err is None and res["mensaje"] == res_c[1]


def test_eliminar_proyecto_denegado_a_usuario_departamento(service, repo, db_conn, audit_store, investigacion):
    rec = _record(service, repo)
    pid = _proyecto_multidep(db_conn)
    fila = _fila(investigacion.editar_proyectos(rec)["filas"], pid)
    texto = fila["codigo_proyecto"] or fila["nombre_proyecto"]
    with pytest.raises(InvestigacionError) as e:
        investigacion.eliminar_proyecto(rec, {"proyecto_id": pid, "huella": fila["huella"], "confirmar": True,
                                              "confirmacion": texto})
    assert e.value.status == 403
    assert [(x.operation, x.outcome) for x in audit_store.events] == [("eliminar_proyecto_investigacion", "DENIED")]


def test_eliminar_proyecto_confirmaciones(service, repo, db_conn, investigacion):
    sup = _record(service, repo, superadmin=True)
    pid = _proyecto_multidep(db_conn)
    fila = _fila(investigacion.editar_proyectos(sup)["filas"], pid)
    with pytest.raises(InvestigacionError, match="Primero confirmá que entendés"):
        investigacion.eliminar_proyecto(sup, {"proyecto_id": pid, "huella": fila["huella"], "confirmar": False})
    with pytest.raises(InvestigacionError, match="no coincide exactamente"):
        investigacion.eliminar_proyecto(sup, {"proyecto_id": pid, "huella": fila["huella"], "confirmar": True,
                                              "confirmacion": "otra cosa"})


def test_baja_asignacion_sin_movimiento(service, repo, db_conn, audit_store, investigacion):
    rec = _record(service, repo)
    filas = investigacion.editar_asignaciones(rec)["filas"]
    fila = filas[0]
    res_c, _, res, err, _ = comparar(
        db_conn, audit_store, lambda ns: ns["eliminar_investigacion_docente"](fila["id"], "motivo", date(2026, 10, 1)),
        lambda: investigacion.baja_asignacion(rec, {"asignacion_id": fila["id"], "huella": fila["huella"],
                                                    "confirmar": True, "motivo": "motivo", "fecha_baja": "2026-10-01"}))
    assert err is None and res["mensaje"] == "Asignación dada de baja. Se conserva en el historial."


# ------------------------------------------------------------------------------------------ Pestaña 3: asignar docentes
def _pagina_asignar(ns, periodo_id, proyecto_id, nombre_proyecto, configs):
    """l. 48712-48782 (bucle v270)."""
    creados, omitidos, errores = 0, 0, []
    for cfg in configs:
        if ns["buscar_asignacion_activa_docente_proyecto"](periodo_id, proyecto_id, cfg["cuil"], todos_departamentos=True):
            omitidos += 1
            continue
        try:
            ns["asignar_docente_a_proyecto"](periodo_id, proyecto_id, cfg["cuil"], cfg["rol"], cfg["horas"], cfg["obs"])
            ns["registrar_movimiento"]("Asignación a investigación", cfg["cuil"], cfg["docente"],
                                       f"Se asignaron {cfg['horas']:g} hs semanales al proyecto {nombre_proyecto} "
                                       f"como {cfg['rol']}.", cfg["obs"], periodo_id)
            creados += 1
        except Exception as exc:
            errores.append(f"{cfg['docente']}: {exc}")
    return creados, omitidos, errores


def test_asignar_docentes_2n_operaciones(service, repo, db_conn, audit_store, investigacion):
    rec = _record(service, repo)
    pid = _proyecto_multidep(db_conn)
    ov = investigacion.overview(rec)
    proy = _fila(investigacion.asignar_proyectos(rec)["proyectos"], pid)
    det = investigacion.asignar_detalle(rec, {"proyecto_id": pid})
    nuevos = det["docentes"][:2]
    configs = [{"cuil": d["cuil"], "docente": d["nombre_completo"], "rol": r, "horas": h, "obs": o}
               for d, r, h, o in zip(nuevos, ["Directora", "Integrante"], [2.5, 0.0], ["", "obs ZZNEXT"])]
    per = ov["abierto"]["id"]

    def siguiente():
        return investigacion.asignar(rec, {
            "proyecto_id": pid, "huella_proyecto": proy["huella"], "huella_periodo": ov["huella_periodo"],
            "huella_integrantes": det["huella_integrantes"],
            "docentes": [{"cuil": c["cuil"], "rol": c["rol"], "horas": c["horas"], "observaciones": c["obs"]}
                         for c in configs]})
    res_c, _, res, err, eventos = comparar(
        db_conn, audit_store, lambda ns: _pagina_asignar(ns, per, pid, proy["nombre_proyecto"], configs), siguiente)
    assert err is None and res["mensaje"] == "Asignación finalizada: 2 nueva/s."


def test_asignar_docente_ya_asignado_omitido(service, repo, db_conn, audit_store, investigacion):
    """Un integrante de OTRO departamento del mismo proyecto: duplicado institucional -> omitido, sin escribir."""
    rec = _record(service, repo)
    pid = _proyecto_multidep(db_conn)
    ov = investigacion.overview(rec)
    proy = _fila(investigacion.asignar_proyectos(rec)["proyectos"], pid)
    det = investigacion.asignar_detalle(rec, {"proyecto_id": pid})
    otro = next(i for i in det["integrantes"] if i["departamento_asignacion_id"] != 2)
    padron = {X_c(d["cuil"]) for d in investigacion._read(investigacion.scope(rec), lambda L: L.padron()
                                                            .to_dict(orient="records"))}
    if X_c(otro["cuil"]) not in padron:
        pytest.skip("integrante fuera del padron")
    res = investigacion.asignar(rec, {"proyecto_id": pid, "huella_proyecto": proy["huella"],
                                      "huella_periodo": ov["huella_periodo"],
                                      "huella_integrantes": det["huella_integrantes"],
                                      "docentes": [{"cuil": otro["cuil"], "rol": "Integrante", "horas": 1}]})
    assert res["mensaje"] == "Asignación finalizada: 0 nueva/s, 1 duplicada/s omitida/s."
    assert audit_store.events == []


def X_c(c):
    from investigacion.rules import clave_cuil
    return clave_cuil(c)


def test_asignar_validaciones_ui(service, repo, db_conn, investigacion):
    rec = _record(service, repo)
    pid = _proyecto_multidep(db_conn)
    det = investigacion.asignar_detalle(rec, {"proyecto_id": pid})
    d = det["docentes"][0]
    with pytest.raises(InvestigacionError, match="completá el rol del docente en el proyecto"):
        investigacion.asignar(rec, {"proyecto_id": pid, "docentes": [{"cuil": d["cuil"], "rol": " ", "horas": 1}]})
    with pytest.raises(InvestigacionError, match="las horas deben ser 0 o más"):
        investigacion.asignar(rec, {"proyecto_id": pid, "docentes": [{"cuil": d["cuil"], "rol": "X", "horas": -1}]})


def test_eliminar_asignacion_por_error_superadmin(service, repo, db_conn, audit_store, investigacion):
    sup = _record(service, repo, superadmin=True)
    pid = _proyecto_multidep(db_conn)
    det = investigacion.asignar_detalle(sup, {"proyecto_id": pid})
    fila = det["eliminables"][0]
    res_c, _, res, err, _ = comparar(
        db_conn, audit_store, lambda ns: ns["eliminar_investigacion_docente_definitivamente"](fila["id"]),
        lambda: investigacion.eliminar_asignacion_error(sup, {"proyecto_id": pid, "asignacion_id": fila["id"],
                                                              "huella": fila["huella"], "confirmar": True}),
        rol="superadmin")
    assert err is None and res["mensaje"] == res_c[1]


def test_eliminables_filtrados_por_departamento(service, repo, db_conn, investigacion):
    rec = _record(service, repo)
    det = investigacion.asignar_detalle(rec, {"proyecto_id": _proyecto_multidep(db_conn)})
    assert det["eliminables"] and all(f["departamento_asignacion_id"] == 2 for f in det["eliminables"])
    assert len(det["integrantes"]) > len(det["eliminables"])


# ------------------------------------------------------------------------------------------ Pestaña 6: editar asignacion
def test_editar_asignacion_con_movimiento_y_etiqueta(service, repo, db_conn, audit_store, investigacion):
    rec = _record(service, repo)
    fila = investigacion.editar_asignaciones(rec)["filas"][0]
    opc = investigacion.editar_asignacion_opciones(rec, {"asignacion_id": fila["id"]})
    actual = next(o for o in opc["docentes"] if o["actual"])
    per = investigacion.overview(rec)["abierto"]["id"]
    pid = int(fila["proyecto_id"])

    def cert(ns):
        p = ns["_proyecto_investigacion_por_id"](pid)
        ok, msg = ns["actualizar_investigacion_docente"](fila["id"], per, actual["cuil"], p.get("nombre_proyecto", ""),
                                                         "Codirectora", p.get("anio_llamado"),
                                                         p.get("periodo_ejecucion", ""), 3.0, "obs",
                                                         p.get("codigo_proyecto", ""), p.get("instituto_proyecto", ""),
                                                         proyecto_id=pid)
        if ok:
            ns["registrar_movimiento"]("Modificación de investigación", actual["cuil"], actual["etiqueta"],
                                       f"Se modificó la asignación al proyecto {p.get('nombre_proyecto', '')} como "
                                       f"Codirectora ({3.0:g} hs semanales).", "obs", per)
        return ok, msg
    res_c, _, res, err, _ = comparar(db_conn, audit_store, cert, lambda: investigacion.editar_asignacion(rec, {
        "asignacion_id": fila["id"], "huella": fila["huella"], "proyecto_id": pid,
        "docente_etiqueta": actual["etiqueta"], "rol": "Codirectora", "horas": 3, "observaciones": "obs"}))
    assert err is None and res["mensaje"] == "Asignación actualizada." and res_c[0]
    assert res["alerta_post_accion"]["accion"] == "Modificación de Investigación"


def test_editar_asignacion_rol_vacio(service, repo, investigacion):
    rec = _record(service, repo)
    fila = investigacion.editar_asignaciones(rec)["filas"][0]
    actual = next(o for o in investigacion.editar_asignacion_opciones(rec, {"asignacion_id": fila["id"]})["docentes"]
                  if o["actual"])
    with pytest.raises(InvestigacionError, match="Completá el rol."):
        investigacion.editar_asignacion(rec, {"asignacion_id": fila["id"], "huella": fila["huella"],
                                              "proyecto_id": int(fila["proyecto_id"]),
                                              "docente_etiqueta": actual["etiqueta"], "rol": "", "horas": 1})


# ------------------------------------------------------------------------------------------ actos
def test_vincular_y_desvincular_actos(service, repo, db_conn, audit_store, investigacion):
    sup = _record(service, repo, dep=1, superadmin=True)
    doc = _documento(db_conn, dep=1)
    filas = investigacion.historial(sup)["filas"][:3]
    ids = [f["id"] for f in filas]
    huellas = {str(f["id"]): f["huella"] for f in filas}
    proyectos = [{"tipo": "investigacion", "id": f["id"], "nombre": f["nombre_proyecto"], "codigo": f["codigo_proyecto"]}
                 for f in filas]
    comparar(db_conn, audit_store, lambda ns: ns["_vincular_proyectos_documento_v261"](doc, proyectos),
             lambda: investigacion.vincular_acto(sup, {"documento_id": doc, "proyecto_ids": ids, "huellas": huellas}),
             rol="superadmin", dep=1)

    def preparar_vinculo():
        db_conn.execute("INSERT INTO documentos_respaldo_proyectos (institucion_id, departamento_id, documento_id, "
                        "proyecto_tipo, proyecto_id, proyecto_nombre, codigo_proyecto) VALUES (1,1,%s,'investigacion',%s,"
                        "'x','x') ON CONFLICT DO NOTHING", [doc, ids[0]])
    with db_conn.transaction() as tx:
        res_c, _, res, err, _ = comparar(
            db_conn, audit_store, lambda ns: ns["desvincular_acto_proyectos_masivo_v267"](doc, "investigacion", ids),
            lambda: investigacion.desvincular_acto(sup, {"documento_id": doc, "proyecto_ids": ids, "huellas": huellas}),
            rol="superadmin", dep=1, preparar=preparar_vinculo)
        assert err is None and res_c == int(res["mensaje"].split()[2])
        raise psycopg.Rollback(tx)


def test_desvincular_denegado_a_usuario_departamento(service, repo, db_conn, audit_store, investigacion):
    rec = _record(service, repo, dep=1)
    doc = _documento(db_conn, dep=1)
    f = investigacion.historial(rec)["filas"][0]
    with pytest.raises(InvestigacionError) as e:
        investigacion.desvincular_acto(rec, {"documento_id": doc, "proyecto_ids": [f["id"]],
                                             "huellas": {str(f["id"]): f["huella"]}})
    assert e.value.status == 403


# ------------------------------------------------------------------------------------------ Pestaña 8: carga rapida
def _excel(investigacion, rec, proyectos=(), asignaciones=()):
    from openpyxl import load_workbook
    wb = load_workbook(BytesIO(investigacion.modelo_excel(rec)))
    ws = wb["Carga rápida"]
    fila = next(r for r in range(2, ws.max_row + 2) if ws.cell(row=r, column=2).value in (None, ""))
    for p in proyectos:
        for j, v in enumerate(p, 1):
            ws.cell(row=fila, column=j, value=v)
        fila += 1
    ws = wb["Asignar docentes"]
    fila = next(r for r in range(2, ws.max_row + 2) if ws.cell(row=r, column=2).value in (None, ""))
    for a in asignaciones:
        for j, v in enumerate(a, 1):
            ws.cell(row=fila, column=j, value=v)
        fila += 1
    out = BytesIO()
    wb.save(out)
    return out.getvalue()


def _pagina_carga(ns, contenido, periodo_id):
    """render_carga_rapida_proyectos_v217 (l. 49210) al presionar "🚀 Procesar carga rápida"."""
    df_carga = ns["leer_excel_carga_rapida_proyectos_v127"](contenido)
    df_nuevas = df_carga[df_carga["id"].apply(ns["_parse_id_excel_proyecto_v127"]).isna()].copy()
    df_nuevas = df_nuevas[df_nuevas.apply(lambda r: any(pd.notna(v) and str(v).strip() and str(v).strip().lower()
                                                        not in {"nan", "none"} for v in r.tolist()), axis=1)].copy()
    df_asig = ns["leer_asignaciones_proyectos_excel_v217"](contenido)
    df_asig_nuevas = df_asig[df_asig["id"].apply(ns["_parse_id_excel_proyecto_v127"]).isna()].copy()
    rp = {"creados": 0}
    if not df_nuevas.empty:
        rp = ns["cargar_proyectos_excel_v127"](df_carga, "investigacion")
    ra = {"creadas": 0, "omitidas": 0}
    if not df_asig_nuevas.empty:
        ra = ns["cargar_asignaciones_proyectos_excel_v217"](df_asig, "investigacion", int(periodo_id))
    return rp, ra


def _carga(investigacion, rec, contenido, ov):
    import base64
    return investigacion.carga_ejecutar(rec, {"archivo": base64.b64encode(contenido).decode(), "confirmar": True,
                                              "huella_periodo": ov["huella_periodo"]})


def test_carga_rapida_proyectos_y_asignaciones(service, repo, db_conn, audit_store, investigacion):
    rec = _record(service, repo)
    ov = investigacion.overview(rec)
    pid = _proyecto_multidep(db_conn)
    det = investigacion.asignar_detalle(rec, {"proyecto_id": pid})
    d1, d2 = det["docentes"][:2]
    proy = _fila(investigacion.asignar_proyectos(rec)["proyectos"], pid)
    etiqueta = f"[{proy['codigo_proyecto']}] {proy['nombre_proyecto']}" if proy["codigo_proyecto"] else proy["nombre_proyecto"]
    contenido = _excel(investigacion, rec,
                       proyectos=[("", "ZZNEXT Excel A", "ZZNEXT-X1", "", 2025, date(2025, 3, 1), date(2027, 3, 1),
                                   "Activo", "o"),
                                  ("", "ZZNEXT Excel B", "", "Otra unidad", "", "01/04/2026", "31/03/2028", "activo", "")],
                       asignaciones=[("", etiqueta, f"{d1['nombre_completo']} | {d1['cuil']}", "Directora", 2.5, ""),
                                     ("", "[ZZNEXT-X1] ZZNEXT Excel A", f"{d2['nombre_completo']} | {d2['cuil']}",
                                      "Codirectora", 4, "x")])
    _, _, res, err, _ = comparar(db_conn, audit_store, lambda ns: _pagina_carga(ns, contenido, ov["abierto"]["id"]),
                                 lambda: _carga(investigacion, rec, contenido, ov))
    assert err is None and "Proyectos creados: 2" in res["mensaje"] and "asignaciones docentes creadas: 2" in res["mensaje"]


def test_carga_rapida_validacion_previa_no_escribe(service, repo, db_conn, audit_store, investigacion):
    rec = _record(service, repo)
    ov = investigacion.overview(rec)
    contenido = _excel(investigacion, rec, proyectos=[("", "ZZNEXT ok", "", "", 2025, date(2025, 1, 1),
                                                       date(2025, 12, 31), "Activo", ""),
                                                      ("", "ZZNEXT mal", "", "", 2025, date(2025, 12, 31),
                                                       date(2025, 1, 1), "Activo", "")])
    _, err_c, _, err, eventos = comparar(db_conn, audit_store, lambda ns: _pagina_carga(ns, contenido, ov["abierto"]["id"]),
                                         lambda: _carga(investigacion, rec, contenido, ov))
    assert str(err_c) == err.message and err.message.startswith("No se realizó la carga porque se detectaron errores")
    assert [(e.operation, e.outcome) for e in eventos] == [("cargar_proyectos_excel_v127", "FAILED")]


def test_carga_rapida_falla_parcial_conserva_proyectos(service, repo, db_conn, audit_store, investigacion):
    """Op 2 rechazada (docente fuera del padron) despues del COMMIT de la Op 1: los proyectos quedan."""
    rec = _record(service, repo)
    ov = investigacion.overview(rec)
    contenido = _excel(investigacion, rec,
                       proyectos=[("", "ZZNEXT parcial", "ZZNEXT-P1", "", 2025, date(2025, 1, 1), date(2027, 12, 31),
                                   "Activo", "")],
                       asignaciones=[("", "[ZZNEXT-P1] ZZNEXT parcial", "Nadie | 20-00000000-0", "Integrante", 1, "")])
    _, err_c, _, err, eventos = comparar(db_conn, audit_store, lambda ns: _pagina_carga(ns, contenido, ov["abierto"]["id"]),
                                         lambda: _carga(investigacion, rec, contenido, ov))
    assert str(err_c) == err.message and "no está disponible en el plantel" in err.message
    assert [(e.operation, e.outcome) for e in eventos] == [("cargar_asignaciones_proyectos_excel_v217", "FAILED")]
