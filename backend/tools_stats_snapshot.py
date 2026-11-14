"""Instantanea de pg_stat_database (vista global) leida desde deptit_next_dev como deptit_next_app."""
import json
import psycopg
import db

s = db.load_settings()
db.check_config(s)
with psycopg.connect(s["database_url"], connect_timeout=5, application_name="deptit_next_audit") as conn:
    conn.read_only = True
    db.verify_identity(conn)
    conn.execute("SELECT pg_stat_clear_snapshot()")
    rows = conn.execute(
        """SELECT datname, xact_commit, xact_rollback, tup_inserted, tup_updated, tup_deleted, sessions,
                  now()::text FROM pg_stat_database WHERE datname IN ('deptit','deptit_next_dev') ORDER BY 1"""
    ).fetchall()
    act = conn.execute(
        "SELECT datname, usename, application_name, count(*) FROM pg_stat_activity WHERE datname = 'deptit' GROUP BY 1,2,3"
    ).fetchall()
keys = ["datname", "xact_commit", "xact_rollback", "tup_inserted", "tup_updated", "tup_deleted", "sessions", "ts"]
print(json.dumps({"stats": [dict(zip(keys, r)) for r in rows], "deptit_sessions": [list(a) for a in act]}, default=str))
