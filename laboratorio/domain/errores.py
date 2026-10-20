"""
Errores de dominio. Son excepciones de DRF para que lleguen al cliente con
el formato estándar {estado, mensaje, ...} (RNF-09) y el código HTTP correcto.
Lanzarlos dentro de `transaction.atomic()` revierte la transacción (RNF-29).
"""
from rest_framework import status
from rest_framework.exceptions import APIException


class ErrorDeDominio(APIException):
    """Conflicto con el estado actual del sistema (409 por defecto)."""
    status_code = status.HTTP_409_CONFLICT
    estado = 'conflicto'

    def __init__(self, mensaje, estado=None, codigo_http=None, **extra):
        if codigo_http is not None:
            self.status_code = codigo_http
        self.detail = {'estado': estado or self.estado, 'mensaje': mensaje, 'detail': mensaje, **extra}


class ErrorDeValidacion(ErrorDeDominio):
    status_code = status.HTTP_400_BAD_REQUEST
    estado = 'error_validacion'


class NoEncontrado(ErrorDeDominio):
    status_code = status.HTTP_404_NOT_FOUND
    estado = 'no_encontrado'


class ErrorDeConfiguracion(ErrorDeDominio):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    estado = 'error_config'


class TransicionInvalida(ErrorDeDominio):
    estado = 'transicion_invalida'
