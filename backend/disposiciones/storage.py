"""Almacenamiento documental de Disposiciones: variante NEXT de B12E (``deptit_refactor/b12e/document_isolation.py``).

Se portan las garantias funcionales certificadas, sin Streamlit ni la frontera B10 del entry (esa la hace el servicio):
* Raiz documental PERSISTENTE (decision D2; 6A-B1): ``DEPTIT_DOCUMENTS_DIR`` de la configuracion central
  (``settings.py``).  En desarrollo, si falta, ``<repo>/storage/documents`` (resuelta con pathlib, portable
  Windows/Linux); en preproduccion/produccion es obligatoria, absoluta, existente y con permisos.  La raiz es un
  parametro de construccion: los tests usan directorios temporales.  Nunca se usan rutas que lleguen del cliente.
* Estructura B12E: ``<raiz>/inst_<id>/plantillas/disposicion.docx`` (una plantilla por institucion) y
  ``<raiz>/inst_<id>/dep_<id>/disposiciones/<AAAAMMDD-HHMMSS>_<etiqueta>_<128 bits>.docx``.
* Toda ruta se arma desde la raiz + ids enteros + nombres generados por codigo; cada ruta se canonicaliza y debe quedar
  dentro de la raiz, sin enlaces/junctions intermedios.
* Historial: referencia ``b12e:inst_<i>/dep_<d>/disposiciones/<nombre>`` (no una ruta).  Las filas heredadas (ruta
  absoluta) son ``LEGACY_UNVERIFIED``: no se abren nunca (decision D5).
* Plantilla: temporal en el mismo directorio + fsync + re-validacion + ``os.replace``.  Salida: reserva exclusiva
  ``O_CREAT|O_EXCL`` + temporal + publicacion sobre la propia reserva; compensacion que borra solo lo publicado por
  ESTE intento (mismo sha256).
Los mensajes son los del certificado (``MESSAGES``) y nunca incluyen rutas del servidor.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import io
import os
import re
import secrets
import stat
import tempfile
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

import settings as app_settings
from auth.core import to_int_or_none as _to_int

CONFIG_ROOT = "DEPTIT_DOCUMENTS_DIR"
DEFAULT_ROOT = str(app_settings.DEFAULT_DOCUMENTS_DIR)
REF_PREFIX = "b12e:"
TEMPLATE_DIR = "plantillas"
TEMPLATE_FILENAME = "disposicion.docx"
OUTPUT_DIR = "disposiciones"
MAX_TEMPLATE_BYTES = 20 * 1024 * 1024
MAX_OUTPUT_BYTES = 50 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 256 * 1024 * 1024
MAX_ZIP_ENTRIES = 5000
MAX_ALLOCATION_ATTEMPTS = 8
MAX_HISTORY_IDS = 5000
DOCX_MAIN_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
WORDML_NS = b"http://schemas.openxmlformats.org/wordprocessingml/2006/main"

MESSAGES = {
    "TEMPLATE_MISSING": "La institución no tiene una plantilla Word de disposición configurada. Un usuario del "
                        "departamento o el superadmin (con la institución seleccionada) debe cargarla en Configuración.",
    "TEMPLATE_INVALID": "La plantilla Word configurada para la institución no es un .docx válido. Volvé a cargarla en "
                        "Configuración.",
    "DOCX_EXTENSION": "El archivo debe tener extensión .docx.",
    "DOCX_INVALID": "El archivo no es un documento Word (.docx) válido.",
    "DOCX_TOO_LARGE": "El documento Word supera el tamaño máximo permitido.",
    "DOCX_EMPTY": "El archivo está vacío.",
    "SCOPE_MISSING": "No hay un ámbito institucional/departamental verificado para esta operación.",
    "SCOPE_MISMATCH": "El ámbito de la sesión no coincide con el de la operación.",
    "SUPERADMIN_SELECTION_REQUIRED": "Seleccioná explícitamente la institución en la barra lateral antes de administrar "
                                     "su plantilla.",
    "ROLE_NOT_PERMITTED": "Tu rol no puede realizar esta operación sobre documentos institucionales.",
    "NO_AUTHORIZED_ACTOR": "La operación no tiene un actor autorizado.",
    "NOT_FOUND": "La disposición no existe en tu ámbito.",
    "LEGACY_UNVERIFIED": "Documento histórico anterior a B12E: su archivo está en el almacenamiento compartido heredado y "
                         "no puede verificarse que pertenezca a tu institución. Queda bloqueado hasta la migración "
                         "controlada (B13).",
    "OWNERSHIP_MISSING": "La disposición no tiene institución/departamento registrados: queda bloqueada.",
    "OWNERSHIP_MISMATCH": "El archivo no pertenece a la institución/departamento de la disposición.",
    "FILE_MISSING": "El archivo Word de esta disposición no está disponible en el almacenamiento institucional.",
    "PATH_REJECTED": "Ruta de documento rechazada.",
    "DB_UNAVAILABLE": "No se pudo verificar el documento porque la base de datos no está disponible. Reintentá más tarde.",
    "AUTH_UNAVAILABLE": "No se pudo verificar la sesión. Reintentá más tarde.",
    "SESSION_REVOKED": "La sesión ya no es válida. Ingresá nuevamente.",
    "STORAGE_ERROR": "No se pudo usar el almacenamiento institucional de documentos.",
    "OUTPUT_ALLOCATION_FAILED": "No se pudo reservar un nombre único para el documento generado.",
    "UNSUPPORTED_MODE": "Los documentos institucionales requieren el modo PostgreSQL.",
    "INVALID_ID": "Identificador de disposición inválido.",
}


class DocumentError(RuntimeError):
    """Error funcional B12E.  ``str()`` es un mensaje para el usuario: nunca incluye rutas del servidor."""

    def __init__(self, code: str, detail: str = ""):
        self.code = code
        self.detail = detail
        super().__init__(MESSAGES.get(code, "Operación de documentos rechazada.") + (f" [{code}]" if code else ""))


class DocumentPathError(DocumentError):
    pass


class DocxValidationError(DocumentError):
    pass


class DocumentAccessDenied(DocumentError):
    pass


class DocumentUnavailable(DocumentError):
    pass


# --- ganchos de prueba (inyeccion de fallos en puntos del protocolo) -------------------------------------------------
HOOKS: Dict[str, Callable[[], None]] = {}


def _hook(name: str) -> None:
    fn = HOOKS.get(name)
    if fn is not None:
        fn()


def _token() -> str:
    """128 bits del CSPRNG del sistema."""
    return secrets.token_hex(16)


# --- nombres y rutas ------------------------------------------------------------------------------------------------
_COMPONENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,159}$")
_WIN_RESERVED = frozenset({"con", "prn", "aux", "nul", *(f"com{i}" for i in range(10)), *(f"lpt{i}" for i in range(10))})
_OUTPUT_NAME_RE = re.compile(r"^\d{8}-\d{6}_[A-Za-z0-9_-]{1,60}_[0-9a-f]{32}\.docx$")
_OUTPUT_REF_RE = re.compile(r"^b12e:inst_([1-9][0-9]{0,17})/dep_([1-9][0-9]{0,17})/disposiciones/([^/\\]{1,200})$")


def positive_id(value: Any, what: str = "id") -> int:
    v = _to_int(value)
    if v is None or v <= 0:
        raise DocumentPathError("PATH_REJECTED", f"{what} inválido")
    return v


def check_component(name: Any) -> str:
    """Un unico componente generado por codigo: sin separadores, '..', unidad/UNC, vacios, reservados de Windows ni
    punto/espacio final."""
    if not isinstance(name, str):
        raise DocumentPathError("PATH_REJECTED", "componente no textual")
    if name in ("", ".", "..") or ".." in name or name.endswith((".", " ")):
        raise DocumentPathError("PATH_REJECTED", "componente inválido")
    if not _COMPONENT_RE.fullmatch(name):
        raise DocumentPathError("PATH_REJECTED", "componente inválido")
    if name.split(".")[0].lower() in _WIN_RESERVED:
        raise DocumentPathError("PATH_REJECTED", "nombre reservado")
    return name


def safe_label(text: Any, limit: int = 60) -> str:
    """Etiqueta ASCII [A-Za-z0-9_-] (sin partes de ruta del cliente)."""
    raw = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("ascii")
    raw = re.sub(r"[^A-Za-z0-9_-]+", "_", raw)
    raw = re.sub(r"_+", "_", raw).strip("_-")
    return raw[:limit].strip("_-") or "documento"


def template_components(inst: Any) -> List[str]:
    return [f"inst_{positive_id(inst, 'institución')}", TEMPLATE_DIR, TEMPLATE_FILENAME]


def output_dir_components(inst: Any, dep: Any) -> List[str]:
    return [f"inst_{positive_id(inst, 'institución')}", f"dep_{positive_id(dep, 'departamento')}", OUTPUT_DIR]


def check_output_name(name: Any) -> str:
    check_component(name)
    if not _OUTPUT_NAME_RE.fullmatch(name):
        raise DocumentPathError("PATH_REJECTED", "nombre de salida inválido")
    return name


def output_ref(inst: int, dep: int, name: str) -> str:
    check_output_name(name)
    return f"{REF_PREFIX}inst_{positive_id(inst)}/dep_{positive_id(dep)}/{OUTPUT_DIR}/{name}"


def template_ref(inst: int, sha256: str) -> str:
    """Valor informativo de ``plantilla_usada`` (nunca se usa como ruta)."""
    if not re.fullmatch(r"[0-9a-f]{64}", str(sha256 or "")):
        raise DocumentPathError("PATH_REJECTED", "sha256 inválido")
    return f"{REF_PREFIX}inst_{positive_id(inst)}/{TEMPLATE_DIR}/{TEMPLATE_FILENAME}#sha256={sha256}"


@dataclass(frozen=True)
class OutputRef:
    institution_id: int
    department_id: int
    name: str

    @property
    def ref(self) -> str:
        return output_ref(self.institution_id, self.department_id, self.name)


def is_b12e_ref(value: Any) -> bool:
    return isinstance(value, str) and value.startswith(REF_PREFIX)


def parse_output_ref(value: Any) -> OutputRef:
    """Referencia del historial -> (inst, dep, nombre) validados.  Lo que no sea una referencia B12E bien formada se
    rechaza: las rutas heredadas son ``LEGACY_UNVERIFIED`` y NUNCA se abren."""
    if not is_b12e_ref(value):
        raise DocumentAccessDenied("LEGACY_UNVERIFIED", "valor sin prefijo b12e:")
    m = _OUTPUT_REF_RE.fullmatch(value)
    if not m:
        raise DocumentPathError("PATH_REJECTED", "referencia B12E mal formada")
    inst, dep, name = int(m.group(1)), int(m.group(2)), m.group(3)
    check_output_name(name)
    return OutputRef(inst, dep, name)


def estado_documento(archivo_word: Any) -> str:
    """Estado del documento de una fila del historial, sin tocar el disco: ``B12E`` o ``LEGACY_UNVERIFIED``."""
    try:
        parse_output_ref(archivo_word)
        return "B12E"
    except DocumentAccessDenied:
        return "LEGACY_UNVERIFIED"
    except DocumentError:
        return "PATH_REJECTED"


def _is_link(path: str) -> bool:
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return False
    if stat.S_ISLNK(st.st_mode):
        return True
    if getattr(st, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
        return True
    isjunction = getattr(os.path, "isjunction", None)
    return bool(isjunction and isjunction(path))


def configured_root() -> str:
    """Raiz documental del entorno activo (``DEPTIT_DOCUMENTS_DIR``, validada al arrancar por ``settings``)."""
    return str(app_settings.get().documents_dir)


# D2: la raiz nunca puede ser (ni estar dentro de) un arbol protegido, el codigo del backend ni una ruta del sistema
# local actual (``settings.documents_dir_problem`` + ``DEPTIT_FORBIDDEN_DIRS``).
RAICES_PROHIBIDAS = app_settings.RAICES_PROTEGIDAS_WINDOWS
FRAGMENTOS_PROHIBIDOS = ("deptit_postgres",)


def _raiz_prohibida(path: str) -> bool:
    if app_settings.documents_dir_problem(Path(path)) is not None:
        return True
    return any(f in os.path.normcase(os.path.normpath(path)) for f in FRAGMENTOS_PROHIBIDOS)


class DocumentStorage:
    """Raiz del almacenamiento institucional.  Solo construye rutas desde componentes validados."""

    def __init__(self, root: Any):
        raw = os.fspath(root) if isinstance(root, (str, os.PathLike)) else ""
        if not raw or "\x00" in raw or not os.path.isabs(raw):
            raise DocumentPathError("STORAGE_ERROR", "la raíz de documentos debe ser una ruta absoluta")
        self.root = os.path.normpath(os.path.abspath(raw))
        if _raiz_prohibida(self.root):  # fail-closed, sin tocar el disco
            raise DocumentPathError("STORAGE_ERROR", "raíz documental no permitida en desarrollo")

    def path_for(self, components: Iterable[str]) -> str:
        parts = [check_component(c) for c in components]
        if not parts:
            raise DocumentPathError("PATH_REJECTED", "ruta vacía")
        return self.contained(os.path.join(self.root, *parts))

    def template_path(self, inst: Any) -> str:
        return self.path_for(template_components(inst))

    def output_dir(self, inst: Any, dep: Any) -> str:
        return self.path_for(output_dir_components(inst, dep))

    def output_path(self, ref: OutputRef) -> str:
        return self.path_for(output_dir_components(ref.institution_id, ref.department_id)
                             + [check_output_name(ref.name)])

    def contained(self, path: Any) -> str:
        """Ruta absoluta canonica DENTRO de la raiz, sin enlaces/junctions por debajo de la raiz."""
        try:
            raw = os.fspath(path)
        except TypeError:
            raise DocumentPathError("PATH_REJECTED", "ruta no textual") from None
        if not isinstance(raw, str) or not raw or "\x00" in raw:
            raise DocumentPathError("PATH_REJECTED", "ruta vacía o inválida")
        root = self.root
        p_abs = os.path.normpath(os.path.abspath(raw))
        n_root, n_path = os.path.normcase(root), os.path.normcase(p_abs)
        if n_path != n_root and not n_path.startswith(n_root.rstrip("\\/") + os.sep):
            raise DocumentPathError("PATH_REJECTED", "fuera de la raíz")
        rel = os.path.relpath(p_abs, root)
        parts = [] if rel == "." else rel.split(os.sep)
        if any(part in ("", ".", "..") for part in parts):
            raise DocumentPathError("PATH_REJECTED", "componente relativo")
        cur = root
        for part in parts:
            cur = os.path.join(cur, part)
            if _is_link(cur):
                raise DocumentPathError("PATH_REJECTED", "enlace/junction dentro del almacenamiento")
        real_root = os.path.realpath(root)
        expected = os.path.normcase(os.path.normpath(os.path.join(real_root, *parts))) if parts \
            else os.path.normcase(real_root)
        if os.path.normcase(os.path.realpath(p_abs)) != expected:
            raise DocumentPathError("PATH_REJECTED", "la ruta resuelta escapa de la raíz")
        return p_abs

    def ensure_dir(self, components: Iterable[str]) -> str:
        """Crea (si falta) un directorio interno, verificando cada nivel."""
        parts = [check_component(c) for c in components]
        cur = self.root
        os.makedirs(cur, exist_ok=True)
        for part in parts:
            cur = os.path.join(cur, part)
            self.contained(cur)
            try:
                os.mkdir(cur)
            except FileExistsError:
                pass
            self.contained(cur)
            if not os.path.isdir(cur):
                raise DocumentPathError("STORAGE_ERROR", "no es un directorio")
        return cur


# --- lectura segura -------------------------------------------------------------------------------------------------
def read_regular_file(storage: DocumentStorage, path: str, max_bytes: int) -> bytes:
    """Lee un archivo REGULAR dentro de la raiz (sin seguir enlaces; mismo archivo antes/despues de abrir)."""
    p = storage.contained(path)
    try:
        st = os.lstat(p)
    except FileNotFoundError:
        raise DocumentAccessDenied("FILE_MISSING", "no existe") from None
    if not stat.S_ISREG(st.st_mode) or _is_link(p):
        raise DocumentPathError("PATH_REJECTED", "no es un archivo regular")
    if st.st_size > max_bytes:
        raise DocxValidationError("DOCX_TOO_LARGE", f"{st.st_size} bytes")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(p, flags)
    with os.fdopen(fd, "rb") as fh:
        fst = os.fstat(fh.fileno())
        if (fst.st_dev, fst.st_ino) != (st.st_dev, st.st_ino) or not stat.S_ISREG(fst.st_mode):
            raise DocumentPathError("PATH_REJECTED", "el archivo cambió durante la apertura")
        data = fh.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise DocxValidationError("DOCX_TOO_LARGE", "creció durante la lectura")
    return data


# --- validacion DOCX ------------------------------------------------------------------------------------------------
def check_docx_filename(filename: Any) -> str:
    name = str(filename or "")
    base = re.split(r"[\\/]", name)[-1]
    if not base.lower().endswith(".docx") or len(base) <= 5:
        raise DocxValidationError("DOCX_EXTENSION")
    return base


def _zip_member_ok(name: str) -> bool:
    if not name or "\x00" in name or "\\" in name or name.startswith("/") or re.match(r"^[A-Za-z]:", name):
        return False
    return ".." not in name.split("/")


def validate_docx_bytes(data: Any, *, filename: Any = None, max_bytes: int = MAX_TEMPLATE_BYTES) -> dict:
    """DOCX estructuralmente valido (no por extension): ZIP integro (CRC), sin miembros peligrosos ni cifrados ni macros,
    ``[Content_Types].xml`` con ``/word/document.xml`` WordprocessingML, ``_rels/.rels`` y ``word/document.xml``."""
    if filename is not None:
        check_docx_filename(filename)
    if isinstance(data, memoryview):
        data = data.tobytes()
    if not isinstance(data, (bytes, bytearray)):
        raise DocxValidationError("DOCX_INVALID", "contenido no binario")
    data = bytes(data)
    if not data:
        raise DocxValidationError("DOCX_EMPTY")
    if len(data) > max_bytes:
        raise DocxValidationError("DOCX_TOO_LARGE", f"{len(data)} bytes")
    if not data.startswith(b"PK\x03\x04"):
        raise DocxValidationError("DOCX_INVALID", "no es un contenedor ZIP")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            infos = zf.infolist()
            names = [i.filename for i in infos]
            if not infos or len(infos) > MAX_ZIP_ENTRIES or len(set(names)) != len(names):
                raise DocxValidationError("DOCX_INVALID", "entradas ZIP inválidas")
            total = 0
            for info in infos:
                if not _zip_member_ok(info.filename) or info.flag_bits & 0x1:
                    raise DocxValidationError("DOCX_INVALID", "miembro inválido")
                total += int(info.file_size)
                if total > MAX_UNCOMPRESSED_BYTES:
                    raise DocxValidationError("DOCX_TOO_LARGE", "contenido descomprimido excesivo")
            lower = {n.lower() for n in names}
            if any(n.endswith("vbaproject.bin") for n in lower):
                raise DocxValidationError("DOCX_INVALID", "contiene macros")
            for required in ("[Content_Types].xml", "_rels/.rels", "word/document.xml"):
                if required not in names:
                    raise DocxValidationError("DOCX_INVALID", f"falta {required}")
            bad = zf.testzip()
            if bad is not None:
                raise DocxValidationError("DOCX_INVALID", "CRC inválido")
            ct = zf.read("[Content_Types].xml")
            if b"<!DOCTYPE" in ct.upper() or b"<!ENTITY" in ct.upper():
                raise DocxValidationError("DOCX_INVALID", "DTD no permitido")
            root = ET.fromstring(ct)
            main = [el.get("ContentType") for el in root
                    if el.tag.endswith("Override") and el.get("PartName") == "/word/document.xml"]
            if main != [DOCX_MAIN_CONTENT_TYPE]:
                raise DocxValidationError("DOCX_INVALID", "tipo de la parte principal")
            doc = zf.read("word/document.xml")
            if WORDML_NS not in doc[:4096] or b"document" not in doc[:4096]:
                raise DocxValidationError("DOCX_INVALID", "word/document.xml no es WordprocessingML")
    except DocxValidationError:
        raise
    except (zipfile.BadZipFile, zipfile.LargeZipFile, ET.ParseError, KeyError, ValueError, RuntimeError,
            NotImplementedError, EOFError, OSError) as exc:
        raise DocxValidationError("DOCX_INVALID", type(exc).__name__) from None
    return {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "entries": len(names)}


# --- escrituras -----------------------------------------------------------------------------------------------------
def _fsync_dir(directory: str) -> None:
    if os.name == "nt":  # Windows no permite fsync de directorios; os.replace ya es atomico en el mismo volumen
        return
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _unlink_quiet(path: Optional[str]) -> None:
    if path:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass


def atomic_replace_template(storage: DocumentStorage, inst: int, data: bytes) -> dict:
    """Reemplazo atomico: temporal del MISMO directorio (fsync), re-validacion del temporal y ``os.replace``.  Ante
    cualquier fallo el temporal se borra y la plantilla anterior queda intacta."""
    info = validate_docx_bytes(data)
    comps = template_components(inst)
    directory = storage.ensure_dir(comps[:-1])
    target = storage.path_for(comps)
    if os.path.lexists(target) and (_is_link(target) or not os.path.isfile(target)):
        raise DocumentPathError("PATH_REJECTED", "el destino de la plantilla no es un archivo regular")
    fd, tmp = tempfile.mkstemp(prefix=".b12e-tpl-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        _hook("template.after_temp_write")
        written = read_regular_file(storage, tmp, MAX_TEMPLATE_BYTES)
        if hashlib.sha256(written).hexdigest() != info["sha256"]:
            raise DocumentError("STORAGE_ERROR", "el temporal no coincide con lo validado")
        validate_docx_bytes(written)
        _hook("template.before_replace")
        os.replace(tmp, target)
        tmp = None
        _fsync_dir(directory)
    finally:
        _unlink_quiet(tmp)
    return info


@dataclass
class Reservation:
    institution_id: int
    department_id: int
    name: str
    path: str
    dev_ino: Tuple[int, int]

    @property
    def ref(self) -> str:
        return output_ref(self.institution_id, self.department_id, self.name)


def allocate_output(storage: DocumentStorage, inst: int, dep: int, label: Any, *, now: Optional[_dt.datetime] = None,
                    attempts: int = MAX_ALLOCATION_ATTEMPTS) -> Reservation:
    """Reserva EXCLUSIVA (``O_CREAT|O_EXCL``): marca de tiempo + etiqueta saneada + 128 bits aleatorios.  Nunca
    reutiliza ni reemplaza un archivo existente; agotados los intentos -> error (fail-closed)."""
    inst, dep = positive_id(inst), positive_id(dep)
    directory = storage.ensure_dir(output_dir_components(inst, dep))
    stamp = (now or _dt.datetime.now()).strftime("%Y%m%d-%H%M%S")
    lab = safe_label(label)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    for _ in range(max(1, int(attempts))):
        name = check_output_name(f"{stamp}_{lab}_{_token()}.docx")
        path = storage.contained(os.path.join(directory, name))
        try:
            fd = os.open(path, flags, 0o600)
        except FileExistsError:
            continue
        try:
            st = os.fstat(fd)
        finally:
            os.close(fd)
        return Reservation(inst, dep, name, path, (st.st_dev, st.st_ino))
    raise DocumentError("OUTPUT_ALLOCATION_FAILED", f"{attempts} colisiones")


def _reservation_intact(res: Reservation) -> bool:
    try:
        st = os.lstat(res.path)
    except FileNotFoundError:
        return False
    return stat.S_ISREG(st.st_mode) and (st.st_dev, st.st_ino) == res.dev_ino and st.st_size == 0


def release_reservation(res: Reservation) -> None:
    """Borra la reserva SOLO si sigue siendo la propia (vacia, mismo archivo)."""
    if _reservation_intact(res):
        _unlink_quiet(res.path)


def publish_output(storage: DocumentStorage, res: Reservation, render: Callable[[str], Any]) -> bytes:
    """``render(tmp)`` escribe el Word en un temporal propio del mismo directorio; se valida como DOCX y se publica sobre
    la PROPIA reserva (verificada).  Ante cualquier fallo: temporal y reserva se borran."""
    directory = os.path.dirname(res.path)
    storage.contained(directory)
    fd, tmp = tempfile.mkstemp(prefix=".b12e-gen-", suffix=".docx", dir=directory)
    os.close(fd)
    try:
        render(tmp)
        data = read_regular_file(storage, tmp, MAX_OUTPUT_BYTES)
        validate_docx_bytes(data, max_bytes=MAX_OUTPUT_BYTES)
        with open(tmp, "rb+") as fh:
            os.fsync(fh.fileno())
        _hook("output.before_publish")
        if not _reservation_intact(res):
            raise DocumentError("OUTPUT_ALLOCATION_FAILED", "la reserva cambió")
        os.replace(tmp, res.path)
        tmp = None
        _fsync_dir(directory)
        return data
    except BaseException:
        release_reservation(res)
        raise
    finally:
        _unlink_quiet(tmp)


def remove_published(storage: DocumentStorage, res: Reservation, expected_sha256: str) -> bool:
    """Compensacion: borra el Word recien publicado por ESTE intento (mismo contenido) si su fila no se guardo."""
    try:
        data = read_regular_file(storage, res.path, MAX_OUTPUT_BYTES)
    except DocumentError:
        return False
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        return False
    _unlink_quiet(res.path)
    return True


def zip_payloads(items: Iterable[Tuple[str, bytes]]) -> Tuple[bytes, int]:
    """ZIP en memoria (nivel 1: DOCX ya es ZIP).  Nombres saneados y unicos; contenido = bytes ya resueltos."""
    out, used, n = io.BytesIO(), set(), 0
    with zipfile.ZipFile(out, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=1) as zf:
        for label, data in items:
            base = safe_label(label, 120)
            name, k = f"{base}.docx", 2
            while name.lower() in used:
                name, k = f"{base}_{k}.docx", k + 1
            used.add(name.lower())
            zf.writestr(name, bytes(data))
            n += 1
    return (out.getvalue(), n) if n else (b"", 0)


def row_owner_check(row: dict, inst: int, dep: Optional[int]) -> OutputRef:
    """Fila (re-consultada por id) -> referencia validada: dueño no nulo, igual al ambito y a la referencia."""
    r_inst, r_dep = _to_int(row.get("institucion_id")), _to_int(row.get("departamento_id"))
    if r_inst is None or r_dep is None or r_inst <= 0 or r_dep <= 0:
        raise DocumentAccessDenied("OWNERSHIP_MISSING")
    if r_inst != inst or (dep is not None and r_dep != dep):
        raise DocumentAccessDenied("NOT_FOUND", "fila de otro ámbito")
    ref = parse_output_ref(row.get("archivo_word"))
    if (ref.institution_id, ref.department_id) != (r_inst, r_dep):
        raise DocumentAccessDenied("OWNERSHIP_MISMATCH")
    return ref


@dataclass
class DocumentPayload:
    data: bytes
    file_name: str
    ref: str
    mime: str = DOCX_MIME


def payload_for_row(storage: DocumentStorage, row: dict, inst: int, dep: Optional[int]) -> DocumentPayload:
    """``_payload`` B12E: dueño + referencia + archivo regular dentro de la raiz + DOCX valido."""
    ref = row_owner_check(row, inst, dep)
    data = read_regular_file(storage, storage.output_path(ref), MAX_OUTPUT_BYTES)
    validate_docx_bytes(data, max_bytes=MAX_OUTPUT_BYTES)
    return DocumentPayload(data, ref.name, ref.ref)


def template_status(storage: DocumentStorage, inst: int) -> dict:
    """Estado de la plantilla de la institucion (sin rutas del servidor)."""
    try:
        path = storage.template_path(inst)
        if not os.path.lexists(path):
            return {"status": "MISSING", "message": MESSAGES["TEMPLATE_MISSING"], "institucion_id": inst}
        data = read_regular_file(storage, path, MAX_TEMPLATE_BYTES)
        info = validate_docx_bytes(data)
        st = os.lstat(path)
        return {"status": "OK", "institucion_id": inst, "bytes": info["bytes"], "sha256_12": info["sha256"][:12],
                "actualizada": _dt.datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")}
    except DocumentUnavailable as exc:
        return {"status": "UNAVAILABLE", "message": str(exc)}
    except DocxValidationError:
        return {"status": "INVALID", "message": MESSAGES["TEMPLATE_INVALID"]}
    except DocumentError as exc:
        return {"status": "DENIED", "message": str(exc), "code": exc.code}


__all__ = [n for n in dir() if not n.startswith("_") or n in ("_hook", "_token", "_is_link")]
