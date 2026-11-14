"""Diferenciales de ESCRITURA de Designaciones: misma operacion de pantalla, certificado vs NEXT, desde el mismo estado.

Lado certificado: la secuencia de la pagina (entry l. 63392-64858, transcrita) llamando a los writers certificados
(``certified_designaciones``).  Lado NEXT: el servicio con una sesion real del AuthService (FakeRepo).  Entre ambos,
ROLLBACK al SAVEPOINT.  Se comparan: designaciones del departamento, movimientos nuevos, asignaciones a comision
(rol / estado / observaciones), vinculos documentales y la secuencia de COMMITs por operacion B12H
(``commit_seq``, ``mutating_statements``, ``committing_writer``, ``nested_system_task``)."""

from __future__ import annotations

from datetime import date

import psycopg
import pytest

from designaciones import rules
from designaciones_support import (  # noqa: F401  (fixtures)
    FIXED_TODAY, audit_rows, audit_store, baseline, certified_designaciones, corregir_fecha_anio_primero, db_conn,
    designaciones, session_for, state,
)

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")

INST, DEP, ABIERTO, CERRADO = 1, 1, 9, 5


def _record(service, repo, dep=DEP, superadmin=False):
    if dep == DEP and not superadmin:
        return session_for(service, repo, 3)[0]
    sup = session_for(service, repo, 1)[0]
    service.set_context(sup, INST, dep, False)
    return sup


def comparar(db_conn, audit_store, certificado, siguiente, dep=DEP):
    max_mov = baseline(db_conn)
    ns = certified_designaciones(db_conn, INST, dep)
    with db_conn.transaction() as tx:
        res_c = certificado(ns)
        st_c = state(db_conn, INST, dep, max_mov)
        ops_c = [o for o in ns["_frames"].ops]
        raise psycopg.Rollback(tx)
    with db_conn.transaction() as tx:
        n_eventos = len(audit_store.events)
        res_n = siguiente()
        st_n = state(db_conn, INST, dep, max_mov)
        eventos = audit_rows(db_conn)
        post = [e.operation for e in audit_store.events[n_eventos:]
                if e.outcome == "SUCCESS" and e.audit_mode == "POST_OPERATION"]
        raise psycopg.Rollback(tx)
    for clave in st_c:
        if st_c[clave] != st_n[clave]:
            import json
            a = [json.loads(x) if isinstance(x, str) else x for x in st_c[clave]] if isinstance(st_c[clave], list) else st_c[clave]
            b = [json.loads(x) if isinstance(x, str) else x for x in st_n[clave]] if isinstance(st_n[clave], list) else st_n[clave]
            if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
                dif = [(i, k, x.get(k), y.get(k)) for i, (x, y) in enumerate(zip(a, b)) if isinstance(x, dict)
                       for k in set(x) | set(y) if x.get(k) != y.get(k)]
                raise AssertionError(f"{clave}: {dif[:6]}")
            raise AssertionError(f"{clave}: {len(a) if isinstance(a, list) else a} vs {len(b) if isinstance(b, list) else b}")
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
        import pprint
        raise AssertionError(f"ops certificado:\n{pprint.pformat(ops_c)}\nops NEXT:\n{pprint.pformat(ops_n)}")
    assert [o["op"] for o in ops_c if not o["commits"]] == post
    return res_c, res_n


def _cuil_con_asignaciones(db_conn, nd: int):
    """CUIL del departamento con ``nd`` designaciones activas en el periodo abierto y asignaciones activas."""
    return db_conn.execute("""
        SELECT d.cuil FROM designaciones d
        JOIN asignaciones_docentes_comision a ON a.cuil=d.cuil AND a.institucion_id=1 AND a.departamento_id=1
             AND a.estado='Activa'
        JOIN comisiones co ON co.id=a.comision_id AND co.periodo_id=9
        WHERE d.periodo_id=9 AND d.estado='Activa' AND COALESCE(d.funcion_no_docente,0)=0
        GROUP BY d.cuil HAVING count(DISTINCT d.id)=%s ORDER BY count(DISTINCT a.id) DESC, d.cuil LIMIT 1""",
                           [nd]).fetchone()[0]


def _nombre(db_conn, cuil):
    return db_conn.execute("""SELECT CASE WHEN apellido IS NOT NULL AND nombres IS NOT NULL THEN apellido||', '||nombres
                              WHEN nombre IS NOT NULL THEN nombre ELSE '' END FROM docentes
                              WHERE institucion_id=1 AND departamento_id=1 AND cuil=%s""", [cuil]).fetchone()[0]


def _documento(db_conn, dep=DEP) -> int:
    return db_conn.execute("""INSERT INTO documentos_respaldo (institucion_id, departamento_id, tipo_documento, categoria,
                              numero, fecha, archivo_nombre, archivo_pdf, titulo)
                              VALUES (1, %s, 'Resolución', 'Designación docente', 'ZZ-1/2026', '2026-08-01',
                              'zz.pdf', '\\x00'::bytea, 'ZZNEXT acto') RETURNING id""", [dep]).fetchone()[0]


# ------------------------------------------------------------------------------------------ Pestaña 2: alta
def _pagina_alta(ns, cuil, nombre, v, acto=None, confirmar=False):
    """entry l. 63744-63797."""
    per = ns["get_periodo_abierto"]()
    did = ns["guardar_designacion"](per["id"], cuil, v["cargo"], v["dedicacion"], v["horas"], v["tipo"], v["adh"],
                                    v["desde"], v["hasta"], v["estado"], v["obs"], permitir_duplicada=confirmar,
                                    numero_resolucion="", funcion_no_docente=v["funcion"],
                                    texto_funcion_no_docente=v["texto"])
    if acto is not None and did is not None:
        ns["vincular_acto_designacion_v266"](did, acto)
    mov = ns["registrar_movimiento"](
        "Alta de designación", cuil, nombre,
        f"{per['nombre']} - {v['cargo']} - {v['dedicacion']} - {v['horas']} hs - {v['tipo']} - Función: "
        f"{'No docente' if v['funcion'] else 'Docencia'}"
        + (f" - Tareas: {ns['_texto_funcion_no_docente_limpio_v164'](v['texto'])}" if v["funcion"] else ""),
        v["obs"], per["id"], horas_variacion=0 if v["funcion"] else v["horas"])
    if acto is not None and mov is not None:
        ns["vincular_acto_movimiento_v266"](mov, acto)
    return did


def _payload_alta(cuil, v, acto=None, confirmar=False):
    return {"cuil": cuil, "cargo": v["cargo"], "dedicacion": v["dedicacion"], "tipo_designacion": v["tipo"],
            "ad_honorem": v["adh"], "fecha_desde": str(v["desde"]), "fecha_hasta": str(v["hasta"]),
            "estado": v["estado"], "funcion_no_docente": v["funcion"], "texto_funcion_no_docente": v["texto"],
            "observaciones": v["obs"], "confirmar_duplicada": confirmar,
            "acto": {"modo": "existente", "documento_id": acto} if acto else {"modo": "pendiente"}}


def _valores(**kw):
    v = {"cargo": "Titular", "dedicacion": "Simple", "tipo": "Interino", "adh": "No", "desde": date(2026, 8, 1),
         "hasta": date(2026, 12, 31), "estado": "Activa", "obs": "ZZNEXT alta", "funcion": False, "texto": ""}
    v.update(kw)
    v["horas"] = rules.horas_segun_dedicacion(v["dedicacion"])
    return v


def test_alta_sincroniza_cargo_en_comisiones(db_conn, designaciones, service, repo, audit_store):
    cuil = _cuil_con_asignaciones(db_conn, 2)
    nombre, v = _nombre(db_conn, cuil), _valores(cargo="Titular")
    rec = _record(service, repo)
    abierto = designaciones.overview(rec)["abierto_huella"]
    rc, rn = comparar(db_conn, audit_store, lambda ns: _pagina_alta(ns, cuil, nombre, v),
                      lambda: designaciones.alta(rec, {**_payload_alta(cuil, v), "abierto_huella": abierto}))
    assert rn["mensaje"] == "Designación registrada correctamente."


@pytest.mark.parametrize("funcion", [False, True])
def test_alta_con_acto_existente(db_conn, designaciones, service, repo, audit_store, funcion):
    acto = _documento(db_conn)
    cuil = _cuil_con_asignaciones(db_conn, 1)
    nombre = _nombre(db_conn, cuil)
    v = _valores(cargo="JTP", dedicacion="Parcial", funcion=funcion, texto="  de coordinación  administrativa ")
    rec = _record(service, repo)
    abierto = designaciones.overview(rec)["abierto_huella"]
    comparar(db_conn, audit_store, lambda ns: _pagina_alta(ns, cuil, nombre, v, acto=acto),
             lambda: designaciones.alta(rec, {**_payload_alta(cuil, v, acto), "abierto_huella": abierto}))


def test_alta_duplicada_confirmada(db_conn, designaciones, service, repo, audit_store):
    f = db_conn.execute("SELECT cuil, cargo, dedicacion, tipo_designacion, ad_honorem, fecha_desde, fecha_hasta, estado "
                        "FROM designaciones WHERE periodo_id=9 AND estado='Activa' AND COALESCE(funcion_no_docente,0)=0 "
                        "ORDER BY id LIMIT 1").fetchone()
    cuil, nombre = f[0], _nombre(db_conn, f[0])
    v = _valores(cargo=f[1], dedicacion=f[2], tipo=f[3], adh=f[4], desde=date.fromisoformat(f[5]),
                 hasta=date.fromisoformat(f[6]), estado=f[7])
    rec = _record(service, repo)
    abierto = designaciones.overview(rec)["abierto_huella"]
    from designaciones.service import DesignacionesError
    with pytest.raises(DesignacionesError) as exc:
        designaciones.alta(rec, {**_payload_alta(cuil, v), "abierto_huella": abierto})
    assert exc.value.message == ("La designación exactamente igual ya existe. Marcá la confirmación si corresponde a "
                                 "otro acto administrativo u otra alta intencional.")
    comparar(db_conn, audit_store, lambda ns: _pagina_alta(ns, cuil, nombre, v, confirmar=True),
             lambda: designaciones.alta(rec, {**_payload_alta(cuil, v, confirmar=True), "abierto_huella": abierto}))


# ------------------------------------------------------------------------------------------ Pestaña 3: modificar
def _fila(ns, did):
    df = ns["get_designaciones"](ABIERTO)
    return df[df["id"] == did].iloc[0]


def _pagina_modificar(ns, did, tipo, d):
    """entry l. 63910-64298 (rama no-baja), con los valores elegidos en el formulario ``d``."""
    import pandas as pd
    per = ns["get_periodo_abierto"]()
    fila = _fila(ns, did)
    sd = ns["safe_date"]
    es_nd, limpio = ns["_es_funcion_no_docente_v162"], ns["_texto_funcion_no_docente_limpio_v164"]
    nuevo_cargo, nueva_dedicacion = fila["cargo"], fila["dedicacion"]
    nuevas_horas = int(fila["horas"]) if pd.notna(fila["horas"]) else 10
    nuevo_tipo, nuevo_adh = fila["tipo_designacion"], fila["ad_honorem"] or "No"
    nueva_funcion = es_nd(fila.get("funcion_no_docente"))
    nuevo_texto = limpio(fila.get("texto_funcion_no_docente", ""))
    texto_anterior = nuevo_texto
    nuevo_estado = fila["estado"] or "Activa"
    nueva_desde = sd(fila["fecha_desde"], sd(per["fecha_inicio"], FIXED_TODAY))
    nueva_hasta = sd(fila["fecha_hasta"], sd(per["fecha_fin"], FIXED_TODAY))
    if tipo == "Cambio de cargo":
        nuevo_cargo = d["cargo"]
    elif tipo in ("Aumento de dedicación", "Disminución de dedicación"):
        nueva_dedicacion = d["dedicacion"]
        nuevas_horas = ns["horas_segun_dedicacion"](nueva_dedicacion, fila.get("horas", 0))
    elif tipo == "Cambio de tipo de designación":
        nuevo_tipo = d["tipo_designacion"]
    elif tipo == "Cambio de condición Ad Honorem":
        nuevo_adh = d["ad_honorem"]
    elif tipo == "Cambio de función docente / no docente":
        nueva_funcion = d["funcion_no_docente"]
    elif tipo == "Modificación general":
        nuevo_cargo, nueva_dedicacion = d["cargo"], d["dedicacion"]
        nuevas_horas = ns["horas_segun_dedicacion"](nueva_dedicacion, fila.get("horas", 0))
        nuevo_tipo, nuevo_adh = d["tipo_designacion"], d["ad_honorem"]
        nueva_desde, nueva_hasta = date.fromisoformat(d["fecha_desde"]), date.fromisoformat(d["fecha_hasta"])
        nuevo_estado, nueva_funcion = d["estado"], d["funcion_no_docente"]
    if nueva_funcion:
        nuevo_texto = d.get("texto_funcion_no_docente", nuevo_texto)
    else:
        nuevo_texto = ""
    nuevas_obs = d["observaciones"]
    detalle_anterior = "Antes: " + ns["detalle_designacion"](fila)
    horas_actuales = int(fila["horas"]) if pd.notna(fila["horas"]) else 0
    texto_nuevo = limpio(nuevo_texto)
    detalle_nuevo = (f"Ahora: {nuevo_cargo} - {nueva_dedicacion} - {nuevas_horas} hs - {nuevo_tipo} - Ad Honorem: "
                     f"{nuevo_adh} - Función: {'No docente' if nueva_funcion else 'Docencia'}"
                     + (f" - Tareas: {texto_nuevo}" if nueva_funcion else "") + f" - Estado {nuevo_estado}")
    tipo_mov = tipo
    if tipo == "Cambio de condición Ad Honorem":
        tipo_mov = "Pase a Ad Honorem" if ns["normalizar_clave"](nuevo_adh) in {"SI", "SÍ"} else "Pase a Rentado"
    era = es_nd(fila.get("funcion_no_docente"))
    if tipo == "Cambio de función docente / no docente" and bool(nueva_funcion) == bool(era) \
            and texto_nuevo != texto_anterior:
        tipo_mov = "Cambio de funciones no docentes"
    antes, despues = (0 if era else horas_actuales), (0 if nueva_funcion else int(nuevas_horas or 0))
    var = despues - antes if tipo_mov in ("Aumento de dedicación", "Disminución de dedicación", "Cambio de cargo",
                                          "Modificación general", "Cambio de función docente / no docente") else 0
    ns["actualizar_designacion"](did, nuevo_cargo, nueva_dedicacion, nuevas_horas, nuevo_tipo, nuevo_adh, nueva_desde,
                                 nueva_hasta, nuevo_estado, nuevas_obs, numero_resolucion=None,
                                 funcion_no_docente=nueva_funcion, texto_funcion_no_docente=texto_nuevo)
    ns["registrar_movimiento"](tipo_mov, fila["cuil"], fila["nombre_completo"],
                               f"{per['nombre']} - {detalle_anterior} / {detalle_nuevo}", nuevas_obs, per["id"],
                               horas_variacion=var)


def _designacion(db_conn, cuil, **filtro):
    extra = "".join(f" AND {k}=%s" for k in filtro)
    return db_conn.execute(f"SELECT id FROM designaciones WHERE periodo_id=9 AND cuil=%s{extra} ORDER BY id LIMIT 1",
                           [cuil, *filtro.values()]).fetchone()[0]


CASOS_MOD = [
    ("Cambio de cargo", {"cargo": "Titular"}),
    ("Aumento de dedicación", {"dedicacion": "Exclusiva"}),
    ("Disminución de dedicación", {"dedicacion": "Simple"}),
    ("Cambio de tipo de designación", {"tipo_designacion": "Concursado"}),
    ("Cambio de condición Ad Honorem", {"ad_honorem": "Sí"}),
    ("Cambio de función docente / no docente", {"funcion_no_docente": True,
                                                "texto_funcion_no_docente": "de coordinación del área"}),
    ("Modificación general", {"cargo": "Asociado", "dedicacion": "Parcial + Simple", "tipo_designacion": "Interino",
                              "ad_honorem": "No", "fecha_desde": "2026-08-15", "fecha_hasta": "2026-12-20",
                              "estado": "Suspendida", "funcion_no_docente": False}),
]


@pytest.mark.parametrize("tipo,datos", CASOS_MOD, ids=[c[0] for c in CASOS_MOD])
def test_modificar_ocho_tipos(db_conn, designaciones, service, repo, audit_store, tipo, datos):
    if tipo == "Disminución de dedicación":
        did = db_conn.execute("SELECT id FROM designaciones WHERE periodo_id=9 AND estado='Activa' AND horas>10 "
                              "ORDER BY id LIMIT 1").fetchone()[0]
    else:
        did = _designacion(db_conn, _cuil_con_asignaciones(db_conn, 2), estado="Activa")
    rec = _record(service, repo)
    fila = next(f for f in designaciones.periodo(rec, ABIERTO)["designaciones"] if f["id"] == did)
    d = {"observaciones": "ZZNEXT modificación", "texto_funcion_no_docente": fila["texto_funcion_no_docente"], **datos}
    comparar(db_conn, audit_store, lambda ns: _pagina_modificar(ns, did, tipo, d),
             lambda: designaciones.modificar(rec, {"id": did, "huella": fila["huella"], "tipo_cambio": tipo,
                                                   "acto": {"modo": "pendiente"}, **d}))


def test_modificar_sin_cambio_real_no_escribe(db_conn, designaciones, service, repo, audit_store):
    did = _designacion(db_conn, _cuil_con_asignaciones(db_conn, 2), estado="Activa")
    rec = _record(service, repo)
    fila = next(f for f in designaciones.periodo(rec, ABIERTO)["designaciones"] if f["id"] == did)
    max_mov = baseline(db_conn)
    antes = state(db_conn, INST, DEP, max_mov)
    res = designaciones.modificar(rec, {"id": did, "huella": fila["huella"], "tipo_cambio": "Cambio de cargo",
                                        "cargo": fila["cargo"], "observaciones": fila["observaciones"] or ""})
    assert res == {"mensaje": "No se efectuó ninguna modificación: el cargo seleccionado es el mismo que el actual.",
                   "tono": "info", "sin_cambios": True}
    assert state(db_conn, INST, DEP, max_mov) == antes and audit_store.events == []


def test_baja_finaliza_asignaciones_a_comision(db_conn, designaciones, service, repo, audit_store):
    cuil = _cuil_con_asignaciones(db_conn, 1)
    did = _designacion(db_conn, cuil, estado="Activa")
    rec = _record(service, repo)
    fila = next(f for f in designaciones.periodo(rec, ABIERTO)["designaciones"] if f["id"] == did)
    fe, motivo = date(2026, 10, 20), "ZZNEXT baja"

    def certificado(ns):
        per = ns["get_periodo_abierto"]()
        f = _fila(ns, did)
        prevista = str(f.get("fecha_hasta_prevista") or f.get("fecha_hasta") or "")
        detalle = (f"{per['nombre']} - Antes: {ns['detalle_designacion'](f)}. Fecha efectiva de baja: {fe}. "
                   f"Vencimiento previsto conservado: {prevista}. ID designación original: {did}.")
        reg = ns["finalizar_designacion_anticipadamente"](did, fe, motivo)
        ns["registrar_movimiento"]("Baja de designación", f["cuil"], f["nombre_completo"], detalle, motivo, per["id"],
                                   horas_variacion=-int(f["horas"]), fecha_movimiento=fe)
        return reg

    rc, rn = comparar(db_conn, audit_store, certificado, lambda: designaciones.modificar(rec, {
        "id": did, "huella": fila["huella"], "tipo_cambio": "Finalizar / baja de designación", "fecha_baja": str(fe),
        "motivo_baja": motivo, "observaciones": "", "acto": {"modo": "pendiente"}}))
    assert rc["_comisiones_finalizadas_auto"] > 0
    assert f"se dieron de baja automáticamente {rc['_comisiones_finalizadas_auto']} asignación/es" in rn["mensaje"]


@pytest.mark.parametrize("fe,error", [(date(2026, 7, 1), "La fecha efectiva no puede ser anterior al inicio de la designación."),
                                      (date(2027, 2, 1), "La fecha efectiva no puede ser posterior al vencimiento previsto.")])
def test_baja_fechas_invalidas(db_conn, designaciones, service, repo, audit_store, fe, error):
    from designaciones.service import DesignacionesError
    cuil = _cuil_con_asignaciones(db_conn, 1)
    did = _designacion(db_conn, cuil, estado="Activa")
    rec = _record(service, repo)
    fila = next(f for f in designaciones.periodo(rec, ABIERTO)["designaciones"] if f["id"] == did)
    with pytest.raises(DesignacionesError) as exc:
        designaciones.modificar(rec, {"id": did, "huella": fila["huella"], "tipo_cambio": "Finalizar / baja de designación",
                                      "fecha_baja": str(fe), "motivo_baja": "", "observaciones": ""})
    assert exc.value.message == error
    assert [(e.outcome, e.metadata.get("coupled_commits")) for e in audit_store.events] == [("FAILED", 0)]


# ------------------------------------------------------------------------------------------ Pestaña 4: por error
def test_corregir_por_error_limpia_movimientos(db_conn, designaciones, service, repo, audit_store):
    from designaciones import escrituras as E
    from designaciones.repository import DesignacionesRepository
    r = DesignacionesRepository(db_conn, INST, DEP)
    did = next(int(f["id"]) for f in r.designaciones(ABIERTO)
               if E.ids_movimientos_que_referencian(r, r.designacion_ref(int(f["id"]))))
    rec = _record(service, repo)
    fila = next(f for f in designaciones.periodo(rec, ABIERTO)["designaciones"] if f["id"] == did)
    datos = {"cargo": "Titular", "dedicacion": "Exclusiva", "tipo_designacion": "Concursado", "ad_honorem": "No",
             "funcion_no_docente": False, "fecha_desde": "2026-08-02", "fecha_hasta": "2026-12-30", "estado": "Activa",
             "observaciones": "ZZNEXT corrección"}
    rc, rn = comparar(db_conn, audit_store, lambda ns: ns["actualizar_designacion_por_error"](
        did, "Titular", "Exclusiva", ns["horas_segun_dedicacion"]("Exclusiva", fila["horas"]), "Concursado", "No",
        date(2026, 8, 2), date(2026, 12, 30), "Activa", "ZZNEXT corrección", numero_resolucion=None,
        funcion_no_docente=False, texto_funcion_no_docente=""),
        lambda: designaciones.corregir(rec, {"id": did, "huella": fila["huella"], "confirmar": True, **datos}))
    assert rc >= 1 and rn["mensaje"] == (f"Designación corregida sin registrar movimiento. Se limpiaron {rc} "
                                         "movimiento/s que describían datos ya inexistentes.")


def test_eliminar_individual_y_masivo(db_conn, designaciones, service, repo, audit_store):
    cuil = _cuil_con_asignaciones(db_conn, 2)
    ids = [r[0] for r in db_conn.execute("SELECT id FROM designaciones WHERE periodo_id=9 AND cuil=%s ORDER BY id",
                                         [cuil]).fetchall()]
    rec = _record(service, repo, superadmin=True)  # B10: designaciones.delete solo superadmin
    filas = {f["id"]: f for f in designaciones.periodo(rec, ABIERTO)["designaciones"]}
    rc, rn = comparar(db_conn, audit_store, lambda ns: ns["eliminar_designacion"](ids[0]),
                      lambda: designaciones.eliminar(rec, {"id": ids[0], "huella": filas[ids[0]]["huella"],
                                                           "confirmar": True}))
    assert rc["designaciones_eliminadas"] == 1
    rc, rn = comparar(db_conn, audit_store, lambda ns: ns["eliminar_designaciones_por_error_masivo"](ids),
                      lambda: designaciones.eliminar_masivo(rec, {"confirmar": True, "seleccion": [
                          {"id": i, "huella": filas[i]["huella"]} for i in ids]}))
    assert rc["designaciones_eliminadas"] == len(ids)


def test_grilla_de_fechas_sin_movimiento(db_conn, designaciones, service, repo, audit_store):
    rec = _record(service, repo)
    filas = designaciones.periodo(rec, ABIERTO)["designaciones"][:2]
    cambios = [{"id": f["id"], "huella": f["huella"], "desde": "2026-08-03", "hasta": "2026-12-15"} for f in filas]

    def certificado(ns):
        for f in filas:
            ns["actualizar_resolucion_fechas_designacion_directo_v171"](f["id"], f["numero_resolucion_legacy"],
                                                                        "2026-08-03", "2026-12-15")

    comparar(db_conn, audit_store, certificado, lambda: designaciones.fechas(rec, {"cambios": cambios}))


def test_grilla_historica_sincroniza_baja_v207(db_conn, designaciones, service, repo, audit_store):
    rec = _record(service, repo)
    data = designaciones.periodo(rec, CERRADO)
    assert data["historico"] is True
    filas = [f for f in data["designaciones"] if f["fecha_hasta"] == "2026-07-31"][:2]
    cambios = [{"id": filas[0]["id"], "huella": filas[0]["huella"], "desde": filas[0]["fecha_desde"],
                "hasta": "2026-05-15"},
               {"id": filas[1]["id"], "huella": filas[1]["huella"], "desde": "2026-02-01", "hasta": "2026-07-31"}]

    def certificado(ns):
        for c, f in zip(cambios, filas):
            ns["actualizar_resolucion_fechas_designacion_directo_v171"](c["id"], f["numero_resolucion"], c["desde"],
                                                                        c["hasta"])
            if c["hasta"] != f["fecha_hasta"]:
                ns["sincronizar_movimiento_baja_designacion_v207"](
                    c["id"], c["hasta"], origen="corrección de fecha_hasta en grilla histórica")

    rc, rn = comparar(db_conn, audit_store, certificado,
                      lambda: designaciones.fechas_historicas(rec, {"periodo_id": CERRADO, "cambios": cambios}))
    assert rn["mensaje"] == ("Se guardaron 2 corrección/es de fechas del período histórico. "
                             "Movimientos de baja sincronizados: 1.")


# ------------------------------------------------------------------------------------------ Actos v266/v267
def test_vincular_y_desvincular_masivo(db_conn, designaciones, service, repo, audit_store):
    acto = _documento(db_conn)
    rec = _record(service, repo, superadmin=True)  # B10: documentos.delete solo superadmin
    data = designaciones.periodo(rec, ABIERTO)
    filas = data["designaciones"][:3]
    sel = [{"id": f["id"], "huella": f["huella"]} for f in filas]
    ids = [f["id"] for f in filas]
    rc, rn = comparar(db_conn, audit_store, lambda ns: ns["vincular_acto_designaciones_masivo_v267"](ids, acto),
                      lambda: designaciones.vincular(rec, {"destino": "designaciones", "periodo_id": ABIERTO,
                                                           "seleccion": sel, "documento_id": acto}, False))
    assert rn["mensaje"] == "Acto administrativo vinculado a 3 designación/es."
    comparar(db_conn, audit_store, lambda ns: ns["desvincular_acto_designaciones_masivo_v267"](ids),
             lambda: designaciones.vincular(rec, {"destino": "designaciones", "periodo_id": ABIERTO,
                                                  "seleccion": sel}, True))
    movs = [h for h in data["historial"] if h["tipo_movimiento"] in rules.MOVIMIENTOS_ACTO_ADMINISTRATIVO_V266
            and h["id"] > 0][:2]
    if movs:
        sel_m = [{"id": h["id"], "huella": h["huella"]} for h in movs]
        comparar(db_conn, audit_store, lambda ns: ns["vincular_acto_movimientos_masivo_v267"]([h["id"] for h in movs],
                                                                                             acto),
                 lambda: designaciones.vincular(rec, {"destino": "movimientos", "periodo_id": ABIERTO,
                                                      "seleccion": sel_m, "documento_id": acto}, False))


# ------------------------------------------------------------------------------------------ Pestaña 5: carga rapida
def test_carga_rapida_fila_por_fila(db_conn, designaciones, service, repo, audit_store):
    cuil = _cuil_con_asignaciones(db_conn, 2)
    texto = ("cuil\tcargo\tdedicacion\ttipo_designacion\tnumero_resolucion\tad_honorem\tfecha_desde\tfecha_hasta\t"
             f"observaciones\n{cuil}\tTitular\tParcial\tConcursado\tR-77/2026\tNo\t01/08/2026\t31/12/2026\tZZNEXT\n"
             f"{cuil}\tJTP\tSimple\tInterino\t\tsi\t2026-03-01\t2026-07-31\tZZNEXT hist\n")
    rec = _record(service, repo)

    def certificado(ns):
        # Desviacion deliberada (docs/ETAPA5_FINAL_REMEDIATION.md): la fila 2026-03-01 se guarda 2026-03-01, no
        # 2026-01-03 como en el certificado.
        corregir_fecha_anio_primero(ns)
        abierto = ns["get_periodo_abierto"]()
        df = ns["parsear_designaciones_pegadas"](texto, abierto)
        assert ns["detectar_designaciones_duplicadas_carga"](df, abierto).empty
        for _, row in df.iterrows():
            per = ns["get_periodo_por_nombre"](row["periodo"]) if row["periodo"] else abierto
            horas = ns["horas_segun_dedicacion"](row["dedicacion"], row["horas"])
            ns["guardar_designacion"](per["id"], row["cuil"], row["cargo"], row["dedicacion"], horas,
                                      row["tipo_designacion"], row["ad_honorem"] or "No", row["fecha_desde"],
                                      row["fecha_hasta"], row["estado"] or "Activa", row["observaciones"],
                                      permitir_duplicada=False, numero_resolucion=row["numero_resolucion"])
            doc = ns["docente_existe"](row["cuil"]).iloc[0]
            ns["registrar_movimiento"]("Alta de designación", row["cuil"],
                                       ns["nombre_completo"](doc["apellido"], doc["nombres"]) or doc["nombre"],
                                       f"{per['nombre']} - {row['cargo']} - {row['dedicacion']} - {horas} hs - "
                                       f"{row['tipo_designacion']}", row["observaciones"], per["id"],
                                       horas_variacion=horas)

    rc, rn = comparar(db_conn, audit_store, certificado, lambda: designaciones.carga_ejecutar(rec, texto, False))
    assert rn["mensaje"] == "Carga finalizada. Designaciones cargadas: 2. Omitidas: 0."


# ------------------------------------------------------------------------------------------ legado "Simple Ad Honorem"
@pytest.mark.parametrize("tipo,datos", [
    ("Cambio de cargo", {"cargo": "Titular"}),
    ("Modificación general", {"cargo": "JTP", "dedicacion": "Simple", "tipo_designacion": "Interino",
                              "ad_honorem": "Sí", "fecha_desde": "2026-08-01", "fecha_hasta": "2026-12-31",
                              "estado": "Activa", "funcion_no_docente": False}),
])
def test_legado_simple_ad_honorem(db_conn, designaciones, service, repo, audit_store, tipo, datos):
    """Fuera del catálogo: el cambio de cargo la conserva; Modificación general guarda lo que preselecciona el
    formulario certificado ("Simple", ``safe_index``).  Sin limpieza masiva."""
    did, per = db_conn.execute("SELECT id, periodo_id FROM designaciones WHERE dedicacion='Simple Ad Honorem' AND "
                               "departamento_id=9 AND periodo_id=14 ORDER BY id LIMIT 1").fetchone()
    rec = _record(service, repo, dep=9)
    fila = next(f for f in designaciones.periodo(rec, per)["designaciones"] if f["id"] == did)
    assert fila["dedicacion"] == "Simple Ad Honorem"
    assert rules.DEDICACIONES[0] == "Simple"  # lo que muestra el selectbox certificado (safe_index -> 0)
    d = {"observaciones": "ZZNEXT legado", **datos}

    def certificado(ns):
        global ABIERTO
        prev, ABIERTO = ABIERTO, per
        try:
            _pagina_modificar(ns, did, tipo, d)
        finally:
            ABIERTO = prev

    comparar(db_conn, audit_store, certificado,
             lambda: designaciones.modificar(rec, {"id": did, "huella": fila["huella"], "tipo_cambio": tipo, **d}),
             dep=9)
    otras = db_conn.execute("SELECT count(*) FROM designaciones WHERE dedicacion='Simple Ad Honorem'").fetchone()[0]
    assert otras == 6
