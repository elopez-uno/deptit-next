"""Plantel historico para Comisiones (``get_plantel_periodo`` v191 -> v183 l. 40051 -> v182 l. 39559 -> v174 l. 37132
-> l. 26936 -> l. 4645) y la rama historica de ``get_docentes_activos_para_comisiones`` v182 (l. 39671).

Solo lectura.  La reparacion v212 que ``get_designaciones`` ejecuta al leer queda excluida (decision aprobada: las
lecturas no escriben).  ``_prestados_recibidos_periodo_v175`` efectivo = v183 (l. 39846) sobre la base l. 37327.
"""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from designaciones.rules import condicion_periodo_equivalente_sql, es_funcion_no_docente, horas_segun_dedicacion
from docentes.rules import departamento_origen_desde_obs_prestado, nombre_completo

from . import rules as R

COLS_PLANTEL = ["cuil", "legajo", "nombre_completo", "titulo", "titulo_posgrado", "email", "telefono",
                "tipo_docente", "estado_operativo_periodo", "fecha_alta_periodo", "fecha_finalizacion_periodo",
                "designaciones_del_periodo", "designaciones_activas", "horas_activas",
                "horas_registradas_periodo", "detalle_designaciones"]

# l. 4645 con el inyector B12B (tools_comisiones_inject_sql.py): params [inst, dep, periodo, inst, dep].
PLANTEL_BASE_SQL = """
        SELECT
            doc.cuil,
            doc.legajo,
            CASE
                WHEN doc.apellido IS NOT NULL AND doc.nombres IS NOT NULL THEN doc.apellido || ', ' || doc.nombres
                WHEN doc.nombre IS NOT NULL THEN doc.nombre
                ELSE ''
            END AS nombre_completo,
            doc.titulo,
            COALESCE(doc.titulo_posgrado, '') AS titulo_posgrado,
            doc.email,
            doc.telefono,
            COALESCE(doc.tipo_docente, 'Propio') AS tipo_docente,
            CASE
                WHEN SUM(
                    CASE
                        WHEN d.estado = 'Activa'
                         AND COALESCE((SELECT p2.estado FROM periodos p2 WHERE p2.id = d.periodo_id), '') <> 'Cerrado'
                        THEN 1 ELSE 0
                    END
                ) > 0
                    THEN 'Activo en el período'
                ELSE 'Finalizado / sin designación activa'
            END AS estado_operativo_periodo,
            MIN(d.fecha_desde) AS fecha_alta_periodo,
            MAX(d.fecha_hasta) AS fecha_finalizacion_periodo,
            COUNT(d.id) AS designaciones_del_periodo,
            SUM(
                CASE
                    WHEN d.estado = 'Activa'
                     AND COALESCE((SELECT p3.estado FROM periodos p3 WHERE p3.id = d.periodo_id), '') <> 'Cerrado'
                    THEN 1 ELSE 0
                END
            ) AS designaciones_activas,
            SUM(
                CASE
                    WHEN d.estado = 'Activa'
                     AND COALESCE((SELECT p4.estado FROM periodos p4 WHERE p4.id = d.periodo_id), '') <> 'Cerrado'
                    THEN COALESCE(d.horas, 0) ELSE 0
                END
            ) AS horas_activas,
            SUM(COALESCE(d.horas, 0)) AS horas_registradas_periodo,
            STRING_AGG((d.cargo || ' - ' || d.dedicacion || ' - ' || d.horas || ' hs - ' ||
                d.tipo_designacion || ' - Ad Honorem: ' || COALESCE(d.ad_honorem, 'No') ||
                ' - Estado: ' ||
                CASE
                    WHEN COALESCE((SELECT p5.estado FROM periodos p5 WHERE p5.id = d.periodo_id), '') = 'Cerrado'
                     AND d.estado = 'Activa'
                    THEN 'Finalizada'
                    ELSE COALESCE(d.estado, '')
                END)::text, ' | ' ORDER BY d.id) AS detalle_designaciones
        FROM designaciones d
        LEFT JOIN docentes doc ON (d.cuil = doc.cuil) AND (doc.institucion_id = %s) AND (doc.departamento_id = %s)
        WHERE d.periodo_id = %s AND (d.institucion_id = %s) AND (d.departamento_id = %s) GROUP BY
            doc.cuil, doc.legajo, doc.apellido, doc.nombres, doc.nombre,
            doc.titulo, doc.titulo_posgrado, doc.email, doc.telefono, doc.tipo_docente
        ORDER BY doc.apellido, doc.nombres
"""
# l. 26945 inyectado: params [inst, dep].
PRESTADOS_LOCALES_SQL = """
            SELECT
                doc.cuil,
                doc.legajo,
                CASE
                    WHEN doc.apellido IS NOT NULL AND doc.nombres IS NOT NULL THEN doc.apellido || ', ' || doc.nombres
                    WHEN doc.nombre IS NOT NULL THEN doc.nombre
                    ELSE ''
                END AS nombre_completo,
                doc.titulo,
                COALESCE(doc.titulo_posgrado, '') AS titulo_posgrado,
                doc.email,
                doc.telefono,
                COALESCE(doc.tipo_docente, 'Propio') AS tipo_docente,
                doc.fecha_alta,
                COALESCE(doc.observaciones, '') AS observaciones
            FROM docentes doc
            WHERE COALESCE(doc.estado, 'Activo') = 'Activo'
              AND COALESCE(doc.tipo_docente, 'Propio') = 'Prestado' AND (doc.institucion_id = %s) AND (doc.departamento_id = %s) ORDER BY doc.apellido, doc.nombres
"""
# l. 6342 rama PG (``_pg_read_dataframe``, sin inyector; tal cual el certificado).
DESIG_TODOS_DEPS_SQL = f"""
            WITH pr AS (
                SELECT id, institucion_id, nombre, anio, semestre
                FROM periodos
                WHERE id = %s
                LIMIT 1
            )
            SELECT
                d.id, d.periodo_id, d.departamento_id, d.cargo, d.dedicacion, d.horas, d.tipo_designacion,
                COALESCE(d.numero_resolucion, '') AS numero_resolucion,
                d.fecha_desde, d.fecha_hasta, d.estado, dep.nombre AS departamento
            FROM designaciones d
            JOIN periodos p ON p.id = d.periodo_id
            JOIN pr ON {condicion_periodo_equivalente_sql('p', 'pr')}
            LEFT JOIN departamentos dep ON dep.id = d.departamento_id
            WHERE regexp_replace(COALESCE(d.cuil, ''), '[^0-9]', '', 'g') = %s
            ORDER BY dep.nombre, d.tipo_designacion, d.cargo, d.dedicacion, d.id
"""
COLS_DESIG_TODOS = ["id", "periodo_id", "departamento_id", "cargo", "dedicacion", "horas",
                    "tipo_designacion", "numero_resolucion", "fecha_desde", "fecha_hasta", "estado", "departamento"]
IDENTIDAD_37132_SQL = """
                    SELECT doc.cuil, doc.legajo, doc.apellido, doc.nombres, doc.nombre, doc.titulo,
                           COALESCE(doc.titulo_posgrado,'') AS titulo_posgrado, doc.email, doc.telefono
                    FROM docentes doc
                    WHERE doc.institucion_id=%s AND doc.cuil=%s
                    ORDER BY CASE WHEN doc.departamento_id=%s THEN 0 ELSE 1 END, doc.id
                    LIMIT 1
"""
IDENTIDAD_V182_SQL = """
                SELECT doc.cuil, doc.legajo, doc.apellido, doc.nombres, doc.nombre,
                       doc.titulo, COALESCE(doc.titulo_posgrado,'') AS titulo_posgrado,
                       doc.email, doc.telefono
                FROM docentes doc
                WHERE doc.institucion_id=%s
                  AND regexp_replace(COALESCE(doc.cuil,''), '[^0-9]', '', 'g')=%s
                ORDER BY CASE WHEN doc.departamento_id=%s THEN 0 ELSE 1 END, doc.id
                LIMIT 1
"""
# l. 37327 (rama PG).
V175_PERIODO_SQL = "SELECT id, anio, semestre, estado FROM periodos WHERE id=%s AND institucion_id=%s AND departamento_id=%s LIMIT 1"
V175_ASIG_SQL = """
            SELECT DISTINCT a.cuil, COALESCE(a.estado,'Activa') AS estado_asignacion
            FROM asignaciones_docentes_comision a
            JOIN comisiones co
              ON co.id=a.comision_id
             AND co.institucion_id=a.institucion_id
             AND co.departamento_id=a.departamento_id
            WHERE co.institucion_id=%s AND co.departamento_id=%s AND co.periodo_id=%s
              AND COALESCE(TRIM(a.cuil),'')<>''
"""
V175_DOC_SQL = """
            SELECT cuil,
                   CASE WHEN apellido IS NOT NULL AND nombres IS NOT NULL THEN apellido || ', ' || nombres
                        WHEN nombre IS NOT NULL THEN nombre ELSE cuil END AS docente,
                   COALESCE(tipo_docente,'Propio') AS tipo_docente,
                   COALESCE(observaciones,'') AS observaciones
            FROM docentes
            WHERE institucion_id=%s AND departamento_id=%s
"""
V175_LOCAL_DES_SQL = """
            SELECT DISTINCT cuil
            FROM designaciones
            WHERE institucion_id=%s AND departamento_id=%s AND periodo_id=%s
              AND COALESCE(funcion_no_docente,0)=0
              AND COALESCE(TRIM(cuil),'')<>''
"""
V175_OTRAS_DES_SQL = """
            SELECT DISTINCT d.cuil, dep.nombre AS departamento_origen
            FROM designaciones d
            JOIN periodos p
              ON p.id=d.periodo_id AND p.institucion_id=d.institucion_id AND p.departamento_id=d.departamento_id
            JOIN departamentos dep
              ON dep.id=d.departamento_id AND dep.institucion_id=d.institucion_id
            WHERE d.institucion_id=%s AND d.departamento_id<>%s
              AND p.anio=%s AND p.semestre=%s
              AND COALESCE(d.funcion_no_docente,0)=0
              AND COALESCE(TRIM(d.cuil),'')<>''
"""
V175_PR_SQL = """
                SELECT cuil, COALESCE(departamento_origen,'') AS departamento_origen,
                       COALESCE(estado,'Activo') AS estado
                FROM prestamos_docentes
                WHERE institucion_id=%s AND departamento_id=%s AND periodo_id=%s
"""
V175_MOV_SQL = """
            SELECT DISTINCT cuil
            FROM movimientos
            WHERE institucion_id=%s AND departamento_id=%s AND periodo_id=%s
              AND LOWER(TRIM(COALESCE(tipo_movimiento,'')))='alta de docente prestado'
              AND COALESCE(TRIM(cuil),'')<>''
"""
V175_COLS = ["cuil", "docente", "departamento_origen", "evidencia", "estado_asignacion"]


def fecha_prestamo_texto_v179(valor):
    """domain/designaciones.py l. 300."""
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except Exception:
        pass
    if isinstance(valor, (date, datetime)):
        try:
            return valor.strftime("%Y-%m-%d")
        except Exception:
            return str(valor)
    txt = str(valor).strip()
    if not txt or txt.casefold() in {"none", "nan", "nat"}:
        return ""
    return txt


def horas_designaciones_v165(df):
    """domain/catalog_unlocked/designaciones.py l. 41."""
    if df is None or df.empty:
        return 0.0
    total = 0.0
    for _, r in df.iterrows():
        try:
            total += float(horas_segun_dedicacion(r.get("dedicacion"), r.get("horas", 0)) or 0)
        except Exception:
            try:
                total += float(pd.to_numeric(r.get("horas"), errors="coerce") or 0)
            except Exception:
                pass
    return round(total, 2)


def _claves(df) -> set:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return set()
    return {x for x in df.get("cuil", pd.Series(dtype=str)).fillna("").astype(str).map(R.clave_cuil).tolist() if x}


class PlantelMixin:
    """Metodos del ``Lector`` (``self.repo`` = ``ComisionesRepository``)."""

    # ------------------------------------------------------------------ designaciones del departamento
    def designaciones_periodo_df(self, periodo_id) -> pd.DataFrame:
        """``get_designaciones(periodo_id)`` efectiva (v95 + v162), sin la reparacion v212 al leer."""
        df = pd.DataFrame(self.repo.designaciones(int(periodo_id)))
        if "horas" in df.columns:
            df["horas"] = pd.to_numeric(df["horas"], errors="coerce")
        if df.empty:
            for col in ("funcion_no_docente", "texto_funcion_no_docente"):
                if col not in df.columns:
                    df[col] = pd.Series(dtype=int if col == "funcion_no_docente" else str)
            return df
        df["funcion_no_docente"] = pd.to_numeric(df.get("funcion_no_docente", 0), errors="coerce").fillna(0).astype(int)
        df["texto_funcion_no_docente"] = df["texto_funcion_no_docente"].fillna("").astype(str)
        return df

    def designaciones_funcionales_analisis_v169(self, periodo_id):
        """l. 36487."""
        from designaciones.rules import filtrar_foto_v183
        try:
            base = self.designaciones_periodo_df(int(periodo_id))
        except Exception:
            base = pd.DataFrame()
        base = filtrar_foto_v183(base, self.es_historico(periodo_id), self.periodo_info(periodo_id))
        if base is None:
            base = pd.DataFrame()
        if base.empty:
            for col, dtype in [("funcion_no_docente", int), ("texto_funcion_no_docente", str),
                               ("cuil", str), ("estado", str), ("horas", float)]:
                if col not in base.columns:
                    base[col] = pd.Series(dtype=dtype)
            return base.copy(), base.copy(), base.copy()
        if "funcion_no_docente" not in base.columns:
            base["funcion_no_docente"] = 0
        if "texto_funcion_no_docente" not in base.columns:
            base["texto_funcion_no_docente"] = ""
        base["funcion_no_docente"] = base["funcion_no_docente"].map(lambda x: 1 if es_funcion_no_docente(x) else 0)
        base["texto_funcion_no_docente"] = base["texto_funcion_no_docente"].fillna("").astype(str)
        df_no_doc = base[base["funcion_no_docente"].eq(1)].copy()
        df_doc = base[base["funcion_no_docente"].eq(0)].copy()
        return df_doc.reset_index(drop=True), df_no_doc.reset_index(drop=True), base.reset_index(drop=True)

    def designaciones_docentes_institucionales_v169(self, cuil, periodo_id) -> pd.DataFrame:
        """l. 36517 (== ``_designaciones_docente_contexto_v182`` del reajuste v184)."""
        from .lecturas import _LectorComoUnidad
        from .proyectos import designaciones_docente_contexto_v182
        return designaciones_docente_contexto_v182(_LectorComoUnidad(self), cuil, periodo_id)

    def designaciones_todos_departamentos(self, cuil, periodo_id) -> pd.DataFrame:
        """l. 6342."""
        try:
            df = self.repo.read_raw(DESIG_TODOS_DEPS_SQL, [int(periodo_id), R.clave_cuil(cuil)])
        except Exception:
            df = pd.DataFrame(columns=COLS_DESIG_TODOS)
        for col in COLS_DESIG_TODOS:
            if col not in df.columns:
                df[col] = ""
        return df[COLS_DESIG_TODOS]

    # ------------------------------------------------------------------ prestamos
    def filtrar_prestamos_cierre_v183(self, df, periodo_id):
        base = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
        if base.empty or not self.es_historico(periodo_id):
            return base
        ref = self.fecha_cierre(periodo_id)
        if ref is None:
            return base
        desde = base.get("fecha_desde", pd.Series(index=base.index, dtype=object)).apply(lambda x: R.safe_date(x, None))
        hasta = base.get("fecha_hasta", pd.Series(index=base.index, dtype=object)).apply(lambda x: R.safe_date(x, None))
        ok = (desde.isna() | (desde <= ref)) & (hasta.isna() | (hasta >= ref))
        return base[ok].copy().reset_index(drop=True)

    def _prestados_recibidos_base_v175(self, periodo_id) -> pd.DataFrame:
        """l. 37327 (rama PostgreSQL)."""
        if periodo_id is None:
            return pd.DataFrame(columns=V175_COLS)
        try:
            inst_id, dep_id = int(self.repo.inst), int(self.repo.dep)
            raw = self.repo.read_raw
            df_per = raw(V175_PERIODO_SQL, [int(periodo_id), inst_id, dep_id])
            if df_per.empty:
                return pd.DataFrame(columns=V175_COLS)
            anio = int(df_per.iloc[0].get("anio")); semestre = int(df_per.iloc[0].get("semestre"))
            df_asig = raw(V175_ASIG_SQL, [inst_id, dep_id, int(periodo_id)])
            if df_asig.empty:
                return pd.DataFrame(columns=V175_COLS)
            mapa_doc = {}
            for _, r in raw(V175_DOC_SQL, [inst_id, dep_id]).iterrows():
                k = R.clave_cuil(r.get("cuil"))
                if k:
                    mapa_doc[k] = r.to_dict()
            df_local_des = raw(V175_LOCAL_DES_SQL, [inst_id, dep_id, int(periodo_id)])
            claves_local_des = {R.clave_cuil(x) for x in df_local_des.get("cuil", pd.Series(dtype=str)).tolist() if R.clave_cuil(x)}
            origenes_otros = {}
            for _, r in raw(V175_OTRAS_DES_SQL, [inst_id, dep_id, anio, semestre]).iterrows():
                k = R.clave_cuil(r.get("cuil")); dep = str(r.get("departamento_origen") or "").strip()
                if not k:
                    continue
                origenes_otros.setdefault(k, [])
                if dep and dep not in origenes_otros[k]:
                    origenes_otros[k].append(dep)
            try:
                df_pr = raw(V175_PR_SQL, [inst_id, dep_id, int(periodo_id)])
            except Exception:
                df_pr = pd.DataFrame()
            mapa_pr = {}
            for _, r in df_pr.iterrows():
                k = R.clave_cuil(r.get("cuil"))
                if k:
                    mapa_pr[k] = r.to_dict()
            df_mov_pr = raw(V175_MOV_SQL, [inst_id, dep_id, int(periodo_id)])
            claves_mov_pr = {R.clave_cuil(x) for x in df_mov_pr.get("cuil", pd.Series(dtype=str)).tolist() if R.clave_cuil(x)}
            estados_por_clave, cuil_original = {}, {}
            for _, r in df_asig.iterrows():
                k = R.clave_cuil(r.get("cuil"))
                if not k:
                    continue
                cuil_original.setdefault(k, str(r.get("cuil") or "").strip())
                estados_por_clave.setdefault(k, [])
                est = str(r.get("estado_asignacion") or "").strip()
                if est and est not in estados_por_clave[k]:
                    estados_por_clave[k].append(est)
            registros = []
            for k in sorted(cuil_original.keys()):
                doc = mapa_doc.get(k, {})
                tipo_local = str(doc.get("tipo_docente") or "").strip().casefold()
                tiene_local, tiene_otro = k in claves_local_des, k in origenes_otros
                tiene_pr, tiene_mov = k in mapa_pr, k in claves_mov_pr
                if not (tiene_pr or tiene_mov or ((not tiene_local) and (tiene_otro or tipo_local == "prestado"))):
                    continue
                evidencias = []
                if tiene_pr:
                    evidencias.append("Préstamo registrado en el período")
                if tiene_mov:
                    evidencias.append("Alta de docente prestado registrada")
                if tiene_otro and not tiene_local:
                    evidencias.append("Comisión receptora + designación docente en otro departamento")
                if tipo_local == "prestado" and not (tiene_pr or tiene_mov or tiene_otro):
                    evidencias.append("Marca histórica de prestado")
                origen = str((mapa_pr.get(k) or {}).get("departamento_origen") or "").strip()
                if not origen and tiene_otro:
                    origen = " / ".join(origenes_otros.get(k, []))
                if not origen:
                    origen = departamento_origen_desde_obs_prestado(doc.get("observaciones", ""))
                registros.append({"cuil": cuil_original[k], "docente": str(doc.get("docente") or cuil_original[k]).strip(),
                                  "departamento_origen": origen, "evidencia": " · ".join(evidencias),
                                  "estado_asignacion": " / ".join(estados_por_clave.get(k, []))})
            if not registros:
                return pd.DataFrame(columns=V175_COLS)
            return pd.DataFrame(registros, columns=V175_COLS).sort_values(["docente", "cuil"], kind="stable").reset_index(drop=True)
        except Exception:
            return pd.DataFrame(columns=V175_COLS)

    def prestados_recibidos_periodo_v175(self, periodo_id) -> pd.DataFrame:
        """v183 l. 39846."""
        raw = self._prestados_recibidos_base_v175(periodo_id)
        raw = raw.copy() if isinstance(raw, pd.DataFrame) else pd.DataFrame()
        if raw.empty or not self.es_historico(periodo_id):
            return raw
        try:
            claves_asig = _claves(self.asignaciones_comisiones_periodo(periodo_id))
        except Exception:
            claves_asig = set()
        try:
            pr_all = self.prestamos_docentes_periodo_v174(periodo_id, solo_activos=False)
            pr_close = self.filtrar_prestamos_cierre_v183(pr_all, periodo_id)
            claves_registradas, claves_pr_close = _claves(pr_all), _claves(pr_close)
        except Exception:
            claves_registradas, claves_pr_close = set(), set()
        claves_raw = raw.get("cuil", pd.Series(index=raw.index, dtype=str)).fillna("").astype(str).map(R.clave_cuil)

        def _ok(k):
            if k not in claves_asig:
                return False
            if k not in claves_registradas:
                return True
            return k in claves_pr_close
        return raw[[bool(_ok(k)) for k in claves_raw]].copy().reset_index(drop=True)

    # ------------------------------------------------------------------ plantel
    def _plantel_4645(self, periodo_id) -> pd.DataFrame:
        s = [self.repo.inst, self.repo.dep]
        return self.repo.read_sql(PLANTEL_BASE_SQL, s + [periodo_id] + s)

    def _plantel_26936(self, periodo_id) -> pd.DataFrame:
        df_base = self._plantel_4645(periodo_id)
        try:
            df_prest = self.repo.read_sql(PRESTADOS_LOCALES_SQL, [self.repo.inst, self.repo.dep])
            if df_prest.empty:
                return df_base
            if df_base is None or df_base.empty:
                df_base = pd.DataFrame(columns=COLS_PLANTEL)
            existentes = set(df_base.get("cuil", pd.Series(dtype=str)).fillna("").astype(str).str.strip())
            rows = []
            for _, r in df_prest.iterrows():
                cuil = str(r.get("cuil") or "").strip()
                if not cuil or cuil in existentes:
                    continue
                origen = departamento_origen_desde_obs_prestado(r.get("observaciones", ""))
                try:
                    df_des = self.designaciones_todos_departamentos(cuil, periodo_id)
                except Exception:
                    df_des = pd.DataFrame()
                if df_des is None:
                    df_des = pd.DataFrame()
                if not df_des.empty and "estado" in df_des.columns:
                    df_act = df_des[df_des["estado"].fillna("").astype(str).str.strip().str.lower().eq("activa")].copy()
                else:
                    df_act = pd.DataFrame()
                n_per = int(len(df_des)) if not df_des.empty else 0
                n_act = int(len(df_act)) if not df_act.empty else 0
                hs_act = float(pd.to_numeric(df_act.get("horas", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) \
                    if not df_act.empty else 0.0
                partes = []
                for _, rd in (df_act if not df_act.empty else df_des).iterrows() if not df_des.empty else []:
                    dep_rd = R.limpiar_texto_tabla(rd.get("departamento", ""))
                    hs_rd = R.hora_numero(rd.get("horas", 0))
                    txt_rd = " · ".join([x for x in [R.limpiar_texto_tabla(rd.get("cargo", "")),
                                                      R.limpiar_texto_tabla(rd.get("dedicacion", "")),
                                                      R.limpiar_texto_tabla(rd.get("tipo_designacion", "")),
                                                      f"{hs_rd:g} hs" if hs_rd else ""] if x])
                    if dep_rd:
                        txt_rd = f"{dep_rd}: {txt_rd}" if txt_rd else dep_rd
                    if txt_rd and txt_rd not in partes:
                        partes.append(txt_rd)
                detalle = "DOCENTE PRESTADO"
                if origen:
                    detalle += f" desde {origen}"
                if partes:
                    detalle += " | Designación institucional: " + " / ".join(partes)
                else:
                    detalle += " | Sin designación institucional encontrada para el período"
                detalle += ". No computa como designación propia del departamento receptor."
                rows.append({"cuil": cuil, "legajo": r.get("legajo", ""), "nombre_completo": r.get("nombre_completo", ""),
                             "titulo": r.get("titulo", ""), "titulo_posgrado": r.get("titulo_posgrado", ""),
                             "email": r.get("email", ""), "telefono": r.get("telefono", ""), "tipo_docente": "Prestado",
                             "estado_operativo_periodo": "Docente prestado en el período",
                             "fecha_alta_periodo": r.get("fecha_alta", ""), "fecha_finalizacion_periodo": "",
                             "designaciones_del_periodo": n_per, "designaciones_activas": n_act,
                             "horas_activas": round(hs_act, 2), "horas_registradas_periodo": round(hs_act, 2),
                             "detalle_designaciones": detalle})
            if rows:
                df_base = pd.concat([df_base, pd.DataFrame(rows)], ignore_index=True)
            return df_base
        except Exception:
            return df_base

    def _plantel_v174(self, periodo_id) -> pd.DataFrame:
        """l. 37132."""
        base = self._plantel_26936(periodo_id)
        base = base.copy() if isinstance(base, pd.DataFrame) else pd.DataFrame()
        try:
            info = self.periodo_info(int(periodo_id))
            abierto = bool(info) and str(info.get("estado") or "").strip().casefold() == "abierto"
        except Exception:
            abierto = False
        prestamos = self.prestamos_docentes_periodo_v174(periodo_id, solo_activos=abierto)
        permitidas = _claves(prestamos)
        for col in ["fecha_alta_periodo", "fecha_finalizacion_periodo"]:
            if col in base.columns:
                try:
                    base[col] = base[col].map(fecha_prestamo_texto_v179).astype(object)
                except Exception:
                    base[col] = base[col].astype(object)
            else:
                base[col] = pd.Series([""] * len(base), index=base.index, dtype=object)
        if not base.empty and "tipo_docente" in base.columns:
            tipo = base["tipo_docente"].fillna("Propio").astype(str).str.strip().str.casefold()
            claves = base.get("cuil", pd.Series(index=base.index, dtype=str)).fillna("").astype(str).map(R.clave_cuil)
            base = base[(tipo.ne("prestado")) | (claves.isin(permitidas))].copy()
        if prestamos.empty:
            return base.reset_index(drop=True)
        existentes = set(base.get("cuil", pd.Series(dtype=str)).fillna("").astype(str).map(R.clave_cuil).tolist()) \
            if not base.empty else set()
        mapa_p = {R.clave_cuil(r.get("cuil")): r.to_dict() for _, r in prestamos.iterrows() if R.clave_cuil(r.get("cuil"))}

        def _estado(pr):
            return ("Docente prestado en el período" if str(pr.get("estado", "Activo")).strip().casefold() == "activo"
                    else "Préstamo finalizado en el período")
        if not base.empty and "tipo_docente" in base.columns:
            for idx, r in base.iterrows():
                if str(r.get("tipo_docente", "Propio")).strip().casefold() != "prestado":
                    continue
                pr = mapa_p.get(R.clave_cuil(r.get("cuil")))
                if not pr:
                    continue
                base.at[idx, "fecha_alta_periodo"] = fecha_prestamo_texto_v179(pr.get("fecha_desde", ""))
                base.at[idx, "fecha_finalizacion_periodo"] = fecha_prestamo_texto_v179(pr.get("fecha_hasta", ""))
                base.at[idx, "estado_operativo_periodo"] = _estado(pr)
        faltantes = [r for _, r in prestamos.iterrows() if R.clave_cuil(r.get("cuil")) not in existentes]
        if faltantes:
            inst_id, filas = int(self.repo.inst), []
            for pr in faltantes:
                cuil = str(pr.get("cuil") or "").strip()
                if not cuil:
                    continue
                try:
                    df_doc = self.repo.read_raw(IDENTIDAD_37132_SQL, [inst_id, cuil, int(self.repo.dep or 0)])
                    dr = df_doc.iloc[0].to_dict() if not df_doc.empty else {}
                except Exception:
                    dr = {}
                nombre = nombre_completo(str(dr.get("apellido") or ""), str(dr.get("nombres") or "")) or str(dr.get("nombre") or cuil)
                try:
                    dfi = self.designaciones_docentes_institucionales_v169(cuil, periodo_id)
                except Exception:
                    dfi = pd.DataFrame()
                horas = float(pd.to_numeric(dfi.get("horas", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) \
                    if not dfi.empty else 0.0
                detalles = []
                if not dfi.empty:
                    for _, rd in dfi.iterrows():
                        dep = R.limpiar_texto_tabla(rd.get("departamento", ""))
                        t = " · ".join([x for x in [R.limpiar_texto_tabla(rd.get("cargo", "")),
                                                     R.limpiar_texto_tabla(rd.get("dedicacion", ""))] if x])
                        if dep:
                            t = f"{dep}: {t}" if t else dep
                        if t and t not in detalles:
                            detalles.append(t)
                detalle = f"DOCENTE PRESTADO desde {pr.get('departamento_origen','') or 'otro departamento'}"
                if detalles:
                    detalle += " | Designación institucional: " + " / ".join(detalles)
                detalle += ". No computa como designación propia del departamento receptor."
                filas.append({"cuil": cuil, "legajo": dr.get("legajo", ""), "nombre_completo": nombre,
                              "titulo": dr.get("titulo", ""), "titulo_posgrado": dr.get("titulo_posgrado", ""),
                              "email": dr.get("email", ""), "telefono": dr.get("telefono", ""), "tipo_docente": "Prestado",
                              "estado_operativo_periodo": _estado(pr),
                              "fecha_alta_periodo": fecha_prestamo_texto_v179(pr.get("fecha_desde", "")),
                              "fecha_finalizacion_periodo": fecha_prestamo_texto_v179(pr.get("fecha_hasta", "")),
                              "designaciones_del_periodo": int(len(dfi)) if not dfi.empty else 0,
                              "designaciones_activas": int(len(dfi)) if not dfi.empty else 0,
                              "horas_activas": round(horas, 2), "horas_registradas_periodo": round(horas, 2),
                              "detalle_designaciones": detalle})
            if filas:
                base = pd.concat([base, pd.DataFrame(filas)], ignore_index=True, sort=False)
        return base.reset_index(drop=True)

    def _identidad_v182(self, cuil) -> dict:
        try:
            df = self.repo.read_raw(IDENTIDAD_V182_SQL, [int(self.repo.inst), R.clave_cuil(cuil), int(self.repo.dep or 0)])
            return df.iloc[0].to_dict() if not df.empty else {}
        except Exception:
            return {}

    @staticmethod
    def _foto_propia(base, df_doc, sufijo_prestado=None):
        claves_df_doc = df_doc.get("cuil", pd.Series(index=df_doc.index, dtype=str)).fillna("").astype(str).map(R.clave_cuil)
        for idx, r in base.iterrows():
            if str(r.get("tipo_docente", "Propio")).strip().casefold() == "prestado":
                if sufijo_prestado:
                    base.at[idx, "estado_operativo_periodo"] = sufijo_prestado
                continue
            sub = df_doc[claves_df_doc.eq(R.clave_cuil(r.get("cuil")))].copy()
            if sub.empty:
                continue
            hs = horas_designaciones_v165(sub)
            base.at[idx, "estado_operativo_periodo"] = "Vigente al cierre del período"
            base.at[idx, "designaciones_del_periodo"] = int(len(sub))
            base.at[idx, "designaciones_activas"] = int(len(sub))
            base.at[idx, "horas_activas"] = round(hs, 2)
            base.at[idx, "horas_registradas_periodo"] = round(hs, 2)
            base.at[idx, "detalle_designaciones"] = " | ".join(
                f"{d.get('cargo','')} - {d.get('dedicacion','')} - {float(pd.to_numeric(d.get('horas'), errors='coerce') or 0):g} hs - "
                f"{d.get('tipo_designacion','')} - Ad Honorem: {d.get('ad_honorem','No')} - Estado al cierre: Vigente"
                for _, d in sub.iterrows())

    def _plantel_v182(self, periodo_id) -> pd.DataFrame:
        """l. 39559."""
        base = self._plantel_v174(periodo_id)
        base = base.copy() if isinstance(base, pd.DataFrame) else pd.DataFrame()
        if not self.es_historico(periodo_id):
            return base
        df_doc, _, _ = self.designaciones_funcionales_analisis_v169(periodo_id)
        claves_doc = _claves(df_doc)
        try:
            df_pr = self.prestados_recibidos_periodo_v175(periodo_id)
        except Exception:
            df_pr = pd.DataFrame()
        try:
            df_pr_tabla = self.prestamos_docentes_periodo_v174(periodo_id, solo_activos=False)
        except Exception:
            df_pr_tabla = pd.DataFrame()
        claves_prest = _claves(df_pr) | _claves(df_pr_tabla)
        if not base.empty:
            tipo = base.get("tipo_docente", pd.Series("Propio", index=base.index)).fillna("Propio").astype(str).str.strip().str.casefold()
            claves = base.get("cuil", pd.Series(index=base.index, dtype=str)).fillna("").astype(str).map(R.clave_cuil)
            base = base[(tipo.ne("prestado") & claves.isin(claves_doc)) | (tipo.eq("prestado") & claves.isin(claves_prest))].copy()
        if isinstance(df_doc, pd.DataFrame) and not df_doc.empty:
            self._foto_propia(base, df_doc)
        existentes = _claves(base)
        mapa_pr = {}
        for dfx in [df_pr_tabla, df_pr]:
            if isinstance(dfx, pd.DataFrame) and not dfx.empty:
                for _, r in dfx.iterrows():
                    k = R.clave_cuil(r.get("cuil"))
                    if k:
                        mapa_pr.setdefault(k, {}).update(r.to_dict())
        nuevas = []
        for k in sorted(claves_prest - existentes):
            pr = mapa_pr.get(k, {})
            cuil = str(pr.get("cuil") or k).strip()
            ident = self._identidad_v182(cuil)
            nombre = nombre_completo(str(ident.get("apellido") or ""), str(ident.get("nombres") or "")) \
                or str(ident.get("nombre") or pr.get("docente") or cuil)
            dfi = self.designaciones_docentes_institucionales_v169(cuil, periodo_id)
            hs = horas_designaciones_v165(dfi) if isinstance(dfi, pd.DataFrame) and not dfi.empty else 0.0
            estado_pr = str(pr.get("estado") or "").strip().casefold()
            nuevas.append({
                "cuil": cuil, "legajo": ident.get("legajo", ""), "nombre_completo": nombre,
                "titulo": ident.get("titulo", ""), "titulo_posgrado": ident.get("titulo_posgrado", ""),
                "email": ident.get("email", ""), "telefono": ident.get("telefono", ""), "tipo_docente": "Prestado",
                "estado_operativo_periodo": "Préstamo finalizado en el período" if estado_pr in {"finalizado", "finalizada", "cerrado"}
                else "Docente prestado en el período",
                "fecha_alta_periodo": fecha_prestamo_texto_v179(pr.get("fecha_desde", "")),
                "fecha_finalizacion_periodo": fecha_prestamo_texto_v179(pr.get("fecha_hasta", "")),
                "designaciones_del_periodo": 0, "designaciones_activas": 0,
                "horas_activas": 0.0, "horas_registradas_periodo": 0.0,
                "detalle_designaciones": f"DOCENTE PRESTADO desde {pr.get('departamento_origen','') or 'otro departamento'}; "
                                         f"designación institucional de origen: {round(hs,2):g} hs.",
            })
        if nuevas:
            base = pd.concat([base, pd.DataFrame(nuevas)], ignore_index=True, sort=False)
        return base.reset_index(drop=True)

    def plantel_periodo(self, periodo_id) -> pd.DataFrame:
        """``get_plantel_periodo`` efectiva: v183 l. 40051 sobre v182."""
        base = self._plantel_v182(periodo_id)
        base = base.copy() if isinstance(base, pd.DataFrame) else pd.DataFrame()
        if not self.es_historico(periodo_id):
            return base
        df_doc, _, _ = self.designaciones_funcionales_analisis_v169(periodo_id)
        claves_doc = _claves(df_doc)
        try:
            pr_close = self.filtrar_prestamos_cierre_v183(
                self.prestamos_docentes_periodo_v174(periodo_id, solo_activos=False), periodo_id)
            claves_prest = _claves(pr_close)
        except Exception:
            claves_prest = set()
        try:
            claves_prest |= _claves(self.prestados_recibidos_periodo_v175(periodo_id))
        except Exception:
            pass
        if not base.empty:
            tipo = base.get("tipo_docente", pd.Series("Propio", index=base.index)).fillna("Propio").astype(str).str.strip().str.casefold()
            claves = base.get("cuil", pd.Series(index=base.index, dtype=str)).fillna("").astype(str).map(R.clave_cuil)
            base = base[(tipo.ne("prestado") & claves.isin(claves_doc)) | (tipo.eq("prestado") & claves.isin(claves_prest))].copy()
        if isinstance(df_doc, pd.DataFrame) and not df_doc.empty and not base.empty:
            self._foto_propia(base, df_doc, sufijo_prestado="Prestado vigente al cierre del período")
        return base.reset_index(drop=True)

    def docentes_plantel_historico(self, periodo_id) -> pd.DataFrame:
        """Rama historica de ``get_docentes_activos_para_comisiones`` v182 (l. 39671)."""
        plantel = self.plantel_periodo(periodo_id)
        if plantel is None or plantel.empty:
            return pd.DataFrame()
        out = plantel.copy()
        for col, default in [("departamento_origen", ""), ("cargo", ""), ("cargo_final", ""), ("dedicacion", ""),
                             ("horas_designadas", 0)]:
            if col not in out.columns:
                out[col] = default
        df_doc, _, _ = self.designaciones_funcionales_analisis_v169(periodo_id)
        for idx, r in out.iterrows():
            cuil = str(r.get("cuil") or "").strip(); k = R.clave_cuil(cuil)
            if str(r.get("tipo_docente", "Propio")).strip().casefold() == "prestado":
                sub = self.designaciones_docentes_institucionales_v169(cuil, periodo_id)
                try:
                    pr = self.prestados_recibidos_periodo_v175(periodo_id)
                    spr = pr[pr.get("cuil", pd.Series(index=pr.index, dtype=str)).fillna("").astype(str).map(R.clave_cuil).eq(k)] \
                        if isinstance(pr, pd.DataFrame) and not pr.empty else pd.DataFrame()
                    if not spr.empty:
                        out.at[idx, "departamento_origen"] = R.limpiar_texto_tabla(spr.iloc[0].get("departamento_origen", ""))
                except Exception:
                    pass
            else:
                sub = df_doc[df_doc.get("cuil", pd.Series(index=df_doc.index, dtype=str)).fillna("").astype(str)
                             .map(R.clave_cuil).eq(k)].copy() if isinstance(df_doc, pd.DataFrame) and not df_doc.empty else pd.DataFrame()
            if isinstance(sub, pd.DataFrame) and not sub.empty:
                cargos = [x for x in dict.fromkeys(sub.get("cargo", pd.Series(dtype=str)).fillna("").astype(str).str.strip().tolist()) if x]
                dedic = [x for x in dict.fromkeys(sub.get("dedicacion", pd.Series(dtype=str)).fillna("").astype(str).str.strip().tolist()) if x]
                out.at[idx, "cargo"] = " / ".join(cargos)
                out.at[idx, "cargo_final"] = " / ".join(cargos)
                out.at[idx, "dedicacion"] = " / ".join(dedic)
                out.at[idx, "horas_designadas"] = round(horas_designaciones_v165(sub), 2)
        return out.reset_index(drop=True)
