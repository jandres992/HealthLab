"""
Django settings for HealthLab project.

Toda la configuración sensible o dependiente del entorno se lee de variables
de entorno (archivo .env en desarrollo; ver .env.example). Nunca se escriben
secretos en este archivo (RNF-27).
"""
import os
import sys
from datetime import timedelta
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / '.env')


def env_bool(nombre, defecto=False):
    valor = os.environ.get(nombre)
    if valor is None or valor.strip() == '':
        return defecto
    return valor.strip().lower() in ('1', 'true', 'si', 'sí', 'yes', 'on')


def env_lista(nombre, defecto=()):
    valor = os.environ.get(nombre)
    if valor is None or valor.strip() == '':
        return list(defecto)
    return [item.strip() for item in valor.split(',') if item.strip()]


# ─────────────────────────────────────────────────────────────────────────────
# Seguridad básica
# ─────────────────────────────────────────────────────────────────────────────

DEBUG = env_bool('DJANGO_DEBUG', True)

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '').strip()
if not SECRET_KEY:
    if DEBUG:
        # Solo para desarrollo local. En producción es obligatoria (RNF-27).
        SECRET_KEY = 'django-insecure-solo-desarrollo-no-usar-en-produccion'
    else:
        raise ImproperlyConfigured('DJANGO_SECRET_KEY es obligatoria cuando DJANGO_DEBUG=false.')

ALLOWED_HOSTS = env_lista('DJANGO_ALLOWED_HOSTS', ('localhost', '127.0.0.1'))
if DEBUG:
    # Expo Go / Ionic en dispositivos de la misma red durante el desarrollo
    ALLOWED_HOSTS = ['*']

# CORS / CSRF: en desarrollo se permite cualquier origen; en producción solo los configurados.
CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = env_lista(
    'DJANGO_CORS_ALLOWED_ORIGINS',
    ('http://localhost:8100', 'capacitor://localhost', 'https://localhost'),
)
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    'accept', 'authorization', 'content-type', 'origin', 'user-agent',
    'x-csrftoken', 'x-requested-with',
    'x-middleware-token', 'idempotency-key', 'if-match',
]
CSRF_TRUSTED_ORIGINS = env_lista('DJANGO_CSRF_TRUSTED_ORIGINS', ())

if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool('DJANGO_SECURE_SSL_REDIRECT', True)
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'


# ─────────────────────────────────────────────────────────────────────────────
# Aplicaciones
# ─────────────────────────────────────────────────────────────────────────────

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'corsheaders',
    'rest_framework',
    'drf_spectacular',
    'rest_framework_simplejwt.token_blacklist',
    'django_filters',
    'simple_history',
    'laboratorio.apps.LaboratorioConfig',
    'usuarios.apps.UsuariosConfig',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'simple_history.middleware.HistoryRequestMiddleware',
]

ROOT_URLCONF = 'HealthLab.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'HealthLab.wsgi.application'


# ─────────────────────────────────────────────────────────────────────────────
# Base de datos
# ─────────────────────────────────────────────────────────────────────────────
# SQLite solo para desarrollo y pruebas unitarias. Producción: PostgreSQL vía
# DATABASE_URL (RNF-31.3). ATOMIC_REQUESTS garantiza que cada petición sea una
# transacción (RNF-29); los servicios además abren transaction.atomic() explícito.

DATABASE_URL = os.environ.get('DATABASE_URL', '').strip()
if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.parse(DATABASE_URL, conn_max_age=60, conn_health_checks=True),
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
            'OPTIONS': {'timeout': 20},
        }
    }
DATABASES['default']['ATOMIC_REQUESTS'] = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'usuarios.Usuario'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 10}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ─────────────────────────────────────────────────────────────────────────────
# Internacionalización y tiempo
# ─────────────────────────────────────────────────────────────────────────────
# USE_TZ=True: todo se guarda en UTC y se presenta en America/Bogota (RNF-35).

LANGUAGE_CODE = 'es-CO'
TIME_ZONE = 'America/Bogota'
USE_I18N = True
USE_TZ = True


# ─────────────────────────────────────────────────────────────────────────────
# Archivos estáticos y media
# ─────────────────────────────────────────────────────────────────────────────

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'static'

MEDIA_URL = '/media/'
MEDIA_ROOT = Path(os.environ.get('DJANGO_MEDIA_ROOT', '').strip() or (BASE_DIR / 'media'))
REPORTS_DIR = MEDIA_ROOT / 'reports'


# ─────────────────────────────────────────────────────────────────────────────
# Django REST Framework
# ─────────────────────────────────────────────────────────────────────────────
# Toda la API exige autenticación salvo lo que se declare explícitamente
# (login, refresh, ingesta de lecturas con token de middleware) — RN-20, RNF-01.1.

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PAGINATION_CLASS': 'HealthLab.pagination.PaginacionLimitOffset',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_THROTTLE_CLASSES': (
        'rest_framework.throttling.ScopedRateThrottle',
    ),
    'DEFAULT_THROTTLE_RATES': {
        'login': os.environ.get('DJANGO_LOGIN_THROTTLE', '5/min'),
        'refresh': '30/min',
        'latido': '120/min',
    },
    'EXCEPTION_HANDLER': 'HealthLab.exceptions.manejador_excepciones',
    'DATETIME_FORMAT': '%Y-%m-%dT%H:%M:%S%z',
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),   # RNF-03
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'UPDATE_LAST_LOGIN': True,
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'HealthLab LIMS API',
    'DESCRIPTION': (
        'API REST para la gestión de laboratorios clínicos de nivel I y II: '
        'pacientes, órdenes, muestras, resultados, validación, informes y '
        'captura de datos desde analizadores.'
    ),
    'VERSION': '2.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'SCHEMA_PATH_PREFIX': r'/(api/v1|usr)/',
    'ENUM_NAME_OVERRIDES': {'EstadoEquipoEnum': 'laboratorio.models.ConfiguracionEquipo.ESTADO_CHOICES'},
}

# Documentación interactiva solo en desarrollo (RNF-27)
EXPONER_DOCUMENTACION_API = DEBUG or env_bool('DJANGO_EXPONER_DOCS', False)


# En las pruebas, un hasher rápido: PBKDF2 hace que cada create_user tarde ~0,5 s.
if len(sys.argv) > 1 and sys.argv[1] == 'test':
    PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']


# ─────────────────────────────────────────────────────────────────────────────
# Registro (logs)
# ─────────────────────────────────────────────────────────────────────────────

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'estandar': {'format': '%(asctime)s %(levelname)s %(name)s: %(message)s'},
    },
    'handlers': {
        'consola': {'class': 'logging.StreamHandler', 'formatter': 'estandar'},
    },
    'root': {'handlers': ['consola'], 'level': 'INFO'},
    'loggers': {
        'django.request': {'level': 'WARNING'},
        'laboratorio': {'level': 'DEBUG' if DEBUG else 'INFO'},
        'usuarios': {'level': 'DEBUG' if DEBUG else 'INFO'},
    },
}
