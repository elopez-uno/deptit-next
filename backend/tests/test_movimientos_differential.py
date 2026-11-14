"""Diferenciales de LECTURA de Movimientos: certificado (``certified_movimientos`` + ``pagina_certificada``) vs NEXT.

Pagina l. 67764-67797: opciones y opcion por defecto del selector de periodo, ``get_movimientos`` (ambito B12B/B12J,
orden certificado), ``_enriquecer_movimientos_acto_v266``, buscador (``filtrar_dataframe_por_texto``) y primera fila
seleccionada (``seleccionar_registro_desde_tabla``).  Los datos reales (legacy y anomalos, D-AL10) se leen tal cual;
las variantes sinteticas (``ZZNEXT``) se insertan dentro de la transaccion del test y se revierten.
"""

from __future__ import annotations

import re
from pathlib import Path

import psycopg
import pytest

from materias_support import planes_injector
from movimientos import repository as RP
from movimientos import rules as R
from movimientos import service as S
from movimientos.repository import MovimientosRepository
from movimientos_support import (  # noqa: F401  (fixtures)
    audit_store, certified_movimientos, db_conn, movimientos, pagina_certificada, session_for,
)

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")

INST = 1
DEPS = [1, 2, 3, 4, 9, 11]
MODULO = Path(__file__).resolve().parents[1] / "movimientos"


def _cert_filas(df) -> list[dict]:
    if df is None or df.empty:
        return []
    out = []
    for r in df.to_dict("records"):
        out.append({c: (None if str(r.get(c)) in ("nan", "None", "<NA>") else str(r.get(c))) for c in R.CAMPOS_FILA})
    return out


def _next_filas(filas: list[dict]) -> list[dict]:
    return [{c: (None if f[c] is None else str(f[c])) for c in R.CAMPOS_FILA} for f in filas]


def _next_pagina(conn, dep, sel=None, buscar=""):
    repo = MovimientosRepository(conn, INST, dep)
    periodos = repo.periods()
    if not periodos:
        filas = S.leer_tabla(repo, None)
        opciones, default = [], None
    else:
        ops = R.opciones_periodos(periodos)
        default = R.periodo_inicial(ops, repo.open_period(), repo.last_period())
        filas = S.leer_tabla(repo, ops[default if sel is None else sel])
        opciones = list(ops)
    vista = R.filtrar_por_texto(filas, buscar, R.COLUMNAS_BUSQUEDA)
    return {"opciones": opciones, "default": default, "filas": filas, "vista": vista,
            "primera": vista[0]["id"] if vista else None}


def _comparar(conn, dep, sel=None, buscar=""):
    c = pagina_certificada(certified_movimientos(conn, INST, dep), sel, buscar)
    n = _next_pagina(conn, dep, sel, buscar)
    assert c["opciones"] == n["opciones"]
    assert c["default"] == n["default"]
    assert _cert_filas(c["df"]) == _next_filas(n["filas"])
    assert _cert_filas(c["vista"]) == _next_filas(n["vista"])
    assert c["primera"] == n["primera"]
    return c, n


# ------------------------------------------------------------------------------------------ SQL efectivo
def _norm(sql: str) -> str:
    return re.sub(r"\s+", " ", sql).replace("( ", "(").replace(" )", ")").strip()


def test_sql_es_el_del_inyector_certificado():
    """El SQL de NEXT es el que produce el inyector B12B v193 + B12J sobre el SQL literal del entry (l. 4824, 9566)."""
    inj = planes_injector()
    scope = {"kind": "tenant", "institucion_id": 101, "departamento_id": 202}
    entry = Path(R.__file__).resolve().parents[2] / "reference_fix02" / "app_postgresql_refactor_b13fix02_uat_fixes.py"
    texto = entry.read_text(encoding="utf-8")
    cuerpo = texto[texto.index("def get_movimientos(periodo_id=None):"):]  # primera definicion, l. 4824
    inicio = cuerpo.index('f"""') + 4
    sql_legacy = cuerpo[inicio:cuerpo.index('"""', inicio)]
    for filtro, params, nuestro in (("", [], RP.MOVIMIENTOS_SQL), ("WHERE m.periodo_id = ?", [7], RP.MOVIMIENTOS_PERIODO_SQL)):
        q, p = inj["_pg_scope_select"](sql_legacy.replace("{filtro}", filtro), params, scope)
        assert _norm(q) == _norm(nuestro)
        assert p == ([101, 202] + params + [101, 202])
    q, p = inj["_pg_scope_update_delete"]("DELETE FROM documentos_respaldo_movimientos WHERE movimiento_id = ?", [5], scope)
    assert _norm(q) == _norm(RP.ELIMINAR_VINCULO_SQL) and p == [5, 101, 202]
    q, p = inj["_pg_scope_update_delete"]("DELETE FROM movimientos WHERE id = ?", [5], scope)
    assert _norm(q) == _norm(RP.ELIMINAR_SQL) and p == [5, 101, 202]


# ------------------------------------------------------------------------------------------ pagina
@pytest.mark.parametrize("dep", DEPS)
def test_periodo_por_defecto_y_todos_los_periodos(db_conn, dep):
    c, n = _comparar(db_conn, dep)
    assert n["default"] is not None and n["opciones"][0] == R.TODOS
    _comparar(db_conn, dep, R.TODOS)


@pytest.mark.parametrize("dep,periodo", [(1, "2026-1"), (2, "2026-1"), (3, "2026-1"), (9, "2026-1")])
def test_periodo_cerrado(db_conn, dep, periodo):
    _, n = _comparar(db_conn, dep, periodo)
    assert n["filas"] and {f["periodo"] for f in n["filas"]} == {periodo}


@pytest.mark.parametrize("buscar", ["alta", "ALTA DE DESIGNACIÓN", "pendiente de vincular", "no requerido", "2026-06",
                                    "20-", "  apertura   de  ", "Generación de disposición", "zzzz-sin-resultados"])
def test_buscador(db_conn, buscar):
    c, n = _comparar(db_conn, 1, R.TODOS, buscar)
    if buscar.startswith("zzzz"):
        assert n["vista"] == [] and n["primera"] is None and c["primera"] is None


def test_orden_columnas_y_primera_fila(db_conn):
    _, n = _comparar(db_conn, 3, R.TODOS)
    assert R.COLUMNAS_TABLA == ["periodo", "fecha", "tipo_movimiento", "nombre", "cuil", "detalle",
                                "acto_administrativo", "observaciones"]
    assert [R.RENOMBRES[c] for c in R.COLUMNAS_TABLA] == ["Período", "Fecha", "Movimiento", "Persona / registro",
                                                         "CUIL", "Detalle", "Acto administrativo", "Observaciones"]
    # D-AL12: todo el resultado, sin paginacion.  Etapa 5 / C2: esperado por SQL independiente (antes literal 2965).
    total = db_conn.execute("SELECT count(*) FROM movimientos WHERE institucion_id = %s AND departamento_id = 3",
                            [INST]).fetchone()[0]
    assert len(n["filas"]) == total > 0
    assert n["primera"] == n["filas"][0]["id"]
    for f in n["filas"]:
        assert set(f) == set(R.CAMPOS_FILA) | {"huella"}


def _conteo_sql(conn, sql: str, params=()) -> int:
    return int(conn.execute(sql, list(params)).fetchone()[0])


def test_tipos_reales_etiquetas_y_totales(db_conn):
    """Todos los movimientos reales de los 6 departamentos se leen (sin filtros ni paginacion) y cada uno recibe la
    etiqueta de acto certificada; disposicion -> "No requerido".

    Mantenimiento de tests (cierre de Etapa 4): ``deptit_next_dev`` es una base PERSISTENTE donde la app agrega
    movimientos reales (p. ej. apertura excepcional / retorno de una validacion visual).  Los totales esperados se
    calculan con SQL independiente de la capa NEXT (``movimientos`` + ``documentos_respaldo_movimientos`` y la lista
    certificada de tipos elegibles), no con conteos absolutos fijos (antes 7072 / 975)."""
    total, etiquetas, tipos = 0, {}, set()
    for dep in DEPS:
        filas = _next_pagina(db_conn, dep, R.TODOS)["filas"]
        total += len(filas)
        for f in filas:
            etiquetas[f["acto_administrativo"]] = etiquetas.get(f["acto_administrativo"], 0) + 1
            tipos.add(f["tipo_movimiento"])
            if f["tipo_movimiento"] == "Generación de disposición":
                assert f["acto_administrativo"] == R.NO_REQUERIDO
                assert re.match(r"^Se generó disposición N° .+: .+$", f["detalle"])
    base = "FROM movimientos m WHERE m.institucion_id=1 AND m.departamento_id = ANY(%s)"
    sin_vinculo = (" AND NOT EXISTS (SELECT 1 FROM documentos_respaldo_movimientos v WHERE v.movimiento_id = m.id"
                   " AND v.institucion_id = m.institucion_id AND v.departamento_id = m.departamento_id)")
    elegibles = sorted(R.MOVIMIENTOS_ACTO_ADMINISTRATIVO_V266)
    esperado_total = _conteo_sql(db_conn, "SELECT count(*) " + base, [DEPS])
    esperado_pendiente = _conteo_sql(db_conn, "SELECT count(*) " + base + sin_vinculo + " AND btrim(COALESCE("
                                     "m.tipo_movimiento,'')) <> %s AND btrim(COALESCE(m.tipo_movimiento,'')) = ANY(%s)",
                                     [DEPS, R.TIPO_HISTORICO, elegibles])
    esperado_historico = _conteo_sql(db_conn, "SELECT count(*) " + base + sin_vinculo + " AND btrim(COALESCE("
                                     "m.tipo_movimiento,'')) = %s", [DEPS, R.TIPO_HISTORICO])
    esperado_vinculados = esperado_total - _conteo_sql(db_conn, "SELECT count(*) " + base + sin_vinculo, [DEPS])
    assert esperado_total > 0 and esperado_pendiente > 0
    assert total == esperado_total
    assert etiquetas.get(R.PENDIENTE, 0) == esperado_pendiente
    assert etiquetas.get(R.NO_CORRESPONDE, 0) == esperado_historico
    assert etiquetas.get(R.NO_REQUERIDO, 0) == (esperado_total - esperado_vinculados - esperado_pendiente
                                                 - esperado_historico)
    assert sum(etiquetas.values()) == total
    reales = {r[0] for r in db_conn.execute("SELECT DISTINCT tipo_movimiento FROM movimientos WHERE institucion_id=1 "
                                            "AND departamento_id = ANY(%s)", [DEPS])}
    assert tipos == reales


def test_legacy_y_anomalias_se_leen_sin_exponer_campos_internos(db_conn):
    """D-AL10: filas legacy (source_db), duplicados, fechas fuera de rango y CUIL no estandar intactos y legibles.

    Mantenimiento de tests (cierre de Etapa 4): en lugar de conteos absolutos de la base persistente (antes 1350 legacy,
    541/1718 duplicados, 553 fuera de rango) se verifica que CADA fila anomala que existe en la base (SQL independiente)
    aparece en la lectura NEXT, sin deduplicar ni filtrar."""
    legacy = {r[0] for r in db_conn.execute("SELECT id FROM movimientos WHERE source_db IS NOT NULL")}
    assert legacy
    vistos = set()
    for dep in DEPS:
        for f in _next_pagina(db_conn, dep, R.TODOS)["filas"]:
            vistos.add(f["id"])
            texto = repr(f)
            assert "source_db" not in texto and "fuente_sqlite" not in texto and ".db'" not in texto
            assert "sqlite_id" not in f and "periodo_id" not in f and "horas_variacion" not in f
    assert legacy <= vistos
    duplicados = {r[0] for r in db_conn.execute(
        "SELECT m.id FROM movimientos m JOIN (SELECT institucion_id, departamento_id, periodo_id, fecha, tipo_movimiento,"
        " cuil, detalle, observaciones FROM movimientos GROUP BY 1,2,3,4,5,6,7,8 HAVING count(*)>1) d USING "
        "(institucion_id, departamento_id, periodo_id, fecha, tipo_movimiento, cuil, detalle, observaciones) "
        "WHERE m.institucion_id=1 AND m.departamento_id = ANY(%s)", [DEPS])}
    assert duplicados and duplicados <= vistos  # los duplicados certificados se leen todos (sin deduplicar)
    fuera = {r[0] for r in db_conn.execute(
        "SELECT m.id FROM movimientos m JOIN periodos p ON p.id=m.periodo_id WHERE m.institucion_id=1 AND "
        "m.departamento_id = ANY(%s) AND (m.fecha::date < p.fecha_inicio::date OR m.fecha::date > p.fecha_fin::date)",
        [DEPS])}
    assert fuera and fuera <= vistos  # fechas fuera del rango del periodo: se leen tal cual


# ------------------------------------------------------------------------------------------ sinteticos ZZNEXT
def _doc(conn, dep=1, numero="ZZNEXT-501/2026", tipo="Resolución", depnom="ZZNEXT Rectorado"):
    return conn.execute(
        "INSERT INTO documentos_respaldo (institucion_id,departamento_id,tipo_documento,categoria,numero,fecha,"
        "dependencia_nombre,archivo_nombre,archivo_mime,archivo_pdf,archivo_bytes) VALUES (1,%s,%s,'Otro',%s,"
        "'2026-10-01',%s,'','','',0) RETURNING id", [dep, tipo, numero, depnom]).fetchone()[0]


def _mov(conn, dep, tipo, periodo_id=None, fecha="2026-10-15", cuil="20-99000001-1", nombre="ZZNEXT Uno"):
    if periodo_id is None:
        periodo_id = conn.execute("SELECT id FROM periodos WHERE institucion_id=1 AND departamento_id=%s AND "
                                  "estado='Abierto'", [dep]).fetchone()[0]
    return conn.execute(
        "INSERT INTO movimientos (institucion_id,departamento_id,periodo_id,fecha,tipo_movimiento,cuil,nombre,detalle,"
        "observaciones,horas_variacion) VALUES (1,%s,%s,%s,%s,%s,%s,'ZZNEXT detalle',NULL,0) RETURNING id",
        [dep, periodo_id, fecha, tipo, cuil, nombre]).fetchone()[0]


def test_sinteticos_acto_vinculado_historico_sin_acto_y_ambito(db_conn):
    with db_conn.transaction() as tx:
        doc = _doc(db_conn)
        con_acto = _mov(db_conn, 1, "Cambio de cargo")
        db_conn.execute("INSERT INTO documentos_respaldo_movimientos (institucion_id,departamento_id,documento_id,"
                        "movimiento_id,usuario_vinculacion) VALUES (1,1,%s,%s,'zz')", [doc, con_acto])
        historico = _mov(db_conn, 1, "Cambio de número de resolución")
        sin_acto = _mov(db_conn, 1, "Apertura de comisión", cuil="", nombre="")
        espacios = _mov(db_conn, 1, " Alta de designación ")  # strip en la etiqueta, no en la elegibilidad
        # periodo de OTRO departamento: el LEFT JOIN con ambito (B12J) deja el nombre vacio
        p2 = db_conn.execute("SELECT id FROM periodos WHERE departamento_id=2 ORDER BY id LIMIT 1").fetchone()[0]
        cruzado = _mov(db_conn, 1, "Alta de designación", periodo_id=p2)
        otro_dep = _mov(db_conn, 2, "Alta de designación")
        db_conn.execute("INSERT INTO documentos_respaldo_movimientos (institucion_id,departamento_id,documento_id,"
                        "movimiento_id,usuario_vinculacion) VALUES (1,2,%s,%s,'zz')", [_doc(db_conn, 2), otro_dep])
        c, n = _comparar(db_conn, 1, R.TODOS)
        por_id = {f["id"]: f for f in n["filas"]}
        assert por_id[con_acto]["acto_administrativo"] == R.etiqueta_acto("Resolución", "ZZNEXT-501/2026",
                                                                          "ZZNEXT Rectorado")
        assert por_id[con_acto]["acto_documento_id"] == doc
        assert por_id[historico]["acto_administrativo"] == R.NO_CORRESPONDE
        assert por_id[sin_acto]["acto_administrativo"] == R.NO_REQUERIDO
        assert por_id[espacios]["acto_administrativo"] == R.PENDIENTE
        assert not R.elegible_acto(por_id[espacios]["tipo_movimiento"])
        assert por_id[cruzado]["periodo"] is None
        assert otro_dep not in por_id
        _comparar(db_conn, 1, R.TODOS, "zznext")
        _comparar(db_conn, 2, R.TODOS)
        raise psycopg.Rollback(tx)


def test_departamento_sin_periodos_y_sin_movimientos(db_conn):
    """Sin periodos: sin selector y todos los movimientos; sin movimientos: "Todavía no hay movimientos registrados"."""
    with db_conn.transaction() as tx:
        dep = db_conn.execute("INSERT INTO departamentos (institucion_id,nombre,slug,estado) VALUES (1,'ZZNEXT Dep','zznext-dep','Activo') "
                              "RETURNING id").fetchone()[0]
        c, n = _comparar(db_conn, dep)
        assert n["opciones"] == [] and n["filas"] == [] and c["df"].empty
        db_conn.execute("INSERT INTO movimientos (institucion_id,departamento_id,periodo_id,fecha,tipo_movimiento,cuil,"
                        "nombre,detalle,observaciones,horas_variacion) VALUES (1,%s,NULL,'2026-10-01','Alta de docente',"
                        "'20-99000002-2','ZZNEXT Dos','ZZNEXT','',0)", [dep])
        _, n = _comparar(db_conn, dep)
        assert len(n["filas"]) == 1 and n["filas"][0]["periodo"] is None
        raise psycopg.Rollback(tx)


def test_lecturas_no_escriben_ni_cachean(db_conn, movimientos, service, repo):
    """D-AL11 / D-AL14: lecturas frescas en transaccion READ ONLY, sin DDL, reconciliaciones ni cache de aplicacion."""
    rec = session_for(service, repo, 3)[0]
    antes = db_conn.execute("SELECT (SELECT md5(string_agg(md5(m::text),'' ORDER BY m.id)) FROM movimientos m), "
                            "(SELECT count(*) FROM documentos_respaldo_movimientos), "
                            "(SELECT count(*) FROM b12h_audit_log)").fetchone()
    ov = movimientos.overview(rec)
    todos = movimientos.listado(rec, {"periodo": R.TODOS})["filas"]
    # Mantenimiento de tests (cierre de Etapa 4): sin conteos absolutos de la base persistente (antes 582 / 1171).
    assert ov["periodo"] == "2026-2" and ov["filas"] and {f["periodo"] for f in ov["filas"]} == {"2026-2"}
    assert sorted(f["id"] for f in ov["filas"]) == sorted(f["id"] for f in todos if f["periodo"] == "2026-2")
    sc = movimientos.scope(rec)
    assert len(todos) == _conteo_sql(db_conn, "SELECT count(*) FROM movimientos WHERE institucion_id=%s AND "
                                              "departamento_id=%s", [sc.institution_id, sc.department_id]) > len(ov["filas"])
    assert movimientos.listado(rec, {"periodo": None})["periodo"] == R.TODOS
    assert len(movimientos.actos(rec)["documentos"]) >= 1
    despues = db_conn.execute("SELECT (SELECT md5(string_agg(md5(m::text),'' ORDER BY m.id)) FROM movimientos m), "
                              "(SELECT count(*) FROM documentos_respaldo_movimientos), "
                              "(SELECT count(*) FROM b12h_audit_log)").fetchone()
    assert antes == despues
    fuente = "\n".join(_codigo(p) for p in MODULO.glob("*.py"))
    for prohibido in ("CREATE ", "ALTER ", "add_column_if_not_exists", "asegurar_esquema", "lru_cache", "cache_data",
                      "reconciliar_", "asegurar_movimientos_baja", "reparar_", "source_db", "advisory", "lock"):
        assert prohibido not in fuente, prohibido


def _codigo(path: Path) -> str:
    """Codigo sin docstrings ni comentarios (``ast.unparse``)."""
    import ast
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body and isinstance(body[0], ast.Expr) and \
                isinstance(getattr(body[0], "value", None), ast.Constant) and isinstance(body[0].value.value, str):
            node.body = body[1:] or [ast.Pass()]
    return ast.unparse(tree)
