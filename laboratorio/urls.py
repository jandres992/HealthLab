from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    # FASE 1 — Catálogos y configuración
    CatalogoCupsViewSet,
    ConfiguracionEquipoViewSet,
    ParametroExamenViewSet,
    TipoDocumentoPacienteViewSet,
    SexoBiologicoViewSet,
    EstadoOrdenViewSet,
    EstadoExamenViewSet,
    EstadoMuestraViewSet,
    # FASE 2 — Pacientes y órdenes
    PacienteViewSet,
    OrdenLaboratorioViewSet,
    # FASE 3 — Muestras físicas
    MuestraFisicaViewSet,
    # FASES 4 & 5 — Exámenes, lecturas seriales y resultados
    ExamenSolicitadoViewSet,
    LecturaEquipoSerialViewSet,
    ResultadoAnalitoViewSet,
    # FASE 6 — Informes y notificaciones
    InformeResultadosViewSet,
    NotificacionViewSet,
)

router = DefaultRouter()

# ── FASE 1 ────────────────────────────────────────────────────────────────────
router.register(r'catalogo-cups', CatalogoCupsViewSet, basename='catalogo-cups')
router.register(r'parametros', ParametroExamenViewSet, basename='parametros')
router.register(r'equipos', ConfiguracionEquipoViewSet, basename='equipos')
router.register(r'tipos-documento', TipoDocumentoPacienteViewSet, basename='tipos-documento')
router.register(r'sexos-biologicos', SexoBiologicoViewSet, basename='sexos-biologicos')
router.register(r'estados-orden', EstadoOrdenViewSet, basename='estados-orden')
router.register(r'estados-examen', EstadoExamenViewSet, basename='estados-examen')
router.register(r'estados-muestra', EstadoMuestraViewSet, basename='estados-muestra')
# ── FASE 2 ────────────────────────────────────────────────────────────────────
router.register(r'pacientes', PacienteViewSet, basename='pacientes')
router.register(r'ordenes', OrdenLaboratorioViewSet, basename='ordenes')
# ── FASE 3 ────────────────────────────────────────────────────────────────────
router.register(r'muestras', MuestraFisicaViewSet, basename='muestras')
# ── FASES 4 & 5 ───────────────────────────────────────────────────────────────
router.register(r'examenes-solicitados', ExamenSolicitadoViewSet, basename='examenes-solicitados')
router.register(r'lecturas-serial', LecturaEquipoSerialViewSet, basename='lecturas-serial')
router.register(r'resultados', ResultadoAnalitoViewSet, basename='resultados')
# ── FASE 6 ────────────────────────────────────────────────────────────────────
router.register(r'informes', InformeResultadosViewSet, basename='informes')
router.register(r'notificaciones', NotificacionViewSet, basename='notificaciones')

urlpatterns = [
    path('api/v1/', include(router.urls)),
]