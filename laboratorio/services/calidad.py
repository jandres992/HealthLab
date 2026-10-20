"""Control de calidad interno (RF-50): corridas, Westgard, acción correctiva, política."""
from django.db import transaction
from django.utils import timezone

from laboratorio.domain import westgard
from laboratorio.domain.calidad import MODOS
from laboratorio.domain.errores import ErrorDeDominio, ErrorDeValidacion, NoEncontrado
from laboratorio.models import ConfiguracionEquipo, CorridaCCI, LoteControl, PoliticaCCI
from usuarios import auditoria


def registrar_corrida(actor, lote_control_id, valor, lectura=None, request=None):
    """Registra una corrida de control y la evalúa con las reglas de Westgard."""
    with transaction.atomic():
        try:
            lote = LoteControl.objects.select_for_update().select_related('equipo').get(pk=lote_control_id)
        except LoteControl.DoesNotExist:
            raise NoEncontrado('El lote de control no existe.')
        if not lote.activo:
            raise ErrorDeDominio('El lote de control está inactivo.')
        if lote.fecha_vencimiento < timezone.localdate():
            raise ErrorDeDominio(f'El lote de control venció el {lote.fecha_vencimiento:%d/%m/%Y}.')

        z = westgard.z_score(valor, lote.media_objetivo, lote.desviacion_objetivo)
        previas = list(CorridaCCI.objects.filter(lote_control=lote).order_by('-fecha')[:9])
        serie = [c.z_score for c in reversed(previas)] + [z]
        resultado, reglas = westgard.evaluar(serie)

        corrida = CorridaCCI.objects.create(
            lote_control=lote, valor=valor, z_score=z, resultado=resultado, reglas_violadas=reglas,
            fecha=timezone.now(), registrada_por=actor, lectura=lectura,
        )
        auditoria.registrar(request, 'cci.corrida', 'CorridaCCI', corrida.pk,
                            {'equipo': lote.equipo.codigo_equipo, 'parametro': lote.nombre_parametro,
                             'z': str(z), 'resultado': resultado, 'reglas': reglas}, usuario=actor)
    return corrida


def registrar_accion_correctiva(actor, corrida_id, texto, request=None):
    texto = (texto or '').strip()
    if not texto:
        raise ErrorDeValidacion('Describa la acción correctiva.', campo='accion_correctiva')
    with transaction.atomic():
        try:
            corrida = CorridaCCI.objects.select_for_update().get(pk=corrida_id)
        except CorridaCCI.DoesNotExist:
            raise NoEncontrado('La corrida no existe.')
        corrida.accion_correctiva = texto
        corrida.accion_correctiva_por = actor
        corrida.fecha_accion_correctiva = timezone.now()
        corrida.save(update_fields=['accion_correctiva', 'accion_correctiva_por', 'fecha_accion_correctiva'])
        auditoria.registrar(request, 'cci.accion_correctiva', 'CorridaCCI', corrida.pk, {'texto': texto[:200]}, usuario=actor)
    return corrida


def definir_politica(actor, equipo_id, nombre_parametro, modo, request=None):
    """Cambia el modo de la política de CCI (RF-50.1). Nunca es automático: lo decide el bacteriólogo."""
    if modo not in MODOS:
        raise ErrorDeValidacion(f'Modo inválido. Use uno de: {", ".join(MODOS)}.', campo='modo')
    with transaction.atomic():
        try:
            equipo = ConfiguracionEquipo.objects.get(pk=equipo_id)
        except ConfiguracionEquipo.DoesNotExist:
            raise NoEncontrado('El equipo no existe.')
        politica, _ = PoliticaCCI.objects.select_for_update().get_or_create(
            equipo=equipo, nombre_parametro=nombre_parametro, defaults={'modo': 'informativo'}
        )
        anterior = politica.modo
        politica.modo = modo
        politica.actualizada_por = actor
        politica.save()
        auditoria.registrar(request, 'cci.politica', 'PoliticaCCI', politica.pk,
                            {'equipo': equipo.codigo_equipo, 'parametro': nombre_parametro,
                             'de': anterior, 'a': modo}, usuario=actor)
    return politica


def modo_politica(equipo, nombre_parametro):
    p = PoliticaCCI.objects.filter(equipo=equipo, nombre_parametro=nombre_parametro).first()
    return p.modo if p else 'informativo'


def propuesta_endurecimiento(equipo, nombre_parametro):
    """
    RF-50.1.1: sugiere pasar a Advertencia con 20 corridas aceptadas y a Bloqueante con
    30 días consecutivos con CCI. Solo informa; el cambio lo aprueba el bacteriólogo.
    """
    corridas = CorridaCCI.objects.filter(lote_control__equipo=equipo, lote_control__nombre_parametro=nombre_parametro)
    aceptadas = corridas.filter(resultado='aceptada').count()
    dias = corridas.dates('fecha', 'day').count()
    modo = modo_politica(equipo, nombre_parametro)
    sugerido = modo
    if modo == 'informativo' and aceptadas >= 20:
        sugerido = 'advertencia'
    if modo in ('informativo', 'advertencia') and dias >= 30:
        sugerido = 'bloqueante'
    return {'modo_actual': modo, 'corridas_aceptadas': aceptadas, 'dias_con_cci': dias, 'modo_sugerido': sugerido}
