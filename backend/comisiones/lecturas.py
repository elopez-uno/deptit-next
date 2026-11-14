"""Lecturas certificadas de Comisiones (cadenas efectivas de B13-FIX02), sin cache de proceso.

``Lector`` envuelve un ``ComisionesRepository`` (transaccion de lectura o COMMIT en curso) y memoiza la unificacion de
materias (cache v196/v199 del certificado; B12I la memoiza dentro de un writer hasta su proxima escritura:
``invalidar()``).  Cada metodo replica la definicion efectiva indicada; el pandas es el del entry.

Cadenas (entry):
- ``get_comisiones``: v285 (piloto off) -> v199 -> ``_get_comisiones_fast_pg_v197`` l. 44319.
- ``get_comisiones_integradas_periodo`` l. 29076; ``get_horarios_comisiones_periodo`` l. 28984;
  ``get_asignaciones_comisiones_periodo`` v183 l. 39919 -> l. 29029; ``get_modificaciones_asignaciones_periodo``
  l. 19204; ``get_movimientos_comision_en_curso`` (extracted_batch03).
- ``get_horarios_comision`` / ``get_asignaciones_comision`` / ``get_materias_conceptuales_comision_v122`` /
  ``get_horarios_reales_asignacion``: v199 l. 45099-45288.
- ``_materias_para_comisiones_unificadas_y_mapa`` l. 28040; ``get_materias_para_comisiones`` l. 28144;
  ``get_materia_comision`` l. 28163.
- ``get_superposiciones_periodo`` v195 l. 43646; ``get_comisiones_sin_docentes_periodo`` l. 24538.
- ``get_sedes_institucionales`` l. 18167.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Optional

import pandas as pd

from designaciones.rules import es_periodo_historico
from materias.rules import MODO_COMPARTICION_AUTO

from . import rules as R
from .lecturas_composicion import ComposicionMixin
from .lecturas_docentes import DocentesMixin
from .lecturas_inscriptos import InscriptosMixin
from .plantel import PlantelMixin
from .repository import ComisionesRepository

_COLS_V197 = [
    "id", "periodo_id", "periodo", "materia_id", "opcion_curricular_id",
    "codigo_materia", "asignatura", "materia_especifica", "tipo_opcion_curricular",
    "escuela_oferente_opcion", "carrera", "escuela", "plan_version", "anio", "cuatrimestre",
    "dictado", "carga_semanal", "carga_total", "materia_ids", "nombre_comision", "turno",
    "sede", "modalidad", "estado", "observaciones", "fecha_creacion", "horas_horario",
    "cantidad_horarios", "docentes_asignados",
]
_COLS_REALES = ["id", "asignacion_id", "horario_comision_id", "dia", "hora_inicio", "hora_fin", "horas", "observaciones"]


class Lector(PlantelMixin, ComposicionMixin, DocentesMixin, InscriptosMixin):
    def __init__(self, repo: ComisionesRepository, today: date):
        self.repo = repo
        self.today = today
        self._memo: dict = {}

    def invalidar(self) -> None:
        self._memo.clear()

    def _cached(self, key, fn):
        if key not in self._memo:
            self._memo[key] = fn()
        return self._memo[key]

    # ------------------------------------------------------------------ periodos
    def periodo_abierto(self) -> Optional[dict]:
        return self.repo.open_period()

    def ultimo_periodo(self) -> Optional[dict]:
        return self.repo.last_period()

    def periodo_info(self, periodo_id) -> Optional[dict]:
        return self.repo.period_info(int(periodo_id))

    def es_historico(self, periodo_id) -> bool:
        """``es_periodo_historico_contexto_v182`` (l. 39224)."""
        try:
            info = self.periodo_info(periodo_id)
        except Exception:
            return False
        return es_periodo_historico(info, self.ultimo_periodo(), self.periodo_abierto())

    def fecha_cierre(self, periodo_id) -> Optional[date]:
        """``_fecha_cierre_periodo_v183`` (l. 39782)."""
        info = self.periodo_info(periodo_id)
        return R.safe_date((info or {}).get("fecha_fin"), None)

    def es_periodo_actual(self, periodo_id) -> bool:
        return R.es_periodo_actual_para_comisiones_v233(periodo_id, self.ultimo_periodo())

    # ------------------------------------------------------------------ materias (fuente unica de planes)
    def materias_detalle(self) -> pd.DataFrame:
        """``_materias_para_comisiones_detalle`` (l. 28015)."""
        try:
            df = self.repo.materias().plan_todas()
        except Exception:
            df = pd.DataFrame()
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.copy()
        if "id" in df.columns and "materia_id" not in df.columns:
            df = df.rename(columns={"id": "materia_id"})
        if "estado" in df.columns and "estado_materia" not in df.columns:
            df = df.rename(columns={"estado": "estado_materia"})
        if "en_plan" not in df.columns:
            df["en_plan"] = 1
        return df

    def unificadas_y_mapa(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        unicas, mapa = self._cached("unificadas", self._unificadas_y_mapa)
        return unicas.copy(), mapa.copy()

    def _unificadas_y_mapa(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """``_materias_para_comisiones_unificadas_y_mapa`` (l. 28040)."""
        df = self.materias_detalle()
        columnas_base = [
            "materia_id", "codigo", "asignatura", "anio", "cuatrimestre",
            "carga_semanal", "carga_total", "estado_materia", "carrera", "escuela", "plan_version",
            "comparticion_modo", "comparticion_grupo", "en_plan",
        ]
        columnas_extra = [c for c in columnas_base if c != "en_plan"] + ["materia_ids", "cantidad_carreras",
                                                                         "cantidad_escuelas"]
        if df.empty:
            return pd.DataFrame(columns=columnas_extra), pd.DataFrame(columns=["materia_id_original"] + columnas_extra)
        df = df.copy()
        for col in columnas_base:
            if col not in df.columns:
                df[col] = 1 if col == "en_plan" else ""
        for col in ["codigo", "asignatura", "anio", "cuatrimestre", "estado_materia", "carrera", "escuela", "plan_version"]:
            df[col] = df[col].apply(R.limpiar_texto_tabla)
        df["comparticion_modo"] = df["comparticion_modo"].apply(R.normalizar_modo_comparticion_v137)
        df["comparticion_grupo"] = df["comparticion_grupo"].fillna("").astype(str).str.strip()
        df["en_plan"] = pd.to_numeric(df["en_plan"], errors="coerce").fillna(1).astype(int)
        estado_operativo = df["estado_materia"].fillna("Activa").astype(str).str.strip()
        estado_operativo = estado_operativo.replace("", "Activa").str.lower()
        df["_estado_activo_comision"] = estado_operativo.eq("activa")
        df["materia_id_original"] = pd.to_numeric(df["materia_id"], errors="coerce")
        df = df.dropna(subset=["materia_id_original"]).copy()
        if df.empty:
            return pd.DataFrame(columns=columnas_extra), pd.DataFrame(columns=["materia_id_original"] + columnas_extra)
        df["materia_id_original"] = df["materia_id_original"].astype(int)
        df["_clave_unica"] = df.apply(R.clave_materia_conceptual_v137, axis=1)

        def _armar_registro(g, materia_id_rep):
            return {
                "materia_id": int(materia_id_rep),
                "codigo": R.deptit_join_unicos(g["codigo"], sep=" / "),
                "asignatura": R.deptit_join_unicos(g["asignatura"], sep=" / "),
                "anio": R.deptit_join_unicos(g["anio"], sep=" / "),
                "cuatrimestre": R.deptit_join_unicos(g["cuatrimestre"], sep=" / "),
                "carga_semanal": R.deptit_join_unicos([str(x).replace('.0', '') for x in g["carga_semanal"].fillna("").tolist()], sep=" / "),
                "carga_total": R.deptit_join_unicos([str(x).replace('.0', '') for x in g["carga_total"].fillna("").tolist()], sep=" / "),
                "estado_materia": R.deptit_join_unicos(g["estado_materia"], sep=" / ") or "Activa",
                "carrera": R.deptit_join_unicos(g["carrera"], sep=" / "),
                "escuela": R.deptit_join_unicos(g["escuela"], sep=" / "),
                "plan_version": R.deptit_join_unicos(g["plan_version"], sep=" / "),
                "comparticion_modo": R.deptit_join_unicos(g["comparticion_modo"], sep=" / ") or MODO_COMPARTICION_AUTO,
                "comparticion_grupo": R.deptit_join_unicos(g["comparticion_grupo"], sep=" / "),
                "materia_ids": ",".join([str(int(x)) for x in sorted(g["materia_id_original"].dropna().astype(int).unique().tolist())]),
                "cantidad_carreras": int(g["carrera"].replace("", pd.NA).dropna().nunique()),
                "cantidad_escuelas": int(g["escuela"].replace("", pd.NA).dropna().nunique()),
            }

        registros = []
        mapa_rows = []
        for clave, g_all in df.groupby("_clave_unica", dropna=False, sort=False):
            g_all = g_all.sort_values(["escuela", "carrera", "plan_version", "anio", "cuatrimestre", "materia_id_original"],
                                      kind="stable")
            g_act = g_all[(g_all["en_plan"] == 1) & (g_all["_estado_activo_comision"] == True)].copy()  # noqa: E712
            if not g_act.empty:
                materia_id_rep_act = int(g_act["materia_id_original"].iloc[0])
                registro_act = _armar_registro(g_act, materia_id_rep_act)
                registro_act["_clave_unica"] = clave
                registros.append(registro_act)
            else:
                materia_id_rep_act = int(g_all["materia_id_original"].iloc[0])
            registro_hist = _armar_registro(g_all, materia_id_rep_act)
            registro_hist["_clave_unica"] = clave
            for mid in g_all["materia_id_original"].dropna().astype(int).unique().tolist():
                mr = dict(registro_hist)
                mr["materia_id_original"] = int(mid)
                mr["materia_id"] = int(mid)
                mr["materia_id_unificada"] = materia_id_rep_act
                mapa_rows.append(mr)
        df_unicas = pd.DataFrame(registros)
        df_mapa = pd.DataFrame(mapa_rows)
        if not df_unicas.empty:
            df_unicas = df_unicas.sort_values(["escuela", "codigo", "asignatura"], kind="stable").reset_index(drop=True)
        if not df_mapa.empty:
            df_mapa = df_mapa.reset_index(drop=True)
        return df_unicas, df_mapa

    def materias_para_comisiones(self) -> pd.DataFrame:
        """``get_materias_para_comisiones`` (l. 28144)."""
        df_unicas, _ = self.unificadas_y_mapa()
        columnas = [
            "materia_id", "codigo", "asignatura", "anio", "cuatrimestre",
            "carga_semanal", "carga_total", "estado_materia", "carrera", "escuela", "plan_version",
            "comparticion_modo", "comparticion_grupo", "materia_ids", "cantidad_carreras", "cantidad_escuelas",
        ]
        for col in columnas:
            if col not in df_unicas.columns:
                df_unicas[col] = ""
        return df_unicas[columnas].reset_index(drop=True)

    def materia_comision(self, materia_id) -> Optional[dict]:
        """``get_materia_comision`` (l. 28163)."""
        try:
            mid = int(materia_id)
        except Exception:
            return None
        df_unicas, df_mapa = self.unificadas_y_mapa()
        if not df_mapa.empty:
            fila = df_mapa[pd.to_numeric(df_mapa["materia_id"], errors="coerce").astype("Int64") == mid]
            if not fila.empty:
                return fila.iloc[0].to_dict()
        if not df_unicas.empty:
            fila = df_unicas[pd.to_numeric(df_unicas["materia_id"], errors="coerce").astype("Int64") == mid]
            if not fila.empty:
                return fila.iloc[0].to_dict()
        return None

    def opciones_materias_comisiones(self) -> tuple[dict, pd.DataFrame]:
        df = self.materias_para_comisiones()
        return R.opciones_desde_df_materias_comisiones(df), df

    def materias_mismo_grupo_conceptual_v118(self, materia_id_a, materia_id_b) -> bool:
        """l. 28607."""
        try:
            a, b = int(materia_id_a), int(materia_id_b)
        except Exception:
            return False
        if a == b:
            return True
        df = self.materias_detalle()
        fa = R.fila_materia_por_id_v118(df, a)
        fb = R.fila_materia_por_id_v118(df, b)
        if fa is None or fb is None:
            return False
        ka = R.clave_materia_conceptual_v137(fa)
        kb = R.clave_materia_conceptual_v137(fb)
        return bool(ka and ka == kb)

    # ------------------------------------------------------------------ comisiones
    def comisiones(self, periodo_id=None, solo_activas=False) -> pd.DataFrame:
        """``_get_comisiones_fast_pg_v197`` (l. 44319)."""
        df = self.repo.comisiones_v197(int(periodo_id) if periodo_id is not None else None, bool(solo_activas))
        if df is None or df.empty:
            return pd.DataFrame(columns=_COLS_V197)
        for col in _COLS_V197:
            if col not in df.columns:
                df[col] = ""
        df["horas_horario"] = pd.to_numeric(df["horas_horario"], errors="coerce").fillna(0)
        df["cantidad_horarios"] = pd.to_numeric(df["cantidad_horarios"], errors="coerce").fillna(0).astype(int)
        df["docentes_asignados"] = pd.to_numeric(df["docentes_asignados"], errors="coerce").fillna(0).astype(int)
        return df[_COLS_V197].reset_index(drop=True)

    def horarios_comisiones_periodo(self, periodo_id) -> pd.DataFrame:
        """``get_horarios_comisiones_periodo`` (l. 28984)."""
        df = self.repo.horarios_periodo(periodo_id)
        if df.empty:
            return df
        meta = self.comisiones(periodo_id=periodo_id, solo_activas=False)[
            ["id", "codigo_materia", "asignatura", "materia_especifica", "carrera", "escuela", "plan_version"]
        ].rename(columns={"id": "comision_id"})
        if not meta.empty:
            df = df.merge(meta, on="comision_id", how="left")
        cols = ["periodo", "codigo_materia", "asignatura", "materia_especifica", "carrera", "escuela", "plan_version",
                "nombre_comision", "turno", "modalidad", "dia", "hora_inicio", "hora_fin", "horas", "observaciones"]
        for col in cols:
            if col not in df.columns:
                df[col] = ""
        return df[cols].reset_index(drop=True)

    def _asignaciones_comisiones_periodo_base(self, periodo_id) -> pd.DataFrame:
        """``get_asignaciones_comisiones_periodo`` (l. 29029)."""
        df = self.repo.asignaciones_periodo(periodo_id)
        if df.empty:
            return df
        meta = self.comisiones(periodo_id=periodo_id, solo_activas=False)[
            ["id", "codigo_materia", "asignatura", "materia_especifica", "carrera", "escuela", "plan_version"]
        ].rename(columns={"id": "comision_id"})
        if not meta.empty:
            df = df.merge(meta, on="comision_id", how="left")
        cols = ["comision_id", "periodo", "codigo_materia", "asignatura", "materia_especifica", "carrera", "escuela",
                "plan_version", "nombre_comision", "turno", "modalidad", "cuil", "docente", "rol", "horas_asignadas",
                "estado", "tipo_docente", "observaciones"]
        for col in cols:
            if col not in df.columns:
                df[col] = ""
        return df[cols].reset_index(drop=True)

    def asignaciones_comisiones_periodo(self, periodo_id) -> pd.DataFrame:
        """v183 l. 39919: foto al cierre si el periodo es historico."""
        df = self._asignaciones_comisiones_periodo_base(periodo_id)
        if periodo_id is not None and self.es_historico(periodo_id):
            return R.filtrar_asignaciones_comision_cierre_v183(df, True, self.fecha_cierre(periodo_id))
        return df

    def modificaciones_asignaciones_periodo(self, periodo_id=None) -> pd.DataFrame:
        """``get_modificaciones_asignaciones_periodo`` (l. 19204)."""
        df = self.repo.modificaciones(int(periodo_id) if periodo_id is not None else None)
        cols = ["comision_id", "modificaciones_asignaciones_periodo"]
        if df.empty:
            return pd.DataFrame(columns=cols)

        def _extraer_comision_id(row):
            texto = f"{row.get('detalle', '')} {row.get('observaciones', '')}"
            m = re.search(r"Comisión\s+ID\s+(\d+)", str(texto), flags=re.I)
            return int(m.group(1)) if m else None

        df["comision_id"] = df.apply(_extraer_comision_id, axis=1)
        df = df[pd.notna(df["comision_id"])].copy()
        if df.empty:
            return pd.DataFrame(columns=cols)
        df["comision_id"] = df["comision_id"].astype(int)

        def _resumir(grupo):
            partes = []
            for _, r in grupo.iterrows():
                tipo = R.limpiar_texto_tabla(r.get("tipo_movimiento", ""))
                if "baja" in tipo.lower():
                    etiqueta = "Baja"
                elif "alta" in tipo.lower():
                    etiqueta = "Alta"
                else:
                    etiqueta = "Cambio"
                fecha = R.limpiar_texto_tabla(r.get("fecha", ""))
                docente = R.limpiar_texto_tabla(r.get("nombre", "")) or R.limpiar_texto_tabla(r.get("cuil", ""))
                partes.append(f"{etiqueta}: {docente}" + (f" ({fecha})" if fecha else ""))
            unicos = []
            for ptxt in partes:
                if ptxt not in unicos:
                    unicos.append(ptxt)
            return " | ".join(unicos)

        res = df.groupby("comision_id", dropna=False).apply(_resumir).reset_index(name="modificaciones_asignaciones_periodo")
        return res[cols]

    def comisiones_integradas_periodo(self, periodo_id=None) -> pd.DataFrame:
        """``get_comisiones_integradas_periodo`` (l. 29076)."""
        df_com = self.comisiones(periodo_id=periodo_id, solo_activas=False)
        if df_com is None or df_com.empty:
            return pd.DataFrame()
        df_h = self.repo.integradas_horarios(periodo_id)
        df_a = self.repo.integradas_asignaciones(periodo_id)

        def _join_h(g):
            vals = []
            for _, r in g.iterrows():
                vals.append(f"{r.get('dia', '')} {r.get('hora_inicio', '')}-{r.get('hora_fin', '')} ({r.get('horas', 0)} hs)")
            return " | ".join(vals)

        def _join_a(g):
            vals = []
            for _, r in g.iterrows():
                tipo = f" - {r.get('tipo_docente')}" if r.get('tipo_docente') else ""
                vals.append(f"{r.get('docente', '')} [{r.get('cuil', '')}] - {r.get('rol', '')} "
                            f"({r.get('horas_asignadas', 0)} hs{tipo})")
            return " | ".join(vals)

        if not df_h.empty:
            h_ag = df_h.groupby("comision_id", dropna=False).apply(_join_h).reset_index(name="horarios")
            hs_ag = df_h.groupby("comision_id", dropna=False)["horas"].sum().reset_index(name="horas_semanales_horario")
            df_com = df_com.merge(h_ag, left_on="id", right_on="comision_id", how="left").drop(columns=["comision_id"], errors="ignore")
            df_com = df_com.merge(hs_ag, left_on="id", right_on="comision_id", how="left").drop(columns=["comision_id"], errors="ignore")
        else:
            df_com["horarios"] = ""
            df_com["horas_semanales_horario"] = 0.0
        if not df_a.empty:
            a_ag = df_a.groupby("comision_id", dropna=False).apply(_join_a).reset_index(name="docentes_asignados_detalle")
            a_ct = df_a.groupby("comision_id", dropna=False)["cuil"].nunique().reset_index(name="cantidad_docentes")
            df_com = df_com.merge(a_ag, left_on="id", right_on="comision_id", how="left").drop(columns=["comision_id"], errors="ignore")
            df_com = df_com.merge(a_ct, left_on="id", right_on="comision_id", how="left").drop(columns=["comision_id"], errors="ignore")
        else:
            df_com["docentes_asignados_detalle"] = ""
            df_com["cantidad_docentes"] = 0
        df_mod_asig = self.modificaciones_asignaciones_periodo(periodo_id)
        if not df_mod_asig.empty:
            df_com = df_com.merge(df_mod_asig, left_on="id", right_on="comision_id", how="left").drop(columns=["comision_id"], errors="ignore")
        else:
            df_com["modificaciones_asignaciones_periodo"] = ""
        df_com["horarios"] = df_com["horarios"].fillna("")
        df_com["docentes_asignados_detalle"] = df_com["docentes_asignados_detalle"].fillna("")
        df_com["modificaciones_asignaciones_periodo"] = df_com["modificaciones_asignaciones_periodo"].fillna("")
        df_com["horas_semanales_horario"] = pd.to_numeric(df_com["horas_semanales_horario"], errors="coerce").fillna(0)
        df_com["cantidad_docentes"] = pd.to_numeric(df_com["cantidad_docentes"], errors="coerce").fillna(0).astype(int)
        return df_com.reset_index(drop=True)

    def opciones_comisiones(self, periodo_id=None, solo_activas=True) -> tuple[dict, pd.DataFrame]:
        """``get_opciones_comisiones`` (l. 18953)."""
        df = self.comisiones_integradas_periodo(periodo_id=periodo_id)
        if df is None or df.empty:
            return {}, pd.DataFrame()
        if solo_activas and "estado" in df.columns:
            df = df[df["estado"].fillna("Activa").astype(str).str.strip().eq("Activa")].copy()
        opciones = {}
        for _, row in df.iterrows():
            opciones[R.etiqueta_comision(row)] = int(row["id"])
        return opciones, df.reset_index(drop=True)

    # ------------------------------------------------------------------ por comision (v199)
    def _horarios_todos(self) -> pd.DataFrame:
        def build():
            df = self.repo.horarios_todos_v199()
            extras = ["periodo", "codigo_materia", "asignatura", "materia_especifica", "carrera", "escuela",
                      "plan_version", "nombre_comision", "turno", "modalidad"]
            if df is None:
                df = pd.DataFrame()
            if df.empty:
                for c in extras:
                    df[c] = ""
                return df
            dfc = self.comisiones(periodo_id=None, solo_activas=False)
            if isinstance(dfc, pd.DataFrame) and not dfc.empty:
                cols = [c for c in ["id"] + extras if c in dfc.columns]
                df = df.merge(dfc[cols].rename(columns={"id": "comision_id"}), on="comision_id", how="left")
            else:
                for c in extras:
                    if c not in df.columns:
                        df[c] = ""
            return df
        return self._cached("horarios_todos", build)

    def horarios_comision(self, comision_id=None) -> pd.DataFrame:
        df = self._horarios_todos()
        out = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
        if comision_id is not None and not out.empty:
            out = out[pd.to_numeric(out.get("comision_id"), errors="coerce").eq(int(comision_id))].copy()
        return out.reset_index(drop=True)

    def _asignaciones_todas(self) -> pd.DataFrame:
        def build():
            df = self.repo.asignaciones_todas_v199()
            extras = ["periodo", "codigo_materia", "asignatura", "materia_especifica", "carrera", "escuela",
                      "plan_version", "nombre_comision"]
            if df is None:
                df = pd.DataFrame()
            if df.empty:
                for c in extras:
                    df[c] = ""
                return df
            dfc = self.comisiones(periodo_id=None, solo_activas=False)
            if isinstance(dfc, pd.DataFrame) and not dfc.empty:
                cols = [c for c in ["id"] + extras + ["periodo_id"] if c in dfc.columns]
                meta = dfc[cols].rename(columns={"id": "comision_id", "periodo_id": "_periodo_id_v199"})
                df = df.merge(meta, on="comision_id", how="left")
            else:
                for c in extras:
                    if c not in df.columns:
                        df[c] = ""
            return df
        return self._cached("asignaciones_todas", build)

    def asignaciones_comision(self, comision_id=None) -> pd.DataFrame:
        df = self._asignaciones_todas()
        out = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
        if comision_id is not None and not out.empty:
            out = out[pd.to_numeric(out.get("comision_id"), errors="coerce").eq(int(comision_id))].copy()
            pid = None
            if "_periodo_id_v199" in out.columns and not out.empty:
                try:
                    pid = int(pd.to_numeric(out.iloc[0].get("_periodo_id_v199"), errors="coerce"))
                except Exception:
                    pid = None
            if pid is not None and self.es_historico(pid):
                out = R.filtrar_asignaciones_comision_cierre_v183(out, True, self.fecha_cierre(pid))
        return out.drop(columns=["_periodo_id_v199"], errors="ignore").reset_index(drop=True)

    def materias_conceptuales_comision_v122(self, comision_id) -> list[int]:
        try:
            cid = int(comision_id)
        except Exception:
            return []
        df = self._cached("vinculos_todos", self.repo.vinculos_todos_v199)
        sub = df[pd.to_numeric(df.get("comision_id"), errors="coerce").eq(cid)].copy() \
            if isinstance(df, pd.DataFrame) and not df.empty else pd.DataFrame()
        if sub.empty:
            return []
        principal = None
        ids = []
        try:
            val = pd.to_numeric(sub.iloc[0].get("materia_principal_id"), errors="coerce")
            if not pd.isna(val):
                principal = int(val)
                ids.append(principal)
        except Exception:
            principal = None
        if "materia_vinculada_id" in sub.columns:
            ids.extend(pd.to_numeric(sub["materia_vinculada_id"], errors="coerce").dropna().astype(int).tolist())
        representantes = []
        claves = set()
        principal_rep = None
        for mid in ids:
            info = self.materia_comision(mid) or {}
            if info:
                try:
                    rep = int(info.get("materia_id_unificada") or info.get("materia_id") or mid)
                except Exception:
                    rep = int(mid)
                clave = R.limpiar_texto_tabla(info.get("_clave_unica", "")) or R.clave_materia_conceptual_v137(info) or f"ID:{rep}"
            else:
                rep = int(mid)
                clave = f"ID:{rep}"
            if principal is not None and int(mid) == int(principal):
                principal_rep = rep
            if clave in claves:
                continue
            claves.add(clave)
            representantes.append(rep)
        if principal_rep is not None and principal_rep in representantes:
            representantes = [principal_rep] + [x for x in representantes if x != principal_rep]
        return representantes

    def horarios_reales_asignacion(self, asignacion_id) -> pd.DataFrame:
        try:
            aid = int(asignacion_id)
        except Exception:
            return pd.DataFrame(columns=_COLS_REALES)
        asign, hrs = self._cached("personalizados", self.repo.personalizados_v199)
        if not isinstance(asign, pd.DataFrame) or asign.empty:
            return pd.DataFrame(columns=_COLS_REALES)
        sub = asign[pd.to_numeric(asign.get("asignacion_id"), errors="coerce").eq(aid)]
        if sub.empty:
            return pd.DataFrame(columns=_COLS_REALES)
        personalizado = bool(sub.iloc[0].get("usa_horario_personalizado", False))
        cid = int(sub.iloc[0].get("comision_id"))
        if personalizado:
            out = hrs[pd.to_numeric(hrs.get("asignacion_id"), errors="coerce").eq(aid)].copy() \
                if isinstance(hrs, pd.DataFrame) and not hrs.empty else pd.DataFrame()
            return out.reset_index(drop=True)
        df = self.horarios_comision(cid)
        if df is None or df.empty:
            return pd.DataFrame(columns=_COLS_REALES)
        return pd.DataFrame({
            "id": [None] * len(df), "asignacion_id": [aid] * len(df), "horario_comision_id": df["id"].tolist(),
            "dia": df["dia"].tolist(), "hora_inicio": df["hora_inicio"].tolist(), "hora_fin": df["hora_fin"].tolist(),
            "horas": df["horas"].tolist(), "observaciones": [""] * len(df),
        })

    def movimientos_comision_en_curso(self, comision_id, periodo_id=None) -> pd.DataFrame:
        if not comision_id:
            return pd.DataFrame(columns=['fecha', 'tipo_movimiento', 'cuil', 'nombre', 'detalle', 'observaciones'])
        return self.repo.movimientos_en_curso(int(comision_id), periodo_id)

    # ------------------------------------------------------------------ alertas
    def superposiciones_periodo(self, periodo_id) -> pd.DataFrame:
        """``_superposiciones_periodo_bulk_pg_v195`` (l. 43646)."""
        cols = ["docente", "cuil", "dia", "asignatura_1", "comision_1", "horario_1", "asignatura_2", "comision_2",
                "horario_2"]
        dfh = self.repo.superposiciones_v195(int(periodo_id))
        if not isinstance(dfh, pd.DataFrame) or dfh.empty:
            return pd.DataFrame(columns=cols)
        out = []
        vistos = set()
        dfh = dfh.copy()
        dfh["_cuil_v195"] = dfh["cuil"].fillna("").astype(str).map(R.clave_cuil)
        for (cuil_clave, dia), g in dfh.groupby(["_cuil_v195", "dia"], dropna=False, sort=False):
            if not cuil_clave or pd.isna(dia):
                continue
            rows = list(g.sort_values(["hora_inicio", "hora_fin", "comision_id"], kind="stable").to_dict("records"))
            for i in range(len(rows)):
                a = rows[i]
                ai, af = R.minutos_v95(a.get("hora_inicio")), R.minutos_v95(a.get("hora_fin"))
                if ai is None or af is None:
                    continue
                for j in range(i + 1, len(rows)):
                    b = rows[j]
                    if a.get("comision_id") == b.get("comision_id"):
                        continue
                    bi, bf = R.minutos_v95(b.get("hora_inicio")), R.minutos_v95(b.get("hora_fin"))
                    if bi is None or bf is None:
                        continue
                    if max(ai, bi) >= min(af, bf):
                        if bi >= af:
                            break
                        continue
                    clave = (str(cuil_clave), str(dia),
                             min(int(a.get("comision_id")), int(b.get("comision_id"))),
                             max(int(a.get("comision_id")), int(b.get("comision_id"))),
                             max(ai, bi), min(af, bf))
                    if clave in vistos:
                        continue
                    vistos.add(clave)
                    out.append({
                        "docente": str(a.get("docente") or b.get("docente") or a.get("cuil") or ""),
                        "cuil": str(a.get("cuil") or b.get("cuil") or ""),
                        "dia": dia,
                        "asignatura_1": R.nombre_materia_visible_v138(a.get("codigo_materia", ""), a.get("asignatura", ""),
                                                                      a.get("materia_especifica", "")),
                        "comision_1": str(a.get("nombre_comision") or ""),
                        "horario_1": f"{R.hora_texto_v95(a.get('hora_inicio'))}-{R.hora_texto_v95(a.get('hora_fin'))}",
                        "asignatura_2": R.nombre_materia_visible_v138(b.get("codigo_materia", ""), b.get("asignatura", ""),
                                                                      b.get("materia_especifica", "")),
                        "comision_2": str(b.get("nombre_comision") or ""),
                        "horario_2": f"{R.hora_texto_v95(b.get('hora_inicio'))}-{R.hora_texto_v95(b.get('hora_fin'))}",
                    })
        return pd.DataFrame(out, columns=cols)

    def comisiones_sin_docentes_periodo(self, periodo_id) -> pd.DataFrame:
        """l. 24538."""
        df = self.comisiones(periodo_id=periodo_id, solo_activas=True)
        if df.empty:
            return pd.DataFrame()
        df = df.copy()
        df["docentes_asignados"] = pd.to_numeric(df["docentes_asignados"], errors="coerce").fillna(0).astype(int)
        return df[df["docentes_asignados"] == 0].drop(columns=["id", "periodo_id", "materia_id", "estado"], errors="ignore")

    # ------------------------------------------------------------------ sedes
    def sedes_institucionales(self, solo_activas=False) -> pd.DataFrame:
        columnas = ["id", "institucion_id", "nombre", "direccion", "localidad", "estado", "observaciones",
                    "fecha_creacion", "fecha_actualizacion"]
        df = self.repo.sedes(bool(solo_activas))
        for col in columnas:
            if col not in df.columns:
                df[col] = ""
        return df[columnas]

    def opciones_sedes_comision(self) -> list:
        df = self.sedes_institucionales(solo_activas=True)
        nombres = [] if df.empty else df["nombre"].tolist()
        return R.opciones_sedes_comision(nombres)

    # ------------------------------------------------------------------ superposicion del candidato (l. 30683)
    def horarios_docente_periodo(self, cuil, periodo_id, excluir_comision_id=None) -> pd.DataFrame:
        """``get_horarios_docente_periodo`` (l. 30520, v199): en PostgreSQL la consulta global institucional l. 30526."""
        from .proyectos import horarios_docente_periodo_pg_global
        return horarios_docente_periodo_pg_global(_LectorComoUnidad(self), cuil, periodo_id,
                                                  excluir_comision_id=excluir_comision_id)

    def detectar_superposiciones_horarios_candidato(self, cuil, periodo_id, horarios_candidato,
                                                    excluir_comision_id=None) -> pd.DataFrame:
        actuales = self.horarios_docente_periodo(cuil, periodo_id, excluir_comision_id=excluir_comision_id)
        hallazgos = []
        for cand in (horarios_candidato or []):
            cd = R.normalizar_dia_v95(cand.get("dia")); ci, cf = R.minutos_v95(cand.get("hora_inicio")), R.minutos_v95(cand.get("hora_fin"))
            if ci is None or cf is None:
                continue
            for _, r in actuales.iterrows():
                if R.normalizar_dia_v95(r.get("dia")) != cd:
                    continue
                ai, af = R.minutos_v95(r.get("hora_inicio")), R.minutos_v95(r.get("hora_fin"))
                if ai is not None and af is not None and max(ci, ai) < min(cf, af):
                    hallazgos.append({"cuil": cuil, "dia": cd,
                                      "nuevo_horario": f"{R.hora_texto_v95(cand.get('hora_inicio'))}-{R.hora_texto_v95(cand.get('hora_fin'))}",
                                      "comision_existente": r.get("asignatura", ""),
                                      "horario_existente": f"{R.hora_texto_v95(r.get('hora_inicio'))}-{R.hora_texto_v95(r.get('hora_fin'))}"})
        return pd.DataFrame(hallazgos)


class _LectorComoUnidad:
    """Adaptador de solo lectura: las funciones del reajuste v184 leen via ``u.read``/``u.lector``/``u.inst``."""

    def __init__(self, lector: Lector):
        self.lector = lector
        self.inst, self.dep = lector.repo.inst, lector.repo.dep

    def read(self, fn):
        # Cada lectura del certificado usa su propia conexion: un error (absorbido por su try/except) no debe abortar
        # la transaccion de lectura compartida -> SAVEPOINT por lectura cuando el repositorio tiene conexion propia.
        repo = self.lector.repo
        if not isinstance(repo, ComisionesRepository):  # dentro de un writer cada lectura ya abre su conexion
            return fn(repo)
        with repo._conn.transaction():
            return fn(repo)
