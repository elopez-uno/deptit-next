"""Genera las respuestas REALES de la API de Sueldos (UNO, departamento 1) para los tests de frontend: overview
(usuario de departamento, solo lectura y superadmin en la institucion 5 sin departamentos), escalas 10/2026, tabla
salarial (por defecto y Exclusiva + Doctor), plantel 2026-2 (primeras filas) y 2026-1.  Solo lectura; la transaccion se
revierte."""
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
from sueldos.routes import router as sueldos_router  # noqa: E402
from sueldos_support import EXTRA_DEPARTMENTS, FakeAuditStore, make_sueldos  # noqa: E402

OUT = Path(r"C:\DEPTIT_NEXT\frontend\tests\fixtures\sueldos_uno.json")
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
app.include_router(sueldos_router)
app.state.auth = auth
app.state.sueldos = make_sueldos(auth, FakeAuditStore(), conn, transaction=lambda: sp(conn))


def client_for(email: str) -> TestClient:
    c = TestClient(app, base_url="http://localhost")
    assert c.post("/auth/login", json={"email": email, "password": repo.passwords[email]}, headers=CSRF).status_code == 200
    return c


def ok(r):
    assert r.status_code == 200, r.text
    return r.json()


try:
    dep = client_for("info@test.local")
    overview = ok(dep.get("/sueldos"))
    p = {x["nombre"]: x["id"] for x in overview["plantel"]["periodos"]}
    plantel = ok(dep.post("/sueldos/plantel", json={"periodo_id": p["2026-2"]}, headers=CSRF))
    plantel["filas"] = plantel["filas"][:6]
    plantel_hist = ok(dep.post("/sueldos/plantel", json={"periodo_id": p["2026-1"]}, headers=CSRF))
    plantel_hist["filas"] = plantel_hist["filas"][:3]
    sup = client_for("super@test.local")
    assert sup.put("/auth/context", json={"institucion_id": 5, "departamento_id": None, "consolidado": False},
                    headers=CSRF).status_code == 200
    data = {
        "overview": overview,
        "lector": ok(client_for("lector@test.local").get("/sueldos")),
        "sin_departamento": ok(sup.get("/sueldos")),
        "escalas": ok(dep.post("/sueldos/escalas", json={"anio": 2026, "mes": 10}, headers=CSRF)),
        "escalas_sin_escala": ok(sup.post("/sueldos/escalas", json={"anio": 2026, "mes": 10}, headers=CSRF)),
        "tabla": ok(dep.post("/sueldos/tabla", json={"mes_referencia": None, "dedicacion": "Simple", "nivel": ""},
                             headers=CSRF)),
        "tabla_exclusiva": ok(dep.post("/sueldos/tabla", json={"mes_referencia": "2026-06", "dedicacion": "Exclusiva",
                                                               "nivel": "Doctor"}, headers=CSRF)),
        "plantel": plantel,
        "plantel_hist": plantel_hist,
    }
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print("ok", OUT, {k: (len(v) if isinstance(v, (list, dict)) else v) for k, v in data.items()})
finally:
    conn.rollback()
    conn.close()
