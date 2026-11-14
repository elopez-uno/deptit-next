"""Etapa 6A-B1: hardening productivo — cookie de sesion, /health, /docs, errores, CSRF directo, origen del cliente y
limite de login por IP, contraseñas versionadas con re-hash progresivo y validacion de subidas Excel
(docs/ETAPA6_6AB1_PRODUCTIVE_SOFTWARE_HARDENING.md).  Sin escrituras en la base: repositorio falso o lecturas."""

from __future__ import annotations

import base64
import io
import os
import subprocess
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import Response
from fastapi.testclient import TestClient

import settings as S
import uploads
from auth import client_ip as CI
from auth import core
from auth import routes as AR
from auth.service import AuthService

BACKEND = Path(__file__).resolve().parents[1]
GENERIC = core.GENERIC_LOGIN_MESSAGE


# ------------------------------------------------------------------------------------------ cookie de sesion
@pytest.mark.parametrize("secure", [True, False])
def test_cookie_de_sesion_atributos_por_entorno(monkeypatch, secure):
    monkeypatch.setattr(S, "get", lambda: SimpleNamespace(cookie_secure=secure))
    r = Response()
    AR._set_cookie(r, "tok", core.load_config(lambda n: None))
    cookie = r.headers["set-cookie"]
    assert "deptit_session=tok" in cookie and "HttpOnly" in cookie and "SameSite=strict" in cookie
    assert "Path=/" in cookie and f"Max-Age={8 * 3600}" in cookie
    assert ("Secure" in cookie) is secure
    r2 = Response()
    AR._clear_cookie(r2)
    borrado = r2.headers["set-cookie"]
    assert "Max-Age=0" in borrado and "HttpOnly" in borrado and ("Secure" in borrado) is secure


def test_login_logout_y_cookie_en_el_flujo(client, repo):
    r = client.post("/auth/login", json={"email": "info@test.local", "password": repo.passwords["info@test.local"]},
                    headers={"x-deptit-request": "1"})
    assert r.status_code == 200 and "HttpOnly" in r.headers["set-cookie"] and "SameSite=strict" in r.headers[
        "set-cookie"]
    assert client.get("/auth/me").status_code == 200
    assert client.post("/auth/logout", headers={"x-deptit-request": "1"}).status_code in (200, 204)
    assert client.get("/auth/me").status_code == 401


# ------------------------------------------------------------------------------------------ CSRF / requests directos
def test_escrituras_directas_sin_cabecera_propia_rechazadas(client, repo):
    """Un request directo (sin el BFF) sin ``x-deptit-request`` no puede iniciar sesion ni escribir."""
    r = client.post("/auth/login", json={"email": "info@test.local", "password": repo.passwords["info@test.local"]})
    assert r.status_code == 403 and r.json()["error"]["code"] == "CSRF"
    assert client.post("/auth/login", json={}, headers={"x-deptit-request": "0"}).status_code == 403
    assert client.post("/auth/logout").status_code == 403


def test_sin_cors_en_el_backend():
    import main
    assert not [m for m in main.app.user_middleware if "CORS" in str(m.cls)]
    c = TestClient(main.app)
    r = c.options("/auth/login", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in {k.lower() for k in r.headers}


# ------------------------------------------------------------------------------------------ /health, /docs, errores
class _PoolFalso:
    def __init__(self, real=None, falla=False):
        self.real, self.falla = real, falla

    def connection(self, timeout=None):
        if self.falla:
            raise ConnectionError("base caida con datos internos: host=10.0.0.1 deptit_next_dev")
        return self.real.connection(timeout=timeout)


@pytest.fixture
def app_main():
    import main
    previo = getattr(main.app.state, "pool", None)
    yield main.app
    if previo is None:
        if hasattr(main.app.state, "pool"):
            del main.app.state.pool
    else:
        main.app.state.pool = previo


def test_health_minimo_sin_base_ni_rol(app_main):
    import db
    pool = db.create_pool()
    try:
        app_main.state.pool = _PoolFalso(pool)
        r = TestClient(app_main).get("/health")
        assert r.status_code == 200 and r.json() == {"status": "ok", "service": "deptit-next-backend"}
        for prohibido in ("deptit_next_dev", "deptit_next_app", "database", "db_user", "version", "C:\\"):
            assert prohibido not in r.text
        app_main.state.pool = _PoolFalso(falla=True)
        r = TestClient(app_main).get("/health")
        assert r.status_code == 503 and r.json() == {"status": "error", "service": "deptit-next-backend"}
        assert "10.0.0.1" not in r.text and "deptit_next_dev" not in r.text
    finally:
        pool.close()


def test_system_info_sigue_protegido(app_main, service, repo):
    previo = getattr(app_main.state, "auth", None)
    app_main.state.auth = service
    try:
        c = TestClient(app_main, base_url="http://localhost")
        assert c.get("/system/info").status_code == 401
        for email, esperado in (("info@test.local", 403), ("lector@test.local", 403)):
            c.post("/auth/login", json={"email": email, "password": repo.passwords[email]},
                   headers={"x-deptit-request": "1"})
            r = c.get("/system/info")
            assert r.status_code == esperado and "usuarios" not in r.text
    finally:
        if previo is None:
            del app_main.state.auth
        else:
            app_main.state.auth = previo


def _main_en_entorno(entorno: str) -> str:
    env = dict(os.environ, DEPTIT_ENTORNO=entorno)
    codigo = ("import main; from fastapi.testclient import TestClient as T; c=T(main.app); "
              "print(main.app.docs_url, main.app.redoc_url, main.app.openapi_url, "
              "c.get('/docs').status_code, c.get('/openapi.json').status_code, c.get('/redoc').status_code)")
    out = subprocess.run([sys.executable, "-B", "-c", codigo], cwd=BACKEND, env=env, capture_output=True, text=True,
                         timeout=120)
    assert out.returncode == 0, out.stderr[-2000:]
    return out.stdout.strip().splitlines()[-1]


def test_docs_y_openapi_solo_en_desarrollo():
    assert _main_en_entorno("desarrollo") == "/docs /redoc /openapi.json 200 200 200"
    for entorno in ("preproduccion", "produccion"):
        assert _main_en_entorno(entorno) == "None None None 404 404 404"


def test_api_docs_habilitada_por_entorno(monkeypatch):
    monkeypatch.setenv("DEPTIT_ENTORNO", "produccion")
    assert S.api_docs_habilitada() is False
    monkeypatch.setenv("DEPTIT_ENTORNO", "desarrollo")
    monkeypatch.setenv("DEPTIT_API_DOCS", "0")
    assert S.api_docs_habilitada() is False
    monkeypatch.setenv("DEPTIT_ENTORNO", "invalido")
    assert S.api_docs_habilitada() is False


def test_errores_sin_trazas_sql_ni_rutas(app_main):
    import asyncio
    import main
    req = SimpleNamespace(method="GET", url=SimpleNamespace(path="/x"))
    exc = RuntimeError('psycopg.errors.UndefinedTable: relation "secreta" at C:\\DEPTIT_NEXT\\backend\\x.py')
    r = asyncio.run(main._error_no_controlado(req, exc))
    assert r.status_code == 500
    body = r.body.decode()
    for prohibido in ("psycopg", "secreta", "C:\\", "Traceback", "RuntimeError"):
        assert prohibido not in body
    c = TestClient(app_main)
    r = c.post("/auth/login", json={"email": ["valor-sensible-xyz"], "password": "p"},
               headers={"x-deptit-request": "1"})
    assert r.status_code == 422 and "valor-sensible-xyz" not in r.text and r.json()["error"]["campos"] == ["email"]
    r = c.get("/no-existe")
    assert r.status_code == 404 and r.json()["error"]["code"] == "HTTP_404" and "detail" not in r.json()


# ------------------------------------------------------------------------------------------ origen del cliente
@pytest.mark.parametrize("peer,header,esperado", [
    ("127.0.0.1", "203.0.113.7", "203.0.113.7"),       # Next.js local confiable informa el origen
    ("::1", "2001:db8::1", "2001:db8::1"),
    ("127.0.0.1", None, None),                          # BFF sin proxy delante: sin origen -> solo limite por cuenta
    ("127.0.0.1", "no-es-ip", None),
    ("198.51.100.9", "203.0.113.7", "198.51.100.9"),    # peer NO confiable: la cabecera se ignora (no falsificable)
    ("testclient", "203.0.113.7", None),
    (None, "203.0.113.7", None),
])
def test_cadena_de_confianza_del_origen(peer, header, esperado):
    assert CI.resolve(peer, header, ("127.0.0.1", "::1")) == esperado


# ------------------------------------------------------------------------------------------ limite por IP
def _svc(repo, clock, **kw):
    return AuthService(repo, clock=clock, config_source=lambda n: None, ip_limits=lambda: (5, 900.0, 900.0), **kw)


def test_limite_por_origen_bloquea_rociado_de_cuentas(repo, clock):
    svc = _svc(repo, clock)
    ip = "203.0.113.7"
    for i in range(5):  # 5 cuentas distintas, una falla cada una: el limite por cuenta no alcanza
        assert svc.login(f"nadie{i}@test.local", "mal", ip).message == GENERIC
    bueno = repo.passwords["info@test.local"]
    r = svc.login("info@test.local", bueno, ip)
    assert r.user is None and r.message == GENERIC and r.status == 401  # misma respuesta que un fallo
    assert svc.login("info@test.local", bueno, "198.51.100.20").user is not None  # otro origen: entra
    assert svc.login("uba@test.local", repo.passwords["uba@test.local"], None).user is not None  # sin origen
    clock.advance(901)
    assert svc.login("info@test.local", bueno, ip).user is not None  # vencido el bloqueo


def test_el_exito_no_limpia_el_contador_del_origen(repo, clock):
    svc = _svc(repo, clock)
    ip = "203.0.113.8"
    for i in range(4):
        svc.login(f"x{i}@test.local", "mal", ip)
    assert svc.login("info@test.local", repo.passwords["info@test.local"], ip).user is not None
    svc.login("x9@test.local", "mal", ip)
    assert svc.login("coord@test.local", repo.passwords["coord@test.local"], ip).user is None
    claves_ip = [k for k in repo.throttle if k.startswith(core.IP_SUBJECT_PREFIX)]
    assert claves_ip == [core.ip_subject_key(ip)] and ip not in claves_ip[0]  # la IP no se guarda en claro


def test_el_limite_por_cuenta_sigue_identico(repo, clock):
    svc = _svc(repo, clock)
    for _ in range(5):
        svc.login("uba@test.local", "mal", None)
    assert svc.login("uba@test.local", repo.passwords["uba@test.local"], None).user is None
    assert not [k for k in repo.throttle if k.startswith(core.IP_SUBJECT_PREFIX)]


def test_ruta_de_login_usa_solo_el_origen_confiable(app, repo, clock):
    app.state.auth = _svc(repo, clock)
    c = TestClient(app, base_url="http://localhost", client=("127.0.0.1", 50000))
    for i in range(5):
        c.post("/auth/login", json={"email": f"n{i}@test.local", "password": "mal"},
               headers={"x-deptit-request": "1", CI.HEADER: "203.0.113.50"})
    r = c.post("/auth/login", json={"email": "info@test.local", "password": repo.passwords["info@test.local"]},
               headers={"x-deptit-request": "1", CI.HEADER: "203.0.113.50"})
    assert r.status_code == 401 and r.json()["error"]["message"] == GENERIC
    externo = TestClient(app, base_url="http://localhost", client=("198.51.100.77", 50000))
    r = externo.post("/auth/login", json={"email": "info@test.local", "password": repo.passwords["info@test.local"]},
                     headers={"x-deptit-request": "1", CI.HEADER: "203.0.113.50"})  # cabecera falsificada ignorada
    assert r.status_code == 200


# ------------------------------------------------------------------------------------------ contraseñas
def test_hash_versionado_y_compatibilidad_con_el_legado():
    salt = "ab" * 16
    legado = core.hash_password("clave-larga-1", salt)
    actual = core.hash_password_actual("clave-larga-1", salt)
    assert len(legado) == 64 and actual.startswith("pbkdf2_sha256$600000$")
    for h in (legado, actual):
        assert core.verify_password("clave-larga-1", salt, h) and not core.verify_password("otra", salt, h)
    assert core.needs_rehash(legado) and not core.needs_rehash(actual)
    assert core.needs_rehash(core.hash_password_actual("x", salt, 200000))
    for malo in ("pbkdf2_sha256$abc$00", "pbkdf2_sha256$0$00", "pbkdf2_sha256$600000", "pbkdf2_sha256$9999999$00"):
        assert core.verify_password("x", salt, malo) is False
    assert core.DUMMY_HASH_ACTUAL.startswith("pbkdf2_sha256$600000$")


def test_rehash_progresivo_al_autenticar_sin_cerrar_la_sesion(repo, clock):
    svc = AuthService(repo, clock=clock, config_source=lambda n: None)
    user = next(u for u in repo.users if u["email"] == "info@test.local")
    legado = user["password_hash"]
    assert core.needs_rehash(legado)
    r = svc.login("info@test.local", repo.passwords["info@test.local"])
    assert r.user is not None and user["password_hash"].startswith("pbkdf2_sha256$600000$")
    assert core.verify_password(repo.passwords["info@test.local"], user["salt"], user["password_hash"])
    token = svc.start_session(r)
    assert svc.validate(token).user["email"] == "info@test.local"  # la huella de credencial ya es la nueva
    antes = user["password_hash"]
    assert svc.login("info@test.local", repo.passwords["info@test.local"]).user is not None
    assert user["password_hash"] == antes  # ya actualizado: no se reescribe


def test_rehash_fallido_no_impide_el_login(repo, clock):
    class Roto(type(repo)):
        def update_password_hash(self, *a):
            raise ConnectionError("x")
    roto = Roto(clock)
    svc = AuthService(roto, clock=clock, config_source=lambda n: None)
    r = svc.login("info@test.local", roto.passwords["info@test.local"])
    assert r.user is not None
    assert svc.validate(svc.start_session(r)) is not None


def test_saas_crea_contraseñas_en_formato_actual():
    from saas import escrituras as E
    salt, h = E._hash("clave-provisoria-larga")
    assert h.startswith("pbkdf2_sha256$600000$") and core.verify_password("clave-provisoria-larga", salt, h)


# ------------------------------------------------------------------------------------------ subidas Excel
def _xlsx() -> bytes:
    from openpyxl import Workbook
    out = io.BytesIO()
    Workbook().save(out)
    return out.getvalue()


def _zip(entries, *, cifrado=False) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for nombre, data in entries:
            zf.writestr(nombre, data)
    data = bytearray(out.getvalue())
    if cifrado:  # zipfile no escribe entradas cifradas: se marca el bit 0 en los encabezados local y central
        for firma, desplazamiento in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
            i = data.find(firma)
            while i != -1:
                data[i + desplazamiento] |= 0x1
                i = data.find(firma, i + 4)
    return bytes(data)


def _bomba() -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", "<x/>")
        zf.writestr("xl/workbook.xml", "<x/>")
        with zf.open("xl/worksheets/sheet1.xml", "w", force_zip64=True) as f:
            bloque = b"\0" * (1 << 20)
            for _ in range(260):
                f.write(bloque)
    return out.getvalue()


def test_validacion_estructural_xlsx():
    assert uploads.problema_xlsx(_xlsx()) is None
    assert uploads.problema_xlsx(b"") == "vacio"
    assert uploads.problema_xlsx(b"%PDF-1.7 ...") == "sin firma ZIP"
    assert uploads.problema_xlsx(b"PK\x03\x04" + b"\0" * 100) == "ZIP ilegible"
    assert uploads.problema_xlsx(_zip([("hola.txt", "x")])) == "no es un libro Excel"
    assert uploads.problema_xlsx(_zip([(f"f{i}", "") for i in range(2001)])) == "demasiadas entradas"
    assert uploads.problema_xlsx(_zip([("[Content_Types].xml", "x"), ("xl/workbook.xml", "x")], cifrado=True)) == "cifrado"
    bomba = _bomba()
    assert len(bomba) < 2 * 1024 * 1024 and uploads.problema_xlsx(bomba) == "tamaño descomprimido excesivo"


def test_los_servicios_rechazan_contenido_no_excel_antes_del_lector():
    from extension.service import ExtensionError, ExtensionService
    from investigacion.service import InvestigacionError, InvestigacionService
    from materias.service import MateriasError, MateriasService
    from comisiones.service import ComisionesService
    # Comisiones conserva el contrato certificado: un Excel ilegible se informa como mensaje de error de la vista
    # previa (``_preview`` valida con ``uploads.problema_xlsx`` antes del lector; test_comisiones_service cubre el
    # camino real).  Los demas modulos responden 422 antes del lector.
    docx_disfrazado = _zip([("[Content_Types].xml", "x"), ("word/document.xml", "x")])
    for contenido in (docx_disfrazado, _bomba(), b"PK\x03\x04basura"):
        b64 = base64.b64encode(contenido).decode()
        for llamar, error in ((lambda: InvestigacionService._contenido({"archivo": b64}), InvestigacionError),
                              (lambda: ExtensionService._contenido({"archivo": b64}), ExtensionError),
                              (lambda: MateriasService._decodificar_excel(b64), MateriasError)):
            with pytest.raises(error) as exc:
                llamar()
            assert exc.value.status == 422
    valido = _xlsx()
    b64 = base64.b64encode(valido).decode()
    assert InvestigacionService._contenido({"archivo": b64}) == valido
    assert ExtensionService._contenido({"archivo": b64}) == valido
    assert MateriasService._decodificar_excel(b64) == valido and ComisionesService._excel_bytes(b64) == valido


def test_carga_integral_valida_contenido_y_extension():
    from docentes.service import DocentesError
    from integraciones.carga_integral import CargaIntegralService
    archivo = lambda nombre, contenido: SimpleNamespace(nombre=nombre, contenido=contenido)  # noqa: E731
    for nombre, contenido in (("x.xlsx", _bomba()), ("x.xlsx", _zip([("a", "b")])), ("x.xls", _xlsx())):
        with pytest.raises(DocentesError) as exc:
            CargaIntegralService._contenido(archivo(nombre, contenido))
        assert exc.value.status == 422
    assert CargaIntegralService._contenido(archivo("modelo.xlsx", _xlsx()))[:4] == b"PK\x03\x04"
