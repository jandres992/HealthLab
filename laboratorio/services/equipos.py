"""Gestión de equipos y lotes (RF-51, RF-52)."""
from django.db import transaction
from django.utils import timezone

from laboratorio.domain.errores import ErrorDeDominio, ErrorDeValidacion, NoEncontrado
from laboratorio.models import CalibracionEquipo, ConfiguracionEquipo, LoteReactivo, MantenimientoEquipo
from usuarios import auditoria


def _equipo_bloqueado(equipo_id):
    try:
        return ConfiguracionEquipo.objects.select_for_update().get(pk=equipo_id)
    except ConfiguracionEquipo.DoesNotExist:
        raise NoEncontrado('El equipo no existe.')


def equipo_por_origen(equipo_origen):
    """Resuelve `equipo_origen` de una lectura (código o nombre) al equipo configurado."""
    if not equipo_origen:
        return None
    return ConfiguracionEquipo.objects.filter(codigo_equipo=equipo_origen).first() \
        or ConfiguracionEquipo.objects.filter(nombre=equipo_origen).first()


def exigir_operativo(equipo):
    """RF-51: un equipo fuera de servicio o con calibración vencida no acepta lecturas ni procesa."""
    if equipo is None:
        return
    motivo = equipo.motivo_no_operativo()
    if motivo:
        raise ErrorDeDominio(motivo, estado='equipo_no_operativo', equipo=equipo.codigo_equipo)


def registrar_calibracion(actor, equipo_id, datos, request=None):
    with transaction.atomic():
        equipo = _equipo_bloqueado(equipo_id)
        cal = CalibracionEquipo.objects.create(equipo=equipo, registrada_por=actor, **datos)
        if cal.resultado == 'conforme':
            equipo.calibracion_vigente_hasta = cal.vigente_hasta
            equipo.save(update_fields=['calibracion_vigente_hasta'])
        auditoria.registrar(request, 'equipo.calibracion', 'ConfiguracionEquipo', equipo.pk,
                            {'resultado': cal.resultado, 'vigente_hasta': str(cal.vigente_hasta)}, usuario=actor)
    return cal


def registrar_mantenimiento(actor, equipo_id, datos, nuevo_estado=None, request=None):
    with transaction.atomic():
        equipo = _equipo_bloqueado(equipo_id)
        mant = MantenimientoEquipo.objects.create(equipo=equipo, registrado_por=actor, **datos)
        if nuevo_estado:
            cambiar_estado(actor, equipo.pk, nuevo_estado, f'Mantenimiento {mant.tipo}', request=request, _equipo=equipo)
        auditoria.registrar(request, 'equipo.mantenimiento', 'ConfiguracionEquipo', equipo.pk,
                            {'tipo': mant.tipo, 'fecha': str(mant.fecha)}, usuario=actor)
    return mant


def cambiar_estado(actor, equipo_id, estado, motivo='', request=None, _equipo=None):
    if estado not in dict(ConfiguracionEquipo.ESTADO_CHOICES):
        raise ErrorDeValidacion('Estado de equipo inválido.', campo='estado')
    with transaction.atomic():
        equipo = _equipo or _equipo_bloqueado(equipo_id)
        anterior = equipo.estado
        equipo.estado = estado
        equipo.save(update_fields=['estado'])
        auditoria.registrar(request, 'equipo.estado', 'ConfiguracionEquipo', equipo.pk,
                            {'de': anterior, 'a': estado, 'motivo': motivo}, usuario=actor)
    return equipo


def registrar_lote_reactivo(actor, datos, request=None):
    with transaction.atomic():
        lote = LoteReactivo.objects.create(registrado_por=actor, **datos)
        auditoria.registrar(request, 'lote.registrar', 'LoteReactivo', lote.pk,
                            {'lote': lote.lote, 'vence': str(lote.fecha_vencimiento)}, usuario=actor)
    return lote


def lote_reactivo_vigente(equipo, nombre_parametro, hoy=None):
    """
    Lote activo para (equipo, analito) o, si no hay, el genérico del equipo.
    Devuelve el lote (puede estar vencido: quien lo use decide) o None.
    """
    if equipo is None:
        return None
    qs = LoteReactivo.objects.filter(equipo=equipo, activo=True).order_by('-fecha_apertura', '-creado')
    return qs.filter(nombre_parametro=nombre_parametro).first() or qs.filter(nombre_parametro='').first()


def exigir_lote_no_vencido(lote):
    """RF-52: no se procesa con un lote vencido."""
    if lote is not None and lote.vencido():
        raise ErrorDeDominio(
            f'El lote de reactivo {lote.lote} ({lote.nombre}) venció el {lote.fecha_vencimiento:%d/%m/%Y}.',
            estado='lote_vencido', lote=lote.lote,
        )


def registrar_latido(equipo, datos=None):
    equipo.ultimo_latido = timezone.now()
    equipo.save(update_fields=['ultimo_latido'])
    return equipo
