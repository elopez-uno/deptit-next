# B08: extracted verbatim from certified B07 (movimientos de designaciones: tipos vinculados y depuracion de bajas v269 (firma / baja sin cambio real)).
# Function text copied byte-for-byte from app_postgresql_refactor_b07_catalogs.py (sha256 f422f375a973756b5a7d7f90d99db91452a09ef16976f941ea536115615e4946).
# Catalogs are the canonical B07 objects (analisis.motor.ref.catalogs); do not duplicate them here.
from __future__ import annotations

import re

from analisis.motor.ref.catalogs.designaciones import CARGOS
from analisis.motor.ref.catalogs.designaciones import DEDICACIONES
from analisis.motor.ref.catalogs.designaciones import TIPOS_DESIGNACION
from analisis.motor.ref.catalogs.movimientos import TIPOS_MOVIMIENTO_VINCULADOS_DESIGNACION
from analisis.motor.ref.catalogs.movimientos import _TIPOS_BAJA_REAL_DESIGNACION_V269
from analisis.motor.ref.extracted_batch04.fechas import safe_date
from analisis.motor.ref.extracted_batch04.identidad import _clave_cuil
from analisis.motor.ref.extracted_batch04.movimientos import _extraer_antes_ahora
from analisis.motor.ref.extracted_batch04.movimientos import _tipo_movimiento_designacion_normalizado
from analisis.motor.ref.extracted_batch04.texto import normalizar_clave


def _es_movimiento_vinculado_designacion(valor):
    tipo = _tipo_movimiento_designacion_normalizado(valor)
    tipos = {
        _tipo_movimiento_designacion_normalizado(x)
        for x in TIPOS_MOVIMIENTO_VINCULADOS_DESIGNACION
    }
    return tipo in tipos


def _firma_baja_movimiento_v269(row):
    """Identidad de una baja histórica sin mezclar designaciones paralelas."""
    texto = " | ".join([
        str(row.get("detalle") or ""), str(row.get("observaciones") or "")
    ])
    cuil = _clave_cuil(row.get("cuil")) or str(row.get("cuil") or "").strip()
    fecha = safe_date(row.get("fecha"), None)
    fecha_key = fecha.isoformat() if fecha is not None else str(row.get("fecha") or "")[:10]
    # IDs fuertes, actuales y legacy.
    for patron in (
        r"\[designacion_id=(\d+)\]",
        r"ID\s+designaci[oó]n\s+original\s*[:#=-]?\s*(\d+)",
        r"\[(?:AUTO_)?V(?:207|208|209|210|211)_DESIGNACION_ID=(\d+)\]",
    ):
        m = re.search(patron, texto, flags=re.I)
        if m:
            return ("id", cuil, m.group(1))
    norm = normalizar_clave(texto)
    cargos = sorted([str(x) for x in CARGOS], key=len, reverse=True)
    dedics = sorted([str(x) for x in DEDICACIONES], key=len, reverse=True)
    tipos = sorted([str(x) for x in TIPOS_DESIGNACION], key=len, reverse=True)
    cargo = next((normalizar_clave(x) for x in cargos if normalizar_clave(x) in norm), "")
    dedic = next((normalizar_clave(x) for x in dedics if normalizar_clave(x) in norm), "")
    tipo = next((normalizar_clave(x) for x in tipos if normalizar_clave(x) in norm), "")
    mh = re.search(r"(?<!\d)(\d+(?:[.,]\d+)?)\s*HS\b", norm, flags=re.I)
    horas = mh.group(1).replace(",", ".") if mh else ""
    if cargo or dedic or horas or tipo:
        return ("firma", cuil, fecha_key, cargo, dedic, horas, tipo)
    # Último respaldo: mismo docente, misma fecha y texto sin estados/ruido de evento.
    reducido = re.sub(r"ESTADO\s+(ACTIVA|FINALIZADA|SUSPENDIDA)", "", norm, flags=re.I)
    reducido = re.sub(r"\s+", " ", reducido).strip()
    return ("texto", cuil, fecha_key, reducido)


def _baja_sin_cambio_real_v269(row):
    tipo = str(row.get("tipo_movimiento") or "").strip()
    if tipo not in _TIPOS_BAJA_REAL_DESIGNACION_V269:
        return False
    detalle = str(row.get("detalle") or "")
    if "Antes:" not in detalle or "Ahora:" not in detalle:
        return False
    antes, ahora = _extraer_antes_ahora(detalle)
    if not antes and not ahora:
        return False
    est_antes = re.findall(r"Estado\s+(Activa|Finalizada|Suspendida)", antes, flags=re.I)
    est_ahora = re.findall(r"Estado\s+(Activa|Finalizada|Suspendida)", ahora, flags=re.I)
    if not est_antes or not est_ahora:
        return False
    return normalizar_clave(est_antes[-1]) == "FINALIZADA" and normalizar_clave(est_ahora[-1]) == "FINALIZADA"


def _depurar_bajas_movimientos_v269(df):
    """Eliminación = corrección de carga, no baja real; además quita duplicados/no-op."""
    if df is None or df.empty or "tipo_movimiento" not in df.columns:
        return df
    out = df.copy()
    tipo = out["tipo_movimiento"].fillna("").astype(str).str.strip()
    # `eliminar_designacion` existe para borrar una carga errónea. No es movimiento de dotación.
    out = out[~tipo.isin(["Eliminación de designación", "Eliminacion de designacion"])].copy()
    if out.empty:
        return out
    out = out[~out.apply(_baja_sin_cambio_real_v269, axis=1)].copy()
    if out.empty:
        return out
    bajas = out["tipo_movimiento"].fillna("").astype(str).isin(_TIPOS_BAJA_REAL_DESIGNACION_V269)
    if not bajas.any():
        return out
    prioridad = {
        "Finalización automática por vencimiento de designación": 0,
        "Baja de designación": 1,
        "Finalizar / baja de designación": 1,
        "Finalización de designación": 2,
        "Finalizacion de designacion": 2,
    }
    elegidos = {}
    for idx, row in out[bajas].iterrows():
        clave = _firma_baja_movimiento_v269(row)
        pr = prioridad.get(str(row.get("tipo_movimiento") or "").strip(), 9)
        if clave not in elegidos or pr < elegidos[clave][0]:
            elegidos[clave] = (pr, idx)
    conservar_bajas = {idx for _, idx in elegidos.values()}
    conservar = [idx for idx in out.index if (not bool(bajas.loc[idx])) or idx in conservar_bajas]
    return out.loc[conservar].copy()
