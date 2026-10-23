"""
Pruebas del cierre de la Fase 1 del producto (§19 del documento de requerimientos):
etiqueta impresa (RF-60 a RF-60.2), impresión del informe guardado (RF-37.6)
y dashboard de indicadores (RF-74, RF-74.1).
"""
import io
import json
import os
import tempfile
import unittest
from datetime import timedelta

from django.core.management import call_command

from django.core.files.base import ContentFile
from django.utils import timezone

from usuarios.models import Auditoria

from .domain import estados as E
from .models import EventoMuestra, InformeResultados
from .services import indicadores as svc_indicadores
from .tests import BaseLaboratorioTest


class EtiquetaMuestraTests(BaseLaboratorioTest):
    def setUp(self):
        super().setUp()
        self.orden = self.crear_orden()
        self.muestra = self.registrar_muestra(self.orden, codigo='MUE-ETQ-001')

    def url(self, **params):
        query = '&'.join(f'{k}={v}' for k, v in params.items())
        return f'/api/v1/muestras/{self.muestra.pk}/etiqueta-pdf/' + (f'?{query}' if query else '')

    def test_tecnico_imprime_y_reimprime(self):
        self.como(self.tecnico)
        r = self.client.get(self.url())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertTrue(r.content.startswith(b'%PDF'))
        self.assertIn('etiqueta_MUE-ETQ-001.pdf', r['Content-Disposition'])

        evento = EventoMuestra.objects.get(muestra=self.muestra, tipo='etiqueta')
        self.assertTrue(evento.observacion.startswith('Impresión de etiqueta (individual, 1 copia)'))
        self.assertEqual(evento.usuario, self.tecnico)
        self.assertTrue(Auditoria.objects.filter(accion='muestra.etiqueta_imprimir', entidad_id=str(self.muestra.pk)).exists())

        r = self.client.get(self.url(formato='hoja', copias=6))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b'%PDF'))
        ultimo = EventoMuestra.objects.filter(muestra=self.muestra, tipo='etiqueta').order_by('-fecha').first()
        self.assertEqual(ultimo.observacion, 'Reimpresión de etiqueta (hoja, 6 copias)')
        self.assertTrue(Auditoria.objects.filter(accion='muestra.etiqueta_reimprimir').exists())

    def test_bacteriologo_puede_reimprimir(self):
        self.como(self.bact)
        self.assertEqual(self.client.get(self.url()).status_code, 200)

    def test_roles_sin_permiso(self):
        for usuario in (self.medico, self.auditor, self.admin):
            self.como(usuario)
            self.assertEqual(self.client.get(self.url()).status_code, 403, usuario.username)
        self.assertFalse(EventoMuestra.objects.filter(muestra=self.muestra, tipo='etiqueta').exists())

    def test_parametros_invalidos(self):
        self.como(self.tecnico)
        self.assertEqual(self.client.get(self.url(formato='zpl')).status_code, 400)
        self.assertEqual(self.client.get(self.url(copias=0)).status_code, 400)
        self.assertEqual(self.client.get(self.url(copias=31)).status_code, 400)
        self.assertEqual(self.client.get(self.url(copias='dos')).status_code, 400)
        self.assertFalse(EventoMuestra.objects.filter(muestra=self.muestra, tipo='etiqueta').exists())

    def test_muestra_descartada_no_imprime(self):
        self.muestra.estado_muestra = E.estado_muestra(E.MUESTRA_DESCARTADA)
        self.muestra.save(update_fields=['estado_muestra'])
        self.como(self.tecnico)
        self.assertEqual(self.client.get(self.url()).status_code, 409)

    def test_muestra_inexistente(self):
        self.como(self.tecnico)
        r = self.client.get('/api/v1/muestras/00000000-0000-0000-0000-000000000000/etiqueta-pdf/')
        self.assertEqual(r.status_code, 404)


class ImprimirInformeTests(BaseLaboratorioTest):
    def setUp(self):
        super().setUp()
        self.orden = self.crear_orden()
        self.informe = InformeResultados.objects.create(orden=self.orden, tipo='final', vigente=True,
                                                        generado_por=self.bact, hash_documento='a' * 64)
        self.informe.archivo_pdf.save('informe_prueba.pdf', ContentFile(b'%PDF-1.4 contenido guardado'), save=True)

    def test_descarga_el_archivo_guardado_sin_generar_otro(self):
        self.como(self.medico)
        r = self.client.get(f'/api/v1/informes/{self.informe.pk}/pdf/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertEqual(r.content, b'%PDF-1.4 contenido guardado')
        self.assertEqual(InformeResultados.objects.filter(orden=self.orden).count(), 1)
        self.assertTrue(Auditoria.objects.filter(accion='informe.imprimir', entidad_id=str(self.informe.pk)).exists())

    def test_tecnico_no_puede(self):
        self.como(self.tecnico)
        self.assertEqual(self.client.get(f'/api/v1/informes/{self.informe.pk}/pdf/').status_code, 403)

    def test_informe_sin_archivo_es_404(self):
        sin_archivo = InformeResultados.objects.create(orden=self.orden, tipo='parcial', vigente=False,
                                                       generado_por=self.bact, hash_documento='b' * 64)
        self.como(self.bact)
        self.assertEqual(self.client.get(f'/api/v1/informes/{sin_archivo.pk}/pdf/').status_code, 404)


class IndicadoresTests(BaseLaboratorioTest):
    URL = '/api/v1/indicadores/'

    def preparar_datos(self):
        # Orden 1: resultado crítico y validado
        orden1 = self.crear_orden()
        muestra1 = self.registrar_muestra(orden1, codigo='BAR-001')
        self.recibir(muestra1)
        self.procesar(self.enviar_lectura_middleware('BAR-001', {'Leucocitos': '45'}))
        examen1 = orden1.examenes_solicitados.get()
        self.aprobar(examen1)
        # Orden 2: muestra rechazada por hemólisis
        orden2 = self.crear_orden([self.cups2])
        muestra2 = self.registrar_muestra(orden2, codigo='BAR-002')
        self.como(self.bact)
        r = self.client.post(f'/api/v1/muestras/{muestra2.pk}/rechazar/',
                             {'motivo_rechazo': 'Muestra hemolizada', 'condicion_muestra': 'Hemolizada'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        return orden1, orden2

    def test_auditor_ve_indicadores_agregados(self):
        self.preparar_datos()
        self.como(self.auditor)
        r = self.client.get(self.URL)
        self.assertEqual(r.status_code, 200, getattr(r, 'data', None))
        d = r.json()
        self.assertEqual(d['periodo']['dias'], 30)
        self.assertEqual(d['totales']['ordenes'], 2)
        self.assertEqual(d['totales']['examenes'], 2)
        self.assertEqual(len(d['ordenes_por_dia']), 30)
        self.assertEqual(sum(f['total'] for f in d['ordenes_por_dia']), 2)
        self.assertEqual(sum(f['total'] for f in d['ordenes_por_estado']), 2)
        self.assertEqual({c['codigo'] for c in d['cups_mas_solicitados']}, {'903895', '902045'})
        self.assertEqual(d['tiempo_orden_validacion']['examenes_validados'], 1)
        self.assertIsNotNone(d['tiempo_orden_validacion']['mediana_horas'])
        self.assertEqual(d['muestras']['total'], 2)
        self.assertEqual(d['muestras']['rechazadas'], 1)
        self.assertEqual(d['muestras']['porcentaje_rechazo'], 50.0)
        self.assertEqual(d['muestras']['motivos'], [{'motivo': 'Hemolizada', 'total': 1}])
        self.assertEqual(d['resultados']['total'], 1)
        self.assertEqual(d['resultados']['criticos'], 1)
        self.assertEqual(d['resultados']['porcentaje_anormales'], 100.0)
        self.assertTrue(Auditoria.objects.filter(accion='indicadores.consultar').exists())

    def test_no_expone_datos_de_pacientes(self):
        self.preparar_datos()
        self.como(self.admin)
        r = self.client.get(self.URL)
        self.assertEqual(r.status_code, 200)
        texto = json.dumps(r.json(), ensure_ascii=False)
        for dato in (self.paciente.numero_documento, self.paciente.primer_nombre, self.paciente.primer_apellido,
                     'BAR-001', 'LAB-'):
            self.assertNotIn(dato, texto)

    def test_roles_clinicos_no_pueden(self):
        for usuario in (self.medico, self.tecnico, self.bact):
            self.como(usuario)
            self.assertEqual(self.client.get(self.URL).status_code, 403, usuario.username)

    def test_rango_de_fechas(self):
        self.como(self.auditor)
        hoy = timezone.localdate()
        r = self.client.get(self.URL, {'fecha_inicio': (hoy - timedelta(days=6)).isoformat(), 'fecha_fin': hoy.isoformat()})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['periodo']['dias'], 7)
        self.assertEqual(self.client.get(self.URL, {'fecha_inicio': '2026-10-10', 'fecha_fin': '2026-10-01'}).status_code, 400)
        self.assertEqual(self.client.get(self.URL, {'fecha_inicio': '10/01/2026'}).status_code, 400)
        self.assertEqual(self.client.get(self.URL, {'fecha_inicio': '2024-01-01', 'fecha_fin': '2026-01-01'}).status_code, 400)

    def test_sin_datos_no_falla(self):
        self.como(self.auditor)
        d = self.client.get(self.URL).json()
        self.assertEqual(d['totales']['ordenes'], 0)
        self.assertIsNone(d['tiempo_orden_validacion']['mediana_horas'])
        self.assertEqual(d['muestras']['porcentaje_rechazo'], 0.0)

    def test_percentil(self):
        self.assertEqual(svc_indicadores.percentil([1, 2, 3, 4], 90), 3.7)
        self.assertEqual(svc_indicadores.percentil([5], 90), 5)
        self.assertIsNone(svc_indicadores.percentil([], 90))


try:
    import pandas  # noqa: F401
    HAY_PANDAS = True
except ImportError:  # el análisis exploratorio usa dependencias opcionales (requirements-analisis.txt)
    HAY_PANDAS = False


@unittest.skipUnless(HAY_PANDAS, 'Requiere pip install -r requirements-analisis.txt')
class AnalisisExploratorioTests(BaseLaboratorioTest):
    def test_genera_archivos_sin_datos_personales(self):
        orden = self.crear_orden()
        muestra = self.registrar_muestra(orden, codigo='BAR-001')
        self.recibir(muestra)
        self.procesar(self.enviar_lectura_middleware('BAR-001', {'Leucocitos': '45'}))
        self.aprobar(orden.examenes_solicitados.get())

        with tempfile.TemporaryDirectory() as carpeta:
            call_command('analisis_exploratorio', salida=carpeta, stdout=io.StringIO())
            archivos = set(os.listdir(carpeta))
            for esperado in ('ordenes.csv', 'examenes.csv', 'muestras.csv', 'resultados.csv', 'resumen_eda.md',
                             'ordenes_por_dia.png', 'tiempo_validacion.png'):
                self.assertIn(esperado, archivos)
            contenido = ''.join(open(os.path.join(carpeta, f), encoding='utf-8').read()
                                for f in archivos if f.endswith(('.csv', '.md')))
        for dato in (self.paciente.numero_documento, self.paciente.primer_nombre, self.paciente.primer_apellido,
                     str(orden.pk), orden.numero_orden, 'BAR-001', '1990-01-01'):
            self.assertNotIn(dato, contenido)
