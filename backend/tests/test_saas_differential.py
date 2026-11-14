"""Diferencial de Administración SaaS contra B13-FIX02: ``render_admin_saas`` (l. 3339) se EJECUTA desde
``reference_fix02`` (``saas_support``) sobre los mismos datos de deptit_next_dev y se compara con el servicio NEXT.

Se distingue explícitamente:
A. EQUIVALENCIA certificada: tablas (mismas filas, orden y valores), tablero de uso, catálogos, labels de las 5
   pestañas, mensajes, métricas del diagnóstico de planes, conteos de cupo y roles denegados;
B. HARDENING aprobado (no es un fallo diferencial): sin ``sqlite_id``/``source_db`` (D-AP6), sin rutas ni textos de
   archivos SQLite (D-AP3), aviso de eliminación de instituciones/departamentos vacíos (D-AP1/D-AP2), Credenciales
   iniciales sin tooling (Etapa 6).  Cada diferencia se compara contra su oráculo (``textos.EXCLUIDOS``)."""

from __future__ import annotations

import pandas as pd
import pytest

from analisis.pagina import tabla
from saas import lecturas as L
from saas import textos as T
from saas.service import SaasError
from saas_support import COORD, SUPER, FIXED_TODAY, render  # noqa: F401
from saas_support import audit_store, auth_db, db_conn, saas, superadmin  # noqa: F401  (fixtures)

pytestmark = pytest.mark.filterwarnings("ignore:pandas only supports SQLAlchemy:UserWarning")
OCULTAS = {"slug", "institucion_slug", "sqlite_id", "source_db"}


def _texto(df: pd.DataFrame) -> pd.DataFrame:
    return df.reset_index(drop=True).map(lambda v: "" if v is None or (isinstance(v, float) and v != v) else str(v))


def _igual_sin_ocultas(cert: pd.DataFrame, nuevo: dict) -> None:
    """A + B: mismas filas/orden/valores; solo faltan las columnas técnicas aprobadas (D-AP6)."""
    esperado = cert.drop(columns=[c for c in cert.columns if c in OCULTAS])
    assert set(cert.columns) - set(esperado.columns) <= OCULTAS
    assert tabla(esperado) == nuevo


@pytest.fixture
def cert(db_conn):
    return render(db_conn, SUPER, {"superadmin_institucion_id": 1})


def test_tablas_principales_identicas_salvo_columnas_tecnicas(cert, saas, superadmin):
    ov = saas.overview(superadmin)
    frames = cert.frames
    # orden certificado de st.dataframe: 0 Instituciones, 1 Datos actuales (Eliminar institución), 2 Departamentos,
    # 3 Datos actuales del departamento, 4 Usuarios, 5 Datos actuales del usuario, 6 Uso, 7 Datos actuales comercial
    assert len(frames) == 8
    _igual_sin_ocultas(frames[0], ov["tablas"]["instituciones"])
    _igual_sin_ocultas(frames[2], ov["tablas"]["departamentos"])
    assert tabla(frames[4]) == ov["tablas"]["usuarios"]
    assert not {"salt", "password_hash"} & set(frames[4].columns) and \
        not {"salt", "password_hash"} & set(ov["tablas"]["usuarios"]["columnas"])
    assert tabla(frames[6]) == ov["tablas"]["uso"]
    # B: el certificado SÍ muestra columnas técnicas (el hardening se ejercita de verdad)
    assert {"sqlite_id", "source_db"} <= set(frames[0].columns) and {"sqlite_id", "source_db"} <= set(frames[2].columns)


def test_fichas_datos_actuales_identicas(cert, saas, superadmin):
    ov = saas.overview(superadmin)
    sel = {e[3]: e[4] for e in cert.ev if e[0] == "selectbox"}
    inst = next(i for i in ov["instituciones"] if f"{i['nombre']} — {i['estado']}" == sel["admin_del_inst_sel"])
    assert tabla(cert.frames[1]) == inst["ficha"]
    dep = next(d for d in ov["departamentos"] if f"{d['nombre']} — {d['estado']}" == sel["admin_edit_dep_sel"]
               and d["institucion"] == sel["admin_dep_inst"])
    assert tabla(cert.frames[3]) == dep["ficha"]
    usr = next(u for u in ov["usuarios"] if u["etiqueta"] == sel["admin_edit_user_sel"])
    assert tabla(cert.frames[5]) == usr["ficha"]
    com = next(i for i in ov["instituciones"] if f"{i['nombre']} — {i['estado']}" == sel["admin_com_inst_sel"])
    assert tabla(cert.frames[7]) == com["ficha"]


def test_selectores_y_catalogos(cert, saas, superadmin):
    ov = saas.overview(superadmin)
    sel = {e[3]: e for e in cert.ev if e[0] == "selectbox"}
    assert sel["admin_inst_plan"][2] == ov["catalogos"]["planes"] == T.PLANES_COMERCIALES
    assert sel["admin_inst_plan"][4] == "Institucional"
    assert sel["admin_inst_estado_pago"][2] == T.ESTADOS_PAGO
    assert sel["admin_inst_suscripcion"][2] == T.ESTADOS_SUSCRIPCION
    assert sel["admin_inst_acceso"][2] == T.ESTADOS_INSTITUCION
    assert sel["admin_user_rol"][2] == T.AUTH_ROLES and sel["admin_user_rol"][4] == "usuario_departamento"
    # opciones de usuarios: "{email} - {rol} - {estado}" en el orden de la tabla
    assert sel["admin_estado_user_sel"][2] == [u["etiqueta"] for u in ov["usuarios"]]
    # Institución de Departamentos / Crear usuario: solo Activas, por nombre
    activas = [i["nombre"] for i in ov["instituciones"] if i["estado"] == "Activa"]
    assert sel["admin_dep_inst"][2] == activas and sel["admin_user_inst"][2] == activas
    # Crear usuario: "Sin departamento" + departamentos Activos de la institución elegida
    inst_id = next(i["id"] for i in ov["instituciones"] if i["nombre"] == sel["admin_user_inst"][4])
    assert sel["admin_user_dep"][2] == [T.SIN_DEPARTAMENTO] + [
        d["nombre"] for d in ov["departamentos"] if d["institucion_id"] == inst_id and d["estado"] == "Activo"]
    # Cupo usado del alta (contar_usuarios_activos_institucion)
    cap = next(e[1] for e in cert.ev if e[0] == "caption" and e[1].startswith("Cupo usado"))
    inst = next(i for i in ov["instituciones"] if i["id"] == inst_id)
    assert cap == T.UI["usuarios"]["crear"]["cupo"].format(activos=inst["activos"], max=inst["max_usuarios"])
    nums = {e[2]: e for e in cert.ev if e[0] == "number_input"}
    assert (nums["admin_inst_cupo"][3], nums["admin_inst_cupo"][4], nums["admin_inst_cupo"][5]) == \
        (T.CUPO_MIN, T.CUPO_MAX, T.CUPO_DEFAULT)


def _labels(ev) -> list[str]:
    out = []
    for e in ev:
        if e[0] in ("title", "subheader", "caption", "info", "warning", "error", "success", "markdown") or \
                e[0] in ("tab", "expander"):
            out.append(str(e[1]))
        elif e[0] in ("button", "checkbox", "text_input", "text_area", "number_input", "date_input", "selectbox"):
            out.append(str(e[1]))
        elif e[0] == "tabs":
            out.extend(e[1])
    return out


def _strings(obj) -> set[str]:
    if isinstance(obj, str):
        return {obj}
    if isinstance(obj, dict):
        return set().union(*[_strings(v) for v in obj.values()]) if obj else set()
    if isinstance(obj, (list, tuple)):
        return set().union(*[_strings(v) for v in obj]) if obj else set()
    return set()


def test_labels_de_las_5_pestanas_presentes_o_excluidos_por_decision(cert):
    """A: todo label/mensaje visible del certificado existe en ``textos.UI`` de NEXT; B: los ausentes son exactamente
    los textos excluidos por decisión aprobada (oráculo ``EXCLUIDOS``)."""
    nuestros = _strings(T.UI) | {T.TITULO, T.MSG_SOLO_SUPERADMIN, "Institución a eliminar"}
    criterio = "\n".join(f"- {t}" for t in T.UI["comercial"]["criterio"]["texto"])
    faltan = []
    for lab in _labels(cert.ev):
        if lab in nuestros or lab in T.EXCLUIDOS or any(lab.startswith(p) for p in T.EXCLUIDOS_PREFIJOS):
            continue
        if lab.startswith("**Datos actuales") or lab.startswith("### Integridad"):
            continue  # títulos de las fichas / del diagnóstico: mismos textos en ``UI`` sin markdown
        if lab.strip().startswith("- **Acceso Activa**"):
            assert " ".join(lab.split()) == " ".join(criterio.split())
            continue
        if lab.startswith("Cupo usado:"):
            continue  # verificado con valores en ``test_selectores_y_catalogos``
        faltan.append(lab)
    assert faltan == []
    assert T.UI["pestanas"] == next(e[1] for e in cert.ev if e[0] == "tabs")
    # B: los excluidos realmente aparecían en el certificado (no son oráculos vacíos)
    vistos = set(_labels(cert.ev))
    for decision, texto in (("D-AP1", "Esta acción elimina la institución del sistema SaaS"),
                            ("D-AP2", "Eliminar un departamento borra su registro de administración"),
                            ("D-AP3", "Respaldar y eliminar también la carpeta local"),
                            ("D-AP3", "#### Fuente única de planes de estudio")):
        assert any(v.startswith(texto) for v in vistos), decision
        assert not any(s.startswith(texto) for s in nuestros), decision
    assert any(v.startswith("Usuarios asignados: ") and "Base local" in v for v in vistos)
    assert any(v.startswith("Archivo usado: ") for v in vistos)


def test_diagnostico_de_planes_metricas_identicas(db_conn, saas, superadmin):
    for inst in (1, 2, 5):
        cert = render(db_conn, SUPER, {"superadmin_institucion_id": 1},
                      selects={"admin_dep_inst": _nombre(db_conn, inst)})
        metricas = [(e[1], e[2]) for e in cert.ev if e[0] == "metric"]
        nuevo = saas.planes(superadmin, {"institucion_id": inst})
        assert [(m["label"], m["valor"]) for m in nuevo["metricas"]] == [(lab, str(v)) for lab, v in metricas]
        # D-AP3: el certificado mostraba la ruta del archivo; NEXT no
        assert any(e[0] == "caption" and str(e[1]).startswith("Archivo usado:") for e in cert.ev)
        assert "Archivo" not in str(nuevo) and ".db" not in str(nuevo)


def _nombre(conn, inst_id):
    with conn.cursor() as cur:
        cur.execute("SELECT nombre FROM instituciones WHERE id = %s", [inst_id])
        return cur.fetchone()[0]


def test_tablero_de_uso_agregado_igual_a_la_semantica_por_departamento(db_conn):
    """El tablero NEXT (8 consultas) == ``get_uso_instituciones`` original certificada (N+1) sobre los mismos datos."""
    cert = render(db_conn, SUPER, {"superadmin_institucion_id": 1})
    original = cert.ns["get_uso_instituciones"]()
    with db_conn.transaction():
        nuevo = L.uso(db_conn, FIXED_TODAY)
    pd.testing.assert_frame_equal(_texto(original), _texto(nuevo))
    assert int(nuevo["Docentes"].sum()) > 0 and set(nuevo["Departamentos"]) >= {0}


def test_conteos_de_cupo_y_eliminacion_iguales(db_conn, saas, superadmin):
    cert = render(db_conn, SUPER, {"superadmin_institucion_id": 1})
    ns = cert.ns
    ov = saas.overview(superadmin)
    for inst in ov["instituciones"]:
        assert inst["activos"] == ns["contar_usuarios_activos_institucion"](inst["id"])
        n_deps = len(ns["get_departamentos_auth"](inst["id"], solo_activos=False))
        assert inst["dependencias"]["departamentos"] == n_deps
    for dep in ov["departamentos"]:
        with db_conn.transaction():
            n = db_conn.execute("SELECT COUNT(*) FROM app_usuarios WHERE departamento_id = %s", [dep["id"]]).fetchone()[0]
        assert dep["usuarios"] == n


@pytest.mark.parametrize("user", [COORD, {**COORD, "rol": "usuario_departamento", "departamento_id": 1},
                                  {**COORD, "rol": "solo_lectura", "departamento_id": 1},
                                  {**COORD, "rol": "solo_lectura", "rol_original": "coordinador_institucional",
                                   "modo_solo_lectura_comercial": True}])
def test_roles_no_superadmin_denegados_como_el_certificado(db_conn, user):
    st = render(db_conn, user, {})
    assert st.ev == [("title", T.TITULO), ("error", T.MSG_SOLO_SUPERADMIN)]


def test_credenciales_iniciales_sin_tooling(cert):
    code = next(e[1] for e in cert.ev if e[0] == "code")
    assert code.split("\n") == T.UI["credenciales"]["cuentas"]
    info = next(e[1] for e in cert.ev if e[0] == "info" and e[1].startswith("Ya no existen"))
    assert "tools/" in info and "tools/" not in T.UI["credenciales"]["info"]  # B: diferencia consciente (Etapa 6)
    assert info.split(" y verificá con")[0] == T.UI["credenciales"]["info"].split(" antes de habilitar")[0]


def test_lectura_sin_permiso_para_otros_roles(db_conn, saas, auth_db):
    from saas_support import ids_por_rol, sesion
    ids = ids_por_rol(db_conn)
    for rol in ("coordinador_institucional", "usuario_departamento"):
        record = sesion(auth_db, ids[rol])[0]
        with pytest.raises(SaasError) as exc:
            saas.overview(record)
        assert exc.value.status == 403 and exc.value.message == T.MSG_SOLO_SUPERADMIN
