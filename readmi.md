# Sistema LIMS HealthLab - Documentación General del Proyecto

Esta es la documentación oficial del proyecto **HealthLab**, abarcando tanto el sistema Backend (Django) como la Aplicación Móvil (React Native/Expo). Este documento detalla el cumplimiento de todos los requisitos propuestos para la entrega final del proyecto.

## 1. Componentes de la Actividad

### Problema Planteado Inicialmente
En los entornos clínicos y laboratorios modernos, la gestión manual de órdenes, muestras y resultados médicos genera cuellos de botella operativos, incrementa el riesgo de errores en la transcripción de datos y dificulta la trazabilidad completa del paciente. Existe la necesidad de un sistema digital integral que gestione el flujo operativo de un laboratorio clínico de manera eficiente, segura y alineada con las normativas de salud vigentes (como los catálogos CUPS y las bases de datos de Divipola en Colombia).

### Objetivo General del Proyecto
Desarrollar e implementar un Sistema de Gestión de Información de Laboratorio (LIMS) completo y funcional, compuesto por una API Backend robusta en la nube y una aplicación móvil cliente. El objetivo es facilitar la interacción en tiempo real del personal clínico (Médicos, Bacteriólogos, Técnicos, Administradores) con los datos médicos, automatizando y asegurando las fases pre-analíticas, analíticas y post-analíticas del laboratorio.

### Funcionalidades Implementadas
- Gestión, importación y validación de catálogos clínicos (Códigos CUPS, Parámetros biomédicos).
- Registro y admisión de pacientes integrando bases de datos de ubicación (Divipola).
- Creación de órdenes de laboratorio mediante selección inteligente de exámenes.
- Trazabilidad y validación física de recolección de muestras.
- Lectura de resultados (tanto contingencia manual como capacidad para lectura serial automatizada).
- Proceso de validación post-analítica de resultados por bacteriólogos, con sistema de alertas de pánico.
- Generación de reportes clínicos estandarizados en PDF.

### Justificación
La aplicación desarrollada responde a la necesidad identificada al centralizar el ciclo completo de procesamiento en una única plataforma digital. Mediante la aplicación móvil de HealthLab, el personal de enfermería puede asegurar la trazabilidad de las muestras in-situ, mientras los médicos y bacteriólogos validan y revisan los resultados con una reducción crítica de latencia y error humano. La arquitectura nativa móvil sobre una API REST garantiza portabilidad, escalabilidad y seguridad.

---

## 2. Implementación Final de la Aplicación Móvil y Backend

El proyecto incluye un sistema funcional en ambos extremos:
- **Tecnología Backend**: API RESTful desarrollada en Python usando **Django** y **Django REST Framework (DRF)**.
- **Tecnología Cliente**: Aplicación móvil desarrollada en **Expo con React Native** (y TypeScript).
- **Navegación Cliente**: Estructurada de manera integral usando `React Navigation` (Stack y Tabs).
- **Flujos Base Implementados**:
  - Registro de nuevos usuarios y pacientes.
  - Inicio de sesión protegido con validación de credenciales.
  - Acceso a funcionalidades principales divididas por módulos interactivos.
  - Cierre de sesión seguro y limpieza de entorno.

---

## 3. Diseño de Interfaz y Experiencia de Usuario (UI/UX)

- **Consistencia Visual**: Se implementó un diseño limpio y moderno con soporte para un sistema de **Theming (Dark/Light Mode)**. Consistencia en el uso de tipografía, paletas de colores semánticas, distribución espacial e íconos intuitivos.
- **Retroalimentación Visual**: La aplicación provee feedback constante al usuario mediante indicadores de carga (Spinners), notificaciones Toast de éxito, e interfaces descriptivas ante estados de error, guiadas por las respuestas del Backend.

---

## 4. Seguridad de la Aplicación

- **Autenticación (JWT)**: Intercambio riguroso de JSON Web Tokens. El backend genera, valida y revoca los tokens utilizando `djangorestframework_simplejwt` con `token_blacklist`.
- **Control de Acceso (RBAC y GUARDS)**: Implementación de Control de Acceso Basado en Roles (Médico, Bacteriólogo, Técnico de Enfermería, Administrador). Las vistas en el frontend están protegidas y los endpoints del backend utilizan decoradores y clases de permisos de DRF para rechazar acciones no autorizadas.
- **Manejo de Errores HTTP**: Respuestas semánticas emitidas por el Backend e interceptadas por el Frontend:
  - `401 Unauthorized`: Token inválido o expirado. Gatilla renovación.
  - `403 Forbidden`: Violación de políticas RBAC.
  - `404 Not Found`: Recursos inexistentes.
  - `422/400 Bad Request`: Errores de validación de modelos, capturados visualmente en los formularios móviles.
  - `500 Server Error`: Fallo interno del servidor controlado.

---

## 5. Gestión de Estado y Persistencia de Sesión

- **Manejo del Estado y Persistencia**: El frontend utiliza **Zustand** y `AsyncStorage` para persistir localmente el Token de acceso y Refresh token.
- **Administración de Sesión**: Renovación de sesión automática en segundo plano mediante interceptores de Axios y rutas del Backend específicas para re-expedición de JWT.

---

## 6. Consumo de Datos y Paginación

- **Integración Backend**: Consumo estructurado a la API central en Django. El Backend expone rutas bajo `/api/v1/`.
- **Presentación de Datos**: Listas optimizadas, formularios con selectores dinámicos y generación de archivos binarios (PDF de reportes) entregados directamente al móvil.
- **Paginación Inteligente**: Todos los listados de la API de Django usan `LimitOffsetPagination`. El cliente los consume progresivamente para optimizar uso de memoria (Scroll Infinito).

---

## 7. Documentación Técnica de la Aplicación (Estructura)

- **Uso de Repositorios**: Control de versiones mediante Git (GitHub).
- **Criterio de Separación (Backend)**: 
  - Organización modular mediante apps de Django (`usuarios`, `laboratorio`).
  - Separación de Modelos, Vistas (Views/ViewSets), Serializadores (Serializers) y URLs.
- **Criterio de Separación (Frontend)**:
  - Vistas, componentes, servicios de red, tiendas de estado y navegación lógicamente separados.
- **Reuso de Componentes**: DRY (Don't Repeat Yourself) implementado en ambos entornos.
- **Estrategias de Código**: Python PEP 8 en backend; TypeScript y convenciones React en Frontend. Endpoints documentados vía Swagger/OpenAPI.

---

## Ejecución Local del Proyecto Backend (Django)

```bash
cd HealthLab

# Activar entorno virtual (Linux/macOS)
source .venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Aplicar migraciones base de datos
python manage.py migrate

# Levantar el servidor en el puerto 8000
python manage.py runserver 0.0.0.0:8000
```
> La documentación interactiva (Swagger) de la API estará disponible en: `http://127.0.0.1:8000/api/docs/`

## 🚀 Despliegue en Producción

Para llevar la API del Backend a un entorno productivo (ej. AWS, DigitalOcean, Heroku), debes seguir estos pasos:

1. **Variables de Entorno**: Cambiar `DEBUG = False` en `settings.py` y configurar `ALLOWED_HOSTS` con la IP o dominio de tu servidor.
2. **Base de Datos**: Migrar de SQLite (desarrollo) a PostgreSQL de manera definitiva, ajustando la variable `DATABASES`.
3. **Servidor WSGI**: Servir la aplicación utilizando **Gunicorn** detrás de un proxy inverso como **Nginx**:
   ```bash
   pip install gunicorn
   gunicorn HealthLab.wsgi:application --bind 0.0.0.0:8000
   ```
4. **Archivos Estáticos**: Ejecutar el comando para recolectar los estáticos del panel de admin.
   ```bash
   python manage.py collectstatic
   ```
