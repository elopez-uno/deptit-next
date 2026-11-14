"""B11 — lector stdlib del encabezado + TOC de un archivo ``pg_dump --format=custom``.

Sirve como verificación INDEPENDIENTE de ``pg_restore --list`` (que es la verificación primaria del backup):

* ``read_archive``: encabezado (versión de archivo, base de origen, versiones de servidor/pg_dump) + entradas del TOC
  (tipo, nombre, sección, DDL).  Solo lee metadatos: nunca descomprime ni interpreta filas de datos.
* ``walk_data_blocks``: recorre la cadena de bloques de datos SOLO por sus encabezados de longitud (seek), y verifica
  que cada entrada ``TABLE DATA`` apunte a un bloque válido con su mismo ``dumpId`` y que el último bloque termine
  exactamente en EOF.  Un dump truncado, parcial o con bytes sobrantes falla.

Formato (``src/bin/pg_dump/pg_backup_archiver.c`` ReadHead/ReadToc, ``pg_backup_custom.c``): enteros = 1 byte de
signo + ``intSize`` bytes little-endian; strings = entero longitud (-1 = NULL) + bytes UTF-8; offsets = 1 byte de
estado + ``offSize`` bytes.  Versiones de archivo soportadas: 1.12 .. 1.16 (PostgreSQL 11 .. 18).  Una versión
posterior se rechaza (fail-closed): hay que extender este lector antes de aceptarla.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

MAGIC = b"PGDMP"
MIN_VERSION = (1, 12, 0)
MAX_VERSION = (1, 16, 0)
FORMAT_CUSTOM = 1
OFFSET_NOT_SET, OFFSET_SET, OFFSET_NO_DATA = 1, 2, 3
BLK_DATA, BLK_BLOBS = 1, 3
MAX_STRING = 256 * 1024 * 1024
MAX_TOC_ENTRIES = 1_000_000


class ArchiveError(ValueError):
    """El archivo no es un dump custom válido/soportado (o está truncado/corrupto)."""


@dataclass(frozen=True)
class TocEntry:
    dump_id: int
    desc: str
    tag: str
    namespace: Optional[str]
    section: int
    defn: str
    owner_present: bool
    deps: Tuple[str, ...]
    offset_state: int
    offset: int


@dataclass
class ArchiveInfo:
    version: Tuple[int, int, int]
    int_size: int
    off_size: int
    fmt: int
    compression: int
    dbname: Optional[str]
    server_version: Optional[str]
    pg_dump_version: Optional[str]
    entries: List[TocEntry] = field(default_factory=list)
    toc_end: int = 0
    file_size: int = 0

    @property
    def version_text(self) -> str:
        return ".".join(str(v) for v in self.version)

    def entries_of(self, desc: str) -> List[TocEntry]:
        return [e for e in self.entries if e.desc == desc]

    def table_names(self, namespace: str = "public") -> List[str]:
        return sorted(e.tag for e in self.entries if e.desc == "TABLE" and (e.namespace or "") == namespace)

    def summary(self) -> dict:
        kinds = {}
        for e in self.entries:
            kinds[e.desc] = kinds.get(e.desc, 0) + 1
        return {"archive_version": self.version_text, "dbname": self.dbname, "server_version": self.server_version,
                "pg_dump_version": self.pg_dump_version, "toc_entries": len(self.entries),
                "tables": len(self.table_names()), "entry_kinds": dict(sorted(kinds.items()))}


class _Reader:
    def __init__(self, fh, size):
        self.fh, self.size = fh, size
        self.int_size = 4
        self.off_size = 8

    def raw(self, n):
        if n < 0 or self.fh.tell() + n > self.size:
            raise ArchiveError("archivo truncado (lectura más allá de EOF)")
        data = self.fh.read(n)
        if len(data) != n:
            raise ArchiveError("archivo truncado")
        return data

    def byte(self):
        return self.raw(1)[0]

    def int(self):
        sign = self.byte()
        if sign not in (0, 1):
            raise ArchiveError("entero con signo inválido")
        value = int.from_bytes(self.raw(self.int_size), "little")
        return -value if sign else value

    def str(self):
        n = self.int()
        if n < 0:
            return None
        if n > MAX_STRING:
            raise ArchiveError("string de TOC demasiado largo")
        try:
            return self.raw(n).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ArchiveError(f"string de TOC no UTF-8: {exc}") from None

    def offset(self):
        state = self.byte()
        value = int.from_bytes(self.raw(self.off_size), "little")
        return state, value


def read_archive(path) -> ArchiveInfo:
    """Encabezado + TOC.  Levanta ``ArchiveError`` ante cualquier inconsistencia."""
    size = os.path.getsize(path)
    with open(path, "rb") as fh:
        r = _Reader(fh, size)
        if r.raw(5) != MAGIC:
            raise ArchiveError("no es un archivo pg_dump custom (magic PGDMP ausente)")
        vmaj, vmin = r.byte(), r.byte()
        vrev = r.byte() if (vmaj > 1 or (vmaj == 1 and vmin > 0)) else 0
        version = (vmaj, vmin, vrev)
        if not (MIN_VERSION <= version <= MAX_VERSION):
            raise ArchiveError(f"versión de archivo {vmaj}.{vmin}.{vrev} no soportada "
                               f"({'.'.join(map(str, MIN_VERSION))}..{'.'.join(map(str, MAX_VERSION))})")
        r.int_size = r.byte()
        r.off_size = r.byte()
        if r.int_size not in (4, 8) or r.off_size not in (4, 8):
            raise ArchiveError(f"intSize/offSize inválidos ({r.int_size}/{r.off_size})")
        fmt = r.byte()
        if fmt != FORMAT_CUSTOM:
            raise ArchiveError(f"formato {fmt} != custom")
        compression = r.byte() if version >= (1, 15, 0) else r.int()
        for _ in range(7):  # timestamp de creación (sec, min, hour, mday, mon, year, isdst)
            r.int()
        dbname = r.str()
        server_version = r.str()
        pg_dump_version = r.str()
        n = r.int()
        if n < 0 or n > MAX_TOC_ENTRIES:
            raise ArchiveError(f"cantidad de entradas de TOC inválida ({n})")
        entries = []
        for _ in range(n):
            dump_id = r.int()
            r.int()  # hadDumper
            r.str()  # tableoid
            r.str()  # oid
            tag = r.str()
            desc = r.str()
            section = r.int()
            defn = r.str()
            r.str()  # dropStmt
            r.str()  # copyStmt
            namespace = r.str()
            r.str()  # tablespace
            if version >= (1, 14, 0):
                r.str()  # tableam
            if version >= (1, 16, 0):
                r.int()  # relkind
            owner = r.str()
            r.str()  # withOids (legado)
            deps = []
            while True:
                d = r.str()
                if d is None:
                    break
                deps.append(d)
            state, off = r.offset()
            if state not in (OFFSET_NOT_SET, OFFSET_SET, OFFSET_NO_DATA):
                raise ArchiveError(f"estado de offset inválido en entrada {dump_id}")
            if desc is None or tag is None:
                raise ArchiveError(f"entrada {dump_id} sin tipo/nombre")
            entries.append(TocEntry(dump_id, desc, tag, namespace, section, defn or "", bool(owner), tuple(deps),
                                    state, off))
        toc_end = fh.tell()
    return ArchiveInfo(version, r.int_size, r.off_size, fmt, compression, dbname, server_version, pg_dump_version,
                       entries, toc_end, size)


def walk_data_blocks(path, info: ArchiveInfo) -> dict:
    """Verifica la cadena de bloques de datos sin decodificarlos.  Devuelve un resumen; ``ArchiveError`` si falla.

    Reglas: toda entrada con datos (``TABLE DATA``/``BLOBS``/``LARGE OBJECTS``) debe tener offset fijado (dump a
    archivo, no a stdout); cada offset apunta a un bloque cuyo tipo y ``dumpId`` coinciden; los bloques no se solapan;
    el último termina exactamente en EOF."""
    data_kinds = {"TABLE DATA", "BLOBS", "LARGE OBJECTS", "BLOB"}
    with_data = [e for e in info.entries if e.desc in data_kinds and e.offset_state != OFFSET_NO_DATA]
    unset = [e.dump_id for e in with_data if e.offset_state != OFFSET_SET]
    if unset:
        raise ArchiveError(f"{len(unset)} entradas de datos sin offset (dump no escrito a archivo seekable)")
    blocks = sorted(with_data, key=lambda e: e.offset)
    size = info.file_size
    with open(path, "rb") as fh:
        r = _Reader(fh, size)
        r.int_size, r.off_size = info.int_size, info.off_size
        prev_end = info.toc_end
        for e in blocks:
            if e.offset < prev_end or e.offset >= size:
                raise ArchiveError(f"offset de datos fuera de rango/solapado (dumpId {e.dump_id})")
            fh.seek(e.offset)
            kind = r.byte()
            if kind not in (BLK_DATA, BLK_BLOBS):
                raise ArchiveError(f"tipo de bloque inválido {kind} (dumpId {e.dump_id})")
            if r.int() != e.dump_id:
                raise ArchiveError(f"bloque con dumpId distinto al TOC (dumpId {e.dump_id})")

            def skip_chunks():
                while True:
                    length = r.int()
                    if length == 0:
                        return
                    if length < 0 or fh.tell() + length > size:
                        raise ArchiveError(f"chunk truncado/inválido (dumpId {e.dump_id})")
                    fh.seek(length, os.SEEK_CUR)

            if kind == BLK_DATA:
                skip_chunks()
            else:
                while True:
                    oid = r.int()
                    if oid == 0:
                        break
                    skip_chunks()
            prev_end = fh.tell()
        if blocks and prev_end != size:
            raise ArchiveError(f"{size - prev_end} bytes sobrantes/incompletos al final del dump")
        if not blocks and info.toc_end > size:
            raise ArchiveError("TOC más allá de EOF")
    return {"data_blocks": len(blocks), "end_offset": prev_end, "file_size": size}


def inspect_archive(path, required_tables=(), expected_dbname: Optional[str] = None) -> dict:
    """Verificación independiente completa: TOC + cadena de bloques + tablas requeridas + base de origen.
    Nunca levanta: devuelve ``{"ok": bool, "problems": [...], ...}``."""
    out = {"ok": False, "problems": []}
    try:
        info = read_archive(path)
        out.update(info.summary())
        out.update(walk_data_blocks(path, info))
    except (ArchiveError, OSError) as exc:
        out["problems"].append(f"{type(exc).__name__}: {exc}")
        return out
    tables = set(info.table_names())
    missing = sorted(t for t in required_tables if t not in tables)
    if missing:
        out["problems"].append(f"tablas críticas ausentes del dump: {missing}")
    if expected_dbname is not None and info.dbname != expected_dbname:
        out["problems"].append(f"base de origen del dump ({info.dbname!r}) != esperada ({expected_dbname!r})")
    out["missing_required_tables"] = missing
    out["ok"] = not out["problems"]
    return out
