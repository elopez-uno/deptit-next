"""Diferenciales de ESCRITURA de Disposiciones: misma operacion de pantalla, certificado vs NEXT, desde el mismo estado.

Lado certificado: la secuencia de la pagina (entry l. 67812-68550, transcrita) con los writers certificados
(``certified_disposiciones``) y el runtime B12E certificado (``certified_b12e``) sobre una raiz temporal.  Lado NEXT: el
servicio con una sesion real del AuthService (FakeRepo) y OTRA raiz temporal.  Entre ambos, ROLLBACK al SAVEPOINT.  Se
comparan las tablas (``disposiciones``, parametros, datos por designacion, ``movimientos``, estado de consulta), la
secuencia de COMMITs por operacion B12H, los Word publicados y los ZIP.
"""

from __future__ import annotations

import io
import json
import os
import pprint
import zipfile
from datetime import date

import psycopg
import pytest

import disposiciones_plantilla as P
from disposiciones import escrituras as E
from disposiciones import storage as S
from disposiciones.service import DisposicionesError
from disposiciones_support import (  # noqa: F401  (fixtures)
    DEP_NOMBRES, FIXED_TODAY, audit_rows, audit_store, baseline, certified_b12e, certified_disposiciones, db_conn,
    disposiciones, free_cuil, make_disposiciones, periodo_id, record_for, state, storage_root,
)

from deptit_refactor.b12e import document_isolation as B  # noqa: E402

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")
INST = 1


def _correr(fn):
    try:
        return fn(), None
    except Exception as exc:  # noqa: BLE001  (el error forma parte de lo que se compara)
        return None, exc


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


def comparar(db_conn, audit_store, certificado, siguiente, dep=1, preparar=None):
    if preparar is not None:
        preparar()
    baseline(db_conn)
    ns = certified_disposiciones(db_conn, INST, dep)
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
                                 f"{pprint.pformat([json.loads(x) for x in a if x not in b][:2])}\nsolo NEXT: "
                                 f"{pprint.pformat([json.loads(x) for x in b if x not in a][:2])}")
    con_commits = [o for o in ops_c if o["commits"]]
    assert con_commits == _ops(eventos), f"cert:\n{pprint.pformat(ops_c)}\nNEXT:\n{pprint.pformat(_ops(eventos))}"
    return res_c, err_c, res_n, err_n, nuevos, eventos


def _instalar_plantilla(root, inst=INST, antigua=False):
    d = root / f"inst_{inst}" / "plantillas"
    d.mkdir(parents=True, exist_ok=True)
    (d / "disposicion.docx").write_bytes(P.construir(antigua=antigua))


def _archivos(root):
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())


def _partes(data: bytes) -> dict:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        return {n: zf.read(n) for n in zf.namelist()}


# ------------------------------------------------------------------------------------------ Pestaña 1: Configuracion
def test_guardar_configuracion(service, repo, db_conn, audit_store, disposiciones):
    rec = record_for(service, repo)
    ov = disposiciones.overview(rec)
    valores = dict(ov["configuracion"], rector="ZZNEXT Rectora", genero_director_departamento="Directora",
                   **{"N° CUDAP EXP – UNO de la Asamblea Universitaria": "EXP-ZZ/26"})
    _, _, res, err, _, eventos = comparar(
        db_conn, audit_store, lambda ns: ns["guardar_parametros_disposicion"](dict(valores)),
        lambda: disposiciones.guardar_configuracion(rec, {"valores": valores, "huella": ov["huella_configuracion"]}))
    assert err is None and res["mensaje"] == "Configuración guardada."
    assert [(e["operation"], e["action"], e["action_scope"], e["entity_type"], e["entity_id"], e["audit_mode"])
            for e in eventos] == [("guardar_parametros_disposicion", "disposiciones.write", "department",
                                   "parametros_disposicion", None, "IN_TRANSACTION")]
    assert eventos[0]["metadata"]["mutating_statements"] >= 10  # 10 UPDATE (+ INSERT si faltaba la clave)


def test_guardar_numero_inicial_crea_clave(service, repo, db_conn, audit_store, disposiciones):
    rec = record_for(service, repo, dep=2)
    pid = periodo_id(db_conn, 2, "2026-2")
    info = disposiciones.periodo(rec, {"periodo_id": pid})

    def borrar():  # la clave no existe: UPDATE con rowcount 0 -> INSERT
        db_conn.execute("DELETE FROM disposicion_parametros WHERE institucion_id=1 AND departamento_id=2 AND clave=%s",
                        [f"numero_inicial_disposiciones_periodo_{pid}"])
    with db_conn.transaction() as tx:
        _, _, res, err, _, eventos = comparar(
            db_conn, audit_store, lambda ns: ns["guardar_numero_inicial_disposiciones_v162"](pid, 301),
            lambda: disposiciones.guardar_numero_inicial(rec, {"periodo_id": pid, "numero": 301, "huella": 1}),
            dep=2, preparar=borrar)
        raise psycopg.Rollback(tx)
    assert err is None and res["mensaje"] == "El período comenzará en la disposición N° 301."
    assert [e["metadata"]["mutating_statements"] for e in eventos] == [2]  # UPDATE (0 filas) + INSERT
    assert info["numero_inicial"] == 70


# ------------------------------------------------------------------------------------------ datos por designacion
def _docente_con_designaciones(disposiciones, rec, pid, minimo=1):
    info = disposiciones.periodo(rec, {"periodo_id": pid})
    for f in info["habilitados"]:
        vista = disposiciones.docente(rec, {"periodo_id": pid, "cuil": f["cuil"]})
        if len(vista["designaciones"]) >= minimo:
            return f, vista
    raise AssertionError("sin docentes con designaciones concursadas/interinas")


def test_guardar_datos_docente_2_operaciones_3_commits(service, repo, db_conn, audit_store, disposiciones):
    rec = record_for(service, repo)
    pid = periodo_id(db_conn, 1, "2026-2")
    fila, vista = _docente_con_designaciones(disposiciones, rec, pid)
    cuil = fila["cuil"]
    ediciones = [{"designacion_id": d["designacion_id"], "fecha_desde": "01 de marzo de 2026",
                  "fecha_hasta": "  28/02/2027 ", "observaciones": " obs ZZNEXT "} for d in vista["designaciones"]]

    def pagina(ns):
        """l. 68262-68311."""
        ctx = ns["obtener_contexto_docente_disposicion"](cuil, pid)
        form = [{**d, "resolucion": d.get("resolucion", ""), "fecha_desde": ed["fecha_desde"],
                 "fecha_hasta": ed["fecha_hasta"], "observaciones": ed["observaciones"]}
                for d, ed in zip(ctx["designaciones_disposicion"], ediciones)]
        ns["guardar_datos_designaciones_docente_disposicion"](cuil, form)
        legacy = ns["get_parametros_docente_disposicion"](cuil)
        legacy["observaciones"] = "Obs general ZZNEXT"
        ns["guardar_parametros_docente_disposicion"](cuil, legacy)
    _, err_c, res, err, _, eventos = comparar(
        db_conn, audit_store, pagina,
        lambda: disposiciones.guardar_datos(rec, {"periodo_id": pid, "cuil": cuil, "designaciones": ediciones,
                                                  "observaciones_generales": "Obs general ZZNEXT",
                                                  "huella_designaciones": vista["huella_designaciones"]}))
    assert err_c is None and err is None and res["mensaje"] == "Datos guardados por designación y departamento."
    assert [(e["operation"], e["entity_type"], e["entity_id"], e["metadata"]["commit_seq"]) for e in eventos] == [
        ("guardar_datos_designaciones_docente_disposicion", "designacion", cuil, 1),
        ("guardar_parametros_docente_disposicion", "parametros_disposicion", cuil, 1),
        ("guardar_parametros_docente_disposicion", "parametros_disposicion", cuil, 2)]


# ------------------------------------------------------------------------------------------ generacion individual
def _pagina_individual(ns, rt, pid, cuil, numero, fecha, tipo, estado, obs):
    """l. 68100-68454 con los valores por defecto del formulario (casillas segun el contexto, fechas recuperadas)."""
    ctx = ns["obtener_contexto_docente_disposicion"](cuil, pid)
    parametros = ns["get_parametros_disposicion"]()
    conc, inter = ctx.get("tiene_concursado", False), ctx.get("tiene_interino", False)
    es_inv = ctx.get("tiene_investigacion_o_extension", ctx.get("tiene_investigacion", False))
    docente_nombre, cargo, dedicacion = ctx.get("docente", ""), ctx.get("cargo", ""), ctx.get("dedicación", "")
    asig = ctx.get("asignaturas que dicta con días, horarios, las carreras a las que pertenecen y escuelas",
                   ctx.get("asignaturas que dicta con las carreras a las que pertenecen y escuelas", ""))
    escuelas = ctx.get("Escuelas en las que se encuentran las materias que dicta", "")
    ef = ns["_estado_funcional_disposicion_v163"](cuil, pid)
    nd, mixta, tiene_nd = bool(ef["es_exclusivamente_no_docente"]), bool(ef["es_mixta"]), bool(ef["tiene_no_docente"])
    texto_nd = ns["_texto_funcion_no_docente_para_disposicion_v164"](cuil, pid)
    form = [{**d, "resolucion": d.get("resolucion", ""), "fecha_desde": d.get("fecha_desde", ""),
             "fecha_hasta": d.get("fecha_hasta", ""), "observaciones": d.get("observaciones", "")}
            for d in ctx.get("designaciones_disposicion", []) or []]
    considerandos = ns["construir_considerandos_designaciones_docente"](ctx.get("docente", cuil), cuil, form,
                                                                        incluir_concursado=conc, incluir_interino=inter)
    texto_inv = ctx.get("Texto funciones de investigación", "")
    norm = ns["_normalizar_tipo_designacion_disposicion"]
    pc = next((x for x in form if norm(x.get("tipo_designacion")) == "Concursado"), {})
    pi = next((x for x in form if norm(x.get("tipo_designacion")) == "Interino"), {})
    variables = {}
    variables.update(parametros)
    variables.update(ctx)
    variables.update({
        "Fecha Disposición": fecha.strftime("%d/%m/%Y"), "número_disposición": numero,
        "departamento_disposicion_encabezado": ctx.get("texto_departamento_disposicion", "")
        or ns["texto_departamento_disposicion_docente"](cuil, pid),
        "fecha": parametros.get("fecha_acta_rector", ""), "fecha_acta_rector": parametros.get("fecha_acta_rector", ""),
        "docente": docente_nombre, "cuil": cuil, "CUIL": cuil, "cargo": cargo, "dedicación": dedicacion,
        "texto_departamentos_revistara": ctx.get("texto_departamentos_revistara", ""),
        "departamento_revistara": ctx.get("texto_departamentos_revistara", ""),
        "asignaturas que dicta con las carreras a las que pertenecen y escuelas": asig,
        "asignaturas que dicta con días, horarios, las carreras a las que pertenecen y escuelas": asig,
        "ES_FUNCION_NO_DOCENTE": nd, "ES_FUNCION_MIXTA": mixta,
        "Texto función no docente": str(texto_nd or "").strip() if tiene_nd else "",
        "Texto variable Artículo 1": str(texto_nd or "").strip() if tiene_nd else "",
        "Escuelas en las que se encuentran las materias que dicta": escuelas,
        "fecha_desde_interino": pi.get("fecha_desde", ""), "fecha_hasta_interino": pi.get("fecha_hasta", ""),
        "Rol en su Proyecto de Investigación": ctx.get("Rol en su Proyecto de Investigación", ""),
        "Nombre Proyecto de Investigación": ctx.get("Nombre Proyecto de Investigación", ""),
        "Código Interno del Proyecto": ctx.get("Código Interno del Proyecto", ""),
        "Instituto/Departamento al que pertenece el proyecto": ctx.get("Instituto/Departamento al que pertenece el proyecto", ""),
        "Texto funciones de investigación": texto_inv, "Texto funciones de investigación y extensión": texto_inv,
        "Tipo funciones investigación/extensión": ctx.get("Tipo funciones investigación/extensión", "investigación"),
        "considerandos_designaciones": considerandos, "designaciones_disposicion": form,
        "resolucion_cs_concursado": pc.get("resolucion", ""), "resolucion_cs_interino": pi.get("resolucion", ""),
        "resolucion_rectoral_interino": pi.get("resolucion", ""), "fecha_desde_concursado": pc.get("fecha_desde", ""),
        "fecha_hasta_concursado": pc.get("fecha_hasta", ""),
    })
    condiciones = {"SI_TIENE_CONCURSADO": conc, "SI_TIENE_INTERINO": inter, "SI_INVESTIGADOR": es_inv,
                   "SI_NO_INVESTIGA": not es_inv}
    if tiene_nd and not str(texto_nd or "").strip():
        raise ValueError("bloqueo no docente")
    return rt.generar(pid, fecha, tipo, numero, cuil, docente_nombre,
                      f"Disposición generada para {docente_nombre} - {tipo}", obs, estado, variables, condiciones)


def _body_individual(vista, pid, estado="Emitida"):
    return {"periodo_id": pid, "cuil": vista["cuil"], "huella": vista["huella"], "fecha": FIXED_TODAY.isoformat(),
            "tipo": "Asignación de funciones docentes", "estado": estado, "observaciones": "Obs ZZNEXT",
            "incluir_concursado": vista["tiene_concursado"], "incluir_interino": vista["tiene_interino"],
            "incluir_investigacion": vista["tiene_investigacion_o_extension"],
            "designaciones": [{"designacion_id": d["designacion_id"], "fecha_desde": d["fecha_desde"],
                               "fecha_hasta": d["fecha_hasta"], "observaciones": d["observaciones"]}
                              for d in vista["designaciones"]]}


def _generar_ambos(db_conn, audit_store, disposiciones, rec, tmp_path, storage_root, pid, vista, dep=1,
                   romper_cert=None, romper_next=None):
    cert_root = tmp_path / "cert_root"
    cert_root.mkdir(exist_ok=True)
    _instalar_plantilla(cert_root)
    _instalar_plantilla(storage_root)

    def certificado(ns):
        rt = certified_b12e(ns, cert_root, INST, dep)
        if romper_cert:
            romper_cert(rt)
        return _pagina_individual(ns, rt, pid, vista["cuil"], vista["numero"], FIXED_TODAY,
                                  "Asignación de funciones docentes", "Emitida", "Obs ZZNEXT")
    if romper_next:
        romper_next()
    out = comparar(db_conn, audit_store, certificado,
                   lambda: disposiciones.generar(rec, _body_individual(vista, pid)), dep=dep)
    return out, cert_root


@pytest.mark.parametrize("rasgo", ["con_designaciones", "primero"])
def test_generar_individual_igual_al_certificado(service, repo, db_conn, audit_store, disposiciones, tmp_path,
                                                 storage_root, rasgo):
    rec = record_for(service, repo)
    pid = periodo_id(db_conn, 1, "2026-2")
    if rasgo == "primero":
        fila = disposiciones.periodo(rec, {"periodo_id": pid})["habilitados"][0]
        vista = disposiciones.docente(rec, {"periodo_id": pid, "cuil": fila["cuil"]})
    else:
        _, vista = _docente_con_designaciones(disposiciones, rec, pid, minimo=2)
    (res_c, err_c, res, err, nuevos, eventos), cert_root = _generar_ambos(
        db_conn, audit_store, disposiciones, rec, tmp_path, storage_root, pid, vista)
    assert err_c is None and err is None, (err_c, err)
    assert res["mensaje"] == ("Disposición generada y guardada en historial. El botón de descarga queda disponible "
                              "debajo.")
    assert [(e["operation"], e["entity_type"], e["entity_id"], e["metadata"]["committing_writer"]) for e in eventos] == [
        ("generar_disposicion_word_b12e", "disposicion", vista["cuil"], "guardar_disposicion"),
        ("generar_disposicion_word_b12e", "disposicion", vista["cuil"], "registrar_movimiento")]
    # mismo Word (mismas partes XML), mismo formato de nombre y referencia B12E
    n_files, c_files = _archivos(storage_root), _archivos(cert_root)
    assert len(n_files) == len(c_files) == 2  # plantilla + 1 disposicion
    n_doc = next(f for f in n_files if "disposiciones" in f)
    c_doc = next(f for f in c_files if "disposiciones" in f)
    assert n_doc.split(os.sep)[:3] == c_doc.split(os.sep)[:3] == ["inst_1", "dep_1", "disposiciones"]
    assert B.check_output_name(os.path.basename(n_doc)) and res["file_name"] == os.path.basename(n_doc)
    assert _partes((storage_root / n_doc).read_bytes()) == _partes((cert_root / c_doc).read_bytes())
    assert res_c["file_name"].split("_", 1)[1][:-38] == res["file_name"].split("_", 1)[1][:-38]


def test_falla_render_antes_de_publicar(service, repo, db_conn, audit_store, tmp_path, storage_root):
    def render(*_):
        raise RuntimeError("render")
    dispo = make_disposiciones(service, audit_store, db_conn, storage_root, render=render)
    repo.departments_rows.extend({"id": 9, "institucion_id": 1, "nombre": DEP_NOMBRES[9], "estado": "Activo"}
                                 for _ in [0])
    rec = record_for(service, repo)
    pid = periodo_id(db_conn, 1, "2026-2")
    _, vista = _docente_con_designaciones(dispo, rec, pid)

    def romper(rt):
        rt.ns["generar_word_desde_plantilla_disposicion"] = render
    (_, err_c, _, err, nuevos, eventos), cert_root = _generar_ambos(
        db_conn, audit_store, dispo, rec, tmp_path, storage_root, pid, vista, romper_cert=romper)
    assert isinstance(err_c, RuntimeError) and isinstance(err, DisposicionesError)
    assert err.message.startswith("No se pudo generar el Word:")
    assert _archivos(storage_root) == ["inst_1/plantillas/disposicion.docx".replace("/", os.sep)]
    assert [f for f in _archivos(cert_root) if "disposiciones" in f] == []  # reserva liberada en ambos
    assert eventos == [] and [(e.outcome, e.metadata["coupled_commits"]) for e in nuevos] == [("FAILED", 0)]


def test_falla_guardar_fila_borra_el_word(service, repo, db_conn, audit_store, disposiciones, tmp_path, storage_root,
                                          monkeypatch):
    rec = record_for(service, repo)
    pid = periodo_id(db_conn, 1, "2026-2")
    _, vista = _docente_con_designaciones(disposiciones, rec, pid)

    def falla(*_a, **_k):
        raise psycopg.errors.CheckViolation("insert")

    def romper(rt):
        rt.ns["guardar_disposicion"] = falla
    (_, err_c, _, err, nuevos, eventos), cert_root = _generar_ambos(
        db_conn, audit_store, disposiciones, rec, tmp_path, storage_root, pid, vista, romper_cert=romper,
        romper_next=lambda: monkeypatch.setattr(E, "guardar_disposicion", falla))
    assert err_c is not None and err is not None
    assert [f for f in _archivos(storage_root) if "disposiciones" in f] == []  # compensacion: Word borrado
    assert [f for f in _archivos(cert_root) if "disposiciones" in f] == []
    assert eventos == [] and [(e.outcome, e.error_code) for e in nuevos] == [("FAILED", "CheckViolation")]


def test_falla_movimiento_conserva_fila_y_word(service, repo, db_conn, audit_store, disposiciones, tmp_path,
                                               storage_root, monkeypatch):
    rec = record_for(service, repo)
    pid = periodo_id(db_conn, 1, "2026-2")
    _, vista = _docente_con_designaciones(disposiciones, rec, pid)

    def falla(*_a, **_k):
        raise psycopg.errors.QueryCanceled("movimiento")

    def romper(rt):
        rt.ns["registrar_movimiento"] = falla
    (_, err_c, _, err, nuevos, eventos), cert_root = _generar_ambos(
        db_conn, audit_store, disposiciones, rec, tmp_path, storage_root, pid, vista, romper_cert=romper,
        romper_next=lambda: monkeypatch.setattr(E.DE, "registrar_movimiento", falla))
    assert err_c is not None and err is not None
    assert len([f for f in _archivos(storage_root) if "disposiciones" in f]) == 1  # sin compensacion
    assert len([f for f in _archivos(cert_root) if "disposiciones" in f]) == 1
    assert [e["metadata"]["committing_writer"] for e in eventos] == ["guardar_disposicion"]
    assert [(e.outcome, e.metadata["coupled_commits"]) for e in nuevos] == [("FAILED", 1)]


def test_stale_al_guardar_borra_el_word(service, repo, db_conn, audit_store, disposiciones, storage_root,
                                        monkeypatch):
    """B12I capa U al entrar a ``guardar_disposicion``: el padron cambio despues de publicar -> FAILED sin fila."""
    rec = record_for(service, repo)
    pid = periodo_id(db_conn, 1, "2026-2")
    _, vista = _docente_con_designaciones(disposiciones, rec, pid)
    _instalar_plantilla(storage_root)
    original = E.generar_disposicion_word

    def con_cambio(u, *a, stale=None, **k):
        def stale_tras_cambio():
            db_conn.execute("UPDATE disposicion_parametros SET valor='5000' WHERE institucion_id=1 AND "
                            "departamento_id=1 AND clave=%s", [f"numero_inicial_disposiciones_periodo_{pid}"])
            stale()
        return original(u, *a, stale=stale_tras_cambio, **k)
    monkeypatch.setattr(E, "generar_disposicion_word", con_cambio)
    with db_conn.transaction() as tx:
        n = len(audit_store.events)
        with pytest.raises(DisposicionesError) as exc:
            disposiciones.generar(rec, _body_individual(vista, pid))
        assert exc.value.code == "STALE" and "[B12I: get_docentes_activos_para_disposiciones_v155]" in exc.value.message
        assert [f for f in _archivos(storage_root) if "disposiciones" in f] == []
        assert [(e.outcome, e.error_code) for e in audit_store.events[n:]] == [("FAILED", "StaleDecisionError")]
        raise psycopg.Rollback(tx)


# ------------------------------------------------------------------------------------------ generacion masiva (D10)
def _pagina_masiva(ns, rt, pid, periodo_sel, fecha, tipo, estado, fallar_cuil=None):
    """l. 67956-68065 (plantilla OK)."""
    df = ns["get_docentes_activos_para_disposiciones_v155"](pid)
    parametros = ns["get_parametros_disposicion"]()
    preparados, sin_acto, sin_funcion, errores = [], [], [], []
    for _, row in df.iterrows():
        cuil_m = str(row.get("cuil") or "").strip()
        numero_m = str(int(row.get("numero_disposicion_auto") or 0))
        try:
            prep = ns["preparar_disposicion_automatica_v158"](cuil_m, pid, numero_m, fecha, parametros=parametros)
            preparados.append(prep)
            if prep.get("designaciones_incompletas"):
                sin_acto.append({"N° disposición": numero_m, "Docente": prep.get("docente", cuil_m), "CUIL": cuil_m})
            if prep.get("funcion_no_docente_sin_texto"):
                sin_funcion.append({"N° disposición": numero_m, "Docente": prep.get("docente", cuil_m), "CUIL": cuil_m})
        except Exception as e:  # noqa: BLE001
            errores.append({"N° disposición": numero_m, "Docente": row.get("nombre_completo", ""), "Error": str(e)})
    if errores:
        return {"bloqueo": "errores", "tabla": errores}
    if sin_acto:
        return {"bloqueo": "sin_acto", "tabla": sin_acto}
    if sin_funcion:
        return {"bloqueo": "sin_funcion", "tabla": sin_funcion}
    registros, errores_gen = [], []
    render = rt.ns["generar_word_desde_plantilla_disposicion"]
    for prep in preparados:
        if fallar_cuil and prep["cuil"] == fallar_cuil:
            rt.ns["generar_word_desde_plantilla_disposicion"] = lambda *_: (_ for _ in ()).throw(RuntimeError("x"))
        try:
            g = rt.generar(pid, fecha, tipo, prep["numero"], prep["cuil"], prep["docente"],
                           f"Disposición generada para {prep['docente']} - {tipo}",
                           "Generación masiva desde Nueva disposición", estado, prep["variables"], prep["condiciones"])
            registros.append({"label": f"{periodo_sel}_Disposicion_{prep['numero']}_{prep['docente']}",
                              "bytes": g["bytes"]})
        except Exception as e:  # noqa: BLE001
            errores_gen.append({"N° disposición": prep["numero"], "Docente": prep["docente"], "Error": str(e)})
        finally:
            rt.ns["generar_word_desde_plantilla_disposicion"] = render
    zip_bytes, n = B.zip_payloads((g["label"], g["bytes"]) for g in registros) if registros else (b"", 0)
    return {"generadas": n, "zip": zip_bytes, "errores": errores_gen}


def test_masiva_preflight_con_error_no_genera_nada(service, repo, db_conn, audit_store, disposiciones, tmp_path,
                                                   storage_root):
    """Datos reales: designaciones activas sin acto vinculado -> el lote completo se bloquea (0 filas/movs/Word)."""
    rec = record_for(service, repo)
    pid = periodo_id(db_conn, 1, "2026-2")
    _instalar_plantilla(storage_root)
    cert_root = tmp_path / "c"
    cert_root.mkdir()
    _instalar_plantilla(cert_root)
    huella = disposiciones.periodo(rec, {"periodo_id": pid})["huella_padron"]
    res_c, _, res, err, nuevos, eventos = comparar(
        db_conn, audit_store,
        lambda ns: _pagina_masiva(ns, certified_b12e(ns, cert_root, INST, 1), pid, "2026-2", FIXED_TODAY,
                                  "Asignación de funciones docentes", "Borrador"),
        lambda: disposiciones.generar_masiva(rec, {"periodo_id": pid, "fecha": FIXED_TODAY.isoformat(),
                                                   "tipo": "Asignación de funciones docentes", "estado": "Borrador",
                                                   "huella_padron": huella}))
    assert err is None and res_c["bloqueo"] == "sin_acto" and res["tabla"] == res_c["tabla"] and res["generadas"] == 0
    assert res["mensaje"].startswith("No se generó ninguna disposición porque hay docentes con una designación")
    assert eventos == [] and nuevos == []
    assert [f for f in _archivos(storage_root) if "disposiciones" in f] == []


def _lote_sintetico(db_conn, cuiles):
    """Periodo ZZNEXT del departamento 9 con 3 docentes sinteticos (designaciones Activas no concursadas/interinas:
    sin considerandos ni actos que bloqueen el lote)."""
    pid = db_conn.execute("INSERT INTO periodos (institucion_id, departamento_id, nombre, anio, semestre, estado) VALUES "
                          "(1, 9, 'ZZNEXT-2031-1', 2031, 1, 'Abierto') RETURNING id").fetchone()[0]
    for i, c in enumerate(cuiles):
        db_conn.execute("INSERT INTO docentes (institucion_id, departamento_id, cuil, apellido, nombres, estado) VALUES "
                        "(1, 9, %s, %s, 'ZZNEXT', 'Activo')", [c, f"ZZNEXT Lote {3 - i}"])
        db_conn.execute("INSERT INTO designaciones (institucion_id, departamento_id, periodo_id, cuil, cargo, dedicacion, "
                        "horas, tipo_designacion, estado, funcion_no_docente) VALUES (1, 9, %s, %s, 'JTP', 'Simple', 10, "
                        "'Contratado', 'Activa', 0)", [pid, c])
    db_conn.execute("INSERT INTO disposicion_parametros (institucion_id, departamento_id, clave, valor) VALUES "
                    "(1, 9, %s, '501')", [f"numero_inicial_disposiciones_periodo_{pid}"])
    return pid


@pytest.mark.parametrize("con_error", [False, True])
def test_masiva_lote_valido_n_operaciones(service, repo, db_conn, audit_store, disposiciones, tmp_path, storage_root,
                                          con_error):
    repo.departments_rows.append({"id": 9, "institucion_id": 1, "nombre": DEP_NOMBRES[9], "estado": "Activo"})
    rec = record_for(service, repo, superadmin=True, dep=9)
    cuiles = [free_cuil(db_conn, f"20-991300{i}{i}-1") for i in (5, 6, 7)]
    _instalar_plantilla(storage_root)
    cert_root = tmp_path / "c"
    cert_root.mkdir()
    _instalar_plantilla(cert_root)
    with db_conn.transaction() as outer:
        pid = _lote_sintetico(db_conn, cuiles)
        info = disposiciones.periodo(rec, {"periodo_id": pid})
        assert [(f["numero_disposicion_auto"], f["nombre_completo"]) for f in info["habilitados"]] == [
            (501, "ZZNEXT Lote 1, ZZNEXT"), (502, "ZZNEXT Lote 2, ZZNEXT"), (503, "ZZNEXT Lote 3, ZZNEXT")]
        fallar = info["habilitados"][1]["cuil"] if con_error else None
        original_render = disposiciones._render
        if con_error:
            def render(tpl, out, variables, condiciones):
                if variables.get("cuil") == fallar:
                    raise RuntimeError("x")
                return original_render(tpl, out, variables, condiciones)
            disposiciones._render = render
        res_c, _, res, err, nuevos, eventos = comparar(
            db_conn, audit_store,
            lambda ns: _pagina_masiva(ns, certified_b12e(ns, cert_root, INST, 9, rol="superadmin"), pid,
                                      "ZZNEXT-2031-1", FIXED_TODAY, "Asignación de funciones docentes", "Emitida",
                                      fallar_cuil=fallar if con_error else None),
            lambda: disposiciones.generar_masiva(rec, {"periodo_id": pid, "fecha": FIXED_TODAY.isoformat(),
                                                       "tipo": "Asignación de funciones docentes", "estado": "Emitida",
                                                       "huella_padron": info["huella_padron"]}), dep=9)
        disposiciones._render = original_render
        esperadas = 2 if con_error else 3
        assert err is None and res["generadas"] == res_c["generadas"] == esperadas
        assert [e["N° disposición"] for e in res["errores"]] == [e["N° disposición"] for e in res_c["errores"]]
        assert ("aviso" in res) is con_error
        assert len({str(e["correlation_id"]) for e in eventos}) == esperadas  # N operaciones independientes
        assert all(e["metadata"]["commit_seq"] in (1, 2) for e in eventos) and len(eventos) == 2 * esperadas
        assert len([f for f in _archivos(storage_root) if "disposiciones" in f]) == esperadas
        raise psycopg.Rollback(outer)


def test_masiva_zip_lote_igual_al_certificado(service, repo, db_conn, audit_store, disposiciones, tmp_path,
                                              storage_root):
    repo.departments_rows.append({"id": 9, "institucion_id": 1, "nombre": DEP_NOMBRES[9], "estado": "Activo"})
    rec = record_for(service, repo, superadmin=True, dep=9)
    cuiles = [free_cuil(db_conn, f"20-991300{i}{i}-1") for i in (5, 6, 7)]
    _instalar_plantilla(storage_root)
    cert_root = tmp_path / "c"
    cert_root.mkdir()
    _instalar_plantilla(cert_root)
    with db_conn.transaction() as outer:
        pid = _lote_sintetico(db_conn, cuiles)
        ns = certified_disposiciones(db_conn, INST, 9)
        with db_conn.transaction() as tx:
            res_c = _pagina_masiva(ns, certified_b12e(ns, cert_root, INST, 9, rol="superadmin"), pid, "ZZNEXT-2031-1",
                                   FIXED_TODAY, "Asignación de funciones docentes", "Emitida")
            raise psycopg.Rollback(tx)
        info = disposiciones.periodo(rec, {"periodo_id": pid})
        res = disposiciones.generar_masiva(rec, {"periodo_id": pid, "fecha": FIXED_TODAY.isoformat(),
                                                 "tipo": "Asignación de funciones docentes", "estado": "Emitida",
                                                 "huella_padron": info["huella_padron"]})
        contenido, nombre = disposiciones.zip_lote(rec, {"periodo_id": pid, "ids": res["ids"]})
        assert nombre == res["zip_nombre"] == "Disposiciones_ZZNEXT-2031-1.zip"
        with zipfile.ZipFile(io.BytesIO(contenido)) as a, zipfile.ZipFile(io.BytesIO(res_c["zip"])) as b:
            assert a.namelist() == b.namelist() == ["ZZNEXT-2031-1_Disposicion_501_ZZNEXT_Lote_1_ZZNEXT.docx",
                                                    "ZZNEXT-2031-1_Disposicion_502_ZZNEXT_Lote_2_ZZNEXT.docx",
                                                    "ZZNEXT-2031-1_Disposicion_503_ZZNEXT_Lote_3_ZZNEXT.docx"]
            for n in a.namelist():
                assert _partes(a.read(n)) == _partes(b.read(n))
        # regenerar el lote: OTRAS filas con los MISMOS numeros (sin UNIQUE, sin reserva)
        res2 = disposiciones.generar_masiva(rec, {"periodo_id": pid, "fecha": date(2026, 11, 1).isoformat(),
                                                  "tipo": "Asignación de funciones docentes", "estado": "Borrador",
                                                  "huella_padron": info["huella_padron"]})
        numeros = [r[0] for r in db_conn.execute("SELECT numero FROM disposiciones WHERE periodo_id=%s ORDER BY id",
                                                [pid]).fetchall()]
        assert res2["generadas"] == 3 and numeros == ["501", "502", "503", "501", "502", "503"]
        raise psycopg.Rollback(outer)


# ------------------------------------------------------------------------------------------ Pestaña 3: eliminar
def test_eliminar_registro_superadmin_igual_al_certificado(service, repo, db_conn, audit_store, disposiciones):
    rec = record_for(service, repo, superadmin=True)
    hist = disposiciones.historial(rec, {"periodo_id": None})
    fila = hist["filas"][0]
    assert fila["documento"]["legado"] is True  # registro historico pre-B12E: se elimina el REGISTRO, no el archivo
    _, _, res, err, _, eventos = comparar(
        db_conn, audit_store, lambda ns: ns["eliminar_disposicion"](fila["id"]),
        lambda: disposiciones.eliminar(rec, {"id": fila["id"], "huella": fila["huella"], "confirmar": True}))
    assert err is None and res == {"mensaje": "Registro eliminado. El archivo Word no se borra automáticamente.",
                                   "tono": "warning"}
    assert [(e["operation"], e["action"], e["entity_type"], e["entity_id"]) for e in eventos] == [
        ("eliminar_disposicion", "disposiciones.delete", "disposicion", None)]
