"""
Clases de permiso DRF basadas en la matriz de acciones (usuarios/acciones.py).

Uso en un ViewSet:
    permission_classes = [PermisoPorAccion]
    acciones = {'list': 'usuarios.ver', 'create': 'usuarios.gestionar', ...}
    # o, más corto:
    accion_lectura = 'usuarios.ver'
    accion_escritura = 'usuarios.gestionar'

Cualquier acción no declarada se niega (regla 5 de §8.1).
"""
from rest_framework.permissions import SAFE_METHODS, BasePermission

from .acciones import puede


class PermisoPorAccion(BasePermission):
    message = 'No tienes permisos para realizar esta acción.'

    def has_permission(self, request, view):
        if request.method in ('OPTIONS', 'HEAD'):
            return True
        usuario = request.user
        if not usuario or not usuario.is_authenticated:
            return False

        accion_vista = getattr(view, 'action', None) or request.method.lower()
        mapa = getattr(view, 'acciones', {}) or {}
        clave = mapa.get(accion_vista)
        if clave is None:
            if request.method in SAFE_METHODS:
                clave = getattr(view, 'accion_lectura', None)
            else:
                clave = getattr(view, 'accion_escritura', None)
        if clave is None:
            return False
        return puede(usuario, clave)


class SoloAutenticado(BasePermission):
    """Lectura para cualquier usuario autenticado (catálogos públicos internos)."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)
