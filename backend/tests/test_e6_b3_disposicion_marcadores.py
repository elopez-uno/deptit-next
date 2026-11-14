"""6A-B3 (aceptacion humana): una Disposicion generada no conserva marcadores ``{{...}}`` / ``{#...}`` / ``{/...}``.
Con una plantilla compatible el resultado tiene 0 marcadores; con un marcador desconocido o incompatible (p. ej. la
plantilla de piloto ZZPILOTB3 con ``{{designaciones_disposicion}}``, que es una LISTA interna y no un texto) se falla con
un error claro: no se publica el Word ni se registra la fila.  Plantillas SINTETICAS (decision D3: nunca la productiva).
"""

from __future__ import annotations

import io

import pytest
from docx import Document

import disposiciones_plantilla as P
from disposiciones import documents as D
from disposiciones.service import DisposicionesError
from disposiciones_support import (  # noqa: F401  (fixtures)
    FIXED_TODAY, audit_store, db_conn, disposiciones, periodo_id, session_for, storage_root,
)
from test_disposiciones_rules import CASOS_DOCX
from test_disposiciones_service import _contar, _generar, _plantilla, _vista

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")


def _docx(*parrafos: str, encabezado: str = "", partido: tuple = ()) -> bytes:
    doc = Document(io.BytesIO(P.construir()))
    for t in parrafos:
        doc.add_paragraph(t)
    if partido:  # marcador partido entre runs (como lo deja Word)
        p = doc.add_paragraph()
        for trozo in partido:
            p.add_run(trozo)
    if encabezado:
        doc.sections[0].header.add_paragraph(encabezado)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def plantilla_piloto_b3() -> bytes:
    """Reproduccion de la plantilla de PILOTO que generaba el harness B3 (ops/preprod/piloto/modulos.py)."""
    d = Document()
    d.add_heading("DISPOSICION N° {{número_disposición}} (PLANTILLA DE PILOTO ZZPILOTB3)", level=1)
    d.add_paragraph("{{departamento_disposicion_encabezado}} - {{Fecha Disposición}}")
    d.add_paragraph("VISTO las designaciones del/la docente {{docente}}, CUIL {{cuil}}: {{considerandos_designaciones}}")
    d.add_paragraph("ARTÍCULO 1°.- Asígnese al/la docente {{docente}}, CUIL N° {{CUIL}}, cargo {{cargo}}, dedicación "
                    "{{dedicación}}: {{designaciones_disposicion}}")
    d.add_paragraph("ARTÍCULO 2°.- Regístrese, comuníquese y archívese. {{texto_departamentos_revistara}}")
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


@pytest.mark.parametrize("variante", ["nueva", "antigua", "corta"])
@pytest.mark.parametrize("caso", sorted(CASOS_DOCX))
def test_plantilla_compatible_cero_marcadores(tmp_path, variante, caso):
    tpl = tmp_path / "p.docx"
    tpl.write_bytes(P.construir(antigua=variante == "antigua", forma_corta=variante == "corta"))
    assert D.marcadores_remanentes(tpl)  # la plantilla SI los tiene
    out = tmp_path / "o.docx"
    D.generar_word_desde_plantilla_disposicion(str(tpl), str(out), *[dict(x) for x in CASOS_DOCX[caso]])
    assert D.marcadores_remanentes(out) == []


@pytest.mark.parametrize("data, esperado", [
    (lambda: plantilla_piloto_b3(), "{{designaciones_disposicion}}"),
    (lambda: _docx("Texto {{marcador_inexistente}} fin."), "{{marcador_inexistente}}"),
    (lambda: _docx(partido=("Valor {{otro_", "desconocido", "}} partido")), "{{otro_desconocido}}"),
    (lambda: _docx(encabezado="Encabezado {{marca_de_encabezado}}"), "{{marca_de_encabezado}}"),
    (lambda: _docx("{#BLOQUE_DESCONOCIDO}"), "{#BLOQUE_DESCONOCIDO}"),
])
def test_marcador_desconocido_falla_con_error_claro(tmp_path, data, esperado):
    tpl = tmp_path / "p.docx"
    tpl.write_bytes(data())
    with pytest.raises(ValueError) as e:
        D.generar_word_desde_plantilla_disposicion(str(tpl), str(tmp_path / "o.docx"),
                                                   *[dict(x) for x in CASOS_DOCX["simple"]])
    assert esperado in str(e.value) and "No se generó la disposición" in str(e.value)


@pytest.fixture
def records(service, repo):
    return {"dep": session_for(service, repo, 3)[0]}


def test_servicio_no_publica_ni_registra_con_plantilla_incompatible(disposiciones, records, db_conn, storage_root):
    _plantilla(storage_root, data=plantilla_piloto_b3())
    pid, v = _vista(disposiciones, records["dep"], db_conn)
    antes = _contar(db_conn)[:7]  # sin la cuenta de auditoria (el FAILED va al almacen separado)
    with pytest.raises(DisposicionesError) as e:
        _generar(disposiciones, records["dep"], pid, v)
    assert e.value.status == 422 and "{{designaciones_disposicion}}" in e.value.message
    assert _contar(db_conn)[:7] == antes
    salida = storage_root / "inst_1" / "dep_1" / "disposiciones"
    assert not salida.exists() or not any(salida.iterdir())  # ni Word publicado ni temporales


def test_servicio_genera_con_plantilla_compatible_sin_marcadores(disposiciones, records, db_conn, storage_root):
    _plantilla(storage_root)
    pid, v = _vista(disposiciones, records["dep"], db_conn)
    res = _generar(disposiciones, records["dep"], pid, v)  # db_conn nunca confirma (ROLLBACK del fixture)
    assert D.marcadores_remanentes(io.BytesIO(disposiciones.descargar(records["dep"], {"id": res["id"]}).data)) == []
