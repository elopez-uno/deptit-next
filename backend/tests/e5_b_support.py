"""Etapa 5 / Tanda B — calculos INDEPENDIENTES para verificar el sueldo estimado del Resumen docente (B1/B2).

El esperado se arma con SQL propio (no reutiliza las consultas NEXT) y las reglas certificadas puras
(``calcular_sueldo_designacion_v256``, ``escala_aplicable_v256`` y el saneamiento v265 de la vista institucional):
- designaciones del docente (digitos del CUIL) en la INSTITUCION de la sesion, cualquier departamento con ficha del
  docente, periodo equivalente (mismo id, nombre o anio+semestre), como la vista institucional v149;
- con el periodo del departamento de la sesion NO cerrado, solo ``estado = 'Activa'`` (base l. 26679 y plantel);
- ``ad_honorem`` de cada designacion (Ad Honorem = $0); el saneamiento v265 por separado para rentadas y Ad Honorem;
- antiguedad y posgrado de la FICHA del docente en el departamento de la sesion.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from comisiones.proyectos import _sanear_designaciones_institucionales_v265
from sueldos import rules as SR

_DIG = "regexp_replace(COALESCE({c}, ''), '[^0-9]', '', 'g')"


def _df(conn, sql, params) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [d.name for d in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)


def sueldo_resumen_independiente(conn, inst: int, dep: int, cuil: str, periodo_id: int, mes_objetivo: str,
                                 hoy: date) -> dict:
    per = conn.execute("SELECT nombre, anio, semestre, estado FROM periodos WHERE id = %s", [periodo_id]).fetchone()
    local = conn.execute("SELECT estado FROM periodos WHERE id = %s AND institucion_id = %s AND departamento_id = %s",
                         [periodo_id, inst, dep]).fetchone()
    solo_activas = local is not None and str(local[0] or "").strip().lower() != "cerrado"
    filas = _df(conn, f"""
        SELECT d.id, d.departamento_id, COALESCE(dep.nombre, 'Sin departamento') AS departamento, d.cargo, d.dedicacion,
               d.horas, d.tipo_designacion, d.estado, d.fecha_desde, d.fecha_hasta, COALESCE(d.ad_honorem, 'No') AS ad_honorem,
               COALESCE(d.funcion_no_docente, 0) AS funcion_no_docente
        FROM designaciones d JOIN periodos p ON p.id = d.periodo_id
        LEFT JOIN departamentos dep ON dep.id = d.departamento_id
        WHERE d.institucion_id = %s AND p.institucion_id = d.institucion_id
          AND p.departamento_id IS NOT DISTINCT FROM d.departamento_id
          AND {_DIG.format(c='d.cuil')} = %s
          AND (d.periodo_id = %s OR p.nombre = %s OR (p.anio = %s AND p.semestre = %s))
          AND EXISTS (SELECT 1 FROM docentes x WHERE x.institucion_id = d.institucion_id
                      AND x.departamento_id IS NOT DISTINCT FROM d.departamento_id
                      AND {_DIG.format(c='x.cuil')} = {_DIG.format(c='d.cuil')})
        ORDER BY dep.nombre, d.fecha_desde, d.id""",
                [inst, SR.clave_cuil(cuil), periodo_id, per[0], int(per[1]), int(per[2])])
    if not filas.empty:  # v265 por separado para rentadas y Ad Honorem (no fusiona una rentada con una Ad Honorem)
        es_adh = filas["ad_honorem"].map(SR.es_ad_honorem_v162)
        filas = pd.concat([_sanear_designaciones_institucionales_v265(filas[es_adh == v]) for v in (False, True)],
                          ignore_index=True)
    if solo_activas and not filas.empty:
        filas = filas[filas["estado"].fillna("Activa").astype(str).str.strip().eq("Activa")]
    ficha = conn.execute(f"SELECT antiguedad_anios, COALESCE(nivel_posgrado_salarial, '') FROM docentes "
                         f"WHERE institucion_id = %s AND departamento_id = %s AND {_DIG.format(c='cuil')} = %s",
                         [inst, dep, SR.clave_cuil(cuil)]).fetchone()
    antig, nivel = (ficha[0], ficha[1]) if ficha else (None, "")
    escalas = _df(conn, "SELECT * FROM escalas_salariales_docentes WHERE institucion_id = %s", [inst])
    mes_esc, escala = SR.escala_aplicable_v256(escalas, mes_objetivo, hoy)
    detalle = []
    for _, r in filas.iterrows():
        c = SR.calcular_sueldo_designacion_v256(r["cargo"], r["dedicacion"], r["ad_honorem"], antig, nivel, escala)
        detalle.append((str(r["cargo"] or ""), str(r["dedicacion"] or ""), "Sí" if c["ad_honorem"] else "No",
                        round(float(c["total_estimado"]), 2)))
    return {"mes_escala": mes_esc, "filas": sorted(detalle), "total": round(sum(x[3] for x in detalle), 2),
            "ad_honorem_en_db": int(filas["ad_honorem"].astype(str).str.startswith("S").sum()) if not filas.empty else 0}


def filas_next(r: dict) -> list:
    """(cargo, dedicacion, Ad Honorem, sueldo) de ``SueldosService.sueldo_docente_resumen``."""
    return sorted((str(f["Cargo"]), str(f["Dedicación"]), f["Ad Honorem"], round(float(f["Sueldo estimado"]), 2))
                  for f in r.get("filas", []))
