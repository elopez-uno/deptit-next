"""Equivalencia de las ESCRITURAS de Materias con el codigo certificado (entry sin cambios) sobre deptit_next_dev.

Cada caso: datos sinteticos (prefijo ``ZZNEXT``) sembrados en un SAVEPOINT externo; el writer certificado corre en un
SAVEPOINT revertido y NEXT en otro, desde el MISMO estado.  Se comparan las 4 tablas de la fuente unica de planes de
la institucion (ids reemplazados por claves naturales) y los mensajes.  Nada se confirma.
"""

from __future__ import annotations

import base64
import io

import pytest
from openpyxl import load_workbook

import unidades_support as U
from materias.service import MateriasError
from materias_support import (  # noqa: F401  (fixtures)
    audit_store, certified_materias, db_conn, materias, session_for, state,
)

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")

INST = 1
ESC = "ZZNEXT Escuela"


@pytest.fixture
def user(service, repo):
    return session_for(service, repo, 3)[0]   # usuario_departamento (institucion 1)


def run_both(conn, certified, nxt):
    out = []
    for fn in (certified, nxt):
        with conn.transaction(force_rollback=True):
            try:
                result, error = fn(), None
            except Exception as exc:  # noqa: BLE001
                result, error = None, exc
            out.append((state(conn, INST), result, error))
    return out


def msg(exc):
    return exc.message if isinstance(exc, MateriasError) else str(exc)


def seed_carrera(conn, nombre, plan="Plan 2099", estado="Activa", escuela=ESC, codigo="ZZ"):
    return conn.execute("INSERT INTO carreras (institucion_id, escuela, codigo, nombre, titulo_otorga, plan_version, "
                        "duracion, estado, observaciones) VALUES (%s,%s,%s,%s,'Título','" + plan + "','4 años',%s,'') "
                        "RETURNING id", [INST, escuela, codigo, nombre, estado]).fetchone()[0]


def seed_materia(conn, carrera_id, codigo, asignatura, *, en_plan=1, anio="1° Año", modo="Automática", grupo=None):
    c = conn.execute("SELECT nombre, escuela, plan_version FROM carreras WHERE id = %s", [carrera_id]).fetchone()
    return conn.execute(
        "INSERT INTO materias (institucion_id, carrera_id, codigo, asignatura, carrera, escuela, anio, dictado, "
        "carga_semanal, carga_total, cuatrimestre, duracion, plan_version, orden, estado, observaciones, en_plan, "
        "comparticion_modo, comparticion_grupo) VALUES (%s,%s,%s,%s,%s,%s,%s,'Presencial',4,64,'1','Cuatrimestral',%s,"
        "NULL,'Activa','',%s,%s,%s) RETURNING id",
        [INST, carrera_id, codigo, asignatura, c[0], c[1], anio, c[2], en_plan, modo, grupo]).fetchone()[0]


def referenced_materia(conn):
    return conn.execute("SELECT m.id, m.carrera_id FROM materias m WHERE m.institucion_id = 1 AND m.en_plan = 1 AND "
                        "EXISTS (SELECT 1 FROM comisiones co WHERE co.materia_id = m.id) ORDER BY m.id LIMIT 1").fetchone()


def huella_plan(materias, record, carrera_id, mid):
    return next(r["huella"] for r in materias.plan(record, {"carrera_id": carrera_id})["plan"] if r["id"] == mid)


def huella_materia(materias, record, mid):
    return materias.materia_detalle(record, {"id": mid})["materia"]["huella"]


def huella_carrera(materias, record, cid):
    return next(c["huella"] for c in materias.overview(record)["carreras"] if c["id"] == cid)


def form(**kw):
    base = dict(codigo="ZZ-901", asignatura="ZZNEXT Materia", anio="2° Año", cuatrimestre="2", dictado="Virtual",
                carga_semanal=6, carga_total=96, duracion="Anual", estado="Activa", observaciones="obs", orden=3)
    base.update(kw)
    return base


# ------------------------------------------------------------------------------------------------ carreras
def test_carrera_alta_editar_equivalent(db_conn, materias, user):
    with db_conn.transaction(force_rollback=True):
        cid = seed_carrera(db_conn, "ZZNEXT Carrera A")
        seed_materia(db_conn, cid, "ZZ-001", "ZZNEXT Uno")
        ns = certified_materias(db_conn, INST)
        datos = dict(escuela=ESC, codigo="ZZB", nombre="ZZNEXT Carrera B", titulo_otorga="Lic.",
                     plan_version="Plan vigente", duracion="5 años", estado="Activa", observaciones="")
        (cs, _, ce), (nst, nr, ne) = run_both(
            db_conn, lambda: ns["guardar_carrera"](*[datos[k] for k in ("escuela", "codigo", "nombre", "titulo_otorga",
                                                                        "plan_version", "duracion", "estado",
                                                                        "observaciones")]),
            lambda: materias.carrera_alta(user, datos))
        assert ce is None and ne is None, ne
        assert nst == cs and nr["mensaje"] == "Carrera / plan registrado correctamente."
        h = huella_carrera(materias, user, cid)
        edit = dict(datos, nombre="ZZNEXT Carrera A2", escuela="ZZNEXT Otra", carrera_id=cid, huella=h, estado="Inactiva")
        (cs, _, ce), (nst, nr, ne) = run_both(
            db_conn, lambda: ns["actualizar_carrera"](cid, edit["escuela"], edit["codigo"], edit["nombre"],
                                                      edit["titulo_otorga"], edit["plan_version"], edit["duracion"],
                                                      edit["estado"], edit["observaciones"]),
            lambda: materias.carrera_editar(user, edit))
    assert ce is None and ne is None, ne
    assert nst == cs and any("ZZNEXT Carrera A2" in m for m in cs["materias"])  # texto sincronizado en materias


@pytest.mark.parametrize("caso", ["vacia", "con_materias_sin_flag", "con_materias_referenciadas", "integral"])
def test_carrera_eliminar_equivalent(db_conn, materias, superadmin_or_user, caso):
    record = superadmin_or_user
    with db_conn.transaction(force_rollback=True):
        if caso == "con_materias_referenciadas":
            mid, cid = referenced_materia(db_conn)
        else:
            cid = seed_carrera(db_conn, "ZZNEXT Borrar")
            if caso != "vacia":
                m1 = seed_materia(db_conn, cid, "ZZ-101", "ZZNEXT Optativa I")
                seed_materia(db_conn, cid, "ZZ-102", "ZZNEXT Dos", en_plan=0)
                op = db_conn.execute("INSERT INTO opciones_curriculares (institucion_id, tipo, nombre, estado) VALUES "
                                     "(1,'Optativa','ZZNEXT Opción','Activa') RETURNING id").fetchone()[0]
                db_conn.execute("INSERT INTO opcion_curricular_materias (institucion_id, opcion_id, materia_id) "
                                "VALUES (1,%s,%s)", [op, m1])
        ns = certified_materias(db_conn, INST)
        flag = caso in ("integral", "con_materias_referenciadas")
        h = huella_carrera(materias, record, cid)
        (cs, _, ce), (nst, nr, ne) = run_both(
            db_conn, lambda: ns["eliminar_carrera"](cid, eliminar_materias=flag),
            lambda: materias.carrera_eliminar(record, {"carrera_id": cid, "huella": h, "confirmar": True,
                                                       "eliminar_materias": flag}))
    assert nst == cs
    if caso in ("vacia", "integral"):
        assert ce is None and ne is None, ne
        assert nr["mensaje"] == "Carrera eliminada."
    else:
        assert ce is not None and msg(ne) == str(ce)


@pytest.fixture
def superadmin_or_user(user):
    return user  # usuario_departamento puede borrar materias (unico dominio con delete)


# ------------------------------------------------------------------------------------------------ materias
@pytest.mark.parametrize("caso", ["nueva", "reactivar", "conflicto_codigo", "sin_carrera_activa"])
def test_materia_alta_equivalent(db_conn, materias, user, caso):
    with db_conn.transaction(force_rollback=True):
        cid = seed_carrera(db_conn, "ZZNEXT Alta", estado="Activa")
        f = form()
        if caso == "reactivar":
            seed_materia(db_conn, cid, "ZZ901", "ZZNEXT Materia", en_plan=0)
        if caso == "conflicto_codigo":
            otro = seed_carrera(db_conn, "ZZNEXT Otra carrera")
            seed_materia(db_conn, otro, "ZZ901", "ZZNEXT Nombre distinto")
        if caso == "sin_carrera_activa":
            db_conn.execute("UPDATE carreras SET estado = 'Inactiva' WHERE id = %s", [cid])
        ns = certified_materias(db_conn, INST)

        def certified():
            return ns["guardar_materia"](cid, f["codigo"], f["asignatura"], f["anio"], f["cuatrimestre"], f["dictado"],
                                         f["carga_semanal"], f["carga_total"], f["duracion"], f["estado"],
                                         f["observaciones"], f["orden"])

        (cs, _, ce), (nst, nr, ne) = run_both(db_conn, certified, lambda: materias.materia_alta(user, dict(f, carrera_id=cid)))
    if caso == "sin_carrera_activa":
        # La UI certificada solo ofrece carreras activas como destino: la API rechaza sin escribir.
        assert isinstance(ne, MateriasError) and ne.code == "NOT_FOUND"
        assert ce is None  # la funcion certificada, llamada directo, no controla el estado de la carrera
        return
    if caso == "conflicto_codigo":
        assert msg(ne) == str(ce) and nst == cs
        return
    assert ce is None and ne is None, ne
    assert nst == cs
    assert nr["mensaje"] == "Materia 'ZZNEXT Materia' agregada correctamente al plan seleccionado."


@pytest.mark.parametrize("modo", ["Automática", "Específica", "Seleccionada"])
def test_materia_editar_two_commits_equivalent(db_conn, materias, user, modo):
    with db_conn.transaction(force_rollback=True):
        c1 = seed_carrera(db_conn, "ZZNEXT C1")
        c2 = seed_carrera(db_conn, "ZZNEXT C2")
        c3 = seed_carrera(db_conn, "ZZNEXT C3")
        m1 = seed_materia(db_conn, c1, "ZZ500", "ZZNEXT Compartida")
        m2 = seed_materia(db_conn, c2, "ZZ500", "ZZNEXT Compartida")
        m3 = seed_materia(db_conn, c3, "ZZ500", "ZZNEXT Compartida")
        ns = certified_materias(db_conn, INST)
        etiqueta = {v: k for k, v in {
            "Compartida automáticamente entre todos los planes donde aparece": "Automática",
            "Específica de esta carrera/plan": "Específica",
            "Compartida únicamente entre planes seleccionados": "Seleccionada"}.items()}[modo]
        seleccion = [m1, m2] if modo == "Seleccionada" else [m1]
        f = form(codigo="ZZ-501", asignatura="ZZNEXT Renombrada")
        h = huella_materia(materias, user, m1)

        def certified():
            ns["guardar_configuracion_comparticion_materia_v137"](m1, modo, seleccion)
            ns["actualizar_materia"](m1, c1, f["codigo"], f["asignatura"], f["anio"], f["cuatrimestre"], f["dictado"],
                                     f["carga_semanal"], f["carga_total"], f["duracion"], f["estado"], f["observaciones"],
                                     f["orden"])

        (cs, _, ce), (nst, nr, ne) = run_both(db_conn, certified, lambda: materias.materia_editar(user, dict(
            f, id=m1, carrera_id=c1, huella=h, comparticion_modo=etiqueta, seleccionados=seleccion)))
    assert ce is None and ne is None, ne
    assert nst == cs and nr["mensaje"] == "Materia actualizada."
    renombradas = sum("ZZNEXT Renombrada" in m for m in cs["materias"])
    assert renombradas == {"Automática": 3, "Específica": 1, "Seleccionada": 2}[modo]
    assert m3


def test_materia_editar_second_commit_failure_keeps_sharing(db_conn, materias, user, audit_store):
    """Igual que el certificado: si la edicion (COMMIT 2) falla, la comparticion (COMMIT 1) ya quedo guardada."""
    with db_conn.transaction(force_rollback=True):
        c1, c2 = seed_carrera(db_conn, "ZZNEXT E1"), seed_carrera(db_conn, "ZZNEXT E2")
        m1 = seed_materia(db_conn, c1, "ZZ600", "ZZNEXT Grupo")
        seed_materia(db_conn, c2, "ZZ600", "ZZNEXT Grupo")
        seed_materia(db_conn, c1, "ZZ601", "ZZNEXT Ocupa codigo")
        h = huella_materia(materias, user, m1)
        with pytest.raises(MateriasError) as exc:  # el codigo ZZ601 ya esta en el plan destino
            materias.materia_editar(user, dict(form(codigo="ZZ601", asignatura="ZZNEXT Ocupa codigo"), id=m1,
                                               carrera_id=c1, huella=h, seleccionados=[],
                                               comparticion_modo="Específica de esta carrera/plan"))
        assert "ya existe dentro de la carrera/plan seleccionado" in exc.value.message
        modo = db_conn.execute("SELECT comparticion_modo FROM materias WHERE id = %s", [m1]).fetchone()[0]
        assert modo == "Específica"
        assert [(e.operation, e.outcome) for e in audit_store.events] == [("actualizar_materia", "FAILED")]


def test_grilla_quitar_eliminar_limpiar_equivalent(db_conn, materias, user):
    with db_conn.transaction(force_rollback=True):
        c1, c2 = seed_carrera(db_conn, "ZZNEXT G1"), seed_carrera(db_conn, "ZZNEXT G2")
        g1 = seed_materia(db_conn, c1, "ZZ700", "ZZNEXT Grilla")
        seed_materia(db_conn, c2, "ZZ700", "ZZNEXT Grilla")
        libre = seed_materia(db_conn, c1, "ZZ701", "ZZNEXT Libre")
        seed_materia(db_conn, c1, "ZZ702", "ZZNEXT Archivada", en_plan=0)
        ns = certified_materias(db_conn, INST)
        h = huella_plan(materias, user, c1, g1)
        (cs, cr, ce), (nst, nr, ne) = run_both(
            db_conn, lambda: ns["actualizar_codigo_nombre_materias_desde_plan"]([{"id": g1, "codigo": "ZZ-799",
                                                                               "asignatura": "ZZNEXT Grilla 2"}]),
            lambda: materias.plan_guardar(user, {"carrera_id": c1, "cambios": [
                {"id": g1, "codigo": "ZZ-799", "asignatura": "ZZNEXT Grilla 2", "huella": h}]}))
        assert ce is None and ne is None, ne
        assert nst == cs and cr["apariciones_actualizadas"] == 2 and "Apariciones actualizadas en planes: 2" in nr["mensaje"]

        ref_id, ref_carrera = referenced_materia(db_conn)
        for mid, cid in ((libre, c1), (ref_id, ref_carrera)):
            hq = huella_plan(materias, user, cid, mid)
            (cs, cr, ce), (nst, nr, ne) = run_both(
                db_conn, lambda: ns["quitar_materia_del_plan"](mid, carrera_id_esperada=cid),
                lambda: materias.plan_quitar(user, {"carrera_id": cid, "confirmar": True,
                                                    "materias": [{"id": mid, "huella": hq}]}))
            assert ce is None and ne is None, ne
            assert nst == cs and cr[0] is True and nr["quitadas"] == 1

        hm = huella_materia(materias, user, g1)
        (cs, _, ce), (nst, nr, ne) = run_both(db_conn, lambda: ns["eliminar_materia"](g1),
                                              lambda: materias.materia_eliminar(user, {"id": g1, "huella": hm,
                                                                                       "confirmar": True}))
        assert ce is None and ne is None, ne
        assert nst == cs and not any("ZZNEXT Grilla" in m for m in cs["materias"])  # las 2 apariciones
        hr = huella_materia(materias, user, ref_id)
        (cs, _, ce), (nst, _, ne) = run_both(db_conn, lambda: ns["eliminar_materia"](ref_id),
                                             lambda: materias.materia_eliminar(user, {"id": ref_id, "huella": hr,
                                                                                      "confirmar": True}))
        assert ce is not None and msg(ne) == str(ce) and nst == cs

        tot = materias.totales(user, {"carrera_id": c1})
        (cs, cr, ce), (nst, nr, ne) = run_both(
            db_conn, lambda: ns["limpiar_registros_materias_fuera_del_plan"](c1),
            lambda: materias.limpiar_fuera_plan(user, {"carrera_id": c1, "confirmar": True,
                                                       "huella": tot["archivadas_huella"]}))
    assert ce is None and ne is None, ne
    assert nst == cs and nr["resumen"] == cr


@pytest.mark.parametrize("reemplazar", [False, True])
def test_carga_rapida_row_by_row_equivalent(db_conn, materias, user, reemplazar):
    with db_conn.transaction(force_rollback=True):
        cid = seed_carrera(db_conn, "ZZNEXT Carga")
        seed_materia(db_conn, cid, "ZZ800", "ZZNEXT Previa")
        texto = "codigo\tasignatura\tanio\tcuatrimestre\tcarga_semanal\tcarga_total\n" \
                "ZZ-810\tZZNEXT Pegada 1\t1\t1\t4\t64\nZZ-811\tZZNEXT Pegada 2\t2\tAnual\t6\t96\n"
        ns = certified_materias(db_conn, INST)

        def certified():
            # Bucle de la UI certificada (entry l. 69256-69302).
            df = ns["parsear_plan_pegado"](texto)
            if reemplazar:
                for mid in ns["get_plan_estudio"](cid)["id"].astype(int).tolist():
                    ok, m = ns["quitar_materia_del_plan"](int(mid), cid)
                    assert ok, m
            cargadas = 0
            for _, row in df.iterrows():
                ns["guardar_materia"](cid, row["codigo"], row["asignatura"],
                                      row["anio"] if row["anio"] in ns["ANIOS"] else "1° Año",
                                      row["cuatrimestre"] if row["cuatrimestre"] in ns["CUATRIMESTRES_MAT"]
                                      else "Sin especificar",
                                      row["dictado"] if row["dictado"] in ns["DICTADOS"] else "Presencial",
                                      int(row["carga_semanal"]), int(row["carga_total"]),
                                      row["duracion"] if row["duracion"] in ns["DURACIONES"] else "Cuatrimestral",
                                      "Activa", "", None if row["orden"] != row["orden"] else int(row["orden"]))
                cargadas += 1
            return f"Se cargaron {cargadas} materias en el plan seleccionado."

        (cs, cr, ce), (nst, nr, ne) = run_both(db_conn, certified, lambda: materias.carga_ejecutar(user, {
            "carrera_id": cid, "texto": texto, "reemplazar": reemplazar, "confirmar": True})["mensaje"])
    assert ce is None and ne is None, ne
    assert nr == cr and nst == cs
    assert any("ZZNEXT Previa" in m for m in cs["materias"]) != reemplazar


# ------------------------------------------------------------------------------------------------ opciones
def test_opciones_writes_equivalent(db_conn, materias, user):
    with db_conn.transaction(force_rollback=True):
        cid = seed_carrera(db_conn, "ZZNEXT Opt")
        esp = seed_materia(db_conn, cid, "ZZ900", "ZZNEXT Optativa I")
        ns = certified_materias(db_conn, INST)
        alta = dict(tipo="Optativa", codigo="ZZO1", nombre="ZZNEXT  Opción   concreta", escuela_oferente="",
                    estado="Activa", observaciones="o")
        (cs, cr, ce), (nst, nr, ne) = run_both(
            db_conn, lambda: ns["guardar_opcion_curricular_v120"](alta["tipo"], alta["codigo"], alta["nombre"],
                                                                  alta["escuela_oferente"], alta["estado"],
                                                                  alta["observaciones"]),
            lambda: materias.opcion_alta(user, alta))
        assert ce is None and ne is None, ne
        assert nst == cs
        ele = dict(alta, tipo="Electiva")
        (cs, _, ce), (nst, _, ne) = run_both(
            db_conn, lambda: ns["guardar_opcion_curricular_v120"]("Electiva", "", "X", "", "Activa", ""),
            lambda: materias.opcion_alta(user, dict(ele, nombre="X", codigo="")))
        # 6A-B3: mensaje con la etiqueta genérica decidida; mismo rechazo y mismo estado
        assert str(ce) == U.MSG_ELECTIVA_CERT and msg(ne) == U.MSG_ELECTIVA and nst == cs

        oid = materias._read(materias.scope(user), lambda r: int(r.opciones()["id"].max()))
        materias.opcion_alta(user, alta)  # alta real (en la transaccion del test) para operar sobre ella
        oid = materias._read(materias.scope(user), lambda r: int(r.opciones()["id"].max()))
        h = next(o["huella"] for o in materias.opciones_consulta(user, {})["opciones"] if o["id"] == oid)
        (cs, cr, ce), (nst, nr, ne) = run_both(
            db_conn, lambda: ns["agregar_vinculos_opcion_curricular_v120"](oid, [esp]),
            lambda: materias.agregar_habilitaciones(user, {"id": oid, "huella": h, "materia_ids": [esp]}))
        assert ce is None and ne is None, ne
        assert nst == cs and cr == 1 and nr["mensaje"] == "Se agregaron 1 habilitación(es)."
        materias.agregar_habilitaciones(user, {"id": oid, "huella": h, "materia_ids": [esp]})
        (cs, _, ce), (nst, _, ne) = run_both(
            db_conn, lambda: ns["actualizar_opcion_curricular_v120"](oid, "Electiva", "ZZO1", "Otro", "Esc", "Activa", ""),
            lambda: materias.opcion_editar(user, {"id": oid, "huella": h, "tipo": "Electiva", "codigo": "ZZO1",
                                                  "nombre": "Otro", "escuela_oferente": "Esc", "estado": "Activa",
                                                  "observaciones": ""}))
        assert ce is not None and msg(ne) == str(ce) and nst == cs
        for fn_c, fn_n in [
            (lambda: ns["quitar_vinculo_opcion_curricular_v120"](oid, esp),
             lambda: materias.quitar_habilitacion(user, {"id": oid, "materia_id": esp, "huella": h})),
            (lambda: ns["eliminar_opcion_curricular_v120"](oid),
             lambda: materias.opcion_eliminar(user, {"id": oid, "huella": h, "confirmar": True})),
        ]:
            (cs, _, ce), (nst, _, ne) = run_both(db_conn, fn_c, fn_n)
            assert ce is None and ne is None, ne
            assert nst == cs
        usada = db_conn.execute("SELECT opcion_curricular_id FROM comisiones WHERE opcion_curricular_id IS NOT NULL "
                                "AND institucion_id = 1 LIMIT 1").fetchone()[0]
        hu = next(o["huella"] for o in materias.opciones_consulta(user, {})["opciones"] if o["id"] == usada)
        (cs, _, ce), (nst, _, ne) = run_both(db_conn, lambda: ns["eliminar_opcion_curricular_v120"](usada),
                                             lambda: materias.opcion_eliminar(user, {"id": usada, "huella": hu,
                                                                                     "confirmar": True}))
    assert ce is not None and msg(ne) == str(ce) and nst == cs


def test_excel_import_equivalent(db_conn, materias, user):
    with db_conn.transaction(force_rollback=True):
        cid = seed_carrera(db_conn, "ZZNEXT Excel")
        esp = seed_materia(db_conn, cid, "ZZ950", "ZZNEXT Optativa II")
        ns = certified_materias(db_conn, INST)
        wb = load_workbook(io.BytesIO(materias.modelo_excel(user)))
        ws = wb["Carga rápida"]
        etiqueta = next(ws_e.value for ws_e in wb["Espacios disponibles"]["J"] if ws_e.value and f"[ID:{esp}]" in
                        str(ws_e.value))
        fila = next(r for r in range(2, ws.max_row + 1) if not ws.cell(r, 3).value)
        for col, val in enumerate(["Optativa", "ZZX1", "ZZNEXT Desde Excel", "", "", "", etiqueta], start=1):
            ws.cell(fila, col, val)
        existente = ws.cell(2, 3).value
        buf = io.BytesIO()
        wb.save(buf)
        contenido = buf.getvalue()
        prev = materias.excel_preview(user, {"contenido_b64": base64.b64encode(contenido).decode()})
        assert any(r["nombre"] == "ZZNEXT Desde Excel" for r in prev["filas"]) and existente

        # 6A-B3: el modelo NEXT rotula "Unidad académica oferente"; el certificado lee el MISMO libro con el
        # encabezado histórico (que NEXT también sigue aceptando, test_e6_b3_unidades_interfaz)
        historico = U.xlsx_con_encabezado_opciones(contenido, U.ENCABEZADO_OPCIONES_HISTORICO)

        def certified():
            return ns["cargar_opciones_curriculares_excel_v124"](ns["leer_excel_carga_rapida_opciones_v124"](historico))

        (cs, cr, ce), (nst, nr, ne) = run_both(db_conn, certified, lambda: materias.excel_cargar(user, {
            "contenido_b64": base64.b64encode(contenido).decode(), "confirmar": True}))
    assert ce is None and ne is None, ne
    assert nst == cs
    assert cr["opciones_creadas"] == 1 and nr["mensaje"].startswith("Carga completada: 1 opción(es) creada(s)")
    sin_id = lambda filas: [{k: v for k, v in f.items() if k != "ID opción"} for f in filas]  # noqa: E731
    cert_detalle = [{(U.DETALLE if k == U.DETALLE_CERT else k): v for k, v in f.items()}
                    for f in cr["detalle"].to_dict(orient="records")]  # 6A-B3: columna "Unidad académica oferente"
    assert sin_id(nr["detalle"]) == sin_id(cert_detalle)  # el ID sale de la secuencia
