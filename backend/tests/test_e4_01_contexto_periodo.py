"""E4-01 — aviso global "🕰️ Contexto histórico activo" (D-AN9) contra B13-FIX02.

Diferencial: el bloque LITERAL del entry certificado (l. 59263-59273, extraido por AST) se ejecuta DESDE
``reference_fix02`` con ``get_periodo_abierto`` (l. 4724), ``get_ultimo_periodo`` (``extracted_batch03``),
``_info_periodo_analisis_v169`` (l. 36408), ``_periodo_contexto_info_v182`` y ``es_periodo_historico_contexto_v182``
(l. 39213/39224) sobre la conexion ``tenant`` certificada (inyector v193 + B12J).  Ambito institucional (superadmin o
coordinador sin departamento): el inyector recibe ``departamento_id`` None y B12B devuelve None como departamento
actual (scope institucional con departamento opcional).  Se compara el texto exacto del ``st.warning`` (o su
ausencia) con NEXT.

Escenarios: datos reales de todos los departamentos e instituciones y fixtures SINTETICOS (institucion/departamentos
``zznext`` + periodos) creados dentro de la transaccion del test: ROLLBACK al final, nada persiste.
"""
from __future__ import annotations

import ast
import copy
import re
from pathlib import Path

import pandas as pd
import pytest

from designaciones_support import _Conn, _Frames
from materias_support import planes_injector
from periodos_support import ENTRY, _tree, exec_defs
from saas_support import auth_db, ids_por_rol, nueva_institucion, nuevo_departamento, sesion  # noqa: F401
from periodos_support import audit_store, db_conn  # noqa: F401

from auth import policy
from integraciones.contexto_periodo import ContextoPeriodoService, aviso, lecturas

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")

BACKEND = Path(__file__).resolve().parents[1]
BANNER_DESDE, BANNER_HASTA = 59264, 59273


# ------------------------------------------------------------------------------------------ certificado
class _StAviso:
    def __init__(self):
        self.avisos: list[str] = []

    def warning(self, texto, *a, **k):
        self.avisos.append(texto)


def _banner_code():
    nodos = [copy.deepcopy(n) for n in _tree(ENTRY).body if BANNER_DESDE <= n.lineno <= BANNER_HASTA]
    assert [type(n).__name__ for n in nodos] == ["Assign", "If"], "el bloque certificado del aviso cambió de forma"
    assert ast.unparse(nodos[0]) == "_periodo_contexto_ui_v182 = get_periodo_abierto()"
    return compile(ast.Module(body=nodos, type_ignores=[]), str(ENTRY), "exec")


def certificado(raw, institucion_id: int, departamento_id) -> list[str]:
    """Ejecuta el aviso certificado con el ambito dado; devuelve los ``st.warning`` emitidos (0 o 1)."""
    injector = planes_injector()
    if departamento_id is None:  # B12B: superadmin/coordinador sin departamento -> scope institucional
        injector["_pg_current_dep_id"] = lambda: None
    frames = _Frames()
    scope = {"kind": "tenant", "institucion_id": int(institucion_id),
             "departamento_id": None if departamento_id is None else int(departamento_id)}
    st = _StAviso()
    ns = {"__builtins__": __builtins__, "pd": pd, "USE_POSTGRESQL": True, "st": st,
          "get_conn": lambda: _Conn(raw, frames, scope, injector)}
    exec_defs(ENTRY, [("get_periodo_abierto", 0), ("get_ultimo_periodo", 0), ("_info_periodo_analisis_v169", 0),
                      ("_periodo_contexto_info_v182", 0), ("es_periodo_historico_contexto_v182", 0)], ns)
    exec(_banner_code(), ns)
    return st.avisos


def next_texto(raw, institucion_id: int, departamento_id):
    return aviso(*lecturas(raw, institucion_id, departamento_id))


def _comparar(raw, inst, dep):
    cert = certificado(raw, inst, dep)
    nxt = next_texto(raw, inst, dep)
    assert len(cert) <= 1
    assert nxt == (cert[0] if cert else None)
    return nxt


# ------------------------------------------------------------------------------------------ fixtures sinteticas
def periodo(conn, inst: int, dep: int, nombre: str, anio: int, semestre: int, estado: str,
            fi="2026-03-01", ff="2026-07-31") -> int:
    with conn.cursor() as cur:
        cur.execute("INSERT INTO periodos (institucion_id, departamento_id, nombre, anio, semestre, fecha_inicio, "
                    "fecha_fin, estado, observaciones) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, '') RETURNING id",
                    [inst, dep, nombre, anio, semestre, fi, ff, estado])
        return int(cur.fetchone()[0])


def sintetico(conn, nombre="ZZNEXT E4-01"):
    inst = nueva_institucion(conn, nombre=f"{nombre} Instituto")
    return inst, nuevo_departamento(conn, inst, nombre=f"{nombre} Depto A"), \
        nuevo_departamento(conn, inst, nombre=f"{nombre} Depto B")


# Escenarios por departamento: (periodos en orden de alta, aviso esperado: None / patron del nombre activo)
ESCENARIOS = {
    "actual_abierto": ([("2026-1", 2026, 1, "Cerrado"), ("2026-2", 2026, 2, "Abierto")], None),
    "anterior_abierto_por_excepcion": ([("2026-1", 2026, 1, "Abierto"), ("2026-2", 2026, 2, "Cerrado")], "2026-1"),
    "sin_abierto_ultimo_cerrado": ([("2026-1", 2026, 1, "Cerrado"), ("2026-2", 2026, 2, "Cerrado")], None),
    "unico_abierto": ([("2026-1", 2026, 1, "Abierto")], None),
    "dos_abiertos_mayor_id_anterior": ([("2026-2", 2026, 2, "Abierto"), ("2026-1", 2026, 1, "Abierto")], "2026-1"),
    "empate_anio_semestre": ([("2026-1 A", 2026, 1, "Abierto"), ("2026-1 B", 2026, 1, "Cerrado")], "2026-1 A"),
}


# ------------------------------------------------------------------------------------------ A, B, C, F: diferencial
def test_banner_certificado_extraido_literal():
    texto = ast.unparse(ast.Module(body=[n for n in _tree(ENTRY).body if BANNER_DESDE <= n.lineno <= BANNER_HASTA],
                                   type_ignores=[]))
    assert "es_periodo_historico_contexto_v182(_periodo_contexto_ui_v182.get('id'))" in texto
    assert "🕰️ **Contexto histórico activo:" in texto and "st.warning(" in texto


def test_datos_reales_todos_los_departamentos_e_instituciones(db_conn):
    """Datos reales: cada departamento con periodos y cada institucion (ambito institucional) = certificado."""
    with db_conn.cursor() as cur:
        cur.execute("SELECT DISTINCT institucion_id, departamento_id FROM periodos ORDER BY 1, 2")
        pares = cur.fetchall()
        cur.execute("SELECT id FROM instituciones ORDER BY id")
        insts = [r[0] for r in cur.fetchall()]
    assert pares, "deptit_next_dev debería tener periodos"
    for inst, dep in pares:
        _comparar(db_conn, inst, dep)
    for inst in insts:
        _comparar(db_conn, inst, None)


@pytest.mark.parametrize("nombre", list(ESCENARIOS))
def test_escenarios_departamento(db_conn, nombre):
    periodos, esperado = ESCENARIOS[nombre]
    inst, dep, _ = sintetico(db_conn)
    for (n, anio, sem, estado) in periodos:
        periodo(db_conn, inst, dep, n, anio, sem, estado)
    texto = _comparar(db_conn, inst, dep)
    if esperado is None:
        assert texto is None
    else:
        assert texto is not None and texto.startswith(f"🕰️ **Contexto histórico activo: {esperado}** (")
        assert "El último período cronológico sigue siendo **" in texto


def test_sin_periodos(db_conn):
    inst, dep, _ = sintetico(db_conn)
    assert _comparar(db_conn, inst, dep) is None
    assert _comparar(db_conn, inst, None) is None


def test_texto_exacto_y_valores_nulos(db_conn):
    """Texto literal certificado, incluida la representacion de una fecha NULL (``None``, como el f-string)."""
    inst, dep, _ = sintetico(db_conn)
    periodo(db_conn, inst, dep, "2025-2", 2025, 2, "Abierto", fi="2025-08-01", ff=None)
    periodo(db_conn, inst, dep, "2026-1", 2026, 1, "Cerrado")
    texto = _comparar(db_conn, inst, dep)
    assert texto == (
        "🕰️ **Contexto histórico activo: 2025-2** (2025-08-01 al None). "
        "Las vistas periodizadas muestran la foto exacta de cómo estaba el sistema al finalizar el último día de este "
        "período. El último período cronológico sigue siendo **2026-1**. La operatoria académica normal de Comisiones "
        "permanece protegida/bloqueada para el período anterior; solo siguen disponibles las correcciones históricas "
        "ya previstas por la app.")


def test_ambito_institucional(db_conn):
    """Sin departamento (B12B institucional): abierto = mayor id Abierto de la institucion; ultimo cronologico de la
    institucion.  Dos departamentos: el mayor id abierto es anterior al ultimo -> aviso; al reves -> sin aviso."""
    inst, a, b = sintetico(db_conn)
    periodo(db_conn, inst, a, "2026-2", 2026, 2, "Abierto")
    periodo(db_conn, inst, b, "2026-1", 2026, 1, "Abierto")
    texto = _comparar(db_conn, inst, None)
    assert texto is not None and texto.startswith("🕰️ **Contexto histórico activo: 2026-1**")
    assert _comparar(db_conn, inst, a) is None and _comparar(db_conn, inst, b) is None
    inst2, c, d = sintetico(db_conn, "ZZNEXT E4-01 bis")
    periodo(db_conn, inst2, c, "2026-1", 2026, 1, "Abierto")
    periodo(db_conn, inst2, d, "2026-2", 2026, 2, "Abierto")
    assert _comparar(db_conn, inst2, None) is None


# ------------------------------------------------------------------------------------------ D, E: roles y ambito
def make_contexto(auth, db_conn, **kwargs):
    from periodos_support import savepoint
    kwargs.setdefault("transaction", lambda: savepoint(db_conn))
    return ContextoPeriodoService(None, auth, **kwargs)


def test_roles_reales_igual_al_certificado(auth_db, db_conn):
    ids = ids_por_rol(db_conn)
    svc = make_contexto(auth_db, db_conn)
    for rol in ("superadmin", "coordinador_institucional", "usuario_departamento"):
        record, _ = sesion(auth_db, ids[rol])
        out = svc.aviso(record)
        res = auth_db.resolve_scope(record)
        dep = res.department["id"] if res.department else None
        cert = certificado(db_conn, res.institution["id"], dep)
        assert out == {"aviso": None if not cert else {"texto": cert[0]}}, rol


def test_superadmin_en_contexto_historico_y_cambio_de_contexto(auth_db, db_conn):
    inst, a, b = sintetico(db_conn)
    periodo(db_conn, inst, a, "2026-1", 2026, 1, "Abierto")
    periodo(db_conn, inst, a, "2026-2", 2026, 2, "Cerrado")
    periodo(db_conn, inst, b, "2026-2", 2026, 2, "Abierto")
    ids = ids_por_rol(db_conn)
    svc = make_contexto(auth_db, db_conn)
    record, _ = sesion(auth_db, ids["superadmin"], **{policy.SUPERADMIN_INSTITUTION_KEY: inst,
                                                      policy.DEPARTMENT_SCOPE_KEY: a})
    out = svc.aviso(record)
    assert out["aviso"]["texto"] == certificado(db_conn, inst, a)[0]
    record.scope[policy.DEPARTMENT_SCOPE_KEY] = b  # cambio legitimo de contexto: se recalcula
    assert svc.aviso(record) == {"aviso": None} and certificado(db_conn, inst, b) == []


def test_coordinador_institucional_y_con_departamento(auth_db, db_conn):
    """El coordinador sin departamento ve el aviso institucional certificado; con departamento, el del departamento."""
    ids = ids_por_rol(db_conn)
    record, _ = sesion(auth_db, ids["coordinador_institucional"])
    inst = int(auth_db.resolve_scope(record).institution["id"])
    nuevo = nuevo_departamento(db_conn, inst, nombre="ZZNEXT E4-01 Coord")
    periodo(db_conn, inst, nuevo, "2020-1", 2020, 1, "Abierto")  # mayor id abierto, cronologicamente anterior
    svc = make_contexto(auth_db, db_conn)
    out = svc.aviso(record)
    cert = certificado(db_conn, inst, None)
    assert cert and out == {"aviso": {"texto": cert[0]}}
    assert out["aviso"]["texto"].startswith("🕰️ **Contexto histórico activo: 2020-1**")
    with db_conn.cursor() as cur:
        cur.execute("SELECT id FROM departamentos WHERE institucion_id = %s AND id <> %s AND estado = 'Activo' "
                    "ORDER BY id LIMIT 1", [inst, nuevo])
        dep = cur.fetchone()[0]
    record.scope[policy.DEPARTMENT_SCOPE_KEY] = dep
    cert_dep = certificado(db_conn, inst, dep)
    assert svc.aviso(record) == {"aviso": None if not cert_dep else {"texto": cert_dep[0]}}


def test_ambito_no_verificable_sin_aviso(auth_db, db_conn):
    """Departamento de otra institucion en la sesion -> B12B no verifica el scope (SCOPE_DENIED: 0 filas)."""
    ids = ids_por_rol(db_conn)
    record, _ = sesion(auth_db, ids["usuario_departamento"])
    propia = int(auth_db.resolve_scope(record).institution["id"])
    with db_conn.cursor() as cur:
        cur.execute("SELECT id FROM departamentos WHERE institucion_id <> %s ORDER BY id LIMIT 1", [propia])
        ajeno = cur.fetchone()[0]
    record.scope[policy.DEPARTMENT_SCOPE_KEY] = ajeno
    assert auth_db.resolve_scope(record).reason is not None
    assert make_contexto(auth_db, db_conn).aviso(record) == {"aviso": None}


def test_falla_de_base_generica(auth_db, db_conn):
    from contextlib import contextmanager

    from integraciones.contexto_periodo import ContextoError

    @contextmanager
    def caida():
        raise RuntimeError("SELECT secreto FROM x; C:\\ruta")
        yield  # pragma: no cover

    record, _ = sesion(auth_db, ids_por_rol(db_conn)["usuario_departamento"])
    with pytest.raises(ContextoError) as exc:
        make_contexto(auth_db, db_conn, transaction=caida).aviso(record)
    assert exc.value.status == 503 and "SELECT" not in exc.value.message and "ruta" not in exc.value.message


# ------------------------------------------------------------------------------------------ HTTP y seguridad
@pytest.fixture
def http(auth_db, db_conn):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from auth.routes import router as auth_router
    from integraciones.routes import contexto_router

    app = FastAPI()
    app.state.auth = auth_db
    app.state.contexto_periodo = make_contexto(auth_db, db_conn)
    app.include_router(auth_router)
    app.include_router(contexto_router)
    return TestClient(app, base_url="http://localhost")


def test_http_sesion_metodo_y_parametros_ignorados(http, auth_db, db_conn):
    inst, a, _ = sintetico(db_conn)
    periodo(db_conn, inst, a, "2026-1", 2026, 1, "Abierto")
    periodo(db_conn, inst, a, "2026-2", 2026, 2, "Cerrado")
    assert http.get("/contexto/periodo").status_code == 401
    _, token = sesion(auth_db, ids_por_rol(db_conn)["superadmin"], **{policy.SUPERADMIN_INSTITUTION_KEY: inst,
                                                                         policy.DEPARTMENT_SCOPE_KEY: a})
    http.cookies.set("deptit_session", token)
    r = http.get("/contexto/periodo")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    assert set(r.json()) == {"aviso"} and set(r.json()["aviso"]) == {"texto"}
    # ningun parametro del cliente decide el aviso ni el ambito
    for q in ("?historico=0", "?departamento_id=1&institucion_id=1", "?periodo_id=1"):
        assert http.get("/contexto/periodo" + q).json() == r.json()
    assert http.post("/contexto/periodo", json={}).status_code == 405
    assert not re.search(r"(?i)select\s|traceback|psycopg|C:\\\\|password|salt", r.text)


# ------------------------------------------------------------------------------------------ G y arquitectura
def test_composicion_solo_lectura_y_sin_ciclos():
    fuente = (BACKEND / "integraciones" / "contexto_periodo.py").read_text(encoding="utf-8")
    assert "SET TRANSACTION READ ONLY" in fuente
    codigo = re.sub(r'"""[\s\S]*?"""', "", fuente)
    assert not re.search(r"(?i)\b(INSERT|UPDATE|DELETE|AuditStore|audit)\b", codigo)
    for py in BACKEND.rglob("*.py"):
        rel = py.relative_to(BACKEND).as_posix()
        # 6A-B2: ``operacion/`` es la CLI operativa (backup/restore con las herramientas B11), no runtime: como main.py,
        # compone integraciones; la app nunca la importa (test_e6_b2_backup.py::test_runtime_no_carga_...).
        if rel.startswith((".venv/", "tests/", "integraciones/", "operacion/")) or rel == "main.py" or "/ref/" in rel:
            continue
        assert not re.search(r"^\s*(from|import)\s+integraciones\b", py.read_text(encoding="utf-8", errors="ignore"),
                             re.M), f"{rel} importa la capa de composicion"
    imports = set(re.findall(r"^from (\w+)", fuente, re.M)) - {"__future__", "contextlib", "typing", "psycopg",
                                                              "logging"}
    assert imports == {"auth", "designaciones", "periodos"}
