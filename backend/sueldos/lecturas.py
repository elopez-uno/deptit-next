"""Lecturas y motor de Sueldos (B13-FIX02) sobre un repositorio ya abierto.  Sin cache propia (el certificado no la
tiene: escalas, Resumen y v257 leen PostgreSQL en cada render).  Nunca escribe (sin repair-on-read).

Tres cadenas distintas, que NO se unifican (docs/sueldos_analysis.md §6):
1. Plantel del departamento (pagina l. 61860-61931): ``get_designaciones`` del departamento (lectura portada por
   Designaciones) + perfil ``get_docentes`` (Docentes); en el periodo actual solo Activas; en historico, todas.
2. Resumen docente (``construir_tabla_sueldo_docente_v256`` l. 25723): ``get_designaciones_docente_todos_departamentos_pg``
   efectiva v162 (l. 34990) -> v149/v265 (sin columna ``ad_honorem``: toda designacion se valoriza como rentada;
   decision H2, DEUDA FUNCIONAL replicada en la Etapa 4).  Etapa 5 / Tanda B (B1): el Resumen NEXT valoriza
   ``designaciones_sueldo_resumen`` (ad_honorem restituido + solo Activas en el periodo no cerrado, como la base
   l. 26679 y el plantel) con la antiguedad y el posgrado de la ficha; la replica certificada queda para comparar.
3. Costos de proyectos (``calcular_costos_asignaciones_proyecto_v257`` l. 25759 + v258).
Escala aplicable: la ultima ``mes_referencia`` <= mes objetivo; mes objetivo = mes de HOY en el periodo actual y mes
de ``fecha_fin`` en uno historico (``_mes_ref_desde_periodo_v256`` l. 25488 + ``es_periodo_historico_contexto_v182``).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

import pandas as pd

from comisiones import proyectos as CP
from designaciones.repository import DesignacionesRepository
from designaciones.rules import es_periodo_historico
from docentes.repository import DocentesRepository

from . import rules as SR
from .repository import SueldosRepository


class _ComoUnidad:
    """Adaptador minimo para ``comisiones.proyectos.designaciones_periodo_institucional_v149`` (sin modificarla)."""

    def __init__(self, motor: "Motor"):
        self.inst = motor.repo.inst
        self._repo = motor.repo
        self.lector = self

    def periodo_equivalente_pg(self, periodo_id):
        return self._repo.periodo_equivalente(periodo_id)

    def read(self, fn):
        return fn(self._repo)


class Motor:
    def __init__(self, repo: SueldosRepository, today: date):
        self.repo = repo
        self.today = today
        self._escalas: Optional[pd.DataFrame] = None

    # ------------------------------------------------------------------ escalas
    def escalas(self) -> pd.DataFrame:
        """``get_escalas_salariales_v256`` (una lectura por operacion; cada operacion relee la base)."""
        if self._escalas is None:
            self._escalas = self.repo.escalas()
        return self._escalas

    def escala_mes(self, mes) -> dict:
        return SR.escala_salarial_mes_v256(self.escalas(), mes)

    def escala_aplicable(self, mes_objetivo=None) -> tuple[Optional[str], dict]:
        return SR.escala_aplicable_v256(self.escalas(), mes_objetivo, self.today)

    def meses_disponibles(self) -> list[str]:
        df = self.escalas()
        if df.empty:
            return []
        return sorted(df.get("mes_referencia", pd.Series(dtype=str)).dropna().astype(str).unique().tolist(), reverse=True)

    # ------------------------------------------------------------------ periodos (departamento de la sesion)
    def _drep(self) -> DesignacionesRepository:
        if self.repo.dep is None:
            raise LookupError("sin departamento")
        return DesignacionesRepository(self.repo._conn, self.repo.inst, self.repo.dep)

    def periodos(self) -> list[dict]:
        return self._drep().periods()

    def periodo_abierto(self) -> Optional[dict]:
        return self._drep().open_period()

    def ultimo_periodo(self) -> Optional[dict]:
        return self._drep().last_period()

    def es_historico(self, periodo_id) -> bool:
        """``es_periodo_historico_contexto_v182`` (l. 39224)."""
        try:
            info = self._drep().period_info(int(periodo_id)) if periodo_id is not None else None
            return es_periodo_historico(info, self.ultimo_periodo(), self.periodo_abierto())
        except Exception:
            return False

    def mes_ref_desde_periodo(self, periodo: Optional[dict]) -> str:
        """``_mes_ref_desde_periodo_v256`` (l. 25488)."""
        if not periodo:
            return SR.mes_ref_v256(self.today, self.today)
        try:
            pid = int(periodo.get("id"))
            if not self.es_historico(pid):
                return SR.mes_ref_v256(self.today, self.today)
        except Exception:
            pass
        return SR.mes_ref_v256(periodo.get("fecha_fin") or self.today, self.today)

    # ------------------------------------------------------------------ 1. plantel del departamento
    def plantel(self, periodo: dict) -> dict:
        """Pestaña "👥 Sueldos del plantel" (l. 61876-61931) para el periodo elegido (fila de ``get_periodos``)."""
        per_id = int(periodo["id"])
        mes_obj = self.mes_ref_desde_periodo(periodo)
        mes_esc, escala = self.escala_aplicable(mes_obj)
        if not escala:
            return {"estado": "sin_escala", "mes_objetivo": mes_obj}
        drep = self._drep()
        df_d = pd.DataFrame(drep.designaciones(per_id))
        base = {"mes_objetivo": mes_obj, "mes_escala": mes_esc}
        if df_d.empty:
            return {"estado": "sin_designaciones", **base}
        historico = self.es_historico(per_id)
        if not historico and "estado" in df_d.columns:
            df_d = df_d[df_d["estado"].fillna("Activa").astype(str).str.casefold().eq("activa")].copy()
        perfil = {}
        for rr in DocentesRepository(self.repo._conn, self.repo.inst, self.repo.dep).docentes():
            perfil[SR.clave_cuil(rr.get("cuil"))] = dict(rr)
        filas = []
        for _, rr in df_d.iterrows():
            pf = perfil.get(SR.clave_cuil(rr.get("cuil")), {})
            calc = SR.calcular_sueldo_designacion_v256(rr.get("cargo"), rr.get("dedicacion"), rr.get("ad_honorem", "No"),
                                                       pf.get("antiguedad_anios"), pf.get("nivel_posgrado_salarial", ""),
                                                       escala)
            antig_inf = SR.antiguedad_informada(pf.get("antiguedad_anios"))
            filas.append({
                "Docente": rr.get("nombre_completo", "") or pf.get("nombre_completo", ""),
                "CUIL": rr.get("cuil", ""),
                "Cargo": rr.get("cargo", ""),
                "Dedicación": rr.get("dedicacion", ""),
                "Antigüedad": f"{SR.antiguedad_entera_v256(pf.get('antiguedad_anios'))} años"
                              + ("" if antig_inf else " (no informada)"),
                "% antig.": f"{calc['porcentaje_antiguedad']*100:.0f}%",
                "Posgrado": SR.nivel_posgrado_v256(pf.get("nivel_posgrado_salarial", "")) or "-",
                "% posgrado": f"{calc['porcentaje_posgrado']*100:.0f}%",
                "Ad Honorem": "Sí" if calc["ad_honorem"] else "No",
                "Básico dedicación": calc["basico_dedicacion"],
                "Sueldo estimado": calc["total_estimado"],
            })
        df_calc = pd.DataFrame(filas)
        if df_calc.empty:
            return {"estado": "vacio", **base}
        total = float(pd.to_numeric(df_calc["Sueldo estimado"], errors="coerce").fillna(0).sum())
        docs_unicos = int(df_calc["CUIL"].astype(str).map(SR.clave_cuil).nunique())
        return {"estado": "ok", **base, "historico": bool(historico), "docentes": docs_unicos,
                "designaciones": int(len(df_calc)), "total": total, "filas": filas}

    # ------------------------------------------------------------------ 2. Resumen docente (cadena v162/v149)
    def designaciones_todos_departamentos_v162(self, cuil, periodo_id) -> pd.DataFrame:
        """``get_designaciones_docente_todos_departamentos_pg`` efectiva (v162 l. 34990 sobre base l. 26679)."""
        try:
            if not str(cuil or "").strip():
                base = pd.DataFrame()
            else:
                filtrar = None
                if periodo_id is not None:
                    try:
                        estado = self.repo.estado_periodo_local(int(periodo_id)) if self.repo.dep is not None else None
                        filtrar = estado is not None and estado.strip().lower() != "cerrado"
                    except Exception:
                        filtrar = True
                base = self.repo.todos_deptos_base(SR.clave_cuil(cuil), periodo_id, filtrar)
        except Exception:
            base = pd.DataFrame()
        out = base.copy()
        inst = pd.DataFrame()
        if periodo_id is not None:
            try:
                inst = CP.designaciones_periodo_institucional_v149(_ComoUnidad(self), cuil, periodo_id)
                if inst is not None and not inst.empty:
                    out = inst.copy()
            except Exception:
                inst = pd.DataFrame()
            try:
                if inst is not None and not inst.empty:
                    susp = inst[inst.get("estado", pd.Series(index=inst.index, dtype=str))
                                .fillna("").astype(str).str.strip().str.casefold().eq("suspendida")].copy()
                    if not susp.empty:
                        cols = ["departamento", "periodo", "cargo", "dedicacion", "horas", "tipo_designacion", "estado",
                                "fecha_desde", "fecha_hasta", "observaciones"]
                        for col in cols:
                            if col not in susp.columns:
                                susp[col] = ""
                        out = pd.concat([out, susp[cols]], ignore_index=True, sort=False)
                        claves_dup = [c for c in ["departamento", "periodo", "cargo", "dedicacion", "tipo_designacion",
                                                  "fecha_desde", "fecha_hasta"] if c in out.columns]
                        if claves_dup:
                            out = out.drop_duplicates(subset=claves_dup, keep="first")
            except Exception:
                pass
        if not out.empty and "estado" in out.columns:
            out["estado"] = out["estado"].map(SR.estado_designacion_visible_v162)
        if not out.empty and "funcion_no_docente" in out.columns:
            from designaciones.rules import es_funcion_no_docente
            out["funcion_no_docente"] = out["funcion_no_docente"].map(
                lambda x: "No docente" if es_funcion_no_docente(x) else "Docencia")
        if "texto_funcion_no_docente" in out.columns:
            out["texto_funcion_no_docente"] = out["texto_funcion_no_docente"].fillna("").astype(str)
        out = out.rename(columns={"funcion_no_docente": "Función", "texto_funcion_no_docente": "Funciones no docentes",
                                  "numero_resolucion": "N° resolución"})
        return out.reset_index(drop=True)

    def designaciones_sueldo_resumen(self, cuil, periodo_id) -> pd.DataFrame:
        """Etapa 5 / Tanda B (B1): fuente CORREGIDA del sueldo estimado del Resumen docente.

        La fuente base certificada (l. 26679, ``todos_deptos_base``) trae ``ad_honorem`` y, con el periodo del
        departamento no cerrado, solo designaciones Activas (la misma regla del plantel de Sueldos); la v162 la
        reemplazo por la v149 institucional, que perdio las dos cosas (H2: la designacion Ad Honorem se valorizaba como
        rentada y se sumaban Suspendidas, Finalizadas y Bajas del periodo actual, contra el propio caption certificado
        "las designaciones Ad Honorem computan $0").  Se conservan las filas v149/v265 (institucion de la sesion, todos
        sus departamentos, periodo equivalente) y se restituyen ``ad_honorem`` (por id de designacion, misma
        institucion) y el filtro de Activas de la base.  El saneamiento v265 (dedup por departamento, cargo,
        dedicacion, tipo, estado, horas, fechas y funcion) se aplica por separado a rentadas y Ad Honorem: su clave no
        incluye ``ad_honorem`` porque la v149 no lo traia, y dos designaciones reales iguales salvo esa condicion
        (una rentada y otra Ad Honorem) no deben fusionarse en una sola."""
        clave = SR.clave_cuil(cuil)
        if not clave or periodo_id is None:
            return pd.DataFrame()
        try:
            estado = self.repo.estado_periodo_local(int(periodo_id)) if self.repo.dep is not None else None
            filtrar = estado is not None and estado.strip().lower() != "cerrado"
        except Exception:
            filtrar = True
        try:
            nombre_p, anio, semestre = self.repo.periodo_equivalente(periodo_id)
            raw = self.repo.read_raw(CP.DESIG_INST_V149_SQL, [int(self.repo.inst), clave, int(periodo_id), nombre_p,
                                                             int(anio), int(semestre)])
        except Exception:
            raw = pd.DataFrame()
        if raw is None or raw.empty:
            return self.repo.todos_deptos_base(clave, periodo_id, filtrar)
        inst = int(self.repo.inst)
        extra = self.repo.read_raw(CP.FUNCION_INST_V162_SQL, [inst, clave])
        adh = self.repo.read_raw("SELECT id, COALESCE(ad_honorem, 'No') AS ad_honorem FROM designaciones "
                                 "WHERE institucion_id = %s AND regexp_replace(COALESCE(cuil, ''), '[^0-9]', '', 'g') = %s",
                                 [inst, clave])
        out = raw.merge(extra, on="id", how="left").merge(adh, on="id", how="left")
        out["funcion_no_docente"] = pd.to_numeric(out["funcion_no_docente"], errors="coerce").fillna(0).astype(int)
        out["texto_funcion_no_docente"] = out["texto_funcion_no_docente"].fillna("").astype(str)
        out["ad_honorem"] = out["ad_honorem"].fillna("No")
        out["_orden_b1"] = range(len(out))
        es_adh = out["ad_honorem"].map(SR.es_ad_honorem_v162)
        out = pd.concat([CP._sanear_designaciones_institucionales_v265(out[es_adh == v]) for v in (False, True)],
                        ignore_index=True).sort_values("_orden_b1").drop(columns=["_orden_b1"])
        if filtrar and "estado" in out.columns:
            out = out[out["estado"].fillna("Activa").astype(str).str.strip().eq("Activa")]
        return out.reset_index(drop=True)

    def construir_tabla_sueldo_docente(self, cuil, periodo_id, antiguedad_anios, nivel_posgrado,
                                       mes_objetivo, fuente: Optional[pd.DataFrame] = None
                                       ) -> tuple[Optional[str], pd.DataFrame, float]:
        """``construir_tabla_sueldo_docente_v256`` (l. 25723).  Con la fuente efectiva certificada (v162) el
        ``ad_honorem`` NO llega: ``r.get("ad_honorem", "No")`` -> "No" (H2).  ``fuente``: filas a valorizar en lugar
        de la v162 (el Resumen NEXT pasa ``designaciones_sueldo_resumen``, Etapa 5 / B1)."""
        mes_escala, escala = self.escala_aplicable(mes_objetivo)
        if not escala:
            return mes_escala, pd.DataFrame(), 0.0
        df = self.designaciones_todos_departamentos_v162(cuil, periodo_id) if fuente is None else fuente
        if df is None or df.empty:
            return mes_escala, pd.DataFrame(), 0.0
        filas = []
        for _, r in df.iterrows():
            calc = SR.calcular_sueldo_designacion_v256(r.get("cargo"), r.get("dedicacion"), r.get("ad_honorem", "No"),
                                                       antiguedad_anios, nivel_posgrado, escala)
            filas.append({
                "Departamento": r.get("departamento", "") or "",
                "Cargo": r.get("cargo", "") or "",
                "Dedicación": r.get("dedicacion", "") or "",
                "Ad Honorem": "Sí" if calc["ad_honorem"] else "No",
                "Básico simple": calc["basico_simple"],
                "Básico dedicación": calc["basico_dedicacion"],
                "Antigüedad": f"{SR.antiguedad_entera_v256(antiguedad_anios)} años "
                              f"({calc['porcentaje_antiguedad']*100:.0f}%)",
                "Posgrado": (SR.nivel_posgrado_v256(nivel_posgrado) or "Sin adicional")
                            + f" ({calc['porcentaje_posgrado']*100:.0f}%)",
                "Adic. antigüedad": calc["adicional_antiguedad"],
                "Adic. posgrado": calc["adicional_posgrado"],
                "Sueldo estimado": calc["total_estimado"],
            })
        out = pd.DataFrame(filas)
        total = float(pd.to_numeric(out.get("Sueldo estimado"), errors="coerce").fillna(0).sum()) if not out.empty else 0.0
        return mes_escala, out, round(total, 2)

    # ------------------------------------------------------------------ 3. costos de proyectos (v257/v258)
    def costos_asignaciones_v257(self, df_asignaciones: Optional[pd.DataFrame],
                                 periodo_contexto: Optional[dict]) -> tuple[Optional[str], pd.DataFrame, float]:
        """``calcular_costos_asignaciones_proyecto_v257`` (l. 25759)."""
        if df_asignaciones is None or not isinstance(df_asignaciones, pd.DataFrame) or df_asignaciones.empty:
            return None, pd.DataFrame(), 0.0
        try:
            periodo_id = int((periodo_contexto or {}).get("id"))
        except Exception:
            return None, df_asignaciones.copy(), 0.0

        mes_obj = self.mes_ref_desde_periodo(periodo_contexto or {"id": periodo_id})
        mes_escala, escala = self.escala_aplicable(mes_obj)
        salida = df_asignaciones.copy()
        for col, default in [
            ("cargo_salarial_v257", ""), ("dedicacion_salarial_v257", ""),
            ("condicion_salarial_v257", "Sin designación"),
            ("horas_contractuales_rentadas_v257", 0.0),
            ("sueldo_mensual_docente_v257", 0.0),
            ("tarifa_mensual_por_hora_v257", 0.0),
            ("costo_mensual_proyecto_v257", 0.0),
            ("meses_ejecucion_v258", 0),
            ("costo_total_proyecto_v258", 0.0),
        ]:
            salida[col] = default
        if not escala:
            return mes_escala, salida, 0.0

        cuiles = sorted({SR.clave_cuil(v) for v in salida.get("cuil", pd.Series(dtype=str)).tolist() if SR.clave_cuil(v)})
        if not cuiles:
            return mes_escala, salida, 0.0

        try:
            nombre_p, anio_p, semestre_p = self.repo.periodo_equivalente(periodo_id)
            historico = bool(self.es_historico(periodo_id))
            df_des = self.repo.costos_designaciones(periodo_id, nombre_p, anio_p, semestre_p, cuiles, historico)
            df_perfiles = self.repo.costos_perfiles(cuiles)
        except Exception:
            df_des = pd.DataFrame()
            df_perfiles = pd.DataFrame()
        dep_sesion = self.repo.dep

        if not df_des.empty:
            df_des["_cuil_v257"] = df_des.get("cuil", pd.Series(index=df_des.index, dtype=str)).map(SR.clave_cuil)
            if "departamento_id" not in df_des.columns:
                df_des["departamento_id"] = dep_sesion
        if not df_perfiles.empty:
            df_perfiles["_cuil_v257"] = df_perfiles.get("cuil", pd.Series(index=df_perfiles.index, dtype=str)).map(
                SR.clave_cuil)
            if "departamento_id" not in df_perfiles.columns:
                df_perfiles["departamento_id"] = dep_sesion

        def _dep_int(v, fallback=None):
            try:
                if v is None or pd.isna(v):
                    return fallback
            except Exception:
                pass
            try:
                return int(v)
            except Exception:
                return fallback

        total_imputado = 0.0
        for idx, asig in salida.iterrows():
            ckey = SR.clave_cuil(asig.get("cuil"))
            dep_id = _dep_int(asig.get("departamento_asignacion_id"), dep_sesion)
            sub_des = pd.DataFrame()
            if not df_des.empty and ckey:
                sub_des = df_des[df_des["_cuil_v257"].eq(ckey)].copy()
                if dep_id is not None and "departamento_id" in sub_des.columns:
                    exactas = sub_des[pd.to_numeric(sub_des["departamento_id"], errors="coerce").eq(float(dep_id))].copy()
                    if not exactas.empty:
                        sub_des = exactas
                    # Sin designacion local (docente prestado): se usa la designacion formal de origen.

            pf: dict = {}
            if not df_perfiles.empty and ckey:
                sub_pf = df_perfiles[df_perfiles["_cuil_v257"].eq(ckey)].copy()
                if dep_id is not None and not sub_pf.empty:
                    exact_pf = sub_pf[pd.to_numeric(sub_pf["departamento_id"], errors="coerce").eq(float(dep_id))]
                    if not exact_pf.empty:
                        sub_pf = exact_pf
                if not sub_pf.empty:
                    pf = sub_pf.iloc[0].to_dict()

            sueldo_total = 0.0
            horas_rentadas = 0.0
            cargos: list[str] = []
            dedicaciones: list[str] = []
            tiene_rentada = False
            tiene_adh = False
            if isinstance(sub_des, pd.DataFrame) and not sub_des.empty:
                for _, des in sub_des.iterrows():
                    calc = SR.calcular_sueldo_designacion_v256(des.get("cargo"), des.get("dedicacion"),
                                                               des.get("ad_honorem", "No"), pf.get("antiguedad_anios"),
                                                               pf.get("nivel_posgrado_salarial", ""), escala)
                    cargo_txt = str(des.get("cargo") or "").strip()
                    ded_txt = str(des.get("dedicacion") or "").strip()
                    if cargo_txt and cargo_txt not in cargos:
                        cargos.append(cargo_txt)
                    if ded_txt and ded_txt not in dedicaciones:
                        dedicaciones.append(ded_txt)
                    if calc["ad_honorem"]:
                        tiene_adh = True
                        continue
                    tiene_rentada = True
                    sueldo_total += float(calc["total_estimado"] or 0)
                    hs = pd.to_numeric(des.get("horas"), errors="coerce")
                    try:
                        hs = float(hs) if not pd.isna(hs) and float(hs) > 0 else 0.0
                    except Exception:
                        hs = 0.0
                    if hs <= 0:
                        hs = float(SR.HORAS_POR_DEDICACION.get(str(des.get("dedicacion") or "").strip(), 0) or 0)
                    horas_rentadas += hs

            horas_proyecto = pd.to_numeric(asig.get("horas_asignadas"), errors="coerce")
            try:
                horas_proyecto = float(horas_proyecto) if not pd.isna(horas_proyecto) else 0.0
            except Exception:
                horas_proyecto = 0.0
            tarifa = (sueldo_total / horas_rentadas) if horas_rentadas > 0 else 0.0
            costo = round(max(0.0, horas_proyecto) * tarifa, 2)
            meses_ejecucion = SR.meses_ejecucion_v258(asig.get("fecha_inicio"), asig.get("fecha_fin"))
            costo_total = round(costo * float(meses_ejecucion), 2) if meses_ejecucion > 0 else 0.0
            total_imputado += costo_total

            if tiene_rentada and tiene_adh:
                condicion = "Mixta (rentada + Ad Honorem)"
            elif tiene_rentada:
                condicion = "Rentada"
            elif tiene_adh:
                condicion = "Ad Honorem"
            else:
                condicion = "Sin designación"
            salida.at[idx, "cargo_salarial_v257"] = " + ".join(cargos)
            salida.at[idx, "dedicacion_salarial_v257"] = " + ".join(dedicaciones)
            salida.at[idx, "condicion_salarial_v257"] = condicion
            salida.at[idx, "horas_contractuales_rentadas_v257"] = round(horas_rentadas, 2)
            salida.at[idx, "sueldo_mensual_docente_v257"] = round(sueldo_total, 2)
            salida.at[idx, "tarifa_mensual_por_hora_v257"] = round(tarifa, 2)
            salida.at[idx, "costo_mensual_proyecto_v257"] = costo
            salida.at[idx, "meses_ejecucion_v258"] = int(meses_ejecucion)
            salida.at[idx, "costo_total_proyecto_v258"] = costo_total

        return mes_escala, salida, round(total_imputado, 2)


def ficha_salarial(motor: "Motor", cuil) -> dict:
    """Etapa 5 / Tanda B (B1): ``antiguedad_anios`` y ``nivel_posgrado_salarial`` de la FICHA del docente en el
    departamento de la sesion (``get_docentes``, la misma fuente del plantel).  Sin ficha: ``None`` / ``""``, que
    ``calcular_sueldo_designacion_v256`` trata como 0 anios (20 %) y sin adicional, igual que antes."""
    clave = SR.clave_cuil(cuil)
    if motor.repo.dep is not None and clave:
        for rr in DocentesRepository(motor.repo._conn, motor.repo.inst, motor.repo.dep).docentes():
            if SR.clave_cuil(rr.get("cuil")) == clave:
                return {"antiguedad_anios": rr.get("antiguedad_anios"),
                        "nivel_posgrado_salarial": SR.nivel_posgrado_v256(rr.get("nivel_posgrado_salarial", ""))}
    return {"antiguedad_anios": None, "nivel_posgrado_salarial": SR.nivel_posgrado_v256("")}


def costos_por_proyecto(detalle: pd.DataFrame) -> dict:
    """Agregado de la tabla de vigentes (l. 33222-33228): ``{proyecto_id(float): costo}``."""
    if not isinstance(detalle, pd.DataFrame) or detalle.empty or "proyecto_id" not in detalle.columns \
            or "costo_total_proyecto_v258" not in detalle.columns:
        return {}
    pid = pd.to_numeric(detalle["proyecto_id"], errors="coerce")
    val = pd.to_numeric(detalle.get("costo_total_proyecto_v258"), errors="coerce").fillna(0)
    tmp = pd.DataFrame({"pid": pid, "costo": val}).dropna(subset=["pid"])
    if tmp.empty:
        return {}
    return tmp.groupby("pid")["costo"].sum().to_dict()


__all__ = ["Motor", "costos_por_proyecto"]
