"""Lecturas certificadas de Resoluciones y respaldos sobre el repositorio de la sesion (sin escrituras, D-AK7).

- ``repositorio``: ``get_documentos_respaldo_v251`` EFECTIVA = v286 (modo off: legado) -> v266 l. 55662 (docentes de los
  vinculos exactos designacion/movimiento) -> v251 l. 50953 (relaciones docentes/proyectos + compatibilidad v249) ->
  v249 l. 50430.  Las lecturas de relaciones no se silencian (B12D: sitio CRITICAL_DECISION l. 50993 / 55699).
- ``dependencias``: ``get_dependencias_documentales_v262`` l. 50216 (sin la siembra ni la migracion v262, D-AK7).
- ``docentes_por_periodo_v253`` l. 50594 sobre ``get_designaciones`` efectiva (la lectura ya portada de Designaciones).
- ``proyectos``: ``get_proyectos_investigacion`` / ``get_proyectos_extension`` efectivas (v283 off -> v199), las
  lecturas ya portadas de Investigacion / Extension.
- ``fuentes_resumen_docente``: las fuentes de ``get_actos_docente_resumen_v263`` (v263 + v266) SIN consolidar ni
  deduplicar; las consume la Etapa 4 (Resumen docente).  No hay pantalla ni endpoint que las use en este bloque.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Optional

import pandas as pd

from designaciones.service import DesignacionesService
from extension.lecturas import Lecturas as LecturasExtension
from extension.repository import ExtensionRepository
from investigacion.lecturas import Lecturas as LecturasInvestigacion

from . import rules as R
from .repository import DocumentosRepository

COLUMNAS_DOCENTES = ["Docente", "CUIL"]


class Lecturas:
    def __init__(self, repo: DocumentosRepository, today: date, rol: Optional[str]):
        self.repo = repo
        self.today = today
        self.rol = rol

    # ------------------------------------------------------------------ repositorio
    def repositorio(self) -> pd.DataFrame:
        base = self._repositorio_v251()
        if base is None or base.empty:
            return pd.DataFrame(base).copy()
        return pd.DataFrame(self._enriquecer_v266(base)).copy()

    def _repositorio_v251(self) -> pd.DataFrame:
        base = self.repo.documentos_v249()
        if base is None or base.empty:
            return base
        rel = self.repo.relacion_docentes()
        rel_proy = self.repo.relacion_proyectos()
        base = base.copy()
        base["cantidad_docentes"] = 0
        base["docentes"] = ""
        base["cuiles"] = ""
        base["cantidad_proyectos"] = 0
        base["proyectos"] = ""
        base["proyecto_ids"] = ""

        if rel is not None and not rel.empty:
            rel = rel.copy()
            rel["documento_id"] = pd.to_numeric(rel["documento_id"], errors="coerce")
            for idx, row in base.iterrows():
                did = int(row["id"])
                rr = rel[rel["documento_id"] == did].copy()
                if not rr.empty:
                    pares = []
                    for _, rd in rr.iterrows():
                        nom = str(rd.get("docente_nombre", "") or "").strip()
                        cui = str(rd.get("cuil", "") or "").strip()
                        pares.append(f"{nom} — {cui}" if nom else cui)
                    base.at[idx, "cantidad_docentes"] = int(len(rr))
                    base.at[idx, "docentes"] = " | ".join(pares)
                    base.at[idx, "cuiles"] = " | ".join(rr["cuil"].fillna("").astype(str).tolist())

        if rel_proy is not None and not rel_proy.empty:
            rel_proy = rel_proy.copy()
            rel_proy["documento_id"] = pd.to_numeric(rel_proy["documento_id"], errors="coerce")
            for idx, row in base.iterrows():
                did = int(row["id"])
                rr = rel_proy[rel_proy["documento_id"] == did].copy()
                if rr.empty:
                    continue
                etiquetas, ids = [], []
                for _, rp in rr.iterrows():
                    nom = str(rp.get("proyecto_nombre", "") or "").strip()
                    cod = str(rp.get("codigo_proyecto", "") or "").strip()
                    p_tipo = str(rp.get("proyecto_tipo", "") or "").strip()
                    try:
                        pid = int(rp.get("proyecto_id"))
                    except Exception:
                        pid = None
                    etiqueta = (f"[{cod}] " if cod else "") + (nom or (f"Proyecto {pid}" if pid else "Proyecto"))
                    if p_tipo == "investigacion":
                        etiqueta += " (Investigación)"
                    elif p_tipo == "extension":
                        etiqueta += " (Extensión)"
                    etiquetas.append(etiqueta)
                    if pid is not None:
                        ids.append(f"{p_tipo}:{pid}")
                base.at[idx, "cantidad_proyectos"] = int(len(rr))
                base.at[idx, "proyectos"] = " | ".join(etiquetas)
                base.at[idx, "proyecto_ids"] = " | ".join(ids)

        # Compatibilidad con registros antiguos que aun no tengan relacion explicita.
        for idx, row in base.iterrows():
            if int(row.get("cantidad_docentes", 0) or 0) <= 0:
                nom = str(row.get("docente", "") or "").strip()
                cui = str(row.get("cuil", "") or "").strip()
                if nom or cui:
                    base.at[idx, "cantidad_docentes"] = 1
                    base.at[idx, "docentes"] = f"{nom} — {cui}" if nom and cui else (nom or cui)
                    base.at[idx, "cuiles"] = cui
            if int(row.get("cantidad_proyectos", 0) or 0) <= 0:
                pid = row.get("proyecto_id")
                p_tipo = str(row.get("proyecto_tipo", "") or "").strip()
                if pd.notna(pid) and str(pid).strip() and p_tipo:
                    try:
                        pid_i = int(pid)
                    except Exception:
                        pid_i = None
                    if pid_i is not None:
                        ref = str(row.get("referencia", "") or "").strip()
                        base.at[idx, "cantidad_proyectos"] = 1
                        base.at[idx, "proyectos"] = ref or f"Proyecto {pid_i}"
                        base.at[idx, "proyecto_ids"] = f"{p_tipo}:{pid_i}"
        return base

    def _enriquecer_v266(self, base: pd.DataFrame) -> pd.DataFrame:
        exactos = self.repo.vinculos_exactos_v266()
        if exactos is None or exactos.empty:
            return base
        out = base.copy()
        exactos["documento_id"] = pd.to_numeric(exactos["documento_id"], errors="coerce")
        for idx, row in out.iterrows():
            try:
                did = int(row.get("id"))
            except Exception:
                continue
            rr = exactos[exactos["documento_id"].eq(did)].copy()
            if rr.empty:
                continue
            actuales = [i.strip() for i in str(row.get("docentes") or "").split(" | ") if i.strip()]
            actuales_cuil = [i.strip() for i in str(row.get("cuiles") or "").split(" | ") if i.strip()]
            mapa_cuil = {(R.clave_cuil(x) or x): x for x in actuales_cuil}
            for _, rd in rr.iterrows():
                cui = str(rd.get("cuil") or "").strip()
                nom = str(rd.get("docente_nombre") or "").strip()
                ck = R.clave_cuil(cui) or cui
                if ck and ck not in mapa_cuil:
                    mapa_cuil[ck] = cui
                    actuales_cuil.append(cui)
                    etiqueta = f"{nom} — {cui}" if nom else cui
                    if etiqueta not in actuales:
                        actuales.append(etiqueta)
            out.at[idx, "cantidad_docentes"] = len(mapa_cuil)
            out.at[idx, "docentes"] = " | ".join(actuales)
            out.at[idx, "cuiles"] = " | ".join(actuales_cuil)
        return out

    # ------------------------------------------------------------------ dependencias, periodos
    def dependencias(self, solo_activas: bool = False) -> pd.DataFrame:
        return self.repo.dependencias(solo_activas=solo_activas)

    def periodos(self) -> pd.DataFrame:
        rows = self.repo.periods()
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    def ultimo_periodo(self) -> Optional[dict]:
        return self.repo.last_period()

    # ------------------------------------------------------------------ selectores de la pestaña "Cargar acto"
    def designaciones(self, periodo_id: int) -> pd.DataFrame:
        filas = DesignacionesService._designaciones(self.repo, int(periodo_id))
        return pd.DataFrame(filas) if filas else pd.DataFrame()

    def designaciones_de_docentes(self, cuiles: Any) -> list[dict]:
        """6A-B3 (aceptacion humana): todas las designaciones (``get_designaciones`` efectiva, cada periodo) de los
        CUIL indicados, con su acto vinculado actual (``documentos_respaldo_designaciones``).  Se usa para elegir por
        id real que designacion respalda una resolucion de "Designación docente"."""
        claves = {R.clave_cuil(c) or str(c).strip() for c in (cuiles or []) if str(c or "").strip()}
        if not claves:
            return []
        out = []
        for per in self.repo.periods():
            for f in DesignacionesService._designaciones(self.repo, int(per["id"])):
                if (R.clave_cuil(f.get("cuil")) or str(f.get("cuil") or "").strip()) in claves:
                    out.append(f)
        return out

    def legado_documento(self, documento_id: int) -> dict:
        """Columnas historicas v249 del acto (docente y primer proyecto): el listado las usa solo si el acto no tiene
        relaciones explicitas v251 / v261."""
        out = {"cuil": "", "docente": "", "proyecto_id": None, "proyecto_tipo": ""}
        docs = self.repo.documentos_v249()
        if docs is None or docs.empty:
            return out
        fila = docs[pd.to_numeric(docs["id"], errors="coerce").eq(int(documento_id))]
        if fila.empty:
            return out
        f = fila.iloc[0]
        pid = pd.to_numeric(f.get("proyecto_id"), errors="coerce")
        return {"cuil": str(f.get("cuil") or "").strip(), "docente": str(f.get("docente") or "").strip(),
                "proyecto_id": None if pd.isna(pid) else int(pid),
                "proyecto_tipo": str(f.get("proyecto_tipo") or "").strip()}

    def cuiles_documento(self, documento_id: int) -> list[str]:
        """CUIL vinculados a un documento: relacion v251 (``documentos_respaldo_docentes``) + columna legacy v249."""
        rel = self.repo.relacion_docentes()
        cuiles = [] if rel is None or rel.empty else \
            [str(c).strip() for c in rel[pd.to_numeric(rel["documento_id"], errors="coerce").eq(int(documento_id))]
             ["cuil"].tolist()]
        docs = self.repo.documentos_v249()
        if docs is not None and not docs.empty:
            fila = docs[pd.to_numeric(docs["id"], errors="coerce").eq(int(documento_id))]
            if not fila.empty and str(fila.iloc[0].get("cuil") or "").strip():
                cuiles.append(str(fila.iloc[0]["cuil"]).strip())
        return list(dict.fromkeys(c for c in cuiles if c))

    def docentes_por_periodo_v253(self, periodo_id: Any, solo_activas: bool = False) -> pd.DataFrame:
        if periodo_id is None:
            return pd.DataFrame(columns=COLUMNAS_DOCENTES)
        df_des = self.designaciones(int(periodo_id))
        if df_des is None or df_des.empty:
            return pd.DataFrame(columns=COLUMNAS_DOCENTES)
        df = df_des.copy()
        if solo_activas:
            estados = df.get("estado", pd.Series(index=df.index, dtype=str)).fillna("").astype(str).str.strip() \
                .str.casefold()
            df = df[estados.eq("activa")].copy()
        if df.empty:
            return pd.DataFrame(columns=COLUMNAS_DOCENTES)
        cuiles = df.get("cuil", pd.Series(index=df.index, dtype=str)).fillna("").astype(str).str.strip()
        nombres = df.get("nombre_completo", pd.Series(index=df.index, dtype=str)).fillna("").astype(str).str.strip()
        salida = pd.DataFrame({"Docente": nombres, "CUIL": cuiles})
        salida = salida[salida["CUIL"].ne("")].copy()
        salida.loc[salida["Docente"].eq(""), "Docente"] = salida.loc[salida["Docente"].eq(""), "CUIL"]
        salida["_cuil_key_v253"] = salida["CUIL"].map(lambda x: R.clave_cuil(x) or str(x).strip())
        salida = salida.drop_duplicates("_cuil_key_v253", keep="first").drop(columns=["_cuil_key_v253"])
        return salida.sort_values(["Docente", "CUIL"], kind="stable").reset_index(drop=True)

    def proyectos(self, tipo: str) -> pd.DataFrame:
        """Tabla selectora de proyectos (l. 51937-51956)."""
        if tipo == "extension":
            lec = LecturasExtension(ExtensionRepository(self.repo._conn, self.repo.inst, self.repo.dep), self.today,
                                    self.rol)
        else:
            lec = LecturasInvestigacion(self.repo, self.today, self.rol)
        df_pr = lec.proyectos()
        filas = []
        if isinstance(df_pr, pd.DataFrame) and not df_pr.empty:
            for _, rr in df_pr.iterrows():
                try:
                    pid = int(rr.get("id"))
                except Exception:
                    continue
                filas.append({
                    "ID": pid,
                    "Código": str(rr.get("codigo_proyecto", "") or "").strip(),
                    "Proyecto": str(rr.get("nombre_proyecto", "") or "").strip() or f"Proyecto {pid}",
                    "Estado": str(rr.get("estado", "") or "").strip(),
                    "Inicio": rr.get("fecha_inicio", ""),
                    "Fin": rr.get("fecha_fin", ""),
                    "Departamento creador": str(rr.get("departamento_creador", "") or "").strip(),
                })
        return pd.DataFrame(filas)

    # ------------------------------------------------------------------ PDF (solo descarga y detalle)
    def pdf(self, documento_id: int) -> Optional[dict]:
        """``obtener_pdf_documento_respaldo_v249`` (l. 50480)."""
        row = self.repo.pdf(int(documento_id))
        if row is None:
            return None
        return {"nombre": str(row.get("archivo_nombre") or R.NOMBRE_PDF_DEFECTO),
                "mime": str(row.get("archivo_mime") or R.PDF_MIME),
                "bytes": bytes(row.get("archivo_pdf") or b"")}

    def tiene_pdf(self, documento_id: int) -> bool:
        return bool(self.repo.pdf_bytes(int(documento_id)) or 0)

    # ------------------------------------------------------------------ Resumen docente (Etapa 4)
    def fuentes_resumen_docente(self, cuil: Any) -> dict:
        """Fuentes certificadas de ``get_actos_docente_resumen_v263`` (v263 l. 51302 + v266 l. 55808), sin consolidar."""
        clave = R.clave_cuil(cuil) or re.sub(r"[^0-9]", "", str(cuil or ""))
        if not clave:
            return {"clave": "", "repositorio": [], "disposiciones": [], "pendientes": [], "vinculos_v266": []}
        return {"clave": clave,
                "repositorio": self.repo.resumen_repositorio(clave),
                "disposiciones": self.repo.resumen_disposiciones(clave),
                "pendientes": self.repo.resumen_pendientes(clave),
                "vinculos_v266": self.repo.resumen_vinculos_v266(clave)}


# ------------------------------------------------------------------ opciones de pantalla (labels certificados)
def opciones_periodo_alta(df_per: pd.DataFrame) -> dict:
    """"Período relacionado (opcional)" (l. 51756-51765): etiqueta -> id; la primera etiqueta repetida gana."""
    mapa: dict = {"Sin período": None}
    if isinstance(df_per, pd.DataFrame) and not df_per.empty:
        for _, rp in df_per.sort_values(["anio", "semestre"], ascending=[False, False]).iterrows():
            et = str(rp.get("nombre") or f"{rp.get('anio', '')}-{rp.get('semestre', '')}")
            if et not in mapa:
                mapa[et] = int(rp["id"])
    return mapa


def opciones_periodo_docentes(df_periodos: pd.DataFrame) -> dict:
    """"Período / cuatrimestre" del modo "Elegir un período" (l. 51812-51844)."""
    mapa: dict = {}
    if df_periodos is None or df_periodos.empty:
        return mapa
    df = df_periodos.copy()
    for col in ["anio", "semestre", "id"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    cols = [c for c in ["anio", "semestre", "id"] if c in df.columns]
    if cols:
        df = df.sort_values(cols, ascending=[False] * len(cols), kind="stable")
    for _, rp in df.iterrows():
        try:
            pid = int(rp.get("id"))
        except Exception:
            continue
        nombre = str(rp.get("nombre") or "").strip()
        if not nombre:
            anio = str(rp.get("anio") or "").strip()
            sem = str(rp.get("semestre") or "").strip()
            nombre = f"{anio}-{sem}".strip("-") or f"Período {pid}"
        etiqueta = nombre if nombre not in mapa else f"{nombre} — ID {pid}"
        mapa[etiqueta] = pid
    return mapa


def opciones_dependencias_alta(df: pd.DataFrame) -> dict:
    """Dependencias activas del alta (l. 51733-51747): etiqueta -> (id, nombre)."""
    mapa: dict = {"Seleccionar dependencia": (None, "")}
    if df is not None and not df.empty:
        for _, rd in df.iterrows():
            nom = str(rd.get("nombre") or "").strip()
            if not nom:
                continue
            etiqueta = nom if nom not in mapa else f"{nom} — ID {int(rd['id'])}"
            mapa[etiqueta] = (int(rd["id"]), nom)
    return mapa


def opciones_dependencias_correccion(df: pd.DataFrame, dependencia_id_actual: Any) -> tuple[list, dict, int]:
    """"Asignar o corregir dependencia emisora" (l. 51651-51670): todas, con " [Inactiva]"."""
    opciones, mapa = [], {}
    if df is None or df.empty:
        return opciones, mapa, 0
    for _, rd in df.iterrows():
        did = int(rd["id"])
        nom = str(rd.get("nombre") or "").strip()
        estado = str(rd.get("estado") or "Activa").strip()
        etiqueta = nom + (" [Inactiva]" if estado == "Inactiva" else "")
        opciones.append(etiqueta)
        mapa[etiqueta] = did
    index = 0
    try:
        actual = int(dependencia_id_actual) if pd.notna(dependencia_id_actual) and \
            str(dependencia_id_actual).strip() else None
    except Exception:
        actual = None
    if actual is not None:
        for pos, et in enumerate(opciones):
            if mapa.get(et) == actual:
                index = pos
                break
    return opciones, mapa, index
