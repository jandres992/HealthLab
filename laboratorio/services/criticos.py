"""Valores críticos: acuse con read-back y escalado (RF-54, RF-54.1, RN-25)."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from laboratorio.domain.errores import ErrorDeDominio, ErrorDeValidacion, NoEncontrado
from laboratorio.models import AcuseValorCritico, OrdenLaboratorio, ResultadoAnalito
from usuarios import auditoria
from usuarios.roles import BACTERIOLOGO, roles_de

from . import notificaciones

MINUTOS_ESCALADO = 30


def criticos_sin_acuse(orden):
    """Resultados críticos de la orden (en exámenes no anulados) que aún no tienen acuse."""
    return list(
        ResultadoAnalito.objects.filter(examen_solicitado__orden=orden, es_critico=True, acuse__isnull=True)
        .exclude(examen_solicitado__estado_examen__nombre='Anulado')
        .select_related('parametro')
    )


def registrar_acuse(actor, resultado_id, comunicado_a, medio, read_back, fecha_declarada=None, observacion='', request=None):
    comunicado_a = (comunicado_a or '').strip()
    if not comunicado_a:
        raise ErrorDeValidacion('Indique a quién se comunicó el valor crítico.', campo='comunicado_a')
    if not read_back:
        raise ErrorDeValidacion('El acuse exige la confirmación por repetición (read-back).', campo='read_back')
    with transaction.atomic():
        try:
            resultado = ResultadoAnalito.objects.select_for_update().select_related('examen_solicitado__orden', 'parametro').get(pk=resultado_id)
        except ResultadoAnalito.DoesNotExist:
            raise NoEncontrado('El resultado no existe.')
        if not resultado.es_critico:
            raise ErrorDeDominio('El resultado no está marcado como crítico.')
        if AcuseValorCritico.objects.filter(resultado=resultado).exists():
            raise ErrorDeDominio('Este valor crítico ya tiene acuse registrado.')
        acuse = AcuseValorCritico.objects.create(
            resultado=resultado, comunicado_a=comunicado_a, medio=medio, read_back=True,
            fecha_comunicacion=timezone.now(), fecha_declarada=fecha_declarada, registrado_por=actor,
            observacion=observacion or '', escalado=resultado.critico_escalado, fecha_escalado=resultado.fecha_escalado,
        )
        auditoria.registrar(request, 'critico.acuse', 'ResultadoAnalito', resultado.pk,
                            {'parametro': resultado.parametro.nombre_parametro, 'valor': resultado.valor_resultado,
                             'comunicado_a': comunicado_a, 'medio': medio}, usuario=actor)
        # Con el acuse, la orden puede cerrarse si ya cumplía lo demás (RN-25).
        from .ordenes import recalcular_estado_orden  # noqa: PLC0415 (ciclo de importación)
        orden = OrdenLaboratorio.objects.select_for_update().select_related('estado_general', 'medico', 'paciente').get(
            pk=resultado.examen_solicitado.orden_id)
        recalcular_estado_orden(orden, actor=actor)
    return acuse


def escalar_pendientes(minutos=MINUTOS_ESCALADO, ahora=None):
    """
    RF-54.1: un crítico sin acuse tras N minutos se escala: se avisa a todos los
    bacteriólogos y de nuevo al médico, y queda marcado. Se ejecuta por comando
    (`manage.py escalar_criticos`) o tarea programada.
    """
    ahora = ahora or timezone.now()
    limite = ahora - timedelta(minutes=minutos)
    pendientes = ResultadoAnalito.objects.filter(
        es_critico=True, acuse__isnull=True, critico_escalado=False, fecha_procesamiento__lte=limite,
    ).exclude(examen_solicitado__estado_examen__nombre='Anulado').select_related(
        'examen_solicitado__orden__medico', 'examen_solicitado__orden__paciente', 'parametro')

    Usuario = get_user_model()
    responsables = [u for u in Usuario.objects.filter(is_active=True) if BACTERIOLOGO in roles_de(u)]
    escalados = 0
    for r in pendientes:
        orden = r.examen_solicitado.orden
        texto = (f"ESCALADO — valor crítico sin acuse hace más de {minutos} min: {r.parametro.nombre_parametro} "
                 f"{r.valor_resultado} {r.unidades_aplicadas or ''} (orden {orden.numero_orden}, paciente "
                 f"{orden.paciente.primer_nombre} {orden.paciente.primer_apellido}). Comunique y registre el acuse.")
        with transaction.atomic():
            r.critico_escalado = True
            r.fecha_escalado = ahora
            r.save(update_fields=['critico_escalado', 'fecha_escalado'])
            notificaciones.notificar_medico(orden, 'alerta_critica', texto)
            for u in responsables:
                notificaciones.notificar(u, 'alerta_critica', texto, orden=orden)
            auditoria.registrar(None, 'critico.escalado', 'ResultadoAnalito', r.pk, {'orden': orden.numero_orden})
        escalados += 1
    return escalados
