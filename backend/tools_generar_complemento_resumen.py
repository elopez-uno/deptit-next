"""Generador del COMPLEMENTO certificado del Resumen docente (E4-05) sobre el motor de lectura de Analisis.

El Resumen docente (entry l. 60845-61197, sin la seccion Estado de consulta / Mensaje, que es E4-06) usa 251
funciones; 216 ya estan, literales, en ``analisis/motor/certificado.py`` (cierre de la pagina Analisis, cuyo corte
l. 66604 no redefine ninguna de ellas despues de l. 60845).  Este script escribe en
``backend/integraciones/resumen_motor/``:

- ``complemento.py``: el texto LITERAL de las definiciones de nivel modulo del entry (anteriores a l. 60845, en el ORDEN
  DEL ENTRY, sin decoradores) que forman el cierre transitivo de ``RAICES`` y que NO estan en el motor de Analisis.
  Las referencias a ``deptit_refactor`` apuntan a ``analisis.motor.ref`` (la copia literal ya existente); si falta un
  modulo, el script falla (no copia nada nuevo).
- ``metadata.py``: huella del entry, bloques, writers de negocio / tareas de sistema del registro B10 dentro del
  complemento (no se vendorizan sus cuerpos: el entorno los bloquea / anula como en el motor).

Fuera del complemento, a proposito (owner NEXT ya validado contra el certificado): el sueldo estimado
(``SueldosService.sueldo_docente_resumen``, H2) y Actividades Especiales
(``ActividadesService.participaciones_docente_institucion``, G5).
No ejecuta codigo certificado ni toca la base.  Uso: ``python -B tools_generar_complemento_resumen.py``.
"""
from __future__ import annotations

import ast
import collections
import hashlib
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
REF = Path(r"C:\DEPTIT_NEXT\reference_fix02")
ENTRY = REF / "app_postgresql_refactor_b13fix02_uat_fixes.py"
BACKEND = Path(__file__).resolve().parent
MOTOR = BACKEND / "analisis" / "motor"
OUT = BACKEND / "integraciones" / "resumen_motor"
CUTOFF = 60845
NUEVO = "analisis.motor.ref"
RAICES = [
    # Datos generales
    "estado_actual_docente", "fecha_finalizacion_resumen_docente", "get_trayectoria_docente_institucional_v149",
    # Tarjeta del resumen actual (render_tarjeta_resumen_actual_docente, l. 27714): sus lecturas
    "get_resumen_actual_periodo_docente", "es_docente_prestado_local",
    # Actos administrativos (v263 + v266)
    "get_actos_docente_resumen_v263",
    # Comisiones, cronograma (render_cronograma_semanal_docente, l. 31994: sus lecturas y helpers) y superposiciones
    "get_comisiones_docente", "get_horarios_docente_periodo", "_expandir_horarios_por_materias_comision_v131",
    "_normalizar_dia_v95", "_minutos_v95", "_hora_texto_v95", "_abreviar_asignatura_v95",
    "get_superposiciones_docente_institucional_v149",
    # Materias historicas
    "get_materias_historicas_docente",
    # Busqueda de docentes (filtrar_dataframe_por_texto)
    "filtrar_dataframe_por_texto",
]
CONSTANTES = ["DIAS_SEMANA_V95"]
# E4-06: seccion "Mensaje para consultar la designación" (l. 61200-61275): el generador de mensaje (lectura).  El estado
# de consulta lo leen Disposiciones (lectura) y Designaciones (writer, owner B10); no se vendorizan.
RAICES_MENSAJE = ["generar_mensaje_consulta_designacion_docente"]


PKG = REF / "deptit_refactor"
PROPIO = "integraciones.resumen_motor.ref"


def _ruta(base: Path, partes: list) -> Path | None:
    for cand in (base.joinpath(*partes).with_suffix(".py"), base.joinpath(*partes) / "__init__.py"):
        if cand.exists():
            return cand
    return None


def _modulo(partes: list):
    """(partes del modulo, es_atributo): ``deptit_refactor.a.b`` puede ser modulo o ``modulo.atributo``."""
    if _ruta(PKG, partes):
        return partes, False
    if len(partes) > 1 and _ruta(PKG, partes[:-1]):
        return partes[:-1], True
    return None, False


def reescribir(texto: str, copiados: set) -> str:
    """``deptit_refactor.X`` -> ``analisis.motor.ref.X`` si la copia literal de Analisis ya lo tiene; si no, el modulo
    se copia LITERAL a ``integraciones/resumen_motor/ref`` (con sus dependencias) y la referencia apunta alli."""
    def repl(m):
        partes = m.group(1).strip(".").split(".")
        mod, _ = _modulo(partes)
        if mod is None or _ruta(MOTOR / "ref", mod):
            return NUEVO + m.group(1)
        copiados.add(tuple(mod))
        return PROPIO + m.group(1)
    return re.sub(r"\bdeptit_refactor((?:\.\w+)+)", repl, texto)


def copiar_modulos(copiados: set) -> None:
    hechos: set = set()
    while copiados - hechos:
        mod = sorted(copiados - hechos)[0]
        hechos.add(mod)
        origen = _ruta(PKG, list(mod))
        texto = origen.read_text(encoding="utf-8")
        if re.search(r"^\s*from\s+\.", texto, re.M):
            raise SystemExit(f"import relativo no soportado en {origen}")
        destino = OUT / "ref" / origen.relative_to(PKG)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(reescribir(texto, copiados), encoding="utf-8", newline="\n")
    for carpeta in [OUT / "ref"] + [p for p in (OUT / "ref").rglob("*") if p.is_dir()]:
        if carpeta.exists() and not (carpeta / "__init__.py").exists():
            (carpeta / "__init__.py").write_text("", encoding="utf-8")


def generar(raices, constantes_raiz, archivo, meta, descripcion, previos=()) -> None:
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
    seen, queue = set(), list(raices) + list(constantes_raiz)
    while queue:
        n = queue.pop()
        if n in seen or n == "st":
            continue
        seen.add(n)
        for d in defs.get(n, []):
            queue.extend({x.id for x in ast.walk(d) if isinstance(x, ast.Name)} - seen)
        for a in aliases.get(n, []):
            queue.append(a.value.id)

    motor = (MOTOR / "certificado.py").read_text(encoding="utf-8")
    for previo in previos:  # complementos ya generados: no se duplican
        motor += "\n" + (OUT / previo).read_text(encoding="utf-8")
    en_motor = set(re.findall(r"^def (\w+)\(", motor, re.M)) | set(re.findall(r"^(\w+)\s*=", motor, re.M))
    sys.path.insert(0, str(REF))
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
            if node.decorator_list:  # sin decoradores (caches Streamlit)
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
    cuerpo = reescribir(constantes + "\n" + "\n\n".join(bloques), copiados)
    OUT.mkdir(parents=True, exist_ok=True)
    copiar_modulos(copiados)
    cabecera = (f'"""GENERADO por tools_generar_complemento_resumen.py -- NO EDITAR A MANO.\n\n'
                f"Texto literal del entry certificado B13-FIX02 ({ENTRY.name}, sha256 {huella}): definiciones del\n"
                f"{descripcion}, {len(bloques)} bloques en el orden del entry.\n"
                f"Se ejecuta DESPUES de ``analisis/motor/certificado.py`` en el mismo namespace del request\n"
                f"(``integraciones.resumen_docente``); nunca a nivel modulo.\n"
                f'"""\n# flake8: noqa\n# fmt: off\n\n')
    (OUT / archivo).write_text(cabecera + cuerpo, encoding="utf-8", newline="\n")
    (OUT / meta).write_text(
        '"""GENERADO -- NO EDITAR.  Metadatos del complemento certificado del Resumen docente."""\n\n'
        f"ENTRY_SHA256 = {huella!r}\n"
        f"BLOQUES = {len(bloques)}\n"
        f"NOMBRES = {nombres!r}\n"
        f"WRITERS_NEGOCIO = {negocio!r}\n"
        f"TAREAS_SISTEMA = {sistema!r}\n", encoding="utf-8", newline="\n")
    (OUT / "__init__.py").write_text('"""Complemento certificado del Resumen docente (generado)."""\n', encoding="utf-8")
    print(f"{archivo}: bloques={len(bloques)} funciones={sorted(set(nombres))} negocio={negocio} "
          f"sistema={sorted(sistema)} literales={sorted(literales)}")


def main() -> None:
    generar(RAICES, CONSTANTES, "complemento.py", "metadata.py",
            "Resumen docente (E4-05) que no estan en el motor de Analisis")
    generar(RAICES_MENSAJE, [], "complemento_mensaje.py", "metadata_mensaje.py",
            "Mensaje para consultar la designación (E4-06) que no estan en el motor de Analisis ni en el\n"
            "complemento del Resumen", previos=("complemento.py",))


if __name__ == "__main__":
    main()
