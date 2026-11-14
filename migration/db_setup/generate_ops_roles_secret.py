"""6A-B2: genera las contrasenas de los roles operativos de desarrollo (deptit_next_backup, deptit_next_restore), las
guarda SOLO en backend/.env.ops (ignorado por Git, nunca lo lee la aplicacion) y produce el SQL con los verificadores
SCRAM-SHA-256 FUERA del repositorio (directorio temporal privado del usuario, o el indicado como primer argumento).
El SQL se aplica con ``run_as_postgres.ps1`` y se borra despues.  No imprime secretos.  No sobrescribe .env.ops."""

import secrets
import sys
import tempfile
from pathlib import Path

from generate_role_secret import scram_sha256_verifier

ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT / "backend" / ".env.ops"
TEMPLATE = ROOT / "migration" / "db_setup" / "03_create_ops_roles.template.sql"
OUTPUT_NAME = "03_create_ops_roles.generated.sql"


def main() -> int:
    if ENV_PATH.exists():
        print(f"ABORT: {ENV_PATH} ya existe; no se sobrescribe.")
        return 1
    out_dir = (Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp(prefix="deptit_ops_sql_"))).resolve()
    if out_dir == ROOT or ROOT in out_dir.parents:
        print("ABORT: el SQL generado (material de credencial) no puede quedar dentro del repositorio")
        return 1
    backup, restore = secrets.token_urlsafe(48), secrets.token_urlsafe(48)
    ENV_PATH.write_text(
        "# DEPTIT NEXT - roles OPERATIVOS de desarrollo (backup / restore drill). SECRETO: no versionar ni compartir.\n"
        "# Lo leen solo las herramientas de backend/operacion; la aplicacion nunca carga este archivo.\n"
        f"DEPTIT_BACKUP_DB_USER=deptit_next_backup\nDEPTIT_BACKUP_DB_PASSWORD={backup}\n"
        f"DEPTIT_RESTORE_DB_USER=deptit_next_restore\nDEPTIT_RESTORE_DB_PASSWORD={restore}\n",
        encoding="utf-8",
    )
    sql = (TEMPLATE.read_text(encoding="utf-8")
           .replace("__BACKUP_VERIFIER__", scram_sha256_verifier(backup))
           .replace("__RESTORE_VERIFIER__", scram_sha256_verifier(restore)))
    output = out_dir / OUTPUT_NAME
    output.write_text(sql, encoding="utf-8")
    print(f"OK: .env.ops escrito ({ENV_PATH}); SQL generado ({output})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
