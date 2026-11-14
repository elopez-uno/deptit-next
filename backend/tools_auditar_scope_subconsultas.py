"""Auditoria ESTATICA de subconsultas sin ambito (``DQ-SCOPE-SUBQUERY-B12B``; Etapa 5 / Tanda A).  READ ONLY.

El inyector B12B certificado solo agrega el ambito a las tablas del FROM/JOIN de NIVEL SUPERIOR: una subconsulta
``(SELECT … FROM designaciones d0 WHERE d0.cuil = docentes.cuil)`` lee TODOS los tenants.  El mismo patron puede estar
en SQL NEXT escrito a mano (que reproduce el SQL ya inyectado).  Para cada literal SQL del backend (nativo, motores
vendorizados y ``ref/``), cada subconsulta que lee una tabla con ambito y no menciona ``institucion_id`` ni
``departamento_id`` se clasifica por su correlacion con la consulta externa:
- ``clave_tecnica``: se correlaciona por un id/FK (``x.id = d.periodo_id``, ``… = co.periodo_id``): el padre ya esta en el
  ambito y A2 verifico 0 filas con tenant distinto en esas relaciones -> sin fuga;
- ``parametro_tecnico``: filtra por un id/FK parametrizado (``periodo_id = ?``) que ya pertenece al ambito -> sin fuga;
- ``parametro``: filtra por otro parametro -> depende del valor (revisar el llamador);
- ``clave_negocio``: SOLO por CUIL / nombre / codigo -> FUGA si el mismo valor existe en otro tenant;
- ``sin_correlacion``: agrega toda la tabla -> FUGA.
Uso: ``python -B tools_auditar_scope_subconsultas.py <salida.json>``.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

from analisis.motor.entorno import _inyector  # noqa: E402
from tools_auditar_scope_or import EXCLUIR, _texto  # noqa: E402

_INJ = _inyector()
SCOPED = set(_INJ["PG_INSTITUTION_TABLES"]) | set(_INJ["PG_DEPARTMENT_TABLES"])
_TABLA = re.compile(r"\b(?:FROM|JOIN)\s+\"?([A-Za-z_][A-Za-z0-9_]*)\"?(?:\s+(?:AS\s+)?([A-Za-z_][A-Za-z0-9_]*))?", re.I)
_RESERVADAS = {"WHERE", "JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "ON", "GROUP", "ORDER", "LIMIT", "AND", "OR", "USING"}
_TECNICAS = re.compile(r"(^id$|_id$)")


def _subconsultas(sql: str):
    """(inicio, fin) de cada ``(SELECT …)`` del texto (todas las profundidades)."""
    for m in re.finditer(r"\(\s*SELECT\b", sql, re.I):
        depth = 0
        for i in range(m.start(), len(sql)):
            if sql[i] == "(":
                depth += 1
            elif sql[i] == ")":
                depth -= 1
                if depth == 0:
                    yield m.start(), i + 1
                    break


def _clasificar(seg: str):
    propios = {}
    for t, a in _TABLA.findall(seg):
        alias = a if a and a.upper() not in _RESERVADAS else t
        propios[alias.lower()] = t.lower()
    scoped = sorted({t for t in propios.values() if t in SCOPED})
    if not scoped or re.search(r"institucion_id|departamento_id", seg, re.I):
        return None
    externas = []
    for izq, der in re.findall(r"([A-Za-z_][\w]*\.[A-Za-z_]\w*)\s*=\s*([A-Za-z_][\w]*\.[A-Za-z_]\w*)", seg):
        for lado, otro in ((izq, der), (der, izq)):
            alias, col = lado.split(".")
            if alias.lower() not in propios:
                externas.append((col.lower(), otro.split(".")[1].lower()))
    param_tecnico = re.search(r"\b(?:\w+_id|id)\s*=\s*(?:\?|%s)", seg, re.I)
    if externas and any(_TECNICAS.search(c) or _TECNICAS.search(o) for c, o in externas):
        clase = "clave_tecnica"
    elif param_tecnico:
        clase = "parametro_tecnico"  # p. ej. ``periodo_id = ?``: el id ya pertenece al ambito del llamador
    elif externas:
        clase = "clave_negocio"
    elif re.search(r"(\?|%s)", seg):
        clase = "parametro"
    else:
        clase = "sin_correlacion"
    return {"tablas": scoped, "correlacion": sorted(set(externas)), "clase": clase,
            "subconsulta": " ".join(seg.split())[:300]}


def auditar() -> dict:
    hallazgos = []
    for ruta in sorted(BACKEND.rglob("*.py")):
        rel = ruta.relative_to(BACKEND).as_posix()
        if any(p in EXCLUIR for p in ruta.relative_to(BACKEND).parts) or rel.startswith("tools_"):
            continue
        try:
            arbol = ast.parse(ruta.read_text(encoding="utf-8-sig"))
        except SyntaxError:
            continue
        padres, funcs = {}, {}
        for n in ast.walk(arbol):
            for h in ast.iter_child_nodes(n):
                padres[h] = n
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for h in ast.walk(n):
                    funcs.setdefault(h, n.name)
        for n in ast.walk(arbol):
            if not isinstance(n, (ast.Constant, ast.JoinedStr, ast.BinOp)) or isinstance(
                    padres.get(n), (ast.BinOp, ast.JoinedStr)):
                continue
            sql = _texto(n)
            if not sql or not re.search(r"\(\s*SELECT\b", sql, re.I):
                continue
            for a, b in _subconsultas(sql):
                c = _clasificar(sql[a:b])
                if c:
                    hallazgos.append({"archivo": rel, "linea": n.lineno, "funcion": funcs.get(n, "<modulo>"), **c})
    return {"hallazgos": hallazgos}


if __name__ == "__main__":
    res = auditar()
    Path(sys.argv[1]).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    import collections
    print(collections.Counter(h["clase"] for h in res["hallazgos"]))
