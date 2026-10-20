# HealthLab — Backend (Django + Django REST Framework)

API del sistema LIMS HealthLab. La especificación completa está en
[`../Ingenieria_de_Requerimientos_HealthLab.md`](../Ingenieria_de_Requerimientos_HealthLab.md)
(§15 y §16 describen el plan que este código ejecuta).

## Estado de la migración

| Bloque | Estado |
|---|---|
| Configuración por entorno (`.env`), `IsAuthenticated` por defecto, throttling de login, errores estándar | ✔ |
| Roles múltiples, matriz de acciones (`usuarios/acciones.py`), `/usr/me/` con `acciones[]`, auditoría, historial de cuentas | ✔ |
| Capa de dominio (`laboratorio/domain/`) y servicios transaccionales (`laboratorio/services/`) | ✔ |
| Estados finales en catálogo, cierre de órdenes (RN-10), anulación, informes parcial/final con hash encadenado | ✔ |
| Historial y versión optimista en entidades clínicas, FK `PROTECT`, secuencia de órdenes | ✔ |
| Idempotencia (`Idempotency-Key`), esquema OpenAPI sin advertencias | ✔ |
| PostgreSQL, Celery/Redis (PDF y notificaciones asíncronas), `django-pghistory` | pendiente (requiere instalar PostgreSQL) |
| Bridge de analizadores, CCI, cadena de custodia, acuse de críticos (Fase 2) | pendiente |

## Ejecución local

```bash
cd HealthLab
python -m venv venv
venv\Scripts\activate            # Windows   |   source venv/bin/activate  (Linux/macOS)
pip install -r requirements.txt
copy .env.example .env           # ajustar valores
python manage.py migrate
python manage.py seed_test_data  # datos de prueba: usuarios, roles, catálogos, órdenes
python manage.py runserver 0.0.0.0:8000
```

- Documentación interactiva (solo con `DJANGO_DEBUG=true`): <http://127.0.0.1:8000/api/docs/>
- Esquema OpenAPI (siempre): <http://127.0.0.1:8000/api/schema/>

### Usuarios de prueba (`seed_test_data`)

Contraseña de todos: `Prueba123*`

| Usuario | Rol |
|---|---|
| `carlos_moreno`, `maria_santos` | Médico |
| `fernando_ruiz`, `sandra_vera` | Bacteriólogo |
| `helena_gomez`, `ricardo_flores` | Técnico de Enfermería |
| `luis_torres`, `patricia_castro` | Auditor |
| `jorge_pena`, `catalina_ramirez` | Administrador |

> Un usuario **sin rol** no puede iniciar sesión (RF-01.1). Un superusuario de Django solo
> puede gestionar cuentas y catálogos; **no** puede validar ni finalizar (RN-19).

## Pruebas

```bash
python manage.py test
```

46 pruebas por rol: seguridad de usuarios, flujo clínico completo, reglas de cierre,
rollback cuando falla el PDF, inmutabilidad de resultados validados, permisos e idempotencia.

## Estructura

```
HealthLab/
├── HealthLab/            settings (por entorno), urls, exceptions (formato estándar),
│                         pagination, idempotencia
├── usuarios/             cuentas, roles.py, acciones.py (matriz §8.1), permissions.py,
│                         auditoria.py, tokens.py, /usr/me/
└── laboratorio/
    ├── domain/           errores.py, estados.py (máquinas de estado, RN-10)
    ├── services/         ordenes, muestras, examenes, resultados, informes, pacientes,
    │                     notificaciones — cada uno una transacción con bloqueo de filas
    ├── views.py          ViewSets delgados: permiso por acción + serializador + servicio
    ├── serializers.py    campos explícitos; estados de solo lectura
    └── utils.py          rangos por sexo/edad, banderas, PDF
```

## Contrato con los clientes

- Toda la API exige JWT (`Authorization: Bearer`) salvo `POST /usr/login/`,
  `POST /usr/token/refresh/` y `POST /api/v1/lecturas-serial/` con `X-Middleware-Token`.
- El login y `GET /usr/me/` devuelven `roles[]` y `acciones[]`: las interfaces muestran
  solo lo que el backend permite (RF-44.1).
- Los estados (`estado_general`, `estado_examen`, `estado_muestra`) son de solo lectura;
  cambian con las acciones `admitir`, `recibir-laboratorio`, `rechazar`, `aprobar`,
  `anular`, `finalizar` (RN-23). Una transición inválida responde `409`.
- `POST /api/v1/ordenes/` recibe `examenes: [cups...]` y crea todo en una transacción.
- Las escrituras aceptan `Idempotency-Key`; un reenvío devuelve la respuesta original.
- Listados: sin `?limit=` devuelven el arreglo completo (compatibilidad con la app Expo);
  con `?limit=&offset=` responden paginados. Al retirar la app Expo se paginará siempre.
- Errores: `{ "estado": "...", "mensaje": "...", "errores": {...} }`.

## Producción

`DJANGO_DEBUG=false` exige `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`,
`DJANGO_CORS_ALLOWED_ORIGINS` y `DATABASE_URL` (PostgreSQL). Activa HTTPS forzado, HSTS y
cookies seguras. Servir con Gunicorn detrás de Nginx; `collectstatic` para el admin.
