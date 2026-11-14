"""Genera las respuestas REALES de la API de Designaciones (UNO, departamento 1) para los tests de frontend:
overview (usuario de departamento y solo lectura), /designaciones/periodo de cada periodo, repositorio de actos,
duplicado del formulario de alta por defecto y vista previa de una carga rapida.  Solo lectura; la transaccion se
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
from designaciones.routes import router as designaciones_router  # noqa: E402
from designaciones_support import EXTRA_DEPARTMENTS, FakeAuditStore, make_designaciones  # noqa: E402

OUT = Path(r"C:\DEPTIT_NEXT\frontend\tests\fixtures\designaciones_uno.json")
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
app.include_router(designaciones_router)
app.state.auth = auth
app.state.designaciones = make_designaciones(auth, FakeAuditStore(), conn, transaction=lambda: sp(conn))


def client_for(email: str) -> TestClient:
    c = TestClient(app, base_url="http://localhost")
    assert c.post("/auth/login", json={"email": email, "password": repo.passwords[email]}, headers=CSRF).status_code == 200
    return c


def ok(r):
    assert r.status_code == 200, r.text
    return r.json()


info = client_for("info@test.local")
overview = ok(info.get("/designaciones"))
assert overview["contexto"]["institucion"]["id"] == 1 and overview["contexto"]["departamento"]["id"] == 1
lector = ok(client_for("lector@test.local").get("/designaciones"))
periodos = {str(p["id"]): ok(info.post("/designaciones/periodo", json={"periodo_id": p["id"]}, headers=CSRF))
            for p in overview["periodos"]}
actos = ok(info.post("/designaciones/actos", json={}, headers=CSRF))

abierto, cat = overview["abierto"], overview["catalogos"]
docente = overview["docentes"][0]
alta_default = {"cuil": docente["cuil"], "cargo": cat["cargos"][0], "dedicacion": cat["dedicaciones"][0],
                "tipo_designacion": cat["tipos"][0], "ad_honorem": cat["ad_honorem"][0], "estado": cat["estados"][0],
                "fecha_desde": abierto["fecha_inicio"], "fecha_hasta": abierto["fecha_fin"],
                "funcion_no_docente": False}
duplicado = {"body": alta_default, "respuesta": ok(info.post("/designaciones/duplicado", json=alta_default, headers=CSRF))}

# Una fila nueva valida y una con CUIL inexistente (sintetico, verificado libre en la base).
texto = ("cuil\tcargo\tdedicacion\tfecha_desde\tfecha_hasta\n"
         f"{docente['cuil']}\tJTP\tSimple\t{abierto['fecha_inicio']}\t{abierto['fecha_fin']}\n"
         f"20-99119999-0\tJTP\tSimple\t{abierto['fecha_inicio']}\t{abierto['fecha_fin']}\n")
assert conn.execute("SELECT count(*) FROM docentes WHERE regexp_replace(cuil,'[^0-9]','','g')='20991199990'"
                    ).fetchone()[0] == 0
carga = {"texto": texto,
         "respuesta": ok(info.post("/designaciones/carga-rapida/previsualizar", json={"texto": texto}, headers=CSRF))}

OUT.write_text(json.dumps({"overview": overview, "lector": lector, "periodos": periodos, "actos": actos,
                           "duplicado": duplicado, "carga": carga}, ensure_ascii=False), encoding="utf-8")
conn.rollback()
conn.close()
for pid, p in periodos.items():
    print(f"periodo {pid} {p['periodo']['nombre']}: historico={p['historico']} designaciones={len(p['designaciones'])} "
          f"conteo={p['conteo']} historial={len(p['historial'])} indicadores={len(p['indicadores'])}")
print("abierto:", abierto["nombre"], "| actos:", len(actos["documentos"]), "| permisos info:", overview["permisos"],
      "| permisos lector:", lector["permisos"])
print("duplicado:", duplicado["respuesta"], "| carga:", len(carga["respuesta"]["filas"]), "filas,",
      len(carga["respuesta"]["inexistentes"]), "inexistentes")
