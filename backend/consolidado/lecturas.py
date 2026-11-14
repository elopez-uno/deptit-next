"""Lecturas de Consolidado institucional (B13-FIX02 ``render_consolidado_institucional`` v242, entry l. 53184).

Decision D-AO1: se COMPONE con lecturas NEXT ya certificadas, importadas sin modificarlas:
- ``investigacion.lecturas.consolidado_v240`` (l. 53142 + snapshot l. 53026): resumen por departamento, CUIL unicos,
  listado de docentes contados y conteo de designaciones (un repositorio por departamento: la sesion no se toca);
- ``DesignacionesService._designaciones`` (``get_designaciones`` con actos v266): tabla "designaciones" de 28 columnas;
- ``materias.rules.filtrar_dataframe_por_texto`` (``common/text.py``, ya portado): buscador de la tabla.
Lo unico nuevo es el lector de las 7 tablas crudas (``_consolidado_tabla_pg_v238`` l. 49403, rama generica), con el
nombre fisico tomado SOLO de una allowlist fija (``psycopg.sql.Identifier``; nunca texto del cliente), y el hardening
H-1 (``archivo_word``/``plantilla_usada`` de ``disposiciones`` reducidos al nombre del archivo).

Sin escrituras: solo SELECT dentro de la transaccion READ ONLY del servicio.  Sin reparacion v229, sin caches
persistentes ni pilotos.
"""

from __future__ import annotations

import ntpath
from datetime import date
from typing import Optional

import pandas as pd
from psycopg import Connection, sql
from psycopg.rows import dict_row

from comisiones.lecturas import Lector
from designaciones.repository import DesignacionesRepository
from designaciones.service import ROW_FIELDS, DesignacionesService
from investigacion.lecturas import consolidado_v240
from investigacion.repository import InvestigacionRepository
from materias.rules import filtrar_dataframe_por_texto

# Selector "Tabla" (l. 53254-53258): claves y orden certificados.
TABLAS = ["docentes", "designaciones", "comisiones", "inscriptos_asignatura_periodo",
          "asignaciones_docentes_comision", "investigacion_docente", "extension_docente", "disposiciones",
          "movimientos"]
# Allowlist clave publica -> tabla fisica de la rama generica (las 2 primeras salen de los listados v240).
TABLAS_CRUDAS = {
    "comisiones": "comisiones",
    "inscriptos_asignatura_periodo": "inscriptos_asignatura_periodo",
    "asignaciones_docentes_comision": "asignaciones_docentes_comision",
    "investigacion_docente": "investigacion_docente",
    "extension_docente": "extension_docente",
    "disposiciones": "disposiciones",
    "movimientos": "movimientos",
}
LIMITE = 5000  # ``_consolidado_tabla_pg_v238(inst, tabla, 5000)``: rn <= min(limite, 5000) por departamento
TABLA_CRUDA_SQL = """
    WITH x AS (
        SELECT dep.nombre AS departamento_origen, t.*,
               ROW_NUMBER() OVER (PARTITION BY t.departamento_id ORDER BY t.id) rn
        FROM {tabla} t
        JOIN departamentos dep ON dep.id=t.departamento_id AND dep.institucion_id=t.institucion_id
        WHERE t.institucion_id=%s
    )
    SELECT * FROM x WHERE rn <= {limite} ORDER BY departamento_origen, id
"""
# Hardening NEXT H-1: el certificado muestra estas columnas con la ruta absoluta (con el usuario de Windows); NEXT
# muestra, busca y exporta solo el nombre del archivo.  Unicamente en ``disposiciones``.
COLUMNAS_SOLO_NOMBRE = {"disposiciones": ("archivo_word", "plantilla_usada")}
SIN_PERIODOS = "Sin períodos"
COLUMNAS_TECNICAS = ["sqlite_id", "source_db", "source"]
FINALES = ["departamento_origen", "periodo_consolidado", "departamentos", "id"]
RENOMBRE_RESUMEN = {
    "departamento": "Departamento",
    "periodo_actual": "Período tomado",
    "estado_periodo": "Estado del período",
    "docentes": "Docentes del período",
    "designaciones": "Designaciones del período",
    "horas_designadas": "Horas de designaciones",
}


def consolidado(conn: Connection, inst: int, today: date):
    """``_consolidado_desde_listados_reales_v240(inst)``: (resumen, docentes, designaciones contadas, CUIL unicos).

    ``InvestigacionRepository`` exige un departamento entero aunque esta lectura solo use la institucion (cada
    departamento se lee con su propio repositorio dentro de ``consolidado_v240``)."""
    return consolidado_v240(InvestigacionRepository(conn, int(inst), 0), today)


def _periodo_tomado(conn: Connection, inst: int, dep: int, today: date) -> Optional[dict]:
    """Periodo del snapshot v240 (l. 53058-53067): abierto si existe; si no, el primero de ``get_periodos()``."""
    rd = InvestigacionRepository(conn, int(inst), int(dep))
    periodos = rd.periods()
    if not periodos:
        return None
    return Lector(rd, today).periodo_abierto() or periodos[0]


def designaciones_enriquecidas(conn: Connection, inst: int, resumen: pd.DataFrame, contadas: pd.DataFrame,
                               today: date) -> pd.DataFrame:
    """Tabla "designaciones": por departamento, ``get_designaciones(periodo)`` (con actos v266) filtrada a Activa, con
    ``departamento_origen`` y ``periodo_consolidado`` al frente (l. 53074-53083 y 53125-53128).

    Las filas son exactamente las ``contadas`` por v240 y en su orden (el certificado): ``_designaciones`` de
    Designaciones desempata de otra forma a un mismo docente, por eso se reordena por la posicion del ``id``."""
    partes = []
    for _, fila in resumen.iterrows():
        if int(fila.get("designaciones") or 0) <= 0:
            continue
        dep = int(fila["departamento_id"])
        periodo = _periodo_tomado(conn, inst, dep, today)
        if periodo is None:
            continue
        filas = DesignacionesService._designaciones(DesignacionesRepository(conn, int(inst), dep), int(periodo["id"]))
        df = pd.DataFrame(filas, columns=list(ROW_FIELDS) + ["huella"]).drop(columns=["huella"])
        # como el certificado (columna object con enteros y nulos): evita que pandas lo convierta a float ("5.0")
        df["acto_documento_id"] = pd.Series([f["acto_documento_id"] for f in filas], index=df.index, dtype=object)
        estado = df["estado"].fillna("").astype(str).str.strip().str.casefold()
        df = df[estado.eq("activa")].copy()
        if df.empty:
            continue
        df.insert(0, "departamento_origen", str(fila.get("departamento") or ""))
        df.insert(1, "periodo_consolidado", str(periodo.get("nombre") or ""))
        partes.append(df)
    if not partes:
        return pd.DataFrame()
    out = pd.concat(partes, ignore_index=True, sort=False)
    orden = {int(i): n for n, i in enumerate(contadas["id"])} if "id" in contadas.columns else {}
    if set(orden) != set(int(i) for i in out["id"]):
        raise RuntimeError("designaciones contadas y enriquecidas no coinciden")
    return out.iloc[sorted(range(len(out)), key=lambda k: orden[int(out["id"].iat[k])])].reset_index(drop=True)


def tabla_cruda(conn: Connection, inst: int, clave: str) -> pd.DataFrame:
    """Rama generica de ``_consolidado_tabla_pg_v238`` (l. 49477-49492) para una clave de la allowlist."""
    fisica = TABLAS_CRUDAS[clave]  # KeyError si no esta en la allowlist: el servicio valida antes
    consulta = sql.SQL(TABLA_CRUDA_SQL).format(tabla=sql.Identifier(fisica), limite=sql.Literal(LIMITE))
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(consulta, [int(inst)])
        filas = cur.fetchall()
        columnas = [d.name for d in cur.description] if cur.description else []
    dft = pd.DataFrame(filas, columns=columnas).drop(columns=["rn"], errors="ignore")
    for col in COLUMNAS_SOLO_NOMBRE.get(clave, ()):
        if col in dft.columns:
            dft[col] = dft[col].map(solo_nombre)
    return dft


def solo_nombre(valor):
    """Hardening NEXT H-1 (aprobado 2026-10-30): de una ruta absoluta (Windows o POSIX) queda solo el nombre del
    archivo; nulos y no-texto quedan igual.  Solo transforma la vista: la base no se modifica."""
    return ntpath.basename(valor) if isinstance(valor, str) else valor


def resumen_vista(resumen: pd.DataFrame) -> pd.DataFrame:
    """Tabla "Resumen por departamento" (l. 53236-53244)."""
    return resumen.rename(columns=RENOMBRE_RESUMEN).drop(columns=["departamento_id"], errors="ignore")


def ordenar(dft: pd.DataFrame) -> pd.DataFrame:
    """l. 53266-53269: sin columnas tecnicas y con las finales al final."""
    dft = dft.drop(columns=COLUMNAS_TECNICAS, errors="ignore")
    finales = [c for c in FINALES if c in dft.columns]
    principales = [c for c in dft.columns if c not in finales]
    return dft[principales + finales]


def buscar(dft: pd.DataFrame, texto: str) -> pd.DataFrame:
    """l. 53274-53283: busqueda sobre todas las columnas de la tabla ya obtenida."""
    return filtrar_dataframe_por_texto(dft, texto, dft.columns.tolist())
