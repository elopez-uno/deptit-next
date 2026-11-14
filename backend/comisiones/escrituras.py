"""Writers certificados de Comisiones con sus COMMITs reales (cadenas efectivas de B13-FIX02).

Cada funcion recibe la ``Unidad`` de la operacion B12H en curso.  Igual que el certificado, cada ``get_conn()`` /
``_pg_raw_conn()`` / ``get_auth_conn()`` con escritura es un COMMIT propio (``Unidad.commit``); los writers de negocio
anidados abren su marco B10 (``u.writer``) y su COMMIT queda atribuido a ellos (``committing_writer``).  Un error
confirma lo anterior y revierte solo el COMMIT en curso (no se convierte nada en atomico).

Cadenas (entry):
- ``guardar_comision`` l. 18562 (+ ``insertar_vinculos_materias_comision_cursor_v118`` l. 28558).
- ``actualizar_comision`` l. 18638; ``actualizar_nombre_comision_correccion_v180`` l. 18773;
  ``actualizar_nombres_comisiones_lote_v195`` l. 43824.
- ``eliminar_comision`` v95 l. 32800 -> base l. 18849; compensacion ``_b10_revertir_alta_comision_incompleta`` l. 59172.
- ``guardar_horario_comision`` l. 19039; ``actualizar_horario_comision`` v95 l. 30475 -> base l. 19007 (+ reparacion de
  franjas l. 30451); ``eliminar_horario_comision`` v95 l. 30486 -> base l. 19059.
- ``sincronizar_horas_asignaciones_comision`` v184 l. 40531 -> v95 l. 30389.
- ``guardar_asignacion_docente_comision`` v184 l. 40554 -> v95 l. 30415 (+ prestado local l. 26201);
  ``guardar_horarios_reales_asignacion`` v184 l. 40542 -> base l. 30349;
  ``actualizar_estado_asignacion_docente_comision`` l. 19173; ``eliminar_asignacion_docente_comision`` v95 l. 30444.
- ``guardar_inscriptos_asignatura_periodo_v248`` l. 53751; sedes l. 18204/18233/18264.
- Reajuste de proyectos v184 (``reconciliar_horas_proyectos_por_comisiones_v184``): ``proyectos.py``.
- ``registrar_movimiento`` l. 4424: el port de Designaciones, sin cambios.
"""

from __future__ import annotations

import time
from datetime import date
from typing import Any, Callable, Optional

import pandas as pd

import audit
from designaciones import escrituras as DE
from designaciones.repository import _numeric
from materias.repository import MateriasRepository

from . import rules as R
from .lecturas import Lector
from .repository import ComisionesRepository

W_GUARDAR_COMISION = "guardar_comision"
W_ACTUALIZAR_COMISION = "actualizar_comision"
W_NOMBRE_V180 = "actualizar_nombre_comision_correccion_v180"
W_NOMBRES_LOTE = "actualizar_nombres_comisiones_lote_v195"
W_CARGA_LOTE = "cargar_comisiones_rapidas_lote_v232"
W_ELIMINAR_COMISION = "eliminar_comision"
W_COMPENSACION = "_b10_revertir_alta_comision_incompleta"
W_GUARDAR_HORARIO = "guardar_horario_comision"
W_ACTUALIZAR_HORARIO = "actualizar_horario_comision"
W_REPARAR_FRANJAS = "_reparar_horarios_personalizados_por_horario_comision_v95"
W_ELIMINAR_HORARIO = "eliminar_horario_comision"
W_SINCRONIZAR_HORAS = "sincronizar_horas_asignaciones_comision"
W_GUARDAR_ASIGNACION = "guardar_asignacion_docente_comision"
W_HORARIOS_REALES = "guardar_horarios_reales_asignacion"
W_ESTADO_ASIGNACION = "actualizar_estado_asignacion_docente_comision"
W_ELIMINAR_ASIGNACION = "eliminar_asignacion_docente_comision"
W_INSCRIPTOS = "guardar_inscriptos_asignatura_periodo_v248"
W_GUARDAR_SEDE = "guardar_sede_institucional"
W_ACTUALIZAR_SEDE = "actualizar_sede_institucional"
W_ELIMINAR_SEDE = "eliminar_sede_institucional"
W_PRESTADO_LOCAL = "asegurar_docente_prestado_local_si_corresponde"
W_HORAS_PROYECTO = "_actualizar_horas_proyecto_directo_v184"
W_MOVIMIENTO = DE.W_MOVIMIENTO

AuditoriaFallida = DE.AuditoriaFallida

MSG_COMISION_YA_CARGADA = "Esa comisión ya estaba cargada. No se creó un duplicado."
MSG_HORARIO_YA_CARGADO = "Ese horario ya estaba cargado en la comisión. No se creó un duplicado."

# --- SQL (get_conn + inyector; texto de tools_comisiones_inject_sql.py) -----------------------------------------
_S = "(comisiones.institucion_id = %s) AND (comisiones.departamento_id = %s)"
INSERT_COMISION_SQL = ("INSERT INTO comisiones (periodo_id, materia_id, nombre_comision, turno, sede, modalidad, estado, "
                       "observaciones, fecha_creacion, materia_especifica, opcion_curricular_id, institucion_id, "
                       "departamento_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)  RETURNING id")
DELETE_VINCULOS_SQL = ("DELETE FROM comision_materias WHERE comision_id = %s AND (comision_materias.institucion_id = %s) "
                       "AND (comision_materias.departamento_id = %s) ")
INSERT_VINCULO_SQL = ("INSERT INTO comision_materias (comision_id, materia_id, carrera_id_snapshot, carrera_snapshot, "
                      "escuela_snapshot, plan_version_snapshot, anio_snapshot, cuatrimestre_snapshot, dictado_snapshot, "
                      "carga_semanal_snapshot, carga_total_snapshot, codigo_snapshot, asignatura_snapshot, fecha_vinculacion, "
                      "origen, institucion_id, departamento_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
                      "%s, %s, %s, %s)  RETURNING id")
COMISION_ACTUAL_SQL = ("SELECT materia_id, opcion_curricular_id, COALESCE(materia_especifica, '') FROM comisiones "
                       f"WHERE id = %s AND {_S} LIMIT 1")
COUNT_VINCULOS_SQL = ("SELECT COUNT(*) FROM comision_materias WHERE comision_id = %s AND "
                      "(comision_materias.institucion_id = %s) AND (comision_materias.departamento_id = %s) ")
UPDATE_COMISION_SQL = ("UPDATE comisiones SET materia_id = %s, nombre_comision = %s, turno = %s, sede = %s, modalidad = %s, "
                       "estado = %s, observaciones = %s, materia_especifica = %s, opcion_curricular_id = %s "
                       f"WHERE id = %s AND {_S} ")
COMISION_V180_SQL = ("SELECT id, periodo_id, materia_id, nombre_comision, turno, sede, modalidad, "
                     "COALESCE(opcion_curricular_id, NULL) AS opcion_curricular_id, COALESCE(materia_especifica, '') AS "
                     f"materia_especifica FROM comisiones WHERE id = %s AND {_S} LIMIT 1")
UPDATE_NOMBRE_SQL = f"UPDATE comisiones SET nombre_comision = %s WHERE id = %s AND {_S} "
COMISIONES_LOTE_SQL = ("SELECT id, periodo_id, materia_id, nombre_comision, turno, sede, modalidad, opcion_curricular_id, "
                       "COALESCE(materia_especifica,'') AS materia_especifica FROM comisiones WHERE id IN ({ph}) "
                       f"AND {_S}")
DELETE_FRANJAS_COMISION_SQL = ("DELETE FROM horarios_asignacion_docente_comision WHERE asignacion_id IN (SELECT id FROM "
                               "asignaciones_docentes_comision WHERE comision_id=%s) AND "
                               "(horarios_asignacion_docente_comision.institucion_id = %s) AND "
                               "(horarios_asignacion_docente_comision.departamento_id = %s) ")
DELETE_ASIGNACIONES_COMISION_SQL = ("DELETE FROM asignaciones_docentes_comision WHERE comision_id = %s AND "
                                    "(asignaciones_docentes_comision.institucion_id = %s) AND "
                                    "(asignaciones_docentes_comision.departamento_id = %s) ")
DELETE_HORARIOS_COMISION_SQL = ("DELETE FROM horarios_comision WHERE comision_id = %s AND (horarios_comision.institucion_id = %s) "
                                "AND (horarios_comision.departamento_id = %s) ")
DELETE_INS_CM_SQL = ("DELETE FROM inscriptos_comision_materia WHERE comision_id = %s AND "
                     "(inscriptos_comision_materia.institucion_id = %s) AND (inscriptos_comision_materia.departamento_id = %s) ")
DELETE_INS_C_SQL = ("DELETE FROM inscriptos_comision WHERE comision_id = %s AND (inscriptos_comision.institucion_id = %s) "
                    "AND (inscriptos_comision.departamento_id = %s) ")
DELETE_COMISION_SQL = f"DELETE FROM comisiones WHERE id = %s AND {_S} "
_SH = "(horarios_comision.institucion_id = %s) AND (horarios_comision.departamento_id = %s)"
HORARIO_COMISION_SQL = f"SELECT id, comision_id FROM horarios_comision WHERE id = %s AND {_SH} LIMIT 1"
UPDATE_HORARIO_SQL = ("UPDATE horarios_comision SET dia = %s, hora_inicio = %s, hora_fin = %s, horas = %s, observaciones = %s "
                      f"WHERE id = %s AND {_SH} ")
INSERT_HORARIO_SQL = ("INSERT INTO horarios_comision (comision_id, dia, hora_inicio, hora_fin, horas, observaciones, "
                      "institucion_id, departamento_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)  RETURNING id")
COMISION_DE_HORARIO_SQL = f"SELECT comision_id FROM horarios_comision WHERE id = %s AND {_SH} LIMIT 1"
DELETE_HORARIO_SQL = f"DELETE FROM horarios_comision WHERE id = %s AND {_SH} "
HORARIO_DUP_SQL = ("SELECT id, dia, hora_inicio, hora_fin FROM horarios_comision WHERE comision_id = %s AND "
                   "UPPER(TRIM(COALESCE(dia, ''))) = UPPER(TRIM(%s)) AND COALESCE(hora_inicio, '') = %s AND "
                   "COALESCE(hora_fin, '') = %s{excluir} AND " + _SH + " LIMIT 1")
_SA = "(asignaciones_docentes_comision.institucion_id = %s) AND (asignaciones_docentes_comision.departamento_id = %s)"
_SF = ("(horarios_asignacion_docente_comision.institucion_id = %s) AND "
       "(horarios_asignacion_docente_comision.departamento_id = %s)")
ASIGNACIONES_ACTIVAS_SQL = ("SELECT id, COALESCE(usa_horario_personalizado, FALSE) AS usa_horario_personalizado FROM "
                            "asignaciones_docentes_comision WHERE comision_id=%s AND COALESCE(estado, 'Activa')='Activa' "
                            f"AND {_SA} ")
SUMA_HORARIOS_SQL = f"SELECT COALESCE(SUM(horas),0) AS h FROM horarios_comision WHERE comision_id=%s AND {_SH} "
SUMA_FRANJAS_SQL = f"SELECT COALESCE(SUM(horas),0) AS h FROM horarios_asignacion_docente_comision WHERE asignacion_id=%s AND {_SF} "
UPDATE_HORAS_ASIGNACION_SQL = f"UPDATE asignaciones_docentes_comision SET horas_asignadas=%s WHERE id=%s AND {_SA} "
CONTEXTO_ASIGNACION_SQL = ("SELECT a.cuil, co.periodo_id FROM asignaciones_docentes_comision a JOIN comisiones co ON "
                           "co.id=a.comision_id WHERE a.id=%s AND (a.institucion_id = %s) AND (a.departamento_id = %s) AND "
                           "(co.institucion_id = %s) AND (co.departamento_id = %s) LIMIT 1")
CONTEXTO_COMISION_SQL = ("SELECT DISTINCT a.cuil, co.periodo_id FROM asignaciones_docentes_comision a JOIN comisiones co ON "
                         "co.id=a.comision_id WHERE co.id=%s AND COALESCE(a.estado,'Activa')='Activa' AND "
                         "(a.institucion_id = %s) AND (a.departamento_id = %s) AND (co.institucion_id = %s) AND "
                         "(co.departamento_id = %s) ")
PERIODO_DE_COMISION_SQL = f"SELECT periodo_id FROM comisiones WHERE id=%s AND {_S} LIMIT 1"
ASIGNACION_DUP_SQL = ("SELECT id, comision_id, cuil, rol FROM asignaciones_docentes_comision WHERE comision_id = %s AND "
                      "REPLACE(REPLACE(REPLACE(REPLACE(COALESCE(cuil, ''), '-', ''), ' ', ''), '.', ''), '/', '') = "
                      "REPLACE(REPLACE(REPLACE(REPLACE(COALESCE(%s, ''), '-', ''), ' ', ''), '.', ''), '/', ''){excluir} "
                      "AND " + _SA + " LIMIT 1")
INSERT_ASIGNACION_SQL = ("INSERT INTO asignaciones_docentes_comision (comision_id, cuil, rol, horas_asignadas, estado, "
                         "observaciones, usa_horario_personalizado, institucion_id, departamento_id) VALUES (%s, %s, %s, %s, "
                         "%s, %s, %s, %s, %s)  RETURNING id")
ASIGNACION_COMISION_SQL = f"SELECT id, comision_id FROM asignaciones_docentes_comision WHERE id=%s AND {_SA} LIMIT 1"
DELETE_FRANJAS_ASIGNACION_SQL = f"DELETE FROM horarios_asignacion_docente_comision WHERE asignacion_id=%s AND {_SF} "
INSERT_FRANJA_SQL = ("INSERT INTO horarios_asignacion_docente_comision (asignacion_id, horario_comision_id, dia, hora_inicio, "
                     "hora_fin, horas, observaciones, institucion_id, departamento_id) VALUES (%s, %s, %s, %s, %s, %s, %s, "
                     "%s, %s)  RETURNING id")
UPDATE_PERSONALIZADO_SQL = ("UPDATE asignaciones_docentes_comision SET usa_horario_personalizado=%s, horas_asignadas=%s "
                            f"WHERE id=%s AND {_SA} ")
ASIGNACION_STAR_SQL = f"SELECT * FROM asignaciones_docentes_comision WHERE id = %s AND {_SA} LIMIT 1"
UPDATE_ESTADO_ASIGNACION_SQL = f"UPDATE asignaciones_docentes_comision SET estado = %s, observaciones = %s WHERE id = %s AND {_SA} "
DELETE_ASIGNACION_SQL = f"DELETE FROM asignaciones_docentes_comision WHERE id=%s AND {_SA} "
FRANJAS_DE_HORARIO_SQL = f"SELECT * FROM horarios_asignacion_docente_comision WHERE horario_comision_id=%s AND {_SF} "
DELETE_FRANJA_SQL = f"DELETE FROM horarios_asignacion_docente_comision WHERE id=%s AND {_SF} "
UPDATE_FRANJA_SQL = ("UPDATE horarios_asignacion_docente_comision SET dia=%s, hora_inicio=%s, hora_fin=%s, horas=%s "
                     f"WHERE id=%s AND {_SF} ")
DELETE_FRANJAS_HORARIO_SQL = f"DELETE FROM horarios_asignacion_docente_comision WHERE horario_comision_id=%s AND {_SF} "
DOCENTE_LOCAL_SQL = ("SELECT cuil FROM docentes WHERE cuil = %s AND (docentes.institucion_id = %s) AND "
                     "(docentes.departamento_id = %s) LIMIT 1")
DOCENTE_OTRO_DEP_SQL = """
    SELECT
        doc.cuil, doc.nombre, doc.apellido, doc.nombres, doc.legajo, doc.titulo,
        COALESCE(doc.titulo_posgrado, '') AS titulo_posgrado,
        doc.antiguedad_anios,
        COALESCE(doc.nivel_posgrado_salarial, '') AS nivel_posgrado_salarial,
        doc.email, doc.telefono, doc.ref_legajo_fisico,
        COALESCE(dep.nombre, 'otro departamento') AS departamento_origen
    FROM docentes doc
    LEFT JOIN departamentos dep ON dep.id = doc.departamento_id
    WHERE doc.institucion_id = %s
      AND COALESCE(doc.departamento_id, -1) <> %s
      AND doc.cuil = %s
    ORDER BY doc.id
    LIMIT 1
"""
INSERT_PRESTADO_SQL = ("INSERT INTO docentes (cuil, nombre, apellido, nombres, legajo, titulo, titulo_posgrado, "
                       "antiguedad_anios, nivel_posgrado_salarial, email, telefono, ref_legajo_fisico, estado, tipo_docente, "
                       "fecha_alta, observaciones, institucion_id, departamento_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, "
                       "%s, %s, %s, %s, 'Activo', 'Prestado', %s, %s, %s, %s)  RETURNING id")
_SI = "(inscriptos_asignatura_periodo.institucion_id = %s) AND (inscriptos_asignatura_periodo.departamento_id = %s)"
INSCRIPTO_EXISTENTE_SQL = ("SELECT id, cantidad_final, fecha_actualizacion_final, COALESCE(observaciones,'') FROM "
                           "inscriptos_asignatura_periodo WHERE periodo_id=%s AND materia_id=%s AND "
                           f"COALESCE(opcion_curricular_id,0)=%s AND {_SI} LIMIT 1")
UPDATE_INSCRIPTO_SQL = ("UPDATE inscriptos_asignatura_periodo SET cantidad=%s, cantidad_final=%s, fecha_actualizacion=%s, "
                        f"fecha_actualizacion_final=%s, observaciones=%s WHERE id=%s AND {_SI} ")
INSERT_INSCRIPTO_SQL = ("INSERT INTO inscriptos_asignatura_periodo (periodo_id, materia_id, opcion_curricular_id, cantidad, "
                        "cantidad_final, fecha_actualizacion, fecha_actualizacion_final, observaciones, institucion_id, "
                        "departamento_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)  RETURNING id")
# get_auth_conn (sin inyector; institucion explicita)
SEDE_POR_NOMBRE_SQL = ("SELECT * FROM sedes_institucion WHERE institucion_id = %s AND LOWER(TRIM(nombre)) = LOWER(TRIM(%s)) "
                       "LIMIT 1")
INSERT_SEDE_SQL = ("INSERT INTO sedes_institucion (institucion_id, nombre, direccion, localidad, estado, observaciones, "
                   "fecha_creacion, fecha_actualizacion) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)")
SEDE_DUPLICADA_SQL = ("SELECT id FROM sedes_institucion WHERE institucion_id = %s AND LOWER(TRIM(nombre)) = LOWER(TRIM(%s)) "
                      "AND id <> %s LIMIT 1")
UPDATE_SEDE_SQL = ("UPDATE sedes_institucion SET nombre = %s, direccion = %s, localidad = %s, estado = %s, observaciones = %s, "
                   "fecha_actualizacion = %s WHERE id = %s AND institucion_id = %s")
DELETE_SEDE_SQL = "DELETE FROM sedes_institucion WHERE id = %s AND institucion_id = %s"


# ------------------------------------------------------------------------------------------ Unidad de Comisiones
class _LazyMaterias:
    """``MateriasRepository`` cuyas lecturas abren cada vez la conexion de la operacion (como ``get_planes_conn``)."""

    def __init__(self, u: "Unidad"):
        self._u = u

    def __getattr__(self, name):
        return lambda *a, **k: self._u.read(lambda repo: getattr(MateriasRepository(repo._conn, repo.inst), name)(*a, **k))


class _LazyRepo:
    """``ComisionesRepository`` cuyas lecturas abren cada vez la conexion de la operacion (como ``get_conn``)."""

    def __init__(self, u: "Unidad"):
        self._u = u
        self.inst, self.dep = u.inst, u.dep
        self._scope = [u.inst, u.dep]

    def materias(self):
        return _LazyMaterias(self._u)

    def __getattr__(self, name):
        return lambda *a, **k: self._u.read(lambda repo: getattr(repo, name)(*a, **k))


class Unidad(DE.Unidad):
    """La ``Unidad`` B12H de Designaciones con el repositorio de Comisiones (mismo acoplamiento de COMMITs)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._lector: Optional[Lector] = None

    @property
    def lector(self) -> Lector:
        """Lecturas frescas dentro del writer, memoizadas hasta la proxima escritura (B12I capa W)."""
        if self._lector is None:
            self._lector = Lector(_LazyRepo(self), self.today)
        return self._lector

    def read(self, fn: Callable[[ComisionesRepository], Any]) -> Any:
        with self._transaction() as conn:
            return fn(ComisionesRepository(conn, self.inst, self.dep))

    def commit(self, fn: Callable[[ComisionesRepository], Any]) -> Any:
        if self.audit_failed:
            raise AuditoriaFallida("AUDIT_FAILED_EARLIER")
        repo = None
        try:
            with self._transaction() as conn:
                repo = ComisionesRepository(conn, self.inst, self.dep)
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
            if self._lector is not None:
                self._lector.invalidar()
        return result


# ------------------------------------------------------------------------------------------ helpers de SQL
def _insertar_vinculos(repo: ComisionesRepository, comision_id, vinculos, origen="v118", reemplazar=True,
                       hoy: Optional[date] = None) -> None:
    """``insertar_vinculos_materias_comision_cursor_v118`` (l. 28558): dentro del mismo COMMIT."""
    if reemplazar:
        repo._mutate(DELETE_VINCULOS_SQL, [int(comision_id)] + repo._scope)
    vistos = set()
    for v in list(vinculos or []):
        try:
            mid = int(v.get("materia_id"))
        except Exception:
            continue
        if mid in vistos:
            continue
        vistos.add(mid)
        repo._insert_id(INSERT_VINCULO_SQL, [
            int(comision_id), mid, v.get("carrera_id_snapshot"), v.get("carrera_snapshot", ""),
            v.get("escuela_snapshot", ""), v.get("plan_version_snapshot", ""),
            v.get("anio_snapshot", ""), v.get("cuatrimestre_snapshot", ""),
            v.get("dictado_snapshot", ""), v.get("carga_semanal_snapshot", ""),
            v.get("carga_total_snapshot", ""), v.get("codigo_snapshot", ""),
            v.get("asignatura_snapshot", ""), str(hoy), str(origen or "v118"),
        ] + repo._scope)


def existe_horario_duplicado(u: Unidad, comision_id, dia, hora_inicio, hora_fin, excluir_id=None) -> pd.DataFrame:
    """l. 18971 (``(? IS NULL OR id <> ?)`` con ``excluir_id`` ausente se omite: misma semantica)."""
    excluir = "" if excluir_id is None else " AND (id <> %s)"
    params = [comision_id, dia, hora_inicio, hora_fin] + ([] if excluir_id is None else [excluir_id])
    return u.read(lambda repo: repo.read_sql(HORARIO_DUP_SQL.replace("{excluir}", excluir), params + repo._scope))


def existe_asignacion_duplicada(u: Unidad, comision_id, cuil, rol=None, excluir_id=None) -> pd.DataFrame:
    """l. 19127: un docente una sola vez por comision, sin importar el rol."""
    excluir = "" if excluir_id is None else " AND (id <> %s)"
    params = [comision_id, cuil] + ([] if excluir_id is None else [excluir_id])
    return u.read(lambda repo: repo.read_sql(ASIGNACION_DUP_SQL.replace("{excluir}", excluir), params + repo._scope))


def _reconciliar(u: Unidad, cuil, periodo_id) -> list:
    """``reconciliar_horas_proyectos_por_comisiones_v184`` envuelto como en el certificado (``try/except pass``)."""
    from .proyectos import reconciliar_horas_proyectos_por_comisiones_v184
    try:
        return reconciliar_horas_proyectos_por_comisiones_v184(u, cuil, periodo_id) or []
    except AuditoriaFallida:
        raise
    except Exception:
        return []


def _contexto_asignacion_comision_v184(u: Unidad, comision_id=None, asignacion_id=None) -> list:
    """l. 40495."""
    try:
        if asignacion_id is not None:
            df = u.read(lambda repo: repo.read_sql(CONTEXTO_ASIGNACION_SQL, [int(asignacion_id)] + repo._scope * 2))
        else:
            df = u.read(lambda repo: repo.read_sql(CONTEXTO_COMISION_SQL, [int(comision_id)] + repo._scope * 2))
        if df is None or df.empty:
            return []
        return [(str(r.get("cuil") or "").strip(), int(r.get("periodo_id")))
                for _, r in df.iterrows() if str(r.get("cuil") or "").strip() and pd.notna(r.get("periodo_id"))]
    except Exception:
        return []


# ------------------------------------------------------------------------------------------ comisiones
def guardar_comision(u: Unidad, periodo_id, materia_id, nombre_comision, turno, sede, modalidad, estado, observaciones,
                     fecha_creacion=None, materia_especifica="", opcion_curricular_id=None,
                     materia_ids_adicionales=None) -> int:
    """l. 18562."""
    L = u.lector
    fecha_creacion_final = str(fecha_creacion) if fecha_creacion else str(u.today)
    seleccion = L.materias_conceptuales_seleccionadas_v122(materia_id, materia_ids_adicionales)
    if len(seleccion) > 1 and any(x["es_optativa_electiva"] for x in seleccion):
        raise ValueError("Las comisiones multicódigo pueden combinar materias comunes, pero no espacios Optativa/Electiva.")
    materia_id_principal = int(seleccion[0]["materia_id"])
    es_oe = len(seleccion) == 1 and seleccion[0]["es_optativa_electiva"]
    opcion_id = None
    materia_especifica_final = ""
    if es_oe:
        if opcion_curricular_id in [None, ""]:
            raise ValueError("Para abrir una comisión de una Optativa/Electiva seleccioná primero la opción curricular concreta.")
        opcion_id = int(opcion_curricular_id)
        op = L.opcion_curricular_v120(opcion_id)
        if not op or str(op.get("estado") or "Activa").strip() != "Activa":
            raise ValueError("La opción curricular seleccionada no existe o no está activa.")
        materia_especifica_final = R.limpiar_texto_tabla(op.get("nombre", ""))
    vinculos = L.preparar_vinculos_multiples_materias_comision_v122(
        materia_id_principal, [x["materia_id"] for x in seleccion[1:]], opcion_curricular_id=opcion_id,
        incluir_historicas=False)
    duplicada = L.existe_comision_duplicada(
        periodo_id, materia_id_principal, nombre_comision, turno, sede, modalidad, opcion_curricular_id=opcion_id,
        materia_especifica=materia_especifica_final, materia_ids_adicionales=[x["materia_id"] for x in seleccion[1:]])
    if not duplicada.empty:
        u.avisos.append(MSG_COMISION_YA_CARGADA)
        return int(duplicada.iloc[0]["id"])
    origen = ("apertura_opcion_curricular_v120" if es_oe else
              "apertura_multicodigo_v122" if len(seleccion) > 1 else "apertura_v118")

    def body(repo: ComisionesRepository) -> int:
        nuevo_id = repo._insert_id(INSERT_COMISION_SQL, [
            periodo_id, materia_id_principal, nombre_comision, turno, sede, modalidad, estado, observaciones,
            fecha_creacion_final, materia_especifica_final, opcion_id] + repo._scope)
        _insertar_vinculos(repo, nuevo_id, vinculos, origen=origen, reemplazar=True, hoy=u.today)
        return nuevo_id
    return u.commit(body)


def actualizar_comision(u: Unidad, comision_id, materia_id, nombre_comision, turno, sede, modalidad, estado, observaciones,
                        materia_especifica="", opcion_curricular_id=None, materia_ids_adicionales=None) -> None:
    """l. 18638."""
    L = u.lector
    seleccion_nueva = L.materias_conceptuales_seleccionadas_v122(materia_id, materia_ids_adicionales)
    if len(seleccion_nueva) > 1 and any(x["es_optativa_electiva"] for x in seleccion_nueva):
        raise ValueError("Las comisiones multicódigo pueden combinar materias comunes, pero no espacios Optativa/Electiva.")
    ids_nuevos = [int(x["materia_id"]) for x in seleccion_nueva]
    claves_nuevas = frozenset(x["clave"] for x in seleccion_nueva)
    ids_actuales = L.materias_conceptuales_comision_v122(comision_id)
    claves_actuales = set()
    for rep in ids_actuales:
        info = L.materia_comision(rep) or {}
        claves_actuales.add(R.limpiar_texto_tabla(info.get("_clave_unica", "")) or R.clave_materia_conceptual_v137(info)
                            or f"ID:{int(rep)}")
    claves_actuales = frozenset(claves_actuales)

    def body(repo: ComisionesRepository) -> None:
        fila = repo._first(COMISION_ACTUAL_SQL, [int(comision_id)] + repo._scope)
        if not fila:
            raise ValueError("No se encontró la comisión seleccionada.")
        fila = list(fila.values())
        materia_id_anterior = int(fila[0]) if fila[0] is not None else None
        opcion_id_anterior = int(fila[1]) if len(fila) > 1 and fila[1] is not None else None
        especifica_anterior = str(fila[2] or "") if len(fila) > 2 else ""
        principal_nuevo = ids_nuevos[0]
        misma_principal = bool(materia_id_anterior is not None
                               and L.materias_mismo_grupo_conceptual_v118(materia_id_anterior, principal_nuevo))
        materia_id_guardar = materia_id_anterior if misma_principal and materia_id_anterior is not None else principal_nuevo
        row = repo._first(COUNT_VINCULOS_SQL, [int(comision_id)] + repo._scope)
        tiene_vinculos = int((list(row.values()) if row else [0])[0] or 0) > 0
        composicion_igual = bool(claves_actuales and claves_actuales == claves_nuevas)
        es_oe = len(seleccion_nueva) == 1 and seleccion_nueva[0]["es_optativa_electiva"]
        opcion_id_final = None
        materia_especifica_final = ""
        reemplazar_vinculos = False
        vinculos_nuevos = None
        if es_oe:
            if opcion_curricular_id in [None, ""]:
                if composicion_igual and opcion_id_anterior is None and especifica_anterior.strip():
                    opcion_id_final = None
                    materia_especifica_final = especifica_anterior.strip()
                    reemplazar_vinculos = not tiene_vinculos
                    if reemplazar_vinculos:
                        vinculos_nuevos = L.preparar_vinculos_materias_comision_v118(materia_id_guardar, incluir_historicas=True)
                else:
                    raise ValueError("Seleccioná la opción curricular concreta de esta Optativa/Electiva.")
            else:
                opcion_id_final = int(opcion_curricular_id)
                op = L.opcion_curricular_v120(opcion_id_final)
                if not op:
                    raise ValueError("No se encontró la opción curricular seleccionada.")
                materia_especifica_final = R.limpiar_texto_tabla(op.get("nombre", ""))
                misma_opcion = bool(composicion_igual and opcion_id_anterior is not None
                                    and int(opcion_id_anterior) == int(opcion_id_final))
                if misma_opcion and tiene_vinculos:
                    reemplazar_vinculos = False
                else:
                    if str(op.get("estado") or "Activa").strip() != "Activa":
                        raise ValueError("La opción curricular seleccionada no está activa para nuevas comisiones.")
                    vinculos_nuevos = L.preparar_vinculos_multiples_materias_comision_v122(
                        principal_nuevo, [], opcion_curricular_id=opcion_id_final, incluir_historicas=False)
                    reemplazar_vinculos = True
        else:
            opcion_id_final = None
            materia_especifica_final = ""
            if composicion_igual and opcion_id_anterior is None and tiene_vinculos:
                reemplazar_vinculos = False
            else:
                vinculos_nuevos = L.preparar_vinculos_multiples_materias_comision_v122(
                    principal_nuevo, ids_nuevos[1:], incluir_historicas=False)
                reemplazar_vinculos = True
        repo._mutate(UPDATE_COMISION_SQL, [materia_id_guardar, nombre_comision, turno, sede, modalidad, estado,
                                           observaciones, materia_especifica_final, opcion_id_final, comision_id]
                     + repo._scope)
        if reemplazar_vinculos:
            _insertar_vinculos(repo, comision_id, vinculos_nuevos or [], origen=(
                "edicion_opcion_curricular_v128" if es_oe
                else "edicion_multicodigo_v122" if len(ids_nuevos) > 1
                else "edicion_materia_v122"), reemplazar=True, hoy=u.today)
    u.commit(body)


def actualizar_nombre_comision_correccion_v180(u: Unidad, comision_id, nuevo_nombre) -> dict:
    """l. 18773 (sin movimiento)."""
    L = u.lector
    cid = int(comision_id)
    nuevo = str(nuevo_nombre or "").strip()
    if not nuevo:
        raise ValueError("La comisión no puede quedar vacía. Indicá un número o letra.")
    df = u.read(lambda repo: repo.read_sql(COMISION_V180_SQL, [cid] + repo._scope))
    if df.empty:
        raise ValueError("No se encontró la comisión seleccionada.")
    fila = df.iloc[0]
    anterior = str(fila.get("nombre_comision") or "").strip()
    if nuevo == anterior:
        return {"cambio": False, "anterior": anterior, "nuevo": nuevo}
    try:
        materia_id = int(fila.get("materia_id"))
    except Exception:
        raise ValueError("La comisión no tiene una materia principal válida.")
    try:
        ids_actuales = [int(x) for x in L.materias_conceptuales_comision_v122(cid)]
    except Exception:
        ids_actuales = [materia_id]
    adicionales = [mid for mid in ids_actuales if int(mid) != int(materia_id)]
    oid = fila.get("opcion_curricular_id")
    try:
        opcion_id = int(oid) if oid is not None and not pd.isna(oid) else None
    except Exception:
        opcion_id = None
    duplicada = L.existe_comision_duplicada(
        int(fila.get("periodo_id")), materia_id, nuevo, str(fila.get("turno") or ""), str(fila.get("sede") or ""),
        str(fila.get("modalidad") or ""), excluir_id=cid, opcion_curricular_id=opcion_id,
        materia_especifica=str(fila.get("materia_especifica") or ""), materia_ids_adicionales=adicionales)
    if isinstance(duplicada, pd.DataFrame) and not duplicada.empty:
        raise ValueError(f"No se puede cambiar la comisión a '{nuevo}' porque duplicaría otra comisión existente "
                         "con la misma materia/códigos, turno, sede y modalidad.")
    u.commit(lambda repo: repo._mutate(UPDATE_NOMBRE_SQL, [nuevo, cid] + repo._scope))
    return {"cambio": True, "anterior": anterior, "nuevo": nuevo}


def actualizar_nombres_comisiones_lote_v195(u: Unidad, cambios) -> dict:
    """l. 43824: valida todo el lote y aplica en UNA transaccion (un COMMIT)."""
    t0 = time.perf_counter()
    L = u.lector
    normalizados = []
    vistos_ids = set()
    for item in list(cambios or []):
        if isinstance(item, dict):
            cid = item.get("id") or item.get("comision_id")
            anterior = item.get("anterior", "")
            nuevo = item.get("nuevo", "")
        else:
            cid, anterior, nuevo = item[0], item[1], item[2]
        cid = int(cid)
        nuevo = str(nuevo or "").strip()
        anterior = str(anterior or "").strip()
        if not nuevo:
            raise ValueError(f"La comisión ID {cid} no puede quedar vacía.")
        if cid in vistos_ids:
            continue
        vistos_ids.add(cid)
        normalizados.append((cid, anterior, nuevo))
    if not normalizados:
        return {"aplicados": 0, "segundos": round(time.perf_counter() - t0, 4), "cambios": []}
    ids = [x[0] for x in normalizados]
    sql = COMISIONES_LOTE_SQL.replace("{ph}", ",".join(["%s"] * len(ids)))
    df_target = u.read(lambda repo: repo.read_sql(sql, ids + repo._scope))
    if df_target is None or len(df_target) != len(ids):
        encontrados = set(pd.to_numeric(df_target.get("id", pd.Series(dtype=float)), errors="coerce").dropna().astype(int)
                          .tolist()) if isinstance(df_target, pd.DataFrame) else set()
        faltan = sorted(set(ids) - encontrados)
        raise ValueError(f"No se encontraron las comisiones: {faltan}")
    mapa_target = {int(r["id"]): r.to_dict() for _, r in df_target.iterrows()}
    errores = []
    for cid, anterior, nuevo in normalizados:
        fila = mapa_target[cid]
        actual = str(fila.get("nombre_comision") or "").strip()
        if nuevo == actual:
            continue
        try:
            materia_id = int(fila.get("materia_id"))
        except Exception:
            errores.append(f"ID {cid}: la comisión no tiene una materia principal válida.")
            continue
        try:
            reps = [int(x) for x in L.materias_conceptuales_comision_v122(cid)]
        except Exception:
            reps = [materia_id]
        adicionales = [x for x in reps if int(x) != materia_id]
        oid = fila.get("opcion_curricular_id")
        try:
            opcion_id = int(oid) if oid is not None and not pd.isna(oid) else None
        except Exception:
            opcion_id = None
        dup = L.existe_comision_duplicada(
            int(fila.get("periodo_id")), materia_id, nuevo, str(fila.get("turno") or ""), str(fila.get("sede") or ""),
            str(fila.get("modalidad") or ""), excluir_id=cid, opcion_curricular_id=opcion_id,
            materia_especifica=str(fila.get("materia_especifica") or ""), materia_ids_adicionales=adicionales)
        if isinstance(dup, pd.DataFrame) and not dup.empty:
            errores.append(f"ID {cid}: '{nuevo}' duplicaría otra comisión existente "
                           "con la misma materia/códigos, turno, sede y modalidad.")
    propuestas = []
    for cid, anterior, nuevo in normalizados:
        fila = mapa_target[cid]
        propuestas.append({"id": cid, "periodo_id": int(fila.get("periodo_id")), "nombre": nuevo.strip().upper(),
                           "turno": str(fila.get("turno") or "").strip().upper(),
                           "sede": str(fila.get("sede") or "").strip().upper(),
                           "modalidad": str(fila.get("modalidad") or "").strip().upper()})
    grupos: dict = {}
    for p in propuestas:
        grupos.setdefault((p["periodo_id"], p["nombre"], p["turno"], p["sede"], p["modalidad"]), []).append(p["id"])
    claves_conceptuales: dict = {}
    for ids_grupo in grupos.values():
        if len(ids_grupo) <= 1:
            continue
        for cid in ids_grupo:
            try:
                claves_conceptuales[cid] = L.claves_comision_existente_v122(cid)
            except Exception:
                claves_conceptuales[cid] = frozenset()
        for i in range(len(ids_grupo)):
            for j in range(i + 1, len(ids_grupo)):
                a, b = ids_grupo[i], ids_grupo[j]
                if claves_conceptuales.get(a) and (claves_conceptuales.get(a) & claves_conceptuales.get(b, frozenset())):
                    errores.append(f"IDs {a} y {b}: los cambios del lote generarían dos comisiones "
                                   "con la misma identidad operativa y materias/códigos superpuestos.")
    if errores:
        raise ValueError("\n".join(dict.fromkeys(errores)))
    cambios_reales = [(cid, str(mapa_target[cid].get("nombre_comision") or "").strip(), nuevo)
                      for cid, anterior, nuevo in normalizados
                      if nuevo != str(mapa_target[cid].get("nombre_comision") or "").strip()]
    if not cambios_reales:
        return {"aplicados": 0, "segundos": round(time.perf_counter() - t0, 4), "cambios": []}

    def body(repo: ComisionesRepository) -> int:
        aplicados = 0
        for cid, _anterior, nuevo in cambios_reales:
            aplicados += repo._mutate(UPDATE_NOMBRE_SQL, [nuevo, int(cid)] + repo._scope)
        return aplicados
    aplicados = u.commit(body)
    return {"aplicados": int(aplicados), "segundos": round(time.perf_counter() - t0, 4), "cambios": cambios_reales}


def _eliminar_comision_base(repo: ComisionesRepository, comision_id) -> None:
    for sql in (DELETE_ASIGNACIONES_COMISION_SQL, DELETE_HORARIOS_COMISION_SQL, DELETE_INS_CM_SQL, DELETE_INS_C_SQL,
                DELETE_VINCULOS_SQL):
        repo._mutate(sql, [comision_id] + repo._scope)
    repo._mutate(DELETE_COMISION_SQL, [comision_id] + repo._scope)


def eliminar_comision(u: Unidad, comision_id) -> None:
    """v95 l. 32800 (franjas: COMMIT 1) -> base l. 18849 (resto: COMMIT 2)."""
    with u.writer(W_ELIMINAR_COMISION):
        u.commit(lambda repo: repo._mutate(DELETE_FRANJAS_COMISION_SQL, [int(comision_id)] + repo._scope))
        u.commit(lambda repo: _eliminar_comision_base(repo, comision_id))


def revertir_alta_comision_incompleta(u: Unidad, comision_id) -> None:
    """``_b10_revertir_alta_comision_incompleta`` (l. 59172): elimina SOLO la comision recien creada."""
    eliminar_comision(u, comision_id)


# ------------------------------------------------------------------------------------------ horarios
def sincronizar_horas_asignaciones_comision(u: Unidad, comision_id):
    """v184 l. 40531 -> v95 l. 30389."""
    with u.writer(W_SINCRONIZAR_HORAS):
        afectados = _contexto_asignacion_comision_v184(u, comision_id=comision_id)

        def body(repo: ComisionesRepository):
            df = repo.read_sql(ASIGNACIONES_ACTIVAS_SQL, [int(comision_id)] + repo._scope)
            total = repo.read_sql(SUMA_HORARIOS_SQL, [int(comision_id)] + repo._scope)
            total_com = float(total.iloc[0]["h"] or 0) if not total.empty else 0.0
            actualizadas = 0
            for _, r in df.iterrows():
                aid = int(r["id"])
                if bool(r.get("usa_horario_personalizado", False)):
                    dfx = repo.read_sql(SUMA_FRANJAS_SQL, [aid] + repo._scope)
                    tot = float(dfx.iloc[0]["h"] or 0) if not dfx.empty else 0.0
                else:
                    tot = total_com
                repo._mutate(UPDATE_HORAS_ASIGNACION_SQL, [_numeric(round(tot, 2)), aid] + repo._scope)
                actualizadas += 1
            return actualizadas, total_com
        resultado = u.commit(body)
        for cuil, pid in afectados:
            _reconciliar(u, cuil, pid)
        return resultado


def guardar_horario_comision(u: Unidad, comision_id, dia, hora_inicio, hora_fin, observaciones=""):
    """l. 19039."""
    dup = existe_horario_duplicado(u, comision_id, dia, hora_inicio, hora_fin)
    if not dup.empty:
        u.avisos.append(MSG_HORARIO_YA_CARGADO)
        return R.calcular_horas_desde_texto(hora_inicio, hora_fin)
    horas = R.calcular_horas_desde_texto(hora_inicio, hora_fin)
    u.commit(lambda repo: repo._insert_id(INSERT_HORARIO_SQL, [comision_id, dia, hora_inicio, hora_fin, _numeric(horas),
                                                               observaciones] + repo._scope))
    sincronizar_horas_asignaciones_comision(u, comision_id)
    return horas


def _actualizar_horario_base(u: Unidad, horario_id, dia, hora_inicio, hora_fin, observaciones=""):
    """l. 19007."""
    df = u.read(lambda repo: repo.read_sql(HORARIO_COMISION_SQL, [int(horario_id)] + repo._scope))
    if df.empty:
        return False, "No se encontró el horario."
    comision_id = int(df.iloc[0]["comision_id"])
    dup = existe_horario_duplicado(u, comision_id, dia, hora_inicio, hora_fin, excluir_id=horario_id)
    if not dup.empty:
        return False, "Ya existe otro horario igual en la comisión."
    horas = R.calcular_horas_desde_texto(hora_inicio, hora_fin)
    if horas <= 0:
        return False, "La hora de finalización debe ser posterior a la de inicio."
    u.commit(lambda repo: repo._mutate(UPDATE_HORARIO_SQL, [dia, hora_inicio, hora_fin, _numeric(horas), observaciones,
                                                            int(horario_id)] + repo._scope))
    sincronizar_horas_asignaciones_comision(u, comision_id)
    return True, "Horario actualizado correctamente."


def _reparar_horarios_personalizados_v95(u: Unidad, horario_id, dia, hora_inicio, hora_fin) -> None:
    """l. 30451: recorta o borra franjas personalizadas del horario editado (un COMMIT)."""
    with u.writer(W_REPARAR_FRANJAS):
        def body(repo: ComisionesRepository):
            df = repo.read_sql(FRANJAS_DE_HORARIO_SQL, [int(horario_id)] + repo._scope)
            afectados = set()
            n_ini, n_fin = R.minutos_v95(hora_inicio), R.minutos_v95(hora_fin)
            for _, r in df.iterrows():
                aid = int(r["asignacion_id"])
                afectados.add(aid)
                a, b = R.minutos_v95(r.get("hora_inicio")), R.minutos_v95(r.get("hora_fin"))
                ini = max(a if a is not None else n_ini, n_ini)
                fin = min(b if b is not None else n_fin, n_fin)
                if ini is None or fin is None or fin <= ini:
                    repo._mutate(DELETE_FRANJA_SQL, [int(r["id"])] + repo._scope)
                else:
                    hi, hf = f"{ini // 60:02d}:{ini % 60:02d}", f"{fin // 60:02d}:{fin % 60:02d}"
                    repo._mutate(UPDATE_FRANJA_SQL, [R.normalizar_dia_v95(dia), hi, hf, R.horas_intervalo_v95(hi, hf),
                                                     int(r["id"])] + repo._scope)
            for aid in afectados:
                dfx = repo.read_sql(SUMA_FRANJAS_SQL, [aid] + repo._scope)
                total = float(dfx.iloc[0]["h"] or 0) if not dfx.empty else 0.0
                repo._mutate(UPDATE_HORAS_ASIGNACION_SQL, [_numeric(total), aid] + repo._scope)
        u.commit(body)


def actualizar_horario_comision(u: Unidad, horario_id, dia, hora_inicio, hora_fin, observaciones=""):
    """v95 l. 30475."""
    ok, msg = _actualizar_horario_base(u, horario_id, dia, hora_inicio, hora_fin, observaciones)
    if ok:
        _reparar_horarios_personalizados_v95(u, horario_id, dia, hora_inicio, hora_fin)
        df = u.read(lambda repo: repo.read_sql(COMISION_DE_HORARIO_SQL, [int(horario_id)] + repo._scope))
        if not df.empty:
            sincronizar_horas_asignaciones_comision(u, int(df.iloc[0]["comision_id"]))
    return ok, msg


def eliminar_horario_comision(u: Unidad, horario_id) -> None:
    """v95 l. 30486 -> base l. 19059."""
    df = u.read(lambda repo: repo.read_sql(COMISION_DE_HORARIO_SQL, [int(horario_id)] + repo._scope))
    u.commit(lambda repo: repo._mutate(DELETE_FRANJAS_HORARIO_SQL, [int(horario_id)] + repo._scope))
    # base: lee la comision, borra el horario (COMMIT) y resincroniza
    fila = u.read(lambda repo: repo._first(COMISION_DE_HORARIO_SQL, [horario_id] + repo._scope))
    comision_id = int(fila["comision_id"]) if fila and fila.get("comision_id") is not None else None
    u.commit(lambda repo: repo._mutate(DELETE_HORARIO_SQL, [horario_id] + repo._scope))
    if comision_id is not None:
        sincronizar_horas_asignaciones_comision(u, comision_id)
    if not df.empty:
        sincronizar_horas_asignaciones_comision(u, int(df.iloc[0]["comision_id"]))


# ------------------------------------------------------------------------------------------ asignaciones
def asegurar_docente_prestado_local_si_corresponde(u: Unidad, cuil) -> bool:
    """l. 26201: crea la fila local ``Prestado`` si el CUIL existe en otro departamento de la institucion."""
    if not cuil:
        return False
    with u.writer(W_PRESTADO_LOCAL):
        try:
            df_local = u.read(lambda repo: repo.read_sql(DOCENTE_LOCAL_SQL, [cuil] + repo._scope))
            if not df_local.empty:
                return False
            df_src = u.read(lambda repo: repo.read_raw(DOCENTE_OTRO_DEP_SQL, [int(u.inst), int(u.dep), cuil]))
            if df_src.empty:
                return False
            r = df_src.iloc[0]
            obs = (f"Docente prestado desde {r.get('departamento_origen', 'otro departamento')}. No posee designación local "
                   "en este departamento.")
            nombre_val = str(r.get("nombre") or R.nombre_completo(str(r.get("apellido") or ""), str(r.get("nombres") or ""))
                             or "")
            antig = r.get("antiguedad_anios")
            antig = (None if pd.isna(antig) else int(antig)) if antig is not None else None
            u.commit(lambda repo: repo._insert_id(INSERT_PRESTADO_SQL, [
                str(r.get("cuil") or cuil), nombre_val, str(r.get("apellido") or ""), str(r.get("nombres") or ""),
                str(r.get("legajo") or ""), str(r.get("titulo") or ""), str(r.get("titulo_posgrado") or ""), antig,
                str(r.get("nivel_posgrado_salarial") or ""), str(r.get("email") or ""), str(r.get("telefono") or ""),
                str(r.get("ref_legajo_fisico") or ""), str(u.today), obs] + repo._scope))
            return True
        except AuditoriaFallida:
            raise
        except Exception:
            return False


def guardar_horarios_reales_asignacion(u: Unidad, asignacion_id, horarios_reales):
    """v184 l. 40542 -> base l. 30349."""
    with u.writer(W_HORARIOS_REALES):
        df_asig = u.read(lambda repo: repo.read_sql(ASIGNACION_COMISION_SQL, [int(asignacion_id)] + repo._scope))
        if df_asig.empty:
            raise ValueError("No se encontró la asignación docente.")
        comision_id = int(df_asig.iloc[0]["comision_id"])
        df_base = u.lector.horarios_comision(comision_id)
        filas = []
        for item in (horarios_reales or []):
            dia = R.normalizar_dia_v95(item.get("dia"))
            hi = R.hora_texto_v95(item.get("hora_inicio"))
            hf = R.hora_texto_v95(item.get("hora_fin"))
            if not R.es_subintervalo_v95(dia, hi, hf, df_base):
                raise ValueError(f"El horario {dia} {hi}-{hf} queda fuera del horario definido para la comisión.")
            match = df_base[
                (df_base["dia"].fillna("").map(R.normalizar_dia_v95) == dia)
                & (df_base["hora_inicio"].fillna("").map(R.minutos_v95) <= R.minutos_v95(hi))
                & (df_base["hora_fin"].fillna("").map(R.minutos_v95) >= R.minutos_v95(hf))
            ]
            horario_id = int(match.iloc[0]["id"]) if not match.empty else None
            filas.append((horario_id, dia, hi, hf, R.horas_intervalo_v95(hi, hf), str(item.get("observaciones") or "")))
        if not filas:
            raise ValueError("Seleccioná al menos una franja horaria para el docente.")

        def body(repo: ComisionesRepository):
            repo._mutate(DELETE_FRANJAS_ASIGNACION_SQL, [int(asignacion_id)] + repo._scope)
            for horario_id, dia, hi, hf, horas, obs in filas:
                repo._insert_id(INSERT_FRANJA_SQL, [int(asignacion_id), horario_id, dia, hi, hf, horas, obs] + repo._scope)
            total = round(sum(x[4] for x in filas), 2)
            repo._mutate(UPDATE_PERSONALIZADO_SQL, [True, _numeric(total), int(asignacion_id)] + repo._scope)
            return total
        resultado = u.commit(body)
        for cuil, pid in _contexto_asignacion_comision_v184(u, asignacion_id=asignacion_id):
            _reconciliar(u, cuil, pid)
        return resultado


def guardar_asignacion_docente_comision(u: Unidad, comision_id, cuil, rol, horas_asignadas, estado, observaciones,
                                        horarios_reales=None) -> int:
    """v184 l. 40554 -> (validacion v174 de prestamos) -> v95 l. 30415."""
    with u.writer(W_GUARDAR_ASIGNACION):
        try:
            dfc = u.read(lambda repo: repo.read_sql(PERIODO_DE_COMISION_SQL, [int(comision_id)] + repo._scope))
            pid = int(dfc.iloc[0].get("periodo_id")) if not dfc.empty else None
        except Exception:
            pid = None
        if pid is not None:
            tipo_local = u.lector.docente_tipo_local(cuil)
            if str(tipo_local).strip().casefold() == "prestado" and not u.lector.prestamo_docente_activo_v174(cuil, pid):
                raise ValueError("El docente fue prestado en otro período. Registralo nuevamente como prestado "
                                 "para este período antes de asignarlo a una comisión.")
        # v95
        try:
            asegurar_docente_prestado_local_si_corresponde(u, cuil)
        except AuditoriaFallida:
            raise
        except Exception:
            pass
        dup = existe_asignacion_duplicada(u, comision_id, cuil, rol)
        if not dup.empty:
            aid = int(dup.iloc[0]["id"])
            if horarios_reales is not None:
                guardar_horarios_reales_asignacion(u, aid, horarios_reales)
        else:
            flag_personalizado = bool(horarios_reales is not None)
            aid = u.commit(lambda repo: repo._insert_id(INSERT_ASIGNACION_SQL, [
                int(comision_id), str(cuil), rol, _numeric(float(horas_asignadas or 0)), estado, observaciones,
                flag_personalizado] + repo._scope))
            if horarios_reales is not None:
                guardar_horarios_reales_asignacion(u, aid, horarios_reales)
            else:
                sincronizar_horas_asignaciones_comision(u, comision_id)
        # v184
        if pid is not None:
            _reconciliar(u, cuil, pid)
        return aid


def actualizar_estado_asignacion_docente_comision(u: Unidad, asignacion_id, estado="Finalizada", observaciones_extra=""):
    """l. 19173 (baja logica con historial)."""
    def body(repo: ComisionesRepository):
        df = repo.read_sql(ASIGNACION_STAR_SQL, [asignacion_id] + repo._scope)
        if df.empty:
            return DE._Rollback(None)
        obs_actual = R.limpiar_texto_tabla(df.iloc[0].get("observaciones", ""))
        obs_extra = R.limpiar_texto_tabla(observaciones_extra)
        obs_final = obs_actual
        if obs_extra:
            obs_final = (obs_final + " | " if obs_final else "") + obs_extra
        repo._mutate(UPDATE_ESTADO_ASIGNACION_SQL, [estado, obs_final, asignacion_id] + repo._scope)
        row = df.iloc[0].to_dict()
        row["estado"] = estado
        row["observaciones"] = obs_final
        return row
    return u.commit(body)


def eliminar_asignacion_docente_comision(u: Unidad, asignacion_id) -> None:
    """v95 l. 30444 (un COMMIT)."""
    def body(repo: ComisionesRepository):
        repo._mutate(DELETE_FRANJAS_ASIGNACION_SQL, [int(asignacion_id)] + repo._scope)
        repo._mutate(DELETE_ASIGNACION_SQL, [int(asignacion_id)] + repo._scope)
    u.commit(body)


# ------------------------------------------------------------------------------------------ inscriptos
def guardar_inscriptos_asignatura_periodo_v248(u: Unidad, periodo_id, materia_id, cantidad, opcion_curricular_id=0,
                                               observaciones="", fecha_actualizacion=None, cantidad_final=None,
                                               fecha_actualizacion_final=None, actualizar_final=False) -> None:
    """l. 53751: upsert por periodo + asignatura/codigo (+ opcion).  Sin compuerta de periodo."""
    pid = int(periodo_id)
    mid = u.lector.materia_representante_inscriptos_v123(materia_id)
    if mid is None:
        raise ValueError("No se pudo identificar la asignatura/código.")
    oid = R.opcion_id_inscriptos_v248(opcion_curricular_id)
    cant = max(int(cantidad or 0), 0)
    final_norm = None if cantidad_final is None or str(cantidad_final).strip() == "" else max(int(cantidad_final), 0)
    fecha_i = str(fecha_actualizacion or u.today)
    fecha_f = str(fecha_actualizacion_final or u.today) if final_norm is not None else None

    def body(repo: ComisionesRepository):
        existente = repo._first(INSCRIPTO_EXISTENTE_SQL, [pid, int(mid), oid] + repo._scope)
        if existente:
            vals = list(existente.values())
            final_guardado, fecha_final_guardada = vals[1], vals[2]
            final_a = final_norm if actualizar_final else final_guardado
            fecha_final_a = fecha_f if actualizar_final else fecha_final_guardada
            repo._mutate(UPDATE_INSCRIPTO_SQL, [cant, final_a, fecha_i, fecha_final_a, str(observaciones or "").strip(),
                                                int(vals[0])] + repo._scope)
        else:
            repo._insert_id(INSERT_INSCRIPTO_SQL, [pid, int(mid), oid, cant, final_norm, fecha_i, fecha_f,
                                                   str(observaciones or "").strip()] + repo._scope)
    u.commit(body)


# ------------------------------------------------------------------------------------------ sedes (get_auth_conn)
def _limpio(v) -> str:
    return " ".join(str(v or "").strip().split())


def guardar_sede_institucional(u: Unidad, nombre, direccion, localidad, observaciones="", estado="Activa") -> None:
    """l. 18204."""
    inst_id = u.inst
    nombre, direccion, localidad = _limpio(nombre), _limpio(direccion), _limpio(localidad)
    if inst_id is None:
        raise ValueError("No se pudo identificar la institución actual.")
    if not nombre:
        raise ValueError("Indicá el nombre de la sede.")
    if not direccion:
        raise ValueError("Indicá la calle y numeración de la sede.")
    if not localidad:
        raise ValueError("Indicá la localidad de la sede.")
    existente = u.read(lambda repo: repo.read_sql(SEDE_POR_NOMBRE_SQL, [int(inst_id), nombre]))
    if not existente.empty:
        raise ValueError("Ya existe una sede con ese nombre en la institución.")
    ahora = str(u.now)
    u.commit(lambda repo: repo._mutate(INSERT_SEDE_SQL, [int(inst_id), nombre, direccion, localidad, estado,
                                                         str(observaciones or "").strip(), ahora, ahora]))


def actualizar_sede_institucional(u: Unidad, sede_id, nombre, direccion, localidad, estado="Activa",
                                  observaciones="") -> None:
    """l. 18233."""
    inst_id = u.inst
    nombre, direccion, localidad = _limpio(nombre), _limpio(direccion), _limpio(localidad)
    if inst_id is None:
        raise ValueError("No se pudo identificar la institución actual.")
    if not nombre or not direccion or not localidad:
        raise ValueError("Completá nombre, calle/dirección y localidad.")

    def body(repo: ComisionesRepository):
        duplicada = repo.read_sql(SEDE_DUPLICADA_SQL, [int(inst_id), nombre, int(sede_id)])
        if not duplicada.empty:
            raise ValueError("Ya existe otra sede con ese nombre en la institución.")
        repo._mutate(UPDATE_SEDE_SQL, [nombre, direccion, localidad, estado, str(observaciones or "").strip(), str(u.now),
                                       int(sede_id), int(inst_id)])
    u.commit(body)


def eliminar_sede_institucional(u: Unidad, sede_id) -> None:
    """l. 18264."""
    inst_id = u.inst
    if inst_id is None:
        return
    u.commit(lambda repo: repo._mutate(DELETE_SEDE_SQL, [int(sede_id), int(inst_id)]))


# ------------------------------------------------------------------------------------------ movimientos
def registrar_movimiento(u: Unidad, tipo, cuil, nombre, detalle, observaciones="", periodo_id=None, horas_variacion=0,
                         fecha_movimiento=None) -> int:
    return DE.registrar_movimiento(u, tipo, cuil, nombre, detalle, observaciones, periodo_id,
                                   horas_variacion=horas_variacion, fecha_movimiento=fecha_movimiento)
