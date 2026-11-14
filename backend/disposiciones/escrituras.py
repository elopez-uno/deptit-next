"""Writers certificados de Disposiciones con sus COMMITs reales (B13-FIX02) y el comando B12E de generacion.

Cada ``get_conn()`` con escritura del certificado es un COMMIT propio (``Unidad.commit`` de Designaciones: SUCCESS en
la misma transaccion, ``commit_seq`` por COMMIT de la operacion).  Se replica sin "mejoras":
- ``guardar_parametros_disposicion`` l. 5559: por clave UPDATE y, si ``rowcount == 0``, INSERT; UN COMMIT.
- ``guardar_parametros_docente_disposicion`` v162 l. 35228 -> base l. 5639: UPDATE-o-INSERT (COMMIT 1) + UPDATE del
  texto de funcion (COMMIT 2).  Sin compensacion: lo confirmado queda.  Sin ``CREATE TABLE`` (B12F).
- ``guardar_datos_designaciones_docente_disposicion`` l. 5942: acto v266 por designacion (lectura propia) + UPDATE-o-
  INSERT por designacion visible; UN COMMIT.
- ``guardar_disposicion`` l. 6230 (INSERT, UN COMMIT) y ``eliminar_disposicion`` l. 6245 (DELETE por id sin validar
  ``rowcount``, UN COMMIT; NO borra el Word ni movimientos ni renumera).
- ``generar_disposicion_word_b12e`` (B12E ``generate``): plantilla de la institucion validada -> reserva exclusiva ->
  render sobre una copia privada -> publicacion -> ``guardar_disposicion`` (COMMIT 1; si falla, se borra el Word
  publicado por este intento) -> ``registrar_movimiento`` "Generación de disposición" (COMMIT 2; si falla, quedan la
  fila y el Word).  Sin lock (no hay familia B12I de capa T), sin reserva de numero, sin compensacion global.
- ``reemplazar_plantilla_disposicion_b12e``: solo disco (temporal + fsync + ``os.replace``), sin COMMIT.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from typing import Any, Callable, Optional

import audit
from designaciones import escrituras as DE

from . import rules as R
from . import storage as S
from .repository import DisposicionesRepository

W_PARAMETROS = "guardar_parametros_disposicion"
W_PARAMETROS_DOCENTE = "guardar_parametros_docente_disposicion"
W_DATOS_DESIGNACIONES = "guardar_datos_designaciones_docente_disposicion"
W_GUARDAR = "guardar_disposicion"
W_ELIMINAR = "eliminar_disposicion"
W_GENERAR = "generar_disposicion_word_b12e"
W_PLANTILLA = "reemplazar_plantilla_disposicion_b12e"

AuditoriaFallida = DE.AuditoriaFallida


class Unidad(DE.Unidad):
    """La ``Unidad`` B12H de Designaciones con el repositorio de Disposiciones (mismo acoplamiento de COMMITs)."""

    def read(self, fn: Callable[[DisposicionesRepository], Any]) -> Any:
        with self._transaction() as conn:
            return fn(DisposicionesRepository(conn, self.inst, self.dep))

    def commit(self, fn: Callable[[DisposicionesRepository], Any]) -> Any:
        if self.audit_failed:
            raise AuditoriaFallida("AUDIT_FAILED_EARLIER")
        repo = None
        try:
            with self._transaction() as conn:
                repo = DisposicionesRepository(conn, self.inst, self.dep)
                result = fn(repo)
                if result is DE.ROLLBACK or isinstance(result, DE._Rollback):
                    raise result if isinstance(result, DE._Rollback) else DE._Rollback(None)
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
        except DE._Rollback as rb:
            return rb.value
        if repo is not None and repo.mutating_statements:
            self.op.coupled_commits += 1
        return result


# ------------------------------------------------------------------------------------------ parametros
def guardar_parametros_disposicion(u: Unidad, parametros: dict) -> None:
    def body(repo: DisposicionesRepository):
        for clave, valor in parametros.items():
            clave_txt = str(clave)
            valor_txt = "" if valor is None else str(valor)
            if repo.update_parametro(clave_txt, valor_txt) == 0:
                repo.insert_parametro(clave_txt, valor_txt)
    u.commit(body)


def guardar_numero_inicial_disposiciones_v162(u: Unidad, periodo_id, numero) -> int:
    """l. 35183: no es un writer B10 propio; la operacion es ``guardar_parametros_disposicion``."""
    numero = max(1, int(numero))
    guardar_parametros_disposicion(u, {R.clave_numero_inicial_disposicion_v162(periodo_id): str(numero)})
    return numero


def guardar_parametros_docente_disposicion(u: Unidad, cuil, datos: dict) -> None:
    """v162: base (UPDATE-o-INSERT, COMMIT 1) + texto de funcion (COMMIT 2)."""
    valores = [datos.get(k, "") for k in ("resolucion_cs_concursado", "fecha_desde_concursado",
                                          "fecha_hasta_concursado", "resolucion_cs_interino", "fecha_desde_interino",
                                          "fecha_hasta_interino", "codigo_proyecto", "instituto_proyecto",
                                          "observaciones")]

    def base(repo: DisposicionesRepository):
        if repo.update_parametros_docente(valores, str(cuil)) == 0:
            repo.insert_parametros_docente(str(cuil), valores)
    u.commit(base)
    u.commit(lambda repo: repo.update_texto_funcion(str(datos.get("texto_funcion_disposicion", "") or ""), str(cuil)))


def guardar_datos_designaciones_docente_disposicion(u: Unidad, cuil, registros) -> None:
    ahora = str(u.now)
    filas = []
    for registro in registros or []:
        designacion_id = registro.get("designacion_id")
        if designacion_id is None:
            continue
        resolucion_fuente = ""
        try:
            mapa = u.read(lambda repo: {int(r["designacion_id"]): r
                                        for r in repo.actos_designaciones([int(designacion_id)])})
            acto = (mapa or {}).get(int(designacion_id))
            if acto:
                resolucion_fuente = R.normalizar_texto_disposicion(acto.get("numero", ""))
        except Exception:
            resolucion_fuente = ""
        tipo = R.normalizar_tipo_designacion_disposicion(registro.get("tipo_designacion"))
        cargo = R.normalizar_texto_disposicion(registro.get("cargo"))
        dedicacion = R.normalizar_texto_disposicion(registro.get("dedicacion"))
        desde = R.normalizar_texto_disposicion(registro.get("fecha_desde"))
        hasta = R.normalizar_texto_disposicion(registro.get("fecha_hasta"))
        obs = str(registro.get("observaciones", "") or "").strip()
        filas.append(((registro.get("departamento_id"), tipo, cargo, dedicacion, resolucion_fuente, desde, hasta, obs,
                       ahora, int(designacion_id), str(cuil)),
                      (int(designacion_id), str(cuil), registro.get("departamento_id"), tipo, cargo, dedicacion,
                       resolucion_fuente, desde, hasta, obs, ahora)))

    def body(repo: DisposicionesRepository):
        for update, insert in filas:
            if repo.update_datos_designacion(update) == 0:
                repo.insert_datos_designacion(insert)
    u.commit(body)


# ------------------------------------------------------------------------------------------ registro
def guardar_disposicion(u: Unidad, periodo_id, fecha, tipo, numero, cuil, docente, detalle, observaciones, estado,
                        archivo_word, plantilla_usada, variables) -> int:
    with u.writer(W_GUARDAR):
        return u.commit(lambda repo: repo.insert_disposicion([
            periodo_id, str(fecha), tipo, numero, cuil, docente, detalle, observaciones, estado, archivo_word,
            plantilla_usada, json.dumps(variables, ensure_ascii=False), str(u.today)]))


def eliminar_disposicion(u: Unidad, id_disposicion) -> None:
    u.commit(lambda repo: repo.delete_disposicion(int(id_disposicion)))


# ------------------------------------------------------------------------------------------ B12E
def reemplazar_plantilla(storage: S.DocumentStorage, inst: int, contenido: bytes, nombre_archivo) -> dict:
    """Cuerpo de ``reemplazar_plantilla_disposicion_b12e`` (la autorizacion ya corrio): valida ANTES de tocar el disco."""
    S.check_docx_filename(nombre_archivo)
    S.validate_docx_bytes(contenido, filename=nombre_archivo)
    info = S.atomic_replace_template(storage, inst, contenido)
    return {"institucion_id": inst, "sha256": info["sha256"], "bytes": info["bytes"]}


def generar_disposicion_word(u: Unidad, storage: S.DocumentStorage, render: Callable[[str, str, dict, dict], Any],
                             periodo_id, fecha, tipo, numero, cuil, docente, detalle, observaciones, estado,
                             variables: dict, condiciones: dict, *, stale: Optional[Callable[[], None]] = None) -> dict:
    """``DocumentIsolationRuntime.generate``: publicar Word -> COMMIT fila -> COMMIT movimiento."""
    inst, dep = u.inst, u.dep
    tpl_path = storage.template_path(inst)
    if not os.path.lexists(tpl_path):
        raise S.DocumentAccessDenied("TEMPLATE_MISSING")
    try:
        tpl_data = S.read_regular_file(storage, tpl_path, S.MAX_TEMPLATE_BYTES)
        tpl_info = S.validate_docx_bytes(tpl_data)
    except S.DocumentAccessDenied:
        raise S.DocumentAccessDenied("TEMPLATE_MISSING") from None
    except S.DocumentError:
        raise S.DocxValidationError("TEMPLATE_INVALID") from None
    res = S.allocate_output(storage, inst, dep, f"Disposicion_{numero}_{docente}", now=u.now)
    directory = os.path.dirname(res.path)
    fd, tpl_copy = tempfile.mkstemp(prefix=".b12e-tplcopy-", suffix=".docx", dir=directory)
    try:
        with os.fdopen(fd, "wb") as fh:  # copia privada de los bytes YA validados (sin TOCTOU sobre la plantilla)
            fh.write(tpl_data)
        data = S.publish_output(storage, res, lambda tmp: render(tpl_copy, tmp, variables, condiciones))
    except BaseException:
        S.release_reservation(res)
        raise
    finally:
        S._unlink_quiet(tpl_copy)
    sha = hashlib.sha256(data).hexdigest()
    try:
        # B12I capa U: al entrar a ``guardar_disposicion`` (despues de publicar), como el certificado.
        if stale is not None:
            stale()
        disposicion_id = guardar_disposicion(u, periodo_id, fecha, tipo, numero, cuil, docente, detalle, observaciones,
                                             estado, res.ref, S.template_ref(inst, tpl_info["sha256"]), variables)
    except BaseException:
        S.remove_published(storage, res, sha)  # la fila no existe: no queda un Word huerfano
        raise
    DE.registrar_movimiento(u, R.TIPO_MOVIMIENTO, cuil, docente, f"Se generó disposición N° {numero}: {tipo}",
                            observaciones, periodo_id)
    return {"id": disposicion_id, "ref": res.ref, "file_name": res.name, "bytes": data, "sha256": sha}


__all__ = [n for n in dir() if n.startswith("W_")] + ["Unidad", "AuditoriaFallida"]
