"""Casos de uso de muestras: registrar toma, recibir en laboratorio, rechazar."""
import uuid

from django.db import transaction
from django.utils import timezone

from laboratorio.domain import estados as E
from laboratorio.domain.errores import ErrorDeDominio, ErrorDeValidacion, NoEncontrado
from laboratorio.models import ExamenSolicitado, MuestraFisica, OrdenLaboratorio
from usuarios import auditoria

from . import notificaciones
from .custodia import registrar_evento
from .ordenes import recalcular_estado_orden


def _muestra_bloqueada(muestra_id):
    try:
        return MuestraFisica.objects.select_for_update().select_related(
            'orden__estado_general', 'orden__medico', 'estado_muestra', 'usuario_recolecta'
        ).get(pk=muestra_id)
    except MuestraFisica.DoesNotExist:
        raise NoEncontrado('La muestra no existe.')


def registrar_muestra(actor, orden, datos, examenes_ids=None, request=None):
    """
    Registra la toma (RF-24). Vincula a la muestra los exámenes de la orden que
    estén Pendientes sin muestra o en Repetir (RF-35.1) y los pasa a
    'Muestra Recolectada'. `examenes_ids` restringe a esos exámenes.
    """
    with transaction.atomic():
        orden = OrdenLaboratorio.objects.select_for_update().select_related('estado_general').get(pk=orden.pk)
        if orden.estado_general.nombre in E.ORDEN_ESTADOS_FINALES:
            raise ErrorDeDominio('La orden está cerrada; no admite nuevas muestras.')

        muestra = MuestraFisica(
            orden=orden,
            codigo_barras=datos.get('codigo_barras') or f"MUE-{uuid.uuid4().hex[:12].upper()}",
            tipo_muestra=datos['tipo_muestra'],
            fecha_recoleccion=datos.get('fecha_recoleccion') or timezone.now(),
            estado_muestra=E.estado_muestra(E.MUESTRA_RECOLECTADA),
            usuario_recolecta=actor,
            condicion_muestra=datos.get('condicion_muestra') or 'Normal',
            fecha_declarada_dispositivo=datos.get('fecha_declarada_dispositivo'),
            ubicacion_actual=datos.get('ubicacion') or '',
        )
        muestra.save()
        registrar_evento(actor, muestra, 'toma', ubicacion=datos.get('ubicacion') or '',
                         observacion=datos.get('observacion') or '', fecha_declarada=datos.get('fecha_declarada_dispositivo'))

        candidatos = orden.examenes_solicitados.select_for_update().select_related('estado_examen')
        if examenes_ids:
            candidatos = candidatos.filter(pk__in=examenes_ids)
        recolectada = E.estado_examen(E.EXAMEN_MUESTRA_RECOLECTADA)
        vinculados = 0
        for examen in candidatos:
            nombre = examen.estado_examen.nombre
            if nombre == E.EXAMEN_REPETIR or (nombre == E.EXAMEN_PENDIENTE and examen.muestra_id is None):
                E.validar_transicion_examen(nombre, E.EXAMEN_MUESTRA_RECOLECTADA)
                examen.muestra = muestra
                examen.estado_examen = recolectada
                examen.save(update_fields=['muestra', 'estado_examen'])
                vinculados += 1
        if examenes_ids and vinculados == 0:
            raise ErrorDeValidacion('Ninguno de los exámenes indicados admite una nueva muestra.')

        auditoria.registrar(request, 'muestra.registrar', 'MuestraFisica', muestra.pk,
                            {'codigo_barras': muestra.codigo_barras, 'orden': orden.numero_orden,
                             'examenes_vinculados': vinculados}, usuario=actor)
    return muestra


def recibir_muestra(actor, muestra_id, request=None):
    """Recepción en el laboratorio (RF-28): muestra → Recibida; exámenes → En Análisis."""
    with transaction.atomic():
        muestra = _muestra_bloqueada(muestra_id)
        desde = muestra.estado_muestra.nombre if muestra.estado_muestra else E.MUESTRA_RECOLECTADA
        E.validar_transicion_muestra(desde, E.MUESTRA_RECIBIDA)
        muestra.estado_muestra = E.estado_muestra(E.MUESTRA_RECIBIDA)
        muestra.fecha_recepcion = timezone.now()
        muestra.recibida_por = actor
        muestra.save(update_fields=['estado_muestra', 'fecha_recepcion', 'recibida_por'])
        registrar_evento(actor, muestra, 'recepcion', ubicacion='Laboratorio')

        en_analisis = E.estado_examen(E.EXAMEN_EN_ANALISIS)
        actualizados = 0
        for examen in muestra.examenes.select_for_update().select_related('estado_examen'):
            if examen.estado_examen.nombre in (E.EXAMEN_PENDIENTE, E.EXAMEN_MUESTRA_RECOLECTADA):
                examen.estado_examen = en_analisis
                examen.save(update_fields=['estado_examen'])
                actualizados += 1

        orden = OrdenLaboratorio.objects.select_for_update().select_related('estado_general', 'medico', 'paciente').get(pk=muestra.orden_id)
        recalcular_estado_orden(orden, actor=actor)
        auditoria.registrar(request, 'muestra.recibir', 'MuestraFisica', muestra.pk,
                            {'examenes_actualizados': actualizados}, usuario=actor)
    return muestra, actualizados


def rechazar_muestra(actor, muestra_id, motivo, condicion=None, request=None):
    """Rechazo por el bacteriólogo (RF-29): exámenes vinculados → Repetir; avisa al flebotomista y al médico."""
    motivo = (motivo or '').strip()
    if not motivo:
        raise ErrorDeValidacion('Se requiere indicar el motivo_rechazo.', campo='motivo_rechazo')
    with transaction.atomic():
        muestra = _muestra_bloqueada(muestra_id)
        desde = muestra.estado_muestra.nombre if muestra.estado_muestra else E.MUESTRA_RECOLECTADA
        E.validar_transicion_muestra(desde, E.MUESTRA_RECHAZADA)
        muestra.estado_muestra = E.estado_muestra(E.MUESTRA_RECHAZADA)
        muestra.motivo_rechazo = motivo
        if condicion:
            muestra.condicion_muestra = condicion
        muestra.fecha_rechazo = timezone.now()
        muestra.rechazada_por = actor
        muestra.save(update_fields=['estado_muestra', 'motivo_rechazo', 'condicion_muestra', 'fecha_rechazo', 'rechazada_por'])
        registrar_evento(actor, muestra, 'rechazo', observacion=f'{muestra.condicion_muestra}: {motivo}')

        repetir = E.estado_examen(E.EXAMEN_REPETIR)
        for examen in muestra.examenes.select_for_update().select_related('estado_examen'):
            nombre = examen.estado_examen.nombre
            if nombre in (E.EXAMEN_MUESTRA_RECOLECTADA, E.EXAMEN_EN_ANALISIS, E.EXAMEN_EN_ESPERA):
                examen.estado_examen = repetir
                examen.motivo_rechazo = f"Muestra rechazada: {motivo}"
                examen.save(update_fields=['estado_examen', 'motivo_rechazo'])

        orden = OrdenLaboratorio.objects.select_for_update().select_related('estado_general', 'medico', 'paciente').get(pk=muestra.orden_id)
        recalcular_estado_orden(orden, actor=actor)

        texto = (f"La muestra {muestra.codigo_barras} de la orden {orden.numero_orden} fue rechazada. "
                 f"Motivo: {motivo}. Por favor repita la toma.")
        notificaciones.notificar_flebotomista(muestra, 'muestra_rechazada', texto)
        notificaciones.notificar_medico(orden, 'muestra_rechazada',
                                        f"La muestra {muestra.codigo_barras} de la orden {orden.numero_orden} fue rechazada ({motivo}); el resultado se retrasa.")
        auditoria.registrar(request, 'muestra.rechazar', 'MuestraFisica', muestra.pk,
                            {'motivo': motivo, 'condicion': muestra.condicion_muestra}, usuario=actor)
    return muestra
