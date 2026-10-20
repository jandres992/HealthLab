"""
Permisos del módulo laboratorio.

La matriz de acciones por rol (usuarios/acciones.py) es la única fuente de
verdad; aquí solo se añade el caso del middleware, que ingesta lecturas sin
JWT con el token estático del equipo (RF-30.1, RNF-05).
`is_staff` / `is_superuser` no saltan ninguna regla clínica (RN-19).
"""
from django.db.models import Q

from laboratorio.models import ConfiguracionEquipo
from usuarios.permissions import PermisoPorAccion


def token_middleware_valido(request):
    """True si la petición trae un token de middleware vigente para su `equipo_origen`."""
    token = request.headers.get('X-Middleware-Token') or request.data.get('token_middleware')
    equipo = request.data.get('equipo_origen')
    if not token or not equipo:
        return False
    return ConfiguracionEquipo.objects.filter(
        activo=True, token_middleware=token
    ).filter(Q(codigo_equipo=equipo) | Q(nombre=equipo)).exists()


class PermisoIngestaLecturas(PermisoPorAccion):
    """`create` se permite con token de middleware o con la acción `lecturas.registrar`."""

    def has_permission(self, request, view):
        if getattr(view, 'action', None) == 'create' and token_middleware_valido(request):
            return True
        return super().has_permission(request, view)
