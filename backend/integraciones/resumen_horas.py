"""Resumen docente — situación institucional y evolución de horas del período (capa NEXT nativa).

Corrige dos defectos del motor certificado (``analisis/motor/certificado.py`` + ``ref/``, texto literal que no se
edita):

* **Bug A (resumen histórico institucional).**  En un período cerrado el motor deduplica las designaciones con la clave
  ``(cargo, dedicación, tipo, horas)`` (``_clave_designacion_desde_row_designacion``), que NO incluye el departamento:
  dos designaciones idénticas en departamentos distintos se fusionaban, el docente dejaba de verse como compartido y
  las horas institucionales quedaban subcontadas.  Acá la fuente es la MISMA que la tabla "Designaciones
  institucionales del docente" (``_get_designaciones_periodo_institucional_v149``: todas las designaciones del CUIL en
  el período equivalente, en todos los departamentos) y cada fila se identifica por su ``id``; la agrupación es por
  departamento.  En un período cerrado la foto se reconstruye por FECHAS (la ``Finalizada`` del cierre técnico no es
  una baja), en uno abierto por el estado actual (``Activa``), igual que la pestaña Designaciones.

* **Bug B (evolución de horas).**  El motor obtenía la base restando hacia atrás (``final − Aumento/Disminución``) e
  ignoraba altas y bajas, por lo que una baja de 40 hs se veía 0 → 0 → 0.  Regla implementada::

      horas_base + variación_neta = horas_finales

  - ``horas_finales``: designaciones docentes vigentes al cierre del período (abierto: activas hoy).
  - ``horas_base``: designaciones docentes vigentes al inicio del período, con las horas que tenían ENTONCES.  Los
    cambios de dedicación se guardan editando la fila (``update_base``) y dejando un movimiento con la variación
    (``horas_variacion`` / "Antes … / Ahora …"), así que las horas iniciales de esas filas se obtienen descontando
    esos movimientos, por departamento.
  - ``variación_neta = horas_finales − horas_base``: incluye altas (+h), bajas (−h), aumentos y disminuciones.

  Las altas y bajas salen de las FILAS (sus fechas reales), no de los movimientos, para no contarlas dos veces.

Exclusiones (las mismas del motor para la tarjeta): designaciones con función no docente (tienen su propia sección) y
suspendidas (licencia: no suman horas; se listan como "Suspendida (licenciada)").

Funciones puras sobre ``DataFrame`` (testeables sin base); ``situacion_desde_motor`` es el único punto que lee el
namespace del motor, y solo usa lecturas institucionales ya existentes.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Callable, Optional

import pandas as pd

from analisis.motor.ref.extracted_batch04.designaciones import _es_funcion_no_docente_v162
from designaciones.rules import calcular_variacion_horas_movimiento, limpiar_texto_tabla, normalizar_clave

EPS = 1e-9

# Movimientos que cambian las horas de una designación EXISTENTE editando su fila (designaciones/service.py,
# ``modificar``: ``variacion = despues - antes`` para estos tipos).  Altas y bajas NO van acá: salen de las filas.
TIPOS_CAMBIO_EN_FILA = frozenset({
    "Aumento de dedicación", "Disminución de dedicación", "Cambio de cargo", "Modificación general",
    "Cambio de función docente / no docente",
})

SUSPENDIDA_TXT = "Suspendida (licenciada)"


# ------------------------------------------------------------------------------------------ utilidades
def _fecha(valor: Any) -> Optional[date]:
    """Misma lectura de fechas que el motor (``_fecha_a_timestamp_seguro``: ``pd.to_datetime``, dayfirst=False)."""
    try:
        if valor is None or (not isinstance(valor, str) and pd.isna(valor)):
            return None
        txt = str(valor).strip()
        if not txt:
            return None
        ts = pd.to_datetime(txt, errors="coerce", dayfirst=False)
        return None if pd.isna(ts) else ts.date()
    except Exception:
        return None


def _horas(valor: Any) -> float:
    try:
        n = float(pd.to_numeric(valor, errors="coerce"))
    except Exception:
        return 0.0
    return 0.0 if pd.isna(n) else n


def _txt(valor: Any) -> str:
    return limpiar_texto_tabla(valor)


def _hs(valor: float) -> str:
    """``10`` -> ``"10"``, ``7.5`` -> ``"7.5"`` (mismo formato ``:g`` que el motor)."""
    return f"{int(valor) if float(valor).is_integer() else valor:g}"


def _es_no_docente(valor: Any) -> bool:
    """Misma regla que el motor y la tabla institucional (``_es_funcion_no_docente_v162``)."""
    return bool(_es_funcion_no_docente_v162(valor))


def fin_real(fila: dict) -> Optional[date]:
    """Fin de vigencia real: baja efectiva > fecha prevista > fecha hasta (``_fecha_fin_real_designacion_v269``).

    La finalización técnica del cierre de período (``estado='Finalizada'`` sin ``fecha_finalizacion_efectiva``) NO es
    un fin: la fila conserva su ``fecha_hasta`` real."""
    for campo in ("fecha_finalizacion_efectiva", "fecha_hasta_prevista", "fecha_hasta"):
        f = _fecha(fila.get(campo))
        if f is not None:
            return f
    return None


def vigente_en(fila: dict, dia: Optional[date]) -> bool:
    if dia is None:
        return True
    desde = _fecha(fila.get("fecha_desde"))
    fin = fin_real(fila)
    return (desde is None or desde <= dia) and (fin is None or fin >= dia)


def vigente_durante(fila: dict, inicio: Optional[date], fin_periodo: Optional[date]) -> bool:
    desde = _fecha(fila.get("fecha_desde"))
    fin = fin_real(fila)
    if fin_periodo is not None and desde is not None and desde > fin_periodo:
        return False
    if inicio is not None and fin is not None and fin < inicio:
        return False
    return True


# ------------------------------------------------------------------------------------------ fuente
def preparar_designaciones(df: Optional[pd.DataFrame], dep_actual_id: Optional[int] = None,
                           dep_actual_nombre: str = "") -> list[dict]:
    """Filas institucionales del período, una por designación (``id``), sin sombras administrativas.

    Sombra (regla v227 del motor): fila de OTRO ``departamento_id`` cuyo nombre visible es el del departamento actual;
    no pertenece al tenant y no se mezcla.  NO se deduplica por (cargo, dedicación, tipo, horas): dos designaciones
    iguales en departamentos distintos son dos designaciones."""
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return []
    nombre_actual = normalizar_clave(dep_actual_nombre) if dep_actual_nombre else ""
    filas, vistos = [], set()
    for _, r in df.iterrows():
        fila = r.to_dict()
        did = fila.get("id")
        clave_id = None
        if did is not None and not (isinstance(did, float) and pd.isna(did)):
            clave_id = str(did)
            if clave_id in vistos:
                continue
            vistos.add(clave_id)
        dep_id = pd.to_numeric(fila.get("departamento_id"), errors="coerce")
        dep_id = None if pd.isna(dep_id) else int(dep_id)
        dep_nombre = _txt(fila.get("departamento")) or "Sin departamento"
        if (dep_actual_id is not None and dep_id is not None and dep_id != int(dep_actual_id) and nombre_actual
                and normalizar_clave(dep_nombre) == nombre_actual):
            continue
        estado = normalizar_clave(fila.get("estado"))
        filas.append({
            **fila,
            "_dep_id": dep_id,
            "_dep_key": f"id:{dep_id}" if dep_id is not None else f"nombre:{normalizar_clave(dep_nombre)}",
            "_dep": dep_nombre,
            "_hs": _horas(fila.get("horas")),
            "_estado": estado,
            "_suspendida": estado == "SUSPENDIDA",
            "_no_docente": _es_no_docente(fila.get("funcion_no_docente")),
        })
    return filas


def _computables(filas: list[dict]) -> list[dict]:
    """Designaciones que suman horas docentes: docencia, no suspendidas, con horas."""
    return [f for f in filas if not f["_no_docente"] and not f["_suspendida"] and f["_hs"] > EPS]


def foto_inicio(filas: list[dict], inicio: Optional[date]) -> list[dict]:
    return [f for f in _computables(filas) if vigente_en(f, inicio)]


def foto_final(filas: list[dict], inicio: Optional[date], fin_periodo: Optional[date], abierto: bool) -> list[dict]:
    """Abierto: estado actual (``Activa``), como la pestaña Designaciones.  Cerrado: vigentes al último día del
    período por fechas reales (el ``Finalizada`` del cierre técnico no cuenta como baja)."""
    comp = _computables(filas)
    if abierto:
        return [f for f in comp if f["_estado"] == "ACTIVA" and vigente_durante(f, inicio, fin_periodo)]
    return [f for f in comp if vigente_en(f, fin_periodo)]


# ------------------------------------------------------------------------------------------ movimientos
def cambios_en_fila_por_departamento(df_mov: Optional[pd.DataFrame], deps: dict[Optional[int], str]) -> dict:
    """Variación neta de los cambios hechos EDITANDO filas existentes, por ``departamento_id``.

    ``deps``: ``departamento_id -> _dep_key`` de las designaciones válidas.  Un movimiento sin departamento se
    atribuye al único departamento si hay uno solo; si no, queda en la clave ``None`` (ajuste global)."""
    out: dict = {}
    if df_mov is None or not isinstance(df_mov, pd.DataFrame) or df_mov.empty:
        return out
    claves = {k for k in deps.values()}
    unica = next(iter(claves)) if len(claves) == 1 else None
    for _, r in df_mov.iterrows():
        tipo = str(r.get("tipo_movimiento") or "").strip()
        if tipo not in TIPOS_CAMBIO_EN_FILA:
            continue
        delta = float(calcular_variacion_horas_movimiento(tipo, r.get("detalle", ""), r.get("horas_variacion", 0))
                      or 0)
        if abs(delta) < EPS:
            continue
        dep_id = pd.to_numeric(r.get("departamento_id"), errors="coerce")
        dep_id = None if pd.isna(dep_id) else int(dep_id)
        if dep_id is not None:
            if dep_id not in deps:
                continue  # departamento ajeno a la fuente validada (p. ej. sombra)
            clave = deps[dep_id]
        else:
            clave = unica
        out[clave] = out.get(clave, 0.0) + delta
    return out


# ------------------------------------------------------------------------------------------ balance
def balance(horas_inicio_filas: dict, horas_finales: dict, cambios: dict) -> dict:
    """``horas_base + variación_neta = horas_finales``.

    ``horas_inicio_filas``: horas ACTUALES de las filas vigentes al inicio, por departamento.  Se les descuenta la
    variación de los cambios en fila del período para recuperar las horas que tenían al inicio (nunca < 0: un cambio
    sobre una designación dada de alta en el mismo período no puede hacer negativa la base)."""
    base = 0.0
    for clave in set(horas_inicio_filas) | {k for k in cambios if k is not None}:
        base += max(float(horas_inicio_filas.get(clave, 0.0)) - float(cambios.get(clave, 0.0)), 0.0)
    base = max(base - float(cambios.get(None, 0.0)), 0.0)
    final = float(sum(horas_finales.values()))
    base, final = round(base, 2), round(final, 2)
    neta = round(final - base, 2)
    if abs(neta) < EPS:
        neta = 0.0
    return {"horas_base": base, "variacion_neta": neta, "horas_finales": final}


def _texto_cargo(f: dict) -> str:
    cargo = _txt(f.get("cargo")) or "Sin cargo"
    tipo = _txt(f.get("tipo_designacion"))
    dedic = _txt(f.get("dedicacion"))
    txt = cargo + (f" ({tipo})" if tipo else "") + (f" · {dedic}" if dedic else "")
    return txt + f" · {_hs(f['_hs'])} hs"


def _por_departamento(filas: list[dict]) -> dict:
    out: dict = {}
    for f in filas:
        out[f["_dep_key"]] = out.get(f["_dep_key"], 0.0) + f["_hs"]
    return out


# ------------------------------------------------------------------------------------------ cálculo completo
def calcular(df_designaciones: Optional[pd.DataFrame], df_movimientos: Optional[pd.DataFrame], periodo: dict, *,
             dep_actual_id: Optional[int] = None, dep_actual_nombre: str = "") -> dict:
    """Situación institucional del docente en el período y evolución de horas.

    ``periodo``: fila de ``periodos`` (``fecha_inicio``, ``fecha_fin``, ``estado``)."""
    inicio = _fecha(periodo.get("fecha_inicio"))
    fin_periodo = _fecha(periodo.get("fecha_fin"))
    abierto = str(periodo.get("estado") or "").strip().casefold() != "cerrado"

    filas = preparar_designaciones(df_designaciones, dep_actual_id, dep_actual_nombre)
    del_periodo = [f for f in filas if vigente_durante(f, inicio, fin_periodo)]
    ini = foto_inicio(del_periodo, inicio)
    fin = foto_final(del_periodo, inicio, fin_periodo, abierto)

    deps = {f["_dep_id"]: f["_dep_key"] for f in del_periodo if f["_dep_id"] is not None}
    cambios = cambios_en_fila_por_departamento(df_movimientos, deps)
    bal = balance(_por_departamento(ini), _por_departamento(fin), cambios)

    # Departamentos del período: los que tuvieron designaciones docentes computables en algún momento del período.
    computables_periodo = _computables(del_periodo)
    orden: list[str] = []
    nombres: dict[str, str] = {}
    for f in sorted(computables_periodo, key=lambda x: normalizar_clave(x["_dep"])):
        if f["_dep_key"] not in nombres:
            orden.append(f["_dep_key"])
            nombres[f["_dep_key"]] = f["_dep"]
    departamentos = []
    for clave in orden:
        filas_dep = [f for f in fin if f["_dep_key"] == clave]
        textos = list(dict.fromkeys(_texto_cargo(f) for f in filas_dep))
        departamentos.append({
            "departamento": nombres[clave],
            "cargo/s en el período": " / ".join(textos) if textos else "Baja en el período",
            "horas": round(sum(f["_hs"] for f in filas_dep), 2),
        })
    compartido = len(departamentos) > 1

    if compartido:
        cargos = [f"{d['departamento']}: {d['cargo/s en el período']}" for d in departamentos
                  if d["horas"] > EPS]
    else:
        cargos = list(dict.fromkeys(f"{f['_dep']}: {_texto_cargo(f)}" for f in fin))

    suspendidas = []
    for f in del_periodo:
        if f["_suspendida"] and not f["_no_docente"]:
            partes = [x for x in [_txt(f.get("cargo")), f"({_txt(f.get('tipo_designacion'))})"
                                  if _txt(f.get("tipo_designacion")) else "", _txt(f.get("dedicacion")),
                                  SUSPENDIDA_TXT] if x]
            txt = f"{f['_dep']}: " + " · ".join(partes)
            if txt not in suspendidas:
                suspendidas.append(txt)

    return {
        **bal,
        "departamentos": departamentos,
        "compartido": compartido,
        "cargos": cargos,
        "suspendidas": suspendidas,
        "baja_en_periodo": bal["horas_finales"] <= EPS and bal["horas_base"] > EPS,
        "lectura_historica": not abierto,
    }


# ------------------------------------------------------------------------------------------ namespace del motor
def situacion_desde_motor(ns: dict, cuil: str, periodo_id: int, fila_periodo: Optional[dict],
                          resumen_motor: dict) -> Optional[dict]:
    """Calcula la situación con las lecturas institucionales del motor; ``None`` = conservar la del motor.

    Se conserva la del motor cuando: no hay PostgreSQL (lectura local legada), falta la fila del período, o el motor
    aplicó la regla v227 "docente propio sin designación física local en el período" (la tarjeta queda vacía a
    propósito: una fila institucional de otro departamento no se hereda)."""
    if not ns.get("USE_POSTGRESQL") or not fila_periodo:
        return None
    if bool(resumen_motor.get("sin_designacion_local_periodo_v227")):
        return None
    lector: Callable = ns["_get_designaciones_periodo_institucional_v149"]
    df = lector(cuil, periodo_id)
    df_mov = ns["_get_movimientos_periodo_institucional_v149"](cuil, periodo_id)
    try:
        dep_actual_id = ns["_pg_current_dep_id"]()
        dep_actual_id = int(dep_actual_id) if dep_actual_id is not None else None
    except Exception:
        dep_actual_id = None
    try:
        dep_actual_nombre = ns["_nombre_departamento_actual_v227"]() or ""
    except Exception:
        dep_actual_nombre = ""
    return calcular(df, df_mov, fila_periodo, dep_actual_id=dep_actual_id, dep_actual_nombre=dep_actual_nombre)
