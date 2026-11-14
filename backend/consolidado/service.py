"""Servicio de Consolidado institucional (B13-FIX02, ruteo l. 59795 -> ``render_consolidado_institucional`` v242
l. 53184).  100 % lectura.

Decisiones D-AO1..D-AO6 (docs/consolidado_institucional_analysis.md §AR):
- D-AO1: composicion de lecturas NEXT ya certificadas (``lecturas.py``); sin motor vendorizado.
- D-AO2: columnas funcionales del certificado (CUIL, nombre, email, telefono, texto de actos...) solo donde el
  Consolidado certificado las muestra; nunca en logs, errores ni nombres de archivo.  Sin ``sqlite_id``/``source_db``.
- D-AO3: la lectura inicial trae titulo, KPIs, control, resumen y el catalogo de tablas; cada tabla se pide al
  seleccionarla (clave de allowlist + texto de busqueda); busqueda, CSV y Excel se resuelven en el backend.
- D-AO4: Excel global (``mostrar_boton_descarga_excel_tabla`` v200 l. 46790) bajo "Resumen por departamento" y bajo la
  tabla elegida (VISTA FILTRADA); el CSV exporta la tabla COMPLETA (asimetria certificada, congelada por tests).
- D-AO5: la institucion sale SIEMPRE del ambito verificado de la sesion (``AuthService.resolve_scope``); sin
  institucion valida -> fail-closed (409), nunca una institucion por defecto.
- D-AO6: anomalias certificadas replicadas (periodo por departamento, doble conteo, funciones no docentes, tablas
  crudas sin filtro temporal, CSV completo vs Excel filtrado).
Acceso: rol de sesion en {coordinador_institucional, superadmin} (``user["rol"]`` como el render: la solo lectura
comercial queda fuera) y modulo visible (``policy.visible_modules``).  Sin dominio B10 propio.
"""
from __future__ import annotations

import logging
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable, Optional

import pandas as pd
from psycopg import Connection

from analisis.pagina import metrica, tabla
from auth import policy
from auth.service import AuthService, SessionRecord
from inicio.service import XLSX, excel_bytes
from periodos.service import MSG_DB_READ, scope_message

from . import lecturas as L

log = logging.getLogger("deptit_next.consolidado")

MODULO = "consolidado"
ROLES = (policy.ROLE_COORDINADOR, policy.ROLE_SUPERADMIN)
TITULO = "🏛️ Consolidado institucional"
MSG_ROL = "Esta vista es para coordinación institucional o superadmin."
MSG_SIN_DATOS = "Sin datos para consolidar."
MSG_SIN_CRITERIO = "No hay datos para el criterio seleccionado."
MSG_SIN_COINCIDENCIAS = "No se encontraron registros que coincidan con la búsqueda."
MSG_TABLA = "La tabla solicitada no está disponible."
CAPTION_FUENTE = (
    "Fuente única: **Designaciones del período** parte exactamente del listado departamental y "
    "cuenta únicamente las filas con estado **Activa** dentro del período actual. "
    "Para **Docentes del período**, se parte del mismo Plantel por período y se cuentan únicamente "
    "las personas con al menos una designación activa (designaciones_activas > 0). "
    "Luego, para el total institucional, esos docentes activos se deduplican por CUIL."
)
CAPTION_CONTROL = (
    "La segunda cifra suma únicamente los docentes con designación activa de cada Plantel por período. "
    "Las designaciones sumadas también son solo las que tienen estado Activa en ese período. "
    "La primera vuelve a contar esas mismas personas después de normalizar el CUIL, por eso un docente compartido "
    "queda una sola vez institucionalmente."
)
BUSCADOR = {"label": "🔎 Buscar en esta tabla",
            "placeholder": "Buscar por nombre, CUIL, cargo, materia, período, estado, departamento...",
            "help": "Busca el texto ingresado en todas las columnas de la tabla seleccionada."}
CSV_LABEL = "Descargar CSV consolidado"
MAX_BUSQUEDA = 200
CSV = "text/csv"


class ConsolidadoError(Exception):
    def __init__(self, status: int, code: str, message: str, tone: str = "error"):
        super().__init__(message)
        self.status, self.code, self.message, self.tone = status, code, message, tone


@dataclass(frozen=True)
class Descarga:
    contenido: bytes
    nombre: str
    media_type: str


def _named(row: Optional[dict]) -> Optional[dict]:
    return None if row is None else {"id": int(row["id"]), "nombre": row.get("nombre")}


def clave_tabla(valor: Any) -> str:
    """Clave publica de la allowlist (nunca un nombre fisico ni SQL del cliente)."""
    if not isinstance(valor, str) or valor not in L.TABLAS:
        raise ConsolidadoError(422, "TABLA_INVALIDA", MSG_TABLA)
    return valor


def texto_busqueda(valor: Any) -> str:
    if valor is None:
        return ""
    if not isinstance(valor, str):
        raise ConsolidadoError(422, "INVALID", "El texto de búsqueda no es válido.")
    return valor[:MAX_BUSQUEDA]


def kpis(resumen: pd.DataFrame, cuiles: set) -> dict:
    """Metricas y control de consistencia (l. 53202-53233)."""
    docentes_inst = int(len(cuiles))
    suma_docentes_dep = int(pd.to_numeric(resumen.get("docentes"), errors="coerce").fillna(0).sum())
    designaciones_inst = int(pd.to_numeric(resumen.get("designaciones"), errors="coerce").fillna(0).sum())
    horas_inst = float(pd.to_numeric(resumen.get("horas_designadas"), errors="coerce").fillna(0).sum())
    return {
        "metricas": [metrica("Departamentos", len(resumen)),
                     metrica("Docentes únicos por CUIL", docentes_inst),
                     metrica("Designaciones del período", designaciones_inst),
                     metrica("Horas de las designaciones", round(horas_inst, 2))],
        "caption": CAPTION_FUENTE,
        "control": {"titulo": "🔎 Control de consistencia", "abierto": True,
                    "metricas": [metrica("Docentes únicos por CUIL", docentes_inst),
                                 metrica("Suma de docentes de los departamentos", suma_docentes_dep),
                                 metrica("Designaciones sumadas", designaciones_inst),
                                 metrica("Docentes compartidos · repeticiones",
                                         max(suma_docentes_dep - docentes_inst, 0))],
                    "caption": CAPTION_CONTROL},
    }


class ConsolidadoService:
    def __init__(self, pool, auth: AuthService, *, today: Callable[[], date] = date.today,
                 now: Callable[[], datetime] = datetime.now,
                 transaction: Optional[Callable[[], AbstractContextManager[Connection]]] = None):
        self.auth = auth
        self.today = today
        self.now = now
        self._transaction = transaction or (lambda: pool.connection(timeout=5))

    # ------------------------------------------------------------------ acceso y ambito (D-AO5)
    def scope(self, record: SessionRecord) -> dict:
        self.auth.apply_default_context(record)
        user, session_scope = record.user, record.scope
        role = policy.normalize_role(user.get("rol"))
        visible = policy.visible_modules(role, session_scope.get(policy.DEPARTMENT_SCOPE_KEY))
        if role not in ROLES or not any(m[0] == MODULO for m in visible):
            raise ConsolidadoError(403, "DENIED", MSG_ROL)
        resolution = self.auth.resolve_scope(record)
        if resolution.institution is None or resolution.reason is not None:
            raise ConsolidadoError(409, "SCOPE_NOT_VERIFIED", scope_message(resolution))
        return resolution.institution

    def _leer(self, fn: Callable[[Connection], Any]) -> Any:
        """Una transaccion READ ONLY por request (cualquier sentencia mutante falla en la base)."""
        try:
            with self._transaction() as conn:
                conn.execute("SET TRANSACTION READ ONLY")
                return fn(conn)
        except ConsolidadoError:
            raise
        except Exception as exc:
            log.error("consolidado: lectura fallida: %s", type(exc).__name__)
            raise ConsolidadoError(503, "DB_READ", MSG_DB_READ) from None

    def _dft(self, conn: Connection, inst: int, clave: str) -> pd.DataFrame:
        """``dft`` del render (l. 53262-53269): listados contados para docentes/designaciones; resto crudo."""
        if clave in ("docentes", "designaciones"):
            resumen, docentes, contadas, _ = L.consolidado(conn, inst, self.today())
            dft = docentes.copy() if clave == "docentes" else L.designaciones_enriquecidas(
                conn, inst, resumen, contadas, self.today())
        else:
            dft = L.tabla_cruda(conn, inst, clave)
        return dft if dft is None or dft.empty else L.ordenar(dft)

    # ------------------------------------------------------------------ lectura inicial
    def overview(self, record: SessionRecord) -> dict:
        inst = self.scope(record)
        out = {"titulo": TITULO, "contexto": {"institucion": _named(inst)}}
        resumen, _, _, cuiles = self._leer(lambda conn: L.consolidado(conn, int(inst["id"]), self.today()))
        if resumen is None or resumen.empty:
            return {**out, "estado": "sin_datos", "mensaje": MSG_SIN_DATOS}
        return {**out, "estado": "tablero", **kpis(resumen, cuiles),
                "resumen": {"titulo": "Resumen por departamento", "tabla": tabla(L.resumen_vista(resumen)),
                            "excel": True},
                "visor": {"titulo": "Ver datos consolidados", "label": "Tabla", "opciones": list(L.TABLAS),
                          "default": L.TABLAS[0], "buscador": BUSCADOR, "csv": CSV_LABEL}}

    # ------------------------------------------------------------------ visor (bajo demanda, D-AO3)
    def tabla(self, record: SessionRecord, clave: Any, texto: Any) -> dict:
        inst = self.scope(record)
        clave, texto = clave_tabla(clave), texto_busqueda(texto)
        dft = self._leer(lambda conn: self._dft(conn, int(inst["id"]), clave))
        if dft is None or dft.empty:
            return {"tabla": clave, "vacio": True, "mensaje": MSG_SIN_CRITERIO}
        vista = L.buscar(dft, texto)
        return {"tabla": clave, "vacio": False, "busqueda": texto, "total": int(len(dft)),
                "encontrados": int(len(vista)),
                "caption": f"Resultados encontrados: {len(vista)} de {len(dft)} registros." if texto.strip() else None,
                "sin_coincidencias": MSG_SIN_COINCIDENCIAS if vista.empty else None,
                "datos": None if vista.empty else tabla(vista), "excel": not vista.empty}

    # ------------------------------------------------------------------ descargas
    def csv(self, record: SessionRecord, clave: Any) -> Descarga:
        """"Descargar CSV consolidado": la tabla COMPLETA, sin aplicar la busqueda (l. 53291-53295)."""
        inst = self.scope(record)
        clave = clave_tabla(clave)
        dft = self._leer(lambda conn: self._dft(conn, int(inst["id"]), clave))
        if dft is None or dft.empty:
            raise ConsolidadoError(409, "SIN_DATOS", MSG_SIN_CRITERIO, tone="info")
        return Descarga(dft.to_csv(index=False).encode("utf-8-sig"), f"{clave}_consolidado.csv", CSV)

    def excel(self, record: SessionRecord, clave: Any, texto: Any) -> Descarga:
        """Excel global v200 de la tabla mostrada: el resumen o la VISTA FILTRADA de la tabla elegida."""
        inst = self.scope(record)
        if clave == "resumen":
            resumen = self._leer(lambda conn: L.consolidado(conn, int(inst["id"]), self.today())[0])
            if resumen is None or resumen.empty:
                raise ConsolidadoError(409, "SIN_DATOS", MSG_SIN_DATOS, tone="info")
            df = L.resumen_vista(resumen)
        else:
            clave, texto = clave_tabla(clave), texto_busqueda(texto)
            dft = self._leer(lambda conn: self._dft(conn, int(inst["id"]), clave))
            if dft is None or dft.empty:
                raise ConsolidadoError(409, "SIN_DATOS", MSG_SIN_CRITERIO, tone="info")
            df = L.buscar(dft, texto)
            if df.empty:
                raise ConsolidadoError(409, "SIN_COINCIDENCIAS", MSG_SIN_COINCIDENCIAS, tone="info")
        return Descarga(excel_bytes(df), f"Consolidado_institucional_{self.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        XLSX)
