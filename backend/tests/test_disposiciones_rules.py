"""Diferenciales PUROS de Disposiciones contra B13-FIX02 (sin escribir en la base):

- reglas de texto (considerandos, normalizadores, fechas, escuelas, prefijos, genero, v249) contra las funciones
  certificadas de ``deptit_refactor``;
- generador Word: el certificado (cadena v249 -> v95 -> base ejecutada por AST con python-docx 1.2.0) y NEXT sobre la
  MISMA plantilla sintetica y las mismas variables producen las MISMAS partes XML del .docx;
- almacenamiento B12E: validacion DOCX, nombres, referencias, contencion de rutas, enlaces, reserva/publicacion y ZIP
  contra ``deptit_refactor/b12e/document_isolation.py``.
"""

from __future__ import annotations

import hashlib
import io
import os
import zipfile

import pytest

import disposiciones_plantilla as P
from disposiciones import documents as D
from disposiciones import rules as R
from disposiciones import storage as S
from disposiciones_support import certified_disposiciones, db_conn  # noqa: F401  (fixture)
from periodos_support import FIXED_TODAY  # noqa: F401

from deptit_refactor.b12e import document_isolation as B  # noqa: E402  (reference_fix02, solo lectura)
from deptit_refactor.common import dates as cert_dates, identifiers as cert_ids, text as cert_text  # noqa: E402
from deptit_refactor.domain import designaciones as cert_ddes, documentos as cert_doc  # noqa: E402
from deptit_refactor.domain import materias as cert_mat, proyectos as cert_proy  # noqa: E402
from deptit_refactor.extracted_batch01 import designaciones as b01d, docentes as b01doc, otros as b01o  # noqa: E402
from deptit_refactor.extracted_batch01 import periodos as b01p  # noqa: E402
from deptit_refactor.extracted_batch02 import safe_helpers as b02  # noqa: E402

TEXTOS = [None, "", "  ", "Concursado", " interino ", "INTERINO", "Contratado", "  a   b  ", 7, "Departamento de X",
          "departamento  del  Sur", "Depto. de Biología", "Secretaría de Extensión", "área de Vinculación", "de la Nación",
          "Instituto de Ingenierías", "Escuela de Salud", "cs. tecnológicas", "Posgrado en X", "Administración",
          "Cs. Tecnológicas aplicadas", "sí", "Si", "1", "true", "no", "Ñandú Ünico"]
FECHAS = [None, "", "2027-08-01", "2026-3-1", "01/08/2027", "1-8-2027", "31/12/2026", "01 de marzo de 2026", "texto",
          "2026-02-30", float("nan")]


# 6A-B3 (unidades académicas): divergencia DECIDIDA respecto del certificado, que antepone "Escuela de" a una
# denominación institucional completa ("Escuela de Instituto de ..."). El resto de TEXTOS sigue idéntico.
ESCUELA_DIVERGE = {"Departamento de X": "Departamento de X", "departamento  del  Sur": "departamento del Sur",
                   "Depto. de Biología": "Depto. de Biología", "Secretaría de Extensión": "Secretaría de Extensión",
                   "área de Vinculación": "área de Vinculación", "Instituto de Ingenierías": "Instituto de Ingenierías"}


@pytest.mark.parametrize("valor", TEXTOS)
def test_normalizadores_y_prefijos(valor):
    assert R.normalizar_texto_disposicion(valor) == b01o._normalizar_texto_disposicion(valor)
    assert R.normalizar_tipo_designacion_disposicion(valor) == b02._normalizar_tipo_designacion_disposicion(valor)
    assert R.texto_funcion_no_docente_limpio_v164(valor) == b01doc._texto_funcion_no_docente_limpio_v164(valor)
    assert R.es_ad_honorem_v162(valor) == b01d._es_ad_honorem_v162(valor)
    assert R.clave_departamento_dispo_v159(valor) == cert_ids._clave_departamento_dispo_v159(valor)
    assert R.clave_unidad_proyecto_notificacion_v215(valor) == b02._clave_unidad_proyecto_notificacion_v215(valor)
    assert R.nombre_departamento_para_considerando(valor) == b02._nombre_departamento_para_considerando(valor)
    assert R.nombre_archivo_seguro(valor) == cert_text.nombre_archivo_seguro(valor)
    if valor is not None:
        if valor in ESCUELA_DIVERGE:
            assert cert_mat.formatear_nombre_escuela(valor).startswith("Escuela de ")
            assert R.formatear_nombre_escuela(valor) == ESCUELA_DIVERGE[valor]
        else:
            assert R.formatear_nombre_escuela(valor) == cert_mat.formatear_nombre_escuela(valor)
        assert R.prefijo_instituto_proyecto(valor) == cert_proy._prefijo_instituto_proyecto(valor)
        assert R.prefijo_area_extension(valor) == cert_proy._prefijo_area_extension(valor)


@pytest.mark.parametrize("valor", FECHAS)
def test_formatear_fecha_larga(valor):
    assert R.formatear_fecha_larga(valor) == cert_dates.formatear_fecha_larga(valor)


def test_listas_y_clave_numero_inicial():
    for vals in ([], ["A"], ["A", "A", " B "], ["A", "B", "C", ""], [None, "x"]):
        assert R.unir_lista_natural(vals) == cert_text._unir_lista_natural(vals)
        assert R.unir_items_administrativos(vals) == cert_text._unir_items_administrativos(vals)
    for pid in (1, "9", 14.0):
        assert R.clave_numero_inicial_disposicion_v162(pid) == b01p._clave_numero_inicial_disposicion_v162(pid)


REGISTROS = [
    {"tipo_designacion": "Concursado", "departamento": "Informática", "cargo": "JTP", "dedicacion": "Simple",
     "ad_honorem": "No", "resolucion": "123/24", "fecha_desde": "2026-03-01", "fecha_hasta": "2027-02-28"},
    {"tipo_designacion": "concursado", "departamento": "Departamento de Biología", "cargo": "Adjunto",
     "dedicacion": "Parcial", "ad_honorem": "Sí", "resolucion": "123/24 ", "fecha_desde": "2026-03-01",
     "fecha_hasta": "2027-02-28"},
    {"tipo_designacion": "Interino", "departamento": "", "cargo": "", "dedicacion": "", "resolucion": "",
     "fecha_desde": "01/08/2026", "fecha_hasta": ""},
    {"tipo_designacion": "Interino", "departamento": "Informática", "cargo": "Ayudante", "dedicacion": "Simple",
     "resolucion": "", "fecha_desde": "", "fecha_hasta": "2026-12-31"},
    {"tipo_designacion": "Contratado", "departamento": "X", "cargo": "Y", "dedicacion": "Z"},
]


@pytest.mark.parametrize("conc,inter", [(True, True), (True, False), (False, True), (False, False)])
def test_considerandos_agrupados(conc, inter):
    for regs in (REGISTROS, REGISTROS[:1], REGISTROS[2:], [], None):
        assert R.construir_considerandos_designaciones_docente("ZZNEXT, Ana", "20-99130001-1", regs, conc, inter) == \
            cert_doc.construir_considerandos_designaciones_docente("ZZNEXT, Ana", "20-99130001-1", regs, conc, inter)


def test_variables_bloque_v249_y_reemplazos():
    v = {"cargo": "G", "cargo_concursado": "C", "dedicación_interino": "DI", "resolucion_cs_interino": "R1",
         "docente": "D", "lista": [1], "flag": True, "nada": None, "n": 3,
         "asignaturas que dicta con las carreras a las que pertenecen y escuelas": " x ",
         "ES_FUNCION_MIXTA": False, "designaciones_disposicion": [{"funcion_no_docente": 0}, {"funcion_no_docente": "0"}]}
    for bloque in (None, "SI_TIENE_CONCURSADO", "SI_TIENE_INTERINO", "SI_INVESTIGADOR"):
        assert R.variables_para_bloque_disposicion(v, bloque) == b01d._variables_para_bloque_disposicion(v, bloque)
    texto = "{{docente}} {{cargo}} {{lista}} {{flag}} {{nada}} {{n}} {{otro}}"
    assert R.reemplazar_variables_texto_simple(texto, v) == b01o._reemplazar_variables_texto_simple(texto, v)
    assert R.reemplazar_variables_manteniendo_docente(texto, v) == \
        b01doc._reemplazar_variables_manteniendo_docente(texto, v)
    for vv in (v, {**v, "ES_FUNCION_MIXTA": True}, {**v, "designaciones_disposicion": []},
               {**v, "designaciones_disposicion": [{"funcion_no_docente": 1}]}):
        assert R.designacion_es_exclusivamente_docente_v249(vv) == cert_ddes._designacion_es_exclusivamente_docente_v249(vv)
        assert R.texto_asignaturas_variables_v249(vv) == cert_doc._texto_asignaturas_variables_v249(vv)
    assert R.VARIABLES_ASIGNATURAS_DISPOSICION == __import__(
        "deptit_refactor.catalogs.documentos", fromlist=["x"]).VARIABLES_ASIGNATURAS_DISPOSICION


def test_cargo_autoridad_y_estado_consulta(db_conn):
    ns = certified_disposiciones(db_conn, 1, 1)
    for p in ({}, {"genero_director_departamento": "Directora"}, {"genero_director_departamento": " directora "},
              {"genero_director_departamento": "Director"}, {"genero_director_departamento": None}):
        assert R.cargo_autoridad_departamento(p) == ns["cargo_autoridad_departamento"](p or {"x": 1})
    assert R.PARAMETROS_DISPOSICION_DEFAULT == ns["PARAMETROS_DISPOSICION_DEFAULT"]
    for e, tono in (("Designación confirmada", "success"), ("Consulta enviada", "warning"),
                    ("Consulta Enviada", "warning"), ("Rever designación", "error"), ("", "info"), ("otro", "info")):
        assert R.estado_consulta_mostrado(e)["tono"] == tono


# ------------------------------------------------------------------------------------------ generador Word (DOCX)
def _vars(**extra):
    base = {
        "docente": "ZZNEXT, Ana", "CUIL": "20-99130001-1", "cuil": "20-99130001-1", "número_disposición": "72",
        "Fecha Disposición": "26/10/2026", "fecha_acta_rector": "01/03/2026", "rector": "ZZNEXT Rector",
        "N° CUDAP EXP – UNO de la Asamblea Universitaria": "EXP-1/26", "DNI Rector": "1",
        "director/a de departamento": "ZZNEXT Dir", "DNI director/a de departamento": "2",
        "Número de Resolución Direector de Departamento": "R-9",
        R.CLAVE_ASIGNATURAS: "Algoritmos (00123) - Comisión A, turno Mañana, Informática, Lunes de 08:00 a 10:00 "
                             "(Licenciatura, Escuela de Ciencias)",
        "considerandos_designaciones": ["Que, por Resolución CS N.º 1 se designó al docente ZZNEXT;",
                                        "Que, por Resolución Rectoral se designó al docente ZZNEXT;"],
        "cargo": "JTP / Adjunto", "dedicación": "Simple / Parcial", "horas": "10 / 20", "cargo_concursado": "JTP",
        "dedicación_concursado": "Simple", "horas_concursado": "10", "cargo_interino": "Adjunto",
        "dedicación_interino": "Parcial", "horas_interino": "20", "resolucion_cs_concursado": "1/24",
        "resolucion_cs_interino": "2/24", "fecha_desde_interino": "01 de marzo de 2026",
        "departamento_disposicion_encabezado": "Departamento de Informática",
        "Texto funciones de investigación": "como Director en el Proyecto “P” PID-1 del Instituto X",
        "Tipo funciones investigación/extensión": "investigación",
        "Escuelas en las que se encuentran las materias que dicta": "Escuela de Ciencias, Instituto X",
        "designaciones_disposicion": [{"funcion_no_docente": 0}], "ES_FUNCION_NO_DOCENTE": False,
        "ES_FUNCION_MIXTA": False, "Texto función no docente": "", "genero_director_departamento": "Director",
    }
    base.update(extra)
    return base


AE = "ARTÍCULO 3°.- Participó activamente de la siguiente actividad: “Olimpíada ZZNEXT”, en carácter de Colaboradora."
CASOS_DOCX = {
    "simple": (_vars(), {"SI_TIENE_CONCURSADO": True, "SI_TIENE_INTERINO": True, "SI_INVESTIGADOR": False,
                         "SI_NO_INVESTIGA": True}),
    "investigacion": (_vars(), {"SI_TIENE_CONCURSADO": True, "SI_TIENE_INTERINO": False, "SI_INVESTIGADOR": True,
                                "SI_NO_INVESTIGA": False}),
    "actividades": (_vars(**{"Texto Actividades Especiales": AE, "genero_director_departamento": "Directora"}),
                    {"SI_TIENE_CONCURSADO": False, "SI_TIENE_INTERINO": True, "SI_INVESTIGADOR": True,
                     "SI_NO_INVESTIGA": False}),
    "no_docente": (_vars(**{"ES_FUNCION_NO_DOCENTE": True, "Texto función no docente": "administrativas en Rectorado.",
                            R.CLAVE_ASIGNATURAS: "", "designaciones_disposicion": [{"funcion_no_docente": 1}]}),
                   {"SI_TIENE_CONCURSADO": True, "SI_TIENE_INTERINO": False, "SI_INVESTIGADOR": False,
                    "SI_NO_INVESTIGA": True}),
    "mixta": (_vars(**{"ES_FUNCION_MIXTA": True, "Texto función no docente": "de coordinación de carrera",
                       "designaciones_disposicion": [{"funcion_no_docente": 0}, {"funcion_no_docente": 1}]}),
              {"SI_TIENE_CONCURSADO": True, "SI_TIENE_INTERINO": True, "SI_INVESTIGADOR": False,
               "SI_NO_INVESTIGA": True}),
    "v249_sin_comisiones": (_vars(**{R.CLAVE_ASIGNATURAS: "", "Texto funciones de investigación":
                                     "como Directora en el Proyecto de Extensión “E” EXT-2 de la Secretaría X",
                                     "Tipo funciones investigación/extensión": "extensión"}),
                            {"SI_TIENE_CONCURSADO": True, "SI_TIENE_INTERINO": False, "SI_INVESTIGADOR": True,
                             "SI_NO_INVESTIGA": False}),
    "v249_con_ae": (_vars(**{R.CLAVE_ASIGNATURAS: "", "Texto Actividades Especiales": AE}),
                    {"SI_TIENE_CONCURSADO": True, "SI_TIENE_INTERINO": False, "SI_INVESTIGADOR": True,
                     "SI_NO_INVESTIGA": False}),
    "sin_considerandos": (_vars(**{"considerandos_designaciones": []}),
                          {"SI_TIENE_CONCURSADO": False, "SI_TIENE_INTERINO": False, "SI_INVESTIGADOR": False,
                           "SI_NO_INVESTIGA": True}),
}


def _partes(path) -> dict:
    with zipfile.ZipFile(path) as zf:
        return {n: zf.read(n) for n in zf.namelist()}


@pytest.mark.parametrize("variante", ["nueva", "antigua", "corta"])
@pytest.mark.parametrize("caso", sorted(CASOS_DOCX))
def test_docx_certificado_vs_next(db_conn, tmp_path, variante, caso):
    ns = certified_disposiciones(db_conn, 1, 1)
    tpl = tmp_path / "plantilla.docx"
    tpl.write_bytes(P.construir(antigua=variante == "antigua", forma_corta=variante == "corta"))
    original = hashlib.sha256(tpl.read_bytes()).hexdigest()
    variables, condiciones = CASOS_DOCX[caso]
    ns["generar_word_desde_plantilla_disposicion"](str(tpl), str(tmp_path / "cert.docx"), dict(variables),
                                                  dict(condiciones))
    D.generar_word_desde_plantilla_disposicion(str(tpl), str(tmp_path / "next.docx"), dict(variables),
                                               dict(condiciones))
    cert, nxt = _partes(tmp_path / "cert.docx"), _partes(tmp_path / "next.docx")
    assert sorted(cert) == sorted(nxt)
    for parte in cert:
        assert cert[parte] == nxt[parte], parte
    assert hashlib.sha256(tpl.read_bytes()).hexdigest() == original  # la plantilla no se muta
    data = (tmp_path / "next.docx").read_bytes()
    S.validate_docx_bytes(data, max_bytes=S.MAX_OUTPUT_BYTES)
    assert B.validate_docx_bytes(data, max_bytes=B.MAX_OUTPUT_BYTES)["sha256"] == hashlib.sha256(data).hexdigest()


def test_docx_contenido_esperado(tmp_path):
    """Contenido funcional del Word sobre la plantilla sintetica: marcadores, bloques, articulos y membrete."""
    tpl = tmp_path / "p.docx"
    tpl.write_bytes(P.construir())

    def gen(caso):
        out = tmp_path / f"{caso}.docx"
        D.generar_word_desde_plantilla_disposicion(str(tpl), str(out), *[dict(x) for x in CASOS_DOCX[caso]])
        return P.textos(out.read_bytes())
    t = gen("actividades")
    cuerpo = [c[0] for c in t["cuerpo"]]
    assert t["dibujos_encabezado"] == 1  # el membrete (w:drawing) se preserva
    assert "Departamento de Informática" in t["encabezado"][0]
    assert t["pie"] == ["Firma: Directora del Departamento (directora)"]
    assert "LA DIRECTORA DE DEPARTAMENTO" in cuerpo
    assert "VISTO el acta del 01/03/2026 y el expediente EXP-1/26;" in cuerpo  # marcador partido entre runs
    assert not any("{{#" in c or "{{/" in c or "considerandos_designaciones" in c for c in cuerpo)
    assert not any("concursado como" in c for c in cuerpo)  # bloque concursado desactivado
    assert any("interino como Adjunto con dedicación Parcial" in c for c in cuerpo)  # variables del bloque
    art = [c for c in cuerpo if c.startswith("ARTÍCULO")]
    assert [a[:12] for a in art] == ["ARTÍCULO 1º.", "ARTÍCULO 2º.", "ARTÍCULO 3º.", "ARTÍCULO 4º.", "ARTÍCULO 5º."]
    assert "Participó activamente de la siguiente actividad: “Olimpíada ZZNEXT”, en carácter de Colaboradora." in art[2]
    art1 = next(c for c in t["cuerpo"] if c[0].startswith("ARTÍCULO 1"))
    assert [r for r in art1[1] if r[1]] == [("ARTÍCULO 1º.– ", True), ("ZZNEXT, Ana", True)]  # solo rotulo y docente
    assert t["tablas"][0] == ["ZZNEXT Rector", "ZZNEXT Dir"]
    t = gen("no_docente")
    art1 = next(c[0] for c in t["cuerpo"] if c[0].startswith("ARTÍCULO 1"))
    assert art1 == ("ARTÍCULO 1º.– Asígnese al/la docente ZZNEXT, Ana, CUIL N° 20-99130001-1, el cumplimiento de "
                    "funciones administrativas en Rectorado.")
    t = gen("mixta")
    art1 = next(c[0] for c in t["cuerpo"] if c[0].startswith("ARTÍCULO 1"))
    assert art1.endswith("(Licenciatura, Escuela de Ciencias) y de funciones de coordinación de carrera.")
    t = gen("v249_sin_comisiones")
    art = [c[0] for c in t["cuerpo"] if c[0].startswith("ARTÍCULO")]
    assert art[0].startswith("ARTÍCULO 1º.– Asígnese al docente ZZNEXT, Ana CUIL N° 20-99130001-1 el cumplimiento de "
                             "funciones de extensión como Directora en el Proyecto de Extensión")
    assert art[1] == "ARTÍCULO 2º.– " + R.ARTICULO_2_GENERAL_V249
    assert not any("Texto Actividades" in c for c in art)


def test_docx_plantilla_antigua_inserta_art3_y_renumera(tmp_path):
    tpl = tmp_path / "p.docx"
    tpl.write_bytes(P.construir(antigua=True))
    out = tmp_path / "o.docx"
    D.generar_word_desde_plantilla_disposicion(str(tpl), str(out), *[dict(x) for x in CASOS_DOCX["actividades"]])
    art = [c[0] for c in P.textos(out.read_bytes())["cuerpo"] if c[0].startswith("ARTÍCULO")]
    assert art[2].startswith("ARTÍCULO 3°.– Participó activamente")
    assert art[3].startswith("ARTÍCULO 4º.– El docente presentará")
    assert art[4].startswith("ARTÍCULO 5º.– Notifíquese")


# ------------------------------------------------------------------------------------------ almacenamiento B12E
def _codigo(fn):
    try:
        out = fn()
        if hasattr(out, "institution_id"):  # OutputRef (dataclasses distintas en cada lado)
            return ("OK", (out.institution_id, out.department_id, out.name, out.ref))
        return ("OK", out if not isinstance(out, dict) else {k: out[k] for k in ("sha256", "bytes", "entries")})
    except B.DocumentError as exc:  # certificado
        return (exc.code, str(exc))
    except S.DocumentError as exc:  # NEXT
        return (exc.code, str(exc))


def _zip(miembros: dict, flag_bits: int = 0) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as zf:
        for n, d in miembros.items():
            info = zipfile.ZipInfo(n)
            info.flag_bits |= flag_bits
            zf.writestr(info, d)
    return out.getvalue()


def _docx_casos() -> dict:
    ok = P.construir()
    with zipfile.ZipFile(io.BytesIO(ok)) as zf:
        partes = {n: zf.read(n) for n in zf.namelist()}
    sin_doc = {k: v for k, v in partes.items() if k != "word/document.xml"}
    macro = dict(partes, **{"word/vbaProject.bin": b"x"})
    traversal = dict(partes, **{"../evil.txt": b"x"})
    ct_macro = dict(partes, **{"[Content_Types].xml": partes["[Content_Types].xml"].replace(
        b"document.main+xml", b"document.macroEnabled.main+xml")})
    dtd = dict(partes, **{"[Content_Types].xml": b"<!DOCTYPE x>" + partes["[Content_Types].xml"]})
    return {"ok": ok, "vacio": b"", "texto": b"hola", "pk_roto": b"PK\x03\x04roto", "sin_document": _zip(sin_doc),
            "macro": _zip(macro), "traversal": _zip(traversal), "ct_macro": _zip(ct_macro), "dtd": _zip(dtd),
            "cifrado": _zip(partes, flag_bits=0x1), "grande": ok + b"\x00" * 64}


@pytest.mark.parametrize("caso", sorted(_docx_casos()))
@pytest.mark.parametrize("nombre", [None, "plantilla.docx", "PLANTILLA.DOCX", "x.doc", ".docx", "C:\\a\\b.docx", "../p.docx"])
def test_validacion_docx_igual_al_certificado(caso, nombre):
    data = _docx_casos()[caso]
    limite = len(P.construir()) + 8 if caso == "grande" else S.MAX_TEMPLATE_BYTES
    assert _codigo(lambda: S.validate_docx_bytes(data, filename=nombre, max_bytes=limite)) == \
        _codigo(lambda: B.validate_docx_bytes(data, filename=nombre, max_bytes=limite))


@pytest.mark.parametrize("valor", ["Disposicion_72_Pérez, Ana", "../../etc/passwd", "C:\\Windows", "", None, "ñ" * 90,
                                   "con", "a/b\\c", "  __x--  "])
def test_nombres_y_referencias_igual_al_certificado(valor):
    assert S.safe_label(valor) == B.safe_label(valor)
    assert S.safe_label(valor, 120) == B.safe_label(valor, 120)
    for comp in (valor, "inst_1", "con.docx", "a..b", "x.", "ok_1.docx"):
        assert _codigo(lambda: S.check_component(comp)) == _codigo(lambda: B.check_component(comp))
    nombre = "20261026-103000_Disposicion_72_Perez_Ana_" + "a" * 32 + ".docx"
    for ref in (f"b12e:inst_1/dep_1/disposiciones/{nombre}", f"b12e:inst_1/dep_1/disposiciones/../{nombre}",
                f"b12e:inst_0/dep_1/disposiciones/{nombre}", "C:\\Users\\x\\disposiciones_generadas\\a.docx",
                f"b12e:inst_1/dep_1/plantillas/{nombre}", f"b12e:inst_1/dep_1/disposiciones/x.docx", None, 5):
        assert _codigo(lambda: S.parse_output_ref(ref)) == _codigo(lambda: B.parse_output_ref(ref))
    assert S.output_ref(1, 2, nombre) == B.output_ref(1, 2, nombre)
    assert S.template_ref(1, "a" * 64) == B.template_ref(1, "a" * 64)
    assert S.MESSAGES == B.MESSAGES


@pytest.mark.parametrize("fila", [
    {"institucion_id": 1, "departamento_id": 1, "archivo_word": "C:\\legacy\\disposiciones_generadas\\a.docx"},
    {"institucion_id": None, "departamento_id": 1, "archivo_word": "b12e:x"},
    {"institucion_id": 2, "departamento_id": 1, "archivo_word": "b12e:x"},
    {"institucion_id": 1, "departamento_id": 2, "archivo_word": "b12e:x"},
    {"institucion_id": 1, "departamento_id": 1,
     "archivo_word": "b12e:inst_1/dep_2/disposiciones/20261026-103000_D_" + "b" * 32 + ".docx"},
    {"institucion_id": 1, "departamento_id": 1,
     "archivo_word": "b12e:inst_1/dep_1/disposiciones/20261026-103000_D_" + "b" * 32 + ".docx"},
])
def test_dueño_de_fila_igual_al_certificado(fila):
    assert _codigo(lambda: S.row_owner_check(fila, 1, 1)) == _codigo(lambda: B.row_owner_check(fila, 1, 1))


def test_contencion_rutas_y_enlaces(tmp_path):
    root = tmp_path / "raiz"
    root.mkdir()
    st_n, st_c = S.DocumentStorage(str(root)), B.DocumentStorage(str(root))
    for ruta in (root / "inst_1", root / ".." / "fuera", tmp_path, root / "inst_1" / ".." / ".." / "x", "relativa",
                 "\x00", ""):
        assert _codigo(lambda: st_n.contained(ruta)) == _codigo(lambda: st_c.contained(ruta))
    for comps in (["inst_1", "plantillas", "disposicion.docx"], ["..", "x"], ["inst_1", "a/b"], []):
        assert _codigo(lambda: st_n.path_for(comps)) == _codigo(lambda: st_c.path_for(comps))
    with pytest.raises(S.DocumentPathError):
        S.DocumentStorage("relativa")
    # enlace / junction dentro del almacenamiento -> PATH_REJECTED (si el sistema permite crearlo)
    afuera = tmp_path / "afuera"
    afuera.mkdir()
    try:
        os.symlink(afuera, root / "inst_9", target_is_directory=True)
    except (OSError, NotImplementedError):
        import _winapi  # Windows sin privilegio de symlink: junction (tambien es un punto de reanalisis)
        _winapi.CreateJunction(str(afuera), str(root / "inst_9"))
    (afuera / "plantillas").mkdir()
    (afuera / "plantillas" / "disposicion.docx").write_bytes(P.construir())
    assert S.template_status(st_n, 9)["code"] == "PATH_REJECTED"  # nunca se sigue el enlace hacia afuera
    assert _codigo(lambda: st_n.path_for(["inst_9", "plantillas", "disposicion.docx"]))[0] == "PATH_REJECTED"
    assert _codigo(lambda: st_c.path_for(["inst_9", "plantillas", "disposicion.docx"]))[0] == "PATH_REJECTED"


def test_reserva_publicacion_y_compensacion(tmp_path):
    st = S.DocumentStorage(str(tmp_path))
    res = S.allocate_output(st, 1, 2, "Disposicion_72_Pérez Ana", now=__import__("datetime").datetime(2026, 10, 26, 10, 30))
    assert res.name.startswith("20261026-103000_Disposicion_72_Perez_Ana_") and os.path.getsize(res.path) == 0
    assert B.check_output_name(res.name) == res.name and B.parse_output_ref(res.ref).name == res.name
    plantilla = P.construir()
    data = S.publish_output(st, res, lambda tmp: open(tmp, "wb").write(plantilla))
    assert data == plantilla and open(res.path, "rb").read() == plantilla
    assert not [f for f in os.listdir(os.path.dirname(res.path)) if f.startswith(".b12e")]  # sin temporales
    assert S.remove_published(st, res, hashlib.sha256(b"otro").hexdigest()) is False  # otro contenido: no se borra
    assert S.remove_published(st, res, hashlib.sha256(plantilla).hexdigest()) is True and not os.path.exists(res.path)
    # render que falla: se borran reserva y temporal
    res2 = S.allocate_output(st, 1, 2, "x")
    with pytest.raises(RuntimeError):
        S.publish_output(st, res2, lambda tmp: (_ for _ in ()).throw(RuntimeError("render")))
    assert os.listdir(os.path.dirname(res2.path)) == []
    # render que no produce un DOCX valido: DOCX_INVALID y nada publicado
    res3 = S.allocate_output(st, 1, 2, "x")
    with pytest.raises(S.DocxValidationError):
        S.publish_output(st, res3, lambda tmp: open(tmp, "wb").write(b"no es docx"))
    assert os.listdir(os.path.dirname(res3.path)) == []


def test_plantilla_atomica_y_estado(tmp_path):
    st = S.DocumentStorage(str(tmp_path))
    assert S.template_status(st, 1)["status"] == "MISSING"
    info = S.atomic_replace_template(st, 1, P.construir())
    est = S.template_status(st, 1)
    assert est["status"] == "OK" and est["sha256_12"] == info["sha256"][:12] and "C:" not in str(est)
    anterior = open(st.template_path(1), "rb").read()
    S.HOOKS["template.before_replace"] = lambda: (_ for _ in ()).throw(OSError("disco"))
    try:
        with pytest.raises(OSError):
            S.atomic_replace_template(st, 1, P.construir(antigua=True))
    finally:
        S.HOOKS.clear()
    assert open(st.template_path(1), "rb").read() == anterior  # la plantilla anterior queda intacta
    assert [f for f in os.listdir(os.path.dirname(st.template_path(1)))] == ["disposicion.docx"]
    with pytest.raises(S.DocxValidationError):
        S.atomic_replace_template(st, 1, b"PK\x03\x04no")
    (tmp_path / "inst_1" / "plantillas" / "disposicion.docx").write_bytes(b"corrupta")
    assert S.template_status(st, 1)["status"] == "INVALID"


def test_zip_igual_al_certificado():
    items = [("2026-2_Disposicion_72_Pérez, Ana", b"a"), ("2026-2_Disposicion_72_Pérez, Ana", b"b"),
             ("../x", b"c"), ("", b"d")]
    zn, nn = S.zip_payloads(items)
    zc, nc = B.zip_payloads(items)
    with zipfile.ZipFile(io.BytesIO(zn)) as a, zipfile.ZipFile(io.BytesIO(zc)) as b:
        assert a.namelist() == b.namelist() == ["2026-2_Disposicion_72_Perez_Ana.docx",
                                                "2026-2_Disposicion_72_Perez_Ana_2.docx", "x.docx", "documento.docx"]
        assert [a.read(n) for n in a.namelist()] == [b.read(n) for n in b.namelist()]
        assert {i.compress_type for i in a.infolist()} == {zipfile.ZIP_DEFLATED}
    assert nn == nc == 4
    assert S.zip_payloads([]) == B.zip_payloads([]) == (b"", 0)


def test_raiz_documental_productiva_rechazada_sin_tocar_el_disco():
    """D2: la raiz de desarrollo nunca puede apuntar a rutas productivas ni a arboles protegidos."""
    for raiz in (r"C:\DEPTIT_PROD", r"C:\DEPTIT_PROD\documents_root", r"c:\deptit_prod\x\..\y",
                 r"C:\Users\augus\deptit_postgres\disposiciones_generadas", r"C:\Users\augus\deptit_postgres\plantillas",
                 r"C:\DEPTIT_NEXT\reference_fix02", r"C:\DEPTIT_REFACTOR_B13\documentos_institucionales"):
        with pytest.raises(S.DocumentPathError) as exc:
            S.DocumentStorage(raiz)
        assert exc.value.code == "STORAGE_ERROR"
    # 6A-B1: la raiz por defecto de desarrollo se resuelve con pathlib desde el repo (en esta PC, la misma ruta).
    assert S.DocumentStorage(S.DEFAULT_ROOT).root == r"C:\DEPTIT_NEXT\storage\documents"
    assert S.DEFAULT_ROOT == r"C:\DEPTIT_NEXT\storage\documents" and S.CONFIG_ROOT == "DEPTIT_DOCUMENTS_DIR"
    with pytest.raises(S.DocumentPathError):  # tampoco dentro del codigo del backend
        S.DocumentStorage(r"C:\DEPTIT_NEXT\backend\documentos")
