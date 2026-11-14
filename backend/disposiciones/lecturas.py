"""Lecturas certificadas de Disposiciones (cadenas efectivas de B13-FIX02), sin cache de proceso.

``Lecturas`` envuelve un ``DisposicionesRepository`` dentro de UNA transaccion de lectura.  Cada lectura que el
certificado protege con ``try/except`` corre en su propio SAVEPOINT (un error no aborta la transaccion compartida y
devuelve lo mismo que el certificado).  La memoizacion es solo por request (equivale a la cache v191/v199 del
certificado: misma lectura, mismo resultado dentro de una pantalla).

Cadenas (entry):
- Parametros: ``get_parametros_disposicion`` l. 5548; numero inicial v162 l. 35175 (clave ``extracted_batch01``).
- Habilitados: ``get_docentes_activos_para_disposiciones_v155`` v162 l. 35192 -> base l. 6012 (``get_docentes`` del
  departamento + ``get_designaciones(periodo)`` local; orden ``normalizar_clave(nombre)`` + CUIL, estable).
- Designaciones de la disposicion: ``get_designaciones_docente_periodo_disposicion_v159`` v162 l. 35277 -> l. 6515.
- Ambito: ``_ambito_disposicion_v159`` l. 6412 y ``_filtrar_por_departamentos_disposicion_v159`` l. 6542.
- Art. 1: ``texto_asignaturas_docente`` v95 l. 32175 (horarios reales del ambito + ``_expandir_horarios_por_materias_
  comision_v131`` l. 31093 / ``_detalle_materias_comisiones_v131`` l. 31020 + plan de estudios unico).
- Art. 2: ``texto_proyectos_investigacion_docente`` l. 6919, ``texto_proyectos_extension_docente`` l. 6966 sobre
  ``get_investigacion_docente`` / ``get_extension_docente`` institucionales (v183 + base; la v277 solo agrega columnas de
  presentacion que Disposiciones no usa).
- Art. 3: ``texto_actividades_especiales_docente`` l. 32161 (lectura institucional G5 de Actividades Especiales).
- Art. 4: ``_destinos_articulo_4_v215`` l. 7059.
- Contexto: ``obtener_contexto_docente_disposicion`` v95 l. 32390 -> base l. 7070.
- Datos por designacion: ``get_datos_designaciones_docente_disposicion`` l. 5785 (acto v266 por id).
- Parametros por docente: v162 l. 35206 -> base l. 5605 (sin el ``CREATE TABLE`` incidental: B12F).
- Funcion no docente: ``_estado_funcional_disposicion_v163`` l. 34256, ``_texto_funcion_no_docente_para_disposicion_
  v164`` l. 34414.
- Preparacion masiva: ``preparar_disposicion_automatica_v158`` v162 l. 35243 -> l. 6118.
- Estado de consulta: ``get_estado_consulta_designacion`` l. 23842 (SOLO LECTURA, D12).
- Historial: ``get_disposiciones`` (extracted_batch03).
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Callable, Optional

import pandas as pd

from comisiones import proyectos as CP
from comisiones.lecturas import Lector, _LectorComoUnidad
from designaciones.rules import etiqueta_acto
from materias.rules import clave_materia_unica_codigo_nombre, deptit_join_unicos

from . import rules as R
from .repository import DisposicionesRepository

COLUMNAS_HABILITADOS = ["nombre_completo", "cuil", "legajo", "titulo", "estado", "email", "tipo_docente",
                        "numero_disposicion_auto"]
COLUMNAS_DESIGNACIONES_V159 = ["id", "periodo_id", "departamento_id", "cargo", "dedicacion", "horas", "tipo_designacion",
                               "numero_resolucion", "ad_honorem", "fecha_desde", "fecha_hasta", "estado", "departamento"]
_COLS_V131 = ["comision_id", "codigo_materia", "asignatura", "carrera", "escuela", "plan_version",
              "contextos_plan_v131", "escuelas_v131"]
_RE_PRESTADO = re.compile(r"Docente\s+prestado\s+desde\s+(.+?)(?:\.\s*No\s+posee\s+designaci[oó]n\s+local|\.|$)",
                          flags=re.I)


class Lecturas:
    def __init__(self, repo: DisposicionesRepository, today: date, departamento_usuario: Any = ""):
        """``departamento_usuario`` = ``current_user()["departamento_nombre"]`` (departamento PROPIO del usuario)."""
        self.repo = repo
        self.today = today
        self.inst, self.dep = int(repo.inst), int(repo.dep)
        self.lector = Lector(repo, today)
        self._u = _LectorComoUnidad(self.lector)
        self._departamento_usuario = departamento_usuario
        self._memo: dict = {}

    # ------------------------------------------------------------------ infraestructura
    def _cached(self, key, fn: Callable[[], Any]):
        if key not in self._memo:
            self._memo[key] = fn()
        return self._memo[key]

    def _safe(self, fn: Callable[[], Any], default: Callable[[], Any]):
        """``try: ... except Exception: default`` del certificado sin abortar la transaccion de lectura."""
        try:
            with self.repo._conn.transaction():
                return fn()
        except Exception:
            return default()

    # ------------------------------------------------------------------ periodos
    def periodos(self) -> list[dict]:
        return self._cached("periodos", lambda: list(self.repo.periods()))

    def periodo_por_defecto(self) -> Optional[dict]:
        """``get_periodo_abierto() or get_ultimo_periodo()`` (l. 67883)."""
        return self.repo.open_period() or self.repo.last_period()

    # ------------------------------------------------------------------ parametros (l. 5548 / v162 l. 35175)
    def parametros(self) -> dict:
        def build():
            df = self.repo.parametros()
            datos = dict(R.PARAMETROS_DISPOSICION_DEFAULT)
            if not df.empty:
                for _, row in df.iterrows():
                    datos[str(row["clave"])] = "" if pd.isna(row["valor"]) else str(row["valor"])
            return datos
        return dict(self._cached("parametros", build))

    def numero_inicial(self, periodo_id) -> int:
        try:
            valor = self.parametros().get(R.clave_numero_inicial_disposicion_v162(periodo_id), "1")
            return max(1, int(float(valor)))
        except Exception:
            return 1

    # ------------------------------------------------------------------ departamento de la sesion (l. 6616)
    def _dep_actual_crudo(self) -> str:
        dep_actual = self._departamento_usuario or ""
        if not dep_actual:
            def leer():
                df = self.repo.departamento_nombre(self.dep)
                return str(df.iloc[0].get("nombre") or "") if not df.empty else ""
            dep_actual = self._cached("dep_nombre", lambda: self._safe(leer, lambda: ""))
        return dep_actual

    def dep_actual_nombre(self) -> str:
        dep_actual = " ".join(str(self._dep_actual_crudo() or "").strip().split())
        return dep_actual or "Departamento correspondiente"

    # ------------------------------------------------------------------ designaciones (get_designaciones efectiva)
    def designaciones(self, periodo_id) -> pd.DataFrame:
        def build():
            df = self.repo.designaciones_df(int(periodo_id))
            out = df.copy()
            if out.empty:
                if "funcion_no_docente" not in out.columns:
                    out["funcion_no_docente"] = pd.Series(dtype=int)
                if "texto_funcion_no_docente" not in out.columns:
                    out["texto_funcion_no_docente"] = pd.Series(dtype=str)
                return out
            out["funcion_no_docente"] = pd.to_numeric(out.get("funcion_no_docente", 0), errors="coerce").fillna(0).astype(int)
            out["texto_funcion_no_docente"] = out["texto_funcion_no_docente"].fillna("").astype(str)
            return out
        return self._cached(("designaciones", int(periodo_id)), lambda: self._safe(build, pd.DataFrame)).copy()

    # ------------------------------------------------------------------ habilitados + numeracion (D6)
    def habilitados(self, periodo_id) -> pd.DataFrame:
        """Base v155 (l. 6012) + numeracion v162: ``numero_inicial + posicion`` alfabetica.  Sin reserva."""
        def build():
            out = self._habilitados_base(periodo_id)
            if out is None or out.empty:
                return out
            inicio = self.numero_inicial(periodo_id)
            out = out.copy().reset_index(drop=True)
            out["numero_disposicion_auto"] = range(inicio, inicio + len(out))
            return out
        return self._cached(("habilitados", int(periodo_id)), build).copy()

    def _habilitados_base(self, periodo_id) -> pd.DataFrame:
        df_doc = self.repo.docentes_df()
        if df_doc is None or df_doc.empty:
            return pd.DataFrame(columns=COLUMNAS_HABILITADOS)
        try:
            df_desig_periodo = self.designaciones(int(periodo_id))
        except Exception:
            df_desig_periodo = pd.DataFrame()
        if df_desig_periodo is None or df_desig_periodo.empty or "cuil" not in df_desig_periodo.columns:
            return pd.DataFrame(columns=COLUMNAS_HABILITADOS)
        if "estado" in df_desig_periodo.columns:
            df_desig_periodo = df_desig_periodo[
                df_desig_periodo["estado"].fillna("").astype(str).str.strip().str.lower().eq("activa")].copy()
        if df_desig_periodo.empty:
            return pd.DataFrame(columns=COLUMNAS_HABILITADOS)
        habilitados = {R.clave_cuil(x) for x in df_desig_periodo["cuil"].dropna().astype(str).tolist()
                       if R.clave_cuil(x)}
        if not habilitados:
            return pd.DataFrame(columns=COLUMNAS_HABILITADOS)
        base = df_doc.copy()
        if "estado" in base.columns:
            base = base[base["estado"].fillna("").astype(str).str.strip().str.lower().eq("activo")].copy()
        filas, vistos = [], set()
        for _, row in base.iterrows():
            cuil = str(row.get("cuil") or "").strip()
            clave = R.clave_cuil(cuil)
            if not clave or clave in vistos or clave not in habilitados:
                continue
            registro = row.to_dict()
            registro["_clave_cuil_v155"] = clave
            registro["_orden_nombre_v155"] = R.normalizar_clave(registro.get("nombre_completo")
                                                                or registro.get("nombre") or cuil)
            filas.append(registro)
            vistos.add(clave)
        if not filas:
            return pd.DataFrame(columns=COLUMNAS_HABILITADOS)
        out = pd.DataFrame(filas).sort_values(["_orden_nombre_v155", "_clave_cuil_v155"], kind="stable") \
            .reset_index(drop=True)
        out["numero_disposicion_auto"] = range(1, len(out) + 1)
        return out

    # ------------------------------------------------------------------ designaciones de la disposicion (v159 / v162)
    def designaciones_docente(self, cuil, periodo_id) -> pd.DataFrame:
        def build():
            out = self._designaciones_docente_base(cuil, periodo_id)
            if out is None:
                out = pd.DataFrame()
            if out.empty:
                if "funcion_no_docente" not in out.columns:
                    out["funcion_no_docente"] = pd.Series(dtype=int)
                return out
            try:
                base = self.designaciones(periodo_id)[["id", "funcion_no_docente", "texto_funcion_no_docente"]].copy()
                out = out.drop(columns=["funcion_no_docente", "texto_funcion_no_docente"], errors="ignore") \
                    .merge(base, on="id", how="left")
            except Exception:
                out["funcion_no_docente"] = 0
                out["texto_funcion_no_docente"] = ""
            out["funcion_no_docente"] = pd.to_numeric(out.get("funcion_no_docente", 0), errors="coerce").fillna(0).astype(int)
            if "texto_funcion_no_docente" not in out.columns:
                out["texto_funcion_no_docente"] = ""
            out["texto_funcion_no_docente"] = out["texto_funcion_no_docente"].fillna("").astype(str)
            return out
        return self._cached(("desig_docente", str(cuil), int(periodo_id)), build).copy()

    def _designaciones_docente_base(self, cuil, periodo_id) -> pd.DataFrame:
        try:
            df = self.designaciones(int(periodo_id))
        except Exception:
            df = pd.DataFrame()
        if df is None or df.empty or "cuil" not in df.columns:
            return pd.DataFrame(columns=COLUMNAS_DESIGNACIONES_V159)
        clave = R.clave_cuil(cuil)
        df = df[df["cuil"].fillna("").astype(str).map(R.clave_cuil).eq(clave)].copy()
        if df.empty:
            return pd.DataFrame(columns=COLUMNAS_DESIGNACIONES_V159)
        df["departamento_id"] = self.dep
        df["departamento"] = self.dep_actual_nombre()
        for col in COLUMNAS_DESIGNACIONES_V159:
            if col not in df.columns:
                df[col] = ""
        return df[COLUMNAS_DESIGNACIONES_V159]

    # ------------------------------------------------------------------ ambito compartido / prestado (l. 6412)
    def ambito(self, cuil, periodo_id) -> dict:
        return dict(self._cached(("ambito", str(cuil), int(periodo_id)), lambda: self._ambito(cuil, periodo_id)))

    def _ambito(self, cuil, periodo_id) -> dict:
        dep_actual_id = self.dep
        dep_actual_nombre = self.dep_actual_nombre()

        def leer():
            receptores_ids, receptores_nombres = [], []
            clave = R.clave_cuil(cuil)
            df_designados = self.repo.ambito_designados(int(periodo_id), clave)
            deps_con_designacion = {int(x) for x in pd.to_numeric(
                df_designados.get("departamento_id", pd.Series(dtype=float)), errors="coerce").dropna().tolist()}
            df_prestados = self.repo.ambito_prestados(clave)
            clave_origen_actual = R.clave_departamento_dispo_v159(dep_actual_nombre)
            for _, row in df_prestados.iterrows():
                try:
                    dep_id = int(row.get("departamento_id"))
                except Exception:
                    continue
                if dep_id == int(dep_actual_id):
                    continue
                if dep_id in deps_con_designacion:  # tiene designacion propia: compartido, no receptor
                    continue
                obs = R.limpiar_texto_tabla(row.get("observaciones", ""))
                m = _RE_PRESTADO.search(obs)
                origen = R.limpiar_texto_tabla(m.group(1)) if m else ""
                if not origen:
                    continue
                if R.clave_departamento_dispo_v159(origen) != clave_origen_actual:
                    continue
                if dep_id not in receptores_ids:
                    receptores_ids.append(dep_id)
                    receptores_nombres.append(R.limpiar_texto_tabla(row.get("departamento", "")) or str(dep_id))
            return receptores_ids, receptores_nombres

        receptores_ids, receptores_nombres = self._safe(leer, lambda: ([], []))
        funciones = [int(dep_actual_id)]
        for dep_id in receptores_ids:
            if dep_id not in funciones:
                funciones.append(dep_id)
        return {"departamento_actual_id": dep_actual_id, "departamento_actual": dep_actual_nombre,
                "departamentos_receptores_prestamo_ids": receptores_ids,
                "departamentos_receptores_prestamo": receptores_nombres,
                "departamentos_funciones_ids": funciones, "es_departamento_prestador": bool(receptores_ids)}

    def filtrar_por_departamentos(self, df, columna_id, cuil, periodo_id) -> pd.DataFrame:
        if df is None:
            return pd.DataFrame()
        salida = df.copy()
        if salida.empty:
            return salida
        permitidos = set(self.ambito(cuil, periodo_id).get("departamentos_funciones_ids") or [])
        if not permitidos or columna_id not in salida.columns:
            return salida.iloc[0:0].copy()
        ids = pd.to_numeric(salida[columna_id], errors="coerce")
        return salida[ids.isin(permitidos)].copy()

    # ------------------------------------------------------------------ fuentes del ambito (l. 6558-6599)
    def horarios_disposicion(self, cuil, periodo_id) -> pd.DataFrame:
        df = self.lector.horarios_docente_periodo(cuil, periodo_id)
        return self.filtrar_por_departamentos(df, "departamento_id", cuil, periodo_id)

    def _proyectos(self, tipo, cuil, periodo_id) -> pd.DataFrame:
        def build():
            df = CP.proyectos_docente_v183(self._u, tipo, cuil, periodo_id)
            return self.filtrar_por_departamentos(df, "departamento_asignacion_id", cuil, periodo_id)
        return self._cached((tipo, str(cuil), int(periodo_id)), build).copy()

    def investigacion_disposicion(self, cuil, periodo_id) -> pd.DataFrame:
        return self._proyectos("investigacion", cuil, periodo_id)

    def extension_disposicion(self, cuil, periodo_id) -> pd.DataFrame:
        return self._proyectos("extension", cuil, periodo_id)

    def actividades_disposicion(self, cuil, periodo_id) -> pd.DataFrame:
        df = self._safe(lambda: self.repo.participaciones_institucion(cuil, periodo_id, False), pd.DataFrame)
        return self.filtrar_por_departamentos(df, "departamento_asignacion_id", cuil, periodo_id)

    # ------------------------------------------------------------------ Art. 1 (v95 l. 32175)
    def _plan_todas(self) -> pd.DataFrame:
        return self._cached("plan_todas", lambda: self._safe(lambda: self.repo.materias().plan_todas(),
                                                             pd.DataFrame)).copy()

    def _materias_detalle(self) -> pd.DataFrame:
        return self._cached("materias_detalle", lambda: self._safe(self.lector.materias_detalle, pd.DataFrame)).copy()

    def _detalle_materias_comisiones_v131(self, comision_ids) -> pd.DataFrame:
        ids = []
        for valor in list(comision_ids or []):
            try:
                cid = int(valor)
            except Exception:
                continue
            if cid not in ids:
                ids.append(cid)
        if not ids:
            return pd.DataFrame(columns=_COLS_V131)
        vinculos = self._safe(lambda: self.repo.vinculos_v118_global(ids), pd.DataFrame)
        if vinculos is None or vinculos.empty:
            return pd.DataFrame(columns=_COLS_V131)
        detalle_actual = self._materias_detalle()
        actuales = {}
        if isinstance(detalle_actual, pd.DataFrame) and not detalle_actual.empty:
            col_id = "materia_id" if "materia_id" in detalle_actual.columns else "id" \
                if "id" in detalle_actual.columns else None
            if col_id:
                for _, fila in detalle_actual.iterrows():
                    try:
                        actuales[int(fila.get(col_id))] = fila.to_dict()
                    except Exception:
                        pass
        lim = R.limpiar_texto_tabla
        filas = []
        for _, link in vinculos.iterrows():
            try:
                cid = int(link.get("comision_id"))
                mid = int(link.get("materia_id"))
            except Exception:
                continue
            act = actuales.get(mid, {}) or {}
            codigo = lim(act.get("codigo", "")) or lim(link.get("codigo_snapshot", ""))
            asignatura = lim(act.get("asignatura", "")) or lim(link.get("asignatura_snapshot", ""))
            if not codigo and not asignatura:
                continue
            carrera = lim(link.get("carrera_snapshot", "")) or lim(act.get("carrera", ""))
            escuela = lim(link.get("escuela_snapshot", "")) or lim(act.get("escuela", ""))
            plan = lim(link.get("plan_version_snapshot", "")) or lim(act.get("plan_version", ""))
            filas.append({"comision_id": cid, "codigo_materia": codigo, "asignatura": asignatura, "carrera": carrera,
                          "escuela": escuela, "plan_version": plan,
                          "_clave_v131": clave_materia_unica_codigo_nombre(codigo, asignatura)
                          or f"{codigo}::{R.normalizar_clave(asignatura)}"})
        base = pd.DataFrame(filas)
        if base.empty:
            return pd.DataFrame(columns=_COLS_V131)
        salida = []
        for (cid, _), grupo in base.groupby(["comision_id", "_clave_v131"], dropna=False, sort=False):
            primera = grupo.iloc[0]
            contextos, escuelas_unicas = [], []
            for _, r in grupo.iterrows():
                car = lim(r.get("carrera", ""))
                esc = R.formatear_nombre_escuela(lim(r.get("escuela", "")))
                if esc and esc not in escuelas_unicas:
                    escuelas_unicas.append(esc)
                ctx = f"{car}, {esc}" if car and esc else (car or esc)
                if ctx and ctx not in contextos:
                    contextos.append(ctx)
            salida.append({
                "comision_id": int(cid),
                "codigo_materia": deptit_join_unicos(grupo["codigo_materia"], sep=" / ")
                or lim(primera.get("codigo_materia", "")),
                "asignatura": deptit_join_unicos(grupo["asignatura"], sep=" / ") or lim(primera.get("asignatura", "")),
                "carrera": deptit_join_unicos(grupo["carrera"], sep=" / "),
                "escuela": deptit_join_unicos(grupo["escuela"], sep=" / "),
                "plan_version": deptit_join_unicos(grupo["plan_version"], sep=" / "),
                "contextos_plan_v131": "; ".join(contextos),
                "escuelas_v131": " / ".join(escuelas_unicas),
            })
        return pd.DataFrame(salida, columns=_COLS_V131)

    def _expandir_horarios_v131(self, df):
        if df is None or not isinstance(df, pd.DataFrame) or df.empty or "comision_id" not in df.columns:
            return df
        ids = pd.to_numeric(df["comision_id"], errors="coerce").dropna().astype(int).unique().tolist()
        detalle = self._detalle_materias_comisiones_v131(ids)
        if detalle.empty:
            return df
        mapa = {int(cid): g.copy() for cid, g in detalle.groupby("comision_id", sort=False)}
        filas = []
        for _, fila in df.iterrows():
            try:
                cid = int(fila.get("comision_id"))
            except Exception:
                cid = None
            materias = mapa.get(cid) if cid is not None else None
            if materias is None or materias.empty:
                filas.append(fila.to_dict())
                continue
            for _, mat in materias.iterrows():
                item = fila.to_dict()
                for col in ["codigo_materia", "asignatura", "carrera", "escuela", "plan_version", "contextos_plan_v131",
                            "escuelas_v131"]:
                    valor = mat.get(col, "")
                    if valor is not None and str(valor).strip():
                        item[col] = valor
                filas.append(item)
        return pd.DataFrame(filas)

    def texto_asignaturas(self, cuil, periodo_id) -> tuple[str, str]:
        return self._cached(("asignaturas", str(cuil), int(periodo_id)),
                            lambda: self._texto_asignaturas(cuil, periodo_id))

    def _texto_asignaturas(self, cuil, periodo_id) -> tuple[str, str]:
        """Una comision multicodigo es UNA comision: nombres con su codigo unidos por " / ", horario una sola vez."""
        df = self.horarios_disposicion(cuil, periodo_id)
        df = self._expandir_horarios_v131(df)
        df = pd.DataFrame() if df is None else df.copy()
        if "departamento" not in df.columns:
            df["departamento"] = df.get("departamento_comision", "")
        if df.empty:
            return "", ""

        def limpiar(valor):
            if valor is None or pd.isna(valor):
                return ""
            return str(valor).strip()

        def fmt_hora(valor):
            txt = limpiar(valor)
            if not txt:
                return ""
            partes = txt.split(":")
            if len(partes) >= 2 and partes[0].isdigit() and partes[1].isdigit():
                return f"{int(partes[0]):02d}:{int(partes[1]):02d}"
            return txt

        def clave_materia_unica_dispo(codigo, asignatura):
            codigo_key = R.normalizar_codigo_materia(codigo)
            asignatura_key = R.normalizar_clave(asignatura)
            if codigo_key and asignatura_key:
                return f"{codigo_key}::{asignatura_key}"
            if codigo_key:
                return f"codigo::{codigo_key}"
            return ""

        carreras_por_materia: dict = {}
        df_materias = self._plan_todas()
        if df_materias is not None and not df_materias.empty:
            df_materias = df_materias.copy()
            for col in ["codigo", "asignatura", "carrera", "escuela"]:
                if col not in df_materias.columns:
                    df_materias[col] = ""
            for _, row_m in df_materias.iterrows():
                clave = clave_materia_unica_dispo(row_m.get("codigo"), row_m.get("asignatura"))
                if not clave:
                    continue
                carrera = limpiar(row_m.get("carrera"))
                escuela = R.formatear_nombre_escuela(limpiar(row_m.get("escuela")))
                if not carrera and not escuela:
                    continue
                item = {"carrera": carrera, "escuela": escuela}
                existentes = carreras_por_materia.setdefault(clave, [])
                firma = (R.normalizar_clave(carrera), R.normalizar_clave(escuela))
                firmas = [(R.normalizar_clave(x.get("carrera")), R.normalizar_clave(x.get("escuela"))) for x in existentes]
                if firma not in firmas:
                    existentes.append(item)

        def carreras_escuelas_para_materia(codigo, asignatura, carrera_base, escuela_base):
            clave = clave_materia_unica_dispo(codigo, asignatura)
            items = carreras_por_materia.get(clave, []) if clave else []
            if items:
                return items
            carrera_base = limpiar(carrera_base)
            escuela_base = R.formatear_nombre_escuela(limpiar(escuela_base))
            if carrera_base or escuela_base:
                return [{"carrera": carrera_base, "escuela": escuela_base}]
            return []

        def texto_carreras_escuelas(items):
            partes = []
            for item in items:
                carrera = limpiar(item.get("carrera"))
                escuela = R.formatear_nombre_escuela(limpiar(item.get("escuela")))
                if carrera and escuela:
                    txt = f"{carrera}, {escuela}"
                elif carrera:
                    txt = carrera
                elif escuela:
                    txt = escuela
                else:
                    txt = ""
                if txt and txt not in partes:
                    partes.append(txt)
            return "; ".join(partes)

        escuelas, registros = [], []
        for col in ["departamento", "comision_id", "materia_id", "codigo_materia", "asignatura", "materia_especifica",
                    "nombre_comision", "turno", "contextos_plan_v131", "escuelas_v131", "carrera", "escuela", "dia",
                    "hora_inicio", "hora_fin"]:
            if col not in df.columns:
                df[col] = ""

        def clave_comision_fisica(row):
            try:
                return f"id:{int(row.get('comision_id'))}"
            except Exception:
                return "fallback:" + "||".join([
                    limpiar(row.get("departamento")), limpiar(row.get("nombre_comision")), limpiar(row.get("turno")),
                    limpiar(row.get("sede")) if "sede" in row else "",
                    limpiar(row.get("modalidad")) if "modalidad" in row else "",
                ])

        df["_grupo_comision_dispo_v134"] = df.apply(clave_comision_fisica, axis=1)
        for _, grupo in df.groupby("_grupo_comision_dispo_v134", dropna=False, sort=False):
            primera = grupo.iloc[0]
            departamento = limpiar(primera.get("departamento", ""))
            nombre_comision = limpiar(primera.get("nombre_comision", ""))
            turno = limpiar(primera.get("turno", ""))
            materias, claves_vistas = [], set()
            for _, row in grupo.iterrows():
                codigo = limpiar(row.get("codigo_materia", ""))
                asignatura = limpiar(row.get("asignatura", ""))
                especifica = limpiar(row.get("materia_especifica", ""))
                clave = clave_materia_unica_dispo(codigo, asignatura) or f"{codigo}::{R.normalizar_clave(asignatura)}"
                if clave in claves_vistas:
                    continue
                claves_vistas.add(clave)
                nombre_mostrar = asignatura
                if especifica and R.normalizar_clave(especifica) != R.normalizar_clave(asignatura):
                    nombre_mostrar = f"{asignatura} ({especifica})"
                codigo_mostrar = limpiar(codigo)
                if codigo_mostrar:  # v172: cada materia con su codigo
                    nombre_mostrar = f"{nombre_mostrar} ({codigo_mostrar})"
                contextos_explicitos = limpiar(row.get("contextos_plan_v131", ""))
                escuelas_explicitas = limpiar(row.get("escuelas_v131", ""))
                if contextos_explicitos:
                    contexto_txt = contextos_explicitos
                    for esc in [x.strip() for x in escuelas_explicitas.split(" / ") if x.strip()]:
                        esc_fmt = R.formatear_nombre_escuela(esc)
                        if esc_fmt and esc_fmt not in escuelas:
                            escuelas.append(esc_fmt)
                else:
                    items_carreras = carreras_escuelas_para_materia(codigo, asignatura, limpiar(row.get("carrera", "")),
                                                                    limpiar(row.get("escuela", "")))
                    contexto_txt = texto_carreras_escuelas(items_carreras)
                    for item in items_carreras:
                        esc = R.formatear_nombre_escuela(limpiar(item.get("escuela")))
                        if esc and esc not in escuelas:
                            escuelas.append(esc)
                materias.append({"nombre": nombre_mostrar, "contexto": contexto_txt})
            nombres_materias = " / ".join([m["nombre"] for m in materias if m.get("nombre")])
            contextos_materias = " / ".join([m["contexto"] for m in materias if m.get("contexto")])
            horarios = []
            for _, row in grupo.iterrows():
                dia = limpiar(row.get("dia", ""))
                hi = fmt_hora(row.get("hora_inicio", ""))
                hf = fmt_hora(row.get("hora_fin", ""))
                if dia and hi and hf:
                    item = f"{dia} de {hi} a {hf}"
                elif dia and hi:
                    item = f"{dia} desde {hi}"
                elif dia:
                    item = dia
                elif hi and hf:
                    item = f"{hi} a {hf}"
                else:
                    item = ""
                if item and item not in horarios:
                    horarios.append(item)
            horarios_txt = " y ".join(horarios) if horarios else "horario no cargado"
            extras = []
            if nombre_comision:
                extras.append(f"Comisión {nombre_comision}")
            if turno:
                extras.append(f"turno {turno}")
            if departamento:
                extras.append(departamento)
            extras_txt = " - " + ", ".join(extras) if extras else ""
            if contextos_materias:
                registros.append(f"{nombres_materias}{extras_txt}, {horarios_txt} ({contextos_materias})")
            else:
                registros.append(f"{nombres_materias}{extras_txt}, {horarios_txt}")
        return "; ".join(registros), ", ".join(escuelas)

    # ------------------------------------------------------------------ Art. 2 (l. 6919 / 6966)
    def texto_proyectos_investigacion(self, cuil, periodo_id):
        df_inv = self.investigacion_disposicion(cuil, periodo_id)
        if df_inv is None or df_inv.empty:
            return "", df_inv
        registros = []
        for _, row in df_inv.iterrows():
            rol = "" if pd.isna(row.get("rol", "")) else str(row.get("rol", "")).strip()
            nombre = "" if pd.isna(row.get("nombre_proyecto", "")) else str(row.get("nombre_proyecto", "")).strip()
            codigo = "" if pd.isna(row.get("codigo_proyecto", "")) else str(row.get("codigo_proyecto", "")).strip()
            instituto = R.prefijo_instituto_proyecto(row.get("instituto_proyecto", ""))
            if not any([rol, nombre, codigo, instituto]):
                continue
            partes = [f"como {rol}" if rol else "en carácter de integrante"]
            partes.append(f"en el Proyecto “{nombre}”" if nombre else "en proyecto de investigación")
            if codigo:
                partes.append(codigo)
            if instituto:
                partes.append(instituto)
            registros.append(" ".join(partes))
        return R.unir_items_administrativos(registros), df_inv

    def texto_proyectos_extension(self, cuil, periodo_id):
        df_ext = self.extension_disposicion(cuil, periodo_id)
        if df_ext is None or df_ext.empty:
            return "", df_ext
        registros = []
        for _, row in df_ext.iterrows():
            rol = "" if pd.isna(row.get("rol", "")) else str(row.get("rol", "")).strip()
            nombre = "" if pd.isna(row.get("nombre_proyecto", "")) else str(row.get("nombre_proyecto", "")).strip()
            codigo = "" if pd.isna(row.get("codigo_proyecto", "")) else str(row.get("codigo_proyecto", "")).strip()
            area = R.prefijo_area_extension(row.get("instituto_proyecto", ""))
            if not any([rol, nombre, codigo, area]):
                continue
            partes = [f"como {rol}" if rol else "en carácter de integrante"]
            partes.append(f"en el Proyecto de Extensión “{nombre}”" if nombre else "en proyecto de extensión")
            if codigo:
                partes.append(codigo)
            if area:
                partes.append(area)
            registros.append(" ".join(partes))
        return R.unir_items_administrativos(registros), df_ext

    # ------------------------------------------------------------------ Art. 4 (l. 7024 / 7059)
    def unidades_proyectos_notificacion(self, df_inv, df_ext) -> list[str]:
        clave_departamento_actual = R.clave_unidad_proyecto_notificacion_v215(self.dep_actual_nombre())
        unidades, claves_vistas = [], set()
        for df in (df_inv, df_ext):
            if df is None or df.empty or "instituto_proyecto" not in df.columns:
                continue
            for valor in df["instituto_proyecto"].dropna().tolist():
                txt_completo = R.normalizar_texto_disposicion(valor)
                if not txt_completo:
                    continue
                partes = [x.strip() for x in re.split(r"\s*(?:/|;)\s*", txt_completo) if x.strip()]
                for unidad in partes or [txt_completo]:
                    clave = R.clave_unidad_proyecto_notificacion_v215(unidad)
                    if not clave:
                        continue
                    if clave_departamento_actual and clave == clave_departamento_actual:
                        continue
                    if clave in claves_vistas:
                        continue
                    claves_vistas.add(clave)
                    unidades.append(unidad)
        return unidades

    def destinos_articulo_4(self, escuelas_txt, df_inv, df_ext):
        escuelas = R.normalizar_texto_disposicion(escuelas_txt)
        unidades = self.unidades_proyectos_notificacion(df_inv, df_ext)
        if escuelas and unidades:
            return f"{escuelas}, {', '.join(unidades)}", unidades
        if escuelas:
            return escuelas, unidades
        return ", ".join(unidades), unidades

    # ------------------------------------------------------------------ Art. 3 (l. 32161)
    def texto_actividades_especiales(self, cuil, periodo_id):
        df = self.actividades_disposicion(cuil, periodo_id)
        if df is None or df.empty:
            return "", df
        items = []
        for _, r in df.iterrows():
            titulo = " ".join(str(r.get("titulo") or "").split())
            rol = " ".join(str(r.get("rol") or "").split())
            if titulo:
                items.append(f'“{titulo}”, en carácter de {rol or "participante"}')
        if not items:
            return "", df
        if len(items) == 1:
            return f"ARTÍCULO 3°.- Participó activamente de la siguiente actividad: {items[0]}.", df
        enumeracion = "; ".join(items[:-1]) + "; y " + items[-1]
        return f"ARTÍCULO 3°.- Participó activamente de las siguientes actividades: {enumeracion}.", df

    # ------------------------------------------------------------------ parametros por docente (v162 -> base)
    def parametros_docente(self, cuil) -> dict:
        def base():
            df = self.repo.parametros_docente(str(cuil))
            datos = {col: "" for col in R.COLUMNAS_PARAMETROS_DOCENTE}
            datos["cuil"] = str(cuil)
            if not df.empty:
                for col in R.COLUMNAS_PARAMETROS_DOCENTE:
                    if col in df.columns:
                        datos[col] = "" if pd.isna(df.iloc[0][col]) else str(df.iloc[0][col])
            return datos
        datos = dict(base() or {})
        datos.setdefault("texto_funcion_disposicion", "")

        def texto():
            df = self.repo.texto_funcion_docente(str(cuil))
            return None if df.empty else str(df.iloc[0].get("texto_funcion_disposicion") or "")
        valor = self._safe(texto, lambda: None)
        if valor is not None:
            datos["texto_funcion_disposicion"] = valor
        return datos

    # ------------------------------------------------------------------ datos por designacion (l. 5785)
    def mapa_actos(self, ids) -> dict:
        """``_mapa_actos_designaciones_v266``: acto del repositorio vinculado a cada designacion (por id)."""
        ids = sorted({int(x) for x in ids if pd.notna(x)})
        if not ids:
            return {}
        return {int(r["designacion_id"]): dict(r) for r in self.repo.actos_designaciones(ids)}

    def datos_designaciones(self, cuil, periodo_id) -> list[dict]:
        df_desig = self.designaciones_docente(cuil, periodo_id)
        if df_desig is None or df_desig.empty:
            return []
        df_use = df_desig.copy()
        if "estado" in df_use.columns:
            df_use = df_use[df_use["estado"].fillna("").astype(str).str.lower().eq("activa")].copy()
            if df_use.empty:
                return []
        if "tipo_designacion" not in df_use.columns:
            return []
        df_use["_tipo_norm"] = df_use["tipo_designacion"].map(R.normalizar_tipo_designacion_disposicion)
        df_use = df_use[df_use["_tipo_norm"].isin(["Concursado", "Interino"])].copy()
        if df_use.empty:
            return []
        cantidad_por_tipo = df_use["_tipo_norm"].value_counts().to_dict()
        df_guardados = self.repo.datos_designaciones(str(cuil))
        legacy = self.parametros_docente(cuil)

        def _igual(a, b):
            return R.normalizar_texto_disposicion(a).lower() == R.normalizar_texto_disposicion(b).lower()

        try:
            ids_v266 = pd.to_numeric(df_use.get("id", pd.Series(dtype=float)), errors="coerce").dropna().astype(int) \
                .tolist()
            mapa_actos = self._safe(lambda: self.mapa_actos(ids_v266), dict) or {}
        except Exception:
            mapa_actos = {}

        resultados = []
        for _, row in df_use.iterrows():
            designacion_id = row.get("id")
            try:
                designacion_id = int(designacion_id) if pd.notna(designacion_id) else None
            except Exception:
                designacion_id = None
            departamento_id = row.get("departamento_id")
            try:
                departamento_id = int(departamento_id) if pd.notna(departamento_id) else None
            except Exception:
                departamento_id = None
            tipo = R.normalizar_tipo_designacion_disposicion(row.get("tipo_designacion"))
            cargo = R.normalizar_texto_disposicion(row.get("cargo"))
            dedicacion = R.normalizar_texto_disposicion(row.get("dedicacion"))
            departamento = R.normalizar_texto_disposicion(row.get("departamento")) or self.dep_actual_nombre()

            guardado = None
            if df_guardados is not None and not df_guardados.empty:
                if designacion_id is not None and "designacion_id" in df_guardados.columns:
                    exactos = df_guardados[pd.to_numeric(df_guardados["designacion_id"], errors="coerce")
                                           .eq(designacion_id)]
                    if not exactos.empty:
                        guardado = exactos.iloc[0].to_dict()
                if guardado is None:
                    candidatos = df_guardados.copy()
                    if departamento_id is not None and "departamento_id" in candidatos.columns:
                        candidatos = candidatos[pd.to_numeric(candidatos["departamento_id"], errors="coerce")
                                                .eq(departamento_id)]
                    candidatos = candidatos[
                        candidatos["tipo_designacion"].map(lambda x: _igual(x, tipo))
                        & candidatos["cargo"].map(lambda x: _igual(x, cargo))
                        & candidatos["dedicacion"].map(lambda x: _igual(x, dedicacion))
                    ]
                    if not candidatos.empty:
                        guardado = candidatos.iloc[0].to_dict()

            usar_legacy = int(cantidad_por_tipo.get(tipo, 0) or 0) == 1
            if tipo == "Concursado" and usar_legacy:
                legacy_desde = legacy.get("fecha_desde_concursado", "")
                legacy_hasta = legacy.get("fecha_hasta_concursado", "")
            elif tipo == "Interino" and usar_legacy:
                legacy_desde = legacy.get("fecha_desde_interino", "")
                legacy_hasta = legacy.get("fecha_hasta_interino", "")
            else:
                legacy_desde = legacy_hasta = ""

            acto = mapa_actos.get(designacion_id) if designacion_id is not None else None
            resolucion_designacion = R.normalizar_texto_disposicion((acto or {}).get("numero", ""))
            resolucion_legacy = R.normalizar_texto_disposicion(row.get("numero_resolucion", ""))
            fecha_desde = (R.normalizar_texto_disposicion((guardado or {}).get("fecha_desde", "")) or legacy_desde
                           or R.formatear_fecha_larga(row.get("fecha_desde")))
            fecha_hasta = (R.normalizar_texto_disposicion((guardado or {}).get("fecha_hasta", "")) or legacy_hasta
                           or R.formatear_fecha_larga(row.get("fecha_hasta")))
            resultados.append({
                "designacion_id": designacion_id,
                "departamento_id": departamento_id,
                "departamento": departamento,
                "tipo_designacion": tipo,
                "cargo": cargo,
                "dedicacion": dedicacion,
                "horas": row.get("horas", ""),
                "ad_honorem": "Sí" if R.es_ad_honorem_v162(row.get("ad_honorem")) else "No",
                "funcion_no_docente": 1 if R.es_funcion_no_docente_v162(row.get("funcion_no_docente")) else 0,
                "estado": R.normalizar_texto_disposicion(row.get("estado")),
                "resolucion": resolucion_designacion,
                "numero_resolucion_designacion": resolucion_designacion,
                "numero_resolucion_legacy": resolucion_legacy,
                "acto_administrativo": (
                    etiqueta_acto((acto or {}).get("tipo_documento"), (acto or {}).get("numero"),
                                  (acto or {}).get("dependencia_emisora")) if acto else (
                        f"Resolución {resolucion_legacy} — pendiente de vincular al repositorio"
                        if resolucion_legacy else "Pendiente de vincular")),
                "fecha_desde": fecha_desde,
                "fecha_hasta": fecha_hasta,
                "observaciones": R.normalizar_texto_disposicion((guardado or {}).get("observaciones", "")),
            })
        orden_tipo = {"Concursado": 0, "Interino": 1}
        resultados.sort(key=lambda x: (orden_tipo.get(x.get("tipo_designacion"), 9),
                                       R.normalizar_texto_disposicion(x.get("departamento")).lower(),
                                       R.normalizar_texto_disposicion(x.get("cargo")).lower()))
        return resultados

    # ------------------------------------------------------------------ departamentos de origen (l. 6636 / 6661)
    def departamentos_origen(self, cuil, periodo_id) -> list[str]:
        deps = []
        try:
            df_desig = self.designaciones_docente(cuil, periodo_id)
            if df_desig is not None and not df_desig.empty:
                df_use = df_desig[df_desig["estado"].fillna("").astype(str).str.lower().eq("activa")].copy()
                if df_use.empty:
                    df_use = df_desig.copy()
                for x in df_use.get("departamento", pd.Series(dtype=str)).dropna().astype(str).tolist():
                    dep = " ".join(str(x or "").strip().split())
                    if dep and dep not in deps:
                        deps.append(dep)
        except Exception:
            deps = []
        if not deps:
            deps = [self.dep_actual_nombre()]
        return deps

    def texto_departamento_disposicion_docente(self, cuil, periodo_id) -> str:
        return R.texto_departamento_disposicion(self.departamentos_origen(cuil, periodo_id))

    # ------------------------------------------------------------------ contexto (v95 l. 32390 -> base l. 7070)
    def contexto(self, cuil, periodo_id) -> dict:
        return dict(self._cached(("contexto", str(cuil), int(periodo_id)), lambda: self._contexto(cuil, periodo_id)))

    def _contexto(self, cuil, periodo_id) -> dict:
        ctx = dict(self._contexto_base(cuil, periodo_id) or {})
        txt, df = self.texto_actividades_especiales(cuil, periodo_id)
        ctx["Texto Actividades Especiales"] = txt
        ctx["texto_actividades_especiales"] = txt
        cuerpo = R.cuerpo_actividades_especiales(txt)
        ctx["Texto Actividades Especiales Cuerpo"] = cuerpo
        ctx["texto_actividades_especiales_cuerpo"] = cuerpo
        ctx["tiene_actividades_especiales"] = bool(txt)
        ctx["Cantidad Actividades Especiales"] = 0 if df is None or df.empty else int(len(df))
        return ctx

    def _contexto_base(self, cuil, periodo_id) -> dict:
        df_doc = self.repo.docente_nombre(cuil)
        df_desig = self.designaciones_docente(cuil, periodo_id)
        docente = df_doc.iloc[0]["docente"] if not df_doc.empty else cuil
        df_activas = df_desig[df_desig["estado"].fillna("").astype(str).eq("Activa")].copy() \
            if not df_desig.empty else df_desig
        if df_activas.empty:
            df_activas = df_desig.copy()

        def valores_por_tipo(tipo):
            if df_activas.empty:
                return "", "", "", "", ""
            dft = df_activas[df_activas["tipo_designacion"].fillna("").astype(str).str.upper() == tipo.upper()].copy()
            if dft.empty:
                return "", "", "", "", ""
            cargo = " / ".join([str(x) for x in dft["cargo"].dropna().unique() if str(x).strip()])
            dedicaciones = []
            for _, fila_ded in dft.iterrows():
                ded_txt = R.normalizar_texto_disposicion(fila_ded.get("dedicacion"))
                if not ded_txt:
                    continue
                if R.es_ad_honorem_v162(fila_ded.get("ad_honorem")):
                    ded_txt = f"{ded_txt} Ad Honorem"
                if ded_txt not in dedicaciones:
                    dedicaciones.append(ded_txt)
            dedicacion = " / ".join(dedicaciones)
            horas = " / ".join([str(int(x)) if pd.notna(x) else "" for x in dft["horas"].dropna().unique()])
            desde = " / ".join([str(x) for x in dft["fecha_desde"].dropna().unique() if str(x).strip()])
            hasta = " / ".join([str(x) for x in dft["fecha_hasta"].dropna().unique() if str(x).strip()])
            return cargo, dedicacion, horas, desde, hasta

        cargo_conc, ded_conc, horas_conc, desde_conc, hasta_conc = valores_por_tipo("Concursado")
        cargo_int, ded_int, horas_int, desde_int, hasta_int = valores_por_tipo("Interino")
        cargo_general = " / ".join([x for x in [cargo_conc, cargo_int] if x])
        dedicacion_general = " / ".join([x for x in [ded_conc, ded_int] if x])
        horas_general = " / ".join([x for x in [horas_conc, horas_int] if x])

        asignaturas_txt, escuelas_txt = self.texto_asignaturas(cuil, periodo_id)
        texto_investigacion_solo, df_inv = self.texto_proyectos_investigacion(cuil, periodo_id)
        texto_extension_solo, df_ext = self.texto_proyectos_extension(cuil, periodo_id)
        tiene_inv = bool(df_inv is not None and not df_inv.empty)
        tiene_ext = bool(df_ext is not None and not df_ext.empty)
        tipo_funciones_academicas = ("investigación y extensión" if (tiene_inv and tiene_ext) else "investigación"
                                     if tiene_inv else "extensión" if tiene_ext else "investigación")
        texto_investigacion_txt = R.unir_items_administrativos([texto_investigacion_solo, texto_extension_solo])
        destinos_articulo_4, unidades_proyectos_notificar = self.destinos_articulo_4(escuelas_txt, df_inv, df_ext)

        def unicos(df, col):
            return " / ".join([str(x).strip() for x in df[col].dropna().unique() if str(x).strip()])

        roles_inv = nombres_inv = codigos_inv = institutos_inv = ""
        if df_inv is not None and not df_inv.empty:
            roles_inv = unicos(df_inv, "rol")
            nombres_inv = unicos(df_inv, "nombre_proyecto")
            codigos_inv = unicos(df_inv, "codigo_proyecto") if "codigo_proyecto" in df_inv.columns else ""
            institutos_inv = unicos(df_inv, "instituto_proyecto") if "instituto_proyecto" in df_inv.columns else ""
        roles_ext = nombres_ext = codigos_ext = areas_ext = ""
        if df_ext is not None and not df_ext.empty:
            roles_ext = unicos(df_ext, "rol")
            nombres_ext = unicos(df_ext, "nombre_proyecto")
            codigos_ext = unicos(df_ext, "codigo_proyecto") if "codigo_proyecto" in df_ext.columns else ""
            areas_ext = unicos(df_ext, "instituto_proyecto") if "instituto_proyecto" in df_ext.columns else ""

        datos_doc_dispo = self.parametros_docente(cuil)
        datos_designaciones_dispo = self.datos_designaciones(cuil, periodo_id)

        def primer_dato_designacion(tipo):
            for item in datos_designaciones_dispo:
                if R.normalizar_tipo_designacion_disposicion(item.get("tipo_designacion")) == tipo:
                    return item
            return {}

        dato_conc = primer_dato_designacion("Concursado")
        dato_int = primer_dato_designacion("Interino")
        fecha_desde_conc = (dato_conc.get("fecha_desde", "") or datos_doc_dispo.get("fecha_desde_concursado", "")
                            or R.formatear_fecha_larga(desde_conc))
        fecha_hasta_conc = (dato_conc.get("fecha_hasta", "") or datos_doc_dispo.get("fecha_hasta_concursado", "")
                            or R.formatear_fecha_larga(hasta_conc))
        fecha_desde_int = (dato_int.get("fecha_desde", "") or datos_doc_dispo.get("fecha_desde_interino", "")
                           or R.formatear_fecha_larga(desde_int))
        fecha_hasta_int = (dato_int.get("fecha_hasta", "") or datos_doc_dispo.get("fecha_hasta_interino", "")
                           or R.formatear_fecha_larga(hasta_int))
        departamentos_origen_dispo = self.departamentos_origen(cuil, periodo_id)
        texto_departamentos_revistara = R.texto_departamentos_revistara_desde_lista(
            departamentos_origen_dispo, self._dep_actual_crudo())
        texto_departamento_disposicion = self.texto_departamento_disposicion_docente(cuil, periodo_id)
        ambito = self.ambito(cuil, periodo_id)

        def cantidad(df):
            if df is None or df.empty:
                return 0
            if "proyecto_id" in df.columns and df["proyecto_id"].notna().any():
                return int(df["proyecto_id"].dropna().nunique())
            return int(df[["nombre_proyecto", "codigo_proyecto"]].drop_duplicates().shape[0])

        return {
            "ambito_disposicion": "prestador" if ambito.get("es_departamento_prestador") else "departamental",
            "departamentos_receptores_prestamo": " / ".join(ambito.get("departamentos_receptores_prestamo") or []),
            "docente": docente,
            "cuil": cuil,
            "CUIL": cuil,
            "cargo": cargo_general,
            "dedicación": dedicacion_general,
            "horas": horas_general,
            "texto_departamentos_revistara": texto_departamentos_revistara,
            "departamento_revistara": texto_departamentos_revistara,
            "texto_departamento_disposicion": texto_departamento_disposicion,
            "departamento_disposicion": texto_departamento_disposicion,
            "cargo_concursado": cargo_conc,
            "dedicación_concursado": ded_conc,
            "horas_concursado": horas_conc,
            "cargo_interino": cargo_int,
            "dedicación_interino": ded_int,
            "horas_interino": horas_int,
            "resolucion_cs_concursado": dato_conc.get("resolucion", "") or datos_doc_dispo.get("resolucion_cs_concursado", ""),
            "fecha_desde_concursado": fecha_desde_conc,
            "fecha_hasta_concursado": fecha_hasta_conc,
            "resolucion_cs_interino": dato_int.get("resolucion", "") or datos_doc_dispo.get("resolucion_cs_interino", ""),
            "resolucion_rectoral_interino": dato_int.get("resolucion", "") or datos_doc_dispo.get("resolucion_cs_interino", ""),
            "fecha_desde_interino": fecha_desde_int,
            "fecha_hasta_interino": fecha_hasta_int,
            R.CLAVE_ASIGNATURAS_LEGACY: asignaturas_txt,
            R.CLAVE_ASIGNATURAS: asignaturas_txt,
            # El marcador de la plantilla vigente esta en el Art. 4: escuelas + unidades externas de proyectos.
            "Escuelas en las que se encuentran las materias que dicta": destinos_articulo_4,
            "Escuelas de las materias": escuelas_txt,
            "Institutos/Departamentos de proyectos a notificar": ", ".join(unidades_proyectos_notificar),
            "Destinatarios institucionales Artículo 4": destinos_articulo_4,
            "Rol en su Proyecto de Investigación": roles_inv,
            "Nombre Proyecto de Investigación": nombres_inv,
            "Código Interno del Proyecto": codigos_inv,
            "Instituto/Departamento al que pertenece el proyecto": institutos_inv,
            "Texto funciones de investigación": texto_investigacion_txt,
            "Texto funciones de investigación y extensión": texto_investigacion_txt,
            "Tipo funciones investigación/extensión": tipo_funciones_academicas,
            "Rol en su Proyecto de Extensión": roles_ext,
            "Nombre Proyecto de Extensión": nombres_ext,
            "Código Interno del Proyecto de Extensión": codigos_ext,
            "Área/Secretaría al que pertenece el proyecto de Extensión": areas_ext,
            "designaciones_disposicion": datos_designaciones_dispo,
            "considerandos_designaciones": R.construir_considerandos_designaciones_docente(
                docente, cuil, datos_designaciones_dispo, incluir_concursado=True, incluir_interino=True),
            "Cantidad proyectos de investigación": cantidad(df_inv),
            "Cantidad proyectos de extensión": cantidad(df_ext),
            "tiene_concursado": bool(cargo_conc or ded_conc),
            "tiene_interino": bool(cargo_int or ded_int),
            "tiene_investigacion": tiene_inv,
            "tiene_extension": tiene_ext,
            "tiene_investigacion_o_extension": bool(tiene_inv or tiene_ext),
        }

    # ------------------------------------------------------------------ funcion no docente (v163 / v164)
    def estado_funcional(self, cuil, periodo_id) -> dict:
        try:
            df = self.designaciones_docente(cuil, periodo_id)
        except Exception:
            df = pd.DataFrame()
        if df is None or df.empty:
            return {"tiene_no_docente": False, "tiene_docente": False, "es_exclusivamente_no_docente": False,
                    "es_mixta": False}
        df_use = df.copy()
        if "estado" in df_use.columns:
            activas = df_use[df_use["estado"].fillna("").astype(str).str.casefold().eq("activa")].copy()
            if not activas.empty:
                df_use = activas
        if "funcion_no_docente" not in df_use.columns:
            flags = pd.Series(False, index=df_use.index)
        else:
            flags = df_use["funcion_no_docente"].map(R.es_funcion_no_docente_v162)
        tiene_no_docente = bool(flags.any())
        tiene_docente = bool((~flags).any()) if len(flags) else False
        return {"tiene_no_docente": tiene_no_docente, "tiene_docente": tiene_docente,
                "es_exclusivamente_no_docente": bool(tiene_no_docente and not tiene_docente),
                "es_mixta": bool(tiene_no_docente and tiene_docente)}

    def texto_funcion_no_docente(self, cuil, periodo_id) -> str:
        try:
            df = self.designaciones_docente(cuil, periodo_id)
        except Exception:
            df = pd.DataFrame()
        if df is None or df.empty:
            return ""
        out = df.copy()
        if "estado" in out.columns:
            out = out[out["estado"].fillna("").astype(str).str.strip().str.casefold().eq("activa")].copy()
        if out.empty:
            return ""
        if "funcion_no_docente" not in out.columns:
            return ""
        out = out[out["funcion_no_docente"].map(R.es_funcion_no_docente_v162)].copy()
        textos = []
        for valor in out.get("texto_funcion_no_docente", pd.Series(dtype=str)).tolist():
            txt = R.texto_funcion_no_docente_limpio_v164(valor).rstrip(".")
            if txt and txt not in textos:
                textos.append(txt)
        return "; ".join(textos)

    # ------------------------------------------------------------------ preparacion masiva (v162 -> l. 6118)
    def preparar(self, cuil, periodo_id, numero_dispo, fecha_dispo, parametros=None) -> dict:
        prep = dict(self._preparar_base(cuil, periodo_id, numero_dispo, fecha_dispo, parametros=parametros) or {})
        estado_funcional = self.estado_funcional(cuil, periodo_id)
        es_no_docente = bool(estado_funcional.get("es_exclusivamente_no_docente"))
        es_mixta = bool(estado_funcional.get("es_mixta"))
        tiene_no_docente = bool(estado_funcional.get("tiene_no_docente"))
        texto = self.texto_funcion_no_docente(cuil, periodo_id)
        variables = dict(prep.get("variables") or {})
        variables["ES_FUNCION_NO_DOCENTE"] = es_no_docente
        variables["ES_FUNCION_MIXTA"] = es_mixta
        variables["Texto función no docente"] = texto if tiene_no_docente else ""
        variables["Texto variable Artículo 1"] = texto if tiene_no_docente else ""
        prep["variables"] = variables
        contexto = dict(prep.get("contexto") or {})
        contexto["ES_FUNCION_NO_DOCENTE"] = es_no_docente
        contexto["ES_FUNCION_MIXTA"] = es_mixta
        contexto["Texto función no docente"] = texto if tiene_no_docente else ""
        contexto["Texto variable Artículo 1"] = texto if tiene_no_docente else ""
        prep["contexto"] = contexto
        prep["funcion_no_docente_sin_texto"] = bool(tiene_no_docente and not texto)
        return prep

    def _preparar_base(self, cuil, periodo_id, numero_dispo, fecha_dispo, parametros=None) -> dict:
        parametros = dict(parametros or self.parametros() or {})
        contexto_doc = dict(self.contexto(cuil, periodo_id) or {})
        docente_nombre = R.limpiar_texto_tabla(contexto_doc.get("docente", "")) or str(cuil)
        asignaturas_txt = contexto_doc.get(R.CLAVE_ASIGNATURAS, contexto_doc.get(R.CLAVE_ASIGNATURAS_LEGACY, ""))
        datos_designaciones = [dict(x) for x in (contexto_doc.get("designaciones_disposicion", []) or [])]
        tiene_concursado = bool(contexto_doc.get("tiene_concursado", False))
        tiene_interino = bool(contexto_doc.get("tiene_interino", False))
        es_investigador = bool(contexto_doc.get("tiene_investigacion_o_extension",
                                                contexto_doc.get("tiene_investigacion", False)))
        considerandos = R.construir_considerandos_designaciones_docente(
            docente_nombre, cuil, datos_designaciones, incluir_concursado=tiene_concursado,
            incluir_interino=tiene_interino)
        primer_conc = primera_designacion(datos_designaciones, "Concursado")
        primer_int = primera_designacion(datos_designaciones, "Interino")
        incompletas = [x for x in datos_designaciones if (
            (R.normalizar_tipo_designacion_disposicion(x.get("tipo_designacion")) == "Concursado" and tiene_concursado)
            or (R.normalizar_tipo_designacion_disposicion(x.get("tipo_designacion")) == "Interino" and tiene_interino))
            and not R.normalizar_texto_disposicion(x.get("resolucion"))]
        variables = {}
        variables.update(parametros)
        variables.update(contexto_doc)
        variables.update({
            "Fecha Disposición": fecha_dispo.strftime("%d/%m/%Y") if hasattr(fecha_dispo, "strftime") else str(fecha_dispo),
            "número_disposición": str(numero_dispo),
            "departamento_disposicion_encabezado": contexto_doc.get("texto_departamento_disposicion", "")
            or self.texto_departamento_disposicion_docente(cuil, periodo_id),
            "fecha": parametros.get("fecha_acta_rector", ""),
            "fecha_acta_rector": parametros.get("fecha_acta_rector", ""),
            "docente": docente_nombre,
            "cuil": str(cuil),
            "CUIL": str(cuil),
            "cargo": contexto_doc.get("cargo", ""),
            "dedicación": contexto_doc.get("dedicación", ""),
            "texto_departamentos_revistara": contexto_doc.get("texto_departamentos_revistara", ""),
            "departamento_revistara": contexto_doc.get("texto_departamentos_revistara", ""),
            R.CLAVE_ASIGNATURAS_LEGACY: asignaturas_txt,
            R.CLAVE_ASIGNATURAS: asignaturas_txt,
            "Escuelas en las que se encuentran las materias que dicta":
                contexto_doc.get("Escuelas en las que se encuentran las materias que dicta", ""),
            "fecha_desde_interino": primer_int.get("fecha_desde", ""),
            "fecha_hasta_interino": primer_int.get("fecha_hasta", ""),
            "Rol en su Proyecto de Investigación": contexto_doc.get("Rol en su Proyecto de Investigación", ""),
            "Nombre Proyecto de Investigación": contexto_doc.get("Nombre Proyecto de Investigación", ""),
            "Código Interno del Proyecto": contexto_doc.get("Código Interno del Proyecto", ""),
            "Instituto/Departamento al que pertenece el proyecto":
                contexto_doc.get("Instituto/Departamento al que pertenece el proyecto", ""),
            "Texto funciones de investigación": contexto_doc.get("Texto funciones de investigación", ""),
            "Texto funciones de investigación y extensión": contexto_doc.get("Texto funciones de investigación", ""),
            "Tipo funciones investigación/extensión": contexto_doc.get("Tipo funciones investigación/extensión",
                                                                       "investigación"),
            "considerandos_designaciones": considerandos,
            "designaciones_disposicion": datos_designaciones,
            "resolucion_cs_concursado": primer_conc.get("resolucion", ""),
            "resolucion_cs_interino": primer_int.get("resolucion", ""),
            "resolucion_rectoral_interino": primer_int.get("resolucion", ""),
            "fecha_desde_concursado": primer_conc.get("fecha_desde", ""),
            "fecha_hasta_concursado": primer_conc.get("fecha_hasta", ""),
        })
        condiciones = {"SI_TIENE_CONCURSADO": tiene_concursado, "SI_TIENE_INTERINO": tiene_interino,
                       "SI_INVESTIGADOR": es_investigador, "SI_NO_INVESTIGA": not es_investigador}
        return {"cuil": str(cuil), "docente": docente_nombre, "numero": str(numero_dispo), "contexto": contexto_doc,
                "variables": variables, "condiciones": condiciones, "designaciones_incompletas": incompletas}

    # ------------------------------------------------------------------ estado de consulta (D12) e historial
    def estado_consulta(self, cuil, periodo_id) -> dict:
        df = self.repo.estado_consulta(int(periodo_id), str(cuil))
        if df.empty:
            return {"estado": "", "fecha_actualizacion": ""}
        return df.iloc[0].to_dict()

    def historial(self, periodo_id=None) -> pd.DataFrame:
        return self.repo.historial(periodo_id)


def primera_designacion(datos: list[dict], tipo: str) -> dict:
    """``_primera_designacion`` / ``_primer_formulario_tipo``: primer registro del tipo normalizado."""
    for item in datos:
        if R.normalizar_tipo_designacion_disposicion(item.get("tipo_designacion")) == tipo:
            return item
    return {}


__all__ = ["Lecturas", "primera_designacion", "COLUMNAS_HABILITADOS"]
