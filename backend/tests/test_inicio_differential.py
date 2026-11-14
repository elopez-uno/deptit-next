"""Diferenciales de Inicio: certificado (``reference_fix02``, ``certified_inicio``) vs motor NEXT de Analisis
(``analisis.motor``, D-AN1) y vs el contrato de pantalla (``inicio.pagina``), mismo estado de base.

- Datos: ``_inicio_datos_tablero_cache`` (v188 -> v165 -> v146) identico, escalares y DataFrames, en los 10 periodos
  reales de los departamentos 1, 2, 3, 4, 9 y 11 (abiertos e historicos).
- Contrato de UI: el bloque ``if modulo == "🏠 Inicio":`` LITERAL del entry, ejecutado con un Streamlit que graba, es
  identico a la secuencia construida desde el payload NEXT (5 tarjetas, 2 listas, acciones, 6 controles, indice de
  salud, 11 indicadores, 2 graficos Vega-Lite, vencimientos con su Excel, ayuda y los 8 destinos de navegacion), salvo
  las 2 diferencias conscientes D-AN3 (caption de Actualizar) y D-AN4 (titulo).  Estados: tablero, periodo historico
  reabierto, sin periodo abierto, coordinador sin departamento.
- Anomalias certificadas congeladas (docs/inicio_analysis.md §36).  Datos sinteticos ``ZZNEXT`` dentro de la
  transaccion del test (ROLLBACK).
"""

from __future__ import annotations

import pandas as pd
import pytest

from analisis_support import escalares, igual_df
from inicio import pagina as P
from inicio_support import (  # noqa: F401  (fixtures)
    AYUDA_UA, AYUDA_UA_CERT, certified_inicio, db_conn, eventos_payload, motor, normalizar_certificado,
    pagina_certificada, payload_motor,
)

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")

INST = 1
ABIERTOS = {1: 9, 2: 11, 3: 10, 4: 13, 9: 14, 11: 6}
CASOS = [(1, 9), (1, 5), (2, 11), (2, 1), (3, 10), (3, 4), (4, 13), (9, 14), (9, 3), (11, 6)]


def _comparar(c: dict, n: dict) -> None:
    assert escalares(c) == escalares(n)
    for k, v in c.items():
        if isinstance(v, pd.DataFrame):
            assert igual_df(v, n[k]), k


def _departamento(conn, dep: int) -> dict:
    return {"id": dep, "nombre": conn.execute("SELECT nombre FROM departamentos WHERE id=%s", [dep]).fetchone()[0]}


def _periodo(conn, pid: int) -> dict:
    cur = conn.execute("SELECT id, nombre, anio, semestre, fecha_inicio, fecha_fin, estado, observaciones FROM periodos "
                       "WHERE id=%s", [pid])
    return dict(zip([d.name for d in cur.description], cur.fetchone()))


@pytest.mark.parametrize("dep,pid", CASOS)
def test_tablero_motor_igual_al_certificado(db_conn, dep, pid):
    """D-AN1: el tablero de las 3 capas (metricas incluidas) es identico al certificado; 0 escrituras al leer."""
    c, n = certified_inicio(db_conn, INST, dep), motor(db_conn, INST, dep)
    out = []
    for ns in (c, n):
        hoy = str(ns["fecha_referencia_contexto_v182"](pid))
        out.append(ns["_inicio_datos_tablero_cache"](pid, INST, dep, hoy))
    _comparar(out[0]["metricas"], out[1]["metricas"])
    _comparar({k: v for k, v in out[0].items() if k != "metricas"}, {k: v for k, v in out[1].items() if k != "metricas"})
    assert c["get_periodo_abierto"]() == n["get_periodo_abierto"]()
    assert sum(len(o["commits"]) for o in c["_frames"].ops) == 0


@pytest.mark.parametrize("dep", sorted(ABIERTOS))
def test_contrato_ui_igual_a_la_pagina_certificada(db_conn, dep):
    """Estado tablero (periodo abierto de mayor id): pagina certificada literal == payload NEXT."""
    c, n = certified_inicio(db_conn, INST, dep), motor(db_conn, INST, dep)
    abierto = c["get_periodo_abierto"]()
    assert int(abierto["id"]) == ABIERTOS[dep] and abierto == n["get_periodo_abierto"]()
    payload = payload_motor(n, _departamento(db_conn, dep), n["get_periodo_abierto"]())
    cert = pagina_certificada(c, abierto, departamento_scope=dep)
    assert normalizar_certificado(cert, payload["titulo"]) == eventos_payload(payload)
    assert cert[0] == ("title", payload["titulo"])  # sin pertenencia, el titulo certificado ya es el operativo


@pytest.mark.parametrize("dep,pid", [(1, 5), (9, 3), (2, 1)])
def test_periodo_historico_reabierto(db_conn, dep, pid):
    """Un periodo anterior reabierto por excepcion: "Foto al cierre", fecha de referencia = fin del periodo y la mezcla
    certificada de foto historica (metricas) con filtros ``Activa`` actuales (anomalia §36.9) — igual al certificado."""
    db_conn.execute("UPDATE periodos SET estado='Abierto' WHERE id=%s", [pid])  # ROLLBACK del test
    db_conn.execute("UPDATE periodos SET estado='Cerrado' WHERE id=%s", [ABIERTOS[dep]])
    c, n = certified_inicio(db_conn, INST, dep), motor(db_conn, INST, dep)
    abierto = c["get_periodo_abierto"]()
    assert int(abierto["id"]) == pid
    payload = payload_motor(n, _departamento(db_conn, dep), n["get_periodo_abierto"]())
    cert = pagina_certificada(c, abierto, departamento_scope=dep)
    assert normalizar_certificado(cert, payload["titulo"]) == eventos_payload(payload)
    t = payload["tablero"]
    assert t["periodo"]["linea"].startswith("**Foto al cierre:**") and t["periodo"]["historico"]
    assert t["periodo"]["actualizar"]["caption"].startswith(P.CAPTION_HISTORICO)
    assert t["graficos"][0]["vacio"]  # cargos: designaciones ya no "Activa" (foto historica)
    problemas = next(x for x in t["salud"]["controles"] if "Asignaciones docentes" in x["titulo"])
    assert "a revisar" in problemas["titulo"]


def test_sin_periodo_abierto(db_conn):
    """Institucion 2 (departamentos sin periodos) y departamento con su periodo cerrado: estado B."""
    for inst, dep, cerrar in ((2, 5, None), (INST, 11, 6)):
        if cerrar:
            db_conn.execute("UPDATE periodos SET estado='Cerrado' WHERE id=%s", [cerrar])
        c, n = certified_inicio(db_conn, inst, dep), motor(db_conn, inst, dep)
        assert c["get_periodo_abierto"]() is None and n["get_periodo_abierto"]() is None
        payload = payload_motor(n, _departamento(db_conn, dep), None)
        cert = pagina_certificada(c, None, departamento_scope=dep)
        assert normalizar_certificado(cert, payload["titulo"]) == eventos_payload(payload)
        assert ("button", "🗓️ Ir a Períodos", "periodos") in cert


def test_coordinador_sin_departamento(db_conn):
    """Estado A: mensaje + boton a Consolidado; no se calcula ningun tablero (ninguna lectura del periodo)."""
    c = certified_inicio(db_conn, INST, 1)
    cert = pagina_certificada(c, c["get_periodo_abierto"](), rol="coordinador_institucional", departamento_scope=None)
    payload = {"titulo": P.titulo(None), "estado": "institucional", "institucional": P.institucional()}
    assert normalizar_certificado(cert, payload["titulo"]) == eventos_payload(payload)
    assert cert[-1] == ("button", "🏛️ Ir al consolidado institucional", "consolidado")
    assert payload["titulo"] == "Inicio — Departamento correspondiente"  # D-AN4: sin departamento operativo


def test_dos_diferencias_conscientes(db_conn):
    """D-AN4: con un departamento de PERTENENCIA distinto del operativo el certificado titula con la pertenencia; NEXT
    con el operativo.  D-AN3: el caption de la cache de 60 s se reemplaza.  Nada mas cambia."""
    c = certified_inicio(db_conn, INST, 9, departamento_nombre="Departamento de Pertenencia ZZNEXT")
    n = motor(db_conn, INST, 9)
    cert = pagina_certificada(c, c["get_periodo_abierto"](), departamento_scope=9)
    payload = payload_motor(n, _departamento(db_conn, 9), n["get_periodo_abierto"]())
    assert cert[0] == ("title", "Inicio — Departamento de Pertenencia ZZNEXT")
    assert payload["titulo"] == f"Inicio — {_departamento(db_conn, 9)['nombre']}"
    assert any(e[0] == "caption" and "hasta 60 segundos" in e[1] for e in cert)
    distintos = [(a, b) for a, b in zip(cert, eventos_payload(payload)) if a != b]
    # + D-UA1 (6A-B3): la ayuda dice "unidades académicas" en lugar de "escuelas"
    assert len(distintos) == 3 and len(cert) == len(eventos_payload(payload))
    assert any(AYUDA_UA_CERT in str(a) and AYUDA_UA in str(b) for a, b in distintos)


# ------------------------------------------------------------------------------------------ casos sinteticos ZZNEXT
def _clonar(conn, tabla: str, donde: str, cambios: dict) -> int:
    cols = [r[0] for r in conn.execute("SELECT column_name FROM information_schema.columns WHERE table_name=%s AND "
                                       "column_name<>'id' ORDER BY ordinal_position", [tabla])]
    sel = ", ".join(f"%s AS {c}" if c in cambios else c for c in cols)
    return conn.execute(f"INSERT INTO {tabla} ({', '.join(cols)}) SELECT {sel} FROM {tabla} WHERE {donde} LIMIT 1 "
                        f"RETURNING id", [cambios[c] for c in cols if c in cambios]).fetchone()[0]


def vencimientos_sinteticos(conn, n: int, docente: bool = True) -> None:
    """``n`` designaciones ``Activa`` con vencimiento previsto dentro de 30 dias (dep. 1, periodo 9)."""
    for i in range(n):
        cuil = f"20-98{i:06d}-1"
        _clonar(conn, "docentes", "institucion_id=1 AND departamento_id=1",
                {"cuil": cuil, "apellido": f"ZZNEXT{i:02d}", "nombres": "Vence", "nombre": f"ZZNEXT{i:02d}, Vence",
                 "estado": "Activo", "sqlite_id": None})
        _clonar(conn, "designaciones", "institucion_id=1 AND departamento_id=1 AND periodo_id=9 AND estado='Activa' AND "
                f"COALESCE(funcion_no_docente,0)={0 if docente else 1}",
                {"cuil": cuil, "fecha_hasta_prevista": f"2026-11-{(i % 20) + 1:02d}", "fecha_hasta": None,
                 "sqlite_id": None})


def test_vencimientos_y_acciones_con_datos(db_conn):
    """10 vencimientos (9 docentes + 1 no docente) -> accion 🟠 (10 casos), tabla con las 8 primeras + Excel global y
    "Ver todos los vencimientos" -> Designaciones; igual que la pagina certificada."""
    vencimientos_sinteticos(db_conn, 9)
    _clonar(db_conn, "designaciones", "institucion_id=1 AND departamento_id=1 AND periodo_id=9 AND estado='Activa' AND "
            "COALESCE(funcion_no_docente,0)=1", {"fecha_hasta_prevista": "2026-11-20", "fecha_hasta": None,
                                                 "sqlite_id": None})
    c, n = certified_inicio(db_conn, INST, 1), motor(db_conn, INST, 1)
    payload = payload_motor(n, _departamento(db_conn, 1), n["get_periodo_abierto"]())
    cert = pagina_certificada(c, c["get_periodo_abierto"](), departamento_scope=1)
    assert normalizar_certificado(cert, payload["titulo"]) == eventos_payload(payload)
    t = payload["tablero"]
    accion = next(a for a in t["acciones"]["items"] if "a vencer" in a["titulo"])
    # anomalia certificada de texto: el plural conserva la tilde ("designaciónes", "comisiónes", "asignaciónes")
    assert accion["titulo"] == "10 designaciónes próximas a vencer" and accion["icono"] == "🟠"
    assert accion["boton"] == {"label": "Revisar designaciones", "destino": "designaciones", "primario": False}
    v = t["vencimientos"]
    assert v["excel"] and len(v["tabla"]["filas"]) == 8 and v["tabla"]["columnas"] == P.COLS_VENCIMIENTOS
    assert v["boton"]["destino"] == "designaciones"
    dias = [f[3] for f in v["tabla"]["filas"]]
    assert dias == sorted(dias) and all(0 <= d <= 30 for d in dias)
    assert ("dataframe", v["tabla"], True) in cert  # el Excel global alcanza a esta tabla (D-AN6)


def test_comision_sin_cubrir_y_problemas(db_conn):
    """Comision activa sin docentes + asignacion con cargo distinto al de la designacion: acciones 🔴 con sus destinos
    (Comisiones), salud con el control de asignaciones en rojo; igual que la pagina certificada."""
    _clonar(db_conn, "comisiones", "institucion_id=1 AND departamento_id=1 AND periodo_id=9 AND estado='Activa'",
            {"nombre_comision": "ZZNEXT-SIN-DOCENTE", "sqlite_id": None})
    db_conn.execute("UPDATE asignaciones_docentes_comision SET rol='Titular' WHERE id=(SELECT a.id FROM "
                    "asignaciones_docentes_comision a JOIN comisiones c ON c.id=a.comision_id WHERE c.periodo_id=9 AND "
                    "a.departamento_id=1 AND a.estado='Activa' AND a.rol<>'Titular' ORDER BY a.id LIMIT 1)")
    c, n = certified_inicio(db_conn, INST, 1), motor(db_conn, INST, 1)
    payload = payload_motor(n, _departamento(db_conn, 1), n["get_periodo_abierto"]())
    cert = pagina_certificada(c, c["get_periodo_abierto"](), departamento_scope=1)
    assert normalizar_certificado(cert, payload["titulo"]) == eventos_payload(payload)
    items = {a["boton"]["label"]: a for a in payload["tablero"]["acciones"]["items"]}
    assert items["Ver comisiones"]["boton"]["destino"] == "comisiones"
    assert items["Ver comisiones"]["titulo"] == "1 comisión sin cubrir"


# ------------------------------------------------------------------------------------------ anomalias congeladas (§36)
def test_anomalias_certificadas_preservadas(db_conn):
    n = motor(db_conn, INST, 3)
    t = payload_motor(n, _departamento(db_conn, 3), n["get_periodo_abierto"]())["tablero"]
    tarjetas = {m["label"]: m["valor"] for m in t["situacion"]["tarjetas"]}
    ind = {m["label"]: m for fila in t["indicadores"]["filas"] for m in fila}
    # 5: 0 comisiones abiertas con horas frente a comision (horas institucionales via productividad)
    abiertas = db_conn.execute("SELECT count(*) FROM comisiones co JOIN periodos p ON p.id = co.periodo_id WHERE "
                               "co.institucion_id = %s AND co.departamento_id = 3 AND p.estado = 'Abierto'",
                               [INST]).fetchone()[0]  # Etapa 5 / C2: derivado (la anomalia exige 0)
    assert abiertas == 0 and tarjetas["Comisiones abiertas"] == "0" and ind["Horas frente a comisión"]["valor"] == "90 hs"
    assert ind["Horas no lectivas"]["caption"].startswith("Parámetro base 0 %")
    # 4: "sin carga" (local) != "Sin actividad registrada" (Productividad institucional)
    sin_carga = next(a for a in t["acciones"]["items"] if "sin carga" in a["titulo"])
    prod = n["get_docentes_productividad_periodo"](10)
    # Etapa 5 / C2: la anomalia es que los dos indicadores DIFIEREN (antes literales 209 / 199 de la base dev)
    n_sin_carga = int(sin_carga["titulo"].split()[0])
    n_sin_actividad = int((prod["diagnostico"] == "Sin actividad registrada").sum())
    assert sin_carga["titulo"] == f"{n_sin_carga} docentes sin carga" and n_sin_carga > 0 and n_sin_actividad > 0
    assert n_sin_carga != n_sin_actividad
    # 6: alumnos por docente 0 (tabla de inscriptos vacia)
    assert ind["Alumnos por docente"]["valor"] == "0"
    # 2: superposiciones sin columnas de materias (la pagina pide materia_1/2; v195 entrega asignatura_1/2)
    n9 = motor(db_conn, INST, 9)
    t9 = payload_motor(n9, _departamento(db_conn, 9), n9["get_periodo_abierto"]())["tablero"]
    sup = t9["salud"]["controles"][0]
    assert sup["titulo"] == "🔴 Superposiciones horarias — 25 casos"
    assert sup["casos"]["tabla"]["columnas"] == ["Docente", "CUIL", "Día", "Comisión 1", "Horario 1", "Comisión 2",
                                                "Horario 2"]
    # 8: alertas criticas suman filas de superposicion + personas con exceso (25 + 16)
    assert {m["label"]: m["valor"] for m in t9["situacion"]["tarjetas"]}["Alertas críticas"] == "41"
    # 12/7: semaforos de Inicio sin umbrales de Productividad (solo cantidad de casos)
    assert t9["salud"]["controles"][1]["titulo"] == "🔴 Exceso de dedicación — 16 casos"


def test_periodo_abierto_vencido_y_graficos_vacios(db_conn):
    """Departamento 11: 2026-1 abierto con fin vencido -> barra al 100 % y ambos graficos "Todavía no hay datos"."""
    n = motor(db_conn, INST, 11)
    t = payload_motor(n, _departamento(db_conn, 11), n["get_periodo_abierto"]())["tablero"]
    assert t["periodo"]["progreso"] == 1.0
    assert t["periodo"]["caption_progreso"] == "El período ya alcanzó su fecha de finalización prevista."
    assert [g["vacio"] for g in t["graficos"]] == [True, True]
    assert t["graficos"][0]["mensaje"] == P.MSG_SIN_GRAFICO
    assert t["salud"]["porcentaje"] == 100 and t["acciones"]["vacio"]
