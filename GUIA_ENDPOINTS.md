# Guia Completa de Endpoints - HealthLab Backend

## 1. Resumen del Proyecto

Backend en Django + Django REST Framework con dos modulos principales:

- `laboratorio`: flujo clinico (pacientes, ordenes, muestras, examenes, lecturas seriales, resultados).
- `usuarios`: gestion de usuarios, catalogos de identidad/geografia, permisos y autenticacion JWT.

Tambien expone documentacion OpenAPI con `drf-spectacular`.

## 2. URL Base y Rutas Globales

Asumiendo ejecucion local:

- Base sugerida: `http://127.0.0.1:8000`

Rutas globales:

- `GET /api/schema/` - esquema OpenAPI.
- `GET /api/docs/` - Swagger UI.
- `GET /api/redoc/` - ReDoc.
- `GET /admin/` - panel admin Django.

## 3. Autenticacion

Configuracion global:

- Tipo: JWT Bearer (`Authorization: Bearer <token>`).
- `ACCESS_TOKEN_LIFETIME`: 60 minutos.
- `REFRESH_TOKEN_LIFETIME`: 7 dias.

Endpoints de auth:

- `POST /usr/login/` - obtiene `access` y `refresh`.
- `POST /usr/token/refresh/` - renueva access token.

Nota importante: en el codigo actual no hay `permission_classes` definidos por vista, por lo que los endpoints quedan accesibles segun las politicas por defecto del proyecto/DRF (actualmente no restringidas por vista).

## 4. Convenciones de Respuesta

### 4.1 Endpoints de `laboratorio`

La mayoria hereda de `EstandarRespuestaViewSet` y usa este formato (principalmente en `create`, `retrieve`, `update`, `destroy`):

- Exito:
  - `{"estado": "exito", "mensaje": "...", "datos": {...}}`
- Validacion:
  - `{"estado": "error_validacion", "mensaje": "...", "errores": {...}}`
- No encontrado:
  - `{"estado": "no_encontrado", "mensaje": "..."}`
- Error servidor:
  - `{"estado": "error_servidor", "mensaje": "..."}`

Detalle tecnico importante:

- `list` (`GET coleccion`) **no esta sobreescrito**; por eso responde con formato DRF estandar (lista/paginacion), no con `estado/mensaje`.

### 4.2 Endpoints de `usuarios`

Usan `ModelViewSet` estandar DRF, por lo que devuelven JSON directo (sin wrapper `estado`).

## 5. Endpoints del Modulo Laboratorio

El router de laboratorio esta expuesto en dos prefijos equivalentes:

- ` /api/v1/...`
- ` /lab/api/v1/...`

Ambos apuntan a los mismos ViewSets.

## 5.1 Catalogos y Referencias (CRUD)

Cada endpoint soporta operaciones REST de `ModelViewSet`:

- `GET {ruta}/` (listar)
- `POST {ruta}/` (crear)
- `GET {ruta}/{id}/` (detalle)
- `PUT {ruta}/{id}/` (reemplazo)
- `PATCH {ruta}/{id}/` (actualizacion parcial)
- `DELETE {ruta}/{id}/` (eliminar)

Rutas:

- `/api/v1/catalogo-cups/`
- `/api/v1/parametros/`
- `/api/v1/tipos-documento/`
- `/api/v1/sexos-biologicos/`
- `/api/v1/estados-orden/`
- `/api/v1/estados-examen/`

Campos principales por recurso:

### `catalogo-cups`

- `codigo_cups` (string, unico, requerido)
- `descripcion` (string, requerido)
- `activo` (bool, opcional, default `true`)

### `parametros`

- `cups` (FK a `catalogo-cups`, requerido)
- `nombre_parametro` (string, requerido)
- `unidades_medida` (string, opcional)
- `rango_referencia_minimo` (decimal, opcional)
- `rango_referencia_maximo` (decimal, opcional)
- `rango_texto` (string, opcional)

Restriccion:

- unico por (`cups`, `nombre_parametro`).

### `tipos-documento`

- `codigo` (string <= 3, unico)
- `descripcion` (string)
- `activo` (bool)

### `sexos-biologicos`

- `codigo` (string 1, unico)
- `descripcion` (string)

### `estados-orden`

- `nombre` (string unico)
- `descripcion` (string opcional)

### `estados-examen`

- `nombre` (string unico)
- `descripcion` (string opcional)

## 5.2 Pacientes

Ruta:

- `/api/v1/pacientes/`

Metodos:

- CRUD completo.

Campos principales (`POST`/`PUT`/`PATCH`):

- `tipo_documento` (FK id)
- `numero_documento` (string)
- `primer_nombre` (string)
- `segundo_nombre` (string opcional)
- `primer_apellido` (string)
- `segundo_apellido` (string opcional)
- `fecha_nacimiento` (date `YYYY-MM-DD`)
- `sexo_biologico` (FK id)
- `telefono` (string opcional)
- `correo_electronico` (email opcional)
- `activo` (bool, opcional)

Campos solo lectura:

- `id`, `fecha_creacion`.

Comportamientos especiales:

- `GET /api/v1/pacientes/?incluir_inactivos=true` incluye pacientes inactivos.
- `DELETE /api/v1/pacientes/{id}/` realiza **eliminacion logica** (`activo=false`) y responde `200`, no borra fisicamente.

Restriccion:

- documento unico por (`tipo_documento`, `numero_documento`).

## 5.3 Ordenes de Laboratorio

Ruta:

- `/api/v1/ordenes/`

Campos:

- `paciente` (FK UUID)
- `numero_orden` (string unico)
- `observaciones_clinicas` (texto opcional)
- `estado_general` (FK id)

Campos solo lectura:

- `id`, `fecha_orden`.

## 5.4 Muestras Fisicas

Ruta:

- `/api/v1/muestras/`

Campos:

- `orden` (FK UUID)
- `codigo_barras` (string unico, opcional al crear)
- `tipo_muestra` (string)
- `fecha_recoleccion` (datetime)

Comportamiento especial:

- Si `codigo_barras` no se envia, se autogenera como `MUE-XXXXXXXXXXXX`.

## 5.5 Examenes Solicitados

Ruta base:

- `/api/v1/examenes-solicitados/`

Campos:

- `orden` (FK UUID)
- `cups` (FK id)
- `muestra` (FK UUID, opcional)
- `estado_examen` (FK id)

Accion personalizada:

- `POST /api/v1/examenes-solicitados/{id}/aprobar/`

Reglas de `aprobar`:

- Si faltan resultados vs parametros del CUPS: `409`.
- Si no hay resultados: `400`.
- Si todo esta completo: cambia estado a `Validado` y responde `200`.

Requisito de datos maestros:

- Debe existir `EstadoExamen` con `nombre='Validado'`.

## 5.6 Lecturas de Equipo Serial

Ruta base:

- `/api/v1/lecturas-serial/`

Campos:

- `equipo_origen` (string)
- `codigo_barras_leido` (string opcional)
- `trama_cruda` (texto)
- `datos_json` (objeto JSON)
- `procesado` (bool, generalmente gestionado por backend)

Campos solo lectura:

- `id`, `fecha_recepcion`.

Accion personalizada:

- `POST /api/v1/lecturas-serial/{id}/procesar/`

Que hace `procesar`:

- Busca examenes por `muestra.codigo_barras == codigo_barras_leido`.
- Para cada parametro esperado del CUPS, intenta mapear valor desde `datos_json`.
- Crea o actualiza `ResultadoAnalito`.
- Marca `es_anormal` segun rangos min/max.
- Cambia estado de examen de `Pendiente`/`Muestra Recolectada` a `En Analisis`.
- Marca la lectura como `procesado=true`.

Respuestas relevantes:

- `400` si no hay codigo de barras.
- `404` si no hay examenes vinculados.
- `200` con conteos: `resultados_creados`, `resultados_actualizados`, `resultados_omitidos`.

Requisitos de datos maestros:

- Debe existir `EstadoExamen` con `nombre='En Analisis'`.

## 5.7 Resultados de Analitos

Ruta:

- `/api/v1/resultados/`

Campos:

- `examen_solicitado` (FK UUID)
- `parametro` (FK id)
- `lectura_serial` (FK UUID, opcional)
- `valor_resultado` (string)
- `es_anormal` (bool, calculado automaticamente en serializer)

Campos solo lectura:

- `id`, `fecha_procesamiento`.

Restriccion:

- unico por (`examen_solicitado`, `parametro`).

## 6. Endpoints del Modulo Usuarios

Prefijo unico:

- `/usr/`

Todos estos recursos son `ModelViewSet` CRUD completo (`GET/POST/GET by id/PUT/PATCH/DELETE`):

- `/usr/tipos-id/`
- `/usr/sexos/`
- `/usr/departamentos/`
- `/usr/municipios/`
- `/usr/usuarios/`
- `/usr/tipos-usuario/`
- `/usr/permisos/`
- `/usr/usuarios-permisos/`
- `/usr/dispositivos-confianza/`

## 6.1 Campos principales por recurso

### `tipos-id`

- `tipo_id`, `detalle`, `estado`.

### `sexos`

- `sexo`, `descripcion`.

### `departamentos`

- `codigo`, `departamento`.

### `municipios`

- `codigo`, `municipio`, `departamento` (FK id).

### `tipos-usuario`

- `tipo`, `descripcion`.

### `permisos`

- `permiso`, `tipo_usuario` (FK id).

### `usuarios-permisos`

- `permiso` (FK id), `usuario` (FK id).

### `dispositivos-confianza`

- `usuario` (FK id)
- `device_id` (string)
- `nombre` (string)
- `user_agent` (string opcional)
- `es_confiable` (bool)

Solo lectura:

- `ultimo_acceso`, `creado_en`.

### `usuarios`

Campos expuestos por serializer:

- `id` (read-only)
- `username` (requerido)
- `password` (write-only)
- `email`
- `tipo_id` (FK id)
- `numero_id`
- `p_nombre`, `s_nombre`, `p_apellido`, `s_apellido`
- `f_nacimiento`
- `sexo` (FK id)
- `municipio_residencia` (FK id)
- `direccion_residencia`
- `telefono`
- `avatar` (archivo)
- `recibir_notificaciones` (bool)
- `is_active` (bool)

Comportamiento especial:

- `password` se guarda en hash (`set_password`) en create/update.

## 6.2 Auth JWT

### `POST /usr/login/`

Body minimo:

```json
{
  "username": "admin",
  "password": "tu_password"
}
```

Body extendido opcional para registrar dispositivo:

```json
{
  "username": "admin",
  "password": "tu_password",
  "device_id": "android-001",
  "nombre_dispositivo": "Pixel 8",
  "user_agent": "Expo/Android",
  "es_confiable": true
}
```

Respuesta esperada (`200`):

```json
{
  "refresh": "<jwt_refresh>",
  "access": "<jwt_access>"
}
```

En error de credenciales responde `401` con `detalle`.

### `POST /usr/token/refresh/`

```json
{
  "refresh": "<jwt_refresh>"
}
```

Devuelve nuevo `access` (y segun configuracion puede rotar refresh).

## 7. Ejemplos Rapidos con cURL

## 7.1 Login

```bash
curl -X POST http://127.0.0.1:8000/usr/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"123456"}'
```

## 7.2 Crear paciente

```bash
curl -X POST http://127.0.0.1:8000/api/v1/pacientes/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "tipo_documento": 1,
    "numero_documento": "1234567890",
    "primer_nombre": "Ana",
    "primer_apellido": "Lopez",
    "fecha_nacimiento": "1998-04-10",
    "sexo_biologico": 1
  }'
```

## 7.3 Procesar lectura serial

```bash
curl -X POST http://127.0.0.1:8000/api/v1/lecturas-serial/<lectura_id>/procesar/ \
  -H "Authorization: Bearer <token>"
```

## 7.4 Aprobar examen

```bash
curl -X POST http://127.0.0.1:8000/api/v1/examenes-solicitados/<examen_id>/aprobar/ \
  -H "Authorization: Bearer <token>"
```

## 8. Hallazgos Tecnicos Relevantes del Analisis

- `laboratorio/serializers.py` contiene clases duplicadas; las ultimas definiciones sobrescriben las primeras (comportamiento efectivo actual).
- Por esa sobrescritura, en `PacienteSerializer`/`OrdenLaboratorioSerializer`/`ExamenSolicitadoSerializer` se usan FKs por ID, no `SlugRelatedField`.
- El modulo `laboratorio` esta montado dos veces (`/api/v1` y `/lab/api/v1`), lo cual duplica superficie API.
- Las acciones `aprobar` y `procesar` dependen de valores exactos en catalogos de estado (`Validado`, `En Analisis`, `Pendiente`, `Muestra Recolectada`).

## 9. Checklist de Uso en Integraciones

1. Autenticar en `/usr/login/` y guardar `access`/`refresh`.
2. Enviar `Authorization: Bearer <access>` en llamadas protegidas.
3. Crear y mantener catalogos base (tipos documento, estados, CUPS, parametros) antes del flujo operativo.
4. Flujo sugerido: paciente -> orden -> muestra -> examen -> lectura serial -> procesar -> aprobar.
5. Renovar token con `/usr/token/refresh/` cuando expire el access.
