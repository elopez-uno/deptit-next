"""Generador del COMPLEMENTO certificado de la Carga rápida integral (E4-09) sobre el motor de lectura de Analisis.

La pestaña "📥 Carga rápida" de Docentes (entry l. 61278-61652, seccion "Carga rápida integral de docentes y
designaciones") usa, para LEER, el Excel integral (``generar_excel_integral_docentes_designaciones``), su lector
(``leer_excel_integral_docentes_designaciones``), la revision (``analizar_carga_integral_docentes_designaciones``), la
identidad estable y la foto fisica v220 (``_clave_designacion_integral_v220``, ``_snapshot_designaciones_integral_v220``)
y la mezcla parcial v247 (``_mezclar_docente_existente_excel_v247``).  Este script escribe en
``backend/integraciones/carga_integral_motor/``:

- ``complemento.py``: el texto LITERAL de las definiciones de nivel modulo del entry ANTERIORES a la pestaña
  (l. 61278, en el ORDEN DEL ENTRY, sin decoradores) que forman el cierre transitivo de ``RAICES`` y que NO estan en el
  motor de Analisis.  Las referencias a ``deptit_refactor`` apuntan a ``analisis.motor.ref`` o a una copia literal
  propia (mismo criterio que ``tools_generar_complemento_resumen.py``, cuyas funciones reutiliza).
- ``metadata.py``: huella del entry, bloques, writers de negocio / tareas de sistema del cierre (no se vendorizan:
  el entorno los bloquea).
Ademas VERIFICA que ninguna funcion del cierre que ya esta en el motor (corte l. 66604) se redefina entre la pestaña y
ese corte: si ocurriera, el motor tendria una version posterior a la que ejecuta la pagina y el script falla.
Las ESCRITURAS de la carga no se vendorizan: son los contratos de Docentes y Designaciones (D-E4-01).
No ejecuta codigo certificado ni toca la base.  Uso: ``python -B tools_generar_complemento_carga_integral.py``.
"""
from __future__ import annotations

import ast
import collections
import hashlib
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))
import tools_generar_complemento_resumen as T  # noqa: E402

CUTOFF = 61278          # with tab6: (entry) — "Carga rápida integral de docentes y designaciones"
MOTOR_CUTOFF = 66604    # corte del motor de Analisis
T.OUT = BACKEND / "integraciones" / "carga_integral_motor"
T.PROPIO = "integraciones.carga_integral_motor.ref"
RAICES = [
    "generar_excel_integral_docentes_designaciones", "leer_excel_integral_docentes_designaciones",
    "analizar_carga_integral_docentes_designaciones", "_clave_designacion_integral_v220",
    "_snapshot_designaciones_integral_v220", "_mezclar_docente_existente_excel_v247", "docente_existe",
    # helpers que la pagina llama directamente (l. 61474-61620)
    "limpiar_cuil", "nombre_completo", "limpiar_texto_tabla",
]


def main() -> None:
    src = T.ENTRY.read_text(encoding="utf-8")
    tree = ast.parse(src)
    defs, aliases = collections.defaultdict(list), collections.defaultdict(list)
    tardias = collections.defaultdict(list)
    for node in tree.body:
        nombre = None
        if isinstance(node, ast.FunctionDef):
            nombre = node.name
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            nombre = node.targets[0].id
        if nombre is None:
            continue
        if node.lineno < CUTOFF:
            if isinstance(node, ast.FunctionDef):
                defs[nombre].append(node)
            elif isinstance(node.value, ast.Name):
                aliases[nombre].append(node)
        elif node.lineno < MOTOR_CUTOFF:
            tardias[nombre].append(node.lineno)
    seen, queue = set(), list(RAICES)
    while queue:
        n = queue.pop()
        if n in seen or n == "st":
            continue
        seen.add(n)
        for d in defs.get(n, []):
            queue.extend({x.id for x in ast.walk(d) if isinstance(x, ast.Name)} - seen)
        for a in aliases.get(n, []):
            queue.append(a.value.id)

    motor = (T.MOTOR / "certificado.py").read_text(encoding="utf-8")
    en_motor = set(re.findall(r"^def (\w+)\(", motor, re.M)) | set(re.findall(r"^(\w+)\s*=", motor, re.M))
    conflictos = sorted(n for n in seen & en_motor if tardias.get(n))
    if conflictos:
        raise SystemExit(f"funciones del motor redefinidas entre l. {CUTOFF} y {MOTOR_CUTOFF}: {conflictos}")
    sys.path.insert(0, str(T.REF))
    from deptit_refactor.security.legacy_write_actions import BUSINESS_WRITERS, SYSTEM_WRITERS  # noqa: E402
    negocio = sorted(n for n in BUSINESS_WRITERS if n in seen and n not in en_motor)
    sistema = {n: SYSTEM_WRITERS[n][0] for n in sorted(SYSTEM_WRITERS) if n in seen and n not in en_motor}
    excluir = en_motor | set(negocio) | set(sistema)

    literales = {}
    for node in tree.body:
        if node.lineno >= CUTOFF:
            break
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            nombre = node.targets[0].id
            if nombre in seen and nombre not in excluir and nombre not in literales \
                    and not isinstance(node.value, ast.Name):
                try:
                    ast.literal_eval(node.value)
                    literales[nombre] = ast.get_source_segment(src, node)
                except Exception:
                    pass
    bloques, nombres = [], []
    for node in tree.body:
        if node.lineno >= CUTOFF:
            continue
        if isinstance(node, ast.FunctionDef) and node.name in seen and node.name not in excluir:
            texto = ast.get_source_segment(src, node)
            if node.decorator_list:  # sin decoradores (caches Streamlit / lru_cache)
                texto = "\n".join(l for l in texto.splitlines() if not l.lstrip().startswith("@"))
            bloques.append(f"# --- entry l. {node.lineno}-{node.end_lineno}\n{texto}\n")
            nombres.append(node.name)
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and isinstance(node.value, ast.Name) and node.targets[0].id in seen \
                and node.targets[0].id not in excluir:
            bloques.append(f"# --- entry l. {node.lineno}\n{ast.get_source_segment(src, node)}\n")
            nombres.append(node.targets[0].id)

    huella = hashlib.sha256(src.encode("utf-8")).hexdigest()
    constantes = "".join(f"# --- entry (literal)\n{literales[k]}\n" for k in sorted(literales))
    copiados: set = set()
    cuerpo = T.reescribir(constantes + "\n" + "\n\n".join(bloques), copiados)
    T.OUT.mkdir(parents=True, exist_ok=True)
    T.copiar_modulos(copiados)
    cabecera = (f'"""GENERADO por tools_generar_complemento_carga_integral.py -- NO EDITAR A MANO.\n\n'
                f"Texto literal del entry certificado B13-FIX02 ({T.ENTRY.name}, sha256 {huella}): definiciones de la\n"
                f"Carga rápida integral (E4-09) que no estan en el motor de Analisis, {len(bloques)} bloques en el orden\n"
                f"del entry.  Se ejecuta DESPUES de ``analisis/motor/certificado.py`` en el mismo namespace del request\n"
                f"(``integraciones.carga_integral``); nunca a nivel modulo.\n"
                f'"""\n# flake8: noqa\n# fmt: off\n\n')
    (T.OUT / "complemento.py").write_text(cabecera + cuerpo, encoding="utf-8", newline="\n")
    (T.OUT / "metadata.py").write_text(
        '"""GENERADO -- NO EDITAR.  Metadatos del complemento certificado de la Carga rápida integral."""\n\n'
        f"ENTRY_SHA256 = {huella!r}\n"
        f"CUTOFF = {CUTOFF}\n"
        f"BLOQUES = {len(bloques)}\n"
        f"NOMBRES = {nombres!r}\n"
        f"EN_MOTOR = {sorted(seen & en_motor)!r}\n"
        f"WRITERS_NEGOCIO = {negocio!r}\n"
        f"TAREAS_SISTEMA = {sistema!r}\n", encoding="utf-8", newline="\n")
    (T.OUT / "__init__.py").write_text('"""Complemento certificado de la Carga rápida integral (generado)."""\n',
                                       encoding="utf-8")
    print(f"complemento.py: bloques={len(bloques)} funciones={sorted(set(nombres))}\nnegocio={negocio} "
          f"sistema={sorted(sistema)} literales={sorted(literales)}\nen_motor={len(seen & en_motor)}")


if __name__ == "__main__":
    main()
