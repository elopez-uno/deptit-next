"""Etapa 5 - remediacion final §13: fechas año-primero en la Carga rapida Excel de proyectos de Investigacion y
Extension (docs/ETAPA5_FINAL_REMEDIATION.md).

DESVIACION DELIBERADA Y DOCUMENTADA DEL BASELINE CERTIFICADO: ``_parse_fecha_excel_proyecto_v127`` certificado
(``deptit_refactor/domain/proyectos.py``) aplica ``pd.to_datetime(txt, dayfirst=True)`` tambien a las celdas de TEXTO
``AAAA-MM-DD`` e invierte dia y mes cuando el dia es <= 12 (2026-03-01 -> 2026-01-03); la vista previa muestra el texto
original y el INSERT del proyecto guarda la fecha invertida.  NEXT (``investigacion/rules.py::parse_fecha_excel_v127``,
compartido por Extension) interpreta año-primero estricto y deja igual el resto.
Camino real sobre deptit_next_dev dentro de una transaccion revertida; ``db_conn`` nunca confirma."""

from __future__ import annotations

import base64
import warnings
from datetime import date
from io import BytesIO

import psycopg
import pytest

from investigacion import rules as IR
from extension_support import extension  # noqa: F401  (fixture)
from investigacion_support import (  # noqa: F401  (fixtures)
    audit_store, certified_investigacion, db_conn, investigacion, lock_conn, session_for,
)

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")


@pytest.mark.parametrize("valor,esperado", [
    ("2026-03-01", date(2026, 3, 1)), ("2026-08-01", date(2026, 8, 1)), ("2026-11-03", date(2026, 11, 3)),
    ("01/03/2026", date(2026, 3, 1)), ("31/07/2026", date(2026, 7, 31)),
    ("2026-12-01", date(2026, 12, 1)), ("2026-3-1", date(2026, 3, 1)), ("2026/03/01", date(2026, 3, 1)),
    ("2026-03-01 00:00:00", date(2026, 3, 1)), ("1/3/2026", date(2026, 3, 1)),
    # invalidos y vacios: None (contrato de la funcion -> "completá Fecha de inicio y Fecha de finalización")
    ("2026-13-01", None), ("2026-02-30", None), ("x", None), ("", None), ("nan", None), (None, None),
    # celdas con fecha real de Excel: sin cambios
    (date(2026, 3, 1), date(2026, 3, 1)),
])
def test_parse_fecha_excel(valor, esperado):
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # año-primero ya no pasa por dayfirst: ningun warning de pandas
        assert IR.parse_fecha_excel_v127(valor) == esperado


def test_desviacion_respecto_del_baseline(db_conn):
    """Documenta el bug heredado: el certificado invierte; NEXT no.  dd/mm/aaaa coincide en ambos."""
    certificada = certified_investigacion(db_conn, 1, 2)["_parse_fecha_excel_proyecto_v127"]
    assert certificada("2026-03-01") == date(2026, 1, 3)
    assert certificada("2026-11-03") == date(2026, 3, 11)
    assert IR.parse_fecha_excel_v127("2026-03-01") == date(2026, 3, 1)
    for texto in ("01/03/2026", "31/07/2026"):
        assert certificada(texto) == IR.parse_fecha_excel_v127(texto)


def _excel(svc, rec, filas):
    from openpyxl import load_workbook
    wb = load_workbook(BytesIO(svc.modelo_excel(rec)))
    ws = wb["Carga rápida"]
    fila = next(r for r in range(2, ws.max_row + 2) if ws.cell(row=r, column=2).value in (None, ""))
    for p in filas:
        for j, v in enumerate(p, 1):
            ws.cell(row=fila, column=j, value=v)
        fila += 1
    out = BytesIO()
    wb.save(out)
    return base64.b64encode(out.getvalue()).decode()


@pytest.mark.parametrize("modulo,tabla", [("investigacion", "proyectos_investigacion"),
                                          ("extension", "proyectos_extension")])
def test_carga_rapida_persiste_la_fecha_iso_correcta(request, service, repo, db_conn, modulo, tabla):
    """Celdas de TEXTO ISO (con el bug: 2026-01-03..2026-03-11 y 2026-01-08..2026-12-31), dd/mm y fecha real."""
    svc = request.getfixturevalue(modulo)
    rec = session_for(service, repo, 6)[0]  # usuario de departamento (dep 2)
    archivo = _excel(svc, rec, [
        ("", "ZZNEXT e5 iso A", "", "", "", "2026-03-01", "2026-11-03", "Activo", ""),
        ("", "ZZNEXT e5 iso B", "", "", "", "2026-08-01", "2026-12-31", "Activo", ""),
        ("", "ZZNEXT e5 ddmm", "", "", "", "01/03/2026", "31/07/2026", "Activo", ""),
        ("", "ZZNEXT e5 fecha real", "", "", "", date(2026, 3, 1), date(2026, 11, 3), "Activo", ""),
    ])
    ov = svc.overview(rec)
    contar = f"SELECT count(*), max(id) FROM {tabla}"
    antes = db_conn.execute(contar).fetchone()
    with db_conn.transaction() as tx:
        res = svc.carga_ejecutar(rec, {"archivo": archivo, "confirmar": True, "huella_periodo": ov["huella_periodo"]})
        assert "Proyectos creados: 4;" in res["mensaje"]
        filas = db_conn.execute(f"SELECT nombre_proyecto, fecha_inicio, fecha_fin, anio_llamado FROM {tabla} "
                                "WHERE nombre_proyecto LIKE 'ZZNEXT e5%%' ORDER BY id").fetchall()
        assert filas == [("ZZNEXT e5 iso A", date(2026, 3, 1), date(2026, 11, 3), 2026),
                         ("ZZNEXT e5 iso B", date(2026, 8, 1), date(2026, 12, 31), 2026),
                         ("ZZNEXT e5 ddmm", date(2026, 3, 1), date(2026, 7, 31), 2026),
                         ("ZZNEXT e5 fecha real", date(2026, 3, 1), date(2026, 11, 3), 2026)]
        raise psycopg.Rollback(tx)
    assert db_conn.execute(contar).fetchone() == antes
    assert db_conn.execute(f"SELECT count(*) FROM {tabla} WHERE nombre_proyecto LIKE 'ZZNEXT e5%%'").fetchone()[0] == 0
