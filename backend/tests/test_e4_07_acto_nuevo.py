"""E4-07 — Designaciones → "Cargar un nuevo acto ahora" (alta, finalización / baja, modificación).

Diferencial contra B13-FIX02, desde el mismo estado (SAVEPOINT + ROLLBACK):
- lado certificado: el formulario en linea ``_render_nuevo_acto_inline_v267`` (l. 54565) EJECUTADO con un Streamlit que
  graba cada control y devuelve los valores elegidos (sus ``errores``, defaults y textos salen del certificado), luego
  la secuencia de la pagina (alta l. 63744-63797, baja l. 64110-64157, modificacion l. 64246-64298) con
  ``_resolver_acto_contextual_v267``, los writers certificados de Designaciones y ``_eliminar_acto_recien_creado_v267``;
- lado NEXT: ``ActoContextualService`` (composicion) -> ``DesignacionesService.alta`` / ``.modificar`` con el puerto
  ``ActoNuevo`` -> writers de Resoluciones y respaldos.
Se comparan: designaciones, movimientos, asignaciones, documentos (binario como md5 + largo), vinculos acto <->
designacion / movimiento, la secuencia de operaciones B12H con sus COMMITs y el mensaje visible.
"""
from __future__ import annotations

import ast
import contextlib
import json
import pprint
import re
from datetime import date
from pathlib import Path

import psycopg
import pytest

import designaciones_support as DS
from designaciones import escrituras as DE
from designaciones_support import (  # noqa: F401  (fixtures)
    FIXED_TODAY, audit_rows, audit_store, certified_designaciones, db_conn, designaciones, session_for,
)
from resoluciones_support import MAX_IDS, certified_resoluciones, make_resoluciones, pdf_sintetico
from resoluciones_support import baseline as res_baseline
from resoluciones_support import state as res_state
from test_designaciones_writes_differential import _cuil_con_asignaciones, _designacion, _fila, _nombre, _payload_alta
from test_designaciones_writes_differential import _pagina_modificar, _valores

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")

INST, DEP, ABIERTO = 1, 1, 9
BACKEND = Path(__file__).resolve().parents[1]
SUFIJO_ALTA = " El nuevo acto también fue guardado en Resoluciones y respaldos."
SUFIJO_BAJA = " El nuevo acto administrativo fue guardado en Resoluciones y respaldos."
SUFIJO_MOD = " El nuevo acto administrativo fue guardado en Resoluciones y respaldos y quedó vinculado a la modificación."
L_TIPO, L_NUM, L_FECHA = "Tipo de documento", "Número / código del acto", "Fecha del acto"
L_TIT, L_DET, L_OBS = "Título / asunto", "Detalle / referencia adicional", "Observaciones internas"
L_PDF = "PDF del acto administrativo (opcional; puede cargarse después)"


# ------------------------------------------------------------------------------------------ fixtures
@pytest.fixture
def resoluciones(service, audit_store, db_conn):
    return make_resoluciones(service, audit_store, db_conn)  # mismo FakeRepo (ya extendido por ``designaciones``)


@pytest.fixture
def acto(designaciones, resoluciones):
    from integraciones.acto_contextual import ActoContextualService
    return ActoContextualService(designaciones, resoluciones)


def _record(service, repo, uid=3, dep=None):
    rec = session_for(service, repo, uid)[0]
    if dep is not None:
        service.set_context(rec, INST, dep, False)
    return rec


# ------------------------------------------------------------------------------------------ formulario certificado
class _Subido:
    def __init__(self, nombre, mime, contenido):
        self.name, self.type, self._c = nombre, mime, contenido

    def getvalue(self):
        return self._c


class _Form:
    """Streamlit que graba los controles de ``_render_nuevo_acto_inline_v267`` y devuelve los valores elegidos."""
    session_state: dict = {}

    def __init__(self, valores: dict):
        self.v, self.eventos = valores, []

    def markdown(self, t, **_):
        self.eventos.append(("markdown", t))

    def caption(self, t, **_):
        self.eventos.append(("caption", t))

    def warning(self, t, **_):
        self.eventos.append(("warning", t))

    def selectbox(self, label, options, key=None, help=None, **_):
        options = list(options)
        self.eventos.append(("selectbox", label, options, help))
        valor = self.v.get(label, options[0])
        assert valor in options, (label, valor, options)
        return valor

    def text_input(self, label, value="", placeholder=None, key=None, **_):
        self.eventos.append(("text_input", label, value, placeholder))
        return self.v.get(label, value)

    def date_input(self, label, value=None, key=None, **_):
        self.eventos.append(("date_input", label, value))
        return self.v.get(label, value)

    def text_area(self, label, value="", key=None, height=None, **_):
        self.eventos.append(("text_area", label, value))
        return self.v.get(label, value)

    def file_uploader(self, label, type=None, key=None, **_):
        self.eventos.append(("file_uploader", label, type))
        return self.v.get(label)

    @staticmethod
    def columns(n):
        return [contextlib.nullcontext() for _ in range(n)]


class _Cert:
    """Ambos namespaces certificados sobre la misma conexion; junta las operaciones B12H en el orden de la pagina."""

    def __init__(self, db_conn, dep=DEP):
        self.nsr = certified_resoluciones(db_conn, INST, dep)
        self.nsd = certified_designaciones(db_conn, INST, dep)
        self.ops: list = []
        self.eventos: list = []

    def __call__(self, ns, name, *a, **k):
        n = len(ns["_frames"].ops)
        try:
            return ns[name](*a, **k)
        finally:
            self.ops += ns["_frames"].ops[n:]

    def render(self, valores, categoria, periodo_id, titulo_sugerido, detalle_sugerido=""):
        form, previo = _Form(valores), self.nsr["st"]
        self.nsr["st"] = form
        try:
            payload = self.nsr["_render_nuevo_acto_inline_v267"]("k", categoria, periodo_id=periodo_id,
                                                                  titulo_sugerido=titulo_sugerido,
                                                                  detalle_sugerido=detalle_sugerido)
        finally:
            self.nsr["st"] = previo
        self.eventos = form.eventos
        return {"modo": "nuevo", "documento_id": None, "payload": payload}

    def resolver(self, config, periodo_id, categoria, **k):
        return self(self.nsr, "_resolver_acto_contextual_v267", config, periodo_id, categoria, **k)

    def compensar(self, documento_id):
        self(self.nsr, "_eliminar_acto_recien_creado_v267", documento_id)


def _categoria(tipo):
    from deptit_refactor.extracted_batch01.movimientos import _categoria_respaldo_movimiento_v263
    return _categoria_respaldo_movimiento_v263(tipo)


# ------------------------------------------------------------------------------------------ estado y comparacion
def estado(conn, max_mov, dep=DEP) -> dict:
    out = DS.state(conn, INST, dep, max_mov)
    out.pop("links_designaciones"), out.pop("links_movimientos")
    r = res_state(conn, INST)
    out["documentos_respaldo"], out["dependencias"] = r["documentos_respaldo"], r["dependencias_documentales"]
    max_doc = MAX_IDS["documentos_respaldo"]

    def doc(i):
        return "nuevo" if i > max_doc else str(i)
    out["links_d"] = sorted((doc(a), "nueva" if b > DS.MAX_DES_ID[0] else str(b)) for a, b in conn.execute(
        "SELECT documento_id, designacion_id FROM documentos_respaldo_designaciones WHERE institucion_id=%s", [INST]))
    out["links_m"] = sorted((doc(a), "nuevo" if b > max_mov else str(b)) for a, b in conn.execute(
        "SELECT documento_id, movimiento_id FROM documentos_respaldo_movimientos WHERE institucion_id=%s", [INST]))
    return out


def _correr(fn):
    try:
        return fn(), None
    except psycopg.Error:
        raise
    except Exception as exc:
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


def comparar(db_conn, audit_store, certificado, siguiente, dep=DEP):
    max_mov = DS.baseline(db_conn)
    res_baseline(db_conn)
    cert = _Cert(db_conn, dep)
    with db_conn.transaction() as tx:
        rc, ec = _correr(lambda: certificado(cert))
        st_c = estado(db_conn, max_mov, dep)
        raise psycopg.Rollback(tx)
    with db_conn.transaction() as tx:
        n = len(audit_store.events)
        rn, en = _correr(siguiente)
        st_n = estado(db_conn, max_mov, dep)
        eventos = audit_rows(db_conn)
        nuevos = audit_store.events[n:]
        raise psycopg.Rollback(tx)
    for clave in st_c:
        assert st_c[clave] == st_n[clave], f"{clave}:\ncert {pprint.pformat(st_c[clave])[:1500]}\n" \
                                           f"NEXT {pprint.pformat(st_n[clave])[:1500]}"
    ops_c = [o for o in cert.ops if o["commits"]]
    ops_n = _ops(eventos)
    assert ops_c == ops_n, f"cert:\n{pprint.pformat(ops_c)}\nNEXT:\n{pprint.pformat(ops_n)}"
    return {"rc": rc, "ec": ec, "rn": rn, "en": en, "nuevos": nuevos, "ops": ops_n, "cert": cert, "eventos": eventos}


# ------------------------------------------------------------------------------------------ datos del formulario
def _dependencia(db_conn, nombre="Rectorado"):
    row = db_conn.execute("SELECT id, nombre FROM dependencias_documentales WHERE institucion_id=1 AND nombre=%s "
                          "AND estado='Activa'", [nombre]).fetchone()
    return int(row[0]), str(row[1])


def valores(tipo="Resolución", dep=None, numero="ZZNEXT-7/2026", fecha=date(2026, 10, 30), titulo=None, detalle=None,
            obs="ZZNEXT obs acto", pdf=None):
    """Lo que el usuario elige en el formulario (claves = rotulos certificados); ``None`` = dejar el default."""
    v = {L_TIPO: tipo, L_NUM: numero, L_FECHA: fecha, L_OBS: obs}
    if dep is not None:
        v["Dependencia emisora" if tipo in ("Resolución", "Disposición") else "Dependencia emisora (opcional)"] = dep
    if titulo is not None:
        v[L_TIT] = titulo
    if detalle is not None:
        v[L_DET] = detalle
    if pdf is not None:
        v[L_PDF] = _Subido(*pdf)
    return v


def payload_next(v, deps: dict, titulo_sugerido, detalle_sugerido=""):
    """Lo que envia el formulario web: mismos valores; titulo / detalle prellenados con las sugerencias."""
    dep = v.get("Dependencia emisora", v.get("Dependencia emisora (opcional)"))
    return {"tipo_documento": v[L_TIPO], "numero": v[L_NUM], "fecha": v[L_FECHA].isoformat(),
            "dependencia_id": deps[dep] if dep else None, "titulo": v.get(L_TIT, titulo_sugerido),
            "detalle": v.get(L_DET, detalle_sugerido), "observaciones": v[L_OBS]}


def archivo_next(v):
    from resoluciones_respaldos.service import Archivo
    s = v.get(L_PDF)
    return None if s is None else Archivo(nombre=s.name, mime=s.type, contenido=s.getvalue())


# ------------------------------------------------------------------------------------------ pagina certificada
def cert_alta(cert, cuil, nombre, v, val, romper=False):
    """entry l. 63709-63797 con el acto nuevo."""
    nsd = cert.nsd
    per = nsd["get_periodo_abierto"]()
    det = (f"{per['nombre']} - {nombre} - {v['cargo']} - {v['dedicacion']} - {v['horas']} hs - {v['tipo']} - "
           f"Función: {'No docente' if v['funcion'] else 'Docencia'}")
    config = cert.render(val, "Designación docente", per["id"], f"Designación — {nombre}", det)
    try:
        acto_id, creado = cert.resolver(config, per["id"], "Designación docente",
                                        referencia_texto=f"Designación: {nombre} — CUIL {cuil}",
                                        titulo_sugerido=f"Designación — {nombre}", detalle_sugerido=det,
                                        observaciones_sugeridas=v["obs"])
    except Exception as exc:
        return {"error": str(exc)}
    did = None
    try:
        if romper:
            raise RuntimeError("fallo inyectado")
        did = cert(nsd, "guardar_designacion", per["id"], cuil, v["cargo"], v["dedicacion"], v["horas"], v["tipo"],
                   v["adh"], v["desde"], v["hasta"], v["estado"], v["obs"], permitir_duplicada=False,
                   numero_resolucion="", funcion_no_docente=v["funcion"], texto_funcion_no_docente=v["texto"])
        if acto_id is not None and did is not None:
            cert(nsd, "vincular_acto_designacion_v266", did, acto_id)
        mov = cert(nsd, "registrar_movimiento", "Alta de designación", cuil, nombre,
                   f"{per['nombre']} - {v['cargo']} - {v['dedicacion']} - {v['horas']} hs - {v['tipo']} - Función: "
                   f"{'No docente' if v['funcion'] else 'Docencia'}"
                   + (f" - Tareas: {nsd['_texto_funcion_no_docente_limpio_v164'](v['texto'])}" if v["funcion"] else ""),
                   v["obs"], per["id"], horas_variacion=0 if v["funcion"] else v["horas"])
        if acto_id is not None and mov is not None:
            cert(nsd, "vincular_acto_movimiento_v266", mov, acto_id)
        return {"mensaje": "Designación registrada correctamente." + (SUFIJO_ALTA if creado else "")}
    except Exception as exc:
        if did is None and creado:
            cert.compensar(acto_id)
        return {"error": f"No se pudo registrar la designación: {exc}"}


def cert_baja(cert, did, fe, motivo, val, romper=False):
    """entry l. 64091-64157 con el acto nuevo."""
    nsd = cert.nsd
    per = nsd["get_periodo_abierto"]()
    f = _fila(nsd, did)
    tipo_cambio = "Finalizar / baja de designación"
    config = cert.render(val, _categoria(tipo_cambio), per["id"], f"{tipo_cambio} — {f['nombre_completo']}", "")
    prevista = str(f.get("fecha_hasta_prevista") or f.get("fecha_hasta") or "")
    detalle = (f"{per['nombre']} - Antes: {nsd['detalle_designacion'](f)}. Fecha efectiva de baja: {fe}. "
               f"Vencimiento previsto conservado: {prevista}. ID designación original: {did}.")
    try:
        acto_id, creado = cert.resolver(config, per["id"], _categoria("Baja de designación"),
                                        referencia_texto=f"Baja de designación: {f['nombre_completo']} — CUIL {f['cuil']}",
                                        titulo_sugerido=f"Baja de designación — {f['nombre_completo']}",
                                        detalle_sugerido=detalle, observaciones_sugeridas=motivo)
    except Exception as exc:
        return {"error": str(exc)}
    mov = None
    try:
        if romper:
            raise RuntimeError("fallo inyectado")
        reg = cert(nsd, "finalizar_designacion_anticipadamente", did, fe, motivo)
        mov = cert(nsd, "registrar_movimiento", "Baja de designación", f["cuil"], f["nombre_completo"], detalle, motivo,
                   per["id"], horas_variacion=-int(f["horas"]), fecha_movimiento=fe)
        if acto_id is not None and mov is not None:
            cert(nsd, "vincular_acto_movimiento_v266", mov, acto_id)
        n = int((reg or {}).get("_comisiones_finalizadas_auto", 0) or 0)
        msg = ("Designación finalizada. Se conservaron por separado el vencimiento previsto, la fecha efectiva de baja "
               "y la fecha de registro.")
        if creado:
            msg += SUFIJO_BAJA
        if n:
            msg += (f" Además, al quedar sin otra designación docente vigente, se dieron de baja automáticamente {n} "
                    "asignación/es activa/s a comisión del período con la misma fecha efectiva.")
        return {"mensaje": msg}
    except Exception as exc:
        if creado and mov is None:
            cert.compensar(acto_id)
        return {"error": str(exc)}


def cert_mod(cert, db_conn, did, tipo, d, val, tipo_mov, max_mov):
    """entry l. 64091-64098 (formulario) y 64246-64298: acto resuelto antes de actualizar; vinculo al movimiento."""
    nsd = cert.nsd
    per = nsd["get_periodo_abierto"]()
    f = _fila(nsd, did)
    config = cert.render(val, _categoria(tipo), per["id"], f"{tipo} — {f['nombre_completo']}", "")
    acto_id, creado = cert.resolver(config, per["id"], _categoria(tipo_mov),
                                    referencia_texto=f"{tipo_mov}: {f['nombre_completo']} — CUIL {f['cuil']}",
                                    titulo_sugerido=f"{tipo_mov} — {f['nombre_completo']}",
                                    detalle_sugerido="(detalle del movimiento)", observaciones_sugeridas=d["observaciones"])
    n = len(nsd["_frames"].ops)
    _pagina_modificar(nsd, did, tipo, d)  # actualizar_designacion + registrar_movimiento certificados
    cert.ops += nsd["_frames"].ops[n:]
    mov = db_conn.execute("SELECT max(id) FROM movimientos WHERE id > %s", [max_mov]).fetchone()[0]
    cert(nsd, "vincular_acto_movimiento_v266", mov, acto_id)
    return {"mensaje": "Designación actualizada correctamente." + (SUFIJO_MOD if creado else "")}


# ------------------------------------------------------------------------------------------ alta
@pytest.mark.parametrize("caso", ["resolucion_pdf", "disposicion_sin_pdf", "otro_sin_dependencia_titulo_vacio"])
def test_alta_con_acto_nuevo(db_conn, designaciones, service, repo, audit_store, acto, caso):
    cuil = _cuil_con_asignaciones(db_conn, 1)
    nombre, v = _nombre(db_conn, cuil), _valores(cargo="JTP", dedicacion="Parcial")
    dep_id, dep_nom = _dependencia(db_conn)
    deps = {dep_nom: dep_id}
    if caso == "resolucion_pdf":
        val = valores(dep=dep_nom, pdf=("ZZNEXT acto.pdf", "application/pdf", pdf_sintetico("e4-07")))
    elif caso == "disposicion_sin_pdf":
        val = valores(tipo="Disposición", dep=dep_nom, numero="ZZNEXT-D-3/2026", detalle="ZZNEXT detalle propio")
    else:
        val = valores(tipo="Otro", numero="", titulo="")  # sin dependencia ni numero; titulo vacio -> sugerido
    rec = _record(service, repo)
    ov = designaciones.overview(rec)
    det = (f"{ov['abierto']['nombre']} - {nombre} - JTP - Parcial - {v['horas']} hs - {v['tipo']} - Función: Docencia")
    datos = {**_payload_alta(cuil, v), "abierto_huella": ov["abierto_huella"],
             "acto": {"modo": "nuevo", "payload": payload_next(val, deps, f"Designación — {nombre}", det)}}
    r = comparar(db_conn, audit_store, lambda c: cert_alta(c, cuil, nombre, v, val),
                 lambda: acto.alta(rec, datos, archivo_next(val)))
    assert r["en"] is None and r["rn"]["mensaje"] == r["rc"]["mensaje"] == "Designación registrada correctamente." + SUFIJO_ALTA
    assert [o["op"] for o in r["ops"]] == ["guardar_documento_respaldo_v251", "guardar_designacion",
                                           "vincular_acto_designacion_v266", "registrar_movimiento",
                                           "vincular_acto_movimiento_v266"]


@pytest.mark.parametrize("val,mensaje", [
    (valores(numero=""), "No se puede crear el acto administrativo: Seleccioná la dependencia emisora. Completá el "
                         "número del acto administrativo."),
    (valores(tipo="Disposición", numero="ZZ-1"), "No se puede crear el acto administrativo: Seleccioná la dependencia "
                                                 "emisora."),
    (valores(tipo="Otro", numero="", pdf=("g.pdf", "application/pdf", pdf_sintetico("g", 50 * 1024 * 1024))),
     "No se puede crear el acto administrativo: El PDF supera 50 MB."),
], ids=["resolucion_sin_dependencia_ni_numero", "disposicion_sin_dependencia", "pdf_mayor_50mb"])
def test_alta_errores_del_formulario_no_escriben(db_conn, designaciones, service, repo, audit_store, acto, val, mensaje):
    from designaciones.service import DesignacionesError
    cuil = _cuil_con_asignaciones(db_conn, 1)
    nombre, v = _nombre(db_conn, cuil), _valores()
    rec = _record(service, repo)
    ov = designaciones.overview(rec)
    datos = {**_payload_alta(cuil, v), "abierto_huella": ov["abierto_huella"],
             "acto": {"modo": "nuevo", "payload": payload_next(val, {}, f"Designación — {nombre}")}}
    r = comparar(db_conn, audit_store, lambda c: cert_alta(c, cuil, nombre, v, val),
                 lambda: acto.alta(rec, datos, archivo_next(val)))
    assert r["rc"] == {"error": mensaje}
    assert isinstance(r["en"], DesignacionesError) and (r["en"].status, r["en"].message) == (422, mensaje)
    assert r["ops"] == [] and r["nuevos"] == []  # ni escrituras ni eventos B12H (el certificado valida antes del writer)


def test_alta_falla_y_compensa_el_acto_recien_creado(db_conn, designaciones, service, repo, audit_store, acto,
                                                     monkeypatch):
    """l. 63794-63796: si falla sin que exista la designacion, ``_eliminar_acto_recien_creado_v267`` borra el acto
    (documento, PDF y vinculos): queda como antes.  Mensaje NEXT generico (hardening de errores)."""
    from designaciones.service import DesignacionesError

    cuil = _cuil_con_asignaciones(db_conn, 1)
    nombre, v = _nombre(db_conn, cuil), _valores()
    dep_id, dep_nom = _dependencia(db_conn)
    val = valores(dep=dep_nom, pdf=("ZZNEXT.pdf", "application/pdf", pdf_sintetico("comp")))
    rec = _record(service, repo)
    ov = designaciones.overview(rec)
    datos = {**_payload_alta(cuil, v), "abierto_huella": ov["abierto_huella"],
             "acto": {"modo": "nuevo", "payload": payload_next(val, {dep_nom: dep_id}, f"Designación — {nombre}")}}

    def roto(*a, **k):
        raise RuntimeError("fallo inyectado")
    monkeypatch.setattr(DE, "guardar_designacion", roto)
    r = comparar(db_conn, audit_store, lambda c: cert_alta(c, cuil, nombre, v, val, romper=True),
                 lambda: acto.alta(rec, datos, archivo_next(val)))
    assert r["rc"] == {"error": "No se pudo registrar la designación: fallo inyectado"}
    assert isinstance(r["en"], DesignacionesError) and r["en"].message.startswith("No se pudo registrar la designación: ")
    assert "fallo inyectado" not in r["en"].message
    assert [o["op"] for o in r["ops"]] == ["guardar_documento_respaldo_v251", "_eliminar_acto_recien_creado_v267"]
    assert [(e.operation, e.outcome) for e in r["nuevos"]] == [("guardar_designacion", "FAILED")]
    comp = [e for e in r["eventos"] if e["operation"] == "_eliminar_acto_recien_creado_v267"]
    assert {(e["entity_type"], e["action"], e["action_scope"], e["outcome"], e["audit_mode"]) for e in comp} == {
        ("acto_administrativo", "documentos.write", "department", "SUCCESS", "IN_TRANSACTION")}
    assert len(comp) == 2 and len({e["entity_id"] for e in comp}) == 1 and comp[0]["entity_id"].isdigit()
    doc = [e for e in r["eventos"] if e["operation"] == "guardar_documento_respaldo_v251"]
    assert {(e["entity_type"], e["action"], e["outcome"]) for e in doc} == {("documento", "documentos.write", "SUCCESS")}


# ------------------------------------------------------------------------------------------ baja y modificacion
def _baja(db_conn, designaciones, service, repo):
    cuil = _cuil_con_asignaciones(db_conn, 1)
    did = _designacion(db_conn, cuil, estado="Activa")
    rec = _record(service, repo)
    fila = next(f for f in designaciones.periodo(rec, ABIERTO)["designaciones"] if f["id"] == did)
    return did, rec, fila


@pytest.mark.parametrize("romper", [False, True], ids=["ok", "falla_y_compensa"])
def test_baja_con_acto_nuevo(db_conn, designaciones, service, repo, audit_store, acto, monkeypatch, romper):
    did, rec, fila = _baja(db_conn, designaciones, service, repo)
    fe, motivo = date(2026, 10, 20), "ZZNEXT baja"
    dep_id, dep_nom = _dependencia(db_conn)
    val = valores(dep=dep_nom, pdf=("ZZNEXT baja.pdf", "application/pdf", pdf_sintetico("baja")))
    titulo = f"Finalizar / baja de designación — {fila['nombre_completo']}"
    datos = {"id": did, "huella": fila["huella"], "tipo_cambio": "Finalizar / baja de designación",
             "fecha_baja": str(fe), "motivo_baja": motivo, "observaciones": "",
             "acto": {"modo": "nuevo", "payload": payload_next(val, {dep_nom: dep_id}, titulo)}}
    if romper:
        def roto(*a, **k):
            raise RuntimeError("fallo inyectado")
        monkeypatch.setattr(DE, "finalizar_designacion_anticipadamente", roto)
    r = comparar(db_conn, audit_store, lambda c: cert_baja(c, did, fe, motivo, val, romper=romper),
                 lambda: acto.modificar(rec, datos, archivo_next(val)))
    if romper:
        assert r["rc"] == {"error": "fallo inyectado"} and r["en"] is not None
        assert [o["op"] for o in r["ops"]] == ["guardar_documento_respaldo_v251", "_eliminar_acto_recien_creado_v267"]
    else:
        assert r["en"] is None and r["rn"]["mensaje"] == r["rc"]["mensaje"] and SUFIJO_BAJA in r["rn"]["mensaje"]
        assert [o["op"] for o in r["ops"]] == ["guardar_documento_respaldo_v251", "finalizar_designacion_anticipadamente",
                                               "registrar_movimiento", "vincular_acto_movimiento_v266"]


CASOS_MOD = [("Cambio de cargo", {"cargo": "Titular"}, "Cambio de cargo"),
             ("Cambio de condición Ad Honorem", {"ad_honorem": "Sí"}, "Pase a Ad Honorem")]


@pytest.mark.parametrize("tipo,datos_mod,tipo_mov", CASOS_MOD, ids=[c[0] for c in CASOS_MOD])
def test_modificacion_con_acto_nuevo(db_conn, designaciones, service, repo, audit_store, acto, tipo, datos_mod,
                                     tipo_mov):
    did = _designacion(db_conn, _cuil_con_asignaciones(db_conn, 2), estado="Activa")
    rec = _record(service, repo)
    fila = next(f for f in designaciones.periodo(rec, ABIERTO)["designaciones"] if f["id"] == did)
    d = {"observaciones": "ZZNEXT modificación", "texto_funcion_no_docente": fila["texto_funcion_no_docente"],
         **datos_mod}
    # "Otro" sin dependencia ni PDF, con detalle propio (el sugerido del movimiento no interviene)
    val = valores(tipo="Otro", numero="", detalle="ZZNEXT detalle de la modificación")
    titulo = f"{tipo} — {fila['nombre_completo']}"
    max_mov = DS.baseline(db_conn)
    r = comparar(db_conn, audit_store, lambda c: cert_mod(c, db_conn, did, tipo, d, val, tipo_mov, max_mov),
                 lambda: acto.modificar(rec, {"id": did, "huella": fila["huella"], "tipo_cambio": tipo, **d,
                                              "acto": {"modo": "nuevo", "payload": payload_next(val, {}, titulo)}}, None))
    assert r["en"] is None and r["rn"]["mensaje"] == r["rc"]["mensaje"] == "Designación actualizada correctamente." + SUFIJO_MOD
    assert [o["op"] for o in r["ops"]] == ["guardar_documento_respaldo_v251", "actualizar_designacion",
                                           "registrar_movimiento", "vincular_acto_movimiento_v266"]


def test_categoria_y_titulo_del_acto_por_operacion(db_conn, designaciones, service, repo, audit_store, acto):
    """Categoria certificada por operacion (``_categoria_respaldo_movimiento_v263``) y titulo / referencia guardados."""
    did = _designacion(db_conn, _cuil_con_asignaciones(db_conn, 2), estado="Activa")
    rec = _record(service, repo)
    fila = next(f for f in designaciones.periodo(rec, ABIERTO)["designaciones"] if f["id"] == did)
    val = valores(tipo="Otro", numero="", titulo="")
    with db_conn.transaction() as tx:
        acto.modificar(rec, {"id": did, "huella": fila["huella"], "tipo_cambio": "Cambio de condición Ad Honorem",
                             "ad_honorem": "Sí", "observaciones": "ZZNEXT",
                             "acto": {"modo": "nuevo", "payload": payload_next(val, {}, "")}}, None)
        cat, titulo, ref = db_conn.execute("SELECT categoria, titulo, referencia_texto FROM documentos_respaldo "
                                           "ORDER BY id DESC LIMIT 1").fetchone()
        raise psycopg.Rollback(tx)
    assert cat == "Cambio de condición Ad Honorem / Rentada"
    assert titulo == f"Pase a Ad Honorem — {fila['nombre_completo']}"  # titulo vacio -> sugerido por tipo de movimiento
    assert ref == f"Pase a Ad Honorem: {fila['nombre_completo']} — CUIL {fila['cuil']}"


# ------------------------------------------------------------------------------------------ formulario en linea (UI)
def test_contexto_del_formulario_igual_al_certificado(db_conn, service, repo, acto):
    """Textos, controles, opciones (dependencias activas con la etiqueta certificada) y defaults del formulario."""
    cert = _Cert(db_conn)
    with db_conn.transaction() as tx:
        cert.render({}, "Designación docente", ABIERTO, "Designación — X", "D")
        ev_res = cert.eventos
        cert.render({L_TIPO: "Otro"}, "Designación docente", ABIERTO, "T", "")
        ev_otro = cert.eventos
        raise psycopg.Rollback(tx)
    ctx = acto.contexto(_record(service, repo))
    assert ev_res[0] == ("markdown", "##### " + ctx["titulo"])
    assert ev_res[1] == ("caption", ctx["caption"].format(categoria="Designación docente"))
    assert ev_res[2] == ("selectbox", L_TIPO, ctx["tipos"], None)
    deps = next(e for e in ev_res if e[0] == "selectbox" and e[1] == "Dependencia emisora")
    assert deps[2] == [d["etiqueta"] for d in ctx["dependencias"]] and deps[3] == ctx["help_dependencia"]
    assert next(e for e in ev_otro if e[0] == "selectbox" and e[1].startswith("Dependencia"))[1] == \
        "Dependencia emisora (opcional)"
    assert ("text_input", L_NUM, "", "Ej.: 441/2026") in ev_res
    assert ("date_input", L_FECHA, FIXED_TODAY) in ev_res  # value=date.today()
    assert ("text_input", L_TIT, "Designación — X", "Descripción breve del acto") in ev_res
    assert ("text_area", L_DET, "D") in ev_res and ("text_area", L_OBS, "") in ev_res
    assert ("file_uploader", L_PDF, ["pdf"]) in ev_res
    assert not any(e[0] == "warning" for e in ev_res) and ctx["sin_dependencias"] == ""
    assert ctx["max_pdf_bytes"] == 50 * 1024 * 1024 and ctx["pdf_grande"] == "El PDF supera 50 MB."
    from designaciones import rules
    assert ctx["categoria_alta"] == "Designación docente"
    assert ctx["categorias"] == {t: _categoria(t) for t in rules.TIPOS_CAMBIO}  # categoria certificada por tipo de cambio


def test_contexto_sin_dependencias_activas_muestra_el_aviso(db_conn, service, repo, acto):
    cert = _Cert(db_conn)
    with db_conn.transaction() as tx:
        db_conn.execute("UPDATE dependencias_documentales SET estado='Inactiva' WHERE institucion_id=1")
        cert.render({}, "Designación docente", ABIERTO, "T", "")
        ctx = acto.contexto(_record(service, repo))
        raise psycopg.Rollback(tx)
    aviso = [e[1] for e in cert.eventos if e[0] == "warning"]
    assert aviso == [ctx["sin_dependencias"]] and [d["etiqueta"] for d in ctx["dependencias"]] == ["Seleccionar dependencia"]


# ------------------------------------------------------------------------------------------ permisos, ambito, hardening
def test_permisos_b10(db_conn, designaciones, service, repo, audit_store, acto):
    """Solo lectura: el primer writer es ``guardar_documento_respaldo_v251`` -> 403 ``documentos.write`` + DENIED, sin
    escrituras.  Coordinador sin departamento -> 409.  Superadmin con contexto -> crea el acto."""
    from designaciones.service import DesignacionesError
    cuil = _cuil_con_asignaciones(db_conn, 1)
    nombre, v = _nombre(db_conn, cuil), _valores()
    val = valores(tipo="Otro", numero="")
    max_mov = DS.baseline(db_conn)
    res_baseline(db_conn)
    antes = estado(db_conn, max_mov)
    sup = _record(service, repo, 1, dep=DEP)
    huella = designaciones.overview(sup)["abierto_huella"]
    datos = {**_payload_alta(cuil, v), "abierto_huella": huella,
             "acto": {"modo": "nuevo", "payload": payload_next(val, {}, f"Designación — {nombre}")}}
    with pytest.raises(DesignacionesError) as exc:
        acto.alta(_record(service, repo, 7), datos, None)
    assert exc.value.status == 403 and "documentos.write" in exc.value.message
    assert [(e.operation, e.outcome) for e in audit_store.events] == [("guardar_documento_respaldo_v251", "DENIED")]
    with pytest.raises(DesignacionesError) as exc:
        acto.alta(_record(service, repo, 2), datos, None)
    assert exc.value.status == 409
    assert estado(db_conn, max_mov) == antes
    with db_conn.transaction() as tx:
        r = acto.alta(sup, datos, None)
        raise psycopg.Rollback(tx)
    assert r["mensaje"].endswith(SUFIJO_ALTA)


def test_hardening_del_formulario(db_conn, designaciones, service, repo, audit_store, acto):
    """NEXT valida en el servidor: tipo fuera del selector, fecha / tipos invalidos, dependencia inexistente, inactiva o
    de otra institucion (el nombre sale del catalogo, nunca del cliente), firma %PDF- y "nuevo" por la ruta JSON."""
    from designaciones.service import DesignacionesError
    from resoluciones_respaldos.service import Archivo
    cuil = _cuil_con_asignaciones(db_conn, 1)
    nombre, v = _nombre(db_conn, cuil), _valores()
    rec = _record(service, repo)
    huella = designaciones.overview(rec)["abierto_huella"]
    dep_id, dep_nom = _dependencia(db_conn)
    ajena = db_conn.execute("SELECT id FROM dependencias_documentales WHERE institucion_id<>1 ORDER BY id LIMIT 1"
                            ).fetchone()
    base = payload_next(valores(dep=dep_nom), {dep_nom: dep_id}, "T")
    casos = [({**base, "tipo_documento": "Decreto"}, None, 422), ({**base, "fecha": "31/10/2026"}, None, 422),
             ({**base, "numero": 7}, None, 422), ({**base, "dependencia_id": "1"}, None, 422),
             ({**base, "dependencia_id": 999999}, None, 409),
             ({**base}, Archivo("x.pdf", "application/pdf", b"MZ no es pdf"), 422)]
    if ajena is not None:
        casos.append(({**base, "dependencia_id": int(ajena[0])}, None, 409))
    max_mov = DS.baseline(db_conn)
    res_baseline(db_conn)
    antes = estado(db_conn, max_mov)
    for payload, archivo, status in casos:
        with pytest.raises(DesignacionesError) as exc:
            acto.alta(rec, {**_payload_alta(cuil, v), "abierto_huella": huella,
                            "acto": {"modo": "nuevo", "payload": payload}}, archivo)
        assert exc.value.status == status, payload
    with db_conn.transaction() as tx:
        db_conn.execute("UPDATE dependencias_documentales SET estado='Inactiva' WHERE id=%s", [dep_id])
        with pytest.raises(DesignacionesError) as exc:
            acto.alta(rec, {**_payload_alta(cuil, v), "abierto_huella": huella,
                            "acto": {"modo": "nuevo", "payload": base}}, None)
        assert exc.value.status == 409
        raise psycopg.Rollback(tx)
    with pytest.raises(DesignacionesError) as exc:  # sin puerto (ruta JSON): rechazo controlado anterior a E4-07
        designaciones.alta(rec, {**_payload_alta(cuil, v), "abierto_huella": huella, "acto": {"modo": "nuevo"}})
    assert exc.value.code == "ACTO_NUEVO_PENDIENTE"
    assert estado(db_conn, max_mov) == antes and audit_store.events == []


# ------------------------------------------------------------------------------------------ HTTP
@pytest.fixture
def http(service, designaciones, resoluciones, acto):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from auth.routes import router as auth_router
    from designaciones.routes import router as designaciones_router
    from integraciones.routes import designaciones_router as integracion_router

    app = FastAPI()
    app.state.auth, app.state.designaciones = service, designaciones
    app.state.resoluciones_respaldos, app.state.acto_contextual = resoluciones, acto
    app.include_router(auth_router)
    app.include_router(designaciones_router)
    app.include_router(integracion_router)
    return TestClient(app, base_url="http://localhost")


def test_http_multipart_csrf_sesion_y_respuestas_limpias(http, service, repo, db_conn, designaciones):
    csrf = {"X-DEPTIT-Request": "1"}
    cuil = _cuil_con_asignaciones(db_conn, 1)
    nombre, v = _nombre(db_conn, cuil), _valores()
    dep_id, dep_nom = _dependencia(db_conn)
    rutas = ("/designaciones/acto-nuevo/alta", "/designaciones/acto-nuevo/modificar")
    for ruta in rutas + ("/designaciones/acto-nuevo/contexto",):
        assert http.post(ruta, headers=csrf).status_code == 401
    _, token = session_for(service, repo, 3)
    http.cookies.set("deptit_session", token)
    for ruta in rutas + ("/designaciones/acto-nuevo/contexto",):
        assert http.post(ruta).status_code == 403
        assert http.get(ruta).status_code == 405
    assert http.post(rutas[0], json={}, headers=csrf).status_code == 415  # solo multipart
    ctx = http.post("/designaciones/acto-nuevo/contexto", headers=csrf)
    assert ctx.status_code == 200 and any(d["id"] == dep_id for d in ctx.json()["dependencias"])
    huella = designaciones.overview(_record(service, repo))["abierto_huella"]
    datos = {**_payload_alta(cuil, v), "abierto_huella": huella, "departamento_id": 2, "institucion_id": 9,
             "acto": {"modo": "nuevo", "payload": payload_next(valores(dep=dep_nom), {dep_nom: dep_id}, "T")}}
    pdf = pdf_sintetico("http")
    with db_conn.transaction() as tx:
        r = http.post(rutas[0], headers=csrf, data={"datos": json.dumps(datos)},
                      files={"archivo": ("ZZNEXT http.pdf", pdf, "application/pdf")})
        assert r.status_code == 200 and r.json()["mensaje"].endswith(SUFIJO_ALTA), r.text
        fila = db_conn.execute("SELECT departamento_id, archivo_nombre, archivo_mime, length(archivo_pdf), "
                               "dependencia_nombre FROM documentos_respaldo ORDER BY id DESC LIMIT 1").fetchone()
        assert fila == (DEP, "ZZNEXT http.pdf", "application/pdf", len(pdf), dep_nom)  # ambito de la sesion
        raise psycopg.Rollback(tx)
    r = http.post(rutas[0], headers=csrf, files={"datos": (None, json.dumps({**datos, "acto": {  # FormData sin PDF
        "modo": "nuevo", "payload": {**datos["acto"]["payload"], "tipo_documento": "x"}}}))})
    assert r.status_code == 422 and not re.search(r"(?i)select\s|traceback|psycopg|insert\s|C:\\\\", r.text)


# ------------------------------------------------------------------------------------------ arquitectura
def test_arquitectura_owner_y_composicion():
    """Designaciones no importa Resoluciones ni la composicion; la composicion no ejecuta SQL propio ni duplica
    writers (usa ``resolver_acto_contextual_v267`` / ``eliminar_acto_recien_creado_v267`` de Resoluciones)."""
    for archivo in (BACKEND / "designaciones").glob("*.py"):
        arbol = ast.parse(archivo.read_text(encoding="utf-8"))
        mods = {getattr(n, "module", "") or "" for n in ast.walk(arbol) if isinstance(n, ast.ImportFrom)} | \
            {a.name for n in ast.walk(arbol) if isinstance(n, ast.Import) for a in n.names}
        assert not any(m.startswith(("resoluciones_respaldos", "integraciones")) for m in mods), archivo
    comp = (BACKEND / "integraciones" / "acto_contextual.py").read_text(encoding="utf-8")
    codigo = re.sub(r'"""[\s\S]*?"""', "", comp)
    assert not re.search(r"(?i)\b(insert|update|delete)\s+(into|from|\w+\s+set)|\.execute\(", codigo)
    assert "RE.resolver_acto_contextual_v267" in codigo and "RE.eliminar_acto_recien_creado_v267" in codigo
    import audit
    assert "_eliminar_acto_recien_creado_v267" in audit.WRITER_NAMES
