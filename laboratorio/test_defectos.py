"""Pruebas de los defectos encontrados en la prueba de sistema (D-03; D-04 está en usuarios/tests.py)."""
from .models import EventoMuestra, MuestraFisica
from .tests import BaseLaboratorioTest


class TomaSinExamenesTests(BaseLaboratorioTest):
    def test_toma_que_no_vincula_examenes_es_409_y_no_queda_registrada(self):
        orden = self.crear_orden()
        self.registrar_muestra(orden, codigo='BAR-D03-1')
        self.como(self.tecnico)
        r = self.client.post('/api/v1/muestras/', {'orden': str(orden.pk), 'tipo_muestra': 'Sangre Total',
                                                   'codigo_barras': 'BAR-D03-2'}, format='json')
        self.assertEqual(r.status_code, 409, r.data)
        self.assertIn('pendiente de muestra', str(r.data))
        self.assertFalse(MuestraFisica.objects.filter(codigo_barras='BAR-D03-2').exists())
        self.assertEqual(EventoMuestra.objects.filter(muestra__orden=orden, tipo='toma').count(), 1)
