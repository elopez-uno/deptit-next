"""Genera las respuestas REALES de la API de Resoluciones y respaldos (UNO, departamento 1) para los tests de frontend:
overview (usuario de departamento, superadmin y solo lectura), detalle del primer documento, tabla de docentes del
periodo actual y de proyectos de investigacion.  Solo lectura (``SET TRANSACTION READ ONLY``); la transaccion se revierte.
No incluye binarios: el listado y el detalle nunca los traen (D-AK12)."""
import json
import sys
import warnings
from contextlib import contextmanager
from pathlib import Path

warnings.filterwarnings("ignore")
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import db  # noqa: E402
from auth.routes import router as auth_router  # noqa: E402
from auth.service import AuthService  # noqa: E402
from conftest import Clock, FakeRepo  # noqa: E402
from resoluciones_respaldos.routes import router as resoluciones_router  # noqa: E402
from resoluciones_support import EXTRA_DEPARTMENTS, FakeAuditStore, make_resoluciones  # noqa: E402

OUT = Path(r"C:\DEPTIT_NEXT\frontend\tests\fixtures\resoluciones_uno.json")
CSRF = {"X-DEPTIT-Request": "1"}

s = db.load_settings()
db.check_config(s)
conn = psycopg.connect(s["database_url"], application_name="deptit_next_tests")
db.verify_identity(conn)
conn.execute("SET TRANSACTION READ ONLY")
repo = FakeRepo(Clock())
repo.departments_rows.extend(dict(d) for d in EXTRA_DEPARTMENTS)
auth = AuthService(repo, config_source=lambda n: None)


@contextmanager
def sp(c):
    with c.transaction():
        yield c


app = FastAPI()
app.include_router(auth_router)
app.include_router(resoluciones_router)
app.state.auth = auth
app.state.resoluciones_respaldos = make_resoluciones(auth, FakeAuditStore(), conn, transaction=lambda: sp(conn))


def client_for(email: str) -> TestClient:
    c = TestClient(app, base_url="http://localhost")
    assert c.post("/auth/login", json={"email": email, "password": repo.passwords[email]}, headers=CSRF).status_code == 200
    return c


def get(c, path=""):
    r = c.get(f"/resoluciones-respaldos{path}")
    assert r.status_code == 200, r.text
    return r.json()


def post(c, path, body):
    r = c.post(f"/resoluciones-respaldos/{path}", json=body, headers=CSRF)
    assert r.status_code == 200, r.text
    return r.json()


try:
    dep = client_for("info@test.local")
    overview = get(dep)
    primero = overview["repositorio"]["filas"][0]["id"]
    sup = client_for("super@test.local")
    assert sup.put("/auth/context", json={"institucion_id": 1, "departamento_id": 1, "consolidado": False},
                    headers=CSRF).status_code == 200
    fx = {
        "overview": overview,
        "super": get(sup),
        "lector": get(client_for("lector@test.local")),
        "detalle": post(dep, "documento", {"id": primero}),
        "docentes": post(dep, "docentes", {"modo": "Designaciones activas del período actual"}),
        "proyectos": post(dep, "proyectos", {"tipo": "investigacion"}),
    }
    texto = json.dumps(fx, ensure_ascii=False, indent=1)
    assert "%PDF" not in texto.replace("%PDF-.", "") and "archivo_pdf" not in texto
    OUT.write_text(texto, encoding="utf-8")
    print("fixtures:", OUT, len(texto), "bytes")
finally:
    conn.rollback()
    conn.close()
