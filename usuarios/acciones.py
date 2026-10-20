"""
Matriz de acciones por rol — única fuente de verdad de permisos (§8.1, RF-44.1).

Cada acción es una clave `recurso.verbo`. El backend la usa en sus clases de
permiso y la devuelve en /usr/me/ y en el login como `acciones[]`, para que
las interfaces muestren solo lo que el usuario puede hacer.

Si un usuario tiene varios roles, sus acciones son la unión (RN-16).
`is_superuser` solo suma las acciones del Administrador (gestión), nunca
las clínicas (RN-19).
"""
from . import roles as R

MATRIZ = {
    # ── Cuenta propia (todos) ────────────────────────────────────────────────
    'perfil.ver': R.ROLES,
    'perfil.editar': R.ROLES,
    'dispositivos.propios': R.ROLES,
    'notificaciones.propias': R.ROLES,

    # ── Gestión de cuentas y roles ──────────────────────────────────────────
    'usuarios.ver': (R.AUDITOR, R.ADMINISTRADOR),
    'usuarios.gestionar': (R.ADMINISTRADOR,),
    'roles.ver': (R.AUDITOR, R.ADMINISTRADOR),
    'roles.gestionar': (R.ADMINISTRADOR,),
    'dispositivos.todos': (R.ADMINISTRADOR,),
    'auditoria.ver': (R.AUDITOR, R.ADMINISTRADOR),

    # ── Catálogos ───────────────────────────────────────────────────────────
    'catalogos.ver': R.ROLES,
    'catalogos.gestionar': (R.ADMINISTRADOR,),
    'parametros.ver': (R.MEDICO, R.BACTERIOLOGO, R.AUDITOR, R.ADMINISTRADOR),
    'parametros.gestionar': (R.BACTERIOLOGO,),
    'equipos.ver': (R.BACTERIOLOGO, R.AUDITOR, R.ADMINISTRADOR),
    'equipos.gestionar': (R.ADMINISTRADOR,),
    'equipos.regenerar_token': (R.ADMINISTRADOR,),
    'equipos.mantenimiento': (R.ADMINISTRADOR, R.BACTERIOLOGO),   # calibraciones, mantenimientos, estado
    'lotes.ver': (R.BACTERIOLOGO, R.AUDITOR, R.ADMINISTRADOR),
    'lotes.gestionar': (R.BACTERIOLOGO,),
    'calidad.ver': (R.BACTERIOLOGO, R.AUDITOR, R.ADMINISTRADOR),
    'calidad.gestionar': (R.BACTERIOLOGO,),                       # corridas, acciones correctivas, política
    'custodia.ver': R.ROLES_CLINICOS,
    'custodia.registrar': (R.TECNICO, R.BACTERIOLOGO),
    'criticos.ver': (R.MEDICO, R.BACTERIOLOGO, R.AUDITOR),
    'criticos.acusar': (R.MEDICO, R.BACTERIOLOGO),

    # ── Pacientes ───────────────────────────────────────────────────────────
    'pacientes.ver': R.ROLES_CLINICOS,
    'pacientes.crear': (R.MEDICO, R.TECNICO),
    'pacientes.editar': (R.MEDICO, R.TECNICO),
    'pacientes.desactivar': (R.MEDICO,),

    # ── Órdenes ─────────────────────────────────────────────────────────────
    'ordenes.ver': R.ROLES_CLINICOS,
    'ordenes.crear': (R.MEDICO,),
    'ordenes.editar': (R.MEDICO,),
    'ordenes.admitir': (R.MEDICO, R.TECNICO),
    'ordenes.reporte_pdf': (R.MEDICO, R.BACTERIOLOGO, R.AUDITOR),
    'ordenes.finalizar': (R.BACTERIOLOGO,),
    'ordenes.export_rips': (R.AUDITOR,),

    # ── Muestras ────────────────────────────────────────────────────────────
    'muestras.ver': R.ROLES_CLINICOS,
    'muestras.registrar': (R.TECNICO,),
    'muestras.buscar': R.ROLES_CLINICOS,
    'muestras.recibir': (R.BACTERIOLOGO,),
    'muestras.rechazar': (R.BACTERIOLOGO,),

    # ── Exámenes y resultados ───────────────────────────────────────────────
    'examenes.ver': R.ROLES_CLINICOS,
    'examenes.crear': (R.MEDICO,),
    'examenes.aprobar': (R.BACTERIOLOGO,),
    'examenes.rechazar': (R.BACTERIOLOGO,),
    'examenes.anular': (R.MEDICO, R.BACTERIOLOGO),
    'lecturas.ver': (R.BACTERIOLOGO, R.AUDITOR),
    'lecturas.registrar': (R.BACTERIOLOGO,),   # además del middleware con token (RF-30.1)
    'lecturas.procesar': (R.BACTERIOLOGO,),
    'resultados.ver': (R.MEDICO, R.BACTERIOLOGO, R.AUDITOR),
    'resultados.registrar': (R.BACTERIOLOGO,),
    'informes.ver': (R.MEDICO, R.BACTERIOLOGO, R.AUDITOR),
}


def acciones_de(usuario):
    """Lista ordenada de acciones permitidas al usuario."""
    roles = set(R.roles_de(usuario))
    if getattr(usuario, 'is_superuser', False):
        roles.add(R.ADMINISTRADOR)
    if not roles:
        return []
    return sorted(accion for accion, permitidos in MATRIZ.items() if roles.intersection(permitidos))


def puede(usuario, accion):
    if accion not in MATRIZ:
        raise KeyError(f'Acción no definida en la matriz: {accion}')
    roles = set(R.roles_de(usuario))
    if getattr(usuario, 'is_superuser', False):
        roles.add(R.ADMINISTRADOR)
    return bool(roles.intersection(MATRIZ[accion]))
