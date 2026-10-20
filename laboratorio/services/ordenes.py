"""Casos de uso de órdenes: crear, admitir, recalcular estado, finalizar."""
from django.db import transaction
from django.utils import timezone

from laboratorio.domain import estados as E
from laboratorio.domain.errores import ErrorDeDominio, ErrorDeValidacion, NoEncontrado
from laboratorio.models import CatalogoCups, ExamenSolicitado, OrdenLaboratorio, SecuenciaOrden
from usuarios import auditoria

from . import informes, notificaciones


def generar_numero_orden():
    """LAB-YYYYMMDD-NNNN con contador diario bloqueado por fila (RNF-31.1)."""
    hoy = timezone.localdate()
    secuencia, _ = SecuenciaOrden.objects.select_for_update().get_or_create(fecha=hoy)
    secuencia.ultimo += 1
    secuencia.save(update_fields=['ultimo'])
    return f"LAB-{hoy:%Y%m%d}-{secuencia.ultimo:04d}"


def _orden_bloqueada(orden_id):
    try:
        return OrdenLaboratorio.objects.select_for_update().select_related('estado_general', 'medico', 'paciente').get(pk=orden_id)
    except OrdenLaboratorio.DoesNotExist:
        raise NoEncontrado('La orden no existe.')


def crear_orden(actor, paciente, examenes_cups, datos, request=None):
    """
    Crea la orden y todos sus exámenes en una sola transacción (RNF-29.1).
    `examenes_cups`: lista de CatalogoCups o de sus ids/códigos.
    """
    if not examenes_cups:
        raise ErrorDeValidacion('La orden debe tener al menos un examen.', campo='examenes')

    cups_objs = []
    for item in examenes_cups:
        if isinstance(item, CatalogoCups):
            cups = item
        else:
            cups = (CatalogoCups.objects.filter(pk=item).first() if str(item).isdigit() else None) \
                or CatalogoCups.objects.filter(codigo_cups=str(item)).first()
        if cups is None:
            raise ErrorDeValidacion(f"El examen CUPS '{item}' no existe.", campo='examenes')
        if not cups.activo:
            raise ErrorDeValidacion(f"El CUPS {cups.codigo_cups} está inactivo.", campo='examenes')
        if cups not in cups_objs:
            cups_objs.append(cups)

    with transaction.atomic():
        orden = OrdenLaboratorio(
            paciente=paciente,
            medico=datos.get('medico') or actor,
            numero_orden=datos.get('numero_orden') or generar_numero_orden(),
            estado_general=E.estado_orden(E.ORDEN_REGISTRADA),
            observaciones_clinicas=datos.get('observaciones_clinicas'),
            codigo_cie10=datos.get('codigo_cie10'),
            entidad_remitente=datos.get('entidad_remitente'),
            convenio=datos.get('convenio'),
            finalidad_consulta=datos.get('finalidad_consulta') or 'No Aplica',
            causa_externa=datos.get('causa_externa') or 'Enfermedad general',
            tipo_diagnostico=datos.get('tipo_diagnostico') or 'Impresion diagnostica',
        )
        orden.save()
        pendiente = E.estado_examen(E.EXAMEN_PENDIENTE)
        ExamenSolicitado.objects.bulk_create([
            ExamenSolicitado(orden=orden, cups=c, estado_examen=pendiente) for c in cups_objs
        ])
        auditoria.registrar(request, 'orden.crear', 'OrdenLaboratorio', orden.pk,
                            {'numero_orden': orden.numero_orden, 'paciente': str(paciente.pk),
                             'cups': [c.codigo_cups for c in cups_objs]}, usuario=actor)
    return orden


def admitir_orden(actor, orden_id, request=None):
    with transaction.atomic():
        orden = _orden_bloqueada(orden_id)
        if orden.estado_general.nombre in E.ORDEN_ESTADOS_FINALES:
            raise ErrorDeDominio('No se puede admitir una orden cerrada.')
        if orden.fecha_admision:
            raise ErrorDeDominio('La orden ya fue admitida.', fecha_admision=orden.fecha_admision.isoformat())
        orden.fecha_admision = timezone.now()
        orden.usuario_admite = actor
        orden.save(update_fields=['fecha_admision', 'usuario_admite'])
        auditoria.registrar(request, 'orden.admitir', 'OrdenLaboratorio', orden.pk, usuario=actor)
    return orden


def recalcular_estado_orden(orden, actor=None):
    """
    Recalcula y guarda el estado de la orden según sus exámenes (§5.3).
    Debe llamarse con la orden ya bloqueada dentro de una transacción.
    Devuelve (cambio: bool, nombre_estado).
    """
    examenes = list(orden.examenes_solicitados.select_related('estado_examen'))
    actual = orden.estado_general.nombre
    nuevo = E.calcular_estado_orden(examenes, estado_actual=actual)
    if nuevo == E.ORDEN_FINALIZADA:
        # RN-25: con valores críticos sin acuse la orden no cierra; queda en parciales.
        from .criticos import criticos_sin_acuse  # noqa: PLC0415
        if criticos_sin_acuse(orden):
            nuevo = E.ORDEN_RESULTADOS_PARCIALES
    if nuevo == actual:
        return False, actual

    orden.estado_general = E.estado_orden(nuevo)
    campos = ['estado_general']
    if nuevo == E.ORDEN_FINALIZADA:
        orden.fecha_finalizacion = timezone.now()
        orden.finalizada_por = actor
        campos += ['fecha_finalizacion', 'finalizada_por']
    orden.save(update_fields=campos)

    if nuevo == E.ORDEN_FINALIZADA:
        informes.generar_informe(orden, 'final', actor)
        notificaciones.notificar_medico(
            orden, 'orden_finalizada',
            f"Los resultados de la orden {orden.numero_orden} del paciente "
            f"{orden.paciente.primer_nombre} {orden.paciente.primer_apellido} ya están disponibles.",
        )
    elif nuevo == E.ORDEN_RESULTADOS_PARCIALES and actual != E.ORDEN_RESULTADOS_PARCIALES:
        notificaciones.notificar_medico(
            orden, 'resultados_parciales',
            f"La orden {orden.numero_orden} tiene resultados parciales disponibles.",
        )
    return True, nuevo


def finalizar_orden(actor, orden_id, request=None):
    """
    Cierre manual (RF-38): solo si todos los exámenes son finales y hay al
    menos uno Validado. Si no, 409 con la lista de pendientes. El PDF se
    genera en la misma transacción: si falla, la orden no se cierra (RNF-29.2).
    """
    with transaction.atomic():
        orden = _orden_bloqueada(orden_id)
        if orden.estado_general.nombre == E.ORDEN_FINALIZADA:
            raise ErrorDeDominio('La orden ya está finalizada.')
        examenes = list(orden.examenes_solicitados.select_related('estado_examen', 'cups'))
        finalizable, pendientes = E.puede_finalizar(examenes)
        if not finalizable:
            raise ErrorDeDominio(
                'No se puede finalizar: hay exámenes pendientes o ninguno validado.',
                pendientes=[{'id': str(e.pk), 'cups': e.cups.codigo_cups, 'examen': e.cups.descripcion,
                             'estado': e.estado_examen.nombre} for e in pendientes],
            )
        from .criticos import criticos_sin_acuse  # noqa: PLC0415
        criticos = criticos_sin_acuse(orden)
        if criticos:
            raise ErrorDeDominio(
                'No se puede finalizar: hay valores críticos sin acuse de comunicación (RN-25).',
                estado='criticos_sin_acuse',
                criticos=[{'resultado_id': str(r.pk), 'parametro': r.parametro.nombre_parametro,
                           'valor': r.valor_resultado} for r in criticos],
            )
        cambio, _ = recalcular_estado_orden(orden, actor=actor)
        if not cambio:  # ya cumplía las condiciones pero no se había cerrado
            orden.estado_general = E.estado_orden(E.ORDEN_FINALIZADA)
            orden.fecha_finalizacion = timezone.now()
            orden.finalizada_por = actor
            orden.save(update_fields=['estado_general', 'fecha_finalizacion', 'finalizada_por'])
            informes.generar_informe(orden, 'final', actor)
        auditoria.registrar(request, 'orden.finalizar', 'OrdenLaboratorio', orden.pk,
                            {'numero_orden': orden.numero_orden}, usuario=actor)
    return orden
