"""Diferencial de Consolidado institucional contra B13-FIX02: el render certificado efectivo
(``render_consolidado_institucional`` v242, l. 53184) se EJECUTA desde ``reference_fix02`` (``consolidado_support``) y
se compara con el servicio NEXT sobre los mismos datos de deptit_next_dev:
- secuencia de UI (titulo, metricas, captions, control de consistencia, resumen, selector, buscador, mensajes, CSV);
- KPIs, deduplicacion por CUIL, suma departamental, designaciones y horas; periodo tomado por departamento;
- las 9 tablas del visor (mismas columnas, orden y valores), la busqueda, el CSV byte a byte (tabla COMPLETA) y el
  Excel global (VISTA FILTRADA, hoja "Datos");
- institucion con varios departamentos (1), departamentos sin periodos (2), institucion sin departamentos (5),
  coordinador, superadmin y roles denegados;
- anomalias certificadas congeladas (D-AO6) y ausencia de escrituras.
Las cifras de la institucion 1 NO son constantes del codigo: se verifican contra la ejecucion certificada."""

from __future__ import annotations

import io
import re
from pathlib import PureWindowsPath

import pandas as pd
import pytest

from analisis.pagina import tabla
from consolidado import lecturas as L
from consolidado.service import CSV_LABEL, ConsolidadoError
from consolidado_support import FIXED_TODAY, _Session, consolidado, db_conn, render, session_for  # noqa: F401
from periodos_support import EXTRA_DEPARTMENTS

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")

SIN_SCOPE = {"tenant_scope_departamento_id": None}


@pytest.fixture
def records(service, repo):
    repo.departments_rows.extend(dict(d) for d in EXTRA_DEPARTMENTS)
    coord = session_for(service, repo, 2)[0]
    sup = session_for(service, repo, 1)[0]
    service.set_context(sup, 1, 1, False)
    return {"coord": coord, "super": sup}


def _xid(db_conn):
    return db_conn.execute("SELECT pg_current_xact_id_if_assigned()").fetchone()[0]


def _excel(contenido: bytes) -> pd.DataFrame:
    import openpyxl

    libro = openpyxl.load_workbook(io.BytesIO(contenido))
    assert libro.sheetnames == ["Datos"]
    return pd.read_excel(io.BytesIO(contenido), sheet_name="Datos", dtype=str, keep_default_na=False)


# Orden no determinista CERTIFICADO: ``detalle_designaciones`` sale de ``GROUP_CONCAT``/``STRING_AGG`` sin ORDER BY
# (l. 4701) y ``get_designaciones`` (l. 32479) no desempata por ``d.id`` a un mismo docente en el periodo.  Etapa 5 /
# Tanda C (C1): el lado NEXT ya es determinista (``ORDER BY d.id``, test_e5_c_determinismo_performance); el lado
# CERTIFICADO sigue sin orden, asi que en "docentes" y "designaciones" se compara modulo ese orden: partes del detalle
# ordenadas y, en designaciones, misma secuencia (departamento, periodo, docente) y mismas filas.
NO_DETERMINISTAS = ("docentes", "designaciones")


# Hardening NEXT H-1 (aprobado por el usuario el 2026-10-30): el certificado muestra ``archivo_word`` y
# ``plantilla_usada`` de ``disposiciones`` con la ruta absoluta de Windows; NEXT solo el nombre del archivo.  El
# diferencial compara TODAS las columnas contra el certificado y SOLO esas 2 contra ``basename(valor_certificado)``
# (oraculo independiente del codigo: ``PureWindowsPath.name``).
SOLO_NOMBRE = {"disposiciones": ("archivo_word", "plantilla_usada")}
RUTA = re.compile(r"(?i)([a-z]:[\\/]|\\users\\|/users/|^[\\/])")


def esperado(clave: str, df: pd.DataFrame) -> pd.DataFrame:
    """La salida certificada con el hardening H-1 aplicado (identidad para cualquier otra tabla/columna)."""
    cols = [c for c in SOLO_NOMBRE.get(clave, ()) if c in df.columns]
    if not cols:
        return df
    df = df.copy()
    for c in cols:
        df[c] = df[c].map(lambda v: PureWindowsPath(v).name if isinstance(v, str) and v else v)
    return df


def _df(t: dict) -> pd.DataFrame:
    return pd.DataFrame(t["filas"], columns=t["columnas"]).map(lambda v: "" if v is None else str(v))


def _csv(b: bytes) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(b), dtype=str, keep_default_na=False, encoding="utf-8-sig")


def equivalentes(clave: str, a: pd.DataFrame, b: pd.DataFrame) -> None:
    a, b = a.reset_index(drop=True).copy(), b.reset_index(drop=True).copy()
    assert list(a.columns) == list(b.columns) and len(a) == len(b)
    if clave in NO_DETERMINISTAS:
        if "detalle_designaciones" in a.columns:
            for d in (a, b):
                d["detalle_designaciones"] = d["detalle_designaciones"].map(
                    lambda s: " | ".join(sorted(str(s).split(" | "))))
        if clave == "designaciones":
            k = ["departamento_origen", "periodo", "nombre_completo"]
            assert a[k].values.tolist() == b[k].values.tolist()
            a = a.sort_values(list(a.columns)).reset_index(drop=True)
            b = b.sort_values(list(b.columns)).reset_index(drop=True)
    pd.testing.assert_frame_equal(a, b)


def eventos_next(ov: dict, tb: dict | None, clave: str, csv_nombre: str | None) -> list[tuple]:
    """Secuencia de UI del payload NEXT con la forma de ``consolidado_support.Grabador``."""
    ev = [("title", ov["titulo"])]
    if ov["estado"] == "sin_datos":
        return ev + [("info", ov["mensaje"])]
    ev += [("columns", 4)] + [("metric", m["label"], m["valor"]) for m in ov["metricas"]]
    ev += [("caption", ov["caption"]), ("expander", ov["control"]["titulo"], ov["control"]["abierto"]),
           ("columns", 4)] + [("metric", m["label"], m["valor"]) for m in ov["control"]["metricas"]]
    ev += [("caption", ov["control"]["caption"]), ("/expander",),
           ("markdown", f"### {ov['resumen']['titulo']}"), ("dataframe", ov["resumen"]["excel"]),
           ("markdown", f"### {ov['visor']['titulo']}"),
           ("selectbox", ov["visor"]["label"], ov["visor"]["opciones"], "consol_tabla", clave)]
    if tb["vacio"]:
        return ev + [("info", tb["mensaje"])]
    b = ov["visor"]["buscador"]
    ev.append(("text_input", b["label"], f"consol_buscar_{clave}", b["placeholder"], b["help"], tb["busqueda"]))
    if tb["caption"]:
        ev.append(("caption", tb["caption"]))
    ev.append(("info", tb["sin_coincidencias"]) if tb["sin_coincidencias"] else ("dataframe", tb["excel"]))
    return ev + [("download_button", ov["visor"]["csv"], csv_nombre, "text/csv")]


def eventos_cert(st) -> list[tuple]:
    """Eventos certificados con los valores de ``st.metric`` como texto (``valor``) y sin el indice de frame."""
    out = []
    for e in st.ev:
        if e[0] == "metric":
            out.append(("metric", e[1], str(e[2])))
        elif e[0] == "dataframe":
            out.append(("dataframe", e[2]))
        else:
            out.append(e)
    return out


def _comparar(db_conn, consolidado, record, usuario, sesion, clave="docentes", texto=""):
    textos = {f"consol_buscar_{clave}": texto} if texto else {}
    st = render(db_conn, usuario, sesion, selects={"consol_tabla": clave}, textos=textos)
    ov = consolidado.overview(record)
    tb = consolidado.tabla(record, clave, texto) if ov["estado"] == "tablero" else None
    csv = None
    if tb is not None and not tb["vacio"]:
        csv = consolidado.csv(record, clave)
    assert eventos_next(ov, tb, clave, csv.nombre if csv else None) == eventos_cert(st)
    return st, ov, tb, csv


# ------------------------------------------------------------------------------------------ pagina e indicadores
def test_pagina_kpis_resumen_y_control_inst1(db_conn, consolidado, records):
    """Inst 1 (coordinador): misma pagina, KPIs (suma + CUIL unicos), control, resumen y periodo por departamento."""
    xid = _xid(db_conn)
    st, ov, tb, csv = _comparar(db_conn, consolidado, records["coord"], "coord1", SIN_SCOPE)
    assert tabla(st.frames[0]) == ov["resumen"]["tabla"]
    assert ov["resumen"]["tabla"]["columnas"] == ["Departamento", "Período tomado", "Estado del período",
                                                  "Docentes del período", "Designaciones del período",
                                                  "Horas de designaciones"]
    nombres = [f[0] for f in ov["resumen"]["tabla"]["filas"]]
    assert len(nombres) == len(set(nombres)) and len(nombres) == int(ov["metricas"][0]["valor"])
    # cifras de la auditoria (casos reales, no constantes del codigo) verificadas contra la ejecucion certificada
    vals = {m["label"]: m["valor"] for m in ov["metricas"] + ov["control"]["metricas"]}
    assert vals == {"Departamentos": "6", "Docentes únicos por CUIL": "596", "Designaciones del período": "653",
                    "Horas de las designaciones": "9570.0", "Suma de docentes de los departamentos": "619",
                    "Designaciones sumadas": "653", "Docentes compartidos · repeticiones": "23"}
    assert _xid(db_conn) == xid


def test_periodo_por_departamento_y_misma_vista_para_cualquier_contexto(db_conn, consolidado, records, service):
    """Cada departamento toma su periodo (abierto o el ultimo); el departamento operativo de la sesion no influye y
    no se modifica (el certificado lo muta y restaura; NEXT no lo toca)."""
    st = render(db_conn, "coord1", {"tenant_scope_departamento_id": 2})
    assert st.session_state["tenant_scope_departamento_id"] == 2
    coord = records["coord"]
    service.set_context(coord, None, 2, False)
    antes = dict(coord.scope)
    ov = consolidado.overview(coord)
    assert coord.scope == antes
    assert tabla(st.frames[0]) == ov["resumen"]["tabla"]
    periodos = {f[0]: (f[1], f[2]) for f in ov["resumen"]["tabla"]["filas"]}
    for dep_id, nombre in db_conn.execute("SELECT id, nombre FROM departamentos WHERE institucion_id=1 "
                                          "AND COALESCE(estado,'Activo')='Activo'").fetchall():
        abierto = db_conn.execute("SELECT nombre, estado FROM periodos WHERE departamento_id=%s AND "
                                  "estado='Abierto' ORDER BY id DESC LIMIT 1", [dep_id]).fetchone()
        ultimo = db_conn.execute("SELECT nombre, estado FROM periodos WHERE departamento_id=%s ORDER BY anio DESC, "
                                 "semestre DESC, id DESC LIMIT 1", [dep_id]).fetchone()
        esperado = abierto or ultimo or ("Sin períodos", "Sin períodos")
        assert periodos[nombre] == tuple(esperado), nombre
    # superadmin: misma institucion -> mismo tablero (con cualquier departamento operativo)
    sup = render(db_conn, "super", {"superadmin_institucion_id": 1, "tenant_scope_departamento_id": 3})
    assert eventos_cert(sup) == eventos_cert(st)
    service.set_context(records["super"], 1, 3, False)
    assert consolidado.overview(records["super"])["metricas"] == ov["metricas"]


# ------------------------------------------------------------------------------------------ visor de tablas
@pytest.mark.parametrize("clave", L.TABLAS)
def test_nueve_tablas_csv_completo_y_excel(db_conn, consolidado, records, clave):
    """Cada tabla: misma pagina, mismas columnas/orden/valores, CSV identico byte a byte y Excel de la tabla mostrada."""
    st, ov, tb, csv = _comparar(db_conn, consolidado, records["coord"], "coord1", SIN_SCOPE, clave)
    assert ov["visor"]["opciones"] == L.TABLAS and ov["visor"]["csv"] == CSV_LABEL
    if tb["vacio"]:
        assert len(st.frames) == 1 and not [d for d in st.descargas if d["tipo"] == "csv"]
        with pytest.raises(ConsolidadoError):
            consolidado.csv(records["coord"], clave)
        return
    cert = st.frames[-1]
    assert tb["total"] == tb["encontrados"] == len(cert)
    assert "sqlite_id" not in tb["datos"]["columnas"] and "source_db" not in tb["datos"]["columnas"]
    cert_csv = next(d for d in st.descargas if d["tipo"] == "csv")
    assert cert_csv["nombre"] == csv.nombre == f"{clave}_consolidado.csv" and csv.contenido.startswith(b"\xef\xbb\xbf")
    cert_xlsx = next(d for d in st.descargas if d["tipo"] == "excel" and d["frame"] == len(st.frames) - 1)
    nuevo = consolidado.excel(records["coord"], clave, "")
    if clave in NO_DETERMINISTAS:
        equivalentes(clave, _df(tabla(cert)), _df(tb["datos"]))
        equivalentes(clave, _csv(cert_csv["bytes"]), _csv(csv.contenido))
        equivalentes(clave, _excel(cert_xlsx["bytes"]), _excel(nuevo.contenido))
    elif clave in SOLO_NOMBRE:  # H-1: identico salvo las 2 columnas, que valen basename(valor certificado)
        assert tabla(esperado(clave, cert)) == tb["datos"] and tabla(cert) != tb["datos"]
        pd.testing.assert_frame_equal(_csv(csv.contenido), esperado(clave, _csv(cert_csv["bytes"])))
        pd.testing.assert_frame_equal(_excel(nuevo.contenido), esperado(clave, _excel(cert_xlsx["bytes"])))
    else:  # identico: tipos JSON, CSV byte a byte y Excel
        assert tabla(cert) == tb["datos"] and cert_csv["bytes"] == csv.contenido
        pd.testing.assert_frame_equal(_excel(nuevo.contenido), _excel(cert_xlsx["bytes"]))
    assert nuevo.nombre.startswith("Consolidado_institucional_") and nuevo.nombre.endswith(".xlsx")


def test_excel_del_resumen(db_conn, consolidado, records):
    st = render(db_conn, "coord1", SIN_SCOPE)
    cert = next(d for d in st.descargas if d["tipo"] == "excel" and d["frame"] == 0)
    pd.testing.assert_frame_equal(_excel(consolidado.excel(records["coord"], "resumen", None).contenido),
                                  _excel(cert["bytes"]))


@pytest.mark.parametrize("clave,texto", [("docentes", "informática"), ("designaciones", "Titular"),
                                         ("movimientos", "baja"), ("disposiciones", "ZZZ-sin-coincidencia"),
                                         ("comisiones", "  ")])
def test_busqueda_csv_completo_excel_filtrado(db_conn, consolidado, records, clave, texto):
    """Busqueda equivalente a ``filtrar_dataframe_por_texto`` y asimetria certificada: CSV = tabla COMPLETA (sin la
    busqueda, se ofrece aunque no haya coincidencias); Excel = VISTA FILTRADA."""
    st, ov, tb, csv = _comparar(db_conn, consolidado, records["coord"], "coord1", SIN_SCOPE, clave, texto)
    completo = consolidado.csv(records["coord"], clave).contenido
    sin_busqueda = render(db_conn, "coord1", SIN_SCOPE, selects={"consol_tabla": clave})
    cert_completo = next(d for d in sin_busqueda.descargas if d["tipo"] == "csv")["bytes"]
    equivalentes(clave, esperado(clave, _csv(cert_completo)), _csv(completo))
    # el CSV de la pagina CON busqueda es el mismo archivo completo (certificado)
    cert_con_busqueda = [d for d in st.descargas if d["tipo"] == "csv"]
    assert len(cert_con_busqueda) == 1
    equivalentes(clave, esperado(clave, _csv(cert_con_busqueda[0]["bytes"])), _csv(completo))
    assert tb["total"] == len(sin_busqueda.frames[-1])
    if tb["sin_coincidencias"]:
        assert tb["datos"] is None and len(st.frames) == 1
        with pytest.raises(ConsolidadoError) as exc:
            consolidado.excel(records["coord"], clave, texto)
        assert exc.value.code == "SIN_COINCIDENCIAS"
        return
    vista = st.frames[-1]
    equivalentes(clave, _df(tabla(esperado(clave, vista))), _df(tb["datos"]))
    xlsx = consolidado.excel(records["coord"], clave, texto).contenido
    cert_xlsx = next(d for d in st.descargas if d["tipo"] == "excel" and d["frame"] == len(st.frames) - 1)
    equivalentes(clave, esperado(clave, _excel(cert_xlsx["bytes"])), _excel(xlsx))  # Excel = VISTA FILTRADA
    if texto.strip():
        assert len(vista) == len(_excel(xlsx)) < tb["total"] == len(_csv(completo))  # CSV = tabla COMPLETA


def test_h1_disposiciones_sin_rutas_absolutas(db_conn, consolidado, records):
    """H-1: el certificado expone rutas absolutas en ``archivo_word``/``plantilla_usada``; NEXT no expone ninguna ruta,
    letra de unidad ni ``\\Users\\`` en ninguna columna de tabla, CSV ni Excel, y la busqueda opera sobre el nombre
    del archivo (una busqueda por un fragmento de la ruta ya no encuentra esas filas).  Solo afecta a disposiciones."""
    assert L.COLUMNAS_SOLO_NOMBRE == SOLO_NOMBRE
    coord, clave = records["coord"], "disposiciones"
    cert = render(db_conn, "coord1", SIN_SCOPE, selects={"consol_tabla": clave}).frames[-1]
    for c in SOLO_NOMBRE[clave]:  # el hardening se ejercita de verdad: el certificado SI trae rutas
        assert cert[c].map(lambda v: bool(RUTA.search(str(v))) if isinstance(v, str) else False).sum() > 0
    tb = consolidado.tabla(coord, clave, "")
    salidas = {"tabla": _df(tb["datos"]), "csv": _csv(consolidado.csv(coord, clave).contenido),
               "excel": _excel(consolidado.excel(coord, clave, "").contenido)}
    for nombre, df in salidas.items():
        assert len(df) == len(cert), nombre
        for c in df.columns:
            assert not df[c].map(lambda v: bool(RUTA.search(v))).any(), (nombre, c)
    # busqueda: fragmento de ruta -> el certificado encuentra filas, NEXT no; por nombre de archivo -> mismas filas
    # que el filtro certificado aplicado a la salida esperada
    from materias.rules import filtrar_dataframe_por_texto
    base = esperado(clave, cert)
    for texto in ("users", ".docx"):
        cert_busq = render(db_conn, "coord1", SIN_SCOPE, selects={"consol_tabla": clave},
                           textos={f"consol_buscar_{clave}": texto})
        r = consolidado.tabla(coord, clave, texto)
        oraculo = filtrar_dataframe_por_texto(base, texto, base.columns.tolist())
        assert r["encontrados"] == len(oraculo)
        if r["datos"] is not None:
            equivalentes(clave, _df(tabla(oraculo)), _df(r["datos"]))
            assert len(_excel(consolidado.excel(coord, clave, texto).contenido)) == len(oraculo)
        if texto == "users":
            assert len(cert_busq.frames[-1]) > r["encontrados"]
        else:
            assert r["encontrados"] > 0
    for otra in set(L.TABLAS_CRUDAS) - {clave}:  # ninguna otra tabla se transforma
        assert otra not in L.COLUMNAS_SOLO_NOMBRE


# ------------------------------------------------------------------------------------------ estados y roles
def test_departamentos_sin_periodos_y_sin_departamentos(db_conn, consolidado, records, service, repo):
    """Inst 2 (todos sin periodos): filas "Sin períodos" en 0 y tablas vacias; inst 5 (sin departamentos)."""
    coord2 = render(db_conn, "coord2", SIN_SCOPE)
    sup = records["super"]
    service.set_context(sup, 2, 5, False)
    st, ov, tb, _ = _comparar(db_conn, consolidado, sup, "super",
                              {"superadmin_institucion_id": 2, "tenant_scope_departamento_id": 5})
    assert eventos_cert(coord2) == eventos_cert(st)
    assert {tuple(f[1:]) for f in ov["resumen"]["tabla"]["filas"]} == {("Sin períodos", "Sin períodos", 0, 0, 0.0)}
    assert tb["vacio"] and tb["mensaje"] == "No hay datos para el criterio seleccionado."
    service.set_context(sup, 5, None, False)
    st5, ov5, _, _ = _comparar(db_conn, consolidado, sup, "super", {"superadmin_institucion_id": 5})
    assert ov5["estado"] == "sin_datos" and ov5["mensaje"] == "Sin datos para consolidar."


@pytest.mark.parametrize("usuario", ["dep", "lector", "comercial"])
def test_roles_denegados_como_el_certificado(db_conn, usuario):
    """El render certificado rechaza todo rol que no sea coordinador/superadmin (incluida la solo lectura comercial
    de un coordinador); NEXT devuelve 403 con el mismo mensaje (``test_consolidado_service``)."""
    st = render(db_conn, usuario, {"tenant_scope_departamento_id": 1})
    assert st.ev == [("title", "🏛️ Consolidado institucional"),
                     ("error", "Esta vista es para coordinación institucional o superadmin.")]


# ------------------------------------------------------------------------------------------ anomalias (D-AO6)
def test_anomalias_certificadas_congeladas(db_conn, consolidado, records):
    """1 periodos mezclados; 2-3 docentes repetidos entre departamentos y deduplicados solo en el KPI por CUIL;
    4 designaciones identicas repetidas entre departamentos SIN deduplicar (horas incluidas); 5 funciones no docentes
    contadas; 6 tablas crudas sin filtro de periodo; 7 CSV completo vs Excel filtrado (test de busqueda)."""
    coord = records["coord"]
    ov = consolidado.overview(coord)
    periodos = {f[1] for f in ov["resumen"]["tabla"]["filas"] if f[1] != "Sin períodos"}
    assert len(periodos) > 1  # 2026-2 y 2026-1 (Posgrado) sumados en el mismo total
    vals = {m["label"]: int(float(m["valor"])) for m in ov["control"]["metricas"]}
    docs = consolidado.tabla(coord, "docentes", "")
    from docentes.rules import clave_cuil

    i_cuil = docs["datos"]["columnas"].index("cuil")
    claves = [clave_cuil(f[i_cuil]) for f in docs["datos"]["filas"]]
    assert len(claves) == vals["Suma de docentes de los departamentos"] > len(set(claves)) \
        == vals["Docentes únicos por CUIL"]
    assert vals["Docentes compartidos · repeticiones"] == len(claves) - len(set(claves))
    des = consolidado.tabla(coord, "designaciones", "")
    cols = des["datos"]["columnas"]
    df = pd.DataFrame(des["datos"]["filas"], columns=cols)
    assert len(df) == vals["Designaciones sumadas"] and set(df["estado"]) == {"Activa"}
    df["k"] = df["cuil"].map(clave_cuil)
    ident = ["k", "cargo", "dedicacion", "horas", "fecha_desde", "fecha_hasta"]
    repetidas = df[df.duplicated(subset=ident, keep="first")]
    assert len(repetidas) > 0 and set(repetidas["departamento_origen"]) - set()  # contadas en otro departamento
    horas = float(pd.to_numeric(df["horas"]).sum())
    assert f"{round(horas, 2)}" == ov["metricas"][3]["valor"]  # las horas repetidas y no docentes estan sumadas
    assert int((df["funcion_no_docente"] == 1).sum()) > 0
    for clave in ("comisiones", "movimientos", "disposiciones"):
        t = consolidado.tabla(coord, clave, "")
        ip = t["datos"]["columnas"].index("periodo_id")
        assert len({f[ip] for f in t["datos"]["filas"]}) > len(periodos)


def test_reader_crudo_solo_por_allowlist(db_conn):
    """El lector crudo solo acepta claves de la allowlist (sin interpolar texto del cliente)."""
    assert set(L.TABLAS_CRUDAS) == set(L.TABLAS) - {"docentes", "designaciones"}
    for mala in ("departamentos", "app_usuarios", "comisiones; DROP TABLE x", "public.comisiones", '"comisiones"'):
        with pytest.raises(KeyError):
            L.tabla_cruda(db_conn, 1, mala)
