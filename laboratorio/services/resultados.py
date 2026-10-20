"""Casos de uso de resultados: registro manual y procesamiento de lecturas de analizador."""
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from laboratorio.domain import estados as E
from laboratorio.domain.errores import ErrorDeDominio, ErrorDeValidacion, NoEncontrado
from laboratorio.models import ExamenSolicitado, LecturaEquipoSerial, OrdenLaboratorio, ParametroExamen, ResultadoAnalito
from laboratorio.utils import buscar_valor_parametro, es_anormal, obtener_parametro_para_paciente
from usuarios import auditoria

from . import notificaciones
from .ordenes import recalcular_estado_orden


def _a_decimal(valor):
    try:
        return Decimal(str(valor).replace(',', '.').strip())
    except (InvalidOperation, AttributeError, TypeError, ValueError):
        return None


def registrar_resultado(actor, examen, parametro, valor, comentario=None, lectura=None, request=None):
    """
    Crea o actualiza el resultado de un analito en un examen NO validado.
    Usa el rango más específico para el paciente (RN-05), calcula banderas
    (RN-06, RN-07) y guarda la copia del rango aplicado (RF-53).
    Devuelve (resultado, creado, critico).
    """
    if examen.estado_examen.nombre in E.EXAMEN_ESTADOS_FINALES:
        raise ErrorDeDominio(
            f"El examen está '{examen.estado_examen.nombre}'; sus resultados son inmutables (RN-22).",
        )
    if parametro.cups_id != examen.cups_id:
        raise ErrorDeValidacion('El parámetro no pertenece al examen (CUPS distinto).', campo='parametro')
    if valor is None or str(valor).strip() == '':
        raise ErrorDeValidacion('El valor del resultado es obligatorio.', campo='valor_resultado')

    paciente = examen.orden.paciente
    efectivo = obtener_parametro_para_paciente(parametro.cups_id, parametro.nombre_parametro, paciente) or parametro
    anormal, critico = es_anormal(efectivo, valor)

    resultado, creado = ResultadoAnalito.objects.update_or_create(
        examen_solicitado=examen,
        parametro=efectivo,
        defaults={
            'muestra': examen.muestra,
            'lectura_serial': lectura,
            'valor_resultado': str(valor).strip(),
            'valor_numerico': _a_decimal(valor),
            'es_anormal': anormal,
            'es_critico': critico,
            'unidades_aplicadas': efectivo.unidades_medida,
            'rango_min_aplicado': efectivo.rango_referencia_minimo,
            'rango_max_aplicado': efectivo.rango_referencia_maximo,
            'rango_texto_aplicado': efectivo.rango_texto,
            'parametro_version': efectivo.version,
            'comentario_bacteriologo': comentario if comentario is not None else None,
            'registrado_por': actor,
        },
    )
    if critico:
        notificaciones.notificar_medico(
            examen.orden, 'alerta_critica',
            f"ALERTA CRÍTICA — {efectivo.nombre_parametro}: {valor} {efectivo.unidades_medida or ''} "
            f"(Orden {examen.orden.numero_orden}, paciente {paciente.primer_nombre} {paciente.primer_apellido}).",
        )
    return resultado, creado, critico


def registrar_resultado_manual(actor, examen_id, parametro_id, valor, comentario=None, request=None):
    """Ingreso manual por el bacteriólogo (RF-32), en transacción con bloqueo del examen."""
    with transaction.atomic():
        try:
            examen = ExamenSolicitado.objects.select_for_update().select_related(
                'estado_examen', 'orden__paciente', 'orden__medico', 'muestra'
            ).get(pk=examen_id)
        except ExamenSolicitado.DoesNotExist:
            raise NoEncontrado('El examen no existe.')
        try:
            parametro = ParametroExamen.objects.get(pk=parametro_id)
        except ParametroExamen.DoesNotExist:
            raise NoEncontrado('El parámetro no existe.')

        resultado, creado, critico = registrar_resultado(actor, examen, parametro, valor, comentario, request=request)
        if examen.estado_examen.nombre in (E.EXAMEN_PENDIENTE, E.EXAMEN_MUESTRA_RECOLECTADA):
            examen.estado_examen = E.estado_examen(E.EXAMEN_EN_ANALISIS)
            examen.save(update_fields=['estado_examen'])
            orden = OrdenLaboratorio.objects.select_for_update().select_related('estado_general', 'medico', 'paciente').get(pk=examen.orden_id)
            recalcular_estado_orden(orden, actor=actor)
        auditoria.registrar(request, 'resultado.registrar', 'ResultadoAnalito', resultado.pk,
                            {'examen': str(examen.pk), 'parametro': parametro.nombre_parametro,
                             'valor': str(valor), 'critico': critico, 'creado': creado}, usuario=actor)
    return resultado, creado


def procesar_lectura(actor, lectura_id, request=None):
    """
    Convierte la trama del analizador en resultados (RF-31). Todo o nada:
    si falla a mitad, no queda ningún resultado parcial (RNF-29).
    """
    with transaction.atomic():
        try:
            lectura = LecturaEquipoSerial.objects.select_for_update().get(pk=lectura_id)
        except LecturaEquipoSerial.DoesNotExist:
            raise NoEncontrado('La lectura no existe.')
        if not lectura.codigo_barras_leido:
            raise ErrorDeValidacion('La lectura no tiene código de barras asociado.')

        examenes = list(ExamenSolicitado.objects.select_for_update().select_related(
            'cups', 'estado_examen', 'orden__paciente__sexo_biologico', 'orden__medico', 'muestra'
        ).filter(muestra__codigo_barras=lectura.codigo_barras_leido))
        if not examenes:
            raise NoEncontrado('No se encontraron exámenes para el código de barras recibido.',
                               codigo_barras=lectura.codigo_barras_leido)

        creados = actualizados = omitidos = criticos = 0
        ordenes_tocadas = set()
        for examen in examenes:
            if examen.estado_examen.nombre in E.EXAMEN_ESTADOS_FINALES:
                omitidos += 1
                continue
            nombres = list(ParametroExamen.objects.filter(cups=examen.cups, activo=True)
                           .values_list('nombre_parametro', flat=True).distinct())
            for nombre in nombres:
                parametro = obtener_parametro_para_paciente(examen.cups_id, nombre, examen.orden.paciente)
                valor = buscar_valor_parametro(lectura.datos_json, nombre) if parametro else None
                if parametro is None or valor is None:
                    omitidos += 1
                    continue
                _, creado, critico = registrar_resultado(actor, examen, parametro, valor, lectura=lectura, request=request)
                creados += int(creado)
                actualizados += int(not creado)
                criticos += int(critico)
            if examen.estado_examen.nombre in (E.EXAMEN_PENDIENTE, E.EXAMEN_MUESTRA_RECOLECTADA):
                examen.estado_examen = E.estado_examen(E.EXAMEN_EN_ANALISIS)
                examen.save(update_fields=['estado_examen'])
            ordenes_tocadas.add(examen.orden_id)

        for orden_id in ordenes_tocadas:
            orden = OrdenLaboratorio.objects.select_for_update().select_related('estado_general', 'medico', 'paciente').get(pk=orden_id)
            recalcular_estado_orden(orden, actor=actor)

        lectura.procesado = True
        lectura.procesada_por = actor
        lectura.fecha_procesamiento = timezone.now()
        lectura.save(update_fields=['procesado', 'procesada_por', 'fecha_procesamiento'])
        auditoria.registrar(request, 'lectura.procesar', 'LecturaEquipoSerial', lectura.pk,
                            {'creados': creados, 'actualizados': actualizados, 'omitidos': omitidos,
                             'criticos': criticos}, usuario=actor)
    return {
        'lectura_id': str(lectura.pk),
        'resultados_creados': creados,
        'resultados_actualizados': actualizados,
        'resultados_omitidos': omitidos,
        'alertas_criticas': criticos,
    }
