"""Gate de backup previo de "Crear período" (B11, D-E4-04).

Certificado (B13-FIX02 l. 59117-59130, ``deptit_refactor/operations/backup_gate.py``): ``crear_periodo`` exige un backup
reciente y VERIFICADO de esa misma base (manifest de ``tools/b11_backup_postgresql.py``: esquema, validacion PASS,
identidad, antiguedad <= ``DEPTIT_CRITICAL_BACKUP_MAX_AGE_HOURS``, dump presente, tamaño y SHA-256).  Si no -> DENY,
0 SQL.  La evaluacion es la copia LITERAL de ese modulo (``ref_b11/``): NEXT no fabrica evidencia de backup.

Contrato de configuracion NEXT (D-E4-04), leido del entorno del proceso (nunca de la base ni del cliente):
- ``DEPTIT_ENTORNO``: ``desarrollo`` o ``produccion``.  Ausente o cualquier otro valor = ``produccion`` (fail closed).
- ``DEPTIT_BACKUP_GATE_CREAR_PERIODO``: ``activo`` (default) o ``desactivado``.
  ``desactivado`` solo se acepta con ``DEPTIT_ENTORNO=desarrollo``: el arranque en produccion con el gate desactivado
  FALLA (``validar_arranque``).  En desarrollo, el gate desactivado se informa en la pantalla de Crear periodo.
- Con el gate activo: ``DEPTIT_BACKUP_DIR`` / ``DEPTIT_CRITICAL_BACKUP_MAX_AGE_HOURS`` como el certificado.
El backup productivo real (herramienta, programacion, restore) es Etapa 6.

6A-B2 (``operacion/backup_db.py``): la evidencia la produce la herramienta B11 literal; ``database_url`` es la URL de
IDENTIDAD de la base de la app (sin credenciales: el gate compara host+puerto+nombre).  Despues de la decision B11,
NEXT exige ademas que el backup aceptado sea del MISMO entorno (``deptit.entorno`` del manifest): otro entorno, o un
manifest sin entorno, -> ``DENY_OTHER_ENVIRONMENT`` (fail-closed; cada entorno usa su propio ``DEPTIT_BACKUP_DIR``).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Optional

from .ref_b11 import backup_gate as B11
from .ref_b11.backup_manifest import load_manifest

ENTORNO_ENV = "DEPTIT_ENTORNO"
GATE_ENV = "DEPTIT_BACKUP_GATE_CREAR_PERIODO"
DESARROLLO, PRODUCCION = "desarrollo", "produccion"
ACTIVO, DESACTIVADO = "activo", "desactivado"
DECISION_DESACTIVADO = "ALLOW_GATE_DISABLED_DEV"
AVISO_DESACTIVADO = (f"Desarrollo: el control de backup previo de Crear período está DESACTIVADO por configuración "
                     f"explícita ({GATE_ENV}={DESACTIVADO}, {ENTORNO_ENV}={DESARROLLO}). En producción es obligatorio "
                     "y el sistema no arranca con el control desactivado.")
# Texto certificado (``mensaje_precondicion_backup``) con la herramienta B11 que corresponde a NEXT (Etapa 6).
COMANDO_NEXT = "el procedimiento de backup verificado de la instalación"
DENY_OTHER_ENVIRONMENT = "DENY_OTHER_ENVIRONMENT"
MOTIVO_OTRO_ENTORNO = "el backup es de otro entorno"


class GateConfigError(RuntimeError):
    """Configuracion insegura del gate: el proceso no debe arrancar."""


@dataclass(frozen=True)
class Configuracion:
    entorno: str
    activo: bool


@dataclass(frozen=True)
class Decision:
    permitido: bool
    codigo: str
    mensaje: str


def configuracion(env: Optional[Mapping[str, str]] = None) -> Configuracion:
    env = os.environ if env is None else env
    entorno = DESARROLLO if str(env.get(ENTORNO_ENV, "")).strip().lower() == DESARROLLO else PRODUCCION
    valor = str(env.get(GATE_ENV, ACTIVO) or ACTIVO).strip().lower()
    if valor not in (ACTIVO, DESACTIVADO):
        raise GateConfigError(f"{GATE_ENV}={valor!r}: valores admitidos {ACTIVO!r} o {DESACTIVADO!r}.")
    if valor == DESACTIVADO and entorno != DESARROLLO:
        raise GateConfigError(f"{GATE_ENV}={DESACTIVADO} solo se admite con {ENTORNO_ENV}={DESARROLLO}: en producción "
                              "el backup previo de Crear período es obligatorio.")
    return Configuracion(entorno, valor == ACTIVO)


def validar_arranque(env: Optional[Mapping[str, str]] = None) -> Configuracion:
    """Llamado al arrancar ``main.py``: una configuracion insegura impide levantar el servicio."""
    return configuracion(env)


def mensaje_denegacion(decision: "B11.GateDecision") -> str:
    texto = B11.mensaje_precondicion_backup(decision)
    return texto.replace(f"`{B11.BACKUP_COMMAND_HINT}`", COMANDO_NEXT).replace(
        " (ver docs/B11_OPERATIONAL_READINESS.md)", "")


def evaluar(database_url: str, *, env: Optional[Mapping[str, str]] = None,
            evidencia: Optional[Callable[[], "B11.GateDecision"]] = None) -> Decision:
    """Decision del gate para UNA operacion (antes de abrir la transaccion: 0 SQL si deniega)."""
    cfg = configuracion(env)
    if not cfg.activo:
        return Decision(True, DECISION_DESACTIVADO, AVISO_DESACTIVADO)
    fuente = env if env is not None else os.environ
    try:
        if evidencia is not None:
            decision = evidencia()
        else:
            decision = B11.require_recent_backup(lambda k, d=None: fuente.get(k, d), database_url=database_url,
                                                 use_postgresql=True)
    except Exception as exc:  # el certificado: cualquier error de evidencia = DENY
        decision = B11._deny("DENY_EVIDENCE_ERROR", f"{B11.DENY_CODES['DENY_EVIDENCE_ERROR']} ({type(exc).__name__})")
    if decision.allowed and evidencia is None:
        decision = _mismo_entorno(decision, fuente)
    if decision.allowed:
        return Decision(True, decision.code, decision.detail)
    return Decision(False, decision.code, mensaje_denegacion(decision))


def _mismo_entorno(decision: "B11.GateDecision", fuente: Mapping[str, str]) -> "B11.GateDecision":
    """El manifest aceptado por B11 debe declarar el entorno del proceso.  Cualquier duda -> DENY."""
    try:
        nombre = str(decision.evidence.get("manifest") or "")
        directorio = Path(str(fuente.get(B11.BACKUP_DIR_ENV, "") or "").strip()).resolve()
        if not nombre or Path(nombre).name != nombre:
            raise ValueError("manifest sin nombre")
        doc = load_manifest(directorio / nombre)
        entorno = doc.get("deptit", {}).get("entorno")
        if entorno and entorno == str(fuente.get(ENTORNO_ENV, "") or "").strip():
            return decision
    except Exception as exc:
        return B11._deny("DENY_EVIDENCE_ERROR", f"{B11.DENY_CODES['DENY_EVIDENCE_ERROR']} ({type(exc).__name__})")
    return B11._deny(DENY_OTHER_ENVIRONMENT, MOTIVO_OTRO_ENTORNO)


__all__ = ["Configuracion", "Decision", "GateConfigError", "configuracion", "evaluar", "validar_arranque",
           "AVISO_DESACTIVADO"]
