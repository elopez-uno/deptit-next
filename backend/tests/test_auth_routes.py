"""Contrato HTTP: cookie HttpOnly, sin secretos en respuestas, CSRF, logout y rechazos sin sesion."""

import json

CSRF = {"X-DEPTIT-Request": "1"}
FORBIDDEN_IN_BODY = ("salt", "password_hash", "password", "DATABASE_URL", "postgresql://", "deptit_session")


def do_login(client, repo, email, password=None):
    body = {"email": email, "password": repo.passwords[email] if password is None else password}
    return client.post("/auth/login", json=body, headers=CSRF)


def assert_clean(response, repo):
    text = response.text
    for word in FORBIDDEN_IN_BODY:
        assert word not in text, word
    for u in repo.users:
        assert u["salt"] not in text and u["password_hash"] not in text
    for pwd in repo.passwords.values():
        assert pwd not in text


def test_login_sets_httponly_strict_cookie_and_returns_no_secrets(client, repo):
    r = do_login(client, repo, "info@test.local")
    assert r.status_code == 200
    cookie = r.headers["set-cookie"]
    assert cookie.startswith("deptit_session=") and "HttpOnly" in cookie and "SameSite=strict" in cookie
    assert "Path=/" in cookie and "Max-Age=28800" in cookie
    token = cookie.split(";")[0].split("=", 1)[1]
    assert token not in r.text
    assert_clean(r, repo)
    data = r.json()
    assert data["usuario"]["rol"] == "usuario_departamento"
    assert data["contexto"]["institucion"]["id"] == 1 and data["contexto"]["departamento"]["id"] == 1
    assert r.headers["cache-control"] == "no-store"


def test_me_requires_session(client):
    r = client.get("/auth/me")
    assert r.status_code == 401 and r.json()["error"]["code"] == "NO_SESSION"


def test_me_with_session_then_logout_invalidates(client, repo):
    do_login(client, repo, "coord@test.local")
    r = client.get("/auth/me")
    assert r.status_code == 200 and r.json()["contexto"]["vista"] == "consolidado"
    assert_clean(r, repo)
    token = client.cookies.get("deptit_session")
    r = client.post("/auth/logout", headers=CSRF)
    assert r.status_code == 204 and "deptit_session=" in r.headers["set-cookie"]
    assert client.get("/auth/me").status_code == 401
    client.cookies.set("deptit_session", token)  # reutilizar el token viejo
    assert client.get("/auth/me").status_code == 401


def test_rejections_are_uniform_and_set_no_cookie(client, repo):
    for email, pwd in [("info@test.local", "mal"), ("nadie@test.local", "mal"),
                       ("inactivo@test.local", None)]:
        r = do_login(client, repo, email, pwd)
        assert r.status_code == 401
        assert r.json()["error"]["message"] == "Credenciales inválidas o acceso temporalmente no disponible."
        assert "deptit_session=\"\"" in r.headers.get("set-cookie", "") or "Max-Age=0" in r.headers.get("set-cookie", "")


def test_csrf_header_required_for_state_changes(client, repo):
    r = client.post("/auth/login", json={"email": "info@test.local", "password": repo.passwords["info@test.local"]})
    assert r.status_code == 403
    do_login(client, repo, "super@test.local")
    assert client.put("/auth/context", json={"institucion_id": 1}).status_code == 403
    assert client.post("/auth/logout").status_code == 403
    assert client.get("/auth/me").status_code == 200  # el logout sin cabecera no cerro la sesion


def test_context_endpoints(client, repo):
    do_login(client, repo, "super@test.local")
    opts = client.get("/auth/context/options").json()
    assert [i["id"] for i in opts["instituciones"]] == [2, 5, 1]
    r = client.put("/auth/context", json={"institucion_id": 1, "departamento_id": 1}, headers=CSRF)
    assert r.status_code == 200 and r.json()["contexto"]["departamento"]["id"] == 1
    r = client.put("/auth/context", json={"institucion_id": 1, "departamento_id": 5}, headers=CSRF)
    assert r.status_code == 403 and r.json()["error"]["code"] == "CONTEXT_NOT_ALLOWED"


def test_departmental_user_cannot_change_context(client, repo):
    do_login(client, repo, "info@test.local")
    r = client.put("/auth/context", json={"departamento_id": 2}, headers=CSRF)
    assert r.status_code == 403
    assert client.get("/auth/me").json()["contexto"]["departamento"]["id"] == 1


def test_sessions_are_isolated_between_clients(app, repo):
    from fastapi.testclient import TestClient
    a, b = TestClient(app, base_url="http://localhost"), TestClient(app, base_url="http://localhost")
    do_login(a, repo, "super@test.local")
    do_login(b, repo, "uba@test.local")
    a.put("/auth/context", json={"institucion_id": 1, "departamento_id": 2}, headers=CSRF)
    assert a.get("/auth/me").json()["usuario"]["rol"] == "superadmin"
    me_b = b.get("/auth/me").json()
    assert me_b["usuario"]["id"] == 4 and me_b["contexto"]["departamento"]["id"] == 5
    a.post("/auth/logout", headers=CSRF)
    assert b.get("/auth/me").status_code == 200


def test_revocation_reaches_next_request(client, repo):
    do_login(client, repo, "info@test.local")
    repo.users[2]["estado"] = "Inactivo"
    r = client.get("/auth/me")
    assert r.status_code == 401 and r.json()["error"]["code"] == "USER_INACTIVE"
    assert "cambiaron tus datos de acceso" in r.json()["error"]["message"]


def test_db_failure_returns_503_without_details(client, repo):
    do_login(client, repo, "info@test.local")
    repo.fail = True
    r = client.get("/auth/me")
    assert r.status_code == 503 and "db down" not in r.text
    repo.fail = False
    assert client.get("/auth/me").status_code == 200


def test_modules_and_permissions_payload(client, repo):
    do_login(client, repo, "coord@test.local")
    mods = client.get("/auth/me").json()["modulos"]
    assert [m["clave"] for m in mods] == ["inicio", "consolidado", "materias"]
    materias = next(m for m in mods if m["clave"] == "materias")
    assert materias["puede_escribir"] is True and materias["puede_borrar"] is True
    client.post("/auth/logout", headers=CSRF)
    do_login(client, repo, "lector@test.local")
    mods = client.get("/auth/me").json()["modulos"]
    assert not any(m["puede_escribir"] or m["puede_borrar"] for m in mods)
    json.dumps(mods)
