"""
Manejador global de excepciones de la API (RNF-09, BE-04).

Convierte cualquier excepción de DRF al formato estándar del sistema:
    { "estado": ..., "mensaje": ..., "errores": {...} }

Se conserva también la clave `detail` para compatibilidad con los clientes
que la leen (la app Expo actual).
"""
from rest_framework import status
from rest_framework.views import exception_handler as manejador_drf

ESTADOS_POR_CODIGO = {
    status.HTTP_400_BAD_REQUEST: ('error_validacion', 'Los datos enviados no son válidos.'),
    status.HTTP_401_UNAUTHORIZED: ('no_autenticado', 'Se requiere iniciar sesión.'),
    status.HTTP_403_FORBIDDEN: ('no_autorizado', 'No tienes permisos para realizar esta acción.'),
    status.HTTP_404_NOT_FOUND: ('no_encontrado', 'El recurso solicitado no existe.'),
    status.HTTP_405_METHOD_NOT_ALLOWED: ('metodo_no_permitido', 'Método no permitido.'),
    status.HTTP_409_CONFLICT: ('conflicto', 'La operación entra en conflicto con el estado actual.'),
    status.HTTP_429_TOO_MANY_REQUESTS: ('limite_excedido', 'Demasiados intentos. Espera e inténtalo de nuevo.'),
}


def manejador_excepciones(exc, context):
    respuesta = manejador_drf(exc, context)
    if respuesta is None:
        return None  # Excepciones no-DRF → Django las convierte en 500

    estado, mensaje_defecto = ESTADOS_POR_CODIGO.get(
        respuesta.status_code, ('error', 'Ocurrió un error al procesar la solicitud.')
    )
    datos = respuesta.data

    errores = None
    mensaje = mensaje_defecto
    if isinstance(datos, dict):
        if 'detail' in datos and len(datos) == 1:
            mensaje = str(datos['detail'])
        elif 'estado' in datos:
            # Ya viene en el formato estándar (lanzado desde un servicio)
            return respuesta
        else:
            errores = datos
    elif isinstance(datos, list):
        errores = {'non_field_errors': datos}

    cuerpo = {'estado': estado, 'mensaje': mensaje, 'detail': mensaje}
    if errores:
        cuerpo['errores'] = errores
    respuesta.data = cuerpo
    return respuesta
