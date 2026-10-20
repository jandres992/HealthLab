"""
Vistas de la Fase 2: custodia, control de calidad, críticos, equipos y lotes.
ViewSets delgados (RNF-38.1) con permisos por acción (§8.1).
"""
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from usuarios import auditoria
from usuarios.permissions import PermisoPorAccion

from .domain import calidad as dominio_calidad
from .domain.errores import ErrorDeValidacion, NoEncontrado
from .models import (
    AcuseValorCritico, CalibracionEquipo, ConfiguracionEquipo, CorridaCCI, EventoMuestra, LoteControl,
    LoteReactivo, MantenimientoEquipo, PoliticaCCI, ResultadoAnalito,
)
from .serializers import MuestraFisicaSerializer, ResultadoAnalitoSerializer
from .serializers_calidad import (
    AccionCorrectivaSerializer, AcuseRegistrarSerializer, AcuseValorCriticoSerializer, AlicuotaSerializer,
    CalibracionEquipoSerializer, CambioEstadoEquipoSerializer, CorridaCCISerializer, CorridaRegistrarSerializer,
    EstadoCCISerializer, EventoAnotarSerializer, EventoMuestraSerializer, LoteControlSerializer,
    LoteReactivoSerializer, MantenimientoEquipoSerializer, PoliticaCCISerializer, PoliticaDefinirSerializer,
)
from .services import calidad as svc_calidad
from .services import criticos as svc_criticos
from .services import custodia as svc_custodia
from .services import equipos as svc_equipos


def exito(mensaje=None, datos=None, codigo=status.HTTP_200_OK, **extra):
    cuerpo = {'estado': 'exito'}
    if mensaje:
        cuerpo['mensaje'] = mensaje
    if datos is not None:
        cuerpo['datos'] = datos
    cuerpo.update(extra)
    return Response(cuerpo, status=codigo)


# ── Custodia ──────────────────────────────────────────────────────────────────

class EventoMuestraViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Cadena de custodia: solo lectura; los eventos se crean con las acciones de muestras."""
    queryset = EventoMuestra.objects.select_related('muestra', 'usuario', 'muestra_relacionada').order_by('fecha')
    serializer_class = EventoMuestraSerializer
    permission_classes = [PermisoPorAccion]
    accion_lectura = 'custodia.ver'
    filterset_fields = ['muestra', 'tipo']


class CustodiaMuestraMixin:
    """Acciones de custodia que se añaden al MuestraFisicaViewSet."""

    @extend_schema(responses={200: EventoMuestraSerializer(many=True)})
    @action(detail=True, methods=['get'])
    def custodia(self, request, pk=None):
        muestra = self.get_object()
        eventos = muestra.eventos.select_related('usuario', 'muestra_relacionada').order_by('fecha')
        return Response(EventoMuestraSerializer(eventos, many=True).data)

    @extend_schema(request=EventoAnotarSerializer, responses={201: EventoMuestraSerializer})
    @action(detail=True, methods=['post'])
    def evento(self, request, pk=None):
        s = EventoAnotarSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        evento = svc_custodia.anotar(request.user, pk, d['tipo'], d.get('ubicacion', ''), d.get('observacion', ''),
                                     d.get('temperatura'), request=request)
        return exito('Evento registrado.', EventoMuestraSerializer(evento).data, status.HTTP_201_CREATED)

    @extend_schema(request=AlicuotaSerializer, responses={201: MuestraFisicaSerializer})
    @action(detail=True, methods=['post'])
    def alicuota(self, request, pk=None):
        s = AlicuotaSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        hija = svc_custodia.crear_alicuota(request.user, pk, d.get('tipo_muestra'), d.get('codigo_barras') or None,
                                           d.get('ubicacion', ''), request=request)
        return exito('Alícuota creada.', MuestraFisicaSerializer(hija).data, status.HTTP_201_CREATED)

    @extend_schema(request=AccionCorrectivaSerializer, responses={200: OpenApiTypes.OBJECT})
    @action(detail=True, methods=['post'])
    def descartar(self, request, pk=None):
        motivo = request.data.get('motivo') or request.data.get('accion_correctiva') or ''
        muestra = svc_custodia.descartar(request.user, pk, motivo, request=request)
        return exito('Muestra descartada.', muestra_id=str(muestra.pk))


# ── Equipos: calibraciones, mantenimientos, estado ────────────────────────────

class EquipoGestionMixin:
    """Acciones que se añaden al ConfiguracionEquipoViewSet."""

    @extend_schema(request=CalibracionEquipoSerializer, responses={201: CalibracionEquipoSerializer})
    @action(detail=True, methods=['post'])
    def calibracion(self, request, pk=None):
        s = CalibracionEquipoSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        cal = svc_equipos.registrar_calibracion(request.user, pk, s.validated_data, request=request)
        return exito('Calibración registrada.', CalibracionEquipoSerializer(cal).data, status.HTTP_201_CREATED)

    @extend_schema(responses={200: CalibracionEquipoSerializer(many=True)})
    @action(detail=True, methods=['get'])
    def calibraciones(self, request, pk=None):
        return Response(CalibracionEquipoSerializer(CalibracionEquipo.objects.filter(equipo_id=pk), many=True).data)

    @extend_schema(request=MantenimientoEquipoSerializer, responses={201: MantenimientoEquipoSerializer})
    @action(detail=True, methods=['post'])
    def mantenimiento(self, request, pk=None):
        s = MantenimientoEquipoSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        datos = dict(s.validated_data)
        nuevo_estado = datos.pop('nuevo_estado', None)
        mant = svc_equipos.registrar_mantenimiento(request.user, pk, datos, nuevo_estado, request=request)
        return exito('Mantenimiento registrado.', MantenimientoEquipoSerializer(mant).data, status.HTTP_201_CREATED)

    @extend_schema(responses={200: MantenimientoEquipoSerializer(many=True)})
    @action(detail=True, methods=['get'])
    def mantenimientos(self, request, pk=None):
        return Response(MantenimientoEquipoSerializer(MantenimientoEquipo.objects.filter(equipo_id=pk), many=True).data)

    @extend_schema(request=CambioEstadoEquipoSerializer, responses={200: OpenApiTypes.OBJECT})
    @action(detail=True, methods=['post'], url_path='cambiar-estado')
    def cambiar_estado(self, request, pk=None):
        s = CambioEstadoEquipoSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        equipo = svc_equipos.cambiar_estado(request.user, pk, s.validated_data['estado'], s.validated_data.get('motivo', ''), request=request)
        return exito('Estado actualizado.', estado=equipo.estado)

    @extend_schema(request=None, responses={200: OpenApiTypes.OBJECT})
    @action(detail=True, methods=['post'])
    def latido(self, request, pk=None):
        """Latido del Bridge (RF-68). Se autentica igual que la ingesta de lecturas."""
        equipo = self.get_object()
        svc_equipos.registrar_latido(equipo, request.data)
        return exito('Latido registrado.', ultimo_latido=equipo.ultimo_latido.isoformat())


class LoteReactivoViewSet(viewsets.ModelViewSet):
    queryset = LoteReactivo.objects.select_related('equipo').order_by('-creado')
    serializer_class = LoteReactivoSerializer
    permission_classes = [PermisoPorAccion]
    accion_lectura = 'lotes.ver'
    accion_escritura = 'lotes.gestionar'
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    filterset_fields = ['equipo', 'nombre_parametro', 'activo']

    def perform_create(self, serializer):
        serializer.instance = svc_equipos.registrar_lote_reactivo(self.request.user, serializer.validated_data, request=self.request)

    def perform_update(self, serializer):
        lote = serializer.save()
        auditoria.registrar(self.request, 'lote.editar', 'LoteReactivo', lote.pk, {'campos': sorted(serializer.validated_data)})


# ── Control de calidad ────────────────────────────────────────────────────────

class LoteControlViewSet(viewsets.ModelViewSet):
    queryset = LoteControl.objects.select_related('equipo').order_by('equipo', 'nombre_parametro', 'nivel')
    serializer_class = LoteControlSerializer
    permission_classes = [PermisoPorAccion]
    accion_lectura = 'calidad.ver'
    accion_escritura = 'calidad.gestionar'
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    filterset_fields = ['equipo', 'nombre_parametro', 'nivel', 'activo']

    def perform_create(self, serializer):
        lote = serializer.save(registrado_por=self.request.user)
        auditoria.registrar(self.request, 'cci.lote_control', 'LoteControl', lote.pk, {'lote': lote.lote})


class CorridaCCIViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = CorridaCCI.objects.select_related('lote_control__equipo', 'registrada_por').order_by('-fecha')
    serializer_class = CorridaCCISerializer
    permission_classes = [PermisoPorAccion]
    acciones = {'list': 'calidad.ver', 'retrieve': 'calidad.ver', 'create': 'calidad.gestionar',
                'accion_correctiva': 'calidad.gestionar', 'estado': 'calidad.ver', 'politica': 'calidad.gestionar',
                'politicas': 'calidad.ver'}
    filterset_fields = {'lote_control': ['exact'], 'lote_control__equipo': ['exact'],
                        'lote_control__nombre_parametro': ['exact'], 'resultado': ['exact'], 'fecha': ['gte', 'lte']}

    @extend_schema(request=CorridaRegistrarSerializer, responses={201: CorridaCCISerializer})
    def create(self, request, *args, **kwargs):
        s = CorridaRegistrarSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        corrida = svc_calidad.registrar_corrida(request.user, s.validated_data['lote_control'].pk, s.validated_data['valor'], request=request)
        return exito(f'Corrida {corrida.resultado}.', CorridaCCISerializer(corrida).data, status.HTTP_201_CREATED)

    @extend_schema(request=AccionCorrectivaSerializer, responses={200: CorridaCCISerializer})
    @action(detail=True, methods=['post'], url_path='accion-correctiva')
    def accion_correctiva(self, request, pk=None):
        s = AccionCorrectivaSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        corrida = svc_calidad.registrar_accion_correctiva(request.user, pk, s.validated_data['accion_correctiva'], request=request)
        return exito('Acción correctiva registrada.', CorridaCCISerializer(corrida).data)

    @extend_schema(parameters=[OpenApiParameter('equipo', OpenApiTypes.INT, required=True),
                               OpenApiParameter('nombre_parametro', OpenApiTypes.STR, required=True)],
                   responses={200: EstadoCCISerializer})
    @action(detail=False, methods=['get'])
    def estado(self, request):
        """Estado del CCI del día, modo vigente y propuesta de endurecimiento (RF-50.1.1)."""
        equipo_id = request.query_params.get('equipo')
        nombre = request.query_params.get('nombre_parametro')
        if not equipo_id or not nombre:
            raise ErrorDeValidacion('Se requieren equipo y nombre_parametro.')
        equipo = ConfiguracionEquipo.objects.filter(pk=equipo_id).first()
        if equipo is None:
            raise NoEncontrado('El equipo no existe.')
        return Response({
            'equipo': equipo.pk, 'nombre_parametro': nombre,
            'estado': dominio_calidad.estado_cci_del_dia(equipo, nombre, timezone.localdate()),
            'modo': svc_calidad.modo_politica(equipo, nombre),
            'propuesta': svc_calidad.propuesta_endurecimiento(equipo, nombre),
        })

    @extend_schema(request=PoliticaDefinirSerializer, responses={200: PoliticaCCISerializer})
    @action(detail=False, methods=['post'])
    def politica(self, request):
        s = PoliticaDefinirSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        politica = svc_calidad.definir_politica(request.user, d['equipo'].pk, d['nombre_parametro'], d['modo'], request=request)
        return exito('Política actualizada.', PoliticaCCISerializer(politica).data)

    @extend_schema(responses={200: PoliticaCCISerializer(many=True)})
    @action(detail=False, methods=['get'])
    def politicas(self, request):
        qs = PoliticaCCI.objects.select_related('equipo').order_by('equipo', 'nombre_parametro')
        return Response(PoliticaCCISerializer(qs, many=True).data)


# ── Críticos ──────────────────────────────────────────────────────────────────

class CriticoViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Valores críticos pendientes de acuse y registro del acuse (RF-54)."""
    serializer_class = ResultadoAnalitoSerializer
    permission_classes = [PermisoPorAccion]
    acciones = {'list': 'criticos.ver', 'acusar': 'criticos.acusar', 'acuse': 'criticos.ver'}
    filterset_fields = ['examen_solicitado__orden']

    def get_queryset(self):
        qs = ResultadoAnalito.objects.filter(es_critico=True).select_related(
            'parametro', 'examen_solicitado__estado_examen', 'examen_solicitado__orden'
        ).exclude(examen_solicitado__estado_examen__nombre='Anulado').order_by('-fecha_procesamiento')
        if str(self.request.query_params.get('pendientes', 'true')).lower() == 'true':
            qs = qs.filter(acuse__isnull=True)
        return qs

    @extend_schema(request=AcuseRegistrarSerializer, responses={201: AcuseValorCriticoSerializer})
    @action(detail=True, methods=['post'])
    def acusar(self, request, pk=None):
        s = AcuseRegistrarSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        acuse = svc_criticos.registrar_acuse(request.user, pk, d['comunicado_a'], d['medio'], d['read_back'],
                                             d.get('fecha_declarada'), d.get('observacion', ''), request=request)
        return exito('Acuse registrado.', AcuseValorCriticoSerializer(acuse).data, status.HTTP_201_CREATED)

    @extend_schema(responses={200: AcuseValorCriticoSerializer})
    @action(detail=True, methods=['get'])
    def acuse(self, request, pk=None):
        acuse = AcuseValorCritico.objects.filter(resultado_id=pk).select_related('registrado_por').first()
        if acuse is None:
            raise NoEncontrado('El resultado no tiene acuse.')
        return Response(AcuseValorCriticoSerializer(acuse).data)
