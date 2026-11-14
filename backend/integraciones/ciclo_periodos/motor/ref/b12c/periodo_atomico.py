"""B12C — Crear período atómico (F-B09-04).

Crear período heredado (B12B) hacía 1 commit propio (cierre del Abierto + alta) y después O(N) commits más: el
movimiento de apertura, los vencimientos de concursadas, la copia de designaciones con sus movimientos, los vínculos
de actos, la renovación de investigación/extensión y la finalización del período anterior, cada uno con su propia
conexión.  El advisory lock transaccional se liberaba en el primer commit y ``periodo_anterior`` salía de la caché
de proceso (v199/v200).

B12C ejecuta la operación completa como UNA unidad de trabajo sobre UNA conexión física:

* ``TransactionUnit`` toma una sola conexión del pool.  Mientras está activa (``ContextVar``), el ``_pg_raw_conn``
  re-enlazado entrega a todo el código heredado un manejador NO propietario de esa misma conexión: ``commit()`` y
  ``close()`` quedan suprimidos (contados), ``rollback()`` invalida la unidad, y cualquier error SQL la envenena
  (semántica PostgreSQL: una transacción con error ya no puede confirmar).  Así el SQL heredado, el inyector de
  scope B12B y las reglas de negocio se ejecutan sin cambios, pero en una única transacción.
* El lock ``pg_advisory_xact_lock`` se toma dentro de esa transacción, antes de cualquier mutación, y se libera solo
  con el COMMIT o el ROLLBACK final.
* ``periodo_anterior`` se lee con SQL dentro de la transacción, después del lock (sin caché de proceso).  Las cachés
  versionadas v199/v200 reciben una versión única de la unidad: dentro de la transacción no se sirve ningún valor
  previo y lo leído no se reutiliza después.
* Las invalidaciones de caché heredadas (``invalidar_cache_rendimiento_v191``, ``limpiar_cache_comisiones_operativas``)
  se difieren y se ejecutan, en el mismo orden, solo después del COMMIT.  Ante un fallo se descartan.
* Los pasos cuyo código heredado silenciaba fallos de escrituras obligatorias tienen una variante B12C sin
  ``except/pass`` (vencimientos v268, copia v266, renovaciones de investigación/extensión).  La única fase opcional es
  la asociación documental posterior de la copia v266 (el código heredado declara que "la copia del período no debe
  fallar por una asociación documental posterior"): corre bajo SAVEPOINT y, si falla, se revierte completa y la
  creación continúa.
* Precondiciones antes de abrir la transacción (0 SQL de la operación si fallan): autorización B10 y backup B11 (los
  wrappers heredados siguen envolviendo igual) y scope institución/departamento verificado por B12B.

Solo modo PostgreSQL: en el modo SQLite legacy ``crear_periodo`` delega en el cuerpo heredado sin cambios.
"""
from __future__ import annotations

import contextlib
import contextvars
import functools
import itertools
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, List, MutableMapping, Optional

INSTALL_ATTR = "_b12c_period_atomic"
STATUS_FUNCTION_NAME = "estado_crear_periodo_b12c"
B10_GUARD_ATTR = "_b10_write_guard"
B10_SYSTEM_ATTR = "_b10_system_writer"
B11_GATE_ATTR = "_b11_backup_precondition"

_ACTIVE: contextvars.ContextVar = contextvars.ContextVar("deptit_b12c_unidad_crear_periodo", default=None)
_TOKENS = itertools.count(1)

# Puntos de prueba: cada función recibe (unidad, paso).  Vacío en producción; los tests inyectan fallos aquí.
CHECKPOINT_HOOKS: List[Callable[["TransactionUnit", str], None]] = []

STEPS = (
    "S0_bloqueo", "S1_duplicado", "S2_periodo_anterior", "S3_cierre_y_alta", "S4_movimiento_apertura",
    "S5_vencimientos", "S6_copia_designaciones", "S7_investigacion", "S8_extension", "S9_finalizacion",
)
OPTIONAL_PHASES = ("actos_v266_origen", "actos_v266_vinculos")

# ---------------------------------------------------------------------------------------------------- SQL heredado
# Copiado literalmente del cuerpo heredado; tests/test_batch12c_period_atomic.py lo compara con el entrypoint.
LOCK_SQL = "SELECT pg_advisory_xact_lock(hashtext(?))"
DUPLICADO_SQL = """
            SELECT id, nombre, estado
            FROM periodos
            WHERE (anio = ? AND semestre = ?)
               OR UPPER(TRIM(COALESCE(nombre, ''))) = UPPER(TRIM(?))
            ORDER BY id DESC
            LIMIT 1
            """
PERIODO_ABIERTO_SQL = """
        SELECT id, nombre, anio, semestre, fecha_inicio, fecha_fin, estado, observaciones
        FROM periodos
        WHERE estado = 'Abierto'
        ORDER BY id DESC
        LIMIT 1
    """
ULTIMO_PERIODO_SQL = (
    "\n        SELECT id, nombre, anio, semestre, fecha_inicio, fecha_fin, estado, observaciones\n"
    "        FROM periodos\n        ORDER BY anio DESC, semestre DESC, id DESC\n        LIMIT 1\n    "
)
CERRAR_ABIERTO_SQL = "UPDATE periodos SET estado = 'Cerrado' WHERE estado = 'Abierto'"
ALTA_PERIODO_SQL = """
            INSERT INTO periodos
            (nombre, anio, semestre, fecha_inicio, fecha_fin, estado, observaciones)
            VALUES (?, ?, ?, ?, ?, 'Abierto', ?)
            """
V268_PERIODO_SQL = "SELECT id,nombre,fecha_inicio,fecha_fin FROM periodos WHERE id=? LIMIT 1"
V268_CONCURSADAS_SQL = """
            SELECT d.id,d.cuil,d.cargo,d.dedicacion,d.horas,d.tipo_designacion,
                   d.fecha_desde,d.fecha_hasta,d.fecha_hasta_prevista,
                   d.fecha_finalizacion_efectiva,d.estado,
                   CASE
                     WHEN doc.apellido IS NOT NULL AND doc.nombres IS NOT NULL THEN doc.apellido || ', ' || doc.nombres
                     WHEN doc.nombre IS NOT NULL THEN doc.nombre
                     ELSE d.cuil
                   END AS nombre_completo
            FROM designaciones d
            LEFT JOIN docentes doc ON doc.cuil=d.cuil
            WHERE d.periodo_id=?
              AND UPPER(TRIM(COALESCE(d.tipo_designacion,'')))='CONCURSADO'
        """
V268_FINALIZAR_SQL = (
    "UPDATE designaciones SET estado='Finalizada' WHERE id=? AND UPPER(TRIM(COALESCE(estado,'Activa')))='ACTIVA'"
)
V268_EXISTE_MOVIMIENTO_SQL = """
                SELECT id FROM movimientos
                WHERE periodo_id=? AND TRIM(COALESCE(cuil,''))=TRIM(?)
                  AND LOWER(TRIM(COALESCE(tipo_movimiento,'')))=LOWER(TRIM(?))
                  AND (COALESCE(observaciones,'') LIKE ? OR COALESCE(detalle,'') LIKE ?)
                LIMIT 1
            """

_WRITE_RE = re.compile(r"^\s*(INSERT\s+INTO|UPDATE|DELETE\s+FROM|MERGE\s+INTO|CREATE|ALTER|DROP|TRUNCATE)\s+"
                       r"(?:TABLE\s+|INDEX\s+|UNIQUE\s+INDEX\s+)?(?:IF\s+(?:NOT\s+)?EXISTS\s+)?\"?([A-Za-z_][\w.]*)?",
                       re.I)
_TX_CONTROL_RE = re.compile(r"^\s*(COMMIT|ROLLBACK|BEGIN|START\s+TRANSACTION|END|SAVEPOINT|RELEASE)\b", re.I)


class AtomicPeriodError(RuntimeError):
    """Base de los errores B12C."""


class PeriodScopeError(AtomicPeriodError):
    """El scope institución/departamento no está verificado: Crear período no abre la transacción."""


class TransactionAborted(AtomicPeriodError):
    """La unidad recibió un error (aunque el código heredado lo haya silenciado): solo puede revertirse."""


class NestedTransactionError(AtomicPeriodError):
    """Crear período dentro de otra unidad, o control transaccional manual dentro de la unidad."""


class InstallError(RuntimeError):
    """La instalación B12C no coincide con el namespace esperado (fail-closed en el arranque)."""


# ---------------------------------------------------------------------------------------------------- traza
@dataclass
class UnitTrace:
    token: int
    outcome: str = "open"
    steps: List[str] = field(default_factory=list)
    statements: int = 0
    writes: List[tuple] = field(default_factory=list)  # (paso, verbo, tabla)
    lock_key: Optional[str] = None
    lock_statement: Optional[int] = None
    first_write_statement: Optional[int] = None
    connections_opened: int = 0
    shared_handles: int = 0
    commits: int = 0
    rollbacks: int = 0
    suppressed_commits: int = 0
    suppressed_closes: int = 0
    nested_rollbacks: int = 0
    deferred: List[str] = field(default_factory=list)
    deferred_run: List[str] = field(default_factory=list)
    deferred_failed: List[str] = field(default_factory=list)
    optional_skipped: List[tuple] = field(default_factory=list)
    schema_preparation: List[tuple] = field(default_factory=list)
    periodo_anterior_fuente: str = ""
    poison: str = ""
    error: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def active_unit() -> Optional["TransactionUnit"]:
    return _ACTIVE.get()


# ---------------------------------------------------------------------------------------------------- conexión
class _GuardedCursor:
    """Cursor de la conexión de la unidad: registra cada sentencia y envenena la unidad ante cualquier error."""

    def __init__(self, unit: "TransactionUnit", cursor):
        self._unit = unit
        self._cursor = cursor

    def execute(self, sql, params=None):
        self._unit._before_statement(sql)
        try:
            out = self._cursor.execute(sql) if params is None else self._cursor.execute(sql, params)
        except BaseException as exc:
            self._unit._poison(exc, sql)
            raise
        return out

    def executemany(self, sql, seq):
        self._unit._before_statement(sql)
        try:
            return self._cursor.executemany(sql, seq)
        except BaseException as exc:
            self._unit._poison(exc, sql)
            raise

    def __getattr__(self, name):
        return getattr(self._cursor, name)

    def __iter__(self):
        return iter(self._cursor)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            self._cursor.close()
        except Exception:
            pass
        return False


class _SharedRawConnection:
    """Manejador NO propietario de la conexión de la unidad.  ``commit``/``close`` suprimidos, ``rollback`` invalida."""

    def __init__(self, unit: "TransactionUnit"):
        self._unit = unit

    def cursor(self, *args, **kwargs):
        return _GuardedCursor(self._unit, self._unit._raw_connection().cursor(*args, **kwargs))

    def commit(self):
        self._unit._suppressed_commit()

    def rollback(self):
        self._unit._nested_rollback()

    def close(self, *args, **kwargs):
        self._unit._suppressed_close()

    @property
    def closed(self):
        return 0 if self._unit.state == "active" else 1

    def __getattr__(self, name):
        return getattr(self._unit._raw_connection(), name)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            self._unit._poison(exc, "<with conexión>")
        return False


class TransactionUnit:
    """Una transacción, una conexión física, un lock: todo o nada."""

    def __init__(self, open_raw: Callable[[], Any]):
        self._open_raw = open_raw
        self._raw = None
        self._token = None
        self.state = "new"
        self.poison: Optional[BaseException] = None
        self.trace = UnitTrace(token=next(_TOKENS))
        self._epoch = 0  # sube con cada escritura y cada rollback a savepoint; nunca se reutiliza
        self._deferred: List[tuple] = []
        self._current_step = "S0_bloqueo"

    @property
    def cache_token(self) -> tuple:
        """Versión de caché de la unidad: única por transacción y por estado de datos dentro de ella."""
        return ("b12c_tx", self.trace.token, self._epoch)

    # -- ciclo de vida
    def __enter__(self):
        if _ACTIVE.get() is not None:
            raise NestedTransactionError("Crear período ya se está ejecutando en esta unidad de trabajo.")
        self._raw = self._open_raw()
        self.trace.connections_opened += 1
        self.state = "active"
        self._token = _ACTIVE.set(self)
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if self.state == "active":
                self._rollback(exc)
        finally:
            _ACTIVE.reset(self._token)
            self._close_raw()
        return False

    def _raw_connection(self):
        if self.state != "active" or self._raw is None:
            raise TransactionAborted("La unidad de Crear período ya no está activa.")
        return self._raw

    def shared_connection(self) -> _SharedRawConnection:
        self._raw_connection()
        self.trace.shared_handles += 1
        return _SharedRawConnection(self)

    def commit(self):
        """El ÚNICO commit real de Crear período."""
        if self.poison is not None:
            raise TransactionAborted(f"Crear período recibió un error y se revierte completo: {self.poison!r}")
        if self.trace.lock_statement is None:
            raise TransactionAborted("Crear período intentó confirmar sin el lock de la operación.")
        self._raw_connection().commit()
        self.trace.commits += 1
        self.state = "committed"
        self.trace.outcome = "committed"

    def _rollback(self, exc):
        self._deferred.clear()
        try:
            self._raw.rollback()
            self.trace.rollbacks += 1
        except Exception as rb_exc:  # conexión rota: se descarta al devolverla
            self.trace.error = f"{self.trace.error} | rollback falló: {rb_exc!r}".strip(" |")
            self._broken = True
        self.state = "rolled_back"
        self.trace.outcome = "rolled_back"
        if exc is not None and not self.trace.error:
            self.trace.error = repr(exc)

    def _close_raw(self):
        raw, self._raw = self._raw, None
        if raw is None:
            return
        if getattr(self, "_broken", False):
            try:
                raw.close(broken=True)
                return
            except TypeError:
                pass
        raw.close()

    # -- sentencias
    def _before_statement(self, sql):
        if self.state != "active":
            raise TransactionAborted("La unidad de Crear período ya no está activa.")
        if self.poison is not None:
            raise TransactionAborted(f"Transacción de Crear período abortada por un error previo: {self.poison!r}")
        text = str(sql or "")
        if _TX_CONTROL_RE.match(text):
            exc = NestedTransactionError(f"control transaccional manual dentro de Crear período: {text.strip()[:40]}")
            self._poison(exc, text)
            raise exc
        self.trace.statements += 1
        if "pg_advisory_xact_lock" in text and self.trace.lock_statement is None:
            self.trace.lock_statement = self.trace.statements
        m = _WRITE_RE.match(text)
        if m:
            self._epoch += 1
            verb = " ".join(m.group(1).upper().split()[:1])
            self.trace.writes.append((self._current_step, verb, (m.group(2) or "").lower()))
            if self.trace.first_write_statement is None:
                self.trace.first_write_statement = self.trace.statements

    def _poison(self, exc, sql):
        if self.poison is None:
            self.poison = exc
            self.trace.poison = f"{type(exc).__name__}: {str(sql or '').strip()[:80]}"

    def _suppressed_commit(self):
        self.trace.suppressed_commits += 1

    def _suppressed_close(self):
        self.trace.suppressed_closes += 1

    def _nested_rollback(self):
        self.trace.nested_rollbacks += 1
        self._poison(TransactionAborted("rollback parcial pedido por código heredado"), "<rollback anidado>")

    # -- pasos / fases
    def step(self, name: str):
        self._current_step = name

    def checkpoint(self, name: str):
        self.trace.steps.append(name)
        if self.poison is not None:
            raise TransactionAborted(f"{name}: la transacción recibió un error silenciado: {self.poison!r}")
        for hook in list(CHECKPOINT_HOOKS):
            hook(self, name)

    @contextlib.contextmanager
    def optional(self, label: str):
        """Fase opcional bajo SAVEPOINT: si falla, se revierte entera y la operación continúa."""
        if self.poison is not None:
            raise TransactionAborted(f"{label}: transacción abortada por un error previo: {self.poison!r}")
        name = f"b12c_{label}"
        previous_step, deferred_len, writes_len = self._current_step, len(self._deferred), len(self.trace.writes)
        self._current_step = label
        cur = self._raw_connection().cursor()
        try:
            cur.execute(f"SAVEPOINT {name}")
            failure = None
            try:
                yield
            except Exception as exc:
                failure = exc
            if failure is None and self.poison is not None:
                failure = self.poison
            if failure is None:
                cur.execute(f"RELEASE SAVEPOINT {name}")
            else:
                cur.execute(f"ROLLBACK TO SAVEPOINT {name}")
                cur.execute(f"RELEASE SAVEPOINT {name}")
                self._epoch += 1
                self.poison = None
                self.trace.poison = ""
                del self._deferred[deferred_len:]
                del self.trace.writes[writes_len:]
                self.trace.optional_skipped.append((label, f"{type(failure).__name__}: {failure}"[:200]))
        finally:
            self._current_step = previous_step
            try:
                cur.close()
            except Exception:
                pass

    # -- efectos posteriores
    def defer(self, name: str, fn: Callable, args, kwargs):
        self._deferred.append((name, fn, args, kwargs))
        self.trace.deferred.append(name)

    def run_deferred(self):
        if self.state != "committed":
            raise TransactionAborted("Las invalidaciones de Crear período solo corren después del COMMIT.")
        pending, self._deferred = self._deferred, []
        for name, fn, args, kwargs in pending:
            try:
                fn(*args, **kwargs)
                self.trace.deferred_run.append(name)
            except Exception as exc:  # los datos ya están confirmados; el heredado también lo silenciaba
                self.trace.deferred_failed.append(f"{name}: {exc!r}"[:200])


# ---------------------------------------------------------------------------------------------------- wrappers
def _mark(fn, original=None):
    setattr(fn, INSTALL_ATTR, True)
    if original is not None:
        fn._b12c_original = original
    return fn


def raw_connection_router(original: Callable[[], Any]) -> Callable[[], Any]:
    """Dentro de una unidad: la conexión de la unidad.  Fuera: el pool heredado, sin cambios."""

    def _pg_raw_conn():
        unit = _ACTIVE.get()
        if unit is None:
            return original()
        return unit.shared_connection()

    return _mark(_pg_raw_conn, original)


def isolate_scope_version(original: Callable[[], tuple]) -> Callable[[], tuple]:
    """Versión v199 (``_scope_rendimiento_v191``) única por unidad: las cachés v199/v282 no sirven valores previos."""

    @functools.wraps(original)
    def _scope_rendimiento_v191():
        out = original()
        unit = _ACTIVE.get()
        if unit is None:
            return out
        db_url, inst, dep, version = out
        version = tuple(version) if isinstance(version, tuple) else (version,)
        return db_url, inst, dep, version + (unit.cache_token,)

    return _mark(_scope_rendimiento_v191, original)


def isolate_dependency_version(original: Callable[..., tuple]) -> Callable[..., tuple]:
    """Versión v200 (``_version_dependencias_v200``) única por unidad."""

    @functools.wraps(original)
    def _version_dependencias_v200(*args, **kwargs):
        out = original(*args, **kwargs)
        unit = _ACTIVE.get()
        if unit is None:
            return out
        return tuple(out) + (unit.cache_token,)

    return _mark(_version_dependencias_v200, original)


def defer_until_commit(original: Callable, name: str) -> Callable:
    """Dentro de una unidad la invalidación se difiere al post-COMMIT; fuera, se ejecuta igual que antes."""

    @functools.wraps(original)
    def wrapper(*args, **kwargs):
        unit = _ACTIVE.get()
        if unit is None:
            return original(*args, **kwargs)
        unit.defer(name, original, args, kwargs)
        return None

    return _mark(wrapper, original)


# ---------------------------------------------------------------------------------------------------- pasos
def require_department_scope(g: MutableMapping[str, Any]) -> tuple:
    """Scope B12B verificado (institución + departamento) o ``PeriodScopeError`` antes de cualquier SQL de la operación."""
    inst = g["_pg_current_inst_id"]()
    dep = g["_pg_current_dep_id"]()
    if inst is None or dep is None:
        motivo = ""
        try:
            motivo = getattr(g["estado_scope_b12b"](), "status", "") or ""
        except Exception:
            motivo = "NO_VERIFICABLE"
        raise PeriodScopeError(
            "Crear período requiere un ámbito institución/departamento verificado. "
            f"No se ejecutó ninguna escritura. [B12C/B12B {motivo or 'SIN_DEPARTAMENTO'}]"
        )
    return inst, dep


SCHEMA_PREPARATION = (
    "asegurar_esquema_investigacion_separado",
    "asegurar_esquema_extension_separado",
    "asegurar_esquema_actos_administrativos_v266",
)


def prepare_schema(g: MutableMapping[str, Any], trace: UnitTrace):
    """DDL idempotente heredado (con flag de sesión) ANTES de la transacción: no retiene locks de DDL dentro de ella.
    Si falla, el mismo helper vuelve a correr dentro de la transacción y su error la revierte."""
    for name in SCHEMA_PREPARATION:
        try:
            g[name]()
            trace.schema_preparation.append((name, "ok"))
        except Exception as exc:
            trace.schema_preparation.append((name, f"reintento dentro de la transacción: {type(exc).__name__}"))


def periodo_anterior_en_transaccion(g: MutableMapping[str, Any], conn) -> Optional[dict]:
    """``get_periodo_abierto() or get_ultimo_periodo()`` con el mismo SQL, dentro de la transacción y sin caché."""
    pd = g["pd"]
    df = pd.read_sql(PERIODO_ABIERTO_SQL, conn)
    if not df.empty:
        return df.iloc[0].to_dict()
    df = pd.read_sql(ULTIMO_PERIODO_SQL, conn)
    if df.empty:
        return None
    return df.iloc[0].to_dict()


def vencimientos_concursados(g: MutableMapping[str, Any], periodo_id) -> int:
    """Variante B12C de ``sincronizar_vencimientos_concursados_v268``: mismo SQL y mismas reglas, sobre la conexión de
    la unidad, sin commits propios y SIN silenciar la baja de comisiones ni la sincronización de cargos."""
    pd, safe_date, date = g["pd"], g["safe_date"], g["date"]
    try:
        pid = int(periodo_id)
    except Exception:
        return 0
    conn = g["get_conn"]()
    dfp = pd.read_sql(V268_PERIODO_SQL, conn, params=[pid])
    if dfp.empty:
        return 0
    per = dfp.iloc[0].to_dict()
    inicio = safe_date(per.get("fecha_inicio"), None)
    fin = safe_date(per.get("fecha_fin"), None)
    hoy = date.today()
    df = pd.read_sql(V268_CONCURSADAS_SQL, conn, params=[pid])
    if df.empty:
        return 0

    pendientes = []
    for _, r in df.iterrows():
        desde = safe_date(r.get("fecha_desde"), None)
        if safe_date(r.get("fecha_finalizacion_efectiva"), None) is not None:
            continue
        hasta = safe_date(r.get("fecha_hasta_prevista"), None)
        if hasta is None:
            hasta = safe_date(r.get("fecha_hasta"), None)
        if hasta is None or hasta >= hoy:
            continue
        if fin is not None and hasta > fin:
            continue
        if inicio is not None and hasta < inicio:
            continue
        if desde is not None and hasta < desde:
            continue
        pendientes.append((r.to_dict(), hasta))

    creados = 0
    c = conn.cursor()
    for r, hasta in pendientes:
        did = int(r.get("id"))
        c.execute(V268_FINALIZAR_SQL, (did,))
        g["_finalizar_comisiones_si_sin_designacion_docente_v214"](str(r.get("cuil") or ""), pid, hasta, did)
        g["sincronizar_cargos_asignaciones_docente_periodo"](str(r.get("cuil") or ""), pid)

        marcador = f"[designacion_id={did}]"
        ex = pd.read_sql(V268_EXISTE_MOVIMIENTO_SQL, conn, params=[
            pid, str(r.get("cuil") or ""), "Finalización automática por vencimiento de designación",
            f"%{marcador}%", f"%{marcador}%",
        ])
        if not ex.empty:
            continue
        horas = float(pd.to_numeric(r.get("horas"), errors="coerce") or 0)
        detalle = (
            f"Vencimiento natural de designación concursada: {r.get('cargo','')} - "
            f"{r.get('dedicacion','')} - {horas:g} hs - Concursado. "
            f"Fecha de vencimiento: {hasta.isoformat()}. {marcador}"
        )
        g["registrar_movimiento"](
            "Finalización automática por vencimiento de designación",
            str(r.get("cuil") or ""), str(r.get("nombre_completo") or ""),
            detalle,
            f"Baja automática por vencimiento contractual de la designación concursada. {marcador}",
            pid, horas_variacion=-abs(horas), fecha_movimiento=hasta,
        )
        creados += 1
    if pendientes:
        g["invalidar_cache_rendimiento_v191"]("vencimientos concursados v268")
        g["limpiar_cache_comisiones_operativas"]()
    return creados


def _vincular_actos_copia(g: MutableMapping[str, Any], origen_v266, periodo_destino_id):
    """Asociación documental posterior de la copia v266 (cuerpo heredado, sin el ``except: pass`` que lo envolvía)."""
    pd, _clave_cuil = g["pd"], g["_clave_cuil"]
    destino_v266 = g["get_designaciones"](int(periodo_destino_id))
    if isinstance(origen_v266, pd.DataFrame) and not origen_v266.empty and isinstance(destino_v266, pd.DataFrame) and not destino_v266.empty:
        orig_conc = origen_v266[origen_v266.get("tipo_designacion", pd.Series(index=origen_v266.index,dtype=str)).fillna("").astype(str).str.strip().str.casefold().eq("concursado")].copy()
        dest_conc = destino_v266[destino_v266.get("tipo_designacion", pd.Series(index=destino_v266.index,dtype=str)).fillna("").astype(str).str.strip().str.casefold().eq("concursado")].copy()
        for _, dd in dest_conc.iterrows():
            clave = _clave_cuil(dd.get("cuil")) or str(dd.get("cuil") or "").strip()
            candidatos = orig_conc[orig_conc.get("cuil",pd.Series(index=orig_conc.index,dtype=str)).fillna("").astype(str).map(lambda x:_clave_cuil(x) or str(x).strip()).eq(clave)].copy()
            for col in ["cargo","dedicacion","tipo_designacion"]:
                if col in candidatos.columns:
                    candidatos = candidatos[candidatos[col].fillna("").astype(str).str.strip().str.casefold().eq(str(dd.get(col) or "").strip().casefold())]
            candidatos = candidatos[candidatos.get("acto_documento_id",pd.Series(index=candidatos.index,dtype=object)).notna()] if not candidatos.empty else candidatos
            ids_doc = pd.to_numeric(candidatos.get("acto_documento_id",pd.Series(dtype=float)),errors="coerce").dropna().astype(int).unique().tolist() if not candidatos.empty else []
            if len(ids_doc)==1:
                g["vincular_acto_designacion_v266"](int(dd.get("id")), int(ids_doc[0]))
        # Vincula las renovaciones automáticas solo cuando el CUIL quedó con un único acto de designación.
        movs = g["get_movimientos_designaciones_periodo_v266"](int(periodo_destino_id))
        if isinstance(movs,pd.DataFrame) and not movs.empty:
            renov = movs[movs["tipo_movimiento"].fillna("").astype(str).eq("Renovación automática de designación")].copy()
            destino_ref = g["get_designaciones"](int(periodo_destino_id))
            for _, mm in renov.iterrows():
                clave = _clave_cuil(mm.get("cuil")) or str(mm.get("cuil") or "").strip()
                ds = destino_ref[destino_ref.get("cuil",pd.Series(index=destino_ref.index,dtype=str)).fillna("").astype(str).map(lambda x:_clave_cuil(x) or str(x).strip()).eq(clave)].copy()
                ids_doc = pd.to_numeric(ds.get("acto_documento_id",pd.Series(dtype=float)),errors="coerce").dropna().astype(int).unique().tolist() if not ds.empty else []
                if len(ids_doc)==1 and pd.isna(mm.get("acto_documento_id")):
                    g["vincular_acto_movimiento_v266"](int(mm.get("id")),int(ids_doc[0]))


def copiar_designaciones_v266(g: MutableMapping[str, Any], unit: TransactionUnit, periodo_origen_id, periodo_destino_id,
                              nombre_destino, copiar_no_concursadas=True):
    """Variante B12C de ``copiar_designaciones_periodo`` (v266): la copia y sus movimientos son obligatorios; la
    asociación documental posterior es la única fase opcional y corre bajo SAVEPOINT."""
    pd = g["pd"]
    origen_v266 = pd.DataFrame()
    if periodo_origen_id is not None:
        with unit.optional("actos_v266_origen"):
            origen_v266 = g["get_designaciones"](int(periodo_origen_id))
    resultado = g["_copiar_designaciones_periodo_pre_v266"](
        periodo_origen_id, periodo_destino_id, nombre_destino,
        copiar_no_concursadas=copiar_no_concursadas
    )
    g["invalidar_cache_rendimiento_v191"]("copia de designaciones v266")
    with unit.optional("actos_v266_vinculos"):
        _vincular_actos_copia(g, origen_v266, periodo_destino_id)
    return resultado


def crear_periodo_atomico(g: MutableMapping[str, Any], open_raw: Callable[[], Any], record: Callable[[UnitTrace], None],
                          anio, semestre, copiar_anterior=True, observaciones=""):
    anio = int(anio)
    semestre = int(semestre)
    nombre = g["nombre_periodo"](anio, semestre)
    fecha_inicio, fecha_fin = g["fechas_periodo"](anio, semestre)

    unit = TransactionUnit(open_raw)
    record(unit.trace)
    try:
        require_department_scope(g)
    except PeriodScopeError as exc:
        unit.trace.outcome = "denied_scope"
        unit.trace.error = str(exc)
        raise
    prepare_schema(g, unit.trace)

    with unit:
        conn = g["get_conn"]()
        c = conn.cursor()
        unit.step("S0_bloqueo")
        clave_bloqueo = (
            f"deptit_crear_periodo:{g['_pg_current_inst_id']() or 0}:"
            f"{g['_pg_current_dep_id']() or 0}"
        )
        c.execute(LOCK_SQL, (clave_bloqueo,))
        unit.trace.lock_key = clave_bloqueo
        unit.checkpoint("S0_bloqueo")

        unit.step("S1_duplicado")
        c.execute(DUPLICADO_SQL, (anio, semestre, nombre))
        existente = c.fetchone()
        if existente:
            unit.trace.outcome = "duplicate"
            raise g["PeriodoDuplicadoError"](
                f"El período {nombre} ya está registrado. No se creó ningún período nuevo "
                "ni se modificó el período abierto."
            )
        unit.checkpoint("S1_duplicado")

        unit.step("S2_periodo_anterior")
        periodo_anterior = periodo_anterior_en_transaccion(g, conn)
        unit.trace.periodo_anterior_fuente = "sql_en_transaccion_tras_lock"
        unit.checkpoint("S2_periodo_anterior")

        unit.step("S3_cierre_y_alta")
        c.execute(CERRAR_ABIERTO_SQL)
        c.execute(ALTA_PERIODO_SQL, (nombre, anio, semestre, fecha_inicio, fecha_fin, observaciones))
        nuevo_periodo_id = c.lastrowid
        unit.checkpoint("S3_cierre_y_alta")

        unit.step("S4_movimiento_apertura")
        g["registrar_movimiento"](
            "Apertura de período",
            "",
            "",
            f"Se creó el período {nombre} ({fecha_inicio} al {fecha_fin}).",
            observaciones,
            nuevo_periodo_id,
        )
        unit.checkpoint("S4_movimiento_apertura")

        unit.step("S5_vencimientos")
        if periodo_anterior is not None:
            vencimientos_concursados(g, periodo_anterior["id"])
        unit.checkpoint("S5_vencimientos")

        unit.step("S6_copia_designaciones")
        copiar_designaciones_v266(
            g, unit,
            periodo_anterior["id"] if periodo_anterior is not None else None,
            nuevo_periodo_id,
            nombre,
            copiar_no_concursadas=bool(copiar_anterior and periodo_anterior is not None),
        )
        unit.checkpoint("S6_copia_designaciones")

        if periodo_anterior is not None:
            unit.step("S7_investigacion")
            inv_copiadas = g["copiar_investigacion_vigente_periodo"](periodo_anterior["id"], nuevo_periodo_id, nombre)
            if inv_copiadas:
                g["registrar_movimiento"](
                    "Renovación automática de investigación",
                    "",
                    "",
                    f"Se renovaron {inv_copiadas} asignación/es de investigación vigentes en {nombre}.",
                    observaciones,
                    nuevo_periodo_id,
                )
            unit.checkpoint("S7_investigacion")

            unit.step("S8_extension")
            ext_copiadas = g["copiar_extension_vigente_periodo"](periodo_anterior["id"], nuevo_periodo_id, nombre)
            if ext_copiadas:
                g["registrar_movimiento"](
                    "Renovación automática de extensión",
                    "",
                    "",
                    f"Se renovaron {ext_copiadas} asignación/es de extensión vigentes en {nombre}.",
                    observaciones,
                    nuevo_periodo_id,
                )
            unit.checkpoint("S8_extension")

            unit.step("S9_finalizacion")
            g["finalizar_designaciones_activas_periodo"](
                periodo_anterior["id"],
                registrar=True,
                observaciones=f"Cierre automático generado al crear el período {nombre}.",
            )
            unit.checkpoint("S9_finalizacion")

        unit.commit()

    unit.run_deferred()
    return nuevo_periodo_id


# ---------------------------------------------------------------------------------------------------- instalación
REQUIRED_CALLABLES = (
    "crear_periodo", "_pg_raw_conn", "get_conn", "_pg_current_inst_id", "_pg_current_dep_id", "estado_scope_b12b",
    "_scope_rendimiento_v191", "_version_dependencias_v200", "invalidar_cache_rendimiento_v191",
    "limpiar_cache_comisiones_operativas", "_envolver_mutacion_rendimiento_v191", "nombre_periodo", "fechas_periodo",
    "PeriodoDuplicadoError", "registrar_movimiento", "safe_date", "_finalizar_comisiones_si_sin_designacion_docente_v214",
    "sincronizar_cargos_asignaciones_docente_periodo", "get_designaciones", "_copiar_designaciones_periodo_pre_v266",
    "get_movimientos_designaciones_periodo_v266", "vincular_acto_designacion_v266", "vincular_acto_movimiento_v266",
    "_clave_cuil", "copiar_investigacion_vigente_periodo", "copiar_extension_vigente_periodo",
    "finalizar_designaciones_activas_periodo",
) + SCHEMA_PREPARATION
REBOUND_NAMES = ("_pg_raw_conn", "_scope_rendimiento_v191", "_version_dependencias_v200",
                 "invalidar_cache_rendimiento_v191", "limpiar_cache_comisiones_operativas", "crear_periodo")


def install_period_atomic(namespace: MutableMapping[str, Any]) -> dict:
    """Re-enlaza ``crear_periodo`` (bajo el wrapper v191 heredado, re-aplicado igual) y los puntos de unidad de trabajo.

    Fail-closed: falta un nombre, ya instalado, o ``crear_periodo`` ya envuelto por B11/B10 (orden incorrecto)."""
    missing = sorted(n for n in REQUIRED_CALLABLES if not callable(namespace.get(n)))
    if missing or "pd" not in namespace or "date" not in namespace:
        raise InstallError(f"B12C: nombres ausentes del namespace: {missing[:8]}")
    if any(hasattr(namespace[n], INSTALL_ATTR) for n in REBOUND_NAMES) or STATUS_FUNCTION_NAME in namespace:
        raise InstallError("B12C: instalación duplicada")
    current = namespace["crear_periodo"]
    if any(hasattr(current, a) for a in (B10_GUARD_ATTR, B10_SYSTEM_ATTR, B11_GATE_ATTR)):
        raise InstallError("B12C: crear_periodo ya está envuelto por B11/B10; B12C debe instalarse antes")
    legacy = getattr(current, "__wrapped__", None)
    if not getattr(current, "_v191_perf_wrapped", False) or getattr(legacy, "__name__", "") != "crear_periodo":
        raise InstallError("B12C: crear_periodo no tiene la forma heredada (wrapper v191 sobre el cuerpo original)")

    open_raw = namespace["_pg_raw_conn"]
    holder: dict = {"trace": None}

    def _record(trace: UnitTrace):
        holder["trace"] = trace

    namespace["_pg_raw_conn"] = raw_connection_router(open_raw)
    namespace["_scope_rendimiento_v191"] = isolate_scope_version(namespace["_scope_rendimiento_v191"])
    namespace["_version_dependencias_v200"] = isolate_dependency_version(namespace["_version_dependencias_v200"])
    for name in ("invalidar_cache_rendimiento_v191", "limpiar_cache_comisiones_operativas"):
        namespace[name] = defer_until_commit(namespace[name], name)

    @functools.wraps(legacy)
    def crear_periodo(anio, semestre, copiar_anterior=True, observaciones=""):
        if not namespace.get("USE_POSTGRESQL"):
            return legacy(anio, semestre, copiar_anterior, observaciones)
        return crear_periodo_atomico(namespace, open_raw, _record, anio, semestre, copiar_anterior, observaciones)

    crear_periodo.__wrapped__ = legacy
    namespace["crear_periodo"] = _mark(crear_periodo, legacy)
    namespace["_envolver_mutacion_rendimiento_v191"]("crear_periodo")
    rewrapped = namespace["crear_periodo"]
    if not getattr(rewrapped, "_v191_perf_wrapped", False) or getattr(rewrapped, "__wrapped__", None) is not crear_periodo:
        raise InstallError("B12C: no se pudo re-aplicar el wrapper v191 heredado sobre crear_periodo")

    def estado_crear_periodo_b12c() -> Optional[dict]:
        trace = holder["trace"]
        return trace.as_dict() if trace is not None else None

    namespace[STATUS_FUNCTION_NAME] = _mark(estado_crear_periodo_b12c)
    return {"rebound": list(REBOUND_NAMES), "status_function": STATUS_FUNCTION_NAME,
            "steps": list(STEPS), "optional_phases": list(OPTIONAL_PHASES)}
