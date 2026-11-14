"""Soporte de los tests de E4-10 / E4-11 / E4-12 (operaciones de Periodos).

- ``certified_ns``: el MISMO entorno de ejecucion de NEXT (conexiones de una transaccion, inyector B12B/B12J literal)
  pero con el codigo CERTIFICADO tomado de ``reference_fix02``: el cierre transitivo de las mismas raices compilado
  desde el AST del entry (no el ``complemento.py`` vendorizado) y el modulo B12C original
  (``deptit_refactor.b12c.periodo_atomico``).  Es el lado "certificado" del diferencial.
- ``estado``: foto comparable de lo que tocan las operaciones (ids nuevos normalizados).
"""
from __future__ import annotations

import ast
import collections
import copy
import functools
import json
import sys
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from periodos_support import ENTRY, _tree  # noqa: E402

DEV = {"DEPTIT_ENTORNO": "desarrollo", "DEPTIT_BACKUP_GATE_CREAR_PERIODO": "desactivado"}


@functools.lru_cache(maxsize=4)
def certified_code(extra=()):
    import tools_generar_motor_ciclo_periodos as G
    tree = copy.deepcopy(_tree(ENTRY))
    defs, aliases = collections.defaultdict(list), collections.defaultdict(list)
    for node in tree.body:
        if node.lineno >= G.CUTOFF:
            continue
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            defs[node.name].append(node)
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and isinstance(node.value, ast.Name):
            aliases[node.targets[0].id].append(node)
    seen, queue = set(), list(G.RAICES) + list(extra)
    while queue:
        n = queue.pop()
        if n in seen or n in G.INFRA:
            continue
        seen.add(n)
        for d in defs.get(n, []):
            queue.extend({x.id for x in ast.walk(d) if isinstance(x, ast.Name)} - seen)
        for a in aliases.get(n, []):
            queue.append(a.value.id)
    picked = []
    for node in tree.body:
        if node.lineno >= G.CUTOFF:
            continue
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in seen:
            node.decorator_list = []
            picked.append(node)
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            nombre = node.targets[0].id
            if nombre in seen and (isinstance(node.value, ast.Name) or _literal(node.value)):
                picked.append(node)
    return compile(ast.Module(body=picked, type_ignores=[]), str(ENTRY), "exec")


def _literal(value) -> bool:
    try:
        ast.literal_eval(value)
        return True
    except Exception:
        return False


def certified_ns(inst, dep, *, hoy, ahora, usuario=None, extra=()):
    """Entorno NEXT + codigo certificado de reference_fix02 + B12C original."""
    from deptit_refactor.b12c import periodo_atomico as RB12C

    from integraciones.ciclo_periodos import entorno
    original = entorno._codigo
    entorno._codigo = lambda: certified_code(tuple(extra))
    try:
        ns = entorno.construir(inst, dep, usuario=usuario, hoy=hoy, ahora=ahora)
    finally:
        entorno._codigo = original
    router = RB12C.raw_connection_router(entorno._sin_unidad)
    ns["_pg_raw_conn"] = router

    def _pg_read_dataframe(sql, params=None):
        import pandas as pd
        cur = router().cursor()
        cur.execute(sql, list(params or []))
        rows = cur.fetchall() if cur.description else []
        cols = [d.name for d in cur.description] if cur.description else []
        return pd.DataFrame(rows, columns=cols)
    ns["_pg_read_dataframe"] = _pg_read_dataframe
    ns["_B12C"] = RB12C
    return ns


# ------------------------------------------------------------------------------------------ estado comparable
MAX = {}


def baseline(conn) -> None:
    for t in ("periodos", "designaciones", "movimientos", "investigacion_docente", "extension_docente",
              "documentos_respaldo_designaciones", "documentos_respaldo_movimientos", "estado_consulta_designacion"):
        MAX[t] = conn.execute(f"SELECT coalesce(max(id),0) FROM {t}").fetchone()[0]


def _rows(conn, sql, params=()):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, list(params))
        return list(cur.fetchall())


def estado(conn, inst=1, dep=1) -> dict:
    def per(v):
        return "NUEVO" if v is not None and int(v) > MAX["periodos"] else v

    def norm(rows, tabla, campos_periodo=("periodo_id",)):
        out = []
        for r in rows:
            d = dict(r)
            nuevo = int(d.pop("id")) > MAX[tabla]
            d["_id"] = "nuevo" if nuevo else r["id"]
            for c in campos_periodo:
                if c in d:
                    d[c] = per(d[c])
            out.append(json.dumps(d, sort_keys=True, default=str))
        return sorted(out)
    periodos = []
    for r in _rows(conn, "SELECT * FROM periodos WHERE institucion_id=%s AND departamento_id=%s ORDER BY id", [inst, dep]):
        d = dict(r)
        d["id"] = per(d["id"])
        periodos.append(json.dumps(d, sort_keys=True, default=str))
    movs = []
    for r in _rows(conn, "SELECT * FROM movimientos WHERE id > %s ORDER BY id", [MAX["movimientos"]]):
        d = {k: v for k, v in r.items() if k != "id"}
        d["periodo_id"] = per(d["periodo_id"])
        d["horas_variacion"] = float(d["horas_variacion"] or 0)
        movs.append(json.dumps(d, sort_keys=True, default=str))
    return {
        "periodos": sorted(periodos),
        "designaciones": norm(_rows(conn, "SELECT * FROM designaciones WHERE institucion_id=%s AND departamento_id=%s",
                                    [inst, dep]), "designaciones"),
        "movimientos_nuevos": sorted(movs),
        "movimientos_viejos": conn.execute("SELECT count(*), coalesce(sum(id),0) FROM movimientos WHERE id <= %s",
                                           [MAX["movimientos"]]).fetchone(),
        "investigacion": norm(_rows(conn, "SELECT * FROM investigacion_docente WHERE institucion_id=%s", [inst]),
                              "investigacion_docente"),
        "extension": norm(_rows(conn, "SELECT * FROM extension_docente WHERE institucion_id=%s", [inst]),
                          "extension_docente"),
        "asignaciones": sorted(json.dumps(r, sort_keys=True, default=str) for r in _rows(
            conn, "SELECT id, rol, estado, observaciones FROM asignaciones_docentes_comision WHERE institucion_id=%s",
            [inst])),
        "links_designaciones": conn.execute(
            "SELECT count(*), count(*) FILTER (WHERE designacion_id > %s) FROM documentos_respaldo_designaciones",
            [MAX["designaciones"]]).fetchone(),
        "links_movimientos": conn.execute(
            "SELECT count(*), count(*) FILTER (WHERE movimiento_id > %s) FROM documentos_respaldo_movimientos",
            [MAX["movimientos"]]).fetchone(),
        "estado_consulta": conn.execute("SELECT count(*), coalesce(sum(id),0) FROM estado_consulta_designacion"
                                        ).fetchone(),
    }


def audit_rows(conn) -> list[dict]:
    return _rows(conn, "SELECT * FROM b12h_audit_log WHERE occurred_at >= transaction_timestamp() "
                       "ORDER BY occurred_at, correlation_id, event_seq")


def correr(conn, fn, inst=1, dep=1):
    """(resultado, excepcion, estado, filas B12H) de ``fn`` en un SAVEPOINT revertido."""
    out = {}
    with conn.transaction() as tx:
        try:
            out["r"], out["e"] = fn(), None
        except psycopg.Error:
            raise
        except Exception as exc:  # noqa: BLE001
            out["r"], out["e"] = None, exc
        out["st"], out["audit"] = estado(conn, inst, dep), audit_rows(conn)
        raise psycopg.Rollback(tx)
    return out["r"], out["e"], out["st"], out["audit"]
