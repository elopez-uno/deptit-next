"""Huellas semanticas de una base (6A-B2): esquema + contenido, para comparar origen y restore.

* Esquema (``huella_esquema``): tablas y columnas (tipo, NOT NULL, default), restricciones
  (``pg_get_constraintdef``), indices (``pg_get_indexdef``), secuencias, vistas y funciones de ``public``.  Sin owners
  ni ACL: el restore usa ``--no-owner --no-privileges`` (los permisos se reaplican con la plantilla de roles).
* Contenido (``huella_datos``): por tabla, filas + MD5 de todas las filas como texto, ordenadas con collation "C"
  (independiente de la configuracion regional de cada base); secuencias: ``last_value`` / ``is_called``.
* Solo lecturas.  Las tablas se citan con ``format('%I')`` del propio servidor.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional

COLUMNAS = """
SELECT c.relname, a.attname, format_type(a.atttypid, a.atttypmod), a.attnotnull,
       coalesce(pg_get_expr(d.adbin, d.adrelid), '')
  FROM pg_attribute a
  JOIN pg_class c ON c.oid = a.attrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
  LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
 WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') AND a.attnum > 0 AND NOT a.attisdropped
 ORDER BY c.relname, a.attnum"""
RESTRICCIONES = """
SELECT c.relname, k.conname, pg_get_constraintdef(k.oid)
  FROM pg_constraint k JOIN pg_class c ON c.oid = k.conrelid JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'public' ORDER BY 1, 2"""
INDICES = """
SELECT tablename, indexname, indexdef FROM pg_indexes WHERE schemaname = 'public' ORDER BY 1, 2"""
SECUENCIAS = """
SELECT sequencename, data_type::text, start_value, increment_by, max_value, cycle
  FROM pg_sequences WHERE schemaname = 'public' ORDER BY 1"""
VISTAS = "SELECT viewname, definition FROM pg_views WHERE schemaname = 'public' ORDER BY 1"
FUNCIONES = """
SELECT p.oid::regprocedure::text, md5(pg_get_functiondef(p.oid))
  FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
 WHERE n.nspname = 'public' AND p.prokind IN ('f', 'p') ORDER BY 1"""
TABLAS = """
SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') ORDER BY 1"""
VALORES_SECUENCIAS = "SELECT sequencename, last_value FROM pg_sequences WHERE schemaname = 'public' ORDER BY 1"


def _sha(valor: Any) -> str:
    return hashlib.sha256(json.dumps(valor, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


def _filas(conn, sql: str, params=None) -> List[list]:
    return [list(r) for r in conn.execute(sql, params).fetchall()]


def huella_esquema(conn) -> Dict[str, Any]:
    tablas: Dict[str, list] = {}
    for tabla, col, tipo, notnull, default in _filas(conn, COLUMNAS):
        tablas.setdefault(tabla, []).append([col, tipo, bool(notnull), default])
    out = {"tablas": tablas, "restricciones": _filas(conn, RESTRICCIONES), "indices": _filas(conn, INDICES),
           "secuencias": _filas(conn, SECUENCIAS), "vistas": _filas(conn, VISTAS),
           "funciones": _filas(conn, FUNCIONES)}
    out["sha256"] = _sha(out)
    return out


def tablas(conn) -> List[str]:
    return [r[0] for r in conn.execute(TABLAS).fetchall()]


def huella_datos(conn, solo: Optional[List[str]] = None) -> Dict[str, Any]:
    """``solo``: subconjunto de tablas (pruebas con un rol que no lee todas); por defecto, todas las de ``public``."""
    por_tabla = {}
    for tabla in (tablas(conn) if solo is None else sorted(solo)):
        ident = conn.execute("SELECT format('public.%%I', %s::text)", (tabla,)).fetchone()[0]
        filas, md5 = conn.execute(
            f"SELECT count(*), md5(coalesce(string_agg(x, E'\\n' ORDER BY x COLLATE \"C\"), '')) "
            f"FROM (SELECT t::text AS x FROM {ident} t) s").fetchone()
        por_tabla[tabla] = {"filas": int(filas), "md5": md5}
    secuencias = {nombre: valor for nombre, valor in _filas(conn, VALORES_SECUENCIAS)}
    out = {"tablas": por_tabla, "secuencias": secuencias}
    out["sha256"] = _sha(out)
    return out


def huella(conn) -> Dict[str, Any]:
    return {"esquema": huella_esquema(conn), "datos": huella_datos(conn)}


def diferencias(origen: Dict[str, Any], destino: Dict[str, Any]) -> List[str]:
    """Lista legible de diferencias (vacia = equivalentes).  Sin valores de filas: solo nombres y conteos."""
    out = []
    eo, ed = origen["esquema"], destino["esquema"]
    for clave in ("restricciones", "indices", "secuencias", "vistas", "funciones"):
        if eo[clave] != ed[clave]:
            out.append(f"esquema.{clave} distinto")
    for t in sorted(set(eo["tablas"]) | set(ed["tablas"])):
        if eo["tablas"].get(t) != ed["tablas"].get(t):
            out.append(f"esquema.tabla {t} distinta")
    do, dd = origen["datos"], destino["datos"]
    for t in sorted(set(do["tablas"]) | set(dd["tablas"])):
        a, b = do["tablas"].get(t), dd["tablas"].get(t)
        if a != b:
            out.append(f"datos.{t}: origen {a and a['filas']} filas, destino {b and b['filas']} filas"
                       + (" (contenido distinto)" if a and b and a["filas"] == b["filas"] else ""))
    for s in sorted(set(do["secuencias"]) | set(dd["secuencias"])):
        if do["secuencias"].get(s) != dd["secuencias"].get(s):
            out.append(f"secuencia {s} distinta")
    return out


def resumen(h: Dict[str, Any]) -> Dict[str, Any]:
    datos = h["datos"]["tablas"]
    return {"esquema_sha256": h["esquema"]["sha256"], "datos_sha256": h["datos"]["sha256"],
            "tablas": len(datos), "filas": sum(v["filas"] for v in datos.values()),
            "secuencias": len(h["datos"]["secuencias"]),
            "restricciones": len(h["esquema"]["restricciones"]), "indices": len(h["esquema"]["indices"])}
