"""E4-02 / E4-03 — Docentes: pestañas "📋 Plantel del período abierto" y "👥 Equipos docentes"; estado operativo
historico de la base maestra.

Certificado (B13-FIX02):
- pestaña ``tab1`` (entry l. 59813-59925; el piloto v304 queda excluido: apagado por defecto): selector "Seleccioná el
  período" con ``get_periodos()`` (opciones ``{nombre: id}``, por defecto el periodo abierto o el primero), aviso
  informativo, ``get_plantel_periodo(id)`` (efectiva v191 -> v183 l. 40051) en ``st.dataframe`` y el conteo de docentes
  con designaciones activas;
- base maestra: ``get_docentes`` v183 (l. 40115) etiqueta ``estado_periodo_abierto`` con el plantel al cierre del
  periodo abierto historico (puerto ``plantel_cuiles`` de ``DocentesService``);
- pestaña ``tab7`` "👥 Equipos docentes" (E4-03, l. 60828-60844): selector "Seleccioná el período" (mismas reglas que
  Plantel), ``get_equipos_docentes_periodo(id)`` (l. 24248; el cache v199 no cambia el resultado) en ``st.dataframe`` y
  el conteo de materias.

Composicion (D-E4-01): el plantel es una lectura de Comisiones (``comisiones.lecturas.Lector.plantel_periodo``, ya
validada contra el certificado) y Docentes no puede importar Comisiones (Comisiones importa Docentes).  Ambito y permiso
salen del contrato publico de Docentes (``DocentesService.scope``, ``ACTION_READ``); los periodos, del repositorio de
Periodos.  Equipos compone ``Lector.comisiones`` (``get_comisiones`` efectiva) y ``Lector.materia_comision`` con la
lectura de asignaciones propia de la funcion certificada (``ASIGNACIONES_EQUIPOS_SQL``, mismo texto que ejecuta el
certificado tras el inyector de tenant).  Solo lectura: transaccion READ ONLY, sin writers, sin B12H, sin locks.
"""
from __future__ import annotations

import logging
from contextlib import AbstractContextManager
from datetime import date
from typing import Any, Callable, Optional

import pandas as pd
from psycopg import Connection

from analisis.pagina import tabla
from auth import policy
from auth.service import AuthService, SessionRecord
from comisiones.lecturas import Lector
from comisiones.repository import ComisionesRepository
from comisiones.rules import (clave_materia_conceptual_v137, clave_materia_unica_codigo_nombre,
                              es_materia_optativa_electiva, limpiar_texto_tabla, normalizar_clave)
from docentes.service import ACTION_READ, DocentesError, DocentesService
from periodos.repository import PeriodosRepository
from periodos.service import MSG_DB_READ, denial_message

log = logging.getLogger("deptit_next.integraciones")

MSG_SIN_PERIODOS = "Todavía no hay períodos registrados. Creá uno en el módulo Períodos para ver el plantel."
MSG_PLANTEL_VACIO = "No hay docentes con designaciones registradas en el período seleccionado."
MSG_PERIODO_INVALIDO = "El período seleccionado no existe en el departamento."
MSG_EQUIPOS_SIN_PERIODOS = "Todavía no hay períodos registrados."
MSG_EQUIPOS_INFO = ("Muestra los docentes que tiene cada materia en el período seleccionado, agrupando todas sus "
                    "comisiones y evitando repetir docentes.")
MSG_EQUIPOS_VACIO = "No hay comisiones/equipos docentes registrados para ese período."

COLUMNAS_EQUIPOS = [
    "periodo", "codigo_materia", "asignatura", "materia_especifica", "carrera", "escuela",
    "plan_version", "comisiones", "turnos", "modalidades", "equipo_docente",
    "cantidad_comisiones", "cantidad_docentes", "horas_docentes_asignadas",
]
# SELECT de ``get_equipos_docentes_periodo`` (l. 24265-24276) tal como lo ejecuta el certificado tras ``_pg_scope_select``
# (predicados de tenant en cada alias).  SIN ``ORDER BY``, como el certificado: el orden fisico de las filas define el
# orden de ``equipo_docente`` y el rol que se muestra de un docente repetido en varias comisiones (anomalia certificada,
# ver DOCENTES_E4_03_INTEGRATION.md).  No se corrige.
ASIGNACIONES_EQUIPOS_SQL = (
    "SELECT a.comision_id, a.cuil, CASE "
    "WHEN doc.apellido IS NOT NULL AND doc.nombres IS NOT NULL THEN doc.apellido || ', ' || doc.nombres "
    "WHEN doc.nombre IS NOT NULL THEN doc.nombre "
    "WHEN a.cuil IS NOT NULL THEN a.cuil ELSE '' END AS docente, "
    "a.rol, COALESCE(a.horas_asignadas, 0) AS horas_asignadas "
    "FROM asignaciones_docentes_comision a "
    "LEFT JOIN docentes doc ON (doc.cuil = a.cuil) AND (doc.institucion_id = %s) AND (doc.departamento_id = %s) "
    "LEFT JOIN comisiones co ON (co.id = a.comision_id) AND (co.institucion_id = %s) AND (co.departamento_id = %s) "
    "WHERE co.periodo_id = %s AND (a.institucion_id = %s) AND (a.departamento_id = %s)")


def texto_info(periodo_nombre: Any) -> str:
    return (f"Este plantel se calcula desde **todas las designaciones registradas** del período "
            f"**{periodo_nombre}**. La columna de estado operativo indica si el docente sigue activo "
            f"o si ya quedó finalizado / sin designación activa en ese período.")


def total_activos(df: pd.DataFrame) -> int:
    """Conteo certificado (l. 59917-59920): designaciones activas > 0, o el estado operativo si falta la columna."""
    if "designaciones_activas" in df.columns:
        return int((pd.to_numeric(df["designaciones_activas"], errors="coerce").fillna(0) > 0).sum())
    return int((df["estado_operativo_periodo"] == "Activo en el período").sum())


def opciones_periodos(periodos: list[dict]) -> dict:
    """``{row["nombre"]: row["id"] for _, row in df_periodos.iterrows()}``: orden de primera aparicion, id del ultimo."""
    out: dict = {}
    for p in periodos:
        out[p.get("nombre")] = int(p["id"])
    return out


def _limpio(v) -> str:
    if v is None:
        return ""
    try:
        if pd.isna(v):
            return ""
    except Exception:
        pass
    t = str(v).strip()
    return "" if t.lower() in ["nan", "none", "nat"] else t


def _unir(vals) -> str:
    out: list = []
    for v in vals:
        t = _limpio(v)
        if t and t not in out:
            out.append(t)
    return " | ".join(out)


def equipos_docentes_periodo(lector: Lector, periodo_id: int) -> pd.DataFrame:
    """``get_equipos_docentes_periodo`` (l. 24248): una fila por dictado real (codigo + nombre; las optativas/electivas
    por opcion curricular), con comisiones, turnos, modalidades y el equipo docente sin repetir."""
    df_com = lector.comisiones(periodo_id=periodo_id, solo_activas=False)
    if df_com is None or df_com.empty:
        return pd.DataFrame(columns=COLUMNAS_EQUIPOS)
    repo = lector.repo
    df_asig = repo.read_sql(ASIGNACIONES_EQUIPOS_SQL,
                            [repo.inst, repo.dep] * 2 + [int(periodo_id), repo.inst, repo.dep])
    if df_asig.empty:
        base = df_com.copy()
        base["cuil"] = ""
        base["docente"] = ""
        base["rol"] = ""
        base["horas_asignadas"] = 0.0
    else:
        base = df_com.merge(df_asig, left_on="id", right_on="comision_id", how="left")

    def clave_dictado(r):
        oid = r.get("opcion_curricular_id")
        try:
            if oid is not None and not pd.isna(oid):
                return f"OP:{int(oid)}"
        except Exception:
            pass
        info_grupo = lector.materia_comision(r.get("materia_id")) if r.get("materia_id") is not None else {}
        clave_formal = (
            limpiar_texto_tabla((info_grupo or {}).get("_clave_unica", ""))
            or clave_materia_conceptual_v137(info_grupo or r)
            or clave_materia_unica_codigo_nombre(r.get("codigo_materia", ""), r.get("asignatura", ""))
        )
        if es_materia_optativa_electiva(r.get("codigo_materia", ""), r.get("asignatura", "")):
            esp = normalizar_clave(r.get("materia_especifica", ""))
            if esp:
                return f"LEGACY:{clave_formal}:{esp}"
        return f"MAT:{clave_formal}"

    base["_clave_dictado"] = base.apply(clave_dictado, axis=1)
    registros = []
    for _, g in base.groupby("_clave_dictado", dropna=False, sort=False):
        primero = g.iloc[0]
        comisiones = []
        for _, r in g.drop_duplicates(subset=["id"], keep="first").iterrows():
            com = _limpio(r.get("nombre_comision"))
            extras = [x for x in [_limpio(r.get("turno")), _limpio(r.get("modalidad"))] if x]
            et = com
            if extras:
                et = f"{com} ({' / '.join(extras)})" if com else " / ".join(extras)
            if et and et not in comisiones:
                comisiones.append(et)
        docentes = []
        vistos = set()
        for _, r in g.iterrows():
            cuil, doc, rol = _limpio(r.get("cuil")), _limpio(r.get("docente")), _limpio(r.get("rol"))
            if not cuil and not doc:
                continue
            k = cuil or doc.upper()
            if k in vistos:
                continue
            vistos.add(k)
            et = doc or cuil
            if rol:
                et = f"{et} ({rol})"
            docentes.append(et)
        registros.append({
            "periodo": _limpio(primero.get("periodo")),
            "codigo_materia": _limpio(primero.get("codigo_materia")),
            "asignatura": _limpio(primero.get("asignatura")),
            "materia_especifica": _limpio(primero.get("materia_especifica")),
            "carrera": _unir(g["carrera"]), "escuela": _unir(g["escuela"]), "plan_version": _unir(g["plan_version"]),
            "comisiones": " | ".join(comisiones), "turnos": _unir(g["turno"]), "modalidades": _unir(g["modalidad"]),
            "equipo_docente": " | ".join(docentes), "cantidad_comisiones": len(comisiones),
            "cantidad_docentes": len(docentes),
            "horas_docentes_asignadas": float(pd.to_numeric(g["horas_asignadas"], errors="coerce").fillna(0).sum()),
        })
    out = pd.DataFrame(registros, columns=COLUMNAS_EQUIPOS)
    return out.sort_values(["escuela", "carrera", "codigo_materia", "asignatura", "materia_especifica"],
                           kind="stable").reset_index(drop=True)


class DocentesPeriodoService:
    def __init__(self, pool, auth: AuthService, docentes: DocentesService, *,
                 today: Callable[[], date] = date.today,
                 transaction: Optional[Callable[[], AbstractContextManager[Connection]]] = None):
        self.auth = auth
        self.docentes = docentes
        self.today = today
        self._transaction = transaction or (lambda: pool.connection(timeout=5))

    # ------------------------------------------------------------------ puerto de Docentes (base maestra v183)
    def plantel_cuiles(self, conn: Connection, institution_id: int, department_id: int, periodo_id: int) -> list:
        """CUIL de ``get_plantel_periodo(periodo_id)`` en la conexion (y transaccion) del llamador."""
        df = Lector(ComisionesRepository(conn, institution_id, department_id), self.today()).plantel_periodo(periodo_id)
        if not isinstance(df, pd.DataFrame) or df.empty or "cuil" not in df.columns:
            return []
        return df["cuil"].fillna("").astype(str).tolist()

    # ------------------------------------------------------------------ selector de periodo (Plantel y Equipos)
    def _leer_periodo(self, record: SessionRecord, periodo_id: Any, leer: Callable[[Lector, int], Any]):
        """Ambito y permiso de Docentes; ``{nombre: id}`` de ``get_periodos``; por defecto el abierto o el primero.
        Devuelve ``None`` sin periodos, o ``(opciones, seleccionado, leer(lector, id))``."""
        scope = self.docentes.scope(record)
        decision = policy.decide(policy.actor_from_session(record.user, record.scope), ACTION_READ)
        if not decision.allowed:
            raise DocentesError(403, "DENIED", denial_message(decision, ACTION_READ))
        if periodo_id is not None and (isinstance(periodo_id, bool) or not isinstance(periodo_id, int)):
            raise DocentesError(422, "VALIDATION", MSG_PERIODO_INVALIDO)
        try:
            with self._transaction() as conn:
                conn.execute("SET TRANSACTION READ ONLY")
                prepo = PeriodosRepository(conn, scope.institution_id, scope.department_id)
                periodos, abierto = prepo.list(), prepo.open_period()
                if not periodos:
                    return None
                opciones = opciones_periodos(periodos)
                nombres = list(opciones)
                if periodo_id is None:
                    sel = abierto["nombre"] if abierto else nombres[0]
                else:
                    sel = next((n for n in nombres if opciones[n] == periodo_id), None)
                    if sel is None:
                        raise DocentesError(404, "NOT_FOUND", MSG_PERIODO_INVALIDO)
                lector = Lector(ComisionesRepository(conn, scope.institution_id, scope.department_id), self.today())
                return opciones, sel, leer(lector, opciones[sel])
        except DocentesError:
            raise
        except Exception as exc:
            log.error("docentes_periodo: lectura fallida: %s", type(exc).__name__)
            raise DocentesError(503, "DB_READ", MSG_DB_READ) from None

    @staticmethod
    def _selector(opciones: dict, sel) -> dict:
        return {"periodos": [{"id": v, "nombre": n} for n, v in opciones.items()],
                "seleccionado": {"id": opciones[sel], "nombre": sel}, "sin_periodos": None}

    # ------------------------------------------------------------------ pestaña Plantel
    def plantel(self, record: SessionRecord, periodo_id: Any = None) -> dict:
        leido = self._leer_periodo(record, periodo_id, lambda lector, pid: lector.plantel_periodo(pid))
        if leido is None:
            return {"periodos": [], "seleccionado": None, "sin_periodos": MSG_SIN_PERIODOS}
        opciones, sel, df = leido
        vacio = not isinstance(df, pd.DataFrame) or df.empty
        return {
            **self._selector(opciones, sel),
            "info": texto_info(sel),
            "vacio": MSG_PLANTEL_VACIO if vacio else None,
            "tabla": None if vacio else tabla(df),
            "total_activos": None if vacio else total_activos(df),
        }

    # ------------------------------------------------------------------ pestaña Equipos docentes (E4-03)
    def equipos(self, record: SessionRecord, periodo_id: Any = None) -> dict:
        leido = self._leer_periodo(record, periodo_id, equipos_docentes_periodo)
        if leido is None:
            return {"info": MSG_EQUIPOS_INFO, "periodos": [], "seleccionado": None,
                    "sin_periodos": MSG_EQUIPOS_SIN_PERIODOS}
        opciones, sel, df = leido
        vacio = df.empty
        return {
            "info": MSG_EQUIPOS_INFO,
            **self._selector(opciones, sel),
            "vacio": MSG_EQUIPOS_VACIO if vacio else None,
            "tabla": None if vacio else tabla(df),
            "total_materias": None if vacio else len(df),
        }


__all__ = ["DocentesPeriodoService", "equipos_docentes_periodo", "opciones_periodos", "texto_info", "total_activos"]
