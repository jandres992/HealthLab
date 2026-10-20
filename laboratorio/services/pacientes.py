"""Casos de uso de pacientes."""
from django.db import transaction

from laboratorio.domain.errores import NoEncontrado
from laboratorio.models import Paciente
from usuarios import auditoria


def desactivar_paciente(actor, paciente_id, request=None):
    """Eliminación lógica (RF-17, RN-02)."""
    with transaction.atomic():
        try:
            paciente = Paciente.objects.select_for_update().get(pk=paciente_id)
        except Paciente.DoesNotExist:
            raise NoEncontrado('El paciente no existe.')
        if paciente.activo:
            paciente.activo = False
            paciente.save(update_fields=['activo'])
        auditoria.registrar(request, 'paciente.desactivar', 'Paciente', paciente.pk,
                            {'documento': f'{paciente.tipo_documento.codigo} {paciente.numero_documento}'}, usuario=actor)
    return paciente
