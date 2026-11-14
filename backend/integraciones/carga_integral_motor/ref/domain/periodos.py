# B05: extracted verbatim from certified B04 (periodos: eliminacion y formulas de la hoja Periodos).
from __future__ import annotations


def periodo_puede_eliminarse(conteos):
    """Devuelve True solo si el período no tiene datos académicos/administrativos."""
    campos_bloqueantes = [
        "designaciones",
        "movimientos_gestion",
        "comisiones",
        "horarios_comision",
        "asignaciones_comision",
        "horarios_asignacion_docente",
        "inscriptos",
        "investigacion",
        "extension",
        "actividades_especiales",
        "asignaciones_actividades_especiales",
        "disposiciones",
    ]
    return all(int(conteos.get(c, 0) or 0) == 0 for c in campos_bloqueantes)


def _formula_periodo_excel_v230(fila, col_desde, col_hasta, ultima_fila_periodos):
    if ultima_fila_periodos < 2:
        return '=""'
    return (
        f'=IF(OR({col_desde}{fila}="",{col_hasta}{fila}=""),"",'
        f'IFERROR(LOOKUP(2,1/(({col_desde}{fila}<=\'Períodos\'!$C$2:$C${ultima_fila_periodos})*'
        f'({col_hasta}{fila}>=\'Períodos\'!$B$2:$B${ultima_fila_periodos})),\'Períodos\'!$A$2:$A${ultima_fila_periodos}),""))'
    )
