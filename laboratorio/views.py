import logging
import unicodedata
from decimal import Decimal, InvalidOperation

from django.db import models
from django.http import Http404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

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
from .serializers import (
    CatalogoCupsSerializer,
    EstadoExamenSerializer,
    EstadoOrdenSerializer,
    ExamenSolicitadoSerializer,
    LecturaEquipoSerialSerializer,
    MuestraFisicaSerializer,
    OrdenLaboratorioSerializer,
    PacienteSerializer,
    ParametroExamenSerializer,
    ResultadoAnalitoSerializer,
    SexoBiologicoSerializer,
    TipoDocumentoPacienteSerializer,
)

logger = logging.getLogger(__name__)


class EstandarRespuestaViewSet(viewsets.ModelViewSet):
    """
    Clase base que estandariza las respuestas de la API.
    Captura errores comunes y devuelve siempre un JSON con estructura:
    { "estado": "...", "mensaje": "...", "datos/errores": ... }
    acompañado de su respectivo código HTTP.
    """

    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                self.perform_create(serializer)
                return Response(
                    {
                        'estado': 'exito',
                        'mensaje': 'Registro creado correctamente.',
                        'datos': serializer.data,
                    },
                    status=status.HTTP_201_CREATED,
                )

            return Response(
                {
                    'estado': 'error_validacion',
                    'mensaje': 'Los datos enviados no son validos.',
                    'errores': serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error("Error 500 al crear: %s", str(e))
            return Response(
                {
                    'estado': 'error_servidor',
                    'mensaje': 'Ocurrio un error interno al intentar guardar el registro.',
                    'detalle': str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return Response({'estado': 'exito', 'datos': serializer.data}, status=status.HTTP_200_OK)
        except Http404:
            return Response(
                {
                    'estado': 'no_encontrado',
                    'mensaje': 'El registro solicitado no existe en la base de datos.',
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.error("Error 500 al recuperar detalle: %s", str(e))
            return Response(
                {
                    'estado': 'error_servidor',
                    'mensaje': 'Error interno al buscar el registro.',
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def update(self, request, *args, **kwargs):
        try:
            partial = kwargs.pop('partial', False)
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=partial)

            if serializer.is_valid():
                self.perform_update(serializer)
                return Response(
                    {
                        'estado': 'exito',
                        'mensaje': 'Registro actualizado correctamente.',
                        'datos': serializer.data,
                    },
                    status=status.HTTP_200_OK,
                )

            return Response(
                {
                    'estado': 'error_validacion',
                    'mensaje': 'Error en los datos para actualizacion.',
                    'errores': serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Http404:
            return Response(
                {
                    'estado': 'no_encontrado',
                    'mensaje': 'No se puede actualizar. El registro no existe.',
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.error("Error 500 al actualizar: %s", str(e))
            return Response(
                {
                    'estado': 'error_servidor',
                    'mensaje': 'Error interno al actualizar el registro.',
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            self.perform_destroy(instance)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Http404:
            return Response(
                {
                    'estado': 'no_encontrado',
                    'mensaje': 'No se puede eliminar. El registro no existe.',
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        except models.ProtectedError:
            return Response(
                {
                    'estado': 'conflicto',
                    'mensaje': 'No se puede eliminar este registro porque tiene informacion clinica vinculada a el.',
                },
                status=status.HTTP_409_CONFLICT,
            )
        except Exception as e:
            logger.error("Error 500 al eliminar: %s", str(e))
            return Response(
                {
                    'estado': 'error_servidor',
                    'mensaje': 'Error interno al intentar eliminar el registro.',
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


def _normalizar_texto(valor):
    if valor is None:
        return ''
    texto = str(valor).strip().lower()
    texto = unicodedata.normalize('NFKD', texto)
    return ''.join(ch for ch in texto if not unicodedata.combining(ch))


def _buscar_valor_parametro(datos_json, nombre_parametro):
    if not isinstance(datos_json, dict):
        return None

    objetivo = _normalizar_texto(nombre_parametro)
    mapa = {_normalizar_texto(clave): valor for clave, valor in datos_json.items()}

    if objetivo in mapa:
        return mapa[objetivo]

    for clave, valor in mapa.items():
        if objetivo in clave or clave in objetivo:
            return valor

    return None


def _es_anormal(parametro, valor_resultado):
    try:
        valor_numerico = Decimal(str(valor_resultado).replace(',', '.').strip())
    except (InvalidOperation, AttributeError):
        return False

    if parametro.rango_referencia_minimo is not None and valor_numerico < parametro.rango_referencia_minimo:
        return True
    if parametro.rango_referencia_maximo is not None and valor_numerico > parametro.rango_referencia_maximo:
        return True
    return False


class CatalogoCupsViewSet(EstandarRespuestaViewSet):
    queryset = CatalogoCups.objects.all().order_by('codigo_cups')
    serializer_class = CatalogoCupsSerializer


class ParametroExamenViewSet(EstandarRespuestaViewSet):
    queryset = ParametroExamen.objects.all().order_by('nombre_parametro')
    serializer_class = ParametroExamenSerializer


# ==========================================
# Vistas de tablas de referencia (domänio)
# ==========================================

class TipoDocumentoPacienteViewSet(EstandarRespuestaViewSet):
    queryset = TipoDocumentoPaciente.objects.all().order_by('codigo')
    serializer_class = TipoDocumentoPacienteSerializer


class SexoBiologicoViewSet(EstandarRespuestaViewSet):
    queryset = SexoBiologico.objects.all().order_by('codigo')
    serializer_class = SexoBiologicoSerializer


class EstadoOrdenViewSet(EstandarRespuestaViewSet):
    queryset = EstadoOrden.objects.all().order_by('nombre')
    serializer_class = EstadoOrdenSerializer


class EstadoExamenViewSet(EstandarRespuestaViewSet):
    queryset = EstadoExamen.objects.all().order_by('nombre')
    serializer_class = EstadoExamenSerializer


class PacienteViewSet(EstandarRespuestaViewSet):
    serializer_class = PacienteSerializer

    def get_queryset(self):
        incluir_inactivos = str(self.request.query_params.get('incluir_inactivos', 'false')).lower() == 'true'
        queryset = Paciente.objects.all().order_by('-fecha_creacion')
        if incluir_inactivos:
            return queryset
        return queryset.filter(activo=True)

    def destroy(self, request, *args, **kwargs):
        try:
            paciente = self.get_object()  # Http404 si ya está inactivo (no aparece en queryset)
            paciente.activo = False
            paciente.save(update_fields=['activo'])
            return Response(
                {
                    'estado': 'exito',
                    'mensaje': 'Paciente desactivado correctamente (eliminacion logica).',
                },
                status=status.HTTP_200_OK,
            )
        except Http404:
            return Response(
                {
                    'estado': 'no_encontrado',
                    'mensaje': 'No se puede eliminar. El paciente no existe.',
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.error("Error 500 al eliminar logicamente paciente: %s", str(e))
            return Response(
                {
                    'estado': 'error_servidor',
                    'mensaje': 'Error interno al intentar eliminar logicamente el paciente.',
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class OrdenLaboratorioViewSet(EstandarRespuestaViewSet):
    queryset = OrdenLaboratorio.objects.all().order_by('-fecha_orden')
    serializer_class = OrdenLaboratorioSerializer


class MuestraFisicaViewSet(EstandarRespuestaViewSet):
    queryset = MuestraFisica.objects.all().order_by('-fecha_recoleccion')
    serializer_class = MuestraFisicaSerializer


class ExamenSolicitadoViewSet(EstandarRespuestaViewSet):
    queryset = ExamenSolicitado.objects.all()
    serializer_class = ExamenSolicitadoSerializer

    @action(detail=True, methods=['post'], url_path='aprobar')
    def aprobar(self, request, pk=None):
        examen = self.get_object()
        total_parametros = ParametroExamen.objects.filter(cups=examen.cups).count()
        total_resultados = examen.resultados.count()

        if total_parametros > 0 and total_resultados < total_parametros:
            return Response(
                {
                    'estado': 'conflicto',
                    'mensaje': 'No es posible aprobar: faltan resultados por registrar o procesar.',
                    'faltantes': total_parametros - total_resultados,
                },
                status=status.HTTP_409_CONFLICT,
            )

        if total_resultados == 0:
            return Response(
                {
                    'estado': 'error_validacion',
                    'mensaje': 'No se puede aprobar un examen sin resultados.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        examen.estado_examen = EstadoExamen.objects.get(nombre='Validado')
        examen.save(update_fields=['estado_examen'])
        return Response(
            {
                'estado': 'exito',
                'mensaje': 'Examen aprobado y marcado como Validado.',

                'examen_id': str(examen.id),
            },
            status=status.HTTP_200_OK,
        )


class LecturaEquipoSerialViewSet(EstandarRespuestaViewSet):
    queryset = LecturaEquipoSerial.objects.all().order_by('-fecha_recepcion')
    serializer_class = LecturaEquipoSerialSerializer

    @action(detail=True, methods=['post'], url_path='procesar')
    def procesar(self, request, pk=None):
        lectura = self.get_object()

        if not lectura.codigo_barras_leido:
            return Response(
                {
                    'estado': 'error_validacion',
                    'mensaje': 'La lectura no tiene codigo de barras asociado.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        examenes = ExamenSolicitado.objects.select_related('cups').filter(muestra__codigo_barras=lectura.codigo_barras_leido)
        if not examenes.exists():
            return Response(
                {
                    'estado': 'no_encontrado',
                    'mensaje': 'No se encontraron examenes para el codigo de barras recibido.',
                    'codigo_barras': lectura.codigo_barras_leido,
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        resultados_creados = 0
        resultados_actualizados = 0
        resultados_omitidos = 0

        for examen in examenes:
            parametros = ParametroExamen.objects.filter(cups=examen.cups)

            for parametro in parametros:
                valor = _buscar_valor_parametro(lectura.datos_json, parametro.nombre_parametro)
                if valor is None:
                    resultados_omitidos += 1
                    continue

                resultado, created = ResultadoAnalito.objects.update_or_create(
                    examen_solicitado=examen,
                    parametro=parametro,
                    defaults={
                        'lectura_serial': lectura,
                        'valor_resultado': str(valor),
                        'es_anormal': _es_anormal(parametro, valor),
                    },
                )

                if created:
                    resultados_creados += 1
                else:
                    resultados_actualizados += 1

            if examen.estado_examen.nombre in ['Pendiente', 'Muestra Recolectada']:
                examen.estado_examen = EstadoExamen.objects.get(nombre='En Análisis')
                examen.save(update_fields=['estado_examen'])

        lectura.procesado = True
        lectura.save(update_fields=['procesado'])

        return Response(
            {
                'estado': 'exito',
                'mensaje': 'Lectura serial procesada correctamente.',
                'lectura_id': str(lectura.id),
                'resultados_creados': resultados_creados,
                'resultados_actualizados': resultados_actualizados,
                'resultados_omitidos': resultados_omitidos,
            },
            status=status.HTTP_200_OK,
        )


class ResultadoAnalitoViewSet(EstandarRespuestaViewSet):
    queryset = ResultadoAnalito.objects.all().order_by('-fecha_procesamiento')
    serializer_class = ResultadoAnalitoSerializer