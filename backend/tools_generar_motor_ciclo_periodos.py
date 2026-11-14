"""Generador del MOTOR CERTIFICADO de las operaciones de Períodos (E4-10..E4-12): texto LITERAL de B13-FIX02.

Escribe en ``backend/integraciones/ciclo_periodos/motor/``:
- ``complemento.py``: las definiciones de nivel modulo del entry ANTERIORES a la pagina Periodos (l. 61933), en el ORDEN
  DEL ENTRY y sin decoradores, que forman el cierre transitivo de ``RAICES``: la cascada que ``crear_periodo_atomico``
  (B12C) invoca (vencimientos v268, copia v266 de designaciones con sus vinculos documentales, renovacion de
  investigacion y extension, finalizacion del periodo anterior, ``registrar_movimiento`` y las tareas de sistema de
  comisiones / cargos), el diagnostico y la reversion del ultimo cierre, y los contadores del periodo vacio.  A
  diferencia del motor de LECTURA de Analisis, aca los writers de negocio y las tareas de sistema SI se vendorizan: se
  ejecutan dentro de la unica transaccion de la operacion de Periodos (D-E4-06).  La infraestructura de conexion
  (``get_conn``, ``_pg_raw_conn``, inyector B12B/B12J, cachés) NO se copia: la provee el entorno NEXT.
  Las referencias a ``deptit_refactor`` se copian literales a ``motor/ref`` (incluye ``b12c/periodo_atomico.py``).
- ``metadata.py``: huella del entry, bloques, writers de negocio / tareas de sistema del cierre.
Ademas copia LITERALES (paquete propio, imports relativos intactos) los modulos B11 ``operations/backup_gate.py``,
``backup_manifest.py`` y ``db_identity.py`` a ``ciclo_periodos/ref_b11/``.
No ejecuta codigo certificado ni toca la base.  Uso: ``python -B tools_generar_motor_ciclo_periodos.py``.
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
BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))
import tools_generar_complemento_resumen as T  # noqa: E402

CUTOFF = 61933  # elif modulo == "🗓️ Períodos": (AST)
BASE = BACKEND / "integraciones" / "ciclo_periodos"
T.OUT = BASE / "motor"
T.PROPIO = "integraciones.ciclo_periodos.motor.ref"
RAICES = [
    # E4-10: lo que crear_periodo_atomico (b12c/periodo_atomico.py) toma del namespace (REQUIRED_CALLABLES)
    "nombre_periodo", "fechas_periodo", "PeriodoDuplicadoError", "registrar_movimiento", "safe_date",
    "_finalizar_comisiones_si_sin_designacion_docente_v214", "sincronizar_cargos_asignaciones_docente_periodo",
    "get_designaciones", "_copiar_designaciones_periodo_pre_v266", "get_movimientos_designaciones_periodo_v266",
    "vincular_acto_designacion_v266", "vincular_acto_movimiento_v266", "_clave_cuil",
    "copiar_investigacion_vigente_periodo", "copiar_extension_vigente_periodo",
    "finalizar_designaciones_activas_periodo", "get_periodo_por_nombre", "get_periodos", "get_periodo_abierto",
    "get_ultimo_periodo",
    # E4-11
    "diagnosticar_reversion_ultimo_cierre", "revertir_ultimo_cierre_periodo", "get_periodo_anterior_cronologico",
    # E4-12 (contadores certificados del periodo vacio, base del inventario NEXT)
    "contar_datos_asociados_periodo", "periodo_puede_eliminarse",
    # E4-12 / P-12b "Reparar finalizaciones automaticas del periodo abierto" (l. 63264-63284): diagnostico y writer
    "diagnosticar_finalizaciones_automaticas_periodo", "reactivar_finalizaciones_automaticas_periodo",
]
# Infraestructura que provee el entorno NEXT (no se copia ni se recorre).
INFRA = {
    "st", "get_conn", "_pg_raw_conn", "_pg_conn", "get_planes_conn", "PgConnectionCompat", "PgCursorCompat",
    "_PgPooledRawConnection", "_pg_prepare_sql", "_pg_scope_select", "_pg_scope_insert", "_pg_scope_update_delete",
    "_pg_convert_sql", "_pg_current_inst_id", "_pg_current_dep_id", "_pg_read_dataframe", "current_user",
    "current_role", "_institucion_id_operativa", "_scope_rendimiento_v191", "_copiar_resultado_cache_v191",
    "_version_dependencias_v200", "invalidar_cache_rendimiento_v191", "limpiar_cache_comisiones_operativas",
    "_envolver_funcion_perf_v193", "_versiones_scope_v199", "_cache_scope_proyectos_v127", "_b12f_arranque_omitido",
    "_perf_registrar_sql_v191", "_pg_available", "get_db_identity",
    # pilotos de LECTURA v280/v282 (apagados por defecto): el entorno devuelve "off" y no se copian
    "_modo_lectura_designaciones_v282", "_modo_lectura_periodos_v280", "_get_designaciones_nuevo_cache_v282",
    "_get_periodos_nuevo_cache_v280",
}
# Codigo de pilotos que solo se alcanza con un piloto encendido: sus imports apuntan a un paquete INEXISTENTE
# (ImportError = fail closed si alguna vez se alcanzara) en lugar de copiar los modulos de piloto.
PILOTOS = ("deptit_refactor.integration.", "integraciones.ciclo_periodos.motor.pilotos_no_portados.")
B11 = ("backup_gate.py", "backup_manifest.py", "db_identity.py")


def main() -> None:
    src = T.ENTRY.read_text(encoding="utf-8")
    tree = ast.parse(src)
    defs, aliases = collections.defaultdict(list), collections.defaultdict(list)
    for node in tree.body:
        if node.lineno >= CUTOFF:
            continue
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            defs[node.name].append(node)
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and isinstance(node.value, ast.Name):
            aliases[node.targets[0].id].append(node)
    seen, queue = set(), list(RAICES)
    while queue:
        n = queue.pop()
        if n in seen or n in INFRA:
            continue
        seen.add(n)
        for d in defs.get(n, []):
            queue.extend({x.id for x in ast.walk(d) if isinstance(x, ast.Name)} - seen)
        for a in aliases.get(n, []):
            queue.append(a.value.id)
    sys.path.insert(0, str(T.REF))
    from deptit_refactor.security.legacy_write_actions import BUSINESS_WRITERS, SYSTEM_WRITERS  # noqa: E402
    negocio = sorted(n for n in BUSINESS_WRITERS if n in seen)
    sistema = {n: SYSTEM_WRITERS[n][0] for n in sorted(SYSTEM_WRITERS) if n in seen}

    literales = {}
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
    bloques, nombres = [], []
    for node in tree.body:
        if node.lineno >= CUTOFF:
            continue
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in seen:
            texto = ast.get_source_segment(src, node)
            if node.decorator_list:  # sin decoradores (caches Streamlit / lru_cache)
                texto = "\n".join(l for l in texto.splitlines() if not l.lstrip().startswith("@"))
            bloques.append(f"# --- entry l. {node.lineno}-{node.end_lineno}\n{texto}\n")
            nombres.append(node.name)
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and isinstance(node.value, ast.Name) and node.targets[0].id in seen:
            bloques.append(f"# --- entry l. {node.lineno}\n{ast.get_source_segment(src, node)}\n")
            nombres.append(node.targets[0].id)

    huella = hashlib.sha256(src.encode("utf-8")).hexdigest()
    constantes = "".join(f"# --- entry (literal)\n{literales[k]}\n" for k in sorted(literales))
    copiados: set = {("b12c", "periodo_atomico")}
    cuerpo = T.reescribir((constantes + "\n" + "\n\n".join(bloques)).replace(*PILOTOS), copiados)
    T.OUT.mkdir(parents=True, exist_ok=True)
    T.copiar_modulos(copiados)
    cabecera = (f'"""GENERADO por tools_generar_motor_ciclo_periodos.py -- NO EDITAR A MANO.\n\n'
                f"Texto literal del entry certificado B13-FIX02 ({T.ENTRY.name}, sha256 {huella}): definiciones\n"
                f"anteriores a la pagina Periodos (l. {CUTOFF}) que usan Crear periodo (B12C), Revertir ultimo cierre,\n"
                f"los contadores del periodo vacio y Reparar finalizaciones automaticas (P-12b), {len(bloques)} bloques en el orden del entry (incluye writers de negocio\n"
                f"y tareas de sistema).  Se ejecuta en el entorno de escritura de ``integraciones.ciclo_periodos`` dentro de\n"
                f"UNA transaccion por operacion; nunca a nivel modulo.\n"
                f'"""\n# flake8: noqa\n# fmt: off\n\n')
    (T.OUT / "complemento.py").write_text(cabecera + cuerpo, encoding="utf-8", newline="\n")
    (T.OUT / "metadata.py").write_text(
        '"""GENERADO -- NO EDITAR.  Metadatos del motor certificado de Periodos (E4-10..E4-12)."""\n\n'
        f"ENTRY_SHA256 = {huella!r}\n"
        f"CUTOFF = {CUTOFF}\n"
        f"BLOQUES = {len(bloques)}\n"
        f"NOMBRES = {nombres!r}\n"
        f"WRITERS_NEGOCIO = {negocio!r}\n"
        f"TAREAS_SISTEMA = {sistema!r}\n", encoding="utf-8", newline="\n")
    (T.OUT / "__init__.py").write_text('"""Motor certificado de Periodos (generado)."""\n', encoding="utf-8")
    destino = BASE / "ref_b11"
    destino.mkdir(parents=True, exist_ok=True)
    for nombre in B11:
        shutil.copyfile(T.PKG / "operations" / nombre, destino / nombre)
    (destino / "__init__.py").write_text('"""Copia LITERAL de deptit_refactor/operations (B11), sin cambios."""\n',
                                         encoding="utf-8")
    print(f"bloques={len(bloques)} funciones={len(set(nombres))} negocio={negocio}\nsistema={sistema}\n"
          f"literales={sorted(literales)} copiados={sorted(copiados)}")


if __name__ == "__main__":
    main()
