"""E4-04 — Costos salariales de "📚 Proyectos vigentes" en Investigación y Extensión.

Certificado (B13-FIX02): ``render_proyectos_vigentes_v101`` (entry l. 33122; la usan las dos paginas, l. 65015 y
l. 65804) arma ``act_v162`` (asignaciones del periodo abierto: por nombre de periodo; en historico, foto al cierre
v183; si no, solo Activas) y llama a ``calcular_costos_asignaciones_proyecto_v257`` (l. 25759 + v258).  Muestra:
- columna "Costo total sueldos" de la tabla y del listado completo: ``_moneda_v256(round(costo_por_proyecto, 2))``
  (l. 33233-33236);
- metrica "Costo total en sueldos" de la ficha: ``_moneda_v256`` de la suma del detalle del proyecto (l. 33459) y la
  leyenda de calculo (l. 33463-33467);
- por integrante: cargo · dedicacion · condicion salarial y "Costo total imputado" (l. 33533-33553).

Permiso (P-04, resuelto por diferencial): el certificado no autoriza lecturas con B10; los costos se ven con la pagina
del modulo.  NEXT exige la lectura del propio modulo (``InvestigacionService.reader`` / ``ExtensionService.reader``),
no ``sueldos.read``.

Composicion (D-E4-01): el motor es de Sueldos (``SueldosService.costos_proyectos_vigentes``, validado al centavo) y
Sueldos ya importa Investigacion/Extension, asi que el cruce vive aqui.  Los proyectos y sus fechas salen de la lectura
publica de cada modulo (``vigentes``).  Solo lectura (las lecturas del motor y de los modulos son READ ONLY).

D-E4-02: el resultado se presenta como ESTIMACION con una advertencia discreta; no se corrige ninguna anomalia del
motor certificado.
"""
from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from auth.service import SessionRecord
from extension.service import ExtensionError, ExtensionService
from investigacion.rules import valor_proyecto_v101
from investigacion.service import InvestigacionError, InvestigacionService
from sueldos import rules as SR
from sueldos.service import Scope as SueldosScope
from sueldos.service import SueldosError, SueldosService

log = logging.getLogger("deptit_next.integraciones")

ETIQUETA_ESTIMACION = "ESTIMACIÓN"
ADVERTENCIA_ESTIMACION = ("Los costos son una estimación: usan la lógica salarial certificada y pueden no contemplar "
                          "todos los conceptos.")
LEYENDA_HORAS = ("Las horas totales se calculan como horas semanales × semanas comprendidas entre "
                 "la fecha de inicio y la fecha de finalización del proyecto. ")
LEYENDA_SIN_ESCALA = "No hay una escala salarial aplicable para calcular el costo total."
LEYENDA_AD_HONOREM = " Las designaciones Ad Honorem imputan $0."


class CostosError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def leyenda_costo(mes_escala, meses: Any) -> str:
    """Leyenda de la ficha (l. 33463-33467)."""
    if mes_escala:
        costo = (f"El costo total salarial usa como base la escala {SR.etiqueta_mes_v256(mes_escala)}, prorratea el "
                 "sueldo según horas asignadas / horas contractuales rentadas y proyecta ese importe por los "
                 f"{meses} meses de ejecución del proyecto.")
    else:
        costo = LEYENDA_SIN_ESCALA
    return LEYENDA_HORAS + costo + LEYENDA_AD_HONOREM


def detalle_salarial(fila: pd.Series) -> str:
    """Caption del integrante (l. 33535-33538): cargo · dedicacion · condicion."""
    cargo = valor_proyecto_v101(fila.get("cargo_salarial_v257"), "Sin designación")
    ded = valor_proyecto_v101(fila.get("dedicacion_salarial_v257"), "")
    cond = valor_proyecto_v101(fila.get("condicion_salarial_v257"), "")
    return f"{cargo}" + (f" · {ded}" if ded else "") + (f" · {cond}" if cond else "")


class CostosProyectosService:
    def __init__(self, sueldos: SueldosService, investigacion: InvestigacionService, extension: ExtensionService):
        self.sueldos = sueldos
        self.modulos = {"investigacion": investigacion, "extension": extension}

    def costos(self, record: SessionRecord, tipo: str) -> dict:
        svc = self.modulos[tipo]
        try:
            scope = svc.reader(record)  # P-04: lectura del modulo (y su ambito departamental)
            filas = svc.vigentes(record)["filas"]
        except (InvestigacionError, ExtensionError) as exc:
            raise CostosError(exc.status, exc.code, exc.message) from None
        try:
            r = self.sueldos.costos_proyectos_vigentes(
                SueldosScope(scope.institution_id, scope.department_id, scope.institution, scope.department,
                             scope.rol), tipo)
        except SueldosError as exc:
            raise CostosError(exc.status, exc.code, exc.message) from None
        mes = r["mes_escala"]
        por_proyecto = r["por_proyecto"]
        detalle = r["detalle"] if isinstance(r["detalle"], pd.DataFrame) else pd.DataFrame()
        proyectos = []
        for f in filas:
            pid = int(f["id"])
            del_proyecto = detalle[pd.to_numeric(detalle["proyecto_id"], errors="coerce").eq(float(pid))] \
                if not detalle.empty and "proyecto_id" in detalle.columns else pd.DataFrame()
            total_ficha = float(pd.to_numeric(del_proyecto.get("costo_total_proyecto_v258"), errors="coerce")
                                .fillna(0).sum()) if not del_proyecto.empty else 0.0
            proyectos.append({
                "proyecto_id": pid,
                "costo_tabla": SR.moneda_v256(round(float(por_proyecto.get(float(pid), 0.0) or 0), 2)),
                "costo_ficha": SR.moneda_v256(total_ficha),
                "leyenda": leyenda_costo(mes, f.get("meses_ejecucion_v258")),
            })
        integrantes = []
        if not detalle.empty and "id" in detalle.columns:
            for _, d in detalle.iterrows():
                integrantes.append({
                    "asignacion_id": int(d["id"]),
                    "proyecto_id": int(pd.to_numeric(d.get("proyecto_id"), errors="coerce")),
                    "detalle_salarial": detalle_salarial(d),
                    "costo": SR.moneda_v256(float(d.get("costo_total_proyecto_v258") or 0)),
                })
        return {
            "estimacion": {"etiqueta": ETIQUETA_ESTIMACION, "advertencia": ADVERTENCIA_ESTIMACION},
            "proyectos": proyectos,
            "integrantes": integrantes,
            "sin_costo": SR.moneda_v256(0.0),
        }


__all__ = ["CostosProyectosService", "CostosError", "leyenda_costo", "detalle_salarial"]
