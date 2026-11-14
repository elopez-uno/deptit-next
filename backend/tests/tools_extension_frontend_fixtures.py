"""Genera las respuestas REALES de la API de Extension (UNO, departamento 2) para los tests de frontend: overview
(usuario de departamento y solo lectura), vigentes + ficha, historial, asignar (proyectos y detalle del primero),
asignaciones del periodo abierto, edicion (proyectos, asignaciones y opciones de la primera), suspension, archivo y
actos.  Solo lectura; la transaccion se revierte."""
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
from extension.routes import router as extension_router  # noqa: E402
from extension_support import EXTRA_DEPARTMENTS, FakeAuditStore, make_extension  # noqa: E402

OUT = Path(r"C:\DEPTIT_NEXT\frontend\tests\fixtures\extension_uno.json")
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
app.include_router(extension_router)
app.state.auth = auth
app.state.extension = make_extension(auth, FakeAuditStore(), conn, transaction=lambda: sp(conn))


def client_for(email: str) -> TestClient:
    c = TestClient(app, base_url="http://localhost")
    assert c.post("/auth/login", json={"email": email, "password": repo.passwords[email]}, headers=CSRF).status_code == 200
    return c


def ok(r):
    assert r.status_code == 200, r.text
    return r.json()


try:
    c = client_for("admin@test.local")
    lector = client_for("lector@test.local")
    p = lambda ruta, body=None: ok(c.post(f"/extension/{ruta}", json=body or {}, headers=CSRF))  # noqa: E731
    out = {"overview": ok(c.get("/extension")), "lector": ok(lector.get("/extension"))}
    out["vigentes"] = p("vigentes")
    out["ficha"] = p("vigentes/ficha", {"proyecto_id": out["vigentes"]["filas"][0]["id"]})
    out["historial"] = p("historial")
    out["asignar_proyectos"] = p("asignar/proyectos")
    out["asignar_detalle"] = p("asignar/detalle", {"proyecto_id": out["asignar_proyectos"]["proyectos"][0]["id"]})
    out["asignaciones"] = p("asignaciones", {"periodo_id": out["overview"]["abierto"]["id"]})
    out["editar_proyectos"] = p("editar/proyectos")
    out["editar_asignaciones"] = p("editar/asignaciones")
    out["opciones"] = p("editar/asignacion/opciones", {"asignacion_id": out["editar_asignaciones"]["filas"][0]["id"]})
    out["suspender"] = p("bajas/suspender/proyectos")
    out["archivar"] = p("bajas/archivar/proyectos")
    out["actos"] = p("actos")
    out["alertas"] = p("alertas")
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("fixtures:", OUT, OUT.stat().st_size)
finally:
    conn.rollback()
    conn.close()
