"""Diferenciales de LECTURA de Resoluciones y respaldos: certificado (``certified_resoluciones``) vs NEXT, mismo estado.

Repositorio efectivo (v249 -> v251 -> v266 -> v286 off), filtros, detalle (sin binario en NEXT, D-AK12), dependencias,
selectores de "Cargar acto" (docentes por periodo v253, proyectos, periodos) y las fuentes del Resumen docente que la
Etapa 4 consolidara (reconstruidas aca y comparadas con ``get_actos_docente_resumen_v263`` efectiva).  Las variantes con
datos sinteticos (``ZZNEXT``) se insertan dentro de la transaccion del test y se revierten.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import psycopg
import pytest

from resoluciones_respaldos import lecturas as L
from resoluciones_respaldos import rules as R
from resoluciones_respaldos.lecturas import Lecturas
from resoluciones_respaldos.repository import DocumentosRepository
from resoluciones_respaldos.service import COLUMNAS_LISTADO
from resoluciones_support import (  # noqa: F401  (fixtures)
    FIXED_TODAY, audit_store, certified_resoluciones, db_conn, pdf_sintetico, record_for, resoluciones,
)

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")

INST = 1
MODULO = Path(__file__).resolve().parents[1] / "resoluciones_respaldos"


def _lec(conn, dep):
    return Lecturas(DocumentosRepository(conn, INST, dep), FIXED_TODAY, "usuario_departamento")


def _igual(a: pd.DataFrame, b: pd.DataFrame) -> None:
    assert list(a.columns) == list(b.columns)
    assert a.astype(str).to_dict("records") == b.astype(str).to_dict("records")


def _sinteticos(conn) -> dict:
    """Documentos ZZNEXT en el dep 1: legacy v249 (cuil/proyecto sin relacion), multiples docentes, vinculo exacto de
    designacion y de movimiento, sin PDF y con PDF; una dependencia inactiva."""
    dep_ina = conn.execute("INSERT INTO dependencias_documentales (institucion_id,nombre,estado,observaciones) VALUES "
                           "(1,'ZZNEXT Dependencia Inactiva','Inactiva','') RETURNING id").fetchone()[0]
    des = conn.execute("SELECT d.id, d.cuil FROM designaciones d WHERE d.institucion_id=1 AND d.departamento_id=1 "
                       "AND NOT EXISTS (SELECT 1 FROM documentos_respaldo_designaciones r WHERE r.designacion_id=d.id) "
                       "ORDER BY d.id DESC LIMIT 2").fetchall()
    mov = conn.execute("SELECT id, cuil FROM movimientos WHERE institucion_id=1 AND departamento_id=1 "
                       "ORDER BY id DESC LIMIT 1").fetchone()
    ids = []
    filas = [
        ("Resolución", "Rectoral", "Designación docente", "ZZNEXT-901/2026", "2026-03-01", "20-99110001-1",
         "ZZNEXT Legacy, Uno", "", None, None, "", b""),
        ("Disposición", "", "Proyecto de Investigación", "ZZNEXT-902/2026", None, "", "", "investigacion", 999999,
         dep_ina, "ZZNEXT Dependencia Inactiva", pdf_sintetico("a")),
        ("Otro", "", "Otro", "", "2026-04-01", "", "", "", None, None, "", pdf_sintetico("b", 3000)),
        ("Resolución", "Consejo Superior", "Cambio de cargo", "ZZNEXT-904/2026", "2026-05-01", "", "", "", None, None,
         "", b""),
    ]
    for tipo, tres, cat, num, fecha, cuil, nom, ptipo, pid, depid, depnom, pdf in filas:
        ids.append(conn.execute(
            "INSERT INTO documentos_respaldo (institucion_id,departamento_id,tipo_documento,tipo_resolucion,categoria,"
            "numero,fecha,cuil,docente_nombre,proyecto_tipo,proyecto_id,dependencia_id,dependencia_nombre,"
            "referencia_texto,titulo,detalle,observaciones,archivo_nombre,archivo_mime,archivo_pdf,archivo_bytes,"
            "fecha_carga,usuario_carga) VALUES (1,1,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'ZZNEXT ref','ZZNEXT titulo',"
            "'ZZNEXT detalle','ZZNEXT obs',%s,%s,%s,%s,'2026-10-01 10:00','zz@test.local') RETURNING id",
            [tipo, tres, cat, num, fecha, cuil, nom, ptipo, pid, depid, depnom, "ZZNEXT ñandú.pdf" if pdf else "",
             "application/pdf" if pdf else "", pdf, len(pdf)]).fetchone()[0])
    for cuil, nombre in (("20-99110002-2", "ZZNEXT Dos"), ("20-99110003-3", "")):
        conn.execute("INSERT INTO documentos_respaldo_docentes (institucion_id,departamento_id,documento_id,cuil,"
                     "docente_nombre) VALUES (1,1,%s,%s,%s)", [ids[3], cuil, nombre])
    for d in des:
        conn.execute("INSERT INTO documentos_respaldo_designaciones (institucion_id,departamento_id,documento_id,"
                     "designacion_id,usuario_vinculacion) VALUES (1,1,%s,%s,'zz')", [ids[3], d[0]])
    conn.execute("INSERT INTO documentos_respaldo_movimientos (institucion_id,departamento_id,documento_id,movimiento_id,"
                 "usuario_vinculacion) VALUES (1,1,%s,%s,'zz')", [ids[2], mov[0]])
    return {"ids": ids, "dependencia_inactiva": dep_ina, "designaciones": des, "movimiento": mov}


# ------------------------------------------------------------------------------------------ repositorio
@pytest.mark.parametrize("dep", [1, 9, 2, 3])
def test_repositorio_efectivo_por_departamento(db_conn, dep):
    ns = certified_resoluciones(db_conn, INST, dep)
    _igual(ns["get_documentos_respaldo_v251"](), _lec(db_conn, dep).repositorio())


def test_repositorio_con_legacy_vinculos_exactos_y_pdf_pendiente(db_conn):
    with db_conn.transaction() as tx:
        _sinteticos(db_conn)
        ns = certified_resoluciones(db_conn, INST, 1)
        cert = ns["get_documentos_respaldo_v251"]()
        nxt = _lec(db_conn, 1).repositorio()
        _igual(cert, nxt)
        assert len(nxt) == 7
        raise psycopg.Rollback(tx)


def _pagina_listado(df_docs: pd.DataFrame) -> dict:
    """Transcripcion de l. 51586-51616: opciones de filtros y columnas derivadas de la tabla."""
    mostrar = df_docs.copy()
    bytes_pdf = pd.to_numeric(mostrar["archivo_bytes"], errors="coerce").fillna(0)
    mostrar["Estado PDF"] = bytes_pdf.map(lambda x: "Adjunto" if float(x or 0) > 0 else "Pendiente")
    mostrar["Tamaño (KB)"] = (bytes_pdf / 1024.0).round(1)
    return {
        "tipos": ["Todos"] + sorted(df_docs["tipo_documento"].dropna().astype(str).unique().tolist()),
        "categorias": ["Todas"] + sorted(df_docs["categoria"].dropna().astype(str).unique().tolist()),
        "dependencias": ["Todas"] + sorted([x for x in df_docs.get("dependencia_emisora", pd.Series(dtype=str)).dropna()
                                           .astype(str).unique().tolist() if str(x).strip()]),
        "estado": mostrar["Estado PDF"].tolist(), "kb": [float(x) for x in mostrar["Tamaño (KB)"].tolist()],
        "ids": [int(x) for x in mostrar["id"].tolist()],
    }


def test_overview_listado_filtros_y_sin_binario(service, repo, db_conn, resoluciones):
    with db_conn.transaction() as tx:
        _sinteticos(db_conn)
        ns = certified_resoluciones(db_conn, INST, 1)
        esperado = _pagina_listado(ns["get_documentos_respaldo_v251"]())
        ov = resoluciones.overview(record_for(service, repo, dep=1))
        rep = ov["repositorio"]
        assert rep["filtros"] == {k: esperado[k] for k in ("tipos", "categorias", "dependencias")}
        assert [f["id"] for f in rep["filas"]] == esperado["ids"]
        assert [f["estado_pdf"] for f in rep["filas"]] == esperado["estado"]
        assert [f["tamano_kb"] for f in rep["filas"]] == esperado["kb"]
        for fila in rep["filas"]:
            assert set(fila) == set(COLUMNAS_LISTADO) | {"estado_pdf", "tamano_kb"}
            assert "archivo_pdf" not in fila and "usuario_carga" not in fila
            assert not any(isinstance(v, (bytes, bytearray, memoryview)) for v in fila.values())
        assert rep["busqueda"] == ["tipo_documento", "tipo_resolucion", "dependencia_emisora", "categoria", "numero",
                                   "periodo", "docentes", "cuiles", "proyectos", "proyecto_ids", "referencia", "titulo",
                                   "detalle", "observaciones", "archivo_nombre"]
        raise psycopg.Rollback(tx)


def test_repositorio_vacio(service, repo, db_conn, resoluciones):
    ov = resoluciones.overview(record_for(service, repo, dep=2))
    assert ov["repositorio"]["filas"] == []
    assert ov["repositorio"]["vacio"] == "Todavía no hay documentos respaldatorios cargados en este departamento."
    assert ov["tabs"] == ["📚 Repositorio", "➕ Cargar acto", "🏛️ Dependencias"]


# ------------------------------------------------------------------------------------------ detalle
def _pagina_detalle(ns, fila: dict, doc_id: int) -> dict:
    """Transcripcion de l. 51630-51687 (sin widgets)."""
    pdf = ns["obtener_pdf_documento_respaldo_v249"](doc_id)
    deps = ns["get_dependencias_documentales_v262"](solo_activas=False)
    opciones, mapa, index = [], {}, 0
    for _, rd in deps.iterrows():
        did = int(rd["id"])
        nom = str(rd.get("nombre") or "").strip()
        estado = str(rd.get("estado") or "Activa").strip()
        et = nom + (" [Inactiva]" if estado == "Inactiva" else "")
        opciones.append(et)
        mapa[et] = did
    actual = fila.get("dependencia_id")
    try:
        actual_i = int(actual) if pd.notna(actual) and str(actual).strip() else None
    except Exception:
        actual_i = None
    if actual_i is not None:
        for pos, et in enumerate(opciones):
            if mapa.get(et) == actual_i:
                index = pos
                break
    return {"tiene_pdf": bool(pdf and pdf.get("bytes")),
            "encabezado": f"{str(fila.get('tipo_documento', '') or '').strip()} {fila.get('numero', '')}",
            "aviso": "" if str(fila.get("dependencia_emisora", "") or "").strip() else
            "Este documento histórico todavía no tiene una dependencia emisora asignada.",
            "dependencias": [{"etiqueta": e, "id": mapa[e]} for e in opciones], "indice": index}


def test_detalle_equivalente_sin_binario(service, repo, db_conn, resoluciones):
    with db_conn.transaction() as tx:
        _sinteticos(db_conn)
        ns = certified_resoluciones(db_conn, INST, 1)
        docs = ns["get_documentos_respaldo_v251"]()
        rec = record_for(service, repo, dep=1)
        for fila in docs.to_dict("records"):
            esperado = _pagina_detalle(ns, fila, int(fila["id"]))
            d = resoluciones.documento(rec, {"id": int(fila["id"])})
            assert d["tiene_pdf"] == esperado["tiene_pdf"]
            assert d["encabezado"] == esperado["encabezado"]
            assert d["aviso_dependencia"] == esperado["aviso"]
            assert d["dependencias"] == esperado["dependencias"] and d["dependencia_indice"] == esperado["indice"]
            assert d["pdf_pendiente"] == ("" if esperado["tiene_pdf"] else
                                          "PDF pendiente de carga. El acto y sus vínculos ya están registrados.")
            assert not any(isinstance(v, (bytes, bytearray, memoryview)) for v in d["fila"].values())
        raise psycopg.Rollback(tx)


def test_pdf_descarga_es_el_binario_certificado(service, repo, db_conn, resoluciones):
    with db_conn.transaction() as tx:
        s = _sinteticos(db_conn)
        ns = certified_resoluciones(db_conn, INST, 1)
        for did in s["ids"]:
            cert = ns["obtener_pdf_documento_respaldo_v249"](did)
            nxt = _lec(db_conn, 1).pdf(did)
            assert cert == nxt
        raise psycopg.Rollback(tx)


# ------------------------------------------------------------------------------------------ dependencias
@pytest.mark.parametrize("solo_activas", [False, True])
def test_dependencias_catalogo(db_conn, solo_activas):
    with db_conn.transaction() as tx:
        _sinteticos(db_conn)
        ns = certified_resoluciones(db_conn, INST, 1)
        _igual(ns["get_dependencias_documentales_v262"](solo_activas=solo_activas),
               _lec(db_conn, 1).dependencias(solo_activas=solo_activas))
        raise psycopg.Rollback(tx)


def test_pestana_dependencias_y_opciones_de_alta(service, repo, db_conn, resoluciones):
    with db_conn.transaction() as tx:
        _sinteticos(db_conn)
        ns = certified_resoluciones(db_conn, INST, 1)
        df = ns["get_dependencias_documentales_v262"](solo_activas=False)
        activas = ns["get_dependencias_documentales_v262"](solo_activas=True)
        ov = resoluciones.overview(record_for(service, repo, dep=1))
        dep = ov["dependencias"]
        assert dep["activas"] == int(df["estado"].fillna("Activa").astype(str).eq("Activa").sum())
        assert dep["cargadas"] == len(df)
        assert [f["nombre"] for f in dep["filas"]] == df["nombre"].tolist()
        assert {o["etiqueta"]: o["id"] for o in dep["opciones_edicion"]} == {
            f"{str(r.get('nombre') or '').strip()} [{str(r.get('estado') or 'Activa').strip()}]": int(r["id"])
            for _, r in df.iterrows()}
        # alta (l. 51733-51747)
        mapa = {"Seleccionar dependencia": (None, "")}
        for _, rd in activas.iterrows():
            nom = str(rd.get("nombre") or "").strip()
            if not nom:
                continue
            et = nom if nom not in mapa else f"{nom} — ID {int(rd['id'])}"
            mapa[et] = (int(rd["id"]), nom)
        assert [(o["etiqueta"], o["id"]) for o in ov["alta"]["dependencias"]] == [(k, v[0]) for k, v in mapa.items()]
        raise psycopg.Rollback(tx)


# ------------------------------------------------------------------------------------------ selectores del alta
def test_periodos_del_alta_y_del_selector_de_docentes(service, repo, db_conn, resoluciones):
    for dep in (1, 9):
        ns = certified_resoluciones(db_conn, INST, dep)
        df_per = ns["get_periodos"]()
        mapa = {"Sin período": None}  # l. 51756-51765
        for _, rp in df_per.sort_values(["anio", "semestre"], ascending=[False, False]).iterrows():
            et = str(rp.get("nombre") or f"{rp.get('anio','')}-{rp.get('semestre','')}")
            if et not in mapa:
                mapa[et] = int(rp["id"])
        assert L.opciones_periodo_alta(_lec(db_conn, dep).periodos()) == mapa
        df = df_per.copy()  # l. 51812-51844
        for col in ["anio", "semestre", "id"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.sort_values(["anio", "semestre", "id"], ascending=[False] * 3, kind="stable")
        mapa2 = {}
        for _, rp in df.iterrows():
            pid = int(rp.get("id"))
            nombre = str(rp.get("nombre") or "").strip() or f"Período {pid}"
            et = nombre if nombre not in mapa2 else f"{nombre} — ID {pid}"
            mapa2[et] = pid
        assert L.opciones_periodo_docentes(_lec(db_conn, dep).periodos()) == mapa2
        ultimo = ns["get_ultimo_periodo"]()
        assert _lec(db_conn, dep).ultimo_periodo()["id"] == ultimo["id"]


@pytest.mark.parametrize("dep", [1, 9])
def test_docentes_por_periodo_v253_todos_los_periodos(db_conn, dep):
    ns = certified_resoluciones(db_conn, INST, dep)
    lec = _lec(db_conn, dep)
    for pid in [int(p["id"]) for p in lec.repo.periods()]:
        for solo in (True, False):
            _igual(ns["_docentes_resoluciones_por_periodo_v253"](pid, solo_activas=solo),
                   lec.docentes_por_periodo_v253(pid, solo_activas=solo))
    _igual(ns["_docentes_resoluciones_por_periodo_v253"](None), lec.docentes_por_periodo_v253(None))


def test_servicio_docentes_modos_y_textos(service, repo, db_conn, resoluciones):
    rec = record_for(service, repo, dep=1)
    ns = certified_resoluciones(db_conn, INST, 1)
    ultimo = ns["get_ultimo_periodo"]()
    r1 = resoluciones.docentes(rec, {"modo": "Designaciones activas del período actual"})
    assert r1["filas"] == ns["_docentes_resoluciones_por_periodo_v253"](int(ultimo["id"]), solo_activas=True) \
        .astype(str).to_dict("records")
    assert r1["caption"] == (f"Mostrando personas con cualquier designación **Activa** en **{ultimo['nombre']}**, "
                             "incluidas las de funciones no docentes.")
    viejo = min(int(p["id"]) for p in _lec(db_conn, 1).repo.periods())
    r2 = resoluciones.docentes(rec, {"modo": "Elegir un período", "periodo_id": viejo})
    assert r2["filas"] == ns["_docentes_resoluciones_por_periodo_v253"](viejo, solo_activas=False).astype(str) \
        .to_dict("records")
    assert "aunque el período hoy sea histórico" in r2["caption"]
    with pytest.raises(Exception):
        resoluciones.docentes(rec, {"modo": "Elegir un período", "periodo_id": 987654321})


@pytest.mark.parametrize("tipo,funcion", [("investigacion", "get_proyectos_investigacion"),
                                          ("extension", "get_proyectos_extension")])
def test_tabla_de_proyectos(service, repo, db_conn, resoluciones, tipo, funcion):
    ns = certified_resoluciones(db_conn, INST, 1)
    df_pr = ns[funcion]()
    filas = []  # l. 51941-51956
    for _, rr in df_pr.iterrows():
        pid = int(rr.get("id"))
        filas.append({"ID": pid, "Código": str(rr.get("codigo_proyecto", "") or "").strip(),
                      "Proyecto": str(rr.get("nombre_proyecto", "") or "").strip() or f"Proyecto {pid}",
                      "Estado": str(rr.get("estado", "") or "").strip(), "Inicio": rr.get("fecha_inicio", ""),
                      "Fin": rr.get("fecha_fin", ""),
                      "Departamento creador": str(rr.get("departamento_creador", "") or "").strip()})
    esperado = pd.DataFrame(filas)
    _igual(esperado, _lec(db_conn, 1).proyectos(tipo))
    out = resoluciones.proyectos(record_for(service, repo, dep=1), {"tipo": tipo})
    assert [f["ID"] for f in out["filas"]] == esperado["ID"].tolist()


# ------------------------------------------------------------------------------------------ reglas puras
def test_constantes_y_normalizaciones_certificadas(db_conn):
    ns = certified_resoluciones(db_conn, INST, 1)
    assert R.CATEGORIAS_RESPALDO_V249 == ns["CATEGORIAS_RESPALDO_V249"]
    for nombre in ["  Rectorado ", "consejo   superior", "Secretaría  Académica", "", None, "RECTORADO"]:
        assert R.nombre_dependencia_v262(nombre) == ns["_nombre_dependencia_documental_v262"](nombre)
        assert R.tipo_resolucion_legacy_v262(nombre) == ns["_tipo_resolucion_legacy_desde_dependencia_v262"](nombre)
    docentes = [{"cuil": "20-1-1", "nombre": "A"}, {"cuil": "201-1", "nombre": "dup"}, ("27-2-2", "B", "Mov", "Det"),
                {"cuil": "", "nombre": "sin"}, "x", {"cuil": "30-3-3", "docente": "C", "movimiento": "M"}]
    assert R.normalizar_docentes_respaldo_v251(docentes) == ns["_normalizar_docentes_respaldo_v251"](docentes)
    proyectos = [{"tipo": "investigacion", "id": 3, "nombre": "P"}, {"proyecto_tipo": "investigacion", "proyecto_id": 3},
                 ("extension", "7", "E", "C"), {"id": "x"}, {"tipo": "", "id": 2}]
    assert R.normalizar_proyectos_respaldo_v261(proyectos, "investigacion") == \
        ns["_normalizar_proyectos_respaldo_v261"](proyectos, "investigacion")
    for tipo, num, dep in [("Resolución", "1/2026", "Rectorado"), ("Otro", "", ""), (None, None, None)]:
        assert R.etiqueta_acto(tipo, num, dep) == ns["_etiqueta_acto_v263"](tipo, num, dep)


# ------------------------------------------------------------------------------------------ Resumen docente (Etapa 4)
def _reconstruir_resumen(lec: Lecturas, cuil) -> pd.DataFrame:
    """Consolidacion v263 (l. 51302-51473) + v266 (l. 55808-55874) a partir de las fuentes NEXT (solo en el test: la
    integracion del Resumen es de la Etapa 4)."""
    f = lec.fuentes_resumen_docente(cuil)
    cols = ["Código", "Dependencia emisora", "Tipo de movimiento", "Detalle"]
    if not f["clave"]:
        return pd.DataFrame(columns=cols)
    filas = []
    for r in f["repositorio"]:
        filas.append({"Código": R.etiqueta_acto(r.get("tipo_documento"), r.get("numero")),
                      "Dependencia emisora": str(r.get("dependencia_emisora", "") or "").strip(),
                      "Tipo de movimiento": str(r.get("tipo_movimiento", "") or "").strip(),
                      "Detalle": str(r.get("detalle", "") or "").strip(), "_fecha": r.get("fecha"), "_fuente": 0})
    for r in f["disposiciones"]:
        filas.append({"Código": R.etiqueta_acto("Disposición", r.get("numero")),
                      "Dependencia emisora": str(r.get("dependencia_emisora", "") or "").strip(),
                      "Tipo de movimiento": "Generación de disposición",
                      "Detalle": str(r.get("detalle", "") or r.get("tipo", "") or "").strip(),
                      "_fecha": r.get("fecha"), "_fuente": 1})
    from disposiciones.rules import es_ad_honorem_v162
    for r in f["pendientes"]:
        tipo_des = str(r.get("tipo_designacion", "") or "").strip()
        detalle = " · ".join([x for x in [str(r.get("periodo", "") or "").strip(), str(r.get("cargo", "") or "").strip(),
                                         str(r.get("dedicacion", "") or "").strip(), tipo_des,
                                         ("Ad Honorem" if es_ad_honorem_v162(r.get("ad_honorem")) else "Rentada")] if x])
        filas.append({"Código": R.etiqueta_acto("Resolución", r.get("numero_resolucion"))
                      + " — pendiente de vincular al repositorio",
                      "Dependencia emisora": "Consejo Superior" if tipo_des.casefold() == "concursado" else "Rectorado",
                      "Tipo de movimiento": "Designación docente (pendiente de vincular)", "Detalle": detalle,
                      "_fecha": r.get("fecha_desde"), "_fuente": 2})
    if filas:
        out = pd.DataFrame(filas)
        out["_fecha_ord"] = pd.to_datetime(out.get("_fecha"), errors="coerce")
        out["_dup"] = (out["Código"].fillna("").astype(str).str.strip().str.casefold() + "|"
                       + out["Dependencia emisora"].fillna("").astype(str).str.strip().str.casefold() + "|"
                       + out["Tipo de movimiento"].fillna("").astype(str).str.strip().str.casefold())
        out = out.sort_values(["_fuente", "_fecha_ord"], ascending=[True, False], kind="stable")
        out = out.drop_duplicates("_dup", keep="first")
        out = out.sort_values(["_fecha_ord", "_fuente"], ascending=[False, True], kind="stable")
        base = out[cols].reset_index(drop=True)
    else:
        base = pd.DataFrame(columns=cols)
    extra = [{"Código": R.etiqueta_acto(r.get("tipo_documento"), r.get("numero")),
              "Dependencia emisora": str(r.get("dependencia_emisora") or ""),
              "Tipo de movimiento": str(r.get("tipo_movimiento") or ""), "Detalle": str(r.get("detalle") or "")}
             for r in f["vinculos_v266"]]
    if extra:
        base = pd.concat([base, pd.DataFrame(extra)], ignore_index=True, sort=False)
        base = base.drop_duplicates(subset=cols, keep="first")
    return base.reset_index(drop=True)


def test_fuentes_del_resumen_reconstruyen_el_certificado(db_conn):
    cuiles = [r[0] for r in db_conn.execute(
        "SELECT DISTINCT cuil FROM documentos_respaldo_docentes WHERE institucion_id=1 UNION "
        "SELECT * FROM (SELECT DISTINCT cuil FROM disposiciones WHERE institucion_id=1 ORDER BY cuil LIMIT 3) a UNION "
        "SELECT * FROM (SELECT DISTINCT cuil FROM designaciones WHERE institucion_id=1 AND "
        "TRIM(COALESCE(numero_resolucion,''))<>'' ORDER BY cuil LIMIT 3) b").fetchall()]
    assert len(cuiles) >= 3
    for dep in (1, 9):
        ns = certified_resoluciones(db_conn, INST, dep)
        for cuil in cuiles + ["", "sin-digitos"]:
            cert = ns["get_actos_docente_resumen_v263"](cuil)
            _igual(cert.reset_index(drop=True), _reconstruir_resumen(_lec(db_conn, dep), cuil))


def test_resumen_duplicado_certificado_d_ak9(db_conn):
    """D-AK9: el acto vinculado a designacion aparece dos veces (repositorio + v266, Detalle distinto). Se conserva."""
    cuil = db_conn.execute("SELECT des.cuil FROM documentos_respaldo_designaciones r JOIN designaciones des "
                           "ON des.id=r.designacion_id LIMIT 1").fetchone()[0]
    ns = certified_resoluciones(db_conn, INST, 9)
    cert = ns["get_actos_docente_resumen_v263"](cuil)
    assert cert["Código"].duplicated().any()
    _igual(cert, _reconstruir_resumen(_lec(db_conn, 9), cuil))


# ------------------------------------------------------------------------------------------ legacy y ausencias
def _fuentes_modulo() -> str:
    """Codigo de los modulos sin docstrings ni comentarios (la documentacion cita lo excluido)."""
    import ast

    partes = []
    for p in sorted(MODULO.glob("*.py")):
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            cuerpo = getattr(node, "body", None)
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and cuerpo \
                    and isinstance(cuerpo[0], ast.Expr) and isinstance(cuerpo[0].value, ast.Constant) \
                    and isinstance(cuerpo[0].value.value, str):
                node.body = cuerpo[1:] or [ast.Pass()]
        partes.append(ast.unparse(tree))
    return "\n".join(partes)


def test_tabla_legacy_resoluciones_y_resolucion_id_ignoradas():
    texto = _fuentes_modulo()
    assert not re.search(r"\b(FROM|JOIN|INTO|UPDATE)\s+resoluciones\b", texto, re.I)
    assert "resolucion_id" not in texto


def test_ausencias_zip_excel_import_export_filesystem_locks_versionado():
    texto = _fuentes_modulo()
    for prohibido in ("zipfile", "openpyxl", "to_excel", "read_excel", "tempfile", "os.path", "open(", "shutil",
                      "pg_advisory", "advisory", "storage", "huella", "CREATE TABLE", "ALTER TABLE", "INSERT INTO "
                      "dependencias_documentales (institucion_id, nombre, estado, observaciones, fecha_creacion"):
        assert prohibido not in texto, prohibido
    from resoluciones_respaldos.routes import router
    rutas = [r.path for r in router.routes]
    assert not [r for r in rutas if re.search(r"zip|excel|import|export|csv|version|lote", r)]
    assert "/resoluciones-respaldos/documento/pdf/eliminar" not in rutas
    assert not [r for r in rutas if "dependencias/eliminar" in r]
