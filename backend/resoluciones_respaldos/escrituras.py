"""Writers certificados de Resoluciones y respaldos con sus COMMITs reales (B13-FIX02; D-AK8: sin mejorar atomicidad).

Cada ``_pg_raw_conn()`` con escritura del certificado es un COMMIT propio (``Unidad.commit``: SUCCESS en la misma
transaccion, ``commit_seq`` por COMMIT, ``committing_writer`` = writer de negocio mas interno).  Cadenas (entry):
- ``guardar_documento_respaldo_v251`` l. 50873 (W1): ``guardar_documento_respaldo_v249`` l. 50350 anidado (W1a, COMMIT
  1: INSERT con el binario) -> docentes (COMMIT 2, si hay) -> ``_vincular_proyectos_documento_v261`` l. 50832 anidado
  (COMMIT 3, si hay; el writer ya portado de Investigacion).  Si falla un vinculo: compensacion
  ``eliminar_documento_respaldo_v249`` (otro COMMIT; la cascada borra los vinculos ya confirmados) salvo que B12D haya
  envenenado el writer (fallo de base que no es de restriccion: 0 escrituras posteriores); el error se re-levanta.
- ``adjuntar_pdf_documento_respaldo_v272`` l. 50506 (W2): un COMMIT; ``rowcount != 1`` -> ROLLBACK + ValueError.
- ``actualizar_dependencia_documento_v262`` l. 50317 (W3): lectura del catalogo + un COMMIT.
- ``guardar_dependencia_documental_v262`` l. 50244 (W4) y ``actualizar_dependencia_documental_v262`` l. 50278 (W4b,
  propaga ``dependencia_nombre`` a los documentos de TODA la institucion): un COMMIT, alcance institucional.
- ``eliminar_documento_respaldo_v251`` l. 51475 (W6): COMMIT 1 con los 4 DELETE de vinculos -> ``eliminar_documento_
  respaldo_v249`` l. 50555 anidado (W6a, COMMIT 2).  Si falla el segundo, los vinculos ya quedaron borrados (deuda
  post-equivalencia documentada).
- Etapa 4 (D-AK4, sin pantalla en este bloque): ``_resolver_acto_contextual_v267`` l. 54714 y la compensacion
  ``_eliminar_acto_recien_creado_v267`` l. 54761; los vinculos con designaciones / movimientos son los writers ya
  portados en Designaciones (``designaciones.escrituras``), que operan sobre esta misma ``Unidad``.
Sin locks (B12I: ninguna familia de capa T), sin DDL ni migraciones (D-AK7), sin movimientos.
"""

from __future__ import annotations

from typing import Any, Callable

import pandas as pd
import psycopg

import audit
from designaciones import escrituras as DE
from investigacion import escrituras as IE

from . import rules as R
from .repository import (DEPENDENCIA_DUP_OTRA_SQL, DEPENDENCIA_DUP_SQL, DEPENDENCIA_INSERT_SQL, DEPENDENCIA_PROPAGAR_SQL,
                         DEPENDENCIA_UPDATE_SQL, DocumentosRepository)

W_GUARDAR = "guardar_documento_respaldo_v251"
W_GUARDAR_BASE = "guardar_documento_respaldo_v249"
W_ADJUNTAR_PDF = "adjuntar_pdf_documento_respaldo_v272"
W_DEPENDENCIA_DOCUMENTO = "actualizar_dependencia_documento_v262"
W_GUARDAR_DEPENDENCIA = "guardar_dependencia_documental_v262"
W_ACTUALIZAR_DEPENDENCIA = "actualizar_dependencia_documental_v262"
W_ELIMINAR = "eliminar_documento_respaldo_v251"
W_ELIMINAR_BASE = "eliminar_documento_respaldo_v249"
W_VINCULAR_PROYECTOS = IE.W_VINCULAR_ACTO  # "_vincular_proyectos_documento_v261"
W_COMPENSAR_ALTA_V267 = "_eliminar_acto_recien_creado_v267"
# 6A-B3: edicion posterior de relaciones (writers del catalogo certificado)
W_DESVINCULAR_PROYECTOS = IE.W_DESVINCULAR_ACTO  # "desvincular_acto_proyectos_masivo_v267"
W_ASEGURAR_DOCENTE = "_asegurar_docente_en_documento_v266"
ASEGURAR_DOCENTE_SQL = """
                INSERT INTO documentos_respaldo_docentes
                    (institucion_id, departamento_id, documento_id, cuil, docente_nombre)
                VALUES (%s,%s,%s,%s,%s)
                ON CONFLICT (institucion_id, departamento_id, documento_id, cuil)
                DO UPDATE SET docente_nombre=EXCLUDED.docente_nombre
            """

AuditoriaFallida = DE.AuditoriaFallida

MSG_PDF_GRANDE = "El PDF supera 50 MB."
MSG_PDF_VACIO = "Seleccioná un PDF válido."
MSG_SIN_AMBITO = "No se pudo identificar la institución/departamento actual."
MSG_ACTO_NO_ENCONTRADO = "No se encontró el acto administrativo a actualizar."
MSG_DEPENDENCIA_SIN_NOMBRE = "Indicá el nombre de la dependencia emisora."
MSG_DEPENDENCIA_DUPLICADA = "Ya existe una dependencia con ese nombre en la institución."
MSG_DEPENDENCIA_DUPLICADA_OTRA = "Ya existe otra dependencia con ese nombre en la institución."
MSG_DEPENDENCIA_NO_ENCONTRADA = "No se encontró la dependencia a actualizar."
MSG_DEPENDENCIA_SELECCIONADA = "No se encontró la dependencia seleccionada."
MSG_DOCUMENTO_NO_ENCONTRADO = "No se encontró el documento a actualizar."


class Unidad(DE.Unidad):
    """La ``Unidad`` B12H de Designaciones con el repositorio documental (mismo acoplamiento de COMMITs)."""

    def __init__(self, *args, usuario_carga: str = "", **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario_carga = usuario_carga  # ``current_user()["email"] or ["usuario"]`` (v249 l. 50369)
        self.envenenado = False  # B12D capa W: fallo de base critico dentro del writer

    def read(self, fn: Callable[[DocumentosRepository], Any]) -> Any:
        try:
            with self._transaction() as conn:
                return fn(DocumentosRepository(conn, self.inst, self.dep))
        except psycopg.Error as exc:
            if not isinstance(exc, psycopg.errors.IntegrityError):
                self.envenenado = True
            raise

    def commit(self, fn: Callable[[DocumentosRepository], Any]) -> Any:
        if self.audit_failed:
            raise AuditoriaFallida("AUDIT_FAILED_EARLIER")
        if self.envenenado:
            raise CriticalDBWriteError("CRITICAL_DB_WRITE")
        repo = None
        try:
            with self._transaction() as conn:
                repo = DocumentosRepository(conn, self.inst, self.dep)
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
        except psycopg.Error as exc:
            if not isinstance(exc, psycopg.errors.IntegrityError):
                self.envenenado = True
            raise
        if repo is not None and repo.mutating_statements:
            self.op.coupled_commits += 1
        return result


class CriticalDBWriteError(RuntimeError):
    """B12D: el writer quedo envenenado por un fallo de base; no se ejecutan escrituras posteriores."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


# ------------------------------------------------------------------------------------------ alta (W1 / W1a)
def guardar_documento_respaldo_v249(u: Unidad, tipo_documento, categoria, numero, fecha_doc, periodo_id, cuil,
                                    docente_nombre, proyecto_tipo, proyecto_id, referencia_texto, titulo, detalle,
                                    observaciones, archivo_nombre, archivo_mime, archivo_pdf, tipo_resolucion="",
                                    dependencia_id=None, dependencia_nombre="") -> int:
    with u.writer(W_GUARDAR_BASE):
        contenido = bytes(archivo_pdf or b"")
        # v272: el acto puede existir antes que su archivo (BYTEA vacio compatible con el NOT NULL).
        if len(contenido) > R.MAX_PDF_BYTES:
            raise ValueError(MSG_PDF_GRANDE)
        nombre_guardado = str(archivo_nombre or "").strip() if contenido else ""
        mime_guardado = str(archivo_mime or R.PDF_MIME).strip() if contenido else ""
        fecha_iso = None
        if fecha_doc is not None:
            try:
                fecha_iso = R.safe_date(fecha_doc, None)
            except Exception:
                fecha_iso = None
        params = [
            str(tipo_documento), str(tipo_resolucion or "").strip(), str(categoria), str(numero or "").strip(),
            fecha_iso, int(periodo_id) if periodo_id not in [None, ""] else None,
            str(cuil or "").strip(), str(docente_nombre or "").strip(),
            str(proyecto_tipo or "").strip(), int(proyecto_id) if proyecto_id not in [None, ""] else None,
            int(dependencia_id) if dependencia_id not in [None, ""] else None, R.nombre_dependencia_v262(dependencia_nombre),
            str(referencia_texto or "").strip(), str(titulo or "").strip(), str(detalle or "").strip(),
            str(observaciones or "").strip(), nombre_guardado, mime_guardado, contenido, len(contenido), u.now,
            u.usuario_carga,
        ]
        return int(u.commit(lambda repo: repo.insert_documento(params)))


def guardar_documento_respaldo_v251(u: Unidad, tipo_documento, categoria, numero, fecha_doc, periodo_id,
                                    docentes_relacionados, proyecto_tipo, proyecto_id, referencia_texto, titulo, detalle,
                                    observaciones, archivo_nombre, archivo_mime, archivo_pdf, tipo_resolucion="",
                                    proyectos_relacionados=None, dependencia_id=None, dependencia_nombre="") -> int:
    with u.writer(W_GUARDAR):
        docentes = R.normalizar_docentes_respaldo_v251(docentes_relacionados)
        primero = docentes[0] if docentes else {"cuil": "", "nombre": ""}
        proyectos = R.normalizar_proyectos_respaldo_v261(proyectos_relacionados, proyecto_tipo)
        if not proyectos and proyecto_id not in [None, ""] and str(proyecto_tipo or "").strip():
            proyectos = R.normalizar_proyectos_respaldo_v261(
                [{"tipo": proyecto_tipo, "id": proyecto_id, "nombre": "", "codigo": ""}], proyecto_tipo)
        primer_proyecto = proyectos[0] if proyectos else {"tipo": str(proyecto_tipo or "").strip(), "id": proyecto_id}
        nuevo_id = guardar_documento_respaldo_v249(
            u, tipo_documento, categoria, numero, fecha_doc, periodo_id, primero["cuil"], primero["nombre"],
            primer_proyecto.get("tipo", ""), primer_proyecto.get("id"), referencia_texto, titulo, detalle, observaciones,
            archivo_nombre, archivo_mime, archivo_pdf, tipo_resolucion, dependencia_id, dependencia_nombre)
        try:
            if docentes:
                def body(repo: DocumentosRepository):
                    for item in docentes:
                        repo.upsert_docente(nuevo_id, item)
                u.commit(body)
            if proyectos:
                vincular_proyectos_documento_v261(u, int(nuevo_id), proyectos)
            return int(nuevo_id)
        except Exception:
            # Evita dejar un PDF huerfano si falla la vinculacion multiple.  Si B12D envenenó el writer (fallo de base
            # que no es de restriccion) o B12H fallo antes, ``Unidad.commit`` bloquea esta compensacion (0 escrituras).
            try:
                eliminar_documento_respaldo_v249(u, int(nuevo_id))
            except Exception:
                pass
            raise


def vincular_proyectos_documento_v261(u: Unidad, documento_id, proyectos_relacionados) -> int:
    """El writer ya portado de Investigacion (l. 50832), con su marco B10 propio cuando corre anidado."""
    with u.writer(W_VINCULAR_PROYECTOS):
        return IE.vincular_proyectos_documento_v261(u, documento_id, proyectos_relacionados)


# ------------------------------------------------------------------------------------------ 6A-B3: relaciones
def desvincular_acto_proyectos_masivo_v267(u: Unidad, documento_id, tipo_proyecto, proyecto_ids) -> int:
    """El writer certificado ya portado de Investigacion (l. 54938), con su marco B10."""
    with u.writer(W_DESVINCULAR_PROYECTOS):
        return IE.desvincular_acto_proyectos_masivo_v267(u, documento_id, tipo_proyecto, proyecto_ids)


def asegurar_docente_en_documento_v266(u: Unidad, documento_id, cuil, nombre="") -> int:
    """``_asegurar_docente_en_documento_v266`` (entry l. 58257, writer del catalogo certificado B12H): UPSERT del docente
    en ``documentos_respaldo_docentes`` de un acto ya cargado; un COMMIT.  Sin DDL (D-AK7)."""
    clave = str(cuil or "").strip()
    if not clave:
        return 0
    with u.writer(W_ASEGURAR_DOCENTE):
        return u.commit(lambda repo: repo._mutate(ASEGURAR_DOCENTE_SQL, [
            u.inst, u.dep, int(documento_id), clave, str(nombre or clave)]))


# ------------------------------------------------------------------------------------------ PDF (W2)
def adjuntar_pdf_documento_respaldo_v272(u: Unidad, documento_id, archivo_nombre, archivo_mime, archivo_pdf) -> bool:
    with u.writer(W_ADJUNTAR_PDF):
        contenido = bytes(archivo_pdf or b"")
        if not contenido:
            raise ValueError(MSG_PDF_VACIO)
        if len(contenido) > R.MAX_PDF_BYTES:
            raise ValueError(MSG_PDF_GRANDE)
        nombre = str(archivo_nombre or R.NOMBRE_PDF_DEFECTO).strip() or R.NOMBRE_PDF_DEFECTO
        mime = str(archivo_mime or R.PDF_MIME).strip() or R.PDF_MIME

        def body(repo: DocumentosRepository):
            if repo.update_pdf(nombre, mime, contenido, int(documento_id)) != 1:
                raise ValueError(MSG_ACTO_NO_ENCONTRADO)
        u.commit(body)
        return True


# ------------------------------------------------------------------------------------------ dependencias (W3/W4/W4b)
def actualizar_dependencia_documento_v262(u: Unidad, documento_id, dependencia_id) -> str:
    with u.writer(W_DEPENDENCIA_DOCUMENTO):
        deps = u.read(lambda repo: repo.dependencias(solo_activas=False))
        fila = deps[pd.to_numeric(deps["id"], errors="coerce") == int(dependencia_id)] if not deps.empty else deps
        if fila.empty:
            raise ValueError(MSG_DEPENDENCIA_SELECCIONADA)
        nombre = R.nombre_dependencia_v262(fila.iloc[0].get("nombre", ""))
        legacy = R.tipo_resolucion_legacy_v262(nombre)

        def body(repo: DocumentosRepository):
            if repo.update_dependencia_documento(int(dependencia_id), nombre, legacy, int(documento_id)) != 1:
                raise ValueError(MSG_DOCUMENTO_NO_ENCONTRADO)
        u.commit(body)
        return nombre


def guardar_dependencia_documental_v262(u: Unidad, nombre, observaciones="") -> None:
    with u.writer(W_GUARDAR_DEPENDENCIA):
        nombre = R.nombre_dependencia_v262(nombre)
        if not nombre:
            raise ValueError(MSG_DEPENDENCIA_SIN_NOMBRE)
        observaciones = str(observaciones or "").strip()

        def body(repo: DocumentosRepository):
            if repo.fetch_id(DEPENDENCIA_DUP_SQL, [u.inst, nombre]) is not None:
                raise ValueError(MSG_DEPENDENCIA_DUPLICADA)
            repo._mutate(DEPENDENCIA_INSERT_SQL, [u.inst, nombre, observaciones])
        u.commit(body)


def actualizar_dependencia_documental_v262(u: Unidad, dependencia_id, nombre, estado="Activa",
                                           observaciones="") -> None:
    with u.writer(W_ACTUALIZAR_DEPENDENCIA):
        nombre = R.nombre_dependencia_v262(nombre)
        estado = "Inactiva" if str(estado or "").strip() == "Inactiva" else "Activa"
        if not nombre:
            raise ValueError(MSG_DEPENDENCIA_SIN_NOMBRE)
        observaciones = str(observaciones or "").strip()

        def body(repo: DocumentosRepository):
            if repo.fetch_id(DEPENDENCIA_DUP_OTRA_SQL, [u.inst, nombre, int(dependencia_id)]) is not None:
                raise ValueError(MSG_DEPENDENCIA_DUPLICADA_OTRA)
            if repo._mutate(DEPENDENCIA_UPDATE_SQL, [nombre, estado, observaciones, int(dependencia_id), u.inst]) != 1:
                raise ValueError(MSG_DEPENDENCIA_NO_ENCONTRADA)
            repo._mutate(DEPENDENCIA_PROPAGAR_SQL, [nombre, u.inst, int(dependencia_id)])
        u.commit(body)


# ------------------------------------------------------------------------------------------ eliminar (W6 / W6a)
def eliminar_documento_respaldo_v249(u: Unidad, documento_id) -> int:
    with u.writer(W_ELIMINAR_BASE):
        return int(u.commit(lambda repo: repo.delete_documento(int(documento_id))) or 0)


def eliminar_documento_respaldo_v251(u: Unidad, documento_id) -> int:
    with u.writer(W_ELIMINAR):
        u.commit(lambda repo: repo.delete_vinculos(int(documento_id)))
        return eliminar_documento_respaldo_v249(u, documento_id)


# ------------------------------------------------------------------------------------------ Etapa 4 (D-AK4)
def resolver_acto_contextual_v267(u: Unidad, config: Any, periodo_id, categoria, referencia_texto="",
                                  titulo_sugerido="", detalle_sugerido="", observaciones_sugeridas="") -> tuple:
    """``_resolver_acto_contextual_v267`` (l. 54714): ``(documento_id, creado_ahora)``.  Sin pantalla en este bloque:
    la opcion "Cargar un nuevo acto ahora" de Designaciones sigue pendiente hasta la Etapa 4 (D-AK4)."""
    from designaciones.rules import id_documento_valido

    config = config if isinstance(config, dict) else {"modo": "pendiente"}
    modo = str(config.get("modo") or "pendiente")
    if modo == "pendiente":
        return None, False
    if modo == "existente":
        documento_id = config.get("documento_id")
        if not id_documento_valido(documento_id):
            raise ValueError("Elegiste vincular un acto existente, pero todavía no seleccionaste ninguno. Seleccionalo "
                             "o elegí ‘Dejar pendiente’.")
        return int(documento_id), False
    if modo != "nuevo":
        return None, False
    payload = config.get("payload") if isinstance(config.get("payload"), dict) else {}
    errores = list(payload.get("errores") or [])
    if errores:
        raise ValueError("No se puede crear el acto administrativo: " + " ".join(str(x) for x in errores))
    tipo_documento = str(payload.get("tipo_documento") or "Resolución").strip()
    dependencia_nombre = str(payload.get("dependencia_nombre") or "").strip()
    tipo_resolucion = R.tipo_resolucion_legacy_v262(dependencia_nombre) if tipo_documento == "Resolución" else ""
    nuevo_id = guardar_documento_respaldo_v251(
        u, tipo_documento, str(categoria or payload.get("categoria") or "Otro"), str(payload.get("numero") or "").strip(),
        payload.get("fecha") or u.today, int(periodo_id) if periodo_id not in [None, ""] else None, [], "", None,
        str(referencia_texto or "").strip(),
        str(payload.get("titulo") or titulo_sugerido or categoria or "Acto administrativo").strip(),
        str(payload.get("detalle") or detalle_sugerido or "").strip(),
        str(payload.get("observaciones") or observaciones_sugeridas or "").strip(),
        str(payload.get("archivo_nombre") or ""), str(payload.get("archivo_mime") or ""),
        bytes(payload.get("contenido") or b""), tipo_resolucion, proyectos_relacionados=None,
        dependencia_id=payload.get("dependencia_id"), dependencia_nombre=dependencia_nombre)
    return int(nuevo_id), True


def eliminar_acto_recien_creado_v267(u: Unidad, documento_id) -> None:
    """``_eliminar_acto_recien_creado_v267`` (l. 54761): compensacion registrada en B10 (B12D no la bloquea)."""
    from designaciones.rules import id_documento_valido

    if not id_documento_valido(documento_id):
        return
    with u.writer(W_COMPENSAR_ALTA_V267):
        envenenado, u.envenenado = u.envenenado, False
        try:
            try:
                eliminar_documento_respaldo_v251(u, int(documento_id))
            except Exception:
                try:
                    eliminar_documento_respaldo_v249(u, int(documento_id))
                except Exception:
                    pass
        finally:
            u.envenenado = u.envenenado or envenenado


# Vinculos con designaciones / movimientos (Etapa 4 y Movimientos): writers ya portados, sin cambios.
vincular_acto_designacion_v266 = DE.vincular_acto_designacion
vincular_acto_movimiento_v266 = DE.vincular_acto_movimiento

__all__ = [n for n in dir() if n.startswith("W_")] + ["Unidad", "AuditoriaFallida", "CriticalDBWriteError"]
