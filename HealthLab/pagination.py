"""
Paginación estándar de la API (RNF-19, RNF-42, BE-02).

Durante la transición, si el cliente no envía `?limit=`, la respuesta NO se
pagina (devuelve la lista completa) para no romper la app Expo actual, que
espera arreglos. El cliente Ionic siempre envía `limit`. Cuando la app Expo
se retire, se fija `default_limit = 20` y toda colección queda paginada.
"""
from rest_framework.pagination import LimitOffsetPagination


class PaginacionLimitOffset(LimitOffsetPagination):
    default_limit = None   # TODO(retiro app Expo): poner 20
    max_limit = 100
    limit_query_param = 'limit'
    offset_query_param = 'offset'
