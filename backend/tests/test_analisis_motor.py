"""Integridad del motor de lectura vendorizado de Analisis (``analisis/motor``) frente a la fuente certificada.

- Cada bloque de ``certificado.py`` es el texto LITERAL del entry en la linea indicada (solo cambia el prefijo
  ``deptit_refactor`` -> ``analisis.motor.ref``); el sha256 del entry coincide con ``metadata.ENTRY_SHA256``.
- Cada modulo de ``ref/`` es la copia literal del modulo de ``deptit_refactor`` (mismo reemplazo de prefijo).
- Garantias de solo lectura: sentencias mutantes rechazadas antes de la base, writers de negocio bloqueados, tareas de
  sistema con la compuerta B12F, memoizacion acotada al request (D-AM12) y sin llamadas de red (D-AM9).
"""

from __future__ import annotations

import ast
import hashlib
import re
from pathlib import Path

import psycopg
import pytest

from analisis.motor import entorno, metadata
from analisis_support import FIXED_TODAY, db_conn, motor  # noqa: F401

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")

REF = Path(r"C:\DEPTIT_NEXT\reference_fix02")
ENTRY = REF / "app_postgresql_refactor_b13fix02_uat_fixes.py"
MOTOR = Path(entorno.__file__).resolve().parent


def _norm(texto: str) -> str:
    return re.sub(r"\banalisis\.motor\.ref\b", "deptit_refactor", texto)


def _generador():
    import importlib.util
    spec = importlib.util.spec_from_file_location("tools_generar_motor_analisis",
                                                  MOTOR.parents[1] / "tools_generar_motor_analisis.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_certificado_es_texto_literal_del_entry():
    fuente = ENTRY.read_text(encoding="utf-8")
    assert hashlib.sha256(fuente.encode("utf-8")).hexdigest() == metadata.ENTRY_SHA256
    lineas = fuente.split("\n")
    texto = (MOTOR / "certificado.py").read_text(encoding="utf-8")
    # 6A-B1: UNICA desviacion declarada (generador ``sin_instalacion_dinamica``): sin ``pip install`` en runtime.
    gen = _generador()
    assert texto.count(gen.SIN_INSTALACION_DINAMICA) == 1 and gen.INSTALACION_DINAMICA not in texto
    texto = texto.replace(gen.SIN_INSTALACION_DINAMICA, gen.INSTALACION_DINAMICA)
    bloques = re.split(r"^# --- entry l\. ", texto, flags=re.M)[1:]
    verificados = 0
    for b in bloques:
        cab, _, cuerpo = b.partition("\n")
        m = re.match(r"(\d+)(?:-(\d+))?$", cab.strip())
        if not m:
            continue
        ini, fin = int(m.group(1)), int(m.group(2) or m.group(1))
        original = "\n".join(lineas[ini - 1:fin])
        cuerpo = cuerpo.rstrip("\n")
        # FunctionDef: el segmento empieza en "def" (sin decoradores) y termina en la ultima linea del cuerpo
        assert _norm(cuerpo) in original or original.endswith(_norm(cuerpo)), f"l. {ini}"
        verificados += 1
    assert verificados == metadata.BLOQUES


def test_ref_es_copia_literal_de_deptit_refactor():
    for rel in metadata.MODULOS_REF:
        original = (REF / "deptit_refactor" / rel).read_text(encoding="utf-8")
        copia = (MOTOR / "ref" / rel).read_text(encoding="utf-8")
        assert _norm(copia) == original, rel
    assert not list((MOTOR / "ref").rglob("integration")), "los pilotos no se vendorizan"


def test_sin_red_ni_escritura_ni_disco_en_el_motor_y_el_servicio():
    codigo = "\n".join(p.read_text(encoding="utf-8") for p in [MOTOR / "entorno.py"]
                       + list((MOTOR.parent).glob("*.py")))
    for prohibido in ("requests", "httpx", "urllib.request", "openai", "anthropic", "gemini", "socket",
                      "open(", "NamedTemporaryFile", "write_bytes", "to_excel", "advisory"):
        assert prohibido not in codigo, prohibido


def test_motor_rechaza_escrituras_y_aplica_b12f(db_conn):
    n = motor(db_conn, 1, 1)
    for w in metadata.WRITERS_NEGOCIO:
        with pytest.raises(entorno.EscrituraEnLectura):
            n[w](10)
    for w, cat in metadata.TAREAS_SISTEMA.items():
        assert n[w]() is None, w
    conn = n["get_conn"]()
    with pytest.raises(entorno.EscrituraEnLectura):
        conn.cursor().execute("UPDATE periodos SET estado = estado WHERE id = ?", [9])
    with pytest.raises(entorno.EscrituraEnLectura):
        n["_pg_read_dataframe"]("DELETE FROM movimientos WHERE id = -1")
    with pytest.raises(entorno.EscrituraEnLectura):
        n["_pg_raw_conn"]().cursor().execute("INSERT INTO periodos (nombre) VALUES ('ZZNEXT')")


def test_ambito_de_sesion_inyectado(db_conn):
    """``get_conn`` aplica el inyector B12B efectivo con el ambito de la sesion (no del cliente)."""
    n1, n2 = motor(db_conn, 1, 1), motor(db_conn, 1, 2)
    p1, p2 = n1["get_periodos"](), n2["get_periodos"]()
    assert set(p1["id"]) & set(p2["id"]) == set()
    reales = {r[0] for r in db_conn.execute("SELECT id FROM periodos WHERE departamento_id=1")}
    assert set(p1["id"]) == reales


def test_memoizacion_request_scoped(db_conn):
    """D-AM12: dentro del request, una estructura identica se calcula una vez; un request nuevo no reutiliza nada."""
    n = motor(db_conn, 1, 1)
    llamadas = {"n": 0}
    original = n["_materias_unificadas_pre_v196"]

    def contado(*a, **k):
        llamadas["n"] += 1
        return original(*a, **k)
    n["_materias_unificadas_pre_v196"] = contado
    for _ in range(5):
        n["get_materia_comision"](None) if "get_materia_comision" in n else n["_materias_para_comisiones_unificadas_y_mapa"]()
        n["_materias_para_comisiones_unificadas_y_mapa"]()
    assert llamadas["n"] == 1
    assert n["_motor_memo"]
    otro = motor(db_conn, 1, 1)
    assert otro["_motor_memo"] == {} and otro["_motor_memo"] is not n["_motor_memo"]
    assert set(metadata.CACHEADAS) and set(metadata.CACHEADAS_RUNTIME)


def test_sin_instalacion_dinamica_de_paquetes_en_runtime(db_conn):
    """6A-B1: ningun modulo de runtime instala paquetes ni lanza procesos; python-docx viene de requirements.txt y la
    generacion Word del motor funciona con el entorno ya preparado.
    6A-B2: las herramientas operativas (CLI ``operacion`` y las copias B11 que ejecutan pg_dump / pg_restore) lanzan
    procesos por diseño y NO son runtime: lista cerrada aca; que la app nunca las cargue lo verifica
    ``test_e6_b2_backup.py::test_runtime_no_carga_herramientas_operativas``."""
    backend = MOTOR.parents[1]
    herramientas_operativas = ("integraciones/ciclo_periodos/ref_b11/backup.py",
                               "integraciones/ciclo_periodos/ref_b11/restore_drill.py")
    for p in backend.rglob("*.py"):
        rel = p.relative_to(backend).as_posix()
        if rel.startswith((".venv/", "tests/", "tools_", "operacion/")) or "__pycache__" in rel:
            continue
        if rel in herramientas_operativas:
            continue
        texto = p.read_text(encoding="utf-8-sig")
        assert not re.search(r"\bsubprocess\b|\bensurepip\b|[\"']pip[\"']\s*,\s*[\"']install[\"']", texto), rel
    req = (backend / "requirements.txt").read_text(encoding="utf-8-sig")
    assert re.search(r"^python-docx==\d", req, flags=re.M)
    from docx import Document
    assert motor(db_conn, 1, 1)["_obtener_document_python_docx"]() is Document


def test_codigo_vendorizado_compila_y_no_importa_deptit_refactor():
    texto = (MOTOR / "certificado.py").read_text(encoding="utf-8")
    ast.parse(texto)
    assert "deptit_refactor" not in texto.replace("``deptit_refactor``", "")
    for p in (MOTOR / "ref").rglob("*.py"):
        assert not re.search(r"\bdeptit_refactor\b", p.read_text(encoding="utf-8")), p
