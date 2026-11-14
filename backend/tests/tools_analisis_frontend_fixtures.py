"""Genera las respuestas REALES de la API de Analisis (UNO, departamento 1) para los tests de frontend: overview de
usuario de departamento, superadmin y solo lectura, las pestañas 1-4 de 2026-2 y 2026-1 (historico) y la comparacion con
2026-1.  Solo lectura (``SET TRANSACTION READ ONLY``); la transaccion se revierte.  Los nombres de personas, CUIL y
correos se reemplazan por textos sinteticos ``ZZNEXT`` (los valores numericos, rotulos y especificaciones quedan como
los entrega la API)."""
import json
import re
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
from analisis.routes import router as analisis_router  # noqa: E402
from analisis_support import EXTRA_DEPARTMENTS, FakeAuditStore, make_analisis  # noqa: E402
from auth.routes import router as auth_router  # noqa: E402
from auth.service import AuthService  # noqa: E402
from conftest import Clock, FakeRepo  # noqa: E402

OUT = Path(r"C:\DEPTIT_NEXT\frontend\tests\fixtures\analisis_uno.json")
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
app.include_router(analisis_router)
app.state.auth = auth
app.state.analisis = make_analisis(auth, FakeAuditStore(), conn, transaction=lambda: sp(conn))


def client_for(email: str, dep=None) -> TestClient:
    c = TestClient(app, base_url="http://localhost")
    assert c.post("/auth/login", json={"email": email, "password": repo.passwords[email]}, headers=CSRF).status_code == 200
    if dep is not None:
        assert c.put("/auth/context", json={"institucion_id": 1, "departamento_id": dep, "consolidado": False},
                     headers=CSRF).status_code == 200
    return c


def anonimizar(texto: str) -> str:
    nombres = set()
    for fila in conn.execute(
            "SELECT trim(COALESCE(apellido,'')) || ', ' || trim(COALESCE(nombres,'')), trim(COALESCE(nombre,'')), "
            "trim(COALESCE(apellido,'')), trim(COALESCE(nombres,'')) FROM docentes WHERE institucion_id=1 "
            "UNION SELECT trim(COALESCE(nombre,'')), '', '', '' FROM movimientos WHERE institucion_id=1"):
        nombres.update(x for x in fila if x and len(x) >= 4 and x != ",")
    mapa = {}
    for n in sorted(nombres, key=len, reverse=True):
        clave = json.dumps(n, ensure_ascii=False)[1:-1]
        if clave in texto:
            mapa.setdefault(n, f"ZZNEXT Persona {len(mapa) + 1}")
            texto = texto.replace(clave, mapa[n])
    cuiles = {}
    texto = re.sub(r"\b\d{2}-?\d{7,8}-?\d\b", lambda m: cuiles.setdefault(m.group(0), f"20-99{len(cuiles):06d}-0"), texto)
    return re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "zznext@test.local", texto)


try:
    dep = client_for("info@test.local")
    fx = {"overview": dep.get("/analisis").json(), "super": client_for("super@test.local", 1).get("/analisis").json(),
          "lector": client_for("lector@test.local").get("/analisis").json()}
    for p in ("2026-2", "2026-1"):
        r = dep.post("/analisis/periodo", json={"periodo": p}, headers=CSRF)
        assert r.status_code == 200, r.text
        fx[f"periodo_{p}"] = r.json()
    r = dep.post("/analisis/comparacion", json={"periodos": ["2026-1"]}, headers=CSRF)
    assert r.status_code == 200
    fx["comparacion"] = r.json()
    texto = anonimizar(json.dumps(fx, ensure_ascii=False, indent=0))
    assert "source_db" not in texto and "SELECT " not in texto
    OUT.write_text(texto, encoding="utf-8")
    print("fixtures:", OUT, len(texto), "bytes")
finally:
    conn.rollback()
    conn.close()
