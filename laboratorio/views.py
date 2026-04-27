"""
Views del módulo laboratorio — HealthLab LIMS.
Implementa los flujos clínicos de las fases 1-6.
"""
import csv
import hashlib
import logging
import secrets

from django.core.files.base import ContentFile
from django.http import Http404, HttpResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from django.db.models import ProtectedError, Q

from .models import (
    CatalogoCups,
    ConfiguracionEquipo,
    EstadoExamen,
    EstadoMuestra,
    EstadoOrden,
    ExamenSolicitado,
    InformeResultados,
    LecturaEquipoSerial,
    MuestraFisica,
    Notificacion,
    OrdenLaboratorio,
    Paciente,
    ParametroExamen,
    ResultadoAnalito,
    SexoBiologico,
    TipoDocumentoPaciente,
)
from .serializers import (
    CatalogoCupsSerializer,
    ConfiguracionEquipoSerializer,
    EstadoExamenSerializer,
    EstadoMuestraSerializer,
    EstadoOrdenSerializer,
    ExamenSolicitadoSerializer,
    InformeResultadosSerializer,
    LecturaEquipoSerialSerializer,
    MuestraFisicaSerializer,
    NotificacionSerializer,
    OrdenLaboratorioSerializer,
    PacienteSerializer,
    ParametroExamenSerializer,
    ResultadoAnalitoSerializer,
    SexoBiologicoSerializer,
    TipoDocumentoPacienteSerializer,
)
from .permissions import LaboratorioRolPermission
from .utils import (
    buscar_valor_parametro,
    es_anormal,
    generar_pdf_orden,
    obtener_parametro_para_paciente,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helper de notificaciones internas
# ─────────────────────────────────────────────────────────────────────────────

def _crear_notificacion(destinatario, tipo, mensaje, orden=None):
    """Crea una notificación interna si el usuario las tiene habilitadas."""
    try:
        if destinatario and getattr(destinatario, 'recibir_notificaciones', True):
            Notificacion.objects.create(
                destinatario=destinatario,
                tipo=tipo,
                mensaje=mensaje,
                orden=orden,
            )
    except Exception as exc:
        logger.warning("No se pudo crear notificación: %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
# ViewSet base con respuestas estandarizadas
# ─────────────────────────────────────────────────────────────────────────────

class EstandarRespuestaViewSet(viewsets.ModelViewSet):
    """
    Clase base que estandariza las respuestas de la API.
    Estructura de respuesta: { "estado": ..., "mensaje": ..., "datos/errores": ... }
    """
    permission_classes = [LaboratorioRolPermission]

    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                self.perform_create(serializer)
                return Response(
                    {'estado': 'exito', 'mensaje': 'Registro creado correctamente.', 'datos': serializer.data},
                    status=status.HTTP_201_CREATED,
                )
            return Response(
                {'estado': 'error_validacion', 'mensaje': 'Los datos enviados no son válidos.', 'errores': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error("Error 500 al crear: %s", str(e))
            return Response(
                {'estado': 'error_servidor', 'mensaje': 'Error interno al intentar guardar el registro.', 'detalle': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return Response({'estado': 'exito', 'datos': serializer.data}, status=status.HTTP_200_OK)
        except Http404:
            return Response(
                {'estado': 'no_encontrado', 'mensaje': 'El registro solicitado no existe.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.error("Error 500 al recuperar: %s", str(e))
            return Response(
                {'estado': 'error_servidor', 'mensaje': 'Error interno al buscar el registro.'},
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
                    {'estado': 'exito', 'mensaje': 'Registro actualizado correctamente.', 'datos': serializer.data},
                    status=status.HTTP_200_OK,
                )
            return Response(
                {'estado': 'error_validacion', 'mensaje': 'Error en los datos para actualización.', 'errores': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Http404:
            return Response(
                {'estado': 'no_encontrado', 'mensaje': 'No se puede actualizar. El registro no existe.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.error("Error 500 al actualizar: %s", str(e))
            return Response(
                {'estado': 'error_servidor', 'mensaje': 'Error interno al actualizar el registro.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            self.perform_destroy(instance)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Http404:
            return Response(
                {'estado': 'no_encontrado', 'mensaje': 'No se puede eliminar. El registro no existe.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        except ProtectedError:
            return Response(
                {'estado': 'conflicto', 'mensaje': 'No se puede eliminar: tiene información clínica vinculada.'},
                status=status.HTTP_409_CONFLICT,
            )
        except Exception as e:
            logger.error("Error 500 al eliminar: %s", str(e))
            return Response(
                {'estado': 'error_servidor', 'mensaje': 'Error interno al intentar eliminar el registro.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ─────────────────────────────────────────────────────────────────────────────
# FASE 1 — Catálogos y configuración
# ─────────────────────────────────────────────────────────────────────────────

class CatalogoCupsViewSet(EstandarRespuestaViewSet):
    queryset = CatalogoCups.objects.all().order_by('codigo_cups')
    serializer_class = CatalogoCupsSerializer


class ParametroExamenViewSet(EstandarRespuestaViewSet):
    queryset = ParametroExamen.objects.select_related('cups', 'sexo_aplica').order_by('nombre_parametro')
    serializer_class = ParametroExamenSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        cups_id = self.request.query_params.get('cups')
        if cups_id:
            qs = qs.filter(cups__codigo_cups=cups_id)
        return qs


class ConfiguracionEquipoViewSet(EstandarRespuestaViewSet):
    """FASE 1 — Administración de equipos analizadores y su configuración de conexión."""
    queryset = ConfiguracionEquipo.objects.all().order_by('nombre')
    serializer_class = ConfiguracionEquipoSerializer

    @action(detail=True, methods=['post'], url_path='regenerar-token')
    def regenerar_token(self, request, pk=None):
        equipo = self.get_object()
        equipo.token_middleware = secrets.token_urlsafe(32)
        equipo.save(update_fields=['token_middleware'])
        return Response(
            {'estado': 'exito', 'mensaje': 'Token de middleware regenerado.', 'token_middleware': equipo.token_middleware},
            status=status.HTTP_200_OK,
        )


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


class EstadoMuestraViewSet(EstandarRespuestaViewSet):
    """FASE 3 — Catálogo de estados de muestra física."""
    queryset = EstadoMuestra.objects.all().order_by('nombre')
    serializer_class = EstadoMuestraSerializer


# ─────────────────────────────────────────────────────────────────────────────
# FASE 2 — Pacientes y órdenes
# ─────────────────────────────────────────────────────────────────────────────

class PacienteViewSet(EstandarRespuestaViewSet):
    serializer_class = PacienteSerializer

    def get_queryset(self):
        incluir_inactivos = str(self.request.query_params.get('incluir_inactivos', 'false')).lower() == 'true'
        qs = Paciente.objects.all().order_by('-fecha_creacion')
        return qs if incluir_inactivos else qs.filter(activo=True)

    def destroy(self, request, *args, **kwargs):
        try:
            paciente = self.get_object()
            paciente.activo = False
            paciente.save(update_fields=['activo'])
            return Response(
                {'estado': 'exito', 'mensaje': 'Paciente desactivado correctamente (eliminación lógica).'},
                status=status.HTTP_200_OK,
            )
        except Http404:
            return Response(
                {'estado': 'no_encontrado', 'mensaje': 'El paciente no existe.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.error("Error al desactivar paciente: %s", str(e))
            return Response(
                {'estado': 'error_servidor', 'mensaje': 'Error interno al desactivar el paciente.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class OrdenLaboratorioViewSet(EstandarRespuestaViewSet):
    queryset = OrdenLaboratorio.objects.select_related(
        'paciente', 'medico', 'estado_general', 'usuario_admite'
    ).order_by('-fecha_orden')
    serializer_class = OrdenLaboratorioSerializer

    @action(detail=True, methods=['get'], url_path='reporte-pdf')
    def reporte_pdf(self, request, pk=None):
        """
        FASE 6 — Genera el PDF inmutable del informe de resultados.
        Requiere que la orden esté en estado Finalizada (o Validada).
        """
        orden = self.get_object()
        estados_validos = {'Finalizada', 'Validada', 'Reportada', 'Entregada'}
        if orden.estado_general.nombre not in estados_validos:
            return Response(
                {
                    'estado': 'error_validacion',
                    'mensaje': (
                        f"La orden debe estar en uno de los estados: {', '.join(estados_validos)}. "
                        f"Estado actual: '{orden.estado_general.nombre}'."
                    ),
                },
                status=status.HTTP_409_CONFLICT,
            )
        try:
            pdf_bytes = generar_pdf_orden(orden)
            hash_doc = hashlib.sha256(pdf_bytes).hexdigest()

            informe, _ = InformeResultados.objects.update_or_create(
                orden=orden,
                defaults={
                    'generado_por': request.user if request.user.is_authenticated else None,
                    'hash_documento': hash_doc,
                },
            )
            nombre_archivo = f"informe_{orden.numero_orden}.pdf"
            informe.archivo_pdf.save(nombre_archivo, ContentFile(pdf_bytes), save=True)

            response = HttpResponse(pdf_bytes, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
            return response
        except Exception as e:
            logger.error("Error generando PDF para orden %s: %s", pk, str(e))
            return Response(
                {'estado': 'error_servidor', 'mensaje': 'Error al generar el PDF del informe.', 'detalle': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=['post'], url_path='admitir')
    def admitir(self, request, pk=None):
        """
        FASE 2 — Registra la admisión del paciente en recepción del laboratorio.
        """
        orden = self.get_object()
        orden.fecha_admision = timezone.now()
        orden.usuario_admite = request.user if request.user.is_authenticated else None
        orden.save(update_fields=['fecha_admision', 'usuario_admite'])
        return Response(
            {
                'estado': 'exito',
                'mensaje': 'Admisión registrada correctamente.',
                'fecha_admision': str(orden.fecha_admision),
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=['get'], url_path='export-rips')
    def export_rips(self, request):
        """
        FASE 6 — Exporta un archivo plano/csv con los CUPS finalizados para auditoría.
        Filtros opcionales: ?fecha_inicio=YYYY-MM-DD&fecha_fin=YYYY-MM-DD
        """
        fecha_inicio = request.query_params.get('fecha_inicio')
        fecha_fin = request.query_params.get('fecha_fin')

        qs = OrdenLaboratorio.objects.select_related('paciente__tipo_documento').prefetch_related('examenes_solicitados__cups')
        qs = qs.filter(estado_general__nombre='Finalizada')
        if fecha_inicio:
            qs = qs.filter(fecha_orden__date__gte=fecha_inicio)
        if fecha_fin:
            qs = qs.filter(fecha_orden__date__lte=fecha_fin)

        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="rips_laboratorio.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'numero_orden', 'fecha_orden', 'tipo_doc', 'numero_doc', 'cups',
            'descripcion_cups', 'codigo_cie10', 'entidad_remitente', 'convenio', 'estado_orden'
        ])

        for orden in qs:
            for examen in orden.examenes_solicitados.all():
                writer.writerow([
                    orden.numero_orden,
                    orden.fecha_orden.strftime('%Y-%m-%d %H:%M:%S') if orden.fecha_orden else '',
                    orden.paciente.tipo_documento.codigo if orden.paciente and orden.paciente.tipo_documento else '',
                    orden.paciente.numero_documento if orden.paciente else '',
                    examen.cups.codigo_cups if examen.cups else '',
                    examen.cups.descripcion if examen.cups else '',
                    orden.codigo_cie10 or '',
                    orden.entidad_remitente or '',
                    orden.convenio or '',
                    orden.estado_general.nombre if orden.estado_general else '',
                ])

        return response


# ─────────────────────────────────────────────────────────────────────────────
# FASE 3 — Muestras físicas
# ─────────────────────────────────────────────────────────────────────────────

class MuestraFisicaViewSet(EstandarRespuestaViewSet):
    queryset = MuestraFisica.objects.select_related(
        'orden', 'estado_muestra', 'usuario_recolecta'
    ).order_by('-fecha_recoleccion')
    serializer_class = MuestraFisicaSerializer

    @action(detail=False, methods=['get'], url_path='buscar')
    def buscar(self, request):
        """
        FASE 3 — Busca una muestra por código de barras (escaneo de tablet).
        GET /api/v1/muestras/buscar/?codigo_barras=MUE-XXXX
        """
        codigo = request.query_params.get('codigo_barras', '').strip()
        if not codigo:
            return Response(
                {'estado': 'error_validacion', 'mensaje': 'Se requiere el parámetro codigo_barras.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            muestra = MuestraFisica.objects.select_related(
                'orden__paciente', 'estado_muestra'
            ).get(codigo_barras=codigo)
            return Response(
                {'estado': 'exito', 'datos': MuestraFisicaSerializer(muestra).data},
                status=status.HTTP_200_OK,
            )
        except MuestraFisica.DoesNotExist:
            return Response(
                {'estado': 'no_encontrado', 'mensaje': f"No existe muestra con código '{codigo}'."},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(detail=True, methods=['post'], url_path='recibir-laboratorio')
    def recibir_laboratorio(self, request, pk=None):
        """
        FASE 3/4 — Registra la recepción de la muestra en el laboratorio central.
        Cambia el estado de la muestra a 'Recibida en Laboratorio' y los exámenes
        vinculados a 'En Análisis'.
        """
        muestra = self.get_object()
        try:
            estado_recibida = EstadoMuestra.objects.get(nombre='Recibida en Laboratorio')
            muestra.estado_muestra = estado_recibida
            muestra.save(update_fields=['estado_muestra'])

            estado_analisis = EstadoExamen.objects.get(nombre='En Análisis')
            examenes_actualizados = muestra.examenes.filter(
                estado_examen__nombre__in=['Pendiente', 'Muestra Recolectada']
            )
            examenes_actualizados.update(estado_examen=estado_analisis)

            return Response(
                {
                    'estado': 'exito',
                    'mensaje': 'Muestra recibida en laboratorio. Exámenes marcados como En Análisis.',
                    'examenes_actualizados': examenes_actualizados.count(),
                },
                status=status.HTTP_200_OK,
            )
        except EstadoMuestra.DoesNotExist:
            return Response(
                {'estado': 'error_config', 'mensaje': "Estado 'Recibida en Laboratorio' no está configurado."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as e:
            logger.error("Error al recibir muestra %s: %s", pk, str(e))
            return Response(
                {'estado': 'error_servidor', 'mensaje': 'Error al registrar la recepción de la muestra.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=['post'], url_path='rechazar')
    def rechazar(self, request, pk=None):
        """
        FASE 3/5 — Bacteriólogo rechaza una muestra (ej: hemolizada).
        Notifica al flebotomista para repetir la toma.
        """
        muestra = self.get_object()
        motivo = request.data.get('motivo_rechazo', '').strip()
        if not motivo:
            return Response(
                {'estado': 'error_validacion', 'mensaje': 'Se requiere indicar el motivo_rechazo.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        condicion = request.data.get('condicion_muestra', muestra.condicion_muestra)

        try:
            estado_rechazada = EstadoMuestra.objects.get(nombre='Rechazada')
            muestra.estado_muestra = estado_rechazada
            muestra.motivo_rechazo = motivo
            muestra.condicion_muestra = condicion
            muestra.save(update_fields=['estado_muestra', 'motivo_rechazo', 'condicion_muestra'])

            # Notificar al flebotomista que tomó la muestra
            if muestra.usuario_recolecta:
                _crear_notificacion(
                    destinatario=muestra.usuario_recolecta,
                    tipo='muestra_rechazada',
                    mensaje=(
                        f"La muestra {muestra.codigo_barras} de la orden "
                        f"{muestra.orden.numero_orden} fue rechazada. "
                        f"Motivo: {motivo}. Por favor repita la toma."
                    ),
                    orden=muestra.orden,
                )

            return Response(
                {
                    'estado': 'exito',
                    'mensaje': 'Muestra rechazada. Se emitió alerta al flebotomista.',
                    'muestra_id': str(muestra.id),
                },
                status=status.HTTP_200_OK,
            )
        except EstadoMuestra.DoesNotExist:
            return Response(
                {'estado': 'error_config', 'mensaje': "Estado 'Rechazada' no está configurado."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ─────────────────────────────────────────────────────────────────────────────
# FASE 4 & 5 — Exámenes y resultados
# ─────────────────────────────────────────────────────────────────────────────

class ExamenSolicitadoViewSet(EstandarRespuestaViewSet):
    queryset = ExamenSolicitado.objects.select_related(
        'orden__paciente', 'cups', 'estado_examen', 'validado_por'
    ).order_by('orden__numero_orden')
    serializer_class = ExamenSolicitadoSerializer

    @action(detail=True, methods=['post'], url_path='aprobar')
    def aprobar(self, request, pk=None):
        """
        FASE 5 — Bacteriólogo valida y firma el examen.
        Verifica que todos los parámetros tengan resultado.
        Si todos los exámenes de la orden quedan validados, la orden pasa a 'Finalizada'.
        """
        examen = self.get_object()

        total_parametros = ParametroExamen.objects.filter(cups=examen.cups).values('nombre_parametro').distinct().count()
        total_resultados = examen.resultados.count()

        if total_resultados == 0:
            return Response(
                {'estado': 'error_validacion', 'mensaje': 'No se puede aprobar un examen sin resultados.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if total_parametros > 0 and total_resultados < total_parametros:
            return Response(
                {
                    'estado': 'conflicto',
                    'mensaje': 'No es posible aprobar: faltan resultados por registrar o procesar.',
                    'faltantes': total_parametros - total_resultados,
                },
                status=status.HTTP_409_CONFLICT,
            )

        examen.estado_examen = EstadoExamen.objects.get(nombre='Validado')
        examen.validado_por = request.user if request.user.is_authenticated else None
        examen.fecha_validacion = timezone.now()
        examen.save(update_fields=['estado_examen', 'validado_por', 'fecha_validacion'])

        # Verificar si todos los exámenes de la orden están validados → Finalizar orden
        orden = examen.orden
        estados_no_finales = {'Pendiente', 'Muestra Recolectada', 'En Análisis', 'En Espera'}
        examenes_pendientes = orden.examenes_solicitados.filter(
            estado_examen__nombre__in=estados_no_finales
        ).count()
        if examenes_pendientes == 0:
            estado_finalizada, _ = EstadoOrden.objects.get_or_create(
                nombre='Finalizada',
                defaults={'descripcion': 'Todos los exámenes de la orden han sido validados.'}
            )
            orden.estado_general = estado_finalizada
            orden.save(update_fields=['estado_general'])
            # Notificar al médico solicitante
            if orden.medico:
                _crear_notificacion(
                    destinatario=orden.medico,
                    tipo='orden_finalizada',
                    mensaje=(
                        f"Los resultados de la orden {orden.numero_orden} del paciente "
                        f"{orden.paciente.primer_nombre} {orden.paciente.primer_apellido} "
                        f"ya están disponibles."
                    ),
                    orden=orden,
                )
            orden_finalizada = True
        else:
            orden_finalizada = False

        return Response(
            {
                'estado': 'exito',
                'mensaje': 'Examen validado correctamente.' + (' Orden marcada como Finalizada.' if orden_finalizada else ''),
                'examen_id': str(examen.id),
                'orden_finalizada': orden_finalizada,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=['post'], url_path='rechazar')
    def rechazar(self, request, pk=None):
        """
        FASE 5 — Bacteriólogo rechaza el resultado de un examen (ej: muestra hemolizada).
        Notifica al flebotomista para nueva toma si la muestra está vinculada.
        """
        examen = self.get_object()
        motivo = request.data.get('motivo_rechazo', '').strip()
        if not motivo:
            return Response(
                {'estado': 'error_validacion', 'mensaje': 'Se requiere indicar el motivo_rechazo.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        examen.motivo_rechazo = motivo
        examen.estado_examen = EstadoExamen.objects.get(nombre='Repetir')
        examen.save(update_fields=['motivo_rechazo', 'estado_examen'])

        # Notificar al flebotomista si se conoce quién tomó la muestra
        if examen.muestra and examen.muestra.usuario_recolecta:
            _crear_notificacion(
                destinatario=examen.muestra.usuario_recolecta,
                tipo='examen_rechazado',
                mensaje=(
                    f"El examen '{examen.cups.descripcion}' de la orden "
                    f"{examen.orden.numero_orden} fue rechazado. "
                    f"Motivo: {motivo}. Se requiere nueva toma de muestra."
                ),
                orden=examen.orden,
            )

        return Response(
            {
                'estado': 'exito',
                'mensaje': 'Examen rechazado. Se notificó al flebotomista.',
                'examen_id': str(examen.id),
            },
            status=status.HTTP_200_OK,
        )


class LecturaEquipoSerialViewSet(EstandarRespuestaViewSet):
    queryset = LecturaEquipoSerial.objects.all().order_by('-fecha_recepcion')
    serializer_class = LecturaEquipoSerialSerializer

    def _token_middleware_valido(self, request, equipo_origen):
        token = request.headers.get('X-Middleware-Token') or request.data.get('token_middleware')
        if not token:
            return False
        return ConfiguracionEquipo.objects.filter(
            activo=True,
            token_middleware=token,
        ).filter(
            Q(codigo_equipo=equipo_origen) | Q(nombre=equipo_origen)
        ).exists()

    def create(self, request, *args, **kwargs):
        """
        FASE 4 — Ingesta de tramas desde middleware.
        Permite autenticación por token estático en encabezado X-Middleware-Token.
        """
        equipo_origen = request.data.get('equipo_origen')
        if not equipo_origen:
            return Response(
                {'estado': 'error_validacion', 'mensaje': 'El campo equipo_origen es obligatorio.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        usuario_autenticado = bool(request.user and request.user.is_authenticated)
        if not usuario_autenticado and not self._token_middleware_valido(request, equipo_origen):
            return Response(
                {
                    'estado': 'no_autorizado',
                    'mensaje': 'Token de middleware inválido o faltante para el equipo de origen.',
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        return super().create(request, *args, **kwargs)

    @action(detail=True, methods=['post'], url_path='procesar')
    def procesar(self, request, pk=None):
        """
        FASE 4 — Extrae los analitos de la trama cruda y los guarda en ResultadoAnalito.
        Usa rangos específicos por sexo/edad del paciente para calcular es_anormal/es_critico.
        Genera alertas de valor crítico si corresponde.
        """
        lectura = self.get_object()

        if not lectura.codigo_barras_leido:
            return Response(
                {'estado': 'error_validacion', 'mensaje': 'La lectura no tiene código de barras asociado.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        examenes = ExamenSolicitado.objects.select_related(
            'cups', 'orden__paciente__sexo_biologico'
        ).filter(muestra__codigo_barras=lectura.codigo_barras_leido)

        if not examenes.exists():
            return Response(
                {
                    'estado': 'no_encontrado',
                    'mensaje': 'No se encontraron exámenes para el código de barras recibido.',
                    'codigo_barras': lectura.codigo_barras_leido,
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        creados = actualizados = omitidos = criticos = 0

        for examen in examenes:
            paciente = examen.orden.paciente
            # Obtener nombres únicos de parámetros para evitar procesar duplicados
            nombres = list(
                ParametroExamen.objects.filter(cups=examen.cups)
                .values_list('nombre_parametro', flat=True)
                .distinct()
            )

            for nombre in nombres:
                parametro = obtener_parametro_para_paciente(examen.cups_id, nombre, paciente)
                if not parametro:
                    omitidos += 1
                    continue

                valor = buscar_valor_parametro(lectura.datos_json, nombre)
                if valor is None:
                    omitidos += 1
                    continue

                anormal, critico = es_anormal(parametro, valor)

                resultado, created = ResultadoAnalito.objects.update_or_create(
                    examen_solicitado=examen,
                    parametro=parametro,
                    defaults={
                        'lectura_serial': lectura,
                        'valor_resultado': str(valor),
                        'es_anormal': anormal,
                        'es_critico': critico,
                    },
                )

                if created:
                    creados += 1
                else:
                    actualizados += 1

                # Alerta de valor crítico — notificar al médico de la orden
                if critico:
                    criticos += 1
                    if examen.orden.medico:
                        _crear_notificacion(
                            destinatario=examen.orden.medico,
                            tipo='alerta_critica',
                            mensaje=(
                                f"ALERTA CRÍTICA — {nombre}: {valor} {parametro.unidades_medida or ''} "
                                f"(Orden {examen.orden.numero_orden}, paciente "
                                f"{paciente.primer_nombre} {paciente.primer_apellido})."
                            ),
                            orden=examen.orden,
                        )

            # Avanzar estado del examen
            if examen.estado_examen.nombre in ('Pendiente', 'Muestra Recolectada'):
                examen.estado_examen = EstadoExamen.objects.get(nombre='En Análisis')
                examen.save(update_fields=['estado_examen'])

        lectura.procesado = True
        lectura.save(update_fields=['procesado'])

        return Response(
            {
                'estado': 'exito',
                'mensaje': 'Lectura serial procesada correctamente.',
                'lectura_id': str(lectura.id),
                'resultados_creados': creados,
                'resultados_actualizados': actualizados,
                'resultados_omitidos': omitidos,
                'alertas_criticas': criticos,
            },
            status=status.HTTP_200_OK,
        )


class ResultadoAnalitoViewSet(EstandarRespuestaViewSet):
    queryset = ResultadoAnalito.objects.select_related(
        'parametro', 'examen_solicitado'
    ).order_by('-fecha_procesamiento')
    serializer_class = ResultadoAnalitoSerializer


# ─────────────────────────────────────────────────────────────────────────────
# FASE 6 — Informes y notificaciones
# ─────────────────────────────────────────────────────────────────────────────

class InformeResultadosViewSet(viewsets.ReadOnlyModelViewSet):
    """
    FASE 6 — Solo lectura; la creación/actualización se realiza
    desde OrdenLaboratorioViewSet.reporte_pdf.
    """
    queryset = InformeResultados.objects.select_related('orden', 'generado_por').order_by('-fecha_generacion')
    serializer_class = InformeResultadosSerializer
    permission_classes = [LaboratorioRolPermission]


class NotificacionViewSet(viewsets.ModelViewSet):
    """
    FASE 6 — Gestión de notificaciones internas del LIMS.
    Los usuarios solo ven sus propias notificaciones.
    """
    serializer_class = NotificacionSerializer
    permission_classes = [LaboratorioRolPermission]

    def get_queryset(self):
        if self.request.user.is_authenticated:
            qs = Notificacion.objects.filter(destinatario=self.request.user).order_by('-fecha_creacion')
        else:
            qs = Notificacion.objects.none()
        solo_no_leidas = str(self.request.query_params.get('no_leidas', 'false')).lower() == 'true'
        if solo_no_leidas:
            qs = qs.filter(leida=False)
        return qs

    @action(detail=True, methods=['post'], url_path='marcar-leida')
    def marcar_leida(self, request, pk=None):
        notif = self.get_object()
        if not notif.leida:
            notif.leida = True
            notif.fecha_lectura = timezone.now()
            notif.save(update_fields=['leida', 'fecha_lectura'])
        return Response({'estado': 'exito', 'mensaje': 'Notificación marcada como leída.'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='marcar-todas-leidas')
    def marcar_todas_leidas(self, request):
        ahora = timezone.now()
        actualizadas = self.get_queryset().filter(leida=False).update(leida=True, fecha_lectura=ahora)
        return Response(
            {'estado': 'exito', 'mensaje': f'{actualizadas} notificaciones marcadas como leídas.'},
            status=status.HTTP_200_OK,
        )
