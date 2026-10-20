"""Casos de uso de exámenes: aprobar (validar), rechazar, anular."""
from django.db import transaction
from django.utils import timezone

from laboratorio.domain import estados as E
from laboratorio.domain.errores import ErrorDeDominio, ErrorDeValidacion, NoEncontrado
from laboratorio.models import ExamenSolicitado, OrdenLaboratorio, ParametroExamen
from usuarios import auditoria

from . import notificaciones
from .ordenes import recalcular_estado_orden


def _examen_bloqueado(examen_id):
    try:
        return ExamenSolicitado.objects.select_for_update().select_related(
            'estado_examen', 'cups', 'muestra__usuario_recolecta', 'orden'
        ).get(pk=examen_id)
    except ExamenSolicitado.DoesNotExist:
        raise NoEncontrado('El examen no existe.')


def _orden_bloqueada(orden_id):
    return OrdenLaboratorio.objects.select_for_update().select_related('estado_general', 'medico', 'paciente').get(pk=orden_id)


def _verificar_cci_y_equipo(examen, justificacion):
    """
    RN-24: respeta la política de CCI del analito/equipo de cada resultado y
    exige equipo operativo. Devuelve el estado de CCI más desfavorable.
    """
    from laboratorio.domain import calidad  # noqa: PLC0415
    from .calidad import modo_politica  # noqa: PLC0415
    from .equipos import exigir_operativo  # noqa: PLC0415

    hoy = timezone.localdate()
    peor_estado, modos = 'no_aplica', []
    orden_estados = ['no_aplica', 'aceptado', 'no_corrido', 'rechazado']
    for r in examen.resultados.select_related('equipo', 'parametro'):
        if r.equipo is None:
            continue
        exigir_operativo(r.equipo)
        estado = calidad.estado_cci_del_dia(r.equipo, r.parametro.nombre_parametro, hoy)
        modos.append(modo_politica(r.equipo, r.parametro.nombre_parametro))
        if orden_estados.index(estado) > orden_estados.index(peor_estado):
            peor_estado = estado
    calidad.aplicar_politica(calidad.modo_mas_estricto(modos), peor_estado, justificacion)
    return peor_estado


def aprobar_examen(actor, examen_id, justificacion_cci=None, request=None):
    """
    Validación por el bacteriólogo (RF-34). Es su firma electrónica (RF-34.3):
    queda usuario, fecha y hora; el examen pasa a Validado y no se modifica más.
    Aplica la política de CCI (RF-50.1) y exige equipo operativo (RF-51).
    """
    with transaction.atomic():
        examen = _examen_bloqueado(examen_id)
        desde = examen.estado_examen.nombre
        E.validar_transicion_examen(desde, E.EXAMEN_VALIDADO)

        total_parametros = ParametroExamen.objects.filter(cups=examen.cups, activo=True, vigente_hasta__isnull=True) \
            .values('nombre_parametro').distinct().count()
        total_resultados = examen.resultados.count()
        if total_resultados == 0:
            raise ErrorDeValidacion('No se puede aprobar un examen sin resultados.')
        if total_parametros > 0 and total_resultados < total_parametros:
            raise ErrorDeDominio(
                'No es posible aprobar: faltan resultados por registrar o procesar.',
                faltantes=total_parametros - total_resultados,
            )
        estado_cci = _verificar_cci_y_equipo(examen, justificacion_cci)

        examen.estado_examen = E.estado_examen(E.EXAMEN_VALIDADO)
        examen.validado_por = actor
        examen.fecha_validacion = timezone.now()
        examen.estado_cci_validacion = estado_cci
        examen.justificacion_cci = (justificacion_cci or '').strip() or None
        examen.save(update_fields=['estado_examen', 'validado_por', 'fecha_validacion', 'estado_cci_validacion', 'justificacion_cci'])

        orden = _orden_bloqueada(examen.orden_id)
        _, estado_orden = recalcular_estado_orden(orden, actor=actor)
        auditoria.registrar(request, 'examen.aprobar', 'ExamenSolicitado', examen.pk,
                            {'cups': examen.cups.codigo_cups, 'orden': orden.numero_orden,
                             'estado_orden': estado_orden}, usuario=actor)
    return examen, estado_orden == E.ORDEN_FINALIZADA


def rechazar_examen(actor, examen_id, motivo, request=None):
    """Rechazo del resultado (RF-35): examen → Repetir; avisa al flebotomista y al médico."""
    motivo = (motivo or '').strip()
    if not motivo:
        raise ErrorDeValidacion('Se requiere indicar el motivo_rechazo.', campo='motivo_rechazo')
    with transaction.atomic():
        examen = _examen_bloqueado(examen_id)
        E.validar_transicion_examen(examen.estado_examen.nombre, E.EXAMEN_REPETIR)
        examen.estado_examen = E.estado_examen(E.EXAMEN_REPETIR)
        examen.motivo_rechazo = motivo
        examen.rechazado_por = actor
        examen.fecha_rechazo = timezone.now()
        examen.save(update_fields=['estado_examen', 'motivo_rechazo', 'rechazado_por', 'fecha_rechazo'])

        orden = _orden_bloqueada(examen.orden_id)
        recalcular_estado_orden(orden, actor=actor)

        texto = (f"El examen '{examen.cups.descripcion}' de la orden {orden.numero_orden} fue rechazado. "
                 f"Motivo: {motivo}. Se requiere nueva toma de muestra.")
        notificaciones.notificar_flebotomista(examen.muestra, 'examen_rechazado', texto)
        notificaciones.notificar_medico(orden, 'examen_rechazado',
                                        f"El examen '{examen.cups.descripcion}' de la orden {orden.numero_orden} se repetirá ({motivo}).")
        auditoria.registrar(request, 'examen.rechazar', 'ExamenSolicitado', examen.pk, {'motivo': motivo}, usuario=actor)
    return examen


def anular_examen(actor, examen_id, motivo, request=None):
    """Anulación (RF-35.2): examen que no se realizará. No aplica a Validados."""
    motivo = (motivo or '').strip()
    if not motivo:
        raise ErrorDeValidacion('Se requiere indicar el motivo de anulación.', campo='motivo')
    with transaction.atomic():
        examen = _examen_bloqueado(examen_id)
        desde = examen.estado_examen.nombre
        if desde == E.EXAMEN_VALIDADO:
            raise ErrorDeDominio('Un examen validado no se puede anular; emita una corrección.')
        E.validar_transicion_examen(desde, E.EXAMEN_ANULADO)
        examen.estado_examen = E.estado_examen(E.EXAMEN_ANULADO)
        examen.motivo_anulacion = motivo
        examen.anulado_por = actor
        examen.fecha_anulacion = timezone.now()
        examen.save(update_fields=['estado_examen', 'motivo_anulacion', 'anulado_por', 'fecha_anulacion'])

        orden = _orden_bloqueada(examen.orden_id)
        _, estado_orden = recalcular_estado_orden(orden, actor=actor)
        if orden.medico_id and orden.medico_id != getattr(actor, 'pk', None):
            notificaciones.notificar_medico(orden, 'examen_anulado',
                                            f"El examen '{examen.cups.descripcion}' de la orden {orden.numero_orden} fue anulado: {motivo}.")
        auditoria.registrar(request, 'examen.anular', 'ExamenSolicitado', examen.pk,
                            {'motivo': motivo, 'estado_orden': estado_orden}, usuario=actor)
    return examen
