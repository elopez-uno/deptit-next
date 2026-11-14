"""E4-08 — Docentes → registrar una designacion desde la pagina Docentes (pestaña "➕ Registrar docente").

Certificado (B13-FIX02, entry l. 59947-60392).  Tres caminos, cada uno con su boton:
1. "Seleccionar un docente de la base maestra y registrar su designación en el período actual" (l. 60086-60122):
   docentes propios de ``get_docentes_base_maestra_sin_designacion_periodo(periodo_abierto)`` (l. 4792); formulario
   "Nueva designación para el período"; "💾 Registrar designación y reincorporar al período" ->
   ``guardar_designacion`` + ``registrar_movimiento("Alta de designación", ..., "Reincorporación desde la base
   maestra al período {P} - {cargo} - {dedicación} - {horas} hs - {tipo}[ - Funciones no docentes: …]")``;
2. alta de docente con un CUIL de otro departamento -> "Registrar como propio y cargar una designación en el período
   actual" (l. 60309-60356): ``formulario_designacion_registro_docente`` (l. 23894); "💾 Registrar como propio y
   guardar designación" -> ``_guardar_docente_local_desde_registro_existente(fila, "Propio", "Docente compartido:
   mismo CUIL registrado en {origen}.")`` (solo si no hay ficha local) + ``guardar_designacion`` +
   ``registrar_movimiento("Alta de designación", ..., "Se incorporó como docente propio/compartido con cargo X.")``;
3. alta de docente con un CUIL ya local (l. 60358-60392): mismo formulario; "💾 Registrar una nueva designación para
   este docente" -> SOLO ``guardar_designacion`` (el certificado no registra movimiento en este camino).

Arquitectura (D-E4-01): Docentes no escribe designaciones.  Esta composicion resuelve la pantalla con los contratos
publicos de los owners (``DocentesService.overview`` / ``verificar_cuil`` / ``cuil_existente``,
``DesignacionesService.contexto_desde_docentes`` / ``duplicado``) y delega las escrituras: el docente compartido en
``DocentesService.guardar_propio_desde_existente`` (``guardar_docente``, ``docentes.write``) y la designacion y su
movimiento en ``DesignacionesService.alta_desde_docentes`` (``guardar_designacion`` ``designaciones.write``,
``registrar_movimiento`` ``movimientos.write``), con los COMMITs separados del certificado (D-E4-06).  Ningun owner
importa esta capa; Docentes y Designaciones no se importan entre si.

6A-B3 (aceptacion): acto administrativo opcional en los tres caminos, con la MISMA semantica que el alta de
Designaciones (``data["acto"]``: existente / pendiente por JSON; "Cargar un nuevo acto ahora" por multipart con el
puerto E4-07 ``ActoContextualService.puerto``).  El vinculo real (``documento_id``) y la compensacion los hace
``DesignacionesService.alta_desde_docentes`` con los writers ya certificados; sin ``acto`` el flujo es el certificado.
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from auth.service import SessionRecord
from designaciones import rules as DR
from designaciones.service import SUFIJO_ALTA_ACTO_NUEVO, DesignacionesError, DesignacionesService
from docentes.service import MSG_DOCENTE_NO_ENCONTRADO, MSG_VALOR_INVALIDO, DocentesError, DocentesService
from periodos.service import MSG_DB_READ, MSG_STALE

CAMINO_BASE = "reincorporar"
CAMINO_CUIL_EXISTENTE = "cuil_existente"
CAMINO_CUIL_LOCAL = "cuil_local"

# Textos certificados de la pagina (entry l. 60060-60122, 60309-60392).
MSG_BASE_SIN_PERIODO = "No hay un período abierto. Abrí o creá el período actual antes de reincorporar docentes."
MSG_BASE_SIN_CUIL = "El docente seleccionado no tiene un CUIL válido."
MSG_BASE_OK = "Docente reincorporado y designación registrada correctamente."
MSG_EXISTENTE_SIN_PERIODO = "No hay un período abierto para la designación."
MSG_EXISTENTE_OK = "Docente propio/compartido y designación registrados correctamente."
MSG_LOCAL_SIN_PERIODO = "No hay un período abierto."
MSG_LOCAL_OK = "Designación registrada correctamente."
MSG_SELECCION_INVALIDA = "La selección no corresponde a las filas mostradas. Actualizá la pantalla."
CAMPOS_DESIGNACION = ("cargo", "dedicacion", "tipo_designacion", "ad_honorem", "fecha_desde", "fecha_hasta", "estado",
                      "funcion_no_docente", "texto_funcion_no_docente", "observaciones", "abierto_huella")


def _texto(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise DocentesError(422, "INVALID", MSG_VALOR_INVALIDO)
    return value


def _como_docentes(exc: DesignacionesError) -> DocentesError:
    return DocentesError(exc.status, exc.code, exc.message, exc.error_class)


def _stale_docentes(fn: Callable[[], None]) -> Callable[[], None]:
    """La verificacion B12I corre dentro del writer de Docentes: su error es el del owner que escribe."""
    def check() -> None:
        try:
            fn()
        except DesignacionesError as exc:
            raise _como_docentes(exc) from None
    return check


def detalle_reincorporacion(abierto: dict, v: dict) -> str:
    """Detalle del movimiento del camino 1 (l. 60106-60109)."""
    texto = (f"Reincorporación desde la base maestra al período {abierto['nombre']} - {v['cargo']} - "
             f"{v['dedicacion']} - {v['horas']} hs - {v['tipo']}")
    if v["funcion"]:
        texto += f" - Funciones no docentes: {DR.texto_funcion_limpio(v['texto'])}"
    return texto


def detalle_propio_compartido(_abierto: dict, v: dict) -> str:
    """Detalle del movimiento del camino 2 (l. 60351)."""
    return f"Se incorporó como docente propio/compartido con cargo {v['cargo']}."


def reincorporables(docentes: list[dict], cuiles_periodo: set) -> list[dict]:
    """``get_docentes_base_maestra_sin_designacion_periodo`` (l. 4792) sobre las lecturas de los owners: docentes no
    prestados de la base maestra sin ninguna designacion en el periodo, ordenados por apellido, nombres, nombre
    completo y CUIL (vacios al final)."""
    filas = [d for d in docentes if str(d.get("tipo_docente") or "Propio").strip() != "Prestado"
             and str(d.get("cuil") or "").strip() not in cuiles_periodo]

    def clave(d: dict) -> tuple:
        out = []
        for col in ("apellido", "nombres", "nombre_completo", "cuil"):
            valor = d.get(col)
            vacio = valor is None or (isinstance(valor, float) and valor != valor)
            out += [vacio, "" if vacio else str(valor)]
        return tuple(out)
    return sorted(filas, key=clave)


class RegistroDesignacionService:
    """Coordina la pestaña "Registrar docente" de Docentes con el alta de Designaciones."""

    def __init__(self, docentes: DocentesService, designaciones: DesignacionesService, acto_contextual: Any = None):
        self.docentes, self.designaciones, self.acto_contextual = docentes, designaciones, acto_contextual

    def _designaciones(self, fn: Callable[[], Any]) -> Any:
        try:
            return fn()
        except DesignacionesError as exc:
            raise _como_docentes(exc) from None

    def _base(self, record: SessionRecord) -> tuple[dict, dict]:
        overview = self.docentes.overview(record)  # docentes.read + base maestra efectiva
        ctx = self._designaciones(lambda: self.designaciones.contexto_desde_docentes(record))
        return overview, ctx

    def contexto(self, record: SessionRecord) -> dict:
        """Pantalla del camino 1 y catalogos del formulario de designacion (lectura)."""
        overview, ctx = self._base(record)
        candidatos = reincorporables(overview["docentes"], ctx["cuiles_periodo"]) if ctx["abierto"] else []
        return {"abierto": ctx["abierto"], "abierto_huella": ctx["abierto_huella"], "catalogos": ctx["catalogos"],
                "reincorporables": [{k: d.get(k) for k in ("nombre_completo", "cuil", "legajo", "titulo", "estado",
                                                           "huella")} for d in candidatos],
                "puede_escribir": bool(overview["permisos"]["puede_escribir"])}

    def duplicado(self, record: SessionRecord, data: dict) -> dict:
        """Aviso "Mientras completabas el formulario…" del camino 1 (``existe_designacion_duplicada``)."""
        datos = {k: data.get(k) for k in CAMPOS_DESIGNACION if k in data}
        datos["cuil"] = _texto(data.get("cuil"))
        return self._designaciones(lambda: self.designaciones.duplicado(record, datos))

    def registrar(self, record: SessionRecord, data: dict, archivo: Any = None, acto_nuevo: bool = False) -> dict:
        """``acto_nuevo`` solo desde la ruta multipart: como en Designaciones, por JSON el modo "nuevo" se rechaza."""
        if not isinstance(data, dict):
            raise DocentesError(422, "INVALID", MSG_VALOR_INVALIDO)
        camino = data.get("camino")
        datos = {k: data.get(k) for k in CAMPOS_DESIGNACION if k in data}
        puerto = None
        if acto_nuevo and self.acto_contextual is not None:
            puerto = self.acto_contextual.puerto(record, data, archivo)
        acto = {"acto": data.get("acto"), "acto_nuevo": puerto}
        if camino == CAMINO_BASE:
            return self._reincorporar(record, data, datos, acto)
        if camino == CAMINO_CUIL_EXISTENTE:
            return self._cuil_existente(record, data, datos, acto)
        if camino == CAMINO_CUIL_LOCAL:
            return self._cuil_local(record, data, datos, acto)
        raise DocentesError(422, "INVALID", MSG_VALOR_INVALIDO)

    @staticmethod
    def _resultado(mensaje: str, r: dict) -> dict:
        return {"mensaje": mensaje + (SUFIJO_ALTA_ACTO_NUEVO if r.get("acto_creado") else ""), "tono": "success",
                "avisos": r["avisos"], "id": r["id"], "acto_documento_id": r.get("acto_documento_id")}

    # ------------------------------------------------------------------ camino 1
    def _reincorporar(self, record: SessionRecord, data: dict, datos: dict, acto: dict) -> dict:
        cuil_sel, huella = _texto(data.get("cuil")), data.get("huella")
        overview, ctx = self._base(record)
        if ctx["abierto"] is None:
            raise DocentesError(409, "NO_OPEN_PERIOD", MSG_BASE_SIN_PERIODO)
        fila = next((d for d in reincorporables(overview["docentes"], ctx["cuiles_periodo"])
                     if str(d.get("cuil") or "") == cuil_sel), None)
        if fila is None:
            raise DocentesError(404, "NOT_FOUND", MSG_DOCENTE_NO_ENCONTRADO)
        cuil = str(fila.get("cuil") or "").strip()
        if not cuil:
            raise DocentesError(422, "SIN_CUIL", MSG_BASE_SIN_CUIL)

        def stale() -> None:  # B12I capa U: la fila de la base maestra que el usuario vio sigue igual y sin designar
            try:
                o, c = self._base(record)
            except DocentesError:
                raise DesignacionesError(503, "FRESH_READ", MSG_DB_READ, "FreshReadError") from None
            actual = next((d for d in reincorporables(o["docentes"], c["cuiles_periodo"])
                           if str(d.get("cuil") or "") == cuil_sel), None)
            if actual is None or not isinstance(huella, str) or actual.get("huella") != huella:
                raise DesignacionesError(409, "STALE", f"{MSG_STALE} [B12I: get_docentes_base_maestra_sin_designacion_"
                                                       "periodo]", "StaleDecisionError")

        r = self._designaciones(lambda: self.designaciones.alta_desde_docentes(
            record, datos, cuil=cuil, nombre=str(fila.get("nombre_completo") or "").strip(),
            detalle_movimiento=detalle_reincorporacion, verificar_duplicada=True, msg_sin_periodo=MSG_BASE_SIN_PERIODO,
            stale=stale, **acto))
        return self._resultado(MSG_BASE_OK, r)

    # ------------------------------------------------------------------ camino 2
    def _cuil_existente(self, record: SessionRecord, data: dict, datos: dict, acto: dict) -> dict:
        sel = self.docentes.cuil_existente(record, data.get("cuil"), data.get("departamento_origen"),
                                           data.get("cuil_alta"))
        r = self._designaciones(lambda: self.designaciones.alta_desde_docentes(
            record, datos, cuil=sel["canonico"], nombre=sel["nombre"], detalle_movimiento=detalle_propio_compartido,
            verificar_duplicada=False, msg_sin_periodo=MSG_EXISTENTE_SIN_PERIODO,
            antes_de_escribir=lambda stale: self.docentes.guardar_propio_desde_existente(
                record, sel, stale=_stale_docentes(stale)), **acto))
        return self._resultado(MSG_EXISTENTE_OK, r)

    # ------------------------------------------------------------------ camino 3
    def _cuil_local(self, record: SessionRecord, data: dict, datos: dict, acto: dict) -> dict:
        check = self.docentes.verificar_cuil(record, data.get("cuil_alta"))
        local = check.get("local")
        if check.get("otros_departamentos") or local is None:
            raise DocentesError(409, "SELECCION", MSG_SELECCION_INVALIDA)
        cuil = str(local.get("cuil") or check.get("cuil_limpio") or "").strip()
        r = self._designaciones(lambda: self.designaciones.alta_desde_docentes(
            record, datos, cuil=cuil, nombre=str(local.get("nombre") or ""), detalle_movimiento=None,
            verificar_duplicada=False, msg_sin_periodo=MSG_LOCAL_SIN_PERIODO, **acto))
        return self._resultado(MSG_LOCAL_OK, r)


__all__ = ["RegistroDesignacionService", "reincorporables"]
