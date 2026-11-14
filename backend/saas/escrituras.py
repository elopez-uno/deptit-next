"""Writers de Administración SaaS (B13-FIX02 l. 2931-3336, registro B10 ``legacy_write_actions.py`` l. 231-243).

Cada writer certificado hace UN COMMIT por ``get_auth_conn()`` (sin ámbito: global).  NEXT conserva ese COMMIT único
y mete DENTRO de su transacción las validaciones que el certificado leía en conexiones aparte (duplicados, cupo), con
el SUCCESS B12H en la misma transacción (``Unidad.commit``).  Ante cualquier excepción: ROLLBACK completo.

Hardening NEXT aprobado (D-AP1..D-AP7), además de la equivalencia:
- D-AP1/D-AP2: ``eliminar_institucion_auth`` / ``eliminar_departamento_auth`` solo borran entidades VACÍAS; la vaciedad
  se revalida en la misma transacción, con la fila bloqueada (``FOR UPDATE``), justo antes del DELETE.  Nunca hay
  DELETE en cascada esperado, ni archivos, carpetas o bases SQLite (D-AP3).
- D-AP4: departamento ∈ institución; misma regla rol/departamento en alta y edición; cupo al crear, activar y editar
  (institución bloqueada ``FOR UPDATE`` mientras se cuenta); nunca 0 superadmins activos (los superadmins activos se
  bloquean ``FOR UPDATE`` antes de contar); email duplicado con mensaje funcional.
- D-AP5: contraseña con ``auth.core.hash_password`` (PBKDF2 certificado) y política K4; jamás se registra.
- D-AP7: el ``entity_id`` de las altas es el id creado (``RETURNING``).

Estrategia de concurrencia (sin familia B12I: el certificado no tiene ninguna para SaaS):
- cupo: ``SELECT ... FROM instituciones WHERE id = %s FOR UPDATE`` serializa las altas/activaciones de una institución;
- último superadmin: ``SELECT id FROM app_usuarios WHERE rol='superadmin' AND estado='Activo' FOR UPDATE`` serializa
  bajas/degradaciones concurrentes (tras la espera, READ COMMITTED reevalúa la condición);
- vaciedad: la fila de la institución/departamento queda ``FOR UPDATE``; toda tabla con FK hacia ella necesita
  ``FOR KEY SHARE`` para insertar, así que una alta concurrente espera; las tablas sin FK solo se escriben desde una
  sesión que opere en esa institución/departamento, y el servicio rechaza el borrado si alguna sesión activa la usa;
- duplicados: UNIQUE de la base (email, nombre/slug) -> mensaje funcional certificado.
"""

from __future__ import annotations

import re
import secrets
from datetime import date, datetime
from typing import Any, Callable, Optional

from psycopg import errors as pg_errors
from psycopg.rows import dict_row

import audit
from auth import core
from investigacion.rules import _slugify

from . import lecturas as L
from . import textos as T

W_CREAR_INSTITUCION = "crear_institucion_auth"
W_CUPO = "actualizar_cupo_institucion"
W_COMERCIAL = "actualizar_comercial_institucion"
W_ESTADO_INSTITUCION = "cambiar_estado_institucion_auth"
W_CREAR_DEPARTAMENTO = "crear_departamento_auth"
W_ACTUALIZAR_DEPARTAMENTO = "actualizar_departamento_auth"
W_CREAR_USUARIO = "crear_usuario_auth"
W_ACTUALIZAR_USUARIO = "actualizar_usuario_auth"
W_ESTADO_USUARIO = "cambiar_estado_usuario_auth"
W_ELIMINAR_INSTITUCION = "eliminar_institucion_auth"
W_ELIMINAR_DEPARTAMENTO = "eliminar_departamento_auth"
W_ELIMINAR_USUARIO = "eliminar_usuario_auth"
WRITERS = (W_CREAR_INSTITUCION, W_CUPO, W_COMERCIAL, W_ESTADO_INSTITUCION, W_CREAR_DEPARTAMENTO,
           W_ACTUALIZAR_DEPARTAMENTO, W_CREAR_USUARIO, W_ACTUALIZAR_USUARIO, W_ESTADO_USUARIO, W_ELIMINAR_INSTITUCION,
           W_ELIMINAR_DEPARTAMENTO, W_ELIMINAR_USUARIO)

# --- mensajes certificados de los writers ----------------------------------------------------------------------
MSG_NOMBRE_INSTITUCION = "Indicá el nombre de la institución."
MSG_INSTITUCION_EXISTE = "Esa institución ya existe. No se creó nuevamente."
MSG_NOMBRE_DEPARTAMENTO = "Indicá el nombre del departamento."
MSG_DEPARTAMENTO_EXISTE = "Ese departamento ya existe para la institución seleccionada."
MSG_OTRO_DEPARTAMENTO = "Ya existe otro departamento con ese nombre en la misma institución."
MSG_DEPARTAMENTO_INEXISTENTE = "Departamento inexistente."
MSG_INSTITUCION_INEXISTENTE = "Institución inexistente."
MSG_MAIL = "Indicá el mail del usuario."
MSG_PASSWORD = "Indicá una contraseña provisoria."
MSG_CUENTA_EXISTE = "Ya existe una cuenta con ese mail. No se creó nuevamente."
MSG_CUPO = "La institución ya alcanzó el cupo de {max} usuarios activos."
MSG_SIN_INSTITUCION = "Los usuarios no superadmin deben tener institución."
MSG_AUTOELIMINAR = "No podés eliminar tu propio usuario mientras estás logueado."
MSG_USUARIOS_DEPARTAMENTO = ("No se puede eliminar porque hay usuarios asignados a este departamento. Primero reasigná "
                             "o eliminá esos usuarios.")
# --- mensajes NUEVOS de los hardenings aprobados -----------------------------------------------------------------
MSG_PASSWORD_LARGO = "La contraseña debe tener al menos {n} caracteres."
MSG_PASSWORD_PUBLICA = "La contraseña es una credencial pública conocida: elegí otra."
MSG_PASSWORD_MAIL = "La contraseña no puede ser igual al mail."
MSG_USUARIO_INEXISTENTE = "Usuario inexistente."
MSG_OTRA_CUENTA = "Ya existe otra cuenta con ese mail."  # D-AP4 (el certificado dejaba el error crudo de la base)
MSG_DEPARTAMENTO_AJENO = "El departamento seleccionado no pertenece a la institución del usuario."  # D-AP4
MSG_DEPARTAMENTO_NO_DISPONIBLE = "El departamento seleccionado no está disponible."
MSG_INSTITUCION_NO_DISPONIBLE = "La institución seleccionada no está disponible."
MSG_ULTIMO_SUPERADMIN = ("Debe quedar al menos un superadmin activo: no se puede desactivar, eliminar ni cambiar el rol "
                         "del último superadmin activo.")  # D-AP4
MSG_INSTITUCION_CON_DATOS = ("La institución contiene datos y no puede eliminarse ({detalle}). Para darla de baja "
                             "cambiá su acceso a \"Bloqueada\" o \"Suspendida\" en Suscripción / Comercial.")  # D-AP1
MSG_DEPARTAMENTO_CON_DATOS = ("El departamento contiene datos y no puede eliminarse ({detalle}). Para darlo de baja "
                              "cambiá su estado a \"Inactivo\" en Editar departamento.")  # D-AP2
MIN_PASSWORD_LENGTH = 12  # deptit_refactor/security/credentials.py l. 31
_FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class AuditoriaFallida(Exception):
    """El SUCCESS del COMMIT no pudo insertarse: el COMMIT se revirtió (B12H ``AUDIT_INSERT_FAILED``)."""


class Repo:
    """SQL de los writers sobre la transacción de la ``Unidad`` (cuenta las sentencias mutantes para B12H)."""

    def __init__(self, conn):
        self._conn = conn
        self.mutating_statements = 0
        self.created_id: Optional[int] = None

    def one(self, query: Any, params: Optional[list] = None) -> Optional[dict]:
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, params or [])
            return cur.fetchone()

    def all(self, query: Any, params: Optional[list] = None) -> list[dict]:
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, params or [])
            return list(cur.fetchall())

    def scalar(self, query: Any, params: Optional[list] = None) -> Any:
        with self._conn.cursor() as cur:
            cur.execute(query, params or [])
            row = cur.fetchone()
            return None if row is None else row[0]

    def write(self, query: Any, params: Optional[list] = None, *, returning: bool = False) -> Optional[int]:
        with self._conn.cursor() as cur:
            cur.execute(query, params or [])
            self.mutating_statements += 1
            if returning:
                self.created_id = int(cur.fetchone()[0])
                return self.created_id
            return cur.rowcount

    @property
    def conn(self):
        return self._conn


class Unidad:
    """Una operación B12H (un writer) con su ÚNICO COMMIT: cuerpo + SUCCESS en la misma transacción."""

    def __init__(self, transaction: Callable, op: audit.Operation, *, today: date, now: datetime, actor_user_id: int):
        self._transaction = transaction
        self.op = op
        self.today, self.now = today, now
        self.actor_user_id = actor_user_id
        self.audit_failed = False

    def commit(self, fn: Callable[[Repo], Any]) -> Any:
        if self.audit_failed:
            raise AuditoriaFallida("AUDIT_FAILED_EARLIER")
        repo = None
        with self._transaction() as conn:
            repo = Repo(conn)
            result = fn(repo)
            if repo.mutating_statements:
                if repo.created_id is not None:  # D-AP7: la entidad real creada
                    self.op.entity_id = audit.entity_value(repo.created_id)
                    self.op.entity_param = "id" if self.op.entity_id is not None else None
                meta = {"commit_seq": self.op.coupled_commits + 1, "mutating_statements": repo.mutating_statements,
                        "committing_writer": self.op.name}
                try:
                    audit.insert_on(conn, self.op.event(audit.OUTCOME_SUCCESS, audit.MODE_IN_TRANSACTION,
                                                        metadata=meta))
                except Exception as exc:
                    self.audit_failed = True
                    raise AuditoriaFallida(audit.error_code_of(exc)) from exc
        if repo is not None and repo.mutating_statements:
            self.op.coupled_commits += 1
        return result


# ------------------------------------------------------------------------------------------ validaciones puras
def _texto(valor: Any) -> str:
    return "" if valor is None else str(valor)


def problema_password_nueva(password: Any, email: Any = "") -> str:
    """``b13fix02/validation.problema_password_nueva`` (K4): 12 caracteres, no pública, distinta del mail."""
    pwd = "" if password is None else str(password)
    if len(pwd.strip()) < MIN_PASSWORD_LENGTH:
        return MSG_PASSWORD_LARGO.format(n=MIN_PASSWORD_LENGTH)
    if core.is_public_default_password(pwd) or core.is_public_default_password(pwd.strip()):
        return MSG_PASSWORD_PUBLICA
    mail = _texto(email).strip()
    if mail and pwd.strip().casefold() == mail.casefold():
        return MSG_PASSWORD_MAIL
    return ""


def fecha_iso(valor: Any) -> Optional[str]:
    """``_date_to_iso`` (extracted_batch04/fechas): vacío -> None; fecha -> 'AAAA-MM-DD'."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, (date, datetime)):
        return (valor.date() if isinstance(valor, datetime) else valor).isoformat()
    txt = str(valor).strip()[:10]
    if not _FECHA.match(txt):
        raise ValueError("La fecha de vencimiento no es válida.")
    datetime.strptime(txt, "%Y-%m-%d")
    return txt


def _hash(password: str) -> tuple[str, str]:
    """``_hash_password`` certificado (l. 1672): salt ``token_hex(16)`` + PBKDF2 de ``auth.core``.  6A-B1: formato
    versionado con las iteraciones actuales (``core.hash_password_actual``); el login verifica ambos formatos."""
    salt = secrets.token_hex(16)
    return salt, core.hash_password_actual(password, salt)


def _detalle(dep: dict) -> str:
    r = L.resumen_dependencias(dep)
    partes = []
    if r["usuarios"]:
        partes.append(f"{r['usuarios']} usuario(s)")
    if r["departamentos"]:
        partes.append(f"{r['departamentos']} departamento(s)")
    if r["registros"]:
        partes.append(f"{r['registros']} registro(s) en {r['tablas']} tabla(s)")
    return ", ".join(partes)


# ------------------------------------------------------------------------------------------ bloqueos y controles
def _institucion_lock(repo: Repo, institucion_id: int) -> Optional[dict]:
    return repo.one("SELECT id, nombre, estado, max_usuarios FROM instituciones WHERE id = %s FOR UPDATE",
                    [int(institucion_id)])


def _controlar_cupo(repo: Repo, institucion_id: int, excluir_usuario: Optional[int] = None) -> None:
    fila = _institucion_lock(repo, institucion_id)
    if fila is None:
        raise ValueError(MSG_INSTITUCION_INEXISTENTE)
    max_users = int(fila["max_usuarios"] or 0)
    activos = int(repo.scalar(
        "SELECT COUNT(*) FROM app_usuarios WHERE institucion_id = %s AND estado = 'Activo' AND rol <> 'superadmin' "
        "AND id <> %s", [int(institucion_id), int(excluir_usuario or 0)]) or 0)
    if activos >= max_users:
        raise ValueError(MSG_CUPO.format(max=max_users))


def _controlar_ultimo_superadmin(repo: Repo, usuario_id: int) -> None:
    """Bloquea a TODOS los superadmins activos y exige que quede al menos uno distinto de ``usuario_id``."""
    activos = [int(r["id"]) for r in repo.all(
        "SELECT id FROM app_usuarios WHERE rol = 'superadmin' AND estado = 'Activo' ORDER BY id FOR UPDATE")]
    if not [i for i in activos if i != int(usuario_id)]:
        raise ValueError(MSG_ULTIMO_SUPERADMIN)


def _departamento_del_usuario(repo: Repo, rol: str, institucion_id: Optional[int], departamento_id: Optional[int],
                              actual: Optional[int] = None) -> Optional[int]:
    """D-AP4: superadmin y coordinador sin departamento (regla de la edición certificada, ahora también en el alta);
    para el resto, si hay departamento debe existir, pertenecer a la institución y estar Activo (o ser el actual)."""
    if not departamento_id or rol in ("superadmin", "coordinador_institucional"):
        return None
    dep = repo.one("SELECT id, institucion_id, estado FROM departamentos WHERE id = %s", [int(departamento_id)])
    if dep is None:
        raise ValueError(MSG_DEPARTAMENTO_NO_DISPONIBLE)
    if institucion_id is None or int(dep["institucion_id"] or 0) != int(institucion_id):
        raise ValueError(MSG_DEPARTAMENTO_AJENO)
    if str(dep["estado"] or "") != "Activo" and int(departamento_id) != int(actual or 0):
        raise ValueError(MSG_DEPARTAMENTO_NO_DISPONIBLE)
    return int(departamento_id)


def _institucion_del_usuario(repo: Repo, rol: str, institucion_id: Optional[int],
                             actual: Optional[int] = None) -> Optional[int]:
    """Superadmin -> NULL (certificado).  Resto: existe y Activa (lo que ofrece la UI) o la actual del usuario."""
    if rol == "superadmin":
        return None
    if not institucion_id:
        raise ValueError(MSG_SIN_INSTITUCION)
    fila = repo.one("SELECT id, estado FROM instituciones WHERE id = %s", [int(institucion_id)])
    if fila is None:
        raise ValueError(MSG_INSTITUCION_INEXISTENTE)
    if str(fila["estado"] or "") != "Activa" and int(institucion_id) != int(actual or 0):
        raise ValueError(MSG_INSTITUCION_NO_DISPONIBLE)
    return int(institucion_id)


# ------------------------------------------------------------------------------------------ instituciones
def crear_institucion_auth(u: Unidad, nombre, max_usuarios, plan, observaciones="", fecha_vencimiento=None,
                           estado_pago="Activo", suscripcion="Activa", estado="Activa") -> int:
    nombre = str(nombre or "").strip()
    if not nombre:
        raise ValueError(MSG_NOMBRE_INSTITUCION)
    slug = _slugify(nombre)

    def body(repo: Repo) -> int:
        if repo.one("SELECT id FROM instituciones WHERE LOWER(TRIM(nombre)) = LOWER(TRIM(%s)) OR slug = %s LIMIT 1",
                    [nombre, slug]):
            raise ValueError(MSG_INSTITUCION_EXISTE)
        try:
            return repo.write(
                "INSERT INTO instituciones (nombre, slug, max_usuarios, estado, plan, fecha_alta, fecha_vencimiento, "
                "estado_pago, suscripcion, fecha_ultima_actualizacion_comercial, observaciones) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                [nombre, slug, int(max_usuarios), estado, plan, str(u.today), fecha_iso(fecha_vencimiento),
                 estado_pago, suscripcion, str(u.now), observaciones], returning=True)
        except pg_errors.UniqueViolation:
            raise ValueError(MSG_INSTITUCION_EXISTE) from None
    return u.commit(body)


def actualizar_cupo_institucion(u: Unidad, institucion_id, max_usuarios) -> None:
    def body(repo: Repo) -> None:
        if _institucion_lock(repo, institucion_id) is None:
            raise ValueError(MSG_INSTITUCION_INEXISTENTE)
        repo.write("UPDATE instituciones SET max_usuarios = %s WHERE id = %s", [int(max_usuarios), int(institucion_id)])
    u.commit(body)


def actualizar_comercial_institucion(u: Unidad, institucion_id, plan, max_usuarios, fecha_vencimiento, estado_pago,
                                     suscripcion, estado, observaciones="") -> None:
    venc = fecha_iso(fecha_vencimiento)

    def body(repo: Repo) -> None:
        if _institucion_lock(repo, institucion_id) is None:
            raise ValueError(MSG_INSTITUCION_INEXISTENTE)
        repo.write("UPDATE instituciones SET plan = %s, max_usuarios = %s, fecha_vencimiento = %s, estado_pago = %s, "
                   "suscripcion = %s, estado = %s, observaciones = %s, fecha_ultima_actualizacion_comercial = %s "
                   "WHERE id = %s",
                   [str(plan or "Institucional"), int(max_usuarios), venc, str(estado_pago or "Activo"),
                    str(suscripcion or "Activa"), str(estado or "Activa"), str(observaciones or ""), str(u.now),
                    int(institucion_id)])
    u.commit(body)


def cambiar_estado_institucion_auth(u: Unidad, institucion_id, estado) -> None:
    def body(repo: Repo) -> None:
        if _institucion_lock(repo, institucion_id) is None:
            raise ValueError(MSG_INSTITUCION_INEXISTENTE)
        repo.write("UPDATE instituciones SET estado = %s, fecha_ultima_actualizacion_comercial = %s WHERE id = %s",
                   [str(estado or "Activa"), str(u.now), int(institucion_id)])
    u.commit(body)


def eliminar_institucion_auth(u: Unidad, institucion_id, sesiones_operativas: Callable[[], int]) -> dict:
    """D-AP1: solo una institución VACÍA, revalidada con la fila bloqueada en la misma transacción del DELETE.
    Sin disco (D-AP3).  Si queda cualquier referencia, nada se borra."""
    iid = int(institucion_id)

    def body(repo: Repo) -> dict:
        fila = repo.one("SELECT id, nombre FROM instituciones WHERE id = %s FOR UPDATE", [iid])
        if fila is None:
            raise ValueError(MSG_INSTITUCION_INEXISTENTE)
        dep = L.dependencias_instituciones(repo.conn, [iid]).get(iid, {})
        if dep:
            raise ValueError(MSG_INSTITUCION_CON_DATOS.format(detalle=_detalle(dep)))
        if sesiones_operativas() > 0:
            raise ValueError("La institución está seleccionada como institución operativa en una sesión activa. "
                             "Cambiá la institución operativa antes de eliminarla.")
        borradas = repo.write("DELETE FROM instituciones WHERE id = %s", [iid])
        if borradas != 1:
            raise ValueError(MSG_INSTITUCION_INEXISTENTE)
        return {"nombre": str(fila["nombre"] or "")}
    return u.commit(body)


# ------------------------------------------------------------------------------------------ departamentos
def crear_departamento_auth(u: Unidad, institucion_id, nombre, observaciones="") -> int:
    nombre = str(nombre or "").strip()
    if not nombre:
        raise ValueError(MSG_NOMBRE_DEPARTAMENTO)
    slug = _slugify(nombre)

    def body(repo: Repo) -> int:
        inst = repo.one("SELECT id, estado FROM instituciones WHERE id = %s FOR SHARE", [int(institucion_id)])
        if inst is None or str(inst["estado"] or "") != "Activa":
            raise ValueError(MSG_INSTITUCION_NO_DISPONIBLE)  # la UI certificada solo ofrece instituciones Activas
        if repo.one("SELECT id FROM departamentos WHERE institucion_id = %s AND (LOWER(TRIM(nombre)) = LOWER(TRIM(%s)) "
                    "OR slug = %s) LIMIT 1", [int(institucion_id), nombre, slug]):
            raise ValueError(MSG_DEPARTAMENTO_EXISTE)
        try:
            return repo.write("INSERT INTO departamentos (institucion_id, nombre, slug, estado, observaciones) "
                              "VALUES (%s, %s, %s, 'Activo', %s) RETURNING id",
                              [int(institucion_id), nombre, slug, observaciones], returning=True)
        except pg_errors.UniqueViolation:
            raise ValueError(MSG_DEPARTAMENTO_EXISTE) from None
    return u.commit(body)


def actualizar_departamento_auth(u: Unidad, departamento_id, nombre, estado="Activo", observaciones="") -> None:
    """Nombre (y slug), estado y observaciones.  Sin renombrar/copiar bases SQLite (D-AP3)."""
    departamento_id = int(departamento_id)
    nombre = str(nombre or "").strip()
    if not nombre:
        raise ValueError(MSG_NOMBRE_DEPARTAMENTO)
    nuevo_slug = _slugify(nombre)

    def body(repo: Repo) -> None:
        actual = repo.one("SELECT id, institucion_id FROM departamentos WHERE id = %s FOR UPDATE", [departamento_id])
        if actual is None:
            raise ValueError(MSG_DEPARTAMENTO_INEXISTENTE)
        if repo.one("SELECT id FROM departamentos WHERE institucion_id = %s AND id <> %s AND "
                    "(LOWER(TRIM(nombre)) = LOWER(TRIM(%s)) OR slug = %s) LIMIT 1",
                    [int(actual["institucion_id"]), departamento_id, nombre, nuevo_slug]):
            raise ValueError(MSG_OTRO_DEPARTAMENTO)
        try:
            repo.write("UPDATE departamentos SET nombre = %s, slug = %s, estado = %s, observaciones = %s WHERE id = %s",
                       [nombre, nuevo_slug, str(estado or "Activo"), observaciones, departamento_id])
        except pg_errors.UniqueViolation:
            raise ValueError(MSG_OTRO_DEPARTAMENTO) from None
    u.commit(body)


def eliminar_departamento_auth(u: Unidad, departamento_id, sesiones_operativas: Callable[[], int]) -> None:
    """D-AP2: solo un departamento VACÍO (sin usuarios ni datos, con o sin FK, ni préstamos que lo nombren)."""
    did = int(departamento_id)

    def body(repo: Repo) -> None:
        if repo.one("SELECT id FROM departamentos WHERE id = %s FOR UPDATE", [did]) is None:
            raise ValueError(MSG_DEPARTAMENTO_INEXISTENTE)
        dep = L.dependencias_departamentos(repo.conn, [did]).get(did, {})
        if dep.get("app_usuarios"):
            raise ValueError(MSG_USUARIOS_DEPARTAMENTO)
        if dep:
            raise ValueError(MSG_DEPARTAMENTO_CON_DATOS.format(detalle=_detalle(dep)))
        if sesiones_operativas() > 0:
            raise ValueError("El departamento está seleccionado como departamento operativo en una sesión activa. "
                             "Cambiá el departamento operativo antes de eliminarlo.")
        if repo.write("DELETE FROM departamentos WHERE id = %s", [did]) != 1:
            raise ValueError(MSG_DEPARTAMENTO_INEXISTENTE)
    u.commit(body)


# ------------------------------------------------------------------------------------------ usuarios
def crear_usuario_auth(u: Unidad, institucion_id, departamento_id, nombre, email, rol, password, estado="Activo",
                       observaciones="") -> int:
    email = str(email or "").strip().lower()
    if not email:
        raise ValueError(MSG_MAIL)
    if not str(password or "").strip():
        raise ValueError(MSG_PASSWORD)
    problema = problema_password_nueva(password, email)
    if problema:
        raise ValueError(problema)

    def body(repo: Repo) -> int:
        if repo.one("SELECT id FROM app_usuarios WHERE LOWER(email) = LOWER(%s) LIMIT 1", [email]):
            raise ValueError(MSG_CUENTA_EXISTE)
        inst = _institucion_del_usuario(repo, rol, institucion_id)
        dep = _departamento_del_usuario(repo, rol, inst, departamento_id)
        if inst is not None and estado == "Activo":
            _controlar_cupo(repo, inst)
        salt, pwd_hash = _hash(str(password))
        try:
            return repo.write(
                "INSERT INTO app_usuarios (institucion_id, departamento_id, nombre, email, rol, salt, password_hash, "
                "estado, fecha_alta, observaciones) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                [inst, dep, str(nombre or "").strip(), email, rol, salt, pwd_hash, estado, str(u.today),
                 observaciones], returning=True)
        except pg_errors.UniqueViolation:
            raise ValueError(MSG_CUENTA_EXISTE) from None
    return u.commit(body)


def _usuario_lock(repo: Repo, usuario_id: int) -> dict:
    fila = repo.one("SELECT id, rol, estado, institucion_id, departamento_id FROM app_usuarios WHERE id = %s FOR UPDATE",
                    [int(usuario_id)])
    if fila is None:
        raise ValueError(MSG_USUARIO_INEXISTENTE)
    return fila


def _es_superadmin_activo(fila: dict) -> bool:
    return str(fila["rol"] or "") == "superadmin" and str(fila["estado"] or "") == "Activo"


def cambiar_estado_usuario_auth(u: Unidad, usuario_id, estado) -> None:
    def body(repo: Repo) -> None:
        fila = _usuario_lock(repo, usuario_id)
        if estado != "Activo" and _es_superadmin_activo(fila):
            _controlar_ultimo_superadmin(repo, int(usuario_id))
        if estado == "Activo" and str(fila["estado"] or "") != "Activo" and fila["rol"] != "superadmin" \
                and fila["institucion_id"] is not None:
            _controlar_cupo(repo, int(fila["institucion_id"]), excluir_usuario=int(usuario_id))  # D-AP4
        repo.write("UPDATE app_usuarios SET estado = %s WHERE id = %s", [estado, int(usuario_id)])
    u.commit(body)


def actualizar_usuario_auth(u: Unidad, usuario_id, institucion_id, departamento_id, nombre, email, rol, estado,
                            observaciones="", password="") -> None:
    usuario_id = int(usuario_id)
    rol, estado = str(rol), str(estado)
    email = str(email or "").strip().lower()
    if not email:
        raise ValueError(MSG_MAIL)
    if str(password or "").strip():
        problema = problema_password_nueva(password, email)
        if problema:
            raise ValueError(problema)

    def body(repo: Repo) -> None:
        fila = _usuario_lock(repo, usuario_id)
        if repo.one("SELECT id FROM app_usuarios WHERE LOWER(email) = LOWER(%s) AND id <> %s LIMIT 1",
                    [email, usuario_id]):
            raise ValueError(MSG_OTRA_CUENTA)
        if _es_superadmin_activo(fila) and (rol != "superadmin" or estado != "Activo"):
            _controlar_ultimo_superadmin(repo, usuario_id)
        inst = _institucion_del_usuario(repo, rol, institucion_id, actual=fila["institucion_id"])
        dep = _departamento_del_usuario(repo, rol, inst, departamento_id, actual=fila["departamento_id"])
        if inst is not None and estado == "Activo":
            _controlar_cupo(repo, inst, excluir_usuario=usuario_id)
        campos = [inst, dep, str(nombre or "").strip(), email, rol, estado, observaciones]
        try:
            if str(password or "").strip():
                salt, pwd_hash = _hash(str(password))
                repo.write("UPDATE app_usuarios SET institucion_id = %s, departamento_id = %s, nombre = %s, email = %s, "
                           "rol = %s, estado = %s, observaciones = %s, salt = %s, password_hash = %s WHERE id = %s",
                           campos + [salt, pwd_hash, usuario_id])
            else:
                repo.write("UPDATE app_usuarios SET institucion_id = %s, departamento_id = %s, nombre = %s, email = %s, "
                           "rol = %s, estado = %s, observaciones = %s WHERE id = %s", campos + [usuario_id])
        except pg_errors.UniqueViolation:
            raise ValueError(MSG_OTRA_CUENTA) from None
    u.commit(body)


def eliminar_usuario_auth(u: Unidad, usuario_id) -> None:
    usuario_id = int(usuario_id)
    if usuario_id == int(u.actor_user_id):
        raise ValueError(MSG_AUTOELIMINAR)

    def body(repo: Repo) -> None:
        fila = _usuario_lock(repo, usuario_id)
        if _es_superadmin_activo(fila):
            _controlar_ultimo_superadmin(repo, usuario_id)
        repo.write("DELETE FROM app_usuarios WHERE id = %s", [usuario_id])
    u.commit(body)


__all__ = [n for n in dir() if n.startswith("W_")] + ["Unidad", "AuditoriaFallida", "WRITERS"]
