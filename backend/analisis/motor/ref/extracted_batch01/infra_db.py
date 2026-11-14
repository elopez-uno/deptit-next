# Batch 01 pure helpers extracted verbatim from frozen 8AS.
from __future__ import annotations

def _fecha_pg_v238(expr):
    """Expresión PostgreSQL -> date para campos legacy TEXT/DATE, sin asumir tipo físico."""
    txt = f"BTRIM(CAST({expr} AS text))"
    return f"""(
        CASE
            WHEN {txt} ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}' THEN LEFT({txt},10)::date
            WHEN {txt} ~ '^[0-9]{{1,2}}/[0-9]{{1,2}}/[0-9]{{4}}$' THEN to_date({txt}, 'DD/MM/YYYY')
            ELSE NULL
        END
    )"""


def _pg_quote_literal_text(valor, default=', '):
    """Convierte un literal SQL simple a texto seguro para usar como separador."""
    v = str(valor or '').strip()
    if len(v) >= 2 and v[0] == "'" and v[-1] == "'":
        return v[1:-1].replace("''", "'")
    return default
