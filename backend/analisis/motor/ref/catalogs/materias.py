# B07: catalogo canonico (materias: tipos de opcion curricular y modos/etiquetas de comparticion (v137)).
# Sentencias copiadas verbatim del entrypoint certificado B06 (app_postgresql_refactor_b06_residual_r0_r1.py,
# sha256 6e495a0edf17ab9fd648dacb4f98596b463c8c2b91652784ef6d8ecc3654ce3c). El monolito B07 enlaza estos mismos objetos;
# no cambiar valores, tipos ni orden.

# B06 L12420-12420
TIPOS_OPCION_CURRICULAR = ["Optativa", "Electiva"]

# B06 L25295-25295
MODO_COMPARTICION_AUTO = "Automática"

# B06 L25296-25296
MODO_COMPARTICION_ESPECIFICA = "Específica"

# B06 L25297-25297
MODO_COMPARTICION_SELECCIONADA = "Seleccionada"

# B06 L25299-25303
ETIQUETAS_COMPARTICION_MATERIA = {
    "Compartida automáticamente entre todos los planes donde aparece": MODO_COMPARTICION_AUTO,
    "Específica de esta carrera/plan": MODO_COMPARTICION_ESPECIFICA,
    "Compartida únicamente entre planes seleccionados": MODO_COMPARTICION_SELECCIONADA,
}
