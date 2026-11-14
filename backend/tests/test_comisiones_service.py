"""Servicio y HTTP de Comisiones sobre deptit_next_dev con ROLLBACK: lecturas de las 8 pestañas, flujos de escritura,
permisos B10 (departamento / institucion para sedes), tenant, IDs manipulados, B12I capa U y capa T (lock de 30 s),
B12H (DENIED / FAILED / POST_OPERATION / fallas tras COMMIT parcial / compensacion), lecturas sin escrituras (B12F) y
contrato HTTP.  Usuarios del FakeRepo (sin credenciales humanas)."""

from __future__ import annotations

import base64
import threading

import psycopg
import pytest

import audit
from comisiones import rules as R
from comisiones.service import LOCK_WAIT_SECONDS, ComisionesError
from comisiones_support import (  # noqa: F401  (fixtures)
    EXTRA_DEPARTMENTS, audit_rows, audit_store, comisiones, db_conn, http, lock_conn, make_comisiones, session_for,
)

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")

CSRF = {"X-DEPTIT-Request": "1"}
FORBIDDEN = ("salt", "password_hash", "postgresql://", "DATABASE_URL", "deptit_session", "SELECT ", "UPDATE ",
             "DELETE ", "Traceback", "psycopg", "institucion_id =")
ACTUAL = 9      # 2026-2 Abierto (dep 1)
HISTORICO = 5   # 2026-1 Cerrado (dep 1)


@pytest.fixture
def records(service, repo):
    out = {"dep": session_for(service, repo, 3)[0], "lector": session_for(service, repo, 7)[0],
           "coord": session_for(service, repo, 2)[0], "otro_dep": session_for(service, repo, 6)[0]}
    sup = session_for(service, repo, 1)[0]
    service.set_context(sup, 1, 1, False)
    out["super"] = sup
    coord_dep = session_for(service, repo, 2)[0]
    service.set_context(coord_dep, 1, 1, False)
    out["coord_dep"] = coord_dep
    return out


def _contar(db_conn):
    return db_conn.execute(
        "SELECT (SELECT count(*) FROM comisiones), (SELECT count(*) FROM horarios_comision), "
        "(SELECT count(*) FROM asignaciones_docentes_comision), (SELECT count(*) FROM horarios_asignacion_docente_comision), "
        "(SELECT count(*) FROM comision_materias), (SELECT count(*) FROM movimientos), (SELECT count(*) FROM docentes), "
        "(SELECT count(*) FROM inscriptos_asignatura_periodo), (SELECT count(*) FROM sedes_institucion), "
        "(SELECT md5(string_agg(md5(c::text), '' ORDER BY c.id)) FROM comisiones c), "
        "(SELECT md5(string_agg(md5(a::text), '' ORDER BY a.id)) FROM asignaciones_docentes_comision a), "
        "(SELECT md5(string_agg(md5(i::text), '' ORDER BY i.id)) FROM investigacion_docente i)").fetchone()


def _materia_comun(svc, rec):
    filas = svc.abrir_materias(rec, {})["materias"]
    for f in filas:
        info = svc.abrir_materia(rec, {"materia_id": f["materia_id"]})
        if not info["es_oe"]:
            return f["materia_id"]
    raise AssertionError("sin materia comun")


def _docente(svc, rec, contexto="actual"):
    return svc.docentes(rec, {"contexto": contexto})["docentes"][0]


def _abrir(svc, rec, db_conn, nombre="ZZ1", horarios=None, docentes=None, **extra):
    mid = extra.pop("materia_id", None) or _materia_comun(svc, rec)
    horarios = horarios or [{"dia": "Lunes", "hora_inicio": "08:00", "hora_fin": "10:00"}]
    if docentes is None:
        d = _docente(svc, rec)
        roles = svc.docente_roles(rec, {"contexto": "actual", "cuil": d["cuil"]})["roles"]
        docentes = [{"cuil": d["cuil"], "rol": roles[0] if roles else R.ROLES_DOCENTE_COMISION[0],
                     "franjas": [{"usar": True, "desde": h["hora_inicio"], "hasta": h["hora_fin"]} for h in horarios]}]
    data = {"materia_id": mid, "nombre": nombre, "turno": "mañana", "sede": "Sin especificar", "modalidad": "Presencial",
            "fecha_apertura": "2026-10-26", "observaciones": "ZZNEXT", "observaciones_asignaciones": "",
            "horarios": horarios, "docentes": docentes, "huella_periodos": svc.overview(rec)["huella_periodos"]}
    data.update(extra)
    return svc.abrir(rec, data)


# ------------------------------------------------------------------------------------------ lecturas
def test_lecturas_de_las_pestanas_no_escriben(comisiones, records, db_conn, audit_store):
    rec = records["dep"]
    antes = _contar(db_conn)
    ov = comisiones.overview(rec)
    assert ov["actual"]["id"] == ACTUAL and ov["puede_operar"] and ov["permisos"]["puede_escribir"]
    assert not ov["permisos"]["puede_borrar"] and ov["permisos"]["puede_escribir_sedes"]
    for pid in (ACTUAL, HISTORICO):
        p = comisiones.periodo(rec, pid)
        assert not p["vacio"] and p["filas"] and p["caption"].startswith("Total comisiones:")
        ins = comisiones.inscriptos(rec, pid)
        assert "legacy" in ins
    assert comisiones.alertas(rec)["periodo"]["id"] == ACTUAL
    assert comisiones.sedes(rec)["sedes"]
    mats = comisiones.abrir_materias(rec, {"nombre": "a"})
    assert mats["caption"].startswith("Materias encontradas:")
    assert comisiones.docentes(rec, {"contexto": "actual"})["docentes"]
    lista = comisiones.comisiones_lista(rec, {"contexto": "modificacion"})
    cid = lista["filas"][0]["id"]
    det = comisiones.comision_detalle(rec, {"contexto": "modificacion", "comision_id": cid})
    assert det["huella"] and "historial" in det
    lista_e = comisiones.comisiones_lista(rec, {"contexto": "edicion"})
    det_e = comisiones.comision_detalle(rec, {"contexto": "edicion", "comision_id": lista_e["filas"][0]["id"]})
    datos = comisiones.edicion_datos(rec, {"comision_id": lista_e["filas"][0]["id"]})
    assert datos["materias"] and datos["valores"]["turno"] in R.TURNOS_COMISION
    if det_e["asignaciones"]:
        comisiones.asignacion_franjas(rec, {"comision_id": det_e["fila"]["id"],
                                            "asignacion_id": det_e["asignaciones"][0]["id"]})
    assert comisiones.modelo_excel(rec)[:2] == b"PK"
    contenido, nombre = comisiones.periodo_excel(rec, HISTORICO)
    assert contenido[:2] == b"PK" and nombre.endswith(".xlsx")
    assert _contar(db_conn) == antes and audit_store.events == []


# ------------------------------------------------------------------------------------------ abrir comisión
def test_abrir_comision_completa(comisiones, records, db_conn, audit_store):
    rec = records["dep"]
    antes = _contar(db_conn)
    res = _abrir(comisiones, rec, db_conn)
    assert res["tono"] in ("success", "warning") and res["id"]
    despues = _contar(db_conn)
    assert despues[0] == antes[0] + 1 and despues[1] == antes[1] + 1 and despues[2] == antes[2] + 1
    assert despues[5] == antes[5] + 2  # Apertura + Asignación
    obs = db_conn.execute("SELECT observaciones FROM comisiones WHERE id=%s", [res["id"]]).fetchone()[0]
    assert obs == "ZZNEXT"


# ------------------------------------------------------------------------------------------ permisos B10 / ámbito
def test_overview_permisos_por_rol(comisiones, records):
    dep = comisiones.overview(records["dep"])["permisos"]
    assert dep == {"puede_escribir": True, "puede_borrar": False, "puede_escribir_sedes": True,
                   "puede_borrar_sedes": False, "puede_movimiento": True}
    sup = comisiones.overview(records["super"])["permisos"]
    assert sup["puede_borrar"] and sup["puede_borrar_sedes"]
    lector = comisiones.overview(records["lector"])["permisos"]
    assert not any(lector.values())
    coord = comisiones.overview(records["coord_dep"])["permisos"]
    assert not coord["puede_escribir"] and not coord["puede_borrar"]


def test_coordinador_sin_departamento_no_ve_el_modulo(comisiones, records):
    with pytest.raises(ComisionesError) as exc:
        comisiones.overview(records["coord"])
    assert exc.value.code == "SCOPE_INSTITUTIONAL"


def test_coordinador_y_solo_lectura_no_escriben(comisiones, records, db_conn, audit_store):
    antes = _contar(db_conn)
    for rec in (records["coord_dep"], records["lector"]):
        with pytest.raises(ComisionesError) as exc:
            comisiones.agregar_sede(rec, {"nombre": "ZZ", "direccion": "x 1", "localidad": "y"})
        assert exc.value.code == "DENIED"
    with pytest.raises(ComisionesError) as exc:
        _abrir(comisiones, records["lector"], db_conn)
    assert exc.value.code == "DENIED" and exc.value.message.startswith("No se pudo abrir la comisión completa: ")
    assert _contar(db_conn) == antes
    assert [e.outcome for e in audit_store.events] == ["DENIED"] * 3


def test_usuario_departamento_no_elimina(comisiones, records, db_conn, audit_store):
    rec = records["dep"]
    lista = comisiones.comisiones_lista(rec, {"contexto": "edicion"})
    cid = lista["filas"][0]["id"]
    det = comisiones.comision_detalle(rec, {"contexto": "edicion", "comision_id": cid})
    antes = _contar(db_conn)
    with pytest.raises(ComisionesError) as exc:
        comisiones.eliminar_comision(rec, {"comision_id": cid, "confirmar": True, "huella": det["huella"]})
    assert exc.value.code == "DENIED" and "comisiones.delete" in exc.value.message
    if det["horarios"]:
        with pytest.raises(ComisionesError) as exc:
            comisiones.eliminar_horario(rec, {"comision_id": cid, "horario_id": det["horarios"][0]["id"],
                                              "confirmar": True, "huella": det["huella"]})
        assert exc.value.code == "DENIED"
    sede = comisiones.sedes(rec)["sedes"][0]
    with pytest.raises(ComisionesError) as exc:
        comisiones.eliminar_sede(rec, {"id": sede["id"], "confirmar": True, "huella": sede["huella"]})
    assert exc.value.code == "DENIED"
    assert _contar(db_conn) == antes and {e.outcome for e in audit_store.events} == {"DENIED"}


def test_ids_de_otro_departamento_y_valores_invalidos(comisiones, records, db_conn, audit_store):
    rec = records["dep"]
    ajena = db_conn.execute("SELECT id FROM comisiones WHERE departamento_id<>1 ORDER BY id LIMIT 1").fetchone()[0]
    antes = _contar(db_conn)
    for contexto in ("modificacion", "edicion"):
        with pytest.raises(ComisionesError) as exc:
            comisiones.comision_detalle(rec, {"contexto": contexto, "comision_id": ajena})
        assert exc.value.code == "NOT_FOUND"
    with pytest.raises(ComisionesError) as exc:
        comisiones.eliminar_comision(records["super"], {"comision_id": ajena, "confirmar": True, "huella": "x"})
    assert exc.value.code == "NOT_FOUND"
    for malo in ("9 OR 1=1", -1, True, None, 1.5):
        with pytest.raises(ComisionesError) as exc:
            comisiones.periodo(rec, malo)
        assert exc.value.code == "INVALID"
    with pytest.raises(ComisionesError):
        _abrir(comisiones, rec, db_conn, turno="madrugada")
    with pytest.raises(ComisionesError):
        _abrir(comisiones, rec, db_conn, sede="Sede que no existe ZZ")
    with pytest.raises(ComisionesError):
        _abrir(comisiones, rec, db_conn, horarios=[{"dia": "Feriado", "hora_inicio": "08:00", "hora_fin": "10:00"}])
    otro_doc = db_conn.execute("SELECT cuil FROM docentes WHERE departamento_id<>1 AND cuil NOT IN (SELECT cuil FROM "
                               "docentes WHERE departamento_id=1) ORDER BY id LIMIT 1").fetchone()[0]
    with pytest.raises(ComisionesError) as exc:
        _abrir(comisiones, rec, db_conn, docentes=[{"cuil": otro_doc, "rol": "JTP",
                                                    "franjas": [{"usar": True, "desde": "08:00", "hasta": "10:00"}]}])
    assert exc.value.code == "INVALID"
    assert _contar(db_conn) == antes and audit_store.events == []


def test_tenant_del_cliente_ignorado(comisiones, records, db_conn):
    """Un institucion_id/departamento_id enviado por el cliente no cambia el ámbito (sale de la sesión)."""
    rec = records["dep"]
    res = _abrir(comisiones, rec, db_conn, institucion_id=2, departamento_id=5, nombre="ZZT")
    fila = db_conn.execute("SELECT institucion_id, departamento_id FROM comisiones WHERE id=%s", [res["id"]]).fetchone()
    assert fila == (1, 1)


# ------------------------------------------------------------------------------------------ validaciones certificadas
def test_validaciones_de_abrir_en_orden(comisiones, records, db_conn, audit_store):
    rec = records["dep"]
    antes = _contar(db_conn)
    casos = [
        ({"nombre": "  "}, "Indicá el nombre o número de comisión."),
        ({"horarios": [{"dia": "Lunes", "hora_inicio": "08:00", "hora_fin": "08:00"}]},
         "Hay uno o más horarios inválidos. Revisá las horas de inicio y finalización."),
        ({"horarios": [{"dia": "Lunes", "hora_inicio": "08:00", "hora_fin": "10:00"}] * 2},
         "Hay horarios repetidos dentro de la nueva comisión."),
        ({"docentes": []}, "Seleccioná al menos un docente para abrir la comisión completa."),
    ]
    for extra, msg in casos:
        with pytest.raises(ComisionesError) as exc:
            _abrir(comisiones, rec, db_conn, **extra)
        assert exc.value.message == msg, extra
    d = _docente(comisiones, rec)
    roles = comisiones.docente_roles(rec, {"contexto": "actual", "cuil": d["cuil"]})["roles"]
    rol = roles[0] if roles else R.ROLES_DOCENTE_COMISION[0]
    sin_franja = [{"cuil": d["cuil"], "rol": rol, "franjas": [{"usar": False, "desde": "08:00", "hasta": "10:00"}]}]
    with pytest.raises(ComisionesError) as exc:
        _abrir(comisiones, rec, db_conn, docentes=sin_franja)
    assert exc.value.message == "Cada docente seleccionado debe cubrir al menos una franja horaria válida de la comisión."
    repetido = [{"cuil": d["cuil"], "rol": rol, "franjas": [{"usar": True, "desde": "08:00", "hasta": "10:00"}]}] * 2
    with pytest.raises(ComisionesError) as exc:
        _abrir(comisiones, rec, db_conn, docentes=repetido)
    assert exc.value.message == "Un mismo docente fue seleccionado más de una vez."
    assert _contar(db_conn) == antes and audit_store.events == []


def test_abrir_optativa_sin_opcion(comisiones, records, db_conn):
    rec = records["dep"]
    for m in comisiones.abrir_materias(rec, {})["materias"]:
        info = comisiones.abrir_materia(rec, {"materia_id": m["materia_id"]})
        if info["es_oe"]:
            with pytest.raises(ComisionesError) as exc:
                _abrir(comisiones, rec, db_conn, materia_id=m["materia_id"], nombre="ZZOE")
            assert exc.value.message == "Seleccioná la opción curricular concreta que se dictará en esta comisión."
            return
    pytest.skip("sin Optativa/Electiva")


def test_abrir_duplicada(comisiones, records, db_conn):
    rec = records["dep"]
    res = _abrir(comisiones, rec, db_conn, nombre="ZZD")
    mid = db_conn.execute("SELECT materia_id FROM comisiones WHERE id=%s", [res["id"]]).fetchone()[0]
    with pytest.raises(ComisionesError) as exc:
        _abrir(comisiones, rec, db_conn, materia_id=mid, nombre="ZZD")
    assert exc.value.message == "La comisión ya existe."


def test_compuertas_de_periodo(comisiones, records, db_conn):
    """Sin período abierto: no se opera ni se corrige; Inscriptos y Sedes siguen disponibles."""
    rec = records["dep"]
    db_conn.execute("UPDATE periodos SET estado='Cerrado' WHERE institucion_id=1 AND departamento_id=1")
    ov = comisiones.overview(rec)
    assert not ov["puede_operar"] and not ov["puede_corregir"] and ov["abierto"] is None
    with pytest.raises(ComisionesError) as exc:
        comisiones.abrir_materias(rec, {})
    assert exc.value.message == "Solo podés abrir comisiones en el período actual abierto." and exc.value.tone == "warning"
    with pytest.raises(ComisionesError) as exc:
        comisiones.comisiones_lista(rec, {"contexto": "modificacion"})
    assert exc.value.message == "Solo podés registrar modificaciones de asignaciones en el período actual abierto."
    with pytest.raises(ComisionesError) as exc:
        comisiones.carga_preview(rec, {"texto": "Código\tComisión\nX\t1"})
    assert exc.value.message == "Solo podés hacer carga rápida de comisiones en el período actual abierto."
    lista = comisiones.comisiones_lista(rec, {"contexto": "edicion"})
    cid = lista["filas"][0]["id"]
    det = comisiones.comision_detalle(rec, {"contexto": "edicion", "comision_id": cid})
    with pytest.raises(ComisionesError) as exc:
        comisiones.agregar_horario(rec, {"comision_id": cid, "dia": "Sábado", "hora_inicio": "08:00",
                                         "hora_fin": "09:00", "huella": det["huella"]})
    assert exc.value.message == "No podés agregar horarios si no hay un período abierto para corrección."
    assert comisiones.inscriptos(rec, HISTORICO) is not None and comisiones.sedes(rec)["sedes"]


def test_inscriptos_en_periodo_cerrado(comisiones, records, db_conn):
    rec = records["dep"]
    d = comisiones.inscriptos(rec, HISTORICO)
    if d["vacio"]:
        pytest.skip("sin asignaturas")
    f = d["filas"][0]
    res = comisiones.guardar_inscriptos(rec, {"periodo_id": HISTORICO, "filas": [
        {"clave": f["clave"], "huella": f["huella"], "cantidad": int(f["cantidad"] or 0) + 7, "cantidad_final": None}]})
    assert res["mensaje"] == "Se actualizaron 1 asignatura/s o código/s del período."
    res = comisiones.guardar_inscriptos(rec, {"periodo_id": HISTORICO, "filas": []})
    assert res == {"mensaje": "No había cambios para guardar.", "tono": "info", "sin_cambios": True}


# ------------------------------------------------------------------------------------------ B12I capa U y capa T
def test_huella_obsoleta_no_escribe(comisiones, records, db_conn, audit_store):
    rec = records["dep"]
    lista = comisiones.comisiones_lista(rec, {"contexto": "edicion"})
    cid = lista["filas"][0]["id"]
    det = comisiones.comision_detalle(rec, {"contexto": "edicion", "comision_id": cid})
    db_conn.execute("UPDATE comisiones SET observaciones='cambio de otra sesión' WHERE id=%s", [cid])
    antes = _contar(db_conn)
    with pytest.raises(ComisionesError) as exc:
        comisiones.agregar_horario(rec, {"comision_id": cid, "dia": "Domingo", "hora_inicio": "08:00",
                                         "hora_fin": "09:00", "huella": det["huella"]})
    assert exc.value.code == "STALE" and "[B12I: get_comisiones]" in exc.value.message
    assert _contar(db_conn) == antes
    assert [(e.outcome, e.error_code, e.metadata.get("coupled_commits")) for e in audit_store.events] == [
        ("FAILED", "StaleDecisionError", 0)]
    sede = comisiones.sedes(rec)["sedes"][0]
    db_conn.execute("UPDATE sedes_institucion SET observaciones='otra' WHERE id=%s", [sede["id"]])
    with pytest.raises(ComisionesError) as exc:
        comisiones.editar_sede(rec, {**{k: sede[k] for k in ("id", "nombre", "direccion", "localidad")},
                                     "estado": "Activa", "huella": sede["huella"]})
    assert exc.value.code == "STALE"


def test_lote_de_nombres_sin_cambios_y_huella(comisiones, records, db_conn):
    rec = records["dep"]
    lista = comisiones.comisiones_lista(rec, {"contexto": "edicion"})
    filas = [{"id": f["id"], "comision": f["nombre_comision"]} for f in lista["filas"]]
    res = comisiones.editar_nombres_lote(rec, {"busqueda": "", "filas": filas, "huella_lote": lista["huella_lote"]})
    assert res["mensaje"] == "No hay cambios de Comisión para guardar."
    filas[0]["comision"] = "ZZ9"
    db_conn.execute("UPDATE comisiones SET nombre_comision='ZZ8' WHERE id=%s", [filas[1]["id"]])
    with pytest.raises(ComisionesError) as exc:
        comisiones.editar_nombres_lote(rec, {"busqueda": "", "filas": filas, "huella_lote": lista["huella_lote"]})
    assert exc.value.code == "STALE"
    assert exc.value.message.startswith("No se pudieron guardar todos los cambios. No se aplicó un lote parcial.\n\n")


def test_lock_solo_en_los_cinco_writers_de_identidad(comisiones, records, db_conn, monkeypatch):
    """B12I capa T: guardar/actualizar comisión, nombre v180, lote v195 y carga v232; NO horarios ni asignaciones."""
    from comisiones.service import LOCK_WRITERS
    assert LOCK_WRITERS == {"guardar_comision", "actualizar_comision", "actualizar_nombre_comision_correccion_v180",
                            "actualizar_nombres_comisiones_lote_v195", "cargar_comisiones_rapidas_lote_v232"}
    assert LOCK_WAIT_SECONDS == 30.0
    rec = records["dep"]
    real = comisiones._consistency_lock
    usados = []

    def espia(scope):
        usados.append("lock")
        return real(scope)

    monkeypatch.setattr(comisiones, "_consistency_lock", espia)
    res = _abrir(comisiones, rec, db_conn, nombre="ZZL")
    assert usados == ["lock"]  # solo guardar_comision (horarios, asignaciones y movimientos sin lock)
    usados.clear()
    det = comisiones.comision_detalle(rec, {"contexto": "edicion", "comision_id": res["id"]})
    comisiones.agregar_horario(rec, {"comision_id": res["id"], "dia": "Sábado", "hora_inicio": "08:00",
                                     "hora_fin": "09:00", "huella": det["huella"]})
    assert usados == []


def _probe():
    import db
    settings = db.load_settings()
    conn = psycopg.connect(settings["database_url"], autocommit=True, connect_timeout=5,
                           application_name="deptit_next_tests_probe")
    db.verify_identity(conn)
    return conn


LOCK_KEY = "deptit_b12i_comision_identidad:1:1"


def test_lock_timeout_controlado_no_escribe(service, repo, db_conn, lock_conn, audit_store):
    repo.departments_rows.extend(dict(d) for d in EXTRA_DEPARTMENTS)
    svc = make_comisiones(service, audit_store, db_conn, lock_connection=lock_conn, lock_wait_seconds=0.3)
    rec = session_for(service, repo, 3)[0]
    antes = _contar(db_conn)
    holder = _probe()
    try:
        holder.execute("SELECT pg_advisory_lock(hashtext(%s))", [LOCK_KEY])
        with pytest.raises(ComisionesError) as exc:
            _abrir(svc, rec, db_conn, nombre="ZZK")
    finally:
        holder.execute("SELECT pg_advisory_unlock(hashtext(%s))", [LOCK_KEY])
        holder.close()
    assert exc.value.status == 409 and exc.value.code == "LOCK"
    assert exc.value.message == ("No se pudo abrir la comisión completa: Hay otra operación concurrente sobre los mismos "
                                 "datos. No se guardó nada: reintentá en unos instantes. [B12I: comision_identidad]")
    assert _contar(db_conn) == antes
    assert (audit_store.events[-1].error_code, audit_store.events[-1].metadata["coupled_commits"]) == (
        "ConsistencyLockError", 0)


def test_lock_espera_hasta_30_segundos_con_reintento_cada_100ms(service, repo, db_conn, lock_conn, audit_store):
    """Reloj falso: reintenta cada 0,1 s y se rinde al superar 30 s (sin esperar de verdad)."""
    repo.departments_rows.extend(dict(d) for d in EXTRA_DEPARTMENTS)
    reloj = {"t": 0.0, "sleeps": 0}

    def sleep(s):
        assert s == 0.1
        reloj["t"] += s
        reloj["sleeps"] += 1

    svc = make_comisiones(service, audit_store, db_conn, lock_connection=lock_conn, clock=lambda: reloj["t"],
                          sleep=sleep)
    rec = session_for(service, repo, 3)[0]
    lista = svc.comisiones_lista(rec, {"contexto": "edicion"})
    filas = [{"id": f["id"], "comision": f["nombre_comision"]} for f in lista["filas"]]
    filas[0]["comision"] = "ZZW"
    holder = _probe()
    try:
        holder.execute("SELECT pg_advisory_lock(hashtext(%s))", [LOCK_KEY])
        with pytest.raises(ComisionesError) as exc:
            svc.editar_nombres_lote(rec, {"busqueda": "", "filas": filas, "huella_lote": lista["huella_lote"]})
    finally:
        holder.execute("SELECT pg_advisory_unlock(hashtext(%s))", [LOCK_KEY])
        holder.close()
    assert exc.value.code == "LOCK" and 299 <= reloj["sleeps"] <= 301 and reloj["t"] >= 30.0


def test_lock_tomado_durante_el_commit_y_liberado(comisiones, records, db_conn, monkeypatch):
    from comisiones import escrituras as E
    rec = records["dep"]
    probe = _probe()
    visto = []
    real = E.guardar_comision

    def espia(u, *a, **k):
        visto.append(probe.execute("SELECT pg_try_advisory_xact_lock(hashtext(%s))", [LOCK_KEY]).fetchone()[0])
        return real(u, *a, **k)

    monkeypatch.setattr(E, "guardar_comision", espia)
    try:
        _abrir(comisiones, rec, db_conn, nombre="ZZH")
        assert visto == [False]  # tomado por la operación
        assert probe.execute("SELECT pg_try_advisory_xact_lock(hashtext(%s))", [LOCK_KEY]).fetchone()[0] is True
    finally:
        probe.close()


# ------------------------------------------------------------------------------------------ B12H
def test_abrir_auditada_por_operacion_y_commit(comisiones, records, db_conn, audit_store):
    _abrir(comisiones, records["dep"], db_conn, nombre="ZZA")
    ops = {}
    for e in audit_rows(db_conn):
        ops.setdefault(str(e["correlation_id"]), []).append(e)
    nombres = [v[0]["operation"] for v in ops.values()]
    assert nombres == ["guardar_comision", "guardar_horario_comision", "guardar_asignacion_docente_comision",
                       "registrar_movimiento", "registrar_movimiento"]
    for v in ops.values():
        assert [e["metadata"]["commit_seq"] for e in v] == list(range(1, len(v) + 1))
        assert all(e["outcome"] == "SUCCESS" and e["audit_mode"] == "IN_TRANSACTION" for e in v)
    horario, asignacion = list(ops.values())[1], list(ops.values())[2]
    # recién creada no tiene asignaciones: sincronizar_horas no muta nada y no hay COMMIT propio (como el certificado)
    assert [e["metadata"]["committing_writer"] for e in horario] == ["guardar_horario_comision"]
    assert [e["metadata"]["committing_writer"] for e in asignacion][:2] == [
        "guardar_asignacion_docente_comision", "guardar_horarios_reales_asignacion"]
    assert list(ops.values())[0][0]["action"] == "comisiones.write"
    assert list(ops.values())[3][0]["action"] == "movimientos.write"


def test_falla_del_movimiento_compensa_la_comision(comisiones, records, db_conn, audit_store, monkeypatch):
    """Como el certificado: la compensación borra la comisión pero no los movimientos ya confirmados."""
    from comisiones import escrituras as E
    llamadas = {"n": 0}
    real = E.registrar_movimiento

    def segundo_falla(u, *a, **k):
        llamadas["n"] += 1
        if llamadas["n"] == 2:
            raise psycopg.errors.InternalError("falla inyectada")
        return real(u, *a, **k)

    monkeypatch.setattr(E, "registrar_movimiento", segundo_falla)
    antes = _contar(db_conn)
    with pytest.raises(ComisionesError) as exc:
        _abrir(comisiones, records["dep"], db_conn, nombre="ZZX")
    assert exc.value.code == "DB_ERROR" and exc.value.message.startswith("No se pudo abrir la comisión completa: ")
    despues = _contar(db_conn)
    assert despues[0] == antes[0] and despues[1] == antes[1] and despues[2] == antes[2]  # compensada
    assert despues[5] == antes[5] + 1  # el movimiento de apertura ya confirmado queda (certificado)
    assert [e.operation for e in audit_store.events if e.outcome == "FAILED"] == ["registrar_movimiento"]
    assert "_b10_revertir_alta_comision_incompleta" in {e["operation"] for e in audit_rows(db_conn)}


def test_auditoria_que_falla_revierte_el_commit(comisiones, records, db_conn, audit_store, monkeypatch):
    def boom(conn, event):
        raise RuntimeError("audit down")

    monkeypatch.setattr(audit, "insert_on", boom)
    antes = _contar(db_conn)
    with pytest.raises(ComisionesError) as exc:
        _abrir(comisiones, records["dep"], db_conn, nombre="ZZY")
    assert exc.value.code == "AUDIT" and _contar(db_conn) == antes
    assert audit_store.events[0].error_code == "AuditPersistenceError:AUDIT_INSERT_FAILED"


def test_post_operation_sin_commits(comisiones, records, db_conn, audit_store):
    """``guardar_horario_comision`` de un horario ya cargado: aviso certificado y ningún COMMIT."""
    from comisiones import escrituras as E
    from comisiones.service import SPEC_GUARDAR_HORARIO
    rec = records["dep"]
    fila = db_conn.execute("SELECT h.comision_id, h.dia, h.hora_inicio, h.hora_fin FROM horarios_comision h JOIN "
                           "comisiones c ON c.id=h.comision_id WHERE c.departamento_id=1 AND c.periodo_id=9 "
                           "ORDER BY h.id LIMIT 1").fetchone()
    scope = comisiones.scope(rec)
    _, avisos = comisiones._op(rec, scope, SPEC_GUARDAR_HORARIO, lambda u: E.guardar_horario_comision(
        u, fila[0], fila[1], fila[2], fila[3], ""), entity_raw=fila[0])
    assert avisos == ["Ese horario ya estaba cargado en la comisión. No se creó un duplicado."]
    assert audit_rows(db_conn) == []
    assert [(e.outcome, e.audit_mode, e.metadata.get("post_reason")) for e in audit_store.events] == [
        ("SUCCESS", "POST_OPERATION", "NO_POOLED_COMMIT")]


# ------------------------------------------------------------------------------------------ carga rápida
def test_carga_rapida_bloqueos(comisiones, records, db_conn):
    rec = records["dep"]
    prev = comisiones.carga_preview(rec, {"texto": "sin datos"})
    assert prev["filas"] == [] and prev["mensajes"][0]["texto"].startswith("No encontré filas con comisión para cargar.")
    texto = "Código\tAsignatura\tComisión\tDía 1\tHora Inicio 1\tHora Fin 1\nZZ-1\tNo existe\tA\tLunes\t08:00\t10:00"
    prev = comisiones.carga_preview(rec, {"texto": texto})
    assert prev["totales"] == {"ok": 0, "advertencia": 0, "duplicada": 0, "error": 1}
    with pytest.raises(ComisionesError) as exc:
        comisiones.carga_ejecutar(rec, {"texto": texto, "confirmar": True, "huella": prev["huella"]})
    assert exc.value.message == "No hay comisiones válidas para cargar."
    malo = base64.b64encode(b"no es un xlsx").decode()
    prev = comisiones.carga_preview(rec, {"texto": "", "excel": malo})
    assert prev["mensajes"][0]["tono"] == "error"
    assert prev["mensajes"][0]["texto"].startswith("No se pudo leer el Excel integral de comisiones: ")
    with pytest.raises(ComisionesError) as exc:
        comisiones.carga_preview(rec, {"excel": "%%%no-base64"})
    assert exc.value.code == "INVALID"


def test_carga_rapida_confirmacion_y_vista_previa_obsoleta(comisiones, records, db_conn, audit_store):
    rec = records["dep"]
    mid = _materia_comun(comisiones, rec)
    info = comisiones.abrir_materia(rec, {"materia_id": mid})
    texto = (f"Código\tAsignatura\tComisión\tTurno\tDía 1\tHora Inicio 1\tHora Fin 1\tModalidad\n"
             f"{info['codigo']}\t{info['asignatura']}\tZZC\tnoche\tLunes\t18:00\t20:00\tPresencial")
    prev = comisiones.carga_preview(rec, {"texto": texto})
    assert prev["totales"]["ok"] + prev["totales"]["advertencia"] == 1
    with pytest.raises(ComisionesError) as exc:
        comisiones.carga_ejecutar(rec, {"texto": texto, "confirmar": False, "huella": prev["huella"]})
    assert exc.value.message == "Primero marcá la confirmación de carga."
    antes = _contar(db_conn)
    with pytest.raises(ComisionesError) as exc:
        comisiones.carga_ejecutar(rec, {"texto": texto, "confirmar": True, "huella": "otra"})
    assert exc.value.code == "STALE" and "[B12I: preparar_preview_comisiones_rapidas]" in exc.value.message
    assert _contar(db_conn) == antes
    res = comisiones.carga_ejecutar(rec, {"texto": texto, "confirmar": True, "huella": prev["huella"]})
    assert res["mensaje"].startswith("Se cargaron 1 comisiones, 1 horarios y 0 asignaciones docentes en ")
    assert res["mensaje"].endswith(" s. Duplicadas omitidas: 0. Errores omitidos: 0.")


# ------------------------------------------------------------------------------------------ HTTP
def login(client, repo, email):
    r = client.post("/auth/login", json={"email": email, "password": repo.passwords[email]}, headers=CSRF)
    assert r.status_code == 200


def clean(response, repo):
    for word in FORBIDDEN:
        assert word not in response.text, word
    for pwd in repo.passwords.values():
        assert pwd not in response.text


def test_http_sesion_csrf_y_respuestas_limpias(http, repo, clock, db_conn):
    assert http.get("/comisiones").status_code == 401
    assert http.post("/comisiones/periodo", json={"periodo_id": ACTUAL}, headers=CSRF).status_code == 401
    login(http, repo, "info@test.local")
    r = http.get("/comisiones")
    assert r.status_code == 200
    clean(r, repo)
    assert http.post("/comisiones/periodo", json={"periodo_id": ACTUAL}).json()["error"]["code"] == "CSRF"
    r = http.post("/comisiones/periodo", json={"periodo_id": ACTUAL}, headers=CSRF)
    assert r.status_code == 200 and not r.json()["vacio"]
    clean(r, repo)
    r = http.post("/comisiones/periodo", json={"periodo_id": "9 OR 1=1"}, headers=CSRF)
    assert r.status_code == 422
    clean(r, repo)
    for ruta in ("alertas", "sedes"):
        r = http.post(f"/comisiones/{ruta}", json={}, headers=CSRF)
        assert r.status_code == 200
        clean(r, repo)
    r = http.post("/comisiones/abrir", json={"materia_id": "x"}, headers=CSRF)
    assert r.status_code == 422
    clean(r, repo)
    r = http.post("/comisiones/edicion/eliminar", json={"comision_id": 1, "confirmar": True, "huella": "x"},
                  headers=CSRF)
    assert r.status_code in (403, 404)
    clean(r, repo)
    r = http.get("/comisiones/modelo-excel")
    assert r.status_code == 200 and r.content[:2] == b"PK"
    assert 'filename="modelo_integral_comisiones.xlsx"' in r.headers["content-disposition"]
    r = http.post("/comisiones/periodo/excel", json={"periodo_id": HISTORICO}, headers=CSRF)
    assert r.status_code == 200 and r.content[:2] == b"PK" and "comisiones_integral_" in r.headers["content-disposition"]
    r = http.post("/comisiones/periodo/excel", json={"periodo_id": 999999}, headers=CSRF)
    assert r.status_code == 404
    clock.advance(30 * 60)
    assert http.get("/comisiones").json()["error"]["code"] == "IDLE_TIMEOUT"


def test_http_solo_lectura(http, repo):
    login(http, repo, "lector@test.local")
    assert http.get("/comisiones").json()["permisos"]["puede_escribir"] is False
    r = http.post("/comisiones/sedes/agregar", json={"nombre": "ZZ", "direccion": "x 1", "localidad": "y"},
                  headers=CSRF)
    assert r.status_code == 403
