"""Utilidades compartidas por las pruebas: creación de usuarios con rol."""
from django.contrib.auth import get_user_model

from .models import Permiso, TipoUsuario, UsuarioXPermiso
from .roles import ETIQUETAS

User = get_user_model()

CONTRASENA_PRUEBA = 'Clave-Segura-2026!'


def asignar_rol(usuario, rol):
    """Asigna un rol normalizado ('medico', 'bacteriologo', ...) al usuario."""
    tipo, _ = TipoUsuario.objects.get_or_create(tipo=ETIQUETAS[rol])
    permiso, _ = Permiso.objects.get_or_create(permiso=f'permiso_{rol}', tipo_usuario=tipo)
    UsuarioXPermiso.objects.get_or_create(usuario=usuario, permiso=permiso)
    if hasattr(usuario, '_roles_healthlab'):
        del usuario._roles_healthlab
    return usuario


def crear_usuario(username, *roles, password=CONTRASENA_PRUEBA, **extra):
    usuario = User.objects.create_user(
        username=username, password=password, email=f'{username}@healthlab.test', **extra
    )
    for rol in roles:
        asignar_rol(usuario, rol)
    return usuario
