"""Genera las respuestas REALES de la API de Actividades Especiales (UNO, departamento 1) para los tests de frontend:
overview (usuario de departamento, superadmin y solo lectura), actividades del periodo abierto, asignar (actividades y
selector), historial, editar (actividades y participaciones de la primera).  Solo lectura; la transaccion se revierte."""
import json
import sys
import warnings
from contextlib import contextmanager
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import db  # noqa: E402
from auth.routes import router as auth_router  # noqa: E402
from auth.service import AuthService  # noqa: E402
from conftest import Clock, FakeRepo  # noqa: E402
from actividades_especiales.routes import router as actividades_router  # noqa: E402
from actividades_support import EXTRA_DEPARTMENTS, FakeAuditStore, make_actividades  # noqa: E402

OUT = Path(r"C:\DEPTIT_NEXT\frontend\tests\fixtures\actividades_especiales_uno.json")
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
app.include_router(actividades_router)
app.state.auth = auth
app.state.actividades_especiales = make_actividades(auth, FakeAuditStore(), conn, transaction=lambda: sp(conn))


def client_for(email: str) -> TestClient:
    c = TestClient(app, base_url="http://localhost")
    assert c.post("/auth/login", json={"email": email, "password": repo.passwords[email]}, headers=CSRF).status_code == 200
    return c


def ok(r):
    assert r.status_code == 200, r.text
    return r.json()


try:
    c = client_for("info@test.local")
    sup = client_for("super@test.local")
    assert sup.put("/auth/context", json={"institucion_id": 1, "departamento_id": 1}, headers=CSRF).status_code == 200
    lector = client_for("lector@test.local")
    p = lambda ruta, body=None: ok(c.post(f"/actividades-especiales/{ruta}", json=body or {}, headers=CSRF))  # noqa: E731
    out = {"overview": ok(c.get("/actividades-especiales")), "super": ok(sup.get("/actividades-especiales")),
           "lector": ok(lector.get("/actividades-especiales"))}
    pid = out["overview"]["abierto"]["id"]
    out["periodo"] = p("periodo", {"periodo_id": pid})
    out["asignar_datos"] = p("asignar/datos", {"periodo_id": pid})
    out["historial"] = p("historial")
    out["editar_actividades"] = p("editar/actividades")
    out["participaciones"] = p("editar/participaciones", {"actividad_id": out["editar_actividades"]["filas"][0]["id"]})
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("fixtures:", OUT, OUT.stat().st_size)
finally:
    conn.rollback()
    conn.close()
