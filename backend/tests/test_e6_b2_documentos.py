"""Etapa 6A-B2: backup / verificacion / restore del storage documental (docs/ETAPA6_6AB2_OPERATION_RECOVERY.md).
Todo sobre arboles temporales: el storage real nunca se toca."""

from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
from pathlib import Path

import pytest

from operacion import backup_documentos as D

NOW = dt.datetime(2026, 11, 3, 22, 0, 0, tzinfo=dt.timezone.utc)
ARCHIVOS = {"inst_1/plantillas/disposicion.docx": b"PK\x03\x04plantilla" * 100,
            "inst_1/disposiciones/2026/acto 1.docx": b"PK\x03\x04acto" * 50,
            "inst_2/respaldos/resolucion.pdf": b"%PDF-1.7 contenido",
            "vacio.txt": b""}
EXCLUIDOS = {"inst_1/~$abierto.docx": b"lock", "inst_1/tmp.tmp": b"x", "server.log": b"log", ".env": b"SECRETO=1",
             "inst_2/copia.dump": b"PGDMP"}


def _arbol(raiz: Path, archivos=ARCHIVOS) -> Path:
    for rel, datos in archivos.items():
        p = raiz.joinpath(*rel.split("/"))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(datos)
    return raiz


@pytest.fixture
def entorno(tmp_path):
    origen = _arbol(tmp_path / "documents", {**ARCHIVOS, **EXCLUIDOS})
    backups = tmp_path / "backups" / "documents"
    backups.mkdir(parents=True)
    rep = D.respaldar(origen, backups, entorno="desarrollo", set_id="deptit_set_desarrollo_20261103T220000Z", now=NOW)
    assert rep["result"] == "PASS", rep
    return origen, backups, Path(rep["manifest"]), rep


def _junction(link: Path, destino: Path):
    subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(destino)], check=True, capture_output=True)


def test_backup_valido_y_exclusiones(entorno):
    origen, backups, manifest, rep = entorno
    doc = json.loads(manifest.read_text(encoding="utf-8"))
    assert doc["count"] == len(ARCHIVOS) == rep["count"] and doc["entorno"] == "desarrollo"
    assert sorted(f["path"] for f in doc["files"]) == sorted(ARCHIVOS)
    assert doc["total_bytes"] == sum(len(v) for v in ARCHIVOS.values())
    assert {e["path"] for e in doc["excluded"]} == set(EXCLUIDOS)
    assert doc["set_id"] == "deptit_set_desarrollo_20261103T220000Z" and doc["validation"]["status"] == "PASS"
    copia = backups / doc["backup_id"]
    for rel, datos in ARCHIVOS.items():
        assert copia.joinpath(*rel.split("/")).read_bytes() == datos
    assert not any(copia.rglob(".env")) and not any(copia.rglob("*.log")) and not any(copia.rglob("*.dump"))
    assert [p.name for p in backups.iterdir() if p.name.startswith(".")] == []
    assert D.verificar(manifest, entorno="desarrollo").ok
    assert D.verificar(manifest, entorno="produccion").code == "OTHER_ENVIRONMENT"


def test_restore_exacto_en_carpeta_vacia(entorno, tmp_path):
    _, backups, manifest, _ = entorno
    destino = tmp_path / "restaurado"
    rep = D.restaurar(manifest, destino, backups_dir=backups.parent, entorno="desarrollo")
    assert rep["result"] == "PASS" and rep["code"] == "RESTORE_VERIFIED", rep
    for rel, datos in ARCHIVOS.items():
        assert destino.joinpath(*rel.split("/")).read_bytes() == datos
    assert sorted(p.relative_to(destino).as_posix() for p in destino.rglob("*") if p.is_file()) == sorted(ARCHIVOS)
    vacio = tmp_path / "vacio"
    vacio.mkdir()
    assert D.restaurar(manifest, vacio, backups_dir=backups.parent)["result"] == "PASS"
    assert not list(tmp_path.glob(".*.restoring"))


def test_restore_rechaza_destinos_peligrosos(entorno, tmp_path):
    origen, backups, manifest, _ = entorno
    ocupado = tmp_path / "ocupado"
    ocupado.mkdir()
    (ocupado / "previo.txt").write_bytes(b"no tocar")
    casos = ((ocupado, "TARGET_NOT_EMPTY"), (origen, "TARGET_NOT_EMPTY"),
             (backups / "dentro", "TARGET_PROTECTED"), (Path(r"C:\DEPTIT_PROD\restore_x"), "TARGET_PROTECTED"),
             (Path("relativo"), "TARGET_INVALID"))
    for destino, codigo in casos:
        rep = D.restaurar(manifest, destino, backups_dir=backups.parent)
        assert rep["result"] == "FAIL" and rep["code"] == codigo, (destino, rep)
    assert (ocupado / "previo.txt").read_bytes() == b"no tocar" and len(list(ocupado.iterdir())) == 1
    assert not (backups / "dentro").exists() and not Path(r"C:\DEPTIT_PROD\restore_x").exists()


def _alterar_y_verificar(entorno, tmp_path, alterar, codigo):
    origen, backups, manifest, rep = entorno
    doc = json.loads(manifest.read_text(encoding="utf-8"))
    alterar(manifest, backups / doc["backup_id"], doc)
    chk = D.verificar(manifest)
    assert not chk.ok and chk.code == codigo, chk.summary()
    destino = tmp_path / "destino_alterado"
    r = D.restaurar(manifest, destino, backups_dir=backups.parent)
    assert r["result"] == "FAIL" and r["code"] == "BACKUP_INVALID" and not destino.exists()


def test_hash_alterado(entorno, tmp_path):
    def f(m, copia, doc):
        p = copia / "inst_2" / "respaldos" / "resolucion.pdf"
        datos = bytearray(p.read_bytes())
        datos[0] ^= 0x01
        p.write_bytes(bytes(datos))
    _alterar_y_verificar(entorno, tmp_path, f, "HASH_MISMATCH")


def test_manifest_alterado(entorno, tmp_path):
    def f(m, copia, doc):
        doc["files"][0]["size"] += 1
        m.write_text(json.dumps(doc), encoding="utf-8")
    _alterar_y_verificar(entorno, tmp_path, f, "MANIFEST_INVALID")

    def g(m, copia, doc):
        m.write_text("{roto", encoding="utf-8")
    _alterar_y_verificar(entorno, tmp_path / "g", g, "MANIFEST_INVALID")


@pytest.mark.parametrize("hostil", ["../fuera.txt", "inst_1/../../fuera.txt", "C:/Windows/x.txt", "/etc/x",
                                    "inst_1\\x.txt", "a:stream", "", "./a.txt"])
def test_ruta_hostil_en_manifest(entorno, tmp_path, hostil):
    def f(m, copia, doc):
        doc["files"][0]["path"] = hostil
        m.write_text(json.dumps(doc), encoding="utf-8")
    _alterar_y_verificar(entorno, tmp_path, f, "MANIFEST_INVALID")
    assert not (tmp_path / "fuera.txt").exists() and not (tmp_path.parent / "fuera.txt").exists()


def test_archivo_faltante_y_extra(entorno, tmp_path):
    def faltante(m, copia, doc):
        (copia / "vacio.txt").unlink()
    _alterar_y_verificar(entorno, tmp_path / "a", faltante, "FILE_MISSING")


def test_archivo_extra_inesperado(entorno, tmp_path):
    def extra(m, copia, doc):
        (copia / "inst_1" / "inyectado.docx").write_bytes(b"no estaba")
    _alterar_y_verificar(entorno, tmp_path, extra, "UNEXPECTED_FILE")


def test_enlace_hostil_en_origen_falla_cerrado(tmp_path):
    origen = _arbol(tmp_path / "documents")
    secreto = tmp_path / "fuera"
    secreto.mkdir()
    (secreto / "dato.txt").write_bytes(b"fuera de la raiz")
    _junction(origen / "inst_1" / "atajo", secreto)
    backups = tmp_path / "bk"
    backups.mkdir()
    rep = D.respaldar(origen, backups, entorno="desarrollo", now=NOW)
    assert rep["result"] == "FAIL" and rep["code"] == "HOSTILE_ENTRY", rep
    assert list(backups.iterdir()) == []  # nada publicado, ni temporales


def test_enlace_hostil_en_backup_o_destino(entorno, tmp_path):
    origen, backups, manifest, _ = entorno
    doc = json.loads(manifest.read_text(encoding="utf-8"))
    otro = tmp_path / "otro"
    otro.mkdir()
    _junction(backups / doc["backup_id"] / "inst_1" / "colado", otro)
    assert D.verificar(manifest).code == "HOSTILE_ENTRY"
    destino_link = tmp_path / "destino_link"
    _junction(destino_link, tmp_path / "otro")
    os.rmdir(backups / doc["backup_id"] / "inst_1" / "colado")
    assert D.restaurar(manifest, destino_link, backups_dir=backups.parent)["code"] == "TARGET_INVALID"


def test_archivo_que_cambia_durante_la_copia(tmp_path, monkeypatch):
    """El origen se modifica DE VERDAD mientras se copia (justo despues de escribir la copia): FAIL, nada publicado."""
    origen = _arbol(tmp_path / "documents")
    backups = tmp_path / "bk"
    backups.mkdir()
    victima = origen / "inst_2" / "respaldos" / "resolucion.pdf"
    real_fsync = os.fsync

    def fsync(fd):
        real_fsync(fd)
        original = ARCHIVOS["inst_2/respaldos/resolucion.pdf"]
        if os.fstat(fd).st_size == len(original) and victima.read_bytes() == original:  # copiando la victima
            with open(victima, "ab") as fh:
                fh.write(b" agregado durante la copia")
    monkeypatch.setattr(D.os, "fsync", fsync)
    rep = D.respaldar(origen, backups, entorno="desarrollo", now=NOW)
    monkeypatch.undo()
    assert rep["result"] == "FAIL" and rep["code"] == "SOURCE_CHANGED", rep
    assert list(backups.iterdir()) == []


def test_no_sobrescribe_un_backup_existente(entorno):
    origen, backups, manifest, _ = entorno
    rep = D.respaldar(origen, backups, entorno="desarrollo", now=NOW)
    assert rep["result"] == "FAIL" and rep["code"] == "TARGET_EXISTS"
    assert D.verificar(manifest).ok


def test_origen_y_destino_no_se_contienen(tmp_path):
    origen = _arbol(tmp_path / "documents")
    (origen / "bk").mkdir()
    assert D.respaldar(origen, origen / "bk", entorno="desarrollo", now=NOW)["code"] == "BACKUP_DIR_INVALID"
