"""
Vistas del módulo usuarios.

Permisos según la matriz §8.1 (usuarios/acciones.py). Toda vista exige
autenticación salvo login, refresh y logout (RN-20).
"""
import logging

from django.db import transaction
from rest_framework import exceptions, mixins, status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import auditoria
from .models import (
    Auditoria, Departamento, DispositivoConfianza, Municipio, Permiso, Sexo,
    TipoId, TipoUsuario, Usuario, UsuarioXPermiso,
)
from .permissions import PermisoPorAccion
from .roles import es_administrador
from .serializers import (
    AuditoriaSerializer, CambioContrasenaSerializer, DepartamentoSerializer, DispositivoConfianzaSerializer, LogoutSerializer,
    MunicipioSerializer, PerfilPropioSerializer, PermisoSerializer, SexoSerializer,
    TipoIdSerializer, TipoUsuarioSerializer, TokenPersonalizadoSerializer,
    UsuarioSerializer, UsuarioXPermisoSerializer,
)
from .tokens import revocar_tokens_de

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Catálogos: lectura para cualquier autenticado, escritura solo Administrador
# ─────────────────────────────────────────────────────────────────────────────

class CatalogoViewSet(viewsets.ModelViewSet):
    permission_classes = [PermisoPorAccion]
    accion_lectura = 'catalogos.ver'
    accion_escritura = 'catalogos.gestionar'


class TipoIdViewSet(CatalogoViewSet):
    queryset = TipoId.objects.all().order_by('tipo_id')
    serializer_class = TipoIdSerializer


class SexoViewSet(CatalogoViewSet):
    queryset = Sexo.objects.all().order_by('sexo')
    serializer_class = SexoSerializer


class DepartamentoViewSet(CatalogoViewSet):
    queryset = Departamento.objects.all().order_by('departamento')
    serializer_class = DepartamentoSerializer
    search_fields = ['departamento', 'codigo']


class MunicipioViewSet(CatalogoViewSet):
    queryset = Municipio.objects.select_related('departamento').order_by('municipio')
    serializer_class = MunicipioSerializer
    filterset_fields = ['departamento']
    search_fields = ['municipio', 'codigo']


# ─────────────────────────────────────────────────────────────────────────────
# Cuentas y roles — RF-05, RF-05.1
# ─────────────────────────────────────────────────────────────────────────────

class UsuarioViewSet(viewsets.ModelViewSet):
    queryset = Usuario.objects.all().order_by('username')
    serializer_class = UsuarioSerializer
    permission_classes = [PermisoPorAccion]
    accion_lectura = 'usuarios.ver'
    accion_escritura = 'usuarios.gestionar'
    filterset_fields = ['is_active']
    search_fields = ['username', 'email', 'p_nombre', 'p_apellido', 'numero_id', 'registro_profesional']

    def perform_create(self, serializer):
        usuario = serializer.save()
        auditoria.registrar(self.request, 'usuario.crear', 'Usuario', usuario.pk,
                            {'username': usuario.username})

    def perform_update(self, serializer):
        cambio_password = bool(serializer.validated_data.get('password'))
        usuario = serializer.save()
        detalle = {'campos': sorted(k for k in serializer.validated_data if k != 'password')}
        if cambio_password:
            detalle['password'] = 'restablecida'
            revocar_tokens_de(usuario)
        if 'is_active' in serializer.validated_data and not usuario.is_active:
            revocar_tokens_de(usuario)
        auditoria.registrar(self.request, 'usuario.editar', 'Usuario', usuario.pk, detalle)

    def destroy(self, request, *args, **kwargs):
        """RF-05: las cuentas no se borran; se desactivan y se revocan sus tokens."""
        usuario = self.get_object()
        if usuario == request.user:
            raise exceptions.PermissionDenied('No puedes desactivar tu propia cuenta.')
        with transaction.atomic():
            usuario.is_active = False
            usuario.save(update_fields=['is_active'])
            revocar_tokens_de(usuario)
            auditoria.registrar(request, 'usuario.desactivar', 'Usuario', usuario.pk,
                                {'username': usuario.username})
        return Response(
            {'estado': 'exito', 'mensaje': 'Cuenta desactivada. Sus sesiones fueron revocadas.'},
            status=status.HTTP_200_OK,
        )


class TipoUsuarioViewSet(viewsets.ModelViewSet):
    queryset = TipoUsuario.objects.all().order_by('tipo')
    serializer_class = TipoUsuarioSerializer
    permission_classes = [PermisoPorAccion]
    accion_lectura = 'roles.ver'
    accion_escritura = 'roles.gestionar'


class PermisoViewSet(viewsets.ModelViewSet):
    queryset = Permiso.objects.select_related('tipo_usuario').order_by('permiso')
    serializer_class = PermisoSerializer
    permission_classes = [PermisoPorAccion]
    accion_lectura = 'roles.ver'
    accion_escritura = 'roles.gestionar'


class UsuarioXPermisoViewSet(viewsets.ModelViewSet):
    queryset = UsuarioXPermiso.objects.select_related('usuario', 'permiso__tipo_usuario').order_by('usuario__username')
    serializer_class = UsuarioXPermisoSerializer
    permission_classes = [PermisoPorAccion]
    accion_lectura = 'roles.ver'
    accion_escritura = 'roles.gestionar'
    filterset_fields = ['usuario', 'permiso']
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def perform_create(self, serializer):
        asignacion = serializer.save()
        auditoria.registrar(self.request, 'rol.asignar', 'Usuario', asignacion.usuario_id,
                            {'permiso': asignacion.permiso.permiso, 'rol': asignacion.permiso.tipo_usuario.tipo})

    def perform_destroy(self, instance):
        if instance.usuario == self.request.user:
            raise exceptions.PermissionDenied('No puedes modificar tus propios roles.')
        detalle = {'permiso': instance.permiso.permiso, 'rol': instance.permiso.tipo_usuario.tipo}
        usuario_id = instance.usuario_id
        instance.delete()
        revocar_tokens_de(instance.usuario)  # los tokens vigentes llevan los roles anteriores
        auditoria.registrar(self.request, 'rol.quitar', 'Usuario', usuario_id, detalle)


class AuditoriaViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Bitácora de solo lectura (RNF-25): Auditor y Administrador."""
    queryset = Auditoria.objects.select_related('usuario').order_by('-fecha')
    serializer_class = AuditoriaSerializer
    permission_classes = [PermisoPorAccion]
    accion_lectura = 'auditoria.ver'
    filterset_fields = {'accion': ['exact', 'startswith'], 'entidad': ['exact'], 'entidad_id': ['exact'],
                        'usuario': ['exact'], 'exito': ['exact'], 'fecha': ['gte', 'lte']}
    search_fields = ['username', 'accion', 'entidad_id', 'ip']


# ─────────────────────────────────────────────────────────────────────────────
# Dispositivos de confianza — RF-05.3
# ─────────────────────────────────────────────────────────────────────────────

class DispositivoConfianzaViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                                  mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """Cada usuario ve y revoca los suyos; el Administrador, los de todos."""
    queryset = DispositivoConfianza.objects.none()  # para el esquema; el real está en get_queryset
    serializer_class = DispositivoConfianzaSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = DispositivoConfianza.objects.select_related('usuario').order_by('-ultimo_acceso')
        if es_administrador(self.request.user):
            return qs
        return qs.filter(usuario=self.request.user)

    def perform_destroy(self, instance):
        auditoria.registrar(self.request, 'dispositivo.revocar', 'DispositivoConfianza', instance.pk,
                            {'usuario': instance.usuario.username, 'device_id': instance.device_id})
        instance.delete()


# ─────────────────────────────────────────────────────────────────────────────
# Perfil propio — RF-05.2, BE-01
# ─────────────────────────────────────────────────────────────────────────────

class PerfilPropioView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PerfilPropioSerializer

    def get(self, request):
        return Response(PerfilPropioSerializer(request.user, context={'request': request}).data)

    def patch(self, request):
        serializer = PerfilPropioSerializer(request.user, data=request.data, partial=True,
                                            context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        auditoria.registrar(request, 'perfil.editar', 'Usuario', request.user.pk,
                            {'campos': sorted(serializer.validated_data)})
        return Response(serializer.data)


class CambioContrasenaView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CambioContrasenaSerializer

    def post(self, request):
        serializer = CambioContrasenaSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            request.user.set_password(serializer.validated_data['password_nueva'])
            request.user.save(update_fields=['password'])
            revocar_tokens_de(request.user)
            auditoria.registrar(request, 'perfil.cambiar_password', 'Usuario', request.user.pk)
        return Response({'estado': 'exito', 'mensaje': 'Contraseña actualizada. Vuelve a iniciar sesión.'})


# ─────────────────────────────────────────────────────────────────────────────
# Autenticación — RF-01, RF-02, RF-03, RNF-26
# ─────────────────────────────────────────────────────────────────────────────

class LoginPersonalizadoView(TokenObtainPairView):
    """Devuelve JWT, roles y acciones; registra el dispositivo; audita éxito y fallo."""
    serializer_class = TokenPersonalizadoSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = 'login'

    def post(self, request, *args, **kwargs):
        username = str(request.data.get('username', ''))[:150]
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except exceptions.PermissionDenied as exc:
            auditoria.registrar(request, 'login.sin_rol', 'Usuario', None, {'username': username}, exito=False)
            return Response({'estado': 'no_autorizado', 'mensaje': str(exc.detail), 'detail': str(exc.detail)},
                            status=status.HTTP_403_FORBIDDEN)
        except (exceptions.AuthenticationFailed, exceptions.ValidationError, TokenError):
            # RNF-26: mensaje genérico, sin revelar si el usuario existe.
            logger.warning('Intento de login fallido para usuario %s', username)
            auditoria.registrar(request, 'login.fallo', 'Usuario', None, {'username': username}, exito=False)
            mensaje = 'Usuario o contraseña incorrectos.'
            return Response({'estado': 'no_autenticado', 'mensaje': mensaje, 'detail': mensaje},
                            status=status.HTTP_401_UNAUTHORIZED)

        usuario = serializer.user
        payload = serializer.validated_data

        device_id = request.data.get('device_id')
        if device_id:
            DispositivoConfianza.objects.update_or_create(
                usuario=usuario,
                device_id=str(device_id)[:255],
                defaults={
                    'nombre': (request.data.get('nombre_dispositivo') or 'Dispositivo no identificado')[:100],
                    'user_agent': request.data.get('user_agent') or request.META.get('HTTP_USER_AGENT', ''),
                    'es_confiable': str(request.data.get('es_confiable', 'true')).lower() in ('1', 'true', 'si', 'yes'),
                },
            )

        auditoria.registrar(request, 'login.exito', 'Usuario', usuario.pk, usuario=usuario)
        return Response(payload, status=status.HTTP_200_OK)


class RefrescarTokenView(TokenRefreshView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = 'refresh'


class LogoutView(APIView):
    """Invalida el refresh token enviado (RF-08)."""
    permission_classes = [IsAuthenticated]
    serializer_class = LogoutSerializer

    def post(self, request):
        refresh = request.data.get('refresh')
        if refresh:
            try:
                RefreshToken(refresh).blacklist()
            except TokenError:
                pass  # ya vencido o inválido: el resultado es el mismo
        auditoria.registrar(request, 'logout', 'Usuario', request.user.pk)
        return Response({'estado': 'exito', 'mensaje': 'Sesión cerrada.'})
