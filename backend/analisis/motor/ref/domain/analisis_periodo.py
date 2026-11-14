# B05: extracted verbatim from certified B04 (analisis de periodo: fotos de designaciones y balance de horas).
from __future__ import annotations

import pandas as pd

from analisis.motor.ref.domain.designaciones import _clave_designacion_desde_row_designacion
from analisis.motor.ref.domain.movimientos import _deduplicar_bajas_misma_designacion
from analisis.motor.ref.domain.movimientos import _delta_horas_movimiento_real
from analisis.motor.ref.domain.movimientos import _hay_baja_en_periodo_en_movimientos
from analisis.motor.ref.domain.movimientos import _row_indica_baja_en_periodo
from analisis.motor.ref.extracted_batch04.fechas import _fecha_a_timestamp_seguro
from analisis.motor.ref.extracted_batch04.numeros import _hora_numero
from analisis.motor.ref.extracted_batch04.texto import limpiar_texto_tabla


def _horas_inicio_desde_designaciones(df_all, fecha_inicio_periodo):
    """Calcula las horas que el docente tenía vigentes al comienzo del período."""
    if df_all is None or df_all.empty:
        return None
    fecha_inicio = _fecha_a_timestamp_seguro(fecha_inicio_periodo)
    if pd.isna(fecha_inicio):
        return None
    df = df_all.copy()
    df["_desde"] = df["fecha_desde"].apply(_fecha_a_timestamp_seguro) if "fecha_desde" in df.columns else pd.NaT
    if "fecha_finalizacion_efectiva" in df.columns:
        _serie_hasta = df["fecha_finalizacion_efectiva"].where(
            df["fecha_finalizacion_efectiva"].fillna("").astype(str).str.strip().ne(""),
            df.get("fecha_hasta", pd.Series(index=df.index, dtype=object))
        )
        df["_hasta"] = _serie_hasta.apply(_fecha_a_timestamp_seguro)
    else:
        df["_hasta"] = df["fecha_hasta"].apply(_fecha_a_timestamp_seguro) if "fecha_hasta" in df.columns else pd.NaT
    vigente_inicio = (
        (df["_desde"].isna() | (df["_desde"] <= fecha_inicio))
        & (df["_hasta"].isna() | (df["_hasta"] >= fecha_inicio))
    )
    df_inicio = df[vigente_inicio].copy()
    if df_inicio.empty:
        return None
    return float(pd.to_numeric(df_inicio.get("horas", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())


def _horas_referencia_alta_baja_mismo_periodo(df_all, fecha_inicio_periodo, fecha_fin_periodo=None, horas_actuales=0):
    """Referencia para docentes dados de alta y de baja dentro del mismo período.

    Si el docente no estaba al inicio del período y hoy no tiene cargo activo,
    comparar contra 0 hs hace que una baja completa se vea como variación 0.
    En ese caso se toma como referencia la primera foto real que tuvo dentro
    del período, sin duplicar filas generadas por ediciones o bajas repetidas.

    Ejemplo: alta en mayo 10 hs + baja en junio -> inicio operativo 10 hs,
    actual 0 hs, variación -10 hs.
    """
    if df_all is None or df_all.empty:
        return None
    if float(horas_actuales or 0) > 0:
        # Para docentes nuevos que siguen activos, la referencia sigue siendo el
        # estado actual salvo que existan movimientos explícitos de aumento/baja.
        return None

    fecha_inicio = _fecha_a_timestamp_seguro(fecha_inicio_periodo)
    fecha_fin = _fecha_a_timestamp_seguro(fecha_fin_periodo)
    df = df_all.copy()
    df["_desde"] = df["fecha_desde"].apply(_fecha_a_timestamp_seguro) if "fecha_desde" in df.columns else pd.NaT

    candidatos = df[df["_desde"].notna()].copy()
    if not pd.isna(fecha_inicio):
        candidatos = candidatos[candidatos["_desde"] >= fecha_inicio]
    if not pd.isna(fecha_fin):
        candidatos = candidatos[candidatos["_desde"] <= fecha_fin]
    if candidatos.empty:
        return None

    # Se toma la primera foto de designación dentro del período. Así no se
    # confunden aumentos posteriores o bajas editadas con horas iniciales.
    primera_fecha = candidatos["_desde"].min()
    df_ref = candidatos[candidatos["_desde"] == primera_fecha].copy()

    total = 0.0
    claves = set()
    for _, row in df_ref.iterrows():
        hs = _hora_numero(row.get("horas", 0))
        if hs <= 0:
            continue
        clave = _clave_designacion_desde_row_designacion(row)
        if clave in claves:
            continue
        claves.add(clave)
        total += hs
    return total if total > 0 else None


def _primeras_horas_designacion_en_periodo(df_all, fecha_inicio_periodo, fecha_fin_periodo=None):
    """Primera dedicación efectiva dentro del período.

    Sirve para docentes que no estaban al 1º día del período: la comparación no
    debe ser contra 0 hs sino contra su primera dedicación registrada en ese
    período.
    """
    if df_all is None or df_all.empty:
        return None
    df = df_all.copy()
    if "horas" not in df.columns:
        return None
    df["_hs_num"] = pd.to_numeric(df["horas"], errors="coerce").fillna(0)
    df = df[df["_hs_num"] > 0].copy()
    if df.empty:
        return None
    df["_desde"] = df["fecha_desde"].apply(_fecha_a_timestamp_seguro) if "fecha_desde" in df.columns else pd.NaT
    fecha_inicio = _fecha_a_timestamp_seguro(fecha_inicio_periodo)
    fecha_fin = _fecha_a_timestamp_seguro(fecha_fin_periodo)
    cand = df[df["_desde"].notna()].copy()
    if not pd.isna(fecha_inicio):
        cand = cand[cand["_desde"] >= fecha_inicio]
    if not pd.isna(fecha_fin):
        cand = cand[cand["_desde"] <= fecha_fin]
    if cand.empty:
        return None
    primera = cand["_desde"].min()
    g = cand[cand["_desde"] == primera].copy()
    total = 0.0
    vistos = set()
    for _, row in g.iterrows():
        clave = _clave_designacion_desde_row_designacion(row)
        if clave in vistos:
            continue
        vistos.add(clave)
        total += _hora_numero(row.get("horas", 0))
    return total if total > 0 else None


def _df_designaciones_estado_final_operativo_periodo(df_all, fecha_inicio_periodo, fecha_fin_periodo, df_mov=None):
    """Foto final del docente dentro del período, antes del cierre técnico.

    En períodos cerrados, las designaciones pueden figurar como Finalizadas por
    el cierre. Esta función intenta reconstruir qué cargo/horas quedaban al fin
    operativo del período. Si hubo baja real dentro del período y no queda una
    designación vigente al final, devuelve vacío para que se vea como baja.
    """
    if df_all is None or df_all.empty:
        return pd.DataFrame(columns=getattr(df_all, "columns", []))
    df = df_all.copy()
    if "horas" not in df.columns:
        return df.iloc[0:0].copy()
    df["_hs_num"] = pd.to_numeric(df["horas"], errors="coerce").fillna(0)
    df = df[df["_hs_num"] > 0].copy()
    if df.empty:
        return df
    if "estado" in df.columns:
        df = df[df["estado"].fillna("").astype(str).str.strip().str.lower() != "suspendida"].copy()
    if df.empty:
        return df

    fecha_inicio = _fecha_a_timestamp_seguro(fecha_inicio_periodo)
    fecha_fin = _fecha_a_timestamp_seguro(fecha_fin_periodo)
    df["_desde"] = df["fecha_desde"].apply(_fecha_a_timestamp_seguro) if "fecha_desde" in df.columns else pd.NaT
    df["_hasta"] = df["fecha_hasta"].apply(_fecha_a_timestamp_seguro) if "fecha_hasta" in df.columns else pd.NaT

    if not pd.isna(fecha_fin):
        vigente_fin = (df["_desde"].isna() | (df["_desde"] <= fecha_fin)) & (df["_hasta"].isna() | (df["_hasta"] >= fecha_fin))
        df_fin = df[vigente_fin].copy()
        if not df_fin.empty:
            vistos = set(); keep = []
            for idx, row in df_fin.iterrows():
                clave = _clave_designacion_desde_row_designacion(row)
                if clave in vistos:
                    continue
                vistos.add(clave); keep.append(idx)
            return df_fin.loc[keep].copy()

    # Si hubo baja real y no hay foto vigente al final, no se usa una designación vieja.
    if _hay_baja_en_periodo_en_movimientos(df_mov, evento_col="tipo_movimiento"):
        return df.iloc[0:0].copy()

    # Respaldo: tomar la última foto dentro del período.
    cand = df.copy()
    if not pd.isna(fecha_inicio):
        cand = cand[cand["_desde"].isna() | (cand["_desde"] >= fecha_inicio)]
    if not pd.isna(fecha_fin):
        cand = cand[cand["_desde"].isna() | (cand["_desde"] <= fecha_fin)]
    if cand.empty:
        return cand
    ultima = cand["_desde"].dropna().max()
    if pd.isna(ultima):
        return cand.tail(1).copy()
    cand = cand[cand["_desde"] == ultima].copy()
    vistos = set(); keep = []
    for idx, row in cand.iterrows():
        clave = _clave_designacion_desde_row_designacion(row)
        if clave in vistos:
            continue
        vistos.add(clave); keep.append(idx)
    return cand.loc[keep].copy()


def _balance_horas_periodo_docente(df_all, df_mov, fecha_inicio_periodo, fecha_fin_periodo=None, horas_actuales_visuales=0, horas_inicio_override=None):
    """Reconstruye una evolución horaria simple y didáctica (v140).

    La base del período reúne TODAS las designaciones que componen la situación
    del docente (por ejemplo, Concursado + Interino). Una designación paralela no
    se presenta como un aumento de dedicación: simplemente forma parte de la base.

    Solo los movimientos reales rotulados como Aumento/Disminución de dedicación
    modifican ``variacion_operativa``. De esta forma:

        horas_base + aumento/disminución real = horas actuales/del período

    ``horas_inicio_override`` se conserva en la firma por compatibilidad con las
    correcciones administrativas anteriores, pero la vista ya no necesita mostrar
    ni distinguir una "base corregida": la base visual se deriva de la foto total
    y de los cambios reales de dedicación.
    """
    # Solo movimientos que realmente cambian las horas de una designación ya existente.
    neto = 0.0
    eventos = []
    baja_real = False
    if df_mov is not None and not df_mov.empty:
        df_limpio = _deduplicar_bajas_misma_designacion(df_mov.copy(), evento_col="tipo_movimiento")
        for _, row in df_limpio.iterrows():
            delta, etiqueta = _delta_horas_movimiento_real(row)
            if abs(float(delta or 0)) > 1e-9:
                neto += float(delta)
                if etiqueta:
                    eventos.append(etiqueta)
            if _row_indica_baja_en_periodo(row, evento_col="tipo_movimiento"):
                baja_real = True

    # La foto visual actual/final ya suma todas las designaciones que corresponden
    # al docente en el período (Concursadas, Interinas, etc.). Esa es la fuente de
    # verdad del total. La base se obtiene quitando únicamente la variación REAL de
    # dedicación, no las altas de designaciones independientes.
    resultado = max(float(horas_actuales_visuales or 0), 0.0)
    horas_base = float(resultado or 0) - float(neto or 0)
    if horas_base < 0 and abs(horas_base) < 1e-9:
        horas_base = 0.0
    horas_base = max(horas_base, 0.0)

    return {
        "horas_inicio_operativo": round(float(horas_base or 0), 2),
        "variacion_operativa": round(float(neto or 0), 2),
        # Se mantiene por compatibilidad con código/estados anteriores; desde v140
        # ya no se presenta ni se necesita como concepto visual independiente.
        "variacion_composicion": 0.0,
        "horas_resultado_operativo": round(float(resultado or 0), 2),
        "baja_en_periodo_operativa": bool(baja_real and resultado <= 0),
        "eventos_horas": list(dict.fromkeys([e for e in eventos if e])),
    }


def _df_designaciones_vigentes_durante_periodo(df_all, fecha_inicio_periodo, fecha_fin_periodo):
    """Devuelve la foto histórica de designaciones que tuvieron vigencia dentro del período.

    En períodos cerrados las designaciones suelen quedar como Finalizada por la
    lógica de cierre. Para el resumen histórico no debe verse como 0 hs/baja si
    el docente efectivamente revistó durante ese período. Por eso se reconstruye
    la foto del período por rango de fechas, no solo por estado='Activa'.
    """
    if df_all is None or df_all.empty:
        return pd.DataFrame(columns=getattr(df_all, 'columns', []))
    df = df_all.copy()
    if 'horas' not in df.columns:
        return df.iloc[0:0].copy()
    df['_hs_num'] = pd.to_numeric(df['horas'], errors='coerce').fillna(0)
    df = df[df['_hs_num'] > 0].copy()
    if df.empty:
        return df

    if 'estado' in df.columns:
        df = df[df['estado'].fillna('').astype(str).str.strip().str.lower() != 'suspendida'].copy()
        if df.empty:
            return df

    fecha_inicio = _fecha_a_timestamp_seguro(fecha_inicio_periodo)
    fecha_fin = _fecha_a_timestamp_seguro(fecha_fin_periodo)
    df['_desde'] = df['fecha_desde'].apply(_fecha_a_timestamp_seguro) if 'fecha_desde' in df.columns else pd.NaT
    df['_hasta'] = df['fecha_hasta'].apply(_fecha_a_timestamp_seguro) if 'fecha_hasta' in df.columns else pd.NaT

    if not pd.isna(fecha_inicio) or not pd.isna(fecha_fin):
        vigente = pd.Series(True, index=df.index)
        if not pd.isna(fecha_fin):
            vigente = vigente & (df['_desde'].isna() | (df['_desde'] <= fecha_fin))
        if not pd.isna(fecha_inicio):
            vigente = vigente & (df['_hasta'].isna() | (df['_hasta'] >= fecha_inicio))
        df = df[vigente].copy()

    if df.empty:
        return df

    # Quita duplicados exactos de la misma designación para no inflar horas.
    vistos = set()
    keep = []
    for idx, row in df.iterrows():
        clave = _clave_designacion_desde_row_designacion(row)
        if clave in vistos:
            continue
        vistos.add(clave)
        keep.append(idx)
    return df.loc[keep].copy()


def _resumen_departamentos_desde_designaciones_df(df_designaciones):
    """Agrupa designaciones por departamento para mostrar docente compartido en resumen."""
    if df_designaciones is None or df_designaciones.empty:
        return []
    df = df_designaciones.copy()
    if "departamento" not in df.columns:
        df["departamento"] = "Departamento actual"
    if "horas" not in df.columns:
        df["horas"] = 0
    df["_hs_num"] = pd.to_numeric(df["horas"], errors="coerce").fillna(0)
    df = df[df["_hs_num"] > 0].copy()
    if df.empty:
        return []

    registros = []
    for depto, g in df.groupby("departamento", dropna=False, sort=True):
        vistos = set()
        cargos = []
        horas = 0.0
        for _, r in g.iterrows():
            clave = _clave_designacion_desde_row_designacion(r)
            if clave in vistos:
                continue
            vistos.add(clave)
            hs = _hora_numero(r.get("horas", 0))
            if hs <= 0:
                continue
            cargo = limpiar_texto_tabla(r.get("cargo", ""))
            dedic = limpiar_texto_tabla(r.get("dedicacion", ""))
            tipo = limpiar_texto_tabla(r.get("tipo_designacion", ""))
            texto = cargo or "Sin cargo"
            if tipo:
                texto += f" ({tipo})"
            if dedic:
                texto += f" · {dedic}"
            texto += f" · {int(hs) if float(hs).is_integer() else hs:g} hs"
            if texto not in cargos:
                cargos.append(texto)
            horas += hs
        if horas > 0:
            registros.append({
                "departamento": limpiar_texto_tabla(depto) or "Sin departamento",
                "cargo/s en el período": " / ".join(cargos),
                "horas": round(horas, 2),
            })
    return registros
