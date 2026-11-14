"""Diferenciales de LECTURA de Disposiciones: mismas funciones, certificado (AST sobre la base real) vs NEXT.

- Datos reales de ``deptit_next_dev`` (transaccion que se revierte): los 3 departamentos con disposiciones (1, 2 y 9),
  TODOS sus docentes habilitados (padron, numeracion, contexto completo con considerandos y Art. 1-4, preparacion
  masiva v162, estado funcional, texto no docente, estado de consulta, parametros por docente) y el periodo historico
  2026-1 (contexto con la foto al cierre v183).
- Escenarios sinteticos ZZNEXT (SAVEPOINT + ROLLBACK): funcion no docente (con y sin texto), mixta, prestado (ambito
  "prestador" con funciones del receptor), compartido, Investigacion/Extension sin comisiones (v249), Actividades
  Especiales (titulo, rol y "participante"), sin acto, cambio del padron (los numeros se corren), numero inicial con
  textos legacy raros y estado de consulta.
"""

from __future__ import annotations

import pytest

from disposiciones.lecturas import Lecturas
from disposiciones.repository import DisposicionesRepository
from disposiciones_support import (  # noqa: F401  (fixtures)
    DEP_NOMBRES, FIXED_TODAY, certified_disposiciones, db_conn, free_cuil, normal, periodo_id,
)

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")

CASOS_REALES = [(1, "2026-2"), (2, "2026-2"), (9, "2026-2")]


def _lados(conn, dep, dep_nombre=None):
    nombre = DEP_NOMBRES[dep] if dep_nombre is None else dep_nombre
    ns = certified_disposiciones(conn, 1, dep, dep_nombre=nombre)
    lec = Lecturas(DisposicionesRepository(conn, 1, dep), FIXED_TODAY, nombre)
    return ns, lec


def _padron(df):
    return [(r["cuil"], r.get("nombre_completo"), int(r["numero_disposicion_auto"])) for r in df.to_dict("records")]


def _partes(v):
    return sorted(v.split(" / ")) if isinstance(v, str) else v


def _igual_salvo_empate(cert, nxt, cuil, pid, db_conn):
    """Etapa 5 / Tanda C (C1), como ``test_comisiones_differential._sin_orden_detalle``: el certificado ordena
    ``get_designaciones`` por periodo y apellido/nombres SIN desempate (l. 32479), NEXT agrega ``d.id``.  Con dos o mas
    designaciones del docente en el periodo, el orden de las partes " / " (cargo, dedicacion, horas, fechas) del
    certificado depende del plan de PostgreSQL (6A-B3: aparecio en la regresion completa, no aislado).  Exacto primero;
    si difiere, solo se aceptan claves con las MISMAS partes en otro orden y solo para un docente con empate real.
    Recorre los dict anidados: ``preparar`` repite el contexto en ``contexto`` y ``variables`` (H-B3-11)."""
    if cert == nxt:
        return
    assert set(cert) == set(nxt), cuil
    distintas = [k for k in cert if cert[k] != nxt[k]]
    n = db_conn.execute("SELECT count(*) FROM designaciones WHERE periodo_id=%s AND cuil=%s", [pid, cuil]).fetchone()[0]
    assert n >= 2, (cuil, distintas)
    for k in distintas:
        if isinstance(cert[k], dict) and isinstance(nxt[k], dict):
            _igual_salvo_empate(cert[k], nxt[k], cuil, pid, db_conn)
            continue
        assert isinstance(cert[k], str) and " / " in cert[k] and _partes(cert[k]) == _partes(nxt[k]), (cuil, k)


def _comparar_docente(ns, lec, cuil, pid, numero, db_conn):
    _igual_salvo_empate(normal(ns["obtener_contexto_docente_disposicion"](cuil, pid)), normal(lec.contexto(cuil, pid)),
                        cuil, pid, db_conn)
    _igual_salvo_empate(normal(ns["preparar_disposicion_automatica_v158"](cuil, pid, str(numero), FIXED_TODAY)),
                        normal(lec.preparar(cuil, pid, str(numero), FIXED_TODAY)), cuil, pid, db_conn)
    assert ns["_estado_funcional_disposicion_v163"](cuil, pid) == lec.estado_funcional(cuil, pid)
    assert ns["_texto_funcion_no_docente_para_disposicion_v164"](cuil, pid) == lec.texto_funcion_no_docente(cuil, pid)
    assert normal(ns["get_estado_consulta_designacion"](cuil, pid)) == normal(lec.estado_consulta(cuil, pid))
    assert ns["get_parametros_docente_disposicion"](cuil) == lec.parametros_docente(cuil)
    assert ns["texto_departamento_disposicion_docente"](cuil, pid) == lec.texto_departamento_disposicion_docente(cuil, pid)
    assert normal(ns["_ambito_disposicion_v159"](cuil, pid)) == normal(lec.ambito(cuil, pid))


@pytest.mark.parametrize("dep,periodo", CASOS_REALES)
def test_padron_numeracion_y_contextos_reales(db_conn, dep, periodo):
    ns, lec = _lados(db_conn, dep)
    pid = periodo_id(db_conn, dep, periodo)
    assert ns["get_parametros_disposicion"]() == lec.parametros()
    assert ns["get_numero_inicial_disposiciones_v162"](pid) == lec.numero_inicial(pid)
    cert = _padron(ns["get_docentes_activos_para_disposiciones_v155"](pid))
    assert cert == _padron(lec.habilitados(pid)) and len(cert) >= 60
    assert [n for _, _, n in cert] == list(range(lec.numero_inicial(pid), lec.numero_inicial(pid) + len(cert)))
    for cuil, _, numero in cert:
        _comparar_docente(ns, lec, cuil, pid, numero, db_conn)


def test_periodo_historico_y_sin_habilitados(db_conn):
    """2026-1 (Cerrado): sin designaciones Activas -> 0 habilitados (no se puede generar); el contexto de cualquier
    docente del periodo se lee igual que el certificado (foto al cierre v183)."""
    ns, lec = _lados(db_conn, 1)
    pid = periodo_id(db_conn, 1, "2026-1")
    assert _padron(ns["get_docentes_activos_para_disposiciones_v155"](pid)) == _padron(lec.habilitados(pid)) == []
    cuiles = [r[0] for r in db_conn.execute("SELECT DISTINCT cuil FROM designaciones WHERE periodo_id=%s ORDER BY cuil "
                                            "LIMIT 12", [pid]).fetchall()]
    assert cuiles
    for cuil in cuiles:
        _comparar_docente(ns, lec, cuil, pid, 1, db_conn)


def test_empate_anidado_con_plan_forzado(db_conn):
    """H-B3-11: sin indices el certificado invierte el orden de las 2 designaciones de 20-99000101-5 en 2026-1; las
    diferencias (anidadas en ``contexto``/``variables`` de ``preparar``) son solo permutaciones y el helper las acepta.
    Con 1 designacion o partes distintas sigue fallando."""
    ns, lec = _lados(db_conn, 1)
    pid = periodo_id(db_conn, 1, "2026-1")
    cuil = "20-99000101-5"
    db_conn.execute("SET LOCAL enable_indexscan=off")
    db_conn.execute("SET LOCAL enable_bitmapscan=off")
    cert = normal(ns["preparar_disposicion_automatica_v158"](cuil, pid, "1", FIXED_TODAY))
    nxt = normal(lec.preparar(cuil, pid, "1", FIXED_TODAY))
    db_conn.execute("RESET ALL")
    assert cert != nxt and cert["contexto"] != nxt["contexto"]
    _igual_salvo_empate(cert, nxt, cuil, pid, db_conn)
    roto = {**nxt, "contexto": {**nxt["contexto"], "horas": "10 / 41"}}
    with pytest.raises(AssertionError):
        _igual_salvo_empate(cert, roto, cuil, pid, db_conn)
    otro = db_conn.execute("SELECT cuil FROM designaciones WHERE periodo_id=%s GROUP BY cuil HAVING count(*)=1 LIMIT 1",
                           [pid]).fetchone()[0]
    with pytest.raises(AssertionError):
        _igual_salvo_empate(cert, nxt, otro, pid, db_conn)


def test_departamento_desde_la_base_si_la_sesion_no_lo_trae(db_conn):
    """``_departamento_actual_operativo_nombre``: sin ``departamento_nombre`` en el usuario se lee de la base."""
    ns, lec = _lados(db_conn, 2, dep_nombre="")
    pid = periodo_id(db_conn, 2, "2026-2")
    for cuil, _, numero in _padron(lec.habilitados(pid))[:6]:
        _comparar_docente(ns, lec, cuil, pid, numero, db_conn)


def test_historial_igual_al_certificado(db_conn):
    for dep in (1, 2, 9):
        ns, lec = _lados(db_conn, dep)
        for pid in [None] + [r[0] for r in db_conn.execute(
                "SELECT id FROM periodos WHERE institucion_id=1 AND departamento_id=%s", [dep]).fetchall()]:
            assert normal(ns["get_disposiciones"](pid).to_dict("records")) == \
                normal(lec.historial(pid).to_dict("records"))


def test_legacy_774_se_listan_y_quedan_bloqueados(db_conn):
    from disposiciones import storage as S
    filas = db_conn.execute("SELECT archivo_word, plantilla_usada, estado FROM disposiciones").fetchall()
    assert len(filas) >= 774
    legacy = [f for f in filas if not str(f[0] or "").startswith("b12e:")]
    assert len(legacy) >= 774 and {S.estado_documento(f[0]) for f in legacy} == {"LEGACY_UNVERIFIED"}


# ------------------------------------------------------------------------------------------ escenarios sinteticos
def _docente(conn, cuil, apellido, dep=1, tipo="Propio", obs="", estado="Activo"):
    conn.execute("INSERT INTO docentes (institucion_id, departamento_id, cuil, apellido, nombres, estado, tipo_docente, "
                 "observaciones) VALUES (1, %s, %s, %s, 'ZZNEXT', %s, %s, %s)", [dep, cuil, apellido, estado, tipo, obs])


def _designacion(conn, cuil, pid, dep=1, tipo="Concursado", cargo="JTP", dedicacion="Simple", horas=10, nd=0,
                 texto="", estado="Activa", ad_honorem="No", resolucion=""):
    return conn.execute(
        "INSERT INTO designaciones (institucion_id, departamento_id, periodo_id, cuil, cargo, dedicacion, horas, "
        "tipo_designacion, ad_honorem, fecha_desde, fecha_hasta, estado, funcion_no_docente, texto_funcion_no_docente, "
        "numero_resolucion) VALUES (1, %s, %s, %s, %s, %s, %s, %s, %s, '2026-08-01', '2027-02-28', %s, %s, %s, %s) "
        "RETURNING id", [dep, pid, cuil, cargo, dedicacion, horas, tipo, ad_honorem, estado, nd, texto, resolucion]
    ).fetchone()[0]


def _comparar_sintetico(conn, dep, pid, cuiles):
    ns, lec = _lados(conn, dep)
    padron = _padron(ns["get_docentes_activos_para_disposiciones_v155"](pid))
    assert padron == _padron(lec.habilitados(pid))
    numeros = {c: n for c, _, n in padron}
    for cuil in cuiles:
        _comparar_docente(ns, lec, cuil, pid, numeros.get(cuil, 1), db_conn)
    return ns, lec, numeros


def test_no_docente_mixta_sin_acto_y_padron_que_se_corre(db_conn):
    pid = periodo_id(db_conn, 1, "2026-2")
    a, b, c = (free_cuil(db_conn, f"20-991300{i:02d}-1") for i in (1, 2, 3))
    with db_conn.transaction():
        antes = _padron(Lecturas(DisposicionesRepository(db_conn, 1, 1), FIXED_TODAY, DEP_NOMBRES[1]).habilitados(pid))
        _docente(db_conn, a, "AAAA ZZNEXT")  # primero alfabeticamente: corre todos los numeros
        _designacion(db_conn, a, pid, nd=1, texto="  administrativas   en Rectorado. ")
        _docente(db_conn, b, "ZZNEXT Mixta")
        _designacion(db_conn, b, pid, tipo="Interino", cargo="Adjunto", dedicacion="Parcial", horas=20)
        _designacion(db_conn, b, pid, nd=1, texto="de coordinación de carrera", ad_honorem="Sí")
        _docente(db_conn, c, "ZZNEXT SinTexto")
        _designacion(db_conn, c, pid, nd=1, texto="")
        ns, lec, numeros = _comparar_sintetico(db_conn, 1, pid, [a, b, c])
        assert numeros[a] == antes[0][2] and [n for *_, n in _padron(lec.habilitados(pid))][1] == antes[0][2] + 1
        assert lec.estado_funcional(a, pid)["es_exclusivamente_no_docente"] and lec.estado_funcional(b, pid)["es_mixta"]
        assert lec.preparar(c, pid, "1", FIXED_TODAY)["funcion_no_docente_sin_texto"] is True
        assert lec.preparar(b, pid, "1", FIXED_TODAY)["designaciones_incompletas"]  # sin acto vinculado


def test_prestado_compartido_ie_sin_comisiones_y_actividades(db_conn):
    p1, p2 = periodo_id(db_conn, 1, "2026-2"), periodo_id(db_conn, 2, "2026-2")
    x, y = free_cuil(db_conn, "20-99130011-1"), free_cuil(db_conn, "20-99130012-1")
    with db_conn.transaction():
        # x: origen dep 1, prestado al dep 2 (sin designacion alli) -> ambito "prestador"; con I/E y sin comisiones
        _docente(db_conn, x, "ZZNEXT Prestador")
        _designacion(db_conn, x, p1)
        _docente(db_conn, x, "ZZNEXT Prestador", dep=2, tipo="Prestado",
                 obs=f"Docente prestado desde {DEP_NOMBRES[1]}. No posee designación local.")
        proy = db_conn.execute("INSERT INTO proyectos_investigacion (institucion_id, departamento_id, nombre_proyecto, "
                               "codigo_proyecto, instituto_proyecto, estado) VALUES (1, 2, 'ZZNEXT Proyecto', "
                               "'PID-ZZ', 'Instituto ZZNEXT', 'Activo') RETURNING id").fetchone()[0]
        db_conn.execute("INSERT INTO investigacion_docente (institucion_id, departamento_id, periodo_id, cuil, "
                        "nombre_proyecto, rol, codigo_proyecto, instituto_proyecto, proyecto_id, estado_asignacion, "
                        "horas_asignadas) VALUES (1, 2, %s, %s, 'ZZNEXT Proyecto', 'Director', 'PID-ZZ', "
                        "'Instituto ZZNEXT', %s, 'Activa', 4)", [p2, x, proy])
        act = db_conn.execute("INSERT INTO actividades_especiales (institucion_id, departamento_id, periodo_id, titulo, "
                              "estado) VALUES (1, 1, %s, 'ZZNEXT Olimpíada', 'Activa') RETURNING id", [p1]).fetchone()[0]
        db_conn.execute("INSERT INTO actividad_especial_docente (institucion_id, departamento_id, actividad_id, "
                        "periodo_id, cuil, rol, estado_asignacion) VALUES (1, 1, %s, %s, %s, '', 'Activa')", [act, p1, x])
        # y: compartido (designacion propia en dep 1 y dep 2): cada departamento emite lo suyo
        _docente(db_conn, y, "ZZNEXT Compartido")
        _designacion(db_conn, y, p1)
        _docente(db_conn, y, "ZZNEXT Compartido", dep=2)
        _designacion(db_conn, y, p2, dep=2, cargo="Titular")
        db_conn.execute("INSERT INTO estado_consulta_designacion (institucion_id, departamento_id, periodo_id, cuil, "
                        "estado) VALUES (1, 1, %s, %s, 'Rever designación')", [p1, y])
        ns, lec, _ = _comparar_sintetico(db_conn, 1, p1, [x, y])
        ctx = lec.contexto(x, p1)
        assert ctx["ambito_disposicion"] == "prestador" and ctx["tiene_investigacion"]
        assert "Instituto ZZNEXT" in ctx["Escuelas en las que se encuentran las materias que dicta"]
        assert ctx["Texto Actividades Especiales"] == ("ARTÍCULO 3°.- Participó activamente de la siguiente actividad: "
                                                       "“ZZNEXT Olimpíada”, en carácter de participante.")
        assert lec.contexto(y, p1)["ambito_disposicion"] == "departamental"
        assert lec.estado_consulta(y, p1)["estado"] == "Rever designación"
        _comparar_sintetico(db_conn, 2, p2, [y])


@pytest.mark.parametrize("valor", ["abc", "72.9", "0", "-5", "", "nn", "9999", "111222", " 15 "])
def test_numero_inicial_texto_legacy(db_conn, valor):
    pid = periodo_id(db_conn, 9, "2026-2")
    with db_conn.transaction():
        db_conn.execute("DELETE FROM disposicion_parametros WHERE institucion_id=1 AND departamento_id=9 AND clave=%s",
                        [f"numero_inicial_disposiciones_periodo_{pid}"])
        db_conn.execute("INSERT INTO disposicion_parametros (institucion_id, departamento_id, clave, valor) VALUES "
                        "(1, 9, %s, %s)", [f"numero_inicial_disposiciones_periodo_{pid}", valor])
        ns, lec = _lados(db_conn, 9)
        assert ns["get_numero_inicial_disposiciones_v162"](pid) == lec.numero_inicial(pid)
        assert _padron(ns["get_docentes_activos_para_disposiciones_v155"](pid)) == _padron(lec.habilitados(pid))
