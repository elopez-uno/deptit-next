# B07: catalogo canonico (movimientos de designaciones: tipos vinculados, inicio/baja real (v269) y actos administrativos (v266)).
# Sentencias copiadas verbatim del entrypoint certificado B06 (app_postgresql_refactor_b06_residual_r0_r1.py,
# sha256 6e495a0edf17ab9fd648dacb4f98596b463c8c2b91652784ef6d8ecc3654ce3c). El monolito B07 enlaza estos mismos objetos;
# no cambiar valores, tipos ni orden.

# B06 L8536-8561
TIPOS_MOVIMIENTO_VINCULADOS_DESIGNACION = {
    "alta de designación",
    "alta de designacion",
    "renovación automática de designación",
    "renovacion automatica de designacion",
    "aumento de dedicación",
    "aumento de dedicacion",
    "disminución de dedicación",
    "disminucion de dedicacion",
    "cambio de cargo",
    "cambio de condición ad honorem",
    "pase a ad honorem",
    "pase a rentado",
    "modificación general",
    "modificacion general",
    "baja de designación",
    "baja de designacion",
    "eliminación de designación",
    "eliminacion de designacion",
    "finalización de designación",
    "finalizacion de designacion",
    "finalización automática por cierre de período",
    "finalizacion automatica por cierre de periodo",
    "finalización automática por vencimiento de designación",
    "finalizacion automatica por vencimiento de designacion",
}

# B06 L9739-9743
_TIPOS_INICIO_DESIGNACION_V269 = {
    "Alta de designación",
    "Renovación automática de designación",
    "Continuidad automática de designación concursada",
}

# B06 L9744-9750
_TIPOS_BAJA_REAL_DESIGNACION_V269 = {
    "Baja de designación",
    "Finalización de designación",
    "Finalizacion de designacion",
    "Finalizar / baja de designación",
    "Finalización automática por vencimiento de designación",
}

# B06 L54233-54247
MOVIMIENTOS_ACTO_ADMINISTRATIVO_V266 = {
    "Alta de designación",
    "Renovación automática de designación",
    "Cambio de cargo",
    "Aumento de dedicación",
    "Disminución de dedicación",
    "Cambio de tipo de designación",
    "Cambio de condición Ad Honorem",
    "Pase a Ad Honorem",
    "Pase a Rentado",
    "Finalizar / baja de designación",
    "Baja de designación",
    "Finalización de designación",
    "Modificación general",
}
