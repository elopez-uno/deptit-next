"""Etapa 5 - remediacion final: fechas año-primero en Carga rapida de Designaciones (docs/ETAPA5_FINAL_REMEDIATION.md).

DESVIACION DELIBERADA Y DOCUMENTADA DEL BASELINE CERTIFICADO: el ``normalizar_fecha_texto`` certificado aplica
``pd.to_datetime(txt, dayfirst=True)`` tambien a ``AAAA-MM-DD`` e invierte dia y mes cuando el dia es <= 12
(2026-03-01 -> 2026-01-03, sin warning).  NEXT interpreta año-primero estricto y deja igual el resto.
Camino real sobre deptit_next_dev con SAVEPOINT revertido; ``db_conn`` nunca confirma."""

from __future__ import annotations

import warnings

import psycopg
import pytest

from designaciones import escrituras as E
from designaciones import rules
from designaciones_support import (  # noqa: F401  (fixtures)
    FIXED_TODAY, audit_store, certified_designaciones, db_conn, designaciones, session_for,
)

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")


@pytest.mark.parametrize("texto,esperado", [
    ("2026-03-01", "2026-03-01"), ("2026-11-03", "2026-11-03"), ("2026-12-01", "2026-12-01"),
    ("01/03/2026", "2026-03-01"), ("31/07/2026", "2026-07-31"),
    # año-primero con otros separadores / sin ceros / con hora: tambien estrictos
    ("2026-3-1", "2026-03-01"), ("2026/03/01", "2026-03-01"), ("2026-03-01 00:00:00", "2026-03-01"),
    # dia/mes/año sin cambios
    ("1/3/2026", "2026-03-01"), ("01-03-2026", "2026-03-01"), ("01.03.2026", "2026-03-01"),
    # invalidos: se devuelve el texto (mismo contrato que el certificado para 2026-02-30); vacio -> fallback
    ("2026-13-01", "2026-13-01"), ("2026-02-30", "2026-02-30"), ("x", "x"), ("", ""),
])
def test_normalizar_fecha_texto(texto, esperado):
    assert rules.normalizar_fecha_texto(texto, "") == esperado


def test_desviacion_respecto_del_baseline(db_conn):
    """Documenta el bug heredado: el certificado invierte; NEXT no.  dd/mm/aaaa coincide en ambos."""
    certificada = certified_designaciones(db_conn, 1, 1)["normalizar_fecha_texto"]
    assert certificada("2026-03-01", "") == "2026-01-03"  # invierte sin warning
    with pytest.warns(UserWarning, match="dayfirst=True"):  # solo avisa cuando no puede invertir (dia > 12)
        assert certificada("2026-07-31", "") == "2026-07-31"
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # NEXT no pasa año-primero por dayfirst: ningun warning
        assert rules.normalizar_fecha_texto("2026-03-01", "") == "2026-03-01"
        assert rules.normalizar_fecha_texto("2026-07-31", "") == "2026-07-31"
    for texto in ("01/03/2026", "31/07/2026"):
        assert certificada(texto, "") == rules.normalizar_fecha_texto(texto, "")


def test_carga_rapida_persiste_la_fecha_iso_correcta(designaciones, service, repo, db_conn, monkeypatch):
    """Carga rapida real: 2026-09-01..2026-11-01 sin periodo.  Con el bug serian 2026-01-09..2026-01-11 -> 2026-1
    (Cerrado, Finalizada).  Correcto: 2026-2 (Abierto, id 9) y Activa (hoy 2026-10-26)."""
    rec = session_for(service, repo, 3)[0]
    cuil = db_conn.execute("SELECT cuil FROM docentes WHERE institucion_id=1 AND departamento_id=1 ORDER BY id "
                           "LIMIT 1").fetchone()[0]
    texto = ("cuil\tcargo\tdedicacion\ttipo_designacion\tfecha_desde\tfecha_hasta\tobservaciones\n"
             f"{cuil}\tTitular\tExclusiva\tInterino\t2026-09-01\t2026-11-01\tZZNEXT e5 fecha iso\n")
    prev = designaciones.carga_preview(rec, texto)
    assert not prev["duplicados"] and not prev["inexistentes"]
    assert [(f["fecha_desde"], f["fecha_hasta"], f["periodo"], f["estado"]) for f in prev["filas"]] == \
        [("2026-09-01", "2026-11-01", "2026-2", "Activa")]

    guardadas = []
    original = E.guardar_designacion

    def espia(u, periodo_id, cuil_, cargo, dedicacion, horas, tipo, ad_honorem, fecha_desde, fecha_hasta, estado,
              *a, **k):
        guardadas.append((periodo_id, fecha_desde, fecha_hasta, estado))
        return original(u, periodo_id, cuil_, cargo, dedicacion, horas, tipo, ad_honorem, fecha_desde, fecha_hasta,
                        estado, *a, **k)

    monkeypatch.setattr(E, "guardar_designacion", espia)
    contar = ("SELECT (SELECT count(*) FROM designaciones), (SELECT count(*) FROM movimientos), "
              "(SELECT max(id) FROM designaciones)")
    antes = db_conn.execute(contar).fetchone()
    with db_conn.transaction() as tx:
        res = designaciones.carga_ejecutar(rec, texto, False)
        assert res["mensaje"] == "Carga finalizada. Designaciones cargadas: 1. Omitidas: 0."
        assert guardadas == [(9, "2026-09-01", "2026-11-01", "Activa")]
        fila = db_conn.execute("SELECT periodo_id, fecha_desde, fecha_hasta, estado FROM designaciones "
                               "WHERE observaciones='ZZNEXT e5 fecha iso'").fetchall()
        assert fila == [(9, "2026-09-01", "2026-11-01", "Activa")]
        raise psycopg.Rollback(tx)
    assert db_conn.execute(contar).fetchone() == antes
    assert db_conn.execute("SELECT count(*) FROM designaciones WHERE observaciones LIKE 'ZZNEXT e5%'").fetchone()[0] == 0
