"""Reglas puras de la pagina Movimientos, copiadas de la fuente certificada B13-FIX02.

Origen (entry): pagina ``elif modulo == "📜 Movimientos"`` l. 67764-67810 (selector de periodo, buscador, tabla,
gestion de actos y eliminar); ``_enriquecer_movimientos_acto_v266`` l. 55786; ``_render_gestion_acto_movimiento_v266``
l. 55572 (elegibles por tipo); ``seleccionar_registro_desde_tabla`` l. 14437 (primera fila por defecto).
Se reutilizan sin modificar las reglas ya portadas por Designaciones (``MOVIMIENTOS_ACTO_ADMINISTRATIVO_V266``,
``_etiqueta_acto_v263``, ``normalizar_clave``) y el filtro de texto de Docentes (``filtrar_dataframe_por_texto``).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

import pandas as pd

from designaciones.rules import MOVIMIENTOS_ACTO_ADMINISTRATIVO_V266, etiqueta_acto
from docentes.rules import filtrar_por_texto

__all__ = ["MOVIMIENTOS_ACTO_ADMINISTRATIVO_V266", "etiqueta_acto", "filtrar_por_texto"]

# --- textos certificados (l. 67764-67810, 55572-55640) -----------------------------------------------------------
TITULO = "📜 Movimientos"
SUBTITULO = "Historial de movimientos"
TODOS = "Todos los períodos"
LABEL_PERIODO = "Filtrar por período"
MSG_SIN_MOVIMIENTOS = "Todavía no hay movimientos registrados."
LABEL_BUSCAR = "Buscar en movimientos"
PLACEHOLDER_BUSCAR = "Fecha, tipo, docente, CUIL, detalle, observaciones..."
TITULO_TABLA = "Movimientos encontrados"
TITULO_ELIMINAR = "Eliminar movimiento del historial"
LABEL_CONFIRMAR = "Confirmo que quiero eliminar este movimiento"
BOTON_ELIMINAR = "🗑️ Eliminar movimiento"
MSG_ELIMINADO = "Movimiento eliminado."
MSG_CONFIRMAR = "Primero confirmá la eliminación."
TITULO_ACTOS = "🔗 Vincular / cambiar acto administrativo de uno o varios movimientos"
AYUDA_ACTOS = "Una misma resolución puede aprobar varias altas, modificaciones o bajas."
LABEL_BUSCAR_ACTOS = "Buscar movimientos para vincular"
PLACEHOLDER_BUSCAR_ACTOS = "Fecha, movimiento, docente, CUIL o detalle..."
MSG_SIN_COINCIDENCIAS_ACTOS = "No hay movimientos que coincidan con la búsqueda."
TITULO_SELECTOR = "Acto administrativo común para los movimientos seleccionados"
BOTON_VINCULAR = "🔗 Vincular / cambiar acto de los seleccionados"
BOTON_QUITAR = "Quitar vínculo de los seleccionados y dejar pendiente"

# Etiquetas de ``_enriquecer_movimientos_acto_v266`` (D-AL8: distintas del historial de Designaciones a proposito).
NO_CORRESPONDE = "No corresponde (histórico)"
PENDIENTE = "Pendiente de vincular"
NO_REQUERIDO = "No requerido"
TIPO_HISTORICO = "Cambio de número de resolución"

# Tabla principal: columnas, rotulos y orden certificados (``seleccionar_registro_desde_tabla``, l. 67790-67795).
COLUMNAS_TABLA = ["periodo", "fecha", "tipo_movimiento", "nombre", "cuil", "detalle", "acto_administrativo",
                  "observaciones"]
RENOMBRES = {"periodo": "Período", "fecha": "Fecha", "tipo_movimiento": "Movimiento", "nombre": "Persona / registro",
             "cuil": "CUIL", "detalle": "Detalle", "acto_administrativo": "Acto administrativo",
             "observaciones": "Observaciones"}
COLUMNAS_BUSQUEDA = list(COLUMNAS_TABLA)  # ``filtrar_dataframe_por_texto`` l. 67787-67789
# Grilla del expander de actos (l. 55588-55599).
COLUMNAS_BUSQUEDA_ACTOS = ["fecha", "tipo_movimiento", "nombre", "cuil", "detalle", "acto_administrativo"]
RENOMBRES_ACTOS = {"fecha": "Fecha", "tipo_movimiento": "Movimiento", "nombre": "Docente", "cuil": "CUIL",
                   "detalle": "Detalle", "acto_administrativo": "Acto administrativo"}

# Campos que la API devuelve por fila: los 8 visibles + los internos de la pagina (``id`` y el acto vinculado).
# Nunca columnas legacy (``source_db``, ``sqlite_id``, ...) ni ``periodo_id``/``horas_variacion`` (no se muestran).
CAMPOS_FILA = ["id"] + COLUMNAS_TABLA + ["acto_documento_id"]


def opciones_periodos(periodos: list[dict]) -> dict:
    """``opciones_periodos`` (l. 67771-67772): dict ``{nombre: id}`` en el orden de ``get_periodos`` (un nombre repetido
    conserva su posicion y queda con el ultimo id, como ``dict.update``)."""
    opciones: dict = {TODOS: None}
    opciones.update({row["nombre"]: row["id"] for row in periodos})
    return opciones


def periodo_inicial(opciones: dict, abierto: Optional[dict], ultimo: Optional[dict]) -> str:
    """``get_periodo_abierto() or get_ultimo_periodo()`` -> su nombre; si no esta entre las opciones, la primera."""
    ctx = abierto or ultimo
    default = str((ctx or {}).get("nombre") or TODOS)
    lista = list(opciones.keys())
    return lista[lista.index(default) if default in lista else 0]


def enriquecer(df: pd.DataFrame, mapa: dict) -> pd.DataFrame:
    """``_enriquecer_movimientos_acto_v266`` (l. 55786) con el mapa ya leido (``_mapa_actos_movimientos_v266``)."""
    if df is None or df.empty or "id" not in df.columns:
        return df
    out = df.copy()
    out["acto_documento_id"] = pd.NA
    out["acto_administrativo"] = ""
    for idx, row in out.iterrows():
        try:
            mid = int(row.get("id"))
        except Exception:
            continue
        tipo = str(row.get("tipo_movimiento") or "").strip()
        act = mapa.get(mid)
        if act:
            out.at[idx, "acto_documento_id"] = int(act.get("documento_id"))
            out.at[idx, "acto_administrativo"] = etiqueta_acto(act.get("tipo_documento"), act.get("numero"),
                                                               act.get("dependencia_emisora"))
        elif tipo == TIPO_HISTORICO:
            out.at[idx, "acto_administrativo"] = NO_CORRESPONDE
        elif tipo in MOVIMIENTOS_ACTO_ADMINISTRATIVO_V266:
            out.at[idx, "acto_administrativo"] = PENDIENTE
        else:
            out.at[idx, "acto_administrativo"] = NO_REQUERIDO
    return out


def elegible_acto(tipo: Any) -> bool:
    """Elegibles del expander de actos (l. 55576): ``fillna("").astype(str).isin(...)`` sin ``strip``."""
    texto = "" if tipo is None or (not isinstance(tipo, str) and pd.isna(tipo)) else str(tipo)
    return texto in MOVIMIENTOS_ACTO_ADMINISTRATIVO_V266


def _jsonable(value: Any) -> Any:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def fila_api(row: dict) -> dict:
    """Fila de la tabla para la API: solo ``CAMPOS_FILA`` + ``huella`` (B12I capa U, D-AL5)."""
    out = {c: _jsonable(row.get(c)) for c in CAMPOS_FILA}
    if out.get("acto_documento_id") is not None:
        out["acto_documento_id"] = int(out["acto_documento_id"])
    out["huella"] = huella(out)
    return out


def huella(fila: dict) -> str:
    """Huella del estado que el usuario vio de UNA fila (contenido visible + acto vinculado)."""
    payload = {c: fila.get(c) for c in CAMPOS_FILA}
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
