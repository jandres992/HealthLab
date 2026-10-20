from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AuditoriaViewSet, CambioContrasenaView, DepartamentoViewSet, DispositivoConfianzaViewSet,
    LoginPersonalizadoView, LogoutView, MunicipioViewSet, PerfilPropioView,
    PermisoViewSet, RefrescarTokenView, SexoViewSet, TipoIdViewSet,
    TipoUsuarioViewSet, UsuarioViewSet, UsuarioXPermisoViewSet,
)

router = DefaultRouter()
router.register(r'tipos-id', TipoIdViewSet, basename='tipos-id')
router.register(r'sexos', SexoViewSet, basename='sexos')
router.register(r'departamentos', DepartamentoViewSet, basename='departamentos')
router.register(r'municipios', MunicipioViewSet, basename='municipios')
router.register(r'usuarios', UsuarioViewSet, basename='usuarios')
router.register(r'tipos-usuario', TipoUsuarioViewSet, basename='tipos-usuario')
router.register(r'permisos', PermisoViewSet, basename='permisos')
router.register(r'usuarios-permisos', UsuarioXPermisoViewSet, basename='usuarios-permisos')
router.register(r'dispositivos-confianza', DispositivoConfianzaViewSet, basename='dispositivos-confianza')
router.register(r'auditoria', AuditoriaViewSet, basename='auditoria')

urlpatterns = [
    path('login/', LoginPersonalizadoView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', RefrescarTokenView.as_view(), name='token_refresh'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('me/', PerfilPropioView.as_view(), name='perfil-propio'),
    path('me/password/', CambioContrasenaView.as_view(), name='perfil-password'),
    path('', include(router.urls)),
]
