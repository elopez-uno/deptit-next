"""Generador del motor de LECTURA certificado de Analisis / Productividad (decision de implementacion del bloque).

Lee la fuente certificada ``C:\\DEPTIT_NEXT\\reference_fix02`` (solo lectura) y escribe ``backend/analisis/motor/``:

- ``certificado.py``: el texto LITERAL de las definiciones de nivel modulo del entry que forman el cierre transitivo de
  nombres de la pagina ``📊 Analisis`` (l. 66604-67763), en el ORDEN DEL ENTRY y anteriores al ruteo, con sus alias
  ``x = y`` (cadenas ``_pre_vNNN``) y las constantes literales que usan.  Sin decoradores (las caches Streamlit se
  sustituyen por memoizacion del request, D-AM12).  Cada bloque lleva su linea de origen.
- ``inyector.py``: el inyector de ambito efectivo del entry (B12B v193 + tablas de ambito) que ``get_conn()`` aplica.
- ``ref/``: los modulos de ``deptit_refactor`` que ese codigo importa (cierre de importaciones), copiados LITERALMENTE
  con el prefijo ``deptit_refactor`` reescrito a ``analisis.motor.ref``.  Se excluyen los pilotos (``integration``):
  el motor los fija en ``off`` (D-AL11 / D-AM12) y sus importaciones estan protegidas por ``try`` en el certificado.
- ``metadata.py``: nombres con cache Streamlit, writers de negocio y tareas de sistema del registro B10 que el cierre
  contiene (el motor bloquea los primeros y aplica la compuerta B12F a las segundas), y la huella sha256 del entry.

No ejecuta codigo certificado ni toca la base.  Uso: ``python -B tools_generar_motor_analisis.py``.
"""
from __future__ import annotations

import ast
import collections
import hashlib
import re
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True
REF = Path(r"C:\DEPTIT_NEXT\reference_fix02")
ENTRY = REF / "app_postgresql_refactor_b13fix02_uat_fixes.py"
PKG = REF / "deptit_refactor"
OUT = Path(__file__).resolve().parent / "analisis" / "motor"
PAGE = (66604, 67763)
CUTOFF = PAGE[0]
NUEVO = "analisis.motor.ref"
EXCLUIR_PAQUETES = ("integration",)
# Inyector efectivo (periodos_support.certified_injector + materias_support.planes_injector).
INYECTOR = [("_pg_quote_literal_text", 0), ("_pg_split_sql_args", 0), ("_pg_convert_group_concat", 0),
            ("_pg_convert_sql", 0), ("_pg_top_level_positions", 0), ("_pg_insert_conditions", 0),
            ("_pg_aliases_select_v193", 0), ("_pg_scope_select_template_v193", 0), ("_pg_scope_insert", 0),
            ("_pg_scope_update_delete", 0), ("_pg_scope_select", 1)]


def reescribir(texto: str) -> str:
    return re.sub(r"\bdeptit_refactor\b", NUEVO, texto)


# 6A-B1: un servicio productivo nunca instala paquetes en runtime.  ``_obtener_document_python_docx`` (entry l. 7585)
# intentaba ``pip install python-docx`` si el import fallaba; python-docx ya es dependencia fija (requirements.txt), asi
# que se elimina SOLO ese intento: con el paquete instalado el resultado es identico; sin el, el mismo RuntimeError.
INSTALACION_DINAMICA = '''    try:
        from docx import Document
        return Document
    except Exception:
        pass

    try:
        import sys
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "python-docx"])
        from docx import Document
        return Document
    except Exception as e:'''
SIN_INSTALACION_DINAMICA = '''    # NEXT 6A-B1: sin instalacion dinamica de paquetes (python-docx esta en requirements.txt).
    try:
        from docx import Document
        return Document
    except Exception as e:'''


def sin_instalacion_dinamica(texto: str) -> str:
    if texto.count(INSTALACION_DINAMICA) != 1:
        raise SystemExit("ABORT: el bloque de instalacion dinamica de python-docx no aparece exactamente una vez")
    return texto.replace(INSTALACION_DINAMICA, SIN_INSTALACION_DINAMICA)


def main() -> None:
    src = ENTRY.read_text(encoding="utf-8")
    tree = ast.parse(src)
    defs, aliases = collections.defaultdict(list), collections.defaultdict(list)
    for node in tree.body:
        if node.lineno >= CUTOFF:
            continue
        if isinstance(node, ast.FunctionDef):
            defs[node.name].append(node)
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and isinstance(node.value, ast.Name):
            aliases[node.targets[0].id].append(node)
    start = {x.id for x in ast.walk(tree) if isinstance(x, ast.Name) and PAGE[0] <= getattr(x, "lineno", 0) <= PAGE[1]}
    seen, queue = set(), list(start)
    while queue:
        n = queue.pop()
        if n in seen or n == "st":
            continue
        seen.add(n)
        for d in defs.get(n, []):
            queue.extend({x.id for x in ast.walk(d) if isinstance(x, ast.Name)} - seen)
        for a in aliases.get(n, []):
            queue.append(a.value.id)

    bloques, cacheadas, literales = [], set(), {}
    for node in tree.body:
        if node.lineno >= CUTOFF:
            break
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            nombre = node.targets[0].id
            if nombre in seen and nombre not in literales and not isinstance(node.value, ast.Name):
                try:
                    ast.literal_eval(node.value)
                    literales[nombre] = ast.get_source_segment(src, node)
                except Exception:
                    pass
    for node in tree.body:
        if node.lineno >= CUTOFF:
            continue
        if isinstance(node, ast.FunctionDef) and node.name in seen:
            if any("cache" in ast.unparse(d) for d in node.decorator_list):
                cacheadas.add(node.name)
            bloques.append(f"# --- entry l. {node.lineno}-{node.end_lineno}\n{ast.get_source_segment(src, node)}\n")
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and isinstance(node.value, ast.Name) and node.targets[0].id in seen:
            bloques.append(f"# --- entry l. {node.lineno}\n{ast.get_source_segment(src, node)}\n")

    huella = hashlib.sha256(src.encode("utf-8")).hexdigest()
    cabecera = (f'"""GENERADO por tools_generar_motor_analisis.py -- NO EDITAR A MANO.\n\n'
                f"Texto literal del entry certificado B13-FIX02 ({ENTRY.name}, sha256 {huella}): cierre transitivo de la\n"
                f"pagina Analisis (l. {PAGE[0]}-{PAGE[1]}), {len(bloques)} bloques en el orden del entry.  Las referencias a\n"
                f"``deptit_refactor`` apuntan a la copia literal ``{NUEVO}``.  Se compila y ejecuta por request en un\n"
                f"namespace propio (``analisis.motor.entorno``); nunca a nivel modulo.\n"
                f'"""\n# flake8: noqa\n# fmt: off\n\n')
    constantes = "".join(f"# --- entry (literal)\n{literales[k]}\n" for k in sorted(literales))
    cuerpo = sin_instalacion_dinamica(reescribir(constantes + "\n" + "\n\n".join(bloques)))
    # Solo se reemplaza lo generado (``entorno.py`` es codigo NEXT escrito a mano).
    if (OUT / "ref").exists():
        shutil.rmtree(OUT / "ref")
    (OUT / "ref").mkdir(parents=True)
    (OUT / "certificado.py").write_text(cabecera + cuerpo, encoding="utf-8", newline="\n")

    # inyector
    iny_bloques = []
    for nombre, indice in INYECTOR:
        nodo = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == nombre][indice]
        iny_bloques.append(f"# --- entry l. {nodo.lineno}-{nodo.end_lineno} ({nombre} #{indice})\n"
                           f"{ast.get_source_segment(src, nodo)}\n")
    conjuntos = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and node.targets[0].id in ("PG_INSTITUTION_TABLES", "PG_DEPARTMENT_TABLES") \
                and node.targets[0].id not in conjuntos:
            conjuntos[node.targets[0].id] = ast.get_source_segment(src, node)
    (OUT / "inyector.py").write_text(
        '"""GENERADO -- NO EDITAR.  Inyector de ambito B12B efectivo del entry (v193 para SELECT; original para\n'
        'INSERT/UPDATE/DELETE), texto literal; ``_pg_scope_select`` lo re-enlaza B12J (``ref.b12j.left_join_scope``)."""\n'
        "# flake8: noqa\n# fmt: off\n\n" + reescribir("\n".join(conjuntos.values()) + "\n\n" + "\n\n".join(iny_bloques)),
        encoding="utf-8", newline="\n")

    # deptit_refactor: cierre de importaciones
    pendientes = set(re.findall(r"\bdeptit_refactor((?:\.\w+)+)", cuerpo.replace(NUEVO, "deptit_refactor")))
    pendientes |= {".b12j.left_join_scope", ".catalogs.comisiones", ".catalogs.designaciones", ".catalogs.materias",
                   ".catalogs.movimientos"}
    copiados, excluidos = set(), set()
    while pendientes:
        mod = pendientes.pop()
        partes = mod.strip(".").split(".")
        if partes[0] in EXCLUIR_PAQUETES:
            excluidos.add(mod)
            continue
        ruta = PKG.joinpath(*partes).with_suffix(".py")
        if not ruta.exists():
            ruta2 = PKG.joinpath(*partes) / "__init__.py"
            if ruta2.exists():
                ruta = ruta2
            else:
                # ``from deptit_refactor.x import nombre`` (nombre = atributo, no modulo)
                pendientes.add("." + ".".join(partes[:-1])) if len(partes) > 1 else None
                continue
        if ruta in copiados:
            continue
        copiados.add(ruta)
        texto = ruta.read_text(encoding="utf-8")
        for m in re.findall(r"\bdeptit_refactor((?:\.\w+)+)", texto):
            pendientes.add(m)
        for m in re.findall(r"^\s*from\s+(\.+)(\w+(?:\.\w+)*)?\s+import", texto, flags=re.M):
            nivel, resto = len(m[0]), m[1]
            base = list(ruta.relative_to(PKG).parent.parts)
            base = base[:len(base) - (nivel - 1)] if nivel > 1 else base
            pendientes.add("." + ".".join(base + (resto.split(".") if resto else [])))
        destino = OUT / "ref" / ruta.relative_to(PKG)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(reescribir(texto), encoding="utf-8", newline="\n")
    for carpeta in [OUT / "ref"] + [p for p in (OUT / "ref").rglob("*") if p.is_dir()]:
        init = carpeta / "__init__.py"
        if not init.exists():
            init.write_text("", encoding="utf-8")

    # caches instaladas en tiempo de ejecucion (``globals()[nombre] = wrapper``): v199 (lista) y v200 (dict)
    runtime = set()
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)                 and node.targets[0].id in ("_LECTURAS_CACHE_V199", "_DEPENDENCIAS_LECTURAS_V200"):
            valor = ast.literal_eval(node.value)
            runtime |= set(valor if isinstance(valor, list) else valor.keys())
    runtime &= seen

    # metadata: registro B10
    sys.path.insert(0, str(REF))
    from deptit_refactor.security.legacy_write_actions import BUSINESS_WRITERS, SYSTEM_WRITERS  # noqa: E402
    negocio = sorted(n for n in BUSINESS_WRITERS if n in seen)
    sistema = {n: SYSTEM_WRITERS[n][0] for n in sorted(SYSTEM_WRITERS) if n in seen}
    (OUT / "metadata.py").write_text(
        '"""GENERADO -- NO EDITAR.  Metadatos del motor certificado de Analisis."""\n\n'
        f"ENTRY_SHA256 = {huella!r}\n"
        f"BLOQUES = {len(bloques)}\n"
        f"CACHEADAS = {sorted(cacheadas)!r}\n"
        f"CACHEADAS_RUNTIME = {sorted(runtime)!r}\n"
        f"WRITERS_NEGOCIO = {negocio!r}\n"
        f"TAREAS_SISTEMA = {sistema!r}\n"
        f"MODULOS_REF = {sorted(str(p.relative_to(PKG)).replace(chr(92), '/') for p in copiados)!r}\n"
        f"EXCLUIDOS = {sorted(excluidos)!r}\n", encoding="utf-8", newline="\n")
    (OUT / "__init__.py").write_text('"""Motor de lectura certificado de Analisis (generado + entorno)."""\n',
                                     encoding="utf-8")
    print(f"bloques={len(bloques)} cacheadas={len(cacheadas)} negocio={negocio} sistema={len(sistema)} "
          f"ref={len(copiados)} excluidos={sorted(excluidos)}")


if __name__ == "__main__":
    main()
