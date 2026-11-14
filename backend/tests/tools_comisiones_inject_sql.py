"""Herramienta de desarrollo (solo lectura, sin base): imprime el SQL que el certificado ejecuta por ``get_conn()`` con el
inyector efectivo B12B v193 + B12J, para escribir el SQL de ``comisiones/repository.py`` con el mismo ambito.

Uso: python tests/tools_comisiones_inject_sql.py <archivo con un SQL por bloque separado por lineas '----'>"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

from materias_support import planes_injector  # noqa: E402

SCOPE = {"kind": "tenant", "institucion_id": 101, "departamento_id": 202}


def inject(sql: str, params=None):
    inj = planes_injector()
    head = sql.lstrip().upper()
    if head.startswith("SELECT") or head.startswith("WITH"):
        return inj["_pg_scope_select"](sql, params or [], SCOPE)
    if head.startswith("INSERT"):
        return inj["_pg_scope_insert"](sql, params or [], SCOPE)
    if head.startswith("UPDATE") or head.startswith("DELETE"):
        return inj["_pg_scope_update_delete"](sql, params or [], SCOPE)
    return inj["_pg_convert_sql"](sql), list(params or [])


if __name__ == "__main__":
    text = Path(sys.argv[1]).read_text(encoding="utf-8")
    for block in [b for b in text.split("\n----\n") if b.strip()]:
        n = block.count("?")
        q, p = inject(block, [f"P{i}" for i in range(n)])
        print(q)
        print("PARAMS:", p)
        print("=" * 100)
