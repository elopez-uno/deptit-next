"""Contrato HTTP de Docentes: sesion revalidada, expiracion, CSRF, tenant del cliente ignorado y respuestas limpias.
Base real con ROLLBACK; usuarios del FakeRepo con contrasenas aleatorias (sin credenciales humanas)."""

import pytest

from docentes_support import audit_store, db_conn, docentes, free_cuil, http  # noqa: F401  (fixtures)

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")

CSRF = {"X-DEPTIT-Request": "1"}
FORBIDDEN = ("salt", "password_hash", "postgresql://", "DATABASE_URL", "deptit_session", "SELECT ", "UPDATE ",
             "DELETE ", "Traceback", "psycopg", "regexp_replace")
C1 = "27-99000021-0"
POSTS = ["ficha", "verificar-cuil", "alta", "editar", "eliminar", "prestado", "finalizar-prestamo", "reparar-cuil",
         "carga-rapida/previsualizar", "carga-rapida"]


def login(client, repo, email):
    r = client.post("/auth/login", json={"email": email, "password": repo.passwords[email]}, headers=CSRF)
    assert r.status_code == 200
    return r


def clean(response, repo):
    for word in FORBIDDEN:
        assert word not in response.text, word
    for pwd in repo.passwords.values():
        assert pwd not in response.text
    assert response.headers["cache-control"] == "no-store"


def test_requires_session(http):
    for path in ("", "/prestables", "/modelo-excel"):
        r = http.get(f"/docentes{path}")
        assert r.status_code == 401 and r.json()["error"]["code"] == "NO_SESSION"
    for path in POSTS:
        assert http.post(f"/docentes/{path}", json={}, headers=CSRF).status_code == 401


def test_posts_require_proxy_header(http, repo, db_conn):
    login(http, repo, "info@test.local")
    free_cuil(db_conn, C1)
    for path in POSTS:
        r = http.post(f"/docentes/{path}", json={"cuil": C1, "apellido": "A", "nombres": "B"})
        assert r.status_code == 403 and r.json()["error"]["code"] == "CSRF"
    assert db_conn.execute("SELECT count(*) FROM docentes WHERE cuil = %s", [C1]).fetchone()[0] == 0


def test_expired_session_is_rejected(http, repo, clock):
    login(http, repo, "info@test.local")
    assert http.get("/docentes").status_code == 200
    clock.advance(30 * 60)
    r = http.get("/docentes")
    assert r.status_code == 401 and r.json()["error"]["code"] == "IDLE_TIMEOUT"
    assert http.get("/docentes").json()["error"]["code"] == "NO_SESSION"


def test_overview_clean_and_scoped(http, repo, db_conn):
    login(http, repo, "info@test.local")
    r = http.get("/docentes")
    assert r.status_code == 200
    clean(r, repo)
    data = r.json()
    assert data["contexto"]["departamento"]["id"] == 1
    n = db_conn.execute("SELECT count(*) FROM docentes WHERE institucion_id = 1 AND departamento_id = 1").fetchone()[0]
    assert len(data["docentes"]) == n
    assert all(len(row["huella"]) == 32 for row in data["docentes"])


def test_client_tenant_fields_are_ignored(http, repo, db_conn):
    login(http, repo, "info@test.local")
    free_cuil(db_conn, C1)
    body = {"apellido": "Tenant", "nombres": "Prueba", "cuil": C1, "fecha_alta": "2026-10-26",
            "institucion_id": 2, "departamento_id": 5, "tenant_scope_departamento_id": 5}
    r = http.post("/docentes/alta", json=body, headers=CSRF)
    assert r.status_code == 200, r.text
    clean(r, repo)
    assert db_conn.execute("SELECT institucion_id, departamento_id FROM docentes WHERE cuil = %s",
                           [C1]).fetchall() == [(1, 1)]


def test_read_only_role_gets_controlled_denial(http, repo, db_conn):
    login(http, repo, "lector@test.local")
    free_cuil(db_conn, C1)
    r = http.post("/docentes/alta", json={"apellido": "A", "nombres": "B", "cuil": C1}, headers=CSRF)
    assert r.status_code == 403
    clean(r, repo)
    assert "Tu usuario es de solo lectura" in r.json()["error"]["message"]


def test_delete_denied_for_department_user(http, repo, db_conn):
    login(http, repo, "info@test.local")
    cuil = db_conn.execute("SELECT cuil FROM docentes WHERE institucion_id = 1 AND departamento_id = 1 ORDER BY id "
                           "LIMIT 1").fetchone()[0]
    r = http.post("/docentes/eliminar", json={"cuil": cuil, "huella": "x", "confirmar": True}, headers=CSRF)
    assert r.status_code == 403 and "docentes.delete" in r.json()["error"]["message"]
    assert db_conn.execute("SELECT count(*) FROM docentes WHERE cuil = %s AND departamento_id = 1",
                           [cuil]).fetchone()[0] == 1


def test_excel_download(http, repo):
    login(http, repo, "lector@test.local")
    r = http.get("/docentes/modelo-excel")
    assert r.status_code == 200 and r.content[:2] == b"PK"
    assert r.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert "modelo_carga_rapida_docentes.xlsx" in r.headers["content-disposition"]


def test_invalid_body_types_are_controlled(http, repo):
    login(http, repo, "info@test.local")
    r = http.post("/docentes/eliminar", json={"cuil": "x", "confirmar": "si"}, headers=CSRF)
    assert r.status_code == 422
    clean(r, repo)
    r = http.post("/docentes/alta", json={"apellido": "A", "nombres": "B", "cuil": "20-12345678-9",
                                          "antiguedad_anios": "5"}, headers=CSRF)
    assert r.status_code in (409, 422)
    clean(r, repo)
