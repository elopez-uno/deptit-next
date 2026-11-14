"""Lecturas de Administración SaaS sobre una conexión/transacción ya abierta (nunca confirma ni crea tablas).

Origen certificado (B13-FIX02):
- ``get_instituciones_auth`` l. 1816 (``SELECT * FROM instituciones ORDER BY nombre``);
- ``get_departamentos_auth`` / ``get_usuarios_auth`` / ``contar_usuarios_activos_institucion``:
  ``deptit_refactor/extracted_batch03/readonly_queries.py`` l. 30-64 (mismo SQL, mismo orden);
- ``get_uso_instituciones`` l. 3204: misma semántica con una lectura AGREGADA (8 consultas en lugar de
  1 + Σ(2 + 3·departamentos + 2)); los conteos por departamento del certificado (``_pg_count_table`` con
  ``institucion_id`` y ``departamento_id`` de cada departamento de la institución) equivalen al JOIN con
  ``departamentos`` por id e institución;
- diagnóstico de planes (``mostrar_diagnostico_planes_institucion`` l. 2621, D-AP3): solo los conteos
  ``carreras``/``materias`` de la institución (``_pg_count_table`` de tablas institucionales) y su estado.

Las conexiones ``auth`` del certificado no reciben ámbito (l. 1108/1163/42899): SaaS es global por diseño.

Dependencias (D-AP1/D-AP2): inventario DINÁMICO del catálogo (toda tabla base de ``public`` con ``institucion_id`` /
``departamento_id``; nombres desde ``information_schema``, nunca del cliente), así una tabla nueva también bloquea la
eliminación.  ``b12h_audit_log`` (auditoría histórica) no cuenta como dependencia y nunca se borra.  Además
``prestamos_docentes.departamento_origen`` referencia al departamento POR NOMBRE.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

import pandas as pd
from psycopg import Connection, sql
from psycopg.rows import dict_row

from auth import core

# Columnas técnicas heredadas de la migración SQLite: no se muestran (D-AP6) ni el slug (certificado).
COLUMNAS_OCULTAS_INSTITUCIONES = ["slug", "sqlite_id", "source_db"]
COLUMNAS_OCULTAS_DEPARTAMENTOS = ["slug", "institucion_slug", "sqlite_id", "source_db"]
COLUMNAS_DATOS_INSTITUCION = ["id", "nombre", "plan", "max_usuarios", "fecha_vencimiento", "estado_pago", "suscripcion",
                              "estado", "observaciones"]
COLUMNAS_DATOS_DEPARTAMENTO = ["id", "institucion", "nombre", "estado", "observaciones"]
COLUMNAS_DATOS_USUARIO = ["id", "nombre", "email", "rol", "estado", "institucion", "departamento", "observaciones"]
TABLAS_EXCLUIDAS_DEPENDENCIAS = frozenset({"b12h_audit_log"})

INSTITUCIONES_SQL = "SELECT * FROM instituciones {filtro} ORDER BY nombre"
DEPARTAMENTOS_SQL = """
        SELECT d.*, i.nombre AS institucion, i.slug AS institucion_slug
        FROM departamentos d
        LEFT JOIN instituciones i ON i.id = d.institucion_id
        {where}
        ORDER BY i.nombre, d.nombre
    """
USUARIOS_SQL = """
        SELECT
            u.id, u.institucion_id, u.departamento_id, u.nombre, u.email, u.rol, u.estado,
            u.fecha_alta, u.observaciones,
            i.nombre AS institucion,
            d.nombre AS departamento
        FROM app_usuarios u
        LEFT JOIN instituciones i ON i.id = u.institucion_id
        LEFT JOIN departamentos d ON d.id = u.departamento_id
        {where}
        ORDER BY COALESCE(i.nombre, 'Sistema'), u.rol, u.nombre, u.email
    """
ACTIVOS_SQL = ("SELECT COUNT(*) FROM app_usuarios WHERE institucion_id = %s AND estado = 'Activo' "
               "AND rol <> 'superadmin'")
TABLAS_CON_COLUMNA_SQL = """
    SELECT c.table_name FROM information_schema.columns c
    JOIN information_schema.tables t ON t.table_schema = c.table_schema AND t.table_name = c.table_name
         AND t.table_type = 'BASE TABLE'
    WHERE c.table_schema = 'public' AND c.column_name = %s ORDER BY c.table_name
"""


def _df(conn: Connection, query: Any, params: Optional[list] = None) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute(query, params or [])
        cols = [d.name for d in cur.description] if cur.description else []
        return pd.DataFrame(cur.fetchall(), columns=cols)


def _scalar(conn: Connection, query: Any, params: Optional[list] = None) -> Any:
    with conn.cursor() as cur:
        cur.execute(query, params or [])
        row = cur.fetchone()
        return None if row is None else row[0]


# ------------------------------------------------------------------------------------------ lecturas certificadas
def instituciones(conn: Connection, solo_activas: bool = False) -> pd.DataFrame:
    filtro = "WHERE estado = 'Activa'" if solo_activas else ""
    return _df(conn, INSTITUCIONES_SQL.format(filtro=filtro))


def departamentos(conn: Connection, institucion_id: Optional[int] = None, solo_activos: bool = False) -> pd.DataFrame:
    filtros, params = [], []
    if institucion_id is not None:
        filtros.append("d.institucion_id = %s")
        params.append(int(institucion_id))
    if solo_activos:
        filtros.append("d.estado = 'Activo'")
    where = "WHERE " + " AND ".join(filtros) if filtros else ""
    return _df(conn, DEPARTAMENTOS_SQL.format(where=where), params)


def usuarios(conn: Connection, institucion_id: Optional[int] = None) -> pd.DataFrame:
    """Nunca selecciona ``salt`` ni ``password_hash`` (mismo SELECT que el certificado)."""
    where, params = ("WHERE u.institucion_id = %s", [int(institucion_id)]) if institucion_id is not None else ("", [])
    return _df(conn, USUARIOS_SQL.format(where=where), params)


def activos_institucion(conn: Connection, institucion_id: int) -> int:
    return int(_scalar(conn, ACTIVOS_SQL, [int(institucion_id)]) or 0)


def vista_instituciones(df: pd.DataFrame) -> pd.DataFrame:
    return df.drop(columns=COLUMNAS_OCULTAS_INSTITUCIONES, errors="ignore")


def vista_departamentos(df: pd.DataFrame) -> pd.DataFrame:
    return df.drop(columns=COLUMNAS_OCULTAS_DEPARTAMENTOS, errors="ignore")


def datos_actuales(fila: dict, columnas: list[str]) -> pd.DataFrame:
    """``mostrar_datos_actuales_seleccion`` (l. 2748): una fila con las columnas pedidas que existan."""
    return pd.DataFrame([{c: fila.get(c, "") for c in columnas if c in fila}])


# ------------------------------------------------------------------------------------------ tablero de uso
def _por_institucion(conn: Connection, query: Any) -> dict[int, int]:
    with conn.cursor() as cur:
        cur.execute(query)
        return {int(r[0]): int(r[1]) for r in cur.fetchall() if r[0] is not None}


def uso(conn: Connection, today: date) -> pd.DataFrame:
    """``get_uso_instituciones`` (l. 3204) con lecturas agregadas; mismas columnas, filas y valores."""
    inst = instituciones(conn)
    if inst.empty:
        return pd.DataFrame()
    activos = _por_institucion(conn, "SELECT institucion_id, COUNT(*) FILTER (WHERE estado = 'Activo') "
                                     "FROM app_usuarios GROUP BY institucion_id")
    deps = _por_institucion(conn, "SELECT institucion_id, COUNT(*) FROM departamentos GROUP BY institucion_id")
    por_dep = {t: _por_institucion(conn, sql.SQL(
        "SELECT t.institucion_id, COUNT(*) FROM {t} t JOIN departamentos d ON d.id = t.departamento_id "
        "AND d.institucion_id = t.institucion_id GROUP BY t.institucion_id").format(t=sql.Identifier(t)))
        for t in ("docentes", "designaciones", "comisiones")}
    planes = {t: _por_institucion(conn, sql.SQL("SELECT institucion_id, COUNT(*) FROM {t} GROUP BY institucion_id")
                                  .format(t=sql.Identifier(t))) for t in ("carreras", "materias")}
    registros = []
    for _, i in inst.iterrows():
        iid = int(i.get("id"))
        max_usuarios = int(i.get("max_usuarios") or 0)
        usuarios_activos = activos.get(iid, 0)
        vencida = core.fecha_vencimiento_vencida(i.get("fecha_vencimiento"), today)
        estado_pago = str(i.get("estado_pago") or "Activo")
        registros.append({
            "Institución": i.get("nombre"),
            "Plan": i.get("plan"),
            "Suscripción": str(i.get("suscripcion") or "Activa"),
            "Estado de pago": "Vencido" if vencida and estado_pago == "Activo" else estado_pago,
            "Acceso": str(i.get("estado") or "Activa"),
            "Vencimiento": i.get("fecha_vencimiento") or "",
            "Usuarios activos": usuarios_activos,
            "Cupo usuarios": max_usuarios,
            "Uso cupo": f"{usuarios_activos}/{max_usuarios}" if max_usuarios else str(usuarios_activos),
            "Departamentos": deps.get(iid, 0),
            "Carreras": planes["carreras"].get(iid, 0),
            "Materias": planes["materias"].get(iid, 0),
            "Docentes": por_dep["docentes"].get(iid, 0),
            "Designaciones": por_dep["designaciones"].get(iid, 0),
            "Comisiones": por_dep["comisiones"].get(iid, 0),
            "Última act. comercial": i.get("fecha_ultima_actualizacion_comercial") or "",
            "Observaciones": i.get("observaciones") or "",
        })
    return pd.DataFrame(registros)


def planes(conn: Connection, institucion_id: int) -> dict:
    """Métricas del diagnóstico de planes (D-AP3: sin archivo ni rutas)."""
    carreras = int(_scalar(conn, "SELECT COUNT(*) FROM carreras WHERE institucion_id = %s", [int(institucion_id)]) or 0)
    materias = int(_scalar(conn, "SELECT COUNT(*) FROM materias WHERE institucion_id = %s", [int(institucion_id)]) or 0)
    return {"carreras": carreras, "materias": materias, "estado": "OK" if carreras > 0 or materias > 0 else "Sin datos"}


# ------------------------------------------------------------------------------------------ dependencias
def tablas_con_columna(conn: Connection, columna: str) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(TABLAS_CON_COLUMNA_SQL, [columna])
        return [r[0] for r in cur.fetchall()]


def _conteos(conn: Connection, columna: str, excluidas: set[str], ids: Optional[list[int]] = None) -> dict:
    """{id: {tabla: filas}} para cada tabla con ``columna`` (UNA consulta UNION ALL)."""
    tablas = [t for t in tablas_con_columna(conn, columna) if t not in excluidas]
    if not tablas:
        return {}
    filtro = sql.SQL(" WHERE {c} = ANY(%s)").format(c=sql.Identifier(columna)) if ids is not None else sql.SQL("")
    partes = [sql.SQL("SELECT {lit}::text AS tabla, {c} AS id, COUNT(*) AS n FROM {t}{f} GROUP BY {c}").format(
        lit=sql.Literal(t), c=sql.Identifier(columna), t=sql.Identifier(t), f=filtro) for t in tablas]
    params = [list(ids)] * len(partes) if ids is not None else []
    out: dict[int, dict[str, int]] = {}
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql.SQL(" UNION ALL ").join(partes), params)
        for r in cur.fetchall():
            if r["id"] is not None and int(r["n"]) > 0:
                out.setdefault(int(r["id"]), {})[r["tabla"]] = int(r["n"])
    return out


def dependencias_instituciones(conn: Connection, ids: Optional[list[int]] = None) -> dict:
    """Filas que referencian cada institución en CUALQUIER tabla (con o sin FK), incluidos usuarios y departamentos."""
    return _conteos(conn, "institucion_id", {"instituciones"} | TABLAS_EXCLUIDAS_DEPENDENCIAS, ids)


def dependencias_departamentos(conn: Connection, ids: Optional[list[int]] = None) -> dict:
    """Filas que referencian cada departamento (``departamento_id`` en cualquier tabla, incluidos los usuarios) y los
    préstamos de docentes cuyo departamento de origen es ese departamento (por nombre, misma institución)."""
    out = _conteos(conn, "departamento_id", {"departamentos"} | TABLAS_EXCLUIDAS_DEPENDENCIAS, ids)
    filtro = "WHERE d.id = ANY(%s)" if ids is not None else ""
    with conn.cursor() as cur:
        cur.execute("SELECT d.id, COUNT(p.*) FROM departamentos d JOIN prestamos_docentes p "
                    "ON p.institucion_id = d.institucion_id AND LOWER(TRIM(p.departamento_origen)) = "
                    f"LOWER(TRIM(d.nombre)) {filtro} GROUP BY d.id", [list(ids)] if ids is not None else [])
        for did, n in cur.fetchall():
            if int(n) > 0:
                out.setdefault(int(did), {})["prestamos_docentes.departamento_origen"] = int(n)
    return out


def resumen_dependencias(dep: dict) -> dict:
    """Totales sin nombres de tablas para la UI: usuarios, departamentos y demás registros."""
    usuarios_n = dep.get("app_usuarios", 0)
    departamentos_n = dep.get("departamentos", 0)
    otros = sum(n for t, n in dep.items() if t not in ("app_usuarios", "departamentos"))
    return {"usuarios": usuarios_n, "departamentos": departamentos_n, "registros": otros,
            "tablas": len([t for t in dep if t not in ("app_usuarios", "departamentos")])}
