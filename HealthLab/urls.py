"""
URL configuration for HealthLab project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.conf import settings
from django.urls import path, include
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('laboratorio.urls')),      # /api/v1/* (RF-09)
    path('lab/', include('laboratorio.urls')),  # alias histórico; se retira con la app Expo
    path('usr/', include('usuarios.urls')),
]

# Documentación OpenAPI: el esquema siempre (lo usa el generador del cliente);
# las interfaces Swagger/Redoc solo en desarrollo o si se habilitan por entorno (RNF-27).
urlpatterns += [path('api/schema/', SpectacularAPIView.as_view(), name='schema')]
if settings.EXPONER_DOCUMENTACION_API:
    urlpatterns += [
        path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
        path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    ]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)