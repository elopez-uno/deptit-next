"""Writers certificados de Extension con sus COMMITs reales (cadenas efectivas de B13-FIX02).

Cada funcion recibe la ``Unidad`` de la operacion B12H en curso.  Igual que el certificado, cada ``get_conn()`` /
``_pg_raw_conn()`` con escritura es un COMMIT propio (``Unidad.commit``); ``conn.rollback()`` / ``conn.close()`` sin
COMMIT -> ``DE._Rollback``.  No se convierte nada en atomico, no se agregan locks, indices ni validaciones (E7).

Los writers certificados de Extension son los de Investigacion con sus tablas (docs/audit/extension_phase_a/
pair_diff.txt); este modulo es la variante propia de ``investigacion.escrituras`` sobre ``ExtensionRepository``:
- ``guardar_proyecto_extension`` l. 22506; ``actualizar_proyecto_extension`` l. 22564;
  ``suspender_proyecto_extension`` l. 22693; ``archivar_proyecto_extension`` l. 22807;
  ``eliminar_proyecto_extension`` l. 22832.
- ``guardar_extension_docente`` l. 22937 (via ``asignar_docente_a_proyecto_extension`` v217 l. 48362 -> v127 ->
  l. 22991); ``actualizar_extension_docente`` v184 l. 40373 (+ ``_validar_horas_proyecto_v184`` v187 l. 40670) ->
  l. 23003; ``eliminar_extension_docente`` l. 23045; ``eliminar_extension_docente_definitivamente`` l. 23059.
  Los writers ACEPTAN 0 hs y solo rechazan negativos (E6): el "> 0" es de la pantalla y del Excel.
- ``cargar_proyectos_excel_v127(df, "extension")`` v199 l. 46111; ``cargar_asignaciones_proyectos_excel_v217(df,
  "extension", periodo)`` l. 49057 (con "en Extensión las horas deben ser mayores a 0", l. 49107).
- ``_vincular_proyectos_documento_v261`` l. 50832, ``desvincular_acto_proyectos_masivo_v267`` l. 54938 y
  ``registrar_movimiento`` l. 4424: los mismos writers que Investigacion (el tipo llega como dato), importados sin
  cambios de ``investigacion.escrituras``.
Excluidos (E11): pilotos 8I/8K/8W, ``asegurar_esquema_extension_separado`` (B12F: solo verificacion, sin DDL ni DML),
``copiar_extension_vigente_periodo`` (Periodos).
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from typing import Any, Callable, Iterator, Optional

import pandas as pd
import psycopg

import audit
from comisiones.lecturas import Lector
from designaciones import escrituras as DE
from designaciones.repository import _numeric

from . import repository as Q
from . import rules as IR
from .lecturas import Lecturas, validar_horas_v187
from .repository import ExtensionRepository
from investigacion.escrituras import (  # noqa: F401,E402  (writers identicos, sin modificar)
    desvincular_acto_proyectos_masivo_v267, registrar_movimiento, vincular_proyectos_documento_v261,
)

W_GUARDAR_PROYECTO = "guardar_proyecto_extension"
W_ACTUALIZAR_PROYECTO = "actualizar_proyecto_extension"
W_SUSPENDER_PROYECTO = "suspender_proyecto_extension"
W_ARCHIVAR_PROYECTO = "archivar_proyecto_extension"
W_ELIMINAR_PROYECTO = "eliminar_proyecto_extension"
W_GUARDAR_ASIGNACION = "guardar_extension_docente"
W_ACTUALIZAR_ASIGNACION = "actualizar_extension_docente"
W_BAJA_ASIGNACION = "eliminar_extension_docente"
W_ELIMINAR_ASIGNACION = "eliminar_extension_docente_definitivamente"
W_CARGA_PROYECTOS = "cargar_proyectos_excel_v127"
W_CARGA_ASIGNACIONES = "cargar_asignaciones_proyectos_excel_v217"
W_VINCULAR_ACTO = "_vincular_proyectos_documento_v261"
W_DESVINCULAR_ACTO = "desvincular_acto_proyectos_masivo_v267"
W_MOVIMIENTO = DE.W_MOVIMIENTO

AuditoriaFallida = DE.AuditoriaFallida

# Texto propio que sustituye ``{e}`` (texto del driver, nunca expuesto) cuando el certificado devuelve el error de una
# restriccion de unicidad (IntegrityError, SQLSTATE 23: B12D no lo trata como fallo critico).
MSG_INTEGRIDAD = "la base de datos rechazó el cambio por una restricción de unicidad (IntegrityError)."


def _py(valor: Any) -> Any:
    """Valor de pandas/numpy -> Python para el driver; ``NaN`` -> ``None``."""
    try:
        if valor is None or pd.isna(valor):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(valor, "item") and not isinstance(valor, (str, bytes)):
        try:
            return valor.item()
        except Exception:
            return valor
    return valor


# ------------------------------------------------------------------------------------------ Unidad de Extension
class _LazyRepo:
    """``ExtensionRepository`` cuyas lecturas abren cada vez la conexion de la operacion (como ``get_conn``)."""

    def __init__(self, u: "Unidad"):
        self._u = u
        self.inst, self.dep = u.inst, u.dep
        self._scope = [u.inst, u.dep]

    def __getattr__(self, name):
        return lambda *a, **k: self._u.read(lambda repo: getattr(repo, name)(*a, **k))


class Unidad(DE.Unidad):
    """La ``Unidad`` B12H de Designaciones con el repositorio de Extension (mismo acoplamiento de COMMITs)."""

    def __init__(self, *args, rol: Optional[str] = None, dep_nombre: str = "", **kwargs):
        super().__init__(*args, **kwargs)
        self.rol = rol
        self.dep_nombre = dep_nombre
        self._lecturas: Optional[Lecturas] = None

    @property
    def lecturas(self) -> Lecturas:
        """Lecturas frescas dentro del writer, memoizadas hasta la proxima escritura (B12I capa W)."""
        if self._lecturas is None:
            lazy = _LazyRepo(self)
            self._lecturas = Lecturas(lazy, self.today, self.rol, Lector(lazy, self.today))
        return self._lecturas

    @property
    def lector(self) -> Lector:
        return self.lecturas.clec

    def read(self, fn: Callable[[ExtensionRepository], Any]) -> Any:
        with self._transaction() as conn:
            return fn(ExtensionRepository(conn, self.inst, self.dep))

    def commit(self, fn: Callable[[ExtensionRepository], Any]) -> Any:
        if self.audit_failed:
            raise AuditoriaFallida("AUDIT_FAILED_EARLIER")
        repo = None
        try:
            with self._transaction() as conn:
                repo = ExtensionRepository(conn, self.inst, self.dep)
                result = fn(repo)
                if result is DE.ROLLBACK or isinstance(result, DE._Rollback):
                    raise result if isinstance(result, DE._Rollback) else DE._Rollback(None)
                if repo.mutating_statements:
                    meta = {"commit_seq": self.op.coupled_commits + 1,
                            "mutating_statements": repo.mutating_statements,
                            "committing_writer": next(n for k, n in reversed(self._stack) if k == "business"),
                            "nested_system_task": self._stack[-1][1] if self._stack[-1][0] == "system" else None}
                    try:
                        audit.insert_on(conn, self.op.event(audit.OUTCOME_SUCCESS, audit.MODE_IN_TRANSACTION,
                                                            metadata=meta))
                    except Exception as exc:
                        self.audit_failed = True
                        raise AuditoriaFallida(audit.error_code_of(exc)) from exc
        except DE._Rollback as rb:
            return rb.value
        if repo is not None and repo.mutating_statements:
            self.op.coupled_commits += 1
            if self._lecturas is not None:
                self._lecturas.invalidar()
        return result


@contextmanager
def _sin_marco() -> Iterator[None]:
    yield


# ------------------------------------------------------------------------------------------ proyectos
def guardar_proyecto_extension(u: Unidad, nombre_proyecto, codigo_proyecto, instituto_proyecto, anio_llamado,
                                   fecha_inicio, fecha_fin, observaciones="", estado="Activo"):
    """l. 22506: un proyecto institucional; ``(id, False)`` sin escribir si ya existe."""
    nombre = str(nombre_proyecto or "").strip()
    codigo = str(codigo_proyecto or "").strip()
    instituto = IR.normalizar_radicacion_v216(instituto_proyecto, u.dep_nombre)
    inicio = IR.fecha_proyecto(fecha_inicio)
    fin = IR.fecha_proyecto(fecha_fin)
    if not nombre or not inicio or not fin or fin < inicio:
        return None, False
    ejecucion = IR.texto_periodo_proyecto(inicio, fin)

    def body(repo: ExtensionRepository):
        if codigo:
            existente = repo.fetch_one(Q.DUP_CODIGO_SQL, [codigo, u.inst])
        else:
            existente = repo.fetch_one(Q.DUP_NOMBRE_FECHAS_SQL, [nombre, str(inicio), str(fin), u.inst])
        if existente:
            return DE._Rollback((int(existente[0]), False))
        pid = repo._insert_id(Q.INSERT_PROYECTO_SQL, [
            u.dep, nombre, codigo, instituto, _py(anio_llamado), inicio, fin, ejecucion,
            str(observaciones or "").strip(), str(estado or "Activo"), str(u.today), u.inst])
        return pid, True

    return u.commit(body)


def actualizar_proyecto_extension(u: Unidad, proyecto_id, nombre_proyecto, codigo_proyecto, instituto_proyecto,
                                      anio_llamado, fecha_inicio, fecha_fin, observaciones="", estado="Activo"):
    """l. 22564: proyecto + columnas desnormalizadas de TODAS las asignaciones de la institucion (un COMMIT)."""
    proyecto_actual = u.lecturas.proyecto_por_id(proyecto_id)
    if not proyecto_actual:
        return False, "No se encontró el proyecto."
    if not proyecto_actual.get("puede_administrar"):
        return False, "Solo el departamento creador o la coordinación institucional pueden editar este proyecto."
    if str(estado or "Activo").strip() == "Suspendido" and str(proyecto_actual.get("estado") or "Activo").strip() != "Suspendido":
        return False, ("Para suspender el proyecto usá la acción específica de suspensión. "
                       "Así se dan de baja las asignaciones del período actual y queda trazabilidad.")
    nombre = str(nombre_proyecto or "").strip()
    codigo = str(codigo_proyecto or "").strip()
    instituto = IR.normalizar_radicacion_v216(instituto_proyecto, u.dep_nombre)
    inicio = IR.fecha_proyecto(fecha_inicio)
    fin = IR.fecha_proyecto(fecha_fin)
    if not nombre:
        return False, "El proyecto debe tener nombre."
    if not inicio or not fin:
        return False, "Completá la fecha de inicio y la fecha de finalización."
    if fin < inicio:
        return False, "La fecha de finalización no puede ser anterior a la fecha de inicio."
    ejecucion = IR.texto_periodo_proyecto(inicio, fin)
    pid = int(proyecto_id)

    def body(repo: ExtensionRepository):
        if codigo:
            dup = repo.fetch_one(Q.DUP_OTRO_CODIGO_SQL, [u.inst, pid, codigo])
        else:
            dup = repo.fetch_one(Q.DUP_OTRO_NOMBRE_SQL, [u.inst, pid, nombre, inicio, fin])
        if dup:
            return DE._Rollback((False, "Ya existe otro proyecto institucional con ese código o con esos mismos datos."))
        filas = repo.mutate_rowcount(Q.UPDATE_PROYECTO_SQL, [
            nombre, codigo, instituto, _py(anio_llamado), inicio, fin, ejecucion, str(observaciones or "").strip(),
            str(estado or "Activo"), pid, u.inst])
        if filas != 1:
            return DE._Rollback((False, "No se pudo actualizar el proyecto."))
        repo._mutate(Q.UPDATE_ASIG_DESNORMALIZADAS_SQL, [nombre, codigo, instituto, _py(anio_llamado), ejecucion, pid,
                                                         u.inst])
        return True, "Proyecto institucional actualizado en todos los departamentos."

    try:
        return u.commit(body)
    except psycopg.errors.IntegrityError:
        return False, f"No se pudo actualizar el proyecto: {MSG_INTEGRIDAD}"


def suspender_proyecto_extension(u: Unidad, proyecto_id, periodo_id, motivo="", fecha_suspension_efectiva=None):
    """l. 22693: baja de las asignaciones Activas del proyecto en TODOS los departamentos cuyo periodo tenga el mismo
    nombre que el periodo abierto del departamento (un COMMIT, sin movimientos)."""
    proyecto = u.lecturas.proyecto_por_id(proyecto_id)
    if not proyecto:
        return False, "No se encontró el proyecto.", 0
    if not proyecto.get("puede_administrar"):
        return False, "Solo el departamento creador o la coordinación institucional pueden suspender este proyecto.", 0
    motivo_limpio = str(motivo or "").strip()
    if not motivo_limpio:
        return False, "Completá el motivo de la suspensión.", 0
    fecha_obj = fecha_suspension_efectiva or u.today
    fecha_suspension = str(fecha_obj)
    try:
        fecha_legible = fecha_obj.strftime("%d/%m/%Y")
    except Exception:
        fecha_legible = str(fecha_obj)
    detalle = f"Suspendido el {fecha_legible}: {motivo_limpio}"
    observaciones = str(proyecto.get("observaciones") or "").strip()
    observaciones = (observaciones + " | " if observaciones else "") + detalle
    motivo_asignaciones = f"Suspensión del proyecto: {motivo_limpio}"
    pid = int(proyecto_id)

    def body(repo: ExtensionRepository):
        fila_periodo = repo.fetch_one(Q.NOMBRE_PERIODO_DEP_SQL, [int(periodo_id), u.inst, u.dep])
        if not fila_periodo:
            return DE._Rollback((False, "No se encontró el período actual del departamento.", 0))
        nombre_periodo = str(fila_periodo[0] or "").strip()
        filas = repo.mutate_rowcount(Q.SUSPENDER_PROYECTO_SQL, [fecha_suspension, motivo_limpio, observaciones, pid,
                                                                 u.inst])
        if filas != 1:
            return DE._Rollback((False, "No se pudo suspender el proyecto.", 0))
        afectadas = max(repo.mutate_rowcount(Q.SUSPENDER_ASIGNACIONES_SQL, [
            fecha_suspension, motivo_asignaciones, u.inst, u.inst, nombre_periodo, pid]), 0)
        return True, (f"Proyecto suspendido. Se dieron de baja {afectadas} asignación/es del período {nombre_periodo} "
                      "en la institución. Los períodos anteriores no fueron modificados."), afectadas

    return u.commit(body)


def archivar_proyecto_extension(u: Unidad, proyecto_id, motivo=""):
    """l. 22807: estado Archivado + observacion (get_conn; sin validar ``rowcount``)."""
    proyecto = u.lecturas.proyecto_por_id(proyecto_id)
    if not proyecto:
        return False, "No se encontró el proyecto."
    if not proyecto.get("puede_administrar"):
        return False, "Solo el departamento creador o la coordinación institucional pueden archivar este proyecto."
    observaciones = str(proyecto.get("observaciones") or "").strip()
    agregado = f"Archivado el {u.today.strftime('%d/%m/%Y')}"
    if str(motivo or "").strip():
        agregado += f": {str(motivo).strip()}"
    observaciones = (observaciones + " | " if observaciones else "") + agregado
    u.commit(lambda repo: repo._mutate(Q.ARCHIVAR_PROYECTO_SQL, [observaciones, int(proyecto_id), u.inst]))
    return True, "Proyecto archivado para toda la institución. Se conservaron todas sus asignaciones e historial."


def eliminar_proyecto_extension(u: Unidad, proyecto_id):
    """l. 22832: borra las asignaciones de TODOS los departamentos y el proyecto (un COMMIT).  Los movimientos y los
    vinculos de actos quedan (no hay FK; comportamiento heredado)."""
    proyecto = u.lecturas.proyecto_por_id(proyecto_id)
    if not proyecto:
        return False, "No se encontró el proyecto."
    if not proyecto.get("puede_administrar"):
        return False, "Solo el departamento creador o la coordinación institucional pueden eliminar este proyecto."
    pid = int(proyecto_id)

    def body(repo: ExtensionRepository):
        fila = repo.fetch_one(Q.PROYECTO_NOMBRE_CODIGO_SQL, [pid, u.inst])
        if not fila:
            return DE._Rollback((False, "No se encontró el proyecto."))
        nombre_proyecto = str(fila[0] or "").strip()
        codigo_proyecto = str(fila[1] or "").strip()
        cantidad = int((repo.fetch_one(Q.CONTAR_ASIG_PROYECTO_SQL, [pid, u.inst]) or [0])[0] or 0)
        repo._mutate(Q.DELETE_ASIG_PROYECTO_SQL, [pid, u.inst])
        if repo.mutate_rowcount(Q.DELETE_PROYECTO_SQL, [pid, u.inst]) != 1:
            return DE._Rollback((False, "No se pudo eliminar el proyecto."))
        identificador = codigo_proyecto or nombre_proyecto
        return True, (f"Proyecto institucional «{identificador}» eliminado definitivamente. "
                      f"También se eliminaron {cantidad} asignación/es de todos los departamentos. "
                      "No quedará visible en el historial.")

    return u.commit(body)


# ------------------------------------------------------------------------------------------ asignaciones
def guardar_extension_docente(u: Unidad, periodo_id, cuil, nombre_proyecto, rol, anio_llamado, periodo_ejecucion,
                                  horas_asignadas, observaciones, codigo_proyecto="", instituto_proyecto="",
                                  proyecto_id=None):
    """l. 22937: si ya existe una asignacion activa (institucional o local) devuelve su id SIN escribir."""
    if proyecto_id is None:
        # La rama legacy sin proyecto (crea el proyecto desde el texto libre) no la usa ninguna pantalla certificada.
        raise ValueError("La asignación debe indicar un proyecto institucional.")
    proyecto = u.lecturas.proyecto_por_id(proyecto_id)
    if proyecto:
        nombre_proyecto = proyecto.get("nombre_proyecto", nombre_proyecto)
        codigo_proyecto = proyecto.get("codigo_proyecto", codigo_proyecto)
        instituto_proyecto = proyecto.get("instituto_proyecto", instituto_proyecto)
        anio_llamado = proyecto.get("anio_llamado", anio_llamado)
        periodo_ejecucion = proyecto.get("periodo_ejecucion", periodo_ejecucion)
    existente_global = u.lecturas.buscar_activa(periodo_id, proyecto_id, cuil)
    if existente_global:
        return int(existente_global.get("id"))

    def body(repo: ExtensionRepository):
        existente = repo.fetch_one(Q.DUP_LOCAL_ASIG_SQL, [int(periodo_id), cuil, int(proyecto_id), u.inst, u.dep])
        if existente:
            return DE._Rollback(int(existente[0]))
        return repo._insert_id(Q.INSERT_ASIG_SQL, [
            int(proyecto_id), int(periodo_id), cuil, _py(nombre_proyecto), rol, _py(anio_llamado),
            _py(periodo_ejecucion), _numeric(horas_asignadas), observaciones, str(u.today), _py(codigo_proyecto),
            _py(instituto_proyecto), u.inst, u.dep])

    return u.commit(body)


def actualizar_extension_docente(u: Unidad, id_extension, periodo_id, cuil, nombre_proyecto, rol, anio_llamado,
                                     periodo_ejecucion, horas_asignadas, observaciones, codigo_proyecto="",
                                     instituto_proyecto="", proyecto_id=None):
    """v184 l. 40373 (+ v187: solo bloquean horas negativas) -> l. 23003.  No valida ``rowcount``."""
    ok, msg, _ = validar_horas_v187(u, cuil, periodo_id, horas_asignadas, excluir_tipo="extension",
                                    excluir_id=id_extension)
    if not ok:
        return False, msg.replace("**", "")
    proyecto = u.lecturas.proyecto_por_id(proyecto_id) if proyecto_id is not None else {}
    if proyecto:
        nombre_proyecto = proyecto.get("nombre_proyecto", nombre_proyecto)
        codigo_proyecto = proyecto.get("codigo_proyecto", codigo_proyecto)
        instituto_proyecto = proyecto.get("instituto_proyecto", instituto_proyecto)
        anio_llamado = proyecto.get("anio_llamado", anio_llamado)
        periodo_ejecucion = proyecto.get("periodo_ejecucion", periodo_ejecucion)
    duplicada = u.lecturas.buscar_activa(periodo_id, proyecto_id, cuil, excluir_id=id_extension)
    if duplicada:
        departamento = str(duplicada.get("departamento_asignacion") or "otro departamento")
        return False, f"El docente ya está asignado a este proyecto en {departamento} para el mismo cuatrimestre."
    u.commit(lambda repo: repo._mutate(Q.UPDATE_ASIG_SQL, [
        _py(proyecto_id), int(periodo_id), cuil, _py(nombre_proyecto), rol, _py(anio_llamado), _py(periodo_ejecucion),
        _numeric(horas_asignadas), observaciones, _py(codigo_proyecto), _py(instituto_proyecto), int(id_extension),
        u.inst, u.dep]))
    return True, "Asignación actualizada."


def eliminar_extension_docente(u: Unidad, id_extension, motivo="", fecha_baja=None) -> None:
    """l. 23045: baja logica con la fecha efectiva (sin validar estado previo ni ``rowcount``; sin movimiento)."""
    fecha_efectiva = str(fecha_baja or u.today)
    u.commit(lambda repo: repo._mutate(Q.BAJA_ASIG_SQL, [fecha_efectiva, str(motivo or "").strip(),
                                                          int(id_extension), u.inst, u.dep]))


def eliminar_extension_docente_definitivamente(u: Unidad, id_extension):
    """l. 23059: el mensaje de fallo por ``rowcount`` se decide DESPUES del COMMIT (comportamiento heredado)."""
    aid = int(id_extension)

    def body(repo: ExtensionRepository):
        fila = repo.fetch_one(Q.ASIG_POR_ID_INST_SQL, [aid, u.inst])
        if not fila:
            return DE._Rollback((False, "No se encontró la asignación."))
        puede = u.rol in ["superadmin", "coordinador_institucional"]
        if not puede:
            try:
                puede = int(fila[2]) == int(u.dep)
            except Exception:
                puede = False
        if not puede:
            return DE._Rollback((False, "Solo el departamento que realizó la asignación o la coordinación institucional "
                                        "puede eliminarla definitivamente."))
        return repo.mutate_rowcount(Q.DELETE_ASIG_SQL, [aid, u.inst])

    resultado = u.commit(body)
    if isinstance(resultado, tuple):
        return resultado
    if int(resultado or 0) != 1:
        return False, "No se pudo eliminar la asignación."
    return True, "Asignación eliminada definitivamente. No quedará en el historial."


# registrar_movimiento, vincular_proyectos_documento_v261 y desvincular_acto_proyectos_masivo_v267: importados.


# ------------------------------------------------------------------------------------------ carga rapida
def cargar_proyectos_excel_v127(u: Unidad, df_carga: pd.DataFrame) -> dict:
    """v199 l. 46111: validacion completa previa (cualquier error -> nada se escribe) y UNA transaccion."""
    if df_carga is None or df_carga.empty:
        raise ValueError("El Excel no contiene filas para procesar.")
    lim, clave = IR.limpiar_texto_tabla, IR.normalizar_clave
    errores, nuevos = [], []
    omitidos_existentes = 0
    for idx, row in df_carga.iterrows():
        nro = int(idx) + 2
        if IR.parse_id_excel_v127(row.get("id")) is not None:
            omitidos_existentes += 1
            continue
        nombre = " ".join(lim(row.get("nombre_proyecto", "")).split())
        codigo = lim(row.get("codigo_proyecto", ""))
        responsable = IR.normalizar_radicacion_v216(lim(row.get("instituto_proyecto", "")), u.dep_nombre)
        inicio = IR.parse_fecha_excel_v127(row.get("fecha_inicio"))
        fin = IR.parse_fecha_excel_v127(row.get("fecha_fin"))
        estado_txt = lim(row.get("estado", "")) or "Activo"
        estado = next((e for e in IR.ESTADOS_PROYECTO_EXCEL_V127 if clave(e) == clave(estado_txt)), "")
        obs = lim(row.get("observaciones", ""))
        if not nombre:
            resto = any([codigo, responsable, inicio, fin, obs, lim(row.get("anio_llamado", "")),
                         lim(row.get("estado", ""))])
            if resto:
                errores.append(f"Fila {nro}: falta el nombre del proyecto.")
            continue
        if not inicio or not fin:
            errores.append(f"Fila {nro}: completá Fecha de inicio y Fecha de finalización.")
            continue
        if fin < inicio:
            errores.append(f"Fila {nro}: la Fecha de finalización es anterior a la Fecha de inicio.")
            continue
        if not estado:
            errores.append(f"Fila {nro}: Estado administrativo inválido.")
            continue
        try:
            anio_raw = row.get("anio_llamado")
            vacio_anio = anio_raw is None or (isinstance(anio_raw, float) and pd.isna(anio_raw)) or not str(anio_raw).strip()
            anio = int(inicio.year) if vacio_anio else int(float(str(anio_raw).strip()))
        except Exception:
            errores.append(f"Fila {nro}: Año de llamado inválido.")
            continue
        if anio < 1900 or anio > 2100:
            errores.append(f"Fila {nro}: Año de llamado fuera de rango.")
            continue
        nuevos.append({"fila": nro, "nombre": nombre, "codigo": codigo, "responsable": responsable, "anio": anio,
                       "inicio": inicio, "fin": fin, "estado": estado, "obs": obs})
    if errores:
        raise ValueError("No se realizó la carga porque se detectaron errores:\n- " + "\n- ".join(errores[:30])
                         + ("\n- ..." if len(errores) > 30 else ""))
    if not nuevos:
        return {"creados": 0, "existentes": 0, "omitidos_existentes": omitidos_existentes, "detalle": pd.DataFrame()}

    def body(repo: ExtensionRepository):
        creados, existentes, detalle = 0, 0, []
        for g in nuevos:
            if g["codigo"]:
                existente = repo.fetch_one(Q.DUP_CODIGO_SQL, [g["codigo"], u.inst])
            else:
                existente = repo.fetch_one(Q.DUP_NOMBRE_FECHAS_SQL, [g["nombre"], str(g["inicio"]), str(g["fin"]), u.inst])
            if existente:
                proyecto_id, creado = int(existente[0]), False
                existentes += 1
            else:
                ejecucion = IR.texto_periodo_proyecto(g["inicio"], g["fin"])
                proyecto_id = int(repo._insert_id(Q.INSERT_PROYECTO_SQL, [
                    u.dep, g["nombre"], g["codigo"], g["responsable"], g["anio"], g["inicio"], g["fin"], ejecucion,
                    g["obs"], g["estado"], str(u.today), u.inst]))
                creado = True
                creados += 1
            detalle.append({"Fila Excel": g["fila"], "Resultado": "Creado" if creado else "Ya existía",
                            "ID proyecto": proyecto_id, "Código": g["codigo"], "Proyecto": g["nombre"],
                            "Responsable": g["responsable"], "Inicio": g["inicio"], "Fin": g["fin"],
                            "Estado": g["estado"]})
        return creados, existentes, detalle

    creados, existentes, detalle = u.commit(body)
    return {"creados": creados, "existentes": existentes, "omitidos_existentes": omitidos_existentes,
            "detalle": pd.DataFrame(detalle)}


def cargar_asignaciones_proyectos_excel_v217(u: Unidad, df_asig: pd.DataFrame, periodo_id) -> dict:
    """l. 49057: validacion completa previa contra el catalogo y el padron v276; UNA transaccion con las altas y sus
    movimientos (INSERT directo en ``movimientos``)."""
    if df_asig is None or df_asig.empty:
        return {"creadas": 0, "omitidas": 0, "detalle": pd.DataFrame()}
    if periodo_id is None:
        raise ValueError("No hay un período abierto para asociar las asignaciones del Excel.")
    lim = IR.limpiar_texto_tabla
    proyectos = u.lecturas.proyectos()
    docentes = u.lecturas.padron()
    permitidos = {}
    if isinstance(docentes, pd.DataFrame) and not docentes.empty:
        for _, r in docentes.iterrows():
            k = IR.clave_cuil(r.get("cuil"))
            if k:
                permitidos[k] = r.to_dict()
    preparados, errores, omitidos_id = [], [], 0
    for idx, row in df_asig.iterrows():
        nro = int(idx) + 2
        if IR.parse_id_excel_v127(row.get("id")) is not None:
            omitidos_id += 1
            continue
        proyecto_ref = lim(row.get("proyecto", ""))
        docente_ref = lim(row.get("docente", ""))
        rol = lim(row.get("rol", ""))
        obs = lim(row.get("observaciones", ""))
        if not any([proyecto_ref, docente_ref, rol, lim(row.get("horas", "")), obs]):
            continue
        proyecto = IR.resolver_proyecto_ref_v217(proyecto_ref, proyectos)
        if not proyecto:
            errores.append(f"Fila {nro}: no se pudo identificar de forma unívoca el proyecto '{proyecto_ref}'.")
            continue
        cuil = IR.cuil_desde_ref_docente_v217(docente_ref)
        clave = IR.clave_cuil(cuil)
        if not clave or clave not in permitidos:
            errores.append(f"Fila {nro}: el docente '{docente_ref}' no está disponible en el plantel del período actual.")
            continue
        if not rol:
            errores.append(f"Fila {nro}: falta el rol del docente.")
            continue
        try:
            horas = float(row.get("horas") if pd.notna(row.get("horas")) and str(row.get("horas")).strip() else 0)
        except Exception:
            errores.append(f"Fila {nro}: Horas semanales inválidas.")
            continue
        if horas < 0 or horas > 100:
            errores.append(f"Fila {nro}: las horas deben estar entre 0 y 100.")
            continue
        if horas <= 0:
            errores.append(f"Fila {nro}: en Extensión las horas deben ser mayores a 0.")
            continue
        preparados.append({"fila": nro, "proyecto": proyecto, "cuil": str(permitidos[clave].get("cuil") or cuil),
                           "docente": str(permitidos[clave].get("nombre_completo") or cuil), "rol": rol,
                           "horas": round(horas, 2), "obs": obs})
    if errores:
        raise ValueError("No se realizó la carga de asignaciones porque se detectaron errores:\n- "
                         + "\n- ".join(errores[:40]) + ("\n- ..." if len(errores) > 40 else ""))
    if not preparados:
        return {"creadas": 0, "omitidas": omitidos_id, "detalle": pd.DataFrame()}
    tipo_mov = "Asignación a extensión"

    def body(repo: ExtensionRepository):
        detalle, creadas, omitidas = [], 0, omitidos_id
        per = repo.fetch_one(Q.PERIODO_INST_SQL, [int(periodo_id), u.inst])
        if not per:
            raise ValueError("No se encontró el período abierto.")
        per_nombre, per_anio, per_sem = per
        existentes = {(int(r[0]), str(r[1] or "")) for r in repo.fetch_all(Q.PARES_ACTIVOS_SQL, [
            u.inst, per_anio, per_sem, per_nombre])}
        vistos = set(existentes)
        for g in preparados:
            proyecto = g["proyecto"]
            clave = (int(proyecto["id"]), IR.clave_cuil(g["cuil"]))
            fila = {"Fila Excel": g["fila"], "Proyecto": proyecto.get("nombre_proyecto", ""), "Docente": g["docente"],
                    "Rol": g["rol"], "Horas": g["horas"]}
            if clave in vistos:
                omitidas += 1
                detalle.append({"Fila Excel": g["fila"], "Resultado": "Omitida: ya estaba asignado",
                                **{k: v for k, v in fila.items() if k != "Fila Excel"}})
                continue
            anio = proyecto.get("anio_llamado")
            repo._insert_id(Q.INSERT_ASIG_EXCEL_SQL, [
                u.inst, u.dep, int(proyecto["id"]), int(periodo_id), g["cuil"], proyecto.get("nombre_proyecto", ""),
                g["rol"], int(anio) if pd.notna(anio) and str(anio).strip() else None,
                proyecto.get("periodo_ejecucion", ""), _numeric(g["horas"]), g["obs"], str(u.today),
                proyecto.get("codigo_proyecto", ""), proyecto.get("instituto_proyecto", "")])
            repo._mutate(Q.INSERT_MOVIMIENTO_EXCEL_SQL, [
                u.inst, u.dep, int(periodo_id), str(u.today), tipo_mov, g["cuil"], g["docente"],
                f"Carga rápida: {proyecto.get('nombre_proyecto','')} como {g['rol']} ({g['horas']:g} hs).", g["obs"], 0])
            vistos.add(clave)
            creadas += 1
            detalle.append({"Fila Excel": g["fila"], "Resultado": "Asignada",
                            **{k: v for k, v in fila.items() if k != "Fila Excel"}})
        return creadas, omitidas, detalle

    creadas, omitidas, detalle = u.commit(body)
    return {"creadas": creadas, "omitidas": omitidas, "detalle": pd.DataFrame(detalle)}


__all__ = [n for n in dir() if n.startswith("W_")] + ["Unidad", "AuditoriaFallida", "MSG_INTEGRIDAD"]
_ = (date, _sin_marco)
