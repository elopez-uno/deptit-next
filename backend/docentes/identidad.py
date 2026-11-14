"""Identidad docente v168 (entry l. 35572-36395), portada paso a paso sobre ``DocentesRepository``.

- ``actualizar_docente``: identidad institucional (todas las fichas del mismo CUIL en la institucion), atributos locales
  (estado, tipo, observaciones) solo en el departamento operativo, sincronizacion de nombre en movimientos y
  disposiciones, y migracion de referencias si cambia el CUIL.  B12A valida el nivel de posgrado ANTES de cualquier SQL.
- ``migrar_referencias``: cambio de CUIL / reparacion de CUIL huerfano en las 12 tablas de ``_TABLAS_CUIL_V168``.
- ``cuiles_huerfanos``: CUIL usados en cargas que ya no existen en ``docentes`` (institucion).
Todo corre en la transaccion de ``repo``; el llamador confirma o revierte.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from . import rules

TABLAS_CUIL_V168 = [
    "designaciones",
    "asignaciones_docentes_comision",
    "investigacion_docente",
    "extension_docente",
    "actividad_especial_docente",
    "movimientos",
    "disposiciones",
    "estado_consulta_designacion",
    "correcciones_historial_horas",
    "disposicion_docente_parametros",
    "disposicion_docente_designaciones",
    "prestamos_docentes",
]

CLAVES_DUPLICADO_CUIL_V168 = {
    "designaciones": [
        "departamento_id", "periodo_id", "cargo", "dedicacion", "horas",
        "tipo_designacion", "numero_resolucion", "ad_honorem", "fecha_desde",
        "fecha_hasta", "estado", "funcion_no_docente", "texto_funcion_no_docente",
    ],
    "asignaciones_docentes_comision": ["departamento_id", "comision_id"],
    "investigacion_docente": ["departamento_id", "periodo_id", "proyecto_id", "rol"],
    "extension_docente": ["departamento_id", "periodo_id", "proyecto_id", "rol"],
    "actividad_especial_docente": ["departamento_id", "periodo_id", "actividad_id", "rol"],
    "estado_consulta_designacion": ["departamento_id", "periodo_id"],
    "correcciones_historial_horas": ["departamento_id", "periodo_id"],
    "disposicion_docente_designaciones": ["departamento_id", "designacion_id"],
    "prestamos_docentes": ["departamento_id", "periodo_id"],
}

TABLAS_OPERATIVAS_V168 = [
    "asignaciones_docentes_comision", "investigacion_docente", "extension_docente",
    "actividad_especial_docente", "estado_consulta_designacion", "correcciones_historial_horas",
]

TABLAS_BUSQUEDA_HUERFANOS = [
    "designaciones", "asignaciones_docentes_comision", "investigacion_docente",
    "extension_docente", "actividad_especial_docente", "movimientos", "disposiciones",
]
NOMBRES_TABLA_HUERFANOS = {
    "designaciones": "designaciones",
    "asignaciones_docentes_comision": "comisiones",
    "investigacion_docente": "investigación",
    "extension_docente": "extensión",
    "actividad_especial_docente": "actividades",
    "movimientos": "movimientos",
    "disposiciones": "disposiciones",
}

MSG_CUIL_INVALIDO_EDICION = "Completá un CUIL válido antes de guardar los cambios."
MSG_DOCENTE_NO_ENCONTRADO = "No se encontró el docente que se intenta modificar."
MSG_CUILS_MIGRACION = "El CUIL anterior y el nuevo deben ser válidos."


class IdentidadError(ValueError):
    """``ValueError`` certificado de la identidad v168 (mensaje para el usuario)."""


class RemanentesError(RuntimeError):
    """``RuntimeError`` certificado: quedaron referencias con el CUIL anterior; la transaccion se revierte."""


def _tabla_existe(repo, tabla: str) -> bool:
    try:
        return bool(repo.columns(tabla))
    except Exception:
        return False


def _vacio_resumen() -> dict:
    return {"actualizados": 0, "duplicados_eliminados": 0, "por_tabla": {}}


def _merge_parametros_disposicion(repo, clave_origen: str, clave_destino: str, cuil_destino: str) -> dict:
    tabla = "disposicion_docente_parametros"
    if not _tabla_existe(repo, tabla):
        return {"actualizados": 0, "duplicados_eliminados": 0}
    origen, cols = repo.fetch_rows_cuil(tabla, clave_origen)
    destino, _ = repo.fetch_rows_cuil(tabla, clave_destino)
    if not origen:
        return {"actualizados": 0, "duplicados_eliminados": 0}

    def ambito(row):
        return (row.get("institucion_id") if "institucion_id" in cols else None,
                row.get("departamento_id") if "departamento_id" in cols else None)

    por_ambito_dest = {ambito(r): r for r in destino}
    actualizados = eliminados = 0
    for old in origen:
        target = por_ambito_dest.get(ambito(old))
        if target is None:
            if "id" in cols and old.get("id") is not None:
                actualizados += repo.update_id_cuil(tabla, old["id"], cuil_destino)
            else:
                extra = {"departamento_id": old.get("departamento_id")} if "departamento_id" in cols else {}
                actualizados += repo.update_where_cuil(tabla, {"cuil": str(cuil_destino)}, clave_origen, extra)
            continue
        # Ficha auxiliar ya existente con el CUIL nuevo: conserva sus valores y completa solo los vacios.
        cambios = {}
        excluir = {"id", "institucion_id", "departamento_id", "cuil", "sqlite_id", "source_db"}
        for col in cols:
            if col in excluir:
                continue
            if rules.es_vacio_v168(target.get(col)) and not rules.es_vacio_v168(old.get(col)):
                cambios[col] = old.get(col)
        if cambios:
            if target.get("id") is not None and "id" in cols:
                repo.update_row_values(tabla, target["id"], cambios)
            else:
                extra = {"departamento_id": target.get("departamento_id")} if "departamento_id" in cols else {}
                repo.update_where_cuil(tabla, cambios, clave_destino, extra)
        if old.get("id") is not None and "id" in cols:
            eliminados += repo.delete_id(tabla, old["id"])
        else:
            extra = {"departamento_id": old.get("departamento_id")} if "departamento_id" in cols else {}
            eliminados += repo.delete_where_cuil(tabla, clave_origen, extra)
    return {"actualizados": actualizados, "duplicados_eliminados": eliminados}


def _actualizar_variables_disposiciones(repo, clave_destino: str, cuil_destino: str, nombre_destino: str) -> int:
    tabla = "disposiciones"
    cols = repo.columns(tabla) if _tabla_existe(repo, tabla) else []
    if not cols or "variables_json" not in cols or "id" not in cols:
        return 0
    rows, _ = repo.fetch_rows_cuil(tabla, clave_destino)
    total = 0
    for row in rows:
        raw = row.get("variables_json")
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        cambio = False
        for k in ["cuil", "CUIL"]:
            if k in data and str(data.get(k) or "") != str(cuil_destino):
                data[k] = str(cuil_destino)
                cambio = True
        if nombre_destino:
            for k in ["docente", "Docente"]:
                if k in data and str(data.get(k) or "") != str(nombre_destino):
                    data[k] = str(nombre_destino)
                    cambio = True
        if cambio:
            total += repo.update_variables_json(row["id"], data)
    return total


def migrar_referencias(repo, cuil_origen: Any, cuil_destino: Any, nombre_destino: str = "") -> dict:
    """``_migrar_referencias_cuil_conn_v168``."""
    origen = rules.limpiar_cuil(cuil_origen)
    destino = rules.limpiar_cuil(cuil_destino)
    clave_o = rules.clave_cuil(origen)
    clave_d = rules.clave_cuil(destino)
    if not clave_o or not clave_d:
        raise IdentidadError(MSG_CUILS_MIGRACION)
    if clave_o == clave_d and origen == destino:
        return {"actualizados": 0, "duplicados_eliminados": 0, "por_tabla": {}, "remanentes": 0}

    # Solo cambio el formato visible del mismo CUIL: UPDATE textual, sin deduplicar.
    if clave_o == clave_d:
        resumen = _vacio_resumen()
        for tabla in TABLAS_CUIL_V168:
            if not _tabla_existe(repo, tabla) or "cuil" not in repo.columns(tabla):
                continue
            cols = repo.columns(tabla)
            extras = {}
            if tabla == "movimientos" and nombre_destino and "nombre" in cols:
                extras["nombre"] = str(nombre_destino)
            if tabla == "disposiciones" and nombre_destino and "docente" in cols:
                extras["docente"] = str(nombre_destino)
            n = repo.update_cuil_textual(tabla, origen, destino, extras)
            resumen["por_tabla"][tabla] = {"actualizados": n, "duplicados_eliminados": 0}
            resumen["actualizados"] += n
        try:
            resumen["variables_disposicion_actualizadas"] = _actualizar_variables_disposiciones(
                repo, clave_d, destino, nombre_destino)
        except Exception:
            resumen["variables_disposicion_actualizadas"] = 0
        rem = 0
        for tabla in TABLAS_CUIL_V168:
            if not _tabla_existe(repo, tabla) or "cuil" not in repo.columns(tabla):
                continue
            rem += repo.count_cuil_textual(tabla, origen)
        resumen["remanentes"] = rem
        return resumen

    resumen = _vacio_resumen()
    mapa_designaciones: dict[int, int] = {}

    # 1) Designaciones: si ya fue recreada con el CUIL nuevo, se conserva la nueva y se borra la vieja duplicada.
    tabla = "designaciones"
    if _tabla_existe(repo, tabla):
        olds, cols = repo.fetch_rows_cuil(tabla, clave_o)
        news, _ = repo.fetch_rows_cuil(tabla, clave_d)
        claves = [c for c in CLAVES_DUPLICADO_CUIL_V168[tabla] if c in cols]
        por_firma = {rules.firma_fila_v168(r, claves): r for r in news}
        upd = dele = 0
        for old in olds:
            sig = rules.firma_fila_v168(old, claves)
            target = por_firma.get(sig)
            if target is not None:
                if old.get("id") is not None:
                    mapa_designaciones[int(old["id"])] = int(target.get("id") or old["id"])
                    dele += repo.delete_id(tabla, old["id"])
            else:
                if old.get("id") is not None:
                    mapa_designaciones[int(old["id"])] = int(old["id"])
                    upd += repo.update_id_cuil(tabla, old["id"], destino)
                    por_firma[sig] = dict(old, cuil=destino)
        resumen["por_tabla"][tabla] = {"actualizados": upd, "duplicados_eliminados": dele}
        resumen["actualizados"] += upd
        resumen["duplicados_eliminados"] += dele

    # 2) Tablas operativas con ID e identidad logica deduplicable.
    for tabla in TABLAS_OPERATIVAS_V168:
        if not _tabla_existe(repo, tabla):
            continue
        olds, cols = repo.fetch_rows_cuil(tabla, clave_o)
        news, _ = repo.fetch_rows_cuil(tabla, clave_d)
        claves = [c for c in CLAVES_DUPLICADO_CUIL_V168.get(tabla, []) if c in cols]
        por_firma = {rules.firma_fila_v168(r, claves): r for r in news}
        upd = dele = 0
        for old in olds:
            sig = rules.firma_fila_v168(old, claves)
            target = por_firma.get(sig) if claves else None
            if target is not None and old.get("id") is not None:
                dele += repo.delete_id(tabla, old["id"])
            elif old.get("id") is not None:
                upd += repo.update_id_cuil(tabla, old["id"], destino)
                if claves:
                    por_firma[sig] = dict(old, cuil=destino)
            else:
                upd += repo.update_cuil_direct(tabla, clave_o, destino)
                break
        resumen["por_tabla"][tabla] = {"actualizados": upd, "duplicados_eliminados": dele}
        resumen["actualizados"] += upd
        resumen["duplicados_eliminados"] += dele

    # 3) Datos de disposicion por designacion: remapea designacion_id antes de deduplicar.
    tabla = "disposicion_docente_designaciones"
    if _tabla_existe(repo, tabla):
        olds, cols = repo.fetch_rows_cuil(tabla, clave_o)
        news, _ = repo.fetch_rows_cuil(tabla, clave_d)
        claves = [c for c in CLAVES_DUPLICADO_CUIL_V168[tabla] if c in cols]
        por_firma = {rules.firma_fila_v168(r, claves): r for r in news}
        upd = dele = 0
        for old in olds:
            extra = {}
            if old.get("designacion_id") is not None:
                did_old = int(old["designacion_id"])
                did_new = int(mapa_designaciones.get(did_old, did_old))
                extra["designacion_id"] = did_new
                old = dict(old)
                old["designacion_id"] = did_new
            sig = rules.firma_fila_v168(old, claves)
            target = por_firma.get(sig)
            if target is not None and old.get("id") is not None:
                dele += repo.delete_id(tabla, old["id"])
            elif old.get("id") is not None:
                upd += repo.update_id_cuil(tabla, old["id"], destino, extra=extra)
                por_firma[sig] = dict(old, cuil=destino)
        resumen["por_tabla"][tabla] = {"actualizados": upd, "duplicados_eliminados": dele}
        resumen["actualizados"] += upd
        resumen["duplicados_eliminados"] += dele

    # 4) Parametros auxiliares por docente: fusiona en vez de perder informacion.
    res_param = _merge_parametros_disposicion(repo, clave_o, clave_d, destino)
    if res_param["actualizados"] or res_param["duplicados_eliminados"]:
        resumen["por_tabla"]["disposicion_docente_parametros"] = res_param
        resumen["actualizados"] += int(res_param["actualizados"])
        resumen["duplicados_eliminados"] += int(res_param["duplicados_eliminados"])

    # 5) Historial y disposiciones emitidas: conservan la fila y cambian la identidad asociada.
    for tabla in ["movimientos", "disposiciones"]:
        if not _tabla_existe(repo, tabla):
            continue
        extras = {}
        cols = repo.columns(tabla)
        if tabla == "movimientos" and nombre_destino and "nombre" in cols:
            extras["nombre"] = str(nombre_destino)
        if tabla == "disposiciones" and nombre_destino and "docente" in cols:
            extras["docente"] = str(nombre_destino)
        n = repo.update_cuil_direct(tabla, clave_o, destino, extras=extras)
        resumen["por_tabla"][tabla] = {"actualizados": n, "duplicados_eliminados": 0}
        resumen["actualizados"] += n

    try:
        resumen["variables_disposicion_actualizadas"] = _actualizar_variables_disposiciones(
            repo, clave_d, destino, nombre_destino)
    except Exception:
        resumen["variables_disposicion_actualizadas"] = 0

    # Verificacion: ninguna tabla conocida debe seguir mostrando el CUIL anterior (incluye prestamos_docentes,
    # que el certificado no migra: un docente con prestamo no puede cambiar los digitos de su CUIL).
    remanentes = 0
    for tabla in TABLAS_CUIL_V168:
        if not _tabla_existe(repo, tabla):
            continue
        rows, _ = repo.fetch_rows_cuil(tabla, clave_o)
        remanentes += len(rows)
    resumen["remanentes"] = int(remanentes)
    return resumen


def _sincronizar_nombre_referencias(repo, clave_cuil: str, cuil_visible: str, nombre: str) -> None:
    for tabla, campo_nombre in [("movimientos", "nombre"), ("disposiciones", "docente")]:
        if not _tabla_existe(repo, tabla):
            continue
        if campo_nombre not in repo.columns(tabla):
            continue
        repo.update_cuil_direct(tabla, clave_cuil, cuil_visible, extras={campo_nombre: str(nombre or "")})
    try:
        _actualizar_variables_disposiciones(repo, clave_cuil, cuil_visible, nombre)
    except Exception:
        pass


def actualizar_docente(repo, cuil_original: Any, cuil: Any, apellido: Any, nombres: Any, legajo: Any, titulo: Any,
                       titulo_posgrado: Any, email: Any, telefono: Any, ref_legajo: Any, estado: Any,
                       tipo_docente: Any = "Propio", observaciones: Any = "", antiguedad_anios: Optional[int] = None,
                       nivel_posgrado_salarial: Any = "") -> dict:
    """``actualizar_docente`` v168 con la guarda B12A (``require_posgrado_level_for_write``) delante."""
    nivel_posgrado_salarial = rules.require_posgrado_level_for_write(nivel_posgrado_salarial)
    cuil_old = rules.limpiar_cuil(cuil_original)
    cuil_new = rules.limpiar_cuil(cuil)
    clave_old = rules.clave_cuil(cuil_old)
    clave_new = rules.clave_cuil(cuil_new)
    if not clave_old or not clave_new:
        raise IdentidadError(MSG_CUIL_INVALIDO_EDICION)

    nombre = rules.nombre_completo(apellido, nombres)
    filas_old = repo.docentes_institucion(clave_old)
    if not filas_old:
        raise IdentidadError(MSG_DOCENTE_NO_ENCONTRADO)

    cambio_cuil = clave_old != clave_new or cuil_old != cuil_new
    if cambio_cuil and clave_old != clave_new:
        filas_target = repo.docentes_institucion(clave_new)
        if filas_target:
            nombres_target = sorted({
                str(r.get("nombre") or rules.nombre_completo(r.get("apellido", ""), r.get("nombres", ""))
                    or r.get("cuil") or "").strip()
                for r in filas_target
            })
            raise IdentidadError(
                "El CUIL nuevo ya está asociado a otro registro de docente en la institución"
                + (f" ({', '.join([x for x in nombres_target if x])})" if any(nombres_target) else "")
                + ". Para evitar fusionar personas por error, no se realizó ningún cambio."
            )

    resumen_cuil = {"actualizados": 0, "duplicados_eliminados": 0, "por_tabla": {}, "remanentes": 0}
    if cambio_cuil:
        resumen_cuil = migrar_referencias(repo, cuil_old, cuil_new, nombre_destino=nombre)
        if int(resumen_cuil.get("remanentes", 0) or 0) > 0:
            raise RemanentesError(
                f"Quedaron {resumen_cuil['remanentes']} referencias con el CUIL anterior. "
                "Se revirtió la operación completa."
            )

    cols_doc = repo.columns("docentes")
    # Identidad personal institucional: se sincroniza en todas las apariciones del mismo docente.
    campos_identidad = {
        "cuil": cuil_new,
        "nombre": nombre,
        "apellido": apellido,
        "nombres": nombres,
        "legajo": legajo,
        "titulo": titulo,
        "titulo_posgrado": titulo_posgrado,
        "antiguedad_anios": antiguedad_anios,
        "nivel_posgrado_salarial": rules.nivel_posgrado_salarial_normalizado(nivel_posgrado_salarial),
        "email": email,
        "telefono": telefono,
        "ref_legajo_fisico": ref_legajo,
    }
    campos_identidad = {k: v for k, v in campos_identidad.items() if k in cols_doc}
    repo.update_where_cuil("docentes", campos_identidad, clave_old)

    # Atributos administrativos: solo en el departamento donde se edita la ficha.
    campos_locales = {"estado": estado, "tipo_docente": tipo_docente, "observaciones": observaciones}
    campos_locales = {k: v for k, v in campos_locales.items() if k in cols_doc}
    if campos_locales:
        extra = {"departamento_id": repo.dep} if "departamento_id" in cols_doc else {}
        repo.update_where_cuil("docentes", campos_locales, clave_new, extra)

    _sincronizar_nombre_referencias(repo, clave_new, cuil_new, nombre)
    return resumen_cuil


def migrar_referencias_cuil(repo, cuil_origen: Any, cuil_destino: Any, nombre_destino: str = "") -> dict:
    """``migrar_referencias_cuil_v168``: remanentes -> RuntimeError (el llamador revierte la transaccion)."""
    resumen = migrar_referencias(repo, cuil_origen, cuil_destino, nombre_destino=nombre_destino)
    if int(resumen.get("remanentes", 0) or 0) > 0:
        raise RemanentesError(
            f"Quedaron {resumen['remanentes']} referencia/s con el CUIL anterior. "
            "La transacción se revirtió para no dejar la identidad a medias."
        )
    return resumen


def cuiles_huerfanos(repo) -> list[dict]:
    """``get_cuiles_huerfanos_v168``: orden Referencias desc, CUIL huerfano asc."""
    claves_doc = {rules.clave_cuil(c) for c in repo.cuiles_docentes_institucion() if rules.clave_cuil(c)}
    agregados: dict[str, dict] = {}
    for tabla in TABLAS_BUSQUEDA_HUERFANOS:
        if not _tabla_existe(repo, tabla) or "cuil" not in repo.columns(tabla):
            continue
        for cuil_txt, n in repo.cuiles_por_tabla(tabla):
            clave = rules.clave_cuil(cuil_txt)
            if not clave or clave in claves_doc:
                continue
            item = agregados.setdefault(clave, {"cuil": str(cuil_txt), "total": 0, "tablas": {}})
            item["total"] += int(n or 0)
            item["tablas"][tabla] = item["tablas"].get(tabla, 0) + int(n or 0)
    out = []
    for item in agregados.values():
        detalle = ", ".join(f"{NOMBRES_TABLA_HUERFANOS.get(t, t)}: {n}" for t, n in item["tablas"].items() if n)
        out.append({"cuil_huerfano": item["cuil"], "referencias": int(item["total"]), "detalle": detalle})
    out.sort(key=lambda r: (-r["referencias"], r["cuil_huerfano"]))
    return out
