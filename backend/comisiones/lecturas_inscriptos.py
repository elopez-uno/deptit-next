"""Inscriptos por asignatura/codigo y periodo (v248) y contexto de alumnos (v188): lecturas certificadas.

Mixin de ``lecturas.Lector``.  Entry: ``_materia_representante_inscriptos_v123`` l. 13582,
``_comisiones_contexto_alumnos_v188`` l. 40805, v248 l. 53376-54075.  La migracion legacy
(``migrar_inscriptos_a_asignatura_periodo_v248``) y el ``asegurar_esquema`` que la lectura invoca NO se ejecutan
(B12F: fuera de una operacion de negocio no corren).  Las cantidades se leen sin compuerta de periodo.
"""

from __future__ import annotations

import pandas as pd

from . import rules as R

GUARDADOS_SQL = (
    "SELECT id, periodo_id, materia_id, COALESCE(opcion_curricular_id,0) AS opcion_curricular_id, "
    "COALESCE(cantidad,0) AS cantidad, cantidad_final, COALESCE(fecha_actualizacion,'') AS fecha_actualizacion, "
    "COALESCE(fecha_actualizacion_final,'') AS fecha_actualizacion_final, COALESCE(observaciones,'') AS "
    "observaciones_inscriptos FROM inscriptos_asignatura_periodo WHERE periodo_id=%s "
    "AND (inscriptos_asignatura_periodo.institucion_id = %s) AND (inscriptos_asignatura_periodo.departamento_id = %s) "
    "ORDER BY materia_id, opcion_curricular_id")
LEGACY_SQL = (
    "SELECT ic.comision_id, COALESCE(ic.cantidad,0) AS total_historico, ic.cantidad_final AS total_final_historico, "
    "COALESCE(ic.fecha_actualizacion,'') AS fecha_actualizacion FROM inscriptos_comision ic JOIN comisiones co "
    "ON co.id=ic.comision_id WHERE co.periodo_id=%s AND (COALESCE(ic.cantidad,0) > 0 OR ic.cantidad_final IS NOT NULL) "
    "AND NOT EXISTS ( SELECT 1 FROM inscriptos_comision_materia icm WHERE icm.comision_id=ic.comision_id ) "
    "AND (ic.institucion_id = %s) AND (ic.departamento_id = %s) AND (co.institucion_id = %s) "
    "AND (co.departamento_id = %s) ORDER BY ic.comision_id")


class InscriptosMixin:
    def materia_representante_inscriptos_v123(self, materia_id):
        try:
            mid = int(materia_id)
        except Exception:
            return None
        info = self.materia_comision(mid) or {}
        try:
            return int(info.get("materia_id") or mid)
        except Exception:
            return mid

    def comisiones_contexto_alumnos_v188(self, periodo_id) -> pd.DataFrame:
        try:
            historico = bool(self.es_historico(int(periodo_id)))
        except Exception:
            historico = False
        try:
            df = self.comisiones(periodo_id=int(periodo_id), solo_activas=not historico)
        except Exception:
            df = pd.DataFrame()
        df = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
        if df.empty:
            return df
        if "estado" in df.columns:
            est = df["estado"].fillna("").astype(str).str.strip().str.casefold()
            df = df[~est.str.contains(r"elimin|cancel", regex=True, na=False)].copy()
        return df.reset_index(drop=True)

    def fila_comision_v248(self, comision_id, periodo_id=None) -> dict:
        try:
            cid = int(comision_id)
        except Exception:
            return {}
        try:
            df = self.comisiones(periodo_id=periodo_id, solo_activas=False)
        except Exception:
            df = pd.DataFrame()
        if isinstance(df, pd.DataFrame) and not df.empty and "id" in df.columns:
            ids = pd.to_numeric(df["id"], errors="coerce")
            sub = df[ids.eq(cid)]
            if not sub.empty:
                return sub.iloc[0].to_dict()
        return {}

    def items_asignaturas_comision_v248(self, comision_id, fila_comision=None) -> list[dict]:
        try:
            cid = int(comision_id)
        except Exception:
            return []
        fila = dict(fila_comision or self.fila_comision_v248(cid) or {})
        try:
            reps = [int(x) for x in (self.materias_conceptuales_comision_v122(cid) or [])]
        except Exception:
            reps = []
        if not reps:
            try:
                mid0 = int(fila.get("materia_id"))
                reps = [mid0]
            except Exception:
                reps = []
        opcion_id = R.opcion_id_inscriptos_v248(fila.get("opcion_curricular_id")) if len(reps) == 1 else 0
        opcion = {}
        if opcion_id:
            try:
                opcion = dict(self.opcion_curricular_v120(opcion_id) or {})
            except Exception:
                opcion = {}
        items, vistos = [], set()
        for mid_raw in reps:
            mid = self.materia_representante_inscriptos_v123(mid_raw)
            if mid is None:
                continue
            oid = opcion_id if len(reps) == 1 else 0
            clave = (int(mid), int(oid))
            if clave in vistos:
                continue
            vistos.add(clave)
            try:
                info = dict(self.materia_comision(int(mid)) or {})
            except Exception:
                info = {}
            base_asig = R.limpiar_texto_tabla(info.get("asignatura", ""))
            materia_especifica = R.limpiar_texto_tabla((opcion or {}).get("nombre", "") or fila.get("materia_especifica", ""))
            codigo = R.limpiar_texto_tabla((opcion or {}).get("codigo", "")) or R.limpiar_texto_tabla(info.get("codigo", ""))
            asignatura = materia_especifica or base_asig
            items.append({
                "materia_id_inscriptos": int(mid),
                "opcion_curricular_id_inscriptos": int(oid),
                "clave_asignatura_v248": f"{int(mid)}:{int(oid)}",
                "codigo_materia": codigo,
                "asignatura": asignatura,
                "asignatura_base": base_asig,
                "materia_especifica": materia_especifica,
                "carrera": R.limpiar_texto_tabla(info.get("carrera", "")),
                "escuela": R.limpiar_texto_tabla(info.get("escuela", "")),
                "plan_version": R.limpiar_texto_tabla(info.get("plan_version", "")),
            })
        return items

    def inscriptos_guardados_periodo_v248(self, periodo_id) -> pd.DataFrame:
        return self.repo.read_sql(GUARDADOS_SQL, [int(periodo_id), self.repo.inst, self.repo.dep])

    def legacy_inscriptos_sin_discriminar_v248(self, periodo_id) -> pd.DataFrame:
        pid = int(periodo_id)
        try:
            legacy = self.repo.read_sql(LEGACY_SQL, [pid] + [self.repo.inst, self.repo.dep] * 2)
        except Exception:
            return pd.DataFrame()
        if legacy is None or legacy.empty:
            return pd.DataFrame()
        guardados = self.inscriptos_guardados_periodo_v248(pid)
        claves_guardadas = set()
        if isinstance(guardados, pd.DataFrame) and not guardados.empty:
            for _, r in guardados.iterrows():
                try:
                    claves_guardadas.add((int(r.get("materia_id")), R.opcion_id_inscriptos_v248(r.get("opcion_curricular_id"))))
                except Exception:
                    pass
        filas = []
        for _, r in legacy.iterrows():
            try:
                cid = int(r.get("comision_id"))
            except Exception:
                continue
            co = self.fila_comision_v248(cid, pid)
            items = self.items_asignaturas_comision_v248(cid, co)
            claves = {(int(x["materia_id_inscriptos"]), int(x["opcion_curricular_id_inscriptos"])) for x in items}
            if claves and claves.issubset(claves_guardadas):
                continue
            filas.append({
                "Comisión": R.etiqueta_comision_derivada_v248(co) or f"ID {cid}",
                "Asignaturas / códigos detectados": " + ".join(R.etiqueta_item_v248(x) for x in items),
                "Total histórico sin discriminar": R.entero_no_negativo_v248(r.get("total_historico", 0)),
                "Regulares históricos": r.get("total_final_historico", pd.NA),
                "Actualización": R.limpiar_texto_tabla(r.get("fecha_actualizacion", "")),
            })
        return pd.DataFrame(filas)

    def inscriptos_asignaturas_periodo_v248(self, periodo_id) -> pd.DataFrame:
        return self._cached(("inscriptos", int(periodo_id)), lambda: self._inscriptos_raw_v248(periodo_id)).copy()

    def _inscriptos_raw_v248(self, periodo_id) -> pd.DataFrame:
        pid = int(periodo_id)
        try:
            df_integrado = self.comisiones_integradas_periodo(pid)
        except Exception:
            df_integrado = pd.DataFrame()
        if df_integrado is None or df_integrado.empty:
            return pd.DataFrame(columns=[
                "materia_id_inscriptos", "opcion_curricular_id_inscriptos", "codigo_materia", "asignatura",
                "cantidad", "cantidad_final", "cantidad_comisiones", "comisiones_relacionadas", "combinaciones_relacionadas",
            ])
        try:
            df_ctx = self.comisiones_contexto_alumnos_v188(pid)
            ids_ctx = set(pd.to_numeric(df_ctx.get("id", pd.Series(dtype=float)), errors="coerce").dropna().astype(int).tolist()) \
                if isinstance(df_ctx, pd.DataFrame) else set()
        except Exception:
            ids_ctx = set()
        if ids_ctx and "id" in df_integrado.columns:
            df_integrado = df_integrado[pd.to_numeric(df_integrado["id"], errors="coerce").isin(ids_ctx)].copy()
        if df_integrado.empty:
            return pd.DataFrame()
        datos: dict = {}
        combos_por_item: dict = {}
        for _, co in df_integrado.iterrows():
            try:
                cid = int(co.get("id"))
            except Exception:
                continue
            items = self.items_asignaturas_comision_v248(cid, co.to_dict())
            if not items:
                continue
            claves_combo = tuple(sorted((int(x["materia_id_inscriptos"]), int(x["opcion_curricular_id_inscriptos"])) for x in items))
            etiqueta_combo = " + ".join(R.etiqueta_item_v248(x) for x in sorted(
                items, key=lambda z: (str(z.get("codigo_materia", "")), str(z.get("asignatura", "")))))
            etiqueta_com = R.etiqueta_comision_derivada_v248(co.to_dict())
            for item in items:
                k = (int(item["materia_id_inscriptos"]), int(item["opcion_curricular_id_inscriptos"]))
                rec = datos.setdefault(k, {**item, "comisiones": [], "comision_ids": set()})
                if etiqueta_com and etiqueta_com not in rec["comisiones"]:
                    rec["comisiones"].append(etiqueta_com)
                rec["comision_ids"].add(cid)
                combos_por_item.setdefault(k, {})[claves_combo] = etiqueta_combo
        guardados = self.inscriptos_guardados_periodo_v248(pid)
        mapa = {}
        if isinstance(guardados, pd.DataFrame) and not guardados.empty:
            for _, r in guardados.iterrows():
                try:
                    mapa[(int(r.get("materia_id")), R.opcion_id_inscriptos_v248(r.get("opcion_curricular_id")))] = r.to_dict()
                except Exception:
                    pass
        filas = []
        for k, rec in datos.items():
            g = mapa.get(k, {})
            fila = {kk: vv for kk, vv in rec.items() if kk not in {"comisiones", "comision_ids"}}
            fila.update({
                "periodo_id": pid,
                "cantidad": R.entero_no_negativo_v248(g.get("cantidad", 0)),
                "cantidad_final": g.get("cantidad_final", pd.NA),
                "fecha_actualizacion": R.limpiar_texto_tabla(g.get("fecha_actualizacion", "")),
                "fecha_actualizacion_final": R.limpiar_texto_tabla(g.get("fecha_actualizacion_final", "")),
                "observaciones_inscriptos": R.limpiar_texto_tabla(g.get("observaciones_inscriptos", "")),
                "cantidad_comisiones": int(len(rec["comision_ids"])),
                "comisiones_relacionadas": " | ".join(rec["comisiones"]),
                "combinaciones_relacionadas": " | ".join(sorted(set(combos_por_item.get(k, {}).values()))),
            })
            filas.append(fila)
        out = pd.DataFrame(filas)
        if out.empty:
            return out
        out["cantidad"] = pd.to_numeric(out["cantidad"], errors="coerce").fillna(0).astype(int)
        out["cantidad_final"] = pd.to_numeric(out["cantidad_final"], errors="coerce")
        return out.sort_values([c for c in ["codigo_materia", "asignatura"] if c in out.columns], kind="stable").reset_index(drop=True)

    def docentes_comisiones_periodo_v248(self, periodo_id) -> pd.DataFrame:
        pid = int(periodo_id)
        try:
            df_ctx = self.comisiones_contexto_alumnos_v188(pid)
        except Exception:
            df_ctx = pd.DataFrame()
        ids = set(pd.to_numeric(df_ctx.get("id", pd.Series(dtype=float)), errors="coerce").dropna().astype(int).tolist()) \
            if isinstance(df_ctx, pd.DataFrame) and not df_ctx.empty else set()
        try:
            df = self.asignaciones_comisiones_periodo(pid)
        except Exception:
            df = pd.DataFrame()
        df = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
        if df.empty or "comision_id" not in df.columns:
            return pd.DataFrame(columns=["comision_id", "cuil", "docente"])
        df["_cid_v248"] = pd.to_numeric(df["comision_id"], errors="coerce")
        if ids:
            df = df[df["_cid_v248"].isin(ids)].copy()
        try:
            historico = bool(self.es_historico(pid))
        except Exception:
            historico = False
        if not historico and "estado" in df.columns:
            est = df["estado"].fillna("Activa").astype(str).str.strip().str.casefold()
            df = df[est.eq("activa")].copy()
        df["_cuil_v248"] = df.get("cuil", pd.Series(index=df.index, dtype=str)).fillna("").astype(str).map(R.clave_cuil)
        df = df[df["_cuil_v248"].ne("")].copy()
        return df

    def analisis_alumnos_por_docente_grupos_v248(self, periodo_id) -> pd.DataFrame:
        pid = int(periodo_id)
        try:
            df_ctx = self.comisiones_contexto_alumnos_v188(pid)
            ids_ctx = set(pd.to_numeric(df_ctx.get("id", pd.Series(dtype=float)), errors="coerce").dropna().astype(int).tolist()) \
                if isinstance(df_ctx, pd.DataFrame) else set()
        except Exception:
            ids_ctx = set()
        try:
            df_com = self.comisiones_integradas_periodo(pid)
        except Exception:
            df_com = pd.DataFrame()
        if df_com is None or df_com.empty:
            return pd.DataFrame()
        if ids_ctx and "id" in df_com.columns:
            df_com = df_com[pd.to_numeric(df_com["id"], errors="coerce").isin(ids_ctx)].copy()
        if df_com.empty:
            return pd.DataFrame()
        df_ins = self.inscriptos_asignaturas_periodo_v248(pid)
        mapa_ins = {}
        if isinstance(df_ins, pd.DataFrame) and not df_ins.empty:
            for _, r in df_ins.iterrows():
                try:
                    mapa_ins[(int(r.get("materia_id_inscriptos")),
                              R.opcion_id_inscriptos_v248(r.get("opcion_curricular_id_inscriptos")))] = r.to_dict()
                except Exception:
                    pass
        df_doc = self.docentes_comisiones_periodo_v248(pid)
        docs_por_com: dict = {}
        nombres_doc = {}
        if isinstance(df_doc, pd.DataFrame) and not df_doc.empty:
            for _, r in df_doc.iterrows():
                try:
                    cid = int(r.get("comision_id"))
                except Exception:
                    continue
                ck = R.clave_cuil(r.get("cuil"))
                if not ck:
                    continue
                docs_por_com.setdefault(cid, set()).add(ck)
                nom = R.limpiar_texto_tabla(r.get("docente", "")) or R.limpiar_texto_tabla(r.get("cuil", ""))
                if nom:
                    nombres_doc[ck] = nom
        grupos: dict = {}
        for _, co in df_com.iterrows():
            try:
                cid = int(co.get("id"))
            except Exception:
                continue
            items = self.items_asignaturas_comision_v248(cid, co.to_dict())
            if not items:
                continue
            key = tuple(sorted((int(x["materia_id_inscriptos"]), int(x["opcion_curricular_id_inscriptos"])) for x in items))
            g = grupos.setdefault(key, {"items": items, "comision_ids": set(), "comisiones": []})
            g["comision_ids"].add(cid)
            et = R.etiqueta_comision_derivada_v248(co.to_dict())
            if et and et not in g["comisiones"]:
                g["comisiones"].append(et)
        filas = []
        for key, g in grupos.items():
            items = g["items"]
            cantidades = []
            finales = []
            for k in key:
                r = mapa_ins.get(k, {})
                cantidades.append(R.entero_no_negativo_v248(r.get("cantidad", 0)))
                finales.append(pd.to_numeric(r.get("cantidad_final", pd.NA), errors="coerce"))
            total = int(sum(cantidades))
            final_total = int(sum(int(v) for v in finales if not pd.isna(v))) \
                if finales and all(not pd.isna(v) for v in finales) else pd.NA
            docs = set()
            for cid in g["comision_ids"]:
                docs.update(docs_por_com.get(cid, set()))
            ratio = round(float(total) / float(len(docs)), 2) if docs else 0.0
            items_ord = sorted(items, key=lambda x: (str(x.get("codigo_materia", "")), str(x.get("asignatura", ""))))
            filas.append({
                "codigos": " + ".join([R.limpiar_texto_tabla(x.get("codigo_materia", "")) for x in items_ord
                                       if R.limpiar_texto_tabla(x.get("codigo_materia", ""))]),
                "asignaturas": " + ".join([R.limpiar_texto_tabla(x.get("asignatura", "")) for x in items_ord
                                           if R.limpiar_texto_tabla(x.get("asignatura", ""))]),
                "inscriptos_totales": total,
                "regulares_finales": final_total,
                "cantidad_comisiones": int(len(g["comision_ids"])),
                "comisiones": " | ".join(g["comisiones"]),
                "docentes_unicos": int(len(docs)),
                "docentes": " | ".join(sorted([nombres_doc.get(c, c) for c in docs])),
                "alumnos_por_docente": float(ratio),
                "clave_combinacion": "+".join(f"{a}:{b}" for a, b in key),
            })
        out = pd.DataFrame(filas)
        if out.empty:
            return out
        return out.sort_values([c for c in ["codigos", "asignaturas"] if c in out.columns], kind="stable").reset_index(drop=True)

    def total_inscriptos_asignaturas_periodo_v248(self, periodo_id) -> int:
        df = self.inscriptos_asignaturas_periodo_v248(int(periodo_id))
        if df is None or df.empty:
            return 0
        return int(pd.to_numeric(df.get("cantidad", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())

    def inscriptos_comisiones_periodo(self, periodo_id) -> pd.DataFrame:
        pid = int(periodo_id)
        df_asig = self.inscriptos_asignaturas_periodo_v248(pid)
        try:
            df_com = self.comisiones_integradas_periodo(pid)
        except Exception:
            df_com = pd.DataFrame()
        if df_com is None or df_com.empty:
            return pd.DataFrame()
        try:
            df_ctx = self.comisiones_contexto_alumnos_v188(pid)
            ids_ctx = set(pd.to_numeric(df_ctx.get("id", pd.Series(dtype=float)), errors="coerce").dropna().astype(int).tolist()) \
                if isinstance(df_ctx, pd.DataFrame) else set()
        except Exception:
            ids_ctx = set()
        if ids_ctx:
            df_com = df_com[pd.to_numeric(df_com.get("id"), errors="coerce").isin(ids_ctx)].copy()
        mapa = {}
        if isinstance(df_asig, pd.DataFrame) and not df_asig.empty:
            for _, r in df_asig.iterrows():
                try:
                    mapa[(int(r.get("materia_id_inscriptos")),
                          R.opcion_id_inscriptos_v248(r.get("opcion_curricular_id_inscriptos")))] = r.to_dict()
                except Exception:
                    pass
        grupos = self.analisis_alumnos_por_docente_grupos_v248(pid)
        grupo_por_clave = {str(r.get("clave_combinacion")): r.to_dict() for _, r in grupos.iterrows()} \
            if isinstance(grupos, pd.DataFrame) and not grupos.empty else {}
        filas = []
        for _, co in df_com.iterrows():
            try:
                cid = int(co.get("id"))
            except Exception:
                continue
            items = self.items_asignaturas_comision_v248(cid, co.to_dict())
            if not items:
                continue
            key_tuple = tuple(sorted((int(x["materia_id_inscriptos"]), int(x["opcion_curricular_id_inscriptos"])) for x in items))
            key_str = "+".join(f"{a}:{b}" for a, b in key_tuple)
            g = grupo_por_clave.get(key_str, {})
            total = int(g.get("inscriptos_totales", 0) or 0)
            total_final = g.get("regulares_finales", pd.NA)
            for item in items:
                k = (int(item["materia_id_inscriptos"]), int(item["opcion_curricular_id_inscriptos"]))
                ins = mapa.get(k, {})
                filas.append({
                    "comision_id": cid,
                    "materia_id_inscriptos": k[0],
                    "opcion_curricular_id_inscriptos": k[1],
                    "periodo": co.get("periodo", ""),
                    "codigo_materia": item.get("codigo_materia", ""),
                    "asignatura": item.get("asignatura", ""),
                    "materia_especifica": item.get("materia_especifica", ""),
                    "carrera": item.get("carrera", ""), "escuela": item.get("escuela", ""),
                    "plan_version": item.get("plan_version", ""),
                    "nombre_comision": co.get("nombre_comision", ""), "turno": co.get("turno", ""),
                    "sede": co.get("sede", ""), "modalidad": co.get("modalidad", ""), "horarios": co.get("horarios", ""),
                    "cantidad": R.entero_no_negativo_v248(ins.get("cantidad", 0)),
                    "cantidad_final": ins.get("cantidad_final", pd.NA),
                    "total_comision": total,
                    "total_final_comision": total_final,
                    "fecha_actualizacion": ins.get("fecha_actualizacion", "") or "",
                    "fecha_actualizacion_final": ins.get("fecha_actualizacion_final", "") or "",
                    "observaciones_inscriptos": ins.get("observaciones_inscriptos", "") or "",
                    "cantidad_comisiones_conjunto": int(g.get("cantidad_comisiones", 1) or 1),
                    "comisiones_conjunto": g.get("comisiones", R.etiqueta_comision_derivada_v248(co.to_dict())),
                    "docentes_unicos_conjunto": int(g.get("docentes_unicos", 0) or 0),
                    "alumnos_por_docente_conjunto": float(g.get("alumnos_por_docente", 0) or 0),
                    "legacy_total_sin_discriminar": 0,
                })
        return pd.DataFrame(filas)

    def _periodos_df(self) -> pd.DataFrame:
        return pd.DataFrame(self.repo.periods())

    def historial_inscriptos_materias(self) -> pd.DataFrame:
        partes = []
        dfp = self._periodos_df()
        if dfp is None or dfp.empty:
            return pd.DataFrame()
        for _, p in dfp.iterrows():
            try:
                d = self.inscriptos_asignaturas_periodo_v248(int(p.get("id")))
            except Exception:
                continue
            if d is None or d.empty:
                continue
            d = d.copy()
            d["periodo"] = R.limpiar_texto_tabla(p.get("nombre", ""))
            d["inscriptos_inicio"] = pd.to_numeric(d.get("cantidad"), errors="coerce").fillna(0).astype(int)
            d["regulares_final"] = pd.to_numeric(d.get("cantidad_final"), errors="coerce")
            d = d[(d["inscriptos_inicio"] > 0) | d["regulares_final"].notna()
                  | d.get("fecha_actualizacion", pd.Series("", index=d.index)).fillna("").astype(str).str.strip().ne("")].copy()
            if d.empty:
                continue
            d["variacion"] = d.apply(lambda r: int(r["regulares_final"] - r["inscriptos_inicio"])
                                     if pd.notna(r["regulares_final"]) else pd.NA, axis=1)
            d["retencion_pct"] = d.apply(lambda r: round(float(r["regulares_final"]) * 100.0 / float(r["inscriptos_inicio"]), 1)
                                         if pd.notna(r["regulares_final"]) and int(r["inscriptos_inicio"] or 0) > 0 else pd.NA,
                                         axis=1)
            d["comisiones"] = pd.to_numeric(d.get("cantidad_comisiones"), errors="coerce").fillna(0).astype(int)
            d["comisiones_con_cierre"] = d["regulares_final"].notna().astype(int) * d["comisiones"]
            partes.append(d)
        if not partes:
            return pd.DataFrame()
        out = pd.concat(partes, ignore_index=True, sort=False)
        cols = ["periodo", "codigo_materia", "asignatura", "asignatura_base", "materia_especifica", "carrera", "escuela",
                "comisiones", "comisiones_relacionadas", "inscriptos_inicio", "regulares_final", "variacion",
                "retencion_pct", "fecha_actualizacion", "fecha_actualizacion_final"]
        orden = [c for c in ["periodo", "codigo_materia", "asignatura"] if c in out.columns]
        return out[[c for c in cols if c in out.columns]].sort_values(
            orden, ascending=[False, True, True][:len(orden)], kind="stable").reset_index(drop=True)

    def historial_inscriptos_por_cuatrimestre(self) -> pd.DataFrame:
        partes = []
        dfp = self._periodos_df()
        if dfp is None or dfp.empty:
            return pd.DataFrame()
        for _, p in dfp.iterrows():
            try:
                g = self.analisis_alumnos_por_docente_grupos_v248(int(p.get("id")))
            except Exception:
                continue
            if g is None or g.empty:
                continue
            g = g.copy()
            g.insert(0, "periodo", R.limpiar_texto_tabla(p.get("nombre", "")))
            partes.append(g)
        if not partes:
            return pd.DataFrame()
        return pd.concat(partes, ignore_index=True, sort=False)
