"""Textos visibles de Administración SaaS (B13-FIX02 ``render_admin_saas`` l. 3339-3693) y catálogos certificados.

El frontend los recibe en la lectura inicial (``ui``) y no los reescribe: así el diferencial compara los labels de la
página certificada con los de NEXT.  Los textos que el certificado muestra y NEXT excluye por decisión aprobada se
documentan en ``EXCLUIDOS`` (D-AP3: rutas/archivos SQLite y disco; Credenciales iniciales: tooling de bootstrap).
"""

from __future__ import annotations

# --- catálogos (entry l. 502 y l. 541-544) ------------------------------------------------------------------------
AUTH_ROLES = ["superadmin", "coordinador_institucional", "usuario_departamento", "solo_lectura"]
PLANES_COMERCIALES = ["Prueba", "Básico", "Institucional", "Profesional", "Enterprise"]
ESTADOS_PAGO = ["Activo", "Pendiente", "Vencido", "Bonificado"]
ESTADOS_SUSCRIPCION = ["Activa", "Prueba", "Inactiva", "Cancelada"]
ESTADOS_INSTITUCION = ["Activa", "Solo lectura", "Bloqueada", "Suspendida"]
ESTADOS_USUARIO = ["Activo", "Inactivo"]
ESTADOS_DEPARTAMENTO = ["Activo", "Inactivo"]
SIN_DEPARTAMENTO = "Sin departamento"
CUPO_MIN, CUPO_MAX, CUPO_DEFAULT = 1, 500, 5
# Cuentas de prueba heredadas (deptit_refactor/security/credentials.py ``LEGACY_SEED_EMAILS``): identificadores de
# cuentas a desactivar o restablecer, sin contraseñas.
LEGACY_SEED_EMAILS = ("admin@local", "coordinador@uno.local", "informatica@uno.local")

TITULO = "⚙️ Administración SaaS"
MSG_SOLO_SUPERADMIN = "Solo el superadmin puede administrar instituciones, cupos y usuarios."
PESTANAS = ["Instituciones", "Departamentos", "Usuarios", "Suscripción / Comercial", "Credenciales iniciales"]

UI = {
    "titulo": TITULO,
    "pestanas": PESTANAS,
    "instituciones": {
        "subtitulo": "Instituciones",
        "crear": {"titulo": "Crear institución", "nombre": "Nombre institución", "cupo": "Cupo usuarios",
                  "plan": "Plan", "vencimiento": "Fecha de vencimiento", "pago": "Estado de pago",
                  "suscripcion": "Suscripción", "acceso": "Acceso", "observaciones": "Observaciones",
                  "boton": "Crear institución"},
        "cupo": {"titulo": "Modificar cupo", "institucion": "Institución", "nuevo": "Nuevo cupo",
                 "boton": "Actualizar cupo"},
        "eliminar": {
            "titulo": "Eliminar institución", "vacio": "No hay instituciones para eliminar.",
            # D-AP1: el aviso certificado ("junto con sus usuarios y departamentos ... carpeta de bases") describía
            # el borrado en cascada; NEXT solo elimina instituciones vacías.
            "aviso": ("Esta acción elimina definitivamente una institución VACÍA: sin usuarios, sin departamentos y sin "
                      "datos académicos. Una institución con datos no puede eliminarse: para darla de baja cambiá su "
                      "acceso a \"Bloqueada\" o \"Suspendida\" en Suscripción / Comercial."),
            "selector": "Institución a eliminar", "datos": "Datos actuales de la institución seleccionada",
            "confirmar": "Confirmo que quiero eliminar esta institución",
            "texto": "Para confirmar, escribí ELIMINAR", "boton": "🗑️ Eliminar institución",
        },
    },
    "departamentos": {
        "subtitulo": "Departamentos", "institucion": "Institución",
        "planes": {"titulo": "Integridad de planes de estudio", "metricas": ["Carreras", "Materias", "Estado"],
                   "sin_planes": "Todavía no hay planes cargados en la fuente única de esta universidad."},
        "crear": {"titulo": "Crear departamento", "nombre": "Nombre departamento", "observaciones": "Observaciones",
                  "boton": "Crear departamento"},
        "editar": {"titulo": "Editar departamento", "vacio": "No hay departamentos para editar en esta institución.",
                   "selector": "Departamento", "datos": "Datos actuales del departamento", "nombre": "Nombre",
                   "estado": "Estado", "observaciones": "Observaciones", "boton": "Guardar cambios de departamento"},
        "eliminar": {
            "titulo": "Eliminar departamento", "vacio": "No hay departamentos para eliminar en esta institución.",
            "selector": "Departamento a eliminar",
            # D-AP2/D-AP3: sin "base local" ni respaldo de archivos; solo departamentos vacíos.
            "aviso": ("Eliminar un departamento borra definitivamente su registro. Solo puede eliminarse un "
                      "departamento VACÍO: sin usuarios asignados y sin datos académicos. Para dar de baja un "
                      "departamento con historia, cambiá su estado a \"Inactivo\" en Editar departamento."),
            "usuarios": "Usuarios asignados: {n}.",
            "confirmar": "Confirmo que quiero eliminar este departamento",
            "con_usuarios": ("No se puede eliminar porque tiene usuarios asignados. Primero reasigná o eliminá esos "
                             "usuarios."),
            "boton": "🗑️ Eliminar departamento",
        },
    },
    "usuarios": {
        "subtitulo": "Usuarios",
        "crear": {"titulo": "Crear usuario", "sin_instituciones": "Primero creá una institución.",
                  "institucion": "Institución", "departamento": "Departamento", "nombre": "Nombre", "mail": "Mail",
                  "rol": "Rol", "password": "Contraseña provisoria", "confirmar": "Confirmar contraseña",
                  "estado": "Estado", "observaciones": "Observaciones",
                  "cupo": "Cupo usado: {activos}/{max} usuarios activos", "boton": "Crear usuario"},
        "estado": {"titulo": "Activar / desactivar usuario", "usuario": "Usuario", "nuevo": "Nuevo estado",
                   "boton": "Actualizar estado"},
        "editar": {"titulo": "Editar usuario", "selector": "Usuario a editar",
                   "datos": "Datos actuales del usuario seleccionado", "nombre": "Nombre", "mail": "Mail",
                   "rol": "Rol", "estado": "Estado", "institucion": "Institución", "departamento": "Departamento",
                   "password": "Nueva contraseña (dejar vacío para conservar)", "observaciones": "Observaciones",
                   "boton": "Guardar cambios de usuario"},
        "eliminar": {"titulo": "Eliminar usuario", "selector": "Usuario a eliminar",
                     "confirmar": "Confirmo que quiero eliminar esta cuenta de usuario", "boton": "🗑️ Eliminar usuario"},
    },
    "comercial": {
        "subtitulo": "Suscripción / Comercial", "vacio": "No hay instituciones cargadas.",
        "editar": {"titulo": "Editar plan, vencimiento, pago y acceso", "vacio": "No hay instituciones para editar.",
                   "institucion": "Institución", "datos": "Datos actuales de la institución", "plan": "Plan",
                   "cupo": "Cupo de usuarios", "vencimiento": "Fecha de vencimiento", "pago": "Estado de pago",
                   "suscripcion": "Suscripción", "acceso": "Acceso", "observaciones": "Observaciones",
                   "guardar": "Guardar datos comerciales", "bloquear": "Bloquear institución",
                   "desbloquear": "Desbloquear institución"},
        "criterio": {"titulo": "Criterio de acceso", "texto": [
            "**Acceso Activa** + **Suscripción Activa/Prueba**: los usuarios ingresan normalmente.",
            "**Acceso Solo lectura**, **pago vencido** o **fecha vencida**: los usuarios ingresan como solo lectura.",
            "**Acceso Bloqueada/Suspendida** o **Suscripción Inactiva/Cancelada**: los usuarios de esa institución "
            "no pueden ingresar.",
            "El **superadmin** siempre puede entrar para administrar y reactivar instituciones.",
        ]},
    },
    "credenciales": {
        # Sin la referencia a tooling de bootstrap del certificado (diferencia consciente NEXT, Etapa 6).
        "info": ("Ya no existen credenciales iniciales. Si esta base proviene de una instalación anterior, desactivá "
                 "o restablecé las cuentas de prueba heredadas listadas abajo antes de habilitar producción."),
        "cuentas": list(LEGACY_SEED_EMAILS),
    },
    "excel": "📥 Descargar tabla en Excel",
}

# --- mensajes de resultado (certificados) -------------------------------------------------------------------------
MSG = {
    "inst_creada": "Institución creada.",
    "cupo_actualizado": "Cupo actualizado.",
    "inst_eliminada": "Institución eliminada.",
    "dep_creado": "Departamento creado.",
    "dep_actualizado": "Departamento actualizado.",
    "dep_eliminado": "Departamento eliminado.",
    "usuario_creado": "Usuario creado.",
    "estado_actualizado": "Estado actualizado.",
    "usuario_actualizado": "Usuario actualizado.",
    "usuario_eliminado": "Usuario eliminado.",
    "comercial_actualizado": "Datos comerciales actualizados.",
    "inst_bloqueada": "Institución bloqueada.",
    "inst_activa": "Institución activa nuevamente.",
}
# Prefijos de error certificados (``st.error(f"<prefijo>: {e}")``); NEXT solo agrega el texto funcional (ValueError).
PREFIJO = {
    "crear": "No se pudo crear",
    "crear_usuario": "No se pudo crear el usuario",
    "actualizar": "No se pudo actualizar",
    "actualizar_usuario": "No se pudo actualizar el usuario",
    "eliminar_inst": "No se pudo eliminar la institución",
    "eliminar": "No se pudo eliminar",
    "eliminar_usuario": "No se pudo eliminar el usuario",
}
MSG_PASSWORDS_DISTINTAS = "Las contraseñas no coinciden."
MSG_CONFIRMAR_INST = "Primero confirmá la eliminación y escribí ELIMINAR."
MSG_CONFIRMAR = "Primero confirmá la eliminación."

# Textos certificados que NEXT no muestra (decisiones aprobadas), para el diferencial de UI.
EXCLUIDOS = {
    "Esta acción elimina la institución del sistema SaaS junto con sus usuarios y departamentos. "
    "Si marcás la opción de datos locales, también respalda y elimina la carpeta de bases de esa institución.": "D-AP1",
    "Respaldar y eliminar también la carpeta local de datos de esta institución": "D-AP1/D-AP3",
    "El respaldo queda como una carpeta `.backup_deleted_inst_...` dentro de `datos_instituciones`.": "D-AP3",
    "Eliminar un departamento borra su registro de administración y deja un backup de su base local si existía.":
        "D-AP2/D-AP3",
    "El sistema compara Secretaría Académica y todos los departamentos de la institución seleccionada. Ya no hace "
    "falta sincronizar manualmente: los cambios en materias se propagan automáticamente.": "D-AP3",
    "#### Fuente única de planes de estudio": "D-AP3",
    "La app usa un único archivo de planes para esta universidad.": "D-AP3",
    "No se compara más contra bases departamentales ni contra la base vieja de Secretaría Académica. Las ediciones "
    "de materias y planes se guardan en `_planes_estudio.db` de la universidad activa.": "D-AP3",
}
EXCLUIDOS_PREFIJOS = {"Archivo usado: ": "D-AP3", "Usuarios asignados: ": "D-AP3 (sin 'Base local')",
                      "Se eliminarán ": "D-AP1 (sin cascada)", "Ya no existen credenciales iniciales.": "Etapa 6"}
