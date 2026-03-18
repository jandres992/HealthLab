import logging

from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import (
    TipoId, Sexo, Municipio, Departamento, Usuario,
    TipoUsuario, Permiso, UsuarioXPermiso, DispositivoConfianza
)
from .serializers import (
    TipoIdSerializer, SexoSerializer, MunicipioSerializer, DepartamentoSerializer,
    UsuarioSerializer, TipoUsuarioSerializer, PermisoSerializer,
    UsuarioXPermisoSerializer, DispositivoConfianzaSerializer, TokenPersonalizadoSerializer
)

logger = logging.getLogger(__name__)

class TipoIdViewSet(viewsets.ModelViewSet):
    queryset = TipoId.objects.all()
    serializer_class = TipoIdSerializer

class SexoViewSet(viewsets.ModelViewSet):
    queryset = Sexo.objects.all()
    serializer_class = SexoSerializer

class DepartamentoViewSet(viewsets.ModelViewSet):
    queryset = Departamento.objects.all()
    serializer_class = DepartamentoSerializer

class MunicipioViewSet(viewsets.ModelViewSet):
    queryset = Municipio.objects.all()
    serializer_class = MunicipioSerializer

class UsuarioViewSet(viewsets.ModelViewSet):
    queryset = Usuario.objects.all()
    serializer_class = UsuarioSerializer

class TipoUsuarioViewSet(viewsets.ModelViewSet):
    queryset = TipoUsuario.objects.all()
    serializer_class = TipoUsuarioSerializer

class PermisoViewSet(viewsets.ModelViewSet):
    queryset = Permiso.objects.all()
    serializer_class = PermisoSerializer

class UsuarioXPermisoViewSet(viewsets.ModelViewSet):
    queryset = UsuarioXPermiso.objects.all()
    serializer_class = UsuarioXPermisoSerializer

class DispositivoConfianzaViewSet(viewsets.ModelViewSet):
    queryset = DispositivoConfianza.objects.all()
    serializer_class = DispositivoConfianzaSerializer

class LoginPersonalizadoView(TokenObtainPairView):
    """
    Toma el usuario y contraseña, devuelve JWT y registra el dispositivo de confianza.
    """
    serializer_class = TokenPersonalizadoSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        try:
            serializer.is_valid(raise_exception=True)
        except Exception as exc:
            logger.warning("Intento de login fallido para usuario %s", request.data.get('username'))
            return Response({'detalle': str(exc)}, status=status.HTTP_401_UNAUTHORIZED)

        user = serializer.user
        payload = serializer.validated_data

        device_id = request.data.get('device_id')
        nombre = request.data.get('nombre_dispositivo') or 'Dispositivo no identificado'
        user_agent = request.data.get('user_agent') or request.META.get('HTTP_USER_AGENT', '')
        es_confiable = str(request.data.get('es_confiable', 'true')).lower() in ['1', 'true', 'si', 'yes']

        if device_id:
            DispositivoConfianza.objects.update_or_create(
                usuario=user,
                device_id=device_id,
                defaults={
                    'nombre': nombre,
                    'user_agent': user_agent,
                    'es_confiable': es_confiable,
                },
            )

        return Response(payload, status=status.HTTP_200_OK)