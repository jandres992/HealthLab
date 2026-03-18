from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CatalogoCupsViewSet, ParametroExamenViewSet, PacienteViewSet,
    OrdenLaboratorioViewSet, MuestraFisicaViewSet, ExamenSolicitadoViewSet,
    LecturaEquipoSerialViewSet, ResultadoAnalitoViewSet,
    TipoDocumentoPacienteViewSet, SexoBiologicoViewSet,
    EstadoOrdenViewSet, EstadoExamenViewSet,
)

# Instanciamos el router
router = DefaultRouter()

# Registramos cada endpoint de la API
router.register(r'catalogo-cups', CatalogoCupsViewSet, basename='catalogo-cups')
router.register(r'parametros', ParametroExamenViewSet, basename='parametros')
router.register(r'tipos-documento', TipoDocumentoPacienteViewSet, basename='tipos-documento')
router.register(r'sexos-biologicos', SexoBiologicoViewSet, basename='sexos-biologicos')
router.register(r'estados-orden', EstadoOrdenViewSet, basename='estados-orden')
router.register(r'estados-examen', EstadoExamenViewSet, basename='estados-examen')
router.register(r'pacientes', PacienteViewSet, basename='pacientes')
router.register(r'ordenes', OrdenLaboratorioViewSet, basename='ordenes')
router.register(r'muestras', MuestraFisicaViewSet, basename='muestras')
router.register(r'examenes-solicitados', ExamenSolicitadoViewSet, basename='examenes-solicitados')
router.register(r'lecturas-serial', LecturaEquipoSerialViewSet, basename='lecturas-serial')
router.register(r'resultados', ResultadoAnalitoViewSet, basename='resultados')

# Exponemos las rutas generadas
urlpatterns = [
    path('api/v1/', include(router.urls)),
]