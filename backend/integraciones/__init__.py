"""Capa de composicion de la Etapa 4 (D-E4-01, ``docs/ETAPA4_IMPLEMENTATION_PLAN.md`` §1).

Integraciones cross-module que consumen contratos publicos de los modulos propietarios.  Los imports van en una sola
direccion (integraciones -> propietarios): ningun modulo propietario importa este paquete; solo ``main.py`` lo conecta.
"""
