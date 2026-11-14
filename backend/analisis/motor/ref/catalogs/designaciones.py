# B07: catalogo canonico (designaciones: estados docentes, cargos, dedicaciones, tipos, horas por dedicacion y orden jerarquico).
# Sentencias copiadas verbatim del entrypoint certificado B06 (app_postgresql_refactor_b06_residual_r0_r1.py,
# sha256 6e495a0edf17ab9fd648dacb4f98596b463c8c2b91652784ef6d8ecc3654ce3c). El monolito B07 enlaza estos mismos objetos;
# no cambiar valores, tipos ni orden.

# B06 L512-512
ESTADOS_DOCENTE = ["Activo", "Licencia", "Jubilado", "Renunciado", "Fallecido"]

# B06 L515-515
CARGOS = ["Titular", "Asociado", "Adjunto", "JTP", "Ayudante 1ra", "Ayudante 2da"]

# B06 L516-516
DEDICACIONES = ["Simple", "Parcial", "Parcial + Simple", "Exclusiva", "Exclusiva + Simple"]

# B06 L517-517
TIPOS_DESIGNACION = ["Concursado", "Interino", "Loc. Serv."]

# B06 L519-525
HORAS_POR_DEDICACION = {
    "Simple": 10,
    "Parcial": 20,
    "Parcial + Simple": 30,
    "Exclusiva": 40,
    "Exclusiva + Simple": 50,
}

# B06 L29349-29351
ORDEN_JERARQUICO_CARGOS_COMISION = [
    "Titular", "Asociado", "Adjunto", "JTP", "Ayudante 1ra", "Ayudante 2da"
]
