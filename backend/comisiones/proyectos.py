"""Reajuste certificado de horas de Investigacion/Extension por horas de comision (v184/v185/v151), minimo necesario.

Efecto mecanico que ejecutan los writers de Comisiones dentro de su operacion de negocio (decision aprobada K2-B):
``reconciliar_horas_proyectos_por_comisiones_v184`` (entry l. 40421) reduce ``horas_asignadas`` de las asignaciones de
proyectos del CUIL (la cargada mas recientemente primero) cuando superan la capacidad, con un UPDATE + COMMIT por fila
(``_actualizar_horas_proyecto_directo_v184`` l. 40391, conexion cruda, filtro por institucion).  No registra movimiento.

Capacidad (``capacidad_proyectos_docente_v184`` l. 40242, cache v191 l. 42643):
  horas contratadas de docencia (l. 40148: ``_designaciones_docente_contexto_v182`` institucional + foto v183)
  - horas reales unicas frente a comision (l. 40179: global PG l. 30526, o historicas v182 l. 39358)
  - horas no lectivas (l. 40195 -> ``get_productividad_docente_institucional_v149``: en el periodo actual la clave la
    fija v151 l. 31696/31625 -- por comision, 50 % si hay 2+ docentes --; en un periodo historico v182 l. 39435 --por
    departamento--).  De la productividad solo se consume ``horas_no_lectivas``.
Asignaciones a proyectos (l. 40218): ``get_investigacion_docente`` / ``get_extension_docente`` con
``todos_departamentos=True`` (rama PG l. 22041 / 23119) + foto al cierre v183 (l. 39972 / 39944).  El enriquecimiento
de presentacion v277 (nombre/departamento de origen) no interviene en el calculo y no se porta.
No se portan pantallas ni otras reglas de Investigacion/Extension.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from designaciones.repository import _numeric
from designaciones.rules import CARGOS, DEDICACIONES, TIPOS_DESIGNACION, condicion_periodo_equivalente_sql
from designaciones.rules import es_funcion_no_docente, filtrar_foto_v183

from . import rules as R

W_HORAS_PROYECTO = "_actualizar_horas_proyecto_directo_v184"

DESIG_INST_V149_SQL = """
    SELECT
        d.id, d.cuil, d.periodo_id, d.departamento_id,
        COALESCE(dep.nombre, 'Sin departamento') AS departamento,
        p.nombre AS periodo,
        d.cargo, d.dedicacion, d.horas, d.tipo_designacion, d.estado,
        d.fecha_desde, d.fecha_hasta,
        COALESCE(NULLIF(d.fecha_hasta_prevista,''), d.fecha_hasta) AS fecha_hasta_prevista,
        d.fecha_finalizacion_efectiva, d.fecha_registro_finalizacion,
        d.motivo_finalizacion, COALESCE(d.observaciones, '') AS observaciones
    FROM designaciones d
    JOIN periodos p ON p.id=d.periodo_id
    LEFT JOIN departamentos dep ON dep.id=d.departamento_id
    WHERE d.institucion_id=%s
      AND p.institucion_id=d.institucion_id
      AND p.departamento_id IS NOT DISTINCT FROM d.departamento_id
      AND regexp_replace(COALESCE(d.cuil,''), '[^0-9]', '', 'g')=%s
      AND (d.periodo_id=%s OR p.nombre=%s OR (p.anio=%s AND p.semestre=%s))
      AND EXISTS (
          SELECT 1 FROM docentes docx
          WHERE docx.institucion_id=d.institucion_id
            AND docx.departamento_id IS NOT DISTINCT FROM d.departamento_id
            AND regexp_replace(COALESCE(docx.cuil,''), '[^0-9]', '', 'g')=
                regexp_replace(COALESCE(d.cuil,''), '[^0-9]', '', 'g')
      )
    ORDER BY dep.nombre, d.fecha_desde, d.id
"""
FUNCION_INST_V162_SQL = """
    SELECT id, COALESCE(funcion_no_docente, 0) AS funcion_no_docente,
           COALESCE(texto_funcion_no_docente, '') AS texto_funcion_no_docente
    FROM designaciones
    WHERE institucion_id = %s
      AND regexp_replace(COALESCE(cuil,''), '[^0-9]', '', 'g') = %s
"""
HORAS_CONTRATADAS_FALLBACK_SQL = """
    SELECT COALESCE(SUM(d.horas),0) AS horas
    FROM designaciones d
    JOIN periodos p ON p.id=d.periodo_id
    WHERE d.institucion_id=%s
      AND regexp_replace(COALESCE(d.cuil,''), '[^0-9]', '', 'g')=%s
      AND COALESCE(d.estado,'Activa')='Activa'
      AND COALESCE(d.funcion_no_docente, FALSE)=FALSE
      AND (d.periodo_id=%s OR p.nombre=%s OR (p.anio=%s AND p.semestre=%s))
"""
HORARIOS_GLOBAL_SQL = """
    WITH base AS (
        SELECT a.id AS asignacion_id, a.cuil, a.rol, a.comision_id,
               COALESCE(a.usa_horario_personalizado, FALSE) AS personalizado,
               co.departamento_id, dep.nombre AS departamento_comision, co.materia_id,
               p.nombre AS periodo, m.codigo AS codigo_materia, m.asignatura,
               COALESCE(co.materia_especifica, '') AS materia_especifica,
               c.nombre AS carrera, c.escuela, co.nombre_comision, co.turno
        FROM asignaciones_docentes_comision a
        JOIN comisiones co ON co.id=a.comision_id
        LEFT JOIN periodos p ON p.id=co.periodo_id
        LEFT JOIN departamentos dep ON dep.id=co.departamento_id
        LEFT JOIN materias m ON m.id=co.materia_id
        LEFT JOIN carreras c ON c.id=m.carrera_id
        WHERE regexp_replace(COALESCE(a.cuil,''), '[^0-9]', '', 'g')=%s AND co.institucion_id=%s
          AND COALESCE(a.estado,'Activa')='Activa' AND COALESCE(co.estado,'Activa')='Activa'
          AND (co.periodo_id=%s OR p.nombre=%s OR (p.anio=%s AND p.semestre=%s)) {filtro_ex}
    ), reales AS (
        SELECT b.*, ha.dia, ha.hora_inicio, ha.hora_fin, ha.horas
        FROM base b JOIN horarios_asignacion_docente_comision ha ON ha.asignacion_id=b.asignacion_id
        WHERE b.personalizado=TRUE
        UNION ALL
        SELECT b.*, h.dia, h.hora_inicio, h.hora_fin, h.horas
        FROM base b JOIN horarios_comision h ON h.comision_id=b.comision_id
        WHERE b.personalizado=FALSE
    )
    SELECT * FROM reales
    ORDER BY CASE dia WHEN 'Lunes' THEN 1 WHEN 'Martes' THEN 2 WHEN 'Miércoles' THEN 3 WHEN 'Jueves' THEN 4 WHEN 'Viernes' THEN 5 WHEN 'Sábado' THEN 6 WHEN 'Domingo' THEN 7 ELSE 99 END,
             hora_inicio, departamento_comision, codigo_materia, nombre_comision
"""
HORARIOS_HISTORICOS_SQL = """
    SELECT DISTINCT
        a.id AS asignacion_id, a.cuil, COALESCE(a.estado,'Activa') AS estado_asignacion,
        COALESCE(a.horas_asignadas,0) AS horas_asignadas,
        co.id AS comision_id, co.departamento_id,
        COALESCE(dep.nombre,'') AS departamento_comision,
        h.dia, h.hora_inicio, h.hora_fin, h.horas
    FROM asignaciones_docentes_comision a
    JOIN comisiones co ON co.id=a.comision_id
    JOIN periodos p ON p.id=co.periodo_id
    JOIN horarios_comision h ON h.comision_id=co.id
    LEFT JOIN departamentos dep ON dep.id=co.departamento_id
    WHERE {filtros}
    ORDER BY h.dia, h.hora_inicio, co.id
"""
PORCENTAJES_SQL = """
    SELECT departamento_id, COALESCE(porcentaje_horas_no_lectivas,0) AS porcentaje
    FROM config_productividad_departamento
    WHERE institucion_id=%s
"""
PORCENTAJE_DEP_SQL = """SELECT porcentaje_horas_no_lectivas
                   FROM config_productividad_departamento
                   WHERE institucion_id=%s AND departamento_id=%s
                   LIMIT 1"""
CONTEO_DOCENTES_SQL = """
    SELECT a.comision_id,
           COUNT(DISTINCT regexp_replace(COALESCE(a.cuil,''), '[^0-9]', '', 'g')) AS docentes
    FROM asignaciones_docentes_comision a
    JOIN comisiones co ON co.id = a.comision_id
    WHERE co.institucion_id = %s
      AND a.comision_id IN ({placeholders})
      AND COALESCE(a.estado, 'Activa') = 'Activa'
      AND COALESCE(co.estado, 'Activa') = 'Activa'
      AND COALESCE(a.cuil, '') <> ''
    GROUP BY a.comision_id
"""
PROYECTOS_TODOS_SQL = """
    {cte}
    SELECT i.id, i.proyecto_id, i.periodo_id, p.nombre AS periodo,
        p.anio AS periodo_anio, p.semestre AS periodo_semestre, i.cuil,
        COALESCE(doc.docente, i.cuil) AS docente,
        COALESCE(NULLIF(pr.nombre_proyecto, ''), i.nombre_proyecto, '') AS nombre_proyecto,
        COALESCE(NULLIF(pr.codigo_proyecto, ''), i.codigo_proyecto, '') AS codigo_proyecto,
        COALESCE(NULLIF(pr.instituto_proyecto, ''), i.instituto_proyecto, '') AS instituto_proyecto,
        i.rol, COALESCE(pr.anio_llamado, i.anio_llamado) AS anio_llamado,
        pr.fecha_inicio, pr.fecha_fin,
        COALESCE(NULLIF(pr.periodo_ejecucion, ''), i.periodo_ejecucion, '') AS periodo_ejecucion,
        COALESCE(pr.estado, 'Activo') AS estado_proyecto,
        COALESCE(i.estado_asignacion, 'Activa') AS estado_asignacion,
        i.horas_asignadas, i.observaciones, i.fecha_carga, i.fecha_baja,
        COALESCE(i.motivo_baja, '') AS motivo_baja,
        i.departamento_id AS departamento_asignacion_id,
        COALESCE(dep.nombre, '') AS departamento_asignacion
    FROM {tabla} i
    JOIN periodos p ON p.id = i.periodo_id
    {join_ref}
    LEFT JOIN {tabla_proyectos} pr ON pr.id = i.proyecto_id
    LEFT JOIN departamentos dep ON dep.id = i.departamento_id
    LEFT JOIN LATERAL (
        SELECT
            CASE
                WHEN d.apellido IS NOT NULL AND d.nombres IS NOT NULL
                    THEN d.apellido || ', ' || d.nombres
                WHEN d.nombre IS NOT NULL THEN d.nombre
                ELSE i.cuil
            END AS docente
        FROM docentes d
        WHERE d.institucion_id = i.institucion_id
          AND regexp_replace(COALESCE(d.cuil,''), '[^0-9]', '', 'g') = regexp_replace(COALESCE(i.cuil,''), '[^0-9]', '', 'g')
        ORDER BY
            CASE WHEN d.departamento_id IS NOT DISTINCT FROM i.departamento_id THEN 0 ELSE 1 END,
            d.id
        LIMIT 1
    ) doc ON TRUE
    {where}
    ORDER BY COALESCE(p.anio,0) DESC, COALESCE(p.semestre,0) DESC,
             departamento_asignacion, docente, nombre_proyecto
"""
PERIODO_REF_CTE = """
    WITH periodo_ref AS (
        SELECT id, institucion_id, nombre, anio, semestre
        FROM periodos
        WHERE id = %s
        LIMIT 1
    )
"""
UPDATE_HORAS_PROYECTO_SQL = "UPDATE {tabla} SET horas_asignadas=%s WHERE id=%s AND institucion_id=%s"
CUILES_CON_PROYECTOS_SQL = """
    WITH pref AS (
        SELECT nombre, anio, semestre
        FROM periodos
        WHERE id=%s AND institucion_id=%s
        LIMIT 1
    ), px AS (
        SELECT i.cuil, i.periodo_id, i.institucion_id
        FROM investigacion_docente i
        WHERE i.institucion_id=%s AND COALESCE(i.estado_asignacion,'Activa')='Activa'
        UNION ALL
        SELECT e.cuil, e.periodo_id, e.institucion_id
        FROM extension_docente e
        WHERE e.institucion_id=%s AND COALESCE(e.estado_asignacion,'Activa')='Activa'
    )
    SELECT DISTINCT regexp_replace(COALESCE(px.cuil,''), '[^0-9]', '', 'g') AS cuil_key
    FROM px
    JOIN periodos p ON p.id=px.periodo_id AND p.institucion_id=px.institucion_id
    CROSS JOIN pref
    WHERE (COALESCE(p.nombre,'')=COALESCE(pref.nombre,'') OR (p.anio=pref.anio AND p.semestre=pref.semestre))
      AND regexp_replace(COALESCE(px.cuil,''), '[^0-9]', '', 'g') = ANY(%s)
"""


def _raw(u, sql, params) -> pd.DataFrame:
    return u.read(lambda repo: repo.read_raw(sql, params))


# ------------------------------------------------------------------------------------------ designaciones
def _sanear_designaciones_institucionales_v265(df):
    """l. 34653: depura la vista consolidada institucional (sin escribir)."""
    import re
    if df is None:
        return pd.DataFrame()
    out = df.copy()
    if out.empty:
        return out
    if "cargo" in out.columns:
        def _cargo_valido_v265(valor):
            raw = R.limpiar_texto_tabla(valor)
            if not raw:
                return False
            if re.search(r"\b20\d{2}\s*[-/]\s*[12]\b", raw):
                return False
            if re.search(r"\b20\d{2}-\d{2}-\d{2}\b", raw):
                return False
            canon = R.normalizar_cargo_para_jerarquia(raw)
            if canon not in CARGOS:
                return False
            raw_key = R.normalizar_clave(raw)
            canon_key = R.normalizar_clave(canon)
            if raw_key != canon_key:
                tokens_prohibidos = [R.normalizar_clave(x) for x in (DEDICACIONES + TIPOS_DESIGNACION)]
                if any(tok and re.search(rf"(^| )%s($| )" % re.escape(tok), raw_key) for tok in tokens_prohibidos):
                    return False
            return True
        out = out[out["cargo"].map(_cargo_valido_v265)].copy()
    if out.empty:
        return out

    def _serie_texto(col, default=""):
        if col in out.columns:
            return out[col].fillna(default).astype(str).map(R.limpiar_texto_tabla)
        return pd.Series(default, index=out.index, dtype=str)
    dep_nombre = _serie_texto("departamento")
    if "departamento_id" in out.columns:
        dep_id = pd.to_numeric(out["departamento_id"], errors="coerce")
    else:
        dep_id = pd.Series(float("nan"), index=out.index)
    out["_v265_dep_key"] = [
        R.normalizar_clave(nom) if R.normalizar_clave(nom) else (f"id:{int(did)}" if pd.notna(did) else "sin_departamento")
        for nom, did in zip(dep_nombre.tolist(), dep_id.tolist())
    ]
    out["_v265_cargo_key"] = _serie_texto("cargo").map(lambda x: R.normalizar_clave(R.normalizar_cargo_para_jerarquia(x)))
    out["_v265_dedic_key"] = _serie_texto("dedicacion").map(R.normalizar_clave)
    out["_v265_tipo_key"] = _serie_texto("tipo_designacion").map(R.normalizar_clave)
    out["_v265_estado_key"] = _serie_texto("estado").map(R.normalizar_clave)
    out["_v265_hs_key"] = pd.to_numeric(out.get("horas", 0), errors="coerce").fillna(0).round(3)
    out["_v265_desde_key"] = _serie_texto("fecha_desde")
    out["_v265_hasta_key"] = _serie_texto("fecha_hasta")
    if "funcion_no_docente" in out.columns:
        out["_v265_nd_key"] = pd.to_numeric(out["funcion_no_docente"], errors="coerce").fillna(0).astype(int)
    else:
        out["_v265_nd_key"] = 0
    claves = ["_v265_dep_key", "_v265_cargo_key", "_v265_dedic_key", "_v265_tipo_key", "_v265_estado_key",
              "_v265_hs_key", "_v265_desde_key", "_v265_hasta_key", "_v265_nd_key"]
    out = out.drop_duplicates(subset=claves, keep="first").copy()
    out = out.drop(columns=[c for c in claves if c in out.columns], errors="ignore")
    return out.reset_index(drop=True)


def designaciones_periodo_institucional_v149(u, cuil, periodo_id) -> pd.DataFrame:
    """v162 l. 34740 -> base l. 31120 + saneamiento v265."""
    if not str(cuil or "").strip() or periodo_id is None:
        df = pd.DataFrame()
    else:
        try:
            nombre_p, anio, semestre = u.lector.periodo_equivalente_pg(periodo_id)
            df = _raw(u, DESIG_INST_V149_SQL, [int(u.inst), R.clave_cuil(cuil), int(periodo_id), nombre_p, int(anio),
                                               int(semestre)])
        except Exception:
            df = pd.DataFrame()
    if df is None:
        return pd.DataFrame()
    out = df.copy()
    if out.empty:
        if "funcion_no_docente" not in out.columns:
            out["funcion_no_docente"] = pd.Series(dtype=int)
        return out
    try:
        extra = _raw(u, FUNCION_INST_V162_SQL, [int(u.inst), R.clave_cuil(cuil)])
        out = out.drop(columns=["funcion_no_docente", "texto_funcion_no_docente"], errors="ignore").merge(extra, on="id", how="left")
    except Exception:
        out["funcion_no_docente"] = 0
        out["texto_funcion_no_docente"] = ""
    out["funcion_no_docente"] = pd.to_numeric(out.get("funcion_no_docente", 0), errors="coerce").fillna(0).astype(int)
    if "texto_funcion_no_docente" not in out.columns:
        out["texto_funcion_no_docente"] = ""
    out["texto_funcion_no_docente"] = out["texto_funcion_no_docente"].fillna("").astype(str)
    return _sanear_designaciones_institucionales_v265(out)


def _foto_v183(u, df, periodo_id):
    """``_filtrar_foto_designaciones_v169`` efectiva (v183)."""
    return filtrar_foto_v183(df, u.lector.es_historico(periodo_id), u.lector.periodo_info(periodo_id))


def designaciones_docente_contexto_v182(u, cuil, periodo_id) -> pd.DataFrame:
    """l. 39417 (institucional)."""
    try:
        df = designaciones_periodo_institucional_v149(u, cuil, periodo_id)
        df = _foto_v183(u, df, periodo_id)
        if df is None or df.empty:
            return pd.DataFrame()
        no_doc = df.get("funcion_no_docente", pd.Series(0, index=df.index)).map(es_funcion_no_docente)
        return df[~no_doc].copy().reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


def horas_contratadas_docencia_institucional_v184(u, cuil, periodo_id) -> float:
    try:
        df = designaciones_docente_contexto_v182(u, cuil, int(periodo_id))
        if isinstance(df, pd.DataFrame) and not df.empty:
            return round(float(pd.to_numeric(df.get("horas", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()), 2)
    except Exception:
        pass
    try:
        nombre_p, anio_p, semestre_p = u.lector.periodo_equivalente_pg(int(periodo_id))
        df = _raw(u, HORAS_CONTRATADAS_FALLBACK_SQL, [int(u.inst), R.clave_cuil(cuil), int(periodo_id), nombre_p,
                                                      int(anio_p), int(semestre_p)])
        if not df.empty:
            return round(float(df.iloc[0].get("horas") or 0), 2)
    except Exception:
        pass
    return 0.0


# ------------------------------------------------------------------------------------------ horarios del docente
def horarios_docente_periodo_pg_global(u, cuil, periodo_id, excluir_comision_id=None) -> pd.DataFrame:
    """l. 30526."""
    try:
        periodo_nombre, anio, semestre = u.lector.periodo_equivalente_pg(periodo_id)
        filtro_ex = " AND co.id <> %s" if excluir_comision_id is not None else ""
        params = [R.clave_cuil(cuil), int(u.inst), int(periodo_id), periodo_nombre, int(anio), int(semestre)]
        if excluir_comision_id is not None:
            params.append(int(excluir_comision_id))
        return _raw(u, HORARIOS_GLOBAL_SQL.replace("{filtro_ex}", filtro_ex), params)
    except Exception:
        return pd.DataFrame()


def horarios_docente_historicos_v182(u, cuil, periodo_id, todos_departamentos=True) -> pd.DataFrame:
    """l. 39358."""
    if not str(cuil or "").strip():
        return pd.DataFrame()
    try:
        nombre_p, anio, semestre = u.lector.periodo_equivalente_pg(periodo_id)
        filtros = ["a.institucion_id=%s", "regexp_replace(COALESCE(a.cuil,''), '[^0-9]', '', 'g')=%s",
                   "(co.periodo_id=%s OR p.nombre=%s OR (p.anio=%s AND p.semestre=%s))"]
        params = [int(u.inst), R.clave_cuil(cuil), int(periodo_id), nombre_p, int(anio), int(semestre)]
        if not todos_departamentos:
            filtros.append("co.departamento_id=%s")
            params.append(int(u.dep))
        return _raw(u, HORARIOS_HISTORICOS_SQL.replace("{filtros}", " AND ".join(filtros)), params)
    except Exception:
        return pd.DataFrame()


def horas_comisiones_institucional_v184(u, cuil, periodo_id) -> float:
    try:
        if u.lector.es_historico(int(periodo_id)):
            df_h = horarios_docente_historicos_v182(u, cuil, int(periodo_id), todos_departamentos=True)
        else:
            df_h = horarios_docente_periodo_pg_global(u, cuil, int(periodo_id))
        return round(float(R.calcular_horas_unicas_desde_horarios_df(df_h) or 0), 2)
    except Exception:
        return 0.0


# ------------------------------------------------------------------------------------------ horas no lectivas
def _porcentajes_no_lectivos_departamentos_v149(u) -> dict:
    try:
        df = _raw(u, PORCENTAJES_SQL, [int(u.inst)])
        return {int(r.get("departamento_id")): float(r.get("porcentaje") or 0)
                for _, r in df.iterrows() if pd.notna(r.get("departamento_id"))}
    except Exception:
        return {}


def _porcentaje_horas_no_lectivas_v148(u) -> float:
    try:
        df = _raw(u, PORCENTAJE_DEP_SQL, [int(u.inst), int(u.dep)])
        if df is None or df.empty:
            return 0.0
        valor = float(pd.to_numeric(df.iloc[0].get("porcentaje_horas_no_lectivas"), errors="coerce") or 0)
        return max(0.0, min(valor, 200.0))
    except Exception:
        return 0.0


def _conteo_docentes_activos_por_comision_v151(u, comision_ids) -> dict:
    ids = []
    for valor in list(comision_ids or []):
        try:
            cid = int(valor)
        except Exception:
            continue
        if cid not in ids:
            ids.append(cid)
    if not ids:
        return {}
    try:
        placeholders = ", ".join(["%s"] * len(ids))
        df = _raw(u, CONTEO_DOCENTES_SQL.replace("{placeholders}", placeholders), [int(u.inst)] + ids)
        if df is None or df.empty:
            return {}
        return {int(r.get("comision_id")): max(int(r.get("docentes") or 0), 0)
                for _, r in df.iterrows() if pd.notna(r.get("comision_id"))}
    except Exception:
        return {}


def _horas_no_lectivas_v151(u, cuil, periodo_id, df_h) -> float:
    """``_calcular_horas_no_lectivas_institucional_v151`` (l. 31625): solo el total."""
    if df_h is None or df_h.empty or "comision_id" not in df_h.columns:
        return 0.0
    porcentajes = _porcentajes_no_lectivos_departamentos_v149(u)
    ids = pd.to_numeric(df_h["comision_id"], errors="coerce").dropna().astype(int).unique().tolist()
    conteos = _conteo_docentes_activos_por_comision_v151(u, ids)
    total_no_lectivas = 0.0
    for cid, grupo in df_h.groupby("comision_id", dropna=True, sort=True):
        try:
            cid_int = int(cid)
        except Exception:
            continue
        hs_doc = float(R.calcular_horas_unicas_desde_horarios_df(grupo) or 0)
        try:
            dep_id = int(pd.to_numeric(grupo.iloc[0].get("departamento_id"), errors="coerce"))
        except Exception:
            dep_id = None
        pct_base = float(porcentajes.get(dep_id, 0) or 0) if dep_id is not None else 0.0
        cantidad_docentes = int(conteos.get(cid_int, 1) or 1)
        pct_aplicado = pct_base if cantidad_docentes <= 1 else pct_base / 2.0
        total_no_lectivas += round(hs_doc * pct_aplicado / 100.0, 2)
    return round(total_no_lectivas, 2)


def _horas_no_lectivas_historicas_v182(u, cuil, periodo_id) -> float:
    """``_productividad_docente_contexto_v182`` (l. 39435, institucional): solo ``horas_no_lectivas``."""
    df_h = horarios_docente_historicos_v182(u, cuil, periodo_id, todos_departamentos=True)
    horas_nl = 0.0
    if isinstance(df_h, pd.DataFrame) and not df_h.empty and "departamento_id" in df_h.columns:
        mapa_pct = _porcentajes_no_lectivos_departamentos_v149(u)
        for dep_id, g in df_h.groupby("departamento_id", dropna=True):
            try:
                dep_i = int(dep_id)
            except Exception:
                continue
            hs = float(R.calcular_horas_unicas_desde_horarios_df(g) or 0)
            pct = float(mapa_pct.get(dep_i, 0) or 0)
            horas_nl += round(hs * pct / 100.0, 2)
    else:
        com_reales = R.calcular_horas_unicas_desde_horarios_df(df_h) if isinstance(df_h, pd.DataFrame) and not df_h.empty else 0.0
        pct = float(_porcentaje_horas_no_lectivas_v148(u) or 0)
        horas_nl = round(float(com_reales) * pct / 100.0, 2)
    return round(float(horas_nl), 2)


def horas_no_lectivas_institucional_v185(u, cuil, periodo_id) -> float:
    try:
        if u.lector.es_historico(int(periodo_id)):
            return round(float(_horas_no_lectivas_historicas_v182(u, cuil, int(periodo_id)) or 0), 2)
        df_h = horarios_docente_periodo_pg_global(u, cuil, int(periodo_id))
        return round(float(_horas_no_lectivas_v151(u, cuil, int(periodo_id), df_h) or 0), 2)
    except Exception:
        try:
            comisiones = horas_comisiones_institucional_v184(u, cuil, int(periodo_id))
            pct = float(_porcentaje_horas_no_lectivas_v148(u) or 0)
            return round(float(comisiones) * pct / 100.0, 2)
        except Exception:
            return 0.0


# ------------------------------------------------------------------------------------------ asignaciones a proyectos
def _filtrar_asignaciones_proyecto_cierre_v183(u, df, periodo_id) -> pd.DataFrame:
    base = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
    if base.empty or not u.lector.es_historico(periodo_id):
        return base
    ref = u.lector.fecha_cierre(periodo_id)
    if ref is None:
        return base
    carga = base.get("fecha_carga", pd.Series(index=base.index, dtype=object)).apply(lambda x: R.safe_date(x, None))
    baja = base.get("fecha_baja", pd.Series(index=base.index, dtype=object)).apply(lambda x: R.safe_date(x, None))
    estado = base.get("estado_asignacion", pd.Series("Activa", index=base.index)).fillna("Activa").astype(str).str.strip().str.casefold()
    ini_pr = base.get("fecha_inicio", pd.Series(index=base.index, dtype=object)).apply(lambda x: R.safe_date(x, None))
    fin_pr = base.get("fecha_fin", pd.Series(index=base.index, dtype=object)).apply(lambda x: R.safe_date(x, None))
    ok = carga.isna() | (carga <= ref)
    ok &= baja.isna() | (baja >= ref)
    ok &= estado.eq("activa") | (baja.notna() & (baja >= ref))
    ok &= ini_pr.isna() | (ini_pr <= ref)
    ok &= fin_pr.isna() | (fin_pr >= ref)
    return base[ok].copy().reset_index(drop=True)


def _proyectos_docente_todos(u, tipo, cuil, periodo_id, incluir_bajas) -> pd.DataFrame:
    """Rama ``todos_departamentos`` de ``get_investigacion_docente`` / ``get_extension_docente`` (l. 22041 / 23119)."""
    tabla = "investigacion_docente" if tipo == "investigacion" else "extension_docente"
    tabla_proyectos = "proyectos_investigacion" if tipo == "investigacion" else "proyectos_extension"
    filtros = ["i.institucion_id = %s"]
    params_filtros = [int(u.inst)]
    if cuil is not None:
        filtros.append("regexp_replace(COALESCE(i.cuil, ''), '[^0-9]', '', 'g') = %s")
        params_filtros.append(R.clave_cuil(cuil))
    if not incluir_bajas:
        filtros.append("COALESCE(i.estado_asignacion, 'Activa') = 'Activa'")
    where = "WHERE " + " AND ".join(filtros)
    if periodo_id is not None:
        cte = PERIODO_REF_CTE
        join_ref = f"JOIN periodo_ref pref ON {condicion_periodo_equivalente_sql('p', 'pref')}"
        params = [int(periodo_id)] + params_filtros
    else:
        cte, join_ref, params = "", "", params_filtros
    sql = (PROYECTOS_TODOS_SQL.replace("{cte}", cte).replace("{join_ref}", join_ref).replace("{where}", where)
           .replace("{tabla_proyectos}", tabla_proyectos).replace("{tabla}", tabla))
    return _raw(u, sql, params)


def proyectos_docente_v183(u, tipo, cuil, periodo_id) -> pd.DataFrame:
    """``get_investigacion_docente`` / ``get_extension_docente`` efectivas (v183 + base), sin v277 de presentacion."""
    if periodo_id is not None and u.lector.es_historico(periodo_id):
        raw = _proyectos_docente_todos(u, tipo, cuil, periodo_id, incluir_bajas=True)
        return _filtrar_asignaciones_proyecto_cierre_v183(u, raw, periodo_id)
    return _proyectos_docente_todos(u, tipo, cuil, periodo_id, incluir_bajas=False)


def asignaciones_proyectos_docente_v184(u, cuil, periodo_id):
    try:
        df_inv = proyectos_docente_v183(u, "investigacion", cuil, int(periodo_id))
    except Exception:
        df_inv = pd.DataFrame()
    try:
        df_ext = proyectos_docente_v183(u, "extension", cuil, int(periodo_id))
    except Exception:
        df_ext = pd.DataFrame()
    if not isinstance(df_inv, pd.DataFrame):
        df_inv = pd.DataFrame()
    if not isinstance(df_ext, pd.DataFrame):
        df_ext = pd.DataFrame()
    return df_inv.copy(), df_ext.copy()


# ------------------------------------------------------------------------------------------ capacidad y reajuste
def capacidad_proyectos_docente_v184(u, cuil, periodo_id) -> dict:
    """l. 40242 (sin exclusion: el reajuste no la usa)."""
    cuil_txt = str(cuil or "").strip()
    if not cuil_txt or periodo_id is None:
        return {"horas_contratadas": 0.0, "horas_comisiones": 0.0, "horas_no_lectivas": 0.0, "horas_investigacion": 0.0,
                "horas_extension": 0.0, "capacidad_total_proyectos": 0.0, "horas_proyectos_actuales": 0.0,
                "horas_disponibles_proyectos": 0.0, "exceso_proyectos": 0.0}
    contratadas = horas_contratadas_docencia_institucional_v184(u, cuil_txt, int(periodo_id))
    comisiones = horas_comisiones_institucional_v184(u, cuil_txt, int(periodo_id))
    no_lectivas = horas_no_lectivas_institucional_v185(u, cuil_txt, int(periodo_id))
    df_inv, df_ext = asignaciones_proyectos_docente_v184(u, cuil_txt, int(periodo_id))
    hs_inv = float(pd.to_numeric(df_inv.get("horas_asignadas", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) \
        if not df_inv.empty else 0.0
    hs_ext = float(pd.to_numeric(df_ext.get("horas_asignadas", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) \
        if not df_ext.empty else 0.0
    capacidad_total = max(round(float(contratadas) - float(comisiones) - float(no_lectivas), 2), 0.0)
    proyectos_actuales = round(hs_inv + hs_ext, 2)
    disponibles = max(round(capacidad_total - proyectos_actuales, 2), 0.0)
    exceso = max(round(proyectos_actuales - capacidad_total, 2), 0.0)
    return {
        "horas_contratadas": round(float(contratadas), 2), "horas_comisiones": round(float(comisiones), 2),
        "horas_no_lectivas": round(float(no_lectivas), 2), "horas_investigacion": round(float(hs_inv), 2),
        "horas_extension": round(float(hs_ext), 2), "capacidad_total_proyectos": round(float(capacidad_total), 2),
        "horas_proyectos_actuales": proyectos_actuales, "horas_disponibles_proyectos": disponibles,
        "exceso_proyectos": exceso,
    }


def actualizar_horas_proyecto_directo_v184(u, tipo, asignacion_id, nuevas_horas) -> None:
    """l. 40391: writer de negocio anidado (``proyectos.write``), conexion cruda, un COMMIT."""
    tabla = "investigacion_docente" if tipo == "investigacion" else "extension_docente"
    with u.writer(W_HORAS_PROYECTO):
        u.commit(lambda repo: repo._mutate(UPDATE_HORAS_PROYECTO_SQL.replace("{tabla}", tabla),
                                           [_numeric(round(float(nuevas_horas), 2)), int(asignacion_id), int(u.inst)]))


def reconciliar_horas_proyectos_por_comisiones_v184(u, cuil, periodo_id) -> list:
    """l. 40421: los proyectos ocupan solo el remanente que dejan las comisiones."""
    if not cuil or periodo_id is None:
        return []
    cap = capacidad_proyectos_docente_v184(u, cuil, int(periodo_id))
    exceso = round(float(cap.get("exceso_proyectos", 0) or 0), 2)
    if exceso <= 1e-9:
        return []
    df_inv, df_ext = asignaciones_proyectos_docente_v184(u, cuil, int(periodo_id))
    filas = []
    for tipo, df in [("investigacion", df_inv), ("extension", df_ext)]:
        if df is None or df.empty:
            continue
        for _, r in df.iterrows():
            try:
                aid = int(r.get("id"))
            except Exception:
                continue
            horas = float(pd.to_numeric(pd.Series([r.get("horas_asignadas")]), errors="coerce").fillna(0).iloc[0])
            if horas <= 0:
                continue
            filas.append({"tipo": tipo, "id": aid, "horas": horas, "fecha_carga": str(r.get("fecha_carga") or ""),
                          "proyecto": str(r.get("nombre_proyecto") or r.get("codigo_proyecto") or f"ID {aid}"),
                          "departamento": str(r.get("departamento_asignacion") or "")})
    filas.sort(key=lambda x: (x.get("fecha_carga", ""), int(x.get("id", 0))), reverse=True)
    restante = exceso
    cambios = []
    for fila in filas:
        if restante <= 1e-9:
            break
        antes = round(float(fila["horas"]), 2)
        reduccion = min(antes, restante)
        despues = max(round(antes - reduccion, 2), 0.0)
        if abs(despues - antes) <= 1e-9:
            continue
        actualizar_horas_proyecto_directo_v184(u, fila["tipo"], fila["id"], despues)
        restante = max(round(restante - reduccion, 2), 0.0)
        cambios.append({"tipo": fila["tipo"], "id": fila["id"], "cuil": str(cuil), "proyecto": fila["proyecto"],
                        "departamento": fila.get("departamento", ""), "horas_antes": antes, "horas_despues": despues,
                        "reduccion": round(reduccion, 2), "periodo_id": int(periodo_id)})
    return cambios


def cuiles_con_proyectos_periodo_v232(u, cuiles, periodo_id) -> set:
    """l. 52194: solo CUIL con proyectos en el periodo academico equivalente."""
    claves = sorted({R.clave_cuil(x) for x in list(cuiles or []) if R.clave_cuil(x)})
    if not claves:
        return set()
    inst = int(u.inst or 0)
    if inst <= 0:
        return set()
    df = _raw(u, CUILES_CON_PROYECTOS_SQL, [int(periodo_id), inst, inst, inst, claves])
    return {str(x) for x in df.get("cuil_key", pd.Series(dtype=str)).tolist() if x}
