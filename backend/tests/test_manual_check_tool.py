"""Regresion del HTTP 500 en la prueba manual: ``next dev`` con su worker caido respondia a /api/auth/login con la
pagina de error HTML de Next.js (500).  La herramienta debe detectarlo ANTES de pedir credenciales y nunca
volcar el cuerpo ni fallar con un segundo traceback (JSONDecodeError)."""

from email.message import Message

import pytest

import tools_auth_manual_check as tool

NEXT_500_HTML = ('<!DOCTYPE html><html><head><script id="__NEXT_DATA__" type="application/json">'
                 '{"props":{"pageProps":{"statusCode":500}},"page":"/_error","err":{"message":'
                 '"Jest worker encountered 2 child process exceptions, exceeding retry limit"}}</script>'
                 '</head><body></body></html>')
LOGIN_REJECTED = '{"error":{"code":"LOGIN_REJECTED","message":"Credenciales inválidas."}}'
SECRET = "S3creta-no-debe-salir"


def headers(content_type):
    h = Message()
    h["Content-Type"] = content_type
    return h


@pytest.fixture
def no_prompt(monkeypatch):
    def forbidden(*_a, **_k):
        raise AssertionError("no debe pedir credenciales")
    monkeypatch.setattr("builtins.input", forbidden)
    monkeypatch.setattr(tool.getpass, "getpass", forbidden)


def test_next_html_500_is_reported_safely_before_asking_credentials(monkeypatch, capsys, no_prompt):
    calls = []

    def fake_http(method, path, body=None, cookie=None):
        calls.append((method, path, body))
        return 500, NEXT_500_HTML, headers("text/html; charset=utf-8")

    monkeypatch.setattr(tool, "http", fake_http)
    assert tool.main() == 1
    out = capsys.readouterr().out
    assert "status=500" in out and "página de error HTML de Next.js" in out and "cuerpo omitido" in out
    assert "<html" not in out and "__NEXT_DATA__" not in out and "Traceback" not in out
    assert calls == [("POST", "/api/auth/login", {"email": "", "password": ""})]


def test_non_json_after_real_login_does_not_raise_or_leak(monkeypatch, capsys):
    responses = iter([(401, LOGIN_REJECTED, headers("application/json")),
                      (500, NEXT_500_HTML, headers("text/html"))])
    monkeypatch.setattr(tool, "http", lambda *a, **k: next(responses))
    monkeypatch.setattr("builtins.input", lambda _p: "super@test.local")
    monkeypatch.setattr(tool.getpass, "getpass", lambda _p: SECRET)
    assert tool.main() == 1
    out = capsys.readouterr().out
    assert "FAIL  login con credenciales válidas  status=500" in out
    assert "respuesta inesperada: status=500" in out
    assert SECRET not in out and "<html" not in out and "Traceback" not in out


def test_rejected_login_shows_backend_message(monkeypatch, capsys):
    monkeypatch.setattr(tool, "http", lambda *a, **k: (401, LOGIN_REJECTED, headers("application/json")))
    monkeypatch.setattr("builtins.input", lambda _p: "super@test.local")
    monkeypatch.setattr(tool.getpass, "getpass", lambda _p: SECRET)
    assert tool.main() == 1
    out = capsys.readouterr().out
    assert "Mensaje: Credenciales inválidas." in out and SECRET not in out


def test_unreachable_next_is_reported_without_traceback(monkeypatch, capsys, no_prompt):
    def refused(*_a, **_k):
        raise tool.urllib.error.URLError(ConnectionRefusedError())

    monkeypatch.setattr(tool, "http", refused)
    assert tool.main() == 1
    assert "No se pudo conectar con http://localhost:3001 (URLError)" in capsys.readouterr().out


def test_preflight_empty_login_does_not_touch_throttle_or_users(client, repo):
    """El chequeo previo de la herramienta no debe consumir intentos del limite de login."""
    r = client.post("/auth/login", json={"email": "", "password": ""}, headers={"X-DEPTIT-Request": "1"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "LOGIN_REJECTED"
    assert not {"lock_state", "register_failure", "users_by_email", "reset"} & set(repo.calls)
    assert repo.throttle == {}
