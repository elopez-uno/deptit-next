"""Lecturas certificadas de opciones curriculares y composicion de comisiones (v118/v120/v122/v127/v128/v129).

Mixin de ``lecturas.Lector`` (usa ``self.repo``, ``self.materia_comision``, ``self.unificadas_y_mapa``,
``self.materias_detalle``, ``self.comisiones`` y ``self.materias_conceptuales_comision_v122``).
Cadenas (entry): opciones l. 12489-12697 y 13378-13467; vinculos v118 l. 28206, v128 l. 28295, v120 l. 28323;
v122 l. 28391-28556; ``existe_comision_duplicada`` l. 28773.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from materias.rules import ESTADOS_OPCION_CURRICULAR, TIPOS_OPCION_CURRICULAR

from . import rules as R


class ComposicionMixin:
    # ------------------------------------------------------------------ opciones curriculares
    def opcion_curricular_v120(self, opcion_id) -> Optional[dict]:
        try:
            oid = int(opcion_id)
        except Exception:
            return None
        return self.repo.materias().opcion(oid)

    def vinculos_opciones_lote_v127(self, opcion_ids, solo_vigentes=False) -> pd.DataFrame:
        ids = []
        for x in list(opcion_ids or []):
            try:
                v = int(x)
            except Exception:
                continue
            if v not in ids:
                ids.append(v)
        columnas = ["vinculo_id", "opcion_id", "materia_id", "fecha_vinculacion", "codigo", "asignatura",
                    "tipo_espacio", "carrera_id", "carrera", "escuela", "plan_version", "anio", "cuatrimestre",
                    "estado", "en_plan"]
        if not ids:
            return pd.DataFrame(columns=columnas)
        out = self.repo.materias().vinculos_lote(ids)
        if out.empty:
            return pd.DataFrame(columns=columnas)
        out["tipo_espacio"] = out.apply(
            lambda r: R.tipo_espacio_curricular_v120(r.get("codigo", ""), r.get("asignatura", "")), axis=1)
        if solo_vigentes:
            en_plan = pd.to_numeric(out["en_plan"], errors="coerce").fillna(1).astype(int)
            estado = out["estado"].fillna("Activa").astype(str).str.strip().str.lower()
            out = out[(en_plan == 1) & estado.isin(["", "activa"])].copy()
        for col in columnas:
            if col not in out.columns:
                out[col] = ""
        return out[columnas].reset_index(drop=True)

    def vinculos_opcion_curricular_v120(self, opcion_id, solo_vigentes=False) -> pd.DataFrame:
        try:
            oid = int(opcion_id)
        except Exception:
            return pd.DataFrame()
        return self.vinculos_opciones_lote_v127([oid], solo_vigentes=bool(solo_vigentes))

    def opciones_curriculares_v120(self, tipo=None, estado=None) -> pd.DataFrame:
        tipo_f = tipo if tipo in TIPOS_OPCION_CURRICULAR else None
        estado_f = estado if estado in ESTADOS_OPCION_CURRICULAR else None
        df = self.repo.materias().opciones(tipo_f, estado_f)
        columnas_extra = ["cantidad_habilitaciones", "destinos", "carreras_habilitadas", "escuelas_destino",
                          "espacios_plan"]
        for col in columnas_extra:
            df[col] = "" if col != "cantidad_habilitaciones" else 0
        if df.empty:
            return df
        ids = pd.to_numeric(df["id"], errors="coerce").dropna().astype(int).tolist()
        vinculos = self.vinculos_opciones_lote_v127(ids, solo_vigentes=True)
        if vinculos.empty:
            return df
        grupos = {int(k): g.copy() for k, g in vinculos.groupby("opcion_id", sort=False)}
        for i, row in df.iterrows():
            try:
                oid = int(row["id"])
            except Exception:
                continue
            vinc = grupos.get(oid, pd.DataFrame())
            if vinc.empty:
                continue
            destinos = []
            for _, v in vinc.iterrows():
                partes = []
                carrera = R.limpiar_texto_tabla(v.get("carrera", ""))
                espacio = R.limpiar_texto_tabla(v.get("asignatura", ""))
                codigo = R.limpiar_texto_tabla(v.get("codigo", ""))
                plan = R.limpiar_texto_tabla(v.get("plan_version", ""))
                if carrera:
                    partes.append(carrera)
                if codigo or espacio:
                    partes.append(f"{codigo} - {espacio}".strip(" -"))
                if plan:
                    partes.append(plan)
                if partes:
                    destinos.append(" · ".join(partes))
            df.at[i, "cantidad_habilitaciones"] = int(len(vinc))
            df.at[i, "destinos"] = " | ".join(destinos)
            df.at[i, "carreras_habilitadas"] = R.deptit_join_unicos(vinc.get("carrera", pd.Series(dtype=str)).tolist(),
                                                                    sep=" / ")
            df.at[i, "escuelas_destino"] = R.deptit_join_unicos(vinc.get("escuela", pd.Series(dtype=str)).tolist(),
                                                                sep=" / ")
            df.at[i, "espacios_plan"] = R.deptit_join_unicos([
                f"{R.limpiar_texto_tabla(v.get('codigo', ''))} - {R.limpiar_texto_tabla(v.get('asignatura', ''))}".strip(" -")
                for _, v in vinc.iterrows()
            ], sep=" / ")
        return df

    def opciones_curriculares_para_materia_v120(self, materia_id) -> pd.DataFrame:
        try:
            mid = int(materia_id)
        except Exception:
            return pd.DataFrame()
        mat = self.materia_comision(mid) or {}
        tipo = R.tipo_espacio_curricular_v120(mat.get("codigo", ""), mat.get("asignatura", ""))
        if not tipo:
            return pd.DataFrame()
        ids_grupo = set(R.ids_materia_v118(mat.get("materia_ids", "")) or [mid])
        opciones = self.opciones_curriculares_v120(tipo=tipo, estado="Activa")
        if opciones.empty:
            return opciones
        ids_opciones = pd.to_numeric(opciones["id"], errors="coerce").dropna().astype(int).tolist()
        vinculos = self.vinculos_opciones_lote_v127(ids_opciones, solo_vigentes=True)
        if vinculos.empty:
            return pd.DataFrame(columns=list(opciones.columns) + ["materia_ids_habilitados", "cantidad_planes"])
        registros = []
        por_opcion = {int(k): g.copy() for k, g in vinculos.groupby("opcion_id", sort=False)}
        for _, op in opciones.iterrows():
            oid = int(op["id"])
            vinc = por_opcion.get(oid, pd.DataFrame())
            if vinc.empty:
                continue
            ids_v = set(pd.to_numeric(vinc["materia_id"], errors="coerce").dropna().astype(int).tolist())
            if not (ids_v & ids_grupo):
                continue
            r = op.to_dict()
            r["materia_ids_habilitados"] = ",".join(str(x) for x in sorted(ids_v))
            r["cantidad_planes"] = len(ids_v)
            registros.append(r)
        return pd.DataFrame(registros).reset_index(drop=True)

    def buscar_opcion_curricular_para_materia_v120(self, materia_id, texto) -> dict:
        texto = R.limpiar_texto_tabla(texto)
        if not texto:
            return {"estado": "ERROR", "motivo": "Falta indicar la opción curricular concreta.", "opcion": None}
        df = self.opciones_curriculares_para_materia_v120(materia_id)
        if df.empty:
            return {"estado": "ERROR",
                    "motivo": "No hay opciones curriculares activas habilitadas para este espacio del plan.",
                    "opcion": None}
        q = R.normalizar_clave(texto)
        qcod = R.normalizar_codigo_materia(texto)
        etiquetas = df.apply(lambda r: R.normalizar_clave(R.etiqueta_opcion_curricular_v120(r)), axis=1)
        exactos = df[(df["nombre"].apply(R.normalizar_clave) == q) | (etiquetas == q)].copy()
        if exactos.empty and qcod:
            exactos = df[df["codigo"].apply(R.normalizar_codigo_materia) == qcod].copy()
        if len(exactos) == 1:
            return {"estado": "OK", "motivo": "Opción curricular identificada.", "opcion": exactos.iloc[0].to_dict()}
        if len(exactos) > 1:
            return {"estado": "ERROR", "motivo": ("La opción indicada coincide con más de un registro. Usá el código o la "
                                                  "etiqueta completa mostrada por el sistema."), "opcion": None}
        parciales = df[
            df["nombre"].apply(lambda v: q in R.normalizar_clave(v))
            | df["codigo"].apply(lambda v: qcod in R.normalizar_codigo_materia(v) if qcod else False)
        ].copy()
        if len(parciales) == 1:
            return {"estado": "ADVERTENCIA", "motivo": "Opción curricular encontrada por coincidencia parcial.",
                    "opcion": parciales.iloc[0].to_dict()}
        return {"estado": "ERROR", "motivo": "No se pudo identificar de forma única la opción curricular habilitada.",
                "opcion": None}

    def vinculos_opcion_para_espacio_seleccionado_v128(self, materia_id, opcion_curricular_id, solo_vigentes=True):
        try:
            mid = int(materia_id)
            oid = int(opcion_curricular_id)
        except Exception:
            return pd.DataFrame()
        mat = self.materia_comision(mid) or {}
        ids_grupo = set(R.ids_materia_v118(mat.get("materia_ids", "")) or [mid])
        vinc = self.vinculos_opcion_curricular_v120(oid, solo_vigentes=solo_vigentes)
        if vinc is None or vinc.empty or "materia_id" not in vinc.columns:
            return pd.DataFrame(columns=list(vinc.columns) if isinstance(vinc, pd.DataFrame) else [])
        mids = pd.to_numeric(vinc["materia_id"], errors="coerce").astype("Int64")
        return vinc[mids.isin(ids_grupo)].copy().reset_index(drop=True)

    # ------------------------------------------------------------------ composicion
    @staticmethod
    def _snapshot(materia_id_v, val, fila_mapa=None) -> dict:
        carrera_id = val("carrera_id", None)
        try:
            carrera_id = int(carrera_id) if carrera_id is not None and str(carrera_id).strip() != "" else None
        except Exception:
            carrera_id = None
        codigo_fb = fila_mapa.get("codigo", "") if fila_mapa is not None else ""
        asignatura_fb = fila_mapa.get("asignatura", "") if fila_mapa is not None else ""
        carga_sem = val("carga_semanal", "")
        carga_tot = val("carga_total", "")
        return {
            "materia_id": int(materia_id_v),
            "carrera_id_snapshot": carrera_id,
            "carrera_snapshot": R.limpiar_texto_tabla(val("carrera", "")),
            "escuela_snapshot": R.limpiar_texto_tabla(val("escuela", "")),
            "plan_version_snapshot": R.limpiar_texto_tabla(val("plan_version", "")),
            "anio_snapshot": R.limpiar_texto_tabla(val("anio", "")),
            "cuatrimestre_snapshot": R.limpiar_texto_tabla(val("cuatrimestre", "")),
            "dictado_snapshot": R.limpiar_texto_tabla(val("dictado", "")),
            "carga_semanal_snapshot": R.limpiar_texto_tabla(str(carga_sem)) if carga_sem not in [None, ""] else "",
            "carga_total_snapshot": R.limpiar_texto_tabla(str(carga_tot)) if carga_tot not in [None, ""] else "",
            "codigo_snapshot": R.limpiar_texto_tabla(val("codigo", codigo_fb) or codigo_fb),
            "asignatura_snapshot": R.limpiar_texto_tabla(val("asignatura", asignatura_fb) or asignatura_fb),
        }

    def preparar_vinculos_materias_comision_v118(self, materia_id, incluir_historicas=False) -> list[dict]:
        try:
            mid = int(materia_id)
        except Exception:
            return []
        df_unicas, df_mapa = self.unificadas_y_mapa()
        df_detalle = self.materias_detalle()
        ids = []
        fila_mapa = None
        if isinstance(df_mapa, pd.DataFrame) and not df_mapa.empty and "materia_id" in df_mapa.columns:
            mids_mapa = pd.to_numeric(df_mapa["materia_id"], errors="coerce").astype("Int64")
            fm = df_mapa[mids_mapa == mid]
            if not fm.empty:
                fila_mapa = fm.iloc[0]
        if incluir_historicas and fila_mapa is not None:
            ids = R.ids_materia_v118(fila_mapa.get("materia_ids", ""))
        else:
            fila_activa = pd.DataFrame()
            if isinstance(df_unicas, pd.DataFrame) and not df_unicas.empty and "materia_id" in df_unicas.columns:
                mids_u = pd.to_numeric(df_unicas["materia_id"], errors="coerce").astype("Int64")
                fila_activa = df_unicas[mids_u == mid]
                if fila_activa.empty and fila_mapa is not None:
                    contiene_mid = df_unicas["materia_ids"].fillna("").astype(str).apply(
                        lambda x: mid in R.ids_materia_v118(x)
                    ) if "materia_ids" in df_unicas.columns else pd.Series(False, index=df_unicas.index)
                    fila_activa = df_unicas[contiene_mid]
            if not fila_activa.empty:
                ids = R.ids_materia_v118(fila_activa.iloc[0].get("materia_ids", ""))
            elif fila_mapa is not None:
                ids = R.ids_materia_v118(fila_mapa.get("materia_ids", ""))
        if not ids:
            ids = [mid]
        vinculos = []
        for materia_id_v in ids:
            fila = R.fila_materia_por_id_v118(df_detalle, materia_id_v)

            def val(nombre, default="", fila=fila):
                if fila is None:
                    return default
                try:
                    v = fila.get(nombre, default)
                except Exception:
                    return default
                try:
                    if pd.isna(v):
                        return default
                except Exception:
                    pass
                return v
            vinculos.append(self._snapshot(materia_id_v, val, fila_mapa))
        return vinculos

    def preparar_vinculos_materias_comision_v120(self, materia_id, opcion_curricular_id=None, incluir_historicas=False):
        if opcion_curricular_id in [None, ""]:
            return self.preparar_vinculos_materias_comision_v118(materia_id, incluir_historicas=incluir_historicas)
        mid = int(materia_id)
        oid = int(opcion_curricular_id)
        mat = self.materia_comision(mid) or {}
        tipo_espacio = R.tipo_espacio_curricular_v120(mat.get("codigo", ""), mat.get("asignatura", ""))
        if not tipo_espacio:
            raise ValueError("Solo las Optativas/Electivas pueden asociarse a una opción curricular.")
        op = self.opcion_curricular_v120(oid)
        if not op:
            raise ValueError("No se encontró la opción curricular seleccionada.")
        if R.normalizar_tipo_opcion_v120(op.get("tipo")) != tipo_espacio:
            raise ValueError("La opción curricular no corresponde al tipo del espacio seleccionado.")
        vinc_df = self.vinculos_opcion_para_espacio_seleccionado_v128(mid, oid, solo_vigentes=not incluir_historicas)
        if vinc_df.empty:
            raise ValueError("La opción curricular no está habilitada para el espacio del plan seleccionado.")
        detalle = self.materias_detalle()
        vinculos = []
        ids_validos = set(pd.to_numeric(vinc_df["materia_id"], errors="coerce").dropna().astype(int).tolist())
        for materia_id_v in sorted(ids_validos):
            fila = R.fila_materia_por_id_v118(detalle, materia_id_v)
            if fila is None:
                continue

            def val(nombre, default="", fila=fila):
                try:
                    v = fila.get(nombre, default)
                    return default if pd.isna(v) else v
                except Exception:
                    return default
            vinculos.append(self._snapshot(materia_id_v, val))
        if not vinculos:
            raise ValueError("No se pudieron resolver los planes vinculados al espacio formal seleccionado.")
        return vinculos

    def materias_conceptuales_seleccionadas_v122(self, materia_id, materia_ids_adicionales=None) -> list[dict]:
        entradas = [materia_id] + R.ids_materia_v118(materia_ids_adicionales)
        salida = []
        claves = set()
        for valor in entradas:
            try:
                mid = int(valor)
            except Exception:
                continue
            info = self.materia_comision(mid) or {}
            if not info:
                raise ValueError(f"No se encontró la materia seleccionada (ID {mid}).")
            try:
                rep = int(info.get("materia_id_unificada") or info.get("materia_id") or mid)
            except Exception:
                rep = mid
            codigo = R.limpiar_texto_tabla(info.get("codigo", ""))
            asignatura = R.limpiar_texto_tabla(info.get("asignatura", ""))
            clave = R.limpiar_texto_tabla(info.get("_clave_unica", "")) or R.clave_materia_conceptual_v137(info) or f"ID:{rep}"
            if clave in claves:
                continue
            claves.add(clave)
            salida.append({"materia_id": rep, "codigo": codigo, "asignatura": asignatura, "info": info, "clave": clave,
                           "es_optativa_electiva": R.es_materia_optativa_electiva(codigo, asignatura)})
        if not salida:
            raise ValueError("Seleccioná al menos una materia para la comisión.")
        return salida

    def preparar_vinculos_multiples_materias_comision_v122(self, materia_id, materia_ids_adicionales=None,
                                                           opcion_curricular_id=None, incluir_historicas=False):
        seleccion = self.materias_conceptuales_seleccionadas_v122(materia_id, materia_ids_adicionales)
        if len(seleccion) > 1 and any(x["es_optativa_electiva"] for x in seleccion):
            raise ValueError(
                "Una comisión con varios códigos no puede mezclar espacios Optativa/Electiva. "
                "Esos espacios siguen administrándose con una opción curricular concreta por comisión."
            )
        if len(seleccion) == 1 and seleccion[0]["es_optativa_electiva"]:
            return self.preparar_vinculos_materias_comision_v120(seleccion[0]["materia_id"],
                                                                 opcion_curricular_id=opcion_curricular_id,
                                                                 incluir_historicas=incluir_historicas)
        vinculos = []
        vistos = set()
        for item in seleccion:
            grupo = self.preparar_vinculos_materias_comision_v118(item["materia_id"], incluir_historicas=incluir_historicas)
            for v in grupo:
                try:
                    mid = int(v.get("materia_id"))
                except Exception:
                    continue
                if mid in vistos:
                    continue
                vistos.add(mid)
                vinculos.append(v)
        if not vinculos:
            raise ValueError("No se pudieron resolver las materias/planes que integran la comisión.")
        return vinculos

    def claves_materias_comision_v122(self, materia_id, materia_ids_adicionales=None):
        seleccion = self.materias_conceptuales_seleccionadas_v122(materia_id, materia_ids_adicionales)
        return frozenset(x["clave"] for x in seleccion)

    def claves_comision_existente_v122(self, comision_id):
        reps = self.materias_conceptuales_comision_v122(comision_id)
        if not reps:
            return frozenset()
        claves = set()
        for rep in reps:
            info = self.materia_comision(rep) or {}
            clave = R.limpiar_texto_tabla(info.get("_clave_unica", "")) or R.clave_materia_conceptual_v137(info) or f"ID:{int(rep)}"
            claves.add(clave)
        return frozenset(claves)

    def descripcion_materias_comision_v122(self, materia_id, materia_ids_adicionales=None) -> str:
        seleccion = self.materias_conceptuales_seleccionadas_v122(materia_id, materia_ids_adicionales)
        partes = []
        for x in seleccion:
            pref = f"{x['codigo']} - " if x["codigo"] else ""
            partes.append(f"{pref}{x['asignatura']}".strip())
        return " / ".join([p for p in partes if p])

    def existe_comision_duplicada(self, periodo_id, materia_id, nombre_comision, turno, sede, modalidad,
                                  excluir_id=None, opcion_curricular_id=None, materia_especifica="",
                                  materia_ids_adicionales=None) -> pd.DataFrame:
        try:
            seleccion = self.materias_conceptuales_seleccionadas_v122(materia_id, materia_ids_adicionales)
            es_oe = len(seleccion) == 1 and seleccion[0]["es_optativa_electiva"]
            if len(seleccion) > 1 and any(x["es_optativa_electiva"] for x in seleccion):
                return pd.DataFrame()
            claves_sel = frozenset(x["clave"] for x in seleccion)
            df = self.comisiones(periodo_id=periodo_id, solo_activas=False)
            if df is None or df.empty:
                return pd.DataFrame()
            df = df.copy()
            base = (
                (df["nombre_comision"].fillna("").astype(str).str.strip().str.upper() == str(nombre_comision or "").strip().upper())
                & (df["turno"].fillna("").astype(str).str.strip().str.upper() == str(turno or "").strip().upper())
                & (df["sede"].fillna("").astype(str).str.strip().str.upper() == str(sede or "").strip().upper())
                & (df["modalidad"].fillna("").astype(str).str.strip().str.upper() == str(modalidad or "").strip().upper())
            )
            if excluir_id is not None and "id" in df.columns:
                base = base & (pd.to_numeric(df["id"], errors="coerce") != int(excluir_id))
            candidatos = df[base].copy()
            if candidatos.empty:
                return pd.DataFrame()
            if es_oe and opcion_curricular_id not in [None, ""]:
                oid = int(opcion_curricular_id)
                ids_op = pd.to_numeric(candidatos.get("opcion_curricular_id",
                                                      pd.Series(index=candidatos.index, dtype=float)),
                                       errors="coerce").astype("Int64")
                candidatos_op = candidatos[ids_op == oid].copy()
                for _, fila in candidatos_op.iterrows():
                    try:
                        cid = int(fila.get("id"))
                    except Exception:
                        continue
                    claves_existentes = self.claves_comision_existente_v122(cid)
                    if claves_existentes and (claves_existentes & claves_sel):
                        return candidatos_op[pd.to_numeric(candidatos_op["id"], errors="coerce") == cid].head(1)\
                            .reset_index(drop=True)
                return pd.DataFrame()
            for _, fila in candidatos.iterrows():
                try:
                    cid = int(fila.get("id"))
                except Exception:
                    continue
                claves_existentes = self.claves_comision_existente_v122(cid)
                if claves_existentes and (claves_existentes & claves_sel):
                    if es_oe:
                        esp = R.normalizar_clave(materia_especifica or "")
                        if R.normalizar_clave(fila.get("materia_especifica", "")) != esp:
                            continue
                    return candidatos[pd.to_numeric(candidatos["id"], errors="coerce") == cid].head(1)\
                        .reset_index(drop=True)
            return pd.DataFrame()
        except Exception:
            return self.repo.duplicada_fallback(periodo_id, nombre_comision, turno, sede, modalidad, materia_id,
                                                opcion_curricular_id, excluir_id)
