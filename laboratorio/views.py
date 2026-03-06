from rest_framework import viewsets, status
from rest_framework.response import Response
from django.http import Http404
from django.db import models
# from django.core.exceptions import ObjectDoesNotExist
import logging

from .models import (
    CatalogoCups, ParametroExamen, Paciente, OrdenLaboratorio,
    MuestraFisica, ExamenSolicitado, LecturaEquipoSerial, ResultadoAnalito
)
from .serializers import (
    CatalogoCupsSerializer, ParametroExamenSerializer, PacienteSerializer,
    OrdenLaboratorioSerializer, MuestraFisicaSerializer, ExamenSolicitadoSerializer,
    LecturaEquipoSerialSerializer, ResultadoAnalitoSerializer
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
        """Maneja las peticiones POST (Crear)"""
        try:
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                self.perform_create(serializer)
                return Response({
                    'estado': 'éxito',
                    'mensaje': 'Registro creado correctamente.',
                    'datos': serializer.data
                }, status=status.HTTP_201_CREATED)

            # Error 400: El frontend envió datos incompletos o inválidos
            return Response({
                'estado': 'error_validacion',
                'mensaje': 'Los datos enviados no son válidos.',
                'errores': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f"Error 500 al crear: {str(e)}")
            return Response({
                'estado': 'error_servidor',
                'mensaje': 'Ocurrió un error interno al intentar guardar el registro.',
                'detalle': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def retrieve(self, request, *args, **kwargs):
        """Maneja las peticiones GET de un solo elemento (Detalle)"""
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return Response({
                'estado': 'éxito',
                'datos': serializer.data
            }, status=status.HTTP_200_OK)

        except Http404:
            # Error 404: El UUID enviado en la URL no existe
            return Response({
                'estado': 'no_encontrado',
                'mensaje': 'El registro solicitado no existe en la base de datos.'
            }, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            logger.error(f"Error 500 al recuperar detalle: {str(e)}")
            return Response({
                'estado': 'error_servidor',
                'mensaje': 'Error interno al buscar el registro.',
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def update(self, request, *args, **kwargs):
        """Maneja las peticiones PUT/PATCH (Actualizar)"""
        try:
            partial = kwargs.pop('partial', False)
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=partial)

            if serializer.is_valid():
                self.perform_update(serializer)
                return Response({
                    'estado': 'éxito',
                    'mensaje': 'Registro actualizado correctamente.',
                    'datos': serializer.data
                }, status=status.HTTP_200_OK)

            return Response({
                'estado': 'error_validacion',
                'mensaje': 'Error en los datos para actualización.',
                'errores': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        except Http404:
            return Response({
                'estado': 'no_encontrado',
                'mensaje': 'No se puede actualizar. El registro no existe.'
            }, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            logger.error(f"Error 500 al actualizar: {str(e)}")
            return Response({
                'estado': 'error_servidor',
                'mensaje': 'Error interno al actualizar el registro.',
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def destroy(self, request, *args, **kwargs):
        """Maneja las peticiones DELETE (Eliminar)"""
        try:
            instance = self.get_object()
            self.perform_destroy(instance)
            # 204 No Content es el estándar para un borrado exitoso
            return Response(status=status.HTTP_204_NO_CONTENT)

        except Http404:
            return Response({
                'estado': 'no_encontrado',
                'mensaje': 'No se puede eliminar. El registro no existe.'
            }, status=status.HTTP_404_NOT_FOUND)

        except models.ProtectedError:
            # Error 409: Intento de borrar un registro que tiene llaves foráneas dependientes (Ej: Borrar un paciente que ya tiene órdenes)
            return Response({
                'estado': 'conflicto',
                'mensaje': 'No se puede eliminar este registro porque tiene información clínica vinculada a él.'
            }, status=status.HTTP_409_CONFLICT)

        except Exception as e:
            logger.error(f"Error 500 al eliminar: {str(e)}")
            return Response({
                'estado': 'error_servidor',
                'mensaje': 'Error interno al intentar eliminar el registro.',
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==========================================
# Vistas específicas heredando la clase base
# ==========================================

class CatalogoCupsViewSet(EstandarRespuestaViewSet):
    queryset = CatalogoCups.objects.all().order_by('codigo_cups')
    serializer_class = CatalogoCupsSerializer


class ParametroExamenViewSet(EstandarRespuestaViewSet):
    queryset = ParametroExamen.objects.all().order_by('nombre_parametro')
    serializer_class = ParametroExamenSerializer


class PacienteViewSet(EstandarRespuestaViewSet):
    queryset = Paciente.objects.all().order_by('-fecha_creacion')
    serializer_class = PacienteSerializer


class OrdenLaboratorioViewSet(EstandarRespuestaViewSet):
    queryset = OrdenLaboratorio.objects.all().order_by('-fecha_orden')
    serializer_class = OrdenLaboratorioSerializer


class MuestraFisicaViewSet(EstandarRespuestaViewSet):
    queryset = MuestraFisica.objects.all().order_by('-fecha_recoleccion')
    serializer_class = MuestraFisicaSerializer


class ExamenSolicitadoViewSet(EstandarRespuestaViewSet):
    queryset = ExamenSolicitado.objects.all()
    serializer_class = ExamenSolicitadoSerializer


class LecturaEquipoSerialViewSet(EstandarRespuestaViewSet):
    queryset = LecturaEquipoSerial.objects.all().order_by('-fecha_recepcion')
    serializer_class = LecturaEquipoSerialSerializer


class ResultadoAnalitoViewSet(EstandarRespuestaViewSet):
    queryset = ResultadoAnalito.objects.all().order_by('-fecha_procesamiento')
    serializer_class = ResultadoAnalitoSerializer