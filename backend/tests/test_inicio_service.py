"""Servicio y HTTP de Inicio: acceso por rol y contexto (D-AN2), estados A/B/C, "🔄 Actualizar tablero" como refetch
habilitado para todos (D-AN3), titulo con el departamento operativo (D-AN4), navegacion (D-AN5), Excel de "Próximos
vencimientos" (D-AN6), cero writers / B12H / locks, ambito exclusivamente de la sesion y respuestas sin detalles
internos.  Datos sinteticos dentro de la transaccion del test (ROLLBACK)."""

from __future__ import annotations

import io
import os
from pathlib import Path

import openpyxl
import psycopg
import pytest

from auth import policy
from inicio import pagina as P
from inicio.service import MSG_TABLERO, InicioError, InicioService
from inicio_support import (  # noqa: F401  (fixtures)
    db_conn, http, inicio, make_inicio, session_for,
)
from test_inicio_differential import _clonar, vencimientos_sinteticos

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")

CSRF = {"X-DEPTIT-Request": "1"}
FORBIDDEN = ("salt", "password_hash", "postgresql://", "DATABASE_URL", "deptit_session", "SELECT ", "UPDATE ",
             "DELETE ", "Traceback", "psycopg", "C:\\", "C:/", "source_db", "sqlite", "reference_fix02",
             "analisis.motor", "deptit_refactor", "RuntimeError", "Exception")
DEP1 = "Departamento de Informática e Ingeniería"


@pytest.fixture
def records(service, repo):
    out = {"dep": session_for(service, repo, 3)[0], "lector": session_for(service, repo, 7)[0]}
    sup = session_for(service, repo, 1)[0]
    service.set_context(sup, 1, 1, False)
    out["super"] = sup
    coord = session_for(service, repo, 2)[0]
    service.set_context(coord, 1, 1, False)
    out["coord_dep"] = coord
    out["coord"] = session_for(service, repo, 2)[0]
    repo.institutions_rows[0]["estado_pago"] = "Vencido"
    out["ro"] = session_for(service, repo, 3)[0]
    repo.institutions_rows[0]["estado_pago"] = "Al día"
    return out


def _foto(db_conn):
    return db_conn.execute(
        "SELECT (SELECT md5(string_agg(md5(d::text),'' ORDER BY d.id)) FROM designaciones d), "
        "(SELECT md5(string_agg(md5(c::text),'' ORDER BY c.id)) FROM comisiones c), "
        "(SELECT md5(string_agg(md5(p::text),'' ORDER BY p.id)) FROM periodos p), "
        "(SELECT md5(string_agg(md5(m::text),'' ORDER BY m.id)) FROM movimientos m), "
        "(SELECT md5(string_agg(md5(c::text),'' ORDER BY c.id)) FROM config_productividad_departamento c), "
        "(SELECT count(*) FROM b12h_audit_log)").fetchone()


def _destinos(t: dict) -> list[str]:
    out = [a["boton"]["destino"] for a in t["acciones"]["items"]] + [t["salud"]["boton"]["destino"]]
    return out + ([t["vencimientos"]["boton"]["destino"]] if t["vencimientos"]["boton"] else [])


# ------------------------------------------------------------------------------------------ roles y contexto (D-AN2)
def test_acceso_por_rol_y_contexto(inicio, records, db_conn, service):
    """Todos los roles con Inicio lo ven segun su contexto; mismo tablero para el mismo departamento; titulo operativo;
    "Actualizar" igual para todos (no depende del rol); destinos visibles para cada rol; ninguna escritura."""
    antes = _foto(db_conn)
    vistos = {}
    for rol in ("dep", "lector", "super", "coord_dep", "ro"):
        out = inicio.tablero(records[rol])
        assert out["estado"] == "tablero" and out["titulo"] == f"Inicio — {DEP1}", rol
        assert out["contexto"]["departamento"] == {"id": 1, "nombre": DEP1}
        t = out["tablero"]
        assert t["periodo"]["actualizar"] == {"label": "🔄 Actualizar tablero", "caption": P.CAPTION_ACTUALIZAR}
        visibles = {m[0] for m in policy.visible_modules(policy.normalize_role(records[rol].user.get("rol")),
                                                         records[rol].scope.get(policy.DEPARTMENT_SCOPE_KEY))}
        assert set(_destinos(t)) <= visibles, rol
        vistos[rol] = {k: v for k, v in t.items()}
    assert all(v == vistos["dep"] for v in vistos.values())  # sin diferencias de datos por rol
    coord = inicio.tablero(records["coord"])
    assert coord["estado"] == "institucional" and "tablero" not in coord
    assert coord["institucional"]["boton"] == {"label": "🏛️ Ir al consolidado institucional",
                                               "destino": "consolidado", "primario": True}
    assert coord["titulo"] == "Inicio — Departamento correspondiente" and coord["contexto"]["departamento"] is None
    assert "consolidado" in {m[0] for m in policy.visible_modules(policy.ROLE_COORDINADOR, None)}
    assert _foto(db_conn) == antes
    assert db_conn.execute("SELECT count(*) FROM pg_locks WHERE locktype='advisory'").fetchone()[0] == 0


def test_ambito_solo_de_la_sesion(inicio, records, service):
    """El departamento sale de la sesion: el superadmin que cambia de contexto ve el otro departamento (titulo y datos);
    un departamento invalido en la sesion se rechaza sin caer a otro (fail-closed)."""
    sup = records["super"]
    service.set_context(sup, 1, 9, False)
    out = inicio.tablero(sup)
    assert out["titulo"] == "Inicio — Departamento de Ciencias Exactas y Naturales"
    assert out["tablero"]["situacion"]["tarjetas"][0]["valor"] == "68"
    sup.scope[policy.DEPARTMENT_SCOPE_KEY] = 999
    with pytest.raises(InicioError) as exc:
        inicio.tablero(sup)
    assert exc.value.code == "SCOPE_NOT_VERIFIED" and exc.value.status == 409


def test_actualizar_recalcula_sin_cache(inicio, records, db_conn):
    """D-AN3: cada consulta recalcula (sin la cache de 60 s): un cambio entre dos pedidos se ve en el segundo."""
    primero = inicio.tablero(records["lector"])["tablero"]
    assert primero["acciones"]["items"][0]["titulo"] == "1 docente sin carga"
    _clonar(db_conn, "comisiones", "institucion_id=1 AND departamento_id=1 AND periodo_id=9 AND estado='Activa'",
            {"nombre_comision": "ZZNEXT-REFRESH", "sqlite_id": None})
    segundo = inicio.tablero(records["lector"])["tablero"]
    assert segundo["acciones"]["items"][0]["titulo"] == "1 comisión sin cubrir"
    assert segundo["situacion"]["tarjetas"][2]["valor"] == "71"


def test_sin_periodo_abierto(inicio, records, db_conn):
    db_conn.execute("UPDATE periodos SET estado='Cerrado' WHERE institucion_id=1 AND departamento_id=1")
    out = inicio.tablero(records["dep"])
    assert out["estado"] == "sin_periodo" and out["sin_periodo"] == P.sin_periodo()
    assert out["sin_periodo"]["boton"]["destino"] == "periodos" and out["sin_periodo"]["ayuda"]["abierto"]


def test_errores_genericos_sin_detalles(inicio, records, db_conn, monkeypatch):
    """El certificado mostraba el texto de la excepcion; NEXT muestra un mensaje generico (hardening)."""
    def boom(ns, periodo):
        raise RuntimeError("SELECT secreto FROM C:\\ruta postgresql://x")
    monkeypatch.setattr(InicioService, "_datos", staticmethod(boom))
    t = inicio.tablero(records["dep"])["tablero"]
    assert t["error"] == MSG_TABLERO and t["periodo"]["linea"].startswith("**Período actual:**")
    assert not any(x in repr(t) for x in FORBIDDEN)

    def caida():
        raise psycopg.OperationalError("connection to postgresql://secreto failed")
    roto = make_inicio(inicio.auth, db_conn, transaction=caida)
    with pytest.raises(InicioError) as exc:
        roto.tablero(records["dep"])
    assert exc.value.status == 503 and not any(x in exc.value.message for x in FORBIDDEN)


# ------------------------------------------------------------------------------------------ Excel (D-AN6)
def _login(http, repo, email="info@test.local"):
    assert http.post("/auth/login", json={"email": email, "password": repo.passwords[email]},
                     headers=CSRF).status_code == 200
    return http


def test_excel_vencimientos(http, repo, db_conn, inicio, records):
    c = _login(http, repo)
    r = c.post("/inicio/descargas/vencimientos", headers=CSRF)  # sin vencimientos: no hay tabla ni Excel
    assert r.status_code == 409 and r.json()["error"]["code"] == "SIN_VENCIMIENTOS"
    archivos_antes = sorted(os.listdir(Path(__file__).resolve().parents[1]))
    vencimientos_sinteticos(db_conn, 10)
    vista = inicio.tablero(records["dep"])["tablero"]["vencimientos"]
    r = c.post("/inicio/descargas/vencimientos", headers=CSRF)
    assert r.status_code == 200 and r.content[:2] == b"PK"
    assert r.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert r.headers["content-disposition"] == ('attachment; filename="Inicio_20261026_103000.xlsx"; '
                                                "filename*=UTF-8''Inicio_20261026_103000.xlsx")
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["cache-control"] == "no-store"
    wb = openpyxl.load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames == ["Datos"]
    filas = [list(f) for f in wb["Datos"].iter_rows(values_only=True)]
    assert filas[0] == P.COLS_VENCIMIENTOS == vista["tabla"]["columnas"]
    assert filas[1:] == vista["tabla"]["filas"] and len(filas) == 9  # solo las 8 filas visibles
    assert sorted(os.listdir(Path(__file__).resolve().parents[1])) == archivos_antes  # sin archivos residuales
    for sin_csrf in (c.post("/inicio/descargas/vencimientos"), c.get("/inicio/descargas/vencimientos")):
        assert sin_csrf.status_code in (403, 405)


def test_excel_ambito_y_periodo(inicio, records, db_conn, service):
    """El Excel es del departamento y periodo abierto de la sesion: el dep. 9 no ve los vencimientos del dep. 1."""
    vencimientos_sinteticos(db_conn, 3)
    assert inicio.excel_vencimientos(records["dep"]).contenido[:2] == b"PK"
    sup = records["super"]
    service.set_context(sup, 1, 9, False)
    with pytest.raises(InicioError) as exc:
        inicio.excel_vencimientos(sup)
    assert exc.value.code == "SIN_VENCIMIENTOS"
    with pytest.raises(InicioError) as exc:
        inicio.excel_vencimientos(records["coord"])
    assert exc.value.code == "SCOPE_INSTITUTIONAL"
    db_conn.execute("UPDATE periodos SET estado='Cerrado' WHERE institucion_id=1 AND departamento_id=1")
    with pytest.raises(InicioError) as exc:
        inicio.excel_vencimientos(records["dep"])
    assert exc.value.code == "SIN_PERIODO"


# ------------------------------------------------------------------------------------------ HTTP
def test_http_sesion_respuestas_limpias_y_ausencias(http, repo, db_conn):
    assert http.get("/inicio").status_code == 401
    assert http.post("/inicio/descargas/vencimientos", headers=CSRF).status_code == 401
    c = _login(http, repo)
    antes = _foto(db_conn)
    r = c.get("/inicio", params={"departamento_id": 9, "periodo_id": 5})  # parametros del cliente: ignorados
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    body = r.json()
    assert body["titulo"] == f"Inicio — {DEP1}" and body["tablero"]["periodo"]["linea"].startswith(
        "**Período actual:** 2026-2")
    assert not any(x in r.text for x in FORBIDDEN), [x for x in FORBIDDEN if x in r.text]
    for ruta in ("excel", "csv", "pdf", "zip", "word", "imprimir", "guardar", "actualizar", "reparar", "periodo"):
        assert c.post(f"/inicio/{ruta}", json={}, headers=CSRF).status_code in (404, 405), ruta
        assert c.post(f"/inicio/descargas/{ruta}", json={}, headers=CSRF).status_code in (404, 405), ruta
    assert c.post("/inicio", json={}, headers=CSRF).status_code == 405
    assert _foto(db_conn) == antes


def test_sin_writers_ni_motor_nuevo():
    """Cero writers (sin SQL mutante, COMMIT, B12H ni locks) y reutilizacion del motor de Analisis (D-AN1): el paquete
    ``inicio`` no define funciones certificadas ni genera otro motor."""
    import re

    raiz = Path(__file__).resolve().parents[1] / "inicio"
    texto = "\n".join(p.read_text(encoding="utf-8") for p in sorted(raiz.glob("*.py")))
    for patron in (r"\bINSERT\b", r"\bUPDATE\b", r"\bDELETE\b", r"\.commit\(", r"\baudit\b", r"advisory",
                   r"pg_advisory", r"def _inicio_datos_tablero_cache", r"def get_metricas_analisis_periodo",
                   r"exec\(", r"compile\(", r"\bopen\(", r"requests|httpx|socket"):
        assert not re.search(patron, texto), patron
    assert "from analisis.motor import entorno" in texto and "SET TRANSACTION READ ONLY" in texto
    assert sorted(p.name for p in raiz.glob("*.py")) == ["__init__.py", "pagina.py", "routes.py", "service.py"]
