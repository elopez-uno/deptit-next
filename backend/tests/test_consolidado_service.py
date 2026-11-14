"""Servicio y HTTP de Consolidado institucional: acceso por rol (coordinador y superadmin; el resto 403, incluida la
solo lectura comercial), institucion exclusivamente de la sesion (D-AO5, fail-closed), sesion inmutable, visor bajo
demanda con allowlist (D-AO3), descargas (D-AO4), cero escrituras / B12H / locks y respuestas sin detalles internos."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from auth import policy
from consolidado import lecturas as L
from consolidado.service import MSG_ROL, ConsolidadoError
from consolidado_support import consolidado, db_conn, http, make_consolidado, session_for  # noqa: F401
from periodos_support import EXTRA_DEPARTMENTS

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")

CSRF = {"X-DEPTIT-Request": "1"}
FORBIDDEN = ("salt", "password_hash", "postgresql://", "DATABASE_URL", "deptit_session", "SELECT ", "UPDATE ",
             "DELETE ", "Traceback", "psycopg", "C:\\", "C:/", "source_db", "sqlite_id", "reference_fix02",
             "deptit_refactor", "RuntimeError", "KeyError", "Exception")


@pytest.fixture
def records(service, repo):
    repo.departments_rows.extend(dict(d) for d in EXTRA_DEPARTMENTS)
    out = {"dep": session_for(service, repo, 3)[0], "lector": session_for(service, repo, 7)[0],
           "coord": session_for(service, repo, 2)[0]}
    sup = session_for(service, repo, 1)[0]
    service.set_context(sup, 1, 1, False)
    out["super"] = sup
    coord_dep = session_for(service, repo, 2)[0]
    service.set_context(coord_dep, None, 2, False)
    out["coord_dep"] = coord_dep
    repo.institutions_rows[0]["estado_pago"] = "Vencido"
    out["ro_coord"] = session_for(service, repo, 2)[0]
    out["ro_dep"] = session_for(service, repo, 3)[0]
    repo.institutions_rows[0]["estado_pago"] = "Al día"
    return out


def _foto(db_conn):
    return db_conn.execute(
        "SELECT pg_current_xact_id_if_assigned(), "
        "(SELECT count(*) FROM pg_locks WHERE locktype='advisory'), "
        "(SELECT count(*) FROM b12h_audit_log), "
        "(SELECT md5(string_agg(md5(d::text),'' ORDER BY d.id)) FROM designaciones d)").fetchone()


def _login(http, repo, uid=2):
    email = next(u["email"] for u in repo.users if u["id"] == uid)
    assert http.post("/auth/login", json={"email": email, "password": repo.passwords[email]},
                     headers=CSRF).status_code == 200
    return http


# ------------------------------------------------------------------------------------------ roles
def test_acceso_por_rol(consolidado, records, db_conn):
    """Coordinador (con o sin departamento elegido) y superadmin: mismo tablero de la institucion 1.  usuario_departamento,
    solo_lectura y la solo lectura COMERCIAL (rol efectivo ``solo_lectura``, incluso de un coordinador): 403 DENIED con
    el mensaje certificado, sin leer datos.  Coincide con el menu (``visible_modules``)."""
    antes = _foto(db_conn)
    vistos = {}
    for rol in ("coord", "coord_dep", "super"):
        ov = consolidado.overview(records[rol])
        assert ov["estado"] == "tablero" and ov["titulo"] == "🏛️ Consolidado institucional", rol
        assert ov["contexto"]["institucion"]["id"] == 1
        vistos[rol] = {k: ov[k] for k in ("metricas", "control", "resumen", "visor")}
    assert vistos["coord"] == vistos["coord_dep"] == vistos["super"]
    for rol in ("dep", "lector", "ro_coord", "ro_dep"):
        visible = {m[0] for m in policy.visible_modules(policy.normalize_role(records[rol].user.get("rol")),
                                                        records[rol].scope.get(policy.DEPARTMENT_SCOPE_KEY))}
        assert "consolidado" not in visible, rol
        for llamada in (lambda r: consolidado.overview(r), lambda r: consolidado.tabla(r, "docentes", ""),
                        lambda r: consolidado.csv(r, "docentes"), lambda r: consolidado.excel(r, "resumen", None)):
            with pytest.raises(ConsolidadoError) as exc:
                llamada(records[rol])
            assert (exc.value.status, exc.value.code, exc.value.message) == (403, "DENIED", MSG_ROL), rol
    assert records["ro_coord"].user["rol"] == "solo_lectura" and records["ro_coord"].user["rol_original"] == \
        "coordinador_institucional"
    assert _foto(db_conn) == antes


# ------------------------------------------------------------------------------------------ ambito (D-AO5)
def test_institucion_solo_de_la_sesion_y_fail_closed(consolidado, records, service):
    """Superadmin: la institucion operativa de la sesion (2 -> 4 departamentos sin periodos; 5 -> sin datos).  Sin
    institucion valida en la sesion: 409 sin caer a otra institucion.  La sesion no se modifica al consolidar."""
    sup = records["super"]
    service.set_context(sup, 2, 5, False)
    antes = dict(sup.scope)
    ov = consolidado.overview(sup)
    assert ov["contexto"]["institucion"]["id"] == 2 and len(ov["resumen"]["tabla"]["filas"]) == 4
    assert sup.scope == antes
    service.set_context(sup, 5, None, False)
    assert consolidado.overview(sup) == {"titulo": "🏛️ Consolidado institucional",
                                         "contexto": {"institucion": {"id": 5, "nombre": "Universidad de Hurlingham"}},
                                         "estado": "sin_datos", "mensaje": "Sin datos para consolidar."}
    for invalida in (999, -1):
        sup.scope[policy.SUPERADMIN_INSTITUTION_KEY] = invalida
        with pytest.raises(ConsolidadoError) as exc:
            consolidado.overview(sup)
        assert exc.value.status == 409 and exc.value.code == "SCOPE_NOT_VERIFIED"
    coord = records["coord"]
    coord.user["institucion_id"] = None  # coordinador sin institucion: fail-closed
    with pytest.raises(ConsolidadoError) as exc:
        consolidado.overview(coord)
    assert exc.value.status == 409


# ------------------------------------------------------------------------------------------ visor y allowlist
def test_visor_bajo_demanda_y_allowlist(consolidado, records, db_conn):
    """La lectura inicial NO trae ninguna tabla del visor (solo el catalogo); cada tabla se pide por clave de la
    allowlist.  Claves inexistentes, nombres fisicos, SQL o tipos no texto: 422 sin leer."""
    coord = records["coord"]
    ov = consolidado.overview(coord)
    assert set(ov) == {"titulo", "contexto", "estado", "metricas", "caption", "control", "resumen", "visor"}
    assert ov["visor"]["opciones"] == L.TABLAS and ov["visor"]["default"] == "docentes"
    assert len(str(ov)) < 20_000  # sin datasets del visor
    t = consolidado.tabla(coord, "movimientos", None)
    assert t["total"] == t["encontrados"] == len(t["datos"]["filas"]) and t["caption"] is None
    for mala in ("departamentos", "app_usuarios", "pg_catalog.pg_user", "comisiones; DROP TABLE comisiones",
                 "COMISIONES", " comisiones", "resumen", "", None, 7, ["comisiones"]):
        with pytest.raises(ConsolidadoError) as exc:
            consolidado.tabla(coord, mala, "")
        assert exc.value.status == 422, mala
        with pytest.raises(ConsolidadoError):
            consolidado.csv(coord, mala)
    with pytest.raises(ConsolidadoError) as exc:
        consolidado.tabla(coord, "docentes", {"$ne": 1})
    assert exc.value.status == 422
    larga = consolidado.tabla(coord, "docentes", "x" * 5000)
    assert larga["busqueda"] == "x" * 200


def test_descargas(consolidado, records):
    coord = records["coord"]
    csv = consolidado.csv(coord, "comisiones")
    assert csv.nombre == "comisiones_consolidado.csv" and csv.media_type == "text/csv"
    x = consolidado.excel(coord, "comisiones", "Mañana")
    assert x.contenido[:2] == b"PK" and x.nombre == "Consolidado_institucional_20261026_101500.xlsx" \
        or x.nombre.startswith("Consolidado_institucional_")
    assert consolidado.excel(coord, "resumen", None).contenido[:2] == b"PK"
    with pytest.raises(ConsolidadoError) as exc:
        consolidado.csv(coord, "inscriptos_asignatura_periodo")
    assert exc.value.code == "SIN_DATOS" and exc.value.tone == "info"


def test_errores_genericos_sin_detalles(records, service, monkeypatch, db_conn):
    from consolidado import lecturas

    roto = make_consolidado(service, db_conn)

    def falla(*a, **k):
        raise RuntimeError("SELECT secreto FROM C:/ruta source_db")
    monkeypatch.setattr(lecturas, "consolidado", falla)
    with pytest.raises(ConsolidadoError) as exc:
        roto.overview(records["coord"])
    assert exc.value.status == 503 and exc.value.code == "DB_READ"
    assert not any(x in exc.value.message for x in FORBIDDEN)


# ------------------------------------------------------------------------------------------ HTTP
def test_http_sesion_csrf_campos_maliciosos_y_cabeceras(http, repo, db_conn):
    assert http.get("/consolidado").status_code == 401
    assert http.post("/consolidado/tabla", json={"tabla": "docentes"}, headers=CSRF).status_code == 401
    c = _login(http, repo, 2)
    antes = _foto(db_conn)
    r = c.get("/consolidado", params={"institucion_id": 2, "departamento_id": 9})  # query del cliente: ignorada
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    assert r.json()["contexto"]["institucion"]["id"] == 1
    assert not any(x in r.text for x in FORBIDDEN), [x for x in FORBIDDEN if x in r.text]
    assert c.post("/consolidado/tabla", json={"tabla": "docentes"}).status_code == 403  # sin CSRF
    for body in ({"tabla": "docentes", "institucion_id": 2}, {"tabla": "docentes", "departamento_ids": [1, 2]},
                 {"tabla": "docentes", "sql": "SELECT 1"}, {"tabla": "app_usuarios"},
                 {"tabla": "comisiones; DROP TABLE comisiones"}, {}, {"tabla": None}):
        rr = c.post("/consolidado/tabla", json=body, headers=CSRF)
        assert rr.status_code == 422, body
        assert not any(x in rr.text for x in FORBIDDEN), body
        assert c.post("/consolidado/descargas/csv", json=body, headers=CSRF).status_code == 422, body
    rt = c.post("/consolidado/tabla", json={"tabla": "comisiones", "buscar": "Mañana"}, headers=CSRF)
    assert rt.status_code == 200 and rt.json()["tabla"] == "comisiones"
    assert not any(x in rt.text for x in ("source_db", "sqlite_id", "SELECT ", "Traceback"))
    for ruta, body in (("csv", {"tabla": "comisiones"}), ("excel", {"tabla": "comisiones", "buscar": "Mañana"}),
                       ("excel", {"tabla": "resumen"})):
        rd = c.post(f"/consolidado/descargas/{ruta}", json=body, headers=CSRF)
        assert rd.status_code == 200, ruta
        assert rd.headers["x-content-type-options"] == "nosniff" and rd.headers["cache-control"] == "no-store"
        disp = rd.headers["content-disposition"]
        assert disp.startswith('attachment; filename="') and "\n" not in disp and "/" not in disp.split(";")[1]
        assert "@" not in disp and not re.search(r"\d{2}-?\d{8}-?\d", disp)  # sin datos personales en el nombre
    for ruta in ("pdf", "zip", "word", "txt", "imprimir", "guardar", "reparar", "normalizar", "sql"):
        assert c.post(f"/consolidado/{ruta}", json={}, headers=CSRF).status_code in (404, 405), ruta
        assert c.post(f"/consolidado/descargas/{ruta}", json={}, headers=CSRF).status_code in (404, 405), ruta
    assert c.post("/consolidado", json={}, headers=CSRF).status_code == 405
    assert _foto(db_conn) == antes


def test_http_rol_sin_acceso(http, repo):
    c = _login(http, repo, 3)
    r = c.get("/consolidado")
    assert r.status_code == 403 and r.json()["error"]["message"] == MSG_ROL
    assert c.post("/consolidado/tabla", json={"tabla": "docentes"}, headers=CSRF).status_code == 403
    assert c.post("/consolidado/descargas/csv", json={"tabla": "docentes"}, headers=CSRF).status_code == 403


# ------------------------------------------------------------------------------------------ sin writers
def test_sin_escrituras_en_ninguna_operacion(consolidado, records, db_conn):
    """0 xid asignado, 0 advisory locks, 0 eventos B12H y base intacta tras todas las operaciones."""
    antes = _foto(db_conn)
    coord = records["coord"]
    consolidado.overview(coord)
    for clave in L.TABLAS:
        consolidado.tabla(coord, clave, "a")
    consolidado.csv(coord, "designaciones")
    consolidado.excel(coord, "docentes", "a")
    assert _foto(db_conn) == antes and antes[0] is None and antes[1] == 0


def test_sin_writers_ni_motor_ni_reparacion():
    """El paquete no tiene SQL mutante, COMMIT, auditoria, locks, motor vendorizado ni la reparacion v229."""
    raiz = Path(__file__).resolve().parents[1] / "consolidado"
    texto = "\n".join(p.read_text(encoding="utf-8") for p in sorted(raiz.glob("*.py")))
    for patron in (r"\bINSERT\b", r"\bUPDATE\b", r"\bDELETE\b", r"\bUPSERT\b", r"ON CONFLICT", r"\.commit\(",
                   r"\baudit\b", r"advisory", r"analisis\.motor", r"normalizar_designaciones", r"_v229",
                   r"exec\(", r"compile\(", r"\bopen\(", r"requests|httpx|socket", r"tenant_scope_departamento_id",
                   r"to_csv\(.*path", r"NamedTemporaryFile"):
        assert not re.search(patron, texto), patron
    assert "SET TRANSACTION READ ONLY" in texto and "sql.Identifier" in texto
    assert sorted(p.name for p in raiz.glob("*.py")) == ["__init__.py", "lecturas.py", "routes.py", "service.py"]
