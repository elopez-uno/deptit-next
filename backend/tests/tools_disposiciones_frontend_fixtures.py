"""Genera las respuestas REALES de la API de Disposiciones (UNO, departamento 1) para los tests de frontend:
overview (usuario de departamento con plantilla sintetica, superadmin, solo lectura y sin plantilla), periodo abierto
(padron numerado), vista de un docente con designaciones y de uno mixto/no docente si existe, vista previa e historial.
Solo lectura; la transaccion se revierte y la raiz documental es un directorio temporal que se borra al terminar."""
import json
import shutil
import sys
import tempfile
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
import disposiciones_plantilla as P  # noqa: E402
from auth.routes import router as auth_router  # noqa: E402
from auth.service import AuthService  # noqa: E402
from conftest import Clock, FakeRepo  # noqa: E402
from disposiciones.routes import router as disposiciones_router  # noqa: E402
from disposiciones_support import EXTRA_DEPARTMENTS, FakeAuditStore, make_disposiciones  # noqa: E402

OUT = Path(r"C:\DEPTIT_NEXT\frontend\tests\fixtures\disposiciones_uno.json")
CSRF = {"X-DEPTIT-Request": "1"}

s = db.load_settings()
db.check_config(s)
conn = psycopg.connect(s["database_url"], application_name="deptit_next_tests")
db.verify_identity(conn)
conn.execute("SET TRANSACTION READ ONLY")
repo = FakeRepo(Clock())
repo.departments_rows.extend(dict(d) for d in EXTRA_DEPARTMENTS)
auth = AuthService(repo, config_source=lambda n: None)
root = Path(tempfile.mkdtemp(prefix="zznext_dispo_fx_"))


@contextmanager
def sp(c):
    with c.transaction():
        yield c


app = FastAPI()
app.include_router(auth_router)
app.include_router(disposiciones_router)
app.state.auth = auth
app.state.disposiciones = make_disposiciones(auth, FakeAuditStore(), conn, root, transaction=lambda: sp(conn))


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
    p = lambda ruta, body=None: ok(c.post(f"/disposiciones/{ruta}", json=body or {}, headers=CSRF))  # noqa: E731
    out = {"sin_plantilla": ok(c.get("/disposiciones"))}
    (root / "inst_1" / "plantillas").mkdir(parents=True)
    (root / "inst_1" / "plantillas" / "disposicion.docx").write_bytes(P.construir())
    out.update({"overview": ok(c.get("/disposiciones")), "super": ok(sup.get("/disposiciones")),
                "lector": ok(lector.get("/disposiciones"))})
    pid = out["overview"]["periodo_defecto"]
    out["periodo"] = p("periodo", {"periodo_id": pid})
    vistas = {}
    for f in out["periodo"]["habilitados"]:
        v = p("docente", {"periodo_id": pid, "cuil": f["cuil"]})
        if "con_designaciones" not in vistas and len(v["designaciones"]) >= 2:
            vistas["con_designaciones"] = v
        if "mixta" not in vistas and (v["es_mixta"] or v["es_no_docente"]):
            vistas["mixta"] = v
        if len(vistas) == 2:
            break
    out["primero"] = p("docente", {"periodo_id": pid, "cuil": out["periodo"]["habilitados"][0]["cuil"]})
    out.update(vistas)
    out["historial"] = p("historial", {"periodo_id": None})
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("fixtures:", OUT, OUT.stat().st_size, sorted(out))
finally:
    conn.rollback()
    conn.close()
    shutil.rmtree(root, ignore_errors=True)
