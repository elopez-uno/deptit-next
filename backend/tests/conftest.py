"""Fixtures sin base de datos: repositorio falso con la misma interfaz que AuthRepository."""

import secrets
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from auth import core  # noqa: E402
from auth.routes import router  # noqa: E402
from auth.service import AuthService  # noqa: E402


class Clock:
    def __init__(self, start: float = 1000.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class FakeRepo:
    """Datos con la forma real de deptit_next_dev (roles, instituciones, departamentos)."""

    def __init__(self, db_clock: Clock):
        self.db_clock = db_clock
        self.fail = False
        self.calls: list[str] = []
        self.passwords: dict[str, str] = {}
        self.institutions_rows = [
            {"id": 1, "nombre": "Universidad Nacional del Oeste", "estado": "Activa", "slug": "uno",
             "fecha_vencimiento": None, "estado_pago": "Activo", "suscripcion": "Activa"},
            {"id": 2, "nombre": "Universidad de Buenos Aires", "estado": "Activa", "slug": "uba",
             "fecha_vencimiento": "2027-06-26", "estado_pago": "Bonificado", "suscripcion": "Prueba"},
            {"id": 5, "nombre": "Universidad de Hurlingham", "estado": "Activa", "slug": "unahur",
             "fecha_vencimiento": "2027-07-14", "estado_pago": "Activo", "suscripcion": "Activa"},
        ]
        self.departments_rows = [
            {"id": 1, "institucion_id": 1, "nombre": "Departamento de Informática e Ingeniería", "estado": "Activo"},
            {"id": 2, "institucion_id": 1, "nombre": "Departamento de Administración", "estado": "Activo"},
            {"id": 4, "institucion_id": 1, "nombre": "Departamento de Biología", "estado": "Inactivo"},
            {"id": 5, "institucion_id": 2, "nombre": "Departamento de Estructuras", "estado": "Activo"},
            {"id": 8, "institucion_id": 2, "nombre": "Departamento de Ciencias Biológicas y Salud", "estado": "Activo"},
        ]
        self.users = []
        self.add_user(1, "super@test.local", "superadmin", None, None)
        self.add_user(2, "coord@test.local", "coordinador_institucional", 1, None)
        self.add_user(3, "info@test.local", "usuario_departamento", 1, 1)
        self.add_user(4, "uba@test.local", "usuario_departamento", 2, 5)
        self.add_user(6, "admin@test.local", "usuario_departamento", 1, 2)
        self.add_user(7, "lector@test.local", "solo_lectura", 1, 1)
        self.add_user(8, "inactivo@test.local", "usuario_departamento", 1, 1, estado="Inactivo")
        self.throttle: dict[str, dict] = {}

    def add_user(self, uid, email, rol, inst, dep, estado="Activo"):
        password = secrets.token_urlsafe(18)
        salt = secrets.token_hex(16)
        self.passwords[email] = password
        self.users.append({"id": uid, "email": email, "nombre": f"Usuario {uid}", "rol": rol, "estado": estado,
                           "salt": salt, "password_hash": core.hash_password(password, salt),
                           "institucion_id": inst, "departamento_id": dep})

    def set_password(self, email, password):
        user = next(u for u in self.users if u["email"] == email)
        user["salt"] = secrets.token_hex(16)
        user["password_hash"] = core.hash_password(password, user["salt"])
        self.passwords[email] = password

    def update_password_hash(self, user_id, old_hash, new_hash):
        self._check("update_password_hash")
        user = next((u for u in self.users if u["id"] == user_id and u["password_hash"] == old_hash), None)
        if user is not None:
            user["password_hash"] = new_hash
        return user is not None

    def _check(self, name):
        self.calls.append(name)
        if self.fail:
            raise ConnectionError("db down")

    def _joined(self, u):
        inst = next((i for i in self.institutions_rows if i["id"] == u["institucion_id"]), None)
        dep = next((d for d in self.departments_rows if d["id"] == u["departamento_id"]), None)
        row = dict(u)
        row.update({"institucion_nombre": inst and inst["nombre"], "institucion_slug": inst and inst["slug"],
                    "institucion_estado": inst and inst["estado"],
                    "fecha_vencimiento": inst and inst["fecha_vencimiento"],
                    "estado_pago": inst and inst["estado_pago"], "suscripcion": inst and inst["suscripcion"],
                    "departamento_nombre": dep and dep["nombre"], "departamento_slug": dep and str(dep["id"])})
        return row

    def user_by_id(self, user_id):
        self._check("user_by_id")
        return [self._joined(u) for u in self.users if u["id"] == user_id][:2]

    def users_by_email(self, email):
        self._check("users_by_email")
        return [self._joined(u) for u in sorted(self.users, key=lambda u: u["id"])
                if u["email"].lower() == core.normalize_email(email)][:2]

    def institutions(self):
        self._check("institutions")
        return [{"id": i["id"], "nombre": i["nombre"], "estado": i["estado"]}
                for i in sorted(self.institutions_rows, key=lambda i: i["nombre"].casefold())]

    def departments(self, institution_id, only_active):
        self._check("departments")
        rows = [d for d in self.departments_rows if d["institucion_id"] == institution_id
                and (not only_active or d["estado"] == "Activo")]
        return sorted(rows, key=lambda d: d["nombre"].casefold())

    def institution(self, institution_id):
        self._check("institution")
        return next(({"id": i["id"], "nombre": i["nombre"], "estado": i["estado"]}
                     for i in self.institutions_rows if i["id"] == institution_id), None)

    def department(self, department_id):
        self._check("department")
        return next((dict(d) for d in self.departments_rows if d["id"] == department_id), None)

    # throttle con la misma semantica que el upsert SQL (reloj "de la base")
    def lock_state(self, key):
        self._check("lock_state")
        row = self.throttle.get(key)
        return bool(row and row["locked_until"] is not None and row["locked_until"] > self.db_clock())

    def register_failure(self, key, cfg):
        self._check("register_failure")
        now = self.db_clock()
        row = self.throttle.get(key)
        if row is None:
            row = {"failures": 1, "window": now,
                   "locked_until": now + cfg.lockout_seconds if 1 >= cfg.max_failed_attempts else None}
        else:
            reset = row["window"] <= now - cfg.failure_window_seconds or (
                row["locked_until"] is not None and row["locked_until"] <= now)
            failures = 1 if reset else row["failures"] + 1
            row = {"failures": failures, "window": now if reset else row["window"],
                   "locked_until": now + cfg.lockout_seconds if failures >= cfg.max_failed_attempts else None}
        row["updated"] = now
        self.throttle[key] = row
        return row["failures"], row["locked_until"]

    def reset(self, key):
        self._check("reset")
        self.throttle.pop(key, None)

    def purge(self, older_than_seconds):
        self._check("purge")


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def repo(clock):
    return FakeRepo(clock)


@pytest.fixture
def service(repo, clock):
    return AuthService(repo, clock=clock, config_source=lambda name: None)


@pytest.fixture
def app(service):
    application = FastAPI()
    application.include_router(router)
    application.state.auth = service
    return application


@pytest.fixture
def client(app):
    from fastapi.testclient import TestClient

    return TestClient(app, base_url="http://localhost")
