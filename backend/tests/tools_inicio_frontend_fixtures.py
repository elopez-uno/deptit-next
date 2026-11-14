"""Genera las respuestas REALES de ``GET /inicio`` (UNO) para los tests de frontend: usuario de departamento (dep. 1),
solo lectura (dep. 1), superadmin en el dep. 9 (superposiciones y exceso), superadmin en el dep. 11 (periodo vencido,
graficos vacios), superadmin en un departamento sin periodos (institucion 2) y coordinador sin departamento.  Solo
lectura (``SET TRANSACTION READ ONLY``); la transaccion se revierte.  Nombres, CUIL y correos se reemplazan por textos
sinteticos ``ZZNEXT`` (los valores numericos, rotulos y especificaciones quedan como los entrega la API)."""
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
from auth.routes import router as auth_router  # noqa: E402
from auth.service import AuthService  # noqa: E402
from conftest import Clock, FakeRepo  # noqa: E402
from inicio.routes import router as inicio_router  # noqa: E402
from inicio_support import EXTRA_DEPARTMENTS, make_inicio  # noqa: E402

OUT = Path(r"C:\DEPTIT_NEXT\frontend\tests\fixtures\inicio_uno.json")
CSRF = {"X-DEPTIT-Request": "1"}

s = db.load_settings()
db.check_config(s)
conn = psycopg.connect(s["database_url"], application_name="deptit_next_tests")
db.verify_identity(conn)
conn.execute("SET TRANSACTION READ ONLY")
assert conn.execute("SHOW transaction_read_only").fetchone()[0] == "on"
repo = FakeRepo(Clock())
repo.departments_rows.extend(dict(d) for d in EXTRA_DEPARTMENTS)
auth = AuthService(repo, config_source=lambda n: None)


@contextmanager
def sp(c):
    with c.transaction():
        yield c


app = FastAPI()
app.include_router(auth_router)
app.include_router(inicio_router)
app.state.auth = auth
app.state.inicio = make_inicio(auth, conn, transaction=lambda: sp(conn))


def client_for(email: str, inst=None, dep=None, consolidado=False) -> TestClient:
    c = TestClient(app, base_url="http://localhost")
    assert c.post("/auth/login", json={"email": email, "password": repo.passwords[email]}, headers=CSRF).status_code == 200
    if dep is not None or consolidado:
        assert c.put("/auth/context", json={"institucion_id": inst, "departamento_id": dep, "consolidado": consolidado},
                     headers=CSRF).status_code == 200
    return c


def anonimizar(texto: str) -> str:
    nombres = set()
    for fila in conn.execute(
            "SELECT trim(COALESCE(apellido,'')) || ', ' || trim(COALESCE(nombres,'')), trim(COALESCE(nombre,'')), "
            "trim(COALESCE(apellido,'')), trim(COALESCE(nombres,'')) FROM docentes WHERE institucion_id=1"):
        nombres.update(x for x in fila if x and len(x) >= 4 and x != ",")
    mapa = {}
    for n in sorted(nombres, key=len, reverse=True):
        clave = json.dumps(n, ensure_ascii=False)[1:-1]
        if clave in texto:
            mapa.setdefault(n, f"ZZNEXT Persona {len(mapa) + 1}")
            texto = texto.replace(clave, mapa[n])
    cuiles = {}
    texto = re.sub(r"\b\d{2}-?\d{6,8}-?\d{1,2}\b", lambda m: cuiles.setdefault(m.group(0), f"20-99{len(cuiles):06d}-0"), texto)
    return re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "zznext@test.local", texto)


def emails():
    por_rol = {}
    for u in repo.users:
        por_rol.setdefault(u["rol"], u["email"])
    return por_rol


E = emails()
out = {}
r = client_for("info@test.local").get("/inicio")
assert r.status_code == 200
out["dep"] = r.json()
lector = next(u["email"] for u in repo.users if u["rol"] == "solo_lectura" and u.get("departamento_id") == 1)
out["lector"] = client_for(lector).get("/inicio").json()
out["dep9"] = client_for(E["superadmin"], 1, 9).get("/inicio").json()
out["dep11"] = client_for(E["superadmin"], 1, 11).get("/inicio").json()
out["sin_periodo"] = client_for(E["superadmin"], 2, 5).get("/inicio").json()
out["coord"] = client_for(E["coordinador_institucional"]).get("/inicio").json()
assert [out[k]["estado"] for k in ("dep", "lector", "dep9", "dep11", "sin_periodo", "coord")] == \
    ["tablero", "tablero", "tablero", "tablero", "sin_periodo", "institucional"]
texto = anonimizar(json.dumps(out, ensure_ascii=False, indent=1))
conn.rollback()
conn.close()
OUT.write_text(texto, encoding="utf-8")
print("fixture:", OUT, "bytes:", OUT.stat().st_size)
