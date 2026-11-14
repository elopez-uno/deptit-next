"""Plantilla Word SINTETICA ZZNEXT para los tests de Disposiciones (decision D3).

No se copia ni se lee la plantilla productiva.  Esta plantilla minima y controlada cubre lo que el generador certificado
manipula: membrete (imagen en el encabezado), marcadores simples y partidos entre runs, encabezado y pie, considerandos
(``{{considerandos_designaciones}}``), bloques condicionales (concursado, interino, investigador / no investiga,
actividades especiales y sus formas ``{#...}``), Art. 1 docente en negrita, Art. 2 I/E y general, Art. 3/4, tabla de
firmas y autoridad Director/Directora.  ``antigua=True`` produce la plantilla historica SIN el marcador
``{{#SI_ACTIVIDADES_ESPECIALES}}`` (insercion v95 del Art. 3 y renumeracion 3->4, 4->5).
"""

from __future__ import annotations

import base64
import io

from docx import Document

# PNG 1x1 (membrete de prueba): el generador NO debe borrar el w:drawing del encabezado.
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/q842iQAAAABJRU5ErkJggg==")

ART1 = ("ARTÍCULO 1º.– Asígnese al docente {{docente}}, CUIL N° {{CUIL}}, el cumplimiento de funciones de docencia en "
        "{{asignaturas que dicta con días, horarios, las carreras a las que pertenecen y escuelas}}.")
ART2_IE = ("ARTÍCULO 2º.– Asígnese al docente {{docente}} CUIL N° {{CUIL}} el cumplimiento de funciones de "
           "{{Tipo funciones investigación/extensión}} {{Texto funciones de investigación}}.")
ART2_GENERAL = ("ARTÍCULO 2º.– Asígnese asimismo, al docente referido en el artículo anterior, en el caso de ser "
                "necesario, el resto de las horas de su contratación para la cobertura de horas docentes, "
                "investigación y/o extensión.")


def _bold(p, texto):
    r = p.add_run(texto)
    r.bold = True
    return r


def construir(antigua: bool = False, forma_corta: bool = False) -> bytes:
    """Bytes de la plantilla sintetica.  ``forma_corta`` usa ``{#BLOQUE}`` en vez de ``{{#BLOQUE}}``."""
    abre = (lambda n: "{#" + n + "}") if forma_corta else (lambda n: "{{#" + n + "}}")
    cierra = (lambda n: "{/" + n + "}") if forma_corta else (lambda n: "{{/" + n + "}}")
    doc = Document()
    sec = doc.sections[0]
    hp = sec.header.paragraphs[0]
    hp.add_run().add_picture(io.BytesIO(PNG_1X1))
    hp.add_run(" ZZNEXT Universidad — {{departamento_disposicion_encabezado}}")
    sec.footer.paragraphs[0].add_run("Firma: {{titulo_autoridad_departamento}} ({{cargo_autoridad_departamento_minuscula}})")

    _bold(doc.add_paragraph(), "DISPOSICIÓN N° {{número_disposición}}")
    doc.add_paragraph("Fecha: {{Fecha Disposición}}")
    p = doc.add_paragraph()  # marcador partido entre runs
    p.add_run("VISTO el acta del {{")
    p.add_run("fecha_acta_rector")
    p.add_run("}} y el expediente {{N° CUDAP EXP – UNO de la Asamblea Universitaria}};")
    doc.add_paragraph("CONSIDERANDO:")
    doc.add_paragraph("{{considerandos_designaciones}}")
    doc.add_paragraph(abre("SI_TIENE_CONCURSADO"))
    doc.add_paragraph("Que el docente {{docente}} es concursado como {{cargo}} con dedicación {{dedicación}} "
                      "({{horas}} hs) por Resolución CS {{resolucion_cs_concursado}};")
    doc.add_paragraph(cierra("SI_TIENE_CONCURSADO"))
    doc.add_paragraph(abre("SI_TIENE_INTERINO"))
    doc.add_paragraph("Que el docente {{docente}} es interino como {{cargo}} con dedicación {{dedicación}} por "
                      "Resolución Rectoral {{resolucion_rectoral_interino}} desde {{fecha_desde_interino}};")
    doc.add_paragraph(cierra("SI_TIENE_INTERINO"))
    doc.add_paragraph("Que el Director del Departamento {{director/a de departamento}} fue designado por "
                      "Resolución {{Número de Resolución Direector de Departamento}};")
    doc.add_paragraph("Por ello,")
    _bold(doc.add_paragraph(), "EL DIRECTOR DE DEPARTAMENTO")
    doc.add_paragraph("DISPONE:")
    _bold(doc.add_paragraph(), ART1)
    doc.add_paragraph(abre("SI_INVESTIGADOR"))
    _bold(doc.add_paragraph(), ART2_IE)
    doc.add_paragraph(cierra("SI_INVESTIGADOR"))
    doc.add_paragraph(abre("SI_NO_INVESTIGA"))
    _bold(doc.add_paragraph(), ART2_GENERAL)
    doc.add_paragraph(cierra("SI_NO_INVESTIGA"))
    if antigua:
        _bold(doc.add_paragraph(), "ARTÍCULO 3°.- El docente presentará la declaración jurada de cargos.")
        _bold(doc.add_paragraph(), "ARTÍCULO 4°.- Notifíquese a {{Escuelas en las que se encuentran las materias que "
                                   "dicta}}, regístrese y archívese.")
    else:
        doc.add_paragraph(abre("SI_ACTIVIDADES_ESPECIALES"))
        _bold(doc.add_paragraph(), "ARTÍCULO 3º.– {{Texto Actividades Especiales Cuerpo}}")
        _bold(doc.add_paragraph(), "ARTÍCULO 4º.– El docente presentará la declaración jurada de cargos.")
        _bold(doc.add_paragraph(), "ARTÍCULO 5º.– Notifíquese a {{Escuelas en las que se encuentran las materias que "
                                   "dicta}}, regístrese y archívese.")
        doc.add_paragraph(cierra("SI_ACTIVIDADES_ESPECIALES"))
        doc.add_paragraph(abre("SI_NO_ACTIVIDADES_ESPECIALES"))
        _bold(doc.add_paragraph(), "ARTÍCULO 3º.– El docente presentará la declaración jurada de cargos.")
        _bold(doc.add_paragraph(), "ARTÍCULO 4º.– Notifíquese a {{Escuelas en las que se encuentran las materias que "
                                   "dicta}}, regístrese y archívese.")
        doc.add_paragraph(cierra("SI_NO_ACTIVIDADES_ESPECIALES"))
    t = doc.add_table(rows=2, cols=2)
    t.cell(0, 0).text = "{{rector}}"
    t.cell(0, 1).text = "{{director/a de departamento}}"
    t.cell(1, 0).text = "Rector/a — DNI {{DNI Rector}}"
    t.cell(1, 1).text = "{{titulo_autoridad_departamento_mayusculas}} — DNI {{DNI director/a de departamento}}"
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


def textos(data: bytes) -> dict:
    """Parrafos del cuerpo / tablas / encabezado / pie con la negrita de cada run (para comparar documentos)."""
    doc = Document(io.BytesIO(data))
    cuerpo = [(p.text, [(r.text, r.bold) for r in p.runs]) for p in doc.paragraphs]
    tablas = [[c.text for c in row.cells] for t in doc.tables for row in t.rows]
    sec = doc.sections[0]
    return {"cuerpo": cuerpo, "tablas": tablas, "encabezado": [p.text for p in sec.header.paragraphs],
            "pie": [p.text for p in sec.footer.paragraphs],
            "dibujos_encabezado": len(sec.header._element.xpath(".//*[local-name()='drawing']"))}
