"""
Pruebas del flujo clínico con usuarios por rol (sin bypass de superusuario).
Cubren §15.5, RN-10, RN-19, RN-22, RN-23, RNF-29 y el flujo CU-03 a CU-10.
"""
import shutil
import tempfile
from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from usuarios.models import Auditoria
from usuarios.testing import crear_usuario

from .domain import estados as E
from .models import (
    CatalogoCups, ConfiguracionEquipo, ExamenSolicitado, InformeResultados, MuestraFisica,
    Notificacion, OrdenLaboratorio, Paciente, ParametroExamen, ResultadoAnalito,
    SexoBiologico, TipoDocumentoPaciente,
)

MEDIA_TMP = tempfile.mkdtemp(prefix='healthlab-media-')


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class BaseLaboratorioTest(APITestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_TMP, ignore_errors=True)

    def setUp(self):
        cache.clear()
        self.client = APIClient(raise_request_exception=False)
        self.medico = crear_usuario('medico1', 'medico', p_nombre='Ana', p_apellido='López')
        self.tecnico = crear_usuario('tecnico1', 'tecnico_de_enfermeria')
        self.bact = crear_usuario('bact1', 'bacteriologo', p_nombre='Luis', p_apellido='Ruiz',
                                  registro_profesional='RB-9876')
        self.auditor = crear_usuario('auditor1', 'auditor')
        self.admin = crear_usuario('admin1', 'administrador')

        self.tipo_cc = TipoDocumentoPaciente.objects.create(codigo='CC', descripcion='Cédula')
        self.sexo_f = SexoBiologico.objects.create(codigo='F', descripcion='Femenino')
        self.paciente = Paciente.objects.create(
            tipo_documento=self.tipo_cc, numero_documento='10000001', primer_nombre='Ana',
            primer_apellido='Lopez', fecha_nacimiento='1990-01-01', sexo_biologico=self.sexo_f,
            consentimiento_habeas_data=True,
        )
        self.cups = CatalogoCups.objects.create(codigo_cups='903895', descripcion='Hemograma')
        self.parametro = ParametroExamen.objects.create(
            cups=self.cups, nombre_parametro='Leucocitos', unidades_medida='cel/uL',
            rango_referencia_minimo=Decimal('4.000'), rango_referencia_maximo=Decimal('11.000'),
            rango_panico_minimo=Decimal('1.000'), rango_panico_maximo=Decimal('30.000'),
        )
        self.cups2 = CatalogoCups.objects.create(codigo_cups='902045', descripcion='Glucosa')
        self.parametro2 = ParametroExamen.objects.create(
            cups=self.cups2, nombre_parametro='Glucosa', unidades_medida='mg/dL',
            rango_referencia_minimo=Decimal('70'), rango_referencia_maximo=Decimal('100'),
        )
        self.equipo = ConfiguracionEquipo.objects.create(
            nombre='URIT-500C', codigo_equipo='URIT500C-LAB1', puerto='9600', token_middleware='tok-secreto',
        )

    # ── helpers ──────────────────────────────────────────────────────────────
    def como(self, usuario):
        self.client.force_authenticate(usuario)

    def crear_orden(self, cups_list=None):
        self.como(self.medico)
        r = self.client.post('/api/v1/ordenes/', {
            'paciente': str(self.paciente.pk),
            'examenes': [str(c.pk) for c in (cups_list or [self.cups])],
            'codigo_cie10': 'E11.9',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        return OrdenLaboratorio.objects.get(pk=r.data['datos']['id'])

    def registrar_muestra(self, orden, codigo='BAR-001'):
        self.como(self.tecnico)
        r = self.client.post('/api/v1/muestras/', {'orden': str(orden.pk), 'tipo_muestra': 'Sangre Total',
                                                   'codigo_barras': codigo}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        return MuestraFisica.objects.get(pk=r.data['datos']['id'])

    def recibir(self, muestra):
        self.como(self.bact)
        r = self.client.post(f'/api/v1/muestras/{muestra.pk}/recibir-laboratorio/')
        self.assertEqual(r.status_code, 200, r.data)

    def enviar_lectura_middleware(self, codigo, datos):
        self.client.force_authenticate(None)
        r = self.client.post('/api/v1/lecturas-serial/', {
            'equipo_origen': 'URIT500C-LAB1', 'codigo_barras_leido': codigo,
            'trama_cruda': 'RAW', 'datos_json': datos,
        }, format='json', HTTP_X_MIDDLEWARE_TOKEN='tok-secreto')
        self.assertEqual(r.status_code, 201, r.data)
        return r.data['datos']['id']

    def procesar(self, lectura_id):
        self.como(self.bact)
        r = self.client.post(f'/api/v1/lecturas-serial/{lectura_id}/procesar/')
        self.assertEqual(r.status_code, 200, r.data)
        return r.data

    def aprobar(self, examen, esperado=200):
        self.como(self.bact)
        r = self.client.post(f'/api/v1/examenes-solicitados/{examen.pk}/aprobar/')
        self.assertEqual(r.status_code, esperado, getattr(r, 'data', r.content[:200]))
        return r


class FlujoCompletoTests(BaseLaboratorioTest):
    def test_orden_a_informe_final(self):
        orden = self.crear_orden()
        self.assertTrue(orden.numero_orden.startswith('LAB-'))
        self.assertEqual(orden.estado_general.nombre, E.ORDEN_REGISTRADA)
        examen = orden.examenes_solicitados.get()
        self.assertEqual(examen.estado_examen.nombre, E.EXAMEN_PENDIENTE)
        self.assertTrue(Auditoria.objects.filter(accion='orden.crear', entidad_id=str(orden.pk)).exists())

        muestra = self.registrar_muestra(orden)
        examen.refresh_from_db()
        self.assertEqual(examen.muestra, muestra)
        self.assertEqual(examen.estado_examen.nombre, E.EXAMEN_MUESTRA_RECOLECTADA)

        self.recibir(muestra)
        examen.refresh_from_db(); orden.refresh_from_db()
        self.assertEqual(examen.estado_examen.nombre, E.EXAMEN_EN_ANALISIS)
        self.assertEqual(orden.estado_general.nombre, E.ORDEN_EN_PROCESO)

        lectura_id = self.enviar_lectura_middleware('BAR-001', {'Leucocitos': '12.500'})
        resumen = self.procesar(lectura_id)
        self.assertEqual(resumen['resultados_creados'], 1)
        resultado = ResultadoAnalito.objects.get(examen_solicitado=examen)
        self.assertTrue(resultado.es_anormal)
        self.assertFalse(resultado.es_critico)
        self.assertEqual(resultado.rango_max_aplicado, Decimal('11.000'))   # copia del rango (RF-53)
        self.assertEqual(resultado.muestra, muestra)

        r = self.aprobar(examen)
        self.assertTrue(r.data['orden_finalizada'])
        examen.refresh_from_db(); orden.refresh_from_db()
        self.assertEqual(examen.estado_examen.nombre, E.EXAMEN_VALIDADO)
        self.assertEqual(examen.validado_por, self.bact)
        self.assertEqual(orden.estado_general.nombre, E.ORDEN_FINALIZADA)
        informe = InformeResultados.objects.get(orden=orden, tipo='final', vigente=True)
        self.assertEqual(len(informe.hash_documento), 64)
        self.assertTrue(Notificacion.objects.filter(destinatario=self.medico, tipo='orden_finalizada').exists())

        self.como(self.medico)
        r = self.client.get(f'/api/v1/ordenes/{orden.pk}/reporte-pdf/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')

    def test_valor_critico_notifica_al_medico(self):
        orden = self.crear_orden()
        muestra = self.registrar_muestra(orden)
        self.recibir(muestra)
        self.procesar(self.enviar_lectura_middleware('BAR-001', {'Leucocitos': '45'}))
        self.assertTrue(ResultadoAnalito.objects.get(examen_solicitado__orden=orden).es_critico)
        self.assertTrue(Notificacion.objects.filter(destinatario=self.medico, tipo='alerta_critica').exists())


class ReglasDeCierreTests(BaseLaboratorioTest):
    def _dos_examenes_en_analisis(self):
        orden = self.crear_orden([self.cups, self.cups2])
        muestra = self.registrar_muestra(orden)
        self.recibir(muestra)
        self.procesar(self.enviar_lectura_middleware('BAR-001', {'Leucocitos': '8', 'Glucosa': '90'}))
        ex1 = orden.examenes_solicitados.get(cups=self.cups)
        ex2 = orden.examenes_solicitados.get(cups=self.cups2)
        return orden, ex1, ex2

    def test_repetir_impide_finalizar_y_anular_la_cierra(self):
        orden, ex1, ex2 = self._dos_examenes_en_analisis()
        self.aprobar(ex1)
        self.como(self.bact)
        r = self.client.post(f'/api/v1/examenes-solicitados/{ex2.pk}/rechazar/', {'motivo_rechazo': 'Hemolizada'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        orden.refresh_from_db()
        self.assertEqual(orden.estado_general.nombre, E.ORDEN_RESULTADOS_PARCIALES)

        r = self.client.post(f'/api/v1/ordenes/{orden.pk}/finalizar/')
        self.assertEqual(r.status_code, 409, r.data)
        self.assertEqual(r.data['pendientes'][0]['estado'], E.EXAMEN_REPETIR)
        self.assertFalse(InformeResultados.objects.filter(orden=orden, tipo='final').exists())

        r = self.client.post(f'/api/v1/examenes-solicitados/{ex2.pk}/anular/', {'motivo': 'Paciente no regresó'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        orden.refresh_from_db()
        self.assertEqual(orden.estado_general.nombre, E.ORDEN_FINALIZADA)
        self.assertTrue(InformeResultados.objects.filter(orden=orden, tipo='final', vigente=True).exists())

    def test_informe_parcial_con_hash_encadenado(self):
        orden, ex1, ex2 = self._dos_examenes_en_analisis()
        self.aprobar(ex1)
        self.como(self.medico)
        r = self.client.get(f'/api/v1/ordenes/{orden.pk}/reporte-pdf/')
        self.assertEqual(r.status_code, 200)
        parcial = InformeResultados.objects.get(orden=orden, tipo='parcial')
        self.aprobar(ex2)
        final = InformeResultados.objects.get(orden=orden, tipo='final', vigente=True)
        self.assertEqual(final.hash_anterior, parcial.hash_documento)

    def test_finalizar_sin_resultados_es_409(self):
        orden = self.crear_orden()
        self.como(self.bact)
        r = self.client.post(f'/api/v1/ordenes/{orden.pk}/finalizar/')
        self.assertEqual(r.status_code, 409)

    def test_aprobar_sin_resultados_400_y_sin_muestra_409(self):
        orden = self.crear_orden()
        examen = orden.examenes_solicitados.get()
        r = self.aprobar(examen, esperado=409)        # Pendiente → Validado no es una transición válida
        self.assertEqual(r.data['estado'], 'transicion_invalida')


class IntegridadTests(BaseLaboratorioTest):
    def test_orden_sin_examenes_es_400(self):
        self.como(self.medico)
        r = self.client.post('/api/v1/ordenes/', {'paciente': str(self.paciente.pk), 'examenes': []}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(OrdenLaboratorio.objects.count(), 0)

    def test_orden_con_cups_inexistente_no_deja_orden_a_medias(self):
        self.como(self.medico)
        r = self.client.post('/api/v1/ordenes/', {'paciente': str(self.paciente.pk),
                                                  'examenes': [str(self.cups.pk), '999999']}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertEqual(OrdenLaboratorio.objects.count(), 0)
        self.assertEqual(ExamenSolicitado.objects.count(), 0)

    def test_finalizar_revierte_si_el_pdf_falla(self):
        orden = self.crear_orden()
        muestra = self.registrar_muestra(orden)
        self.recibir(muestra)
        self.procesar(self.enviar_lectura_middleware('BAR-001', {'Leucocitos': '8'}))
        examen = orden.examenes_solicitados.get()
        with mock.patch('laboratorio.services.informes.generar_pdf_orden', side_effect=RuntimeError('reportlab caído')):
            r = self.aprobar(examen, esperado=500)
        examen.refresh_from_db(); orden.refresh_from_db()
        self.assertEqual(examen.estado_examen.nombre, E.EXAMEN_EN_ANALISIS)   # nada quedó a medias (RNF-29)
        self.assertEqual(orden.estado_general.nombre, E.ORDEN_EN_PROCESO)
        self.assertFalse(InformeResultados.objects.exists())
        self.assertFalse(Notificacion.objects.filter(tipo='orden_finalizada').exists())

    def test_estado_no_se_cambia_por_patch(self):
        orden = self.crear_orden()
        self.como(self.medico)
        r = self.client.patch(f'/api/v1/ordenes/{orden.pk}/', {'estado_general': 'Finalizada', 'convenio': 'EPS X'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        orden.refresh_from_db()
        self.assertEqual(orden.estado_general.nombre, E.ORDEN_REGISTRADA)
        self.assertEqual(orden.convenio, 'EPS X')

    def test_resultado_validado_es_inmutable(self):
        orden = self.crear_orden()
        muestra = self.registrar_muestra(orden)
        self.recibir(muestra)
        self.procesar(self.enviar_lectura_middleware('BAR-001', {'Leucocitos': '8'}))
        examen = orden.examenes_solicitados.get()
        self.aprobar(examen)
        self.como(self.bact)
        r = self.client.post('/api/v1/resultados/', {'examen_solicitado': str(examen.pk),
                                                     'parametro': self.parametro.pk, 'valor_resultado': '9'}, format='json')
        self.assertEqual(r.status_code, 409)
        self.assertEqual(ResultadoAnalito.objects.get(examen_solicitado=examen).valor_resultado, '8')

    def test_rechazar_muestra_pasa_examenes_a_repetir(self):
        orden = self.crear_orden()
        muestra = self.registrar_muestra(orden)
        self.como(self.bact)
        r = self.client.post(f'/api/v1/muestras/{muestra.pk}/rechazar/', {'motivo_rechazo': 'Lipémica', 'condicion_muestra': 'Lipemica'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        examen = orden.examenes_solicitados.get()
        self.assertEqual(examen.estado_examen.nombre, E.EXAMEN_REPETIR)
        self.assertTrue(Notificacion.objects.filter(destinatario=self.tecnico, tipo='muestra_rechazada').exists())
        # nueva toma vincula el examen en Repetir (RF-35.1)
        muestra2 = self.registrar_muestra(orden, codigo='BAR-002')
        examen.refresh_from_db()
        self.assertEqual(examen.muestra, muestra2)
        self.assertEqual(examen.estado_examen.nombre, E.EXAMEN_MUESTRA_RECOLECTADA)

    def test_eliminacion_logica_paciente(self):
        self.como(self.medico)
        r = self.client.delete(f'/api/v1/pacientes/{self.paciente.pk}/')
        self.assertEqual(r.status_code, 200)
        self.paciente.refresh_from_db()
        self.assertFalse(self.paciente.activo)
        self.assertEqual(len(self.client.get('/api/v1/pacientes/').data), 0)

    def test_paciente_sin_consentimiento_400(self):
        self.como(self.medico)
        r = self.client.post('/api/v1/pacientes/', {
            'tipo_documento': 'CC', 'numero_documento': '555', 'primer_nombre': 'X', 'primer_apellido': 'Y',
            'fecha_nacimiento': '2000-01-01', 'sexo_biologico': 'F', 'consentimiento_habeas_data': False,
        }, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('consentimiento_habeas_data', r.data['errores'])

    def test_historial_y_version(self):
        orden = self.crear_orden()
        self.assertEqual(orden.version, 1)
        self.como(self.medico)
        self.client.patch(f'/api/v1/ordenes/{orden.pk}/', {'convenio': 'A'}, format='json')
        orden.refresh_from_db()
        self.assertEqual(orden.version, 2)
        self.assertGreaterEqual(orden.history.count(), 2)


class PermisosClinicosTests(BaseLaboratorioTest):
    def test_matriz_basica(self):
        orden = self.crear_orden()
        examen = orden.examenes_solicitados.get()
        casos = [
            (self.tecnico, 'post', '/api/v1/ordenes/', 403),
            (self.bact, 'post', '/api/v1/ordenes/', 403),
            (self.medico, 'post', f'/api/v1/examenes-solicitados/{examen.pk}/aprobar/', 403),
            (self.admin, 'post', f'/api/v1/examenes-solicitados/{examen.pk}/aprobar/', 403),
            (self.medico, 'post', f'/api/v1/ordenes/{orden.pk}/finalizar/', 403),
            (self.admin, 'post', f'/api/v1/ordenes/{orden.pk}/finalizar/', 403),
            (self.medico, 'post', '/api/v1/muestras/', 403),
            (self.tecnico, 'post', f'/api/v1/ordenes/{orden.pk}/admitir/', 200),
            (self.admin, 'get', '/api/v1/pacientes/', 403),
            (self.auditor, 'get', '/api/v1/pacientes/', 200),
            (self.medico, 'get', '/api/v1/catalogo-cups/', 200),
            (self.tecnico, 'get', '/api/v1/tipos-documento/', 200),
            (self.medico, 'post', '/api/v1/catalogo-cups/', 403),
            (self.admin, 'post', '/api/v1/catalogo-cups/', 201),
            (self.medico, 'get', '/api/v1/equipos/', 403),
            (self.bact, 'get', '/api/v1/equipos/', 200),
            (self.auditor, 'get', '/api/v1/ordenes/export-rips/', 200),
            (self.medico, 'get', '/api/v1/ordenes/export-rips/', 403),
        ]
        for usuario, metodo, ruta, esperado in casos:
            self.como(usuario)
            cuerpo = {'codigo_cups': '999001', 'descripcion': 'Nuevo'} if 'catalogo-cups' in ruta and metodo == 'post' else {}
            r = getattr(self.client, metodo)(ruta, cuerpo, format='json')
            self.assertEqual(r.status_code, esperado, f'{usuario.username} {metodo} {ruta}: {r.status_code} {getattr(r, "data", "")}')

    def test_superusuario_sin_rol_no_valida(self):
        from django.contrib.auth import get_user_model
        root = get_user_model().objects.create_superuser('root', 'r@x.co', 'Clave-Segura-2026!')
        orden = self.crear_orden()
        examen = orden.examenes_solicitados.get()
        self.como(root)
        self.assertEqual(self.client.post(f'/api/v1/examenes-solicitados/{examen.pk}/aprobar/').status_code, 403)

    def test_token_middleware(self):
        self.client.force_authenticate(None)
        cuerpo = {'equipo_origen': 'URIT500C-LAB1', 'trama_cruda': 'x', 'datos_json': {}}
        self.assertEqual(self.client.post('/api/v1/lecturas-serial/', cuerpo, format='json').status_code, 401)
        r = self.client.post('/api/v1/lecturas-serial/', cuerpo, format='json', HTTP_X_MIDDLEWARE_TOKEN='malo')
        self.assertEqual(r.status_code, 401)
        r = self.client.post('/api/v1/lecturas-serial/', cuerpo, format='json', HTTP_X_MIDDLEWARE_TOKEN='tok-secreto')
        self.assertEqual(r.status_code, 201)
        self.equipo.activo = False
        self.equipo.save()
        r = self.client.post('/api/v1/lecturas-serial/', cuerpo, format='json', HTTP_X_MIDDLEWARE_TOKEN='tok-secreto')
        self.assertEqual(r.status_code, 401)

    def test_equipos_no_exponen_token(self):
        self.como(self.bact)
        r = self.client.get('/api/v1/equipos/')
        self.assertNotIn('token_middleware', r.data[0])
        self.como(self.admin)
        r = self.client.post(f'/api/v1/equipos/{self.equipo.pk}/regenerar-token/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('token_middleware', r.data)
