"""Reglas puras de Docentes (sin base de datos), copiadas de la fuente certificada B13-FIX02.

Origen (reference_fix02):
- ``deptit_refactor/b13fix02/validation.py``: K2 (CUIL) y K3 (correo) para datos NUEVOS.
- ``deptit_refactor/extracted_batch04/identidad.py`` y ``texto.py``: ``nombre_completo``, ``_clave_cuil``,
  ``limpiar_cuil``, ``limpiar_texto_tabla``, ``normalizar_clave``, ``safe_index``.
- ``deptit_refactor/b12a/posgrado.py``: canonicalizacion y guarda de escritura del nivel de posgrado.
- ``deptit_refactor/common/text.py``: ``filtrar_dataframe_por_texto`` (sobre listas de dicts).
- ``deptit_refactor/common/normalization.py``: ``_es_vacio_v168`` y ``_firma_fila_v168``.
- Catalogos: ``catalogs/designaciones.py`` (ESTADOS_DOCENTE), entry l. 523 (TIPOS_DOCENTE), l. 25441 (niveles).
"""

from __future__ import annotations

import math
import re
import unicodedata
from typing import Any, Iterable, Optional

ESTADOS_DOCENTE = ["Activo", "Licencia", "Jubilado", "Renunciado", "Fallecido"]
ESTADOS_BAJA_DOCENTE = ["Renunciado", "Jubilado", "Fallecido"]
TIPOS_DOCENTE = ["Propio", "Prestado"]
NIVELES_POSGRADO_SALARIAL = ["", "Especialista", "Magíster", "Doctor"]
ANTIGUEDAD_MIN, ANTIGUEDAD_MAX = 0, 80

# --- K2 / K3 (validation.py) ------------------------------------------------------------------------------
CUIL_DIGITOS = 11
_SEPARADORES_CUIL = re.compile(r"[\s.\-]")
_CUIL_NORMALIZADO = re.compile(r"[0-9]{%d}" % CUIL_DIGITOS)
_EMAIL = re.compile(r"[^@\s]+@[^@\s.]+(\.[^@\s.]+)+")


def _texto(valor: Any) -> str:
    return "" if valor is None else str(valor).strip()


def problema_cuil(cuil: Any) -> str:
    txt = _texto(cuil)
    if not txt:
        return "Completá el CUIL."
    if not _CUIL_NORMALIZADO.fullmatch(_SEPARADORES_CUIL.sub("", txt)):
        return f"El CUIL debe tener {CUIL_DIGITOS} dígitos, con o sin guiones (por ejemplo 20-12345678-9)."
    return ""


def problema_email(email: Any) -> str:
    txt = _texto(email)
    if txt and not _EMAIL.fullmatch(txt):
        return "El correo electrónico no tiene un formato válido (por ejemplo nombre@dominio.com)."
    return ""


def problema_alta_docente(cuil: Any, email: Any) -> str:
    return problema_cuil(cuil) or problema_email(email)


def _sin_espacios(valor: Any) -> str:
    return re.sub(r"\s", "", _texto(valor))


def problema_edicion_docente(cuil_original: Any, cuil_nuevo: Any, email_original: Any, email_nuevo: Any) -> str:
    if _sin_espacios(cuil_nuevo) != _sin_espacios(cuil_original):
        problema = problema_cuil(cuil_nuevo)
        if problema:
            return problema
    if _texto(email_nuevo) != _texto(email_original):
        return problema_email(email_nuevo)
    return ""


# --- identidad y texto (extracted_batch04) ----------------------------------------------------------------
def _is_na(valor: Any) -> bool:
    """``pd.isna`` para escalares (None, NaN, NaT, pd.NA)."""
    if valor is None:
        return True
    if isinstance(valor, float) and math.isnan(valor):
        return True
    try:
        import pandas as pd

        result = pd.isna(valor)
        return isinstance(result, bool) and result
    except Exception:
        return False


def limpiar_texto_tabla(valor: Any) -> str:
    if valor is None or _is_na(valor):
        return ""
    txt = str(valor).strip()
    if txt.lower() in ["nan", "none", "nat"]:
        return ""
    return txt


def nombre_completo(apellido: Any, nombres: Any) -> str:
    apellido = apellido.strip() if apellido else ""
    nombres = nombres.strip() if nombres else ""
    if apellido and nombres:
        return f"{apellido}, {nombres}"
    return apellido or nombres


def clave_cuil(valor: Any) -> str:
    """``_clave_cuil``: compara CUIL por sus digitos, sin alterar como se guarda o se muestra."""
    return re.sub(r"[^0-9]", "", limpiar_texto_tabla(valor))


def limpiar_cuil(valor: Any) -> str:
    txt = limpiar_texto_tabla(valor)
    if txt.endswith(".0"):
        txt = txt[:-2]
    return txt.replace(" ", "")


def separar_docente_en_apellido_nombres(docente: Any) -> tuple[str, str]:
    txt = limpiar_texto_tabla(docente)
    if not txt:
        return "", ""
    if "," in txt:
        partes = txt.split(",", 1)
        return partes[0].strip(), partes[1].strip()
    partes = txt.split()
    if len(partes) <= 1:
        return txt, ""
    # Criterio practico certificado: si no viene separado, la ultima palabra es el apellido.
    return partes[-1].strip(), " ".join(partes[:-1]).strip()


def normalizar_clave(valor: Any) -> str:
    if valor is None or _is_na(valor):
        return ""
    return " ".join(str(valor).strip().upper().split())


def safe_index(options: list, value: Any, default: int = 0) -> int:
    try:
        return options.index(value)
    except Exception:
        return default


def safe_date(value: Any, fallback: Any = None) -> Any:
    """``extracted_batch04/fechas.py::safe_date`` (``pd.to_datetime(value).date()``)."""
    import pandas as pd

    try:
        if value is None or value == "" or pd.isna(value):
            return fallback
        return pd.to_datetime(value).date()
    except Exception:
        return fallback


def departamento_origen_desde_obs_prestado(obs: Any) -> str:
    """``extracted_batch01/docentes.py::_departamento_origen_desde_obs_prestado``."""
    txt = str(obs or "").strip()
    txt = txt.replace("Docente prestado desde ", "")
    txt = txt.replace(". No posee designación local en este departamento.", "")
    return txt.strip(" .")


def filtrar_por_texto(filas: list[dict], texto: Any, columnas: Iterable[str]) -> list[dict]:
    """``filtrar_dataframe_por_texto``: subcadena literal sobre ``normalizar_clave`` (sin quitar tildes)."""
    q = normalizar_clave(texto or "")
    if not q or not filas:
        return list(filas)
    cols = [c for c in columnas if c in filas[0]]
    if not cols:
        return list(filas)
    out = []
    for fila in filas:
        texto_fila = ""
        for col in cols:
            valor = fila.get(col)
            texto_fila += " " + ("" if valor is None or _is_na(valor) else str(valor))
        if q in normalizar_clave(texto_fila):
            out.append(fila)
    return out


# --- B12A: nivel de posgrado salarial ---------------------------------------------------------------------
_SYNONYMS = {
    "Doctor": ("doctor", "doctora", "doctorado"),
    "Magíster": ("magister", "maestria", "master"),
    "Especialista": ("especialista", "especializacion"),
}
CANONICAL_LEVELS = tuple(sorted(_SYNONYMS))


class PosgradoNivelInvalido(ValueError):
    """Valor no vacio de nivel de posgrado fuera del dominio: la escritura se rechaza sin efectos."""


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", str(text))
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(stripped.casefold().split())


_LOOKUP = {}
for _level, _synonyms in _SYNONYMS.items():
    for _key in {_fold(_level)} | {_fold(s) for s in _synonyms}:
        _LOOKUP[_key] = _level


def canonical_posgrado_level(value: Any) -> Optional[str]:
    """``''`` = ausencia; nivel canonico = reconocido; ``None`` = no vacio no reconocido."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    if not isinstance(value, (str, bytes)) and _is_na(value):
        return ""
    key = _fold(value)
    if not key:
        return ""
    return _LOOKUP.get(key)


def nivel_posgrado_salarial_normalizado(value: Any) -> str:
    """Lectura (``_nivel_posgrado_salarial_normalizado_v256`` re-enlazado por B12A): no reconocido -> ``''``."""
    return canonical_posgrado_level(value) or ""


def require_posgrado_level_for_write(value: Any) -> str:
    level = canonical_posgrado_level(value)
    if level is None:
        raise PosgradoNivelInvalido(
            f"Nivel de posgrado salarial no reconocido: {str(value).strip()!r}. "
            f"Usá {', '.join(CANONICAL_LEVELS)} o dejalo vacío. No se modificó ningún dato."
        )
    return level


# --- v168: firma de fila y vacio ---------------------------------------------------------------------------
def es_vacio_v168(valor: Any) -> bool:
    if valor is None:
        return True
    try:
        if _is_na(valor):
            return True
    except Exception:
        pass
    return str(valor).strip() == ""


def firma_fila_v168(row: dict, columnas_clave: Iterable[str]) -> tuple:
    firma = []
    for col in columnas_clave:
        if col not in row:
            continue
        valor = row.get(col)
        if isinstance(valor, float):
            valor = round(valor, 8)
        if isinstance(valor, str):
            valor = valor.strip()
        firma.append((col, valor))
    return tuple(firma)
