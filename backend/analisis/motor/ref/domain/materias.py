# B05: extracted verbatim from certified B04 (materias, planes y opciones curriculares).
from __future__ import annotations

import re
from io import BytesIO

import pandas as pd

from analisis.motor.ref.extracted_batch02.safe_helpers import _normalizar_encabezado_opcion_v124
from analisis.motor.ref.extracted_batch04.materias import _normalizar_tipo_opcion_v120
from analisis.motor.ref.extracted_batch04.materias import es_materia_optativa_electiva
from analisis.motor.ref.extracted_batch04.materias import normalizar_codigo_materia
from analisis.motor.ref.extracted_batch04.texto import _normalizar_valor_plan
from analisis.motor.ref.extracted_batch04.texto import _valor_limpio_materia
from analisis.motor.ref.extracted_batch04.texto import limpiar_texto_tabla
from analisis.motor.ref.extracted_batch04.texto import normalizar_clave


def _resumen_materia(row):
    if not row:
        return ""
    codigo = _normalizar_valor_plan(row.get("codigo"))
    asignatura = _normalizar_valor_plan(row.get("asignatura"))
    carrera = _normalizar_valor_plan(row.get("carrera"))
    plan = _normalizar_valor_plan(row.get("plan_version"))
    partes = []
    if codigo:
        partes.append(codigo)
    if asignatura:
        partes.append(asignatura)
    if carrera:
        partes.append(carrera)
    if plan:
        partes.append(f"Plan {plan}")
    return " — ".join(partes)


def formatear_nombre_escuela(valor):
    """Normaliza el nombre institucional de las escuelas para disposiciones.

    Regla: toda escuela debe figurar como "Escuela de ...", salvo Posgrado.
    Evita duplicar el prefijo si ya viene cargado en la base.
    """
    if valor is None or pd.isna(valor):
        return ""
    txt = " ".join(str(valor).strip().split())
    if not txt:
        return ""

    txt_lower = txt.lower()
    if "posgrado" in txt_lower:
        # Posgrado es la única excepción: no debe quedar antecedido por "Escuela de".
        return "Posgrado"

    mapa = {
        "administracion": "Escuela de Administración",
        "administración": "Escuela de Administración",
        "escuela administracion": "Escuela de Administración",
        "escuela de administracion": "Escuela de Administración",
        "escuela de administración": "Escuela de Administración",
        "ciencias juridicas politicas y sociales": "Escuela de Ciencias Jurídicas, Políticas y Sociales",
        "ciencias jurídicas políticas y sociales": "Escuela de Ciencias Jurídicas, Políticas y Sociales",
        "ciencias juridicas, politicas y sociales": "Escuela de Ciencias Jurídicas, Políticas y Sociales",
        "ciencias jurídicas, políticas y sociales": "Escuela de Ciencias Jurídicas, Políticas y Sociales",
        "escuela ciencias juridicas politicas y sociales": "Escuela de Ciencias Jurídicas, Políticas y Sociales",
        "escuela de ciencias juridicas politicas y sociales": "Escuela de Ciencias Jurídicas, Políticas y Sociales",
        "escuela de ciencias jurídicas políticas y sociales": "Escuela de Ciencias Jurídicas, Políticas y Sociales",
        "cs tecnologicas": "Escuela de Ciencias Tecnológicas",
        "cs tecnológicas": "Escuela de Ciencias Tecnológicas",
        "ciencias tecnologicas": "Escuela de Ciencias Tecnológicas",
        "ciencias tecnológicas": "Escuela de Ciencias Tecnológicas",
        "escuela cs tecnologicas": "Escuela de Ciencias Tecnológicas",
        "escuela cs tecnológicas": "Escuela de Ciencias Tecnológicas",
        "escuela de cs tecnologicas": "Escuela de Ciencias Tecnológicas",
        "escuela de cs tecnológicas": "Escuela de Ciencias Tecnológicas",
        "escuela ciencias tecnologicas": "Escuela de Ciencias Tecnológicas",
        "escuela ciencias tecnológicas": "Escuela de Ciencias Tecnológicas",
        "escuela de ciencias tecnologicas": "Escuela de Ciencias Tecnológicas",
        "escuela de ciencias tecnológicas": "Escuela de Ciencias Tecnológicas",
        "humanidades": "Escuela de Humanidades",
        "escuela humanidades": "Escuela de Humanidades",
        "escuela de humanidades": "Escuela de Humanidades",
        "salud": "Escuela de Salud",
        "escuela salud": "Escuela de Salud",
        "escuela de salud": "Escuela de Salud",
    }
    clave = txt_lower.replace(".", "").replace("-", " ").replace(",", " ")
    clave = " ".join(clave.split())
    if clave in mapa:
        return mapa[clave]

    if txt_lower.startswith("escuela de ") or txt_lower.startswith("escuela "):
        # Si ya viene con prefijo, lo respeta salvo abreviaturas conocidas que ya se normalizaron arriba.
        return txt.replace("Cs. Tecnológicas", "Ciencias Tecnológicas")

    return f"Escuela de {txt.replace('Cs. Tecnológicas', 'Ciencias Tecnológicas')}"


def detectar_conflictos_codigo_en_tabla(df_plan):
    """Detecta en una tabla pegada códigos repetidos con nombres distintos."""
    if df_plan is None or df_plan.empty:
        return pd.DataFrame()
    registros = []
    grupos = {}
    for idx, row in df_plan.iterrows():
        codigo = str(row.get("codigo", "") or "").strip()
        asignatura = str(row.get("asignatura", "") or "").strip()
        codigo_n = normalizar_codigo_materia(codigo)
        asig_n = normalizar_clave(asignatura)
        if not codigo_n or not asig_n:
            continue
        if codigo_n not in grupos:
            grupos[codigo_n] = {"codigo": codigo, "asignaturas": {}, "filas": []}
        grupos[codigo_n]["asignaturas"].setdefault(asig_n, asignatura)
        grupos[codigo_n]["filas"].append(int(idx) + 1)
    for codigo_n, data in grupos.items():
        if len(data["asignaturas"]) > 1:
            registros.append({
                "codigo": data["codigo"],
                "asignaturas_detectadas": " / ".join(data["asignaturas"].values()),
                "filas": ", ".join(map(str, data["filas"])),
                "motivo": "Mismo código con nombres distintos dentro de la tabla pegada",
            })
    return pd.DataFrame(registros)


def tipo_espacio_curricular_v120(codigo, asignatura):
    """Devuelve Optativa/Electiva para un espacio formal del plan o cadena vacía."""
    if not es_materia_optativa_electiva(codigo, asignatura):
        return ""
    nombre = normalizar_clave(asignatura or "").lower()
    if "electiva" in nombre:
        return "Electiva"
    if "optativa" in nombre:
        return "Optativa"
    return ""


def _etiqueta_espacio_plan_opcion_v124(row):
    """Etiqueta única y legible para seleccionar un espacio formal Optativa/Electiva."""
    try:
        materia_id = int(row.get("materia_id"))
    except Exception:
        materia_id = None
    tipo = limpiar_texto_tabla(row.get("tipo_espacio", ""))
    escuela = limpiar_texto_tabla(row.get("escuela", ""))
    carrera = limpiar_texto_tabla(row.get("carrera", ""))
    plan = limpiar_texto_tabla(row.get("plan_version", ""))
    codigo = limpiar_texto_tabla(row.get("codigo", ""))
    asignatura = limpiar_texto_tabla(row.get("asignatura", ""))
    anio = limpiar_texto_tabla(row.get("anio", ""))
    cuatri = limpiar_texto_tabla(row.get("cuatrimestre", ""))
    partes = [p for p in [tipo, escuela, carrera, plan, f"{codigo} - {asignatura}".strip(" -"), anio, f"Cuat. {cuatri}" if cuatri else ""] if p]
    etiqueta = " · ".join(partes)
    if materia_id is not None:
        etiqueta = f"{etiqueta} [ID:{materia_id}]" if etiqueta else f"[ID:{materia_id}]"
    return etiqueta


def leer_excel_carga_rapida_opciones_v124(contenido):
    """Lee y normaliza la hoja Carga rápida del modelo v124."""
    if not contenido:
        return pd.DataFrame()
    try:
        df = pd.read_excel(BytesIO(contenido), sheet_name="Carga rápida", engine="openpyxl", dtype=str)
    except ValueError:
        df = pd.read_excel(BytesIO(contenido), sheet_name=0, engine="openpyxl", dtype=str)
    if df is None or df.empty:
        return pd.DataFrame()
    renombres = {}
    for col in df.columns:
        k = _normalizar_encabezado_opcion_v124(col)
        if k in ["tipo"]:
            renombres[col] = "tipo"
        elif k in ["codigo_de_la_opcion", "codigo_opcion", "codigo"]:
            renombres[col] = "codigo"
        elif k in ["materia_concreta_que_se_ofrece", "materia_concreta", "opcion_concreta", "nombre", "materia"]:
            renombres[col] = "nombre"
        elif k in ["facultad_escuela_oferente", "escuela_oferente", "facultad_oferente"]:
            renombres[col] = "escuela_oferente"
        elif k == "estado":
            renombres[col] = "estado"
        elif k in ["observaciones", "observacion"]:
            renombres[col] = "observaciones"
        else:
            m = re.fullmatch(r"habilitacion_?(\d+)", k)
            if m:
                renombres[col] = f"habilitacion_{int(m.group(1))}"
    df = df.rename(columns=renombres)
    obligatorias = ["tipo", "nombre"]
    faltantes = [c for c in obligatorias if c not in df.columns]
    if faltantes:
        raise ValueError("El Excel no contiene las columnas obligatorias: " + ", ".join(faltantes) + ".")
    for col in ["codigo", "escuela_oferente", "estado", "observaciones"]:
        if col not in df.columns:
            df[col] = ""
    # Conservar solo columnas reconocidas, incluidas todas las Habilitación N que existan.
    habs = sorted([c for c in df.columns if re.fullmatch(r"habilitacion_\d+", str(c))], key=lambda x: int(x.split("_")[-1]))
    columnas = ["tipo", "codigo", "nombre", "escuela_oferente", "estado", "observaciones"] + habs
    df = df[columnas].copy()
    for col in columnas:
        df[col] = df[col].apply(limpiar_texto_tabla)
    df = df[df.apply(lambda r: any(str(v).strip() for v in r.tolist()), axis=1)].reset_index(drop=True)
    return df


def _buscar_opcion_equivalente_v124(df_ops, tipo, codigo, nombre, escuela_oferente=""):
    if df_ops is None or df_ops.empty:
        return pd.DataFrame()
    tipo_n = _normalizar_tipo_opcion_v120(tipo)
    cod_n = normalizar_codigo_materia(codigo)
    nom_n = normalizar_clave(nombre)
    esc_n = normalizar_clave(escuela_oferente)
    mask = (df_ops["tipo"].apply(_normalizar_tipo_opcion_v120) == tipo_n) & (df_ops["nombre"].apply(normalizar_clave) == nom_n)
    if cod_n:
        mask = mask & (df_ops["codigo"].fillna("").apply(normalizar_codigo_materia) == cod_n)
    if tipo_n == "Electiva":
        mask = mask & (df_ops["escuela_oferente"].fillna("").apply(normalizar_clave) == esc_n)
    return df_ops[mask].copy()


def etiqueta_opcion_curricular_v120(row):
    """Etiqueta inequívoca para UI/Excel; en Electivas incluye la escuela oferente."""
    codigo = limpiar_texto_tabla(row.get("codigo", ""))
    nombre = limpiar_texto_tabla(row.get("nombre", ""))
    escuela = limpiar_texto_tabla(row.get("escuela_oferente", ""))
    base = f"{codigo} - {nombre}".strip(" -") or nombre
    if _normalizar_tipo_opcion_v120(row.get("tipo", "")) == "Electiva" and escuela:
        return f"{base} · {escuela}"
    return base


def escuela_para_filtro(valor):
    """Convierte valores de filtros de Facultad/Escuela a parámetro SQL seguro."""
    valor = str(valor or "").strip()
    if not valor or valor in ["Todas", "Escribir manualmente"]:
        return None
    return valor


def _filtrar_busqueda_materias(df, texto, columnas_extra=None):
    """Busca materias por código o texto sin depender de guiones, espacios o mayúsculas."""
    df = df.copy()
    texto = str(texto or "").strip()
    if not texto or df.empty:
        return df

    q_texto = normalizar_clave(texto)
    q_codigo = normalizar_codigo_materia(texto)
    columnas = ["codigo", "asignatura"] + list(columnas_extra or [])
    columnas = [c for c in columnas if c in df.columns]

    def coincide(row):
        # Para código, se compara también sin guiones, espacios ni puntos.
        if "codigo" in row.index:
            cod = _valor_limpio_materia(row.get("codigo"))
            cod_norm = normalizar_codigo_materia(cod)
            if q_codigo and cod_norm and q_codigo in cod_norm:
                return True
            if q_texto and q_texto in normalizar_clave(cod):
                return True
        for col in columnas:
            if col == "codigo":
                continue
            val = _valor_limpio_materia(row.get(col))
            if q_texto and q_texto in normalizar_clave(val):
                return True
            # También permite búsquedas tipo 011 contra textos con código incluido.
            if q_codigo and q_codigo in normalizar_codigo_materia(val):
                return True
        return False

    return df[df.apply(coincide, axis=1)].copy().reset_index(drop=True)


def _normalizar_valor_reparacion_materia(valor):
    """Normalización estable para comparar metadatos de materias sin adivinar."""
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except Exception:
        pass
    return normalizar_clave(str(valor).strip())


def _elegir_representante_grupo_reparacion(grupo, fila_origen=None):
    """Elige un materia_id activo representativo, priorizando la misma carrera."""
    if grupo is None or grupo.empty:
        return None
    g = grupo.copy()
    if fila_origen is not None:
        try:
            carrera_origen = int(fila_origen.get("carrera_id"))
            misma = g[pd.to_numeric(g["carrera_id"], errors="coerce").fillna(-1).astype(int) == carrera_origen]
            if not misma.empty:
                g = misma
        except Exception:
            pass
    try:
        return int(pd.to_numeric(g["id"], errors="coerce").dropna().astype(int).sort_values().iloc[0])
    except Exception:
        return None


def _nombre_materia_visible_v138(codigo, asignatura, materia_especifica=""):
    """Nombre de presentación: una Optativa/Electiva nunca queda mostrada solo por su espacio formal."""
    base = limpiar_texto_tabla(asignatura)
    especifica = limpiar_texto_tabla(materia_especifica)
    if especifica:
        # Conserva el espacio formal porque es relevante para el plan, pero deja visible
        # la materia concreta realmente dictada.
        if base and normalizar_clave(especifica) not in normalizar_clave(base):
            return f"{base} ({especifica})"
        return especifica or base
    try:
        if es_materia_optativa_electiva(codigo, base):
            return f"{base} (sin opción específica registrada)" if base else "Optativa/Electiva (sin opción específica registrada)"
    except Exception:
        pass
    return base


def _clave_materia_unica_desde_codigo_nombre(codigo, asignatura):
    """Clave estable para tratar como única una materia repetida en varios planes."""
    codigo_n = normalizar_clave(codigo)
    asignatura_n = normalizar_clave(asignatura)
    if codigo_n:
        return f"{codigo_n}::{asignatura_n}"
    return f"SIN_CODIGO::{asignatura_n}"


def _etiqueta_plan_materia_v137(fila):
    carrera = limpiar_texto_tabla(fila.get("carrera", ""))
    plan = limpiar_texto_tabla(fila.get("plan_version", "")) or "Sin plan"
    escuela = limpiar_texto_tabla(fila.get("escuela", ""))
    codigo = limpiar_texto_tabla(fila.get("codigo", ""))
    asignatura = limpiar_texto_tabla(fila.get("asignatura", ""))
    return f"{carrera} — {plan} — {escuela} — {codigo} - {asignatura}".strip(" —")


def _ids_materia_v118(valor):
    """Normaliza lista/CSV de IDs de materia a enteros únicos."""
    if valor is None:
        return []
    if isinstance(valor, (list, tuple, set, pd.Series)):
        partes = list(valor)
    else:
        partes = re.split(r"[,;|]+", str(valor))
    salida = []
    for x in partes:
        try:
            mid = int(float(str(x).strip()))
        except Exception:
            continue
        if mid not in salida:
            salida.append(mid)
    return salida


def _fila_materia_por_id_v118(df_detalle, materia_id):
    if df_detalle is None or df_detalle.empty:
        return None
    col = "materia_id" if "materia_id" in df_detalle.columns else "id" if "id" in df_detalle.columns else None
    if col is None:
        return None
    mids = pd.to_numeric(df_detalle[col], errors="coerce").astype("Int64")
    fila = df_detalle[mids == int(materia_id)]
    return None if fila.empty else fila.iloc[0]


def _contexto_excel_materia_v175(codigo, asignatura, candidatos, carrera="", plan="", escuela=""):
    """Elige la misma etiqueta Carrera/plan que usa el Excel modelo."""
    codigo_n = normalizar_codigo_materia(codigo)
    asig_n = normalizar_clave(asignatura)
    matches = [r for r in candidatos if normalizar_codigo_materia(r.get("Código", "")) == codigo_n and normalizar_clave(r.get("Asignatura", "")) == asig_n]
    if not matches:
        matches = [r for r in candidatos if normalizar_clave(r.get("Asignatura", "")) == asig_n]
    if not matches:
        base = " — ".join([x for x in [limpiar_texto_tabla(carrera), limpiar_texto_tabla(plan), limpiar_texto_tabla(escuela)] if x])
        return f"[{limpiar_texto_tabla(codigo).upper()}] {base}".strip() if codigo else base
    buscado = normalizar_clave(" ".join([str(carrera or ""), str(plan or ""), str(escuela or "")]))
    if buscado:
        def score(r):
            ctx = normalizar_clave(r.get("Contexto para carga rápida", ""))
            partes = [normalizar_clave(x) for x in [carrera, plan, escuela] if normalizar_clave(x)]
            return sum(1 for p in partes if p and p in ctx)
        matches = sorted(matches, key=score, reverse=True)
    return limpiar_texto_tabla(matches[0].get("Contexto para carga rápida", ""))
