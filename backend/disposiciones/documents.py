"""Generador Word de Disposiciones (python-docx 1.2.0), cadena efectiva de B13-FIX02.

``generar_word_desde_plantilla_disposicion``: v249 l. 49987 -> v95 l. 32428 -> base l. 7653, con los auxiliares
l. 7246-7652 (recorrido de parrafos, reemplazo de nodos ``w:t`` que preserva el membrete, articulos de asignacion,
considerandos, bloques condicionales y genero de la autoridad), ``_reemplazar_numero_articulo_v95`` l. 32403 y
``_promover_investigacion_articulo_1_v249`` l. 49876.

La pagina, el membrete, las firmas, la tipografia y el texto fijo de los articulos viven en la plantilla de la
institucion; este modulo solo completa variables, decide bloques y reescribe Art. 1 (no docente / mixta), Art. 2 (I/E),
Art. 3 (Actividades Especiales) y la numeracion, igual que el certificado.  No genera PDF.  Excluido: la instalacion en
caliente de python-docx (``_obtener_document_python_docx``): la dependencia esta declarada (D4).
"""

from __future__ import annotations

import re
from copy import deepcopy

from docx import Document
from docx.text.paragraph import Paragraph

from . import rules as R


# --- recorrido y primitivas (l. 7246-7405) ---------------------------------------------------------------------------
def iter_parrafos_docx(document):
    for p in document.paragraphs:
        yield p
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    yield p
    for section in document.sections:
        for p in section.header.paragraphs:
            yield p
        for p in section.footer.paragraphs:
            yield p
        for table in section.header.tables:
            for row in table.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        yield p
        for table in section.footer.tables:
            for row in table.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        yield p


def eliminar_parrafo(parrafo) -> None:
    elemento = parrafo._element
    padre = elemento.getparent()
    if padre is not None:
        padre.remove(elemento)


def run_tiene_contenido_no_textual(run) -> bool:
    """Imagenes, objetos o campos: asignar ``run.text`` los borraria (por ejemplo, el membrete del encabezado)."""
    try:
        return bool(run._r.xpath(
            ".//*[local-name()='drawing' or local-name()='pict' "
            "or local-name()='object' or local-name()='AlternateContent' "
            "or local-name()='fldChar' or local-name()='instrText']"
        ))
    except Exception:
        return False


def transformar_textos_run_sin_reconstruir(run, transformacion) -> bool:
    """Modifica solo nodos ``w:t``: preserva dibujos, campos y objetos del run."""
    cambio = False
    try:
        nodos_texto = run._r.xpath(".//*[local-name()='t']")
    except Exception:
        nodos_texto = []
    for nodo in nodos_texto:
        original = nodo.text or ""
        nuevo = transformacion(original)
        if nuevo != original:
            nodo.text = nuevo
            cambio = True
    return cambio


def vaciar_texto_run_sin_borrar_objetos(run) -> None:
    try:
        nodos_texto = run._r.xpath(".//*[local-name()='t']")
    except Exception:
        nodos_texto = []
    for nodo in nodos_texto:
        nodo.text = ""


def reemplazar_texto_en_parrafo(parrafo, variables: dict) -> None:
    def reemplazar_fragmento(texto):
        nuevo = texto
        for clave, valor in variables.items():
            if isinstance(valor, (bool, dict, list)):
                continue
            nuevo = nuevo.replace("{{" + str(clave) + "}}", "" if valor is None else str(valor))
        return nuevo

    for run in parrafo.runs:
        transformar_textos_run_sin_reconstruir(run, reemplazar_fragmento)

    # Variables partidas entre varios runs: se vacia solo el texto y se preservan los objetos del parrafo.
    texto_total = parrafo.text
    if "{{" in texto_total and "}}" in texto_total:
        nuevo_total = reemplazar_fragmento(texto_total)
        if nuevo_total != texto_total:
            runs = list(parrafo.runs)
            for run in runs:
                vaciar_texto_run_sin_borrar_objetos(run)
            run_destino = next((run for run in runs if not run_tiene_contenido_no_textual(run)), None)
            if run_destino is None:
                run_destino = parrafo.add_run()
            try:
                nodos_texto = run_destino._r.xpath(".//*[local-name()='t']")
            except Exception:
                nodos_texto = []
            if nodos_texto:
                nodos_texto[0].text = nuevo_total
            else:
                run_destino.text = nuevo_total


def copiar_formato_run(origen, destino, forzar_negrita=None) -> None:
    try:
        destino.style = origen.style
    except Exception:
        pass
    try:
        destino.font.name = origen.font.name
        destino.font.size = origen.font.size
        destino.font.italic = origen.font.italic
        destino.font.underline = origen.font.underline
        destino.font.color.rgb = origen.font.color.rgb
    except Exception:
        pass
    destino.bold = forzar_negrita if forzar_negrita is not None else origen.bold


def agregar_run_con_formato(parrafo, texto, run_base=None, negrita=False):
    if not texto:
        return None
    run = parrafo.add_run(texto)
    if run_base is not None:
        copiar_formato_run(run_base, run, forzar_negrita=negrita)
    else:
        run.bold = negrita
    return run


_ROTULO_RE = r"^(ART[IÍ]CULO\s+\d+[º°]?.*?[–-]\s*)"


# --- articulos (l. 7408-7547) ---------------------------------------------------------------------------------------
def reemplazar_articulo_asignacion_docente(parrafo, variables: dict) -> bool:
    """Art. 1 (docencia) y Art. 2 (investigacion): rotulo en negrita, cuerpo normal y solo ``{{docente}}`` en negrita."""
    texto = parrafo.text or ""
    es_articulo_docencia = ("ARTÍCULO 1" in texto.upper()
                            and any(m in texto for m in R.VARIABLES_ASIGNATURAS_DISPOSICION))
    es_articulo_investigacion = (
        "ARTÍCULO 2" in texto.upper()
        and ("{{Nombre Proyecto de Investigación}}" in texto
             or "{{Texto funciones de investigación}}" in texto
             or "{{Texto funciones de investigación y extensión}}" in texto)
    )
    if not (es_articulo_docencia or es_articulo_investigacion):
        return False

    marcador_docente = "§§DOCENTE§§"
    texto_reemplazado = R.reemplazar_variables_manteniendo_docente(texto, variables, marcador_docente=marcador_docente)

    # v167: 1) solo no docente reemplaza el cuerpo; 2) mixta agrega las funciones no docentes; 3) solo docente igual.
    if es_articulo_docencia and bool(variables.get("ES_FUNCION_NO_DOCENTE")):
        texto_funcion_no_docente = str(variables.get("Texto función no docente", "") or "").strip().rstrip(".")
        cuil_txt = "" if variables.get("CUIL") is None else str(variables.get("CUIL", ""))
        patron_tmp = re.match(_ROTULO_RE, texto_reemplazado, flags=re.IGNORECASE)
        rotulo_tmp = patron_tmp.group(1) if patron_tmp else "ARTÍCULO 1º.– "
        texto_reemplazado = (f"{rotulo_tmp}Asígnese al/la docente {marcador_docente}, CUIL N° {cuil_txt}, "
                             f"el cumplimiento de funciones {texto_funcion_no_docente}.")
    elif es_articulo_docencia and bool(variables.get("ES_FUNCION_MIXTA")):
        texto_funcion_no_docente = str(variables.get("Texto función no docente", "") or "").strip().rstrip(".")
        if texto_funcion_no_docente:
            base_docente = str(texto_reemplazado or "").rstrip()
            if base_docente.endswith("."):
                base_docente = base_docente[:-1].rstrip()
            texto_reemplazado = f"{base_docente} y de funciones {texto_funcion_no_docente}."

    # Investigacion/extension: el cuerpo sale de la variable consolidada (varios proyectos).
    if es_articulo_investigacion and variables.get("Texto funciones de investigación"):
        texto_inv = str(variables.get("Texto funciones de investigación", "")).strip()
        texto_inv = texto_inv.rstrip(".")
        tipo_funciones = str(variables.get("Tipo funciones investigación/extensión", "investigación")
                             or "investigación").strip()
        cuil_txt = "" if variables.get("CUIL") is None else str(variables.get("CUIL", ""))
        patron_tmp = re.match(_ROTULO_RE, texto_reemplazado, flags=re.IGNORECASE)
        rotulo_tmp = patron_tmp.group(1) if patron_tmp else "ARTÍCULO 2º.– "
        texto_reemplazado = (f"{rotulo_tmp}Asígnese al docente {marcador_docente} CUIL N° {cuil_txt} el cumplimiento "
                             f"de funciones de {tipo_funciones} {texto_inv}.")

    patron_rotulo = re.match(_ROTULO_RE, texto_reemplazado, flags=re.IGNORECASE)
    rotulo = patron_rotulo.group(1) if patron_rotulo else ""
    cuerpo = texto_reemplazado[len(rotulo):] if rotulo else texto_reemplazado

    runs_originales = list(parrafo.runs)
    run_base = runs_originales[0] if runs_originales else None
    for r in runs_originales:
        r.text = ""

    if rotulo:
        if runs_originales:
            run_rotulo = runs_originales[0]
            run_rotulo.text = rotulo
            if run_base is not None:
                copiar_formato_run(run_base, run_rotulo, forzar_negrita=True)
            else:
                run_rotulo.bold = True
        else:
            agregar_run_con_formato(parrafo, rotulo, run_base, negrita=True)

    partes = cuerpo.split(marcador_docente)
    docente_valor = "" if variables.get("docente") is None else str(variables.get("docente", ""))
    for i, parte in enumerate(partes):
        agregar_run_con_formato(parrafo, parte, run_base, negrita=False)
        if i < len(partes) - 1:
            agregar_run_con_formato(parrafo, docente_valor, run_base, negrita=True)
    return True


def reemplazar_articulo_1_asignaturas_sin_negrita(parrafo, variables: dict) -> bool:
    """La lista de asignaturas del Art. 1 queda sin negrita aunque la plantilla traiga el articulo en negrita."""
    texto = parrafo.text or ""
    marcador = next((m for m in R.VARIABLES_ASIGNATURAS_DISPOSICION if m in texto), None)
    if not marcador:
        return False

    valor_asignaturas = variables.get(marcador.strip("{}"), "")
    antes, despues = texto.split(marcador, 1)
    antes = R.reemplazar_variables_texto_simple(antes, variables)
    despues = R.reemplazar_variables_texto_simple(despues, variables)

    runs_originales = list(parrafo.runs)
    run_base = runs_originales[0] if runs_originales else None
    for r in runs_originales:
        r.text = ""

    if run_base is not None and runs_originales:
        run_antes = runs_originales[0]
        run_antes.text = antes
    else:
        run_antes = parrafo.add_run(antes)
    if run_base is not None:
        copiar_formato_run(run_base, run_antes, forzar_negrita=True)

    run_asig = parrafo.add_run("" if valor_asignaturas is None else str(valor_asignaturas))
    if run_base is not None:
        copiar_formato_run(run_base, run_asig, forzar_negrita=False)
    else:
        run_asig.bold = False

    if despues:
        run_despues = parrafo.add_run(despues)
        if run_base is not None:
            copiar_formato_run(run_base, run_despues, forzar_negrita=False)
    return True


def insertar_parrafos_desde_marcador_lista(document, marcador: str, textos) -> bool:
    """El parrafo marcador se reemplaza por un parrafo clonado por texto (conserva formato); lista vacia -> desaparece."""
    encontrados = False
    for parrafo in list(iter_parrafos_docx(document)):
        if marcador not in (parrafo.text or ""):
            continue
        encontrados = True
        valores = textos if isinstance(textos, (list, tuple)) else ([textos] if textos else [])
        for valor in valores:
            elemento_nuevo = deepcopy(parrafo._p)
            parrafo._p.addprevious(elemento_nuevo)
            nuevo = Paragraph(elemento_nuevo, parrafo._parent)
            runs = list(nuevo.runs)
            for run in runs:
                run.text = ""
            if runs:
                runs[0].text = "" if valor is None else str(valor)
            else:
                nuevo.add_run("" if valor is None else str(valor))
        eliminar_parrafo(parrafo)
    return encontrados


def aplicar_genero_autoridad_documento(document, variables: dict) -> None:
    """Director/Directora sobre los nodos de texto existentes (sin borrar el membrete)."""
    cargo = R.cargo_autoridad_departamento(variables)
    if cargo == "Directora":
        reemplazos = {
            "EL DIRECTOR DE DEPARTAMENTO": "LA DIRECTORA DE DEPARTAMENTO",
            "El Director del Departamento": "La Directora del Departamento",
            "el Director del Departamento": "la Directora del Departamento",
            "Director del ": "Directora del ",
            "director del ": "directora del ",
        }
    else:
        reemplazos = {
            "LA DIRECTORA DE DEPARTAMENTO": "EL DIRECTOR DE DEPARTAMENTO",
            "La Directora del Departamento": "El Director del Departamento",
            "la Directora del Departamento": "el Director del Departamento",
            "Directora del ": "Director del ",
            "directora del ": "director del ",
        }

    def ajustar_fragmento(contenido):
        nuevo = contenido or ""
        for origen, destino in reemplazos.items():
            nuevo = nuevo.replace(origen, destino)
        return nuevo

    for parrafo in list(iter_parrafos_docx(document)):
        for run in parrafo.runs:
            transformar_textos_run_sin_reconstruir(run, ajustar_fragmento)


# --- base l. 7653 ---------------------------------------------------------------------------------------------------
_BLOQUES = ("SI_TIENE_CONCURSADO", "SI_TIENE_INTERINO", "SI_INVESTIGADOR", "SI_NO_INVESTIGA", "SI_ACTIVIDADES_ESPECIALES",
            "SI_NO_ACTIVIDADES_ESPECIALES")


def _generar_base(plantilla_path, salida_path, variables: dict, condiciones: dict) -> None:
    document = Document(plantilla_path)
    insertar_parrafos_desde_marcador_lista(document, "{{considerandos_designaciones}}",
                                           variables.get("considerandos_designaciones", []))
    bloques = {nombre: bool(condiciones.get(nombre, False)) for nombre in _BLOQUES}

    pila_bloques: list[str] = []
    for p in list(iter_parrafos_docx(document)):
        txt = p.text.strip()
        inicio = cierre = None
        for nombre in bloques:
            if txt in ["{{#" + nombre + "}}", "{#" + nombre + "}"]:
                inicio = nombre
                break
            if txt in ["{{/" + nombre + "}}", "{/" + nombre + "}"]:
                cierre = nombre
                break
        if inicio:
            pila_bloques.append(inicio)
            eliminar_parrafo(p)
            continue
        if cierre:
            if pila_bloques:
                pila_bloques.pop()
            eliminar_parrafo(p)
            continue
        if pila_bloques:
            bloque_activo = all(bloques.get(nombre, False) for nombre in pila_bloques)
            if not bloque_activo:
                eliminar_parrafo(p)
            else:
                # Dentro del bloque, variables especificas del tipo (no mezclar concursado e interino).
                vars_bloque = R.variables_para_bloque_disposicion(variables, pila_bloques[-1])
                if not reemplazar_articulo_asignacion_docente(p, vars_bloque):
                    if not reemplazar_articulo_1_asignaturas_sin_negrita(p, vars_bloque):
                        reemplazar_texto_en_parrafo(p, vars_bloque)

    variables_generales = dict(variables)
    variables_generales["resolucion_rectoral_interino"] = variables_generales.get(
        "resolucion_rectoral_interino", variables_generales.get("resolucion_cs_interino", ""))
    cargo_directivo = R.cargo_autoridad_departamento(variables_generales)
    variables_generales["cargo_autoridad_departamento"] = cargo_directivo
    variables_generales["cargo_autoridad_departamento_minuscula"] = cargo_directivo.lower()
    variables_generales["titulo_autoridad_departamento"] = f"{cargo_directivo} del Departamento"
    variables_generales["titulo_autoridad_departamento_mayusculas"] = (
        "LA DIRECTORA DE DEPARTAMENTO" if cargo_directivo == "Directora" else "EL DIRECTOR DE DEPARTAMENTO")
    for p in list(iter_parrafos_docx(document)):
        if not reemplazar_articulo_asignacion_docente(p, variables_generales):
            if not reemplazar_articulo_1_asignaturas_sin_negrita(p, variables_generales):
                reemplazar_texto_en_parrafo(p, variables_generales)

    aplicar_genero_autoridad_documento(document, variables_generales)
    document.save(salida_path)


# --- v95 l. 32403-32475 ---------------------------------------------------------------------------------------------
def reemplazar_numero_articulo_v95(parrafo, origen, destino) -> bool:
    texto = str(parrafo.text or "")
    patron = re.compile(rf"^\s*ART[ÍI]CULO\s+{origen}\s*[º°]?\s*[.\-–—]*\s*", re.I)
    if not patron.search(texto):
        return False
    cuerpo = patron.sub("", texto, count=1).lstrip()
    prefijo = f"ARTÍCULO {destino}º.– "
    runs = list(parrafo.runs)
    for run in runs:
        run.text = ""
    if runs:
        runs[0].text = prefijo
        runs[0].bold = True
        if len(runs) > 1:
            runs[1].text = cuerpo
            runs[1].bold = False
        else:
            r = parrafo.add_run(cuerpo)
            r.bold = False
    else:
        r1 = parrafo.add_run(prefijo)
        r1.bold = True
        r2 = parrafo.add_run(cuerpo)
        r2.bold = False
    return True


def _generar_v95(plantilla_path, salida_path, variables, condiciones) -> None:
    variables2 = dict(variables or {})
    texto = str(variables2.get("Texto Actividades Especiales") or variables2.get("texto_actividades_especiales")
                or "").strip()
    cuerpo = str(variables2.get("Texto Actividades Especiales Cuerpo")
                 or variables2.get("texto_actividades_especiales_cuerpo") or "").strip()
    if texto and not cuerpo:
        cuerpo = R.cuerpo_actividades_especiales(texto)
    variables2["Texto Actividades Especiales Cuerpo"] = cuerpo
    variables2["texto_actividades_especiales_cuerpo"] = cuerpo

    condiciones2 = dict(condiciones or {})
    tiene_actividades = bool(texto or cuerpo or variables2.get("tiene_actividades_especiales"))
    condiciones2["SI_ACTIVIDADES_ESPECIALES"] = tiene_actividades
    condiciones2["SI_NO_ACTIVIDADES_ESPECIALES"] = not tiene_actividades

    # Las plantillas nuevas resuelven el Art. 3 con su marcador; las antiguas reciben la insercion v95.
    usa_condicional_actividades = False
    try:
        doc_tpl = Document(plantilla_path)
        for p in iter_parrafos_docx(doc_tpl):
            t = (p.text or "").strip()
            if t in {"{{#SI_ACTIVIDADES_ESPECIALES}}", "{#SI_ACTIVIDADES_ESPECIALES}"}:
                usa_condicional_actividades = True
                break
    except Exception:
        usa_condicional_actividades = False

    _generar_base(plantilla_path, salida_path, variables2, condiciones2)
    if usa_condicional_actividades or not tiene_actividades:
        return

    doc = Document(salida_path)
    p3 = p4 = None
    for p in list(iter_parrafos_docx(doc)):
        t = (p.text or "").strip().upper().replace("º", "°")
        if p3 is None and re.match(r"ART[ÍI]CULO\s+3\s*°", t):
            p3 = p
        elif p4 is None and re.match(r"ART[ÍI]CULO\s+4\s*°", t):
            p4 = p
    if p3 is None:
        return
    if p4 is not None:
        reemplazar_numero_articulo_v95(p4, 4, 5)
    reemplazar_numero_articulo_v95(p3, 3, 4)
    nuevo = p3.insert_paragraph_before()
    nuevo.style = p3.style
    pref = "ARTÍCULO 3°.– "
    resto = cuerpo or texto
    r1 = nuevo.add_run(pref)
    r1.bold = True
    nuevo.add_run(resto)
    doc.save(salida_path)


# --- v249 l. 49876-49991 --------------------------------------------------------------------------------------------
def promover_investigacion_articulo_1_v249(salida_path, variables, condiciones) -> bool:
    """Sin comisiones (docente exclusivamente docente con I/E): I/E pasa al Art. 1 y se inserta el Art. 2 general."""
    variables = dict(variables or {})
    condiciones = dict(condiciones or {})
    if not bool(condiciones.get("SI_INVESTIGADOR", False)):
        return False
    if not R.designacion_es_exclusivamente_docente_v249(variables):
        return False
    if R.texto_asignaturas_variables_v249(variables):
        return False
    texto_ie = str(variables.get("Texto funciones de investigación", "")
                   or variables.get("Texto funciones de investigación y extensión", "") or "").strip()
    if not texto_ie:
        return False

    doc = Document(salida_path)
    patron_art = re.compile(r"^\s*ART[ÍI]CULO\s+(\d+)\s*[º°]?\s*[.\-–—]*\s*", re.I)
    articulo_1 = articulo_ie = None
    for p in list(iter_parrafos_docx(doc)):
        m = patron_art.match(str(p.text or ""))
        if not m:
            continue
        numero = int(m.group(1))
        if numero == 1 and articulo_1 is None:
            articulo_1 = p
        elif numero == 2 and articulo_ie is None:
            articulo_ie = p
    # Si la estructura no coincide con la historica (I/E en el Art. 2) no se toca el Word.
    if articulo_1 is None or articulo_ie is None:
        return False

    cuerpo_ie_esperado = patron_art.sub("", texto_ie, count=1).strip()
    cuerpo_ie_real = patron_art.sub("", str(articulo_ie.text or ""), count=1).strip()
    if cuerpo_ie_esperado:
        esperado_norm = R.normalizar_clave(cuerpo_ie_esperado)
        real_norm = R.normalizar_clave(cuerpo_ie_real)
        muestra = esperado_norm[:80]
        if muestra and muestra not in real_norm and real_norm[:80] not in esperado_norm:
            return False

    eliminar_parrafo(articulo_1)
    reemplazar_numero_articulo_v95(articulo_ie, 2, 1)

    # El Art. 2 general se CLONA del parrafo de la plantilla para conservar su formato.
    elemento_nuevo = deepcopy(articulo_ie._p)
    articulo_ie._p.addnext(elemento_nuevo)
    nuevo = Paragraph(elemento_nuevo, articulo_ie._parent)

    runs_nuevo = list(nuevo.runs)
    run_base = runs_nuevo[0] if runs_nuevo else None
    for run in runs_nuevo:
        run.text = ""
    if runs_nuevo:
        prefijo = runs_nuevo[0]
        prefijo.text = "ARTÍCULO 2º.– "
        if run_base is not None:
            copiar_formato_run(run_base, prefijo, forzar_negrita=True)
        else:
            prefijo.bold = True
    else:
        prefijo = nuevo.add_run("ARTÍCULO 2º.– ")
        prefijo.bold = True
    cuerpo = nuevo.add_run(R.ARTICULO_2_GENERAL_V249)
    if run_base is not None:
        copiar_formato_run(run_base, cuerpo, forzar_negrita=False)
    else:
        cuerpo.bold = False
    doc.save(salida_path)
    return True


def generar_word_desde_plantilla_disposicion(plantilla_path, salida_path, variables, condiciones) -> None:
    """Cadena efectiva: v249 -> v95 -> base.  ``plantilla_path`` es la copia privada de la plantilla ya validada.

    6A-B3 (aceptacion humana): el Word generado no puede conservar marcadores ``{{...}}`` / ``{#...}`` / ``{/...}``.
    Si la plantilla trae uno que el generador no conoce o no alcanza, se falla con un error claro (el temporal y la
    reserva se descartan en ``publish_output``: no se publica ni se registra un Word defectuoso)."""
    _generar_v95(plantilla_path, salida_path, variables, condiciones)
    promover_investigacion_articulo_1_v249(salida_path, variables, condiciones)
    restantes = marcadores_remanentes(salida_path)
    if restantes:
        raise ValueError(MSG_MARCADORES.format(lista=", ".join(restantes[:10])
                                               + (f" (y {len(restantes) - 10} más)" if len(restantes) > 10 else "")))


MSG_MARCADORES = ("La plantilla Word de la institución tiene marcadores que el generador no reconoce o no puede "
                  "completar: {lista}. No se generó la disposición. Corregí la plantilla en Configuración.")
_MARCADOR = re.compile(r"\{\{[^{}]*\}\}|\{[#/][^{}]*\}")
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_PARTES = re.compile(r"^word/(document|header\d*|footer\d*|footnotes|endnotes)\.xml$")


def marcadores_remanentes(docx_path) -> list[str]:
    """Marcadores sin reemplazar en TODO el texto visible del .docx (cuerpo, tablas, encabezados, pies, cuadros de
    texto y notas), uniendo los ``w:t`` de cada parrafo: detecta tambien marcadores partidos entre runs."""
    import xml.etree.ElementTree as ET
    import zipfile
    encontrados: list[str] = []
    with zipfile.ZipFile(docx_path) as z:
        for nombre in sorted(n for n in z.namelist() if _PARTES.match(n)):
            raiz = ET.fromstring(z.read(nombre))
            for p in raiz.iter(f"{_W}p"):
                texto = "".join(t.text or "" for t in p.iter(f"{_W}t"))
                for m in _MARCADOR.findall(texto):
                    if m not in encontrados:
                        encontrados.append(m)
    return encontrados


__all__ = ["generar_word_desde_plantilla_disposicion", "iter_parrafos_docx", "reemplazar_numero_articulo_v95",
           "promover_investigacion_articulo_1_v249"]
