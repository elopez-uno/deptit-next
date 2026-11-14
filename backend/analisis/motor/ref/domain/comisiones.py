# B05: extracted verbatim from certified B04 (comisiones: turnos, modalidades, filas del Excel, etiquetas).
from __future__ import annotations

import pandas as pd

from analisis.motor.ref.common.horarios import normalizar_hora_excel
from analisis.motor.ref.common.normalization import _normalizar_si_no_cobertura_v153
from analisis.motor.ref.domain.materias import _nombre_materia_visible_v138
from analisis.motor.ref.extracted_batch04.texto import limpiar_texto_tabla
from analisis.motor.ref.extracted_batch04.texto import normalizar_clave


def _clave_catalogo_comision(valor):
    clave = normalizar_clave(valor)
    return clave.translate(str.maketrans({
        "Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U", "Ü": "U", "Ñ": "N"
    }))


def normalizar_turno_comision(valor):
    """Normaliza el turno guardando solamente mañana, tarde o noche.

    También acepta denominaciones históricas como "Turno noche", para que los
    registros ya existentes se muestren y se migren sin duplicar la palabra
    "turno" en disposiciones, mensajes o listados.
    """
    txt = limpiar_texto_tabla(valor)
    clave = _clave_catalogo_comision(txt)
    mapa = {
        "MANANA": "mañana", "TURNO MANANA": "mañana", "MATUTINO": "mañana",
        "TARDE": "tarde", "TURNO TARDE": "tarde", "VESPERTINO": "tarde",
        "NOCHE": "noche", "TURNO NOCHE": "noche", "NOCTURNO": "noche",
    }
    return mapa.get(clave, txt)


def normalizar_modalidad_comision(valor):
    txt = limpiar_texto_tabla(valor)
    if not txt:
        return "Presencial"
    clave = _clave_catalogo_comision(txt)
    mapa = {
        "PRESENCIAL": "Presencial",
        "VIRTUAL": "Virtual",
        "HIBRIDA": "Híbrida",
        "HIBRIDO": "Híbrida",
        "MIXTA": "Híbrida",
        "MIXTO": "Híbrida",
    }
    return mapa.get(clave, txt)


def _inferir_turno_desde_horas_fila(row):
    horas = []
    for col in row.index:
        if str(col).startswith("hora_inicio_"):
            hora = normalizar_hora_excel(row.get(col, ""))
            if hora:
                try:
                    horas.append(int(hora.split(":")[0]))
                except Exception:
                    pass
    if not horas:
        return ""
    primera = min(horas)
    if primera < 13:
        return "mañana"
    if primera < 18:
        return "tarde"
    return "noche"


def _turno_para_etiqueta(valor):
    turno = normalizar_turno_comision(valor)
    return turno or "sin especificar"


def _label_comision_desde_row(row):
    periodo = limpiar_texto_tabla(row.get("periodo", ""))
    codigo = limpiar_texto_tabla(row.get("codigo_materia", ""))
    asig = limpiar_texto_tabla(row.get("asignatura", ""))
    materia_especifica = limpiar_texto_tabla(row.get("materia_especifica", ""))
    if materia_especifica:
        asig = f"{asig} · {materia_especifica}" if asig else materia_especifica
    com = limpiar_texto_tabla(row.get("nombre_comision", ""))
    turno = _turno_para_etiqueta(row.get("turno", ""))
    horarios = limpiar_texto_tabla(row.get("horarios", "")) or "Sin horarios cargados"
    carreras = limpiar_texto_tabla(row.get("carrera", "")) or "Sin carrera informada"
    materia = f"{codigo} - {asig}".strip(" -")
    partes = [p for p in [periodo, materia, f"Comisión {com}" if com else "", turno] if p]
    partes.append(f"Día/s y horario/s: {horarios}")
    partes.append(f"Carrera/s: {carreras}")
    return " — ".join(partes) or f"Comisión ID {row.get('id', '')}"


def horarios_desde_fila_comision(row):
    """Extrae todos los bloques Día N / Hora Inicio N / Hora Fin N presentes en una fila."""
    import re
    indices = set()
    for col in row.index:
        m = re.fullmatch(r"dia_(\d+)|hora_inicio_(\d+)|hora_fin_(\d+)", str(col))
        if m:
            indices.add(int(next(g for g in m.groups() if g)))

    horarios = []
    for n in sorted(indices):
        dia = limpiar_texto_tabla(row.get(f"dia_{n}", ""))
        hi = limpiar_texto_tabla(row.get(f"hora_inicio_{n}", ""))
        hf = limpiar_texto_tabla(row.get(f"hora_fin_{n}", ""))
        if dia or hi or hf:
            horarios.append({"n": n, "dia": dia, "hora_inicio": hi, "hora_fin": hf})
    return horarios


def docentes_desde_fila_comision(row):
    """Extrae docentes y su cobertura horaria desde la fila del Excel.

    v153 agrega un selector explícito ``Cubre Horario M - Docente N``:
    - Sí + horas propias vacías => cubre completo el Horario M general.
    - Sí + horas propias => cubre solamente esa subfranja.
    - No => no cubre ese Horario M.
    - Si el archivo no trae columnas Cubre Horario, se conserva la lógica legacy:
      sin franjas propias = cubre toda la comisión.

    v161 corrige un detalle del modelo integral: que existan las columnas de Docente 1..5
    y Cubre Horario no significa que los cinco docentes sean obligatorios. Un slot docente
    vacío se ignora por completo. Solo se conserva un slot vacío para reportar un error real
    si además trae un cargo manual o horas Inicio/Fin cargadas sin haber indicado docente.
    """
    import re
    indices = set()
    slots_por_docente = {}
    slots_cubre_por_docente = {}

    for col in row.index:
        s = str(col)
        m = re.fullmatch(r"docente_(\d+)|cargo_docente_(\d+)", s)
        if m:
            indices.add(int(next(g for g in m.groups() if g)))
            continue

        mc = re.fullmatch(r"cubre_docente_(\d+)_horario_(\d+)", s)
        if mc:
            n_doc = int(mc.group(1)); n_h = int(mc.group(2))
            indices.add(n_doc)
            slots_por_docente.setdefault(n_doc, set()).add(n_h)
            slots_cubre_por_docente.setdefault(n_doc, set()).add(n_h)
            continue

        mh = re.fullmatch(r"(?:dia|hora_inicio|hora_fin)_docente_(\d+)_horario_(\d+)", s)
        if mh:
            n_doc = int(mh.group(1)); n_h = int(mh.group(2))
            indices.add(n_doc); slots_por_docente.setdefault(n_doc, set()).add(n_h)

    docentes = []
    for n in sorted(indices):
        docente = limpiar_texto_tabla(row.get(f"docente_{n}", ""))
        cargo = limpiar_texto_tabla(row.get(f"cargo_docente_{n}", ""))
        horarios_legacy = []
        hay_franja_legacy = False
        hay_horas_explicitas = False
        cobertura_slots = []
        tiene_columnas_cobertura = bool(slots_cubre_por_docente.get(n))

        for n_h in sorted(slots_por_docente.get(n, set())):
            cubre = _normalizar_si_no_cobertura_v153(
                row.get(f"cubre_docente_{n}_horario_{n_h}", "")
            )
            dia = limpiar_texto_tabla(row.get(f"dia_docente_{n}_horario_{n_h}", ""))
            hi = limpiar_texto_tabla(row.get(f"hora_inicio_docente_{n}_horario_{n_h}", ""))
            hf = limpiar_texto_tabla(row.get(f"hora_fin_docente_{n}_horario_{n_h}", ""))

            if hi or hf:
                hay_horas_explicitas = True

            if tiene_columnas_cobertura:
                cobertura_slots.append({
                    "n": n_h,
                    "cubre": cubre,
                    "dia": dia,
                    "hora_inicio": hi,
                    "hora_fin": hf,
                })

            # Compatibilidad para archivos anteriores o filas sin columnas Sí/No.
            if dia or hi or hf:
                hay_franja_legacy = True
                horarios_legacy.append({
                    "n": n_h, "dia": dia, "hora_inicio": hi, "hora_fin": hf
                })

        # El modelo siempre trae columnas para cinco docentes. Antes, solo por existir
        # esas columnas, los Docentes 2..5 vacíos se interpretaban como asignaciones
        # incompletas. Ahora solo un docente efectivamente informado participa de la fila.
        # Si no hay nombre, ignoramos Sí/No/Día que puedan provenir de fórmulas cacheadas;
        # cargo u horas manuales sí revelan una carga incompleta y se conserva para validar.
        if not docente and not cargo and not hay_horas_explicitas:
            continue

        docentes.append({
            "n": n,
            "docente": docente,
            "rol": cargo,
            "horarios_reales": horarios_legacy if hay_franja_legacy else None,
            "cobertura_slots": cobertura_slots if tiene_columnas_cobertura else None,
        })
    return docentes


def filtrar_materias_para_comisiones(df, codigo_parcial="", nombre_parcial="", cuatrimestre="Todos", escuela="Todas", carrera="Todas"):
    """
    Filtra materias para abrir comisiones.
    Permite buscar por parte del código, parte del nombre/asignatura, cuatrimestre,
    escuela y carrera. Si varios filtros están cargados, aplica todos a la vez.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    df_filtrado = df.copy()
    codigo_parcial = normalizar_clave(codigo_parcial)
    nombre_parcial = normalizar_clave(nombre_parcial)
    cuatrimestre = limpiar_texto_tabla(cuatrimestre)
    escuela = limpiar_texto_tabla(escuela)
    carrera = limpiar_texto_tabla(carrera)

    if codigo_parcial:
        df_filtrado = df_filtrado[
            df_filtrado["codigo"].apply(lambda x: codigo_parcial in normalizar_clave(x))
        ].copy()

    if nombre_parcial:
        df_filtrado = df_filtrado[
            df_filtrado["asignatura"].apply(lambda x: nombre_parcial in normalizar_clave(x))
        ].copy()

    if cuatrimestre and cuatrimestre != "Todos":
        df_filtrado = df_filtrado[
            df_filtrado["cuatrimestre"].astype(str).str.strip() == cuatrimestre
        ].copy()

    if escuela and escuela != "Todas":
        df_filtrado = df_filtrado[
            df_filtrado["escuela"].astype(str).str.strip() == escuela
        ].copy()

    if carrera and carrera != "Todas":
        df_filtrado = df_filtrado[
            df_filtrado["carrera"].astype(str).str.strip() == carrera
        ].copy()

    return df_filtrado.reset_index(drop=True)


def filtrar_opciones_comisiones_por_busqueda(opciones, busqueda):
    """Filtra el selector de comisiones por texto, código, materia, carrera o nombre de comisión."""
    if not opciones:
        return {}
    q = normalizar_clave(busqueda or "")
    if not q:
        return opciones
    filtradas = {}
    for label, value in opciones.items():
        if q in normalizar_clave(label):
            filtradas[label] = value
    return filtradas


def etiqueta_materia_comision(row):
    codigo = limpiar_texto_tabla(row.get("codigo", ""))
    asignatura = limpiar_texto_tabla(row.get("asignatura", ""))
    carreras = limpiar_texto_tabla(row.get("carrera", ""))
    escuelas = limpiar_texto_tabla(row.get("escuela", ""))
    plan = limpiar_texto_tabla(row.get("plan_version", ""))
    anio = limpiar_texto_tabla(row.get("anio", ""))
    cuat = limpiar_texto_tabla(row.get("cuatrimestre", ""))
    prefijo = f"{codigo} - " if codigo else ""
    partes = [f"{prefijo}{asignatura}"]
    if carreras:
        partes.append(f"Carrera/s: {carreras}")
    if escuelas:
        partes.append(f"Escuela/s: {escuelas}")
    if plan:
        partes.append(f"Plan: {plan}")
    if anio:
        partes.append(f"{anio}")
    if cuat:
        partes.append(f"Cuat. {cuat}")
    return " — ".join([p for p in partes if p])


def _ordenar_comisiones_informe_por_asignatura_v201(df_com):
    """Orden alfabético estable para Apertura de comisiones y sus datos asociados."""
    if df_com is None or not isinstance(df_com, pd.DataFrame) or df_com.empty:
        return df_com.copy() if isinstance(df_com, pd.DataFrame) else pd.DataFrame()

    out = df_com.copy()

    def _etiqueta(r):
        try:
            visible = _nombre_materia_visible_v138(
                r.get("codigo_materia", ""),
                r.get("asignatura", ""),
                r.get("materia_especifica", ""),
            )
        except Exception:
            visible = r.get("asignatura", "")
        return normalizar_clave(limpiar_texto_tabla(visible))

    out["_orden_asignatura_v201"] = out.apply(_etiqueta, axis=1)
    out["_orden_comision_v201"] = out.get(
        "nombre_comision", pd.Series("", index=out.index)
    ).fillna("").astype(str).map(normalizar_clave)

    orden = ["_orden_asignatura_v201", "_orden_comision_v201"]
    if "fecha_creacion" in out.columns:
        orden.append("fecha_creacion")

    out = out.sort_values(orden, kind="stable").drop(
        columns=["_orden_asignatura_v201", "_orden_comision_v201"],
        errors="ignore",
    )
    return out.reset_index(drop=True)


def _normalizar_fila_bulk_comision_v232(row):
    materia_id = int(row.get("materia_id"))
    adicionales = []
    for x in list(row.get("materia_ids_adicionales", []) or []):
        try:
            adicionales.append(int(x))
        except Exception:
            pass
    opcion = row.get("opcion_curricular_id")
    try:
        opcion = int(opcion) if opcion not in [None, ""] and not pd.isna(opcion) else None
    except Exception:
        opcion = None
    return materia_id, adicionales, opcion


def _etiqueta_comision_derivada_v248(fila):
    nombre = limpiar_texto_tabla((fila or {}).get("nombre_comision", ""))
    turno = limpiar_texto_tabla((fila or {}).get("turno", ""))
    sede = limpiar_texto_tabla((fila or {}).get("sede", ""))
    partes = [x for x in [f"Comisión {nombre}" if nombre else "Comisión", turno, sede] if x]
    return " · ".join(partes)


def _etiqueta_item_v248(item):
    cod = limpiar_texto_tabla((item or {}).get("codigo_materia", ""))
    asig = limpiar_texto_tabla((item or {}).get("asignatura", ""))
    if cod and asig:
        return f"{cod} — {asig}"
    return cod or asig or limpiar_texto_tabla((item or {}).get("clave_asignatura_v248", ""))
