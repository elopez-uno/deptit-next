"""Historial "Altas, modificaciones y bajas del período" (solo lectura), copiado de la fuente certificada B13-FIX02.

Origen (entry): ``get_movimientos_designaciones_periodo_v266`` l. 55370 (sin la sincronizacion v268, que B12F omite
fuera de una operacion de negocio), ``_renovacion_concursada_legacy_valida_v268`` l. 9706, ``_periodos_contexto_v269``
l. 9758, ``_canonizar_movimientos_designaciones_v269`` l. 9815 y la clasificacion de
``_render_historial_designaciones_analisis_v267`` l. 54976 (variacion, tipo normalizado, categoria e indicadores).
"""

from __future__ import annotations

from typing import Callable, Optional

import pandas as pd

from . import rules
from .repository import DesignacionesRepository


def _renovacion_concursada_legacy_valida(repo: DesignacionesRepository, cuil, periodo: Optional[dict]) -> bool:
    if periodo is None:
        return False
    ini = rules.safe_date(periodo.get("fecha_inicio"), None)
    fin = rules.safe_date(periodo.get("fecha_fin"), None)
    filas = repo.concursadas_cuil(str(cuil or ""))
    for r in filas:
        desde = rules.safe_date(r.get("fecha_desde"), None)
        hasta = rules.safe_date(r.get("fecha_finalizacion_efectiva"), None)
        if hasta is None:
            hasta = rules.safe_date(r.get("fecha_hasta_prevista"), None)
        if hasta is None:
            hasta = rules.safe_date(r.get("fecha_hasta"), None)
        if ini is not None and hasta is not None and hasta < ini:
            continue
        if fin is not None and desde is not None and desde > fin:
            continue
        return True
    return False


def _periodos_contexto(repo: DesignacionesRepository, periodo_id: int):
    filas = repo.periods_context_v269()
    if not filas:
        return None, None, None
    df = pd.DataFrame(filas)
    ids = pd.to_numeric(df["id"], errors="coerce")
    pos = df.index[ids.eq(int(periodo_id))].tolist()
    if not pos:
        return None, df.iloc[0].to_dict(), None
    idx = df.index.get_loc(pos[0])
    actual = df.iloc[idx].to_dict()
    primero = df.iloc[0].to_dict()
    anterior = df.iloc[idx - 1].to_dict() if idx > 0 else None
    return actual, primero, anterior


def canonizar_v269(repo: DesignacionesRepository, df_mov: pd.DataFrame, periodo_id: int,
                   designaciones: Callable[[int], pd.DataFrame]) -> pd.DataFrame:
    """``_canonizar_movimientos_designaciones_v269`` con ``preservar_no_designacion=False``."""
    if df_mov is None:
        return pd.DataFrame()
    base = df_mov.copy()
    actual, primero, anterior = _periodos_contexto(repo, periodo_id)
    if actual is None:
        return rules.depurar_bajas_movimientos_v269(base)
    pid = int(actual.get("id"))
    es_primero = primero is not None and int(primero.get("id")) == pid
    des_mov = rules.depurar_bajas_movimientos_v269(base.copy())
    try:
        actuales = designaciones(pid)
        if actuales is None:
            actuales = pd.DataFrame()
    except Exception:
        actuales = pd.DataFrame()

    if es_primero:
        if not des_mov.empty:
            des_mov = des_mov[~des_mov["tipo_movimiento"].fillna("").astype(str).isin(
                rules.TIPOS_INICIO_DESIGNACION_V269)].copy()
        sinteticas = []
        inicio_per = rules.safe_date(actual.get("fecha_inicio"), None)
        fin_per = rules.safe_date(actual.get("fecha_fin"), None)
        nombre_per = str(actual.get("nombre") or "")
        for _, d in actuales.iterrows():
            did = int(pd.to_numeric(d.get("id"), errors="coerce") or 0)
            fdesde = rules.safe_date(d.get("fecha_desde"), None)
            fecha_mov = fdesde if (fdesde is not None and (inicio_per is None or fdesde >= inicio_per)
                                   and (fin_per is None or fdesde <= fin_per)) else inicio_per
            hs = float(pd.to_numeric(d.get("horas"), errors="coerce") or 0)
            detalle = (f"{nombre_per} - {d.get('cargo','')} - {d.get('dedicacion','')} - {hs:g} hs - "
                       f"{d.get('tipo_designacion','')}")
            fila = {c: pd.NA for c in base.columns}
            fila.update({
                "id": -900000000 - did, "periodo_id": pid, "periodo": nombre_per,
                "fecha": fecha_mov.isoformat() if fecha_mov is not None else str(actual.get("fecha_inicio") or ""),
                "tipo_movimiento": "Alta de designación", "cuil": d.get("cuil", ""),
                "nombre": d.get("nombre_completo", d.get("nombre", d.get("cuil", ""))), "detalle": detalle,
                "observaciones": ("Base inicial del sistema: la designación real del primer período se considera "
                                  "alta para el análisis histórico."),
                "horas_variacion": abs(hs),
            })
            if "acto_documento_id" in base.columns:
                fila["acto_documento_id"] = d.get("acto_documento_id", pd.NA)
            if "acto_administrativo" in base.columns:
                fila["acto_administrativo"] = d.get("acto_administrativo", "Pendiente de vincular")
            sinteticas.append(fila)
        if sinteticas:
            des_mov = pd.concat([des_mov, pd.DataFrame(sinteticas)], ignore_index=True, sort=False)
    elif anterior is not None and not des_mov.empty:
        try:
            prev = designaciones(int(anterior.get("id")))
            if prev is None:
                prev = pd.DataFrame()
        except Exception:
            prev = pd.DataFrame()
        cierre_prev = rules.safe_date(anterior.get("fecha_fin"), None)
        if not prev.empty:
            prev = prev[prev.apply(lambda r: rules.vigente_al_cierre_v269(r, cierre_prev), axis=1)].copy()
        for idx, mov in des_mov.iterrows():
            if str(mov.get("tipo_movimiento") or "").strip() != "Alta de designación":
                continue
            clave = rules.clave_cuil(mov.get("cuil")) or str(mov.get("cuil") or "").strip()
            candidatos = prev[prev.get("cuil", pd.Series(index=prev.index, dtype=str)).fillna("").astype(str).map(
                lambda x: rules.clave_cuil(x) or str(x).strip()).eq(clave)].copy() if not prev.empty else pd.DataFrame()
            if candidatos.empty:
                continue
            coinciden = candidatos[candidatos.apply(
                lambda r: rules.detalle_coincide_designacion_v269(mov.get("detalle", ""), r), axis=1)].copy()
            if coinciden.empty and len(candidatos) == 1:
                coinciden = candidatos.copy()
            if coinciden.empty:
                continue
            tipos_prev = {rules.normalizar_clave(x) for x in
                          coinciden.get("tipo_designacion", pd.Series(dtype=str)).fillna("").astype(str)}
            if tipos_prev == {"CONCURSADO"}:
                nuevo_tipo = "Continuidad automática de designación concursada"
                nota = "Reclasificado desde un Alta legacy: la concursada ya estaba vigente al cierre del período anterior."
            elif "CONCURSADO" not in tipos_prev:
                nuevo_tipo = "Renovación automática de designación"
                nota = "Reclasificado desde un Alta legacy: la designación ya estaba vigente al cierre del período anterior."
            else:
                continue
            des_mov.at[idx, "tipo_movimiento"] = nuevo_tipo
            obs = str(des_mov.at[idx, "observaciones"] or "").strip() if "observaciones" in des_mov.columns else ""
            if "observaciones" in des_mov.columns:
                des_mov.at[idx, "observaciones"] = (obs + " | " if obs else "") + nota
            if "horas_variacion" in des_mov.columns:
                des_mov.at[idx, "horas_variacion"] = 0

    out = des_mov
    if out.empty:
        return out
    orden_cols = [c for c in ["fecha", "id"] if c in out.columns]
    if orden_cols:
        try:
            out = out.sort_values(orden_cols, ascending=[False] * len(orden_cols), kind="stable", na_position="last")
        except Exception:
            pass
    return out.reset_index(drop=True)


def movimientos_designaciones_periodo(repo: DesignacionesRepository, periodo_id: int,
                                      designaciones: Callable[[int], pd.DataFrame]) -> pd.DataFrame:
    """``get_movimientos_designaciones_periodo_v266`` (lectura: la sincronizacion v268 no corre al leer)."""
    df = pd.DataFrame(repo.movimientos_periodo(int(periodo_id)),
                      columns=["id", "periodo_id", "fecha", "tipo_movimiento", "cuil", "nombre", "detalle",
                               "observaciones", "horas_variacion"])
    if df.empty:
        return df
    df = df[df["tipo_movimiento"].fillna("").astype(str).isin(rules.TIPOS_HISTORIAL_V266)].copy()
    if df.empty:
        return df
    periodo = repo.period_info(int(periodo_id))
    descartar = []
    for idx, row in df.iterrows():
        if str(row.get("tipo_movimiento") or "").strip() != "Renovación automática de designación":
            continue
        if "CONCURSADO" not in rules.normalizar_clave(str(row.get("detalle") or "")):
            continue
        if _renovacion_concursada_legacy_valida(repo, row.get("cuil"), periodo):
            df.at[idx, "tipo_movimiento"] = "Continuidad automática de designación concursada"
            obs = str(df.at[idx, "observaciones"] or "").strip()
            nota = "Reclasificado automáticamente: una designación concursada vigente continúa; no se renueva cuatrimestralmente."
            df.at[idx, "observaciones"] = (obs + " | " if obs else "") + nota
        else:
            descartar.append(idx)
    if descartar:
        df = df.drop(index=descartar).copy()
    if df.empty:
        return df
    actos = {int(a["movimiento_id"]): a for a in
             repo.actos_movimientos(pd.to_numeric(df["id"], errors="coerce").dropna().astype(int).tolist())}
    df["acto_documento_id"] = pd.NA
    df["acto_administrativo"] = ""
    try:
        des = designaciones(int(periodo_id))
    except Exception:
        des = pd.DataFrame()
    unicos = {}
    if isinstance(des, pd.DataFrame) and not des.empty:
        claves = des.get("cuil", pd.Series(index=des.index, dtype=str)).fillna("").astype(str).map(
            lambda x: rules.clave_cuil(x) or str(x).strip())
        for clave, g in des.groupby(claves):
            if not clave or g.empty:
                continue
            if len(g) == 1:
                unicos[clave] = g.iloc[0].to_dict()
                continue
            ids_acto = pd.to_numeric(g.get("acto_documento_id", pd.Series(index=g.index, dtype=float)), errors="coerce")
            ids_no_nulos = ids_acto.dropna().astype(int)
            if len(ids_no_nulos) == len(g) and len(ids_no_nulos.unique()) == 1:
                dref = g.iloc[0].to_dict()
                dref["acto_documento_id"] = int(ids_no_nulos.iloc[0])
                etiquetas = [str(x).strip() for x in g.get("acto_administrativo", pd.Series(index=g.index, dtype=str))
                             .fillna("").astype(str).tolist() if str(x).strip()]
                if etiquetas:
                    dref["acto_administrativo"] = etiquetas[0]
                unicos[clave] = dref
    for idx, row in df.iterrows():
        mid = int(row["id"])
        tipo = str(row.get("tipo_movimiento") or "")
        act = actos.get(mid)
        if act:
            df.at[idx, "acto_documento_id"] = int(act.get("documento_id"))
            df.at[idx, "acto_administrativo"] = rules.etiqueta_acto(act.get("tipo_documento"), act.get("numero"),
                                                                    act.get("dependencia_emisora"))
        elif tipo == "Cambio de número de resolución":
            df.at[idx, "acto_administrativo"] = "No corresponde (movimiento histórico de corrección manual)"
        elif tipo in {"Alta de designación", "Renovación automática de designación",
                      "Continuidad automática de designación concursada"}:
            clave = rules.clave_cuil(row.get("cuil")) or str(row.get("cuil") or "").strip()
            d = unicos.get(clave)
            if d:
                df.at[idx, "acto_documento_id"] = d.get("acto_documento_id", pd.NA)
                df.at[idx, "acto_administrativo"] = str(d.get("acto_administrativo") or "Pendiente de vincular")
            else:
                df.at[idx, "acto_administrativo"] = "Pendiente de vincular"
        elif tipo in rules.MOVIMIENTOS_ACTO_ADMINISTRATIVO_V266:
            df.at[idx, "acto_administrativo"] = "Pendiente de vincular"
        else:
            df.at[idx, "acto_administrativo"] = "No requerido"
    try:
        df = canonizar_v269(repo, df, int(periodo_id), designaciones)
    except Exception:
        pass
    return df


def clasificar_v267(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """Columnas de ``_render_historial_designaciones_analisis_v267`` e indicadores (etiqueta -> categoria)."""
    if df is None or df.empty:
        return pd.DataFrame(), []
    base = df.copy()
    base["variacion_horas_v267"] = base.apply(lambda r: rules.calcular_variacion_horas_movimiento(
        r.get("tipo_movimiento", ""), r.get("detalle", ""), r.get("horas_variacion", 0)), axis=1)
    base["tipo_normalizado_v267"] = base.apply(lambda r: rules.normalizar_tipo_movimiento_dedicacion(
        r.get("tipo_movimiento", ""), r.get("variacion_horas_v267", 0)), axis=1)
    base["categoria_movimiento_v267"] = base.apply(lambda r: rules.clasificar_movimiento_docente(
        r.get("tipo_normalizado_v267", ""), r.get("variacion_horas_v267", 0)), axis=1)
    presentes = [str(x) for x in base["categoria_movimiento_v267"].dropna().astype(str).unique().tolist()]
    categorias = [x for x in rules.ORDEN_HISTORIAL_V267 if x in presentes]
    categorias += [x for x in presentes if x not in categorias]
    if not categorias:
        categorias = presentes
    indicadores, vistas = [], set()
    for cat in categorias:
        et = rules.ROTULOS_HISTORIAL_V267.get(cat, cat)
        if et in vistas:
            et = f"{et} ({cat})"
        vistas.add(et)
        indicadores.append({"etiqueta": et, "categoria": cat, "movimiento": rules.ROTULOS_HISTORIAL_V267.get(cat, cat)})
    return base, indicadores
