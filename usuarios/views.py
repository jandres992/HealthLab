from rest_framework import viewsets
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
    Toma el usuario y contraseña y devuelve un token de acceso y uno de refresco.
    """
    serializer_class = TokenPersonalizadoSerializer