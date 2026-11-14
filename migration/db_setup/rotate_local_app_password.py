"""Rotacion de la contraseña LOCAL de ``deptit_next_app`` (solo desarrollo, Etapa 6A-B1).

* Solo opera con ``DEPTIT_ENTORNO`` ausente/``desarrollo``, base ``deptit_next_dev`` y rol ``deptit_next_app``
  (lee la conexion actual de ``backend/.env``); cualquier otra cosa -> ABORT sin conectar.
* El propio rol cambia su contraseña (``ALTER ROLE ... PASSWORD``) con un verificador SCRAM-SHA-256 calculado aca: el
  texto plano nunca viaja en SQL ni queda en logs del servidor.  No toca otros roles, bases ni ``pg_hba.conf``.
* La contraseña nueva se escribe solo en ``backend/.env`` (ignorado; nunca se versiona), en formato ``DEPTIT_DB_*``,
  mediante un temporal + reemplazo atomico.  Antes de reemplazar verifica que la nueva conecta y la vieja no.
* No imprime secretos (ni contraseña ni verificador).
"""

from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path

import psycopg
from dotenv import dotenv_values
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_role_secret import scram_sha256_verifier  # noqa: E402

ENV_PATH = Path(__file__).resolve().parents[2] / "backend" / ".env"
DB, ROLE = "deptit_next_dev", "deptit_next_app"


def _params(values: dict) -> dict:
    if values.get("DATABASE_URL"):
        p = conninfo_to_dict(values["DATABASE_URL"])
        return {"host": p.get("host") or "127.0.0.1", "port": str(p.get("port") or "5432"),
                "dbname": p.get("dbname"), "user": p.get("user"), "password": p.get("password"),
                "sslmode": p.get("sslmode") or "prefer"}
    return {"host": values.get("DEPTIT_DB_HOST") or "127.0.0.1", "port": values.get("DEPTIT_DB_PORT") or "5432",
            "dbname": values.get("DEPTIT_DB_NAME"), "user": values.get("DEPTIT_DB_USER"),
            "password": values.get("DEPTIT_DB_PASSWORD"), "sslmode": values.get("DEPTIT_DB_SSLMODE") or "prefer"}


def _connect(p: dict, password: str) -> psycopg.Connection:
    return psycopg.connect(make_conninfo(host=p["host"], port=p["port"], dbname=p["dbname"], user=p["user"],
                                         password=password, sslmode=p["sslmode"]),
                           connect_timeout=5, application_name="deptit_next_rotation")


def _publicar(tmp: Path) -> None:
    """Reemplazo atomico; si el ACL de ``.env`` no permite borrarlo (solo lectura/escritura, como en esta PC), se
    reescribe en el lugar para conservar ese ACL restringido.  Despues se elimina el temporal."""
    try:
        os.replace(tmp, ENV_PATH)
    except PermissionError:
        ENV_PATH.write_text(tmp.read_text(encoding="utf-8"), encoding="utf-8")
        tmp.unlink()


def main() -> int:
    if not ENV_PATH.exists():
        print("ABORT: backend/.env no existe")
        return 1
    values = {k: (v or "") for k, v in dotenv_values(ENV_PATH).items()}
    if values.get("DEPTIT_ENTORNO", "desarrollo") != "desarrollo":
        print("ABORT: solo se rota la credencial de desarrollo")
        return 1
    p = _params(values)
    if p["dbname"] != DB or p["user"] != ROLE or not p["password"]:
        print("ABORT: la conexion local no es deptit_next_dev / deptit_next_app con contraseña")
        return 1
    old = p["password"]
    new = secrets.token_urlsafe(48)
    lines = [
        "# DEPTIT NEXT backend - DESARROLLO LOCAL. SECRETO: no versionar ni compartir (ver .env.example).",
        "DEPTIT_ENTORNO=desarrollo",
        f"DEPTIT_DB_HOST={p['host']}",
        f"DEPTIT_DB_PORT={p['port']}",
        f"DEPTIT_DB_NAME={DB}",
        f"DEPTIT_DB_USER={ROLE}",
        f"DEPTIT_DB_PASSWORD={new}",
        f"DEPTIT_DB_SSLMODE={p['sslmode']}",
        f"DEPTIT_EXPECTED_DATABASE={DB}",
        f"DEPTIT_EXPECTED_DB_USER={ROLE}",
    ]
    conocidas = {"DATABASE_URL", "DEPTIT_ENTORNO", "DEPTIT_DB_HOST", "DEPTIT_DB_PORT", "DEPTIT_DB_NAME",
                 "DEPTIT_DB_USER", "DEPTIT_DB_PASSWORD", "DEPTIT_DB_SSLMODE", "DEPTIT_EXPECTED_DATABASE",
                 "DEPTIT_EXPECTED_DB_USER"}
    lines += [f"{k}={v}" for k, v in values.items() if k not in conocidas]
    tmp = ENV_PATH.with_name(".env.rotating")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")  # primero: si algo falla, la nueva no se pierde
    try:
        with _connect(p, old) as conn:
            db, user = conn.execute("SELECT current_database(), current_user").fetchone()
            if (db, user) != (DB, ROLE):
                raise SystemExit("ABORT: identidad inesperada")
            conn.execute(sql.SQL("ALTER ROLE {} PASSWORD {}").format(sql.Identifier(ROLE),
                                                                     sql.Literal(scram_sha256_verifier(new))))
            conn.commit()
        with _connect(p, new) as conn:
            ok_new = conn.execute("SELECT current_user").fetchone()[0] == ROLE
        try:
            _connect(p, old).close()
            old_rejected = False
        except psycopg.OperationalError:
            old_rejected = True
        if not (ok_new and old_rejected):
            print(f"FALLO: nueva_conecta={ok_new} vieja_rechazada={old_rejected}; .env.rotating conserva la nueva")
            return 1
        _publicar(tmp)
    except Exception as exc:
        print(f"FALLO: {type(exc).__name__}; revisar .env.rotating antes de reintentar")
        return 1
    print("OK: contraseña local rotada; nueva_conecta=True vieja_rechazada=True; backend/.env actualizado "
          f"(formato DEPTIT_DB_*); longitud={len(new)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
