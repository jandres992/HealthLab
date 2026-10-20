"""
Idempotencia de peticiones (RNF-33, BE-07).

Si la petición trae la cabecera `Idempotency-Key`, la clave se **reserva
antes** de procesar; un reenvío con la misma clave (mismo usuario o equipo y
misma ruta) devuelve la respuesta original sin repetir la operación. Si dos
peticiones iguales llegan a la vez, la segunda espera el bloqueo del índice
único y luego recibe la respuesta guardada.

Uso:
    @idempotente
    def create(self, request, *args, **kwargs): ...
"""
import hashlib
import json
from functools import wraps

from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.utils.encoders import JSONEncoder

from laboratorio.domain.errores import ErrorDeDominio

CABECERA = 'Idempotency-Key'


def _huella(request, clave):
    usuario = request.user.pk if getattr(request.user, 'is_authenticated', False) else ''
    equipo = ''
    if isinstance(getattr(request, 'data', None), dict):
        equipo = request.data.get('equipo_origen') or ''
    base = f'{usuario}|{equipo}|{request.method}|{request.path}|{clave}'
    return hashlib.sha256(base.encode('utf-8')).hexdigest()


def idempotente(metodo):
    @wraps(metodo)
    def envoltura(self, request, *args, **kwargs):
        clave = request.headers.get(CABECERA)
        if not clave:
            return metodo(self, request, *args, **kwargs)

        from laboratorio.models import ClaveIdempotencia  # noqa: PLC0415

        huella = _huella(request, str(clave)[:128])
        try:
            with transaction.atomic():
                reserva = ClaveIdempotencia.objects.create(
                    huella=huella, clave=str(clave)[:128], ruta=request.path[:200],
                    usuario=request.user if getattr(request.user, 'is_authenticated', False) else None,
                    equipo_origen=(request.data.get('equipo_origen') if isinstance(request.data, dict) else None) or '',
                )
        except IntegrityError:
            existente = ClaveIdempotencia.objects.get(huella=huella)
            if not existente.completada:
                raise ErrorDeDominio('La misma petición está en proceso.', estado='en_proceso')
            respuesta = Response(existente.respuesta, status=existente.codigo_http)
            respuesta['Idempotent-Replayed'] = 'true'
            return respuesta

        respuesta = metodo(self, request, *args, **kwargs)
        if isinstance(respuesta, Response) and status.HTTP_200_OK <= respuesta.status_code < 300:
            reserva.codigo_http = respuesta.status_code
            # UUID, Decimal y datetime no son JSON nativos: se normalizan con el codificador de DRF
            reserva.respuesta = json.loads(json.dumps(respuesta.data, cls=JSONEncoder))
            reserva.completada = True
            reserva.save(update_fields=['codigo_http', 'respuesta', 'completada'])
        else:
            # Un error no consume la clave: el cliente puede corregir y reintentar.
            reserva.delete()
        return respuesta
    return envoltura
