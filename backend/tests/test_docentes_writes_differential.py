"""Equivalencia de las ESCRITURAS de Docentes con el codigo certificado (entry sin cambios) sobre deptit_next_dev.

Patron de cada caso: datos sinteticos sembrados en un SAVEPOINT externo; dentro, el writer certificado corre en un
SAVEPOINT que se revierte y luego NEXT corre en otro SAVEPOINT revertido, ambos desde el MISMO estado.  Se comparan las
13 tablas que referencian al docente por CUIL (sin ``id``) y los mensajes.  Nada se confirma (FASE I).
"""

from __future__ import annotations

import json
from datetime import date

import pytest

from docentes.service import DocentesError
from docentes_support import (  # noqa: F401  (fixtures)
    FIXED_TODAY, audit_rows, audit_store, certified_docentes, db_conn, docentes, free_cuil, session_for, state,
)

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")

INST, DEP, DEP2 = 1, 1, 2
PERIOD_DEP1 = 9          # periodo abierto (y ultimo) del departamento 1
COMISION_DEP1 = 306      # comision real del periodo 9 del departamento 1
C_NEW = "27-99000001-4"
C_A = "20-99000002-7"
C_B = "20-99000003-5"
C_C = "27-99000004-8"
C_D = "23-99000005-9"


def digits(*cuils):
    return [c.replace("-", "").replace(" ", "") for c in cuils]


# ------------------------------------------------------------------------------------------------ siembra
def seed_docente(conn, cuil, apellido, nombres, *, dep=DEP, estado="Activo", tipo="Propio", obs="", email="",
                 antiguedad=None, nivel=None):
    conn.execute("INSERT INTO docentes (institucion_id, departamento_id, cuil, nombre, apellido, nombres, legajo, titulo,"
                 " email, telefono, ref_legajo_fisico, estado, tipo_docente, fecha_alta, observaciones, titulo_posgrado,"
                 " antiguedad_anios, nivel_posgrado_salarial) VALUES (%s,%s,%s,%s,%s,%s,'L-1','Lic.',%s,'011','R-1',%s,"
                 "%s,'2025-03-01',%s,'',%s,%s)",
                 [INST, dep, cuil, f"{apellido}, {nombres}", apellido, nombres, email, estado, tipo, obs, antiguedad,
                  nivel])


def seed_designacion(conn, cuil, *, dep=DEP, periodo=PERIOD_DEP1, cargo="JTP", horas=10, estado="Activa"):
    return conn.execute(
        "INSERT INTO designaciones (institucion_id, departamento_id, cuil, cargo, dedicacion, horas, tipo_designacion,"
        " ad_honorem, fecha_desde, fecha_hasta, estado, periodo_id, observaciones, numero_resolucion,"
        " funcion_no_docente, texto_funcion_no_docente) VALUES (%s,%s,%s,%s,'Simple',%s,'Interina','No',"
        "'2026-08-01','2026-12-31',%s,%s,'','',0,'') RETURNING id",
        [INST, dep, cuil, cargo, horas, estado, periodo]).fetchone()[0]


def seed_movimiento(conn, cuil, nombre, *, dep=DEP):
    conn.execute("INSERT INTO movimientos (institucion_id, departamento_id, fecha, tipo_movimiento, cuil, nombre, detalle,"
                 " observaciones, periodo_id, horas_variacion) VALUES (%s,%s,'2026-08-02','Alta de designación',%s,%s,"
                 "'seed','',%s,0)", [INST, dep, cuil, nombre, PERIOD_DEP1 if dep == DEP else None])


def seed_disposicion(conn, cuil, nombre, *, dep=DEP):
    conn.execute("INSERT INTO disposiciones (institucion_id, departamento_id, periodo_id, tipo, numero, cuil, docente,"
                 " variables_json) VALUES (%s,%s,%s,'Designación','D-1',%s,%s,%s)",
                 [INST, dep, PERIOD_DEP1 if dep == DEP else None, cuil, nombre,
                  json.dumps({"cuil": cuil, "docente": nombre, "otro": "x"}, ensure_ascii=False)])


def seed_parametros(conn, cuil, *, dep=DEP, obs="", codigo=""):
    conn.execute("INSERT INTO disposicion_docente_parametros (institucion_id, departamento_id, cuil, observaciones,"
                 " codigo_proyecto) VALUES (%s,%s,%s,%s,%s)", [INST, dep, cuil, obs, codigo])


def seed_asignacion(conn, cuil, *, comision=COMISION_DEP1, estado="Activa"):
    aid = conn.execute("INSERT INTO asignaciones_docentes_comision (institucion_id, departamento_id, comision_id, cuil,"
                       " rol, horas_asignadas, estado, observaciones) VALUES (%s,%s,%s,%s,'JTP',4,%s,'') RETURNING id",
                       [INST, DEP, comision, cuil, estado]).fetchone()[0]
    conn.execute("INSERT INTO horarios_asignacion_docente_comision (institucion_id, departamento_id, asignacion_id, dia,"
                 " hora_inicio, hora_fin, horas) VALUES (%s,%s,%s,'Lunes','08:00','10:00',2)", [INST, DEP, aid])
    return aid


def seed_investigacion(conn, cuil):
    conn.execute("INSERT INTO investigacion_docente (institucion_id, departamento_id, periodo_id, cuil, nombre_proyecto,"
                 " rol, horas_asignadas, estado_asignacion) VALUES (%s,%s,%s,%s,'P-seed','Integrante',2,'Activa')",
                 [INST, DEP, PERIOD_DEP1, cuil])


def seed_consulta(conn, cuil):
    conn.execute("INSERT INTO estado_consulta_designacion (institucion_id, departamento_id, periodo_id, cuil, estado,"
                 " fecha_actualizacion) VALUES (%s,%s,%s,%s,'Consulta Enviada','2026-09-01')",
                 [INST, DEP, PERIOD_DEP1, cuil])


def seed_disposicion_designacion(conn, cuil, designacion_id):
    conn.execute("INSERT INTO disposicion_docente_designaciones (institucion_id, departamento_id, designacion_id, cuil,"
                 " cargo) VALUES (%s,%s,%s,%s,'JTP')", [INST, DEP, designacion_id, cuil])


def seed_prestamo(conn, cuil, *, dep=DEP, origen="Departamento de Administración, Economía y Contabilidad"):
    conn.execute("INSERT INTO prestamos_docentes (institucion_id, departamento_id, periodo_id, cuil, departamento_origen,"
                 " fecha_desde, estado, observaciones) VALUES (%s,%s,%s,%s,%s,'2026-08-01','Activo','')",
                 [INST, dep, PERIOD_DEP1, cuil, origen])


# ------------------------------------------------------------------------------------------------ comparacion
def run_both(conn, cuils, certified, nxt):
    """(estado, resultado | excepcion) del certificado y de NEXT, cada uno en un SAVEPOINT revertido."""
    out = []
    for fn in (certified, nxt):
        with conn.transaction(force_rollback=True):
            try:
                result = fn()
                error = None
            except Exception as exc:  # noqa: BLE001
                result, error = None, exc
            out.append((state(conn, digits(*cuils)), result, error))
    return out


def message(exc):
    return exc.message if isinstance(exc, DocentesError) else str(exc)


def huella(docentes, record, cuil):
    return next(r["huella"] for r in docentes.overview(record)["docentes"] if r["cuil"] == cuil)


def ui_edit_movement(ns, estado_anterior, nuevo_estado, nuevo_cuil, nombre, periodo_id):
    """Movimiento que la UI certificada registra tras ``actualizar_docente`` (entry l. 60607-60631)."""
    bajas = ["Renunciado", "Jubilado", "Fallecido"]
    if estado_anterior not in bajas and nuevo_estado in bajas:
        ns["registrar_movimiento"]("Baja de docente", nuevo_cuil, nombre,
                                   f"Se cambió el estado del docente de {estado_anterior} a {nuevo_estado}.",
                                   periodo_id=periodo_id)
    elif estado_anterior in bajas and nuevo_estado == "Activo":
        ns["registrar_movimiento"]("Alta de docente", nuevo_cuil, nombre,
                                   f"Se reactivó el docente. Estado anterior: {estado_anterior}.", periodo_id=periodo_id)
    else:
        ns["registrar_movimiento"]("Edición de docente", nuevo_cuil, nombre,
                                   "Se modificaron datos del docente en la base maestra.", periodo_id=periodo_id)


@pytest.fixture
def user_dep(service, repo):
    return session_for(service, repo, 3)[0]   # usuario_departamento, departamento 1


@pytest.fixture
def superadmin(service, repo):
    record = session_for(service, repo, 1)[0]
    service.set_context(record, INST, DEP, False)
    return record


# ------------------------------------------------------------------------------------------------ alta
def test_alta_docente_propio_equivalent(db_conn, docentes, user_dep):
    free_cuil(db_conn, C_NEW)
    ns = certified_docentes(db_conn, INST, DEP)
    datos = dict(apellido="Pérez ", nombres=" Ana", cuil=" 27-99000001-4 ", legajo="L9", titulo="Lic.",
                 titulo_posgrado="Mg.", nivel_posgrado_salarial="Magíster", antiguedad_anios=5, email="ana@uno.edu.ar",
                 telefono="011", ref_legajo_fisico="R9", fecha_alta="2026-10-01", observaciones="obs alta")

    def certified():
        cuil = ns["limpiar_cuil"](datos["cuil"])
        ns["guardar_docente"](cuil, datos["apellido"], datos["nombres"], datos["legajo"], datos["titulo"],
                              datos["titulo_posgrado"], datos["email"], datos["telefono"], datos["ref_legajo_fisico"],
                              "Activo", "Propio", date(2026, 10, 1), datos["observaciones"], antiguedad_anios=5,
                              nivel_posgrado_salarial="Magíster")
        ns["registrar_movimiento"]("Alta de docente", cuil, ns["nombre_completo"](datos["apellido"], datos["nombres"]),
                                   "Se registró el docente en la base maestra.", datos["observaciones"],
                                   periodo_id=PERIOD_DEP1)

    (cs, _, ce), (ns_, nr, ne) = run_both(db_conn, [C_NEW], certified, lambda: docentes.alta(user_dep, datos))
    assert ce is None and ne is None, ne
    assert ns_ == cs and len(cs["docentes"]) == 1 and len(cs["movimientos"]) == 1
    assert nr["mensaje"] == "Docente registrado correctamente."


# ------------------------------------------------------------------------------------------------ edicion v168
def _seed_shared(conn):
    """C_A en los departamentos 1 y 2 (docente compartido) con movimientos, disposicion y parametros."""
    for c in (C_A, C_B, C_C):
        free_cuil(conn, c)
    seed_docente(conn, C_A, "Gómez", "Luis", obs="local 1", estado="Activo", antiguedad=3, nivel="Doctor")
    seed_docente(conn, C_A, "Gómez", "Luis", dep=DEP2, obs="local 2", estado="Licencia", tipo="Prestado")
    seed_movimiento(conn, C_A, "Gómez, Luis")
    seed_movimiento(conn, C_A, "Gómez, Luis", dep=DEP2)
    seed_disposicion(conn, C_A, "Gómez, Luis", dep=DEP2)
    seed_parametros(conn, C_A, obs="param viejo")


EDITS = {
    "datos_y_estado": dict(cuil=C_A, apellido="Gómez Ruiz", nombres="Luis", estado="Licencia", nivel="doctora",
                           antig=4, email="luis@uno.edu.ar"),
    "baja": dict(cuil=C_A, apellido="Gómez", nombres="Luis", estado="Renunciado", nivel="", antig=None, email=""),
    "formato_cuil": dict(cuil="20990000027", apellido="Gómez", nombres="Luis", estado="Activo", nivel="Doctor",
                         antig=3, email=""),
    "cambio_cuil": dict(cuil=C_B, apellido="Gómez", nombres="Luis A.", estado="Activo", nivel="Doctor", antig=3,
                        email=""),
}


@pytest.mark.parametrize("caso", sorted(EDITS))
def test_edicion_equivalent(db_conn, docentes, user_dep, caso):
    e = EDITS[caso]
    with db_conn.transaction(force_rollback=True):
        _seed_shared(db_conn)
        if caso == "cambio_cuil":
            # designacion vieja + misma designacion ya recreada con el CUIL nuevo (se deduplica), asignacion, etc.
            d_old = seed_designacion(db_conn, C_A)
            seed_designacion(db_conn, C_B)
            seed_designacion(db_conn, C_A, cargo="Adjunto", horas=20)
            seed_disposicion_designacion(db_conn, C_A, d_old)
            seed_asignacion(db_conn, C_A)
            seed_investigacion(db_conn, C_A)
            seed_consulta(db_conn, C_A)
            seed_parametros(db_conn, C_B, codigo="P-nuevo")
        ns = certified_docentes(db_conn, INST, DEP)
        h = huella(docentes, user_dep, C_A)
        base = dict(legajo="L-1", titulo="Lic.", titulo_posgrado="", telefono="011", ref_legajo_fisico="R-1",
                    tipo_docente="Propio", observaciones="editado")

        def certified():
            ns["actualizar_docente"](C_A, e["cuil"], e["apellido"], e["nombres"], base["legajo"], base["titulo"],
                                     base["titulo_posgrado"], e["email"], base["telefono"], base["ref_legajo_fisico"],
                                     e["estado"], base["tipo_docente"], base["observaciones"],
                                     antiguedad_anios=e["antig"], nivel_posgrado_salarial=e["nivel"])
            ui_edit_movement(ns, "Activo", e["estado"], e["cuil"], ns["nombre_completo"](e["apellido"], e["nombres"]),
                             PERIOD_DEP1)

        def nxt():
            return docentes.editar(user_dep, dict(base, cuil_original=C_A, huella=h, apellido=e["apellido"],
                                                  nombres=e["nombres"], cuil=e["cuil"], estado=e["estado"],
                                                  nivel_posgrado_salarial=e["nivel"], antiguedad_anios=e["antig"],
                                                  email=e["email"]))

        (cs, _, ce), (nst, nr, ne) = run_both(db_conn, [C_A, C_B], certified, nxt)
    assert ce is None and ne is None, (ce, ne)
    assert nst == cs
    if caso == "cambio_cuil":
        assert cs["docentes"] and all(C_B in r for r in cs["docentes"])
        assert "Se migraron" in nr["mensaje"]


@pytest.mark.parametrize("caso", ["destino_existente", "prestamo_bloquea", "nivel_invalido"])
def test_edicion_rechazos_equivalent(db_conn, docentes, user_dep, caso):
    with db_conn.transaction(force_rollback=True):
        _seed_shared(db_conn)
        destino, nivel = C_B, "Doctor"
        if caso == "destino_existente":
            seed_docente(db_conn, C_B, "Otro", "Docente", dep=DEP2)
        elif caso == "prestamo_bloquea":
            seed_prestamo(db_conn, C_A, dep=DEP2)
        else:
            destino, nivel = C_A, "Licenciado"
        ns = certified_docentes(db_conn, INST, DEP)
        h = huella(docentes, user_dep, C_A)
        args = dict(legajo="L-1", titulo="Lic.", titulo_posgrado="", telefono="011", ref_legajo_fisico="R-1",
                    tipo_docente="Propio", observaciones="x", apellido="Gómez", nombres="Luis", email="",
                    estado="Activo", antiguedad_anios=None)

        def certified():
            ns["actualizar_docente"](C_A, destino, args["apellido"], args["nombres"], args["legajo"], args["titulo"],
                                     args["titulo_posgrado"], args["email"], args["telefono"],
                                     args["ref_legajo_fisico"], args["estado"], args["tipo_docente"],
                                     args["observaciones"], antiguedad_anios=None, nivel_posgrado_salarial=nivel)

        def nxt():
            return docentes.editar(user_dep, dict(args, cuil_original=C_A, huella=h, cuil=destino,
                                                  nivel_posgrado_salarial=nivel))

        (cs, _, ce), (nst, _, ne) = run_both(db_conn, [C_A, C_B], certified, nxt)
    assert ce is not None and ne is not None
    assert message(ne) == str(ce)
    assert nst == cs  # nada cambio en ninguno de los dos


# ------------------------------------------------------------------------------------------------ eliminacion
@pytest.mark.parametrize("caso", ["sin_cargas", "con_cargas_rechazo", "integral"])
def test_eliminar_equivalent(db_conn, docentes, superadmin, caso):
    with db_conn.transaction(force_rollback=True):
        free_cuil(db_conn, C_C)
        seed_docente(db_conn, C_C, "Ruiz", "Eva")
        seed_docente(db_conn, C_C, "Ruiz", "Eva", dep=DEP2)  # el mismo CUIL en otro departamento NO se toca
        seed_movimiento(db_conn, C_C, "Ruiz, Eva")
        seed_movimiento(db_conn, C_C, "Ruiz, Eva", dep=DEP2)
        seed_parametros(db_conn, C_C)
        seed_consulta(db_conn, C_C)
        if caso != "sin_cargas":
            d = seed_designacion(db_conn, C_C)
            seed_designacion(db_conn, C_C, dep=DEP2, periodo=None)
            seed_disposicion_designacion(db_conn, C_C, d)
            seed_asignacion(db_conn, C_C)
            seed_investigacion(db_conn, C_C)
        ns = certified_docentes(db_conn, INST, DEP)
        h = huella(docentes, superadmin, C_C)
        integral = caso == "integral"
        horarios_antes = db_conn.execute("SELECT count(*) FROM horarios_asignacion_docente_comision").fetchone()[0]

        def certified():
            return ns["eliminar_docente"](C_C, eliminar_cargas_vinculadas=integral)

        def nxt():
            res = docentes.eliminar(superadmin, {"cuil": C_C, "huella": h, "confirmar": True, "integral": integral})
            res["horarios"] = db_conn.execute("SELECT count(*) FROM horarios_asignacion_docente_comision").fetchone()[0]
            return res

        (cs, cr, ce), (nst, nr, ne) = run_both(db_conn, [C_C], certified, nxt)
    if caso == "con_cargas_rechazo":
        assert message(ne) == str(ce)
    else:
        assert ce is None and ne is None, ne
        assert nr["resumen"] == cr
        assert nr["mensaje"].startswith("Docente eliminado únicamente del departamento actual.")
        if integral:
            assert nr["horarios"] == horarios_antes - 1
    assert nst == cs
    assert any("departamento_id\": 2" in r for r in cs["docentes"])  # la ficha del departamento 2 sigue


# ------------------------------------------------------------------------------------------------ prestamos
def test_alta_prestado_y_finalizar_equivalent(db_conn, docentes, user_dep):
    with db_conn.transaction(force_rollback=True):
        free_cuil(db_conn, C_D)
        seed_docente(db_conn, C_D, "Paz", "Juan", dep=DEP2, antiguedad=9, nivel="Especialista")
        ns = certified_docentes(db_conn, INST, DEP)
        origen = db_conn.execute("SELECT nombre FROM departamentos WHERE id = %s", [DEP2]).fetchone()[0]
        obs = f"Docente prestado desde {origen}. No posee designación local en este departamento."

        def certified_alta():
            df = ns["get_docentes_otros_departamentos_para_prestamo"]()
            row_p = df[df["cuil"] == C_D].iloc[0].to_dict()
            ns["_guardar_docente_local_desde_registro_existente"](row_p, "Prestado", obs)
            ns["registrar_prestamo_docente_v174"](C_D, PERIOD_DEP1, origen, obs, FIXED_TODAY)
            ns["registrar_movimiento"]("Alta de docente prestado", C_D, "Paz, Juan",
                                       f"Se incorporó como prestado desde {origen} exclusivamente para 2026-2, sin "
                                       "designación local.", obs, periodo_id=PERIOD_DEP1)

        def next_alta():
            return docentes.prestado(user_dep, {"flujo": "selector", "cuil": C_D, "departamento_origen": origen})

        (cs, _, ce), (nst, nr, ne) = run_both(db_conn, [C_D], certified_alta, next_alta)
        assert ce is None and ne is None, ne
        assert nst == cs and nr["mensaje"].startswith("Docente prestado registrado para 2026-2.")

        # Finalizar: sobre el prestamo ya registrado y una asignacion activa en una comision del periodo.
        docentes.prestado(user_dep, {"flujo": "selector", "cuil": C_D, "departamento_origen": origen})
        seed_asignacion(db_conn, C_D)
        h = huella(docentes, user_dep, C_D)

        def certified_fin():
            res = ns["finalizar_prestamo_docente_v174"](C_D, PERIOD_DEP1, date(2026, 10, 20), "fin")
            ns["registrar_movimiento"]("Finalización de préstamo docente", C_D, "Paz, Juan",
                                       f"Finalizó el préstamo recibido en 2026-2 el 2026-10-20. Asignaciones en comisión "
                                       f"finalizadas: {res.get('asignaciones_finalizadas', 0)}.", "fin",
                                       periodo_id=PERIOD_DEP1)
            return res

        def next_fin():
            return docentes.finalizar_prestamo(user_dep, {"cuil": C_D, "huella": h, "fecha_fin": "2026-10-20",
                                                          "observaciones": "fin", "confirmar": True})

        (cs, cr, ce), (nst, nr, ne) = run_both(db_conn, [C_D], certified_fin, next_fin)
    assert ce is None and ne is None, ne
    assert cr == {"cambio": True, "asignaciones_finalizadas": 1}
    assert nst == cs and nr["mensaje"] == ("Préstamo finalizado. El docente ya no integra el plantel operativo del "
                                           "período abierto.")


# ------------------------------------------------------------------------------------------------ CUIL huerfano
def test_reparar_cuil_huerfano_equivalent(db_conn, docentes, user_dep):
    with db_conn.transaction(force_rollback=True):
        for c in (C_A, C_B):
            free_cuil(db_conn, c)
        seed_docente(db_conn, C_A, "Gómez", "Luis")
        seed_designacion(db_conn, C_B)            # carga con el CUIL anterior (huerfano)
        seed_movimiento(db_conn, C_B, "Gomez Luis")
        seed_designacion(db_conn, C_A)            # la misma designacion ya recreada: el duplicado viejo se borra
        ns = certified_docentes(db_conn, INST, DEP)
        h = huella(docentes, user_dep, C_A)

        def certified():
            return ns["migrar_referencias_cuil_v168"](C_B, C_A, nombre_destino="Gómez, Luis")

        def nxt():
            return docentes.reparar_cuil(user_dep, {"cuil": C_A, "huella": h, "cuil_huerfano": C_B,
                                                    "confirmar": True})

        (cs, cr, ce), (nst, nr, ne) = run_both(db_conn, [C_A, C_B], certified, nxt)
    assert ce is None and ne is None, ne
    assert nst == cs
    assert nr["mensaje"] == (f"CUIL anterior reparado. Se migraron {cr['actualizados']} referencia/s y se eliminaron "
                             f"{cr['duplicados_eliminados']} duplicado/s viejo/s. El CUIL anterior ya no queda asociado "
                             "a ninguna carga conocida.")


# ------------------------------------------------------------------------------------------------ carga rapida
def test_carga_rapida_equivalent(db_conn, docentes, user_dep):
    with db_conn.transaction(force_rollback=True):
        for c in (C_A, C_NEW):
            free_cuil(db_conn, c)
        seed_docente(db_conn, C_A, "Gómez", "Luis", tipo="Prestado", antiguedad=7, nivel="Doctor")
        seed_docente(db_conn, C_A, "Gómez", "Luis", dep=DEP2, antiguedad=7, nivel="Doctor")
        texto = (f"CUIL\tApellido\tNombres\tEmail\tEstado\n{C_NEW}\tNueva\tAna\ta@b.com\t\n"
                 f"20990000027\tGómez\tLuis Alberto\t\tLicencia\n{C_NEW}\tRepetida\tFila\t\t\n")
        ns = certified_docentes(db_conn, INST, DEP)

        def certified():
            # Bucle de la UI certificada (entry l. 61704-61757) con "actualizar existentes" confirmado.
            df = ns["parsear_docentes_pegados"](texto)
            assert not ns["detectar_docentes_duplicados_carga"](df).empty
            cargados = actualizados = omitidos = 0
            vistos = set()
            for _, row in df.iterrows():
                cuil_row = ns["limpiar_cuil"](row.get("cuil", ""))
                if not cuil_row or cuil_row in vistos:
                    omitidos += 1
                    continue
                vistos.add(cuil_row)
                t = {k: ns["limpiar_texto_tabla"](row.get(k, "")) for k in (
                    "apellido", "nombres", "legajo", "titulo", "titulo_posgrado", "email", "telefono",
                    "ref_legajo_fisico", "estado", "observaciones")}
                estado = t["estado"] or "Activo"
                nombre = ns["nombre_completo"](t["apellido"], t["nombres"])
                if not ns["docente_existe"](cuil_row).empty:
                    ns["actualizar_docente"](cuil_row, cuil_row, t["apellido"], t["nombres"], t["legajo"],
                                             t["titulo"], t["titulo_posgrado"], t["email"], t["telefono"],
                                             t["ref_legajo_fisico"], estado, "Propio", t["observaciones"])
                    ns["registrar_movimiento"]("Actualización de docente existente", cuil_row, nombre,
                                               "Se actualizó el docente mediante carga rápida.", t["observaciones"],
                                               periodo_id=PERIOD_DEP1)
                    actualizados += 1
                else:
                    ns["guardar_docente"](cuil_row, t["apellido"], t["nombres"], t["legajo"], t["titulo"],
                                          t["titulo_posgrado"], t["email"], t["telefono"], t["ref_legajo_fisico"],
                                          estado, observaciones=t["observaciones"])
                    ns["registrar_movimiento"]("Alta de docente", cuil_row, nombre,
                                               "Se registró el docente mediante carga rápida.", t["observaciones"],
                                               periodo_id=PERIOD_DEP1)
                    cargados += 1
            return f"Carga finalizada. Nuevos: {cargados}. Actualizados: {actualizados}. Omitidos: {omitidos}."

        def nxt():
            return docentes.carga_ejecutar(user_dep, texto, True)["mensaje"]

        (cs, cr, ce), (nst, nr, ne) = run_both(db_conn, [C_A, C_NEW], certified, nxt)
    assert ce is None and ne is None, ne
    assert nr == cr == "Carga finalizada. Nuevos: 1. Actualizados: 1. Omitidos: 1."
    assert nst == cs
    # efecto certificado replicado: antiguedad NULL, posgrado vacio y tipo Propio en el registro actualizado
    assert any('"antiguedad_anios": null' in r and '"tipo_docente": "Propio"' in r for r in cs["docentes"])
