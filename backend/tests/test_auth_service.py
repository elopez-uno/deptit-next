"""Login, throttle, sesion y contexto contra el contrato certificado (B12G/B12B/B10), sin base de datos."""

import pytest

from auth import core, policy
from auth.service import AuthUnavailable, ContextError, SessionEnded

GENERIC = core.GENERIC_LOGIN_MESSAGE


def login(service, repo, email, password=None):
    return service.login(email, repo.passwords[email] if password is None else password)


def session_for(service, repo, email):
    result = login(service, repo, email)
    assert result.user is not None
    return service.start_session(result)


# ------------------------------------------------------------------------------------------- login
def test_valid_credentials_grant_access_without_secrets(service, repo):
    result = login(service, repo, "info@test.local")
    assert result.user is not None and result.message == ""
    assert not set(core.SECRET_FIELDS) & set(result.user)
    assert result.user["rol"] == "usuario_departamento"
    assert result.user["institucion_id"] == 1 and result.user["departamento_id"] == 1


def test_email_is_normalized(service, repo):
    result = service.login("  INFO@Test.Local ", repo.passwords["info@test.local"])
    assert result.user is not None


@pytest.mark.parametrize("email,password", [
    ("info@test.local", "contraseña-incorrecta"),
    ("nadie@test.local", "cualquier-cosa"),
    ("inactivo@test.local", None),  # inactivo CON la contrasena correcta
    ("", "x"),
    ("info@test.local", ""),
])
def test_every_rejection_has_the_same_generic_message(service, repo, email, password):
    if password is None:
        password = repo.passwords[email]
    result = service.login(email, password)
    assert result.user is None and result.message == GENERIC and result.status == 401


def test_exactly_one_pbkdf2_per_attempt(service, repo, monkeypatch):
    calls = []
    original = core.verify_password
    monkeypatch.setattr(core, "verify_password", lambda *a: calls.append(1) or original(*a))
    for email, pwd in [("info@test.local", "mal"), ("nadie@test.local", "mal"), ("", "x"),
                       ("inactivo@test.local", repo.passwords["inactivo@test.local"]),
                       ("info@test.local", repo.passwords["info@test.local"])]:
        calls.clear()
        service.login(email, pwd)
        assert len(calls) == 1, email


def test_public_default_password_rejected_before_db(service, repo, monkeypatch):
    import hashlib
    monkeypatch.setattr(core, "PUBLIC_DEFAULT_PASSWORD_SHA256",
                        frozenset({hashlib.sha256(b"publica-de-prueba").hexdigest()}))
    repo.calls.clear()
    result = service.login("info@test.local", "publica-de-prueba")
    assert result.user is None and result.message == core.PUBLIC_DEFAULT_MESSAGE
    assert repo.calls == []


def test_ambiguous_account_fails_closed(service, repo):
    repo.add_user(20, "Dup@test.local", "usuario_departamento", 1, 1)
    repo.add_user(21, "dup@test.local", "usuario_departamento", 1, 1)
    result = service.login("dup@test.local", repo.passwords["dup@test.local"])
    assert result.user is None and result.message == GENERIC


def test_lockout_after_threshold_even_with_correct_password(service, repo, clock):
    for _ in range(5):
        assert login(service, repo, "info@test.local", "mal").user is None
    assert login(service, repo, "info@test.local").user is None  # bloqueado: mismo mensaje
    clock.advance(15 * 60 - 1)
    assert login(service, repo, "info@test.local").user is None
    clock.advance(1)
    assert login(service, repo, "info@test.local").user is not None
    assert core.subject_key("info@test.local") not in repo.throttle  # login correcto limpia


def test_nonexistent_and_existing_accounts_are_throttled_identically(service, repo):
    for _ in range(5):
        service.login("nadie@test.local", "mal")
    assert repo.lock_state(core.subject_key("nadie@test.local"))


def test_db_failure_on_login_is_unavailable(service, repo):
    repo.fail = True
    with pytest.raises(AuthUnavailable):
        login(service, repo, "info@test.local")


# ------------------------------------------------------------------------------------------- comercial
def test_commercial_blocked_institution(service, repo):
    repo.institutions_rows[0]["estado"] = "Suspendida"
    result = login(service, repo, "info@test.local")
    assert result.user is None and result.message == core.BLOCKED_INSTITUTION_MESSAGE and result.status == 403


def test_commercial_blocked_subscription(service, repo):
    repo.institutions_rows[0]["suscripcion"] = "Cancelada"
    result = login(service, repo, "info@test.local")
    assert result.user is None and result.message == core.BLOCKED_SUBSCRIPTION_MESSAGE


@pytest.mark.parametrize("field,value", [("estado", "Solo lectura"), ("estado_pago", "Vencido"),
                                         ("fecha_vencimiento", "2000-01-01")])
def test_commercial_read_only_downgrades_role(service, repo, field, value):
    repo.institutions_rows[0][field] = value
    user = login(service, repo, "info@test.local").user
    assert user["rol"] == "solo_lectura" and user["rol_original"] == "usuario_departamento"
    assert user["modo_solo_lectura_comercial"] is True


def test_superadmin_exempt_from_commercial_state(service, repo):
    for inst in repo.institutions_rows:
        inst["estado"] = "Bloqueada"
    user = login(service, repo, "super@test.local").user
    assert user["rol"] == "superadmin"


# ------------------------------------------------------------------------------------------- sesion
def test_validate_returns_fresh_user_and_advances_activity(service, repo, clock):
    token = session_for(service, repo, "info@test.local")
    clock.advance(60)
    record = service.validate(token)
    assert record.meta["last_activity_mono"] == clock.now


@pytest.mark.parametrize("elapsed,valid", [(30 * 60 - 1, True), (30 * 60, False)])
def test_idle_timeout_boundary(service, repo, clock, elapsed, valid):
    token = session_for(service, repo, "info@test.local")
    clock.advance(elapsed)
    if valid:
        service.validate(token)
    else:
        with pytest.raises(SessionEnded) as exc:
            service.validate(token)
        assert exc.value.reason == core.END_IDLE_TIMEOUT
        assert service.store.get(token) is None


def test_absolute_timeout_even_with_activity(service, repo, clock):
    token = session_for(service, repo, "info@test.local")
    for _ in range(8 * 4):
        clock.advance(15 * 60)
        if clock.now - 1000.0 >= 8 * 3600:
            break
        service.validate(token)
    with pytest.raises(SessionEnded) as exc:
        service.validate(token)
    assert exc.value.reason == core.END_ABSOLUTE_TIMEOUT


@pytest.mark.parametrize("change,reason", [
    (lambda r: r.users.__setitem__(2, {**r.users[2], "estado": "Inactivo"}), core.END_USER_INACTIVE),
    (lambda r: r.set_password("info@test.local", "nueva-clave-segura-123"), core.END_CREDENTIALS_CHANGED),
    (lambda r: r.users.__setitem__(2, {**r.users[2], "rol": "solo_lectura"}), core.END_IDENTITY_CHANGED),
    (lambda r: r.users.__setitem__(2, {**r.users[2], "departamento_id": 2}), core.END_IDENTITY_CHANGED),
    (lambda r: r.users.pop(2), core.END_USER_DELETED),
    (lambda r: r.institutions_rows[0].__setitem__("estado", "Bloqueada"), core.END_COMMERCIAL_BLOCKED),
    (lambda r: r.institutions_rows[0].__setitem__("estado_pago", "Vencido"), core.END_COMMERCIAL_CHANGED),
])
def test_authoritative_change_ends_session(service, repo, change, reason):
    token = session_for(service, repo, "info@test.local")
    change(repo)
    with pytest.raises(SessionEnded) as exc:
        service.validate(token)
    assert exc.value.reason == reason
    assert service.store.get(token) is None


def test_db_failure_does_not_revoke_session(service, repo):
    token = session_for(service, repo, "info@test.local")
    repo.fail = True
    with pytest.raises(AuthUnavailable):
        service.validate(token)
    repo.fail = False
    assert service.validate(token) is not None


def test_logout_invalidates(service, repo):
    token = session_for(service, repo, "info@test.local")
    assert service.logout(token) is True
    with pytest.raises(SessionEnded):
        service.validate(token)


def test_unknown_or_missing_token(service):
    for token in (None, "", "token-inventado"):
        with pytest.raises(SessionEnded):
            service.validate(token)


def test_isolation_between_users(service, repo):
    a = session_for(service, repo, "info@test.local")
    b = session_for(service, repo, "uba@test.local")
    assert a != b
    assert service.validate(a).user["id"] == 3 and service.validate(b).user["id"] == 4
    service.logout(a)
    assert service.validate(b).user["id"] == 4


def test_each_login_issues_a_new_token(service, repo):
    assert session_for(service, repo, "info@test.local") != session_for(service, repo, "info@test.local")


def test_invalid_config_fails_closed(repo, clock):
    from auth.service import AuthService
    bad = AuthService(repo, clock=clock, config_source=lambda n: "999" if n == core.CFG_IDLE else None)
    with pytest.raises(AuthUnavailable):
        bad.login("info@test.local", repo.passwords["info@test.local"])


# ------------------------------------------------------------------------------------------- contexto
def _record(service, repo, email):
    record = service.validate(session_for(service, repo, email))
    service.apply_default_context(record)
    return record


def test_superadmin_default_context_is_first_by_name(service, repo):
    record = _record(service, repo, "super@test.local")
    res = service.resolve_scope(record)
    assert res.institution["nombre"] == "Universidad de Buenos Aires"
    assert res.department["nombre"] == "Departamento de Ciencias Biológicas y Salud"


def test_superadmin_changes_institution_and_department(service, repo):
    record = _record(service, repo, "super@test.local")
    service.set_context(record, 1, None, False)
    res = service.resolve_scope(record)
    assert res.institution["id"] == 1 and res.department["nombre"] == "Departamento de Administración"
    service.set_context(record, 1, 4, False)  # superadmin: tambien departamentos inactivos
    assert service.resolve_scope(record).department["id"] == 4
    with pytest.raises(ContextError):
        service.set_context(record, 1, 5, False)  # departamento de otra institucion
    with pytest.raises(ContextError):
        service.set_context(record, 999, None, False)


def test_coordinator_consolidated_and_active_departments_only(service, repo):
    record = _record(service, repo, "coord@test.local")
    res = service.resolve_scope(record)
    assert res.institution["id"] == 1 and res.department is None and res.reason is None
    opts = service.context_options(record)
    assert [d["id"] for d in opts["departamentos"]] == [2, 1] and opts["permite_consolidado"]
    service.set_context(record, None, 1, False)
    assert service.resolve_scope(record).department["id"] == 1
    for bad in (4, 5):  # inactivo / otra institucion
        with pytest.raises(ContextError):
            service.set_context(record, None, bad, False)
    with pytest.raises(ContextError):
        service.set_context(record, 2, None, True)
    service.set_context(record, None, None, True)
    assert service.resolve_scope(record).department is None


@pytest.mark.parametrize("email", ["info@test.local", "lector@test.local"])
def test_departmental_roles_have_fixed_scope(service, repo, email):
    record = _record(service, repo, email)
    res = service.resolve_scope(record)
    assert res.institution["id"] == 1 and res.department["id"] == 1
    with pytest.raises(ContextError):
        service.set_context(record, None, 2, False)


def test_departmental_user_without_department_has_no_scope(service, repo):
    repo.users[2]["departamento_id"] = None
    record = _record(service, repo, "info@test.local")
    res = service.resolve_scope(record)
    assert res.institution is None and res.reason == "DEPARTMENT_ABSENT"


# ------------------------------------------------------------------------------------------- modulos
def test_visible_modules_per_role():
    keys = lambda role, dep: [m[0] for m in policy.visible_modules(role, dep)]
    assert keys("coordinador_institucional", None) == ["inicio", "consolidado", "materias"]
    assert keys("coordinador_institucional", 1)[1] == "consolidado"
    assert keys("superadmin", 8)[-1] == "administracion_saas" and "consolidado" in keys("superadmin", 8)
    assert "consolidado" not in keys("usuario_departamento", 1)
    assert len(keys("usuario_departamento", 1)) == 14
