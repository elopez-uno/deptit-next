"""6A-B3 (aceptacion humana): una resolucion de "Designación docente" se vincula con la(s) designacion(es) CONCRETA(S)
por id real (``documentos_respaldo_designaciones``, el modelo existente: una designacion -> un acto; un acto -> N
designaciones) al cargarla o despues, al editarla; la Disposicion toma el numero de esa vinculacion.

Datos sinteticos ``ZZNEXT`` dentro de la transaccion del test (ROLLBACK)."""

from __future__ import annotations

import pytest

from disposiciones.lecturas import Lecturas as DLecturas
from disposiciones.repository import DisposicionesRepository
from resoluciones_respaldos import service as S
from resoluciones_respaldos.service import ResolucionesError
from resoluciones_support import FIXED_TODAY, audit_store, db_conn, resoluciones, session_for  # noqa: F401

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")


@pytest.fixture
def records(service, repo):
    sup = session_for(service, repo, 1)[0]
    service.set_context(sup, 1, 1, False)
    return {"dep": session_for(service, repo, 3)[0], "super": sup, "lector": session_for(service, repo, 7)[0]}


def _caso(db_conn):
    """Un docente del dep 1 con una designacion Activa Concursado/Interino que la Disposicion considera, y otra
    designacion cualquiera del mismo docente (no se asume una sola)."""
    filas = db_conn.execute(
        "SELECT d.cuil, d.periodo_id, d.id FROM designaciones d WHERE d.institucion_id=1 AND d.departamento_id=1 "
        "AND lower(coalesce(d.estado,''))='activa' AND d.tipo_designacion IN ('Interino','Concursado') "
        "AND d.cuil IN (SELECT cuil FROM designaciones WHERE institucion_id=1 AND departamento_id=1 GROUP BY cuil "
        "HAVING count(*) >= 2) ORDER BY d.id DESC LIMIT 40").fetchall()
    for cuil, pid, did in filas:
        datos = DLecturas(DisposicionesRepository(db_conn, 1, 1), FIXED_TODAY, "").datos_designaciones(cuil, pid)
        if any(x["designacion_id"] == did for x in datos):
            otra = db_conn.execute("SELECT id FROM designaciones WHERE institucion_id=1 AND departamento_id=1 AND "
                                   "cuil=%s AND id<>%s ORDER BY id LIMIT 1", [cuil, did]).fetchone()[0]
            return cuil, pid, did, otra
    pytest.skip("sin docente con >= 2 designaciones y una Activa Concursado/Interino en la base de prueba")


def _alta(resoluciones, rec, db_conn, cuil, pid, numero, designaciones=None, **extra):
    datos = {"categoria": S.CATEGORIA_DESIGNACION, "tipo_documento": "Otro", "numero": numero, "fecha": "2026-03-01",
             "modo_docentes": "Elegir un período", "periodo_docentes_id": pid, "docentes": [cuil], **extra}
    if designaciones is not None:
        datos["designaciones"] = designaciones
    return resoluciones.guardar_acto(rec, datos, None)


def _vinculo(db_conn, designacion_id):
    r = db_conn.execute("SELECT documento_id FROM documentos_respaldo_designaciones WHERE institucion_id=1 AND "
                        "departamento_id=1 AND designacion_id=%s", [designacion_id]).fetchone()
    return None if r is None else r[0]


def _resolucion_disposicion(db_conn, cuil, pid, designacion_id):
    datos = DLecturas(DisposicionesRepository(db_conn, 1, 1), FIXED_TODAY, "").datos_designaciones(cuil, pid)
    return next(x for x in datos if x["designacion_id"] == designacion_id)


def test_selector_muestra_todas_las_designaciones_del_docente_con_datos_para_distinguirlas(resoluciones, records,
                                                                                          db_conn):
    cuil, _pid, did, otra = _caso(db_conn)
    out = resoluciones.designaciones(records["dep"], {"cuiles": [cuil]})
    ids = {f["id"] for f in out["filas"]}
    assert {did, otra} <= ids
    total = db_conn.execute("SELECT count(*) FROM designaciones WHERE institucion_id=1 AND departamento_id=1 AND "
                            "cuil=%s", [cuil]).fetchone()[0]
    assert len(ids) == total  # todas, de todos los periodos
    fila = next(f for f in out["filas"] if f["id"] == did)
    for campo in ("periodo", "cargo", "dedicacion", "tipo_designacion", "fecha_desde", "fecha_hasta", "estado",
                  "acto_administrativo"):
        assert campo in fila
    assert resoluciones.designaciones(records["dep"], {"cuiles": []})["filas"] == []
    with pytest.raises(ResolucionesError) as e:
        resoluciones.designaciones(records["dep"], {"cuiles": "x"})
    assert e.value.status == 422


def test_alta_vincula_la_designacion_concreta_y_la_disposicion_toma_ese_numero(resoluciones, records, db_conn,
                                                                               audit_store):
    cuil, pid, did, otra = _caso(db_conn)
    db_conn.execute("DELETE FROM documentos_respaldo_designaciones WHERE institucion_id=1 AND departamento_id=1 AND "
                    "designacion_id = ANY(%s)", [[did, otra]])
    out = _alta(resoluciones, records["dep"], db_conn, cuil, pid, "ZZNEXT-777/2026", designaciones=[did])
    assert out["tono"] == "success" and "Respalda 1 designación" in out["mensaje"]
    assert _vinculo(db_conn, did) == out["id"]
    assert _vinculo(db_conn, otra) is None  # solo la elegida (nada por inferencia)
    disp = _resolucion_disposicion(db_conn, cuil, pid, did)
    assert disp["resolucion"] == "ZZNEXT-777/2026"
    assert "ZZNEXT-777/2026" in disp["acto_administrativo"]
    # auditoria B12H del writer de vinculo (la misma etiqueta que usa Designaciones)
    ops = [r[0] for r in db_conn.execute("SELECT operation FROM b12h_audit_log WHERE entity_id=%s AND outcome="
                                         "'SUCCESS'", [str(out["id"])]).fetchall()]
    assert "vincular_acto_designaciones_masivo_v267" in ops


def test_alta_valida_ids_categoria_y_vinculo_existente(resoluciones, records, db_conn):
    cuil, pid, did, _otra = _caso(db_conn)
    ajena = db_conn.execute("SELECT id FROM designaciones WHERE institucion_id=1 AND departamento_id=1 AND cuil<>%s "
                            "LIMIT 1", [cuil]).fetchone()[0]
    antes = db_conn.execute("SELECT count(*) FROM documentos_respaldo").fetchone()[0]
    for sel, status in (([ajena], 409), ([True], 422), ("1", 422)):
        with pytest.raises(ResolucionesError) as e:
            _alta(resoluciones, records["dep"], db_conn, cuil, pid, "ZZNEXT-X", designaciones=sel)
        assert e.value.status == status
    with pytest.raises(ResolucionesError) as e:
        _alta(resoluciones, records["dep"], db_conn, cuil, pid, "ZZNEXT-X", designaciones=[did],
              categoria="Cambio de cargo")
    assert e.value.status == 422
    assert db_conn.execute("SELECT count(*) FROM documentos_respaldo").fetchone()[0] == antes  # nada guardado
    # ya respaldada por otro acto -> se exige confirmar el reemplazo
    primero = _alta(resoluciones, records["dep"], db_conn, cuil, pid, "ZZNEXT-A", designaciones=[did])["id"]
    with pytest.raises(ResolucionesError) as e:
        _alta(resoluciones, records["dep"], db_conn, cuil, pid, "ZZNEXT-B", designaciones=[did])
    assert e.value.code == "VINCULO_EXISTENTE" and "ZZNEXT-A" in e.value.message
    assert _vinculo(db_conn, did) == primero
    segundo = _alta(resoluciones, records["dep"], db_conn, cuil, pid, "ZZNEXT-B", designaciones=[did],
                    reemplazar_vinculos=True)["id"]
    assert _vinculo(db_conn, did) == segundo
    assert _resolucion_disposicion(db_conn, cuil, pid, did)["resolucion"] == "ZZNEXT-B"


def test_resolucion_existente_se_edita_y_vincula_despues(resoluciones, records, db_conn):
    cuil, pid, did, otra = _caso(db_conn)
    db_conn.execute("DELETE FROM documentos_respaldo_designaciones WHERE institucion_id=1 AND departamento_id=1 AND "
                    "designacion_id = ANY(%s)", [[did, otra]])
    doc = _alta(resoluciones, records["dep"], db_conn, cuil, pid, "ZZNEXT-555/2026")["id"]  # solo docente, como antes
    assert _vinculo(db_conn, did) is None
    det = resoluciones.documento(records["dep"], {"id": doc})
    assert det["designacion_docente"] is True
    assert {did, otra} <= {f["id"] for f in det["designaciones"]}
    assert not any(f["vinculada"] for f in det["designaciones"])
    # despues: se asocia a las dos designaciones del docente
    r = resoluciones.vincular_designaciones(records["dep"], {"id": doc, "designaciones": [did, otra]})
    assert r["tono"] == "success"
    assert _vinculo(db_conn, did) == doc and _vinculo(db_conn, otra) == doc
    det = resoluciones.documento(records["dep"], {"id": doc})
    assert {f["id"] for f in det["designaciones"] if f["vinculada"]} >= {did, otra}
    assert _resolucion_disposicion(db_conn, cuil, pid, did)["resolucion"] == "ZZNEXT-555/2026"
    assert resoluciones.vincular_designaciones(records["dep"], {"id": doc, "designaciones": [did, otra]})["tono"] == "info"
    # quitar un vinculo usa el writer de desvinculo de Designaciones: documentos.delete (superadmin), como alli
    with pytest.raises(ResolucionesError) as e:
        resoluciones.vincular_designaciones(records["dep"], {"id": doc, "designaciones": [did]})
    assert e.value.status == 403
    resoluciones.vincular_designaciones(records["super"], {"id": doc, "designaciones": [did]})
    assert _vinculo(db_conn, did) == doc and _vinculo(db_conn, otra) is None
    # solo lectura: no escribe
    with pytest.raises(ResolucionesError) as e:
        resoluciones.vincular_designaciones(records["lector"], {"id": doc, "designaciones": [did, otra]})
    assert e.value.status == 403


def test_edicion_rechaza_categoria_no_designacion_y_ids_ajenos(resoluciones, records, db_conn):
    cuil, pid, did, _otra = _caso(db_conn)
    otro = resoluciones.guardar_acto(records["dep"], {"categoria": "Otro", "tipo_documento": "Otro",
                                                      "fecha": "2026-03-01"}, None)["id"]
    assert resoluciones.documento(records["dep"], {"id": otro})["designacion_docente"] is False
    with pytest.raises(ResolucionesError) as e:
        resoluciones.vincular_designaciones(records["dep"], {"id": otro, "designaciones": [did]})
    assert e.value.status == 422
    doc = _alta(resoluciones, records["dep"], db_conn, cuil, pid, "ZZNEXT-C")["id"]
    ajena = db_conn.execute("SELECT id FROM designaciones WHERE institucion_id=1 AND departamento_id=1 AND cuil<>%s "
                            "LIMIT 1", [cuil]).fetchone()[0]
    with pytest.raises(ResolucionesError) as e:
        resoluciones.vincular_designaciones(records["dep"], {"id": doc, "designaciones": [ajena]})
    assert e.value.status == 409


# ----------------------------------------------------------------------------- ronda 2: relaciones editables
def _docentes_periodo(resoluciones, rec, pid, n=2):
    filas = resoluciones.docentes(rec, {"modo": "Elegir un período", "periodo_id": pid})["filas"]
    assert len(filas) >= n
    return filas


def test_alta_designacion_sin_designacion_queda_pendiente_con_aviso(resoluciones, records, db_conn):
    cuil, pid, did, _otra = _caso(db_conn)
    out = _alta(resoluciones, records["dep"], db_conn, cuil, pid, "ZZNEXT-P/2026")
    assert out["tono"] == "success" and out["aviso"] == S.MSG_DESIGNACION_PENDIENTE
    det = resoluciones.documento(records["dep"], {"id": out["id"]})
    assert det["designacion_pendiente"] == S.MSG_DESIGNACION_PENDIENTE
    assert det["relaciones"] == {"docentes": True, "designaciones": True, "proyectos": None}
    resoluciones.vincular_designaciones(records["dep"], {"id": out["id"], "designaciones": [did],
                                                         "reemplazar_vinculos": True})
    assert resoluciones.documento(records["dep"], {"id": out["id"]})["designacion_pendiente"] == ""


def test_designacion_agregar_docente_y_sus_designaciones_despues(resoluciones, records, db_conn):
    cuil, pid, did, _otra = _caso(db_conn)
    otro = next(f for f in _docentes_periodo(resoluciones, records["dep"], pid) if f["CUIL"] != cuil)
    doc = _alta(resoluciones, records["dep"], db_conn, cuil, pid, "ZZNEXT-D2/2026")["id"]
    r = resoluciones.agregar_docentes(records["dep"], {"id": doc, "modo": "Elegir un período", "periodo_id": pid,
                                                       "docentes": [otro["CUIL"]]})
    assert r["tono"] == "success"
    cuiles = {x[0] for x in db_conn.execute("SELECT cuil FROM documentos_respaldo_docentes WHERE documento_id=%s",
                                            [doc]).fetchall()}
    assert cuiles == {cuil, otro["CUIL"]}  # se conserva el existente
    det = resoluciones.documento(records["dep"], {"id": doc})
    del_otro = [f["id"] for f in det["designaciones"] if f["cuil"] == otro["CUIL"]]
    assert del_otro and did in {f["id"] for f in det["designaciones"]}
    resoluciones.vincular_designaciones(records["dep"], {"id": doc, "designaciones": [did, del_otro[0]],
                                                         "reemplazar_vinculos": True})
    det = resoluciones.documento(records["dep"], {"id": doc})  # reabrir
    assert {f["id"] for f in det["designaciones"] if f["vinculada"]} == {did, del_otro[0]}
    filas = resoluciones.overview(records["dep"])["repositorio"]["filas"]
    assert next(f for f in filas if f["id"] == doc)["cantidad_docentes"] == 2
    with pytest.raises(ResolucionesError) as e:  # ya vinculado -> nada nuevo
        resoluciones.agregar_docentes(records["dep"], {"id": doc, "modo": "Elegir un período", "periodo_id": pid,
                                                       "docentes": [cuil]})
    assert e.value.status == 422
    tercero = next((f for f in _docentes_periodo(resoluciones, records["dep"], pid)
                    if f["CUIL"] not in (cuil, otro["CUIL"])), None)
    if tercero is not None:  # solo lectura: B10 deniega (con un docente valido y no vinculado)
        with pytest.raises(ResolucionesError) as e:
            resoluciones.agregar_docentes(records["lector"], {"id": doc, "modo": "Elegir un período", "periodo_id": pid,
                                                              "docentes": [tercero["CUIL"]]})
        assert e.value.status == 403


@pytest.mark.parametrize("categoria", ["Cambio de cargo", "Cambio de dedicación",
                                       "Cambio de condición Ad Honorem / Rentada"])
def test_categorias_de_cambio_agregan_docentes_y_no_designaciones(resoluciones, records, db_conn, categoria):
    cuil, pid, did, _otra = _caso(db_conn)
    otro = next(f for f in _docentes_periodo(resoluciones, records["dep"], pid) if f["CUIL"] != cuil)
    doc = _alta(resoluciones, records["dep"], db_conn, cuil, pid, "ZZNEXT-C/2026", categoria=categoria)["id"]
    det = resoluciones.documento(records["dep"], {"id": doc})
    assert det["relaciones"] == {"docentes": True, "designaciones": False, "proyectos": None}
    resoluciones.agregar_docentes(records["dep"], {"id": doc, "modo": "Elegir un período", "periodo_id": pid,
                                                   "docentes": [otro["CUIL"]]})
    assert db_conn.execute("SELECT count(*) FROM documentos_respaldo_docentes WHERE documento_id=%s",
                           [doc]).fetchone()[0] == 2
    with pytest.raises(ResolucionesError) as e:
        resoluciones.vincular_designaciones(records["dep"], {"id": doc, "designaciones": [did]})
    assert e.value.status == 422
    with pytest.raises(ResolucionesError) as e:
        resoluciones.vincular_proyectos(records["dep"], {"id": doc, "proyectos": [1]})
    assert e.value.status == 422


@pytest.mark.parametrize("categoria, tipo", [("Proyecto de Investigación", "investigacion"),
                                             ("Proyecto de Extensión", "extension")])
def test_proyectos_agregar_quitar_y_reabrir(resoluciones, records, db_conn, categoria, tipo):
    filas = resoluciones.proyectos(records["dep"], {"tipo": tipo})["filas"]
    if len(filas) < 2:
        pytest.skip(f"menos de 2 proyectos de {tipo} en la base de prueba")
    p1, p2 = int(filas[0]["ID"]), int(filas[1]["ID"])
    doc = resoluciones.guardar_acto(records["dep"], {"categoria": categoria, "tipo_documento": "Otro",
                                                     "fecha": "2026-03-01", "proyectos": [p1]}, None)["id"]
    det = resoluciones.documento(records["dep"], {"id": doc})
    assert det["relaciones"] == {"docentes": False, "designaciones": False, "proyectos": tipo}
    assert det["proyectos_vinculados"] == [p1]
    assert resoluciones.vincular_proyectos(records["dep"], {"id": doc, "proyectos": [p1, p2]})["tono"] == "success"
    assert resoluciones.documento(records["dep"], {"id": doc})["proyectos_vinculados"] == sorted([p1, p2])
    # quitar: documentos.delete (superadmin), el mismo writer certificado de Investigacion / Extension
    with pytest.raises(ResolucionesError) as e:
        resoluciones.vincular_proyectos(records["dep"], {"id": doc, "proyectos": [p2]})
    assert e.value.status == 403
    resoluciones.vincular_proyectos(records["super"], {"id": doc, "proyectos": [p2]})
    assert resoluciones.documento(records["dep"], {"id": doc})["proyectos_vinculados"] == [p2]
    for sel, status in (([], 422), ([True], 422), ([999999999], 409)):
        with pytest.raises(ResolucionesError) as e:
            resoluciones.vincular_proyectos(records["dep"], {"id": doc, "proyectos": sel})
        assert e.value.status == status
    assert resoluciones.vincular_proyectos(records["dep"], {"id": doc, "proyectos": [p2]})["tono"] == "info"
    with pytest.raises(ResolucionesError) as e:
        resoluciones.agregar_docentes(records["dep"], {"id": doc, "modo": "Elegir un período", "periodo_id": 9,
                                                       "docentes": []})
    assert e.value.status == 422


def test_otro_no_admite_relaciones(resoluciones, records, db_conn):
    doc = resoluciones.guardar_acto(records["dep"], {"categoria": "Otro", "tipo_documento": "Otro",
                                                     "fecha": "2026-03-01"}, None)["id"]
    det = resoluciones.documento(records["dep"], {"id": doc})
    assert det["relaciones"] == {"docentes": False, "designaciones": False, "proyectos": None}
    for fn, body in ((resoluciones.agregar_docentes, {"modo": "Elegir un período", "periodo_id": 9, "docentes": []}),
                     (resoluciones.vincular_proyectos, {"proyectos": [1]}),
                     (resoluciones.vincular_designaciones, {"designaciones": []})):
        with pytest.raises(ResolucionesError) as e:
            fn(records["dep"], {"id": doc, **body})
        assert e.value.status == 422


def test_documento_historico_conserva_su_docente_y_proyecto_legados(resoluciones, records, db_conn):
    cuil, pid, _did, _otra = _caso(db_conn)
    otro = next(f for f in _docentes_periodo(resoluciones, records["dep"], pid) if f["CUIL"] != cuil)
    doc = db_conn.execute(
        "INSERT INTO documentos_respaldo (institucion_id,departamento_id,tipo_documento,categoria,numero,cuil,"
        "docente_nombre,archivo_nombre,archivo_pdf,archivo_bytes) VALUES (1,1,'Resolución','Cambio de cargo',"
        "'ZZNEXT-H',%s,'ZZNEXT Legado','',''::bytea,0) RETURNING id", [cuil]).fetchone()[0]
    resoluciones.agregar_docentes(records["dep"], {"id": doc, "modo": "Elegir un período", "periodo_id": pid,
                                                   "docentes": [otro["CUIL"]]})
    cuiles = {x[0] for x in db_conn.execute("SELECT cuil FROM documentos_respaldo_docentes WHERE documento_id=%s",
                                            [doc]).fetchall()}
    assert cuiles == {cuil, otro["CUIL"]}  # el docente historico no desaparece del listado
    filas = resoluciones.proyectos(records["dep"], {"tipo": "investigacion"})["filas"]
    if len(filas) >= 2:
        p1, p2 = int(filas[0]["ID"]), int(filas[1]["ID"])
        dp = db_conn.execute(
            "INSERT INTO documentos_respaldo (institucion_id,departamento_id,tipo_documento,categoria,numero,"
            "proyecto_tipo,proyecto_id,archivo_nombre,archivo_pdf,archivo_bytes) VALUES (1,1,'Disposición',"
            "'Proyecto de Investigación','ZZNEXT-HP','investigacion',%s,'',''::bytea,0) RETURNING id",
            [p1]).fetchone()[0]
        assert resoluciones.documento(records["dep"], {"id": dp})["proyectos_vinculados"] == [p1]
        resoluciones.vincular_proyectos(records["dep"], {"id": dp, "proyectos": [p1, p2]})
        assert resoluciones.documento(records["dep"], {"id": dp})["proyectos_vinculados"] == sorted([p1, p2])
        n = db_conn.execute("SELECT count(*) FROM documentos_respaldo_proyectos WHERE documento_id=%s",
                            [dp]).fetchone()[0]
        assert n == 2  # el historico quedo materializado en la relacion
