"""Writers certificados de Actividades Especiales (entry l. 32099-32160) con sus COMMITs reales.

Cada writer certificado abre su ``get_conn()`` y hace UN COMMIT (``Unidad.commit``).  Se replica sin "mejoras" (G3):
- ``guardar_actividad_especial`` l. 32099: titulo normalizado (vacio -> ``ValueError``), INSERT 'Activa' con
  ``fecha_carga = str(datetime.now())``.
- ``asignar_docente_actividad_especial`` l. 32115: rol normalizado (vacio -> ``ValueError``); periodo de la actividad
  (ambito del departamento; inexistente -> ``ValueError``); duplicado Activo por CUIL LITERAL -> ``ValueError``; INSERT.
  Lecturas e INSERT en la misma conexion: un COMMIT.
- ``actualizar_actividad_especial`` l. 32157: UPDATE sin validar ``rowcount`` ni titulo vacio.
- ``eliminar_asignacion_actividad_especial`` l. 32149 y ``eliminar_actividad_especial`` l. 32153 (2 DELETE, 1 COMMIT):
  sin validar ``rowcount``.
Ningun writer registra movimientos, toma locks ni compensa (G3/G4).  Excluidos (G7): ``asegurar_esquema_v95``, indices
v199, ramas SQLite y envoltorios de cache.
"""

from __future__ import annotations

from typing import Any, Callable

import audit
from designaciones import escrituras as DE

from . import rules as AR
from .repository import ActividadesRepository

W_GUARDAR = "guardar_actividad_especial"
W_ACTUALIZAR = "actualizar_actividad_especial"
W_ASIGNAR = "asignar_docente_actividad_especial"
W_ELIMINAR = "eliminar_actividad_especial"
W_ELIMINAR_ASIGNACION = "eliminar_asignacion_actividad_especial"

AuditoriaFallida = DE.AuditoriaFallida


class Unidad(DE.Unidad):
    """La ``Unidad`` B12H de Designaciones con el repositorio de Actividades Especiales (mismo acoplamiento de COMMITs)."""

    def read(self, fn: Callable[[ActividadesRepository], Any]) -> Any:
        with self._transaction() as conn:
            return fn(ActividadesRepository(conn, self.inst, self.dep))

    def commit(self, fn: Callable[[ActividadesRepository], Any]) -> Any:
        if self.audit_failed:
            raise AuditoriaFallida("AUDIT_FAILED_EARLIER")
        repo = None
        try:
            with self._transaction() as conn:
                repo = ActividadesRepository(conn, self.inst, self.dep)
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
        return result


def _fecha_carga(u: Unidad) -> str:
    """``str(datetime.now())`` del certificado (fecha y hora local con microsegundos)."""
    return str(u.now)


def guardar_actividad_especial(u: Unidad, periodo_id, titulo, descripcion="", observaciones=""):
    titulo = AR.normalizar_espacios(titulo)
    if not titulo:
        raise ValueError("Ingresá el título de la actividad.")
    return u.commit(lambda repo: repo.insert_actividad(int(periodo_id), titulo, descripcion, observaciones,
                                                       _fecha_carga(u)))


def asignar_docente_actividad_especial(u: Unidad, actividad_id, cuil, rol, observaciones=""):
    rol = AR.normalizar_espacios(rol)
    if not rol:
        raise ValueError("Indicá el rol del docente en la actividad.")

    def body(repo: ActividadesRepository):
        pid = repo.periodo_de_actividad(int(actividad_id))
        if pid is None:
            raise ValueError("No se encontró la actividad.")
        if repo.participacion_activa(int(actividad_id), str(cuil)):
            raise ValueError("El docente ya está asignado a esta actividad.")
        return repo.insert_participacion(int(actividad_id), pid, str(cuil), rol, observaciones, _fecha_carga(u))

    return u.commit(body)


def eliminar_asignacion_actividad_especial(u: Unidad, asignacion_id) -> None:
    u.commit(lambda repo: repo.delete_participacion(int(asignacion_id)))


def eliminar_actividad_especial(u: Unidad, actividad_id) -> None:
    u.commit(lambda repo: repo.delete_actividad(int(actividad_id)))


def actualizar_actividad_especial(u: Unidad, actividad_id, titulo, descripcion, estado, observaciones) -> None:
    u.commit(lambda repo: repo.update_actividad(int(actividad_id), AR.normalizar_espacios(titulo), descripcion, estado,
                                                observaciones))


__all__ = [n for n in dir() if n.startswith("W_")] + ["Unidad", "AuditoriaFallida"]
