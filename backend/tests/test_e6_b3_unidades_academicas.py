"""6A-B3 (último detalle): presentación de las unidades académicas en Disposiciones.

Un nombre simple histórico de UNO ("Ciencias Tecnológicas", "Humanidades") sigue saliendo como "Escuela de ...";
una denominación institucional completa ("Facultad de ...", "Instituto de ...", "Departamento de ...") se respeta
tal cual. Un ÚNICO formateador (``disposiciones.rules.formatear_nombre_escuela``) alimenta los datos recuperados, la
vista previa, las variables del generador y el Word: se prueba de punta a punta con los datos cambiados en una
transacción que se deshace (ROLLBACK).
"""

from __future__ import annotations

import io
import json
import re

import psycopg
import pytest
from docx import Document

from disposiciones import documents as D
from disposiciones import rules as R
from disposiciones_support import (  # noqa: F401  (fixtures)
    FIXED_TODAY, audit_store, db_conn, make_disposiciones, periodo_id, session_for, storage_root,
)
from test_disposiciones_rules import TEXTOS
from test_disposiciones_service import _generar, _plantilla, _vista

from deptit_refactor.domain import materias as cert_mat  # noqa: E402  (reference_fix02, solo lectura)

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")

CASOS = {
    "A": ("Ciencias Tecnológicas", "Escuela de Ciencias Tecnológicas"),
    "B": ("Humanidades", "Escuela de Humanidades"),
    "C": ("Facultad de Ingeniería", "Facultad de Ingeniería"),
    "D": ("Escuela de Arquitectura", "Escuela de Arquitectura"),
    "E": ("Instituto de Tecnología", "Instituto de Tecnología"),
    "F": ("Departamento de Ciencias Básicas", "Departamento de Ciencias Básicas"),
}
# H: construcciones que nunca deben aparecer
PROHIBIDO = re.compile(r"(?i)escuela de (facultad|escuela|instituto|departamento)\b")
# valores almacenados hoy en UNO (dev/preprod) y sus variantes simples históricas
HISTORICOS_UNO = ["Escuela de Administración", "Escuela de Ciencias Jurídicas, Políticas y Sociales",
                  "Escuela de Ciencias Tecnológicas", "Escuela de Humanidades", "Escuela de Salud", "Posgrado",
                  "Ciencias Tecnológicas", "Cs. Tecnológicas", "Humanidades", "Salud", "Administración",
                  "Ciencias Jurídicas, Políticas y Sociales", "Escuela Cs. Tecnológicas", "Posgrado en Educación"]


@pytest.mark.parametrize("caso", sorted(CASOS))
def test_regla_a_f(caso):
    valor, esperado = CASOS[caso]
    assert R.formatear_nombre_escuela(valor) == esperado
    assert R.formatear_nombre_escuela(esperado) == esperado  # idempotente (lecturas lo reaplica)


@pytest.mark.parametrize("valor, esperado", [
    ("Facultad de Pelotudismo", "Facultad de Pelotudismo"), ("FACULTAD DE DERECHO", "FACULTAD DE DERECHO"),
    ("  facultad   de  Medicina ", "facultad de Medicina"), ("Instituto Balseiro", "Instituto Balseiro"),
    ("Depto. de Física", "Depto. de Física"), ("Dpto. Matemática", "Dpto. Matemática"),
    ("Centro de Estudios Avanzados", "Centro de Estudios Avanzados"),
    ("Unidad Académica Río Gallegos", "Unidad Académica Río Gallegos"),
    ("Secretaria de Investigación", "Secretaria de Investigación"), ("Área de Salud", "Área de Salud"),
    ("Escuela", "Escuela"), ("Facultad", "Facultad"),
    # no son tipos institucionales: siguen recibiendo "Escuela de"
    ("Ingeniería", "Escuela de Ingeniería"), ("Facultades Unidas", "Escuela de Facultades Unidas"),
    ("Institucional", "Escuela de Institucional"), ("Arquitectura", "Escuela de Arquitectura"),
])
def test_deteccion_general_por_tipo(valor, esperado):
    assert R.formatear_nombre_escuela(valor) == esperado
    assert not PROHIBIDO.search(R.formatear_nombre_escuela(valor))


@pytest.mark.parametrize("valor", HISTORICOS_UNO + [t for t in TEXTOS if t is not None
                                                     and not R.es_denominacion_institucional(t)])
def test_historicos_identicos_al_certificado(valor):
    assert R.formatear_nombre_escuela(valor) == cert_mat.formatear_nombre_escuela(valor)


def _texto_docx(data: bytes) -> str:
    doc = Document(io.BytesIO(data))
    partes = [p.text for p in doc.paragraphs]
    for t in doc.tables:
        partes += [c.text for f in t.rows for c in f.cells]
    return "\n".join(partes)


@pytest.mark.parametrize("caso", sorted(CASOS))
def test_misma_salida_en_datos_vista_variables_y_word(caso, service, repo, db_conn, audit_store, storage_root):
    valor, esperado = CASOS[caso]
    capturadas = []

    def render(plantilla, salida, variables, condiciones):
        capturadas.append(dict(variables))
        D.generar_word_desde_plantilla_disposicion(plantilla, salida, variables, condiciones)

    svc = make_disposiciones(service, audit_store, db_conn, storage_root, render=render)
    rec = session_for(service, repo, 3)[0]
    _plantilla(storage_root)
    with db_conn.transaction() as tx:
        pid, antes = _vista(svc, rec, db_conn)
        assert "Escuela de" in antes["escuelas"]  # precondición: el docente tiene materias con escuela
        for tabla, col in (("materias", "escuela"), ("carreras", "escuela"), ("comision_materias", "escuela_snapshot")):
            db_conn.execute(f"UPDATE {tabla} SET {col}=%s WHERE coalesce({col}, '') <> ''", [valor])
        v = svc.docente(rec, {"periodo_id": pid, "cuil": antes["cuil"]})
        # datos recuperados automáticamente / vista previa (lo que muestra la pantalla)
        assert v["escuelas"].split(", ")[0] == esperado
        assert f", {esperado}" in v["asignaturas"]
        # variables entregadas al generador
        res = _generar(svc, rec, pid, v)
        variables = capturadas[-1]
        assert variables["Escuelas en las que se encuentran las materias que dicta"] == v["escuelas"]
        assert any(f", {esperado}" in str(x) for k, x in variables.items() if k.startswith("asignaturas que dicta"))
        # Word final
        word = _texto_docx(svc.descargar(rec, {"id": res["id"]}).data)
        assert f"Notifíquese a {esperado}" in word and f", {esperado}" in word
        # H: ninguna construcción duplicada en ninguna salida
        for salida in (json.dumps(v, ensure_ascii=False), json.dumps(variables, ensure_ascii=False, default=str), word):
            assert not PROHIBIDO.search(salida)
        raise psycopg.Rollback(tx)
