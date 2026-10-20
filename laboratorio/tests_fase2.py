"""
Pruebas de la Fase 2: cadena de custodia (RF-57), versionado de rangos (RF-53),
CCI con política configurable (RF-50, RF-50.1, RN-24), acuse de críticos (RF-54, RN-25),
equipos y lotes (RF-51, RF-52).
"""
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from .domain import estados as E
from .domain import westgard
from .models import (
    AcuseValorCritico, CorridaCCI, EventoMuestra, InformeResultados, LoteControl, LoteReactivo,
    Notificacion, OrdenLaboratorio, ParametroExamen, ResultadoAnalito,
)
from .services.criticos import escalar_pendientes
from .tests import BaseLaboratorioTest


class WestgardTests(BaseLaboratorioTest):
    def test_reglas(self):
        self.assertEqual(westgard.evaluar([0.5]), ('aceptada', []))
        self.assertEqual(westgard.evaluar([2.5]), ('advertencia', ['1-2s']))
        self.assertEqual(westgard.evaluar([3.2])[0], 'rechazada')
        self.assertIn('2-2s', westgard.evaluar([2.1, 2.3])[1])
        self.assertIn('R-4s', westgard.evaluar([2.2, -2.4])[1])
        self.assertIn('4-1s', westgard.evaluar([1.1, 1.2, 1.3, 1.1])[1])
        self.assertIn('10x', westgard.evaluar([0.2] * 10)[1])


class CustodiaTests(BaseLaboratorioTest):
    def test_eventos_de_toma_recepcion_y_rechazo(self):
        orden = self.crear_orden()
        self.como(self.tecnico)
        r = self.client.post('/api/v1/muestras/', {'orden': str(orden.pk), 'tipo_muestra': 'Sangre', 'ubicacion': 'Sala 2',
                                                   'fecha_declarada_dispositivo': '2026-10-19T08:00:00Z'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        muestra_id = r.data['datos']['id']
        self.recibir(type('M', (), {'pk': muestra_id})())
        tipos = list(EventoMuestra.objects.filter(muestra_id=muestra_id).order_by('fecha').values_list('tipo', flat=True))
        self.assertEqual(tipos, ['toma', 'recepcion'])
        toma = EventoMuestra.objects.get(muestra_id=muestra_id, tipo='toma')
        self.assertEqual(toma.ubicacion, 'Sala 2')
        self.assertIsNotNone(toma.fecha_declarada_dispositivo)
        self.assertNotEqual(toma.fecha, toma.fecha_declarada_dispositivo)   # hora del servidor manda (RN-27)
        self.assertEqual(toma.rol, 'tecnico_de_enfermeria')

        self.como(self.bact)
        r = self.client.post(f'/api/v1/muestras/{muestra_id}/evento/', {'tipo': 'almacenamiento', 'ubicacion': 'Nevera A3', 'temperatura': '4.0'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        r = self.client.get(f'/api/v1/muestras/{muestra_id}/custodia/')
        self.assertEqual([e['tipo'] for e in r.data], ['toma', 'recepcion', 'almacenamiento'])

    def test_alicuota_y_descarte(self):
        orden = self.crear_orden()
        muestra = self.registrar_muestra(orden)
        self.recibir(muestra)
        self.como(self.bact)
        r = self.client.post(f'/api/v1/muestras/{muestra.pk}/alicuota/', {'ubicacion': 'Centrífuga'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(str(r.data['datos']['muestra_madre']), str(muestra.pk))
        self.assertTrue(EventoMuestra.objects.filter(muestra=muestra, tipo='alicuota').exists())
        # no se descarta con exámenes abiertos
        r = self.client.post(f'/api/v1/muestras/{muestra.pk}/descartar/', {'motivo': 'Protocolo bioseguridad'}, format='json')
        self.assertEqual(r.status_code, 409)
        self.client.post(f'/api/v1/examenes-solicitados/{orden.examenes_solicitados.get().pk}/anular/', {'motivo': 'x'}, format='json')
        r = self.client.post(f'/api/v1/muestras/{muestra.pk}/descartar/', {'motivo': 'Protocolo bioseguridad'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        muestra.refresh_from_db()
        self.assertEqual(muestra.estado_muestra.nombre, E.MUESTRA_DESCARTADA)

    def test_tecnico_no_puede_alicuotar(self):
        orden = self.crear_orden()
        muestra = self.registrar_muestra(orden)
        self.como(self.tecnico)
        self.assertEqual(self.client.post(f'/api/v1/muestras/{muestra.pk}/alicuota/', {}, format='json').status_code, 403)


class VersionadoRangosTests(BaseLaboratorioTest):
    def test_cambio_de_rango_crea_version_y_conserva_resultados(self):
        orden = self.crear_orden()
        muestra = self.registrar_muestra(orden)
        self.recibir(muestra)
        self.procesar(self.enviar_lectura_middleware('BAR-001', {'Leucocitos': '10.5'}))
        resultado = ResultadoAnalito.objects.get(examen_solicitado__orden=orden)
        self.assertFalse(resultado.es_anormal)
        self.assertEqual(resultado.rango_max_aplicado, Decimal('11.000'))

        self.como(self.bact)
        r = self.client.patch(f'/api/v1/parametros/{self.parametro.pk}/', {'rango_referencia_maximo': '10.000'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data['version_nueva'])
        nuevo_id = r.data['datos']['id']
        self.assertNotEqual(nuevo_id, self.parametro.pk)
        self.parametro.refresh_from_db()
        self.assertIsNotNone(self.parametro.vigente_hasta)                 # la anterior quedó cerrada
        self.assertEqual(self.parametro.rango_referencia_maximo, Decimal('11.000'))  # e intacta
        resultado.refresh_from_db()
        self.assertEqual(resultado.rango_max_aplicado, Decimal('11.000'))  # el resultado conserva su copia
        self.assertEqual(ParametroExamen.objects.get(pk=nuevo_id).version_anterior_id, self.parametro.pk)

        # un resultado nuevo usa la versión vigente
        orden2 = self.crear_orden()
        m2 = self.registrar_muestra(orden2, codigo='BAR-002')
        self.recibir(m2)
        self.procesar(self.enviar_lectura_middleware('BAR-002', {'Leucocitos': '10.5'}))
        r2 = ResultadoAnalito.objects.get(examen_solicitado__orden=orden2)
        self.assertTrue(r2.es_anormal)
        self.assertEqual(r2.parametro_id, nuevo_id)

    def test_cambio_sin_rango_edita_en_sitio(self):
        self.como(self.bact)
        r = self.client.patch(f'/api/v1/parametros/{self.parametro.pk}/', {'codigo_loinc': '6690-2'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(r.data['version_nueva'])
        self.assertEqual(r.data['datos']['id'], self.parametro.pk)


class CCITests(BaseLaboratorioTest):
    def _lote(self):
        return LoteControl.objects.create(
            equipo=self.equipo, nombre_parametro='Leucocitos', nivel=1, lote='LC-1',
            fecha_vencimiento=timezone.localdate() + timedelta(days=90),
            media_objetivo=Decimal('7.0'), desviacion_objetivo=Decimal('0.5'),
        )

    def _examen_en_analisis(self):
        orden = self.crear_orden()
        muestra = self.registrar_muestra(orden)
        self.recibir(muestra)
        self.procesar(self.enviar_lectura_middleware('BAR-001', {'Leucocitos': '8'}))
        return orden.examenes_solicitados.get()

    def test_corrida_evaluada_y_estado(self):
        lote = self._lote()
        self.como(self.bact)
        r = self.client.post('/api/v1/cci/', {'lote_control': lote.pk, 'valor': '7.2'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['datos']['resultado'], 'aceptada')
        self.assertEqual(Decimal(r.data['datos']['z_score']), Decimal('0.400'))
        r = self.client.get('/api/v1/cci/estado/', {'equipo': self.equipo.pk, 'nombre_parametro': 'Leucocitos'})
        self.assertEqual(r.data['estado'], 'aceptado')
        self.assertEqual(r.data['modo'], 'informativo')

    def test_modo_informativo_no_bloquea_y_registra_estado(self):
        self._lote()  # hay control definido pero no se corrió hoy
        examen = self._examen_en_analisis()
        self.aprobar(examen)
        examen.refresh_from_db()
        self.assertEqual(examen.estado_cci_validacion, 'no_corrido')

    def test_modo_bloqueante_impide_y_accion_correctiva_libera(self):
        lote = self._lote()
        self.como(self.bact)
        self.client.post('/api/v1/cci/politica/', {'equipo': self.equipo.pk, 'nombre_parametro': 'Leucocitos', 'modo': 'bloqueante'}, format='json')
        examen = self._examen_en_analisis()
        r = self.aprobar(examen, esperado=409)
        self.assertEqual(r.data['estado'], 'cci_bloqueante')
        # corrida rechazada tampoco libera
        self.como(self.bact)
        r = self.client.post('/api/v1/cci/', {'lote_control': lote.pk, 'valor': '9.0'}, format='json')   # z = 4 → 1-3s
        self.assertEqual(r.data['datos']['resultado'], 'rechazada')
        self.assertEqual(self.aprobar(examen, esperado=409).data['estado_cci'], 'rechazado')
        # acción correctiva documentada libera el bloqueo
        corrida_id = r.data['datos']['id']
        r = self.client.post(f'/api/v1/cci/{corrida_id}/accion-correctiva/', {'accion_correctiva': 'Recalibración y nuevo control'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.aprobar(examen)
        examen.refresh_from_db()
        self.assertEqual(examen.estado_cci_validacion, 'aceptado')

    def test_modo_advertencia_exige_justificacion(self):
        self._lote()
        self.como(self.bact)
        self.client.post('/api/v1/cci/politica/', {'equipo': self.equipo.pk, 'nombre_parametro': 'Leucocitos', 'modo': 'advertencia'}, format='json')
        examen = self._examen_en_analisis()
        r = self.aprobar(examen, esperado=409)
        self.assertEqual(r.data['estado'], 'cci_requiere_justificacion')
        self.como(self.bact)
        r = self.client.post(f'/api/v1/examenes-solicitados/{examen.pk}/aprobar/', {'justificacion_cci': 'Control pendiente por falta de material; valor coherente con historia'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        examen.refresh_from_db()
        self.assertIn('falta de material', examen.justificacion_cci)

    def test_politica_solo_bacteriologo_y_auditada(self):
        self.como(self.admin)
        r = self.client.post('/api/v1/cci/politica/', {'equipo': self.equipo.pk, 'nombre_parametro': 'Leucocitos', 'modo': 'bloqueante'}, format='json')
        self.assertEqual(r.status_code, 403)
        self.como(self.bact)
        r = self.client.post('/api/v1/cci/politica/', {'equipo': self.equipo.pk, 'nombre_parametro': 'Leucocitos', 'modo': 'bloqueante'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        from usuarios.models import Auditoria
        self.assertTrue(Auditoria.objects.filter(accion='cci.politica').exists())


class CriticosTests(BaseLaboratorioTest):
    def _critico(self):
        orden = self.crear_orden()
        muestra = self.registrar_muestra(orden)
        self.recibir(muestra)
        self.procesar(self.enviar_lectura_middleware('BAR-001', {'Leucocitos': '45'}))
        return orden, ResultadoAnalito.objects.get(examen_solicitado__orden=orden)

    def test_sin_acuse_no_finaliza_y_con_acuse_si(self):
        orden, resultado = self._critico()
        examen = orden.examenes_solicitados.get()
        r = self.aprobar(examen)
        self.assertFalse(r.data['orden_finalizada'])
        orden.refresh_from_db()
        self.assertEqual(orden.estado_general.nombre, E.ORDEN_RESULTADOS_PARCIALES)   # RN-25
        self.como(self.bact)
        r = self.client.post(f'/api/v1/ordenes/{orden.pk}/finalizar/')
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.data['estado'], 'criticos_sin_acuse')

        self.como(self.medico)
        r = self.client.get('/api/v1/criticos/')
        self.assertEqual(len(r.data), 1)
        r = self.client.post(f'/api/v1/criticos/{resultado.pk}/acusar/', {'comunicado_a': 'Dr. Pérez (hospitalización)', 'medio': 'telefono', 'read_back': False}, format='json')
        self.assertEqual(r.status_code, 400)   # exige read-back
        r = self.client.post(f'/api/v1/criticos/{resultado.pk}/acusar/', {'comunicado_a': 'Dr. Pérez (hospitalización)', 'medio': 'telefono', 'read_back': True}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        orden.refresh_from_db()
        self.assertEqual(orden.estado_general.nombre, E.ORDEN_FINALIZADA)   # el acuse cierra la orden
        self.assertTrue(InformeResultados.objects.filter(orden=orden, tipo='final', vigente=True).exists())
        self.assertEqual(self.client.get('/api/v1/criticos/').data, [])
        r = self.client.post(f'/api/v1/criticos/{resultado.pk}/acusar/', {'comunicado_a': 'x', 'medio': 'telefono', 'read_back': True}, format='json')
        self.assertEqual(r.status_code, 409)   # un solo acuse

    def test_escalado_a_los_30_minutos(self):
        orden, resultado = self._critico()
        self.assertEqual(escalar_pendientes(minutos=30), 0)
        ResultadoAnalito.objects.filter(pk=resultado.pk).update(fecha_procesamiento=timezone.now() - timedelta(minutes=31))
        self.assertEqual(escalar_pendientes(minutos=30), 1)
        self.assertEqual(escalar_pendientes(minutos=30), 0)   # no se repite
        resultado.refresh_from_db()
        self.assertTrue(resultado.critico_escalado)
        self.assertTrue(Notificacion.objects.filter(destinatario=self.bact, tipo='alerta_critica', mensaje__startswith='ESCALADO').exists())
        self.assertTrue(Notificacion.objects.filter(destinatario=self.medico, mensaje__startswith='ESCALADO').exists())

    def test_tecnico_no_acusa(self):
        orden, resultado = self._critico()
        self.como(self.tecnico)
        r = self.client.post(f'/api/v1/criticos/{resultado.pk}/acusar/', {'comunicado_a': 'x', 'medio': 'telefono', 'read_back': True}, format='json')
        self.assertEqual(r.status_code, 403)


class EquiposYLotesTests(BaseLaboratorioTest):
    def test_equipo_fuera_de_servicio_no_acepta_lecturas(self):
        self.como(self.admin)
        r = self.client.post(f'/api/v1/equipos/{self.equipo.pk}/cambiar-estado/', {'estado': 'fuera_servicio', 'motivo': 'Falla bomba'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.client.force_authenticate(None)
        r = self.client.post('/api/v1/lecturas-serial/', {'equipo_origen': 'URIT500C-LAB1', 'trama_cruda': 'x', 'datos_json': {}},
                             format='json', HTTP_X_MIDDLEWARE_TOKEN='tok-secreto')
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.data['estado'], 'equipo_no_operativo')

    def test_calibracion_vencida_bloquea_y_nueva_calibracion_libera(self):
        self.como(self.bact)
        r = self.client.post(f'/api/v1/equipos/{self.equipo.pk}/calibracion/', {
            'fecha': str(timezone.localdate() - timedelta(days=400)), 'vigente_hasta': str(timezone.localdate() - timedelta(days=35)),
            'resultado': 'conforme', 'realizada_por': 'Servicio técnico'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        orden = self.crear_orden()
        muestra = self.registrar_muestra(orden)
        self.recibir(muestra)
        self.client.force_authenticate(None)
        r = self.client.post('/api/v1/lecturas-serial/', {'equipo_origen': 'URIT500C-LAB1', 'codigo_barras_leido': 'BAR-001', 'trama_cruda': 'x', 'datos_json': {'Leucocitos': '8'}},
                             format='json', HTTP_X_MIDDLEWARE_TOKEN='tok-secreto')
        self.assertEqual(r.status_code, 409)
        self.como(self.bact)
        r = self.client.post(f'/api/v1/equipos/{self.equipo.pk}/calibracion/', {
            'fecha': str(timezone.localdate()), 'vigente_hasta': str(timezone.localdate() + timedelta(days=365)),
            'resultado': 'conforme', 'realizada_por': 'Servicio técnico'}, format='json')
        self.assertEqual(r.status_code, 201)
        self.enviar_lectura_middleware('BAR-001', {'Leucocitos': '8'})

    def test_lote_vencido_bloquea_procesamiento_y_lote_queda_en_resultado(self):
        self.como(self.bact)
        r = self.client.post('/api/v1/lotes-reactivo/', {'equipo': self.equipo.pk, 'nombre_parametro': 'Leucocitos', 'nombre': 'Diluyente',
                                                         'lote': 'R-OLD', 'fecha_vencimiento': str(timezone.localdate() - timedelta(days=1))}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(r.data['vencido'])
        orden = self.crear_orden()
        muestra = self.registrar_muestra(orden)
        self.recibir(muestra)
        lectura = self.enviar_lectura_middleware('BAR-001', {'Leucocitos': '8'})
        self.como(self.bact)
        r = self.client.post(f'/api/v1/lecturas-serial/{lectura}/procesar/')
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.data['estado'], 'lote_vencido')
        self.assertEqual(ResultadoAnalito.objects.count(), 0)   # todo o nada
        # se desactiva el vencido y se registra uno vigente
        self.client.patch(f"/api/v1/lotes-reactivo/{r.data['lote'] and LoteReactivo.objects.get(lote='R-OLD').pk}/", {'activo': False}, format='json')
        self.client.post('/api/v1/lotes-reactivo/', {'equipo': self.equipo.pk, 'nombre_parametro': 'Leucocitos', 'nombre': 'Diluyente',
                                                     'lote': 'R-NEW', 'fecha_vencimiento': str(timezone.localdate() + timedelta(days=200))}, format='json')
        r = self.client.post(f'/api/v1/lecturas-serial/{lectura}/procesar/')
        self.assertEqual(r.status_code, 200, r.data)
        resultado = ResultadoAnalito.objects.get()
        self.assertEqual(resultado.lote_reactivo.lote, 'R-NEW')
        self.assertEqual(resultado.equipo, self.equipo)

    def test_medico_no_gestiona_lotes_ni_equipos(self):
        self.como(self.medico)
        self.assertEqual(self.client.get('/api/v1/lotes-reactivo/').status_code, 403)
        self.assertEqual(self.client.post(f'/api/v1/equipos/{self.equipo.pk}/cambiar-estado/', {'estado': 'operativo'}, format='json').status_code, 403)
