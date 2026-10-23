"""
Análisis exploratorio de datos (EDA) de la operación del laboratorio (RF-74).

Uso:
    python manage.py analisis_exploratorio
    python manage.py analisis_exploratorio --fecha-inicio 2026-09-01 --fecha-fin 2026-10-31 --salida analisis_salida

Genera, en la carpeta de salida:
- CSV sin datos personales (las órdenes se reemplazan por seudónimos O1, O2…, y del
  paciente solo quedan el sexo y el grupo de edad).
- Gráficas PNG de los indicadores.
- resumen_eda.md con estadísticas descriptivas, valores atípicos y datos faltantes.

Requiere las dependencias de análisis: pip install -r requirements-analisis.txt
"""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from laboratorio.domain import estados as E
from laboratorio.models import ExamenSolicitado, MuestraFisica, OrdenLaboratorio, ResultadoAnalito
from laboratorio.services.indicadores import rango
from laboratorio.utils import calcular_edad_anios

GRUPOS_EDAD = [(0, 4, '0-4'), (5, 17, '5-17'), (18, 29, '18-29'), (30, 44, '30-44'), (45, 59, '45-59'), (60, 200, '60+')]
DIAS_SEMANA = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']


def grupo_edad(edad):
    if edad is None:
        return 'Sin dato'
    for minimo, maximo, etiqueta in GRUPOS_EDAD:
        if minimo <= edad <= maximo:
            return etiqueta
    return 'Sin dato'


def horas_entre(inicio, fin):
    if inicio is None or fin is None or fin < inicio:
        return None
    return round((fin - inicio).total_seconds() / 3600, 3)


def tabla_md(df, columnas=None):
    """Tabla Markdown sencilla (sin depender de tabulate)."""
    if df is None or len(df) == 0:
        return '_Sin datos._\n'
    columnas = columnas or list(df.columns)
    lineas = ['| ' + ' | '.join(str(c) for c in columnas) + ' |', '|' + '---|' * len(columnas)]
    for _, fila in df.iterrows():
        valores = []
        for c in columnas:
            v = fila[c]
            valores.append(f'{v:.2f}' if isinstance(v, float) else str(v))
        lineas.append('| ' + ' | '.join(valores) + ' |')
    return '\n'.join(lineas) + '\n'


class Command(BaseCommand):
    help = 'Análisis exploratorio (pandas) de los datos de operación del laboratorio, sin datos personales.'

    def add_arguments(self, parser):
        parser.add_argument('--fecha-inicio', help='AAAA-MM-DD (por defecto, 30 días antes de la fecha de fin)')
        parser.add_argument('--fecha-fin', help='AAAA-MM-DD (por defecto, hoy)')
        parser.add_argument('--salida', default=str(Path(settings.BASE_DIR) / 'analisis_salida'),
                            help='Carpeta donde se guardan los CSV, las gráficas y el resumen')

    def handle(self, *args, **opciones):
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            import pandas as pd
        except ImportError as exc:
            raise CommandError('Faltan dependencias de análisis. Instale: pip install -r requirements-analisis.txt') from exc

        inicio, fin = rango(opciones.get('fecha_inicio'), opciones.get('fecha_fin'))
        zona = timezone.get_current_timezone()
        desde = timezone.make_aware(timezone.datetime.combine(inicio, timezone.datetime.min.time()), zona)
        hasta = timezone.make_aware(timezone.datetime.combine(fin, timezone.datetime.max.time()), zona)
        salida = Path(opciones['salida'])
        salida.mkdir(parents=True, exist_ok=True)

        # ── 1. Extracción sin datos personales ───────────────────────────────
        filas_ordenes = list(OrdenLaboratorio.objects.filter(fecha_orden__gte=desde, fecha_orden__lte=hasta)
                             .order_by('fecha_orden')
                             .values('id', 'fecha_orden', 'fecha_admision', 'fecha_finalizacion', 'estado_general__nombre',
                                     'paciente__sexo_biologico__codigo', 'paciente__fecha_nacimiento'))
        seudonimo = {f['id']: f'O{i}' for i, f in enumerate(filas_ordenes, start=1)}
        ordenes = pd.DataFrame([{
            'orden': seudonimo[f['id']],
            'fecha_orden': timezone.localtime(f['fecha_orden']),
            'estado': f['estado_general__nombre'],
            'sexo': f['paciente__sexo_biologico__codigo'] or 'Sin dato',
            'grupo_edad': grupo_edad(calcular_edad_anios(f['paciente__fecha_nacimiento'])
                                     if f['paciente__fecha_nacimiento'] else None),
            'horas_orden_admision': horas_entre(f['fecha_orden'], f['fecha_admision']),
            'horas_orden_finalizacion': horas_entre(f['fecha_orden'], f['fecha_finalizacion']),
        } for f in filas_ordenes], columns=['orden', 'fecha_orden', 'estado', 'sexo', 'grupo_edad',
                                            'horas_orden_admision', 'horas_orden_finalizacion'])

        examenes = pd.DataFrame([{
            'orden': seudonimo.get(f['orden_id'], 'fuera_de_periodo'),
            'cups': f['cups__codigo_cups'], 'examen': f['cups__descripcion'], 'estado': f['estado_examen__nombre'],
            'horas_orden_validacion': horas_entre(f['orden__fecha_orden'], f['fecha_validacion']),
        } for f in ExamenSolicitado.objects.filter(orden__fecha_orden__gte=desde, orden__fecha_orden__lte=hasta)
            .values('orden_id', 'cups__codigo_cups', 'cups__descripcion', 'estado_examen__nombre',
                    'orden__fecha_orden', 'fecha_validacion')],
            columns=['orden', 'cups', 'examen', 'estado', 'horas_orden_validacion'])

        muestras = pd.DataFrame([{
            'orden': seudonimo.get(f['orden_id'], 'fuera_de_periodo'),
            'tipo_muestra': f['tipo_muestra'], 'condicion': f['condicion_muestra'] or 'Sin dato',
            'estado': f['estado_muestra__nombre'] or 'Sin dato',
            'rechazada': f['estado_muestra__nombre'] == E.MUESTRA_RECHAZADA or f['fecha_rechazo'] is not None,
            'horas_toma_recepcion': horas_entre(f['fecha_recoleccion'], f['fecha_recepcion']),
        } for f in MuestraFisica.objects.filter(fecha_recoleccion__gte=desde, fecha_recoleccion__lte=hasta,
                                                muestra_madre__isnull=True)
            .values('orden_id', 'tipo_muestra', 'condicion_muestra', 'estado_muestra__nombre', 'fecha_rechazo',
                    'fecha_recoleccion', 'fecha_recepcion')],
            columns=['orden', 'tipo_muestra', 'condicion', 'estado', 'rechazada', 'horas_toma_recepcion'])

        resultados = pd.DataFrame(list(
            ResultadoAnalito.objects.filter(fecha_procesamiento__gte=desde, fecha_procesamiento__lte=hasta)
            .values('parametro__nombre_parametro', 'examen_solicitado__cups__codigo_cups', 'es_anormal', 'es_critico')),
            columns=['parametro__nombre_parametro', 'examen_solicitado__cups__codigo_cups', 'es_anormal', 'es_critico'],
        ).rename(columns={'parametro__nombre_parametro': 'parametro', 'examen_solicitado__cups__codigo_cups': 'cups'})

        for nombre, df in (('ordenes', ordenes), ('examenes', examenes), ('muestras', muestras), ('resultados', resultados)):
            copia = df.copy()
            if 'fecha_orden' in copia:
                copia['fecha_orden'] = copia['fecha_orden'].astype(str)
            copia.to_csv(salida / f'{nombre}.csv', index=False, encoding='utf-8')

        # ── 2. Estadísticas ──────────────────────────────────────────────────
        md = [f'# Análisis exploratorio de la operación del laboratorio\n',
              f'Periodo: {inicio.isoformat()} a {fin.isoformat()} ({(fin - inicio).days + 1} días). '
              f'Generado el {timezone.localtime().strftime("%Y-%m-%d %H:%M")}. '
              'Los datos no incluyen nombres, documentos ni fechas de nacimiento.\n',
              '## 1. Volumen de datos\n',
              tabla_md(pd.DataFrame([{'conjunto': n, 'filas': len(d)} for n, d in
                                     (('Órdenes', ordenes), ('Exámenes', examenes), ('Muestras', muestras),
                                      ('Resultados', resultados))]))]

        graficas = []
        if len(ordenes):
            por_dia = ordenes.set_index('fecha_orden').resample('D').size()
            por_dia = por_dia.reindex(pd.date_range(pd.Timestamp(inicio, tz=zona), pd.Timestamp(fin, tz=zona), freq='D'),
                                      fill_value=0)
            md += ['## 2. Órdenes por día\n',
                   f'- Promedio: {por_dia.mean():.2f} órdenes por día; mediana: {por_dia.median():.0f}; máximo: '
                   f'{por_dia.max()} el {por_dia.idxmax().strftime("%Y-%m-%d")}.\n',
                   f'- Días sin órdenes: {(por_dia == 0).sum()} de {len(por_dia)}.\n']
            semana = ordenes['fecha_orden'].dt.dayofweek.map(lambda d: DIAS_SEMANA[d]).value_counts()
            semana = semana.reindex(DIAS_SEMANA, fill_value=0)
            md += ['\n**Órdenes por día de la semana**\n\n',
                   tabla_md(semana.rename_axis('día').reset_index(name='órdenes'))]
            md += ['\n**Órdenes por estado**\n\n',
                   tabla_md(ordenes['estado'].value_counts().rename_axis('estado').reset_index(name='órdenes'))]
            md += ['\n**Pacientes por sexo y grupo de edad (conteo de órdenes)**\n\n',
                   tabla_md(ordenes.groupby(['sexo', 'grupo_edad']).size().reset_index(name='órdenes'))]

            fig, ax = plt.subplots(figsize=(9, 3.5))
            ax.plot(por_dia.index, por_dia.values, color='#005fb8', marker='o', markersize=3)
            ax.fill_between(por_dia.index, por_dia.values, color='#005fb8', alpha=0.15)
            ax.set_title('Órdenes por día'); ax.set_ylabel('Órdenes'); ax.grid(alpha=0.3)
            fig.autofmt_xdate(); fig.tight_layout(); fig.savefig(salida / 'ordenes_por_dia.png', dpi=150); plt.close(fig)
            graficas.append('ordenes_por_dia.png')

            fig, ax = plt.subplots(figsize=(7, 3.5))
            ax.bar(semana.index, semana.values, color='#00b4e1'); ax.set_title('Órdenes por día de la semana')
            ax.tick_params(axis='x', rotation=30); fig.tight_layout(); fig.savefig(salida / 'ordenes_dia_semana.png', dpi=150)
            plt.close(fig); graficas.append('ordenes_dia_semana.png')

        if len(examenes):
            top = examenes.groupby(['cups', 'examen']).size().sort_values(ascending=False).head(10).reset_index(name='solicitudes')
            md += ['## 3. Exámenes más solicitados\n', tabla_md(top)]
            fig, ax = plt.subplots(figsize=(8, 0.5 * len(top) + 1.5))
            ax.barh(top['examen'].str.slice(0, 40)[::-1], top['solicitudes'][::-1], color='#00488d')
            ax.set_title('Exámenes más solicitados (CUPS)'); fig.tight_layout()
            fig.savefig(salida / 'examenes_top.png', dpi=150); plt.close(fig); graficas.append('examenes_top.png')

            tiempos = examenes['horas_orden_validacion'].dropna()
            md += ['## 4. Tiempo desde la orden hasta la validación\n']
            if len(tiempos):
                q1, q3 = tiempos.quantile(0.25), tiempos.quantile(0.75)
                limite = q3 + 1.5 * (q3 - q1)
                atipicos = int((tiempos > limite).sum())
                md += [f'- Exámenes validados: {len(tiempos)}.\n',
                       f'- Media: {tiempos.mean():.2f} h; mediana: {tiempos.median():.2f} h; percentil 90: '
                       f'{tiempos.quantile(0.9):.2f} h; máximo: {tiempos.max():.2f} h.\n',
                       f'- Valores atípicos (mayores a Q3 + 1,5 × RIC = {limite:.2f} h): {atipicos}.\n']
                por_examen = examenes.dropna(subset=['horas_orden_validacion']).groupby('examen')['horas_orden_validacion'] \
                    .agg(validados='count', mediana='median', maximo='max').reset_index()
                md += ['\n', tabla_md(por_examen)]
                fig, ax = plt.subplots(figsize=(7, 3.5))
                ax.hist(tiempos, bins=min(20, max(5, len(tiempos) // 2)), color='#005fb8', edgecolor='white')
                ax.set_title('Horas desde la orden hasta la validación'); ax.set_xlabel('Horas'); ax.set_ylabel('Exámenes')
                fig.tight_layout(); fig.savefig(salida / 'tiempo_validacion.png', dpi=150); plt.close(fig)
                graficas.append('tiempo_validacion.png')
            else:
                md += ['_No hay exámenes validados en el periodo._\n']

        if len(muestras):
            rechazadas = muestras[muestras['rechazada']]
            md += ['## 5. Muestras y rechazos\n',
                   f'- Muestras: {len(muestras)}; rechazadas: {len(rechazadas)} '
                   f'({100 * len(rechazadas) / len(muestras):.1f} %).\n']
            recepcion = muestras['horas_toma_recepcion'].dropna()
            if len(recepcion):
                md += [f'- Tiempo de la toma a la recepción: mediana {recepcion.median():.2f} h; máximo {recepcion.max():.2f} h.\n']
            md += ['\n**Rechazos por condición de la muestra**\n\n',
                   tabla_md(rechazadas['condicion'].value_counts().rename_axis('condición').reset_index(name='muestras'))]
            md += ['\n**Rechazos por tipo de muestra**\n\n',
                   tabla_md(muestras.groupby('tipo_muestra')['rechazada'].agg(muestras='count', rechazadas='sum').reset_index())]
            if len(rechazadas):
                conteo = rechazadas['condicion'].value_counts()
                fig, ax = plt.subplots(figsize=(6, 3.5))
                ax.bar(conteo.index, conteo.values, color='#c77700'); ax.set_title('Motivos de rechazo')
                fig.tight_layout(); fig.savefig(salida / 'rechazos.png', dpi=150); plt.close(fig); graficas.append('rechazos.png')

        if len(resultados):
            md += ['## 6. Resultados anormales y críticos\n',
                   f'- Resultados: {len(resultados)}; anormales: {int(resultados["es_anormal"].sum())} '
                   f'({100 * resultados["es_anormal"].mean():.1f} %); críticos: {int(resultados["es_critico"].sum())} '
                   f'({100 * resultados["es_critico"].mean():.1f} %).\n\n',
                   tabla_md(resultados.groupby('parametro')[['es_anormal', 'es_critico']].agg(['count', 'sum'])
                            .set_axis(['resultados', 'anormales', '_', 'críticos'], axis=1)
                            .drop(columns='_').sort_values('resultados', ascending=False).head(15).reset_index())]

        md += ['## 7. Datos faltantes\n',
               'Cantidad de valores vacíos por columna. En los tiempos, un vacío indica que el paso aún no ocurre.\n\n']
        faltantes = []
        for nombre, df in (('órdenes', ordenes), ('exámenes', examenes), ('muestras', muestras), ('resultados', resultados)):
            for columna, vacios in df.isna().sum().items():
                if vacios:
                    faltantes.append({'conjunto': nombre, 'columna': columna, 'vacíos': int(vacios), 'filas': len(df)})
        md += [tabla_md(pd.DataFrame(faltantes)) if faltantes else '_No hay valores vacíos._\n']

        if graficas:
            md += ['## 8. Gráficas\n'] + [f'![{g}]({g})\n' for g in graficas]

        (salida / 'resumen_eda.md').write_text('\n'.join(md), encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(
            f'Análisis listo en {salida}: {len(ordenes)} órdenes, {len(examenes)} exámenes, {len(muestras)} muestras, '
            f'{len(resultados)} resultados; {len(graficas)} gráficas.'))
