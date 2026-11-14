"""E4-06 — Docentes → Resumen docente: "Mensaje para consultar la designación" (estado de consulta + mensaje).

Diferencial contra B13-FIX02:
- WRITER: ``guardar_estado_consulta_designacion`` (l. 23858) LITERAL en el namespace certificado de Designaciones
  (conexiones certificadas: inyector de tenant, COMMITs registrados por ``_Frames``) vs
  ``ResumenDocenteService.guardar_estado`` -> ``DesignacionesService.guardar_estado_consulta`` (owner).  Desde el mismo
  estado (SAVEPOINT + ROLLBACK): filas de ``estado_consulta_designacion`` y estructura de COMMITs B12H.
- SECCION: la pestaña COMPLETA literal (l. 60845-61275) con un Streamlit que graba titulo, caption, radio, semaforo
  (``mostrar_estado_consulta_designacion``) y botones, para cada opcion del radio, vs el bloque ``consulta`` de NEXT.
- MENSAJE: ``generar_mensaje_consulta_designacion_docente`` (l. 24088) del namespace certificado (con el mismo
  ``current_user()`` que la sesion) vs ``ResumenDocenteService.mensaje``: asunto, cuerpo (texto completo) y advertencias.
Datos reales de deptit_next_dev y fixtures sinteticas; todo se revierte.
"""
from __future__ import annotations

import ast
import copy
import re
from pathlib import Path

import psycopg
import pytest

from designaciones_support import (  # noqa: F401  (fixtures)
    FIXED_NOW, FIXED_TODAY, audit_rows, audit_store, certified_designaciones, db_conn, designaciones, savepoint,
    session_for,
)
from e4_05_support import certificado, certified_resumen
from periodos_support import ENTRY, _tree
from test_e4_05_resumen import candidatos

from actividades_especiales.service import ActividadesService
from docentes.service import DocentesError, DocentesService
from integraciones import resumen_pagina as RP
from integraciones.resumen_docente import ResumenDocenteService
from sueldos.service import SueldosService

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning", "ignore::DeprecationWarning")

BACKEND = Path(__file__).resolve().parents[1]
INST, DEP, ABIERTO, CERRADO = 1, 1, 9, 5
ESTADOS = ["", "Designación confirmada", "Consulta Enviada", "Rever Designación"]


def make(service, audit_store, db_conn, designaciones):
    kw = dict(today=lambda: FIXED_TODAY, transaction=lambda: savepoint(db_conn))
    return ResumenDocenteService(
        None, service, DocentesService(None, service, None, **kw), SueldosService(None, service, audit_store, **kw),
        ActividadesService(None, service, audit_store, now=lambda: FIXED_NOW, **kw), designaciones=designaciones,
        now=lambda: FIXED_NOW, **kw)


def _record(service, repo, uid=3, dep=None):
    rec = session_for(service, repo, uid)[0]
    if dep is not None:
        service.set_context(rec, INST, dep, False)
    return rec


def filas_estado(conn, dep=DEP) -> list:
    return [tuple(r) for r in conn.execute(
        "SELECT institucion_id, departamento_id, periodo_id, cuil, estado, fecha_actualizacion "
        "FROM estado_consulta_designacion WHERE institucion_id=%s AND departamento_id=%s "
        "ORDER BY periodo_id, cuil, estado", [INST, dep]).fetchall()]


def _writer_certificado(ns):
    """``guardar_estado_consulta_designacion`` literal (l. 23858) como writer de negocio del harness (B10/B12H)."""
    nodo = next(n for n in _tree(ENTRY).body if isinstance(n, ast.FunctionDef)
                and n.name == "guardar_estado_consulta_designacion")
    lista = next(n for n in _tree(ENTRY).body if isinstance(n, ast.Assign) and len(n.targets) == 1
                 and getattr(n.targets[0], "id", "") == "ESTADOS_CONSULTA_DESIGNACION")
    ns["ESTADOS_CONSULTA_DESIGNACION"] = ast.literal_eval(lista.value)
    ns["asegurar_esquema_estado_consulta_designacion"] = lambda: None  # B12F: verificacion, sin DDL
    exec(compile(ast.Module(body=[copy.deepcopy(nodo)], type_ignores=[]), str(ENTRY), "exec"), ns)
    fn, frames = ns["guardar_estado_consulta_designacion"], ns["_frames"]

    def framed(*a, **k):
        frames.enter("business", "guardar_estado_consulta_designacion")
        try:
            return fn(*a, **k)
        finally:
            frames.stack.pop()
    return framed


def comparar_writer(db_conn, svc, record, cuil, periodo_id, estado, dep=DEP):
    ns = certified_designaciones(db_conn, INST, dep)
    writer = _writer_certificado(ns)
    with db_conn.transaction() as tx:
        writer(cuil, periodo_id, estado)
        st_c = filas_estado(db_conn, dep)
        ops_c = [o for o in ns["_frames"].ops if o["commits"]]
        raise psycopg.Rollback(tx)
    with db_conn.transaction() as tx:
        r = svc.guardar_estado(record, {"cuil": cuil, "periodo_id": periodo_id, "estado": estado})
        st_n = filas_estado(db_conn, dep)
        eventos = audit_rows(db_conn)
        raise psycopg.Rollback(tx)
    assert st_n == st_c
    ops_n, vistos = [], {}
    for e in eventos:
        cid = str(e["correlation_id"])
        if cid not in vistos:
            vistos[cid] = {"op": e["operation"], "commits": []}
            ops_n.append(vistos[cid])
        m = e["metadata"]
        vistos[cid]["commits"].append({k: m.get(k) for k in ("commit_seq", "mutating_statements", "committing_writer",
                                                            "nested_system_task")})
        assert (e["operation"], e["entity_type"], e["entity_id"], e["action"], e["action_scope"], e["outcome"],
                e["audit_mode"]) == ("guardar_estado_consulta_designacion", "designacion", cuil, "designaciones.write",
                                     "department", "SUCCESS", "IN_TRANSACTION")
    assert ops_n == ops_c and len(ops_n) == 1 and ops_n[0]["commits"][0]["commit_seq"] == 1
    assert r["mensaje"] == "Estado de la consulta guardado." and r["estado"] == estado
    return st_n


# ------------------------------------------------------------------------------------------ writer
@pytest.mark.parametrize("estado", ESTADOS)
def test_writer_cada_transicion_desde_estado_existente_y_ausente(service, repo, audit_store, db_conn, designaciones,
                                                                  estado):
    svc = make(service, audit_store, db_conn, designaciones)
    rec = _record(service, repo)
    con = db_conn.execute("SELECT cuil FROM estado_consulta_designacion WHERE departamento_id=1 AND periodo_id=9 "
                          "ORDER BY cuil LIMIT 1").fetchone()[0]
    sin = db_conn.execute("SELECT d.cuil FROM docentes d WHERE d.institucion_id=1 AND d.departamento_id=1 AND NOT EXISTS "
                          "(SELECT 1 FROM estado_consulta_designacion e WHERE e.cuil=d.cuil) ORDER BY d.cuil LIMIT 1"
                          ).fetchone()[0]
    antes = filas_estado(db_conn)
    for cuil in (con, sin):
        despues = comparar_writer(db_conn, svc, rec, cuil, ABIERTO, estado)
        mias = [f for f in despues if f[3] == cuil and f[2] == ABIERTO]
        assert mias == ([] if estado == "" else [(INST, DEP, ABIERTO, cuil, estado, str(FIXED_NOW))])
    assert filas_estado(db_conn) == antes  # todo revertido


def test_writer_mismo_valor_y_periodo_historico(service, repo, audit_store, db_conn, designaciones):
    """Mismo valor = DELETE + INSERT igual que el certificado.  El certificado no bloquea periodos cerrados: el
    estado se guarda para el periodo elegido en el selector (incluido 2026-1, Cerrado)."""
    svc = make(service, audit_store, db_conn, designaciones)
    rec = _record(service, repo)
    cuil, actual = db_conn.execute("SELECT cuil, estado FROM estado_consulta_designacion WHERE departamento_id=1 AND "
                                   "periodo_id=9 ORDER BY cuil LIMIT 1").fetchone()
    comparar_writer(db_conn, svc, rec, cuil, ABIERTO, actual)
    assert db_conn.execute("SELECT estado FROM periodos WHERE id=%s", [CERRADO]).fetchone()[0] == "Cerrado"
    comparar_writer(db_conn, svc, rec, cuil, CERRADO, "Rever Designación")


def test_writer_hardening_valores_y_ambito(service, repo, audit_store, db_conn, designaciones):
    """NEXT valida del lado servidor: el certificado con un estado fuera del selector solo borraba; aca 422 sin
    escribir.  Docente o periodo fuera del departamento: 404.  Tipos manipulados: 422."""
    svc = make(service, audit_store, db_conn, designaciones)
    rec = _record(service, repo)
    cuil = db_conn.execute("SELECT cuil FROM estado_consulta_designacion WHERE departamento_id=1 ORDER BY cuil LIMIT 1"
                           ).fetchone()[0]
    ajeno = db_conn.execute("SELECT d.cuil FROM docentes d WHERE d.departamento_id<>1 AND NOT EXISTS (SELECT 1 FROM "
                            "docentes x WHERE x.departamento_id=1 AND x.cuil=d.cuil) ORDER BY d.cuil LIMIT 1").fetchone()[0]
    periodo_ajeno = db_conn.execute("SELECT id FROM periodos WHERE departamento_id<>1 ORDER BY id LIMIT 1").fetchone()[0]
    antes = filas_estado(db_conn)
    casos = [({"cuil": cuil, "periodo_id": ABIERTO, "estado": "Aprobado"}, 422),
             ({"cuil": cuil, "periodo_id": ABIERTO, "estado": None}, 422),
             ({"cuil": cuil, "periodo_id": "9", "estado": ""}, 422),
             ({"cuil": cuil, "periodo_id": True, "estado": ""}, 422),
             ({"cuil": 20123, "periodo_id": ABIERTO, "estado": ""}, 422),
             ({"cuil": ajeno, "periodo_id": ABIERTO, "estado": "Consulta Enviada"}, 404),
             ({"cuil": cuil, "periodo_id": periodo_ajeno, "estado": "Consulta Enviada"}, 404),
             ({"cuil": cuil, "periodo_id": 999999, "estado": "Consulta Enviada"}, 404)]
    for data, status in casos:
        with pytest.raises(DocentesError) as exc:
            svc.guardar_estado(rec, data)
        assert exc.value.status == status, data
    assert filas_estado(db_conn) == antes and audit_rows(db_conn) == []


def test_writer_permisos_b10(service, repo, audit_store, db_conn, designaciones):
    """B10 certificado: ``designaciones.write`` (legacy_write_actions.py l. 71).  Solo lectura -> 403 + evento DENIED
    separado; coordinador sin departamento -> 409 (Docentes no aplica); superadmin con contexto y usuario de
    departamento -> SUCCESS."""
    svc = make(service, audit_store, db_conn, designaciones)
    cuil = db_conn.execute("SELECT cuil FROM estado_consulta_designacion WHERE departamento_id=1 ORDER BY cuil LIMIT 1"
                           ).fetchone()[0]
    data = {"cuil": cuil, "periodo_id": ABIERTO, "estado": "Consulta Enviada"}
    with pytest.raises(DocentesError) as exc:
        svc.guardar_estado(_record(service, repo, 7), data)
    assert exc.value.status == 403 and "designaciones.write" in exc.value.message
    denegado = audit_store.events[-1]
    assert (denegado.operation, denegado.outcome) == ("guardar_estado_consulta_designacion", "DENIED")
    with pytest.raises(DocentesError) as exc:
        svc.guardar_estado(_record(service, repo, 2), data)
    assert exc.value.status == 409
    comparar_writer(db_conn, svc, _record(service, repo, 1, dep=DEP), cuil, ABIERTO, "Consulta Enviada")
    comparar_writer(db_conn, svc, _record(service, repo), cuil, ABIERTO, "Consulta Enviada")


def test_writer_otro_departamento_no_ve_ni_toca_el_estado(service, repo, audit_store, db_conn, designaciones):
    """Usuario del dep 2: un CUIL del dep 1 no es suyo (404) y su propio writer no toca filas del dep 1."""
    svc = make(service, audit_store, db_conn, designaciones)
    rec2 = _record(service, repo, 6)
    cuil1 = db_conn.execute("SELECT cuil FROM estado_consulta_designacion WHERE departamento_id=1 ORDER BY cuil LIMIT 1"
                            ).fetchone()[0]
    propio = db_conn.execute("SELECT cuil FROM docentes WHERE institucion_id=1 AND departamento_id=2 ORDER BY cuil "
                             "LIMIT 1").fetchone()[0]
    pid2 = db_conn.execute("SELECT id FROM periodos WHERE departamento_id=2 AND estado='Abierto'").fetchone()[0]
    if cuil1 not in {r[0] for r in db_conn.execute("SELECT cuil FROM docentes WHERE departamento_id=2").fetchall()}:
        with pytest.raises(DocentesError) as exc:
            svc.guardar_estado(rec2, {"cuil": cuil1, "periodo_id": pid2, "estado": "Consulta Enviada"})
        assert exc.value.status == 404
    antes1 = filas_estado(db_conn, 1)
    comparar_writer(db_conn, svc, rec2, propio, pid2, "Designación confirmada", dep=2)
    assert filas_estado(db_conn, 1) == antes1


# ------------------------------------------------------------------------------------------ seccion (lectura)
def _stream_consulta(c: dict, etiqueta: str) -> list:
    opcion = next(o for o in c["opciones"] if o["etiqueta"] == etiqueta)
    tono = {"success": "success", "warning": "warning", "error": "error", "info": "info"}[opcion["semaforo"]["tono"]]
    return [("markdown", f"### {c['titulo']}"), ("caption", c["caption"]),
            ("radio", c["radio"], [o["etiqueta"] for o in c["opciones"]],
             [o["etiqueta"] for o in c["opciones"]].index(c["seleccion"])),
            (tono, opcion["semaforo"]["texto"]), ("button", c["boton_guardar"]), ("button", c["boton_mensaje"])]


def test_seccion_consulta_igual_al_certificado(service, repo, audit_store, db_conn, designaciones):
    """Estado existente y ausente, y cada opcion elegida en el radio (semaforo de ``mostrar_estado...``)."""
    svc = make(service, audit_store, db_conn, designaciones)
    rec = _record(service, repo)
    con, estado_con = db_conn.execute("SELECT cuil, estado FROM estado_consulta_designacion WHERE departamento_id=1 AND "
                                      "periodo_id=9 ORDER BY cuil LIMIT 1").fetchone()
    sin = db_conn.execute("SELECT d.cuil FROM docentes d WHERE d.institucion_id=1 AND d.departamento_id=1 AND NOT EXISTS "
                          "(SELECT 1 FROM estado_consulta_designacion e WHERE e.cuil=d.cuil) ORDER BY d.cuil LIMIT 1"
                          ).fetchone()[0]
    # el estado esperado sale de la base (los datos de dev cambian con la validación manual), no de un literal
    esperado = next(et for et, valor in RP.MAPA_CONSULTA.items() if valor == estado_con)
    ns = certified_resumen(db_conn, INST, DEP, completa=True)
    for cuil in (con, sin):
        r = svc.resumen(rec, cuil)
        c = r["consulta"]
        assert c["seleccion"] == (esperado if cuil == con else "⚪ Sin estado")
        for et in RP.OPCIONES_CONSULTA:
            ev = certificado(ns, cuil, None, completa=True, radio=et)
            i = ev.index(("markdown", f"### {c['titulo']}"))
            assert ev[i:] == _stream_consulta(c, et), et


# ------------------------------------------------------------------------------------------ mensaje
def _comparar_mensaje(db_conn, svc, rec, dep, cuil, pid, superadmin=False):
    usuario = {k: v for k, v in rec.user.items()}
    ns = certified_resumen(db_conn, INST, dep, usuario=usuario, completa=True)
    if superadmin:
        ns["st"].session_state["superadmin_institucion_id"] = INST
    cert = ns["generar_mensaje_consulta_designacion_docente"](cuil, pid)
    r = svc.mensaje(rec, cuil, pid)
    assert (r["asunto"], r["cuerpo"], r["advertencias"]) == (cert[0], cert[1], list(cert[2]))
    return r


def test_mensaje_igual_al_certificado_por_categoria_y_periodo(service, repo, audit_store, db_conn, designaciones):
    svc = make(service, audit_store, db_conn, designaciones)
    rec = _record(service, repo)
    cand = candidatos(db_conn, INST, DEP)
    assert {"comisiones", "investigacion", "extension", "sin_designaciones", "ad_honorem"} <= set(cand)
    vistos = set()
    for cat, cuil in cand.items():
        for pid in (ABIERTO, CERRADO):
            r = _comparar_mensaje(db_conn, svc, rec, DEP, cuil, pid)
            assert r["asunto"].startswith("Consulta y confirmación de designación - ")
            vistos |= {"sin_designacion" for _ in [0] if "No figura ninguna designación" in r["cuerpo"]}
            vistos |= {"varias" for _ in [0] if r["cuerpo"].count("\n- ") > 3}
            vistos |= {"ad_honorem" for _ in [0] if "; ad honorem" in r["cuerpo"]}
            vistos |= {"extension" for _ in [0] if "Participación en proyectos de extensión:" in r["cuerpo"]}
    assert {"sin_designacion", "varias", "extension"} <= vistos


def test_mensaje_superadmin_y_otro_departamento(service, repo, audit_store, db_conn, designaciones):
    svc = make(service, audit_store, db_conn, designaciones)
    for dep in (1, 2):
        rec = _record(service, repo, 1, dep=dep)
        cuil = next(iter(candidatos(db_conn, INST, dep).values()))
        pid = db_conn.execute("SELECT id FROM periodos WHERE departamento_id=%s AND estado='Abierto'", [dep]).fetchone()[0]
        _comparar_mensaje(db_conn, svc, rec, dep, cuil, pid, superadmin=True)


def test_mensaje_validacion(service, repo, audit_store, db_conn, designaciones):
    svc = make(service, audit_store, db_conn, designaciones)
    rec = _record(service, repo)
    cuil = db_conn.execute("SELECT cuil FROM docentes WHERE institucion_id=1 AND departamento_id=1 ORDER BY cuil LIMIT 1"
                           ).fetchone()[0]
    for c, p, status in ((cuil, None, 422), (cuil, "9", 422), ("", ABIERTO, 422), ("20-99999999-9", ABIERTO, 404),
                         (cuil, 999999, 404)):
        with pytest.raises(DocentesError) as exc:
            svc.mensaje(rec, c, p)
        assert exc.value.status == status


# ------------------------------------------------------------------------------------------ HTTP y seguridad
@pytest.fixture
def http(service, repo, audit_store, db_conn, designaciones):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from auth.routes import router as auth_router
    from integraciones.routes import docentes_router

    app = FastAPI()
    app.state.auth = service
    app.state.resumen_docente = make(service, audit_store, db_conn, designaciones)
    app.include_router(auth_router)
    app.include_router(docentes_router)
    return TestClient(app, base_url="http://localhost")


def test_http_csrf_sesion_y_respuestas_limpias(http, service, repo, db_conn):
    csrf = {"X-DEPTIT-Request": "1"}
    cuil = db_conn.execute("SELECT cuil FROM estado_consulta_designacion WHERE departamento_id=1 ORDER BY cuil LIMIT 1"
                           ).fetchone()[0]
    body = {"cuil": cuil, "periodo_id": ABIERTO, "estado": "Consulta Enviada"}
    for ruta in ("/docentes/resumen/estado-consulta", "/docentes/resumen/mensaje"):
        assert http.post(ruta, json=body, headers=csrf).status_code == 401
    _, token = session_for(service, repo, 3)
    http.cookies.set("deptit_session", token)
    for ruta in ("/docentes/resumen/estado-consulta", "/docentes/resumen/mensaje"):
        assert http.post(ruta, json=body).status_code == 403
        assert http.get(ruta).status_code == 405
    with db_conn.transaction() as tx:
        r = http.post("/docentes/resumen/estado-consulta", json={**body, "departamento_id": 2, "institucion_id": 9},
                      headers=csrf)
        assert r.status_code == 200 and r.json()["semaforo"]["texto"] == "🟡 Estado seleccionado: **Consulta Enviada**"
        raise psycopg.Rollback(tx)
    r = http.post("/docentes/resumen/estado-consulta", json={**body, "estado": "x"}, headers=csrf)
    assert r.status_code == 422 and not re.search(r"(?i)select\s|traceback|psycopg|delete|insert", r.text)
    r = http.post("/docentes/resumen/mensaje", json={"cuil": cuil, "periodo_id": ABIERTO}, headers=csrf)
    assert r.status_code == 200 and set(r.json()) == {"asunto", "cuerpo", "advertencias"}
    assert not re.search(r"(?i)select\s|traceback|psycopg", r.text)


def test_persistencia_guardar_y_nueva_lectura_independiente(http, service, repo, db_conn):
    """Regresión de la validación visual (2026-10-31): guardar -> fin del request -> NUEVA llamada a /docentes/resumen
    (otro request, otra transacción del servicio) -> ``consulta.seleccion`` = lo recién guardado; la fila persistida es
    única por (institución, departamento, período, CUIL).  No usa la respuesta del POST como fuente.  Todo revertido."""
    csrf = {"X-DEPTIT-Request": "1"}
    cuil = db_conn.execute("SELECT d.cuil FROM docentes d WHERE d.institucion_id=1 AND d.departamento_id=1 AND NOT EXISTS "
                           "(SELECT 1 FROM estado_consulta_designacion e WHERE e.cuil=d.cuil) ORDER BY d.cuil LIMIT 1"
                           ).fetchone()[0]
    _, token = session_for(service, repo, 3)
    http.cookies.set("deptit_session", token)
    etiqueta = {"": "⚪ Sin estado", "Designación confirmada": "🟢 Designación confirmada",
                "Consulta Enviada": "🟡 Consulta Enviada", "Rever Designación": "🔴 Rever Designación"}

    def leer() -> str:
        r = http.post("/docentes/resumen", json={"cuil": cuil, "periodo_id": ABIERTO}, headers=csrf)
        assert r.status_code == 200 and r.json()["seleccionado"]["id"] == ABIERTO
        return r.json()["consulta"]["seleccion"]

    with db_conn.transaction() as tx:
        assert leer() == "⚪ Sin estado"  # estado inicial conocido: sin fila
        for estado in ("Designación confirmada", "Consulta Enviada", "Rever Designación", ""):
            r = http.post("/docentes/resumen/estado-consulta", json={"cuil": cuil, "periodo_id": ABIERTO, "estado": estado},
                          headers=csrf)
            assert r.status_code == 200
            filas = db_conn.execute("SELECT institucion_id, departamento_id, periodo_id, estado FROM "
                                    "estado_consulta_designacion WHERE cuil=%s", [cuil]).fetchall()
            assert filas == ([] if estado == "" else [(INST, DEP, ABIERTO, estado)])
            assert leer() == etiqueta[estado]
        raise psycopg.Rollback(tx)
    assert db_conn.execute("SELECT count(*) FROM estado_consulta_designacion WHERE cuil=%s", [cuil]).fetchone()[0] == 0
    # misma secuencia con el writer y el reader CERTIFICADOS (inyector de tenant): fila y lectura posterior iguales
    # El certificado cachea get_estado_consulta_designacion (_LECTURAS_CACHE_V199, l. 44625) con la version del
    # departamento como clave; la escritura llama invalidar_cache_rendimiento_v191 (l. 44542), sube la version y la
    # lectura siguiente va a la base.  La memo del harness no modela versiones: namespace nuevo por lectura = esa invalidacion.
    writer = _writer_certificado(certified_designaciones(db_conn, INST, DEP))

    def reader(c, p):
        return certified_resumen(db_conn, INST, DEP, completa=True)["get_estado_consulta_designacion"](c, p)
    with db_conn.transaction() as tx:
        assert reader(cuil, ABIERTO)["estado"] == ""
        for estado in ("Designación confirmada", "Consulta Enviada", "Rever Designación", ""):
            writer(cuil, ABIERTO, estado)
            filas = db_conn.execute("SELECT institucion_id, departamento_id, periodo_id, estado FROM "
                                    "estado_consulta_designacion WHERE cuil=%s", [cuil]).fetchall()
            assert filas == ([] if estado == "" else [(INST, DEP, ABIERTO, estado)])
            assert reader(cuil, ABIERTO)["estado"] == estado
        raise psycopg.Rollback(tx)


# ------------------------------------------------------------------------------------------ arquitectura
def test_writer_en_el_owner_y_complemento_literal():
    """El writer vive en Designaciones (owner B10) y la composicion solo lo invoca; el complemento del mensaje es texto
    literal del entry, sin writers; Designaciones no importa la composicion."""
    comp = re.sub(r'"""[\s\S]*?"""', "", (BACKEND / "integraciones" / "resumen_docente.py").read_text(encoding="utf-8"))
    assert not re.search(r"(?i)\b(INSERT|DELETE|UPDATE)\b|estado_consulta_designacion\s", comp)
    assert "self.designaciones.guardar_estado_consulta(" in comp
    from integraciones.resumen_motor import metadata_mensaje
    assert metadata_mensaje.WRITERS_NEGOCIO == [] and metadata_mensaje.TAREAS_SISTEMA == {}
    texto = (BACKEND / "integraciones" / "resumen_motor" / "complemento_mensaje.py").read_text(encoding="utf-8")
    assert "def guardar_estado_consulta_designacion" not in texto
    entry = ENTRY.read_text(encoding="utf-8").splitlines()
    bloques = re.findall(r"# --- entry l\. (\d+)-(\d+)\n(.*?)(?=\n\n# --- entry|\Z)", texto, re.S)
    assert len(bloques) == 9
    for a, b, cuerpo in bloques:
        original = "\n".join(entry[int(a) - 1:int(b)]).strip()
        assert re.sub(r"\b(analisis\.motor\.ref|integraciones\.resumen_motor\.ref)\b", "deptit_refactor",
                      cuerpo.strip()) == original
    for paquete in ("designaciones", "docentes", "disposiciones"):
        src = "\n".join(p.read_text(encoding="utf-8") for p in (BACKEND / paquete).glob("*.py"))
        assert not re.search(r"^\s*(from|import)\s+integraciones\b", src, re.M)
