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
    # 2. Rutas para generar el archivo base de Swagger (Esquema JSON/YAML)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),

    # 3. Interfaz gráfica de Swagger UI (La clásica y más usada)
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),

    # 4. (Opcional) Interfaz gráfica de Redoc (Otra vista muy elegante para documentar APIs)
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    path('', include('laboratorio.urls')),  # Expone tambien /api/v1/* segun RF-09.
    path('lab/', include('laboratorio.urls')),
    path('usr/', include('usuarios.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)