"""Pruebas negativas de la guarda fail-closed. NO abren ninguna conexion:
ConnectionPool y psycopg.connect se reemplazan por centinelas que registran cualquier intento."""

import os
import sys

import psycopg

import db

ATTEMPTS: list[str] = []


class SentinelPool:
    def __init__(self, conninfo, *args, **kwargs):
        ATTEMPTS.append("ConnectionPool")
        raise AssertionError("intento de conexion no permitido en prueba negativa")


def sentinel_connect(*args, **kwargs):
    ATTEMPTS.append("psycopg.connect")
    raise AssertionError("intento de conexion no permitido en prueba negativa")


db.ConnectionPool = SentinelPool
psycopg.connect = sentinel_connect

GOOD_URL = "postgresql://deptit_next_app:placeholder@127.0.0.1:5432/deptit_next_dev"

PRECONNECT_CASES = [
    ("URL apunta a deptit (produccion)",
     {"DATABASE_URL": "postgresql://deptit_next_app:placeholder@127.0.0.1:5432/deptit"}),
    ("URL apunta a deptit con usuario productivo deptit_app",
     {"DATABASE_URL": "postgresql://deptit_app:placeholder@127.0.0.1:5432/deptit"}),
    ("URL con usuario postgres sobre deptit_next_dev",
     {"DATABASE_URL": "postgresql://postgres:placeholder@127.0.0.1:5432/deptit_next_dev"}),
    ("URL sin nombre de base (libpq usaria un default)",
     {"DATABASE_URL": "postgresql://deptit_next_app:placeholder@127.0.0.1:5432"}),
    ("URL con service= (redireccion via pg_service.conf)",
     {"DATABASE_URL": "service=deptit dbname=deptit_next_dev user=deptit_next_app"}),
    ("Base esperada redefinida a deptit en configuracion",
     {"DATABASE_URL": "postgresql://deptit_next_app:placeholder@127.0.0.1:5432/deptit",
      "DEPTIT_EXPECTED_DATABASE": "deptit"}),
    ("Usuario esperado redefinido a deptit_app",
     {"DATABASE_URL": GOOD_URL, "DEPTIT_EXPECTED_DB_USER": "deptit_app"}),
    ("DATABASE_URL vacia", {"DATABASE_URL": ""}),
]


class FakeConn:
    def __init__(self, database, user):
        self.row = (database, user)

    def execute(self, sql):
        return self

    def fetchone(self):
        return self.row


POSTCONNECT_CASES = [
    ("Servidor reporta current_database()=deptit", FakeConn("deptit", "deptit_next_app")),
    ("Servidor reporta current_user=postgres", FakeConn("deptit_next_dev", "postgres")),
    ("Servidor reporta deptit / deptit_app", FakeConn("deptit", "deptit_app")),
    ("Coincidencia no exacta (mayusculas)", FakeConn("DEPTIT_NEXT_DEV", "deptit_next_app")),
]


def with_env(overrides):
    base = {"DATABASE_URL": GOOD_URL, "DEPTIT_EXPECTED_DATABASE": "deptit_next_dev",
            "DEPTIT_EXPECTED_DB_USER": "deptit_next_app"}
    base.update(overrides)
    os.environ.update(base)


def main() -> int:
    failures = 0
    # load_dotenv(override=False) no pisa variables ya definidas: las de la prueba prevalecen.
    for name, overrides in PRECONNECT_CASES:
        with_env(overrides)
        before = len(ATTEMPTS)
        try:
            db.create_pool()
            print(f"FAIL  [pre]  {name}: el backend habria arrancado")
            failures += 1
        except db.DatabaseGuardError as exc:
            ok = len(ATTEMPTS) == before
            failures += not ok
            print(f"{'PASS' if ok else 'FAIL'}  [pre]  {name}: RECHAZADO sin conectar -> {exc}")
    for name, conn in POSTCONNECT_CASES:
        try:
            db.verify_identity(conn)
            print(f"FAIL  [post] {name}: aceptado")
            failures += 1
        except db.DatabaseGuardError as exc:
            print(f"PASS  [post] {name}: RECHAZADO -> {exc}")
    print(f"Intentos de conexion registrados: {len(ATTEMPTS)}")
    print(f"RESULTADO: {'OK' if failures == 0 and not ATTEMPTS else 'FALLAS=' + str(failures)}")
    return 1 if failures or ATTEMPTS else 0


if __name__ == "__main__":
    sys.exit(main())
