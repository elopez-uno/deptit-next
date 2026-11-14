"""E4-07 — Designaciones → "Cargar un nuevo acto ahora" (alta, finalización / baja y modificación).

Certificado (B13-FIX02): ``_render_acto_contextual_v267`` (l. 54672) ofrece "Elegir del repositorio" / "Cargar un
nuevo acto ahora" / "Dejar pendiente"; el modo nuevo muestra el formulario en linea ``_render_nuevo_acto_inline_v267``
(l. 54565) y, al guardar la operacion, ``_resolver_acto_contextual_v267`` (l. 54714) crea el acto con
``guardar_documento_respaldo_v251`` ANTES del primer writer de Designaciones.  Si la operacion falla sin haber creado
su registro (designacion en el alta; movimiento en la baja y la modificacion), ``_eliminar_acto_recien_creado_v267``
(l. 54761) borra el acto recien creado.  Puntos de uso: alta l. 63714/63753/63796, baja l. 64091/64117/64156,
modificacion l. 64250/64297.

Arquitectura (D-E4-01): el owner del acto es Resoluciones y respaldos (``guardar_documento_respaldo_v251``, B10
``documentos.write``; compensacion registrada en ``COMPENSATIONS`` con ``documentos.write``); el owner de la
designacion, de los movimientos y de los vinculos es Designaciones.  Esta composicion implementa el puerto
``designaciones.service.ActoNuevo`` con los writers YA portados de Resoluciones (``resolver_acto_contextual_v267``,
``eliminar_acto_recien_creado_v267``) y lo entrega a ``DesignacionesService.alta`` / ``.modificar``, que conservan su
secuencia y sus limites de COMMIT certificados (D-E4-06).  Designaciones no importa Resoluciones (ese import ya existe
al reves: ``resoluciones_respaldos.escrituras`` -> ``designaciones.escrituras``).

Validaciones: las del formulario certificado (``errores`` de l. 54649-54655: dependencia y numero obligatorios para
Resolucion / Disposicion, PDF de 50 MB) se evaluan en el servidor en el mismo punto que el certificado (al resolver el
acto, sin escribir ni auditar).  Hardening NEXT: tipo dentro de los 3 del selector, tipos y fecha validos, dependencia
del catalogo ACTIVO de la institucion de la sesion (el nombre sale del catalogo, nunca del cliente) y firma ``%PDF-``
(D-AK2 de Resoluciones).  El PDF va a ``documentos_respaldo.archivo_pdf`` con el mismo writer de Resoluciones: no hay
almacenamiento paralelo ni filesystem.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Optional

from auth.service import SessionRecord
from designaciones import rules as DR
from designaciones.service import DesignacionesError, DesignacionesService
from resoluciones_respaldos import escrituras as RE
from resoluciones_respaldos import rules as RR
from resoluciones_respaldos.lecturas import opciones_dependencias_alta
from resoluciones_respaldos.service import (ACTION_WRITE, MSG_PDF_INVALIDO, SPEC_GUARDAR, Archivo, ResolucionesError,
                                            ResolucionesService, WriterSpec)

# B10 ``COMPENSATIONS["_eliminar_acto_recien_creado_v267"]`` = ``documentos.write`` (legacy_write_actions.py l. 261);
# B12H ``entity_type_for`` -> "acto_administrativo" (contiene "acto"), ``_entity_param`` -> ``documento_id``.
SPEC_COMPENSAR = WriterSpec(RE.W_COMPENSAR_ALTA_V267, ACTION_WRITE, "acto_administrativo", "documento_id")

# Textos literales del formulario en linea (l. 54567-54640).
TITULO = "Cargar un nuevo acto al repositorio"
CAPTION = ("El acto se guardará en **Resoluciones y respaldos** y, al confirmar la operación, quedará vinculado al "
           "registro correspondiente. El PDF es opcional y puede adjuntarse después. Categoría: **{categoria}**.")
HELP_DEPENDENCIA = "El catálogo de dependencias se administra en Resoluciones y respaldos → Dependencias."
MSG_SIN_DEPENDENCIAS = "No hay dependencias emisoras activas. Primero cargá una en Resoluciones y respaldos → Dependencias."
TIPOS_CON_DEPENDENCIA = {"Resolución", "Disposición"}
ERR_DEPENDENCIA = "Seleccioná la dependencia emisora."
ERR_NUMERO = "Completá el número del acto administrativo."
ERR_PDF_GRANDE = "El PDF supera 50 MB."
PREFIX_ERRORES = "No se puede crear el acto administrativo: "
MSG_VALOR_INVALIDO = "Uno de los valores enviados no es válido para este formulario."
MSG_SELECCION_INVALIDA = "La selección no corresponde a las filas mostradas. Actualizá la pantalla."


def _texto(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise DesignacionesError(422, "INVALID", MSG_VALOR_INVALIDO)
    return value


def _desde_resoluciones(exc: ResolucionesError) -> DesignacionesError:
    return DesignacionesError(exc.status, exc.code, exc.message, exc.error_class)


class _Puerto:
    """``designaciones.service.ActoNuevo`` ligado a la sesion, a los datos del formulario en linea y al PDF."""

    def __init__(self, resoluciones: ResolucionesService, record: SessionRecord, datos: Any,
                 archivo: Optional[Archivo]):
        self.resoluciones, self.record, self.datos, self.archivo = resoluciones, record, datos, archivo

    def _payload(self) -> dict:
        """El ``dict`` que devuelve ``_render_nuevo_acto_inline_v267``, armado y validado en el servidor."""
        d = self.datos if isinstance(self.datos, dict) else {}
        tipo = d.get("tipo_documento")
        if tipo not in RR.TIPOS_DOCUMENTO:
            raise DesignacionesError(422, "INVALID", MSG_VALOR_INVALIDO)
        numero = _texto(d.get("numero")).strip()
        try:
            fecha = date.fromisoformat(str(d.get("fecha")))
        except (TypeError, ValueError):
            raise DesignacionesError(422, "INVALID", MSG_VALOR_INVALIDO) from None
        titulo = _texto(d.get("titulo")).strip()
        detalle = _texto(d.get("detalle")).strip()
        observaciones = _texto(d.get("observaciones")).strip()
        dep_raw = d.get("dependencia_id")
        dependencia_id, dependencia_nombre = None, ""
        if dep_raw is not None:
            if isinstance(dep_raw, bool) or not isinstance(dep_raw, int) or dep_raw <= 0:
                raise DesignacionesError(422, "INVALID", MSG_VALOR_INVALIDO)
            par = next((v for v in self._dependencias().values() if v[0] == dep_raw), None)
            if par is None:
                raise DesignacionesError(409, "SELECCION", MSG_SELECCION_INVALIDA)
            dependencia_id, dependencia_nombre = par
        contenido = self.archivo.contenido if self.archivo is not None else b""
        errores = []
        if tipo in TIPOS_CON_DEPENDENCIA and dependencia_id is None:
            errores.append(ERR_DEPENDENCIA)
        if tipo in TIPOS_CON_DEPENDENCIA and not numero:
            errores.append(ERR_NUMERO)
        if contenido and len(contenido) > RR.MAX_PDF_BYTES:
            errores.append(ERR_PDF_GRANDE)
        if errores:  # _resolver_acto_contextual_v267 l. 54731: antes de escribir, sin evento B12H
            raise DesignacionesError(422, "ACTO_INVALIDO", PREFIX_ERRORES + " ".join(errores))
        if contenido and not RR.es_pdf(contenido):  # hardening NEXT (D-AK2)
            raise DesignacionesError(422, "PDF_INVALIDO", MSG_PDF_INVALIDO)
        return {"tipo_documento": tipo, "numero": numero, "fecha": fecha, "dependencia_id": dependencia_id,
                "dependencia_nombre": dependencia_nombre, "titulo": titulo, "detalle": detalle,
                "observaciones": observaciones,
                "archivo_nombre": self.archivo.nombre if self.archivo is not None else "",
                "archivo_mime": self.archivo.mime if self.archivo is not None else "",
                "contenido": bytes(contenido or b""), "errores": []}

    def _dependencias(self) -> dict:
        res = self.resoluciones
        try:
            return res._read(res.scope(self.record), lambda lec: opciones_dependencias_alta(
                lec.dependencias(solo_activas=True)))
        except ResolucionesError as exc:
            raise _desde_resoluciones(exc) from None

    def crear(self, categoria: str, periodo_id: int, referencia_texto: str, titulo_sugerido: str,
              detalle_sugerido: str, observaciones_sugeridas: str) -> int:
        config = {"modo": "nuevo", "documento_id": None, "payload": self._payload()}
        res = self.resoluciones
        try:
            documento_id, _creado = res._op(self.record, res.scope(self.record), SPEC_GUARDAR,
                                             lambda u: RE.resolver_acto_contextual_v267(
                                                 u, config, periodo_id, categoria, referencia_texto, titulo_sugerido,
                                                 detalle_sugerido, observaciones_sugeridas))
        except ResolucionesError as exc:
            raise _desde_resoluciones(exc) from None
        return int(documento_id)

    def compensar(self, documento_id: int) -> None:
        res = self.resoluciones
        res._op(self.record, res.scope(self.record), SPEC_COMPENSAR,
                lambda u: RE.eliminar_acto_recien_creado_v267(u, documento_id), entity_raw=documento_id)


class ActoContextualService:
    """Coordina el alta / modificacion de Designaciones con el acto nuevo del owner documental."""

    def __init__(self, designaciones: DesignacionesService, resoluciones: ResolucionesService):
        self.designaciones, self.resoluciones = designaciones, resoluciones

    def contexto(self, record: SessionRecord) -> dict:
        """Opciones del formulario en linea: tipos, dependencias emisoras activas (l. 54579-54590, mismas etiquetas
        que el certificado para nombres repetidos), textos, tope del PDF y la categoria que el formulario muestra por
        operacion (alta: "Designación docente"; modificacion: ``_categoria_respaldo_movimiento_v263(tipo_cambio)``, la
        regla del owner).  Lectura (``documentos.read``)."""
        res = self.resoluciones
        try:
            scope = res.reader(record)
            mapa = res._read(scope, lambda lec: opciones_dependencias_alta(lec.dependencias(solo_activas=True)))
        except ResolucionesError as exc:
            raise _desde_resoluciones(exc) from None
        return {"titulo": TITULO, "caption": CAPTION, "tipos": RR.TIPOS_DOCUMENTO,
                "tipos_con_dependencia": sorted(TIPOS_CON_DEPENDENCIA),
                "dependencias": [{"etiqueta": k, "id": v[0]} for k, v in mapa.items()],
                "sin_dependencias": MSG_SIN_DEPENDENCIAS if len(mapa) == 1 else "",
                "help_dependencia": HELP_DEPENDENCIA, "max_pdf_bytes": RR.MAX_PDF_BYTES,
                "pdf_grande": ERR_PDF_GRANDE, "categoria_alta": "Designación docente",
                "categorias": {t: DR.categoria_respaldo_movimiento(t) for t in DR.TIPOS_CAMBIO}}

    def puerto(self, record: SessionRecord, datos: dict, archivo: Optional[Archivo]) -> Optional[_Puerto]:
        """Puerto ``ActoNuevo`` si la operacion pidio "Cargar un nuevo acto ahora" (alta, modificacion y, desde 6A-B3,
        registrar designacion desde Docentes)."""
        acto = datos.get("acto") if isinstance(datos, dict) else None
        if not isinstance(acto, dict) or acto.get("modo") != "nuevo":
            return None
        return _Puerto(self.resoluciones, record, acto.get("payload"), archivo)

    def alta(self, record: SessionRecord, datos: dict, archivo: Optional[Archivo]) -> dict:
        return self.designaciones.alta(record, datos, acto_nuevo=self.puerto(record, datos, archivo))

    def modificar(self, record: SessionRecord, datos: dict, archivo: Optional[Archivo]) -> dict:
        return self.designaciones.modificar(record, datos, acto_nuevo=self.puerto(record, datos, archivo))


__all__ = ["ActoContextualService", "SPEC_COMPENSAR"]
