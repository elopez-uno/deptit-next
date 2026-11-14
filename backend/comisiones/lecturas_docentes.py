"""Docentes disponibles para comisiones, cargo/rol, prestamos y tipo local (cadenas efectivas de B13-FIX02).

Mixin de ``lecturas.Lector``.  Cadena de ``get_docentes_activos_para_comisiones`` (entry):
v234 l. 52979 -> v233 l. 52633 -> v182 l. 39669 -> v174 l. 37237 -> v162 l. 34842 -> v160 l. 30216
(cache sobre l. 26266 + ``_enriquecer_docentes_para_comisiones_v160`` l. 30087).
- Periodo actual: propios desde designaciones Activas del periodo (v234 l. 52834) + prestados de la cadena previa
  (v233 descarta sus propios y conserva sus prestados; v174 exige prestamo activo; v162 exige designacion docente
  activa institucional en el periodo equivalente).
- Periodo historico: v182 (plantel al cierre) -> ``docentes_plantel_historico`` (lecturas_plantel).
``get_roles_docente_periodo``: v233 l. 52665 -> cache v193 -> l. 26331 (institucional) -> l. 20893.
Prestamos: ``get_prestamos_docentes_periodo_v174`` l. 37006, ``prestamo_docente_activo_v174`` l. 37027.
"""

from __future__ import annotations

import re

import pandas as pd

from designaciones.rules import CARGOS

from . import rules as R

DOCENTES_LOCALES_SQL = (
    "SELECT doc.cuil, CASE WHEN doc.apellido IS NOT NULL AND doc.nombres IS NOT NULL THEN doc.apellido || ', ' || "
    "doc.nombres WHEN doc.nombre IS NOT NULL THEN doc.nombre ELSE doc.cuil END AS nombre_completo, "
    "COALESCE(doc.tipo_docente, 'Propio') AS tipo_docente, CASE WHEN COALESCE(doc.tipo_docente, 'Propio') = 'Prestado' "
    "THEN TRIM(REPLACE(REPLACE(COALESCE(doc.observaciones, ''), 'Docente prestado desde ', ''), "
    "'. No posee designación local en este departamento.', '')) ELSE '' END AS departamento_origen, 0 AS es_externo, "
    "COALESCE(( SELECT SUM(d.horas) FROM designaciones d WHERE d.cuil = doc.cuil AND d.periodo_id = %s "
    "AND d.estado = 'Activa' ), 0) AS horas_designadas FROM docentes doc WHERE COALESCE(doc.estado, 'Activo') = 'Activo' "
    "AND ( COALESCE(doc.tipo_docente, 'Propio') = 'Prestado' OR EXISTS ( SELECT 1 FROM designaciones dx "
    "WHERE dx.cuil = doc.cuil AND dx.periodo_id = %s AND dx.estado = 'Activa' ) ) AND (doc.institucion_id = %s) "
    "AND (doc.departamento_id = %s) ORDER BY tipo_docente, nombre_completo")
PRESTAMOS_SQL = (
    "SELECT pr.id, pr.periodo_id, pr.cuil, COALESCE(pr.departamento_origen,'') AS departamento_origen, pr.fecha_desde, "
    "pr.fecha_hasta, COALESCE(pr.estado,'Activo') AS estado, COALESCE(pr.observaciones,'') AS observaciones, "
    "pr.fecha_registro, pr.fecha_finalizacion FROM prestamos_docentes pr WHERE pr.periodo_id=%s {filtro} "
    "AND (pr.institucion_id = %s) AND (pr.departamento_id = %s) ORDER BY pr.fecha_desde, pr.cuil")
DOCENTE_TIPO_SQL = ("SELECT COALESCE(tipo_docente, 'Propio') AS tipo_docente FROM docentes WHERE cuil = %s "
                    "AND (docentes.institucion_id = %s) AND (docentes.departamento_id = %s) LIMIT 1")
PERIODO_EQUIV_SQL = "SELECT nombre, anio, semestre FROM periodos WHERE id = %s LIMIT 1"
CUILES_DOCENTE_ACTIVA_INST_SQL = """
    SELECT DISTINCT d.cuil
    FROM designaciones d
    JOIN periodos p ON p.id = d.periodo_id
    WHERE d.institucion_id = %s
      AND p.institucion_id = d.institucion_id
      AND p.departamento_id IS NOT DISTINCT FROM d.departamento_id
      AND (d.periodo_id = %s OR p.nombre = %s OR (p.anio = %s AND p.semestre = %s))
      AND COALESCE(d.estado, 'Activa') = 'Activa'
      AND COALESCE(d.funcion_no_docente, 0) = 0
"""
DEP_NOMBRE_SQL = "SELECT nombre FROM departamentos WHERE id=%s AND institucion_id=%s LIMIT 1"
PERIODO_INST_SQL = "SELECT nombre, anio, semestre FROM periodos WHERE id=%s AND institucion_id=%s LIMIT 1"
DESIG_INST_V160_SQL = """
    SELECT d.cuil, d.cargo, d.dedicacion, d.horas, d.departamento_id,
           COALESCE(dep.nombre, '') AS departamento
    FROM designaciones d
    JOIN periodos p ON p.id=d.periodo_id
                   AND p.institucion_id=d.institucion_id
                   AND p.departamento_id=d.departamento_id
    LEFT JOIN departamentos dep ON dep.id=d.departamento_id AND dep.institucion_id=d.institucion_id
    WHERE d.institucion_id=%s
      AND UPPER(TRIM(COALESCE(d.estado,'')))='ACTIVA'
      AND ((p.anio=%s AND p.semestre=%s) OR COALESCE(p.nombre,'')=%s)
"""
ORIGEN_V160_SQL = """
    SELECT doc.cuil, COALESCE(dep.nombre,'') AS departamento
    FROM docentes doc
    LEFT JOIN departamentos dep ON dep.id=doc.departamento_id AND dep.institucion_id=doc.institucion_id
    WHERE doc.institucion_id=%s
      AND UPPER(TRIM(COALESCE(doc.tipo_docente,'Propio'))) <> 'PRESTADO'
"""
DESIG_PERIODO_V234_SQL = """
    SELECT d.id, d.cuil, d.cargo, d.dedicacion, d.horas,
           COALESCE(d.funcion_no_docente,0) AS funcion_no_docente
    FROM designaciones d
    WHERE d.institucion_id=%s
      AND d.departamento_id=%s
      AND d.periodo_id=%s
      AND UPPER(TRIM(COALESCE(d.estado,'')))='ACTIVA'
      AND COALESCE(d.funcion_no_docente,0)=0
    ORDER BY d.id
"""
DOCENTES_INST_V234_SQL = """
    SELECT doc.id, doc.departamento_id, doc.cuil,
           CASE
             WHEN COALESCE(TRIM(doc.apellido),'') <> '' OR COALESCE(TRIM(doc.nombres),'') <> ''
               THEN TRIM(CONCAT_WS(', ', NULLIF(TRIM(doc.apellido),''), NULLIF(TRIM(doc.nombres),'')))
             WHEN COALESCE(TRIM(doc.nombre),'') <> '' THEN TRIM(doc.nombre)
             ELSE doc.cuil
           END AS nombre_completo,
           COALESCE(doc.estado,'') AS estado_docente,
           COALESCE(doc.tipo_docente,'Propio') AS tipo_docente,
           COALESCE(doc.legajo,'') AS legajo
    FROM docentes doc
    WHERE doc.institucion_id=%s
    ORDER BY CASE WHEN doc.departamento_id=%s THEN 0 ELSE 1 END, doc.id DESC
"""
DOCENTES_DEP_V233_SQL = """
    SELECT doc.id, doc.cuil,
           CASE
             WHEN COALESCE(TRIM(doc.apellido),'') <> '' OR COALESCE(TRIM(doc.nombres),'') <> ''
               THEN TRIM(CONCAT_WS(', ', NULLIF(TRIM(doc.apellido),''), NULLIF(TRIM(doc.nombres),'')))
             WHEN COALESCE(TRIM(doc.nombre),'') <> '' THEN TRIM(doc.nombre)
             ELSE doc.cuil
           END AS nombre_completo,
           COALESCE(doc.tipo_docente,'Propio') AS tipo_docente,
           COALESCE(doc.observaciones,'') AS observaciones
    FROM docentes doc
    WHERE doc.institucion_id=%s
      AND doc.departamento_id=%s
      AND UPPER(TRIM(COALESCE(doc.estado,'Activo')))='ACTIVO'
    ORDER BY doc.id DESC
"""
ROLES_V233_SQL = """
    SELECT d.cuil, d.cargo
    FROM designaciones d
    WHERE d.institucion_id=%s
      AND d.departamento_id=%s
      AND d.periodo_id=%s
      AND UPPER(TRIM(COALESCE(d.estado,'')))='ACTIVA'
      AND COALESCE(d.funcion_no_docente,0)=0
      AND COALESCE(TRIM(d.cargo),'')<>''
"""
ROLES_INST_SQL = """
    SELECT DISTINCT d.cargo
    FROM designaciones d
    LEFT JOIN periodos p ON p.id = d.periodo_id
    WHERE d.cuil = %s
      AND d.institucion_id = %s
      AND d.estado = 'Activa'
      AND COALESCE(d.cargo, '') <> ''
      AND (d.periodo_id = %s OR p.nombre = %s)
    ORDER BY d.cargo
"""
ROLES_BASE_SQL = ("SELECT DISTINCT cargo FROM designaciones WHERE cuil = %s AND periodo_id = %s AND estado = 'Activa' "
                  "AND COALESCE(cargo, '') <> '' AND (designaciones.institucion_id = %s) "
                  "AND (designaciones.departamento_id = %s) ORDER BY cargo")

_COLS_VACIAS_V234 = ["cuil", "nombre_completo", "tipo_docente", "departamento_origen", "es_externo", "horas_designadas",
                     "cargo", "cargo_final", "dedicacion", "estado_docente_base", "advertencia_disponibilidad"]
_COLS_VACIAS_V233 = ["cuil", "nombre_completo", "tipo_docente", "departamento_origen", "es_externo", "horas_designadas",
                     "cargo", "cargo_final", "dedicacion"]


class DocentesMixin:
    # ------------------------------------------------------------------ prestamos / tipo local
    def prestamos_docentes_periodo_v174(self, periodo_id, solo_activos=False) -> pd.DataFrame:
        if periodo_id is None:
            return pd.DataFrame(columns=["id", "periodo_id", "cuil", "departamento_origen", "fecha_desde", "fecha_hasta",
                                         "estado", "observaciones"])
        filtro = " AND UPPER(TRIM(COALESCE(pr.estado,'Activo')))='ACTIVO'" if solo_activos else ""
        try:
            return self.repo.read_sql(PRESTAMOS_SQL.replace("{filtro}", filtro),
                                      [int(periodo_id), self.repo.inst, self.repo.dep])
        except Exception:
            return pd.DataFrame(columns=["id", "periodo_id", "cuil", "departamento_origen", "fecha_desde", "fecha_hasta",
                                         "estado", "observaciones"])

    def prestamo_docente_activo_v174(self, cuil, periodo_id) -> bool:
        df = self.prestamos_docentes_periodo_v174(periodo_id, solo_activos=True)
        if df.empty:
            return False
        clave = R.clave_cuil(cuil)
        return bool(df.get("cuil", pd.Series(dtype=str)).fillna("").astype(str).map(R.clave_cuil).eq(clave).any())

    def cuiles_prestamos_v174(self, periodo_id, solo_activos=False) -> set:
        df = self.prestamos_docentes_periodo_v174(periodo_id, solo_activos=solo_activos)
        if df.empty:
            return set()
        return {x for x in df.get("cuil", pd.Series(dtype=str)).fillna("").astype(str).map(R.clave_cuil).tolist() if x}

    def docente_tipo_local(self, cuil) -> str:
        """``_docente_tipo_local`` (l. 26179)."""
        try:
            df = self.repo.read_sql(DOCENTE_TIPO_SQL, [cuil, self.repo.inst, self.repo.dep])
            if not df.empty:
                return str(df.iloc[0].get("tipo_docente") or "Propio").strip() or "Propio"
        except Exception:
            pass
        return "Propio"

    def es_docente_prestado_local(self, cuil) -> bool:
        return self.docente_tipo_local(cuil).strip().lower() == "prestado"

    def periodo_equivalente_pg(self, periodo_id):
        try:
            df_p = self.repo.read_raw(PERIODO_EQUIV_SQL, [periodo_id])
            if not df_p.empty:
                r = df_p.iloc[0]
                return (str(r.get('nombre') or ''), int(r.get('anio') or 0), int(r.get('semestre') or 0))
        except Exception:
            pass
        return ('', 0, 0)

    def dep_nombre(self) -> str:
        try:
            df_dep = self.repo.read_raw(DEP_NOMBRE_SQL, [self.repo.dep, self.repo.inst])
            return R.limpiar_texto_tabla(df_dep.iloc[0].get("nombre", "")) if not df_dep.empty else ""
        except Exception:
            return ""

    # ------------------------------------------------------------------ cadena de docentes disponibles
    def _docentes_original_v160(self, periodo_id) -> pd.DataFrame:
        """l. 26266 (``_get_docentes_activos_para_comisiones_original`` l. 19101 queda como fallback)."""
        df = self.repo.read_sql(DOCENTES_LOCALES_SQL, [periodo_id, periodo_id, self.repo.inst, self.repo.dep])
        for col in ["cuil", "nombre_completo", "tipo_docente", "departamento_origen", "es_externo", "horas_designadas"]:
            if col not in df.columns:
                df[col] = "" if col != "horas_designadas" else 0
        return df.reset_index(drop=True)

    def _enriquecer_v160(self, df, periodo_id) -> pd.DataFrame:
        """``_enriquecer_docentes_para_comisiones_v160`` (l. 30087)."""
        out = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
        for col, default in [("departamento_origen", ""), ("cargo", ""), ("cargo_final", ""), ("dedicacion", ""),
                             ("horas_designadas", 0)]:
            if col not in out.columns:
                out[col] = default
        if out.empty:
            return out
        try:
            dep_id = self.repo.dep
            dep_nombre = self.dep_nombre()
            inst_id = self.repo.inst
            df_per = self.repo.read_raw(PERIODO_INST_SQL, [int(periodo_id), int(inst_id)])
            if df_per.empty:
                return out
            per = df_per.iloc[0]
            per_nombre = R.limpiar_texto_tabla(per.get("nombre", ""))
            try:
                per_anio = int(per.get("anio"))
            except Exception:
                per_anio = 0
            try:
                per_sem = int(per.get("semestre"))
            except Exception:
                per_sem = 0
            df_des = self.repo.read_raw(DESIG_INST_V160_SQL, [int(inst_id), per_anio, per_sem, per_nombre])
            df_origen = self.repo.read_raw(ORIGEN_V160_SQL, [int(inst_id)])

            def clave_cuil_v160(v):
                return re.sub(r"\D+", "", str(v or ""))

            mapa_des: dict = {}
            if df_des is not None and not df_des.empty:
                for _, r in df_des.iterrows():
                    k = clave_cuil_v160(r.get("cuil"))
                    if k:
                        mapa_des.setdefault(k, []).append(r.to_dict())
            mapa_origen: dict = {}
            if df_origen is not None and not df_origen.empty:
                for _, r in df_origen.iterrows():
                    k = clave_cuil_v160(r.get("cuil"))
                    dep = R.limpiar_texto_tabla(r.get("departamento", ""))
                    if k and dep and dep not in mapa_origen.setdefault(k, []):
                        mapa_origen[k].append(dep)
            for idx, r in out.iterrows():
                k = clave_cuil_v160(r.get("cuil"))
                tipo = R.limpiar_texto_tabla(r.get("tipo_docente", "Propio")) or "Propio"
                filas = list(mapa_des.get(k, []))
                if tipo.casefold() == "prestado":
                    filas_relevantes = [x for x in filas if int(x.get("departamento_id") or 0) != int(dep_id or 0)]
                    deps = []
                    for x in filas_relevantes:
                        d = R.limpiar_texto_tabla(x.get("departamento", ""))
                        if d and d not in deps:
                            deps.append(d)
                    if not deps:
                        deps = list(mapa_origen.get(k, []))
                    out.at[idx, "departamento_origen"] = " / ".join(deps)
                else:
                    filas_relevantes = [x for x in filas if int(x.get("departamento_id") or 0) == int(dep_id or 0)]
                    out.at[idx, "departamento_origen"] = dep_nombre
                if filas_relevantes:
                    cargos, dedicaciones = [], []
                    total_horas = 0
                    for x in filas_relevantes:
                        cargo = R.limpiar_texto_tabla(x.get("cargo", ""))
                        dedic = R.limpiar_texto_tabla(x.get("dedicacion", ""))
                        if cargo and cargo not in cargos:
                            cargos.append(cargo)
                        if dedic and dedic not in dedicaciones:
                            dedicaciones.append(dedic)
                        total_horas += R.horas_segun_dedicacion(dedic, x.get("horas", 0))
                    out.at[idx, "cargo"] = " / ".join(cargos)
                    out.at[idx, "cargo_final"] = " / ".join(cargos)
                    out.at[idx, "dedicacion"] = " / ".join(dedicaciones)
                    out.at[idx, "horas_designadas"] = int(total_horas)
            return out
        except Exception:
            return out

    def _docentes_v162(self, periodo_id) -> pd.DataFrame:
        df = self._enriquecer_v160(self._docentes_original_v160(periodo_id).copy(), periodo_id)
        if df is None or df.empty or "cuil" not in df.columns:
            return df
        try:
            nombre_p, anio, semestre = self.periodo_equivalente_pg(periodo_id)
            dfc = self.repo.read_raw(CUILES_DOCENTE_ACTIVA_INST_SQL,
                                     [self.repo.inst, int(periodo_id), nombre_p, int(anio), int(semestre)])
            habilitados = {R.clave_cuil(x) for x in dfc.get("cuil", pd.Series(dtype=str)).tolist() if R.clave_cuil(x)}
        except Exception:
            habilitados = set()
        claves = df["cuil"].fillna("").astype(str).map(R.clave_cuil)
        return df[claves.isin(habilitados)].copy().reset_index(drop=True)

    def _docentes_v174(self, periodo_id) -> pd.DataFrame:
        df = self._docentes_v162(periodo_id)
        if df is None or df.empty or "tipo_docente" not in df.columns:
            return df
        permitidos = self.cuiles_prestamos_v174(periodo_id, solo_activos=True)
        tipo = df["tipo_docente"].fillna("Propio").astype(str).str.strip().str.casefold()
        claves = df.get("cuil", pd.Series(index=df.index, dtype=str)).fillna("").astype(str).map(R.clave_cuil)
        return df[(tipo.ne("prestado")) | (claves.isin(permitidos))].reset_index(drop=True)

    def _docentes_v182(self, periodo_id) -> pd.DataFrame:
        if not self.es_historico(periodo_id):
            return self._docentes_v174(periodo_id)
        return self.docentes_plantel_historico(periodo_id)

    def _docentes_propios_v233(self, periodo_id) -> pd.DataFrame:
        """``_docentes_propios_activos_fisicos_comision_v233`` (l. 52515)."""
        try:
            inst, dep, pid = int(self.repo.inst), int(self.repo.dep), int(periodo_id)
        except Exception:
            return pd.DataFrame()
        try:
            df_doc = self.repo.read_raw(DOCENTES_DEP_V233_SQL, [inst, dep])
            df_des = self.repo.read_raw(DESIG_PERIODO_V234_SQL, [inst, dep, pid])
        except Exception:
            return pd.DataFrame()
        if df_doc is None or df_doc.empty or df_des is None or df_des.empty:
            return pd.DataFrame(columns=_COLS_VACIAS_V233)
        mapa_doc = {}
        for _, r in df_doc.iterrows():
            k = R.clave_cuil(r.get("cuil"))
            if not k or k in mapa_doc:
                continue
            if str(r.get("tipo_docente") or "Propio").strip().casefold() == "prestado":
                continue
            mapa_doc[k] = r.to_dict()
        grupos_des: dict = {}
        for _, r in df_des.iterrows():
            k = R.clave_cuil(r.get("cuil"))
            if k:
                grupos_des.setdefault(k, []).append(r.to_dict())
        dep_nombre = self.dep_nombre()
        filas = []
        prioridad = {c: i for i, c in enumerate(R.ORDEN_JERARQUICO_CARGOS_COMISION)}
        for k, doc in mapa_doc.items():
            desigs = grupos_des.get(k, [])
            if not desigs:
                continue
            cargos, dedicaciones, horas = self._cargos_dedicaciones_horas(desigs)
            cargos.sort(key=lambda x: prioridad.get(x, 999))
            filas.append({
                "cuil": str(doc.get("cuil") or "").strip(),
                "nombre_completo": R.limpiar_texto_tabla(doc.get("nombre_completo", "")) or str(doc.get("cuil") or ""),
                "tipo_docente": "Propio", "departamento_origen": dep_nombre, "es_externo": 0,
                "horas_designadas": round(horas, 2), "cargo": " / ".join(cargos), "cargo_final": " / ".join(cargos),
                "dedicacion": " / ".join(dedicaciones),
            })
        return pd.DataFrame(filas)

    @staticmethod
    def _cargos_dedicaciones_horas(desigs):
        cargos, dedicaciones = [], []
        horas = 0.0
        for d in desigs:
            cargo = R.normalizar_cargo_para_jerarquia(d.get("cargo")) or R.limpiar_texto_tabla(d.get("cargo", ""))
            dedic = R.limpiar_texto_tabla(d.get("dedicacion", ""))
            if cargo and cargo not in cargos:
                cargos.append(cargo)
            if dedic and dedic not in dedicaciones:
                dedicaciones.append(dedic)
            try:
                horas += float(R.horas_segun_dedicacion(dedic, d.get("horas", 0)) or 0)
            except Exception:
                try:
                    horas += float(d.get("horas", 0) or 0)
                except Exception:
                    pass
        return cargos, dedicaciones, horas

    def _docentes_v233(self, periodo_id) -> pd.DataFrame:
        if not self.es_periodo_actual(periodo_id):
            return self._docentes_v182(periodo_id)
        try:
            base = self._docentes_v182(periodo_id)
        except Exception:
            base = pd.DataFrame()
        if base is None:
            base = pd.DataFrame()
        if not base.empty:
            tipo = base.get("tipo_docente", pd.Series(index=base.index, dtype=str)).fillna("Propio").astype(str).str.strip().str.casefold()
            prestados = base[tipo.eq("prestado")].copy()
        else:
            prestados = pd.DataFrame()
        propios = self._docentes_propios_v233(periodo_id)
        partes = [x for x in (propios, prestados) if isinstance(x, pd.DataFrame) and not x.empty]
        if not partes:
            return pd.DataFrame(columns=_COLS_VACIAS_V233)
        out = pd.concat(partes, ignore_index=True, sort=False)
        out["_cuil_v233"] = out.get("cuil", pd.Series(index=out.index, dtype=str)).fillna("").astype(str).map(R.clave_cuil)
        out = out[out["_cuil_v233"].astype(bool)].drop_duplicates("_cuil_v233", keep="first").drop(columns=["_cuil_v233"], errors="ignore")
        return out.sort_values(["tipo_docente", "nombre_completo"], kind="stable").reset_index(drop=True)

    def _docentes_propios_v234(self, periodo_id) -> pd.DataFrame:
        """``_docentes_propios_desde_designaciones_activas_v234`` (l. 52834)."""
        try:
            inst, dep, pid = int(self.repo.inst), int(self.repo.dep), int(periodo_id)
        except Exception:
            return pd.DataFrame()
        try:
            df_des = self.repo.read_raw(DESIG_PERIODO_V234_SQL, [inst, dep, pid])
        except Exception:
            df_des = pd.DataFrame()
        if df_des is None or df_des.empty:
            return pd.DataFrame(columns=_COLS_VACIAS_V234)
        try:
            df_doc = self.repo.read_raw(DOCENTES_INST_V234_SQL, [inst, dep])
        except Exception:
            df_doc = pd.DataFrame()
        mapa_identidad = {}
        if isinstance(df_doc, pd.DataFrame) and not df_doc.empty:
            for _, r in df_doc.iterrows():
                k = R.clave_cuil(r.get("cuil"))
                if k and k not in mapa_identidad:
                    mapa_identidad[k] = r.to_dict()
        dep_nombre = self.dep_nombre()
        grupos: dict = {}
        for _, r in df_des.iterrows():
            k = R.clave_cuil(r.get("cuil"))
            if k:
                grupos.setdefault(k, []).append(r.to_dict())
        prioridad = {c: i for i, c in enumerate(R.ORDEN_JERARQUICO_CARGOS_COMISION)}
        filas = []
        for k, desigs in grupos.items():
            ident = mapa_identidad.get(k, {})
            cuil_des = next((str(d.get("cuil") or "").strip() for d in desigs if str(d.get("cuil") or "").strip()), k)
            cuil_mostrar = str(ident.get("cuil") or cuil_des or k).strip()
            nombre = R.limpiar_texto_tabla(ident.get("nombre_completo", "")) or cuil_mostrar
            cargos, dedicaciones, horas = self._cargos_dedicaciones_horas(desigs)
            cargos.sort(key=lambda x: prioridad.get(x, 999))
            estado_base = R.limpiar_texto_tabla(ident.get("estado_docente", ""))
            advertencias = []
            if not ident:
                advertencias.append("Sin fila maestra local/institucional; habilitado por designación activa")
            elif R.normalizar_clave(estado_base) not in {"", "ACTIVO"}:
                advertencias.append(f"La fila maestra figura '{estado_base}', pero la designación docente del período está Activa")
            tipo_base = R.limpiar_texto_tabla(ident.get("tipo_docente", ""))
            if tipo_base and tipo_base.casefold() == "prestado":
                advertencias.append("La fila maestra figura Prestado, pero existe designación local Activa; se trata como "
                                    "propio para esta comisión")
            filas.append({
                "cuil": cuil_mostrar, "nombre_completo": nombre, "tipo_docente": "Propio",
                "departamento_origen": dep_nombre, "es_externo": 0, "horas_designadas": round(horas, 2),
                "cargo": " / ".join(cargos), "cargo_final": " / ".join(cargos), "dedicacion": " / ".join(dedicaciones),
                "estado_docente_base": estado_base, "advertencia_disponibilidad": " | ".join(advertencias),
            })
        return pd.DataFrame(filas)

    def docentes_activos_para_comisiones(self, periodo_id) -> pd.DataFrame:
        """v234 (l. 52979)."""
        if not self.es_periodo_actual(periodo_id):
            return self._docentes_v233(periodo_id)
        try:
            previo = self._docentes_v233(periodo_id)
        except Exception:
            previo = pd.DataFrame()
        if isinstance(previo, pd.DataFrame) and not previo.empty:
            tipo = previo.get("tipo_docente", pd.Series(index=previo.index, dtype=str)).fillna("Propio").astype(str).str.strip().str.casefold()
            prestados = previo[tipo.eq("prestado")].copy()
        else:
            prestados = pd.DataFrame()
        propios = self._docentes_propios_v234(periodo_id)
        partes = [x for x in (propios, prestados) if isinstance(x, pd.DataFrame) and not x.empty]
        if not partes:
            return pd.DataFrame(columns=_COLS_VACIAS_V234)
        out = pd.concat(partes, ignore_index=True, sort=False)
        out["_cuil_v234"] = out.get("cuil", pd.Series(index=out.index, dtype=str)).fillna("").astype(str).map(R.clave_cuil)
        out = out[out["_cuil_v234"].astype(bool)]
        # Si el mismo CUIL aparece propio + prestado, la designacion local Activa manda.
        out["_prio_tipo_v234"] = out.get("tipo_docente", pd.Series("Propio", index=out.index)).fillna("Propio").astype(str)            .str.strip().str.casefold().map(lambda x: 0 if x == "propio" else 1)
        out = out.sort_values(["_prio_tipo_v234", "nombre_completo"], kind="stable")
        out = out.drop_duplicates("_cuil_v234", keep="first").drop(columns=["_cuil_v234", "_prio_tipo_v234"], errors="ignore")
        return out.reset_index(drop=True)

    # ------------------------------------------------------------------ roles
    def _roles_base(self, cuil, periodo_id) -> list:
        """l. 20893 (``_get_roles_docente_periodo_original``): prestado sin cargo local -> catalogo CARGOS."""
        df = self.repo.read_sql(ROLES_BASE_SQL, [cuil, periodo_id, self.repo.inst, self.repo.dep])
        df_tipo = self.repo.read_sql(DOCENTE_TIPO_SQL, [cuil, self.repo.inst, self.repo.dep])
        roles = [R.limpiar_texto_tabla(x) for x in df["cargo"].dropna().tolist()] if not df.empty else []
        if not roles and not df_tipo.empty and df_tipo.iloc[0]["tipo_docente"] == "Prestado":
            return list(CARGOS)
        return roles

    def _roles_institucional(self, cuil, periodo_id) -> list:
        """l. 26331: prestados -> cargos Activos en la institucion para el mismo periodo (id o nombre)."""
        try:
            df_p = self.repo.read_raw("SELECT nombre FROM periodos WHERE id = %s LIMIT 1", [periodo_id])
            periodo_nombre = str(df_p.iloc[0].get("nombre") or "") if not df_p.empty else ""
            df = self.repo.read_raw(ROLES_INST_SQL, [cuil, int(self.repo.inst), periodo_id, periodo_nombre])
            roles = [R.limpiar_texto_tabla(x) for x in df["cargo"].dropna().tolist()] if not df.empty else []
            if roles:
                return roles
        except Exception:
            pass
        return self._roles_base(cuil, periodo_id)

    def roles_docente_periodo(self, cuil, periodo_id) -> list:
        """v233 (l. 52665)."""
        if self.es_periodo_actual(periodo_id):
            try:
                df = self.repo.read_raw(ROLES_V233_SQL, [int(self.repo.inst), int(self.repo.dep), int(periodo_id)])
                k = R.clave_cuil(cuil)
                if isinstance(df, pd.DataFrame) and not df.empty and k:
                    sub = df[df.get("cuil", pd.Series(index=df.index, dtype=str)).fillna("").astype(str).map(R.clave_cuil).eq(k)].copy()
                    roles = []
                    for x in sub.get("cargo", pd.Series(dtype=str)).tolist():
                        cargo = R.normalizar_cargo_para_jerarquia(x) or R.limpiar_texto_tabla(x)
                        if cargo and cargo not in roles:
                            roles.append(cargo)
                    prioridad = {c: i for i, c in enumerate(R.ORDEN_JERARQUICO_CARGOS_COMISION)}
                    roles.sort(key=lambda x: prioridad.get(x, 999))
                    if roles:
                        return roles
            except Exception:
                pass
        return list(self._roles_institucional(str(cuil or ""), int(periodo_id)) or [])
