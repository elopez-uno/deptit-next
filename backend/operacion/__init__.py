"""Operacion de DEPTIT NEXT (Etapa 6A-B2, docs/ETAPA6_6AB2_OPERATION_RECOVERY.md): backup / verificacion / restore de
la base y del storage documental, backup set, retencion, esquema base, bootstrap del primer superadmin, auditoria de
cuentas semilla, health operativo y empaquetado de releases.

Herramientas NO interactivas (salvo la contrasena del bootstrap) para el operador, Task Scheduler / systemd: nunca se
ejecutan desde la aplicacion ni desde un clic.  Uso: ``python -m operacion <comando>`` desde ``backend/``.

Formato de backup de base: el contrato certificado B11 (copia LITERAL en ``integraciones/ciclo_periodos/ref_b11``):
el gate de Crear periodo lo acepta sin adaptaciones.  Lo propio de NEXT (entorno, identificador, set) viaja en la
seccion libre ``deptit`` del manifest.
"""
