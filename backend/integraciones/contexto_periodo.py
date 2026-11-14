"""E4-01 — aviso global "🕰️ Contexto histórico activo" (D-AN9; B13-FIX02 l. 59263-59273).

Certificado: antes del ruteo de modulos (todas las paginas autenticadas), con la conexion ``tenant`` de la sesion:
``get_periodo_abierto()`` (l. 4724); si existe y ``es_periodo_historico_contexto_v182(id)`` (l. 39224, con
``_info_periodo_analisis_v169`` l. 36408 y ``get_ultimo_periodo`` de ``extracted_batch03``) es verdadero, muestra un
``st.warning`` con el texto de ``texto_aviso``.  Sin periodo abierto, o abierto no historico, no hay aviso.

Composicion (sin reglas nuevas):
- ambito con departamento: lecturas propietarias ``periodos.repository.PeriodosRepository`` (abierto, ultimo, por id);
- ambito institucional (superadmin o coordinador sin departamento; B12B les da scope institucional con departamento
  opcional): el inyector certificado (``_pg_scope_select_template_v193`` l. 42873 con ``dep_id`` None) filtra
  ``periodos`` solo por institucion.  Periodos no tiene ese lector, por eso las tres consultas institucionales viven
  aca, con el mismo SQL certificado;
- regla: ``designaciones.rules.es_periodo_historico`` (port de v182, ya validado).
Ambito no verificable (B12B -> ``SCOPE_DENIED_ID``: 0 filas) -> sin aviso.  Solo lectura: transaccion READ ONLY, sin
writers, sin B12H, sin locks.  Ningun valor del cliente interviene (el ambito sale de la sesion revalidada).
"""
from __future__ import annotations

import logging
from contextlib import AbstractContextManager
from typing import Callable, Optional

from psycopg import Connection
from psycopg.rows import dict_row

from auth.service import AuthService, SessionRecord
from designaciones.rules import es_periodo_historico
from periodos.repository import PeriodosRepository
from periodos.service import MSG_DB_READ

log = logging.getLogger("deptit_next.integraciones")

_COLS = "id, nombre, anio, semestre, fecha_inicio, fecha_fin, estado, observaciones"
OPEN_INST_SQL = (f"SELECT {_COLS} FROM periodos WHERE estado = 'Abierto' AND institucion_id = %s "
                 "ORDER BY id DESC LIMIT 1")
LAST_INST_SQL = f"SELECT {_COLS} FROM periodos WHERE institucion_id = %s ORDER BY anio DESC, semestre DESC, id DESC LIMIT 1"
BY_ID_INST_SQL = ("SELECT id, nombre, anio, semestre, fecha_inicio, fecha_fin, estado FROM periodos "
                  "WHERE id = %s AND institucion_id = %s LIMIT 1")


class ContextoError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def texto_aviso(abierto: dict, ultimo: Optional[dict]) -> str:
    """Texto literal del ``st.warning`` certificado (l. 59267-59273), con las mismas expresiones ``.get``."""
    return (
        f"🕰️ **Contexto histórico activo: {abierto.get('nombre','')}** "
        f"({abierto.get('fecha_inicio','')} al {abierto.get('fecha_fin','')}). "
        "Las vistas periodizadas muestran la foto exacta de cómo estaba el sistema al finalizar el último día de este período. "
        + (f"El último período cronológico sigue siendo **{ultimo.get('nombre','')}**. " if ultimo else "")
        + "La operatoria académica normal de Comisiones permanece protegida/bloqueada para el período anterior; solo siguen disponibles las correcciones históricas ya previstas por la app."
    )


def _first(conn: Connection, sql: str, params: list) -> Optional[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def lecturas(conn: Connection, institution_id: int, department_id: Optional[int]) -> tuple:
    """(abierto, ultimo, info del abierto) con el ambito de la sesion."""
    if department_id is not None:
        repo = PeriodosRepository(conn, institution_id, department_id)
        abierto, ultimo = repo.open_period(), repo.last_period()
        info = repo.by_id(int(abierto["id"])) if abierto else None
        return abierto, ultimo, info
    inst = int(institution_id)
    abierto, ultimo = _first(conn, OPEN_INST_SQL, [inst]), _first(conn, LAST_INST_SQL, [inst])
    info = _first(conn, BY_ID_INST_SQL, [int(abierto["id"]), inst]) if abierto else None
    return abierto, ultimo, info


def aviso(abierto: Optional[dict], ultimo: Optional[dict], info: Optional[dict]) -> Optional[str]:
    """Condicion certificada: ``if abierto and es_periodo_historico_contexto_v182(abierto["id"])``."""
    if not abierto or not es_periodo_historico(info, ultimo, abierto):
        return None
    return texto_aviso(abierto, ultimo)


class ContextoPeriodoService:
    def __init__(self, pool, auth: AuthService, *,
                 transaction: Optional[Callable[[], AbstractContextManager[Connection]]] = None):
        self.auth = auth
        self._transaction = transaction or (lambda: pool.connection(timeout=5))

    def aviso(self, record: SessionRecord) -> dict:
        self.auth.apply_default_context(record)
        resolution = self.auth.resolve_scope(record)
        if resolution.reason is not None or resolution.institution is None:
            return {"aviso": None}
        inst = int(resolution.institution["id"])
        dep = int(resolution.department["id"]) if resolution.department is not None else None
        try:
            with self._transaction() as conn:
                conn.execute("SET TRANSACTION READ ONLY")
                texto = aviso(*lecturas(conn, inst, dep))
        except Exception as exc:
            log.error("contexto_periodo: lectura fallida: %s", type(exc).__name__)
            raise ContextoError(503, "DB_READ", MSG_DB_READ) from None
        return {"aviso": None if texto is None else {"texto": texto}}


__all__ = ["ContextoPeriodoService", "ContextoError", "aviso", "lecturas", "texto_aviso"]
