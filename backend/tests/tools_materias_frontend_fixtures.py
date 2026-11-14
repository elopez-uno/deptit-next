"""Genera las respuestas REALES de la API de Materias (UNO, usuario de departamento de prueba) para los tests de
frontend: overview y /materias/plan para cada (escuela, carrera_id).  Solo lectura; la transaccion se revierte."""
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
from materias.routes import router as materias_router  # noqa: E402
from materias_support import EXTRA_DEPARTMENTS, FakeAuditStore, make_materias  # noqa: E402

OUT = Path(r"C:\DEPTIT_NEXT\frontend\tests\fixtures\materias_uno.json")
CSRF = {"X-DEPTIT-Request": "1"}

s = db.load_settings()
db.check_config(s)
conn = psycopg.connect(s["database_url"], application_name="deptit_next_tests")
db.verify_identity(conn)
repo = FakeRepo(Clock())
repo.departments_rows.extend(dict(d) for d in EXTRA_DEPARTMENTS)
auth = AuthService(repo, config_source=lambda n: None)


@contextmanager
def sp(c):
    with c.transaction():
        yield c


app = FastAPI()
app.include_router(auth_router)
app.include_router(materias_router)
app.state.auth = auth
app.state.materias = make_materias(auth, FakeAuditStore(), conn, transaction=lambda: sp(conn))
client = TestClient(app, base_url="http://localhost")
assert client.post("/auth/login", json={"email": "info@test.local", "password": repo.passwords["info@test.local"]},
                   headers=CSRF).status_code == 200
overview = client.get("/materias").json()
assert overview["contexto"]["institucion"]["id"] == 1
ids = [None] + [c["id"] for c in overview["carreras"]]
plan = {}
for escuela in ["Todas"] + overview["escuelas"]:
    for cid in ids:
        r = client.post("/materias/plan", json={"escuela": escuela, "carrera_id": cid}, headers=CSRF)
        assert r.status_code == 200, r.text
        plan[json.dumps({"escuela": escuela, "carrera_id": cid}, ensure_ascii=False)] = r.json()
OUT.write_text(json.dumps({"overview": overview, "plan": plan}, ensure_ascii=False), encoding="utf-8")
conn.rollback()
conn.close()
abog = plan[json.dumps({"escuela": "Todas", "carrera_id": 46})]
print("respuestas:", len(plan), "| Abogacia:", abog["carrera"]["nombre"], len(abog["plan"]), "materias")
