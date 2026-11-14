"""E4-09 — Docentes → "Carga rápida integral de docentes y designaciones" (pestaña "📥 Carga rápida").

Certificado (B13-FIX02, entry l. 61278-61652).  "Integral" = UN Excel con hojas Docentes y Designaciones: primero se
registran los docentes y despues sus designaciones, vinculados por CUIL.
- Modelo: ``generar_excel_integral_docentes_designaciones`` (cadena efectiva l. 17696 -> v230 l. 45899 -> v199
  l. 45953), filas preformateadas configurables (Docentes 1000, Designaciones 5000; minimo 20, maximo 1.048.575).
- Lectura: ``leer_excel_integral_docentes_designaciones`` (l. 17255): hojas "Docentes" y "Designaciones" (nombre
  normalizado), filas vacias descartadas, Periodo y Estado de cada designacion derivados de Fecha desde / Fecha hasta
  (v230/v237), horas desde la dedicacion (v160).
- Revision: ``analizar_carga_integral_docentes_designaciones`` (l. 17408): docentes OK / EXISTENTE / ERROR,
  designaciones OK / ADVERTENCIA / OMITIR (duplicada en el archivo o ya en la base, por identidad estable v223 sin el
  estado) / ERROR.  Con cualquier ERROR no se carga nada.
- Escritura (boton "📥 Cargar docentes y designaciones del Excel" + confirmacion), SIN atomicidad global, con exito
  parcial y errores acumulados por fila, en este orden:
  1. docentes OK: ``guardar_docente`` + ``registrar_movimiento("Alta de docente")`` por docente;
  2. foto FISICA anterior ``_snapshot_designaciones_integral_v220`` de los periodos involucrados;
  3. designaciones OK/ADVERTENCIA que no estaban en la foto: ``_guardar_fila_designacion_integral_v220``
     (``guardar_designacion``) por fila; las que ya estaban -> "Ya existía";
  4. foto FISICA posterior: por cada fila nueva verificada, "Creada" + UN ``registrar_movimiento("Alta de designación")``
     por identidad; si no aparecio -> "No guardada" (nunca se fuerza una segunda insercion);
  5. solo si se pidio: docentes EXISTENTE con ``_mezclar_docente_existente_excel_v247`` (celdas vacias conservan el
     dato) -> ``actualizar_docente`` + ``registrar_movimiento("Actualización de docente existente")``.
  Resultado: mensaje con los contadores, tabla "Verificación contra la base de datos" y hasta 50 errores.

Composicion (D-E4-01, D-E4-06): la LECTURA (modelo, lector, revision, identidad v220, fotos, mezcla v247) es texto
LITERAL del certificado (``carga_integral_motor/complemento.py``, generado por
``tools_generar_complemento_carga_integral.py``) ejecutado sobre el motor de lectura de Analisis en una transaccion READ
ONLY con el ambito de la sesion.  Las ESCRITURAS son contratos de los owners, cada writer con su B10/B12H y su COMMIT:
``DocentesService.alta_desde_carga_integral`` / ``actualizar_desde_carga_integral`` y
``DesignacionesService.guardar_fila_integral`` / ``movimiento_alta_integral``.  Ningun owner importa esta capa.
Hardening NEXT: firma XLSX real (no solo el nombre), tope de transporte (multipart sin disco), la revision se rehace en
el servidor al cargar y debe coincidir con la que el usuario confirmo (huella), y un DENIED de B10 detiene la carga.
"""
from __future__ import annotations

import functools
import hashlib
import json
import logging
from contextlib import AbstractContextManager
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Optional

import pandas as pd
from psycopg import Connection

from analisis.motor import entorno
from auth import policy
from designaciones.service import DesignacionesError, DesignacionesService
from docentes import rules as docentes_rules
from docentes.carga import normalizar_columna_generica
from docentes.service import ACTION_READ, DocentesError, DocentesService
from periodos.service import MSG_DB_READ, MSG_STALE, denial_message
import uploads

from .carga_integral_motor import metadata as complemento_meta

log = logging.getLogger("deptit_next.integraciones")

FILAS_DOCENTES, FILAS_DESIGNACIONES, FILAS_MIN, FILAS_MAX = 1000, 5000, 20, 1048575
NOMBRE_MODELO = "modelo_integral_docentes_designaciones.xlsx"
MAX_EXCEL = 50 * 1024 * 1024
COLUMNAS_DOCENTES = ["fila", "cuil", "apellido", "nombres", "legajo", "antiguedad_anios", "nivel_posgrado_salarial",
                     "estado", "accion", "motivo"]
COLUMNAS_DESIGNACIONES = ["fila", "periodo", "docente", "cuil", "cargo", "dedicacion", "horas", "tipo_designacion",
                          "numero_resolucion", "ad_honorem", "fecha_desde", "fecha_hasta", "estado", "accion", "motivo"]
# Textos certificados (entry l. 61278-61652).
PREFIX_MODELO = "No se pudo generar el Excel integral: "
PREFIX_LECTURA = "No se pudo leer o validar el Excel integral: "
MSG_CON_ERRORES = "Corregí los errores indicados en el Excel y volvé a subirlo. No se guardó ningún dato."
MSG_CONFIRMAR = "Primero confirmá que revisaste el archivo."
MSG_YA_EXISTIA = ("La misma designación ya estaba en la base al iniciar la carga (también se controlan períodos "
                  "históricos).")
MSG_NO_GUARDADA = ("La fila estaba marcada para crear pero no apareció en la base después del intento de alta. No se "
                   "forzó una segunda inserción para evitar duplicados.")
MSG_SIN_FICHA = "No se encontró la ficha actual del docente para aplicar la actualización parcial."
# Textos propios de NEXT (hardening; no existen en Streamlit, donde el uploader filtra por extension).
MSG_NO_XLSX = "El archivo debe ser un Excel .xlsx que conserve las hojas Docentes y Designaciones."
MSG_SIN_ARCHIVO = "Subí el Excel integral completado."
MSG_ARCHIVO_GRANDE = "El archivo supera 50 MB."
MSG_FILAS = "La cantidad de filas preformateadas debe ser un entero entre 20 y 1048575."
MSG_LECTURA_GENERICA = "el archivo no es un Excel válido o no se pudo procesar."


@functools.lru_cache(maxsize=1)
def _codigo_complemento():
    ruta = Path(__file__).resolve().parent / "carga_integral_motor" / "complemento.py"
    return compile(ruta.read_text(encoding="utf-8"), str(ruta), "exec")


def _celda(valor: Any) -> Any:
    if valor is None or (isinstance(valor, float) and valor != valor):
        return None
    if hasattr(valor, "item"):  # numpy
        return valor.item()
    if isinstance(valor, (date, datetime, pd.Timestamp)):
        return str(valor)
    return valor


def _filas(df: pd.DataFrame, columnas: list[str]) -> list[dict]:
    if df is None or df.empty:
        return []
    cols = [c for c in columnas if c in df.columns]
    return [{c: _celda(r.get(c)) for c in cols} for r in df.to_dict("records")]


def _cuenta(df: pd.DataFrame, *valores: str) -> int:
    if df is None or df.empty or "estado_validacion" not in df.columns:
        return 0
    return int(df["estado_validacion"].isin(list(valores)).sum())


class CargaIntegralService:
    def __init__(self, pool, docentes: DocentesService, designaciones: DesignacionesService, *,
                 today: Callable[[], date] = date.today, now: Callable[[], datetime] = datetime.now,
                 transaction: Optional[Callable[[], AbstractContextManager[Connection]]] = None):
        self.docentes, self.designaciones = docentes, designaciones
        self.today, self.now = today, now
        self._transaction = transaction or (lambda: pool.connection(timeout=5))

    # ------------------------------------------------------------------ lectura certificada (motor READ ONLY)
    def _reader(self, record) -> Any:
        scope = self.docentes.scope(record)
        decision = policy.decide(policy.actor_from_session(record.user, record.scope), ACTION_READ)
        if not decision.allowed:
            raise DocentesError(403, "DENIED", denial_message(decision, ACTION_READ))
        return scope

    def _motor(self, record, scope, fn: Callable[[dict], Any]) -> Any:
        usuario = {"email": record.user.get("email"), "rol": record.user.get("rol"),
                   "departamento_nombre": record.user.get("departamento_nombre") or ""}
        try:
            with self._transaction() as conn:
                conn.execute("SET TRANSACTION READ ONLY")
                ns = entorno.construir(conn, scope.institution_id, scope.department_id, usuario=usuario,
                                       hoy=self.today, ahora=self.now)
                exec(_codigo_complemento(), ns)
                # B12A (entry l. 59086, antes de la pagina): el normalizador re-enlazado "corrige ... la carga integral".
                ns["_nivel_posgrado_salarial_normalizado_v256"] = docentes_rules.nivel_posgrado_salarial_normalizado
                # Etapa 5 / Tanda B (B4): el normalizador certificado no reconocia "Años antigüedad" ni "N° resolución"
                # de SU PROPIO modelo (no translitera ü ni quita °): se usa el normalizador NEXT endurecido.
                ns["normalizar_columna_generica"] = normalizar_columna_generica
                for nombre in complemento_meta.WRITERS_NEGOCIO:
                    ns[nombre] = entorno._bloqueado(nombre)
                for nombre in complemento_meta.TAREAS_SISTEMA:
                    ns[nombre] = (lambda *a, **k: None)
                return fn(ns)
        except DocentesError:
            raise
        except Exception as exc:
            log.error("carga_integral: lectura fallida: %s", type(exc).__name__)
            raise DocentesError(503, "DB_READ", MSG_DB_READ) from None

    @staticmethod
    def _filas_modelo(valor: Any, default: int) -> int:
        if valor is None:
            return default
        if isinstance(valor, bool) or not isinstance(valor, int) or not FILAS_MIN <= valor <= FILAS_MAX:
            raise DocentesError(422, "INVALID", MSG_FILAS)
        return valor

    def modelo(self, record, data: dict) -> tuple[bytes, str]:
        """"📥 Descargar Excel integral de docentes y designaciones" (l. 61306-61324)."""
        scope = self._reader(record)
        fd = self._filas_modelo((data or {}).get("filas_docentes"), FILAS_DOCENTES)
        fe = self._filas_modelo((data or {}).get("filas_designaciones"), FILAS_DESIGNACIONES)

        def read(ns: dict) -> bytes:
            try:
                return ns["generar_excel_integral_docentes_designaciones"](
                    periodo_default=ns["get_periodo_abierto"](), filas_docentes=fd, filas_designaciones=fe)
            except Exception as exc:
                log.error("carga_integral: modelo fallido: %s", type(exc).__name__)
                raise DocentesError(503, "MODELO", PREFIX_MODELO + MSG_DB_READ) from None
        return self._motor(record, scope, read), NOMBRE_MODELO

    @staticmethod
    def _contenido(archivo: Any) -> bytes:
        if archivo is None or not getattr(archivo, "contenido", b""):
            raise DocentesError(422, "SIN_ARCHIVO", MSG_SIN_ARCHIVO)
        contenido = archivo.contenido
        if len(contenido) > MAX_EXCEL:
            raise DocentesError(413, "TOO_LARGE", MSG_ARCHIVO_GRANDE)
        if not str(archivo.nombre or "").lower().endswith(".xlsx") or uploads.problema_xlsx(contenido) is not None:
            raise DocentesError(422, "NO_XLSX", MSG_NO_XLSX)  # 6A-B1: estructura OOXML/ZIP validada
        return bytes(contenido)

    @staticmethod
    def _revisar(ns: dict, contenido: bytes) -> dict:
        """l. 61345-61376: lector + revision certificados sobre el mismo periodo abierto."""
        abierto = ns["get_periodo_abierto"]()
        try:
            df_doc, df_des, avisos = ns["leer_excel_integral_docentes_designaciones"](contenido,
                                                                                     periodo_default=abierto)
            prev_doc, prev_des = ns["analizar_carga_integral_docentes_designaciones"](df_doc, df_des,
                                                                                    periodo_default=abierto)
        except ValueError as exc:  # mensajes certificados del lector (hojas faltantes) y de pandas / openpyxl
            texto = str(exc)
            if texto.startswith("El archivo debe contener una hoja llamada"):
                raise DocentesError(422, "LECTURA", PREFIX_LECTURA + texto) from None
            raise DocentesError(422, "LECTURA", PREFIX_LECTURA + MSG_LECTURA_GENERICA) from None
        except DocentesError:
            raise
        except Exception as exc:
            log.error("carga_integral: lectura del Excel fallida: %s", type(exc).__name__)
            raise DocentesError(422, "LECTURA", PREFIX_LECTURA + MSG_LECTURA_GENERICA) from None
        return {"abierto": abierto, "df_doc": df_doc, "df_des": df_des, "avisos": list(avisos),
                "prev_doc": prev_doc, "prev_des": prev_des}

    @staticmethod
    def _vista(r: dict) -> dict:
        prev_doc, prev_des = r["prev_doc"], r["prev_des"]
        errores = _cuenta(prev_doc, "ERROR") + _cuenta(prev_des, "ERROR")
        vista = {
            "avisos": r["avisos"],
            "filas_docentes": int(len(r["df_doc"])), "filas_designaciones": int(len(r["df_des"])),
            "docentes_nuevos": _cuenta(prev_doc, "OK"), "docentes_existentes": _cuenta(prev_doc, "EXISTENTE"),
            "designaciones_nuevas": _cuenta(prev_des, "OK", "ADVERTENCIA"),
            "designaciones_omitidas": _cuenta(prev_des, "OMITIR"),
            "designaciones_detectadas": int(len(prev_des)) if prev_des is not None else 0,
            "errores_docentes": _cuenta(prev_doc, "ERROR"), "errores_designaciones": _cuenta(prev_des, "ERROR"),
            "errores": errores, "sin_errores": errores == 0,
            "docentes": _filas(prev_doc, COLUMNAS_DOCENTES), "designaciones": _filas(prev_des, COLUMNAS_DESIGNACIONES),
        }
        vista["huella"] = hashlib.sha256(json.dumps(vista, sort_keys=True, default=str).encode()).hexdigest()
        return vista

    def previsualizar(self, record, data: dict, archivo: Any) -> dict:
        """Revision previa (l. 61345-61451): sin escrituras."""
        scope = self._reader(record)
        contenido = self._contenido(archivo)
        return self._motor(record, scope, lambda ns: self._vista(self._revisar(ns, contenido)))

    # ------------------------------------------------------------------ escritura (contratos de los owners)
    @staticmethod
    def _detener_si_denegado(exc: Exception) -> None:
        if getattr(exc, "status", None) == 403:
            raise DocentesError(403, getattr(exc, "code", "DENIED"), exc.message) from None

    def ejecutar(self, record, data: dict, archivo: Any) -> dict:
        """"📥 Cargar docentes y designaciones del Excel" (l. 61456-61646)."""
        scope = self._reader(record)
        contenido = self._contenido(archivo)
        data = data if isinstance(data, dict) else {}

        def revisar(ns: dict) -> dict:
            r = self._revisar(ns, contenido)
            r["vista"] = self._vista(r)
            l, lc = ns["limpiar_texto_tabla"], ns["limpiar_cuil"]
            clave = ns["_clave_designacion_integral_v220"]
            r["docentes_ok"] = [dict(x) for x in r["prev_doc"].to_dict("records")
                                if x.get("estado_validacion", "") == "OK"] if not r["prev_doc"].empty else []
            r["existentes"] = [dict(x) for x in r["prev_doc"].to_dict("records")
                               if x.get("estado_validacion", "") == "EXISTENTE"] if not r["prev_doc"].empty else []
            crear = r["prev_des"][r["prev_des"].get("estado_validacion", pd.Series(index=r["prev_des"].index, dtype=str))
                                  .isin(["OK", "ADVERTENCIA"])].copy() if not r["prev_des"].empty else pd.DataFrame()
            filas = []
            for _, row in crear.iterrows():
                cuil_row = l(row.get("_cuil_guardado", "")) or lc(row.get("cuil", ""))
                filas.append({"row": row.to_dict(), "clave": clave(row), "cuil": cuil_row,
                              "nombre": l(row.get("docente", "")) or cuil_row})
            r["crear"] = filas
            periodos = []
            for f in filas:  # l. 61498-61503
                try:
                    periodos.append(int(f["row"].get("_periodo_id")))
                except Exception:
                    pass
            r["periodos"] = periodos
            return r

        r = self._motor(record, scope, revisar)
        vista = r["vista"]
        if not vista["sin_errores"]:
            raise DocentesError(409, "CON_ERRORES", MSG_CON_ERRORES)
        if data.get("confirmar") is not True:
            raise DocentesError(422, "CONFIRMAR", MSG_CONFIRMAR)
        if data.get("huella") != vista["huella"]:
            raise DocentesError(409, "STALE", f"{MSG_STALE} [B12I: analizar_carga_integral_docentes_designaciones]")
        abierto = r["abierto"]
        per_id = int(abierto["id"]) if abierto else None
        nuevos = actualizados = omitidos = 0
        errores: list[str] = []
        detalle: list[dict] = []

        # 1) docentes NUEVOS
        for fila in r["docentes_ok"]:
            try:
                self.docentes.alta_desde_carga_integral(record, fila, per_id)
                nuevos += 1
            except (DocentesError, DesignacionesError) as exc:
                self._detener_si_denegado(exc)
                errores.append(f"Docente fila {fila.get('fila', '')}: {exc.message}")

        # 2) foto FISICA anterior de todas las designaciones involucradas (despues de los docentes, como el certificado)
        antes = self._motor(record, scope, lambda ns: set(
            ns["_snapshot_designaciones_integral_v220"](r["periodos"]).keys()))

        def resultado(row: dict, texto: str, det: str) -> dict:
            return {"Fila": _celda(row.get("fila", "")), "Docente": row.get("docente", ""), "CUIL": row.get("cuil", ""),
                    "Período": row.get("periodo", ""), "Resultado": texto, "Detalle": det}

        for f in r["crear"]:
            row = f["row"]
            if f["clave"] in antes:
                detalle.append(resultado(row, "Ya existía", MSG_YA_EXISTIA))
                continue
            try:
                self.designaciones.guardar_fila_integral(record, {
                    "periodo_id": int(row.get("_periodo_id")), "cuil": f["cuil"], "cargo": row.get("cargo", ""),
                    "dedicacion": row.get("dedicacion", ""), "horas": int(row.get("horas", 0) or 0),
                    "tipo_designacion": row.get("tipo_designacion", ""), "ad_honorem": row.get("ad_honorem", "No"),
                    "fecha_desde": row.get("fecha_desde", ""), "fecha_hasta": row.get("fecha_hasta", ""),
                    "estado": row.get("estado", "Activa"), "observaciones": row.get("observaciones", ""),
                    "numero_resolucion": row.get("numero_resolucion", "")})
            except (DocentesError, DesignacionesError) as exc:
                self._detener_si_denegado(exc)
                errores.append(f"Designación fila {row.get('fila', '')}: {exc.message}")
                detalle.append(resultado(row, "Error", exc.message))

        # 4) verificacion FISICA posterior y movimientos (uno por identidad)
        despues = self._motor(record, scope, lambda ns: set(
            ns["_snapshot_designaciones_integral_v220"](r["periodos"]).keys()))
        creadas = 0
        con_movimiento: set = set()
        for f in r["crear"]:
            row = f["row"]
            if f["clave"] in antes:
                continue
            if f["clave"] in despues:
                creadas += 1
                detalle.append(resultado(row, "Creada", "Verificada en la base de datos."))
                if f["clave"] not in con_movimiento:
                    con_movimiento.add(f["clave"])
                    horas = int(row.get("horas", 0) or 0)
                    try:
                        self.designaciones.movimiento_alta_integral(
                            record, cuil=f["cuil"], nombre=f["nombre"],
                            detalle=f"{row.get('periodo', '')} - {row.get('cargo', '')} - {row.get('dedicacion', '')} "
                                    f"- {horas} hs - {row.get('tipo_designacion', '')}",
                            observaciones=row.get("observaciones", ""), periodo_id=int(row.get("_periodo_id")),
                            horas=horas)
                    except (DocentesError, DesignacionesError) as exc:
                        self._detener_si_denegado(exc)
                        errores.append(f"Movimiento designación fila {row.get('fila', '')}: {exc.message}")
            else:
                errores.append(f"Designación fila {row.get('fila', '')}: {MSG_NO_GUARDADA}")
                detalle.append(resultado(row, "No guardada", MSG_NO_GUARDADA))

        # 5) actualizacion parcial de existentes (solo si se pidio)
        if data.get("actualizar_existentes") is True:
            def preparar(ns: dict) -> list:
                l, lc, nc = ns["limpiar_texto_tabla"], ns["limpiar_cuil"], ns["nombre_completo"]
                out = []
                for row in r["existentes"]:
                    cuil_row = lc(row.get("cuil", ""))
                    cuil_original = l(row.get("_cuil_existente", "")) or cuil_row
                    df_actual = ns["docente_existe"](cuil_original)
                    if df_actual is None or df_actual.empty:
                        out.append({"row": row, "error": MSG_SIN_FICHA})
                        continue
                    actual = df_actual.iloc[0].to_dict()
                    datos, campos = ns["_mezclar_docente_existente_excel_v247"](pd.Series(row), actual)
                    if not campos:
                        out.append({"row": row, "omitir": True})
                        continue
                    nombre_row = nc(datos["apellido"], datos["nombres"])
                    if not l(nombre_row):
                        nombre_row = l(actual.get("nombre", "")) or cuil_original
                    out.append({"row": row, "cuil": cuil_original, "datos": datos, "campos": list(campos),
                                "nombre": nombre_row, "obs": l(row.get("observaciones", ""))})
                return out

            for p in self._motor(record, scope, preparar):
                row = p["row"]
                if p.get("error"):
                    errores.append(f"Docente fila {row.get('fila', '')}: {p['error']}")
                    continue
                if p.get("omitir"):
                    omitidos += 1
                    continue
                try:
                    self.docentes.actualizar_desde_carga_integral(record, p["cuil"], p["datos"], p["campos"],
                                                                  p["nombre"], p["obs"], per_id)
                    actualizados += 1
                except (DocentesError, DesignacionesError) as exc:
                    self._detener_si_denegado(exc)
                    errores.append(f"Docente fila {row.get('fila', '')}: {exc.message}")
        else:
            omitidos = vista["docentes_existentes"]

        mensaje = (f"Carga integral verificada. Docentes nuevos: {nuevos}. Docentes actualizados: {actualizados}. "
                   f"Docentes existentes omitidos: {omitidos}. Designaciones nuevas realmente guardadas: {creadas}. "
                   f"Duplicadas omitidas desde la revisión: {vista['designaciones_omitidas']}. "
                   f"Errores: {len(errores)}.")
        return {"mensaje": mensaje, "tono": "warning" if errores else "success", "errores": len(errores),
                "detalle": detalle, "errores_detalle": errores[:50]}


__all__ = ["CargaIntegralService"]
