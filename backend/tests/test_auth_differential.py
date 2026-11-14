"""Equivalencia con el codigo CERTIFICADO de reference_fix02 (solo lectura: sin bytecode, sin escrituras).

Compara las funciones de DEPTIT NEXT con las certificadas para los mismos datos:
- modulos puros importados de reference_fix02/deptit_refactor (B10, B12B, B12G);
- funciones del entry extraidas por AST (_hash_password, _verify_password, fecha_vencimiento_vencida, modulos).
"""

import ast
import hashlib
import itertools
import secrets
import sys
from datetime import date, datetime
from pathlib import Path

import pytest

sys.dont_write_bytecode = True  # nunca escribir __pycache__ dentro de reference_fix02
REFERENCE = Path(r"C:\DEPTIT_NEXT\reference_fix02")
ENTRY = REFERENCE / "app_postgresql_refactor_b13fix02_uat_fixes.py"
if str(REFERENCE) not in sys.path:
    sys.path.append(str(REFERENCE))

from deptit_refactor.b12b import scope_fail_closed as ref_scope  # noqa: E402
from deptit_refactor.security import authorization as ref_authz  # noqa: E402
from deptit_refactor.security import credentials as ref_cred  # noqa: E402
from deptit_refactor.security import session_adapter as ref_adapter  # noqa: E402
from deptit_refactor.security import session_b12g as ref_b12g  # noqa: E402
from deptit_refactor.security import ui_messages as ref_ui  # noqa: E402

from auth import core, policy  # noqa: E402
from auth.service import AuthService  # noqa: E402
from conftest import Clock, FakeRepo  # noqa: E402


def _entry_functions(*names, extra_source=""):
    tree = ast.parse(ENTRY.read_text(encoding="utf-8"))
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert sorted(n.name for n in nodes) == sorted(names)
    ns = {"hashlib": hashlib, "secrets": secrets, "datetime": datetime, "date": date}
    exec(compile(extra_source, "<extra>", "exec"), ns)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(ENTRY), "exec"), ns)
    return ns


def _fechas_date_to_iso():
    src = (REFERENCE / "deptit_refactor" / "extracted_batch04" / "fechas.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_date_to_iso")
    return ast.unparse(node)


ENTRY_NS = _entry_functions("_hash_password", "_verify_password", "fecha_vencimiento_vencida",
                            extra_source=_fechas_date_to_iso())
REF_EXPIRED = ENTRY_NS["fecha_vencimiento_vencida"]


# ------------------------------------------------------------------------------------------- contrasenas
def test_pbkdf2_hash_and_verify_identical_to_entry():
    for _ in range(20):
        pwd = secrets.token_urlsafe(secrets.randbelow(30) + 1)
        salt = secrets.token_hex(16)
        ref_salt, ref_digest = ENTRY_NS["_hash_password"](pwd, salt)
        assert ref_salt == salt and core.hash_password(pwd, salt) == ref_digest
        for candidate in (pwd, pwd + "x", ""):
            assert core.verify_password(candidate, salt, ref_digest) == \
                ENTRY_NS["_verify_password"](candidate, salt, ref_digest)
    for salt, digest in [(None, "a"), ("", "a"), ("a", None), ("a", "")]:
        assert core.verify_password("x", salt, digest) == ENTRY_NS["_verify_password"]("x", salt, digest)


def test_public_default_passwords_identical():
    assert core.PUBLIC_DEFAULT_PASSWORD_SHA256 == ref_cred.PUBLIC_DEFAULT_PASSWORD_SHA256
    for value in (None, "", "x", "admin", secrets.token_hex(8)):
        assert core.is_public_default_password(value) == ref_cred.is_public_default_password(value)


def test_dummy_and_messages_identical():
    assert (core.DUMMY_SALT, core.DUMMY_HASH) == (ref_b12g.DUMMY_SALT, ref_b12g.DUMMY_HASH)
    for name in ("GENERIC_LOGIN_MESSAGE", "UNAVAILABLE_MESSAGE", "PUBLIC_DEFAULT_MESSAGE",
                 "BLOCKED_INSTITUTION_MESSAGE", "BLOCKED_SUBSCRIPTION_MESSAGE", "NOTICE_EXPIRED", "NOTICE_REVOKED",
                 "NOTICE_INVALID"):
        assert getattr(core, name) == getattr(ref_b12g, name), name
    assert core.SAFE_USER_FIELDS == ref_b12g.SAFE_USER_FIELDS
    assert core.CONFIG_SPEC == ref_b12g.CONFIG_SPEC


# ------------------------------------------------------------------------------------------- funciones puras B12G
EMAILS = ["a@b.c", "  A@B.C ", "ÁNGEL@uno.edu.ar", "Ángel@uno.edu.ar", "", None, "x\u0301@y.z", 123]


def test_email_normalization_and_throttle_key_identical():
    for e in EMAILS:
        assert core.normalize_email(e) == ref_b12g.normalize_email(e)
        assert core.subject_key(e) == ref_b12g.subject_key(e)


def _rows():
    for rol, inst_estado, susc, pago, venc in itertools.product(
            ["superadmin", "coordinador_institucional", "usuario_departamento", "solo_lectura", "otro", None],
            [None, "Activa", "Bloqueada", "Suspendida", "Solo lectura"],
            [None, "Activa", "Inactiva", "Cancelada", "Prueba"],
            [None, "Activo", "Vencido", "Bonificado"],
            [None, "", "2000-01-01", "2999-12-31", "fecha-rota", date(2001, 1, 1), datetime(2999, 1, 1, 10)]):
        yield {"id": 7, "email": "User@Uno.edu", "nombre": "N", "rol": rol, "estado": "Activo", "salt": "s" * 32,
               "password_hash": "h" * 64, "institucion_id": 1, "departamento_id": 2, "institucion_nombre": "UNO",
               "institucion_slug": "uno", "institucion_estado": inst_estado, "fecha_vencimiento": venc,
               "estado_pago": pago, "suscripcion": susc, "departamento_nombre": "D", "departamento_slug": "d"}


def test_expiry_commercial_and_session_user_identical():
    count = 0
    for row in _rows():
        venc = row["fecha_vencimiento"]
        assert core.fecha_vencimiento_vencida(venc) == REF_EXPIRED(venc)
        ours = core.commercial_outcome(row, core.fecha_vencimiento_vencida)
        assert ours == ref_b12g.commercial_outcome(row, REF_EXPIRED)
        assert core.derive_session_user(row, ours) == ref_b12g.derive_session_user(row, ours)
        count += 1
    assert count == 6 * 5 * 5 * 4 * 7


def test_fingerprints_identical():
    for row in _rows():
        for change in ({}, {"id": 8}, {"email": "otro@x"}, {"rol": "solo_lectura"}, {"departamento_id": None},
                       {"salt": "t" * 32}, {"password_hash": None}):
            r = {**row, **change}
            assert core.identity_fingerprint(r) == ref_b12g.identity_fingerprint(r)
            assert core.credential_fingerprint(r) == ref_b12g.credential_fingerprint(r)
        break


def test_evaluate_fresh_identical():
    base = next(_rows())
    base.update(rol="usuario_departamento", institucion_estado="Activa", suscripcion="Activa", estado_pago="Activo",
                fecha_vencimiento=None)
    outcome = core.commercial_outcome(base)
    meta = ref_b12g.new_metadata(base, outcome, now=10.0, wall=0.0)
    variants = [[], [base, base], [{**base, "id": 99}], [{**base, "estado": "Inactivo"}], [{**base, "estado": None}],
                [{**base, "salt": "z" * 32}], [{**base, "email": "nuevo@x"}], [{**base, "rol": "superadmin"}],
                [{**base, "institucion_estado": "Bloqueada"}], [{**base, "suscripcion": "Cancelada"}],
                [{**base, "estado_pago": "Vencido"}], [{**base, "fecha_vencimiento": "2000-01-01"}], [base]]
    for rows in variants:
        assert core.evaluate_fresh(meta, rows, core.fecha_vencimiento_vencida) == \
            ref_b12g.evaluate_fresh(meta, rows, REF_EXPIRED)


def test_timeouts_identical():
    cfg_ours, cfg_ref = core.load_config(lambda n: None), ref_b12g.load_config(lambda n, d="": "")
    row = {**next(_rows()), "rol": "usuario_departamento"}
    user = {"id": 7}
    for issued_ago, idle in itertools.product([0, 60, 1799, 1800, 1801, 8 * 3600 - 1, 8 * 3600, 9 * 3600],
                                              [0, 1799, 1800, 1801]):
        now = 100000.0
        ref_meta = ref_b12g.new_metadata(row, "normal", now=now - issued_ago, wall=0.0)
        ref_meta["last_activity_mono"] = max(now - issued_ago, now - idle)
        our_meta = {**core.new_metadata(row, "normal", now=now - issued_ago),
                    "last_activity_mono": ref_meta["last_activity_mono"]}
        assert core.check_metadata(our_meta, now, cfg_ours) == ref_b12g.check_metadata(ref_meta, user, now, cfg_ref)


@pytest.mark.parametrize("value", ["", "5", "30", "240", "4", "241", "abc", "-1", " 15 ", "1440", "0"])
def test_config_validation_identical(value):
    for name in core.CONFIG_SPEC:
        ref_err = ours_err = None
        try:
            ref = ref_b12g.load_config(lambda n, d="": value if n == name else "")
        except ref_b12g.ConfigError:
            ref_err = True
        try:
            ours = core.load_config(lambda n: value if n == name else None)
        except core.ConfigError:
            ours_err = True
        assert ref_err == ours_err
        if not ref_err:
            assert (ours.idle_seconds, ours.absolute_seconds, ours.max_failed_attempts, ours.failure_window_seconds,
                    ours.lockout_seconds) == (ref.idle_seconds, ref.absolute_seconds, ref.max_failed_attempts,
                                              ref.failure_window_seconds, ref.lockout_seconds)


# ------------------------------------------------------------------------------------------- login completo
class _RefStoreAdapter:
    """Throttle falso con la API del PgLoginThrottleStore certificado (comparte estado con FakeRepo)."""

    def __init__(self, repo):
        self.repo = repo

    def lock_state(self, key):
        return self.repo.lock_state(key), None, None

    def register_failure(self, key, cfg):
        return self.repo.register_failure(key, cfg)

    def reset(self, key):
        self.repo.reset(key)

    def purge(self, older):
        self.repo.purge(older)


def _reference_runtime(repo, clock):
    ns = {"USE_POSTGRESQL": True, "_valor_configuracion": lambda n, d="": "",
          "fecha_vencimiento_vencida": REF_EXPIRED, "_verify_password": ENTRY_NS["_verify_password"],
          "_pg_raw_conn": lambda: (_ for _ in ()).throw(AssertionError("sin conexion real"))}
    rt = ref_b12g.SessionSecurityRuntime(ns)
    rt.reader = type("R", (), {"users_by_email": lambda self, e: repo.users_by_email(e),
                               "user_by_id": lambda self, i: repo.user_by_id(i)})()
    rt.store = _RefStoreAdapter(repo)
    rt.clock = clock
    return rt


def test_login_sequence_identical_to_certified_runtime():
    """Misma secuencia de intentos en ambos sistemas (cada uno con su propio estado): mismo resultado por paso."""
    clock_a, clock_b = Clock(), Clock()
    repo_a, repo_b = FakeRepo(clock_a), FakeRepo(clock_b)
    for u_b, u_a in zip(repo_b.users, repo_a.users):  # mismas credenciales en ambos
        u_b.update(salt=u_a["salt"], password_hash=u_a["password_hash"])
    repo_b.passwords = repo_a.passwords
    ref = _reference_runtime(repo_a, clock_a)
    # 6A-B1: el re-hash progresivo es una desviacion aditiva (test_e6_b1_auth); aca se compara el flujo certificado.
    ours = AuthService(repo_b, clock=clock_b, config_source=lambda n: None, password_upgrade=False)
    pw = repo_a.passwords
    steps = [("info@test.local", pw["info@test.local"], 0), ("INFO@test.local ", pw["info@test.local"], 0),
             ("nadie@test.local", "x", 0), ("", "x", 0), ("info@test.local", "", 0),
             ("inactivo@test.local", pw["inactivo@test.local"], 0), ("super@test.local", pw["super@test.local"], 0),
             ("coord@test.local", pw["coord@test.local"], 0), ("lector@test.local", pw["lector@test.local"], 0)]
    steps += [("uba@test.local", "mal", 1)] * 5 + [("uba@test.local", pw["uba@test.local"], 0),
                                                   ("uba@test.local", pw["uba@test.local"], 900),
                                                   ("uba@test.local", "mal", 0)]
    for email, pwd, advance in steps:
        clock_a.advance(advance)
        clock_b.advance(advance)
        r, o = ref.login(email, pwd), ours.login(email, pwd)
        assert (r.user, r.message) == (o.user, o.message), email
        if r.meta:
            for k in ("user_id", "identity_fp", "credential_fp", "commercial"):
                assert r.meta[k] == o.meta[k]
    assert repo_a.throttle.keys() == repo_b.throttle.keys()


@pytest.mark.parametrize("mutate", [
    lambda r: r.institutions_rows[0].update(estado="Suspendida"),
    lambda r: r.institutions_rows[0].update(suscripcion="Inactiva"),
    lambda r: r.institutions_rows[0].update(estado="Solo lectura"),
    lambda r: r.institutions_rows[1].update(estado_pago="Vencido"),
])
def test_commercial_login_identical(mutate):
    clock = Clock()
    repo = FakeRepo(clock)
    mutate(repo)
    ref = _reference_runtime(repo, clock)
    ours = AuthService(repo, clock=clock, config_source=lambda n: None)
    for email in ("info@test.local", "uba@test.local", "coord@test.local", "super@test.local"):
        r, o = ref.login(email, repo.passwords[email]), ours.login(email, repo.passwords[email])
        assert (r.user, r.message) == (o.user, o.message), email


# ------------------------------------------------------------------------------------------- B10 / B12B
ROLES = ["superadmin", "coordinador_institucional", "usuario_departamento", "solo_lectura", "raro", None]
MODES = ["normal", "read_only", "blocked", "otro", None]
IDS = [None, 1, 2]


def test_policy_constants_identical():
    assert policy.KNOWN_ROLES == ref_authz.KNOWN_ROLES and policy.KNOWN_DOMAINS == ref_authz.KNOWN_DOMAINS
    assert policy.BUSINESS_DOMAINS == ref_authz.BUSINESS_DOMAINS
    for role, op in itertools.product(ROLES, ["read", "write", "delete", "admin"]):
        assert policy._MUTATION_MATRIX.get(role, {}).get(op, frozenset()) == \
            ref_authz._MUTATION_MATRIX.get(role, {}).get(op, frozenset())
        assert policy._READ_MATRIX.get(role) == ref_authz._READ_MATRIX.get(role)


def test_decide_identical_on_full_grid():
    n = 0
    for role, mode, inst, dep, hinst, hdep in itertools.product(ROLES, MODES, IDS, IDS, IDS, IDS):
        ours_actor = policy.ActorContext(True, role, mode, "u", inst, dep, hinst, hdep)
        ref_actor = ref_authz.ActorContext(True, role, mode, "u", inst, dep, hinst, hdep)
        for domain, op, scope in itertools.product(sorted(ref_authz.KNOWN_DOMAINS) + ["x"],
                                                   ["read", "write", "delete", "admin"],
                                                   ["department", "institution", "global"]):
            a, b = policy.decide(ours_actor, policy.Action(domain, op, scope)), \
                ref_authz.decide(ref_actor, ref_authz.Action(domain, op, scope))
            assert (a.allowed, a.code) == (b.allowed, b.code)
            n += 1
    assert n > 100000


def _sessions():
    for rol, extra, sel_inst, sel_dep in itertools.product(
            ["superadmin", "coordinador_institucional", "usuario_departamento", "solo_lectura", None],
            [{}, {"modo_solo_lectura_comercial": True, "rol_original": "coordinador_institucional"},
             {"institucion_estado": "Bloqueada"}, {"estado_pago": "Vencido"}],
            [None, 2, "3"], [None, 5, "x"]):
        user = {"id": 1, "email": "a@b", "rol": rol, "institucion_id": 1, "departamento_id": 1, **extra}
        scope = {}
        if sel_inst is not None:
            scope["superadmin_institucion_id"] = sel_inst
        if sel_dep is not None:
            scope["tenant_scope_departamento_id"] = sel_dep
        yield user, scope


def test_actor_from_session_identical():
    for user, scope in _sessions():
        ours = policy.actor_from_session(user, scope)
        ref = ref_adapter.actor_from_session({"auth_user": user, **scope})
        assert ours.__dict__ == ref.__dict__


MODULE_LABELS = {"inicio": "🏠 Inicio", "consolidado": "🏛️ Consolidado institucional", "periodos": "🗓️ Períodos",
                 "docentes": "👨‍🏫 Docentes", "sueldos": "💰 Sueldos", "designaciones": "📑 Designaciones",
                 "materias": "📚 Materias", "comisiones": "📋 Comisiones", "investigacion": "🔬 Investigación",
                 "extension": "🤝 Extensión", "actividades_especiales": "⭐ Actividades Especiales",
                 "analisis": "📊 Análisis", "movimientos": "📜 Movimientos", "disposiciones": "📄 Disposiciones",
                 "resoluciones_respaldos": "📂 Resoluciones y respaldos",
                 "administracion_saas": "⚙️ Administración SaaS"}


def _certified_modules(role, dep_scope):
    """Ejecuta el bloque REAL del entry (modulos_base ... modulos_visibles) con stubs."""
    tree = ast.parse(ENTRY.read_text(encoding="utf-8"))
    body = tree.body
    start = next(i for i, n in enumerate(body) if isinstance(n, ast.Assign)
                 and any(getattr(t, "id", "") == "modulos_base" for t in n.targets))
    block = ast.Module(body=body[start:start + 4], type_ignores=[])
    st = type("St", (), {"session_state": {"tenant_scope_departamento_id": dep_scope}})()
    ns = {"current_role": lambda: role, "st": st}
    exec(compile(block, str(ENTRY), "exec"), ns)
    return ns["modulos_visibles"]


def test_visible_modules_identical_to_entry():
    for role, dep in itertools.product(ROLES, [None, 1]):
        ours = [MODULE_LABELS[m[0]] for m in policy.visible_modules(role, dep)]
        assert ours == _certified_modules(role, dep), (role, dep)


def test_visual_permissions_identical():
    for user, scope in _sessions():
        ref_actor = ref_adapter.actor_from_session({"auth_user": user, **scope})
        our_actor = policy.actor_from_session(user, scope)
        for key, label in MODULE_LABELS.items():
            domain = next((m[2] for m in list(policy.MODULES_BASE) + [policy.MODULE_CONSOLIDADO, policy.MODULE_SAAS]
                           if m[0] == key), None)
            for op in ("write", "delete"):
                assert policy.visual_can(our_actor, op, domain) == ref_ui.visual_can(ref_actor, op, label), (key, op)


class _RefLookup:
    def __init__(self, repo):
        self.repo = repo

    def institution_exists(self, i):
        return self.repo.institution(i) is not None

    def department_institution(self, d):
        row = self.repo.department(d)
        return None if row is None else (row["institucion_id"] or 0)


def test_scope_resolution_identical_to_b12b():
    clock = Clock()
    repo = FakeRepo(clock)
    service = AuthService(repo, clock=clock, config_source=lambda n: None)
    from auth.service import SessionRecord
    for rol, inst, dep, sel_inst, sel_dep, ro in itertools.product(
            ["superadmin", "coordinador_institucional", "usuario_departamento", "solo_lectura", "raro"],
            [None, 1, 2, 999], [None, 1, 5, 999], [None, 1, 2, 0, "abc", 999], [None, 1, 5, 4, 0, " ", 999],
            [False, True]):
        user = {"id": 1, "rol": "solo_lectura" if ro else rol, "institucion_id": inst, "departamento_id": dep}
        if ro:
            user.update(modo_solo_lectura_comercial=True, rol_original=rol)
        scope = {}
        if sel_inst is not None:
            scope["superadmin_institucion_id"] = sel_inst
        if sel_dep is not None:
            scope["tenant_scope_departamento_id"] = sel_dep
        session = dict(scope)
        resolver = ref_scope.ScopeResolver(lambda: session, lambda: user, _RefLookup(repo), ttl=0)
        ref = resolver.resolve()
        ours = service.resolve_scope(SessionRecord(user=user, meta={}, scope=dict(scope)))
        ours_ids = (ours.institution and ours.institution["id"], ours.department and ours.department["id"])
        assert ours_ids == (ref.institution_id, ref.department_id), (user, scope)
        assert ours.reason == ref.reason, (user, scope)
