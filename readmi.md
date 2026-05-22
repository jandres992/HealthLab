# Sistema LIMS HealthLab - Documentación Integral

El ecosistema **HealthLab** es una plataforma integral (LIMS - *Laboratory Information Management System*) diseñada para gestionar todo el flujo operativo de un laboratorio clínico. El sistema centraliza la administración de datos, asegurando la trazabilidad desde que un paciente ingresa al laboratorio hasta la entrega final de sus resultados.

> **Nota aclaratoria sobre la tecnología frontend**: Aunque se hizo mención a "Vue", el código real del proyecto cliente (`HealthLabMobile`) está construido utilizando **React Native y Expo (TypeScript)**. Esta elección de tecnología permite que el mismo código fuente se ejecute como Aplicación Móvil (Android/iOS) y como Aplicación Web desde el navegador.

---

## 🔬 ¿Qué hace la aplicación completa?

El sistema unifica a médicos, bacteriólogos, técnicos y administradores bajo una sola plataforma que automatiza y asegura **6 fases operativas principales**:

1. **Configuración y Catálogos**: Parametrización de los exámenes médicos (catálogos CUPS), parámetros de los equipos médicos y datos geopolíticos (Divipola).
2. **Registro y Admisión**: Creación de pacientes en el sistema y generación de órdenes de exámenes de laboratorio.
3. **Trazabilidad de Muestras**: Los técnicos en enfermería registran la toma de las muestras, y luego en el laboratorio central estas son recibidas, procesadas o rechazadas con justificación.
4. **Gestión de Resultados**: Integración de los resultados de los exámenes. El sistema está preparado para la lectura serial desde máquinas automatizadas, así como para la carga manual (Plan de contingencia).
5. **Validación Post-analítica**: Los bacteriólogos revisan, validan y aprueban o rechazan los resultados técnicos antes de su liberación.
6. **Informes y Reportes**: Generación automatizada de reportes médicos en formato PDF (preliminares y definitivos) y un sistema interno de notificaciones y alertas.

El proyecto está dividido en dos partes principales: el **Backend (API)** y el **Frontend (Cliente Multipantalla)**.

---

## ⚙️ 1. Backend: Núcleo y API (`/home/andres/aplicaciones/HealthLab`)

El backend actúa como el motor central del sistema. Provee una API RESTful robusta y segura encargada de manejar la base de datos, la lógica de negocio clínica, la generación de reportes y la seguridad.

### Stack Tecnológico
* **Lenguaje y Framework**: Python 3.12+ con Django 6.0 y Django REST Framework (DRF).
* **Autenticación**: JSON Web Tokens (JWT) utilizando `djangorestframework_simplejwt` con control estricto de sesiones (Token Blacklist).
* **Documentación API**: OpenAPI 3.0 / Swagger UI (vía `drf-spectacular`).
* **Generación de Archivos**: `reportlab` para la construcción nativa y dinámica de informes de laboratorio en PDF.

### Módulos Principales
* **Módulo `usuarios`**: Encargado del control de acceso basado en roles (RBAC). Soporta roles como Administrador, Médico, Bacteriólogo y Técnico de Enfermería. También registra "Dispositivos de confianza".
* **Módulo `laboratorio`**: Contiene la lógica clínica. Gestiona desde los catálogos CUPS, pasando por órdenes, muestras y exámenes, hasta la lectura serial de máquinas y generación de PDF.

---

## 📱 2. Frontend: App Móvil y Web (`/home/andres/aplicaciones/HealthLabMobile`)

El frontend es la interfaz gráfica que utilizan los profesionales del laboratorio. Se conecta exclusivamente al Backend a través de su API REST.

### Stack Tecnológico
* **Framework**: React Native con **Expo**, lo que permite compilar la app tanto para móviles (Android/iOS) como para Web Browser (React Native Web).
* **Lenguaje**: TypeScript para asegurar el tipado fuerte y confiabilidad del código.
* **Manejo de Estado**: **Zustand** (con persistencia local en `AsyncStorage`) para manejar la sesión global, perfil del usuario y flujos clínicos locales.
* **Navegación**: React Navigation (Bottom Tabs y Stack Navigators)

### Características Clave
* **Autenticación Persistente**: Los tokens de seguridad (JWT) se guardan localmente. El sistema intercepta errores `401 Unauthorized` de la API e intenta renovar (refresh) el token en segundo plano para evitar interrumpir al usuario.
* **Guardias de Navegación (RBAC)**: La interfaz gráfica se adapta al usuario. Un Técnico de Enfermería verá opciones diferentes a un Bacteriólogo; las vistas no autorizadas son bloqueadas.
* **Soporte de Contingencia**: La aplicación está diseñada para funcionar ágilmente. Posee colas para operaciones offline (guardado temporal por pérdida de red) e ingreso manual de datos.

---

## 🚀 Despliegue y Ejecución Rápida

Para ejecutar la aplicación de forma local, es necesario iniciar ambos sistemas de manera paralela.

### 1. Iniciar el Backend (Django)
```bash
cd /home/andres/aplicaciones/HealthLab
# Activar entorno virtual (Linux/macOS)
source .venv/bin/activate
# Instalar dependencias (si es necesario)
pip install -r requirements.txt
# Levantar el servidor en el puerto 8000
python manage.py runserver 0.0.0.0:8000
```
> La documentación interactiva (Swagger) de la API estará disponible en: `http://127.0.0.1:8000/api/docs/`

### 2. Iniciar el Frontend (React Native / Expo)
```bash
cd /home/andres/aplicaciones/HealthLabMobile
# Instalar dependencias de Node
npm install
# Levantar el entorno de Expo
npx expo start
```
> Desde la consola de Expo puedes presionar **'w'** para abrir la versión Web, **'a'** para Android, o escanear el código QR con la app **Expo Go** en un dispositivo físico. Asegúrate de configurar la variable `EXPO_PUBLIC_API_URL` en el archivo `.env` apuntando a la IP local de tu Backend.
