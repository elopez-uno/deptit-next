"""Auditoria ESTATICA de DQ-SCOPE-OR-B12B (Etapa 5 / Tanda A).  READ ONLY: no ejecuta codigo certificado ni toca la base.

Recorre el AST de todo el backend (codigo nativo NEXT, motores vendorizados y sus ``ref/``), arma cada literal SQL
(constantes, concatenaciones de constantes y f-strings con los huecos reemplazados por ``__X__``) y, para cada sentencia
SELECT / WITH / UPDATE / DELETE cuyo WHERE de NIVEL SUPERIOR contiene ``OR``, la pasa por el inyector B12B certificado
(``analisis.motor.entorno._inyector``, texto literal) con un ambito tenant y con el ambito ``planes``:
- ``inyecta``: el inyector agrega condiciones de ambito (alguna tabla de nivel superior es de institucion/departamento);
- ``vulnerable_si_inyectado``: inyecta Y el OR de nivel superior queda fuera de parentesis (``A OR B AND ambito``);
- ``con_proteccion``: resultado tras ``proteger_or`` (el ambito queda aplicado a todo el WHERE).
Ademas lista las construcciones dinamicas de OR (``" OR ".join``) para revision manual.
Uso: ``python -B tools_auditar_scope_or.py <salida.json>``.
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
from analisis.motor.ambito import nivel_superior as _nivel_superior, proteger_or  # noqa: E402

EXCLUIR = (".venv", "__pycache__", "tests", "node_modules")
_SQL = re.compile(r"^\s*(SELECT|WITH|UPDATE|DELETE)\b", re.I)
_FIN = re.compile(r"\b(ORDER\s+BY|GROUP\s+BY|HAVING|LIMIT|OFFSET|RETURNING|UNION|INTERSECT|EXCEPT|FOR\s+UPDATE)\b", re.I)
TENANT = {"kind": "tenant", "institucion_id": 101, "departamento_id": 202}
PLANES = {"kind": "planes", "institucion_id": 101}


def _texto(nodo) -> str | None:
    if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
        return nodo.value
    if isinstance(nodo, ast.JoinedStr):
        partes = []
        for v in nodo.values:
            partes.append(v.value if isinstance(v, ast.Constant) else "__X__")
        return "".join(partes)
    if isinstance(nodo, ast.BinOp) and isinstance(nodo.op, ast.Add):
        a, b = _texto(nodo.left), _texto(nodo.right)
        if a is not None and b is not None:
            return a + b
    return None


def _superior(sql: str) -> str:
    visibles = set(_nivel_superior(sql))
    return "".join(sql[i] if i in visibles else " " for i in range(len(sql)))


def or_superior(sql: str) -> bool:
    """El WHERE de nivel superior (uno o mas, p. ej. ramas UNION) contiene OR fuera de parentesis."""
    sup = _superior(sql)
    for m in re.finditer(r"\bWHERE\b", sup, re.I):
        fin = _FIN.search(sup, m.end())
        siguiente = re.search(r"\bWHERE\b", sup[m.end():], re.I)
        tope = min(fin.start() if fin else len(sup), m.end() + siguiente.start() if siguiente else len(sup))
        if re.search(r"\bOR\b", sup[m.end():tope], re.I):
            return True
    return False


def _inyectar(inj, sql: str, ambito: dict):
    head = sql.lstrip().upper()
    if head.startswith(("SELECT", "WITH")):
        q, p = inj["_pg_scope_select"](sql, [], ambito)
    else:
        q, p = inj["_pg_scope_update_delete"](sql, [], ambito)
    return q, len(p)


def auditar() -> dict:
    inj = _inyector()
    casos, dinamicos = [], []
    for ruta in sorted(BACKEND.rglob("*.py")):
        rel = ruta.relative_to(BACKEND).as_posix()
        if any(p in EXCLUIR for p in ruta.relative_to(BACKEND).parts) or rel.startswith("tools_"):
            continue
        src = ruta.read_text(encoding="utf-8-sig")
        try:
            arbol = ast.parse(src)
        except SyntaxError:
            continue
        padres = {}
        for n in ast.walk(arbol):
            for h in ast.iter_child_nodes(n):
                padres[h] = n
        funcs = {}
        for n in ast.walk(arbol):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for h in ast.walk(n):
                    funcs.setdefault(h, n.name)  # el mas externo
        vistos = set()
        for n in ast.walk(arbol):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "join" \
                    and isinstance(n.func.value, ast.Constant) and isinstance(n.func.value.value, str) \
                    and re.fullmatch(r"\s*OR\s*", n.func.value.value, re.I):
                dinamicos.append({"archivo": rel, "linea": n.lineno, "funcion": funcs.get(n, "<modulo>")})
            if not isinstance(n, (ast.Constant, ast.JoinedStr, ast.BinOp)):
                continue
            if isinstance(padres.get(n), (ast.BinOp, ast.JoinedStr)):
                continue  # se arma desde el nodo mas externo
            sql = _texto(n)
            if not sql or not _SQL.match(sql) or not re.search(r"\bWHERE\b", sql, re.I):
                continue
            if not re.search(r"\bOR\b", sql, re.I) or (rel, n.lineno) in vistos:
                continue
            vistos.add((rel, n.lineno))
            sup_or = or_superior(sql)
            caso = {"archivo": rel, "linea": n.lineno, "funcion": funcs.get(n, "<modulo>"),
                    "or_nivel_superior": sup_or, "sql": " ".join(sql.split())[:600]}
            if sup_or:
                for nombre, amb in (("tenant", TENANT), ("planes", PLANES)):
                    try:
                        q, k = _inyectar(inj, sql, amb)
                        qp, _ = _inyectar(inj, proteger_or(sql), amb)
                    except Exception as e:  # noqa: BLE001
                        caso[nombre] = {"error": type(e).__name__}
                        continue
                    caso[nombre] = {"condiciones": k, "vulnerable_si_inyectado": k > 0,
                                    "protegido_por_proteger_or": k > 0 and not or_superior_tras(qp, sql),
                                    "sql_inyectado": " ".join(q.split())[:700]}
            casos.append(caso)
    return {"casos": casos, "or_dinamicos": dinamicos}


def or_superior_tras(sql_inyectado: str, original: str) -> bool:
    """Tras proteger_or + inyeccion, ¿queda algun OR de nivel superior? (False = el ambito cubre todo el WHERE)."""
    return or_superior(sql_inyectado)


if __name__ == "__main__":
    salida = Path(sys.argv[1])
    res = auditar()
    salida.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    total = len(res["casos"])
    sup = [c for c in res["casos"] if c["or_nivel_superior"]]
    vul = [c for c in sup if c.get("tenant", {}).get("vulnerable_si_inyectado")
           or c.get("planes", {}).get("vulnerable_si_inyectado")]
    print(f"sql_con_or={total} or_nivel_superior={len(sup)} inyectables_vulnerables={len(vul)} "
          f"or_dinamicos={len(res['or_dinamicos'])}")
