"""6A-B3: genera la configuracion y las credenciales de la PREPRODUCCION LOCAL.

* Contraseñas nuevas (``secrets.token_urlsafe(48)``) para ``deptit_next_preprod_{owner,app,backup}``.
* ``C:\\DEPTIT_NEXT\\var\\preprod\\config\\`` (fuera de Git y de la release; ACL solo del usuario actual):
  - ``backend.env``  : configuracion COMPLETA del backend de preproduccion (la app nunca lee ``backend/.env``);
  - ``ops.env``      : roles operativos (backup, owner) + rol de restore drill (copiado de ``backend/.env.ops``);
  - ``frontend.env`` : variables server-only de ``next start``.
* El SQL con los verificadores SCRAM-SHA-256 se escribe FUERA del repositorio (temporal privado); se aplica con
  ``run_as_postgres.ps1`` y se borra despues.  No imprime secretos.  No sobrescribe nada que ya exista.
"""

import os
import secrets
import subprocess
import sys
import tempfile
from pathlib import Path

from generate_role_secret import scram_sha256_verifier

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "migration" / "db_setup" / "04_create_preprod.template.sql"
OUTPUT_NAME = "04_create_preprod.generated.sql"
DEV_OPS_ENV = ROOT / "backend" / ".env.ops"

VAR = ROOT / "var" / "preprod"
CONFIG = VAR / "config"
DIRS = ("config", "documents", "backups", "backups/documents", "backups/sets", "logs", "run", "caddy", "app", "tmp")

# Puertos exclusivos de preproduccion (desarrollo usa 8001 / 3000); el navegador solo habla con el proxy TLS.
HOST = "deptit-preprod.localhost"
PUERTO_PROXY, PUERTO_FRONTEND, PUERTO_BACKEND = 8443, 3100, 8101


def _restringir(path: Path) -> None:
    """ACL: solo el usuario actual (sin herencia).  Windows; en otro SO, 0700/0600."""
    if os.name != "nt":
        path.chmod(0o700 if path.is_dir() else 0o600)
        return
    usuario = f"{os.environ['USERDOMAIN']}\\{os.environ['USERNAME']}"
    permiso = "(OI)(CI)F" if path.is_dir() else "F"
    subprocess.run(["icacls", str(path), "/inheritance:r", "/grant:r", f"{usuario}:{permiso}"], check=True,
                   capture_output=True)


def _dev_restore() -> tuple[str, str]:
    vals = {}
    for linea in DEV_OPS_ENV.read_text(encoding="utf-8").splitlines():
        if "=" in linea and not linea.lstrip().startswith("#"):
            k, v = linea.split("=", 1)
            vals[k.strip()] = v.strip()
    return vals["DEPTIT_RESTORE_DB_USER"], vals["DEPTIT_RESTORE_DB_PASSWORD"]


def backend_env(app_password: str) -> str:
    return f"""# DEPTIT NEXT - backend de PREPRODUCCION LOCAL (6A-B3). SECRETO: no versionar ni compartir.
# Lo carga ops\\deptit-ops.ps1 -Entorno preproduccion en el proceso del backend (la app no lee backend/.env fuera de
# desarrollo).  Especificacion de cada variable: backend/.env.example y docs/ETAPA6_6AB3_LOCAL_PILOT.md.
DEPTIT_ENTORNO=preproduccion
DEPTIT_TIMEZONE=America/Argentina/Buenos_Aires
DEPTIT_DB_TIMEZONE=UTC
DEPTIT_BACKEND_HOST=127.0.0.1
DEPTIT_BACKEND_PORT={PUERTO_BACKEND}
DEPTIT_DB_HOST=127.0.0.1
DEPTIT_DB_PORT=5432
DEPTIT_DB_NAME=deptit_next_preprod
DEPTIT_DB_USER=deptit_next_preprod_app
DEPTIT_DB_PASSWORD={app_password}
# PostgreSQL local con ssl=off (cluster compartido con PROD: no se reconfigura); loopback -> admitido por B1.
DEPTIT_DB_SSLMODE=disable
DEPTIT_EXPECTED_DATABASE=deptit_next_preprod
DEPTIT_EXPECTED_DB_USER=deptit_next_preprod_app
DEPTIT_SESSION_COOKIE_SECURE=1
DEPTIT_API_DOCS=0
DEPTIT_TRUSTED_FRONTEND_IPS=127.0.0.1,::1
DEPTIT_DOCUMENTS_DIR={VAR / "documents"}
# El storage y el codigo de desarrollo nunca pueden ser raiz documental ni de backups de preproduccion.
DEPTIT_FORBIDDEN_DIRS={ROOT / "storage"};{ROOT / "backend"};{ROOT / "frontend"}
DEPTIT_BACKUP_GATE_CREAR_PERIODO=activo
DEPTIT_BACKUP_DIR={VAR / "backups"}
DEPTIT_CRITICAL_BACKUP_MAX_AGE_HOURS=24
"""


def ops_env(owner: str, backup: str, restore_user: str, restore_password: str) -> str:
    return f"""# DEPTIT NEXT - roles OPERATIVOS de PREPRODUCCION LOCAL (6A-B3). SECRETO: no versionar ni compartir.
# Solo las herramientas (python -m operacion); la aplicacion nunca carga este archivo.
DEPTIT_BACKUP_DB_USER=deptit_next_preprod_backup
DEPTIT_BACKUP_DB_PASSWORD={backup}
DEPTIT_OWNER_DB_USER=deptit_next_preprod_owner
DEPTIT_OWNER_DB_PASSWORD={owner}
# Rol de restore drill del cluster (CREATEDB; solo bases deptit_next_restore_test_*; sin acceso a preprod ni a dev).
DEPTIT_RESTORE_DB_USER={restore_user}
DEPTIT_RESTORE_DB_PASSWORD={restore_password}
DEPTIT_PG_BIN_DIR=C:\\Program Files\\PostgreSQL\\18\\bin
DEPTIT_BACKUP_RETENTION_DAYS=14
"""


def frontend_env() -> str:
    return f"""# DEPTIT NEXT - frontend (next start) de PREPRODUCCION LOCAL (6A-B3).  Sin secretos; todas server-only.
NODE_ENV=production
HOSTNAME=127.0.0.1
PORT={PUERTO_FRONTEND}
DEPTIT_BACKEND_URL=http://127.0.0.1:{PUERTO_BACKEND}
# Un proxy confiable delante (Caddy local): toma la entrada que agrega el proxy en X-Forwarded-For.
DEPTIT_TRUSTED_PROXY_HOPS=1
NEXT_TELEMETRY_DISABLED=1
"""


def main() -> int:
    archivos = {CONFIG / "backend.env", CONFIG / "ops.env", CONFIG / "frontend.env"}
    if existentes := [p.name for p in archivos if p.exists()]:
        print(f"ABORT: ya existen {existentes}; no se sobrescribe nada.")
        return 1
    out_dir = (Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp(prefix="deptit_preprod_sql_"))).resolve()
    if out_dir == ROOT or ROOT in out_dir.parents:
        print("ABORT: el SQL generado (material de credencial) no puede quedar dentro del repositorio")
        return 1
    for d in DIRS:
        (VAR / d).mkdir(parents=True, exist_ok=True)
    _restringir(CONFIG)
    owner, app, backup = (secrets.token_urlsafe(48) for _ in range(3))
    restore_user, restore_password = _dev_restore()
    for path, texto in ((CONFIG / "backend.env", backend_env(app)),
                        (CONFIG / "ops.env", ops_env(owner, backup, restore_user, restore_password)),
                        (CONFIG / "frontend.env", frontend_env())):
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(texto)
        _restringir(path)
    sql = (TEMPLATE.read_text(encoding="utf-8")
           .replace("__OWNER_VERIFIER__", scram_sha256_verifier(owner))
           .replace("__APP_VERIFIER__", scram_sha256_verifier(app))
           .replace("__BACKUP_VERIFIER__", scram_sha256_verifier(backup)))
    output = out_dir / OUTPUT_NAME
    output.write_text(sql, encoding="utf-8")
    print(f"OK: configuracion de preproduccion escrita en {CONFIG} (ACL restringida); SQL generado: {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
