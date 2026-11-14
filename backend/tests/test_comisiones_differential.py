"""Diferenciales de LECTURA de Comisiones: lecturas de NEXT (``Lector``) vs las funciones efectivas del certificado
(``certified_comisiones``) sobre los mismos datos reales de deptit_next_dev, en periodos actuales e historicos de varios
departamentos.  Incluye plantel historico (v183/v182), docentes disponibles y cargos, superposicion del candidato,
composicion/duplicados, inscriptos v248, capacidad de proyectos v184, vista previa de la carga rapida (texto y Excel) y
los dos libros Excel (comparacion estructural celda a celda).  Todo en una transaccion que se revierte."""

from __future__ import annotations

from io import BytesIO

import pandas as pd
import psycopg
import pytest

import unidades_support as U
from comisiones import carga as C
from comisiones import excel as X
from comisiones import proyectos as P
from comisiones import rules as R
from comisiones.lecturas import Lector
from comisiones.repository import ComisionesRepository
from comisiones.service import records
from comisiones_support import FIXED_NOW, FIXED_TODAY, certified_comisiones, db_conn  # noqa: F401  (fixtures)

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning", "ignore::DeprecationWarning")

# (departamento, periodos): actuales e historicos con comisiones en deptit_next_dev.
CASOS = [(1, [5, 9]), (2, [1, 11]), (9, [3, 14])]


def _sin_orden_detalle(df):
    """Etapa 5 / Tanda C (C1): el orden de las partes de ``detalle_designaciones`` del certificado (l. 4701 y plantel
    historico sin desempate por ``d.id``) es el orden fisico de las filas; NEXT ordena por ``d.id``
    (test_e5_c_determinismo_performance).  Lo mismo en las listas de docentes activos (``cargo`` / ``dedicacion`` /
    ``cargo_final`` concatenados con " / " en el orden de las designaciones).  Se comparan las partes como
    multiconjunto; todo lo demas, exacto."""
    if isinstance(df, pd.DataFrame):
        df = df.copy()
        for col, sep in (("detalle_designaciones", " | "), ("cargo", " / "), ("dedicacion", " / "), ("cargo_final", " / ")):
            if col in df.columns:
                df[col] = df[col].map(lambda v, s=sep: s.join(sorted(v.split(s))) if isinstance(v, str) else v)
    return df


def igual(a, b, nombre):
    if isinstance(a, pd.DataFrame) or isinstance(b, pd.DataFrame):
        a, b = _sin_orden_detalle(a), _sin_orden_detalle(b)
        pd.testing.assert_frame_equal(a.reset_index(drop=True), b.reset_index(drop=True), check_dtype=True, obj=nombre)
    else:
        assert a == b, nombre


def ambos(fa, fb, nombre):
    try:
        ra, ea = fa(), None
    except psycopg.Error:
        raise
    except Exception as e:
        ra, ea = None, f"{type(e).__name__}: {e}"
    try:
        rb, eb = fb(), None
    except psycopg.Error:
        raise
    except Exception as e:
        rb, eb = None, f"{type(e).__name__}: {e}"
    assert ea == eb, (nombre, ea, eb)
    if ea is None:
        igual(ra, rb, nombre)


@pytest.fixture(params=CASOS, ids=lambda c: f"dep{c[0]}")
def caso(request, db_conn):
    dep, pids = request.param
    ns = certified_comisiones(db_conn, 1, dep)
    L = Lector(ComisionesRepository(db_conn, 1, dep), FIXED_TODAY)
    return dep, pids, ns, L


def test_catalogos_comisiones_y_sedes(caso):
    dep, pids, ns, L = caso
    igual(L.materias_para_comisiones(), ns["get_materias_para_comisiones"](), "materias_para_comisiones")
    igual(L.comisiones(), ns["get_comisiones"](), "comisiones")
    igual(L.sedes_institucionales(), ns["get_sedes_institucionales"](), "sedes")
    igual(L.opciones_sedes_comision(), ns["opciones_sedes_comision"](), "opciones sedes")


def test_lecturas_por_periodo_y_por_comision(caso):
    dep, pids, ns, L = caso
    for pid in pids:
        for fn, cert in [("comisiones_integradas_periodo", "get_comisiones_integradas_periodo"),
                         ("horarios_comisiones_periodo", "get_horarios_comisiones_periodo"),
                         ("asignaciones_comisiones_periodo", "get_asignaciones_comisiones_periodo"),
                         ("superposiciones_periodo", "get_superposiciones_periodo"),
                         ("comisiones_sin_docentes_periodo", "get_comisiones_sin_docentes_periodo")]:
            igual(getattr(L, fn)(pid), ns[cert](pid), f"p{pid} {fn}")
        op_n, df_n = L.opciones_comisiones(periodo_id=pid, solo_activas=False)
        op_c, df_c = ns["get_opciones_comisiones"](periodo_id=pid, solo_activas=False)
        igual(op_n, op_c, f"p{pid} opciones")
        igual(df_n, df_c, f"p{pid} opciones df")
        for cid in L.comisiones(periodo_id=pid)["id"].tolist()[:15]:
            igual(L.horarios_comision(cid), ns["get_horarios_comision"](cid), f"c{cid} horarios")
            igual(L.asignaciones_comision(cid), ns["get_asignaciones_comision"](cid), f"c{cid} asignaciones")
            igual(L.materias_conceptuales_comision_v122(cid), ns["get_materias_conceptuales_comision_v122"](cid),
                  f"c{cid} composicion")
            igual(L.movimientos_comision_en_curso(cid, pid), ns["get_movimientos_comision_en_curso"](cid, pid),
                  f"c{cid} movimientos")
            for aid in ns["get_asignaciones_comision"](cid).get("id", pd.Series(dtype=int)).tolist()[:2]:
                igual(L.horarios_reales_asignacion(aid), ns["get_horarios_reales_asignacion"](aid), f"a{aid} franjas")


def test_plantel_docentes_roles_y_superposicion_del_candidato(caso):
    """Periodo actual (designacion fisica v233/v234) e historico (foto v182/v183, prestados vigentes al cierre)."""
    dep, pids, ns, L = caso
    candidatos = [[{"dia": "Lunes", "hora_inicio": "08:00", "hora_fin": "12:00"},
                   {"dia": "MIÉRCOLES", "hora_inicio": "14:00", "hora_fin": "18:30"}],
                  [{"dia": "martes", "hora_inicio": "18:00", "hora_fin": "22:00"},
                   {"dia": "Jueves", "hora_inicio": "x", "hora_fin": "10:00"}]]
    for pid in pids:
        igual(L.plantel_periodo(pid), ns["get_plantel_periodo"](pid), f"p{pid} plantel")
        docs = L.docentes_activos_para_comisiones(pid)
        igual(docs, ns["get_docentes_activos_para_comisiones"](pid), f"p{pid} docentes")
        coms = L.comisiones(periodo_id=pid, solo_activas=False)
        excl = [None] + ([] if coms.empty else [int(coms.iloc[0]["id"])])
        for cuil in docs["cuil"].astype(str).tolist()[:6]:
            ambos(lambda: L.roles_docente_periodo(cuil, pid), lambda: ns["get_roles_docente_periodo"](cuil, pid),
                  f"p{pid} roles {cuil}")
            ambos(lambda: L.es_docente_prestado_local(cuil), lambda: ns["es_docente_prestado_local"](cuil),
                  f"prestado {cuil}")
            ambos(lambda: L.prestamo_docente_activo_v174(cuil, pid), lambda: ns["prestamo_docente_activo_v174"](cuil, pid),
                  f"prestamo {cuil}")
            for cand in candidatos:
                for ex in excl:
                    ambos(lambda: L.detectar_superposiciones_horarios_candidato(cuil, pid, cand, excluir_comision_id=ex),
                          lambda: ns["detectar_superposiciones_horarios_candidato"](cuil, pid, cand,
                                                                                    excluir_comision_id=ex),
                          f"p{pid} superposicion {cuil} ex{ex}")


def test_composicion_opciones_y_duplicados(caso):
    dep, pids, ns, L = caso
    mats = ns["get_materias_para_comisiones"]()
    for mid in mats["materia_id"].tolist()[::40]:
        ambos(lambda: L.opciones_curriculares_para_materia_v120(mid),
              lambda: ns["get_opciones_curriculares_para_materia_v120"](mid), f"opciones {mid}")
        ambos(lambda: L.preparar_vinculos_multiples_materias_comision_v122(mid),
              lambda: ns["preparar_vinculos_multiples_materias_comision_v122"](mid), f"v122 {mid}")
        ambos(lambda: L.descripcion_materias_comision_v122(mid), lambda: ns["descripcion_materias_comision_v122"](mid),
              f"descripcion {mid}")
    oe = mats[mats.apply(lambda r: ns["es_materia_optativa_electiva"](r["codigo"], r["asignatura"]), axis=1)]
    for mid in oe["materia_id"].tolist()[:4]:
        ops = ns["get_opciones_curriculares_para_materia_v120"](mid)
        for oid in (ops["id"].tolist() if not ops.empty else [])[:2]:
            nombre = ops[ops.id == oid].iloc[0]["nombre"]
            ambos(lambda: L.buscar_opcion_curricular_para_materia_v120(mid, nombre),
                  lambda: ns["buscar_opcion_curricular_para_materia_v120"](mid, nombre), f"buscar {mid}/{oid}")
            ambos(lambda: L.vinculos_opcion_para_espacio_seleccionado_v128(mid, oid),
                  lambda: ns["get_vinculos_opcion_para_espacio_seleccionado_v128"](mid, oid), f"v128 {mid}/{oid}")
    pid = pids[-1]
    for _, c in ns["get_comisiones"](periodo_id=pid).head(12).iterrows():
        args = (pid, int(c["materia_id"]), c["nombre_comision"], c["turno"], c["sede"], c["modalidad"])
        adic = ns["get_materias_conceptuales_comision_v122"](int(c["id"]))[1:]
        oid = None if pd.isna(c["opcion_curricular_id"]) else int(c["opcion_curricular_id"])
        for ex in (None, int(c["id"])):
            ambos(lambda: L.existe_comision_duplicada(*args, excluir_id=ex, opcion_curricular_id=oid,
                                                      materia_especifica=c["materia_especifica"],
                                                      materia_ids_adicionales=adic),
                  lambda: ns["existe_comision_duplicada"](*args, excluir_id=ex, opcion_curricular_id=oid,
                                                          materia_especifica=c["materia_especifica"],
                                                          materia_ids_adicionales=adic), f"duplicada c{c['id']} ex{ex}")


def test_inscriptos_v248(caso):
    dep, pids, ns, L = caso
    for pid in pids:
        for fn, cert in [("inscriptos_asignaturas_periodo_v248", "get_inscriptos_asignaturas_periodo_v248"),
                         ("legacy_inscriptos_sin_discriminar_v248", "get_legacy_inscriptos_sin_discriminar_v248"),
                         ("analisis_alumnos_por_docente_grupos_v248", "get_analisis_alumnos_por_docente_grupos_v248"),
                         ("inscriptos_comisiones_periodo", "get_inscriptos_comisiones_periodo"),
                         ("total_inscriptos_asignaturas_periodo_v248", "_total_inscriptos_asignaturas_periodo_v248"),
                         ("docentes_comisiones_periodo_v248", "_docentes_comisiones_periodo_v248")]:
            igual(getattr(L, fn)(pid), ns[cert](pid), f"p{pid} {fn}")
    igual(L.historial_inscriptos_materias(), ns["get_historial_inscriptos_materias"](), "historial materias")
    igual(L.historial_inscriptos_por_cuatrimestre(), ns["get_historial_inscriptos_por_cuatrimestre"](), "historial comb")


def test_capacidad_de_proyectos_v184(db_conn):
    from types import SimpleNamespace

    from comisiones import escrituras as E
    from periodos_support import savepoint
    cuiles = [r[0] for r in db_conn.execute(
        "SELECT DISTINCT cuil FROM (SELECT cuil FROM investigacion_docente WHERE institucion_id=1 UNION "
        "SELECT cuil FROM extension_docente WHERE institucion_id=1) x ORDER BY cuil LIMIT 25").fetchall()]
    for dep, pids in [(1, [5, 9]), (9, [14])]:
        ns = certified_comisiones(db_conn, 1, dep)
        u = E.Unidad(lambda: savepoint(db_conn), SimpleNamespace(name="test", coupled_commits=0), 1, dep,
                     today=FIXED_TODAY, now=FIXED_NOW)
        for pid in pids:
            for cuil in cuiles:
                assert P.capacidad_proyectos_docente_v184(u, cuil, pid) == ns["capacidad_proyectos_docente_v184"](
                    cuil, pid), (dep, pid, cuil)


# ------------------------------------------------------------------------------------------ carga rápida
def _texto(L, n_docentes=2):
    mats = L.materias_para_comisiones()
    comunes = mats[~mats.apply(lambda r: R.es_materia_optativa_electiva(r["codigo"], r["asignatura"]), axis=1)]
    oe = mats[mats.apply(lambda r: R.es_materia_optativa_electiva(r["codigo"], r["asignatura"]), axis=1)]
    m1, m2 = comunes.iloc[0], comunes.iloc[3]
    docs = L.docentes_activos_para_comisiones(9)["nombre_completo"].tolist()[:n_docentes]
    filas = [
        "Código\tAsignatura\tCarrera / plan\tCódigo 2\tAsignatura 2\tOpción Curricular\tComisión\tTurno\tDía 1\t"
        "Hora Inicio 1\tHora Fin 1\tDía 2\tHora Inicio 2\tHora Fin 2\tModalidad\tSede\tDocente 1\tCargo 1\t"
        "Cubre Horario 1 - Docente 1\tCubre Horario 2 - Docente 1\tHora Inicio Docente 1 Horario 2\t"
        "Hora Fin Docente 1 Horario 2\tDocente 2\tCupo Total",
        f"{m1['codigo']}\t{m1['asignatura']}\t\t{m2['codigo']}\t{m2['asignatura']}\t\tzz1\tNoche\tlunes\t18:00\t20:00\t"
        f"Miércoles\t18:00\t21:00\tpresencial\tsin especificar\t{docs[0]}\t\tSí\tSí\t19:00\t21:00\t{docs[1]}\t40",
        f"{m1['codigo']}\t{m1['asignatura']}\t\t\t\t\tZZ1\tnoche\tLunes\t18:00\t20:00\t\t\t\tPresencial\t\t\t\t\t\t\t\t\t",
        f"{m1['codigo']}\t{m1['asignatura']}\t\t\t\t\tZZ1\tnoche\tLunes\t18:00\t20:00\t\t\t\tPresencial\t\t\t\t\t\t\t\t\t",
        f"\t{m2['asignatura']}\t\t\t\t\tZZ2\t\tViernes\t14:00\t16:00\t\t\t\tVirtual\tCampus Virtual\t{docs[1]}\tREVISAR CARGO"
        f"\tNo\t\t\t\t\t",
        "ZZ-999\tNo existe ZZ\t\t\t\t\tZZ3\ttarde\tMartes\t10:00\t08:00\t\t\t\tPresencial\tSede inventada\t\t\t\t\t\t\t\t",
        f"{m1['codigo']}\t{m1['asignatura']}\t\t\t\tOpcion inventada\tZZ4\tmañana\tJueves\t08:00\t10:00\t\t\t\t"
        f"Presencial\t\tDocente Inexistente ZZ\t\t\t\t\t\t\t",
    ]
    if not oe.empty:
        filas.append(f"{oe.iloc[0]['codigo']}\t{oe.iloc[0]['asignatura']}\t\t\t\t\tZZ5\ttarde\tMartes\t14:00\t16:00\t"
                     f"\t\t\tPresencial\t\t{docs[0]}\t\t\t\t\t\t\t")
    return "\n".join(filas)


def test_vista_previa_carga_rapida_texto(db_conn):
    ns = certified_comisiones(db_conn, 1, 1)
    L = Lector(ComisionesRepository(db_conn, 1, 1), FIXED_TODAY)
    texto = _texto(L)
    df_c = ns["parsear_comisiones_pegadas"](texto)
    df_n = C.parsear_comisiones_pegadas(texto, L.opciones_sedes_comision())
    igual(df_n, df_c, "parseo")
    pv_c = U.preview_comisiones_decidida(ns["preparar_preview_comisiones_rapidas"](df_c, 9))  # 6A-B3
    pv_n = C.Validador(L, 9).preparar_preview_comisiones_rapidas(df_n)
    assert set(pv_c["estado_validacion"]) >= {"ERROR", "DUPLICADA", "ADVERTENCIA"}
    assert records(pv_n) == records(pv_c)
    # Sin encabezados: formato mas habitual (codigo, asignatura, comision, turno, dia/hora 1 y 2, modalidad).
    sin = "\n".join(texto.split("\n")[1:3])
    igual(C.parsear_comisiones_pegadas(sin, L.opciones_sedes_comision()), ns["parsear_comisiones_pegadas"](sin),
          "parseo sin encabezado")


def _firma_libro(contenido: bytes) -> dict:
    """Todo lo visible y funcional del libro: celdas (valor, formato, relleno, fuente, alineacion), filas ocultas,
    anchos, paneles, validaciones, nombres definidos, tablas, comentarios, filtros y visibilidad de hojas."""
    from openpyxl import load_workbook
    wb = load_workbook(BytesIO(contenido))
    out = {"hojas": wb.sheetnames, "nombres": sorted((n, d.attr_text) for n, d in wb.defined_names.items())}
    for ws in wb.worksheets:
        celdas = []
        for row in ws.iter_rows():
            for c in row:
                if c.value is None and not c.has_style:
                    continue
                celdas.append((c.coordinate, c.value, c.number_format, c.fill.fgColor.rgb if c.fill else None,
                               bool(c.font.bold), c.font.color.rgb if c.font and c.font.color else None,
                               c.alignment.horizontal, bool(c.alignment.wrap_text),
                               c.comment.text if c.comment else None))
        out[ws.title] = {
            "celdas": celdas, "estado": ws.sheet_state, "paneles": ws.freeze_panes,
            "ocultas": sorted(k for k, d in ws.row_dimensions.items() if d.hidden),
            "anchos": sorted((k, d.width, d.hidden) for k, d in ws.column_dimensions.items()),
            "validaciones": sorted((dv.formula1, str(dv.sqref), dv.prompt, dv.promptTitle, dv.error, dv.errorTitle)
                                   for dv in ws.data_validations.dataValidation),
            "tablas": sorted((t.displayName, t.ref) for t in ws.tables.values()),
            "filtro": ws.auto_filter.ref,
        }
    return out


def _partes(contenido: bytes) -> dict:
    """Partes del .xlsx byte a byte, salvo ``docProps/core.xml`` (fechas de creacion/modificacion de openpyxl)."""
    import zipfile
    with zipfile.ZipFile(BytesIO(contenido)) as z:
        return {n: z.read(n) for n in sorted(z.namelist()) if n != "docProps/core.xml"}


def _fuente(db_conn, dep=1):
    L = Lector(ComisionesRepository(db_conn, 1, dep), FIXED_TODAY)
    inst = db_conn.execute("SELECT nombre FROM instituciones WHERE id=1").fetchone()[0]
    nombre_dep = db_conn.execute("SELECT nombre FROM departamentos WHERE id=%s", [dep]).fetchone()[0]
    return L, X.FuenteExcel(L, inst, nombre_dep), inst


def _ns_excel(db_conn, inst_nombre, dep=1):
    ns = certified_comisiones(db_conn, 1, dep)
    ns["current_user"] = lambda: {"email": "info@test.local", "institucion_nombre": inst_nombre}
    return ns


def test_excel_modelo_igual_al_certificado(db_conn):
    L, fuente, inst = _fuente(db_conn)
    ns = _ns_excel(db_conn, inst)
    mine, cert = X.generar_excel_modelo_carga_rapida_comisiones(fuente, 9), ns["generar_excel_modelo_carga_rapida_comisiones"](9)
    cert = U.xlsx_comisiones_decidido(cert)  # 6A-B3: hoja Materias rotula "Unidades académicas"
    a, b = _firma_libro(mine), _firma_libro(cert)
    assert a.keys() == b.keys()
    for k in a:
        assert a[k] == b[k], k
    assert _partes(mine) == _partes(cert)


@pytest.mark.parametrize("pid", [5, 9])
def test_excel_completado_igual_al_certificado(db_conn, pid):
    L, fuente, inst = _fuente(db_conn)
    ns = _ns_excel(db_conn, inst)
    mine = X.generar_excel_comisiones_periodo_completado_v175(fuente, pid)
    cert = U.xlsx_comisiones_decidido(ns["generar_excel_comisiones_periodo_completado_v175"](pid))  # 6A-B3
    a, b = _firma_libro(mine), _firma_libro(cert)
    for k in a:
        assert a[k] == b[k], k
    assert _partes(mine) == _partes(cert)


def test_vista_previa_desde_excel_completado(db_conn):
    """Round trip: el Excel completado del periodo historico subido como carga del periodo actual."""
    L, fuente, inst = _fuente(db_conn)
    ns = _ns_excel(db_conn, inst)
    contenido = X.generar_excel_comisiones_periodo_completado_v175(fuente, 5)
    df_n = C.leer_excel_integral_comisiones_v149(contenido, L.opciones_sedes_comision())
    df_c = ns["leer_excel_integral_comisiones_v149"](contenido)
    igual(df_n, df_c, "lectura Excel")
    assert not df_n.empty
    pv_n = C.Validador(L, 9).preparar_preview_comisiones_rapidas(df_n.head(25))
    pv_c = U.preview_comisiones_decidida(ns["preparar_preview_comisiones_rapidas"](df_c.head(25), 9))  # 6A-B3
    assert records(pv_n) == records(pv_c)
    with pytest.raises(ValueError) as e_n:
        C.leer_excel_integral_comisiones_v149(_libro_sin_hoja(), [])
    with pytest.raises(ValueError) as e_c:
        ns["leer_excel_integral_comisiones_v149"](_libro_sin_hoja())
    assert str(e_n.value) == str(e_c.value)


def _libro_sin_hoja() -> bytes:
    from openpyxl import Workbook
    wb = Workbook()
    wb.active.title = "Otra"
    out = BytesIO()
    wb.save(out)
    return out.getvalue()
