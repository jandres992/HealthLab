from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    TipoIdViewSet, SexoViewSet, MunicipioViewSet, DepartamentoViewSet,
    UsuarioViewSet, TipoUsuarioViewSet, PermisoViewSet,
    UsuarioXPermisoViewSet, DispositivoConfianzaViewSet, LoginPersonalizadoView
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

urlpatterns = [
    path('', include(router.urls)),
    path('login/', LoginPersonalizadoView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]