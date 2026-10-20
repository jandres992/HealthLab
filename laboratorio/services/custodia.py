"""Cadena de custodia de la muestra (RF-57, RNF-37): eventos inmutables, alícuotas, almacenamiento, descarte."""
import uuid

from django.db import transaction
from django.utils import timezone

from laboratorio.domain import estados as E
from laboratorio.domain.errores import ErrorDeDominio, ErrorDeValidacion, NoEncontrado
from laboratorio.models import EventoMuestra, MuestraFisica
from usuarios import auditoria
from usuarios.roles import roles_de


def registrar_evento(actor, muestra, tipo, ubicacion='', observacion='', fecha_declarada=None,
                     temperatura=None, muestra_relacionada=None):
    """Crea el evento con hora del servidor (RN-27). Debe llamarse dentro de la transacción del caso de uso."""
    evento = EventoMuestra.objects.create(
        muestra=muestra, tipo=tipo, fecha=timezone.now(), fecha_declarada_dispositivo=fecha_declarada,
        usuario=actor if getattr(actor, 'is_authenticated', False) else None,
        rol=','.join(sorted(roles_de(actor))) if actor else '',
        ubicacion=ubicacion or '', temperatura=temperatura, observacion=observacion or '',
        muestra_relacionada=muestra_relacionada,
    )
    if ubicacion:
        muestra.ubicacion_actual = ubicacion[:120]
        muestra.save(update_fields=['ubicacion_actual'])
    return evento


def _muestra_bloqueada(muestra_id):
    try:
        return MuestraFisica.objects.select_for_update().select_related('estado_muestra', 'orden').get(pk=muestra_id)
    except MuestraFisica.DoesNotExist:
        raise NoEncontrado('La muestra no existe.')


def anotar(actor, muestra_id, tipo, ubicacion='', observacion='', temperatura=None, request=None):
    """Eventos libres: transporte, almacenamiento, análisis, nota."""
    if tipo not in ('transporte', 'almacenamiento', 'analisis', 'nota'):
        raise ErrorDeValidacion('Tipo de evento no permitido por esta vía.', campo='tipo')
    with transaction.atomic():
        muestra = _muestra_bloqueada(muestra_id)
        if muestra.estado_muestra and muestra.estado_muestra.nombre == E.MUESTRA_DESCARTADA:
            raise ErrorDeDominio('La muestra fue descartada; no admite más eventos.')
        evento = registrar_evento(actor, muestra, tipo, ubicacion, observacion, temperatura=temperatura)
        auditoria.registrar(request, f'muestra.{tipo}', 'MuestraFisica', muestra.pk,
                            {'ubicacion': ubicacion, 'observacion': observacion[:200]}, usuario=actor)
    return evento


def crear_alicuota(actor, muestra_madre_id, tipo_muestra=None, codigo_barras=None, ubicacion='', request=None):
    """Alícuota: muestra hija vinculada a la madre, con evento en ambas."""
    with transaction.atomic():
        madre = _muestra_bloqueada(muestra_madre_id)
        if not madre.estado_muestra or madre.estado_muestra.nombre != E.MUESTRA_RECIBIDA:
            raise ErrorDeDominio('Solo se alicuota una muestra recibida en el laboratorio.')
        hija = MuestraFisica.objects.create(
            orden=madre.orden, codigo_barras=codigo_barras or f"ALI-{uuid.uuid4().hex[:12].upper()}",
            tipo_muestra=tipo_muestra or madre.tipo_muestra, fecha_recoleccion=madre.fecha_recoleccion,
            estado_muestra=madre.estado_muestra, usuario_recolecta=madre.usuario_recolecta,
            condicion_muestra=madre.condicion_muestra, muestra_madre=madre,
            fecha_recepcion=madre.fecha_recepcion, recibida_por=madre.recibida_por, ubicacion_actual=ubicacion,
        )
        registrar_evento(actor, madre, 'alicuota', observacion=f'Alícuota {hija.codigo_barras}', muestra_relacionada=hija)
        registrar_evento(actor, hija, 'alicuota', ubicacion=ubicacion, observacion=f'Obtenida de {madre.codigo_barras}',
                         muestra_relacionada=madre)
        auditoria.registrar(request, 'muestra.alicuota', 'MuestraFisica', hija.pk, {'madre': madre.codigo_barras}, usuario=actor)
    return hija


def descartar(actor, muestra_id, motivo, request=None):
    """Descarte según protocolo de bioseguridad: estado final de la muestra."""
    motivo = (motivo or '').strip()
    if not motivo:
        raise ErrorDeValidacion('Indique el motivo o protocolo de descarte.', campo='motivo')
    with transaction.atomic():
        muestra = _muestra_bloqueada(muestra_id)
        desde = muestra.estado_muestra.nombre if muestra.estado_muestra else E.MUESTRA_RECOLECTADA
        E.validar_transicion_muestra(desde, E.MUESTRA_DESCARTADA)
        pendientes = muestra.examenes.exclude(estado_examen__es_final=True).count()
        if pendientes:
            raise ErrorDeDominio('La muestra tiene exámenes sin cerrar; valide, rechace o anule antes de descartar.',
                                 examenes_pendientes=pendientes)
        muestra.estado_muestra = E.estado_muestra(E.MUESTRA_DESCARTADA)
        muestra.save(update_fields=['estado_muestra'])
        registrar_evento(actor, muestra, 'descarte', observacion=motivo)
        auditoria.registrar(request, 'muestra.descartar', 'MuestraFisica', muestra.pk, {'motivo': motivo}, usuario=actor)
    return muestra
