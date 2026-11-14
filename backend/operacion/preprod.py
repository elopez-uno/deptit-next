"""Preproduccion LOCAL (6A-B3): siembra unica de ``deptit_next_preprod`` desde una copia VERIFICADA de desarrollo.

La siembra NO es una recuperacion (B2 rechaza, con razon, restaurar un backup de otro entorno u otra base): es una
operacion propia, explicita y de una sola vez, con sus guardas:

* solo con ``DEPTIT_ENTORNO=preproduccion``; destino EXACTO ``deptit_next_preprod`` (la base del entorno), VACIO;
* origen: un backup B2 de ``deptit_next_dev`` (entorno ``desarrollo``) que verifica completo (manifest, identidad
  host+puerto+base, antiguedad, tamaño, SHA-256, archivo pg_dump con las tablas criticas).  La app de preproduccion
  nunca se conecta a desarrollo: solo se lee el dump;
* ``--confirm deptit_next_preprod`` + ``--execute`` (sin ellos: plan);
* ``pg_restore --no-owner --no-privileges --single-transaction`` como el OWNER de preproduccion (todo objeto queda
  suyo; la app nunca es owner);
* en UNA transaccion posterior, como owner:
  1. huella semantica (esquema + datos) ANTES de transformar: debe coincidir con la de desarrollo (se compara afuera);
  2. GRANT al rol de la app = replica EXACTA de los privilegios de ``deptit_next_app`` en desarrollo (snapshot
     ``privileges-snapshot``, con SHA-256) + verificacion privilegio por privilegio;
  3. rol de backup: SELECT en todo, sin escritura (+ default privileges del owner);
  4. cuentas heredadas (las 3 semillas y las demas migradas): TODAS quedan ``Inactivo`` con credencial inutilizable
     (salt nuevo + marcador que ningun verificador acepta) y la marca ``ZZPILOTB3`` en observaciones.  Las filas se
     conservan (referencias por id/email en auditoria y documentos); ninguna credencial de desarrollo pasa a preprod;
  5. huella DESPUES: la unica tabla que puede cambiar es ``app_usuarios``.
  Cualquier fallo: ROLLBACK de la transformacion (la base queda restaurada pero sin GRANT: la app no arranca).
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import secrets
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import psycopg
from psycopg import sql

import settings as app_settings
from auth import core
from integraciones.ciclo_periodos.ref_b11 import pg_archive
from integraciones.ciclo_periodos.ref_b11.backup_manifest import CRITICAL_TABLES, format_ts, utc_now, verify_backup
from integraciones.ciclo_periodos.ref_b11.db_identity import identity_from_url, libpq_environment, redact
from integraciones.ciclo_periodos.ref_b11.restore_drill import pg_restore_command

from . import bootstrap, comparacion
from .config import OpsConfig

MARCA = "ZZPILOTB3"
KIND_PRIVILEGIOS = "deptit-next-app-privileges"
PRIVS_RELACION = ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")
PRIVS_SECUENCIA = ("SELECT", "USAGE", "UPDATE")
# Marcador de credencial deshabilitada: prefijo versionado con iteraciones NO numericas, el unico formato que
# ``core._parse_hash`` rechaza (todo texto sin prefijo se interpreta como hash legado).  ``verify_password`` y
# ``needs_rehash`` devuelven False sin calcular nada; un administrador puede asignar una contraseña nueva desde la app.
HASH_DESHABILITADO = f"{core.HASH_PREFIX}deshabilitada${MARCA}"
NOTA_CUENTA = f"[{MARCA}] cuenta heredada de desarrollo: desactivada en preproduccion (sin credencial utilizable)"
STDERR_LIMIT = 2000

REL_ACL = """
SELECT c.relname, c.relkind::text, array_agg(DISTINCT a.privilege_type ORDER BY a.privilege_type)
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace CROSS JOIN LATERAL aclexplode(c.relacl) a
 WHERE n.nspname = 'public' AND a.grantee = %s::regrole AND c.relkind IN ('r', 'p', 'v', 'm', 'f', 'S')
 GROUP BY 1, 2 ORDER BY 1"""
COL_ACL = """
SELECT c.relname, at.attname, array_agg(DISTINCT a.privilege_type ORDER BY a.privilege_type)
  FROM pg_attribute at JOIN pg_class c ON c.oid = at.attrelid JOIN pg_namespace n ON n.oid = c.relnamespace
 CROSS JOIN LATERAL aclexplode(at.attacl) a
 WHERE n.nspname = 'public' AND a.grantee = %s::regrole AND at.attnum > 0 AND NOT at.attisdropped
 GROUP BY 1, 2 ORDER BY 1, 2"""
RELACIONES = """
SELECT c.relname, c.relkind::text FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p', 'v', 'm', 'f', 'S') ORDER BY 1"""


class SiembraError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


# ------------------------------------------------------------------------------------------ privilegios
def _sha_privilegios(doc: Dict[str, Any]) -> str:
    cuerpo = {k: doc[k] for k in ("base_origen", "rol_origen", "relaciones", "columnas")}
    return hashlib.sha256(json.dumps(cuerpo, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def snapshot_privilegios(conn, rol: str = app_settings.ROL_DESARROLLO) -> Dict[str, Any]:
    """Privilegios del rol de la app en la base conectada (solo lectura del catalogo; cualquier rol puede leerlo)."""
    doc = {"kind": KIND_PRIVILEGIOS, "format_version": 1, "base_origen": conn.execute(
        "SELECT current_database()").fetchone()[0], "rol_origen": rol,
           "relaciones": {r[0]: {"relkind": r[1], "privilegios": list(r[2])} for r in conn.execute(REL_ACL, (rol,))},
           "columnas": {f"{r[0]}.{r[1]}": list(r[2]) for r in conn.execute(COL_ACL, (rol,))}}
    doc["sha256"] = _sha_privilegios(doc)
    return doc


def validar_privilegios(doc: Any) -> Optional[str]:
    if not isinstance(doc, dict) or doc.get("kind") != KIND_PRIVILEGIOS or doc.get("format_version") != 1:
        return "no es un snapshot de privilegios valido"
    if doc.get("base_origen") != app_settings.BASES[app_settings.DESARROLLO] \
            or doc.get("rol_origen") != app_settings.ROL_DESARROLLO:
        return "el snapshot no es del rol de la app de desarrollo"
    try:
        if doc.get("sha256") != _sha_privilegios(doc):
            return "el SHA-256 del snapshot no coincide (alterado)"
    except (KeyError, TypeError):
        return "snapshot incompleto"
    for nombre, r in doc["relaciones"].items():
        validos = PRIVS_SECUENCIA if r.get("relkind") == "S" else PRIVS_RELACION
        if not r.get("privilegios") or set(r["privilegios"]) - set(validos):
            return f"privilegios invalidos para {nombre!r}"
    return None


def otorgar_app(conn, app_user: str, doc: Dict[str, Any]) -> Dict[str, int]:
    """GRANT al rol de la app replicando el snapshot (identificadores escapados con psycopg.sql)."""
    rel = col = 0
    for nombre, r in sorted(doc["relaciones"].items()):
        tipo = sql.SQL("SEQUENCE" if r["relkind"] == "S" else "TABLE")
        privs = sql.SQL(", ").join(sql.SQL(p) for p in r["privilegios"])
        conn.execute(sql.SQL("GRANT {} ON {} {}.{} TO {}").format(privs, tipo, sql.Identifier("public"),
                                                                 sql.Identifier(nombre), sql.Identifier(app_user)))
        rel += 1
    for clave, privs in sorted(doc["columnas"].items()):
        tabla, columna = clave.split(".", 1)
        conn.execute(sql.SQL("GRANT {} ({}) ON TABLE {}.{} TO {}").format(
            sql.SQL(", ").join(sql.SQL(p) for p in privs), sql.Identifier(columna), sql.Identifier("public"),
            sql.Identifier(tabla), sql.Identifier(app_user)))
        col += 1
    conn.execute(sql.SQL("GRANT EXECUTE ON ALL ROUTINES IN SCHEMA public TO {}").format(sql.Identifier(app_user)))
    return {"relaciones": rel, "columnas": col}


def diferencias_privilegios(conn, app_user: str, doc: Dict[str, Any]) -> list:
    """Cada privilegio de cada relacion de public: el rol de la app tiene EXACTAMENTE lo del snapshot."""
    out = []
    for nombre, relkind in conn.execute(RELACIONES).fetchall():
        esperado = set(doc["relaciones"].get(nombre, {}).get("privilegios", []))
        funcion, privs = (("has_sequence_privilege", PRIVS_SECUENCIA) if relkind == "S"
                          else ("has_table_privilege", PRIVS_RELACION))
        for p in privs:
            tiene = conn.execute(sql.SQL("SELECT {}(%s, %s, %s)").format(sql.Identifier(funcion)),
                                 (app_user, f"public.{_ident(nombre)}", p)).fetchone()[0]
            if tiene != (p in esperado):
                out.append(f"{nombre}.{p}: {'sobra' if tiene else 'falta'}")
    faltantes = sorted(set(doc["relaciones"]) - {r[0] for r in conn.execute(RELACIONES).fetchall()})
    out += [f"{n}: no existe en el destino" for n in faltantes]
    return out


def _ident(nombre: str) -> str:
    return '"' + nombre.replace('"', '""') + '"'


def otorgar_backup(conn, owner: str, backup_user: str) -> None:
    b, o = sql.Identifier(backup_user), sql.Identifier(owner)
    conn.execute(sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA public TO {}").format(b))
    conn.execute(sql.SQL("GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO {}").format(b))
    conn.execute(sql.SQL("ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public GRANT SELECT ON TABLES TO {}")
                 .format(o, b))
    conn.execute(sql.SQL("ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public GRANT SELECT ON SEQUENCES TO {}")
                 .format(o, b))


def problemas_backup(conn, backup_user: str) -> list:
    sin_select = conn.execute(
        "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'public' "
        "AND c.relkind IN ('r', 'p', 'S') AND NOT has_table_privilege(%s, c.oid, 'SELECT')", (backup_user,)
    ).fetchone()[0]
    escritura = conn.execute(
        "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'public' "
        "AND c.relkind IN ('r', 'p') AND (has_table_privilege(%s, c.oid, 'INSERT') OR has_table_privilege(%s, c.oid, "
        "'UPDATE') OR has_table_privilege(%s, c.oid, 'DELETE') OR has_table_privilege(%s, c.oid, 'TRUNCATE'))",
        (backup_user,) * 4).fetchone()[0]
    return ([f"{sin_select} relaciones sin SELECT"] if sin_select else []) + \
        ([f"{escritura} relaciones con escritura"] if escritura else [])


# ------------------------------------------------------------------------------------------ cuentas heredadas
def desactivar_cuentas_heredadas(conn) -> Dict[str, Any]:
    """Todas las cuentas copiadas de desarrollo: Inactivo + credencial inutilizable + marca.  Devuelve SOLO conteos y
    los emails semilla (identificadores publicos); nunca hashes ni el resto de los emails."""
    assert core._parse_hash(HASH_DESHABILITADO) is None  # el marcador jamas verifica
    filas = conn.execute("SELECT id, email, rol, estado FROM app_usuarios ORDER BY id FOR UPDATE").fetchall()
    for uid, *_ in filas:
        conn.execute("UPDATE app_usuarios SET estado = 'Inactivo', salt = %s, password_hash = %s, "
                     "observaciones = trim(both ' ' from coalesce(observaciones, '') || ' ' || %s) WHERE id = %s",
                     (secrets.token_hex(16), HASH_DESHABILITADO, NOTA_CUENTA, uid))
    activas = conn.execute("SELECT count(*) FROM app_usuarios WHERE estado = 'Activo'").fetchone()[0]
    utilizables = conn.execute("SELECT count(*) FROM app_usuarios WHERE password_hash <> %s",
                               (HASH_DESHABILITADO,)).fetchone()[0]
    semillas = bootstrap.auditar_semillas(conn)
    return {"cuentas": len(filas), "activas_antes": sum(1 for f in filas if f[3] == "Activo"),
            "por_rol": _contar(f[2] for f in filas), "activas_despues": activas,
            "credenciales_utilizables_despues": utilizables, "semillas": semillas}


CUENTA_INEXISTENTE = "INEXISTENTE"
CUENTA_HEREDADA = "HEREDADA_DESACTIVADA"
CUENTA_NO_ELEGIBLE = "NO_ELEGIBLE"


def clasificar_cuenta_humana(conn, email: str, *, base_esperada: Optional[str] = None) -> Dict[str, Any]:
    """Cuenta humana del piloto (``deptit-ops -Action cuenta-humana``): que hacer con ``email`` en PREPRODUCCION.

    Solo consultas (el llamador abre la conexion ``read_only`` y revierte) y solo sobre ``deptit_next_preprod``
    (``base_esperada`` solo la cambian los tests, sobre una base ``restore_test``).  Devuelve:
    * ``INEXISTENTE``: ninguna fila con ese email (sin distinguir mayusculas) -> se crea por Administracion SaaS;
    * ``HEREDADA_DESACTIVADA``: UNA fila que es inequivocamente una cuenta copiada de desarrollo y desactivada por la
      siembra B3 (``Inactivo`` + el marcador EXACTO de credencial deshabilitada + la nota de la siembra) -> se reutiliza
      esa fila (mismo id) por Administracion SaaS;
    * ``NO_ELEGIBLE`` con motivo: cualquier otro caso (activa, ya reactivada, con contraseña propia, sin la nota,
      duplicada por mayusculas): fail closed, no se toca.
    Nunca devuelve hashes, salts ni contraseñas."""
    email = str(email or "").strip().lower()
    if not email or "@" not in email:
        return {"clasificacion": CUENTA_NO_ELEGIBLE, "motivo": "EMAIL_INVALIDO"}
    esperada = base_esperada or app_settings.BASES[app_settings.PREPRODUCCION]
    base = conn.execute("SELECT current_database()").fetchone()[0]
    if base != esperada:
        raise ValueError(f"clasificar_cuenta_humana solo opera sobre {esperada} (conectado a {base})")
    filas = conn.execute(
        "SELECT id, nombre, rol, estado, password_hash = %s, position(%s in coalesce(observaciones, '')) > 0 "
        "FROM app_usuarios WHERE lower(email) = %s ORDER BY id", (HASH_DESHABILITADO, NOTA_CUENTA, email)).fetchall()
    if not filas:
        return {"clasificacion": CUENTA_INEXISTENTE}
    if len(filas) > 1:
        return {"clasificacion": CUENTA_NO_ELEGIBLE, "motivo": "EMAIL_DUPLICADO", "filas": len(filas)}
    uid, nombre, rol, estado, marcador, nota = filas[0]
    base_out = {"id": int(uid), "nombre": nombre, "rol_actual": rol, "estado_actual": estado}
    for ok, motivo in ((estado == "Inactivo", "NO_INACTIVA"), (marcador, "CREDENCIAL_NO_DESHABILITADA_POR_B3"),
                       (nota, "SIN_NOTA_DE_LA_SIEMBRA_B3")):
        if not ok:
            return {"clasificacion": CUENTA_NO_ELEGIBLE, "motivo": motivo, **base_out}
    return {"clasificacion": CUENTA_HEREDADA, **base_out}


def _contar(valores) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for v in valores:
        out[str(v)] = out.get(str(v), 0) + 1
    return out


# ------------------------------------------------------------------------------------------ siembra
def _identidad_dev(cfg: OpsConfig):
    db = cfg.app.db
    return identity_from_url(f"postgresql://siembra@{db.host}:{db.port}/{app_settings.BASES[app_settings.DESARROLLO]}")


def sembrar(cfg: OpsConfig, manifest_path, privilegios: Any, *, execute: bool = False, confirm: Optional[str] = None,
            runner: Callable = subprocess.run, which: Callable = shutil.which, connect: Callable = psycopg.connect,
            now: Optional[_dt.datetime] = None) -> dict:
    now = now or utc_now()
    target = app_settings.BASES[app_settings.PREPRODUCCION]
    report: Dict[str, Any] = {"kind": "deptit-next-preprod-seed", "format_version": 1, "target": target,
                              "mode": "execute" if execute else "plan", "started_at_utc": format_ts(now),
                              "result": "FAIL", "code": None, "steps": []}
    secreto = cfg.owner.password if cfg.owner else None
    try:
        if cfg.entorno != app_settings.PREPRODUCCION:
            raise SiembraError("ENVIRONMENT_REFUSED", "la siembra solo existe en preproduccion")
        if cfg.app.expected_database != target or cfg.app.db.name != target:
            raise SiembraError("TARGET_REFUSED", f"el destino debe ser exactamente {target!r}")
        if cfg.owner is None or cfg.backup is None:
            raise SiembraError("ROLES_MISSING", "faltan DEPTIT_OWNER_DB_* o DEPTIT_BACKUP_DB_* (ops.env)")
        if (motivo := validar_privilegios(privilegios)) is not None:
            raise SiembraError("PRIVILEGES_INVALID", motivo)
        report["privilegios"] = {"sha256": privilegios["sha256"], "relaciones": len(privilegios["relaciones"]),
                                 "columnas": len(privilegios["columnas"])}
        chk = verify_backup(manifest_path, expected_identity=_identidad_dev(cfg), now=now)
        report["origen"] = {"manifest": Path(manifest_path).name, "verification": chk.code}
        if not chk.ok:
            raise SiembraError("BACKUP_INVALID", f"el backup de desarrollo no verifica ({chk.code})")
        m = chk.manifest
        if m["deptit"].get("entorno") != app_settings.DESARROLLO \
                or m["database"]["name"] != app_settings.BASES[app_settings.DESARROLLO]:
            raise SiembraError("SOURCE_NOT_DEVELOPMENT", "el origen debe ser un backup de deptit_next_dev")
        report["origen"].update({"backup_id": m["deptit"].get("backup_id"), "sha256": m["dump"]["sha256"],
                                 "created_at_utc": m["created_at_utc"], "esquema_sha256": m["deptit"].get(
                                     "esquema_sha256")})
        archive = pg_archive.inspect_archive(chk.dump_path, required_tables=CRITICAL_TABLES,
                                             expected_dbname=m["database"]["name"])
        if not archive["ok"]:
            raise SiembraError("ARCHIVE_INVALID", "; ".join(archive["problems"]))
        report["steps"].append("backup_verified")
        if confirm != target:
            raise SiembraError("CONFIRMATION_REQUIRED", f"la siembra exige --confirm {target}")
        if not execute:
            report["result"], report["code"] = "PLANNED", "PLAN_ONLY"
            return report
        pg_restore = which("pg_restore", path=str(cfg.pg_bin_dir)) if cfg.pg_bin_dir else which("pg_restore")
        if not pg_restore:
            raise SiembraError("BINARY_MISSING", "pg_restore no esta instalado")
        with connect(cfg.url(cfg.owner, target), connect_timeout=15, autocommit=True) as c:
            quien = c.execute("SELECT current_database(), current_user").fetchone()
            ocupada = c.execute("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                                "WHERE n.nspname = 'public'").fetchone()[0]
        if quien != (target, cfg.owner.user):
            raise SiembraError("IDENTITY", "la conexion del owner no apunta a la base/rol esperados")
        if ocupada:
            raise SiembraError("TARGET_NOT_EMPTY", "deptit_next_preprod tiene objetos: la siembra es de una sola vez")
        with libpq_environment(identity_from_url(cfg.url(cfg.owner, target)), secreto,
                               {"PGSSLMODE": cfg.app.db.sslmode}, database=target) as env:
            proc = runner(pg_restore_command(pg_restore, target, chk.dump_path), env=env, capture_output=True,
                          text=True)
        if proc.returncode != 0:
            raise SiembraError("PG_RESTORE_FAILED", f"pg_restore rc={proc.returncode}: "
                                                    f"{redact(proc.stderr, secreto)[-STDERR_LIMIT:]}")
        report["steps"].append("pg_restore")
        report.update(_transformar(cfg, privilegios, target, connect))
        report["steps"].append("transformacion")
        report["result"], report["code"] = "PASS", "SEEDED"
    except SiembraError as exc:
        report["code"], report["error"] = exc.code, redact(exc.message, secreto)[:STDERR_LIMIT]
    except Exception as exc:  # noqa: BLE001 (reporte fail-closed, sin secretos)
        report["code"], report["error"] = "UNEXPECTED", redact(f"{type(exc).__name__}: {exc}", secreto)[:500]
    report["finished_at_utc"] = format_ts(utc_now())
    return report


def _transformar(cfg: OpsConfig, privilegios: Dict[str, Any], target: str, connect: Callable) -> Dict[str, Any]:
    app_user, owner, backup_user = cfg.app.expected_db_user, cfg.owner.user, cfg.backup.user
    with connect(cfg.url(cfg.owner, target), connect_timeout=15, autocommit=False) as conn:
        ajenos = conn.execute("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                              "WHERE n.nspname = 'public' AND pg_get_userbyid(c.relowner) <> current_user"
                              ).fetchone()[0]
        if ajenos:
            raise SiembraError("FOREIGN_OWNER", f"{ajenos} objetos no pertenecen al owner de preproduccion")
        antes = comparacion.huella(conn)
        otorgados = otorgar_app(conn, app_user, privilegios)
        if difs := diferencias_privilegios(conn, app_user, privilegios):
            raise SiembraError("PRIVILEGES_MISMATCH", f"{len(difs)} diferencias de privilegios: {difs[:5]}")
        otorgar_backup(conn, owner, backup_user)
        if probs := problemas_backup(conn, backup_user):
            raise SiembraError("BACKUP_ROLE_INVALID", "; ".join(probs))
        cuentas = desactivar_cuentas_heredadas(conn)
        if cuentas["activas_despues"] or cuentas["credenciales_utilizables_despues"] \
                or cuentas["semillas"]["semillas_activas"]:
            raise SiembraError("ACCOUNTS_NOT_DISABLED", "quedaron cuentas heredadas activas o con credencial")
        despues = comparacion.huella(conn)
        difs = comparacion.diferencias(antes, despues)
        if any(not d.startswith("datos.app_usuarios") for d in difs):
            raise SiembraError("UNEXPECTED_CHANGE", f"la transformacion cambio algo mas que app_usuarios: {difs[:5]}")
        conn.commit()
    return {"huella_restaurada": comparacion.resumen(antes), "huella_final": comparacion.resumen(despues),
            "cambios_transformacion": difs, "otorgados_app": otorgados, "rol_backup": "SELECT en todo, sin escritura",
            "cuentas_heredadas": cuentas}
