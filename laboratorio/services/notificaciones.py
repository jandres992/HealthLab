"""Notificaciones internas (RF-41). Se crean en la transacción de la acción (RNF-29.3)."""
from laboratorio.models import Notificacion


def notificar(destinatario, tipo, mensaje, orden=None):
    """Crea la notificación si el destinatario existe y las tiene habilitadas (RN-14)."""
    if destinatario is None or not getattr(destinatario, 'recibir_notificaciones', True):
        return None
    return Notificacion.objects.create(destinatario=destinatario, tipo=tipo, mensaje=mensaje, orden=orden)


def notificar_medico(orden, tipo, mensaje):
    return notificar(orden.medico, tipo, mensaje, orden=orden)


def notificar_flebotomista(muestra, tipo, mensaje):
    if muestra is None:
        return None
    return notificar(muestra.usuario_recolecta, tipo, mensaje, orden=muestra.orden)
