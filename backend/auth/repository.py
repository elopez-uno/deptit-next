"""Acceso a deptit_next_dev para autenticacion. Cada operacion usa su propia conexion/transaccion del pool.

SQL de usuarios y de ``auth_login_throttle``: identico a B12G (``session_b12g.py``).  Instituciones/departamentos:
mismo orden que ``get_instituciones_auth`` / ``get_departamentos_auth`` certificados.  Nunca crea tablas.
"""

from __future__ import annotations

from typing import Optional

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .core import Config, normalize_email

_USER_COLUMNS = ("SELECT u.id, u.email, u.nombre, u.rol, u.estado, u.salt, u.password_hash, u.institucion_id, "
                 "u.departamento_id, i.nombre AS institucion_nombre, i.slug AS institucion_slug, "
                 "i.estado AS institucion_estado, i.fecha_vencimiento, i.estado_pago, i.suscripcion, "
                 "d.nombre AS departamento_nombre, d.slug AS departamento_slug "
                 "FROM app_usuarios u LEFT JOIN instituciones i ON i.id = u.institucion_id "
                 "LEFT JOIN departamentos d ON d.id = u.departamento_id ")
USER_BY_ID_SQL = _USER_COLUMNS + "WHERE u.id = %s ORDER BY u.id LIMIT 2"
USERS_BY_EMAIL_SQL = _USER_COLUMNS + "WHERE LOWER(u.email) = LOWER(%s) ORDER BY u.id LIMIT 2"

THROTTLE_TABLE = "auth_login_throttle"
PG_NOW_SQL = "CAST(EXTRACT(EPOCH FROM now()) AS double precision)"


class AuthRepository:
    def __init__(self, pool: ConnectionPool):
        self._pool = pool

    def _all(self, sql: str, params: list) -> list[dict]:
        with self._pool.connection(timeout=5) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, params)
                return list(cur.fetchall())

    def _one(self, sql: str, params: list) -> Optional[tuple]:
        with self._pool.connection(timeout=5) as conn:
            return conn.execute(sql, params).fetchone()

    # --- usuarios (lecturas autoritativas, sin cache)
    def user_by_id(self, user_id: int) -> list[dict]:
        return self._all(USER_BY_ID_SQL, [int(user_id)])

    def users_by_email(self, email: str) -> list[dict]:
        return self._all(USERS_BY_EMAIL_SQL, [normalize_email(email)])

    # --- instituciones / departamentos
    def institutions(self) -> list[dict]:
        return self._all("SELECT id, nombre, estado FROM instituciones ORDER BY nombre", [])

    def departments(self, institution_id: int, only_active: bool) -> list[dict]:
        sql = ("SELECT d.id, d.nombre, d.estado, d.institucion_id FROM departamentos d "
               "LEFT JOIN instituciones i ON i.id = d.institucion_id WHERE d.institucion_id = %s ")
        if only_active:
            sql += "AND d.estado = 'Activo' "
        return self._all(sql + "ORDER BY i.nombre, d.nombre", [int(institution_id)])

    def institution(self, institution_id: int) -> Optional[dict]:
        rows = self._all("SELECT id, nombre, estado FROM instituciones WHERE id = %s", [int(institution_id)])
        return rows[0] if rows else None

    def department(self, department_id: int) -> Optional[dict]:
        rows = self._all("SELECT id, nombre, estado, institucion_id FROM departamentos WHERE id = %s",
                         [int(department_id)])
        return rows[0] if rows else None

    # --- limite de intentos compartido (B12G PgLoginThrottleStore), reloj de la base
    def lock_state(self, key: str) -> bool:
        row = self._one(f"SELECT locked_until_epoch, {PG_NOW_SQL} AS now_epoch FROM {THROTTLE_TABLE} "
                        "WHERE subject_key = %s", [key])
        if row is None:
            return False
        locked_until, now_epoch = row
        return locked_until is not None and now_epoch is not None and float(locked_until) > float(now_epoch)

    def register_failure(self, key: str, cfg: Config) -> tuple[int, Optional[float]]:
        now, t = PG_NOW_SQL, THROTTLE_TABLE
        reset = (f"({t}.window_started_epoch <= {now} - %s OR ({t}.locked_until_epoch IS NOT NULL "
                 f"AND {t}.locked_until_epoch <= {now}))")
        new_failures = f"(CASE WHEN {reset} THEN 1 ELSE {t}.failures + 1 END)"
        sql = (f"INSERT INTO {t} (subject_key, failures, window_started_epoch, locked_until_epoch, updated_epoch) "
               f"VALUES (%s, 1, {now}, CASE WHEN 1 >= %s THEN {now} + %s ELSE NULL END, {now}) "
               f"ON CONFLICT (subject_key) DO UPDATE SET "
               f"failures = {new_failures}, "
               f"window_started_epoch = CASE WHEN {reset} THEN {now} ELSE {t}.window_started_epoch END, "
               f"locked_until_epoch = CASE WHEN {new_failures} >= %s THEN {now} + %s ELSE NULL END, "
               f"updated_epoch = {now} "
               f"RETURNING failures, locked_until_epoch")
        win, mx, lock = float(cfg.failure_window_seconds), int(cfg.max_failed_attempts), float(cfg.lockout_seconds)
        row = self._one(sql, [key, mx, lock, win, win, win, mx, lock])
        return int(row[0]), row[1]

    # --- 6A-B1: re-hash progresivo (solo si el hash no cambio desde que se leyo)
    def update_password_hash(self, user_id: int, old_hash: str, new_hash: str) -> bool:
        with self._pool.connection(timeout=5) as conn:
            cur = conn.execute("UPDATE app_usuarios SET password_hash = %s WHERE id = %s AND password_hash = %s",
                               [new_hash, int(user_id), old_hash])
            return cur.rowcount == 1

    def reset(self, key: str) -> None:
        with self._pool.connection(timeout=5) as conn:
            conn.execute(f"DELETE FROM {THROTTLE_TABLE} WHERE subject_key = %s", [key])

    def purge(self, older_than_seconds: float) -> None:
        with self._pool.connection(timeout=5) as conn:
            conn.execute(f"DELETE FROM {THROTTLE_TABLE} WHERE updated_epoch < {PG_NOW_SQL} - %s "
                         f"AND (locked_until_epoch IS NULL OR locked_until_epoch <= {PG_NOW_SQL})",
                         [float(older_than_seconds)])
