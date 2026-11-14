"""Lecturas certificadas de Investigacion (cadenas efectivas de B13-FIX02), sin cache de proceso.

``Lecturas`` envuelve un ``InvestigacionRepository`` (transaccion de lectura) o el repositorio perezoso de un writer
(cada lectura abre su conexion, como ``get_conn()`` / ``_pg_read_dataframe`` dentro del writer).  Reutiliza SIN
MODIFICAR el ``Lector`` de Comisiones (periodos, ``es_periodo_historico_contexto_v182``, ``get_designaciones``,
``get_plantel_periodo``) y las funciones de capacidad de ``comisiones/proyectos.py`` (decision D5).

Cadenas (entry):
- ``get_proyectos_investigacion``: v283 (piloto off) -> ``_get_proyectos_v199`` l. 45345 (bulk l. 45295).
- ``get_investigacion_docente``: v277 l. 47761 -> cache v191 -> v183 l. 39972 -> base l. 22041.
- ``buscar_asignacion_activa_docente_proyecto`` v217 l. 48248 (l. 48204); ``get_integrantes_activos_proyecto_periodo``
  v217 l. 48323 (l. 48268 + v277).
- Padron ``_docentes_asignables_proyectos_v217`` l. 47799 -> v276 l. 47458 -> ``_consolidado_desde_listados_reales_v240``
  l. 53142 -> ``_snapshot_listados_departamento_v240`` l. 53026 (decision D4: solo la lectura minima, sin pantalla).
- ``capacidad_proyectos_docente_v184`` l. 40242 con ``excluir_tipo`` / ``excluir_id``; ``detectar_excesos`` l. 40590;
  ``_detalle_proyectos_docente_v187`` l. 40705.
- ``get_documentos_proyectos_v263`` l. 51221; ``_documentos_repo_v266`` (repositorio de Designaciones, solo lectura).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Callable, Optional

import pandas as pd

from comisiones import proyectos as CP
from comisiones import rules as R
from comisiones.lecturas import Lector
from designaciones.rules import CARGOS, condicion_periodo_equivalente_sql, horas_segun_dedicacion

from . import rules as IR
from .repository import PERIODO_REF_CTE, InvestigacionRepository

COLS_PADRON = ["cuil", "nombre_completo", "legajo", "tipo_docente", "departamento_origen", "es_externo",
               "horas_designadas", "cargo", "cargo_final", "dedicacion", "estado_docente_base",
               "advertencia_disponibilidad"]
COLS_DOCS = ["proyecto_id", "documento_id", "tipo_documento", "numero", "dependencia_emisora", "fecha", "categoria",
             "detalle"]
CAP_VACIA = {"horas_contratadas": 0.0, "horas_comisiones": 0.0, "horas_no_lectivas": 0.0, "horas_investigacion": 0.0,
             "horas_extension": 0.0, "capacidad_total_proyectos": 0.0, "horas_proyectos_actuales": 0.0,
             "horas_disponibles_proyectos": 0.0, "exceso_proyectos": 0.0}


class _ComoUnidad:
    """Adaptador de lectura para las funciones de ``comisiones/proyectos.py`` (``u.read`` / ``u.lector`` / ``u.inst``)."""

    def __init__(self, lecturas: "Lecturas"):
        self.lector = lecturas.clec
        self.inst, self.dep = lecturas.inst, lecturas.dep
        self._repo = lecturas.repo

    def read(self, fn):
        # Cada lectura certificada usa su propia conexion: un error absorbido por su try/except no aborta la transaccion
        # compartida -> SAVEPOINT por lectura cuando hay conexion propia (en un writer ya es una conexion nueva).
        if isinstance(self._repo, InvestigacionRepository):
            with self._repo._conn.transaction():
                return fn(self._repo)
        return self._repo.call(fn)


# ------------------------------------------------------------------------------------------ padron v240 / v276
def snapshot_departamento_v240(repo: InvestigacionRepository, today: date, dep_id: int, dep_nombre: str) -> dict:
    """``_snapshot_listados_departamento_v240`` (l. 53026): listados del departamento con su propio ambito."""
    rd = InvestigacionRepository(repo._conn, repo.inst, int(dep_id))
    lec = Lector(rd, today)
    df_periodos = pd.DataFrame(rd.periods())
    if df_periodos.empty:
        return {"resumen": {"departamento_id": int(dep_id), "departamento": str(dep_nombre or ""),
                            "periodo_actual": "Sin períodos", "estado_periodo": "Sin períodos", "docentes": 0,
                            "designaciones": 0, "horas_designadas": 0.0},
                "docentes": pd.DataFrame(), "designaciones": pd.DataFrame()}
    p_abierto = lec.periodo_abierto()
    if p_abierto:
        periodo_id = int(p_abierto["id"])
        periodo_nombre = str(p_abierto.get("nombre") or "")
        periodo_estado = str(p_abierto.get("estado") or "Abierto")
    else:
        p0 = df_periodos.iloc[0].to_dict()
        periodo_id = int(p0["id"])
        periodo_nombre = str(p0.get("nombre") or "")
        periodo_estado = str(p0.get("estado") or "")
    df_desig = lec.designaciones_periodo_df(periodo_id)
    df_desig = df_desig.copy() if isinstance(df_desig, pd.DataFrame) else pd.DataFrame()
    if not df_desig.empty and "estado" in df_desig.columns:
        estado = df_desig["estado"].fillna("").astype(str).str.strip().str.casefold()
        df_desig_contadas = df_desig[estado.eq("activa")].copy()
    else:
        df_desig_contadas = df_desig.copy()
    df_plantel = lec.plantel_periodo(periodo_id)
    df_plantel = df_plantel.copy() if isinstance(df_plantel, pd.DataFrame) else pd.DataFrame()
    if not df_plantel.empty:
        if "designaciones_activas" in df_plantel.columns:
            activas = pd.to_numeric(df_plantel["designaciones_activas"], errors="coerce").fillna(0)
            df_doc_contados = df_plantel[activas.gt(0)].copy()
        elif "estado_operativo_periodo" in df_plantel.columns:
            est = df_plantel["estado_operativo_periodo"].fillna("").astype(str).str.strip().str.casefold()
            df_doc_contados = df_plantel[est.eq("activo en el período".casefold())].copy()
        else:
            df_doc_contados = df_plantel.copy()
    else:
        df_doc_contados = df_plantel.copy()
    horas = float(pd.to_numeric(df_desig_contadas.get("horas", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) \
        if not df_desig_contadas.empty else 0.0
    for df_det in (df_doc_contados, df_desig_contadas):
        if isinstance(df_det, pd.DataFrame) and not df_det.empty:
            df_det.insert(0, "departamento_origen", str(dep_nombre or ""))
            df_det.insert(1, "periodo_consolidado", periodo_nombre)
    return {"resumen": {"departamento_id": int(dep_id), "departamento": str(dep_nombre or ""),
                        "periodo_actual": periodo_nombre, "estado_periodo": periodo_estado,
                        "docentes": int(len(df_doc_contados)), "designaciones": int(len(df_desig_contadas)),
                        "horas_designadas": round(horas, 2)},
            "docentes": df_doc_contados.reset_index(drop=True),
            "designaciones": df_desig_contadas.reset_index(drop=True)}


def consolidado_v240(repo: InvestigacionRepository, today: date):
    """``_consolidado_desde_listados_reales_v240`` (l. 53142): suma literal de los listados departamentales."""
    departamentos = repo.departamentos_activos()
    if departamentos is None or departamentos.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), set()
    resumenes, docentes_partes, designaciones_partes, cuiles_unicos = [], [], [], set()
    for _, dep in departamentos.iterrows():
        snap = snapshot_departamento_v240(repo, today, int(dep["id"]), str(dep.get("nombre") or ""))
        resumenes.append(snap["resumen"])
        dfd = snap.get("docentes", pd.DataFrame())
        if isinstance(dfd, pd.DataFrame) and not dfd.empty:
            docentes_partes.append(dfd)
            for cuil in dfd.get("cuil", pd.Series(dtype=str)).tolist():
                clave = R.clave_cuil(cuil)
                if clave:
                    cuiles_unicos.add(clave)
        dfg = snap.get("designaciones", pd.DataFrame())
        if isinstance(dfg, pd.DataFrame) and not dfg.empty:
            designaciones_partes.append(dfg)
    df_resumen = pd.DataFrame(resumenes)
    df_docentes = pd.concat(docentes_partes, ignore_index=True, sort=False) if docentes_partes else pd.DataFrame()
    df_designaciones = pd.concat(designaciones_partes, ignore_index=True, sort=False) if designaciones_partes else pd.DataFrame()
    return df_resumen, df_docentes, df_designaciones, cuiles_unicos


def padron_v276(repo: InvestigacionRepository, today: date) -> pd.DataFrame:
    """``_docentes_asignables_proyectos_institucional_pg_v276`` (l. 47458): padron EXACTO del Consolidado institucional.

    El ``periodo_id`` del certificado solo se valida (``int``): el padron es la foto actual de cada departamento."""
    lim = R.limpiar_texto_tabla
    try:
        _, df_doc, df_des_raw, cuiles_unicos = consolidado_v240(repo, today)
    except Exception:
        return pd.DataFrame(columns=COLS_PADRON)
    df_doc = df_doc.copy() if isinstance(df_doc, pd.DataFrame) else pd.DataFrame()
    df_des_raw = df_des_raw.copy() if isinstance(df_des_raw, pd.DataFrame) else pd.DataFrame()
    cuiles_unicos = {str(x) for x in (cuiles_unicos or set()) if str(x).strip()}
    if not cuiles_unicos:
        out = pd.DataFrame(columns=COLS_PADRON)
        out.attrs["consolidado_docentes_unicos_v276"] = 0
        out.attrs["selector_docentes_unicos_v276"] = 0
        out.attrs["diagnostico_v276"] = []
        return out
    diagnosticos = []
    df_des_limpias = pd.DataFrame()
    if not df_des_raw.empty:
        partes_limpias = []
        if "departamento_origen" in df_des_raw.columns:
            grupos_dep = list(df_des_raw.groupby(df_des_raw["departamento_origen"].fillna("").astype(str), dropna=False))
        else:
            grupos_dep = [("", df_des_raw)]
        for dep_nom, sub in grupos_dep:
            sub = sub.copy()
            antes = len(sub)
            limpia = CP._sanear_designaciones_institucionales_v265(sub)
            removidas = max(antes - len(limpia), 0)
            if removidas:
                diagnosticos.append(
                    f"{lim(dep_nom) or 'Departamento sin identificar'}: "
                    f"{removidas} designación/es activa/s legacy o estructuralmente inválida/s "
                    "fueron omitidas SOLO para Cargo/Dedicación/Horas. Sus docentes siguen disponibles "
                    "porque el padrón lo determina el Consolidado institucional."
                )
            if isinstance(limpia, pd.DataFrame) and not limpia.empty:
                partes_limpias.append(limpia)
        if partes_limpias:
            df_des_limpias = pd.concat(partes_limpias, ignore_index=True, sort=False)
    grupos_doc: dict = {}
    if not df_doc.empty:
        for _, r in df_doc.iterrows():
            k = R.clave_cuil(r.get("cuil"))
            if k:
                grupos_doc.setdefault(k, []).append(r.to_dict())
    grupos_des: dict = {}
    if not df_des_limpias.empty:
        for _, r in df_des_limpias.iterrows():
            k = R.clave_cuil(r.get("cuil"))
            if k:
                grupos_des.setdefault(k, []).append(r.to_dict())

    def _texto_primero(rows, *cols):
        for r in rows:
            for col in cols:
                v = lim(r.get(col, ""))
                if v:
                    return v
        return ""

    def _score_identidad(r):
        tipo = lim(r.get("tipo_docente", "Propio")) or "Propio"
        nom = lim(r.get("nombre_completo", r.get("nombre", "")))
        leg = lim(r.get("legajo", ""))
        return (0 if tipo.casefold() != "prestado" else 1, 0 if nom else 1, 0 if leg else 1)

    filas = []
    for clave in sorted(cuiles_unicos):
        docs = list(grupos_doc.get(clave, []))
        desigs = list(grupos_des.get(clave, []))
        _ = sorted(docs, key=_score_identidad)[0] if docs else {}
        cuil_mostrar = _texto_primero(docs, "cuil") or _texto_primero(desigs, "cuil") or clave
        nombre = _texto_primero(docs, "nombre_completo", "docente", "nombre") or cuil_mostrar
        legajo = _texto_primero(docs, "legajo")
        tipos = [lim(r.get("tipo_docente", "Propio")) or "Propio" for r in docs]
        tipo_real = "Propio" if any(t.casefold() != "prestado" for t in tipos) else (tipos[0] if tipos else "Propio")
        tipo_por_dep: dict = {}
        for r in docs:
            dep = lim(r.get("departamento_origen", r.get("departamento", "")))
            if not dep:
                continue
            tipo_r = lim(r.get("tipo_docente", "Propio")) or "Propio"
            clave_dep = R.normalizar_clave(dep)
            previo = tipo_por_dep.get(clave_dep)
            if previo is None or (str(previo).casefold() == "prestado" and tipo_r.casefold() != "prestado"):
                tipo_por_dep[clave_dep] = tipo_r
        departamentos = []
        for r in desigs:
            dep = lim(r.get("departamento_origen", r.get("departamento", "")))
            if not dep:
                continue
            tipo_dep = tipo_por_dep.get(R.normalizar_clave(dep), "")
            if str(tipo_dep).casefold() == "prestado":
                continue
            if dep not in departamentos:
                departamentos.append(dep)
        if not departamentos:
            for r in docs:
                tipo_r = lim(r.get("tipo_docente", "Propio")) or "Propio"
                if tipo_r.casefold() == "prestado":
                    continue
                dep = lim(r.get("departamento_origen", r.get("departamento", "")))
                if dep and dep not in departamentos:
                    departamentos.append(dep)
        cargos, dedicaciones = [], []
        total_horas = 0.0
        for r in desigs:
            cargo_raw = lim(r.get("cargo", ""))
            cargo = R.normalizar_cargo_para_jerarquia(cargo_raw) if cargo_raw else ""
            dedic = lim(r.get("dedicacion", ""))
            if cargo and cargo in CARGOS and cargo not in cargos:
                cargos.append(cargo)
            if dedic and dedic not in dedicaciones:
                dedicaciones.append(dedic)
            try:
                total_horas += float(horas_segun_dedicacion(dedic, r.get("horas", 0)) or 0)
            except Exception:
                try:
                    total_horas += float(r.get("horas", 0) or 0)
                except Exception:
                    pass
        advertencias = []
        if not desigs:
            horas_propias, horas_todas = [], []
            for r in docs:
                try:
                    hs = float(pd.to_numeric(r.get("horas_activas", r.get("horas_registradas_periodo", 0)), errors="coerce") or 0)
                except Exception:
                    hs = 0.0
                horas_todas.append(hs)
                tipo_r = lim(r.get("tipo_docente", "Propio")) or "Propio"
                if tipo_r.casefold() != "prestado":
                    horas_propias.append(hs)
            total_horas = sum(horas_propias) if horas_propias else (max(horas_todas) if horas_todas else 0.0)
            advertencias.append(
                "Docente habilitado por el Consolidado institucional; no se usa un cargo legacy inválido para mostrar información."
            )
        filas.append({
            "cuil": cuil_mostrar, "nombre_completo": nombre, "legajo": legajo, "tipo_docente": tipo_real,
            "departamento_origen": " / ".join(departamentos), "es_externo": 0, "horas_designadas": round(total_horas, 2),
            "cargo": " / ".join(cargos), "cargo_final": " / ".join(cargos), "dedicacion": " / ".join(dedicaciones),
            "estado_docente_base": "Activo en el período", "advertencia_disponibilidad": " | ".join(advertencias),
        })
    out = pd.DataFrame(filas, columns=COLS_PADRON)
    if not out.empty:
        out["_cuil_key_v276"] = out["cuil"].astype(str).map(R.clave_cuil)
        out = out.drop_duplicates(subset=["_cuil_key_v276"], keep="first").copy()
        out["_orden_nombre_v276"] = out["nombre_completo"].fillna("").astype(str).str.casefold()
        out = out.sort_values(["_orden_nombre_v276", "_cuil_key_v276"], kind="stable")
        out = out.drop(columns=["_orden_nombre_v276", "_cuil_key_v276"], errors="ignore").reset_index(drop=True)
    consolidado_n, selector_n = int(len(cuiles_unicos)), int(len(out))
    if selector_n != consolidado_n:
        diagnosticos.insert(0, f"Control interno: Consolidado institucional={consolidado_n} docentes únicos por CUIL, "
                               f"selector={selector_n}. Esta diferencia no debería ocurrir y debe revisarse.")
    out.attrs["consolidado_docentes_unicos_v276"] = consolidado_n
    out.attrs["selector_docentes_unicos_v276"] = selector_n
    out.attrs["diagnostico_v276"] = diagnosticos
    return out


# ------------------------------------------------------------------------------------------ foto al cierre v183
def filtrar_cierre_v183(df: pd.DataFrame, historico: bool, ref: Optional[date]) -> pd.DataFrame:
    """``_filtrar_asignaciones_proyecto_cierre_v183`` (l. 39944) con la condicion historica ya resuelta."""
    base = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
    if base.empty or not historico or ref is None:
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


def enriquecer_v277(df: pd.DataFrame, padron: Optional[pd.DataFrame]) -> pd.DataFrame:
    """``_enriquecer_asignaciones_proyecto_origen_v277`` (l. 47677): nombre y departamento/s de origen del padron."""
    if df is None:
        return pd.DataFrame()
    out = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame(df)
    if out.empty:
        return out
    if "departamento_origen_docente" not in out.columns:
        out["departamento_origen_docente"] = ""
    lim = R.limpiar_texto_tabla
    if isinstance(padron, pd.DataFrame) and not padron.empty and "cuil" in padron.columns:
        mapa = {}
        for _, r in padron.iterrows():
            k = R.clave_cuil(r.get("cuil"))
            if not k:
                continue
            mapa[k] = {"nombre": lim(r.get("nombre_completo", "")), "departamentos": lim(r.get("departamento_origen", "")),
                       "tipo": lim(r.get("tipo_docente", ""))}
        for idx, r in out.iterrows():
            info = mapa.get(R.clave_cuil(r.get("cuil")), {})
            nombre = lim(info.get("nombre", ""))
            deps = lim(info.get("departamentos", ""))
            if nombre:
                out.at[idx, "docente"] = nombre
            if deps:
                out.at[idx, "departamento_origen_docente"] = deps
            if info.get("tipo"):
                out.at[idx, "tipo_docente_origen"] = info.get("tipo")
    if "departamento_asignacion" in out.columns:
        vacio = out["departamento_origen_docente"].fillna("").astype(str).str.strip().eq("")
        out.loc[vacio, "departamento_origen_docente"] = out.loc[vacio, "departamento_asignacion"].fillna("").astype(str)
    return out


class Lecturas:
    """Lecturas de Investigacion sobre el repositorio de la sesion (``rol`` y departamento revalidados)."""

    def __init__(self, repo: Any, today: date, rol: Optional[str], clec: Optional[Lector] = None):
        self.repo = repo
        self.today = today
        self.rol = rol
        self.inst, self.dep = int(repo.inst), int(repo.dep)
        self.clec = clec if clec is not None else Lector(repo, today)
        self._memo: dict = {}

    def invalidar(self) -> None:
        self._memo.clear()
        self.clec.invalidar()

    def _cached(self, key, fn: Callable[[], Any]):
        if key not in self._memo:
            self._memo[key] = fn()
        return self._memo[key]

    # ------------------------------------------------------------------ periodos (contexto v182)
    def periodos(self) -> pd.DataFrame:
        return self._cached("periodos", lambda: pd.DataFrame(self.repo.periods()))

    def periodo_abierto(self) -> Optional[dict]:
        return self._cached("abierto", self.clec.periodo_abierto)

    def ultimo_periodo(self) -> Optional[dict]:
        return self._cached("ultimo", self.clec.ultimo_periodo)

    def periodo_info(self, periodo_id) -> Optional[dict]:
        return self._cached(("info", int(periodo_id)), lambda: self.clec.periodo_info(int(periodo_id)))

    def es_historico(self, periodo_id) -> bool:
        from designaciones.rules import es_periodo_historico
        try:
            info = self.periodo_info(periodo_id)
        except Exception:
            return False
        return es_periodo_historico(info, self.ultimo_periodo(), self.periodo_abierto())

    def fecha_cierre(self, periodo_id) -> Optional[date]:
        return R.safe_date((self.periodo_info(periodo_id) or {}).get("fecha_fin"), None)

    def fecha_referencia_v182(self, periodo_id) -> date:
        info = self.periodo_info(periodo_id) if periodo_id is not None else None
        if info and self.es_historico(info.get("id")):
            try:
                return R.safe_date(info.get("fecha_fin"), self.today)
            except Exception:
                return self.today
        return self.today

    # ------------------------------------------------------------------ proyectos
    def proyecto_por_id(self, proyecto_id) -> dict:
        """``_proyecto_investigacion_por_id`` (l. 21215)."""
        if proyecto_id is None:
            return {}
        df = self.repo.proyecto_por_id(int(proyecto_id))
        if df.empty:
            return {}
        fila = df.iloc[0].to_dict()
        fila["situacion"] = IR.situacion_proyecto(fila, hoy=self.today)
        fila["puede_administrar"] = IR.puede_administrar(fila, self.rol, self.dep)
        return fila

    def proyectos(self, solo_activos: bool = False, periodo_id=None) -> pd.DataFrame:
        """``_get_proyectos_v199`` (l. 45345)."""
        historico = bool(periodo_id is not None and self.es_historico(periodo_id))
        raw = self.repo.proyectos_bulk_v199(False if historico else bool(solo_activos))
        df = raw.copy() if isinstance(raw, pd.DataFrame) else pd.DataFrame()
        if df.empty:
            return df
        periodo = None
        if periodo_id is not None:
            try:
                dfp = self.periodos()
                fila = dfp[pd.to_numeric(dfp.get("id"), errors="coerce").eq(int(periodo_id))]
                if not fila.empty:
                    periodo = fila.iloc[0].to_dict()
            except Exception:
                periodo = None
        ref = self.fecha_referencia_v182(periodo_id) if historico else None
        df["situacion"] = df.apply(lambda r: IR.situacion_proyecto(r.to_dict(), ref, hoy=self.today), axis=1)
        df["puede_administrar"] = df.apply(lambda r: IR.puede_administrar(r.to_dict(), self.rol, self.dep), axis=1)
        if periodo is not None:
            df = df[df.apply(lambda r: IR.proyecto_vigente_en_periodo(r.to_dict(), periodo), axis=1)].copy()
        if historico:
            df["fecha_referencia_contexto"] = str(ref)
        return df.reset_index(drop=True)

    # ------------------------------------------------------------------ asignaciones
    def _asignaciones_base(self, cuil, periodo_id, incluir_bajas, todos_departamentos) -> pd.DataFrame:
        """``get_investigacion_docente`` base (l. 22041)."""
        if todos_departamentos:
            return CP._proyectos_docente_todos(_ComoUnidad(self), "investigacion", cuil, periodo_id, incluir_bajas)
        return self.repo.asignaciones_local(cuil, int(periodo_id) if periodo_id is not None else None,
                                            bool(incluir_bajas))

    def asignaciones(self, cuil=None, periodo_id=None, incluir_bajas=False, todos_departamentos=False,
                     enriquecer: bool = True) -> pd.DataFrame:
        """``get_investigacion_docente`` efectiva: v277 -> v183 -> base."""
        if periodo_id is not None and self.es_historico(periodo_id) and not incluir_bajas:
            raw = self._asignaciones_base(cuil, periodo_id, True, todos_departamentos)
            df = filtrar_cierre_v183(raw, True, self.fecha_cierre(periodo_id))
        else:
            df = self._asignaciones_base(cuil, periodo_id, incluir_bajas, todos_departamentos)
        if periodo_id is not None and enriquecer:
            try:
                return enriquecer_v277(df, self.padron())
            except Exception:
                pass
        return df

    def buscar_activa(self, periodo_id, proyecto_id, cuil, excluir_id=None) -> dict:
        """``_buscar_asignacion_activa_proyecto_pg_v217`` (l. 48204, rama ``todos_departamentos``)."""
        cuil_clave = R.clave_cuil(cuil)
        if not cuil_clave:
            return {}
        df = self.repo.buscar_activa_v217(int(periodo_id), int(proyecto_id), cuil_clave,
                                          int(excluir_id) if excluir_id is not None else None)
        return {} if df.empty else df.iloc[0].to_dict()

    def integrantes(self, proyecto_id, periodo_id) -> pd.DataFrame:
        """``_integrantes_proyecto_pg_v217`` (l. 48268) + v277."""
        df = self.repo.integrantes_v217(int(proyecto_id), int(periodo_id))
        return enriquecer_v277(df, self.padron())

    # ------------------------------------------------------------------ padron institucional (D4)
    def padron(self) -> pd.DataFrame:
        def build():
            return self.repo.call(lambda repo: padron_v276(repo, self.today))
        df = self._cached("padron", build)
        out = df.copy()
        out.attrs = dict(df.attrs)
        return out

    # ------------------------------------------------------------------ actos
    def documentos_proyectos(self, proyecto_ids) -> pd.DataFrame:
        """``get_documentos_proyectos_v263`` (l. 51221)."""
        ids = []
        for x in list(proyecto_ids or []):
            try:
                i = int(x)
            except Exception:
                continue
            if i > 0 and i not in ids:
                ids.append(i)
        if not ids:
            return pd.DataFrame(columns=COLS_DOCS)
        try:
            df = self.repo.documentos_proyectos_v263(IR.TIPO, ids)
        except Exception:
            df = pd.DataFrame(columns=COLS_DOCS)
        for c in COLS_DOCS:
            if c not in df.columns:
                df[c] = ""
        return df[COLS_DOCS]

    def actos_por_proyecto(self, proyecto_ids) -> tuple[pd.DataFrame, dict]:
        """Etiquetas v263 por proyecto (``" | ".join`` sin repetir)."""
        docs = self.documentos_proyectos(proyecto_ids)
        mapa = {}
        if isinstance(docs, pd.DataFrame) and not docs.empty:
            for pid, grp in docs.groupby(pd.to_numeric(docs["proyecto_id"], errors="coerce"), dropna=True):
                ets = []
                for _, rd in grp.iterrows():
                    et = IR.etiqueta_acto_v263(rd.get("tipo_documento"), rd.get("numero"), rd.get("dependencia_emisora"))
                    if et not in ets:
                        ets.append(et)
                mapa[int(pid)] = " | ".join(ets)
        return docs, mapa

    # ------------------------------------------------------------------ capacidad (D5)
    def capacidad(self, cuil, periodo_id, excluir_tipo=None, excluir_id=None) -> dict:
        """``capacidad_proyectos_docente_v184`` (l. 40242) con ``excluir_tipo`` / ``excluir_id``."""
        return capacidad_con_exclusion(_ComoUnidad(self), cuil, periodo_id, excluir_tipo, excluir_id)

    def detalle_proyectos_docente_v187(self, cuil, periodo_id) -> pd.DataFrame:
        df_inv, df_ext = CP.asignaciones_proyectos_docente_v184(_ComoUnidad(self), cuil, int(periodo_id))
        filas = []
        for tipo, df in [("Investigación", df_inv), ("Extensión", df_ext)]:
            if not isinstance(df, pd.DataFrame) or df.empty:
                continue
            for _, r in df.iterrows():
                horas = float(pd.to_numeric(pd.Series([r.get("horas_asignadas")]), errors="coerce").fillna(0).iloc[0])
                filas.append({"Tipo": tipo, "Proyecto": str(r.get("nombre_proyecto") or "").strip(),
                              "Código": str(r.get("codigo_proyecto") or "").strip(),
                              "Departamento": str(r.get("departamento_asignacion") or "").strip(),
                              "Rol": str(r.get("rol") or "").strip(), "Hs semanales": round(horas, 2)})
        df = pd.DataFrame(filas)
        if not df.empty:
            df = df.sort_values(["Tipo", "Proyecto", "Departamento"], kind="stable").reset_index(drop=True)
        return df

    def detectar_excesos(self, periodo_id) -> pd.DataFrame:
        """``detectar_excesos_proyectos_v184`` (l. 40590): docentes con asignaciones LOCALES y exceso > 0."""
        try:
            df_local = self.asignaciones(periodo_id=int(periodo_id), incluir_bajas=False, todos_departamentos=False)
        except Exception:
            df_local = pd.DataFrame()
        if not isinstance(df_local, pd.DataFrame) or df_local.empty:
            return pd.DataFrame()
        claves = []
        for _, r in df_local.iterrows():
            cuil = str(r.get("cuil") or "").strip()
            if cuil and R.clave_cuil(cuil) not in {R.clave_cuil(x) for x in claves}:
                claves.append(cuil)
        filas = []
        for cuil in claves:
            cap = self.capacidad(cuil, int(periodo_id))
            if float(cap.get("exceso_proyectos", 0) or 0) <= 1e-9:
                continue
            sub = df_local[df_local.get("cuil", pd.Series(index=df_local.index, dtype=str)).fillna("").astype(str)
                           .map(R.clave_cuil).eq(R.clave_cuil(cuil))]
            docente = (str(sub.iloc[0].get("docente") or "").strip() if not sub.empty else cuil) or cuil
            filas.append({"Docente": docente, "CUIL": cuil, "Hs contratadas": cap["horas_contratadas"],
                          "Hs comisiones": cap["horas_comisiones"], "Hs no lectivas": cap["horas_no_lectivas"],
                          "Capacidad para proyectos": cap["capacidad_total_proyectos"],
                          "Hs investigación": cap["horas_investigacion"], "Hs extensión": cap["horas_extension"],
                          "Exceso": cap["exceso_proyectos"]})
        return pd.DataFrame(filas)


def capacidad_con_exclusion(u, cuil, periodo_id, excluir_tipo=None, excluir_id=None) -> dict:
    """Variante propia de Investigacion de ``capacidad_proyectos_docente_v184`` (l. 40242): reutiliza por importacion los
    componentes validados de ``comisiones/proyectos.py`` y excluye la asignacion que se esta editando."""
    cuil_txt = str(cuil or "").strip()
    if not cuil_txt or periodo_id is None:
        return dict(CAP_VACIA)
    contratadas = CP.horas_contratadas_docencia_institucional_v184(u, cuil_txt, int(periodo_id))
    comisiones = CP.horas_comisiones_institucional_v184(u, cuil_txt, int(periodo_id))
    no_lectivas = CP.horas_no_lectivas_institucional_v185(u, cuil_txt, int(periodo_id))
    df_inv, df_ext = CP.asignaciones_proyectos_docente_v184(u, cuil_txt, int(periodo_id))
    if excluir_id is not None:
        try:
            eid = int(excluir_id)
            if str(excluir_tipo or "").strip().casefold() in {"investigacion", "investigación"} and not df_inv.empty:
                df_inv = df_inv[pd.to_numeric(df_inv.get("id"), errors="coerce").ne(eid)].copy()
            elif str(excluir_tipo or "").strip().casefold() in {"extension", "extensión"} and not df_ext.empty:
                df_ext = df_ext[pd.to_numeric(df_ext.get("id"), errors="coerce").ne(eid)].copy()
        except Exception:
            pass
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


def validar_horas_v187(u, cuil, periodo_id, horas_solicitadas, excluir_tipo=None, excluir_id=None):
    """``_validar_horas_proyecto_v184`` efectiva (v187 l. 40670): diagnostica; solo bloquea horas negativas."""
    cap = capacidad_con_exclusion(u, cuil, periodo_id, excluir_tipo=excluir_tipo, excluir_id=excluir_id)
    solicitadas = round(float(horas_solicitadas or 0), 2)
    if solicitadas < -1e-9:
        return False, "Las horas asignadas no pueden ser negativas.", cap
    disponibles = round(float(cap.get("horas_disponibles_proyectos", 0) or 0), 2)
    if solicitadas > disponibles + 1e-9:
        excederia = round(solicitadas - disponibles, 2)
        return True, (f"Advertencia: se registrarán {solicitadas:g} hs aunque antes de la acción "
                      f"quedaban {disponibles:g} hs disponibles para Investigación/Extensión. "
                      f"La acción agrega un exceso de al menos {excederia:g} hs sobre ese remanente."), cap
    return True, "", cap


__all__ = ["Lecturas", "capacidad_con_exclusion", "validar_horas_v187", "padron_v276", "enriquecer_v277",
           "filtrar_cierre_v183", "PERIODO_REF_CTE", "condicion_periodo_equivalente_sql"]
