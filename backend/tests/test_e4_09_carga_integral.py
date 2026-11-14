"""E4-09 — Docentes → "Carga rápida integral de docentes y designaciones".

Diferencial contra B13-FIX02 con Excel SINTETICOS, desde el mismo estado (SAVEPOINT + ROLLBACK):
- lado certificado: la seccion LITERAL ``with tab6:`` (entry l. 61278-61652) ejecutada con un Streamlit que graba cada
  llamada (``e4_09_support``), sobre el cierre transitivo del entry (lector, revision, fotos v220, mezcla v247 y los
  writers certificados de Docentes y Designaciones con sus COMMITs);
- lado NEXT: ``CargaIntegralService`` (composicion: lectura literal en el motor READ ONLY + contratos de los owners).
Se comparan: revision (filas visibles de ambas hojas, contadores, avisos), modelo Excel, fichas de docentes, designaciones,
movimientos nuevos, asignaciones, secuencia de operaciones B12H con sus COMMITs y el resultado (mensaje, tabla de
verificacion, errores).
"""
from __future__ import annotations

import ast
import json
import pprint
import re
from datetime import date
from io import BytesIO
from pathlib import Path

import psycopg
import pytest
from openpyxl import Workbook, load_workbook

import designaciones_support as DS
import docentes_support as DOS
import e4_09_support as S
from designaciones_support import (  # noqa: F401  (fixtures)
    FIXED_NOW, FIXED_TODAY, audit_rows, audit_store, db_conn, designaciones, savepoint, session_for,
)

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")

INST, DEP = 1, 1
BACKEND = Path(__file__).resolve().parents[1]
N1, N2, E1, X1 = "20-99119001-5", "27-99119002-8", "20-99119003-1", "23-99119004-3"
H_DOC = ["CUIL", "Apellido", "Nombres", "Legajo", "Título", "Título posgrado", "Años antigüedad",
         "Nivel posgrado salarial", "Email", "Teléfono", "Ref. legajo físico", "Estado", "Observaciones"]
H_DES = ["CUIL", "Docente", "Período", "Cargo", "Dedicación", "Horas", "Tipo designación", "N° resolución", "Ad honorem",
         "Fecha desde", "Fecha hasta", "Estado", "Observaciones"]


# ------------------------------------------------------------------------------------------ fixtures
@pytest.fixture
def docentes(service, audit_store, db_conn, designaciones):
    return DOS.make_docentes(service, audit_store, db_conn)


@pytest.fixture
def carga(docentes, designaciones, db_conn):
    from integraciones.carga_integral import CargaIntegralService
    return CargaIntegralService(None, docentes, designaciones, today=lambda: FIXED_TODAY, now=lambda: FIXED_NOW,
                                transaction=lambda: savepoint(db_conn))


def _record(service, repo, uid=3, dep=None):
    rec = session_for(service, repo, uid)[0]
    if dep is not None:
        service.set_context(rec, INST, dep, False)
    return rec


def seed_docente(conn, cuil, apellido="ZZNEXT Existente", nombres="Eva"):
    DOS.free_cuil(conn, cuil)
    conn.execute("INSERT INTO docentes (institucion_id, departamento_id, cuil, nombre, apellido, nombres, legajo, titulo,"
                 " email, telefono, ref_legajo_fisico, estado, tipo_docente, fecha_alta, observaciones, titulo_posgrado,"
                 " antiguedad_anios, nivel_posgrado_salarial) VALUES (1,1,%s,%s,%s,%s,'L-E1','Lic. ZZNEXT',"
                 "'e1@test.local','011','R-1','Activo','Propio','2025-03-01','ZZNEXT seed','',3,'')",
                 [cuil, f"{apellido}, {nombres}", apellido, nombres])


def seed_designacion(conn, cuil, cargo, dedicacion, horas, tipo, resolucion, adh, desde, hasta, periodo=9):
    conn.execute("INSERT INTO designaciones (institucion_id, departamento_id, cuil, cargo, dedicacion, horas,"
                 " tipo_designacion, ad_honorem, fecha_desde, fecha_hasta, estado, periodo_id, observaciones,"
                 " numero_resolucion, funcion_no_docente, texto_funcion_no_docente) VALUES (1,1,%s,%s,%s,%s,%s,%s,%s,"
                 "%s,'Activa',%s,'ZZNEXT seed',%s,0,'')",
                 [cuil, cargo, dedicacion, horas, tipo, adh, desde, hasta, periodo, resolucion])


def excel(docentes_rows, designaciones_rows, *, hojas=("Docentes", "Designaciones"), h_doc=H_DOC, h_des=H_DES,
          base: bytes | None = None) -> bytes:
    """Excel sintetico: sobre el MODELO generado (``base``) o un libro minimo con las mismas cabeceras."""
    if base is not None:
        wb = load_workbook(BytesIO(base))
    else:
        wb = Workbook()
        wb.remove(wb.active)
        for nombre, cab in zip(hojas, (h_doc, h_des)):
            ws = wb.create_sheet(nombre)
            ws.append(cab)
    for nombre, filas in zip(("Docentes", "Designaciones"), (docentes_rows, designaciones_rows)):
        if nombre not in wb.sheetnames:
            continue
        ws = wb[nombre]
        cab = [c.value for c in ws[1]]
        for i, fila in enumerate(filas, start=2):
            for col, valor in fila.items():
                ws.cell(i, cab.index(col) + 1).value = valor
    out = BytesIO()
    wb.save(out)
    return out.getvalue()


def dataset_valido(conn, base=None) -> bytes:
    """Mezcla certificada: 2 docentes nuevos, 1 existente con actualizacion parcial; designaciones OK, ADVERTENCIA,
    duplicada en el archivo, ya existente en la base, historica (periodo cerrado), plurianual y fechas en texto."""
    seed_docente(conn, E1)
    # Etapa 5 / Tanda B (B4): el lector reconoce la cabecera "N° resolución" del propio modelo (el certificado la
    # ignoraba: la fila llegaba con resolucion vacia).  La designacion de la base tiene la MISMA resolucion que la fila
    # "R-BASE" del archivo -> identidad igual (OMITIR, ya existe en la base).
    seed_designacion(conn, E1, "JTP", "Simple", 10, "Interino", "R-BASE", "No", "2026-08-01", "2026-12-31")
    for c in (N1, N2):
        DOS.free_cuil(conn, c)
    docs = [
        {"CUIL": N1, "Apellido": "ZZNEXT Nuevo", "Nombres": "Uno", "Legajo": "L-N1", "Título": "Lic.",
         "Años antigüedad": 5, "Nivel posgrado salarial": "magister", "Email": "n1@test.local", "Observaciones": "obs N1"},
        {"CUIL": N2.replace("-", ""), "Apellido": "ZZNEXT Nuevo", "Nombres": "Dos", "Estado": "Activo"},
        {"CUIL": E1, "Legajo": "L-NUEVO", "Teléfono": "999", "Observaciones": "act parcial"},
    ]
    des = [
        {"CUIL": N1, "Cargo": "JTP", "Dedicación": "Simple", "Tipo designación": "Interino", "N° resolución": "R-1/2026",
         "Ad honorem": "No", "Fecha desde": date(2026, 8, 1), "Fecha hasta": date(2026, 12, 31), "Observaciones": "o1"},
        {"CUIL": N1, "Cargo": "Adjunto", "Dedicación": "Parcial", "Tipo designación": "Concursado",
         "Fecha desde": date(2026, 8, 1), "Fecha hasta": date(2026, 12, 31)},
        {"CUIL": N1, "Cargo": "JTP", "Dedicación": "Simple", "Tipo designación": "Interino", "N° resolución": "R-1/2026",
         "Ad honorem": "No", "Fecha desde": date(2026, 8, 1), "Fecha hasta": date(2026, 12, 31)},
        {"CUIL": E1, "Cargo": "Titular", "Dedicación": "Exclusiva", "Tipo designación": "Interino", "N° resolución": "R-2",
         "Fecha desde": date(2026, 1, 1), "Fecha hasta": date(2026, 7, 31)},
        {"CUIL": N2, "Cargo": "Ayudante 1ra", "Dedicación": "Simple", "Tipo designación": "Loc. Serv.",
         "N° resolución": "R-3", "Ad honorem": "si", "Fecha desde": "01/08/2026", "Fecha hasta": "31/12/2026"},
        {"CUIL": E1, "Cargo": "JTP", "Dedicación": "Simple", "Tipo designación": "Interino", "N° resolución": "R-BASE",
         "Ad honorem": "No", "Fecha desde": date(2026, 8, 1), "Fecha hasta": date(2026, 12, 31)},
        {"CUIL": E1, "Cargo": "Asociado", "Dedicación": "Parcial + Simple", "Tipo designación": "Concursado",
         "N° resolución": "R-4", "Fecha desde": date(2025, 3, 1), "Fecha hasta": date(2027, 3, 1)},
    ]
    return excel(docs, des, base=base)


H_DOC_ANTIGUEDAD = [("antiguedad" if c == "Años antigüedad" else c) for c in H_DOC]


def dataset_invalido(conn) -> bytes:
    seed_docente(conn, E1)
    for c in (N1, N2, X1):
        DOS.free_cuil(conn, c)
    docs = [
        {"CUIL": "", "Apellido": "Sin", "Nombres": "Cuil"},
        {"CUIL": N1, "Apellido": "ZZNEXT", "Nombres": "Rep", "Estado": "Jubiladx", "antiguedad": 99,
         "Nivel posgrado salarial": "licenciado"},
        {"CUIL": N1, "Apellido": "ZZNEXT", "Nombres": "Rep"},
        {"CUIL": N2, "antiguedad": "2,5"},
    ]
    des = [
        {"CUIL": "", "Fecha desde": date(2026, 8, 1), "Fecha hasta": date(2026, 12, 31)},
        {"CUIL": X1, "Fecha desde": date(2026, 8, 1), "Fecha hasta": date(2026, 12, 31)},
        {"CUIL": E1, "Fecha desde": date(2026, 12, 31), "Fecha hasta": date(2026, 8, 1)},
        {"CUIL": E1, "Fecha desde": date(2030, 1, 1), "Fecha hasta": date(2030, 6, 30)},
        {"CUIL": E1, "Cargo": "Decano", "Dedicación": "Total", "Tipo designación": "Eterno", "Ad honorem": "tal vez",
         "Fecha desde": date(2026, 8, 1), "Fecha hasta": date(2026, 12, 31)},
        {"CUIL": E1, "Fecha desde": "", "Fecha hasta": date(2026, 12, 31)},
    ]
    return excel(docs, des, h_doc=H_DOC_ANTIGUEDAD)


def dataset_columnas(conn) -> bytes:
    """Cabeceras con otra grafia, columna extra y columnas faltantes (Observaciones / Título)."""
    seed_docente(conn, E1)
    DOS.free_cuil(conn, N1)
    h_doc = ["cuil", "APELLIDO", "nombres", "Columna extra"]
    h_des = ["cuil", "CARGO", "dedicacion", "tipo designacion", "nro resolucion", "fecha desde", "FECHA HASTA", "Otra"]
    docs = [{"cuil": N1, "APELLIDO": "ZZNEXT Col", "nombres": "Uno", "Columna extra": "x"}]
    des = [{"cuil": N1, "CARGO": "adjunto", "dedicacion": "simple", "tipo designacion": "interino", "nro resolucion": "R9",
            "fecha desde": "2026-08-01", "FECHA HASTA": "2026-12-31", "Otra": "y"}]
    return excel(docs, des, h_doc=h_doc, h_des=h_des)


DATASETS = {"valido": dataset_valido, "invalido": dataset_invalido, "columnas": dataset_columnas}


# ------------------------------------------------------------------------------------------ comparacion
def estado(conn, max_mov, cuiles) -> dict:
    """``horas_variacion`` se compara por VALOR: Docentes (cerrado) guarda 0 con escala 0 y psycopg2 (certificado) con
    escala 1 ('0' vs '0.0', numericamente iguales; deuda registrada en DOCENTES_E4_09_INTEGRATION.md)."""
    out = DS.state(conn, INST, DEP, max_mov)
    out.pop("links_designaciones"), out.pop("links_movimientos")
    movs = []
    for m in out["movimientos"]:
        d = json.loads(m)
        d["horas_variacion"] = float(d["horas_variacion"])
        movs.append(json.dumps(d, sort_keys=True))
    out["movimientos"] = movs
    out["docentes"] = DOS.state(conn, [c.replace("-", "") for c in cuiles], exclude=("id", "fecha_registro"))["docentes"]
    return out


def _ops(eventos):
    ops, vistos = [], {}
    for e in eventos:
        cid = str(e["correlation_id"])
        if cid not in vistos:
            vistos[cid] = {"op": e["operation"], "commits": []}
            ops.append(vistos[cid])
        m = e["metadata"]
        vistos[cid]["commits"].append({k: m.get(k) for k in ("commit_seq", "mutating_statements", "committing_writer",
                                                            "nested_system_task")})
    return ops


def _registros(df, columnas):
    if df is None or df.empty:
        return []
    cols = [c for c in columnas if c in df.columns]
    out = []
    for r in df.to_dict("records"):
        fila = {}
        for c in cols:
            v = r.get(c)
            if v is not None and isinstance(v, float) and v != v:
                v = None
            fila[c] = v.item() if hasattr(v, "item") else v
        out.append(fila)
    return out


def revision_certificada(st) -> dict:
    """Lo que la seccion certificada muestra en la revision (l. 61345-61451)."""
    metricas = {e[1]: e[2] for e in st.ev if e[0] == "metric"}
    tablas = [e[1] for e in st.ev if e[0] == "dataframe"]
    return {"avisos": [e[1] for e in st.ev if e[0] == "info" and e[1] != (
                "No existe un cupo de docentes ni de designaciones por departamento. La cantidad de filas preformateadas "
                "del Excel es solo una comodidad de carga y no limita lo que el sistema puede guardar.")],
            "metricas": metricas, "tablas": tablas, "errores": [e[1] for e in st.ev if e[0] == "error"],
            "captions": [e[1] for e in st.ev if e[0] == "caption"]}


def comparar_revision(st, vista):
    from integraciones.carga_integral import COLUMNAS_DESIGNACIONES, COLUMNAS_DOCENTES
    rc = revision_certificada(st)
    if rc["errores"] and rc["errores"][0].startswith("No se pudo leer o validar el Excel integral: "):
        return rc
    assert rc["metricas"] == {"Docentes nuevos": vista["docentes_nuevos"],
                              "Docentes existentes": vista["docentes_existentes"],
                              "Designaciones nuevas": vista["designaciones_nuevas"], "Errores": vista["errores"]}
    assert rc["avisos"] == vista["avisos"]
    assert (f"Filas con datos detectadas en el archivo: Docentes **{vista['filas_docentes']}** | Designaciones "
            f"**{vista['filas_designaciones']}**. El importador procesa todas las filas detectadas; no corta por "
            "cantidad.") in rc["captions"]
    assert (f"Control de Designaciones: detectadas {vista['designaciones_detectadas']} | nuevas "
            f"{vista['designaciones_nuevas']} | duplicadas {vista['designaciones_omitidas']} | errores "
            f"{vista['errores_designaciones']}.") in rc["captions"]
    tablas = rc["tablas"]
    cert_doc = _registros(tablas[0], COLUMNAS_DOCENTES) if vista["docentes"] else []
    cert_des = _registros(tablas[-1], COLUMNAS_DESIGNACIONES) if vista["designaciones"] else []
    assert cert_doc == vista["docentes"], pprint.pformat((cert_doc, vista["docentes"]))[:3000]
    assert cert_des == vista["designaciones"], pprint.pformat((cert_des, vista["designaciones"]))[:3000]
    return rc


def resultado_certificado(st) -> dict:
    ev = st.resultado.ev
    msg = next(e for e in ev if e[0] in ("success", "warning") and str(e[1]).startswith("Carga integral verificada"))
    tabla = next((e[1] for e in ev if e[0] == "dataframe"), None)
    return {"mensaje": msg[1], "tono": msg[0], "detalle": [] if tabla is None else tabla.to_dict("records"),
            "errores_detalle": [e[1][2:] for e in ev if e[0] == "write" and str(e[1]).startswith("- ")]}


def comparar_carga(db_conn, audit_store, carga, rec, contenido, cuiles, *, actualizar=False, romper=None,
                   genericos=False):
    """Certificado (click + confirmacion) vs NEXT (previsualizar -> ejecutar), desde el mismo estado."""
    from integraciones.carga_integral import CargaIntegralService  # noqa: F401
    from resoluciones_respaldos.service import Archivo
    max_mov = DS.baseline(db_conn)
    archivo = Archivo(nombre="ZZNEXT integral.xlsx", mime="application/vnd.ms-excel", contenido=contenido)
    with db_conn.transaction() as tx:
        ns = S.certified_carga(db_conn, INST, DEP)
        if romper:
            romper(ns, None)
        st = S.ejecutar_seccion(ns, S._Archivo("ZZNEXT integral.xlsx", contenido), actualizar=actualizar,
                                confirmar=True, click=True)
        st_c = estado(db_conn, max_mov, cuiles)
        ops_c = [o for o in ns["_frames"].ops if o["commits"]]
        raise psycopg.Rollback(tx)
    with db_conn.transaction() as tx:
        n = len(audit_store.events)
        vista = carga.previsualizar(rec, {}, archivo)
        deshacer = romper(None, True) if romper else None
        try:
            rn = carga.ejecutar(rec, {"confirmar": True, "actualizar_existentes": actualizar, "huella": vista["huella"]},
                                archivo)
        finally:
            if deshacer:
                deshacer()
        st_n = estado(db_conn, max_mov, cuiles)
        eventos = audit_rows(db_conn)
        nuevos = audit_store.events[n:]
        raise psycopg.Rollback(tx)
    for clave in st_c:
        assert st_c[clave] == st_n[clave], f"{clave}:\ncert {pprint.pformat(st_c[clave])[:2500]}\n" \
                                           f"NEXT {pprint.pformat(st_n[clave])[:2500]}"
    ops_n = _ops(eventos)
    assert ops_c == ops_n, f"cert:\n{pprint.pformat(ops_c)[:4000]}\nNEXT:\n{pprint.pformat(ops_n)[:4000]}"
    rc = resultado_certificado(st)
    assert rn["mensaje"] == rc["mensaje"] and rn["tono"] == rc["tono"], (rn["mensaje"], rc["mensaje"])
    if genericos:  # el certificado muestra el texto de la excepcion; NEXT el mensaje controlado del owner
        limpiar = lambda d: [{**x, "Detalle": "*"} if x["Resultado"] == "Error" else x for x in d]  # noqa: E731
        assert limpiar(rn["detalle"]) == limpiar(rc["detalle"])
        assert [e.split(":")[0] for e in rn["errores_detalle"]] == [e.split(":")[0] for e in rc["errores_detalle"]]
    else:
        assert rn["detalle"] == rc["detalle"]
        assert rn["errores_detalle"] == rc["errores_detalle"]
    return {"vista": vista, "rn": rn, "rc": rc, "ops": ops_n, "nuevos": nuevos, "estado": st_n}


# ------------------------------------------------------------------------------------------ modelo Excel
def _libro(data: bytes):
    return load_workbook(BytesIO(data))


def _mismo_libro(a, b):
    assert a.sheetnames == b.sheetnames
    for name in a.sheetnames:
        x, y = a[name], b[name]
        assert (x.sheet_state, x.max_row, x.max_column) == (y.sheet_state, y.max_row, y.max_column), name
        for ra, rb in zip(x.iter_rows(), y.iter_rows()):
            for ca, cb in zip(ra, rb):
                assert (ca.value, ca.number_format, ca.fill.fgColor.rgb, ca.font.b) == \
                       (cb.value, cb.number_format, cb.fill.fgColor.rgb, cb.font.b), (name, ca.coordinate)
                assert (ca.comment.text if ca.comment else None) == (cb.comment.text if cb.comment else None)
        assert [(d.formula1, str(d.sqref)) for d in x.data_validations.dataValidation] == \
               [(d.formula1, str(d.sqref)) for d in y.data_validations.dataValidation]
        assert [(t.name, t.ref) for t in x.tables.values()] == [(t.name, t.ref) for t in y.tables.values()]
    assert list(a.defined_names) == list(b.defined_names)


def test_modelo_excel_equivalente(db_conn, carga, service, repo):
    """"📥 Descargar Excel integral…": mismo libro (hojas, celdas, formatos, validaciones, nombres, comentarios) con
    los tamaños por defecto (1000 / 5000) y con tamaños elegidos; controles del expander certificados."""
    rec = _record(service, repo)
    with db_conn.transaction() as tx:
        ns = S.certified_carga(db_conn, INST, DEP)
        st = S.ejecutar_seccion(ns, filas_modelo=None)
        raise psycopg.Rollback(tx)
    assert [e for e in st.ev if e[0] == "number_input"] == [
        ("number_input", "Filas preformateadas — Docentes", 20, 1048575, 1000, 100),
        ("number_input", "Filas preformateadas — Designaciones", 20, 1048575, 5000, 500)]
    cert = st.descargas["modelo_integral_docentes_designaciones.xlsx"]
    got, nombre = carga.modelo(rec, {})
    assert nombre == "modelo_integral_docentes_designaciones.xlsx"
    _mismo_libro(_libro(got), _libro(cert))
    with db_conn.transaction() as tx:
        ns = S.certified_carga(db_conn, INST, DEP)
        st = S.ejecutar_seccion(ns, filas_modelo=20)
        raise psycopg.Rollback(tx)
    _mismo_libro(_libro(carga.modelo(rec, {"filas_docentes": 20, "filas_designaciones": 20})[0]),
                 _libro(st.descargas["modelo_integral_docentes_designaciones.xlsx"]))
    from docentes.service import DocentesError
    for malo in ({"filas_docentes": 19}, {"filas_designaciones": 1048576}, {"filas_docentes": "100"}):
        with pytest.raises(DocentesError) as exc:
            carga.modelo(rec, malo)
        assert exc.value.status == 422


# ------------------------------------------------------------------------------------------ revision previa
def test_b4_encabezados_del_modelo_se_leen(db_conn, carga, service, repo, audit_store):
    """Etapa 5 / Tanda B (B4): sobre el MISMO archivo con las cabeceras del modelo, el lector certificado LITERAL no
    reconoce "Años antigüedad" ni "N° resolución" (antiguedad vacia, resolucion vacia y la advertencia "Falta N° de
    resolución"); NEXT (normalizador endurecido) lee 5 anios y "R-1/2026" y no emite esa advertencia."""
    from resoluciones_respaldos.service import Archivo
    rec = _record(service, repo)
    with db_conn.transaction() as tx:
        contenido = dataset_valido(db_conn)
        literal = revision_certificada(S.ejecutar_seccion(S.certified_carga(db_conn, INST, DEP, literal=True),
                                                          S._Archivo("x.xlsx", contenido)))
        vista = carga.previsualizar(rec, {}, Archivo("x.xlsx", "", contenido))
        raise psycopg.Rollback(tx)
    from integraciones.carga_integral import COLUMNAS_DESIGNACIONES, COLUMNAS_DOCENTES
    cert_doc = _registros(literal["tablas"][0], COLUMNAS_DOCENTES)
    cert_des = _registros(literal["tablas"][-1], COLUMNAS_DESIGNACIONES)
    n1_c = next(d for d in cert_doc if d["cuil"] == N1)
    n1 = next(d for d in vista["docentes"] if d["cuil"] == N1)
    assert str(n1_c["antiguedad_anios"]) in ("", "None", "nan") and str(n1["antiguedad_anios"]) == "5"
    assert {str(d["numero_resolucion"]) for d in cert_des} <= {"", "None", "nan"}
    assert vista["designaciones"][0]["numero_resolucion"] == "R-1/2026"
    falta = "Falta N° de resolución"
    assert falta in str(cert_des[0]) and falta not in str(vista["designaciones"][0])


@pytest.mark.parametrize("nombre", sorted(DATASETS))
def test_revision_equivalente(db_conn, carga, service, repo, audit_store, nombre):
    from resoluciones_respaldos.service import Archivo
    rec = _record(service, repo)
    with db_conn.transaction() as tx:
        contenido = DATASETS[nombre](db_conn)
        ns = S.certified_carga(db_conn, INST, DEP)
        st = S.ejecutar_seccion(ns, S._Archivo("x.xlsx", contenido))
        vista = carga.previsualizar(rec, {}, Archivo("x.xlsx", "", contenido))
        raise psycopg.Rollback(tx)
    rc = comparar_revision(st, vista)
    assert audit_store.events == []
    if nombre == "invalido":
        assert vista["sin_errores"] is False and vista["errores"] == 10
        assert rc["errores"] == ["Corregí los errores indicados en el Excel y volvé a subirlo. No se guardó ningún dato."]
        motivos = " | ".join(d["motivo"] for d in vista["docentes"] + vista["designaciones"])
        for texto in ("CUIL obligatorio", "CUIL repetido en la hoja Docentes", "Estado docente no válido",
                      "Años de antigüedad debe ser un entero entre 0 y 80", "Nivel de posgrado salarial no válido",
                      "Falta apellido o nombres", "El CUIL no está en la hoja Docentes ni en la base maestra",
                      "Fecha desde posterior a fecha hasta", "Las fechas no coinciden con ningún período registrado",
                      "Fecha desde y Fecha hasta son obligatorias"):
            assert texto in motivos, texto
    if nombre == "valido":
        estados = [d["estado_validacion"] if "estado_validacion" in d else d["accion"] for d in vista["designaciones"]]
        assert estados == ["Crear designación", "Crear designación", "Omitir duplicada", "Crear designación",
                           "Crear designación", "Omitir duplicada", "Crear designación"]
        assert [d["periodo"] for d in vista["designaciones"]][3] == "2026-1"
        assert vista["designaciones"][3]["estado"] == "Finalizada" and vista["designaciones"][6]["periodo"] == "2026-2"
        assert vista["docentes"][0]["nivel_posgrado_salarial"] == "Magíster"  # B12A
        assert vista["sin_errores"] is True


def test_hoja_faltante_y_archivo_invalido(db_conn, carga, service, repo):
    """Sin hoja Designaciones: mensaje certificado.  NEXT ademas valida la firma XLSX, el nombre y el tamaño."""
    from docentes.service import DocentesError
    from resoluciones_respaldos.service import Archivo
    rec = _record(service, repo)
    contenido = excel([], [], hojas=("Docentes", "Otra"))
    with db_conn.transaction() as tx:
        ns = S.certified_carga(db_conn, INST, DEP)
        st = S.ejecutar_seccion(ns, S._Archivo("x.xlsx", contenido))
        raise psycopg.Rollback(tx)
    esperado = "No se pudo leer o validar el Excel integral: El archivo debe contener una hoja llamada Designaciones."
    assert revision_certificada(st)["errores"] == [esperado]
    with pytest.raises(DocentesError) as exc:
        carga.previsualizar(rec, {}, Archivo("x.xlsx", "", contenido))
    assert (exc.value.status, exc.value.message) == (422, esperado)
    casos = [(Archivo("x.xlsx", "", b"%PDF-1.4 no"), 422), (Archivo("x.pdf", "", contenido), 422),
             (Archivo("x.xlsx", "", b"PK\x03\x04basura"), 422), (None, 422),
             (Archivo("x.xlsx", "", b"PK\x03\x04" + b"0" * (50 * 1024 * 1024)), 413)]
    for archivo, status in casos:
        with pytest.raises(DocentesError) as exc:
            carga.previsualizar(rec, {}, archivo)
        assert exc.value.status == status
        assert "Traceback" not in exc.value.message and "zip" not in exc.value.message.lower()


# ------------------------------------------------------------------------------------------ carga
@pytest.mark.parametrize("actualizar", [False, True])
def test_carga_equivalente(db_conn, carga, service, repo, audit_store, actualizar):
    rec = _record(service, repo)
    with db_conn.transaction() as tx:
        contenido = dataset_valido(db_conn)
        r = comparar_carga(db_conn, audit_store, carga, rec, contenido, [N1, N2, E1], actualizar=actualizar)
        raise psycopg.Rollback(tx)
    ops = [o["op"] for o in r["ops"]]
    assert ops[:4] == ["guardar_docente", "registrar_movimiento", "guardar_docente", "registrar_movimiento"]
    assert ops.count("guardar_designacion") == 5 and ops.count("registrar_movimiento") == 2 + 5 + (1 if actualizar else 0)
    assert ("actualizar_docente" in ops) is actualizar
    assert r["rn"]["mensaje"] == (f"Carga integral verificada. Docentes nuevos: 2. Docentes actualizados: "
                                  f"{1 if actualizar else 0}. Docentes existentes omitidos: {0 if actualizar else 1}. "
                                  "Designaciones nuevas realmente guardadas: 5. Duplicadas omitidas desde la revisión: 2."
                                  " Errores: 0.")
    movs = [json.loads(m) for m in r["estado"]["movimientos"]]
    assert any(m["detalle"] == "2026-1 - Titular - Exclusiva - 40 hs - Interino" and m["periodo_id"] == 5 for m in movs)
    assert any(m["detalle"] == "Se registró el docente mediante el Excel integral." for m in movs)


def test_carga_sobre_el_modelo_generado(db_conn, carga, service, repo, audit_store):
    """La plantilla certificada (formulas de Período / Estado / Docente incluidas) completada y subida."""
    rec = _record(service, repo)
    with db_conn.transaction() as tx:
        base = carga.modelo(rec, {"filas_docentes": 20, "filas_designaciones": 20})[0]
        contenido = dataset_valido(db_conn, base=base)
        comparar_carga(db_conn, audit_store, carga, rec, contenido, [N1, N2, E1])
        raise psycopg.Rollback(tx)


def test_fallos_parciales(db_conn, carga, service, repo, audit_store):
    """Un docente y una designacion fallan: el resto se guarda, los errores se acumulan por fila y las escrituras
    previas quedan (sin atomicidad global, como el certificado)."""
    from designaciones import escrituras as DE
    rec = _record(service, repo)

    def romper(ns, next_side):
        if ns is not None:
            orig_doc, orig_des = ns["guardar_docente"], ns["guardar_designacion"]

            def doc(*a, **k):
                if a[0] == N2.replace("-", ""):
                    raise RuntimeError("fallo inyectado docente")
                return orig_doc(*a, **k)

            def des(*a, **k):
                if a[2] == "Titular":
                    raise RuntimeError("fallo inyectado designacion")
                return orig_des(*a, **k)
            ns["guardar_docente"], ns["guardar_designacion"] = doc, des
            return None
        from docentes import repository as DR
        orig_ins, orig_e = DR.DocentesRepository.insert_docente, DE.guardar_designacion

        def ins(self, values):
            if values["cuil"] == N2.replace("-", ""):
                raise RuntimeError("fallo inyectado docente")
            return orig_ins(self, values)

        def e(u, *a, **k):
            if a[2] == "Titular":
                raise RuntimeError("fallo inyectado designacion")
            return orig_e(u, *a, **k)
        DR.DocentesRepository.insert_docente, DE.guardar_designacion = ins, e

        def deshacer():
            DR.DocentesRepository.insert_docente, DE.guardar_designacion = orig_ins, orig_e
        return deshacer

    with db_conn.transaction() as tx:
        contenido = dataset_valido(db_conn)
        r = comparar_carga(db_conn, audit_store, carga, rec, contenido, [N1, N2, E1], romper=romper, genericos=True)
        raise psycopg.Rollback(tx)
    # La designacion que fallo suma DOS errores, como el certificado: el del intento y "No guardada" (verificacion fisica).
    assert r["rn"]["errores"] == 3 and r["rn"]["tono"] == "warning", r["rn"]["errores_detalle"]
    assert [e.split(":")[0] for e in r["rn"]["errores_detalle"]] == ["Docente fila 3", "Designación fila 5",
                                                                     "Designación fila 5"]
    assert [d["Resultado"] for d in r["rn"]["detalle"] if d["Fila"] == 5] == ["Error", "No guardada"]
    assert "fallo inyectado" not in json.dumps(r["rn"], ensure_ascii=False)
    assert [(e.operation, e.outcome) for e in r["nuevos"] if e.outcome == "FAILED"] == [
        ("guardar_docente", "FAILED"), ("guardar_designacion", "FAILED")]


def test_carga_con_errores_o_sin_confirmar_no_escribe(db_conn, carga, service, repo, audit_store):
    """Con errores el boton certificado esta deshabilitado; sin confirmacion: "Primero confirmá…".  NEXT: 409 / 422."""
    from docentes.service import DocentesError
    from resoluciones_respaldos.service import Archivo
    rec = _record(service, repo)
    max_mov = DS.baseline(db_conn)
    for nombre, confirmar, status, mensaje in (
            ("invalido", True, 409, "Corregí los errores indicados en el Excel y volvé a subirlo. No se guardó ningún "
                                    "dato."),
            ("valido", False, 422, "Primero confirmá que revisaste el archivo.")):
        with db_conn.transaction() as tx:
            contenido = DATASETS[nombre](db_conn)
            antes = estado(db_conn, max_mov, [N1, N2, E1])
            ns = S.certified_carga(db_conn, INST, DEP)
            st = S.ejecutar_seccion(ns, S._Archivo("x.xlsx", contenido), confirmar=confirmar, click=True)
            assert estado(db_conn, max_mov, [N1, N2, E1]) == antes and not ns["_frames"].ops
            if not confirmar:
                assert ("error", mensaje) in st.ev
            archivo = Archivo("x.xlsx", "", contenido)
            vista = carga.previsualizar(rec, {}, archivo)
            with pytest.raises(DocentesError) as exc:
                carga.ejecutar(rec, {"confirmar": confirmar, "huella": vista["huella"]}, archivo)
            assert (exc.value.status, exc.value.message) == (status, mensaje)
            assert estado(db_conn, max_mov, [N1, N2, E1]) == antes
            raise psycopg.Rollback(tx)
    assert audit_store.events == []


def test_revision_obsoleta(db_conn, carga, service, repo, audit_store):
    """Hardening NEXT (B12I): la revision se rehace al cargar; si difiere de la confirmada -> 409 sin escrituras."""
    from docentes.service import DocentesError
    from resoluciones_respaldos.service import Archivo
    rec = _record(service, repo)
    with db_conn.transaction() as tx:
        archivo = Archivo("x.xlsx", "", dataset_valido(db_conn))
        vista = carga.previsualizar(rec, {}, archivo)
        # misma identidad que la fila "R-1/2026" del archivo (B4: la resolucion del modelo ahora se lee)
        seed_designacion(db_conn, N1, "JTP", "Simple", 10, "Interino", "R-1/2026", "No", "2026-08-01", "2026-12-31")
        with pytest.raises(DocentesError) as exc:
            carga.ejecutar(rec, {"confirmar": True, "huella": vista["huella"]}, archivo)
        assert exc.value.status == 409 and exc.value.code == "STALE"
        assert db_conn.execute("SELECT count(*) FROM docentes WHERE cuil=%s", [N1]).fetchone()[0] == 0
        raise psycopg.Rollback(tx)
    assert audit_store.events == []


def test_permisos_y_ambito(db_conn, carga, service, repo, audit_store):
    """solo_lectura: DENIED del primer writer y la carga se detiene (hardening: el boton certificado esta
    deshabilitado); coordinador sin departamento: 409; superadmin con contexto: carga en SU departamento."""
    from docentes.service import DocentesError
    from resoluciones_respaldos.service import Archivo
    with db_conn.transaction() as tx:
        archivo = Archivo("x.xlsx", "", dataset_valido(db_conn))
        lector = _record(service, repo, 7)
        vista = carga.previsualizar(lector, {}, archivo)
        max_mov = DS.baseline(db_conn)
        antes = estado(db_conn, max_mov, [N1, N2, E1])
        with pytest.raises(DocentesError) as exc:
            carga.ejecutar(lector, {"confirmar": True, "huella": vista["huella"]}, archivo)
        assert exc.value.status == 403 and "docentes.write" in exc.value.message
        assert [(e.operation, e.outcome) for e in audit_store.events] == [("guardar_docente", "DENIED")]
        assert estado(db_conn, max_mov, [N1, N2, E1]) == antes
        with pytest.raises(DocentesError) as exc:
            carga.previsualizar(_record(service, repo, 2), {}, archivo)
        assert exc.value.status == 409
        sup = _record(service, repo, 1, dep=DEP)
        r = carga.ejecutar(sup, {"confirmar": True, "huella": carga.previsualizar(sup, {}, archivo)["huella"]}, archivo)
        assert r["errores"] == 0
        assert db_conn.execute("SELECT departamento_id FROM docentes WHERE cuil=%s", [N1]).fetchone()[0] == DEP
        raise psycopg.Rollback(tx)
    with db_conn.transaction() as tx:  # otro departamento: el CUIL existente del 1 no existe alli -> errores
        archivo = Archivo("x.xlsx", "", dataset_valido(db_conn))
        sup2 = _record(service, repo, 1, dep=2)
        vista = carga.previsualizar(sup2, {}, archivo)
        assert vista["docentes_existentes"] == 0
        raise psycopg.Rollback(tx)


# ------------------------------------------------------------------------------------------ HTTP y arquitectura
def test_http_multipart(db_conn, carga, service, repo):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from auth.routes import router as auth_router
    from integraciones.routes import docentes_router

    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(docentes_router)
    app.state.auth = service
    app.state.carga_integral = carga
    c = TestClient(app, base_url="http://localhost")
    h = {"X-DEPTIT-Request": "1"}
    rutas = ("/docentes/carga-integral/previsualizar", "/docentes/carga-integral", "/docentes/carga-integral/modelo")
    for ruta in rutas:
        assert c.post(ruta, headers=h, json={}).status_code == 401
    c.cookies.set("deptit_session", session_for(service, repo, 3)[1])
    for ruta in rutas:
        assert c.post(ruta, json={}).status_code == 403
    r = c.post(rutas[2], headers=h, json={"filas_docentes": 20, "filas_designaciones": 20})
    assert r.status_code == 200 and r.content.startswith(b"PK") and "attachment" in r.headers["content-disposition"]
    with db_conn.transaction() as tx:
        contenido = dataset_valido(db_conn)
        f = {"archivo": ("ZZNEXT.xlsx", contenido, "application/octet-stream")}
        v = c.post(rutas[0], headers=h, files={**f, "datos": (None, "{}")})
        assert v.status_code == 200, v.text
        datos = json.dumps({"confirmar": True, "huella": v.json()["huella"], "institucion_id": 9, "departamento_id": 2})
        r = c.post(rutas[1], headers=h, files={**f, "datos": (None, datos)})
        assert r.status_code == 200 and r.json()["errores"] == 0, r.text
        assert db_conn.execute("SELECT departamento_id FROM docentes WHERE cuil=%s", [N1]).fetchone()[0] == DEP
        raise psycopg.Rollback(tx)
    r = c.post(rutas[0], headers=h, files={"archivo": ("x.xlsx", b"no es excel", "x"), "datos": (None, "{}")})
    assert r.status_code == 422 and not re.search(r"(?i)traceback|select\s|zipfile|openpyxl|C:\\\\", r.text)


def test_complemento_literal():
    """El complemento vendorizado es texto LITERAL del entry certificado (bloque por bloque) y su huella coincide."""
    from integraciones.carga_integral_motor import metadata
    from periodos_support import ENTRY
    src = ENTRY.read_text(encoding="utf-8")
    import hashlib
    assert hashlib.sha256(src.encode("utf-8")).hexdigest() == metadata.ENTRY_SHA256
    lineas = src.splitlines()
    texto = (BACKEND / "integraciones" / "carga_integral_motor" / "complemento.py").read_text(encoding="utf-8")
    bloques = re.findall(r"# --- entry l\. (\d+)(?:-(\d+))?\n(.*?)(?=\n# --- entry|\Z)", texto, re.S)
    assert len(bloques) == metadata.BLOQUES
    for ini, fin, cuerpo in bloques:
        original = "\n".join(l for l in ast.get_source_segment(src, next(
            n for n in ast.parse(src).body if n.lineno == int(ini))).splitlines() if not l.lstrip().startswith("@"))
        original = re.sub(r"\bdeptit_refactor\.", "", original)
        cuerpo = re.sub(r"\b(analisis\.motor\.ref|integraciones\.carga_integral_motor\.ref)\.", "", cuerpo)
        assert cuerpo.strip() == original.strip(), ini
    assert lineas  # entry legible
    assert metadata.WRITERS_NEGOCIO == [] and metadata.TAREAS_SISTEMA == {}


def test_arquitectura_sin_ciclos():
    for owner in ("docentes", "designaciones"):
        for archivo in (BACKEND / owner).glob("*.py"):
            assert not re.search(r"(?m)^\s*(from|import) integraciones", archivo.read_text(encoding="utf-8")), archivo
    texto = (BACKEND / "integraciones" / "carga_integral.py").read_text(encoding="utf-8")
    assert not re.search(r"(?m)^\s*(from|import) \w+\.(repository|escrituras)", texto)
    assert not re.search(r"(?i)\b(insert into|update \w+ set|delete from)\b", texto)
