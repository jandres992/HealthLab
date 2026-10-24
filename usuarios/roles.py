"""
Roles de negocio de HealthLab (§3, §8.1 del documento de requerimientos).

Un usuario puede tener varios roles (RN-16). Los roles se infieren de
UsuarioXPermiso → Permiso → TipoUsuario y se normalizan a estas claves.
`is_staff` / `is_superuser` NO otorgan roles clínicos (RN-19); solo se
consideran equivalentes a ADMINISTRADOR para la gestión de cuentas.
"""
import unicodedata

MEDICO = 'medico'
TECNICO = 'tecnico_de_enfermeria'
BACTERIOLOGO = 'bacteriologo'
AUDITOR = 'auditor'
ADMINISTRADOR = 'administrador'

ROLES = (MEDICO, TECNICO, BACTERIOLOGO, AUDITOR, ADMINISTRADOR)
ROLES_CLINICOS = (MEDICO, TECNICO, BACTERIOLOGO, AUDITOR)

ETIQUETAS = {
    MEDICO: 'Médico',
    TECNICO: 'Auxiliar de Enfermería',
    BACTERIOLOGO: 'Bacteriólogo',
    AUDITOR: 'Auditor',
    ADMINISTRADOR: 'Administrador',
}

# Sinónimos aceptados en TipoUsuario.tipo / Permiso.permiso (normalizados).
_SINONIMOS = {
    'medico': MEDICO,
    'medica': MEDICO,
    'tecnico_de_enfermeria': TECNICO,
    'tecnico_enfermeria': TECNICO,
    'tecnico': TECNICO,
    'auxiliar_de_enfermeria': TECNICO,
    'auxiliar_enfermeria': TECNICO,
    'enfermeria': TECNICO,
    'flebotomista': TECNICO,
    'bacteriologo': BACTERIOLOGO,
    'bacteriologa': BACTERIOLOGO,
    'auditor': AUDITOR,
    'auditora': AUDITOR,
    'administrador': ADMINISTRADOR,
    'administradora': ADMINISTRADOR,
    'admin': ADMINISTRADOR,
}


def normalizar(valor):
    """Minúsculas, sin acentos, espacios → guion bajo."""
    texto = unicodedata.normalize('NFKD', str(valor or '').strip().lower())
    texto = ''.join(ch for ch in texto if not unicodedata.combining(ch))
    return texto.replace(' ', '_').replace('-', '_')


def rol_desde_texto(valor):
    texto = normalizar(valor)
    if texto.startswith('permiso_'):
        texto = texto[len('permiso_'):]
    return _SINONIMOS.get(texto)


def roles_de(usuario):
    """
    Conjunto de roles normalizados del usuario. Se memoriza en el objeto
    usuario durante la petición para no repetir la consulta.
    """
    if usuario is None or not getattr(usuario, 'is_authenticated', False):
        return set()
    cache = getattr(usuario, '_roles_healthlab', None)
    if cache is not None:
        return cache

    from .models import UsuarioXPermiso  # noqa: PLC0415 (evita importación circular)

    roles = set()
    asignaciones = UsuarioXPermiso.objects.select_related(
        'permiso__tipo_usuario'
    ).filter(usuario=usuario)
    for asignacion in asignaciones:
        for candidato in (asignacion.permiso.tipo_usuario.tipo, asignacion.permiso.permiso):
            rol = rol_desde_texto(candidato)
            if rol:
                roles.add(rol)
    usuario._roles_healthlab = roles
    return roles


def tiene_rol(usuario, *roles):
    return bool(roles_de(usuario).intersection(roles))


def es_administrador(usuario):
    """Gestión de cuentas: rol Administrador o superusuario de Django."""
    if usuario is None or not getattr(usuario, 'is_authenticated', False):
        return False
    return bool(getattr(usuario, 'is_superuser', False)) or ADMINISTRADOR in roles_de(usuario)
