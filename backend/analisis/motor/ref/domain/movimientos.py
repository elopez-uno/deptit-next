# B05: extracted verbatim from certified B04 (movimientos de designaciones: variaciones, bajas, resumenes).
from __future__ import annotations

import re

import pandas as pd

from analisis.motor.ref.domain.designaciones import _clave_designacion_desde_texto
from analisis.motor.ref.domain.designaciones import extraer_partes_designacion
from analisis.motor.ref.extracted_batch01.movimientos import _movimiento_es_estado_inicial
from analisis.motor.ref.extracted_batch04.fechas import safe_date
from analisis.motor.ref.extracted_batch04.movimientos import _evento_es_baja_designacion
from analisis.motor.ref.extracted_batch04.movimientos import _extraer_antes_ahora
from analisis.motor.ref.extracted_batch04.movimientos import _extraer_horas_desde_texto
from analisis.motor.ref.extracted_batch04.movimientos import _horas_antes_ahora
from analisis.motor.ref.extracted_batch04.movimientos import _texto_row_movimiento
from analisis.motor.ref.extracted_batch04.movimientos import normalizar_tipo_movimiento_dedicacion
from analisis.motor.ref.extracted_batch04.numeros import _hora_numero
from analisis.motor.ref.extracted_batch04.texto import limpiar_texto_tabla
from analisis.motor.ref.extracted_batch04.texto import normalizar_clave


def resumen_movimientos_por_tipo(df_movimientos):
    if df_movimientos.empty:
        return pd.DataFrame(columns=["tipo_movimiento", "cantidad"])

    return (
        df_movimientos
        .groupby("tipo_movimiento", dropna=False)
        .size()
        .reset_index(name="cantidad")
        .sort_values("cantidad", ascending=False)
    )


def _formatear_cargo_y_tipo(partes):
    """Muestra solo el cargo y, cuando existe, el tipo de designación."""
    if not isinstance(partes, dict):
        return "-"
    cargo = limpiar_texto_tabla(partes.get("cargo", "")) or "-"
    tipo = limpiar_texto_tabla(partes.get("tipo_designacion", ""))
    if tipo:
        return f"{cargo} ({tipo})"
    return cargo


def simplificar_detalle_movimiento(tipo_movimiento, detalle):
    """
    Para el resumen individual del docente, muestra solo el dato que cambió.
    No modifica la base; solo mejora la visualización.
    """
    if detalle is None or pd.isna(detalle):
        return ""

    tipo = str(tipo_movimiento or "").strip()
    detalle_txt = str(detalle).strip()

    tipos_a_simplificar = [
        "Cambio de cargo",
        "Aumento de dedicación",
        "Disminución de dedicación"
    ]

    if tipo not in tipos_a_simplificar:
        return detalle_txt

    if "Antes:" not in detalle_txt or "Ahora:" not in detalle_txt:
        return detalle_txt

    try:
        antes_txt = detalle_txt.split("Antes:", 1)[1].split("/ Ahora:", 1)[0].strip()
        ahora_txt = detalle_txt.split("/ Ahora:", 1)[1].strip()

        antes = extraer_partes_designacion(antes_txt)
        ahora = extraer_partes_designacion(ahora_txt)

        if tipo == "Cambio de cargo":
            return f"Antes: {_formatear_cargo_y_tipo(antes)} / Ahora: {_formatear_cargo_y_tipo(ahora)}"

        if tipo in ["Aumento de dedicación", "Disminución de dedicación"]:
            antes_dedicacion = antes.get("dedicacion", "-")
            antes_horas = antes.get("horas", "-")
            ahora_dedicacion = ahora.get("dedicacion", "-")
            ahora_horas = ahora.get("horas", "-")
            return f"Antes: {antes_dedicacion} - {antes_horas} / Ahora: {ahora_dedicacion} - {ahora_horas}"

        return detalle_txt

    except Exception:
        return detalle_txt


def preparar_movimientos_resumen_docente(df_movimientos):
    """
    Devuelve una copia del historial con el detalle más limpio para cambios de cargo
    y cambios de dedicación/horas.
    """
    if df_movimientos.empty:
        return df_movimientos

    df = df_movimientos.copy()

    if "tipo_movimiento" in df.columns and "detalle" in df.columns:
        df["detalle"] = df.apply(
            lambda row: simplificar_detalle_movimiento(row["tipo_movimiento"], row["detalle"]),
            axis=1
        )

    return df


def calcular_variacion_horas_movimiento(tipo_movimiento, detalle, horas_variacion_guardada=0):
    """
    Calcula la variación de horas de cada movimiento.
    Criterio de signo:
    - Alta de designación: positivo.
    - Baja / eliminación de designación: negativo.
    - Aumento / disminución: diferencia Ahora - Antes.
    - Cambio de cargo: diferencia Ahora - Antes, normalmente 0.
    - Renovaciones y cierres automáticos: 0 para no duplicar el balance real del período.
    """
    try:
        guardada = float(horas_variacion_guardada or 0)
    except Exception:
        guardada = 0.0
    if guardada != 0:
        return guardada

    tipo = str(tipo_movimiento or "").strip()
    detalle_txt = str(detalle or "")
    horas_antes, horas_ahora = _horas_antes_ahora(detalle_txt)

    if tipo == "Alta de designación":
        return abs(_extraer_horas_desde_texto(detalle_txt))

    if tipo in [
        "Baja de designación", "Eliminación de designación",
        "Finalización de designación", "Finalizacion de designacion",
        "Finalización automática por vencimiento de designación",
    ]:
        horas = horas_antes if horas_antes else _extraer_horas_desde_texto(detalle_txt)
        return -abs(horas)

    if tipo in ["Aumento de dedicación", "Disminución de dedicación", "Cambio de cargo", "Modificación general"]:
        if horas_antes or horas_ahora:
            return horas_ahora - horas_antes
        return 0.0

    return 0.0


def clasificar_movimiento_docente(tipo_movimiento, variacion_horas=None):
    tipo = str(tipo_movimiento or "").strip()
    if variacion_horas is not None:
        tipo = normalizar_tipo_movimiento_dedicacion(tipo, variacion_horas)
    mapa = {
        "Alta de docente": "Altas de docentes",
        "Baja de docente": "Bajas de docentes",
        "Baja docente inferida": "Bajas de docentes",
        "Eliminación de docente": "Bajas de docentes",
        "Alta de designación": "Altas de designaciones",
        "Baja de designación": "Bajas de designaciones",
        "Eliminación de designación": "Bajas de designaciones",
        "Finalización de designación": "Bajas de designaciones",
        "Finalizacion de designacion": "Bajas de designaciones",
        "Finalización automática por vencimiento de designación": "Bajas de designaciones",
        "Aumento de dedicación": "Aumentos de dedicación",
        "Disminución de dedicación": "Disminuciones de dedicación",
        "Cambio de cargo": "Cambios de cargo",
        "Renovación automática de designación": "Renovaciones automáticas",
        "Continuidad automática de designación concursada": "Continuidades concursadas",
        "Finalización automática por cierre de período": "Cierres automáticos",
    }
    return mapa.get(tipo, tipo or "Sin tipo")


def resumen_movimiento_docente(df_movimientos_analisis):
    columnas = ["categoria_movimiento", "movimientos", "docentes_afectados", "variacion_horas"]
    if df_movimientos_analisis is None or df_movimientos_analisis.empty:
        return pd.DataFrame(columns=columnas)

    df = df_movimientos_analisis.copy()
    resumen = (
        df.groupby("categoria_movimiento", dropna=False)
        .agg(
            movimientos=("categoria_movimiento", "size"),
            docentes_afectados=("cuil", lambda s: s.dropna().astype(str).replace("", pd.NA).dropna().nunique()),
            variacion_horas=("variacion_horas", "sum")
        )
        .reset_index()
    )

    orden = {
        "Altas de docentes": 1,
        "Bajas de docentes": 2,
        "Altas de designaciones": 3,
        "Aumentos de dedicación": 4,
        "Disminuciones de dedicación": 5,
        "Bajas de designaciones": 6,
        "Cambios de cargo": 7,
        "Renovaciones automáticas": 8,
        "Cierres automáticos": 9,
    }
    resumen["_orden"] = resumen["categoria_movimiento"].map(orden).fillna(99)
    resumen = resumen.sort_values(["_orden", "categoria_movimiento"], kind="stable").drop(columns="_orden")
    resumen["variacion_horas"] = resumen["variacion_horas"].round(2)
    return resumen[columnas]


def resumen_movimiento_docente_por_docente(df_movimientos_analisis):
    columnas = ["docente", "cuil", "categoria_movimiento", "movimientos", "variacion_horas"]
    if df_movimientos_analisis is None or df_movimientos_analisis.empty:
        return pd.DataFrame(columns=columnas)

    df = df_movimientos_analisis.copy()
    resumen = (
        df.groupby(["docente", "cuil", "categoria_movimiento"], dropna=False)
        .agg(
            movimientos=("categoria_movimiento", "size"),
            variacion_horas=("variacion_horas", "sum")
        )
        .reset_index()
        .sort_values(["docente", "categoria_movimiento"], kind="stable")
    )
    resumen["variacion_horas"] = resumen["variacion_horas"].round(2)
    return resumen[columnas]


def _claves_designacion_movimiento(row):
    """Extrae las posibles fotos de designación mencionadas por un movimiento."""
    claves = set()
    detalle = str(row.get("detalle", "") or "")
    observaciones = str(row.get("observaciones", "") or "")
    texto = " | ".join([x for x in [detalle, observaciones] if x])
    candidatos = [detalle, observaciones, texto]
    try:
        antes, ahora = _extraer_antes_ahora(texto)
        candidatos.extend([antes, ahora])
    except Exception:
        pass
    for candidato in candidatos:
        if not str(candidato or "").strip():
            continue
        try:
            clave = _clave_designacion_desde_texto(candidato)
        except Exception:
            clave = None
        if clave:
            claves.add(clave)
    return claves


def texto_resumen_movimientos_docente(df_mov_didactico, periodo_nombre):
    """Devuelve un texto interpretativo del proceso del cargo/dedicación en el período."""
    if df_mov_didactico is None or df_mov_didactico.empty:
        return f"No hay movimientos ni designaciones registradas para este docente en {periodo_nombre}."

    df = _deduplicar_bajas_misma_designacion(df_mov_didactico.copy(), evento_col="evento")
    evento = df["evento"].fillna("").astype(str)

    altas = df[evento == "Alta/asignación en período"]
    cambios_cargo = df[evento == "Cambio de cargo"]
    aumentos = df[evento == "Aumento de dedicación"]
    disminuciones = df[evento == "Disminución de dedicación"]
    bajas = df[evento == "Baja de designación"]
    renovaciones = df[evento == "Renovación automática de designación"]
    cierres = df[evento == "Finalización automática por cierre de período"]
    baja_en_periodo = _hay_baja_en_periodo_en_movimientos(df, evento_col="evento") and _df_didactico_sin_cargo_activo(df, evento_col="evento")

    oraciones = []

    if not altas.empty:
        altas_txt = "; ".join(
            altas["resumen"].dropna().astype(str).replace("", pd.NA).dropna().drop_duplicates().tolist()
        )
        oraciones.append(f"En {periodo_nombre}, el docente registra como alta/asignación: {altas_txt}.")
    else:
        oraciones.append(f"En {periodo_nombre}, no se detecta una alta/asignación directa de designación para este docente.")

    if not renovaciones.empty:
        oraciones.append(f"El período incluye {len(renovaciones)} renovación/es automática/s de designación.")

    if not cambios_cargo.empty:
        txt = "; ".join(cambios_cargo["resumen"].dropna().astype(str).drop_duplicates().tolist())
        oraciones.append(f"Se registraron cambios de cargo: {txt}.")

    mov_dedic = []
    if not aumentos.empty:
        txt = "; ".join(aumentos["resumen"].dropna().astype(str).drop_duplicates().tolist())
        mov_dedic.append(f"aumentos ({txt})")
    if not disminuciones.empty:
        txt = "; ".join(disminuciones["resumen"].dropna().astype(str).drop_duplicates().tolist())
        mov_dedic.append(f"disminuciones ({txt})")
    if mov_dedic:
        oraciones.append("En dedicación/horas se registraron " + " y ".join(mov_dedic) + ".")
    else:
        oraciones.append("No se registran aumentos ni disminuciones de dedicación en el período.")

    if baja_en_periodo:
        oraciones.append("Resultado del período: baja en el período; el docente quedó sin cargo activo/horas vigentes en este período.")
    elif not bajas.empty:
        oraciones.append(f"También hay {len(bajas)} baja/s de designación registrada/s en el período.")

    altas_comision = df[evento == "Alta docente por modificación de asignación"]
    bajas_comision = df[evento == "Baja docente por modificación de asignación"]
    if not altas_comision.empty:
        txt = "; ".join(altas_comision["resumen"].dropna().astype(str).drop_duplicates().head(5).tolist())
        oraciones.append(f"En comisiones en curso se registraron altas: {txt}.")
    if not bajas_comision.empty:
        txt = "; ".join(bajas_comision["resumen"].dropna().astype(str).drop_duplicates().head(5).tolist())
        oraciones.append(f"En comisiones en curso se registraron bajas: {txt}.")

    if not cierres.empty:
        oraciones.append(f"Además, figuran {len(cierres)} finalización/es automática/s por cierre de período.")

    return " ".join(oraciones)


def _clave_designacion_afectada_por_movimiento(row):
    """Clave conservadora para deduplicar una misma baja sin mezclar docentes.

    v211:
    - si el movimiento declara el ID de la designación, esa es la identidad fuerte;
    - en movimientos legacy sin ID nunca se usa solo cargo/dedicación/horas/tipo,
      porque dos docentes distintos pueden compartir exactamente la misma firma;
    - la alternativa legacy incorpora CUIL + fecha + texto normalizado completo.

    Esto evita que una baja de un docente oculte en Análisis la de otro docente
    con el mismo cargo/dedicación, como podía ocurrir antes.
    """
    texto = _texto_row_movimiento(row)
    cuil = limpiar_texto_tabla(row.get("cuil", "")).strip()
    fecha = safe_date(row.get("fecha"), None)
    fecha_key = fecha.isoformat() if fecha is not None else limpiar_texto_tabla(row.get("fecha", ""))

    for patron in (
        r"ID\s+designaci[oó]n\s+original\s*[:#=-]?\s*(\d+)",
        r"\[(?:AUTO_)?V(?:207|208|209|210|211)_DESIGNACION_ID=(\d+)\]",
    ):
        m = re.search(patron, texto, flags=re.I)
        if m:
            return ("id_designacion_original", cuil, m.group(1))

    # Legacy: deduplicar solo si realmente parece la misma fila histórica.
    # No reducir la identidad a la firma contractual porque eso puede ocultar
    # movimientos válidos de personas diferentes o designaciones paralelas.
    texto_norm = re.sub(r"\s+", " ", limpiar_texto_tabla(texto).casefold()).strip()
    texto_norm = re.sub(r"estado\s+(activa|finalizada|suspendida)", "", texto_norm, flags=re.I)
    tipo = limpiar_texto_tabla(row.get("tipo_movimiento", "")).casefold()
    return ("legacy_exacta", cuil, fecha_key, tipo, texto_norm)


def _deduplicar_bajas_misma_designacion(df, evento_col="evento"):
    """Oculta duplicados visuales/analíticos de baja sobre la misma designación.

    No borra datos de la base. Solo devuelve una vista limpia para resúmenes,
    texto interpretativo y análisis. Si la misma baja quedó registrada dos veces
    por editar fecha/estado, conserva la primera fila y descarta las repetidas.
    """
    if df is None or df.empty or evento_col not in df.columns:
        return df
    vistos = set()
    indices = []
    for idx, row in df.iterrows():
        if _evento_es_baja_designacion(row.get(evento_col, "")):
            clave = _clave_designacion_afectada_por_movimiento(row)
            if clave in vistos:
                continue
            vistos.add(clave)
        indices.append(idx)
    return df.loc[indices].copy()


def _row_indica_baja_en_periodo(row, evento_col="evento"):
    """Detecta si una fila implica baja total en el período.

    Incluye bajas explícitas de designación y disminuciones cuya foto de "Ahora"
    queda en 0 hs. Esto permite mostrar "Baja en el período" aunque la baja
    haya sido cargada como disminución hasta cero.
    """
    try:
        evento = limpiar_texto_tabla(row.get(evento_col, ""))
    except Exception:
        evento = ""
    evento_l = evento.lower()
    if _evento_es_baja_designacion(evento) or evento_l in {"baja de docente", "eliminación de docente", "eliminacion de docente"}:
        return True
    if "disminución" in evento_l or "disminucion" in evento_l:
        texto = _texto_row_movimiento(row)
        antes_h, ahora_h = _horas_antes_ahora(texto)
        if float(antes_h or 0) > 0 and float(ahora_h or 0) <= 0:
            return True
        # Respaldo por si el texto simplificado no conserva el formato Antes/Ahora.
        if re.search(r"ahora\s*[:\-].{0,80}\b0\s*hs\b", texto, flags=re.I):
            return True
    return False


def _hay_baja_en_periodo_en_movimientos(df_movimientos, evento_col="evento"):
    if df_movimientos is None or df_movimientos.empty:
        return False
    df = _deduplicar_bajas_misma_designacion(df_movimientos.copy(), evento_col=evento_col)
    return any(_row_indica_baja_en_periodo(row, evento_col=evento_col) for _, row in df.iterrows())


def _df_didactico_sin_cargo_activo(df_mov_didactico, evento_col="evento"):
    """Indica si, según la vista didáctica, el docente no tiene designación activa al cierre visual."""
    if df_mov_didactico is None or df_mov_didactico.empty or evento_col not in df_mov_didactico.columns:
        return False
    df = df_mov_didactico.copy()
    evento = df[evento_col].fillna("").astype(str)
    altas = df[evento == "Alta/asignación en período"].copy()
    if altas.empty:
        return False
    textos = (altas.get("detalle", pd.Series(dtype=str)).fillna("").astype(str) + " " + altas.get("resumen", pd.Series(dtype=str)).fillna("").astype(str)).tolist()
    tiene_activa = any(re.search(r"estado\s+operativo\s*:\s*activa\b", t, flags=re.I) for t in textos)
    return not tiene_activa


def _horas_estado_inicial_desde_movimientos_detallado(df_mov):
    """Devuelve horas iniciales y claves de designaciones ya contadas.

    Esto permite sumar, además, designaciones concursadas/interinas que venían
    vigentes de antes del período y que no siempre aparecen como renovación.
    """
    if df_mov is None or df_mov.empty:
        return None, set()
    total = 0.0
    encontrados = 0
    claves = set()
    for _, row in df_mov.iterrows():
        if not _movimiento_es_estado_inicial(row):
            continue
        detalle = str(row.get("detalle", "") or "")
        hs = _extraer_horas_desde_texto(detalle)
        if hs == 0:
            hs = abs(_hora_numero(row.get("horas_variacion", 0)))
        if hs > 0:
            total += hs
            encontrados += 1
            clave = _clave_designacion_desde_texto(detalle)
            if clave:
                claves.add(clave)
    return (total if encontrados > 0 else None), claves


def _horas_estado_inicial_desde_movimientos(df_mov):
    """Suma las horas del estado de inicio del período sin mezclar bajas/aumentos posteriores."""
    total, _ = _horas_estado_inicial_desde_movimientos_detallado(df_mov)
    return total


def _resumen_cambio_cargo_limpio(detalle):
    antes_txt, ahora_txt = _extraer_antes_ahora(detalle)
    if not antes_txt or not ahora_txt:
        return limpiar_texto_tabla(detalle)
    antes = extraer_partes_designacion(antes_txt)
    ahora = extraer_partes_designacion(ahora_txt)
    return f"Antes: {_formatear_cargo_y_tipo(antes)} / Ahora: {_formatear_cargo_y_tipo(ahora)}"


def _delta_horas_movimiento_real(row):
    """Variación real de dedicación: solo aumentos/disminuciones, no altas/bajas paralelas."""
    if row is None:
        return 0.0, ""
    evento = limpiar_texto_tabla(row.get("tipo_movimiento", ""))
    evento_l = evento.lower()
    detalle = _texto_row_movimiento(row, columnas=["detalle", "observaciones"])
    if _movimiento_es_estado_inicial(row):
        return 0.0, ""
    if "cambio de cargo" in evento_l:
        return 0.0, ""
    if "aumento" in evento_l or "disminución" in evento_l or "disminucion" in evento_l:
        antes_h, ahora_h = _horas_antes_ahora(detalle)
        if antes_h or ahora_h:
            return float(ahora_h or 0) - float(antes_h or 0), evento
        hv = _hora_numero(row.get("horas_variacion", 0))
        return hv, evento
    if _evento_es_baja_designacion(evento) or evento_l in {"baja de docente", "eliminación de docente", "eliminacion de docente"}:
        # Una baja/finalización es un cambio de composición del conjunto de
        # designaciones, no una "Disminución de dedicación". Se detecta aparte
        # mediante _row_indica_baja_en_periodo y no contamina el indicador A/D.
        return 0.0, "Baja"
    return 0.0, ""


def _destino_ad_honorem_mov_v174(detalle):
    matches = re.findall(r"Ad\s*Honorem\s*:\s*(Sí|Si|No)", str(detalle or ""), flags=re.I)
    if not matches:
        return ""
    ultimo = normalizar_clave(matches[-1])
    return "Pase a Ad Honorem" if ultimo in {"SI", "SÍ"} else "Pase a Rentado"


def _filtrar_movimientos_informe_v176(df_mov_analisis):
    """Deja en el Word solo movimientos de gestión relevantes para la lectura ejecutiva."""
    if df_mov_analisis is None or not isinstance(df_mov_analisis, pd.DataFrame) or df_mov_analisis.empty:
        return pd.DataFrame(columns=getattr(df_mov_analisis, "columns", []))
    out = df_mov_analisis.copy()
    tipos_excluidos = {
        normalizar_clave(x) for x in [
            "Generación de disposición",
            "Eliminación de asignación docente a comisión",
            "Alta docente por modificación de asignación",
            "Baja docente por modificación de asignación",
            "Asignación docente a comisión",
            "Modificación de investigación",
            "Retorno al período actual",
            "Asignación a extensión",
            "Alta de horario de comisión",
            "Corrección de fechas de designación concursada",
            "Corrección de continuidad concursada vencida",
            "Modificación general",
            "Renovación automática de designación",
            "Renovaciones automáticas",
            "Renovación automática de investigación",
            "Edición de docente",
            "Asignación a investigación",
            "Cambio de funciones no docentes",
            "Cambio de función docente / no docente",
            "Cambio de función docente/no docente",
            "Actualización de docente existente",
            "Eliminación administrativa de periodo",
            "Eliminación administrativa de período",
            "Continuidad automática de designación concursada",
        ]
    }
    categorias_excluidas = {
        normalizar_clave(x) for x in [
            "Altas de docentes",
            "Bajas de docentes",
            "Alta docente por modificación de asignación",
            "Baja docente por modificación de asignación",
            "Asignación docente a comisión",
            "Modificación de investigación",
            "Renovaciones automáticas",
            "Edición de docente",
            "Asignación a investigación",
            "Cambio de funciones no docentes",
            "Cambio de función docente / no docente",
            "Cambio de función docente/no docente",
            "Actualización de docente existente",
            "Eliminación administrativa de periodo",
            "Eliminación administrativa de período",
            "Continuidad automática de designación concursada",
        ]
    }
    tipo_norm = out.get("tipo_movimiento", pd.Series("", index=out.index)).fillna("").astype(str).map(normalizar_clave)
    cat_norm = out.get("categoria_movimiento", pd.Series("", index=out.index)).fillna("").astype(str).map(normalizar_clave)
    out = out[~tipo_norm.isin(tipos_excluidos) & ~cat_norm.isin(categorias_excluidas)].copy()
    return out.reset_index(drop=True)


def _error_resolucion_movimiento_v263(respaldo):
    if not isinstance(respaldo, dict) or not respaldo.get("adjuntar"):
        return ""
    if respaldo.get("dependencia_id") in [None, ""]:
        return "Seleccioná la dependencia emisora de la resolución respaldatoria."
    if not str(respaldo.get("numero", "") or "").strip():
        return "Completá el número de la resolución respaldatoria."
    contenido = bytes(respaldo.get("contenido") or b"")
    if contenido and len(contenido) > 50 * 1024 * 1024:
        return "El PDF de la resolución supera 50 MB."
    return ""
