"""
Indicadores de operación del laboratorio para el dashboard (RF-74, RF-74.1, BE-46).

Todo es agregado: conteos, porcentajes, medianas y percentiles. No se devuelven
nombres, documentos ni resultados individuales de pacientes, por eso el
Administrador puede consultarlo sin acceder a datos clínicos (RN-21).
"""
import math
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from statistics import median

from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone

from laboratorio.domain import estados as E
from laboratorio.domain.errores import ErrorDeValidacion
from laboratorio.models import ExamenSolicitado, MuestraFisica, OrdenLaboratorio, ResultadoAnalito

DIAS_POR_DEFECTO = 30
MAX_DIAS = 366
TOP_CUPS = 10


def _fecha(valor, campo):
    if valor in (None, ''):
        return None
    if isinstance(valor, date):
        return valor
    try:
        return date.fromisoformat(str(valor))
    except ValueError:
        raise ErrorDeValidacion('La fecha debe tener el formato AAAA-MM-DD.', campo=campo)


def rango(fecha_inicio=None, fecha_fin=None):
    """Rango de fechas locales [inicio, fin] (ambos incluidos). Por defecto, los últimos 30 días."""
    fin = _fecha(fecha_fin, 'fecha_fin') or timezone.localdate()
    inicio = _fecha(fecha_inicio, 'fecha_inicio') or (fin - timedelta(days=DIAS_POR_DEFECTO - 1))
    if inicio > fin:
        raise ErrorDeValidacion('La fecha de inicio no puede ser posterior a la fecha de fin.', campo='fecha_inicio')
    if (fin - inicio).days + 1 > MAX_DIAS:
        raise ErrorDeValidacion(f'El rango no puede superar {MAX_DIAS} días.', campo='fecha_inicio')
    return inicio, fin


def percentil(valores, p):
    """Percentil con interpolación lineal (p entre 0 y 100)."""
    if not valores:
        return None
    datos = sorted(valores)
    if len(datos) == 1:
        return datos[0]
    k = (len(datos) - 1) * p / 100
    piso, techo = math.floor(k), math.ceil(k)
    if piso == techo:
        return datos[int(k)]
    return datos[piso] + (datos[techo] - datos[piso]) * (k - piso)


def _redondear(valor, decimales=1):
    return None if valor is None else round(valor, decimales)


def _porcentaje(parte, total):
    return round(100 * parte / total, 1) if total else 0.0


def calcular(fecha_inicio=None, fecha_fin=None):
    inicio, fin = rango(fecha_inicio, fecha_fin)
    zona = timezone.get_current_timezone()
    desde = timezone.make_aware(datetime.combine(inicio, time.min), zona)
    hasta = timezone.make_aware(datetime.combine(fin + timedelta(days=1), time.min), zona)

    # (a) Órdenes por estado y por día
    ordenes = OrdenLaboratorio.objects.filter(fecha_orden__gte=desde, fecha_orden__lt=hasta)
    por_estado = [
        {'estado': fila['estado_general__nombre'] or 'Sin estado', 'total': fila['total']}
        for fila in ordenes.values('estado_general__nombre').annotate(total=Count('id')).order_by('-total', 'estado_general__nombre')
    ]
    conteo_dia = {
        fila['dia']: fila['total']
        for fila in ordenes.annotate(dia=TruncDate('fecha_orden', tzinfo=zona)).values('dia').annotate(total=Count('id'))
    }
    por_dia = []
    dia = inicio
    while dia <= fin:
        por_dia.append({'fecha': dia.isoformat(), 'total': conteo_dia.get(dia, 0)})
        dia += timedelta(days=1)

    # (b) Exámenes CUPS más solicitados
    examenes = ExamenSolicitado.objects.filter(orden__fecha_orden__gte=desde, orden__fecha_orden__lt=hasta)
    top_cups = [
        {'codigo': fila['cups__codigo_cups'], 'descripcion': fila['cups__descripcion'], 'total': fila['total']}
        for fila in examenes.values('cups__codigo_cups', 'cups__descripcion').annotate(total=Count('id'))
        .order_by('-total', 'cups__codigo_cups')[:TOP_CUPS]
    ]

    # (c) Tiempo desde la orden hasta la validación (exámenes validados en el periodo)
    validados = ExamenSolicitado.objects.filter(fecha_validacion__gte=desde, fecha_validacion__lt=hasta) \
        .values_list('cups__codigo_cups', 'cups__descripcion', 'orden__fecha_orden', 'fecha_validacion')
    horas_por_cups = defaultdict(list)
    descripciones = {}
    todas = []
    for codigo, descripcion, fecha_orden, fecha_validacion in validados:
        if not fecha_orden or not fecha_validacion or fecha_validacion < fecha_orden:
            continue
        horas = (fecha_validacion - fecha_orden).total_seconds() / 3600
        horas_por_cups[codigo].append(horas)
        descripciones[codigo] = descripcion
        todas.append(horas)
    por_examen = sorted(
        ({'codigo': codigo, 'descripcion': descripciones[codigo], 'total': len(h),
          'mediana_horas': _redondear(median(h)), 'p90_horas': _redondear(percentil(h, 90))}
         for codigo, h in horas_por_cups.items()),
        key=lambda f: (-f['total'], f['codigo']),
    )

    # (d) Muestras rechazadas y motivos (sin contar alícuotas)
    muestras = MuestraFisica.objects.filter(fecha_recoleccion__gte=desde, fecha_recoleccion__lt=hasta,
                                            muestra_madre__isnull=True)
    total_muestras = muestras.count()
    rechazadas = muestras.filter(Q(estado_muestra__nombre=E.MUESTRA_RECHAZADA) | Q(fecha_rechazo__isnull=False))
    total_rechazadas = rechazadas.count()
    motivos = defaultdict(int)
    for fila in rechazadas.values('condicion_muestra').annotate(total=Count('id')):
        condicion = fila['condicion_muestra']
        motivos[condicion if condicion and condicion != 'Normal' else 'Otro motivo'] += fila['total']

    # (e) Resultados anormales y críticos
    resultados = ResultadoAnalito.objects.filter(fecha_procesamiento__gte=desde, fecha_procesamiento__lt=hasta)
    agregado = resultados.aggregate(total=Count('id'), anormales=Count('id', filter=Q(es_anormal=True)),
                                    criticos=Count('id', filter=Q(es_critico=True)))

    return {
        'periodo': {'fecha_inicio': inicio.isoformat(), 'fecha_fin': fin.isoformat(), 'dias': (fin - inicio).days + 1},
        'totales': {
            'ordenes': ordenes.count(),
            'examenes': examenes.count(),
            'muestras': total_muestras,
            'resultados': agregado['total'],
        },
        'ordenes_por_estado': por_estado,
        'ordenes_por_dia': por_dia,
        'cups_mas_solicitados': top_cups,
        'tiempo_orden_validacion': {
            'examenes_validados': len(todas),
            'mediana_horas': _redondear(median(todas)) if todas else None,
            'p90_horas': _redondear(percentil(todas, 90)),
            'por_examen': por_examen,
        },
        'muestras': {
            'total': total_muestras,
            'rechazadas': total_rechazadas,
            'porcentaje_rechazo': _porcentaje(total_rechazadas, total_muestras),
            'motivos': [{'motivo': m, 'total': t} for m, t in sorted(motivos.items(), key=lambda x: (-x[1], x[0]))],
        },
        'resultados': {
            'total': agregado['total'],
            'anormales': agregado['anormales'],
            'criticos': agregado['criticos'],
            'porcentaje_anormales': _porcentaje(agregado['anormales'], agregado['total']),
            'porcentaje_criticos': _porcentaje(agregado['criticos'], agregado['total']),
        },
    }
