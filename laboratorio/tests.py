from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import (
    CatalogoCups,
    EstadoExamen,
    EstadoOrden,
    ExamenSolicitado,
    LecturaEquipoSerial,
    MuestraFisica,
    OrdenLaboratorio,
    Paciente,
    ParametroExamen,
    ResultadoAnalito,
    SexoBiologico,
    TipoDocumentoPaciente,
)

User = get_user_model()


class FlujoLaboratorioAPITests(APITestCase):
    def setUp(self):
        # Superusuario para bypasear permisos de rol en los tests
        self.admin = User.objects.create_superuser(
            username='testadmin', password='testpass123', email='admin@test.local'
        )
        self.client.force_authenticate(user=self.admin)

        # Catálogos necesarios (la BD de test está vacía)
        tipo_cc, _ = TipoDocumentoPaciente.objects.get_or_create(codigo='CC', defaults={'descripcion': 'Cédula de ciudadanía'})
        sexo_f, _ = SexoBiologico.objects.get_or_create(codigo='F', defaults={'descripcion': 'Femenino'})
        estado_registrada, _ = EstadoOrden.objects.get_or_create(nombre='Registrada', defaults={'descripcion': 'Orden registrada'})
        estado_pendiente, _ = EstadoExamen.objects.get_or_create(nombre='Pendiente', defaults={'descripcion': 'Examen pendiente'})
        EstadoExamen.objects.get_or_create(nombre='En Análisis', defaults={'descripcion': 'En análisis'})
        EstadoExamen.objects.get_or_create(nombre='Validado', defaults={'descripcion': 'Validado'})

        self.paciente = Paciente.objects.create(
            tipo_documento=tipo_cc,
            numero_documento='10000001',
            primer_nombre='Ana',
            primer_apellido='Lopez',
            fecha_nacimiento='1990-01-01',
            sexo_biologico=sexo_f,
        )

        self.cups = CatalogoCups.objects.create(codigo_cups='903895', descripcion='Hemograma')
        self.parametro = ParametroExamen.objects.create(
            cups=self.cups,
            nombre_parametro='Leucocitos',
            unidades_medida='cel/uL',
            rango_referencia_minimo='4.000',
            rango_referencia_maximo='11.000',
        )

        self.orden = OrdenLaboratorio.objects.create(
            paciente=self.paciente,
            numero_orden='ORD-001',
            observaciones_clinicas='Control general',
            estado_general=estado_registrada,
        )

        self.muestra = MuestraFisica.objects.create(
            orden=self.orden,
            codigo_barras='BAR-001',
            tipo_muestra='Sangre Total',
            fecha_recoleccion=timezone.now(),
        )

        self.examen = ExamenSolicitado.objects.create(
            orden=self.orden,
            cups=self.cups,
            muestra=self.muestra,
            estado_examen=estado_pendiente,
        )

    def test_eliminacion_logica_paciente(self):
        url = f'/lab/api/v1/pacientes/{self.paciente.id}/'
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.paciente.refresh_from_db()
        self.assertFalse(self.paciente.activo)

        listado = self.client.get('/lab/api/v1/pacientes/')
        self.assertEqual(listado.status_code, status.HTTP_200_OK)
        self.assertEqual(len(listado.data), 0)

    def test_procesar_lectura_y_aprobar_examen(self):
        lectura = LecturaEquipoSerial.objects.create(
            equipo_origen='URIT-500C',
            codigo_barras_leido='BAR-001',
            trama_cruda='RAW|BAR-001|LEU=12.500',
            datos_json={'Leucocitos': '12.500'},
        )

        procesar_url = f'/lab/api/v1/lecturas-serial/{lectura.id}/procesar/'
        procesar_response = self.client.post(procesar_url, {}, format='json')
        self.assertEqual(procesar_response.status_code, status.HTTP_200_OK)

        resultado = ResultadoAnalito.objects.get(examen_solicitado=self.examen, parametro=self.parametro)
        self.assertEqual(resultado.valor_resultado, '12.500')
        self.assertTrue(resultado.es_anormal)

        aprobar_url = f'/lab/api/v1/examenes-solicitados/{self.examen.id}/aprobar/'
        aprobar_response = self.client.post(aprobar_url, {}, format='json')
        self.assertEqual(aprobar_response.status_code, status.HTTP_200_OK)

        self.examen.refresh_from_db()
        self.assertEqual(self.examen.estado_examen.nombre, 'Validado')
