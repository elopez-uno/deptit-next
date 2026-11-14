"""Genera las respuestas REALES de la API de Movimientos (UNO, departamento 1) para los tests de frontend: overview de
usuario de departamento, superadmin y solo lectura, listado "Todos los períodos" y repositorio de actos.  Solo lectura
(``SET TRANSACTION READ ONLY``); la transaccion se revierte.  Nombres, CUIL, detalle y observaciones se reemplazan por
textos sinteticos ``ZZNEXT`` (los tipos, periodos, fechas y etiquetas de acto quedan como en la base; la huella se
recalcula sobre la fila anonimizada)."""
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
from movimientos import rules as R  # noqa: E402
from movimientos.routes import router as movimientos_router  # noqa: E402
from movimientos_support import EXTRA_DEPARTMENTS, FakeAuditStore, make_movimientos  # noqa: E402

OUT = Path(r"C:\DEPTIT_NEXT\frontend\tests\fixtures\movimientos_uno.json")
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
app.include_router(movimientos_router)
app.state.auth = auth
app.state.movimientos = make_movimientos(auth, FakeAuditStore(), conn, transaction=lambda: sp(conn))

PERSONAS: dict = {}


def anonimizar(filas):
    out = []
    for f in filas:
        f = dict(f)
        if f.get("cuil"):
            n = PERSONAS.setdefault(f["cuil"], len(PERSONAS) + 1)
            f["cuil"] = f"20-{99000000 + n}-0"
            f["nombre"] = f"ZZNEXT Persona {n}"
        elif f.get("nombre"):
            f["nombre"] = "ZZNEXT Registro"
        f["detalle"] = f"ZZNEXT detalle {f['id']}" if f.get("detalle") else f.get("detalle")
        f["observaciones"] = f"ZZNEXT obs {f['id']}" if f.get("observaciones") else f.get("observaciones")
        f.pop("huella", None)
        f["huella"] = R.huella(f)
        out.append(f)
    return out


def client_for(email: str, dep=None) -> TestClient:
    c = TestClient(app, base_url="http://localhost")
    assert c.post("/auth/login", json={"email": email, "password": repo.passwords[email]}, headers=CSRF).status_code == 200
    if dep is not None:
        assert c.put("/auth/context", json={"institucion_id": 1, "departamento_id": dep, "consolidado": False},
                     headers=CSRF).status_code == 200
    return c


def overview(c):
    r = c.get("/movimientos")
    assert r.status_code == 200, r.text
    d = r.json()
    d["filas"] = anonimizar(d["filas"])
    return d


try:
    dep = client_for("info@test.local")
    fx = {"overview": overview(dep), "super": overview(client_for("super@test.local", 1)),
          "lector": overview(client_for("lector@test.local"))}
    r = dep.post("/movimientos/listado", json={"periodo": R.TODOS}, headers=CSRF)
    assert r.status_code == 200
    fx["todos"] = {"periodo": r.json()["periodo"], "filas": anonimizar(r.json()["filas"])}
    r = dep.post("/movimientos/actos", json={}, headers=CSRF)
    assert r.status_code == 200
    fx["actos"] = r.json()
    texto = json.dumps(fx, ensure_ascii=False, indent=1)
    assert "source_db" not in texto and "sqlite" not in texto
    OUT.write_text(texto, encoding="utf-8")
    print("fixtures:", OUT, len(texto), "bytes", len(fx["overview"]["filas"]), len(fx["todos"]["filas"]))
finally:
    conn.rollback()
    conn.close()
