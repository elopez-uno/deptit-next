"""Genera la contrasena de deptit_next_app, la guarda SOLO en backend/.env y produce
el SQL de fase 2 con el verificador SCRAM-SHA-256 (nunca la contrasena en texto plano).
No imprime secretos. Se niega a sobrescribir un .env existente.

6A-B1: el SQL generado contiene material de credencial (verificador SCRAM): se escribe FUERA del repositorio
(directorio temporal privado del usuario, o el indicado como primer argumento) y debe borrarse tras aplicarlo.
El .env usa el formato DEPTIT_DB_* (ver backend/.env.example)."""

import base64
import hashlib
import hmac
import secrets
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT / "backend" / ".env"
TEMPLATE = ROOT / "migration" / "db_setup" / "02_create_role_and_grants.template.sql"
OUTPUT_NAME = "02_create_role_and_grants.generated.sql"
ITERATIONS = 4096


def scram_sha256_verifier(password: str) -> str:
    salt = secrets.token_bytes(16)
    salted = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    client_key = hmac.new(salted, b"Client Key", hashlib.sha256).digest()
    stored_key = hashlib.sha256(client_key).digest()
    server_key = hmac.new(salted, b"Server Key", hashlib.sha256).digest()
    b64 = lambda b: base64.b64encode(b).decode("ascii")
    return f"SCRAM-SHA-256${ITERATIONS}:{b64(salt)}${b64(stored_key)}:{b64(server_key)}"


def main() -> int:
    if ENV_PATH.exists():
        print(f"ABORT: {ENV_PATH} ya existe; no se sobrescribe.")
        return 1
    out_dir = (Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp(prefix="deptit_role_sql_"))).resolve()
    if out_dir == ROOT or ROOT in out_dir.parents:
        print("ABORT: el SQL generado (material de credencial) no puede quedar dentro del repositorio")
        return 1
    # 48 bytes aleatorios -> 64 caracteres URL-safe (384 bits); no requiere escape en la URL.
    password = secrets.token_urlsafe(48)
    ENV_PATH.write_text(
        "# DEPTIT NEXT backend - SECRETO. No versionar ni compartir.\n"
        "DEPTIT_ENTORNO=desarrollo\n"
        "DEPTIT_DB_HOST=127.0.0.1\nDEPTIT_DB_PORT=5432\nDEPTIT_DB_NAME=deptit_next_dev\n"
        f"DEPTIT_DB_USER=deptit_next_app\nDEPTIT_DB_PASSWORD={password}\nDEPTIT_DB_SSLMODE=prefer\n"
        "DEPTIT_EXPECTED_DATABASE=deptit_next_dev\n"
        "DEPTIT_EXPECTED_DB_USER=deptit_next_app\n",
        encoding="utf-8",
    )
    OUTPUT = out_dir / OUTPUT_NAME
    sql = TEMPLATE.read_text(encoding="utf-8").replace("__SCRAM_VERIFIER__", scram_sha256_verifier(password))
    OUTPUT.write_text(sql, encoding="utf-8")
    print(f"OK: .env escrito ({ENV_PATH}); SQL generado ({OUTPUT}); longitud contrasena={len(password)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
