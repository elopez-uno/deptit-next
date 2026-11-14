"""6A-B4 (R-B3-10): el encabezado de la sesión nombra la institución ACTIVA; sin universidad fija en ningún lado.

- ``contexto.institucion_encabezado`` = institución del contexto resuelto (no la de pertenencia del usuario).
- Sin institución activa: cadena vacía (no hay "Universidad Nacional del Oeste" por defecto).
- Guardia: ningún literal productivo de backend/auth ni del frontend nombra una universidad concreta.
"""
from pathlib import Path

from test_auth_routes import CSRF, do_login

RAIZ = Path(__file__).resolve().parents[2]
UNO, UBA = "Universidad Nacional del Oeste", "Universidad de Buenos Aires"


def _encabezado(client) -> str:
    return client.get("/auth/me").json()["contexto"]["institucion_encabezado"]


def _contexto(client, **ids):
    r = client.put("/auth/context", json=ids, headers=CSRF)
    assert r.status_code == 200, r.text
    return r.json()["contexto"]["institucion_encabezado"]


def test_superadmin_sin_institucion_activa_no_muestra_ninguna(client, repo):
    repo.institutions_rows = []  # sin institución resoluble: no hay contexto institucional por defecto
    do_login(client, repo, "super@test.local")
    me = client.get("/auth/me")
    assert me.json()["contexto"]["institucion"] is None
    assert me.json()["contexto"]["institucion_encabezado"] == ""
    assert UNO not in me.text


def test_cambio_de_contexto_uno_otra_uno_sin_arrastre(client, repo):
    do_login(client, repo, "super@test.local")
    assert _contexto(client, institucion_id=1, departamento_id=1) == UNO
    assert _contexto(client, institucion_id=2, departamento_id=5) == UBA
    assert _encabezado(client) == UBA
    assert _contexto(client, institucion_id=1, departamento_id=2) == UNO
    assert _encabezado(client) == UNO


def test_pertenencia_uno_operando_en_otra_institucion(client, repo):
    repo.add_user(9, "superuno@test.local", "superadmin", 1, None)
    do_login(client, repo, "superuno@test.local")
    assert _contexto(client, institucion_id=2, departamento_id=5) == UBA
    me = client.get("/auth/me").json()
    assert me["pertenencia"]["institucion"]["nombre"] == UNO  # la pertenencia se informa, pero no encabeza
    assert me["contexto"]["institucion_encabezado"] == UBA


def test_usuario_departamental_ve_su_institucion(client, repo):
    do_login(client, repo, "uba@test.local")
    assert _encabezado(client) == UBA


def test_sin_universidad_fija_en_codigo_productivo():
    fuentes = [RAIZ / "backend" / "auth" / "routes.py", *(RAIZ / "frontend" / "src").rglob("*.ts*")]
    hallazgos = [str(p) for p in fuentes if UNO in p.read_text(encoding="utf-8")]
    assert hallazgos == []
    assert not (RAIZ / "frontend" / "public").exists() or not any((RAIZ / "frontend" / "public").glob("*.svg"))
