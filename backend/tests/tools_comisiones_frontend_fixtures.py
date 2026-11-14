"""Genera las respuestas REALES de la API de Comisiones (UNO, departamento 1) para los tests de frontend: overview
(usuario de departamento y solo lectura), /comisiones/periodo del periodo actual y del historico, alertas, sedes,
inscriptos, pestaña Abrir (materias, detalle de la primera materia comun, docentes y cargos), listas y detalle de
Modificacion y Edicion, datos generales de la comision editada y una vista previa de carga rapida.  Solo lectura; la
transaccion se revierte."""
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
from comisiones.routes import router as comisiones_router  # noqa: E402
from comisiones_support import EXTRA_DEPARTMENTS, FakeAuditStore, make_comisiones  # noqa: E402
from conftest import Clock, FakeRepo  # noqa: E402

OUT = Path(r"C:\DEPTIT_NEXT\frontend\tests\fixtures\comisiones_uno.json")
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
app.include_router(comisiones_router)
app.state.auth = auth
app.state.comisiones = make_comisiones(auth, FakeAuditStore(), conn, transaction=lambda: sp(conn))


def client_for(email: str) -> TestClient:
    c = TestClient(app, base_url="http://localhost")
    assert c.post("/auth/login", json={"email": email, "password": repo.passwords[email]}, headers=CSRF).status_code == 200
    return c


def ok(r):
    assert r.status_code == 200, r.text
    return r.json()


def post(c, path, body):
    return ok(c.post(f"/comisiones/{path}", json=body, headers=CSRF))


info = client_for("info@test.local")
overview = ok(info.get("/comisiones"))
assert overview["contexto"]["departamento"]["id"] == 1
lector = ok(client_for("lector@test.local").get("/comisiones"))
actual, historico = overview["actual"]["id"], 5
periodos = {str(pid): post(info, "periodo", {"periodo_id": pid}) for pid in (actual, historico)}
alertas = post(info, "alertas", {})
sedes = post(info, "sedes", {})
inscriptos = {str(actual): post(info, "inscriptos", {"periodo_id": actual})}

filtros = {"codigo": "", "nombre": "", "cuatrimestre": "Todos", "escuela": "Todas", "carrera": "Todas"}
materias = post(info, "abrir/materias", filtros)
materia_body = None
for m in materias["materias"]:
    body = {"materia_id": m["materia_id"], "adicionales": [], "buscar_opcion": "", "opcion_curricular_id": None}
    detalle = post(info, "abrir/materia", body)
    if not detalle["es_oe"]:
        materia_body = body
        break
materias = {"body": filtros, "respuesta": materias}
materia = {"body": materia_body, "respuesta": detalle}
docentes = post(info, "docentes", {"contexto": "actual"})
roles = {d["cuil"]: post(info, "docentes/roles", {"contexto": "actual", "cuil": d["cuil"]})
         for d in docentes["docentes"][:3]}

lista_mod = post(info, "lista", {"contexto": "modificacion", "busqueda": ""})
detalle_mod = post(info, "detalle", {"contexto": "modificacion", "comision_id": lista_mod["filas"][0]["id"]})
lista_ed = post(info, "lista", {"contexto": "edicion", "busqueda": ""})
detalle_ed = post(info, "detalle", {"contexto": "edicion", "comision_id": lista_ed["filas"][0]["id"]})
datos_ed = post(info, "edicion/datos", {"comision_id": lista_ed["filas"][0]["id"], "materia_id": None})

texto = ("Código\tAsignatura\tComisión\tTurno\tDía 1\tHora Inicio 1\tHora Fin 1\tModalidad\n"
         f"{detalle['codigo']}\t{detalle['asignatura']}\tZZ1\tnoche\tLunes\t18:00\t20:00\tPresencial\n"
         "ZZ-999\tNo existe\tZZ2\tnoche\tLunes\t18:00\t20:00\tPresencial")
carga = {"texto": texto, "respuesta": post(info, "carga-rapida/previsualizar", {"texto": texto, "excel": None})}

OUT.write_text(json.dumps({
    "overview": overview, "lector": lector, "periodos": periodos, "alertas": alertas, "sedes": sedes,
    "inscriptos": inscriptos, "materias": materias, "materia": materia, "docentes": docentes, "roles": roles,
    "lista_modificacion": lista_mod, "detalle_modificacion": detalle_mod, "lista_edicion": lista_ed,
    "detalle_edicion": detalle_ed, "datos_edicion": datos_ed, "carga": carga,
}, ensure_ascii=False), encoding="utf-8")
conn.rollback()
conn.close()
print("actual:", overview["actual"]["nombre"], "| periodo actual filas:", len(periodos[str(actual)]["filas"]),
      "| historico filas:", len(periodos[str(historico)]["filas"]), "| materias:", len(materias["respuesta"]["materias"]),
      "| docentes:", len(docentes["docentes"]), "| lista edicion:", len(lista_ed["filas"]),
      "| carga:", carga["respuesta"]["totales"])
