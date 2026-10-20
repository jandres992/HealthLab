"""
Vistas del módulo laboratorio — ViewSets delgados (RNF-38.1).

Cada vista: permiso por acción (matriz §8.1) + serializador + llamada a un
servicio. Ninguna regla clínica vive aquí. Las respuestas de creación,
detalle y actualización conservan la envoltura {estado, mensaje, datos} que
espera la app Expo durante la transición.
"""
import csv
import secrets

from django.db import transaction
from django.db.models import ProtectedError
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from usuarios import auditoria
from usuarios.permissions import PermisoPorAccion

from .domain import estados as E
from .domain.errores import ErrorDeDominio, ErrorDeValidacion
from .models import (
    CatalogoCups, ConfiguracionEquipo, EstadoExamen, EstadoMuestra, EstadoOrden,
    ExamenSolicitado, InformeResultados, LecturaEquipoSerial, MuestraFisica,
    Notificacion, OrdenLaboratorio, Paciente, ParametroExamen, ResultadoAnalito,
    SexoBiologico, TipoDocumentoPaciente,
)
from .permissions import PermisoIngestaLecturas
from .serializers import (
    CatalogoCupsSerializer, ConfiguracionEquipoSerializer, EstadoExamenSerializer,
    EstadoMuestraSerializer, EstadoOrdenSerializer, ExamenAgregarSerializer,
    ExamenSolicitadoSerializer, InformeResultadosSerializer, LecturaEquipoSerialSerializer,
    MotivoSerializer, MuestraCrearSerializer, MuestraFisicaSerializer, NotificacionSerializer,
    OrdenCrearSerializer, OrdenEditarSerializer, OrdenLaboratorioSerializer, PacienteSerializer,
    ParametroExamenSerializer, RechazoSerializer, ResultadoAnalitoSerializer,
    ResultadoRegistrarSerializer, SexoBiologicoSerializer, TipoDocumentoPacienteSerializer,
)
from .services import examenes as svc_examenes
from .services import informes as svc_informes
from .services import muestras as svc_muestras
from .services import ordenes as svc_ordenes
from .services import pacientes as svc_pacientes
from .services import resultados as svc_resultados


def exito(mensaje=None, datos=None, codigo=status.HTTP_200_OK, **extra):
    cuerpo = {'estado': 'exito'}
    if mensaje:
        cuerpo['mensaje'] = mensaje
    if datos is not None:
        cuerpo['datos'] = datos
    cuerpo.update(extra)
    return Response(cuerpo, status=codigo)


class EstandarRespuestaViewSet(viewsets.ModelViewSet):
    """Envoltura estándar en create/retrieve/update; los errores los maneja el handler global."""
    permission_classes = [PermisoPorAccion]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return exito('Registro creado correctamente.', serializer.data, status.HTTP_201_CREATED)

    def retrieve(self, request, *args, **kwargs):
        return exito(datos=self.get_serializer(self.get_object()).data)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return exito('Registro actualizado correctamente.', serializer.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            self.perform_destroy(instance)
        except ProtectedError:
            raise ErrorDeDominio('No se puede eliminar: tiene información clínica vinculada.')
        return Response(status=status.HTTP_204_NO_CONTENT)


class CatalogoViewSet(EstandarRespuestaViewSet):
    """Catálogos: lectura para todos los roles, escritura solo Administrador; borrado = desactivar."""
    accion_lectura = 'catalogos.ver'
    accion_escritura = 'catalogos.gestionar'

    def perform_destroy(self, instance):
        if hasattr(instance, 'activo'):
            instance.activo = False
            instance.save(update_fields=['activo'])
        else:
            instance.delete()


# ─────────────────────────────────────────────────────────────────────────────
# FASE 1 — Catálogos y configuración
# ─────────────────────────────────────────────────────────────────────────────

class CatalogoCupsViewSet(CatalogoViewSet):
    serializer_class = CatalogoCupsSerializer
    search_fields = ['codigo_cups', 'descripcion']
    filterset_fields = ['activo']

    def get_queryset(self):
        qs = CatalogoCups.objects.all().order_by('codigo_cups')
        if str(self.request.query_params.get('incluir_inactivos', 'false')).lower() != 'true':
            qs = qs.filter(activo=True)
        return qs


class TipoDocumentoPacienteViewSet(CatalogoViewSet):
    queryset = TipoDocumentoPaciente.objects.all().order_by('codigo')
    serializer_class = TipoDocumentoPacienteSerializer


class SexoBiologicoViewSet(CatalogoViewSet):
    queryset = SexoBiologico.objects.all().order_by('codigo')
    serializer_class = SexoBiologicoSerializer


class EstadoOrdenViewSet(CatalogoViewSet):
    queryset = EstadoOrden.objects.all().order_by('nombre')
    serializer_class = EstadoOrdenSerializer


class EstadoExamenViewSet(CatalogoViewSet):
    queryset = EstadoExamen.objects.all().order_by('nombre')
    serializer_class = EstadoExamenSerializer


class EstadoMuestraViewSet(CatalogoViewSet):
    queryset = EstadoMuestra.objects.all().order_by('nombre')
    serializer_class = EstadoMuestraSerializer


class ParametroExamenViewSet(EstandarRespuestaViewSet):
    """Rangos de referencia: los define el Bacteriólogo (RF-13.2); con historial (RF-53)."""
    queryset = ParametroExamen.objects.select_related('cups', 'sexo_aplica').order_by('nombre_parametro')
    serializer_class = ParametroExamenSerializer
    accion_lectura = 'parametros.ver'
    accion_escritura = 'parametros.gestionar'
    search_fields = ['nombre_parametro', 'cups__codigo_cups', 'cups__descripcion']
    filterset_fields = ['activo', 'sexo_aplica']

    def get_queryset(self):
        qs = super().get_queryset()
        cups_query = self.request.query_params.get('cups')
        if cups_query:
            qs = qs.filter(cups_id=cups_query) if cups_query.isdigit() else qs.filter(cups__codigo_cups=cups_query)
        return qs

    def perform_destroy(self, instance):
        instance.activo = False
        instance.save(update_fields=['activo'])


class ConfiguracionEquipoViewSet(EstandarRespuestaViewSet):
    queryset = ConfiguracionEquipo.objects.all().order_by('nombre')
    serializer_class = ConfiguracionEquipoSerializer
    accion_lectura = 'equipos.ver'
    accion_escritura = 'equipos.gestionar'
    acciones = {'regenerar_token': 'equipos.regenerar_token'}

    @action(detail=True, methods=['post'], url_path='regenerar-token')
    def regenerar_token(self, request, pk=None):
        equipo = self.get_object()
        equipo.token_middleware = secrets.token_urlsafe(32)
        equipo.save(update_fields=['token_middleware'])
        auditoria.registrar(request, 'equipo.regenerar_token', 'ConfiguracionEquipo', equipo.pk)
        return exito('Token de middleware regenerado. Guárdelo: no se volverá a mostrar.',
                     token_middleware=equipo.token_middleware)


# ─────────────────────────────────────────────────────────────────────────────
# FASE 2 — Pacientes y órdenes
# ─────────────────────────────────────────────────────────────────────────────

class PacienteViewSet(EstandarRespuestaViewSet):
    serializer_class = PacienteSerializer
    acciones = {
        'list': 'pacientes.ver', 'retrieve': 'pacientes.ver',
        'create': 'pacientes.crear', 'update': 'pacientes.editar', 'partial_update': 'pacientes.editar',
        'destroy': 'pacientes.desactivar',
    }
    search_fields = ['numero_documento', 'primer_nombre', 'segundo_nombre', 'primer_apellido', 'segundo_apellido']
    filterset_fields = ['tipo_documento', 'sexo_biologico', 'regimen_salud']

    def get_queryset(self):
        qs = Paciente.objects.select_related('tipo_documento', 'sexo_biologico').order_by('-fecha_creacion')
        if str(self.request.query_params.get('incluir_inactivos', 'false')).lower() != 'true':
            qs = qs.filter(activo=True)
        return qs

    def perform_create(self, serializer):
        paciente = serializer.save()
        auditoria.registrar(self.request, 'paciente.crear', 'Paciente', paciente.pk)

    def perform_update(self, serializer):
        paciente = serializer.save()
        auditoria.registrar(self.request, 'paciente.editar', 'Paciente', paciente.pk,
                            {'campos': sorted(serializer.validated_data)})

    def retrieve(self, request, *args, **kwargs):
        paciente = self.get_object()
        auditoria.registrar(request, 'paciente.consultar', 'Paciente', paciente.pk)
        return exito(datos=self.get_serializer(paciente).data)

    def destroy(self, request, *args, **kwargs):
        svc_pacientes.desactivar_paciente(request.user, kwargs['pk'], request=request)
        return exito('Paciente desactivado correctamente (eliminación lógica).')


class OrdenLaboratorioViewSet(EstandarRespuestaViewSet):
    queryset = OrdenLaboratorio.objects.select_related(
        'paciente', 'medico', 'estado_general', 'usuario_admite'
    ).prefetch_related('examenes_solicitados__cups', 'examenes_solicitados__estado_examen',
                       'examenes_solicitados__muestra', 'examenes_solicitados__validado_por').order_by('-fecha_orden')
    serializer_class = OrdenLaboratorioSerializer
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    acciones = {
        'list': 'ordenes.ver', 'retrieve': 'ordenes.ver', 'create': 'ordenes.crear',
        'partial_update': 'ordenes.editar', 'admitir': 'ordenes.admitir', 'finalizar': 'ordenes.finalizar',
        'reporte_pdf': 'ordenes.reporte_pdf', 'export_rips': 'ordenes.export_rips',
    }
    search_fields = ['numero_orden', 'paciente__numero_documento', 'paciente__primer_nombre', 'paciente__primer_apellido']
    filterset_fields = {'estado_general__nombre': ['exact'], 'paciente': ['exact'], 'medico': ['exact'],
                        'fecha_orden': ['gte', 'lte']}

    def create(self, request, *args, **kwargs):
        serializer = OrdenCrearSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        datos = dict(serializer.validated_data)
        paciente = datos.pop('paciente')
        examenes = datos.pop('examenes')
        orden = svc_ordenes.crear_orden(request.user, paciente, examenes, datos, request=request)
        orden = self.get_queryset().get(pk=orden.pk)
        return exito('Orden creada correctamente.', OrdenLaboratorioSerializer(orden).data, status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        orden = self.get_object()
        if orden.estado_general.nombre != E.ORDEN_REGISTRADA:
            raise ErrorDeDominio('Solo se puede editar una orden en estado Registrada.')
        if orden.medico_id and orden.medico_id != request.user.pk:
            raise PermissionDenied('Solo el médico que creó la orden puede editarla.')
        serializer = OrdenEditarSerializer(orden, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            serializer.save()
            auditoria.registrar(request, 'orden.editar', 'OrdenLaboratorio', orden.pk,
                                {'campos': sorted(serializer.validated_data)})
        return exito('Orden actualizada.', OrdenLaboratorioSerializer(self.get_queryset().get(pk=orden.pk)).data)

    @action(detail=True, methods=['post'])
    def admitir(self, request, pk=None):
        orden = svc_ordenes.admitir_orden(request.user, pk, request=request)
        return exito('Admisión registrada correctamente.', fecha_admision=orden.fecha_admision.isoformat())

    @action(detail=True, methods=['post'])
    def finalizar(self, request, pk=None):
        svc_ordenes.finalizar_orden(request.user, pk, request=request)
        return exito('Orden finalizada correctamente y reporte generado.')

    @action(detail=True, methods=['get'], url_path='reporte-pdf')
    def reporte_pdf(self, request, pk=None):
        """Final (archivo guardado), parcial (se guarda con hash) o preliminar (no se guarda)."""
        orden = self.get_object()
        estado = orden.estado_general.nombre
        if estado == E.ORDEN_FINALIZADA:
            informe = InformeResultados.objects.filter(orden=orden, tipo='final', vigente=True).first()
            if informe and informe.archivo_pdf:
                with informe.archivo_pdf.open('rb') as f:
                    pdf_bytes = f.read()
                nombre = f'informe_{orden.numero_orden}.pdf'
            else:
                with transaction.atomic():
                    informe, pdf_bytes = svc_informes.generar_informe(orden, 'final', request.user)
                nombre = f'informe_{orden.numero_orden}.pdf'
        elif estado == E.ORDEN_RESULTADOS_PARCIALES:
            with transaction.atomic():
                informe, pdf_bytes = svc_informes.generar_informe(orden, 'parcial', request.user)
            nombre = f'PARCIAL_informe_{orden.numero_orden}.pdf'
        else:
            pdf_bytes = svc_informes.generar_pdf(orden, 'preliminar')
            nombre = f'PRELIMINAR_informe_{orden.numero_orden}.pdf'
        auditoria.registrar(request, 'informe.descargar', 'OrdenLaboratorio', orden.pk, {'archivo': nombre})
        respuesta = HttpResponse(pdf_bytes, content_type='application/pdf')
        respuesta['Content-Disposition'] = f'attachment; filename="{nombre}"'
        return respuesta

    @action(detail=False, methods=['get'], url_path='export-rips')
    def export_rips(self, request):
        """CSV de órdenes finalizadas para auditoría (RF-42)."""
        fecha_inicio = request.query_params.get('fecha_inicio')
        fecha_fin = request.query_params.get('fecha_fin')
        qs = OrdenLaboratorio.objects.select_related('paciente__tipo_documento', 'estado_general') \
            .prefetch_related('examenes_solicitados__cups').filter(estado_general__nombre=E.ORDEN_FINALIZADA)
        if fecha_inicio:
            qs = qs.filter(fecha_orden__date__gte=fecha_inicio)
        if fecha_fin:
            qs = qs.filter(fecha_orden__date__lte=fecha_fin)

        respuesta = HttpResponse(content_type='text/csv; charset=utf-8')
        respuesta['Content-Disposition'] = 'attachment; filename="rips_laboratorio.csv"'
        writer = csv.writer(respuesta)
        writer.writerow(['numero_orden', 'fecha_orden', 'tipo_doc', 'numero_doc', 'cups', 'descripcion_cups',
                         'codigo_cie10', 'entidad_remitente', 'convenio', 'finalidad_consulta', 'causa_externa',
                         'tipo_diagnostico', 'estado_orden'])
        for orden in qs:
            for examen in orden.examenes_solicitados.all():
                writer.writerow([
                    orden.numero_orden, timezone.localtime(orden.fecha_orden).strftime('%Y-%m-%d %H:%M:%S'),
                    orden.paciente.tipo_documento.codigo, orden.paciente.numero_documento,
                    examen.cups.codigo_cups, examen.cups.descripcion, orden.codigo_cie10 or '',
                    orden.entidad_remitente or '', orden.convenio or '', orden.finalidad_consulta,
                    orden.causa_externa, orden.tipo_diagnostico, orden.estado_general.nombre,
                ])
        auditoria.registrar(request, 'rips.exportar', 'OrdenLaboratorio', None,
                            {'fecha_inicio': fecha_inicio, 'fecha_fin': fecha_fin, 'ordenes': qs.count()})
        return respuesta


# ─────────────────────────────────────────────────────────────────────────────
# FASE 3 — Muestras
# ─────────────────────────────────────────────────────────────────────────────

class MuestraFisicaViewSet(EstandarRespuestaViewSet):
    queryset = MuestraFisica.objects.select_related('orden__paciente', 'estado_muestra', 'usuario_recolecta') \
        .prefetch_related('examenes').order_by('-fecha_recoleccion')
    serializer_class = MuestraFisicaSerializer
    http_method_names = ['get', 'post', 'head', 'options']
    acciones = {
        'list': 'muestras.ver', 'retrieve': 'muestras.ver', 'create': 'muestras.registrar',
        'buscar': 'muestras.buscar', 'recibir_laboratorio': 'muestras.recibir', 'rechazar': 'muestras.rechazar',
    }
    search_fields = ['codigo_barras', 'orden__numero_orden']
    filterset_fields = ['orden', 'estado_muestra__nombre', 'condicion_muestra']

    def create(self, request, *args, **kwargs):
        serializer = MuestraCrearSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        datos = dict(serializer.validated_data)
        orden = datos.pop('orden')
        examenes = datos.pop('examenes', None)
        muestra = svc_muestras.registrar_muestra(request.user, orden, datos, examenes_ids=examenes, request=request)
        muestra = self.get_queryset().get(pk=muestra.pk)
        return exito('Muestra registrada.', MuestraFisicaSerializer(muestra).data, status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def buscar(self, request):
        codigo = request.query_params.get('codigo_barras', '').strip()
        if not codigo:
            raise ErrorDeValidacion('Se requiere el parámetro codigo_barras.')
        muestra = self.get_queryset().filter(codigo_barras=codigo).first()
        if muestra is None:
            return Response({'estado': 'no_encontrado', 'mensaje': f"No existe muestra con código '{codigo}'."},
                            status=status.HTTP_404_NOT_FOUND)
        return exito(datos=MuestraFisicaSerializer(muestra).data)

    @action(detail=True, methods=['post'], url_path='recibir-laboratorio')
    def recibir_laboratorio(self, request, pk=None):
        _, actualizados = svc_muestras.recibir_muestra(request.user, pk, request=request)
        return exito('Muestra recibida en laboratorio. Exámenes marcados como En Análisis.',
                     examenes_actualizados=actualizados)

    @action(detail=True, methods=['post'])
    def rechazar(self, request, pk=None):
        serializer = RechazoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        muestra = svc_muestras.rechazar_muestra(
            request.user, pk, serializer.validated_data['motivo_rechazo'],
            serializer.validated_data.get('condicion_muestra'), request=request,
        )
        return exito('Muestra rechazada. Se notificó al flebotomista y al médico.', muestra_id=str(muestra.pk))


# ─────────────────────────────────────────────────────────────────────────────
# FASES 4 y 5 — Exámenes, lecturas y resultados
# ─────────────────────────────────────────────────────────────────────────────

class ExamenSolicitadoViewSet(EstandarRespuestaViewSet):
    queryset = ExamenSolicitado.objects.select_related(
        'orden__paciente', 'cups', 'estado_examen', 'validado_por', 'muestra'
    ).order_by('orden__numero_orden')
    serializer_class = ExamenSolicitadoSerializer
    http_method_names = ['get', 'post', 'head', 'options']
    acciones = {
        'list': 'examenes.ver', 'retrieve': 'examenes.ver', 'create': 'examenes.crear',
        'aprobar': 'examenes.aprobar', 'rechazar': 'examenes.rechazar', 'anular': 'examenes.anular',
    }
    search_fields = ['orden__numero_orden', 'cups__codigo_cups', 'cups__descripcion', 'orden__paciente__numero_documento']
    filterset_fields = ['orden', 'estado_examen__nombre', 'cups', 'muestra']

    def create(self, request, *args, **kwargs):
        """Agrega un examen a una orden abierta (RF-20.4). La creación normal va con la orden."""
        serializer = ExamenAgregarSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        orden = serializer.validated_data['orden']
        cups = serializer.validated_data['cups']
        with transaction.atomic():
            orden = OrdenLaboratorio.objects.select_for_update().select_related('estado_general').get(pk=orden.pk)
            if orden.estado_general.nombre in E.ORDEN_ESTADOS_FINALES:
                raise ErrorDeDominio('La orden está cerrada; no admite exámenes nuevos.')
            if orden.examenes_solicitados.filter(cups=cups).exclude(estado_examen__nombre=E.EXAMEN_ANULADO).exists():
                raise ErrorDeDominio('La orden ya tiene ese examen.')
            examen = ExamenSolicitado.objects.create(orden=orden, cups=cups, estado_examen=E.estado_examen(E.EXAMEN_PENDIENTE))
            auditoria.registrar(request, 'examen.agregar', 'ExamenSolicitado', examen.pk,
                                {'orden': orden.numero_orden, 'cups': cups.codigo_cups})
        return exito('Examen agregado a la orden.', ExamenSolicitadoSerializer(self.get_queryset().get(pk=examen.pk)).data,
                     status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def aprobar(self, request, pk=None):
        examen, orden_finalizada = svc_examenes.aprobar_examen(request.user, pk, request=request)
        return exito('Examen validado correctamente.' + (' Orden marcada como Finalizada.' if orden_finalizada else ''),
                     examen_id=str(examen.pk), orden_finalizada=orden_finalizada)

    @action(detail=True, methods=['post'])
    def rechazar(self, request, pk=None):
        serializer = RechazoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        examen = svc_examenes.rechazar_examen(request.user, pk, serializer.validated_data['motivo_rechazo'], request=request)
        return exito('Examen rechazado. Se notificó al flebotomista y al médico.', examen_id=str(examen.pk))

    @action(detail=True, methods=['post'])
    def anular(self, request, pk=None):
        serializer = MotivoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        examen = svc_examenes.anular_examen(request.user, pk, serializer.validated_data['motivo'], request=request)
        return exito('Examen anulado.', examen_id=str(examen.pk))


class LecturaEquipoSerialViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                                 viewsets.GenericViewSet):
    queryset = LecturaEquipoSerial.objects.all().order_by('-fecha_recepcion')
    serializer_class = LecturaEquipoSerialSerializer
    permission_classes = [PermisoIngestaLecturas]
    acciones = {'create': 'lecturas.registrar', 'list': 'lecturas.ver', 'retrieve': 'lecturas.ver',
                'procesar': 'lecturas.procesar'}
    filterset_fields = ['procesado', 'equipo_origen', 'codigo_barras_leido']

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lectura = serializer.save()
        auditoria.registrar(request, 'lectura.recibir', 'LecturaEquipoSerial', lectura.pk,
                            {'equipo_origen': lectura.equipo_origen, 'codigo_barras': lectura.codigo_barras_leido})
        return exito('Lectura registrada.', serializer.data, status.HTTP_201_CREATED)

    def retrieve(self, request, *args, **kwargs):
        return exito(datos=self.get_serializer(self.get_object()).data)

    @action(detail=True, methods=['post'])
    def procesar(self, request, pk=None):
        resumen = svc_resultados.procesar_lectura(request.user, pk, request=request)
        return exito('Lectura serial procesada correctamente.', **resumen)


class ResultadoAnalitoViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                              viewsets.GenericViewSet):
    """Registro manual (RF-32) y consulta. Un resultado validado no se modifica (RN-22)."""
    queryset = ResultadoAnalito.objects.select_related(
        'parametro', 'examen_solicitado__estado_examen', 'examen_solicitado__orden'
    ).order_by('-fecha_procesamiento')
    serializer_class = ResultadoAnalitoSerializer
    permission_classes = [PermisoPorAccion]
    acciones = {'list': 'resultados.ver', 'retrieve': 'resultados.ver', 'create': 'resultados.registrar'}
    filterset_fields = ['examen_solicitado', 'parametro', 'es_anormal', 'es_critico', 'examen_solicitado__orden']

    def create(self, request, *args, **kwargs):
        serializer = ResultadoRegistrarSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        resultado, creado = svc_resultados.registrar_resultado_manual(
            request.user, d['examen_solicitado'].pk, d['parametro'].pk, d['valor_resultado'],
            d.get('comentario_bacteriologo'), request=request,
        )
        resultado = self.get_queryset().get(pk=resultado.pk)
        return exito('Resultado guardado.', ResultadoAnalitoSerializer(resultado).data,
                     status.HTTP_201_CREATED if creado else status.HTTP_200_OK)

    def retrieve(self, request, *args, **kwargs):
        return exito(datos=self.get_serializer(self.get_object()).data)


# ─────────────────────────────────────────────────────────────────────────────
# FASE 6 — Informes y notificaciones
# ─────────────────────────────────────────────────────────────────────────────

class InformeResultadosViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = InformeResultados.objects.select_related('orden', 'generado_por').order_by('-fecha_generacion')
    serializer_class = InformeResultadosSerializer
    permission_classes = [PermisoPorAccion]
    accion_lectura = 'informes.ver'
    filterset_fields = ['orden', 'tipo', 'vigente']


class NotificacionViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Cada usuario ve solo sus notificaciones (RF-41.1)."""
    serializer_class = NotificacionSerializer
    permission_classes = [PermisoPorAccion]
    accion_lectura = 'notificaciones.propias'
    accion_escritura = 'notificaciones.propias'
    filterset_fields = ['tipo', 'leida', 'orden']

    def get_queryset(self):
        qs = Notificacion.objects.filter(destinatario=self.request.user).select_related('orden').order_by('-fecha_creacion')
        if str(self.request.query_params.get('no_leidas', 'false')).lower() == 'true':
            qs = qs.filter(leida=False)
        return qs

    @action(detail=True, methods=['post'], url_path='marcar-leida')
    def marcar_leida(self, request, pk=None):
        notif = self.get_object()
        if not notif.leida:
            notif.leida = True
            notif.fecha_lectura = timezone.now()
            notif.save(update_fields=['leida', 'fecha_lectura'])
        return exito('Notificación marcada como leída.')

    @action(detail=False, methods=['post'], url_path='marcar-todas-leidas')
    def marcar_todas_leidas(self, request):
        actualizadas = self.get_queryset().filter(leida=False).update(leida=True, fecha_lectura=timezone.now())
        return exito(f'{actualizadas} notificaciones marcadas como leídas.')
