"""Hardening NEXT del inyector de ambito B12B (``DQ-SCOPE-OR-B12B``; Etapa 5 / Tanda A).  No es codigo generado.

El inyector certificado (``inyector.py``, ``_pg_insert_conditions`` l. 1079) agrega el ambito al WHERE principal como
``… AND (tabla.institucion_id = %s) AND (…)`` SIN parentesis alrededor del WHERE original: con ``WHERE A OR B`` queda
``WHERE A OR B AND ambito`` = ``A OR (B AND ambito)`` y el termino ``A`` lee todos los tenants.  Antes de inyectar, todo
WHERE de NIVEL SUPERIOR con ``OR`` se envuelve entre parentesis (``WHERE (A OR B)``): el sentido del SQL certificado no
cambia y el ambito alcanza a todo el WHERE.  Sin OR de nivel superior la sentencia queda IDENTICA (equivalencia).
Si hay OR de nivel superior en una forma que no se puede envolver con certeza (mas de un WHERE de nivel superior, p. ej.
ramas UNION), falla CERRADO con ``AmbitoNoGarantizable`` en lugar de ejecutar una lectura con fuga.
Lo usan los dos entornos que ejecutan el inyector: el motor de lectura (``entorno._Conexion``: Analisis, Inicio,
Resumen docente, carga integral) y el motor de escritura de Periodos (``integraciones.ciclo_periodos.entorno``).
"""
from __future__ import annotations

import re

FIN_WHERE = re.compile(r"\b(ORDER\s+BY|GROUP\s+BY|HAVING|LIMIT|OFFSET|RETURNING|UNION|INTERSECT|EXCEPT|FOR\s+UPDATE)\b",
                       re.I)
_WHERE = re.compile(r"\bWHERE\b", re.I)
_OR = re.compile(r"\bOR\b", re.I)


class AmbitoNoGarantizable(RuntimeError):
    """SQL con OR de nivel superior que el hardening no puede envolver con certeza (fail closed)."""


def nivel_superior(sql: str):
    """Indices de ``sql`` que estan fuera de comillas y de parentesis."""
    depth, quote = 0, None
    for i, ch in enumerate(sql):
        if quote:
            if ch == quote:
                quote = None
            continue
        if ch in ("'", '"'):
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif depth == 0:
            yield i


def _superior(sql: str) -> str:
    visibles = set(nivel_superior(sql))
    return "".join(sql[i] if i in visibles else " " for i in range(len(sql)))


def _wheres(sup: str) -> list[tuple[int, int]]:
    """(inicio del cuerpo, fin del cuerpo) de cada WHERE de nivel superior."""
    marcas = list(_WHERE.finditer(sup))
    tramos = []
    for k, m in enumerate(marcas):
        tope = marcas[k + 1].start() if k + 1 < len(marcas) else len(sup)
        fin = FIN_WHERE.search(sup, m.end(), tope)
        tramos.append((m.end(), fin.start() if fin else tope))
    return tramos


def or_nivel_superior(sql: str) -> bool:
    """Algun WHERE de nivel superior contiene OR fuera de parentesis."""
    sup = _superior(str(sql or ""))
    return any(_OR.search(sup, a, b) for a, b in _wheres(sup))


def proteger_or(sql: str) -> str:
    texto = str(sql or "")
    sup = _superior(texto)
    tramos = _wheres(sup)
    con_or = [(a, b) for a, b in tramos if _OR.search(sup, a, b)]
    if not con_or:
        return texto
    if len(tramos) != 1:
        raise AmbitoNoGarantizable("SQL con OR de nivel superior en mas de un WHERE: ambito no garantizable")
    inicio, fin = con_or[0]
    cuerpo = texto[inicio:fin].rstrip()
    resto = texto[inicio + len(cuerpo):]
    return f"{texto[:inicio]} ({cuerpo.strip()}){resto}"


# ---------------------------------------------------------------------------------- DQ-SCOPE-SUBQUERY-B12B
# El inyector certificado solo mira el FROM/JOIN de NIVEL SUPERIOR: una subconsulta (o el cuerpo de un CTE) que lee una
# tabla con ambito queda SIN filtro y lee todos los tenants (``get_resumen_docente``: ``WHERE d0.cuil = docentes.cuil``;
# ``get_designaciones`` v229: "ultimo periodo del departamento" tomado de TODOS los periodos).  Antes de inyectar, cada
# subconsulta que lee tablas con ambito y no menciona ``institucion_id`` / ``departamento_id`` recibe el ambito de la
# SESION con las mismas reglas del inyector (institucion para las tablas institucionales; institucion + departamento
# para las de departamento con ambito ``tenant``).  Los valores son los enteros de la sesion (no parametros: no altera
# el orden de los parametros certificados).  En un LEFT/RIGHT/FULL JOIN el filtro va en el ``ON`` (como B12J); si no,
# en el WHERE de la subconsulta (envuelto entre parentesis).  Sin subconsultas con tablas de ambito el SQL queda
# IDENTICO; en las correlacionadas por id/FK el resultado no cambia (padre ya en el ambito, A2: 0 filas desalineadas).
_TABLA_NIVEL = re.compile(
    r"\b(FROM|(?:(?:LEFT|RIGHT|FULL)(?:\s+OUTER)?\s+|INNER\s+|CROSS\s+)?JOIN)\s+\"?([A-Za-z_][A-Za-z0-9_]*)\"?"
    r"(?:\s+(?:AS\s+)?\"?([A-Za-z_][A-Za-z0-9_]*)\"?)?", re.I)
_RESERVADAS = {"WHERE", "JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "FULL", "ON", "GROUP", "ORDER", "LIMIT", "HAVING",
               "OFFSET", "CROSS", "UNION", "USING", "AS", "INTERSECT", "EXCEPT", "WINDOW", "FOR"}
_FIN_ON = re.compile(r"\b(WHERE|GROUP\s+BY|HAVING|ORDER\s+BY|LIMIT|OFFSET|UNION|INTERSECT|EXCEPT|"
                     r"(?:(?:LEFT|RIGHT|FULL)(?:\s+OUTER)?\s+|INNER\s+|CROSS\s+)?JOIN)\b", re.I)
_ANTES_DE_WHERE = re.compile(r"\b(GROUP\s+BY|HAVING|ORDER\s+BY|LIMIT|OFFSET|UNION|INTERSECT|EXCEPT|WINDOW)\b", re.I)
_MENCIONA_AMBITO = re.compile(r"\b(institucion_id|departamento_id)\b", re.I)


def _hijas_select(texto: str) -> list[tuple[int, int]]:
    """(inicio, fin) del CONTENIDO de cada ``( SELECT … )`` hija directa (no anidada en otra subconsulta) de ``texto``."""
    hijas, pila, quote = [], [], None
    for i, ch in enumerate(texto):
        if quote:
            if ch == quote:
                quote = None
            continue
        if ch in ("'", '"'):
            quote = ch
        elif ch == "(":
            es_select = re.match(r"\(\s*SELECT\b", texto[i:i + 40], re.I) is not None
            pila.append((i, es_select and not any(s for _, s in pila)))
        elif ch == ")" and pila:
            ini, hija = pila.pop()
            if hija:
                hijas.append((ini + 1, i))
    return hijas


def _ambito_nivel(texto: str, ambito: dict, inst_tablas: set, dep_tablas: set) -> str:
    """Agrega el ambito a las tablas del FROM/JOIN de ESTE nivel de una subconsulta."""
    sup = _superior(texto)
    if _MENCIONA_AMBITO.search(sup):  # solo ESTE nivel (las hijas ya se procesaron y pueden mencionarlo)
        return texto
    kind = str(ambito.get("kind") or "tenant")
    inst, dep = int(ambito["institucion_id"]), ambito.get("departamento_id")
    en_where, en_on = [], []
    for m in _TABLA_NIVEL.finditer(sup):
        tabla = m.group(2).lower()
        alias = m.group(3) if m.group(3) and m.group(3).upper() not in _RESERVADAS else m.group(2)
        conds = []
        if tabla in inst_tablas or (kind == "tenant" and tabla in dep_tablas):
            conds.append(f"{alias}.institucion_id = {inst}")
        if kind == "tenant" and tabla in dep_tablas and dep is not None:
            conds.append(f"{alias}.departamento_id = {int(dep)}")
        if not conds:
            continue
        if re.match(r"(LEFT|RIGHT|FULL)\b", m.group(1), re.I):
            on = re.compile(r"\bON\b", re.I).search(sup, m.end())
            if not on:
                raise AmbitoNoGarantizable("subconsulta con JOIN externo sin ON: ambito no garantizable")
            fin = _FIN_ON.search(sup, on.end())
            en_on.append((on.end(), fin.start() if fin else len(texto), conds))
        else:
            en_where.append(conds)
    if not en_where and not en_on:
        return texto
    wheres = list(_WHERE.finditer(sup))
    if len(wheres) > 1:
        raise AmbitoNoGarantizable("subconsulta con mas de un WHERE de nivel superior: ambito no garantizable")
    cambios = []  # (inicio, fin, reemplazo), aplicados de derecha a izquierda
    for ini, fin, conds in en_on:
        cuerpo = texto[ini:fin].rstrip()
        cambios.append((ini, ini + len(cuerpo), f" ({cuerpo.strip()}) AND " + " AND ".join(conds)))
    if en_where:
        clausula = " AND ".join(c for conds in en_where for c in conds)
        if wheres:
            ini = wheres[0].end()
            fin_m = FIN_WHERE.search(sup, ini)
            fin = fin_m.start() if fin_m else len(texto)
            cuerpo = texto[ini:fin].rstrip()
            cambios.append((ini, ini + len(cuerpo), f" ({cuerpo.strip()}) AND {clausula}"))
        else:
            corte = _ANTES_DE_WHERE.search(sup)
            pos = corte.start() if corte else len(texto.rstrip())
            cambios.append((pos, pos, (" " if pos and not texto[pos - 1].isspace() else "") + f"WHERE {clausula} "))
    for ini, fin, nuevo in sorted(cambios, key=lambda c: c[0], reverse=True):
        texto = texto[:ini] + nuevo + texto[fin:]
    return texto


def proteger_subconsultas(sql: str, ambito: dict, inst_tablas: set, dep_tablas: set) -> str:
    """Ambito de la sesion en cada subconsulta / CTE que lee tablas con ambito (el nivel superior lo hace el inyector)."""
    if not isinstance(ambito, dict) or ambito.get("kind") == "auth" or ambito.get("institucion_id") is None:
        return str(sql or "")

    def nivel(texto: str, superior: bool) -> str:
        for ini, fin in sorted(_hijas_select(texto), reverse=True):
            texto = texto[:ini] + nivel(texto[ini:fin], False) + texto[fin:]
        return texto if superior else _ambito_nivel(texto, ambito, inst_tablas, dep_tablas)

    return nivel(str(sql or ""), True)
