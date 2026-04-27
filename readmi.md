# HealthLab Backend (Django + DRF)

Backend para gestion de laboratorio clinico (LIMS) con flujo operativo de fases 1 a 6:

1. Configuracion de catalogos y equipos
2. Registro de pacientes y ordenes
3. Toma y trazabilidad de muestras
4. Integracion serial de equipos
5. Validacion post-analitica
6. Informes y notificaciones

## Stack tecnico

- Python 3.12+
- Django 6.0.3
- Django REST Framework 3.16.1
- JWT (SimpleJWT)
- drf-spectacular (OpenAPI / Swagger)
- SQLite (desarrollo)
- ReportLab (generacion de PDF)

## Estructura principal

- HealthLab/: configuracion global del proyecto
- laboratorio/: dominio clinico (ordenes, muestras, resultados, informes)
- usuarios/: autenticacion, perfiles, tipos de usuario, permisos
- db.sqlite3: base de datos local
- manage.py: comandos Django

## Dependencias

Dependencias actuales detectadas:

- asgiref==3.11.1
- attrs==25.4.0
- Django==6.0.3
- django-cors-headers==4.9.0
- djangorestframework==3.16.1
- djangorestframework_simplejwt==5.5.1
- drf-spectacular==0.29.0
- inflection==0.5.1
- jsonschema==4.26.0
- jsonschema-specifications==2025.9.1
- pillow==12.1.1
- PyJWT==2.11.0
- PyYAML==6.0.3
- referencing==0.37.0
- reportlab==4.4.10
- rpds-py==0.30.0
- sqlparse==0.5.5
- tzdata==2025.3
- uritemplate==4.2.0

## Instalacion y ejecucion

### 1) Crear y activar entorno virtual

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2) Instalar dependencias

```bash
pip install -r requirements.txt
```

Nota: si tu entorno presenta error de codificacion con requirements.txt, conviertelo a UTF-8 y reintenta.

### 3) Migraciones

```bash
python manage.py makemigrations
python manage.py migrate
```

### 4) Cargar datos de prueba

```bash
python manage.py seed_test_data
```

### 5) Levantar servidor

```bash
python manage.py runserver
```

Servidor local:

- http://127.0.0.1:8000/

## Configuracion relevante

Valores principales en settings:

- DEBUG = True
- ALLOWED_HOSTS = ["*"]
- CORS_ALLOW_ALL_ORIGINS = True (solo desarrollo)
- AUTH_USER_MODEL = usuarios.Usuario
- DB por defecto: SQLite (db.sqlite3)
- Zona horaria: America/Bogota
- Idioma: es-CO
- JWT access token: 60 minutos
- JWT refresh token: 7 dias

## Autenticacion

Login:

- POST /usr/login/

Refresh:

- POST /usr/token/refresh/

Header requerido:

```http
Authorization: Bearer <token>
Content-Type: application/json
```

## Documentacion de API

- Swagger UI: /api/docs/
- OpenAPI schema: /api/schema/
- ReDoc: /api/redoc/

## Rutas base

- /api/v1/ -> endpoints del modulo laboratorio
- /usr/ -> endpoints del modulo usuarios
- /admin/ -> panel de administracion Django

## Modulo laboratorio (resumen)

Recursos principales:

- catalogo-cups
- parametros
- equipos
- pacientes
- ordenes
- muestras
- examenes-solicitados
- lecturas-serial
- resultados
- informes
- notificaciones

Acciones destacadas:

- ordenes/{id}/admitir/
- ordenes/{id}/reporte-pdf/
- muestras/buscar/
- muestras/{id}/recibir-laboratorio/
- muestras/{id}/rechazar/
- examenes-solicitados/{id}/aprobar/
- examenes-solicitados/{id}/rechazar/
- lecturas-serial/{id}/procesar/
- notificaciones/{id}/marcar-leida/
- notificaciones/marcar-todas-leidas/

## Modulo usuarios (resumen)

Recursos:

- tipos-id
- sexos
- departamentos
- municipios
- usuarios
- tipos-usuario
- permisos
- usuarios-permisos
- dispositivos-confianza

## Roles de negocio vigentes

Modelo simplificado actual:

- Medico
- Bacteriologo
- Administrador
- Tecnico de Enfermeria (toma y registro de muestras)

## Seguridad actual

- Existe modelo de roles y permisos en base de datos.
- El usuario admin tiene todos los permisos vigentes asignados.
- Pendiente recomendado: enforcement estricto de permisos por endpoint usando permission_classes en DRF.

## Comandos utiles

```bash
python manage.py check
python manage.py createsuperuser
python manage.py shell
python manage.py seed_test_data
```

## Estado del proyecto

Backend funcional para desarrollo local con:

- modelos clinicos y de usuarios operativos
- JWT habilitado
- documentacion OpenAPI habilitada
- generacion de informes PDF
- semilla de datos para pruebas

## Licencia

Uso academico / interno (ajustar segun politica del equipo).
