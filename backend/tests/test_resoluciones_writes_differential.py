"""Diferenciales de ESCRITURA de Resoluciones y respaldos: misma operacion de pantalla, certificado vs NEXT, mismo estado.

Lado certificado: la secuencia de la pagina (l. 51630-52129, transcrita) o del flujo contextual v267 llamando a los
writers certificados (``certified_resoluciones``).  Lado NEXT: el servicio con una sesion real del AuthService (FakeRepo).
Entre ambos, ROLLBACK al SAVEPOINT.  Se comparan las tablas documentales (binario como md5 + largo; ids nuevos
normalizados), la secuencia de COMMITs por operacion B12H (``commit_seq``, ``mutating_statements``,
``committing_writer``) y los eventos sin COMMIT (POST_OPERATION / FAILED).  D-AK8: la atomicidad es la certificada
(1-3 COMMITs en el alta con compensacion; 2 COMMITs en el borrado, con su fallo parcial).
"""

from __future__ import annotations

import json
import pprint
from datetime import date

import psycopg
import pytest

from resoluciones_respaldos import escrituras as E
from resoluciones_respaldos.repository import DocumentosRepository
from resoluciones_respaldos.service import ACTION_DELETE, ACTION_WRITE, Archivo, ResolucionesError, WriterSpec
from resoluciones_support import (  # noqa: F401  (fixtures)
    USER_EMAIL, FIXED_TODAY, audit_rows, audit_store, baseline, certified_resoluciones, db_conn, pdf_sintetico, record_for,
    resoluciones, state,
)

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")

INST = 1
FECHA = date(2026, 10, 20)


def _correr(fn):
    try:
        return fn(), None
    except psycopg.Error:
        raise
    except Exception as exc:
        if isinstance(exc.__context__, psycopg.Error) or isinstance(exc.__cause__, psycopg.Error):
            raise
        return None, exc


def comparar(db_conn, audit_store, certificado, siguiente, dep=1, preparar=None, email=USER_EMAIL):
    """Ejecuta ambos lados desde el mismo estado; devuelve resultados y eventos NEXT (in-tx y separados)."""
    with db_conn.transaction() as outer:
        extra = preparar() if preparar is not None else None
        baseline(db_conn)
        ns = certified_resoluciones(db_conn, INST, dep, email=email)
        with db_conn.transaction() as tx:
            res_c, err_c = _correr(lambda: certificado(ns, extra))
            st_c = state(db_conn, INST)
            ops_c = list(ns["_frames"].ops)
            raise psycopg.Rollback(tx)
        with db_conn.transaction() as tx:
            n = len(audit_store.events)
            res_n, err_n = _correr(lambda: siguiente(extra))
            st_n = state(db_conn, INST)
            eventos = audit_rows(db_conn)
            nuevos = audit_store.events[n:]
            raise psycopg.Rollback(tx)
        raise psycopg.Rollback(outer)
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
    return {"res_c": res_c, "err_c": err_c, "res_n": res_n, "err_n": err_n, "nuevos": nuevos, "eventos": eventos,
            "ops": ops_n}


# ------------------------------------------------------------------------------------------ transcripcion de pantalla
def pagina_guardar(ns, categoria, tipo_documento, dependencia, numero, fecha, periodo_id, docentes, proyectos,
                   titulo="ZZNEXT titulo", detalle="ZZNEXT detalle", observaciones="ZZNEXT obs", archivo=None):
    """"💾 Guardar acto respaldatorio" (l. 51726-52079) con la seleccion ya hecha en las tablas."""
    dependencia_id, dependencia_nombre = dependencia
    tipo_resolucion = ns["_tipo_resolucion_legacy_desde_dependencia_v262"](dependencia_nombre) \
        if tipo_documento == "Resolución" else ""
    proyecto_tipo, proyecto_id, referencia = "", None, ""
    if categoria in {"Designación docente", "Cambio de cargo", "Cambio de dedicación",
                     "Cambio de condición Ad Honorem / Rentada"} and docentes:
        referencia = f"{categoria}: " + "; ".join(f"{d['nombre']} — CUIL {d['cuil']}" for d in docentes)
    elif categoria in {"Proyecto de Extensión", "Proyecto de Investigación"}:
        proyecto_tipo = "extension" if categoria == "Proyecto de Extensión" else "investigacion"
        if proyectos:
            proyecto_id = int(proyectos[0]["id"])
            referencia = f"{categoria}: " + "; ".join((f"[{p['codigo']}] " if p.get("codigo") else "") + p.get("nombre", "")
                                                     for p in proyectos)
    contenido = archivo.contenido if archivo is not None else b""
    if contenido and len(contenido) > 50 * 1024 * 1024:
        return "El PDF supera 50 MB. Reducí su tamaño antes de cargarlo."
    nuevo_id = ns["guardar_documento_respaldo_v251"](
        tipo_documento, categoria, numero, fecha, periodo_id, docentes, proyecto_tipo, proyecto_id, referencia, titulo,
        detalle, observaciones, (archivo.nombre if archivo is not None else ""),
        (archivo.mime if archivo is not None else ""), contenido, tipo_resolucion, proyectos_relacionados=proyectos,
        dependencia_id=dependencia_id, dependencia_nombre=dependencia_nombre)
    cant = len(ns["_normalizar_docentes_respaldo_v251"](docentes))
    cant_proy = len(ns["_normalizar_proyectos_respaldo_v261"](proyectos, proyecto_tipo))
    sufijo = " PDF pendiente de carga." if not contenido else " PDF adjunto."
    if cant_proy > 1:
        return f"Acto guardado correctamente (ID {nuevo_id}) y vinculado a {cant_proy} proyectos." + sufijo
    if cant_proy == 1:
        return f"Acto guardado correctamente (ID {nuevo_id}) y vinculado al proyecto seleccionado." + sufijo
    if cant > 1:
        return f"Acto guardado correctamente (ID {nuevo_id}) y vinculado a {cant} docentes." + sufijo
    if cant == 1:
        return f"Acto guardado correctamente (ID {nuevo_id}) y vinculado al docente seleccionado." + sufijo
    return f"Acto guardado correctamente en el repositorio (ID {nuevo_id})." + sufijo


def _dependencia(db_conn, nombre="Rectorado"):
    row = db_conn.execute("SELECT id, nombre FROM dependencias_documentales WHERE institucion_id=1 AND nombre=%s",
                          [nombre]).fetchone()
    return int(row[0]), str(row[1])


def _mismo_mensaje(r, msg_c):
    """El id nuevo puede diferir (secuencia avanzada por el lado certificado): se compara el texto sin el id."""
    import re
    norm = lambda t: re.sub(r"\(ID \d+\)", "(ID n)", t)  # noqa: E731
    assert norm(r["res_n"]["mensaje"]) == norm(msg_c)


def _pdf(nombre="ZZNEXT acto.pdf", mime="application/pdf", relleno=0):
    return Archivo(nombre=nombre, mime=mime, contenido=pdf_sintetico(nombre, relleno))


# ------------------------------------------------------------------------------------------ alta
def test_alta_otro_sin_dependencia_sin_pdf_sin_vinculos(service, repo, db_conn, audit_store, resoluciones):
    rec = record_for(service, repo, dep=1)
    r = comparar(db_conn, audit_store,
                 lambda ns, _: pagina_guardar(ns, "Otro", "Otro", (None, ""), "", FECHA, None, [], []),
                 lambda _: resoluciones.guardar_acto(rec, {"categoria": "Otro", "tipo_documento": "Otro", "numero": "",
                                                           "fecha": FECHA.isoformat(), "titulo": "ZZNEXT titulo",
                                                           "detalle": "ZZNEXT detalle", "observaciones": "ZZNEXT obs"},
                                                     None))
    assert r["err_c"] is None and r["err_n"] is None
    _mismo_mensaje(r, r["res_c"])
    assert r["ops"][0]["commits"] == [{"commit_seq": 1, "mutating_statements": 1,
                                       "committing_writer": "guardar_documento_respaldo_v249",
                                       "nested_system_task": None}]


def test_alta_resolucion_con_pdf_y_docentes_del_periodo_actual(service, repo, db_conn, audit_store, resoluciones):
    rec = record_for(service, repo, dep=1)
    dep_rect = _dependencia(db_conn)
    archivo = _pdf("ZZNEXT Resolución ñ.pdf")

    def cert(ns, _):
        ultimo = ns["get_ultimo_periodo"]()
        tabla = ns["_docentes_resoluciones_por_periodo_v253"](int(ultimo["id"]), solo_activas=True)
        docentes = [{"cuil": str(r["CUIL"]).strip(), "nombre": str(r["Docente"]).strip()}
                    for _, r in tabla.head(3).iterrows()]
        return pagina_guardar(ns, "Designación docente", "Resolución", dep_rect, "ZZNEXT-77/2026", FECHA, None, docentes,
                              [], archivo=archivo)

    def nxt(_):
        tabla = resoluciones.docentes(rec, {"modo": "Designaciones activas del período actual"})["filas"]
        return resoluciones.guardar_acto(rec, {
            "categoria": "Designación docente", "tipo_documento": "Resolución", "dependencia_id": dep_rect[0],
            "numero": "ZZNEXT-77/2026", "fecha": FECHA.isoformat(), "titulo": "ZZNEXT titulo",
            "detalle": "ZZNEXT detalle", "observaciones": "ZZNEXT obs",
            "modo_docentes": "Designaciones activas del período actual",
            "docentes": [f["CUIL"] for f in reversed(tabla[:3])]}, archivo)

    r = comparar(db_conn, audit_store, cert, nxt)
    assert r["err_c"] is None and r["err_n"] is None, (r["err_c"], r["err_n"])
    _mismo_mensaje(r, r["res_c"])
    assert [c["committing_writer"] for c in r["ops"][0]["commits"]] == ["guardar_documento_respaldo_v249",
                                                                        "guardar_documento_respaldo_v251"]
    assert r["ops"][0]["commits"][1]["mutating_statements"] == 3
    assert {e["entity_id"] for e in r["eventos"]} == {None}  # D-AK13: sin proyectos, entidad vacia


def test_alta_disposicion_con_varios_proyectos_y_periodo(service, repo, db_conn, audit_store, resoluciones):
    rec = record_for(service, repo, dep=1)
    dep_cyt = _dependencia(db_conn, "Secretaría de Ciencia y Tecnología")
    periodo = db_conn.execute("SELECT id FROM periodos WHERE institucion_id=1 AND departamento_id=1 ORDER BY id "
                              "LIMIT 1").fetchone()[0]

    def cert(ns, _):
        df = ns["get_proyectos_investigacion"]()
        proyectos = [{"tipo": "investigacion", "id": int(r["id"]),
                      "nombre": str(r.get("nombre_proyecto", "") or "").strip() or f"Proyecto {int(r['id'])}",
                      "codigo": str(r.get("codigo_proyecto", "") or "").strip()} for _, r in df.iloc[[2, 5, 7]].iterrows()]
        return pagina_guardar(ns, "Proyecto de Investigación", "Disposición", dep_cyt, " ZZNEXT-8/2026 ", FECHA, periodo,
                              [], proyectos, archivo=_pdf())

    def nxt(_):
        filas = resoluciones.proyectos(rec, {"tipo": "investigacion"})["filas"]
        return resoluciones.guardar_acto(rec, {
            "categoria": "Proyecto de Investigación", "tipo_documento": "Disposición", "dependencia_id": dep_cyt[0],
            "numero": " ZZNEXT-8/2026 ", "fecha": FECHA.isoformat(), "periodo_id": periodo, "titulo": "ZZNEXT titulo",
            "detalle": "ZZNEXT detalle", "observaciones": "ZZNEXT obs",
            "proyectos": [filas[7]["ID"], filas[2]["ID"], filas[5]["ID"]]}, _pdf())

    r = comparar(db_conn, audit_store, cert, nxt)
    assert r["err_c"] is None and r["err_n"] is None, (r["err_c"], r["err_n"])
    _mismo_mensaje(r, r["res_c"])
    assert [c["committing_writer"] for c in r["ops"][0]["commits"]] == ["guardar_documento_respaldo_v249",
                                                                        "_vincular_proyectos_documento_v261"]
    primer = resoluciones.proyectos(rec, {"tipo": "investigacion"})["filas"][2]["ID"]
    assert {e["entity_id"] for e in r["eventos"]} == {str(primer)}  # D-AK13: primer proyecto como entidad
    assert {e["metadata"].get("entity_param") for e in r["eventos"]} == {"proyecto_id"}


def test_alta_extension_un_proyecto_mime_extrano_y_nombre_unicode(service, repo, db_conn, audit_store, resoluciones):
    rec = record_for(service, repo, dep=1)
    dep_rect = _dependencia(db_conn)
    archivo = _pdf("ZZNEXT acta Ñandú — año.pdf", mime="application/x-weird")

    def cert(ns, _):
        r0 = ns["get_proyectos_extension"]().iloc[0]
        proyectos = [{"tipo": "extension", "id": int(r0["id"]), "nombre": str(r0["nombre_proyecto"]).strip(),
                      "codigo": str(r0.get("codigo_proyecto", "") or "").strip()}]
        return pagina_guardar(ns, "Proyecto de Extensión", "Resolución", dep_rect, "ZZNEXT-9", FECHA, None, [], proyectos,
                              archivo=archivo)

    def nxt(_):
        fila = resoluciones.proyectos(rec, {"tipo": "extension"})["filas"][0]
        return resoluciones.guardar_acto(rec, {"categoria": "Proyecto de Extensión", "tipo_documento": "Resolución",
                                               "dependencia_id": dep_rect[0], "numero": "ZZNEXT-9",
                                               "fecha": FECHA.isoformat(), "titulo": "ZZNEXT titulo",
                                               "detalle": "ZZNEXT detalle", "observaciones": "ZZNEXT obs",
                                               "proyectos": [fila["ID"]]}, archivo)

    r = comparar(db_conn, audit_store, cert, nxt)
    assert r["err_c"] is None and r["err_n"] is None, (r["err_c"], r["err_n"])
    _mismo_mensaje(r, r["res_c"])


def test_alta_contextual_v267_con_vinculo_a_designacion(service, repo, db_conn, audit_store, resoluciones):
    """D-AK4: servicio y writer del alta disponibles para la Etapa 4 (sin pantalla en Designaciones)."""
    rec = record_for(service, repo, dep=1)
    dep_rect = _dependencia(db_conn)
    des_id = db_conn.execute("SELECT d.id FROM designaciones d WHERE d.institucion_id=1 AND d.departamento_id=1 AND NOT "
                             "EXISTS (SELECT 1 FROM documentos_respaldo_designaciones r WHERE r.designacion_id=d.id) "
                             "ORDER BY d.id DESC LIMIT 1").fetchone()[0]
    payload = {"tipo_documento": "Resolución", "categoria": "Designación docente", "numero": "ZZNEXT-55/2026",
               "fecha": FECHA, "periodo_id": None, "dependencia_id": dep_rect[0], "dependencia_nombre": dep_rect[1],
               "titulo": "", "detalle": "", "observaciones": "", "archivo_nombre": "ZZNEXT.pdf",
               "archivo_mime": "application/pdf", "contenido": pdf_sintetico("ctx"), "errores": []}
    config = {"modo": "nuevo", "documento_id": None, "payload": payload}

    def cert(ns, _):
        doc_id, creado = ns["_resolver_acto_contextual_v267"](config, None, "Designación docente", "ZZNEXT ref",
                                                              "ZZNEXT alta", "ZZNEXT det")
        ns["vincular_acto_designacion_v266"](des_id, doc_id)
        return creado

    def nxt(_):
        scope = resoluciones.scope(rec)
        doc_id, creado = resoluciones._op(rec, scope, resoluciones_spec_guardar(),
                                          lambda u: E.resolver_acto_contextual_v267(
                                              u, config, None, "Designación docente", "ZZNEXT ref", "ZZNEXT alta",
                                              "ZZNEXT det"))
        resoluciones._op(rec, scope, WriterSpec("vincular_acto_designacion_v266", ACTION_WRITE, "acto_administrativo",
                                                "designacion_id"),
                         lambda u: E.vincular_acto_designacion_v266(u, des_id, doc_id), entity_raw=des_id)
        return creado

    r = comparar(db_conn, audit_store, cert, nxt)
    assert r["res_c"] is True and r["res_n"] is True, (r["err_c"], r["err_n"])
    assert [o["op"] for o in r["ops"]] == ["guardar_documento_respaldo_v251", "vincular_acto_designacion_v266"]


def resoluciones_spec_guardar():
    from resoluciones_respaldos.service import SPEC_GUARDAR
    return SPEC_GUARDAR


def test_alta_contextual_v267_con_vinculo_a_movimiento_y_compensacion(service, repo, db_conn, audit_store,
                                                                      resoluciones, monkeypatch):
    """Alta inline + vinculo a movimiento; luego la compensacion ``_eliminar_acto_recien_creado_v267`` (registrada en
    B10) borra el acto y su vinculo por la cascada.  Como operacion propia la invoca Designaciones (Etapa 4, D-AK4):
    aca se simula su alta en el catalogo B12H, que ``audit.py`` todavia no incluye (D-AK11)."""
    import audit
    monkeypatch.setattr(audit, "WRITER_NAMES", audit.WRITER_NAMES | {"_eliminar_acto_recien_creado_v267"})
    rec = record_for(service, repo, dep=1)
    mov_id = db_conn.execute("SELECT id FROM movimientos WHERE institucion_id=1 AND departamento_id=1 ORDER BY id DESC "
                             "LIMIT 1").fetchone()[0]
    payload = {"tipo_documento": "Otro", "numero": "", "fecha": FECHA, "dependencia_id": None, "dependencia_nombre": "",
               "titulo": "ZZNEXT", "archivo_nombre": "", "archivo_mime": "", "contenido": b"", "errores": []}
    config = {"modo": "nuevo", "payload": payload}
    spec_mov = WriterSpec("vincular_acto_movimiento_v266", ACTION_WRITE, "acto_administrativo", "movimiento_id")
    spec_comp = WriterSpec("_eliminar_acto_recien_creado_v267", ACTION_WRITE, "acto_administrativo", "documento_id")

    def cert(ns, _):
        doc_id, _c = ns["_resolver_acto_contextual_v267"](config, None, "Cambio de cargo")
        ns["vincular_acto_movimiento_v266"](mov_id, doc_id)
        ns["_eliminar_acto_recien_creado_v267"](doc_id)

    def nxt(_):
        scope = resoluciones.scope(rec)
        doc_id, _c = resoluciones._op(rec, scope, resoluciones_spec_guardar(),
                                      lambda u: E.resolver_acto_contextual_v267(u, config, None, "Cambio de cargo"))
        resoluciones._op(rec, scope, spec_mov, lambda u: E.vincular_acto_movimiento_v266(u, mov_id, doc_id),
                         entity_raw=mov_id)
        resoluciones._op(rec, scope, spec_comp, lambda u: E.eliminar_acto_recien_creado_v267(u, doc_id),
                         entity_raw=doc_id)

    r = comparar(db_conn, audit_store, cert, nxt)
    assert r["err_c"] is None and r["err_n"] is None, (r["err_c"], r["err_n"])
    assert r["ops"][-1]["commits"] == [
        {"commit_seq": 1, "mutating_statements": 4, "committing_writer": "eliminar_documento_respaldo_v251",
         "nested_system_task": None},
        {"commit_seq": 2, "mutating_statements": 1, "committing_writer": "eliminar_documento_respaldo_v249",
         "nested_system_task": None}]


def test_alta_compensacion_si_falla_el_vinculo_de_proyectos(service, repo, db_conn, audit_store, resoluciones,
                                                            monkeypatch):
    rec = record_for(service, repo, dep=1)
    dep_cyt = _dependencia(db_conn, "Secretaría de Ciencia y Tecnología")

    def falla(*a, **k):
        raise RuntimeError("falla simulada del vinculo")

    def cert(ns, _):
        ns["_vincular_proyectos_documento_v261"] = falla
        r0 = ns["get_proyectos_investigacion"]().iloc[0]
        return pagina_guardar(ns, "Proyecto de Investigación", "Disposición", dep_cyt, "ZZNEXT-C", FECHA, None, [],
                              [{"tipo": "investigacion", "id": int(r0["id"]), "nombre": "x", "codigo": ""}],
                              archivo=_pdf())

    def nxt(_):
        fila = resoluciones.proyectos(rec, {"tipo": "investigacion"})["filas"][0]
        monkeypatch.setattr(E, "vincular_proyectos_documento_v261", falla)
        return resoluciones.guardar_acto(rec, {"categoria": "Proyecto de Investigación", "tipo_documento": "Disposición",
                                               "dependencia_id": dep_cyt[0], "numero": "ZZNEXT-C",
                                               "fecha": FECHA.isoformat(), "proyectos": [fila["ID"]]}, _pdf())

    r = comparar(db_conn, audit_store, cert, nxt)
    assert isinstance(r["err_c"], RuntimeError) and isinstance(r["err_n"], ResolucionesError)
    assert r["ops"][0]["commits"] == [
        {"commit_seq": 1, "mutating_statements": 1, "committing_writer": "guardar_documento_respaldo_v249",
         "nested_system_task": None},
        {"commit_seq": 2, "mutating_statements": 1, "committing_writer": "eliminar_documento_respaldo_v249",
         "nested_system_task": None}]
    fallo = [e for e in r["nuevos"] if e.outcome == "FAILED"]
    assert len(fallo) == 1 and fallo[0].metadata["coupled_commits"] == 2 and fallo[0].error_code == "RuntimeError"


def test_alta_writer_envenenado_por_b12d_no_compensa(service, repo, db_conn, audit_store, resoluciones, monkeypatch):
    """B12D capa W: un fallo de base (no de restriccion) en el vinculo envenena el writer; la compensacion interna NO
    corre (0 escrituras posteriores) y el acto queda.  (El arnés certificado no modela B12D: solo lado NEXT.)"""
    rec = record_for(service, repo, dep=1)
    tabla = resoluciones.docentes(rec, {"modo": "Designaciones activas del período actual"})["filas"]

    def falla(self, *a, **k):
        raise psycopg.errors.OperationalError("conexion perdida simulada")

    monkeypatch.setattr(DocumentosRepository, "upsert_docente", falla)
    with db_conn.transaction() as tx:
        antes = db_conn.execute("SELECT count(*) FROM documentos_respaldo").fetchone()[0]
        with pytest.raises(ResolucionesError) as exc:
            resoluciones.guardar_acto(rec, {"categoria": "Designación docente", "tipo_documento": "Otro",
                                            "fecha": FECHA.isoformat(), "modo_docentes":
                                                "Designaciones activas del período actual",
                                            "docentes": [tabla[0]["CUIL"]]}, None)
        assert exc.value.status == 503
        assert db_conn.execute("SELECT count(*) FROM documentos_respaldo").fetchone()[0] == antes + 1
        fallo = audit_store.events[-1]
        assert fallo.outcome == "FAILED" and fallo.metadata == {"coupled_commits": 1}
        raise psycopg.Rollback(tx)


# ------------------------------------------------------------------------------------------ PDF
def _pendiente(db_conn, dep=1, con_pdf=False):
    pdf = pdf_sintetico("previo") if con_pdf else b""
    return db_conn.execute(
        "INSERT INTO documentos_respaldo (institucion_id,departamento_id,tipo_documento,tipo_resolucion,categoria,numero,"
        "fecha,archivo_nombre,archivo_mime,archivo_pdf,archivo_bytes,dependencia_id,dependencia_nombre) VALUES "
        "(1,%s,'Resolución','Rectoral','Designación docente','ZZNEXT-P/2026','2026-01-02',%s,%s,%s,%s,"
        "(SELECT id FROM dependencias_documentales WHERE institucion_id=1 AND nombre='Rectorado'),'Rectorado') "
        "RETURNING id", [dep, "previo.pdf" if con_pdf else "", "application/pdf" if con_pdf else "", pdf,
                         len(pdf)]).fetchone()[0]


@pytest.mark.parametrize("con_pdf", [False, True], ids=["adjuntar_pendiente", "reemplazar"])
def test_adjuntar_y_reemplazar_pdf(service, repo, db_conn, audit_store, resoluciones, con_pdf):
    rec = record_for(service, repo, dep=1)
    archivo = _pdf("ZZNEXT nuevoé.pdf", relleno=5000)
    r = comparar(db_conn, audit_store,
                 lambda ns, did: ns["adjuntar_pdf_documento_respaldo_v272"](did, archivo.nombre, archivo.mime,
                                                                            archivo.contenido),
                 lambda did: resoluciones.adjuntar_pdf(rec, {"id": did}, archivo),
                 preparar=lambda: _pendiente(db_conn, con_pdf=con_pdf))
    assert r["res_c"] is True and r["res_n"]["mensaje"] == ("PDF actualizado correctamente sin modificar el acto ni "
                                                            "sus vínculos.")


def test_adjuntar_pdf_vacio_falla_en_el_writer(service, repo, db_conn, audit_store, resoluciones):
    rec = record_for(service, repo, dep=1)
    vacio = Archivo(nombre="vacio.pdf", mime="application/pdf", contenido=b"")
    r = comparar(db_conn, audit_store,
                 lambda ns, did: ns["adjuntar_pdf_documento_respaldo_v272"](did, "vacio.pdf", "application/pdf", b""),
                 lambda did: resoluciones.adjuntar_pdf(rec, {"id": did}, vacio), preparar=lambda: _pendiente(db_conn))
    assert str(r["err_c"]) == "Seleccioná un PDF válido."
    assert r["err_n"].message == "Seleccioná un PDF válido."
    assert [e.outcome for e in r["nuevos"]] == ["FAILED"]


def test_pdf_valido_se_guarda_byte_a_byte_y_firma_invalida_se_rechaza(service, repo, db_conn, audit_store,
                                                                      resoluciones):
    rec = record_for(service, repo, dep=1)
    with db_conn.transaction() as tx:
        did = _pendiente(db_conn)
        original = pdf_sintetico("byte a byte", 777) + bytes(range(256))
        resoluciones.adjuntar_pdf(rec, {"id": did}, Archivo("b.pdf", "application/pdf", original))
        assert bytes(db_conn.execute("SELECT archivo_pdf FROM documentos_respaldo WHERE id=%s", [did]).fetchone()[0]) \
            == original
        n = len(audit_store.events)
        for falso in (b"PK\x03\x04 docx", b"<html>%PDF-</html>", b" %PDF-1.4", b"%PDF"):
            with pytest.raises(ResolucionesError) as exc:
                resoluciones.adjuntar_pdf(rec, {"id": did}, Archivo("falso.pdf", "application/pdf", falso))
            assert exc.value.code == "PDF_INVALIDO"
        assert len(audit_store.events) == n  # rechazo de pantalla (hardening D-AK2): sin evento ni escritura
        assert bytes(db_conn.execute("SELECT archivo_pdf FROM documentos_respaldo WHERE id=%s", [did]).fetchone()[0]) \
            == original
        raise psycopg.Rollback(tx)


# ------------------------------------------------------------------------------------------ dependencias
def test_corregir_dependencia_del_documento(service, repo, db_conn, audit_store, resoluciones):
    rec = record_for(service, repo, dep=1)
    dep_cs = _dependencia(db_conn, "Consejo Superior")
    r = comparar(db_conn, audit_store,
                 lambda ns, did: ns["actualizar_dependencia_documento_v262"](did, dep_cs[0]),
                 lambda did: resoluciones.dependencia_documento(rec, {"id": did, "dependencia_id": dep_cs[0]}),
                 preparar=lambda: _pendiente(db_conn))
    assert r["res_n"]["mensaje"] == f"Dependencia actualizada: {r['res_c']}."


def test_agregar_dependencia_y_duplicado(service, repo, db_conn, audit_store, resoluciones):
    rec = record_for(service, repo, dep=1)
    r = comparar(db_conn, audit_store,
                 lambda ns, _: ns["guardar_dependencia_documental_v262"]("  ZZNEXT   Secretaría  Nueva ", " obs "),
                 lambda _: resoluciones.agregar_dependencia(rec, {"nombre": "  ZZNEXT   Secretaría  Nueva ",
                                                                  "observaciones": " obs "}))
    assert r["res_n"]["mensaje"] == ("Dependencia agregada. Ya puede seleccionarse al cargar documentos en cualquier "
                                     "departamento.")
    r = comparar(db_conn, audit_store,
                 lambda ns, _: ns["guardar_dependencia_documental_v262"]("rectorado", ""),
                 lambda _: resoluciones.agregar_dependencia(rec, {"nombre": "rectorado", "observaciones": ""}))
    assert str(r["err_c"]) == r["err_n"].message == "Ya existe una dependencia con ese nombre en la institución."
    r = comparar(db_conn, audit_store,
                 lambda ns, _: ns["guardar_dependencia_documental_v262"]("   ", ""),
                 lambda _: resoluciones.agregar_dependencia(rec, {"nombre": "   "}))
    assert str(r["err_c"]) == r["err_n"].message == "Indicá el nombre de la dependencia emisora."


def test_editar_dependencia_propaga_a_toda_la_institucion(service, repo, db_conn, audit_store, resoluciones):
    rec = record_for(service, repo, dep=1)

    def preparar():
        dep_id = db_conn.execute("INSERT INTO dependencias_documentales (institucion_id,nombre,estado,observaciones) "
                                 "VALUES (1,'ZZNEXT Dep','Activa','') RETURNING id").fetchone()[0]
        for dep in (1, 9):
            db_conn.execute("INSERT INTO documentos_respaldo (institucion_id,departamento_id,tipo_documento,categoria,"
                            "archivo_nombre,archivo_pdf,dependencia_id,dependencia_nombre) VALUES (1,%s,'Otro','Otro','',"
                            "''::bytea,%s,'ZZNEXT Dep')", [dep, dep_id])
        return dep_id

    r = comparar(db_conn, audit_store,
                 lambda ns, did: ns["actualizar_dependencia_documental_v262"](did, " ZZNEXT  Dep  Renombrada ",
                                                                              "Inactiva", " nota "),
                 lambda did: resoluciones.editar_dependencia(rec, {"id": did, "nombre": " ZZNEXT  Dep  Renombrada ",
                                                                   "estado": "Inactiva", "observaciones": " nota "}),
                 preparar=preparar)
    assert r["res_n"]["mensaje"] == "Dependencia actualizada para toda la institución."
    assert r["ops"][0]["commits"][0]["mutating_statements"] == 2
    r = comparar(db_conn, audit_store,
                 lambda ns, did: ns["actualizar_dependencia_documental_v262"](did, "Consejo Superior", "Activa", ""),
                 lambda did: resoluciones.editar_dependencia(rec, {"id": did, "nombre": "Consejo Superior",
                                                                   "estado": "Activa", "observaciones": ""}),
                 preparar=preparar)
    assert str(r["err_c"]) == r["err_n"].message == "Ya existe otra dependencia con ese nombre en la institución."


# ------------------------------------------------------------------------------------------ vinculos
def test_vincular_y_desvincular_designaciones_con_la_unidad_documental(service, repo, db_conn, audit_store,
                                                                       resoluciones):
    from designaciones import escrituras as DE

    rec = record_for(service, repo, dep=9, superadmin=True)
    des = [r[0] for r in db_conn.execute("SELECT id FROM designaciones WHERE institucion_id=1 AND departamento_id=9 "
                                         "ORDER BY id LIMIT 2").fetchall()]
    doc = db_conn.execute("SELECT id FROM documentos_respaldo WHERE departamento_id=9 LIMIT 1").fetchone()[0]
    spec_v = WriterSpec("vincular_acto_designaciones_masivo_v267", ACTION_WRITE, "acto_administrativo", "documento_id")
    spec_d = WriterSpec("desvincular_acto_designaciones_masivo_v267", ACTION_DELETE, "acto_administrativo", None)

    def cert(ns, _):
        ns["vincular_acto_designaciones_masivo_v267"](des, doc)
        return ns["desvincular_acto_designaciones_masivo_v267"](des[:1])

    def nxt(_):
        scope = resoluciones.scope(rec)
        resoluciones._op(rec, scope, spec_v, lambda u: DE.vincular_actos_masivo(u, spec_v.name, des, doc),
                         entity_raw=doc)
        return resoluciones._op(rec, scope, spec_d, lambda u: DE.desvincular_actos_masivo(u, spec_d.name, des[:1]))

    r = comparar(db_conn, audit_store, cert, nxt, dep=9, email="super@test.local")
    assert r["res_c"] == r["res_n"] == 1


# ------------------------------------------------------------------------------------------ eliminar (D-AK8)
def _con_vinculos(db_conn):
    did = _pendiente(db_conn, con_pdf=True)
    db_conn.execute("INSERT INTO documentos_respaldo_docentes (institucion_id,departamento_id,documento_id,cuil,"
                    "docente_nombre) VALUES (1,1,%s,'20-99110009-9','ZZNEXT')", [did])
    db_conn.execute("INSERT INTO documentos_respaldo_proyectos (institucion_id,departamento_id,documento_id,proyecto_tipo,"
                    "proyecto_id) VALUES (1,1,%s,'investigacion',1)", [did])
    des = db_conn.execute("SELECT d.id FROM designaciones d WHERE d.institucion_id=1 AND d.departamento_id=1 AND NOT "
                          "EXISTS (SELECT 1 FROM documentos_respaldo_designaciones r WHERE r.designacion_id=d.id) "
                          "LIMIT 1").fetchone()[0]
    db_conn.execute("INSERT INTO documentos_respaldo_designaciones (institucion_id,departamento_id,documento_id,"
                    "designacion_id) VALUES (1,1,%s,%s)", [did, des])
    return did


def test_eliminar_superadmin_dos_commits(service, repo, db_conn, audit_store, resoluciones):
    rec = record_for(service, repo, dep=1, superadmin=True)
    r = comparar(db_conn, audit_store, lambda ns, did: ns["eliminar_documento_respaldo_v251"](did),
                 lambda did: resoluciones.eliminar(rec, {"id": did, "confirmar": True}),
                 preparar=lambda: _con_vinculos(db_conn))
    assert r["res_c"] == 1 and r["res_n"]["mensaje"] == "Acto/documento eliminado del repositorio."
    assert r["ops"][0]["commits"] == [
        {"commit_seq": 1, "mutating_statements": 4, "committing_writer": "eliminar_documento_respaldo_v251",
         "nested_system_task": None},
        {"commit_seq": 2, "mutating_statements": 1, "committing_writer": "eliminar_documento_respaldo_v249",
         "nested_system_task": None}]


def test_eliminar_sin_vinculos_delete_de_cero_filas_es_mutante(service, repo, db_conn, audit_store, resoluciones):
    rec = record_for(service, repo, dep=1, superadmin=True)
    r = comparar(db_conn, audit_store, lambda ns, did: ns["eliminar_documento_respaldo_v251"](did),
                 lambda did: resoluciones.eliminar(rec, {"id": did, "confirmar": True}),
                 preparar=lambda: _pendiente(db_conn))
    assert r["ops"][0]["commits"][0]["mutating_statements"] == 4  # 4 DELETE de vinculos con 0 filas


def test_eliminar_falla_el_segundo_commit_y_quedan_borrados_los_vinculos(service, repo, db_conn, audit_store,
                                                                         resoluciones, monkeypatch):
    rec = record_for(service, repo, dep=1, superadmin=True)

    def falla(*a, **k):
        raise RuntimeError("falla simulada del segundo COMMIT")

    def cert(ns, did):
        ns["eliminar_documento_respaldo_v249"] = falla
        return ns["eliminar_documento_respaldo_v251"](did)

    def nxt(did):
        monkeypatch.setattr(E, "eliminar_documento_respaldo_v249", falla)
        return resoluciones.eliminar(rec, {"id": did, "confirmar": True})

    r = comparar(db_conn, audit_store, cert, nxt, preparar=lambda: _con_vinculos(db_conn))
    assert isinstance(r["err_c"], RuntimeError) and isinstance(r["err_n"], ResolucionesError)
    assert [c["committing_writer"] for c in r["ops"][0]["commits"]] == ["eliminar_documento_respaldo_v251"]
    fallo = [e for e in r["nuevos"] if e.outcome == "FAILED"]
    assert fallo[0].metadata["coupled_commits"] == 1
