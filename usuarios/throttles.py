"""
Límites de intentos de inicio de sesión (RNF-26, defecto D-04).

Antes el límite de 5 por minuto se contaba solo por IP. En un laboratorio donde todo el
personal sale a internet por la misma IP, los errores de una persona bloqueaban a las demás.
Ahora el límite estricto se cuenta por usuario + IP, y por IP queda un tope más alto que
sigue frenando a quien prueba muchos usuarios desde un mismo equipo.
"""
from rest_framework.throttling import SimpleRateThrottle

from .roles import normalizar


class LoginPorUsuarioThrottle(SimpleRateThrottle):
    scope = 'login'

    def get_cache_key(self, request, view):
        usuario = normalizar(str(request.data.get('username', ''))[:150]) or '-'
        return self.cache_format % {'scope': self.scope, 'ident': f'{usuario}|{self.get_ident(request)}'}


class LoginPorIPThrottle(SimpleRateThrottle):
    scope = 'login_ip'

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}
