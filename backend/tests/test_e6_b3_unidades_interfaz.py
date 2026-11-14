"""6A-B3: "Unidad académica" como categoría genérica en TODA la interfaz productiva (Materias, Comisiones, Inicio).

- Etiquetas/mensajes/encabezados de modelos Excel dicen "Unidad académica"; los nombres reales no se transforman.
- Compatibilidad: el lector del modelo de opciones curriculares acepta el encabezado nuevo y los históricos
  ("Facultad/Escuela oferente", "Escuela oferente", "Facultad oferente") con el mismo resultado.
- Claves internas (``escuela``, ``escuela_oferente``), marcadores Word y código certificado no cambian.
- Guardia: ningún literal productivo usa "Facultad/Escuela", "Facultades/Escuelas", "Escuela/s", "Escuela oferente" ni
  "Escuela destino" (comentarios y código certificado excluidos).
"""
from __future__ import annotations

import io
import re
from pathlib import Path

import pytest
from openpyxl import Workbook

import unidades_support as U
from comisiones import rules as CR
from inicio import pagina as IP
from materias import rules as MR
from materias import service as MS

RAIZ = Path(__file__).resolve().parents[2]
PROHIBIDOS = re.compile(r"Facultad/Escuela|Facultades/Escuelas|Escuela/s|Escuela oferente|Escuela destino|"
                        r"\"Escuela\"|\"Escuelas\"|mantener escuelas|carreras y escuelas")
EXCLUIDOS = ("analisis/motor/ref/", "analisis/motor/certificado.py", "integraciones/resumen_motor/")


def _xlsx(encabezado: str) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Carga rápida"
    ws.append(["Tipo", "Código de la opción", "Materia concreta que se ofrece", encabezado, "Estado", "Habilitación 1"])
    ws.append(["Electiva", "E1", "Inútil avanzado", "Facultad de Pelotudismo", "Activa", ""])
    ws.append(["Electiva", "E2", "Historia", "Escuela de Humanidades", "", ""])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.mark.parametrize("encabezado", [U.ENCABEZADO_OPCIONES, U.ENCABEZADO_OPCIONES_HISTORICO, "Escuela oferente",
                                        "Facultad oferente", " unidad academica OFERENTE "])
def test_excel_opciones_acepta_encabezado_nuevo_e_historicos(encabezado):
    df = MR.leer_excel_carga_rapida_opciones_v124(_xlsx(encabezado))
    assert list(df["escuela_oferente"]) == ["Facultad de Pelotudismo", "Escuela de Humanidades"]  # nombres reales


def test_selector_de_materia_en_comisiones():
    fila = {"codigo": "01", "asignatura": "Inútil I", "carrera": "Ingeniería en Inutilidad", "plan_version": "2026"}
    uno = CR.etiqueta_materia_comision({**fila, "escuela": "Facultad de Pelotudismo"})
    assert "Unidad académica: Facultad de Pelotudismo" in uno and "Escuela/s" not in uno
    varias = CR.etiqueta_materia_comision({**fila, "escuela": "Escuela de Humanidades / Instituto de Tecnología"})
    assert "Unidades académicas: Escuela de Humanidades / Instituto de Tecnología" in varias
    assert "Unidad" not in CR.etiqueta_materia_comision({**fila, "escuela": ""})


def test_textos_genericos():
    assert "Unidad académica" in MS.MSG_CARRERA_REQUERIDOS and "Escuela" not in MS.MSG_CARRERA_REQUERIDOS
    assert "mantener unidades académicas, carreras," in IP.AYUDA_TABLERO and "escuelas" not in IP.AYUDA_TABLERO


def _productivos():
    for base, patron in (("backend", "*.py"), ("frontend/src", "*.ts"), ("frontend/src", "*.tsx")):
        for p in (RAIZ / base).rglob(patron):
            rel = p.relative_to(RAIZ / base).as_posix()
            if rel.startswith("tests/") or "__pycache__" in rel or "node_modules" in rel or rel.startswith(EXCLUIDOS):
                continue
            yield f"{base}/{rel}", p


def test_ningun_literal_productivo_usa_escuela_como_categoria():
    hallazgos = []
    for rel, p in _productivos():
        for n, linea in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            codigo = linea.strip()
            if codigo.startswith(("#", "//", "*")):
                continue  # comentarios (citan nombres del certificado)
            if PROHIBIDOS.search(codigo):
                hallazgos.append(f"{rel}:{n}: {codigo[:120]}")
    assert hallazgos == []
