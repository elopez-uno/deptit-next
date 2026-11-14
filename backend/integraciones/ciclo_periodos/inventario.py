"""Inventario de dependencias de un periodo (E4-11 preflight D-E4-05; E4-12 "realmente vacio" D-E4-03 / P-12).

Solo lectura, sobre la conexion de la transaccion de la operacion (despues del lock).  Fail closed:
1. inventario EXPLICITO: los contadores certificados de ``contar_datos_asociados_periodo`` (extracted_batch03
   l. 88: designaciones, movimientos, comisiones y sus horarios / asignaciones / horarios de asignacion / inscriptos,
   inscriptos por asignatura, investigacion, extension, actividades especiales y sus asignaciones, disposiciones) MAS
   las tablas con ``periodo_id`` que el certificado no mira (estado de consulta, correcciones de historial de horas,
   documentos de respaldo, prestamos docentes) y la composicion de comisiones (``comision_materias``);
2. inventario DINAMICO del esquema: toda tabla con columna ``periodo_id`` y toda FK hacia ``periodos`` (pg_catalog).  Una
   tabla que aparezca y no este en el inventario explicito se cuenta igual (nunca se ignora);
3. referencias a las filas que una reversion borraria (FK reales hacia ``designaciones`` / ``movimientos``, incluidas
   las ON DELETE CASCADE de los vinculos documentales: borrarlas en silencio seria ocultar datos) y las referencias
   SIN FK del esquema real (``disposicion_docente_designaciones.designacion_id``).
Los conteos son GLOBALES por ``periodo_id`` (no filtrados por departamento): una fila ajena que apunte al periodo
tambien bloquea.
"""
from __future__ import annotations

import re
from typing import Iterable, Optional

from psycopg import Connection, sql

# Tablas con periodo_id del inventario explicito (orden de presentacion).
DIRECTAS = (
    ("designaciones", "Designaciones"),
    ("comisiones", "Comisiones"),
    ("inscriptos_asignatura_periodo", "Inscriptos por asignatura"),
    ("investigacion_docente", "Investigación"),
    ("extension_docente", "Extensión"),
    ("actividades_especiales", "Actividades especiales"),
    ("actividad_especial_docente", "Asignaciones de actividades especiales"),
    ("disposiciones", "Disposiciones"),
    ("estado_consulta_designacion", "Estado de consulta de designaciones"),
    ("correcciones_historial_horas", "Correcciones de historial de horas"),
    ("documentos_respaldo", "Documentos de respaldo"),
    ("prestamos_docentes", "Préstamos docentes"),
)
# Hijas de las comisiones del periodo (FK comision_id / asignacion_id).
HIJAS_COMISION = (
    ("horarios_comision", "comision_id", "Horarios de comisión"),
    ("asignaciones_docentes_comision", "comision_id", "Asignaciones de comisión"),
    ("inscriptos_comision", "comision_id", "Inscriptos de comisión"),
    ("inscriptos_comision_materia", "comision_id", "Inscriptos de comisión por materia"),
    ("comision_materias", "comision_id", "Composición de comisiones"),
)
TIPO_APERTURA = "Apertura de período"
TIPO_CIERRE = "Finalización automática por cierre de período"


def _uno(conn: Connection, query, params: Iterable) -> int:
    return int(conn.execute(query, list(params)).fetchone()[0] or 0)


def tablas_con_periodo(conn: Connection) -> set[str]:
    rows = conn.execute("SELECT table_name FROM information_schema.columns WHERE table_schema='public' AND "
                        "column_name='periodo_id'").fetchall()
    fks = conn.execute("""SELECT c.conrelid::regclass::text FROM pg_constraint c
                          WHERE c.contype='f' AND c.confrelid='public.periodos'::regclass""").fetchall()
    return {r[0] for r in rows} | {r[0].split(".")[-1] for r in fks}


def fks_hacia(conn: Connection, tabla: str) -> list[tuple[str, str]]:
    """(tabla, columna) de las FK reales hacia ``tabla`` (``designaciones`` / ``movimientos``)."""
    rows = conn.execute("""SELECT c.conrelid::regclass::text, a.attname FROM pg_constraint c
                           JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum = ANY(c.conkey)
                           WHERE c.contype='f' AND c.confrelid = %s::regclass ORDER BY 1, 2""",
                        [f"public.{tabla}"]).fetchall()
    return [(r[0].split(".")[-1], r[1]) for r in rows]


def conteos_periodo(conn: Connection, periodo_id: int, excluir: Iterable[str] = ()) -> list[dict]:
    """Filas que apuntan al periodo, tabla por tabla (explicito + dinamico).  ``movimientos`` se informa aparte."""
    excluir = set(excluir) | {"movimientos", "periodos"}
    out, vistas = [], set()
    for tabla, etiqueta in DIRECTAS:
        vistas.add(tabla)
        if tabla in excluir:
            continue
        n = _uno(conn, sql.SQL("SELECT count(*) FROM {} WHERE periodo_id = %s").format(sql.Identifier(tabla)),
                 [periodo_id])
        out.append({"tabla": tabla, "etiqueta": etiqueta, "filas": n})
    for tabla, columna, etiqueta in HIJAS_COMISION:
        if tabla in excluir:
            continue
        n = _uno(conn, sql.SQL("SELECT count(*) FROM {} WHERE {} IN (SELECT id FROM comisiones WHERE periodo_id = %s)")
                 .format(sql.Identifier(tabla), sql.Identifier(columna)), [periodo_id])
        out.append({"tabla": tabla, "etiqueta": etiqueta, "filas": n})
    n = _uno(conn, """SELECT count(*) FROM horarios_asignacion_docente_comision WHERE asignacion_id IN (
                      SELECT id FROM asignaciones_docentes_comision WHERE comision_id IN (
                      SELECT id FROM comisiones WHERE periodo_id = %s))""", [periodo_id])
    out.append({"tabla": "horarios_asignacion_docente_comision", "etiqueta": "Horarios de asignación docente",
                "filas": n})
    for tabla in sorted(tablas_con_periodo(conn) - vistas - excluir):
        n = _uno(conn, sql.SQL("SELECT count(*) FROM {} WHERE periodo_id = %s").format(sql.Identifier(tabla)),
                 [periodo_id])
        out.append({"tabla": tabla, "etiqueta": f"Otros datos ({tabla})", "filas": n})
    return out


# Referencias SIN FK en el esquema real (fail closed: se cuentan aunque la base no las declare).
REFERENCIAS_SIN_FK = {
    "designaciones": (("disposicion_docente_designaciones", "designacion_id"),),
    "movimientos": (),
}


def referencias(conn: Connection, tabla: str, ids_query: str, params: list) -> list[dict]:
    """Filas que apunten a las filas de ``ids_query``: toda FK real hacia ``tabla`` + las referencias sin FK."""
    out = []
    pares = list(dict.fromkeys(fks_hacia(conn, tabla) + list(REFERENCIAS_SIN_FK.get(tabla, ()))))
    for hija, columna in pares:
        n = _uno(conn, sql.SQL("SELECT count(*) FROM {} WHERE {} IN (" + ids_query + ")")
                 .format(sql.Identifier(hija), sql.Identifier(columna)), params)
        out.append({"tabla": hija, "etiqueta": f"Vínculos de {tabla} ({hija})", "filas": n})
    return out


def movimientos_periodo(conn: Connection, periodo_id: int) -> list[dict]:
    from psycopg.rows import dict_row
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id, tipo_movimiento, cuil, nombre, detalle, horas_variacion, periodo_id FROM movimientos "
                    "WHERE periodo_id = %s ORDER BY id", [periodo_id])
        return list(cur.fetchall())


def apertura_automatica(periodo: dict, movimientos: list[dict]) -> Optional[dict]:
    """P-12: la UNICA fila de movimientos del periodo es la apertura que crea el sistema (B12C S4):
    tipo "Apertura de período", sin CUIL ni nombre, sin horas, del mismo periodo y con el detalle EXACTO
    "Se creó el período {nombre} ({fecha_inicio} al {fecha_fin}).".  Cualquier otra cosa -> None (fail closed)."""
    if len(movimientos) != 1:
        return None
    m = movimientos[0]
    detalle = f"Se creó el período {periodo['nombre']} ({periodo['fecha_inicio']} al {periodo['fecha_fin']})."
    try:
        horas = float(m.get("horas_variacion") or 0)
    except (TypeError, ValueError):
        return None
    if (m.get("tipo_movimiento") == TIPO_APERTURA and str(m.get("cuil") or "") == "" and str(m.get("nombre") or "") == ""
            and horas == 0 and m.get("detalle") == detalle and int(m.get("periodo_id")) == int(periodo["id"])):
        return m
    return None


def cierres_generados_por(conn: Connection, inst: int, dep: int, nombre: str) -> int:
    """Finalizaciones automaticas que la CREACION de este periodo hizo en el periodo anterior (B12C S9:
    observaciones "Cierre automático generado al crear el período {nombre}.").  Deshacerlas no es eliminar un periodo
    vacio: corresponde a Revertir ultimo cierre."""
    return _uno(conn, "SELECT count(*) FROM movimientos WHERE institucion_id=%s AND departamento_id=%s AND "
                      "tipo_movimiento=%s AND observaciones=%s",
                [inst, dep, TIPO_CIERRE, f"Cierre automático generado al crear el período {nombre}."])


# --- P-12b: finalizaciones automaticas por cierre que quedaron en el periodo ABIERTO
OBS_CIERRE = re.compile(r"^Cierre automático generado al crear el período (.+)\.$")


def cierres_del_periodo(conn: Connection, periodo_id: int) -> list[dict]:
    """Movimientos de cierre automatico del periodo (GLOBAL por periodo_id: uno ajeno tambien se ve)."""
    from psycopg.rows import dict_row
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id, institucion_id, departamento_id, cuil, detalle, observaciones FROM movimientos "
                    "WHERE periodo_id = %s AND tipo_movimiento = %s ORDER BY id", [periodo_id, TIPO_CIERRE])
        return list(cur.fetchall())


def finalizadas_del_periodo(conn: Connection, inst: int, dep: int, periodo_id: int) -> list[dict]:
    from psycopg.rows import dict_row
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id, cuil, cargo, dedicacion, horas, tipo_designacion FROM designaciones WHERE periodo_id = %s"
                    " AND estado = 'Finalizada' AND institucion_id = %s AND departamento_id = %s ORDER BY id",
                    [periodo_id, inst, dep])
        return list(cur.fetchall())


def reparacion_cierres(inst: int, dep: int, abierto: dict, ultimo: Optional[dict], nombres: set, movimientos: list,
                       finalizadas: list, texto_designacion) -> tuple[list[dict], set[int]]:
    """Preflight P-12b fail closed -> (bloqueos, ids de designaciones a reactivar).

    Reparable solo si los cierres son HUERFANOS (el periodo cuya creacion los genero ya no existe) y cada movimiento se
    identifica exactamente: CUIL no vacio, detalle "Al cerrar {abierto}, se finalizó: {texto certificado}" y, por cada
    (CUIL, detalle), tantas designaciones Finalizadas del periodo con ese CUIL y texto como movimientos.  Sin fallback
    por "CUIL con una sola finalizada" (el certificado lo usa: podria reactivar una finalizacion manual)."""
    bloqueos: list[dict] = []
    if ultimo is None or int(ultimo["id"]) != int(abierto["id"]):
        bloqueos.append({"tabla": "periodos", "filas": len(movimientos), "etiqueta":
                         f"el período abierto no es el último del departamento (existe {ultimo['nombre'] if ultimo else '?'}"
                         "): sus finalizaciones corresponden a un cierre vigente"})
    ajenos = [m for m in movimientos if (m["institucion_id"], m["departamento_id"]) != (inst, dep)]
    if ajenos:
        bloqueos.append({"tabla": "movimientos", "filas": len(ajenos), "etiqueta": "movimientos de otro ámbito"})
    vigentes = [m for m in movimientos if (x := OBS_CIERRE.match(str(m.get("observaciones") or "")))
                and x.group(1) in nombres]
    if vigentes:
        bloqueos.append({"tabla": "movimientos", "filas": len(vigentes), "etiqueta":
                         "generadas al crear un período que todavía existe"})
    prefijo = f"Al cerrar {abierto['nombre']}, se finalizó: "
    grupos: dict = {}
    for m in movimientos:
        grupos.setdefault((str(m.get("cuil") or "").strip(), str(m.get("detalle") or "")), []).append(m)
    ambiguos, ids = 0, set()
    for (cuil, detalle), movs in grupos.items():
        candidatas = [int(d["id"]) for d in finalizadas if cuil and str(d.get("cuil") or "").strip() == cuil
                      and detalle.startswith(prefijo) and prefijo + texto_designacion(d) == detalle]
        if len(candidatas) != len(movs):
            ambiguos += len(movs)
        else:
            ids.update(candidatas)
    if ambiguos:
        bloqueos.append({"tabla": "movimientos", "filas": ambiguos, "etiqueta":
                         "movimientos sin una designación finalizada inequívoca (caso ambiguo o finalización manual)"})
    return bloqueos, ids


__all__ = ["apertura_automatica", "cierres_del_periodo", "cierres_generados_por", "conteos_periodo",
           "finalizadas_del_periodo", "movimientos_periodo", "reparacion_cierres", "referencias", "tablas_con_periodo"]
