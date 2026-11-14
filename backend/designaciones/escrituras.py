"""Writers certificados de Designaciones con sus COMMITs reales (cadenas efectivas de B13-FIX02).

Cada funcion recibe la ``Unidad`` de la operacion B12H en curso.  Igual que el certificado, cada ``get_conn()`` /
``_pg_raw_conn()`` con escritura es un COMMIT propio: ``Unidad.commit`` abre una transaccion, ejecuta el cuerpo y, si
hubo sentencias mutantes, inserta su SUCCESS en esa misma transaccion (``commit_seq`` = numero de COMMIT de la
operacion, ``committing_writer`` = writer de negocio mas interno, ``nested_system_task`` = tarea de sistema en curso).
Un error confirma lo anterior y revierte solo el COMMIT en curso (no se convierte nada en atomico).

Cadenas (entry):
- ``guardar_designacion``: v162 l. 34484 -> v95 l. 32501 -> base l. 8492 (+ ``sincronizar_cargos`` l. 29724).
- ``actualizar_designacion``: v233 l. 52730 -> v162 l. 34575 -> v95 l. 32546 -> base l. 8545.
- ``actualizar_designacion_por_error``: v233 l. 52768 -> v162 l. 34613 -> v95 l. 32812 -> base l. 9273.
- ``eliminar_designacion`` l. 9012; ``eliminar_designaciones_por_error_masivo`` l. 9108.
- ``finalizar_designacion_anticipadamente`` l. 32716 (+ ``_finalizar_comisiones_si_sin_designacion_docente_v214``).
- ``actualizar_resolucion_fechas_designacion_directo_v171`` l. 32854; ``sincronizar_movimiento_baja_designacion_v207``
  l. 32899; ``registrar_movimiento`` l. 4424; vinculos v266/v267 l. 54417-54905.
- Cargo prioritario: ``obtener_cargo_prioritario_docente_periodo`` v200 l. 46666 (mapa l. 46512).
"""

from __future__ import annotations

import re
from contextlib import contextmanager
from datetime import date, datetime
from typing import Any, Callable, Iterator, Optional

import pandas as pd

import audit

from . import rules
from .repository import DesignacionesRepository

SYS_SINCRONIZAR_CARGOS = "sincronizar_cargos_asignaciones_docente_periodo"
SYS_FINALIZAR_COMISIONES = "_finalizar_comisiones_si_sin_designacion_docente_v214"

W_GUARDAR = "guardar_designacion"
W_ACTUALIZAR = "actualizar_designacion"
W_POR_ERROR = "actualizar_designacion_por_error"
W_ELIMINAR = "eliminar_designacion"
W_ELIMINAR_MASIVO = "eliminar_designaciones_por_error_masivo"
W_FINALIZAR = "finalizar_designacion_anticipadamente"
W_FECHAS = "actualizar_resolucion_fechas_designacion_directo_v171"
W_LIMPIAR_V233 = "_limpiar_metadatos_finalizacion_si_reactivada_v233"
W_MOVIMIENTO = "registrar_movimiento"
W_BAJA_V207 = "sincronizar_movimiento_baja_designacion_v207"
W_VINCULAR_DES = "vincular_acto_designacion_v266"
W_VINCULAR_MOV = "vincular_acto_movimiento_v266"
W_VINCULAR_DES_MASIVO = "vincular_acto_designaciones_masivo_v267"
W_DESVINCULAR_DES_MASIVO = "desvincular_acto_designaciones_masivo_v267"
W_VINCULAR_MOV_MASIVO = "vincular_acto_movimientos_masivo_v267"
W_DESVINCULAR_MOV_MASIVO = "desvincular_acto_movimientos_masivo_v267"
W_ESTADO_CONSULTA = "guardar_estado_consulta_designacion"

MSG_ESA_YA_CARGADA = "Esa designación exactamente igual ya estaba cargada. No se creó otra fila."


class AuditoriaFallida(Exception):
    """El SUCCESS de un COMMIT no pudo insertarse: ese COMMIT se revirtio (B12H ``AUDIT_INSERT_FAILED``)."""


class _Rollback(Exception):
    """El cuerpo pide cerrar la conexion sin COMMIT (``conn.close()`` del certificado)."""

    def __init__(self, value: Any):
        super().__init__("rollback")
        self.value = value


ROLLBACK = object()


class Unidad:
    """Operacion B12H en curso (un writer externo de la UI) y sus COMMITs."""

    def __init__(self, transaction: Callable, op: audit.Operation, institution_id: int, department_id: int, *,
                 today: date, now: datetime, usuario: str = ""):
        self._transaction = transaction
        self.op = op
        self.inst, self.dep = int(institution_id), int(department_id)
        self.today, self.now, self.usuario = today, now, usuario
        self._stack: list[tuple[str, str]] = [("business", op.name)]  # pila B10 (enforcement._Frame)
        self.audit_failed = False
        self.avisos: list[str] = []

    @contextmanager
    def writer(self, name: str) -> Iterator[None]:
        """Marco ``business`` de la frontera B10 (writer anidado: misma operacion, sin eventos propios)."""
        self._stack.append(("business", name))
        try:
            yield
        finally:
            self._stack.pop()

    @contextmanager
    def system(self, name: str) -> Iterator[None]:
        """Marco ``system`` (reconciliacion permitida dentro de una operacion de negocio, B12F)."""
        self._stack.append(("system", name))
        try:
            yield
        finally:
            self._stack.pop()

    def read(self, fn: Callable[[DesignacionesRepository], Any]) -> Any:
        with self._transaction() as conn:
            return fn(DesignacionesRepository(conn, self.inst, self.dep))

    def commit(self, fn: Callable[[DesignacionesRepository], Any]) -> Any:
        if self.audit_failed:
            raise AuditoriaFallida("AUDIT_FAILED_EARLIER")
        repo = None
        try:
            with self._transaction() as conn:
                repo = DesignacionesRepository(conn, self.inst, self.dep)
                result = fn(repo)
                if result is ROLLBACK or isinstance(result, _Rollback):
                    raise result if isinstance(result, _Rollback) else _Rollback(None)
                if repo.mutating_statements:
                    meta = {"commit_seq": self.op.coupled_commits + 1,
                            "mutating_statements": repo.mutating_statements,
                            "committing_writer": next(n for k, n in reversed(self._stack) if k == "business"),
                            "nested_system_task": self._stack[-1][1] if self._stack[-1][0] == "system" else None}
                    try:
                        audit.insert_on(conn, self.op.event(audit.OUTCOME_SUCCESS, audit.MODE_IN_TRANSACTION,
                                                            metadata=meta))
                    except Exception as exc:
                        self.audit_failed = True
                        raise AuditoriaFallida(audit.error_code_of(exc)) from exc
        except _Rollback as rb:
            return rb.value
        if repo is not None and repo.mutating_statements:
            self.op.coupled_commits += 1
        return result


def _hoy(u: Unidad) -> date:
    return u.today


# ------------------------------------------------------------------------------------------ periodo y estado
def periodo_id_departamento_actual(u: Unidad, periodo_id: Any) -> int:
    """``_periodo_id_designacion_departamento_actual`` (l. 8434)."""
    try:
        periodo_id_int = int(periodo_id)
    except Exception:
        raise ValueError("El período indicado para la designación no es válido.") from None
    ref = u.read(lambda repo: repo.period_raw(periodo_id_int))
    if ref is None:
        raise ValueError("El período seleccionado ya no existe.")
    if int(ref.get("institucion_id") or 0) == u.inst and int(ref.get("departamento_id") or 0) == u.dep:
        return periodo_id_int
    nombre = str(ref.get("nombre") or "").strip()
    anio, semestre = int(ref.get("anio") or 0), int(ref.get("semestre") or 0)
    equiv = u.read(lambda repo: repo.period_equivalente(nombre, anio, semestre))
    if equiv is None:
        raise ValueError("El período seleccionado pertenece a otro departamento y no existe "
                         "un período académico equivalente en el departamento actual.")
    return int(equiv["id"])


def estado_v237(u: Unidad, periodo_id: Any, fecha_hasta: Any, estado: Any) -> Any:
    if rules.normalizar_clave(str(estado or "").strip()) != "ACTIVA":
        return estado
    fin = rules.safe_date(fecha_hasta, None)
    if fin is not None and fin < u.today:
        return "Finalizada"
    try:
        pid = int(periodo_id)
    except Exception:
        return estado
    periodo = u.read(lambda repo: repo.period_fin(pid))
    return rules.estado_segun_vigencia_v237(estado, fecha_hasta, periodo, u.today)


# ------------------------------------------------------------------------------------------ comisiones
def mapa_cargos_prioritarios(repo: DesignacionesRepository, periodo_id: int, dep_contexto: int,
                             solo_cuil: Optional[str] = None) -> dict:
    """``_mapa_cargos_prioritarios_v200`` (l. 46512): docentes, departamentos y designaciones equivalentes.

    ``solo_cuil`` (Etapa 5 / Tanda C, C3): calcula UNICAMENTE la entrada de ese CUIL.  Cada entrada depende solo de las
    filas de su CUIL (ficha y designaciones, en el mismo orden relativo) y del mapa de departamentos, asi que el
    resultado es identico a ``mapa_cargos_prioritarios(...)[clave]`` (test) sin recorrer toda la institucion: era el 93 %
    del tiempo de la carga integral (~0,9 s por fila)."""
    df_dep = pd.DataFrame(repo.departamentos_institucion())
    dep_por_nombre = {}
    if not df_dep.empty:
        for _, r in df_dep.iterrows():
            k = rules.normalizar_clave(r.get("nombre", ""))
            if k:
                dep_por_nombre[k] = int(r.get("id"))
    df_doc = pd.DataFrame(repo.docentes_tipo(dep_contexto))
    df_des = pd.DataFrame(repo.designaciones_equivalentes(periodo_id),
                          columns=["cuil", "cargo", "departamento_id", "departamento"])
    if solo_cuil is not None:
        clave = rules.clave_cuil(solo_cuil)
        if not df_doc.empty:
            df_doc = df_doc[df_doc["cuil"].map(rules.clave_cuil).eq(clave)]
        if not df_des.empty:
            df_des = df_des[df_des["cuil"].fillna("").astype(str).map(rules.clave_cuil).eq(clave)]
    tipos = {}
    if not df_doc.empty:
        for _, r in df_doc.iterrows():
            k = rules.clave_cuil(r.get("cuil"))
            if not k:
                continue
            tipos[k] = {"tipo": str(r.get("tipo_docente") or "Propio"), "obs": str(r.get("observaciones") or "")}
    grupos = {}
    if not df_des.empty:
        aux = df_des.copy()
        aux["_cuil_v200"] = aux["cuil"].fillna("").astype(str).map(rules.clave_cuil)
        for k, g in aux.groupby("_cuil_v200", sort=False):
            if k:
                grupos[str(k)] = g.copy()
    prioridad = {cargo: i for i, cargo in enumerate(rules.ORDEN_JERARQUICO_CARGOS_COMISION)}
    salida = {}
    for k in set(grupos) | set(tipos):
        meta = tipos.get(k, {"tipo": "Propio", "obs": ""})
        es_prestado = rules.normalizar_clave(meta.get("tipo", "")) == "PRESTADO"
        dep_esperado = int(dep_contexto)
        dep_origen_nombre = ""
        if es_prestado:
            dep_origen_nombre = rules.extraer_departamento_origen_prestado(meta.get("obs", ""))
            dep_esperado = dep_por_nombre.get(rules.normalizar_clave(dep_origen_nombre))
        g = grupos.get(k, pd.DataFrame())
        candidatos = pd.DataFrame()
        if isinstance(g, pd.DataFrame) and not g.empty:
            deps = pd.to_numeric(g["departamento_id"], errors="coerce").fillna(-1).astype(int)
            if es_prestado:
                if dep_esperado is not None:
                    candidatos = g[deps.eq(int(dep_esperado))].copy()
                    if candidatos.empty:
                        candidatos = g[~deps.eq(int(dep_contexto))].copy()
                else:
                    candidatos = g[~deps.eq(int(dep_contexto))].copy()
            else:
                candidatos = g[deps.eq(int(dep_contexto))].copy()
        if candidatos.empty:
            salida[k] = {"cargo": "", "departamento": dep_origen_nombre}
            continue
        candidatos = candidatos.copy()
        candidatos["cargo_canonico"] = candidatos["cargo"].map(rules.normalizar_cargo_para_jerarquia)
        candidatos["_prioridad"] = candidatos["cargo_canonico"].map(prioridad).fillna(999)
        candidatos = candidatos.sort_values(["_prioridad", "departamento", "cargo_canonico"], kind="stable")
        elegido = candidatos.iloc[0]
        cargo = str(elegido.get("cargo_canonico") or elegido.get("cargo") or "").strip()
        departamento = str(elegido.get("departamento") or dep_origen_nombre or "").strip()
        salida[k] = {"cargo": cargo, "departamento": departamento}
    return salida


def cargo_prioritario(u: Unidad, cuil: str, periodo_id: int, dep_contexto: int) -> dict:
    """``obtener_cargo_prioritario_docente_periodo`` v200.  Un CUIL ausente del mapa (sin ficha local ni
    designacion activa equivalente en la institucion) cae en el fallback historico, que en ese caso devuelve cargo
    vacio; se reproduce ese resultado (ver docs/DESIGNACIONES_BLOCK_CLOSE.md)."""
    if not cuil or not periodo_id:
        return {"cargo": ""}
    mapa = u.read(lambda repo: mapa_cargos_prioritarios(repo, int(periodo_id), int(dep_contexto), solo_cuil=cuil))
    return dict(mapa.get(rules.clave_cuil(cuil)) or {"cargo": ""})


def sincronizar_cargos(u: Unidad, cuil: Any, periodo_id: Any) -> int:
    """``sincronizar_cargos_asignaciones_docente_periodo`` (l. 29724): reconciliacion dentro de la operacion."""
    with u.system(SYS_SINCRONIZAR_CARGOS):
        cuil = rules.limpiar_cuil(cuil)
        if not cuil or periodo_id is None:
            return 0
        dato = cargo_prioritario(u, cuil, int(periodo_id), u.dep)
        cargo = rules.limpiar_texto_tabla(dato.get("cargo", ""))
        if not cargo:
            return 0
        return u.commit(lambda repo: repo.update_rol_asignaciones(cargo, cuil, int(periodo_id)))


def _sincronizar_silencioso(u: Unidad, cuil: Any, periodo_id: Any) -> None:
    """Las llamadas certificadas van en ``try/except Exception: pass``."""
    try:
        sincronizar_cargos(u, cuil, periodo_id)
    except Exception:
        pass


def finalizar_comisiones_sin_designacion(u: Unidad, cuil: Any, periodo_id: Any, fecha_efectiva: Any,
                                         designacion_finalizada_id: Any = None) -> int:
    """``_finalizar_comisiones_si_sin_designacion_docente_v214`` (l. 32557)."""
    with u.system(SYS_FINALIZAR_COMISIONES):
        cuil_txt = str(cuil or "").strip()
        try:
            pid = int(periodo_id)
        except Exception:
            return 0
        fe = rules.safe_date(fecha_efectiva, None)
        if not cuil_txt or fe is None:
            return 0
        nombre_docente = {"v": cuil_txt}

        def body(repo: DesignacionesRepository):
            df_des = repo.designaciones_activas_cuil(pid, cuil_txt)
            queda = False
            for d in df_des:
                did = d.get("id")
                did = int(did) if did is not None else None
                if designacion_finalizada_id is not None and did == int(designacion_finalizada_id):
                    continue
                if rules.es_funcion_no_docente(d.get("funcion_no_docente")):
                    continue
                fd = rules.safe_date(d.get("fecha_desde"), None)
                fh = rules.safe_date(d.get("fecha_hasta_limite"), None)
                fef = rules.safe_date(d.get("fecha_finalizacion_efectiva"), None)
                if fd is not None and fe < fd:
                    continue
                if fh is not None and fe > fh:
                    continue
                if fef is not None and fe >= fef:
                    continue
                queda = True
                break
            if queda:
                return _Rollback([])
            asignaciones = repo.asignaciones_activas(pid, cuil_txt)
            if not asignaciones:
                return _Rollback([])
            nr = repo.nombre_docente_cuil(cuil_txt)
            if nr is not None:
                from docentes.rules import nombre_completo
                nombre_docente["v"] = (nombre_completo(str(nr.get("apellido") or ""), str(nr.get("nombres") or ""))
                                       or str(nr.get("nombre") or "").strip() or cuil_txt)
            finalizadas = []
            for a in asignaciones:
                aid, cid = int(a.get("id")), int(a.get("comision_id"))
                obs_actual = rules.limpiar_texto_tabla(a.get("observaciones", ""))
                nota = (f"Baja automática de comisión por quedar sin designaciones docentes vigentes. "
                        f"Fecha efectiva: {fe.isoformat()}. Comisión ID {cid}.")
                obs_nueva = (obs_actual.rstrip(". ") + ". " if obs_actual else "") + nota
                if repo.finalizar_asignacion(obs_nueva, aid) > 0:
                    finalizadas.append({"id": aid, "comision_id": cid,
                                        "nombre_comision": rules.limpiar_texto_tabla(a.get("nombre_comision", "")),
                                        "rol": rules.limpiar_texto_tabla(a.get("rol", "")),
                                        "horas": float(rules.hora_numero(a.get("horas_asignadas", 0)) or 0)})
            if not finalizadas:
                return _Rollback([])
            return finalizadas

        asignaciones_a_finalizar = u.commit(body) or []
        for a in asignaciones_a_finalizar:
            cid = int(a["comision_id"])
            existente = u.read(lambda repo: repo.movimiento_baja_comision(pid, cuil_txt, fe.isoformat(), cid))
            if existente is not None:
                continue
            detalle_mov = (f"Baja docente por modificación de asignación: Comisión ID {cid} - {a['nombre_comision']}. "
                           f"Docente {nombre_docente['v']} [{cuil_txt}], rol {a['rol']}, {a['horas']:g} hs. "
                           f"Fecha efectiva: {fe.isoformat()}. Baja automática por finalización de su última "
                           "designación docente vigente.")
            registrar_movimiento(
                u, "Baja docente por modificación de asignación", cuil_txt, nombre_docente["v"], detalle_mov,
                f"Baja automática de comisión por quedar sin designaciones docentes vigentes. Fecha efectiva: "
                f"{fe.isoformat()}. Comisión ID {cid}.", pid, horas_variacion=0, fecha_movimiento=fe)
        return len(asignaciones_a_finalizar)


# ------------------------------------------------------------------------------------------ movimientos
def registrar_movimiento(u: Unidad, tipo: str, cuil: Any, nombre: Any, detalle: str, observaciones: Any = "",
                         periodo_id: Any = None, horas_variacion: Any = 0, fecha_movimiento: Any = None) -> int:
    """``registrar_movimiento`` (l. 4424) con fecha efectiva opcional (v207)."""
    with u.writer(W_MOVIMIENTO):
        try:
            horas = float(horas_variacion or 0)
        except Exception:
            horas = 0
        fecha_mov = ""
        if fecha_movimiento is not None:
            try:
                fm = rules.safe_date(fecha_movimiento, None)
                fecha_mov = fm.isoformat() if fm is not None else ""
            except Exception:
                fecha_mov = ""
        if not fecha_mov:
            fecha_mov = str(u.today)
        return u.commit(lambda repo: repo.insert_movement(
            period_id=periodo_id, fecha=fecha_mov, tipo=tipo, cuil=cuil, nombre=nombre, detalle=detalle,
            observaciones=observaciones, horas_variacion=horas))


def ids_movimientos_que_referencian(repo: DesignacionesRepository, fila: Optional[dict]) -> list[int]:
    """``_ids_movimientos_que_referencian_designacion_conn`` (l. 8605)."""
    if fila is None:
        return []
    try:
        periodo_id = int(fila.get("periodo_id"))
    except Exception:
        return []
    cuil = str(fila.get("cuil") or "").strip()
    if not cuil:
        return []
    try:
        objetivo = rules.clave_designacion_desde_row(fila)
    except Exception:
        objetivo = None
    if not objetivo:
        return []
    ids = []
    for mov in repo.movimientos_cuil(periodo_id, cuil):
        if not rules.es_movimiento_vinculado_designacion(mov.get("tipo_movimiento", "")):
            continue
        try:
            claves = rules.claves_designacion_movimiento(mov)
        except Exception:
            claves = set()
        if objetivo in claves:
            ids.append(int(mov["id"]))
    return sorted(set(ids))


def movimientos_huerfanos(repo: DesignacionesRepository, periodo_id: Any = None, cuil: Any = None) -> list[int]:
    """Ids de ``_diagnosticar_movimientos_designacion_huerfanos_conn`` (l. 8655)."""
    movs = repo.movimientos_filtrados(int(periodo_id) if periodo_id is not None else None, cuil)
    if not movs:
        return []
    des = repo.designaciones_filtradas(int(periodo_id) if periodo_id is not None else None, cuil)
    docs = repo.nombres_docentes()
    locales = {rules.clave_cuil(d.get("cuil")) for d in docs}
    locales.discard(None)
    grupos = {(d.get("periodo_id"), str(rules.clave_cuil(d.get("cuil")) or "").strip()) for d in des}
    ids = []
    for mov in movs:
        k = str(rules.clave_cuil(mov.get("cuil")) or "").strip()
        grupo = (mov.get("periodo_id"), k)
        es_des = rules.es_movimiento_vinculado_designacion(mov.get("tipo_movimiento", ""))
        es_doc = rules.es_movimiento_docente_por_error(mov.get("tipo_movimiento", ""))
        if not es_des and not es_doc:
            continue
        if es_des:
            if grupo in grupos:
                continue
        elif k in locales or grupo in grupos:
            continue
        ids.append(int(mov["id"]))
    return ids


# ------------------------------------------------------------------------------------------ alta
def guardar_designacion(u: Unidad, periodo_id, cuil, cargo, dedicacion, horas, tipo_designacion, ad_honorem,
                        fecha_desde, fecha_hasta, estado, observaciones, permitir_duplicada=False,
                        numero_resolucion="", funcion_no_docente=False, texto_funcion_no_docente="") -> Any:
    """``guardar_designacion`` efectiva (v162 -> v95 -> base).  Devuelve el id (nuevo o existente)."""
    with u.writer(W_GUARDAR):
        # --- v162
        try:
            pid_v237 = periodo_id_departamento_actual(u, periodo_id)
        except Exception:
            pid_v237 = periodo_id
        estado = estado_v237(u, pid_v237, fecha_hasta, estado)
        horas_norm = rules.horas_segun_dedicacion(dedicacion, horas)
        funcion_flag = 1 if funcion_no_docente else 0
        resolucion_txt = str(numero_resolucion or "").strip()
        permitir_base = bool(permitir_duplicada)
        id_misma_funcion = None
        try:
            periodo_local = periodo_id_departamento_actual(u, periodo_id)
            filas = u.read(lambda repo: repo.match(
                periodo_local, cuil, cargo, dedicacion, horas_norm, tipo_designacion, ad_honorem, fecha_desde,
                fecha_hasta, estado=estado, estado_on=True, resolucion=resolucion_txt or None,
                resolucion_vacia=not resolucion_txt, columns="id, COALESCE(funcion_no_docente, 0) AS funcion_no_docente",
                tail="ORDER BY id LIMIT 10"))
            if filas:
                misma = [f for f in filas if int(pd.to_numeric(f.get("funcion_no_docente"), errors="coerce") or 0)
                         == funcion_flag]
                if misma:
                    id_misma_funcion = int(misma[0]["id"])
                else:
                    permitir_base = True
        except Exception:
            permitir_base = bool(permitir_duplicada)
        if id_misma_funcion is not None and not permitir_duplicada:
            return id_misma_funcion

        # --- v95
        horas_v95 = rules.horas_segun_dedicacion(dedicacion, horas_norm)
        res95 = str(numero_resolucion or "").strip()
        permitir_v95 = bool(permitir_base)
        did = None
        resuelto = False
        if res95 and not permitir_v95:
            try:
                filas = u.read(lambda repo: repo.match(
                    periodo_id, cuil, cargo, dedicacion, horas_v95, tipo_designacion, ad_honorem, fecha_desde,
                    fecha_hasta, estado=estado, estado_on=True,
                    columns="id, COALESCE(numero_resolucion,'') AS numero_resolucion", tail=""))
                if filas:
                    mismas = [f for f in filas if str(f.get("numero_resolucion") or "").strip() == res95]
                    if mismas:
                        did = int(mismas[0]["id"])
                        u.commit(lambda repo: repo.update_prevista_coalesce(did))
                        resuelto = True
                    else:
                        permitir_v95 = True
            except Exception:
                permitir_v95 = bool(permitir_base)
        if not resuelto:
            did = _guardar_base(u, periodo_id, cuil, cargo, dedicacion, horas_v95, tipo_designacion, ad_honorem,
                                fecha_desde, fecha_hasta, estado, observaciones, permitir_v95)
            if did:
                u.commit(lambda repo: repo.update_prevista_coalesce_resolucion(int(did), res95))
        # --- v162 (fin)
        if did:
            texto = rules.texto_funcion_limpio(texto_funcion_no_docente) if funcion_flag else ""
            u.commit(lambda repo: repo.update_funcion(int(did), funcion_flag, texto))
        return did


def _guardar_base(u: Unidad, periodo_id, cuil, cargo, dedicacion, horas, tipo, ad_honorem, fecha_desde, fecha_hasta,
                  estado, observaciones, permitir_duplicada) -> int:
    periodo_id = periodo_id_departamento_actual(u, periodo_id)

    def body(repo: DesignacionesRepository):
        existente = repo.match(periodo_id, cuil, cargo, dedicacion, horas, tipo, ad_honorem, fecha_desde,
                               fecha_hasta, estado=estado, estado_on=True)
        if existente and not permitir_duplicada:
            return _Rollback(("existente", int(existente[0]["id"])))
        return ("nuevo", repo.insert_designacion(periodo_id, cuil, cargo, dedicacion, horas, tipo, ad_honorem,
                                                 fecha_desde, fecha_hasta, estado, observaciones))

    kind, did = u.commit(body)
    if kind == "existente":
        u.avisos.append(MSG_ESA_YA_CARGADA)
        return did
    _sincronizar_silencioso(u, cuil, periodo_id)
    return did


# ------------------------------------------------------------------------------------------ edicion
def _funcion_final(u: Unidad, designacion_id: int, funcion_no_docente, texto_funcion_no_docente) -> None:
    """Tramo v162 de ``actualizar_designacion`` / ``actualizar_designacion_por_error``."""
    if funcion_no_docente is None and texto_funcion_no_docente is None:
        return

    def body(repo: DesignacionesRepository):
        actual = None
        if funcion_no_docente is None or texto_funcion_no_docente is None:
            actual = repo.funcion_texto(int(designacion_id))
        if funcion_no_docente is None:
            funcion_final = bool(actual and rules.es_funcion_no_docente(actual.get("funcion_no_docente")))
        else:
            funcion_final = bool(funcion_no_docente)
        if texto_funcion_no_docente is None:
            texto_final = rules.texto_funcion_limpio((actual or {}).get("texto_funcion_no_docente", ""))
        else:
            texto_final = rules.texto_funcion_limpio(texto_funcion_no_docente)
        if not funcion_final:
            texto_final = ""
        return repo.update_funcion(int(designacion_id), 1 if funcion_final else 0, texto_final)

    u.commit(body)


def _estado_v233(u: Unidad, designacion_id: Any, fecha_hasta: Any, estado: Any) -> Any:
    try:
        ref = u.read(lambda repo: repo.designacion_periodo(int(designacion_id)))
        if ref is not None:
            return estado_v237(u, ref.get("periodo_id"), fecha_hasta, estado)
    except Exception:
        pass
    return estado


def _limpiar_v233(u: Unidad, designacion_id: Any, estado: Any) -> None:
    try:
        with u.writer(W_LIMPIAR_V233):
            if rules.normalizar_clave(estado) != "ACTIVA":
                return
            u.commit(lambda repo: repo.limpiar_metadatos_finalizacion(int(designacion_id)))
    except AuditoriaFallida:
        raise
    except Exception:
        pass


def actualizar_designacion(u: Unidad, designacion_id, cargo, dedicacion, horas, tipo_designacion, ad_honorem,
                           fecha_desde, fecha_hasta, estado, observaciones, numero_resolucion=None,
                           funcion_no_docente=None, texto_funcion_no_docente=None) -> None:
    with u.writer(W_ACTUALIZAR):
        estado = _estado_v233(u, designacion_id, fecha_hasta, estado)
        horas = rules.horas_segun_dedicacion(dedicacion, horas)

        def base(repo: DesignacionesRepository):
            ref = repo.designacion_ref(int(designacion_id))
            repo.update_base(designacion_id, cargo, dedicacion, horas, tipo_designacion, ad_honorem, fecha_desde,
                             fecha_hasta, estado, observaciones)
            return ref

        ref = u.commit(base)
        if ref is not None:
            _sincronizar_silencioso(u, str(ref.get("cuil") or ""), int(ref.get("periodo_id")))
        u.commit(lambda repo: repo.update_prevista(int(designacion_id), fecha_hasta, numero_resolucion))
        _funcion_final(u, designacion_id, funcion_no_docente, texto_funcion_no_docente)
        _limpiar_v233(u, designacion_id, estado)


def actualizar_designacion_por_error(u: Unidad, designacion_id, cargo, dedicacion, horas, tipo_designacion,
                                     ad_honorem, fecha_desde, fecha_hasta, estado, observaciones,
                                     numero_resolucion=None, funcion_no_docente=None,
                                     texto_funcion_no_docente=None) -> int:
    with u.writer(W_POR_ERROR):
        estado = _estado_v233(u, designacion_id, fecha_hasta, estado)
        horas = rules.horas_segun_dedicacion(dedicacion, horas)

        def base(repo: DesignacionesRepository):
            ref = repo.designacion_ref(int(designacion_id))
            ids_mov = ids_movimientos_que_referencian(repo, ref) if ref is not None else []
            repo.update_base(designacion_id, cargo, dedicacion, horas, tipo_designacion, ad_honorem, fecha_desde,
                             fecha_hasta, estado, observaciones)
            eliminados = repo.delete_movimientos(ids_mov) if ids_mov else 0
            return ref, eliminados

        ref, eliminados = u.commit(base)
        if ref is not None:
            _sincronizar_silencioso(u, str(ref.get("cuil") or ""), int(ref.get("periodo_id")))
        u.commit(lambda repo: repo.update_prevista(int(designacion_id), fecha_hasta, numero_resolucion))
        _funcion_final(u, designacion_id, funcion_no_docente, texto_funcion_no_docente)
        _limpiar_v233(u, designacion_id, estado)
        return eliminados


def actualizar_fechas_v171(u: Unidad, designacion_id, numero_resolucion, fecha_desde, fecha_hasta) -> None:
    with u.writer(W_FECHAS):
        desde = rules.fecha_iso_correccion_directa_v171(fecha_desde)
        hasta = rules.fecha_iso_correccion_directa_v171(fecha_hasta)
        if not desde or not hasta:
            raise ValueError("Desde y Hasta son obligatorios y deben ser fechas válidas.")
        if desde > hasta:
            raise ValueError("La fecha Desde no puede ser posterior a la fecha Hasta.")
        u.commit(lambda repo: repo.update_fechas_v171(int(designacion_id), str(numero_resolucion or "").strip(),
                                                      desde, hasta))


# ------------------------------------------------------------------------------------------ baja y eliminacion
def guardar_estado_consulta_designacion(u: Unidad, cuil, periodo_id, estado) -> None:
    """l. 23858: DELETE de la fila (periodo, cuil) y, si el estado es uno de los certificados, INSERT con
    ``fecha_actualizacion = str(datetime.now())``; un COMMIT.  Estado vacio ("⚪ Sin estado") -> solo DELETE."""
    estado = str(estado or "").strip()
    with u.writer(W_ESTADO_CONSULTA):
        def body(repo: DesignacionesRepository) -> None:
            repo.borrar_estado_consulta(int(periodo_id), str(cuil))
            if estado in rules.ESTADOS_CONSULTA_DESIGNACION:
                repo.insertar_estado_consulta(int(periodo_id), str(cuil), estado, str(u.now))
        u.commit(body)


def finalizar_designacion_anticipadamente(u: Unidad, designacion_id, fecha_efectiva, motivo="") -> dict:
    with u.writer(W_FINALIZAR):
        def body(repo: DesignacionesRepository):
            r = repo.designacion_star(int(designacion_id))
            if r is None:
                raise ValueError("No se encontró la designación.")
            fd = rules.safe_date(r.get("fecha_desde"), None)
            fp = rules.safe_date(r.get("fecha_hasta_prevista") or r.get("fecha_hasta"), None)
            fe = rules.safe_date(fecha_efectiva, None)
            if fe is None:
                raise ValueError("Indicá la fecha efectiva de finalización.")
            if fd and fe < fd:
                raise ValueError("La fecha efectiva no puede ser anterior al inicio de la designación.")
            if fp and fe > fp:
                raise ValueError("La fecha efectiva no puede ser posterior al vencimiento previsto.")
            repo.finalizar(int(designacion_id), str(fe), str(u.now), str(motivo or ""))
            return r, fe

        r, fe = u.commit(body)
        comisiones_auto = 0
        if not rules.es_funcion_no_docente(r.get("funcion_no_docente")):
            try:
                comisiones_auto = finalizar_comisiones_sin_designacion(
                    u, str(r.get("cuil") or ""), int(r.get("periodo_id")), fe, int(designacion_id))
            except AuditoriaFallida:
                raise
            except Exception:
                comisiones_auto = 0
        _sincronizar_silencioso(u, str(r.get("cuil") or ""), int(r.get("periodo_id")))
        salida = dict(r)
        salida["_comisiones_finalizadas_auto"] = int(comisiones_auto or 0)
        return salida


def eliminar_designacion(u: Unidad, designacion_id) -> dict:
    with u.writer(W_ELIMINAR):
        def body(repo: DesignacionesRepository):
            ref = repo.designacion_ref(int(designacion_id))
            if ref is None:
                return _Rollback({"designaciones_eliminadas": 0, "movimientos_eliminados": 0, "_ref": None})
            ids_mov = ids_movimientos_que_referencian(repo, ref)
            repo.delete_links_designaciones([int(designacion_id)])
            eliminadas = repo.delete_designaciones([int(designacion_id)])
            mov_eliminados = 0
            if ids_mov:
                repo.delete_links_movimientos(ids_mov)
                mov_eliminados += repo.delete_movimientos(ids_mov)
            extra = [i for i in movimientos_huerfanos(repo, int(ref["periodo_id"]), str(ref.get("cuil") or ""))
                     if i not in set(ids_mov)]
            if extra:
                repo.delete_links_movimientos(extra)
                mov_eliminados += repo.delete_movimientos(extra)
            return {"designaciones_eliminadas": eliminadas, "movimientos_eliminados": mov_eliminados, "_ref": ref}

        res = u.commit(body)
        ref = res.pop("_ref")
        if ref is None:
            return res
        _sincronizar_silencioso(u, str(ref.get("cuil") or ""), int(ref["periodo_id"]))
        return res


def eliminar_designaciones_masivo(u: Unidad, ids_designaciones) -> dict:
    with u.writer(W_ELIMINAR_MASIVO):
        ids = []
        for valor in (ids_designaciones or []):
            try:
                ids.append(int(valor))
            except Exception:
                pass
        ids = sorted(set(ids))
        if not ids:
            return {"designaciones_eliminadas": 0, "movimientos_eliminados": 0, "solicitadas": 0, "no_encontradas": 0}

        def body(repo: DesignacionesRepository):
            refs = repo.designaciones_refs(ids)
            if not refs:
                return _Rollback(({"designaciones_eliminadas": 0, "movimientos_eliminados": 0,
                                   "solicitadas": len(ids), "no_encontradas": len(ids)}, []))
            afectados = []
            ids_movs = set()
            for fila in refs:
                try:
                    par = (int(fila.get("periodo_id")), str(fila.get("cuil") or ""))
                    if par not in afectados:
                        afectados.append(par)
                except Exception:
                    pass
                try:
                    ids_movs.update(ids_movimientos_que_referencian(repo, fila))
                except Exception:
                    pass
            reales = [int(f["id"]) for f in refs]
            repo.delete_links_designaciones(reales)
            eliminadas = repo.delete_designaciones(reales)
            mov_eliminados = 0
            if ids_movs:
                lista = sorted(ids_movs)
                repo.delete_links_movimientos(lista)
                mov_eliminados += repo.delete_movimientos(lista)
            extra = set()
            for pid, cuil in afectados:
                try:
                    extra.update(movimientos_huerfanos(repo, pid, cuil))
                except Exception:
                    pass
            extra.difference_update(ids_movs)
            if extra:
                lista = sorted(extra)
                repo.delete_links_movimientos(lista)
                mov_eliminados += repo.delete_movimientos(lista)
            return ({"designaciones_eliminadas": int(eliminadas), "movimientos_eliminados": int(mov_eliminados),
                     "solicitadas": len(ids), "no_encontradas": max(len(ids) - len(refs), 0)}, afectados)

        res, afectados = u.commit(body)
        for pid, cuil in afectados:
            _sincronizar_silencioso(u, cuil, pid)
        return res


# ------------------------------------------------------------------------------------------ baja v207
def sincronizar_baja_v207(u: Unidad, designacion_id, fecha_baja, origen="baja efectiva") -> dict:
    with u.writer(W_BAJA_V207):
        try:
            did = int(designacion_id)
        except Exception:
            return {"estado": "omitido", "motivo": "id inválido", "cambios": 0}
        fb = rules.safe_date(fecha_baja, None)
        if fb is None:
            return {"estado": "omitido", "motivo": "fecha inválida", "cambios": 0}
        marcador = f"[AUTO_V207_DESIGNACION_ID={did}]"

        def body(repo: DesignacionesRepository):
            r = repo.v207_designacion(did)
            if r is None:
                return _Rollback({"estado": "omitido", "motivo": "designación inexistente", "cambios": 0})
            pid = int(r.get("periodo_id"))
            fi = rules.safe_date(r.get("fecha_inicio"), None)
            ff = rules.safe_date(r.get("fecha_fin"), None)
            cuil = str(r.get("cuil") or "").strip()
            autos = repo.v207_autos(pid, cuil, marcador)
            corresponde = True
            if fi is not None and fb < fi:
                corresponde = False
            if ff is None or fb >= ff:
                corresponde = False
            if fb > u.today:
                corresponde = False
            if not corresponde:
                borrados = 0
                for m in autos:
                    borrados += repo.delete_movimiento(int(m["id"]))
                res = {"estado": "sin_baja", "motivo": "vencimiento normal/fuera de período", "cambios": borrados}
                return res if autos else _Rollback(res)
            hs = float(rules.hora_numero(r.get("horas", 0)) or 0)
            es_no_docente = rules.es_funcion_no_docente(r.get("funcion_no_docente"))
            fecha_txt = fb.isoformat()
            detalle = (f"{str(r.get('periodo') or '')} - Baja de designación. "
                       f"Antes: {rules.limpiar_texto_tabla(r.get('cargo',''))} - "
                       f"{rules.limpiar_texto_tabla(r.get('dedicacion',''))} - {hs:g} hs - "
                       f"{rules.limpiar_texto_tabla(r.get('tipo_designacion',''))} - "
                       f"Ad Honorem: {rules.limpiar_texto_tabla(r.get('ad_honorem','No'))}. "
                       f"Fecha efectiva de baja: {fecha_txt}. ID designación original: {did}. {marcador}")
            observ = f"Sincronizada automáticamente desde {origen}. {marcador}"
            variacion = 0.0 if es_no_docente else -abs(hs)
            if autos:
                ids_auto = [int(m["id"]) for m in autos]
                principal = ids_auto[0]
                p = autos[0]
                if (str(p.get("fecha") or "") == fecha_txt
                        and str(p.get("tipo_movimiento") or "").strip() == "Baja de designación"
                        and len(ids_auto) == 1):
                    return _Rollback({"estado": "sin_cambios", "cambios": 0, "movimiento_id": principal})
                repo.v207_update_completo(principal, fecha_txt, str(r.get("nombre_completo") or cuil), detalle,
                                          observ, variacion)
                for mid in ids_auto[1:]:
                    repo.delete_movimiento(mid)
                return {"estado": "actualizado", "cambios": 1, "movimiento_id": principal}
            cand = repo.v207_candidatos(pid, cuil)
            equivalente = None
            if cand:
                cargo = rules.limpiar_texto_tabla(r.get("cargo", "")).casefold()
                dedic = rules.limpiar_texto_tabla(r.get("dedicacion", "")).casefold()
                tipo = rules.limpiar_texto_tabla(r.get("tipo_designacion", "")).casefold()
                for m in cand:
                    txt = (str(m.get("detalle") or "") + " " + str(m.get("observaciones") or "")).casefold()
                    if f"id designación original: {did}".casefold() in txt or f"id designacion original: {did}" in txt:
                        equivalente = m
                        break
                    fecha_decl = re.search(r"fecha efectiva de baja:\s*(\d{4}-\d{2}-\d{2})", txt, flags=re.I)
                    contrato_ok = (not cargo or cargo in txt) and (not dedic or dedic in txt) and (not tipo or tipo in txt)
                    if fecha_decl and fecha_decl.group(1) == fecha_txt and contrato_ok:
                        equivalente = m
                        break
                if equivalente is None and repo.count_designaciones_cuil(pid, cuil) == 1 and len(cand) == 1:
                    equivalente = cand[0]
            if equivalente is not None:
                eid = int(equivalente["id"])
                if (str(equivalente.get("fecha") or "") == fecha_txt
                        and str(equivalente.get("tipo_movimiento") or "").strip() == "Baja de designación"):
                    return _Rollback({"estado": "sin_cambios", "cambios": 0, "movimiento_id": eid})
                repo.v207_update_legacy(eid, fecha_txt, variacion)
                return {"estado": "legacy_actualizado", "cambios": 1, "movimiento_id": eid}
            return _Rollback({"estado": "_insertar", "r": r, "pid": pid, "cuil": cuil, "detalle": detalle,
                              "observ": observ, "variacion": variacion, "fecha": fecha_txt})

        res = u.commit(body)
        if res.get("estado") != "_insertar":
            return res
        registrar_movimiento(u, "Baja de designación", res["cuil"], str(res["r"].get("nombre_completo") or res["cuil"]),
                             res["detalle"], res["observ"], res["pid"], horas_variacion=res["variacion"],
                             fecha_movimiento=res["fecha"])
        return {"estado": "creado", "cambios": 1}


# ------------------------------------------------------------------------------------------ actos v266/v267
def vincular_acto_designacion(u: Unidad, designacion_id, documento_id) -> None:
    with u.writer(W_VINCULAR_DES):
        u.commit(lambda repo: repo.link_designacion(int(documento_id), int(designacion_id), u.usuario))


def vincular_acto_movimiento(u: Unidad, movimiento_id, documento_id) -> None:
    with u.writer(W_VINCULAR_MOV):
        if not rules.id_documento_valido(movimiento_id):
            return
        u.commit(lambda repo: repo.link_movimiento(int(documento_id), int(movimiento_id), u.usuario))


def _ids_validos(ids) -> list[int]:
    return sorted({int(x) for x in list(ids or []) if rules.id_documento_valido(x)})


def vincular_actos_masivo(u: Unidad, writer: str, ids, documento_id) -> int:
    with u.writer(writer):
        lista = _ids_validos(ids)
        if not lista or not rules.id_documento_valido(documento_id):
            return 0
        link = "link_designacion" if writer == W_VINCULAR_DES_MASIVO else "link_movimiento"

        def body(repo: DesignacionesRepository):
            for i in lista:
                getattr(repo, link)(int(documento_id), i, u.usuario)
            return len(lista)

        return u.commit(body)


def desvincular_actos_masivo(u: Unidad, writer: str, ids) -> int:
    with u.writer(writer):
        lista = _ids_validos(ids)
        if not lista:
            return 0
        if writer == W_DESVINCULAR_DES_MASIVO:
            return u.commit(lambda repo: repo.unlink_designaciones(lista))
        return u.commit(lambda repo: repo.unlink_movimientos(lista))
