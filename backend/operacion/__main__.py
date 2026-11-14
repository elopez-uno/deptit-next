"""CLI operativa de DEPTIT NEXT (6A-B2).  Desde ``backend/``:  ``python -m operacion <comando> [opciones]``.

    backup-db | backup-docs | backup-set [--app-detenida]       backups (PASS solo si quedan verificados)
    verify-db | verify-docs --manifest M | verify-set --manifest M   evidencia (verify-db = decision del gate)
    restore-db --manifest M [--modo prueba|recuperacion] [--target T] [--execute] [--confirm T] [--drop-after]
    restore-docs --manifest M --destino DIR                      solo a un directorio inexistente o vacio
    restore-test-dbs                                             bases deptit_next_restore_test_* presentes
    retention [--keep-days N] [--apply]                          dry-run por defecto
    schema-baseline | schema-apply-test --target T               esquema base versionado (migration/schema)
    bootstrap-superadmin --email E [--name N] [--execute] [--password-stdin] [--base-prueba T]
    seed-audit                                                   cuentas semilla heredadas en la base configurada
    health [--backend-url U] [--frontend-url U]                  health operativo detallado (local)
    release [--no-zip] | release-verify --dir D                  artefacto de release + auditoria de secretos
    privileges-snapshot --out F                                  (desarrollo) privilegios de deptit_next_app, con SHA
    preprod-seed --manifest M --privilegios F [--execute] [--confirm deptit_next_preprod]
                                                                 (preproduccion) siembra unica desde un backup de dev
    cuenta-humana-estado --email E                               (preproduccion, solo lectura) inexistente / heredada
                                                                 desactivada por B3 / no elegible

Salida: JSON sin secretos en stdout (y en ``--json-out``).  Exit 0 = PASS/PLANNED; 2 = FAIL; 3 = configuracion.
Una linea de evento por comando en stderr (inicio/fin/codigo) para el log del gestor de servicios.
"""
from __future__ import annotations

import argparse
import getpass
import json
import sys
import time
from pathlib import Path

import psycopg

from integraciones.ciclo_periodos import backup_gate

from . import (backup_db, backup_documentos, backup_set, bootstrap, config, esquema, preprod, release, restore_db,
               retencion, salud)


def _evento(texto: str) -> None:
    print(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} deptit.operacion {texto}", file=sys.stderr, flush=True)


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="python -m operacion", description="Operacion DEPTIT NEXT (6A-B2)")
    ap.add_argument("--json-out")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("backup-db")
    sub.add_parser("backup-docs")
    p = sub.add_parser("backup-set")
    p.add_argument("--app-detenida", action="store_true")
    sub.add_parser("verify-db")
    for name in ("verify-docs", "verify-set"):
        sub.add_parser(name).add_argument("--manifest", required=True)
    p = sub.add_parser("restore-db")
    p.add_argument("--manifest", required=True)
    p.add_argument("--modo", choices=(restore_db.PRUEBA, restore_db.RECUPERACION), default=restore_db.PRUEBA)
    p.add_argument("--target")
    p.add_argument("--execute", action="store_true")
    p.add_argument("--confirm")
    p.add_argument("--drop-after", action="store_true")
    p = sub.add_parser("restore-docs")
    p.add_argument("--manifest", required=True)
    p.add_argument("--destino", required=True)
    sub.add_parser("restore-test-dbs")
    p = sub.add_parser("retention")
    p.add_argument("--keep-days")
    p.add_argument("--apply", action="store_true")
    sub.add_parser("schema-baseline")
    sub.add_parser("schema-apply-test").add_argument("--target", required=True)
    p = sub.add_parser("bootstrap-superadmin")
    p.add_argument("--email", required=True)
    p.add_argument("--name", default="Superadmin")
    p.add_argument("--execute", action="store_true")
    p.add_argument("--password-stdin", action="store_true")
    p.add_argument("--base-prueba", help="solo desarrollo: base deptit_next_restore_test_* (rol de restore)")
    sub.add_parser("seed-audit")
    p = sub.add_parser("health")
    p.add_argument("--backend-url")
    p.add_argument("--frontend-url")
    sub.add_parser("release").add_argument("--no-zip", action="store_true")
    sub.add_parser("release-verify").add_argument("--dir", required=True)
    sub.add_parser("privileges-snapshot").add_argument("--out", required=True)
    p = sub.add_parser("preprod-seed")
    p.add_argument("--manifest", required=True, help="manifest de un backup B2 de deptit_next_dev")
    p.add_argument("--privilegios", required=True, help="JSON de privileges-snapshot")
    p.add_argument("--execute", action="store_true")
    p.add_argument("--confirm")
    sub.add_parser("cuenta-humana-estado").add_argument("--email", required=True)
    return ap


def _password(args, stdin, prompt) -> str:
    if args.password_stdin:
        return (stdin or sys.stdin).readline().rstrip("\r\n")
    primera = prompt("Contraseña del superadmin (no se muestra): ")
    if primera != prompt("Repetir contraseña: "):
        raise ValueError("PASSWORD_MISMATCH")
    return primera


def _bootstrap(cfg: config.OpsConfig, args, *, stdin=None, prompt=getpass.getpass, connect=psycopg.connect) -> dict:
    try:
        password = _password(args, stdin, prompt)
    except ValueError:
        return {"result": "FAIL", "code": "PASSWORD_MISMATCH"}
    esperada = cfg.app.expected_database
    if not args.execute:
        return bootstrap.provisionar(None, args.email, password, args.name, esperada=esperada, entorno=cfg.entorno)
    if args.base_prueba:
        if cfg.entorno != "desarrollo" or not config.RESTORE_TEST_RE.match(args.base_prueba) or cfg.restore is None:
            return {"result": "FAIL", "code": "TARGET_REFUSED",
                    "detail": "--base-prueba exige desarrollo, una base deptit_next_restore_test_* y el rol de restore"}
        esperada = args.base_prueba
        dsn = cfg.url(cfg.restore, args.base_prueba)
    else:
        dsn = cfg.app.db.conninfo
    with connect(dsn, connect_timeout=15, autocommit=False) as conn:
        return bootstrap.provisionar(conn, args.email, password, args.name, esperada=esperada, entorno=cfg.entorno,
                                     execute=True)


def ejecutar(args, cfg: config.OpsConfig, **kw) -> dict:
    c = args.cmd
    if c in ("backup-db", "backup-docs", "backup-set"):
        config.preparar_backup_dir(cfg, crear=cfg.entorno == "desarrollo")
    if c == "backup-db":
        return backup_db.respaldar(cfg)
    if c == "backup-docs":
        return backup_documentos.respaldar(cfg.app.documents_dir, cfg.documentos_dir, entorno=cfg.entorno)
    if c == "backup-set":
        return backup_set.respaldar(cfg, modo=backup_set.APP_DETENIDA if args.app_detenida else backup_set.EN_LINEA)
    if c == "verify-db":
        d = backup_gate.evaluar(cfg.identity_url(), env={**cfg.env, backup_gate.GATE_ENV: backup_gate.ACTIVO})
        return {"result": "PASS" if d.permitido else "FAIL", "code": d.codigo, "detail": d.mensaje}
    if c == "verify-docs":
        chk = backup_documentos.verificar(Path(args.manifest), entorno=cfg.entorno)
        return {"result": "PASS" if chk.ok else "FAIL", **chk.summary()}
    if c == "verify-set":
        chk = backup_set.verificar(cfg, Path(args.manifest))
        return {"result": "PASS" if chk["ok"] else "FAIL", **chk}
    if c == "restore-db":
        return restore_db.restaurar(cfg, Path(args.manifest), modo=args.modo, target=args.target,
                                    execute=args.execute, confirm=args.confirm, drop_after=args.drop_after)
    if c == "restore-docs":
        return backup_documentos.restaurar(Path(args.manifest), Path(args.destino), backups_dir=cfg.backup_dir,
                                           entorno=cfg.entorno, env=cfg.env)
    if c == "restore-test-dbs":
        bases = restore_db.bases_de_prueba(cfg)
        return {"result": "PASS", "bases": bases, "count": len(bases)}
    if c == "retention":
        return retencion.ejecutar(cfg, keep_days=args.keep_days, apply=args.apply)
    if c == "schema-baseline":
        return esquema.generar(cfg)
    if c == "schema-apply-test":
        return esquema.aplicar_en_prueba(cfg, args.target)
    if c == "bootstrap-superadmin":
        return _bootstrap(cfg, args, **kw)
    if c == "seed-audit":
        with psycopg.connect(cfg.app.db.conninfo, connect_timeout=15) as conn:
            conn.read_only = True
            r = bootstrap.auditar_semillas(conn)
        ok = cfg.entorno == "desarrollo" or r["ok_para_produccion"]
        return {"result": "PASS" if ok else "FAIL", "entorno": cfg.entorno, **r}
    if c == "health":
        return salud.revisar(cfg, backend_url=args.backend_url, frontend_url=args.frontend_url)
    if c == "release":
        return release.construir(pg_bin_dir=cfg.pg_bin_dir, zip_=not args.no_zip)
    if c == "release-verify":
        r = release.verificar(Path(args.dir))
        return {"result": "PASS" if r["ok"] else "FAIL", **r}
    if c == "privileges-snapshot":
        return _snapshot_privilegios(cfg, Path(args.out), **kw)
    if c == "preprod-seed":
        try:
            doc = json.loads(Path(args.privilegios).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            doc = None
        return preprod.sembrar(cfg, Path(args.manifest), doc, execute=args.execute, confirm=args.confirm)
    if c == "cuenta-humana-estado":
        return _cuenta_humana_estado(cfg, args.email, **kw)
    raise AssertionError(c)


def _cuenta_humana_estado(cfg: config.OpsConfig, email: str, *, connect=psycopg.connect) -> dict:
    """Solo preproduccion: clasificacion de solo lectura de la cuenta humana del piloto (sin hashes ni secretos)."""
    if cfg.entorno != "preproduccion":
        return {"result": "FAIL", "code": "REFUSED", "detail": "solo en preproduccion"}
    with connect(cfg.app.db.conninfo, connect_timeout=15) as conn:
        conn.read_only = True
        r = preprod.clasificar_cuenta_humana(conn, email)
        conn.rollback()
    return {"result": "PASS", "code": r["clasificacion"], **r}


def _snapshot_privilegios(cfg: config.OpsConfig, out: Path, *, connect=psycopg.connect) -> dict:
    """Solo desarrollo, con el rol de backup (lectura del catalogo).  No sobrescribe un snapshot existente."""
    if cfg.entorno != "desarrollo" or cfg.backup is None:
        return {"result": "FAIL", "code": "REFUSED", "detail": "solo en desarrollo y con el rol de backup"}
    if out.exists():
        return {"result": "FAIL", "code": "TARGET_EXISTS", "detail": f"{out.name} ya existe"}
    with connect(cfg.url(cfg.backup, cfg.app.expected_database), connect_timeout=15) as conn:
        conn.read_only = True
        doc = preprod.snapshot_privilegios(conn)
        conn.rollback()
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return {"result": "PASS", "code": "PASS", "out": str(out), "sha256": doc["sha256"],
            "relaciones": len(doc["relaciones"]), "columnas": len(doc["columnas"])}


def main(argv=None, *, env=None, out=None, **kw) -> int:
    args = _parser().parse_args(argv)
    out = out or sys.stdout
    _evento(f"inicio comando={args.cmd}")
    try:
        cfg = config.load(env, read_files=env is None)
    except config.OpsConfigError as exc:
        report = {"result": "FAIL", "code": "CONFIG", "detail": str(exc)}
        rc = 3
    else:
        try:
            report = ejecutar(args, cfg, **kw)
        except (config.OpsConfigError, release.ReleaseError) as exc:
            report = {"result": "FAIL", "code": "REFUSED", "detail": str(exc)}
        except psycopg.Error as exc:
            report = {"result": "FAIL", "code": "DB_ERROR", "detail": type(exc).__name__}
        rc = 0 if report.get("result") in ("PASS", "PLANNED") else 2
    text = json.dumps(report, ensure_ascii=False, indent=1, default=str)
    if args.json_out:
        Path(args.json_out).write_text(text + "\n", encoding="utf-8")
    out.write(text + "\n")
    _evento(f"fin comando={args.cmd} result={report.get('result')} code={report.get('code')}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
