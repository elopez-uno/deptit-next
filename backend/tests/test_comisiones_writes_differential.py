"""Diferenciales de ESCRITURA de Comisiones: misma operacion de pantalla, certificado vs NEXT, desde el mismo estado.

Lado certificado: la secuencia de la pagina (entry l. 70015-72214, transcrita) llamando a los writers certificados
(``certified_comisiones``).  Lado NEXT: el servicio con una sesion real del AuthService (FakeRepo).  Entre ambos,
ROLLBACK al SAVEPOINT.  Se comparan las tablas que tocan los writers (comisiones, composicion, horarios, asignaciones,
franjas, docentes, proyectos, inscriptos, sedes, movimientos; ids nuevos normalizados) y la secuencia de COMMITs por
operacion B12H (``commit_seq``, ``mutating_statements``, ``committing_writer``, ``nested_system_task``)."""

from __future__ import annotations

import json
import pprint
from datetime import date

import pandas as pd
import psycopg
import pytest

import unidades_support as U
from comisiones import escrituras as E
from comisiones import rules as R
from comisiones.service import ComisionesError
from comisiones_support import (  # noqa: F401  (fixtures)
    FIXED_TODAY, audit_rows, audit_store, baseline_comisiones, certified_comisiones, comisiones, db_conn, lock_conn,
    session_for, state_comisiones,
)

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")

INST, DEP, ACTUAL, HISTORICO = 1, 1, 9, 5


def _record(service, repo, superadmin=False):
    if not superadmin:
        return session_for(service, repo, 3)[0]
    sup = session_for(service, repo, 1)[0]
    service.set_context(sup, INST, DEP, False)
    return sup


def _correr(fn):
    try:
        return fn(), None
    except psycopg.Error:
        raise  # un error de base no es comportamiento comparable: se muestra tal cual
    except Exception as exc:  # el certificado muestra st.error(str(e)); NEXT responde ComisionesError
        if isinstance(exc.__context__, psycopg.Error) or isinstance(exc.__cause__, psycopg.Error):
            raise
        return None, exc


def comparar(db_conn, audit_store, certificado, siguiente, preparar=None):
    """Ejecuta ambos lados desde el mismo estado y compara tablas y COMMITs.  Devuelve (res_c, err_c, res_n, err_n)."""
    if preparar is not None:
        preparar()
    baseline_comisiones(db_conn)
    ns = certified_comisiones(db_conn, INST, DEP)
    with db_conn.transaction() as tx:
        res_c, err_c = _correr(lambda: certificado(ns))
        st_c = state_comisiones(db_conn, INST, DEP)
        ops_c = [o for o in ns["_frames"].ops]
        raise psycopg.Rollback(tx)
    with db_conn.transaction() as tx:
        n_eventos = len(audit_store.events)
        res_n, err_n = _correr(siguiente)
        st_n = state_comisiones(db_conn, INST, DEP)
        eventos = audit_rows(db_conn)
        post = [e.operation for e in audit_store.events[n_eventos:]
                if e.outcome == "SUCCESS" and e.audit_mode == "POST_OPERATION"]
        fallidas = [e.operation for e in audit_store.events[n_eventos:] if e.outcome == "FAILED"]
        raise psycopg.Rollback(tx)
    for tabla in st_c:
        if st_c[tabla] != st_n[tabla]:
            a, b = st_c[tabla], st_n[tabla]
            solo_c = [json.loads(x) for x in a if x not in b][:3]
            solo_n = [json.loads(x) for x in b if x not in a][:3]
            raise AssertionError(f"{tabla}: certificado {len(a)} filas / NEXT {len(b)}\nsolo certificado: "
                                 f"{pprint.pformat(solo_c)}\nsolo NEXT: {pprint.pformat(solo_n)}")
    ops_n, vistos = [], {}
    for e in eventos:
        cid = str(e["correlation_id"])
        if cid not in vistos:
            vistos[cid] = {"op": e["operation"], "commits": []}
            ops_n.append(vistos[cid])
        m = e["metadata"]
        vistos[cid]["commits"].append({k: m.get(k) for k in ("commit_seq", "mutating_statements", "committing_writer",
                                                            "nested_system_task")})
    if [o for o in ops_c if o["commits"]] != ops_n:
        raise AssertionError(f"ops certificado:\n{pprint.pformat(ops_c)}\nops NEXT:\n{pprint.pformat(ops_n)}")
    sin_commits = [o["op"] for o in ops_c if not o["commits"]]
    if err_c is None:
        assert sin_commits == post
    else:  # la operacion que fallo sin COMMIT queda FAILED en NEXT (el certificado no registra exito)
        assert sorted(sin_commits) == sorted(post + [f for f in fallidas if f in sin_commits]), (sin_commits, post, fallidas)
    return res_c, err_c, res_n, err_n


# ------------------------------------------------------------------------------------------ datos de prueba
def _materia(svc, rec, oe=False):
    for f in svc.abrir_materias(rec, {})["materias"]:
        info = svc.abrir_materia(rec, {"materia_id": f["materia_id"]})
        if info["es_oe"] == oe and (not oe or svc.abrir_materia(rec, {"materia_id": f["materia_id"]}).get("opciones")):
            return f["materia_id"], info
    pytest.skip("sin materia del tipo pedido")


def _docentes(svc, rec, n=1, contexto="actual", excluir=()):
    out = [d for d in svc.docentes(rec, {"contexto": contexto})["docentes"] if d["cuil"] not in excluir]
    return out[:n]


def _sel(franjas, parcial=False):
    sel = [{"usar": True, "desde": f["hora_inicio"] if isinstance(f, dict) else f.hora_inicio,
            "hasta": f["hora_fin"] if isinstance(f, dict) else f.hora_fin} for f in franjas]
    if parcial and sel:
        sel[0]["desde"] = R.hora_texto_v95(sel[0]["desde"])
        a = R.minutos_v95(sel[0]["desde"]) + 60
        sel[0]["hasta"] = f"{a // 60:02d}:{a % 60:02d}"
    return sel


def _etiqueta_alta(row):
    prestado = (str(row.get('tipo_docente', 'Propio')).strip() == 'Prestado'
                and str(row.get('departamento_origen', '')).strip())
    return (f"{row['nombre_completo']} - {row['cuil']} "
            f"({row.get('horas_designadas', 0)} hs designadas - {row.get('tipo_docente', 'Propio')}"
            f"{(' desde ' + str(row.get('departamento_origen'))) if prestado else ''})")


# ------------------------------------------------------------------------------------------ Pestaña 2: abrir comisión
def _pagina_abrir(ns, mid, nombre, turno, sede, modalidad, fecha, obs, horarios, docentes, obs_asig, adicionales=(),
                  opcion_id=None, materia_especifica=""):
    """entry l. 70517-70629 (con la compensacion del except)."""
    per = ns["periodo_actual_para_comisiones"]()
    df_doc = ns["get_docentes_activos_para_comisiones"](per["id"])
    cfgs = []
    for d in docentes:
        row = df_doc[df_doc["cuil"].astype(str) == d["cuil"]].iloc[0].to_dict()
        reales, horas, _ = R.horarios_reales_desde_seleccion_v95(horarios, d["franjas"])
        cfgs.append({"etiqueta": _etiqueta_alta(row), "cuil": row["cuil"], "rol": d["rol"], "horarios_reales": reales,
                     "horas_reales": horas})
    nuevo_id = None
    alertas = 0
    try:
        nuevo_id = ns["guardar_comision"](per["id"], mid, nombre, turno, sede, modalidad, "Activa", obs, fecha,
                                          materia_especifica=materia_especifica, opcion_curricular_id=opcion_id,
                                          materia_ids_adicionales=list(adicionales))
        for h in horarios:
            ns["guardar_horario_comision"](nuevo_id, h["dia"], h["hora_inicio"], h["hora_fin"],
                                           "Cargado al abrir la comisión.")
        movs = []
        for cfg in cfgs:
            sup = ns["detectar_superposiciones_horarios_candidato"](cfg["cuil"], per["id"], cfg["horarios_reales"],
                                                                    excluir_comision_id=nuevo_id)
            obs_doc = str(obs_asig or "").strip()
            if not sup.empty:
                alertas += 1
                obs_doc = (obs_doc + " | " if obs_doc else "") + "ALERTA: asignación con superposición horaria detectada."
            if ns["es_docente_prestado_local"](cfg["cuil"]):
                obs_doc = (obs_doc + " | " if obs_doc else "") + "Docente prestado: asignado sin designación local."
            ns["guardar_asignacion_docente_comision"](nuevo_id, cfg["cuil"], cfg["rol"], cfg["horas_reales"], "Activa",
                                                      obs_doc, horarios_reales=cfg["horarios_reales"])
            movs.append((cfg, obs_doc))
        desc = ns["descripcion_materias_comision_v122"](mid, list(adicionales))
        ns["registrar_movimiento"]("Apertura de comisión", "", "",
                                   f"Se abrió comisión {nombre} para {desc or 'materia'} en {per['nombre']}, "
                                   f"con {len(horarios)} horario/s y {len(cfgs)} docente/s.", obs, per["id"])
        for cfg, obs_doc in movs:
            ns["registrar_movimiento"]("Asignación docente a comisión", cfg["cuil"], cfg["etiqueta"],
                                       f"Se asignó a la comisión {nombre} como {cfg['rol']} "
                                       f"({float(cfg['horas_reales'] or 0):g} hs).", obs_doc, per["id"])
    except Exception as e:
        if nuevo_id is not None:
            try:
                ns["_b10_revertir_alta_comision_incompleta"](nuevo_id)
            except Exception:
                pass
        raise RuntimeError(f"No se pudo abrir la comisión completa: {e}")
    return nuevo_id, alertas


def _payload_abrir(svc, rec, mid, nombre, horarios, docentes, **kw):
    data = {"materia_id": mid, "nombre": nombre, "turno": "noche", "sede": "Sin especificar", "modalidad": "Presencial",
            "fecha_apertura": "2026-10-20", "observaciones": "ZZNEXT apertura", "observaciones_asignaciones": "ZZ obs",
            "horarios": horarios, "docentes": docentes, "huella_periodos": svc.overview(rec)["huella_periodos"]}
    data.update(kw)
    return data


HORARIOS = [{"dia": "Martes", "hora_inicio": "18:00", "hora_fin": "20:00", "horas": 2.0},
            {"dia": "Jueves", "hora_inicio": "18:00", "hora_fin": "21:30", "horas": 3.5}]


def _horarios_payload(hs):
    return [{k: h[k] for k in ("dia", "hora_inicio", "hora_fin")} for h in hs]


def _docentes_payload(svc, rec, docs, horarios, parcial=False):
    out = []
    for d in docs:
        roles = svc.docente_roles(rec, {"contexto": "actual", "cuil": d["cuil"]})["roles"]
        out.append({"cuil": d["cuil"], "rol": roles[0] if roles else "Otro", "franjas": _sel(horarios, parcial)})
    return out


def test_abrir_comision_comun_dos_docentes_franja_parcial(db_conn, comisiones, service, repo, audit_store):
    rec = _record(service, repo)
    mid, _ = _materia(comisiones, rec)
    docs = _docentes_payload(comisiones, rec, _docentes(comisiones, rec, 2), HORARIOS, parcial=True)
    docs[1]["franjas"] = _sel(HORARIOS)
    res_c, err_c, res_n, err_n = comparar(
        db_conn, audit_store,
        lambda ns: _pagina_abrir(ns, mid, "ZZ7", "noche", "Sin especificar", "Presencial", date(2026, 10, 20),
                                 "ZZNEXT apertura", HORARIOS, docs, "ZZ obs"),
        lambda: comisiones.abrir(rec, _payload_abrir(comisiones, rec, mid, "ZZ7", _horarios_payload(HORARIOS), docs)))
    assert err_c is None and err_n is None, (err_c, err_n)
    assert (res_c[1] > 0) == (res_n["tono"] == "warning")


def test_abrir_comision_multicodigo(db_conn, comisiones, service, repo, audit_store):
    rec = _record(service, repo)
    mid, info = _materia(comisiones, rec)
    adic = [info["adicionales"][0]["materia_id"]] if info["adicionales"] else []
    if not adic:
        pytest.skip("sin materias adicionales")
    hs = HORARIOS[:1]
    docs = _docentes_payload(comisiones, rec, _docentes(comisiones, rec, 1), hs)
    _, err_c, _, err_n = comparar(
        db_conn, audit_store,
        lambda ns: _pagina_abrir(ns, mid, "ZZM", "noche", "Sin especificar", "Presencial", date(2026, 10, 20),
                                 "ZZNEXT apertura", hs, docs, "ZZ obs", adicionales=adic),
        lambda: comisiones.abrir(rec, _payload_abrir(comisiones, rec, mid, "ZZM", _horarios_payload(hs), docs,
                                                     adicionales=adic)))
    assert err_c is None and err_n is None, (err_c, err_n)


def test_abrir_comision_optativa_con_opcion(db_conn, comisiones, service, repo, audit_store):
    rec = _record(service, repo)
    mid, _ = _materia(comisiones, rec, oe=True)
    info = comisiones.abrir_materia(rec, {"materia_id": mid})
    op = info["opciones"][0]
    hs = HORARIOS[:1]
    docs = _docentes_payload(comisiones, rec, _docentes(comisiones, rec, 1), hs)
    _, err_c, _, err_n = comparar(
        db_conn, audit_store,
        lambda ns: _pagina_abrir(ns, mid, "ZZO", "noche", "Sin especificar", "Presencial", date(2026, 10, 20),
                                 "ZZNEXT apertura", hs, docs, "ZZ obs", opcion_id=op["id"],
                                 materia_especifica=R.limpiar_texto_tabla(op["nombre"])),
        lambda: comisiones.abrir(rec, _payload_abrir(comisiones, rec, mid, "ZZO", _horarios_payload(hs), docs,
                                                     opcion_curricular_id=op["id"])))
    assert err_c is None and err_n is None, (err_c, err_n)


def _cuil_de_otro_departamento(db_conn):
    """CUIL con ficha en otro departamento de la institucion y sin ficha local en dep 1."""
    fila = db_conn.execute("""
        SELECT d.cuil FROM docentes d
        WHERE d.institucion_id=1 AND d.departamento_id<>1
          AND NOT EXISTS (SELECT 1 FROM docentes l WHERE l.institucion_id=1 AND l.departamento_id=1 AND l.cuil=d.cuil)
        ORDER BY d.id LIMIT 1""").fetchone()
    if not fila:
        pytest.skip("sin docente de otro departamento")
    return fila[0]


def test_asignacion_de_docente_de_otro_departamento_crea_prestado_local(db_conn, comisiones, service, repo,
                                                                         audit_store):
    """``asegurar_docente_prestado_local_si_corresponde`` (l. 26201) dentro de guardar_asignacion v184/v95: la UI solo
    ofrece docentes con ficha local, asi que se compara a nivel writer (misma operacion B12H)."""
    from comisiones.service import SPEC_GUARDAR_ASIGNACION
    rec = _record(service, repo)
    cuil = _cuil_de_otro_departamento(db_conn)
    cid, _ = _comision_actual(comisiones, rec)
    scope = comisiones.scope(rec)
    _, err_c, _, err_n = comparar(
        db_conn, audit_store,
        lambda ns: ns["guardar_asignacion_docente_comision"](cid, cuil, "JTP", 2.0, "Activa", "ZZ prestado"),
        lambda: comisiones._op(rec, scope, SPEC_GUARDAR_ASIGNACION, lambda u: E.guardar_asignacion_docente_comision(
            u, cid, cuil, "JTP", 2.0, "Activa", "ZZ prestado"), entity_raw=cid))
    assert err_c is None and err_n is None, (err_c, err_n)
    contar = "SELECT count(*), max(tipo_docente) FROM docentes WHERE institucion_id=1 AND departamento_id=1 AND cuil=%s"
    assert db_conn.execute(contar, [cuil]).fetchone()[0] == 0  # todo se revirtio
    with db_conn.transaction() as tx:
        comisiones._op(rec, scope, SPEC_GUARDAR_ASIGNACION, lambda u: E.guardar_asignacion_docente_comision(
            u, cid, cuil, "JTP", 2.0, "Activa", "ZZ prestado"), entity_raw=cid)
        assert db_conn.execute(contar, [cuil]).fetchone() == (1, "Prestado")
        raise psycopg.Rollback(tx)


def _docente_con_proyecto(db_conn):
    fila = db_conn.execute("""
        SELECT i.cuil FROM investigacion_docente i
        WHERE i.institucion_id=1 AND i.departamento_id=1 AND i.periodo_id=9 AND COALESCE(i.horas_asignadas,0)>0
          AND COALESCE(i.estado_asignacion,'Activa')='Activa'
          AND EXISTS (SELECT 1 FROM designaciones d WHERE d.cuil=i.cuil AND d.institucion_id=1 AND d.departamento_id=1
                      AND d.periodo_id=9 AND d.estado='Activa')
        ORDER BY i.id LIMIT 1""").fetchone()
    if not fila:
        pytest.skip("sin docente con proyecto")
    return fila[0]


def test_abrir_reajusta_horas_de_proyectos_v184(db_conn, comisiones, service, repo, audit_store):
    rec = _record(service, repo)
    cuil = _docente_con_proyecto(db_conn)
    # Proyecto inflado (dentro de la transaccion del test): la nueva comision deja exceso y el reajuste lo reduce.
    db_conn.execute("UPDATE investigacion_docente SET horas_asignadas=60 WHERE institucion_id=1 AND departamento_id=1 "
                    "AND periodo_id=9 AND cuil=%s", [cuil])
    mid, _ = _materia(comisiones, rec)
    doc = next((d for d in comisiones.docentes(rec, {"contexto": "actual"})["docentes"] if d["cuil"] == cuil), None)
    if doc is None:
        pytest.skip("docente con proyecto no disponible")
    docs = _docentes_payload(comisiones, rec, [doc], HORARIOS)
    _, err_c, _, err_n = comparar(
        db_conn, audit_store,
        lambda ns: _pagina_abrir(ns, mid, "ZZR", "noche", "Sin especificar", "Presencial", date(2026, 10, 20),
                                 "ZZNEXT apertura", HORARIOS, docs, "ZZ obs"),
        lambda: comisiones.abrir(rec, _payload_abrir(comisiones, rec, mid, "ZZR", _horarios_payload(HORARIOS), docs)))
    assert err_c is None and err_n is None, (err_c, err_n)
    horas = ("SELECT sum(horas_asignadas) FROM investigacion_docente WHERE institucion_id=1 AND departamento_id=1 "
             "AND periodo_id=9 AND cuil=%s")
    antes = db_conn.execute(horas, [cuil]).fetchone()[0]
    with db_conn.transaction() as tx:
        comisiones.abrir(rec, _payload_abrir(comisiones, rec, mid, "ZZR", _horarios_payload(HORARIOS), docs))
        assert db_conn.execute(horas, [cuil]).fetchone()[0] < antes  # el reajuste v184 redujo el proyecto
        raise psycopg.Rollback(tx)


def test_abrir_falla_en_asignacion_compensa(db_conn, comisiones, service, repo, audit_store, monkeypatch):
    rec = _record(service, repo)
    mid, _ = _materia(comisiones, rec)
    hs = HORARIOS[:1]
    docs = _docentes_payload(comisiones, rec, _docentes(comisiones, rec, 1), hs)

    def boom(*a, **k):
        raise ValueError("falla simulada")

    def cert(ns):
        ns["guardar_asignacion_docente_comision"] = boom
        return _pagina_abrir(ns, mid, "ZZF", "noche", "Sin especificar", "Presencial", date(2026, 10, 20),
                             "ZZNEXT apertura", hs, docs, "ZZ obs")

    monkeypatch.setattr(E, "guardar_asignacion_docente_comision", boom)
    _, err_c, _, err_n = comparar(
        db_conn, audit_store, cert,
        lambda: comisiones.abrir(rec, _payload_abrir(comisiones, rec, mid, "ZZF", _horarios_payload(hs), docs)))
    assert str(err_c) == "No se pudo abrir la comisión completa: falla simulada"
    assert isinstance(err_n, ComisionesError) and err_n.message == str(err_c)


# ------------------------------------------------------------------------------------------ Pestaña 4: alta / baja real
def _comision_actual(svc, rec, con_horarios=True):
    for f in svc.comisiones_lista(rec, {"contexto": "modificacion"})["filas"]:
        det = svc.comision_detalle(rec, {"contexto": "modificacion", "comision_id": f["id"]})
        if (not con_horarios or det["horarios"]) and det["asignaciones"]:
            return f["id"], det
    pytest.skip("sin comision con horarios y docentes")


def test_alta_real_con_movimiento(db_conn, comisiones, service, repo, audit_store):
    rec = _record(service, repo)
    cid, det = _comision_actual(comisiones, rec)
    asignados = {a["cuil"] for a in det["asignaciones"]}
    doc = _docentes(comisiones, rec, 1, excluir=asignados)[0]
    roles = comisiones.docente_roles(rec, {"contexto": "actual", "cuil": doc["cuil"]})["roles"]
    rol = roles[0] if roles else "Otro"
    sel = _sel(det["franjas_alta"], parcial=True)

    def cert(ns):
        per = ns["periodo_actual_para_comisiones"]()
        df_com = ns["get_comisiones_integradas_periodo"](per["id"])
        fila = df_com[df_com["id"].astype(int) == cid].iloc[0]
        com_sel = ns["_label_comision_desde_row"](fila)
        df_h = ns["get_horarios_comision"](cid)
        reales, hs, _ = R.horarios_reales_desde_seleccion_v95(df_h, sel)
        doc_sel = f"{doc['nombre_completo']} - {doc['cuil']}"
        sup = ns["detectar_superposiciones_horarios_candidato"](doc["cuil"], per["id"], reales, excluir_comision_id=cid)
        obs_final = "ZZ alta | " + f"Alta por modificación de asignación. Fecha efectiva: 2026-10-21. Comisión ID {cid}."
        if not sup.empty:
            obs_final += " | ALERTA: asignación con superposición horaria detectada."
        ns["guardar_asignacion_docente_comision"](cid, doc["cuil"], rol, hs, "Activa", obs_final, horarios_reales=reales)
        detalle = (f"Alta docente por modificación de asignación: Comisión ID {cid} - {com_sel}. Docente {doc_sel}, rol "
                   f"{rol}, {hs:g} hs. Fecha efectiva: 2026-10-21.")
        ns["registrar_movimiento"]("Alta docente por modificación de asignación", doc["cuil"], doc_sel, detalle,
                                   obs_final, per["id"])

    _, err_c, _, err_n = comparar(db_conn, audit_store, cert, lambda: comisiones.alta_real(rec, {
        "comision_id": cid, "cuil": doc["cuil"], "rol": rol, "franjas": sel, "fecha": "2026-10-21",
        "observaciones": "ZZ alta", "huella": det["huella"]}))
    assert err_c is None and err_n is None, (err_c, err_n)


def test_baja_real_con_movimiento(db_conn, comisiones, service, repo, audit_store):
    rec = _record(service, repo)
    cid, det = _comision_actual(comisiones, rec)
    a = next(x for x in det["asignaciones"] if str(x.get("estado") or "Activa") == "Activa")

    def cert(ns):
        per = ns["periodo_actual_para_comisiones"]()
        df_com = ns["get_comisiones_integradas_periodo"](per["id"])
        fila = df_com[df_com["id"].astype(int) == cid].iloc[0]
        com_sel = ns["_label_comision_desde_row"](fila)
        df_a = ns["get_asignaciones_comision"](cid)
        fb = df_a[df_a["id"].astype(int) == a["id"]].iloc[0]
        obs_final = f"Baja por modificación de asignación. Fecha efectiva: 2026-10-22. Comisión ID {cid}."
        ns["actualizar_estado_asignacion_docente_comision"](a["id"], "Finalizada", obs_final)
        detalle = (f"Baja docente por modificación de asignación: Comisión ID {cid} - {com_sel}. Docente "
                   f"{fb.get('docente','')} [{fb.get('cuil','')}], rol {fb.get('rol','')}, {fb.get('horas_asignadas',0)} "
                   f"hs. Fecha efectiva: 2026-10-22.")
        ns["registrar_movimiento"]("Baja docente por modificación de asignación", fb.get("cuil", ""),
                                   fb.get("docente", ""), detalle, obs_final, per["id"])

    _, err_c, _, err_n = comparar(db_conn, audit_store, cert, lambda: comisiones.baja_real(rec, {
        "comision_id": cid, "asignacion_id": a["id"], "fecha": "2026-10-22", "observaciones": "", "confirmar": True,
        "huella": det["huella"]}))
    assert err_c is None and err_n is None, (err_c, err_n)


# ------------------------------------------------------------------------------------------ Pestaña 7: editar / eliminar
def _comision_edicion(svc, rec, pred=lambda det: True):
    for f in svc.comisiones_lista(rec, {"contexto": "edicion"})["filas"]:
        det = svc.comision_detalle(rec, {"contexto": "edicion", "comision_id": f["id"]})
        if pred(det):
            return f["id"], det
    pytest.skip("sin comision que cumpla la condicion")


def _cert_edicion(ns, cid):
    _, df = ns["get_opciones_comisiones"](periodo_id=ns["periodo_actual_para_comisiones"]()["id"]
                                          if False else _periodo_correccion(ns)["id"], solo_activas=False)
    fila = df[df["id"].astype(int) == cid].iloc[0]
    return fila, ns["_label_comision_desde_row"](fila)


def _periodo_correccion(ns):
    ok, per, _ = ns["puede_corregir_comisiones_periodo_abierto"]()
    return per


def test_editar_datos_generales(db_conn, comisiones, service, repo, audit_store):
    rec = _record(service, repo)
    cid, det = _comision_edicion(comisiones, rec, lambda d: d["fila"].get("opcion_curricular_id") in (None, 0))
    form = comisiones.edicion_datos(rec, {"comision_id": cid})
    if form["es_oe"]:
        pytest.skip("comision OE")
    nuevo = "ZZE"
    adic = [a["materia_id"] for a in form["adicionales"][:1] if a["materia_id"] not in form["adicionales_default"]]
    adic = form["adicionales_default"] + adic

    def cert(ns):
        fila, _ = _cert_edicion(ns, cid)
        ns["actualizar_comision"](cid, form["materia_id"], nuevo, "tarde", form["valores"]["sede"], "Virtual",
                                  fila["estado"] if pd.notna(fila["estado"]) and str(fila["estado"]).strip() else "Activa",
                                  "ZZ obs editada", materia_especifica="", opcion_curricular_id=None,
                                  materia_ids_adicionales=adic)

    _, err_c, _, err_n = comparar(db_conn, audit_store, cert, lambda: comisiones.editar_datos(rec, {
        "comision_id": cid, "materia_id": form["materia_id"], "nombre": nuevo, "turno": "tarde",
        "sede": form["valores"]["sede"], "modalidad": "Virtual", "adicionales": adic, "opcion_curricular": None,
        "observaciones": "ZZ obs editada", "huella": det["huella"]}))
    assert err_c is None and err_n is None, (err_c, err_n)


def test_nombres_en_lote(db_conn, comisiones, service, repo, audit_store):
    rec = _record(service, repo)
    lista = comisiones.comisiones_lista(rec, {"contexto": "edicion"})
    filas = lista["filas"][:3]
    cambios = [(f["id"], str(f["nombre_comision"] or "").strip(), f"ZZ{i}") for i, f in enumerate(filas)]
    payload = [{"id": f["id"], "comision": f["nombre_comision"]} for f in lista["filas"]]
    for p, (_, _, nuevo) in zip(payload, cambios):
        p["comision"] = nuevo
    _, err_c, res_n, err_n = comparar(
        db_conn, audit_store, lambda ns: ns["actualizar_nombres_comisiones_lote_v195"](cambios),
        lambda: comisiones.editar_nombres_lote(rec, {"busqueda": "", "filas": payload,
                                                     "huella_lote": lista["huella_lote"]}))
    assert err_c is None and err_n is None, (err_c, err_n)
    assert res_n["mensaje"].startswith("Se actualizaron 3 comisión/es en ")


def test_editar_horario_recorta_franjas_personalizadas(db_conn, comisiones, service, repo, audit_store):
    rec = _record(service, repo)
    cid = db_conn.execute("""SELECT co.id FROM comisiones co JOIN asignaciones_docentes_comision a ON a.comision_id=co.id
                             AND a.usa_horario_personalizado WHERE co.periodo_id=9 AND co.departamento_id=1
                             ORDER BY co.id LIMIT 1""").fetchone()
    if not cid:
        pytest.skip("sin franjas personalizadas")
    cid = cid[0]
    det = comisiones.comision_detalle(rec, {"contexto": "edicion", "comision_id": cid})
    h = det["horarios"][0]
    ini = R.hora_texto_v95(h["hora_inicio"])
    a = R.minutos_v95(ini) + 30
    nuevo_ini = f"{a // 60:02d}:{a % 60:02d}"
    hf = R.hora_texto_v95(h["hora_fin"])

    def cert(ns):
        _, com_sel = _cert_edicion(ns, cid)
        ok, msg = ns["actualizar_horario_comision"](h["id"], h["dia"], nuevo_ini, hf, "ZZ obs h")
        if ok:
            ns["registrar_movimiento"]("Modificación de horario de comisión", "", "",
                                       f"Se modificó un horario de {com_sel} a {h['dia']} {nuevo_ini}-{hf}.", "ZZ obs h",
                                       _periodo_correccion(ns)["id"])
        return ok, msg

    res_c, err_c, res_n, err_n = comparar(db_conn, audit_store, cert, lambda: comisiones.editar_horario(rec, {
        "comision_id": cid, "horario_id": h["id"], "dia": h["dia"], "hora_inicio": nuevo_ini, "hora_fin": hf,
        "observaciones": "ZZ obs h", "huella": det["huella"]}))
    assert err_c is None and err_n is None, (err_c, err_n)
    assert res_c[1] == res_n["mensaje"]


def test_agregar_y_eliminar_horario(db_conn, comisiones, service, repo, audit_store):
    rec = _record(service, repo)
    cid, det = _comision_edicion(comisiones, rec, lambda d: bool(d["horarios"]) and bool(d["asignaciones"]))

    def cert_agregar(ns):
        _, com_sel = _cert_edicion(ns, cid)
        ns["guardar_horario_comision"](cid, "Sábado", "08:00", "10:00", "ZZ nuevo")
        ns["registrar_movimiento"]("Alta de horario de comisión", "", "",
                                   f"Se agregó el horario Sábado 08:00-10:00 en {com_sel}.", "ZZ nuevo",
                                   _periodo_correccion(ns)["id"])

    _, err_c, _, err_n = comparar(db_conn, audit_store, cert_agregar, lambda: comisiones.agregar_horario(rec, {
        "comision_id": cid, "dia": "Sábado", "hora_inicio": "08:00", "hora_fin": "10:00", "observaciones": "ZZ nuevo",
        "huella": det["huella"]}))
    assert err_c is None and err_n is None, (err_c, err_n)

    sup = _record(service, repo, superadmin=True)
    det_s = comisiones.comision_detalle(sup, {"contexto": "edicion", "comision_id": cid})
    h = det_s["horarios"][0]

    def cert_eliminar(ns):
        _, com_sel = _cert_edicion(ns, cid)
        df_h = ns["get_horarios_comision"](cid)
        r = df_h[df_h["id"].astype(int) == h["id"]].iloc[0]
        label = f"{r['dia']} {r['hora_inicio']}-{r['hora_fin']} ({r['horas']} hs)"
        ns["eliminar_horario_comision"](h["id"])
        ns["registrar_movimiento"]("Eliminación de horario de comisión", "", "",
                                   f"Se eliminó el horario {label} de {com_sel}.", "Corrección de error de carga.",
                                   _periodo_correccion(ns)["id"])

    _, err_c, _, err_n = comparar(db_conn, audit_store, cert_eliminar, lambda: comisiones.eliminar_horario(sup, {
        "comision_id": cid, "horario_id": h["id"], "confirmar": True, "huella": det_s["huella"]}))
    assert err_c is None and err_n is None, (err_c, err_n)


def test_asignar_por_correccion_y_horario_efectivo(db_conn, comisiones, service, repo, audit_store):
    rec = _record(service, repo)
    cid, det = _comision_edicion(comisiones, rec, lambda d: len(d["horarios"]) >= 1 and bool(d["asignaciones"]))
    asignados = {a["cuil"] for a in det["asignaciones"]}
    doc = _docentes(comisiones, rec, 1, contexto="correccion", excluir=asignados)[0]
    roles = comisiones.docente_roles(rec, {"contexto": "correccion", "cuil": doc["cuil"]})["roles"]
    rol = roles[0] if roles else "Otro"
    sel = _sel(det["franjas_alta"])

    def cert(ns):
        df_h = ns["get_horarios_comision"](cid)
        reales, hs, _ = R.horarios_reales_desde_seleccion_v95(df_h, sel)
        ns["guardar_asignacion_docente_comision"](
            cid, doc["cuil"], rol, hs, "Activa",
            "Asignación agregada como corrección de carga; sin movimiento académico.", horarios_reales=reales)

    _, err_c, _, err_n = comparar(db_conn, audit_store, cert, lambda: comisiones.asignar_correccion(rec, {
        "comision_id": cid, "cuil": doc["cuil"], "rol": rol, "franjas": sel, "observaciones": "",
        "huella": det["huella"]}))
    assert err_c is None and err_n is None, (err_c, err_n)

    a = next(x for x in det["asignaciones"] if str(x.get("estado") or "Activa") == "Activa")
    fr = comisiones.asignacion_franjas(rec, {"comision_id": cid, "asignacion_id": a["id"]})["franjas"]
    sel2 = _sel(fr, parcial=True)

    def cert2(ns):
        df_h = ns["get_horarios_comision"](cid)
        reales, _, _ = R.horarios_reales_desde_seleccion_v95(df_h, sel2)
        ns["guardar_horarios_reales_asignacion"](a["id"], reales)

    _, err_c, _, err_n = comparar(db_conn, audit_store, cert2, lambda: comisiones.guardar_franjas(rec, {
        "comision_id": cid, "asignacion_id": a["id"], "franjas": sel2, "huella": det["huella"]}))
    assert err_c is None and err_n is None, (err_c, err_n)


def test_quitar_asignacion_y_eliminar_comision(db_conn, comisiones, service, repo, audit_store):
    sup = _record(service, repo, superadmin=True)
    cid, det = _comision_edicion(comisiones, sup, lambda d: bool(d["asignaciones"]) and bool(d["horarios"]))
    a = det["asignaciones"][0]

    def cert(ns):
        _, com_sel = _cert_edicion(ns, cid)
        df_a = ns["get_asignaciones_comision"](cid)
        r = df_a[df_a["id"].astype(int) == a["id"]].iloc[0]
        label = f"{r.get('docente','')} - {r.get('rol','')} ({r.get('horas_asignadas',0)} hs)"
        ns["eliminar_asignacion_docente_comision"](a["id"])
        ns["registrar_movimiento"]("Eliminación de asignación docente a comisión", "", "",
                                   f"Se eliminó por error de carga la asignación {label} de {com_sel}.",
                                   "Corrección de error de carga.", _periodo_correccion(ns)["id"])

    _, err_c, _, err_n = comparar(db_conn, audit_store, cert, lambda: comisiones.quitar_asignacion(sup, {
        "comision_id": cid, "asignacion_id": a["id"], "confirmar": True, "huella": det["huella"]}))
    assert err_c is None and err_n is None, (err_c, err_n)

    _, err_c, _, err_n = comparar(db_conn, audit_store, lambda ns: ns["eliminar_comision"](cid),
                                  lambda: comisiones.eliminar_comision(sup, {"comision_id": cid, "confirmar": True,
                                                                             "huella": det["huella"]}))
    assert err_c is None and err_n is None, (err_c, err_n)


# ------------------------------------------------------------------------------------------ inscriptos (abierto y cerrado)
@pytest.mark.parametrize("pid", [ACTUAL, HISTORICO])
def test_guardar_inscriptos(db_conn, comisiones, service, repo, audit_store, pid):
    rec = _record(service, repo)
    d = comisiones.inscriptos(rec, pid)
    if d["vacio"]:
        pytest.skip("sin asignaturas")
    filas = d["filas"][:3]
    edic = [{"clave": f["clave"], "huella": f["huella"], "cantidad": 20 + i, "cantidad_final": (10 + i) if i else None}
            for i, f in enumerate(filas)]

    def cert(ns):
        df = ns["get_inscriptos_asignaturas_periodo_v248"](pid).copy()
        df["cantidad"] = pd.to_numeric(df.get("cantidad", 0), errors="coerce").fillna(0).astype(int)
        for i, (idx, fila) in enumerate(df.head(3).iterrows()):
            cant_ant = int(pd.to_numeric(pd.Series([fila["cantidad"]]), errors="coerce").fillna(0).iloc[0])
            cant_new = 20 + i
            fa = pd.to_numeric(pd.Series([fila.get("cantidad_final")]), errors="coerce").iloc[0]
            final_ant = None if pd.isna(fa) else max(int(fa), 0)
            final_new = (10 + i) if i else None
            ci, cf = cant_new != cant_ant, final_new != final_ant
            if ci or cf:
                ns["guardar_inscriptos_asignatura_periodo_v248"](
                    pid, int(fila.get("materia_id_inscriptos")), cant_new,
                    opcion_curricular_id=int(fila.get("opcion_curricular_id_inscriptos", 0) or 0),
                    observaciones=str(fila.get("observaciones_inscriptos", "") or ""),
                    fecha_actualizacion=FIXED_TODAY if ci else fila.get("fecha_actualizacion", ""),
                    cantidad_final=final_new,
                    fecha_actualizacion_final=FIXED_TODAY if cf else fila.get("fecha_actualizacion_final", ""),
                    actualizar_final=cf)

    _, err_c, _, err_n = comparar(db_conn, audit_store, cert, lambda: comisiones.guardar_inscriptos(rec, {
        "periodo_id": pid, "filas": edic}))
    assert err_c is None and err_n is None, (err_c, err_n)


# ------------------------------------------------------------------------------------------ sedes
def test_sedes_alta_edicion_y_baja(db_conn, comisiones, service, repo, audit_store):
    rec = _record(service, repo)
    _, err_c, _, err_n = comparar(
        db_conn, audit_store,
        lambda ns: ns["guardar_sede_institucional"]("ZZ Sede Norte", "Calle 1 123", "Merlo", "ZZ obs"),
        lambda: comisiones.agregar_sede(rec, {"nombre": "ZZ Sede Norte", "direccion": "Calle 1 123",
                                              "localidad": "Merlo", "observaciones": "ZZ obs"}))
    assert err_c is None and err_n is None, (err_c, err_n)
    sede = comisiones.sedes(rec)["sedes"][0]
    _, err_c, _, err_n = comparar(
        db_conn, audit_store,
        lambda ns: ns["actualizar_sede_institucional"](sede["id"], "ZZ Sede", "Dir 2", "Moreno", "Inactiva", "obs"),
        lambda: comisiones.editar_sede(rec, {"id": sede["id"], "nombre": "ZZ Sede", "direccion": "Dir 2",
                                             "localidad": "Moreno", "estado": "Inactiva", "observaciones": "obs",
                                             "huella": sede["huella"]}))
    assert err_c is None and err_n is None, (err_c, err_n)
    sup = _record(service, repo, superadmin=True)
    _, err_c, _, err_n = comparar(
        db_conn, audit_store, lambda ns: ns["eliminar_sede_institucional"](sede["id"]),
        lambda: comisiones.eliminar_sede(sup, {"id": sede["id"], "confirmar": True, "huella": sede["huella"]}))
    assert err_c is None and err_n is None, (err_c, err_n)


def test_sede_duplicada_mismo_mensaje(db_conn, comisiones, service, repo, audit_store):
    rec = _record(service, repo)
    nombre = comisiones.sedes(rec)["sedes"][0]["nombre"]
    _, err_c, _, err_n = comparar(
        db_conn, audit_store, lambda ns: ns["guardar_sede_institucional"](nombre.upper(), "x 1", "y", ""),
        lambda: comisiones.agregar_sede(rec, {"nombre": nombre.upper(), "direccion": "x 1", "localidad": "y"}))
    assert str(err_c) == err_n.message == "Ya existe una sede con ese nombre en la institución."


# ------------------------------------------------------------------------------------------ carga rápida (lote v232)
def _texto_carga(svc, rec):
    mid, info = _materia(svc, rec)
    docs = _docentes(svc, rec, 2)
    cod = info["codigo"]
    asig = info["asignatura"]
    filas = [
        "Código\tAsignatura\tComisión\tTurno\tDía 1\tHora Inicio 1\tHora Fin 1\tDía 2\tHora Inicio 2\tHora Fin 2\t"
        "Modalidad\tSede\tDocente 1\tCargo 1\tCubre Horario 1 - Docente 1\tCubre Horario 2 - Docente 1\t"
        "Hora Inicio Docente 1 Horario 2\tHora Fin Docente 1 Horario 2\tDocente 2",
        f"{cod}\t{asig}\tZZQ1\tnoche\tLunes\t18:00\t20:00\tMiércoles\t18:00\t21:00\tPresencial\tSin especificar\t"
        f"{docs[0]['nombre_completo']}\t\tSí\tSí\t19:00\t21:00\t{docs[1]['nombre_completo']}",
        f"{cod}\t{asig}\tZZQ2\ttarde\tViernes\t14:00\t16:00\t\t\t\tVirtual\tCampus Virtual\t{docs[1]['nombre_completo']}"
        f"\t\tNo\t\t\t\t",
        f"{cod}\t{asig}\tZZQ1\tnoche\tLunes\t18:00\t20:00\t\t\t\tPresencial\tSin especificar\t\t\t\t\t\t\t",
        "ZZ-NOEXISTE\tMateria inexistente ZZ\tZZQ3\tnoche\tLunes\t18:00\t20:00\t\t\t\tPresencial\tSin especificar\t\t\t\t\t\t\t",
    ]
    return "\n".join(filas)


def test_carga_rapida_preview_y_lote(db_conn, comisiones, service, repo, audit_store):
    rec = _record(service, repo)
    texto = _texto_carga(comisiones, rec)
    prev = comisiones.carga_preview(rec, {"texto": texto})
    assert prev["totales"]["duplicada"] >= 1 and prev["totales"]["error"] >= 1

    def cert(ns):
        per = ns["periodo_actual_para_comisiones"]()
        df = ns["parsear_comisiones_pegadas"](texto)
        pv = ns["preparar_preview_comisiones_rapidas"](df, per["id"])
        df_ok = pv[pv["estado_validacion"].isin(["OK", "ADVERTENCIA"])].copy()
        return ns["cargar_comisiones_rapidas_lote_v232"](df_ok, per), pv

    res_c, err_c, res_n, err_n = comparar(db_conn, audit_store, cert, lambda: comisiones.carga_ejecutar(rec, {
        "texto": texto, "confirmar": True, "huella": prev["huella"]}))
    assert err_c is None and err_n is None, (err_c, err_n)
    r, pv = res_c
    assert res_n["mensaje"].startswith(f"Se cargaron {r['comisiones']} comisiones, {r['horarios']} horarios y "
                                       f"{r['docentes']} asignaciones docentes en ")
    assert [c for c in prev["filas"]] == [
        {k: v for k, v in row.items()} for row in
        __import__("comisiones.service", fromlist=["records"]).records(U.preview_comisiones_decidida(pv), __import__("comisiones.carga", fromlist=["x"]).COLUMNAS_PREVIEW)]  # 6A-B3
