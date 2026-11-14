"""B12J — el inyector de scope respeta la semántica de LEFT JOIN (F-B12-02).

Causa raíz corregida (sin tocar definiciones certificadas): ``_pg_scope_select_template_v193`` del entrypoint agrega
``<alias>.institucion_id = %s`` / ``<alias>.departamento_id = %s`` al WHERE principal para TODO alias de nivel
superior, incluidos los de un LEFT JOIN.  Un predicado de la tabla opcional en el WHERE descarta la fila completada con
NULL: la consulta queda, de hecho, como un INNER JOIN.  Se pierden en silencio las filas cuya tabla opcional no tiene
fila en el scope (designación cuyo CUIL no tiene docente local, comisión de electiva sin materia, materia sin carrera...)
en listados, alertas y en Crear período (copia, cierre y vencimientos sin movimiento).

Contrato B12J (una sola semántica, genérica):

* El scope de un alias de LEFT [OUTER] JOIN de nivel superior sobre una tabla con scope va a la condición de ese join:
  ``ON (<condición original>) AND (<alias>.institucion_id = %s) [AND (<alias>.departamento_id = %s)]``.  La tabla
  opcional sólo aporta filas del propio scope; si no hay, sus columnas quedan en NULL (nunca datos de otro scope).
* Todo lo demás es idéntico al v193: los alias de FROM / INNER / CROSS conservan su predicado en el WHERE, en el mismo
  orden y con los mismos valores; una consulta sin alias reubicado produce el mismo SQL y los mismos parámetros, byte a
  byte.  Los filtros escritos por el autor (incluidos los anti-joins ``alias.id IS NULL``) no se mueven.
* Fallbacks (se conserva la ubicación v193 en el WHERE, nunca menos restrictivo que hoy):
  - el segmento del join no tiene ``ON`` de nivel superior (``USING``, ``NATURAL``, no parseable);
  - el par (tabla, alias) aparece más de una vez en la lista v193 (alias ambiguo);
  - ningún otro alias de nivel superior con scope quedaría en el WHERE: el ancla perdería su único filtro.
* Parámetros: los valores del ON se intercalan en la lista posicional en el índice = cantidad de ``%s`` que preceden al
  punto de inserción (varios ON en el mismo índice siguen el orden del texto); los del WHERE se agregan al final, como en
  v193.
* B12B intacto: los valores de institución/departamento (o ``SCOPE_DENIED_ID``) los sigue resolviendo
  ``_pg_current_inst_id``/``_pg_current_dep_id``; el ancla conserva su predicado, así que un scope denegado sigue dando 0
  filas.  B12D intacto: este módulo no captura excepciones.
* Las consultas de nivel inferior (subconsultas, CTE) no cambian: el inyector heredado sólo actúa en el nivel superior.

``install_left_join_scope(globals())`` re-enlaza ``_pg_scope_select`` (el binding efectivo v193).  Sin SQL al instalar.
La copia del inyector en ``analisis.motor.ref/infrastructure/sql_compat.py`` (pilotos, flags apagados por defecto) no se
modifica en B12J: ver docs/B12J_LEFT_JOIN_SCOPE.md.
"""
from __future__ import annotations

import functools
import re
from typing import Callable, Iterable, MutableMapping, Optional, Tuple

INSTALL_ATTR = "_b12j_left_join_scope"
STATUS_FUNCTION_NAME = "estado_left_join_scope_b12j"
TEMPLATE_CACHE_SIZE = 4096
REQUIRED_NAMES = ("_pg_scope_select", "_pg_scope_select_template_v193", "_pg_aliases_select_v193",
                  "_pg_top_level_positions", "_pg_insert_conditions", "_pg_convert_sql", "_pg_current_inst_id",
                  "_pg_current_dep_id", "PG_INSTITUTION_TABLES", "PG_DEPARTMENT_TABLES")

JOIN_RE = r"\b(?:(LEFT|RIGHT|FULL|INNER|CROSS)\s+(?:OUTER\s+)?)?JOIN\b"
BOUNDARIES = (("join", JOIN_RE), ("from", r"\bFROM\b"), ("where", r"\bWHERE\b"), ("group", r"\bGROUP\s+BY\b"),
              ("having", r"\bHAVING\b"), ("order", r"\bORDER\s+BY\b"), ("limit", r"\bLIMIT\b"),
              ("offset", r"\bOFFSET\b"), ("union", r"\bUNION\b"))
ON_PATTERN = (("on", r"\bON\b"),)
_RESERVED = frozenset({"WHERE", "JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "FULL", "ON", "GROUP", "ORDER", "LIMIT",
                       "HAVING", "OFFSET", "CROSS", "UNION"})
_ITEM_RE = re.compile(r'\s+"?([A-Za-z_][A-Za-z0-9_]*)"?(?:\s+(?:AS\s+)?"?([A-Za-z_][A-Za-z0-9_]*)"?)?', re.I)


class InstallError(RuntimeError):
    """El namespace no tiene el inyector v193 esperado: la instalación B12J falla cerrada en el arranque."""


# ------------------------------------------------------------------------------------------------ análisis puro
def count_placeholders(text: str) -> int:
    """Cantidad de ``%s`` posicionales en ``text`` (``%%`` es un literal)."""
    n, i = 0, 0
    while i < len(text):
        if text.startswith("%%", i):
            i += 2
        elif text.startswith("%s", i):
            n += 1
            i += 2
        else:
            i += 1
    return n


def bounded(sql: str, hits, offset: int = 0) -> list:
    """``_pg_top_level_positions`` acepta una palabra clave al comienzo de CUALQUIER sufijo (p. ej. el ``on`` final de
    ``proyectos_investigacion``).  Se conservan sólo las coincidencias precedidas por un carácter no identificador."""
    out = []
    for hit in hits:
        start = offset + hit[1]
        if start > 0 and (sql[start - 1].isalnum() or sql[start - 1] == "_"):
            continue
        out.append(hit)
    return out


def top_items(sql: str, top_level_positions: Callable) -> list:
    """Ítems de nivel superior: ``[(tipo, tabla, alias, inicio_segmento, fin_segmento)]`` (tipo FROM/LEFT/INNER/...)."""
    pos = bounded(sql, top_level_positions(sql, list(BOUNDARIES)))
    out = []
    for k, (name, _start, end) in enumerate(pos):
        if name not in ("from", "join"):
            continue
        kind = "FROM"
        if name == "join":
            kind = (re.match(JOIN_RE, sql[_start:end], re.I).group(1) or "INNER").upper()
        seg_end = pos[k + 1][1] if k + 1 < len(pos) else len(sql)
        m = _ITEM_RE.match(sql[end:])
        if not m:
            continue
        alias = str(m.group(2) or m.group(1) or "")
        if alias.upper() in _RESERVED:
            alias = m.group(1)
        out.append((kind, m.group(1).lower(), alias, end, seg_end))
    return out


def _conditions(table: str, alias: str, kind: str, inst_id: int, dep_id: Optional[int], inst_tables, dep_tables):
    """Mismos predicados, mismo orden y mismos valores que ``_pg_scope_select_template_v193``."""
    conds, vals = [], []
    if table in inst_tables:
        conds.append(f"{alias}.institucion_id = %s")
        vals.append(int(inst_id))
    if str(kind or "") == "tenant" and table in dep_tables:
        conds.append(f"{alias}.institucion_id = %s")
        vals.append(int(inst_id))
        if dep_id is not None:
            conds.append(f"{alias}.departamento_id = %s")
            vals.append(int(dep_id))
    return conds, vals


def relocatable_aliases(sql: str, pairs, top_level_positions: Callable, scoped: Iterable[str]) -> dict:
    """``{(tabla, alias): (fin_del_ON, fin_del_segmento)}`` de los LEFT JOIN cuyo scope va al ON (vacío = como v193)."""
    scoped = frozenset(scoped)
    relocate = {}
    for kind, table, alias, seg_start, seg_end in top_items(sql, top_level_positions):
        if kind != "LEFT" or table not in scoped or pairs.count((table, alias)) != 1:
            continue
        segment = sql[seg_start:seg_end]
        hits = bounded(sql, top_level_positions(segment, list(ON_PATTERN)), seg_start)
        if hits:
            relocate[(table, alias)] = (seg_start + hits[0][2], seg_start + len(segment.rstrip()))
    if not any(t in scoped and (t, a) not in relocate for t, a in pairs):
        return {}
    return relocate


def build_template(convert_sql: Callable, top_level_positions: Callable, insert_conditions: Callable,
                   aliases_select: Callable, inst_tables, dep_tables) -> Callable:
    """Plantilla pura ``(sql, kind, inst_id, dep_id) -> (sql_scoped, where_values, on_splices)``."""
    inst_tables, dep_tables = frozenset(inst_tables), frozenset(dep_tables)
    scoped = inst_tables | dep_tables

    @functools.lru_cache(maxsize=TEMPLATE_CACHE_SIZE)
    def template(sql_original: str, kind: str, inst_id: int, dep_id: Optional[int]):
        sql = convert_sql(sql_original)
        if str(kind or "") == "auth" or "information_schema" in sql.lower():
            return sql, tuple(), tuple()
        pairs = list(aliases_select(sql))
        relocate = relocatable_aliases(sql, pairs, top_level_positions, scoped)
        where_c, where_v, on_edits = [], [], []
        for table, alias in pairs:
            conds, vals = _conditions(table, alias, kind, inst_id, dep_id, inst_tables, dep_tables)
            if not conds:
                continue
            if (table, alias) in relocate:
                on_end, seg_end = relocate[(table, alias)]
                on_edits.append((on_end, seg_end, conds, vals))
            else:
                where_c.extend(conds)
                where_v.extend(vals)
        splices = []
        for on_end, seg_end, conds, vals in sorted(on_edits, key=lambda e: e[0], reverse=True):
            original = sql[on_end:seg_end].strip()
            replacement = " (" + original + ") AND " + " AND ".join(f"({c})" for c in conds)
            splices.append((count_placeholders(sql[:seg_end]), seg_end, tuple(vals)))
            sql = sql[:on_end] + replacement + sql[seg_end:]
        ordered = tuple((idx, vals) for idx, _end, vals in sorted(splices, key=lambda s: (s[0], s[1])))
        q, values = insert_conditions(sql, where_c, [], where_v)
        return q, tuple(values), ordered

    return template


def merge_params(user_params, where_values, on_splices) -> list:
    """Parámetros finales: los del ON intercalados en su índice, los del WHERE al final (como v193)."""
    user = list(user_params or [])
    out, taken = [], 0
    for idx, vals in on_splices:
        out.extend(user[taken:idx])
        taken = max(taken, idx)
        out.extend(vals)
    out.extend(user[taken:])
    return out + list(where_values)


# ------------------------------------------------------------------------------------------------ instalación
def install_left_join_scope(ns: MutableMapping) -> dict:
    """Re-enlaza ``ns['_pg_scope_select']``.  Falla cerrada si el namespace no expone el inyector v193."""
    missing = [n for n in REQUIRED_NAMES if n not in ns]
    if missing:
        raise InstallError(f"B12J: faltan definiciones del inyector v193: {missing}")
    previous = ns["_pg_scope_select"]
    if getattr(previous, INSTALL_ATTR, None) is not None:
        raise InstallError("B12J: el inyector ya fue re-enlazado (instalación doble)")
    if getattr(previous, "__code__", None) is None or "_pg_scope_select_template_v193" not in previous.__code__.co_names:
        raise InstallError("B12J: _pg_scope_select no es el binding v193 esperado")
    template = build_template(ns["_pg_convert_sql"], ns["_pg_top_level_positions"], ns["_pg_insert_conditions"],
                              ns["_pg_aliases_select_v193"], ns["PG_INSTITUTION_TABLES"], ns["PG_DEPARTMENT_TABLES"])
    stats = {"calls": 0, "relocated_calls": 0}

    def _pg_scope_select(sql, params, scope):
        # Mismas salidas rápidas y misma resolución de scope (B12B) que el v193.
        if not ns["USE_POSTGRESQL"] or not isinstance(scope, dict) or scope.get("kind") == "auth":
            return ns["_pg_convert_sql"](sql), list(params or [])
        if "information_schema" in str(sql or "").lower():
            return ns["_pg_convert_sql"](sql), list(params or [])
        kind = str(scope.get("kind") or "tenant")
        inst_id = scope.get("institucion_id")
        dep_id = scope.get("departamento_id")
        if inst_id is None:
            inst_id = ns["_pg_current_inst_id"]()
        if kind == "tenant" and dep_id is None:
            dep_id = ns["_pg_current_dep_id"]()
        q, where_values, on_splices = template(str(sql or ""), kind, int(inst_id or 0),
                                               int(dep_id) if dep_id is not None else None)
        stats["calls"] += 1
        if on_splices:
            stats["relocated_calls"] += 1
        return q, merge_params(params, where_values, on_splices)

    info = {"wrapped": previous, "template": template, "stats": stats}
    setattr(_pg_scope_select, INSTALL_ATTR, info)
    _pg_scope_select.__wrapped__ = previous
    ns["_pg_scope_select"] = _pg_scope_select

    def estado_left_join_scope_b12j() -> dict:
        cache = template.cache_info()
        return {"instalado": ns.get("_pg_scope_select") is _pg_scope_select, "llamadas": stats["calls"],
                "llamadas_con_scope_en_on": stats["relocated_calls"], "plantillas_cacheadas": cache.currsize}

    ns[STATUS_FUNCTION_NAME] = estado_left_join_scope_b12j
    return {"installed": True, "wrapped": getattr(previous, "__qualname__", repr(previous))}


def installed(ns) -> bool:
    return getattr(ns.get("_pg_scope_select"), INSTALL_ATTR, None) is not None


def template_of(ns) -> Callable:
    return getattr(ns["_pg_scope_select"], INSTALL_ATTR)["template"]


def scope_select_for(ns, sql, params, scope) -> Tuple[str, list]:
    return ns["_pg_scope_select"](sql, params, scope)
