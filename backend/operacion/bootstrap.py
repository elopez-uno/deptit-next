"""Bootstrap del PRIMER superadmin de una base NUEVA (6A-B2).  Porta el procedimiento certificado B11
(``deptit_refactor/operations/provisioning.py`` + reglas B10 de ``security/credentials.py``) al hashing actual de B1.

BOOTSTRAP INICIAL (esta herramienta) vs ADMINISTRADORES POSTERIORES (Administracion SaaS, desde la aplicacion):
el bootstrap solo existe para que una base recien creada tenga UNA cuenta con la que entrar.  Si ya hay cualquier
superadmin activo (o ese email), no hace nada y lo dice (``ALREADY_PROVISIONED``): nunca crea un segundo superadmin
"inicial" en silencio.  Todo administrador posterior se crea desde la aplicacion, con su auditoria B12H.

* Sin credenciales por defecto: la contraseña se pide por ``getpass`` (dos veces) o se lee de stdin (gestor de
  secretos); nunca por argumento, variable de entorno, SQL, log ni reporte.
* Reglas B10: email valido, no es una cuenta semilla heredada; contraseña >= 12, no publica conocida, distinta del
  email.  Hash B1: ``pbkdf2_sha256$600000$<hex>`` (``auth.core.hash_password_actual``) con salt ``token_hex(16)``.
* Una transaccion: ``LOCK TABLE app_usuarios IN SHARE ROW EXCLUSIVE MODE`` -> lee cuentas -> INSERT -> verifica la fila
  (rol, estado y ``verify_password``) -> COMMIT.  Cualquier error -> ROLLBACK.
* Destino: la base del entorno configurado (rol de la app) o, solo en desarrollo, una base de prueba
  ``deptit_next_restore_test_*`` (rol de restore).  ``deptit`` y cualquier otra base: rechazadas.
"""
from __future__ import annotations

import datetime as _dt
import secrets
from typing import Any, Callable, List, Optional

from auth import core
from saas.textos import LEGACY_SEED_EMAILS

from .config import RESTORE_TEST_RE

MIN_PASSWORD_LENGTH = 12
INSERT_SQL = ("INSERT INTO app_usuarios (institucion_id, departamento_id, nombre, email, rol, salt, password_hash, "
              "estado, fecha_alta) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id")


def es_semilla(email: Any) -> bool:
    return str(email or "").strip().casefold() in LEGACY_SEED_EMAILS


def problemas_solicitud(email: str, password: str, name: str) -> List[str]:
    """Reglas B10 (``load_bootstrap_config``); los mensajes nunca contienen la contraseña."""
    p = []
    email = str(email or "").strip()
    if not email or "@" not in email or any(c.isspace() for c in email) or len(email) > 254:
        p.append("email invalido")
    elif es_semilla(email):
        p.append("el email no puede ser una cuenta de prueba heredada")
    if not password:
        p.append("falta la contraseña")
    else:
        if len(password) < MIN_PASSWORD_LENGTH:
            p.append(f"la contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres")
        if core.is_public_default_password(password) or core.is_public_default_password(password.strip()):
            p.append("la contraseña es una credencial publica conocida")
        if email and password.casefold() == email.casefold():
            p.append("la contraseña no puede ser igual al email")
    if not str(name or "").strip() or len(str(name)) > 200:
        p.append("nombre invalido")
    return p


def hashear(password: str) -> tuple[str, str]:
    salt = secrets.token_hex(16)
    return salt, core.hash_password_actual(password, salt)


def destino_problema(base_real: str, *, esperada: str, entorno: str) -> Optional[str]:
    if base_real.lower() in {"deptit", "postgres", "template0", "template1"}:
        return f"la base {base_real!r} esta prohibida"
    if base_real == esperada:
        return None
    if entorno == "desarrollo" and RESTORE_TEST_RE.match(base_real):
        return None
    return f"la base {base_real!r} no es la base del entorno ({esperada!r})"


def provisionar(conn, email: str, password: str, name: str = "Superadmin", *, esperada: str, entorno: str,
                execute: bool = False, today: Optional[str] = None, hasher: Callable = hashear) -> dict:
    email, name = str(email or "").strip(), str(name or "Superadmin").strip()
    if problemas := problemas_solicitud(email, password, name):
        return {"result": "FAIL", "code": "INVALID_REQUEST", "detail": "; ".join(problemas)}
    cuenta = {"email": email, "name": name, "rol": "superadmin"}
    if not execute:
        return {"result": "PLANNED", "code": "DRY_RUN", "detail": "solicitud valida; sin --execute no se conecta",
                "account": cuenta}
    today = today or _dt.date.today().isoformat()
    try:
        base = conn.execute("SELECT current_database()").fetchone()[0]
        if (motivo := destino_problema(base, esperada=esperada, entorno=entorno)) is not None:
            conn.rollback()
            return {"result": "FAIL", "code": "TARGET_REFUSED", "detail": motivo}
        conn.execute("LOCK TABLE app_usuarios IN SHARE ROW EXCLUSIVE MODE")
        filas = conn.execute("SELECT email, rol, estado FROM app_usuarios").fetchall()
        emails = {str(r[0] or "").strip().casefold() for r in filas}
        activos = [r for r in filas if str(r[1] or "").strip().casefold() == "superadmin"
                   and str(r[2] or "").strip() == "Activo"]
        if email.casefold() in emails or activos:
            conn.rollback()
            return {"result": "FAIL", "code": "ALREADY_PROVISIONED",
                    "detail": "ya existe ese email o un superadmin activo: no se modifico nada (los administradores "
                              "posteriores se crean desde Administracion SaaS)",
                    "superadmins_activos": len(activos)}
        salt, digest = hasher(password)
        nuevo_id = conn.execute(INSERT_SQL, (None, None, name, email, "superadmin", salt, digest, "Activo",
                                             today)).fetchone()[0]
        fila = conn.execute("SELECT rol, estado, salt, password_hash FROM app_usuarios WHERE id = %s",
                            (nuevo_id,)).fetchone()
        if not (fila and fila[0] == "superadmin" and fila[1] == "Activo"
                and str(fila[3]).startswith(f"{core.HASH_PREFIX}{core.PBKDF2_ITERATIONS_ACTUAL}$")
                and core.verify_password(password, fila[2], fila[3])):
            conn.rollback()
            return {"result": "FAIL", "code": "VERIFY_FAILED", "detail": "la cuenta creada no verifica: ROLLBACK"}
        conn.commit()
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        return {"result": "FAIL", "code": "DB_ERROR", "detail": type(exc).__name__}
    return {"result": "PASS", "code": "PROVISIONED", "account": {**cuenta, "id": int(nuevo_id)}, "database": base,
            "hash_format": f"{core.HASH_PREFIX}{core.PBKDF2_ITERATIONS_ACTUAL}"}


def auditar_semillas(conn) -> dict:
    """Cuentas semilla heredadas presentes en una base (solo lectura; los emails son identificadores publicos)."""
    filas = conn.execute("SELECT lower(trim(email)), estado FROM app_usuarios WHERE lower(trim(email)) = ANY(%s)",
                         (list(LEGACY_SEED_EMAILS),)).fetchall()
    activas = sorted(r[0] for r in filas if str(r[1] or "").strip() == "Activo")
    return {"semillas_presentes": sorted(r[0] for r in filas), "semillas_activas": activas,
            "ok_para_produccion": not activas}
