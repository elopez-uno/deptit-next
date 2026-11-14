"""E4-08 — Docentes → registrar una designacion desde la pestaña "➕ Registrar docente".

Diferencial contra B13-FIX02, desde el mismo estado (SAVEPOINT + ROLLBACK):
- lado certificado: la secuencia de la pagina (entry l. 60086-60122, 60309-60356, 60365-60392) con las lecturas y
  writers certificados de Docentes (``certified_docentes``: ``get_docentes_mismo_cuil_otro_departamento``,
  ``_guardar_docente_local_desde_registro_existente``) y de Designaciones (``certified_designaciones``:
  ``existe_designacion_duplicada``, ``guardar_designacion``, ``registrar_movimiento``), y el lector
  ``get_docentes_base_maestra_sin_designacion_periodo`` (l. 4792) ejecutado literal;
- lado NEXT: ``RegistroDesignacionService`` (composicion) -> contratos de ``DocentesService`` y
  ``DesignacionesService``.
Se comparan: designaciones del departamento, movimientos nuevos, asignaciones, fichas de docentes del CUIL, la
secuencia de operaciones B12H con sus COMMITs y el mensaje visible.
"""
from __future__ import annotations

import ast
import json
import pprint
from datetime import date
from pathlib import Path

import psycopg
import pytest

import designaciones_support as DS
import docentes_support as DOS
from designaciones_support import (  # noqa: F401  (fixtures)
    FIXED_TODAY, audit_rows, audit_store, certified_designaciones, db_conn, designaciones, session_for,
)
from periodos_support import ENTRY, _tree

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")

INST, DEP, DEP2, ABIERTO = 1, 1, 2, 9
BACKEND = Path(__file__).resolve().parents[1]
C1, C2, C3, C4 = "20-99118001-3", "27-99118002-6", "20-99118003-1", "23-99118004-7"


# ------------------------------------------------------------------------------------------ fixtures
@pytest.fixture
def docentes(service, audit_store, db_conn, designaciones):  # ``designaciones`` ya extendio el FakeRepo
    return DOS.make_docentes(service, audit_store, db_conn)


@pytest.fixture
def registro(docentes, designaciones):
    from integraciones.registro_designacion import RegistroDesignacionService
    return RegistroDesignacionService(docentes, designaciones)


def _record(service, repo, uid=3, dep=None):
    rec = session_for(service, repo, uid)[0]
    if dep is not None:
        service.set_context(rec, INST, dep, False)
    return rec


def seed_docente(conn, cuil, apellido, nombres, *, dep=DEP, tipo="Propio", estado="Activo"):
    DOS.free_cuil(conn, cuil)
    conn.execute("INSERT INTO docentes (institucion_id, departamento_id, cuil, nombre, apellido, nombres, legajo, titulo,"
                 " email, telefono, ref_legajo_fisico, estado, tipo_docente, fecha_alta, observaciones, titulo_posgrado,"
                 " antiguedad_anios, nivel_posgrado_salarial) VALUES (%s,%s,%s,%s,%s,%s,'L-8','Lic. ZZNEXT',"
                 "'zz@test.local','011','R-8',%s,%s,'2025-03-01','ZZNEXT seed','Mg.',7,'Magíster')",
                 [INST, dep, cuil, f"{apellido}, {nombres}", apellido, nombres, estado, tipo])


def seed_designacion(conn, cuil, v, periodo=ABIERTO):
    conn.execute("INSERT INTO designaciones (institucion_id, departamento_id, cuil, cargo, dedicacion, horas,"
                 " tipo_designacion, ad_honorem, fecha_desde, fecha_hasta, estado, periodo_id, observaciones,"
                 " numero_resolucion, funcion_no_docente, texto_funcion_no_docente) VALUES (1,1,%s,%s,%s,%s,%s,%s,%s,"
                 "%s,%s,%s,'','',0,'')", [cuil, v["cargo"], v["dedicacion"], v["horas"], v["tipo"], v["adh"],
                                         str(v["desde"]), str(v["hasta"]), v["estado"], periodo])


def _valores(**kw):
    from designaciones import rules
    v = {"cargo": "JTP", "dedicacion": "Parcial", "tipo": "Interino", "adh": "No", "desde": date(2026, 8, 1),
         "hasta": date(2026, 12, 31), "estado": "Activa", "obs": "ZZNEXT E4-08", "funcion": False, "texto": ""}
    v.update(kw)
    v["horas"] = rules.horas_segun_dedicacion(v["dedicacion"])
    return v


def _payload(v, huella_abierto, **extra):
    return {"cargo": v["cargo"], "dedicacion": v["dedicacion"], "tipo_designacion": v["tipo"],
            "ad_honorem": v["adh"], "fecha_desde": str(v["desde"]), "fecha_hasta": str(v["hasta"]),
            "estado": v["estado"], "funcion_no_docente": v["funcion"], "texto_funcion_no_docente": v["texto"],
            "observaciones": v["obs"], "abierto_huella": huella_abierto, **extra}


def _dep_nombre(conn, dep):
    return conn.execute("SELECT nombre FROM departamentos WHERE id=%s", [dep]).fetchone()[0]


# ------------------------------------------------------------------------------------------ lado certificado
class _Cert:
    """Namespaces certificados de Docentes y Designaciones sobre la misma conexion; operaciones B12H en orden."""

    def __init__(self, db_conn, dep=DEP):
        self.nsd = certified_designaciones(db_conn, INST, dep)
        self.nso = DOS.certified_docentes(db_conn, INST, dep)
        self.ops: list = []
        # get_docentes_base_maestra_sin_designacion_periodo (l. 4792) literal, sobre get_docentes de Docentes y
        # get_designaciones efectiva de Designaciones.
        nodo = next(n for n in _tree(ENTRY).body if isinstance(n, ast.FunctionDef)
                    and n.name == "get_docentes_base_maestra_sin_designacion_periodo")
        ns = {"pd": DS.pd, "get_docentes": self.nso["get_docentes"], "get_designaciones": self.nsd["get_designaciones"]}
        exec(compile(ast.Module(body=[nodo], type_ignores=[]), str(ENTRY), "exec"), ns)
        self.reincorporables = ns["get_docentes_base_maestra_sin_designacion_periodo"]

    def des(self, name, *a, **k):
        frames = self.nsd["_frames"]
        n = len(frames.ops)
        try:
            return self.nsd[name](*a, **k)
        finally:
            self.ops += [o for o in frames.ops[n:] if o["commits"]]

    def doc(self, name, *a, **k):
        commits = self.nso["_commits"]
        n = len(commits)
        try:
            return self.nso[name](*a, **k)
        finally:
            nuevos = commits[n:]
            if nuevos:
                self.ops.append({"op": "guardar_docente", "commits": [
                    {"commit_seq": i, "mutating_statements": c["mutating_statements"],
                     "committing_writer": c["committing_writer"], "nested_system_task": None}
                    for i, c in enumerate(nuevos, start=1)]})


def cert_reincorporar(cert, cuil_sel, v):
    """entry l. 60060-60122."""
    nsd = cert.nsd
    per = nsd["get_periodo_abierto"]()
    if not per:
        return {"error": "No hay un período abierto. Abrí o creá el período actual antes de reincorporar docentes."}
    df = cert.reincorporables(per["id"])
    fila = df[df["cuil"] == cuil_sel]
    if fila.empty:
        return {"error": "no figura"}
    fila = fila.iloc[0]
    cuil, nombre = str(fila.get("cuil") or "").strip(), str(fila.get("nombre_completo") or "").strip()
    dup = nsd["existe_designacion_duplicada"](per["id"], cuil, v["cargo"], v["dedicacion"], v["horas"], v["tipo"],
                                               v["adh"], v["desde"], v["hasta"], v["estado"],
                                               funcion_no_docente=v["funcion"])
    if not cuil:
        return {"error": "El docente seleccionado no tiene un CUIL válido."}
    if dup:
        return {"error": "La designación exactamente igual ya existe en el período actual."}
    if v["hasta"] < v["desde"]:
        return {"error": "La fecha hasta no puede ser anterior a la fecha desde."}
    if v["funcion"] and not nsd["_texto_funcion_no_docente_limpio_v164"](v["texto"]):
        return {"error": "Completá las funciones no docentes antes de guardar la designación."}
    cert.des("guardar_designacion", per["id"], cuil, v["cargo"], v["dedicacion"], v["horas"], v["tipo"], v["adh"],
             v["desde"], v["hasta"], v["estado"], v["obs"], funcion_no_docente=v["funcion"],
             texto_funcion_no_docente=v["texto"])
    cert.des("registrar_movimiento", "Alta de designación", cuil, nombre,
             f"Reincorporación desde la base maestra al período {per['nombre']} - {v['cargo']} - {v['dedicacion']} - "
             f"{v['horas']} hs - {v['tipo']}"
             + (f" - Funciones no docentes: {nsd['_texto_funcion_no_docente_limpio_v164'](v['texto'])}"
                if v["funcion"] else ""),
             v["obs"], per["id"], horas_variacion=(0 if v["funcion"] else v["horas"]))
    return {"mensaje": "Docente reincorporado y designación registrada correctamente."}


def _form_cert(v):
    """``formulario_designacion_registro_docente`` (l. 23894): textos ya sin espacios extremos."""
    return {"cargo": v["cargo"], "dedicacion": v["dedicacion"], "horas": v["horas"], "tipo_designacion": v["tipo"],
            "ad_honorem": v["adh"], "fecha_desde": v["desde"], "fecha_hasta": v["hasta"], "estado": v["estado"],
            "observaciones": v["obs"], "funcion_no_docente": bool(v["funcion"]),
            "texto_funcion_no_docente": str(v["texto"] or "").strip()}


def cert_cuil_existente(cert, cuil_alta, dep_origen, v):
    """entry l. 60234-60356 (camino "Registrar como propio y cargar una designación en el período actual")."""
    nso, nsd = cert.nso, cert.nsd
    per = nsd["get_periodo_abierto"]()
    cuil_limpio = nso["limpiar_cuil"](cuil_alta)
    otros = nso["get_docentes_mismo_cuil_otro_departamento"](cuil_limpio)
    df_local = nso["docente_existe"](cuil_limpio) if cuil_limpio else DS.pd.DataFrame()
    fila = otros[otros["departamento_origen"] == dep_origen].iloc[0].to_dict()
    canonico = str((df_local.iloc[0].get("cuil") if not df_local.empty else fila.get("cuil")) or cuil_limpio).strip()
    datos = _form_cert(v) if per else None
    if datos is None:
        return {"error": "No hay un período abierto para la designación."}
    if datos["fecha_hasta"] < datos["fecha_desde"]:
        return {"error": "La fecha hasta no puede ser anterior a la fecha desde."}
    if datos["funcion_no_docente"] and not nsd["_texto_funcion_no_docente_limpio_v164"](datos["texto_funcion_no_docente"]):
        return {"error": "Completá las funciones no docentes antes de guardar la designación."}
    if df_local.empty:
        origen = str(fila.get("departamento_origen") or "otro departamento")
        cert.doc("_guardar_docente_local_desde_registro_existente", fila, "Propio",
                 f"Docente compartido: mismo CUIL registrado en {origen}.")
    cert.des("guardar_designacion", per["id"], canonico, datos["cargo"], datos["dedicacion"], datos["horas"],
             datos["tipo_designacion"], datos["ad_honorem"], datos["fecha_desde"], datos["fecha_hasta"],
             datos["estado"], datos["observaciones"], funcion_no_docente=datos["funcion_no_docente"],
             texto_funcion_no_docente=datos["texto_funcion_no_docente"])
    cert.des("registrar_movimiento", "Alta de designación", canonico, str(fila.get("nombre_completo") or ""),
             f"Se incorporó como docente propio/compartido con cargo {datos['cargo']}.", datos["observaciones"],
             per["id"], horas_variacion=(0 if datos["funcion_no_docente"] else datos["horas"]))
    return {"mensaje": "Docente propio/compartido y designación registrados correctamente."}


def cert_cuil_local(cert, cuil_alta, v):
    """entry l. 60358-60392 (CUIL ya registrado en el departamento actual): solo ``guardar_designacion``."""
    nso, nsd = cert.nso, cert.nsd
    per = nsd["get_periodo_abierto"]()
    cuil_limpio = nso["limpiar_cuil"](cuil_alta)
    assert nso["get_docentes_mismo_cuil_otro_departamento"](cuil_limpio).empty
    fila_local = nso["docente_existe"](cuil_limpio).iloc[0].to_dict()
    canonico = str(fila_local.get("cuil") or cuil_limpio).strip()
    datos = _form_cert(v) if per else None
    if datos is None:
        return {"error": "No hay un período abierto."}
    if datos["fecha_hasta"] < datos["fecha_desde"]:
        return {"error": "La fecha hasta no puede ser anterior a la fecha desde."}
    if datos["funcion_no_docente"] and not nsd["_texto_funcion_no_docente_limpio_v164"](datos["texto_funcion_no_docente"]):
        return {"error": "Completá las funciones no docentes antes de guardar la designación."}
    cert.des("guardar_designacion", per["id"], canonico, datos["cargo"], datos["dedicacion"], datos["horas"],
             datos["tipo_designacion"], datos["ad_honorem"], datos["fecha_desde"], datos["fecha_hasta"],
             datos["estado"], datos["observaciones"], funcion_no_docente=datos["funcion_no_docente"],
             texto_funcion_no_docente=datos["texto_funcion_no_docente"])
    return {"mensaje": "Designación registrada correctamente."}


# ------------------------------------------------------------------------------------------ comparacion
def estado(conn, max_mov, cuiles, dep=DEP) -> dict:
    out = DS.state(conn, INST, dep, max_mov)
    docs = DOS.state(conn, [c.replace("-", "") for c in cuiles], exclude=("id", "fecha_registro"))
    out["docentes"] = docs["docentes"]
    out["prestamos_docentes"] = docs["prestamos_docentes"]
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


def _correr(fn):
    try:
        return fn(), None
    except psycopg.Error:
        raise
    except Exception as exc:
        return None, exc


def comparar(db_conn, audit_store, cuiles, certificado, siguiente, dep=DEP):
    max_mov = DS.baseline(db_conn)
    cert = _Cert(db_conn, dep)
    with db_conn.transaction() as tx:
        rc, ec = _correr(lambda: certificado(cert))
        st_c = estado(db_conn, max_mov, cuiles, dep)
        raise psycopg.Rollback(tx)
    with db_conn.transaction() as tx:
        n = len(audit_store.events)
        rn, en = _correr(siguiente)
        st_n = estado(db_conn, max_mov, cuiles, dep)
        eventos = audit_rows(db_conn)
        nuevos = audit_store.events[n:]
        raise psycopg.Rollback(tx)
    assert ec is None, ec
    for clave in st_c:
        assert st_c[clave] == st_n[clave], f"{clave}:\ncert {pprint.pformat(st_c[clave])[:2000]}\n" \
                                           f"NEXT {pprint.pformat(st_n[clave])[:2000]}"
    ops_n = _ops(eventos)
    assert cert.ops == ops_n, f"cert:\n{pprint.pformat(cert.ops)}\nNEXT:\n{pprint.pformat(ops_n)}"
    if "error" in rc:
        assert rn is None and en is not None and en.message == rc["error"], (rc, rn, en)
    else:
        assert en is None, getattr(en, "message", en)
        assert rn["mensaje"] == rc["mensaje"]
    return {"rc": rc, "rn": rn, "en": en, "nuevos": nuevos, "ops": ops_n, "cert": cert, "estado": st_n}


def _contexto(registro, rec):
    return registro.contexto(rec)


def _huella_docente(ctx, cuil):
    return next(d["huella"] for d in ctx["reincorporables"] if d["cuil"] == cuil)


# ------------------------------------------------------------------------------------------ camino 1: reincorporar
@pytest.mark.parametrize("caso", ["docencia", "no_docente", "ad_honorem_concursado"])
def test_reincorporar_equivalente(db_conn, registro, service, repo, audit_store, caso):
    seed_docente(db_conn, C1, "Zeta", "Ana")
    v = {"docencia": _valores(), "ad_honorem_concursado": _valores(adh="Sí", tipo="Concursado", dedicacion="Exclusiva",
                                                                    cargo="Titular"),
         "no_docente": _valores(funcion=True, texto="  de coordinación administrativa del Departamento. ")}[caso]
    rec = _record(service, repo)
    ctx = _contexto(registro, rec)
    assert C1 in [d["cuil"] for d in ctx["reincorporables"]]
    r = comparar(db_conn, audit_store, [C1], lambda c: cert_reincorporar(c, C1, v),
                 lambda: registro.registrar(rec, _payload(v, ctx["abierto_huella"], camino="reincorporar", cuil=C1,
                                                          huella=_huella_docente(ctx, C1))))
    assert [o["op"] for o in r["ops"]] == ["guardar_designacion", "registrar_movimiento"]
    mov = [json.loads(x) for x in r["estado"]["movimientos"]]
    assert len(mov) == 1 and mov[0]["detalle"].startswith("Reincorporación desde la base maestra al período 2026-2 - ")
    if caso == "no_docente":
        assert mov[0]["detalle"].endswith(" - Funciones no docentes: de coordinación administrativa del Departamento.")
        assert float(mov[0]["horas_variacion"]) == 0


def test_lista_reincorporables_equivalente(db_conn, registro, service, repo):
    """``get_docentes_base_maestra_sin_designacion_periodo``: propios sin designacion en el periodo abierto (filtro,
    orden y prestados excluidos) en el departamento real y con fixtures."""
    seed_docente(db_conn, C1, "Zeta", "Ana")
    seed_docente(db_conn, C2, "Alfa", "Beto", tipo="Prestado")
    seed_docente(db_conn, C3, "Zeta", "Aaron", estado="Renunciado")
    cert = _Cert(db_conn)
    esperado = [str(c) for c in cert.reincorporables(ABIERTO)["cuil"]]
    got = [d["cuil"] for d in _contexto(registro, _record(service, repo))["reincorporables"]]
    assert got == esperado and C1 in got and C3 in got and C2 not in got
    assert len(got) > 3


def test_reincorporar_errores_de_pantalla(db_conn, registro, service, repo, audit_store):
    """Fecha hasta < desde y funciones no docentes sin texto: mensajes certificados, sin escrituras ni eventos."""
    seed_docente(db_conn, C1, "Zeta", "Ana")
    rec = _record(service, repo)
    ctx = _contexto(registro, rec)
    for v in (_valores(desde=date(2026, 12, 1), hasta=date(2026, 9, 1)), _valores(funcion=True, texto="   ")):
        r = comparar(db_conn, audit_store, [C1], lambda c: cert_reincorporar(c, C1, v),
                     lambda: registro.registrar(rec, _payload(v, ctx["abierto_huella"], camino="reincorporar", cuil=C1,
                                                              huella=_huella_docente(ctx, C1))))
        assert r["ops"] == [] and r["nuevos"] == []


def test_reincorporar_concurrente_y_stale(db_conn, registro, service, repo, audit_store):
    """Si mientras se completaba el formulario el docente recibio una designacion, ya no es reincorporable: 404 sin
    escrituras.  Si cambio su ficha (huella) o el periodo abierto: STALE B12I (FAILED de ``guardar_designacion``)."""
    from docentes.service import DocentesError
    seed_docente(db_conn, C1, "Zeta", "Ana")
    rec = _record(service, repo)
    ctx = _contexto(registro, rec)
    v = _valores()
    datos = _payload(v, ctx["abierto_huella"], camino="reincorporar", cuil=C1, huella=_huella_docente(ctx, C1))
    max_mov = DS.baseline(db_conn)
    antes = estado(db_conn, max_mov, [C1])
    with db_conn.transaction() as tx:
        seed_designacion(db_conn, C1, v)
        assert registro.duplicado(rec, {**datos, "cuil": C1}) == {"duplicada": True}
        with pytest.raises(DocentesError) as exc:
            registro.registrar(rec, datos)
        assert exc.value.status == 404
        raise psycopg.Rollback(tx)
    for cambio in ("UPDATE docentes SET legajo='ZZ-cambio' WHERE cuil=%s", "UPDATE periodos SET nombre=nombre||'*' "
                                                                           "WHERE id=9 AND %s::text IS NOT NULL"):
        n = len(audit_store.events)
        with db_conn.transaction() as tx:  # el cambio ocurre entre la pantalla y el clic
            db_conn.execute(cambio, [C1])
            with pytest.raises(DocentesError) as exc:
                registro.registrar(rec, datos)
            raise psycopg.Rollback(tx)
        assert exc.value.status == 409 and exc.value.code == "STALE"
        assert [(e.operation, e.outcome, e.error_code) for e in audit_store.events[n:]] == [
            ("guardar_designacion", "FAILED", "StaleDecisionError")]
    assert estado(db_conn, max_mov, [C1]) == antes


def test_reincorporar_stale_por_huella(db_conn, registro, service, repo, audit_store):
    from docentes.service import DocentesError
    seed_docente(db_conn, C1, "Zeta", "Ana")
    rec = _record(service, repo)
    ctx = _contexto(registro, rec)
    datos = _payload(_valores(), ctx["abierto_huella"], camino="reincorporar", cuil=C1, huella="vieja")
    with pytest.raises(DocentesError) as exc:
        registro.registrar(rec, datos)
    assert exc.value.code == "STALE"
    assert [(e.operation, e.outcome) for e in audit_store.events] == [("guardar_designacion", "FAILED")]
    datos = _payload(_valores(), "vieja", camino="reincorporar", cuil=C1, huella=_huella_docente(ctx, C1))
    with pytest.raises(DocentesError) as exc:
        registro.registrar(rec, datos)
    assert exc.value.code == "STALE" and "get_periodo_abierto" in exc.value.message


# ------------------------------------------------------------------------------------------ camino 2: CUIL de otro dpto
@pytest.mark.parametrize("caso", ["sin_local", "con_local_prestado", "no_docente"])
def test_cuil_existente_equivalente(db_conn, registro, service, repo, audit_store, caso):
    seed_docente(db_conn, C2, "Otra", "Dora", dep=DEP2)
    if caso == "con_local_prestado":
        db_conn.execute("INSERT INTO docentes (institucion_id, departamento_id, cuil, nombre, apellido, nombres, estado,"
                        " tipo_docente, fecha_alta, observaciones) VALUES (1,1,%s,'Otra, Dora','Otra','Dora','Activo',"
                        "'Prestado','2026-08-01','prestado')", [C2])
    origen = _dep_nombre(db_conn, DEP2)
    v = _valores(funcion=True, texto="de tutoría ") if caso == "no_docente" else _valores(cargo="Adjunto")
    rec = _record(service, repo)
    ctx = _contexto(registro, rec)
    r = comparar(db_conn, audit_store, [C2], lambda c: cert_cuil_existente(c, C2, origen, v),
                 lambda: registro.registrar(rec, _payload(v, ctx["abierto_huella"], camino="cuil_existente", cuil=C2,
                                                          departamento_origen=origen, cuil_alta=C2)))
    esperado = ["guardar_designacion", "registrar_movimiento"]
    if caso != "con_local_prestado":
        esperado = ["guardar_docente"] + esperado
        assert any("Docente compartido: mismo CUIL registrado en" in d for d in r["estado"]["docentes"])
    assert [o["op"] for o in r["ops"]] == esperado


def test_cuil_existente_errores(db_conn, registro, service, repo, audit_store):
    """Errores de pantalla ANTES del alta local del docente: no se crea la ficha ni la designacion."""
    seed_docente(db_conn, C2, "Otra", "Dora", dep=DEP2)
    origen = _dep_nombre(db_conn, DEP2)
    rec = _record(service, repo)
    ctx = _contexto(registro, rec)
    for v in (_valores(desde=date(2026, 12, 1), hasta=date(2026, 9, 1)), _valores(funcion=True, texto="")):
        r = comparar(db_conn, audit_store, [C2], lambda c: cert_cuil_existente(c, C2, origen, v),
                     lambda: registro.registrar(rec, _payload(v, ctx["abierto_huella"], camino="cuil_existente",
                                                              cuil=C2, departamento_origen=origen, cuil_alta=C2)))
        assert r["ops"] == [] and r["nuevos"] == []
    from docentes.service import DocentesError
    with pytest.raises(DocentesError) as exc:  # seleccion que no esta entre las coincidencias
        registro.registrar(rec, _payload(_valores(), ctx["abierto_huella"], camino="cuil_existente", cuil=C2,
                                         departamento_origen="Otro", cuil_alta=C2))
    assert exc.value.status == 409 and audit_store.events == []


def test_cuil_existente_stale_en_el_primer_writer(db_conn, registro, service, repo, audit_store):
    """B12I en el PRIMER writer del clic (``guardar_docente``): periodo abierto cambiado -> nada se escribe."""
    from docentes.service import DocentesError
    seed_docente(db_conn, C2, "Otra", "Dora", dep=DEP2)
    origen = _dep_nombre(db_conn, DEP2)
    rec = _record(service, repo)
    with pytest.raises(DocentesError) as exc:
        registro.registrar(rec, _payload(_valores(), "vieja", camino="cuil_existente", cuil=C2,
                                         departamento_origen=origen, cuil_alta=C2))
    assert exc.value.code == "STALE"
    assert [(e.operation, e.outcome, e.error_code) for e in audit_store.events] == [
        ("guardar_docente", "FAILED", "StaleDecisionError")]
    assert db_conn.execute("SELECT count(*) FROM docentes WHERE cuil=%s AND departamento_id=1", [C2]).fetchone()[0] == 0


# ------------------------------------------------------------------------------------------ camino 3: CUIL local
@pytest.mark.parametrize("caso", ["nueva", "identica_existente", "prestado_local"])
def test_cuil_local_equivalente(db_conn, registro, service, repo, audit_store, caso):
    seed_docente(db_conn, C3, "Local", "Luis", tipo="Prestado" if caso == "prestado_local" else "Propio")
    v = _valores(dedicacion="Simple")
    if caso == "identica_existente":
        seed_designacion(db_conn, C3, v)
    rec = _record(service, repo)
    ctx = _contexto(registro, rec)
    r = comparar(db_conn, audit_store, [C3], lambda c: cert_cuil_local(c, C3, v),
                 lambda: registro.registrar(rec, _payload(v, ctx["abierto_huella"], camino="cuil_local",
                                                          cuil_alta=C3.replace("-", ""))))
    assert [o["op"] for o in r["ops"]] == (["guardar_designacion"] if caso != "identica_existente" else [])
    assert r["estado"]["movimientos"] == []  # el certificado no registra movimiento en este camino


def test_cuil_local_rechaza_si_hay_coincidencias_en_otro_departamento(db_conn, registro, service, repo, audit_store):
    from docentes.service import DocentesError
    seed_docente(db_conn, C2, "Otra", "Dora", dep=DEP2)
    rec = _record(service, repo)
    with pytest.raises(DocentesError) as exc:
        registro.registrar(rec, _payload(_valores(), None, camino="cuil_local", cuil_alta=C2))
    assert exc.value.status == 409 and audit_store.events == []


# ------------------------------------------------------------------------------------------ contexto, permisos, scope
def test_permisos_b10_por_writer(db_conn, registro, service, repo, audit_store):
    """solo_lectura: DENIED del primer writer del camino (``guardar_designacion`` / ``guardar_docente``), nada mas.
    Coordinador sin departamento: 409 de ambito.  Superadmin con contexto: escribe."""
    from docentes.service import DocentesError
    seed_docente(db_conn, C1, "Zeta", "Ana")
    seed_docente(db_conn, C2, "Otra", "Dora", dep=DEP2)
    origen = _dep_nombre(db_conn, DEP2)
    lector = _record(service, repo, 7)
    ctx = _contexto(registro, lector)
    assert ctx["puede_escribir"] is False
    datos1 = _payload(_valores(), ctx["abierto_huella"], camino="reincorporar", cuil=C1, huella=_huella_docente(ctx, C1))
    datos2 = _payload(_valores(), ctx["abierto_huella"], camino="cuil_existente", cuil=C2, departamento_origen=origen,
                      cuil_alta=C2)
    max_mov = DS.baseline(db_conn)
    antes = estado(db_conn, max_mov, [C1, C2])
    for datos, writer, permiso in ((datos1, "guardar_designacion", "designaciones.write"),
                                   (datos2, "guardar_docente", "docentes.write")):
        n = len(audit_store.events)
        with pytest.raises(DocentesError) as exc:
            registro.registrar(lector, datos)
        assert exc.value.status == 403 and permiso in exc.value.message
        assert [(e.operation, e.outcome) for e in audit_store.events[n:]] == [(writer, "DENIED")]
    with pytest.raises(DocentesError) as exc:
        registro.registrar(_record(service, repo, 2), datos1)
    assert exc.value.status == 409
    assert estado(db_conn, max_mov, [C1, C2]) == antes
    sup = _record(service, repo, 1, dep=DEP)
    assert _contexto(registro, sup)["puede_escribir"] is True
    with db_conn.transaction() as tx:
        r = registro.registrar(sup, datos1)
        raise psycopg.Rollback(tx)
    assert r["mensaje"] == "Docente reincorporado y designación registrada correctamente."


def test_ambito_de_la_sesion(db_conn, registro, service, repo, audit_store):
    """El CUIL de un docente de otro departamento no es reincorporable desde el departamento de la sesion (404), y el
    superadmin en el departamento 2 ve SU lista, no la del 1.  Los ids de tenant del cliente se ignoran."""
    from docentes.service import DocentesError
    seed_docente(db_conn, C1, "Zeta", "Ana")
    seed_docente(db_conn, C4, "Dos", "Dino", dep=DEP2)
    sup2 = _record(service, repo, 1, dep=DEP2)
    ctx2 = _contexto(registro, sup2)
    cert2 = _Cert(db_conn, DEP2)
    per2 = cert2.nsd["get_periodo_abierto"]()
    if per2:
        assert [d["cuil"] for d in ctx2["reincorporables"]] == [str(c) for c in cert2.reincorporables(per2["id"])["cuil"]]
    assert C1 not in [d["cuil"] for d in ctx2["reincorporables"]]
    rec = _record(service, repo)
    ctx = _contexto(registro, rec)
    datos = _payload(_valores(), ctx["abierto_huella"], camino="reincorporar", cuil=C4, huella="x",
                     institucion_id=2, departamento_id=DEP2)
    with pytest.raises(DocentesError) as exc:
        registro.registrar(rec, datos)
    assert exc.value.status == 404 and audit_store.events == []


def test_periodo_historico_abierto(db_conn, registro, service, repo, audit_store):
    """Con un periodo anterior abierto por excepcion (historico), el certificado usa ``get_periodo_abierto``: la lista
    y la escritura van a ESE periodo.  NEXT igual."""
    db_conn.execute("UPDATE periodos SET estado='Cerrado' WHERE institucion_id=1 AND departamento_id=1")
    db_conn.execute("UPDATE periodos SET estado='Abierto' WHERE id=5")
    seed_docente(db_conn, C1, "Zeta", "Ana")
    rec = _record(service, repo)
    ctx = _contexto(registro, rec)
    assert ctx["abierto"]["id"] == 5
    cert = _Cert(db_conn)
    assert [d["cuil"] for d in ctx["reincorporables"]] == [str(c) for c in cert.reincorporables(5)["cuil"]]
    v = _valores(desde=date(2025, 3, 1), hasta=date(2025, 7, 31))
    r = comparar(db_conn, audit_store, [C1], lambda c: cert_reincorporar(c, C1, v),
                 lambda: registro.registrar(rec, _payload(v, ctx["abierto_huella"], camino="reincorporar", cuil=C1,
                                                          huella=_huella_docente(ctx, C1))))
    assert '"periodo_id": 5' in r["estado"]["movimientos"][0]


def test_sin_periodo_abierto(db_conn, registro, service, repo, audit_store):
    from docentes.service import DocentesError
    db_conn.execute("UPDATE periodos SET estado='Cerrado' WHERE institucion_id=1 AND departamento_id=1")
    seed_docente(db_conn, C1, "Zeta", "Ana")
    seed_docente(db_conn, C3, "Local", "Luis")
    rec = _record(service, repo)
    ctx = _contexto(registro, rec)
    assert ctx["abierto"] is None and ctx["reincorporables"] == []
    for datos, msg in ((_payload(_valores(), None, camino="reincorporar", cuil=C1, huella="x"),
                        "No hay un período abierto. Abrí o creá el período actual antes de reincorporar docentes."),
                       (_payload(_valores(), None, camino="cuil_local", cuil_alta=C3), "No hay un período abierto.")):
        with pytest.raises(DocentesError) as exc:
            registro.registrar(rec, datos)
        assert exc.value.status == 409 and exc.value.message == msg
    assert audit_store.events == []


def test_contexto_catalogos_del_owner(db_conn, registro, service, repo):
    from designaciones import rules
    ctx = _contexto(registro, _record(service, repo))
    assert ctx["catalogos"] == {"cargos": rules.CARGOS, "dedicaciones": rules.DEDICACIONES,
                                "horas_por_dedicacion": rules.HORAS_POR_DEDICACION, "tipos": rules.TIPOS_DESIGNACION,
                                "estados": rules.ESTADOS_DESIGNACION, "ad_honorem": rules.AD_HONOREM}
    from deptit_refactor.catalogs.designaciones import CARGOS, DEDICACIONES, TIPOS_DESIGNACION
    assert (ctx["catalogos"]["cargos"], ctx["catalogos"]["dedicaciones"], ctx["catalogos"]["tipos"]) == \
        (CARGOS, DEDICACIONES, TIPOS_DESIGNACION)
    assert set(ctx["reincorporables"][0]) == {"nombre_completo", "cuil", "legajo", "titulo", "estado", "huella"}


def test_hardening(db_conn, registro, service, repo, audit_store):
    """Camino o valores fuera de los selectores, tipos invalidos: 422 sin escrituras ni eventos."""
    from docentes.service import DocentesError
    seed_docente(db_conn, C1, "Zeta", "Ana")
    rec = _record(service, repo)
    ctx = _contexto(registro, rec)
    base = _payload(_valores(), ctx["abierto_huella"], camino="reincorporar", cuil=C1, huella=_huella_docente(ctx, C1))
    for datos in ({**base, "camino": "otro"}, {**base, "cargo": "Decano"}, {**base, "fecha_desde": "31/12/2026"},
                  {**base, "cuil": 20991180013}, {**base, "dedicacion": None}, {**base, "estado": "Borrada"}):
        with pytest.raises(DocentesError) as exc:
            registro.registrar(rec, datos)
        assert exc.value.status in (404, 422), datos
    assert audit_store.events == []


# ------------------------------------------------------------------------------------------ HTTP y arquitectura
def test_http(db_conn, registro, service, repo):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from auth.routes import router as auth_router
    from integraciones.routes import docentes_router

    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(docentes_router)
    app.state.auth = service
    app.state.registro_designacion = registro
    client = TestClient(app, base_url="http://localhost")
    seed_docente(db_conn, C1, "Zeta", "Ana")
    h = {"X-DEPTIT-Request": "1"}
    for ruta in ("/docentes/designacion/contexto", "/docentes/designacion/duplicado", "/docentes/designacion"):
        assert client.post(ruta, headers=h, json={}).status_code == 401
    client.cookies.set("deptit_session", session_for(service, repo, 3)[1])
    assert client.post("/docentes/designacion/contexto").status_code == 403  # sin cabecera del proxy
    ctx = client.post("/docentes/designacion/contexto", headers=h).json()
    assert C1 in [d["cuil"] for d in ctx["reincorporables"]]
    datos = _payload(_valores(), ctx["abierto_huella"], camino="reincorporar", cuil=C1,
                     huella=_huella_docente(ctx, C1))
    assert client.post("/docentes/designacion/duplicado", headers=h, json=datos).json() == {"duplicada": False}
    with db_conn.transaction() as tx:
        r = client.post("/docentes/designacion", headers=h, json=datos)
        raise psycopg.Rollback(tx)
    assert r.status_code == 200 and r.json()["mensaje"] == "Docente reincorporado y designación registrada correctamente."
    r = client.post("/docentes/designacion", headers=h, json={**datos, "fecha_hasta": "2026-01-01"})
    assert r.status_code == 422 and r.json()["error"]["message"] == "La fecha hasta no puede ser anterior a la fecha desde."
    assert "SELECT" not in r.text and "Traceback" not in r.text


def test_arquitectura_sin_ciclos():
    """Ningun owner importa la composicion; Docentes no importa Designaciones y Designaciones no importa el servicio de
    Docentes (solo helpers puros ya usados antes de E4-08): sin ciclo (D-E4-01)."""
    import re
    for owner, otro in (("docentes", "designaciones"), ("designaciones", "docentes")):
        for archivo in (BACKEND / owner).glob("*.py"):
            texto = archivo.read_text(encoding="utf-8")
            assert not re.search(r"(?m)^\s*(from|import) integraciones", texto), archivo
            imports = set(re.findall(rf"(?:from|import) ({otro}[\w.]*)", texto))
            assert ("docentes.service" not in imports) if otro == "docentes" else not imports, (archivo, imports)
    texto = (BACKEND / "integraciones" / "registro_designacion.py").read_text(encoding="utf-8")
    assert not re.search(r"(?m)^\s*(from|import) \w+\.(repository|escrituras)", texto)
    assert not re.search(r"(?i)(insert into|update \w+ set|delete from)", texto)
