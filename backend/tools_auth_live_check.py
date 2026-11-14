"""Pruebas reales de autenticacion contra deptit_next_dev (via Next.js :3001 y FastAPI :8001).

No usa contrasenas reales: solo rechazos, bloqueo con un email inexistente, CSRF y sesiones falsas.
Cada cuenta real recibe a lo sumo UN intento fallido (lejos del umbral de bloqueo).  Al final borra las filas de
auth_login_throttle creadas por esta prueba (mismo DELETE que el reset certificado).  No imprime emails ni secretos.
"""

import json
import secrets
import sys
import time
import urllib.error
import urllib.request

import psycopg

import db
from auth import core

NEXT = "http://localhost:3001"
API = "http://127.0.0.1:8001"
ORIGIN = {"Origin": NEXT, "Sec-Fetch-Site": "same-origin"}
GENERIC = core.GENERIC_LOGIN_MESSAGE
FORBIDDEN = ("salt", "password_hash", "postgresql://", "DATABASE_URL")
results: list[tuple[str, bool, str]] = []


def http(method, url, body=None, headers=None, cookie=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    if cookie:
        req.add_header("Cookie", cookie)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode(), r.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(), e.headers


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")


def clean(text):
    return not any(w in text for w in FORBIDDEN)


def main() -> int:
    settings = db.load_settings()
    db.check_config(settings)
    with psycopg.connect(settings["database_url"], connect_timeout=5) as conn:
        conn.read_only = True
        db.verify_identity(conn)
        emails = [r[0] for r in conn.execute("SELECT email FROM app_usuarios ORDER BY id").fetchall()]
        before = conn.execute("SELECT count(*) FROM auth_login_throttle").fetchone()[0]
    fake = f"no-existe-{secrets.token_hex(6)}@deptit-next-test.invalid"
    touched = {core.subject_key(fake)}

    # 1. sin sesion
    for base, path in ((NEXT, "/api/auth/me"), (API, "/auth/me")):
        s, b, _ = http("GET", base + path)
        check(f"/auth/me sin sesion ({base})", s == 401 and "NO_SESSION" in b, f"status={s}")
    s, b, _ = http("GET", NEXT + "/api/auth/me", cookie="deptit_session=" + secrets.token_urlsafe(32))
    check("cookie de sesion inventada", s == 401, f"status={s}")

    # 2. rechazos uniformes (una vez por cuenta real, contrasena aleatoria)
    timings = {}
    for label, email in (("usuario inexistente", fake), ("contraseña incorrecta (cuenta real id=3)", emails[2]),
                         ("contraseña incorrecta (superadmin id=1)", emails[0])):
        touched.add(core.subject_key(email))
        t0 = time.perf_counter()
        s, b, h = http("POST", NEXT + "/api/auth/login", {"email": email, "password": secrets.token_urlsafe(16)},
                       ORIGIN)
        timings[label] = time.perf_counter() - t0
        msg = json.loads(b)["error"]["message"]
        check(f"login rechazado: {label}", s == 401 and msg == GENERIC and clean(b)
              and "deptit_session=" not in (h.get("Set-Cookie") or "").replace('deptit_session=""', ""),
              f"status={s} t={timings[label]:.3f}s")
    s, b, _ = http("POST", NEXT + "/api/auth/login", {"email": "", "password": ""}, ORIGIN)
    check("login vacio", s == 401 and json.loads(b)["error"]["message"] == GENERIC, f"status={s}")

    # 3. bloqueo por intentos (email inexistente; ya tiene 1 fallo)
    for _ in range(4):
        http("POST", NEXT + "/api/auth/login", {"email": fake, "password": "x" * 12}, ORIGIN)
    with psycopg.connect(settings["database_url"], connect_timeout=5) as conn:
        conn.read_only = True
        row = conn.execute("SELECT failures, locked_until_epoch > EXTRACT(EPOCH FROM now()) FROM auth_login_throttle "
                           "WHERE subject_key = %s", [core.subject_key(fake)]).fetchone()
    check("bloqueo tras 5 fallos (clave = SHA-256, sin email en la tabla)", row == (5, True), f"row={row}")
    s, b, _ = http("POST", NEXT + "/api/auth/login", {"email": fake, "password": "x" * 12}, ORIGIN)
    check("intento durante bloqueo: mismo mensaje generico", s == 401 and json.loads(b)["error"]["message"] == GENERIC)

    # 4. CSRF / origen
    s, _, _ = http("POST", NEXT + "/api/auth/login", {"email": fake, "password": "x"},
                   {"Origin": "http://evil.example", "Sec-Fetch-Site": "cross-site"})
    check("proxy Next rechaza origen ajeno", s == 403, f"status={s}")
    s, _, _ = http("POST", NEXT + "/api/auth/login", {"email": fake, "password": "x"})
    check("proxy Next rechaza POST sin Origin", s == 403, f"status={s}")
    s, _, _ = http("POST", API + "/auth/login", {"email": fake, "password": "x"})
    check("FastAPI rechaza POST sin cabecera X-DEPTIT-Request", s == 403, f"status={s}")
    s, _, _ = http("DELETE", NEXT + "/api/auth/me")
    check("metodo no permitido en proxy", s in (404, 405), f"status={s}")
    for route in ("health", "system/info", "me/../login"):
        s, b, _ = http("GET", NEXT + "/api/auth/" + route)
        check(f"proxy no expone rutas fuera de la allowlist ({route})", s in (401, 404) and "deptit_next" not in b,
              f"status={s}")

    # 5. logout sin sesion es idempotente
    s, _, h = http("POST", NEXT + "/api/auth/logout", None, ORIGIN)
    check("logout sin sesion -> 204 y cookie expirada", s == 204 and "Max-Age=0" in (h.get("Set-Cookie") or ""),
          f"status={s}")
    s, _, _ = http("PUT", NEXT + "/api/auth/context", {"departamento_id": 1}, ORIGIN)
    check("cambiar contexto sin sesion", s == 401, f"status={s}")

    # 6. backend sigue exclusivamente en deptit_next_dev / deptit_next_app
    s, b, _ = http("GET", API + "/health")
    h = json.loads(b)
    check("health: deptit_next_dev / deptit_next_app",
          h.get("database") == "deptit_next_dev" and h.get("db_user") == "deptit_next_app", b)

    # 7. limpieza de filas de throttle creadas por esta prueba
    with psycopg.connect(settings["database_url"], connect_timeout=5) as conn:
        db.verify_identity(conn)
        deleted = conn.execute("DELETE FROM auth_login_throttle WHERE subject_key = ANY(%s)",
                               [sorted(touched)]).rowcount
        after = conn.execute("SELECT count(*) FROM auth_login_throttle").fetchone()[0]
    check("limpieza throttle (filas de la prueba)", after == before, f"borradas={deleted} antes={before} despues={after}")

    failed = [r for r in results if not r[1]]
    print(f"\nRESULTADO: {len(results) - len(failed)}/{len(results)} PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
