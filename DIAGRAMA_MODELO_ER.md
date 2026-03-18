# Diagrama Entidad-Relacion - HealthLab Backend

Este diagrama resume las entidades definidas en los modelos de las aplicaciones laboratorio y usuarios.

Nota: Usuario hereda de AbstractUser de Django. En el diagrama se muestran los campos propios del proyecto y no las tablas internas de autenticacion de Django como auth_group o auth_permission.

```mermaid
erDiagram
    TIPO_DOCUMENTO_PACIENTE {
        int id PK
        string codigo UK
        string descripcion
        boolean activo
    }

    SEXO_BIOLOGICO {
        int id PK
        string codigo UK
        string descripcion
    }

    ESTADO_ORDEN {
        int id PK
        string nombre UK
        string descripcion
    }

    ESTADO_EXAMEN {
        int id PK
        string nombre UK
        string descripcion
    }

    CATALOGO_CUPS {
        int id PK
        string codigo_cups UK
        string descripcion
        boolean activo
    }

    PARAMETRO_EXAMEN {
        int id PK
        int cups_id FK
        string nombre_parametro
        string unidades_medida
        decimal rango_referencia_minimo
        decimal rango_referencia_maximo
        string rango_texto
    }

    PACIENTE {
        uuid id PK
        int tipo_documento_id FK
        string numero_documento
        string primer_nombre
        string segundo_nombre
        string primer_apellido
        string segundo_apellido
        date fecha_nacimiento
        int sexo_biologico_id FK
        string telefono
        string correo_electronico
        boolean activo
        datetime fecha_creacion
    }

    ORDEN_LABORATORIO {
        uuid id PK
        uuid paciente_id FK
        string numero_orden UK
        datetime fecha_orden
        text observaciones_clinicas
        int estado_general_id FK
    }

    MUESTRA_FISICA {
        uuid id PK
        uuid orden_id FK
        string codigo_barras UK
        string tipo_muestra
        datetime fecha_recoleccion
    }

    EXAMEN_SOLICITADO {
        uuid id PK
        uuid orden_id FK
        int cups_id FK
        uuid muestra_id FK
        int estado_examen_id FK
    }

    LECTURA_EQUIPO_SERIAL {
        uuid id PK
        string equipo_origen
        string codigo_barras_leido
        datetime fecha_recepcion
        text trama_cruda
        json datos_json
        boolean procesado
    }

    RESULTADO_ANALITO {
        uuid id PK
        uuid examen_solicitado_id FK
        int parametro_id FK
        uuid lectura_serial_id FK
        string valor_resultado
        boolean es_anormal
        datetime fecha_procesamiento
    }

    TIPO_ID {
        int id PK
        string tipo_id
        string detalle
        boolean estado
    }

    SEXO_USUARIO {
        int id PK
        string sexo
        string descripcion
    }

    DEPARTAMENTO {
        int id PK
        string codigo
        string departamento
    }

    MUNICIPIO {
        int id PK
        string codigo
        string municipio
        int departamento_id FK
    }

    USUARIO {
        int id PK
        int tipo_id_id FK
        string username
        string email
        string numero_id
        string p_nombre
        string s_nombre
        string p_apellido
        string s_apellido
        date f_nacimiento
        int sexo_id FK
        int municipio_residencia_id FK
        string direccion_residencia
        string telefono
        string avatar
        boolean recibir_notificaciones
    }

    TIPO_USUARIO {
        int id PK
        string tipo
        text descripcion
    }

    PERMISO {
        int id PK
        string permiso
        int tipo_usuario_id FK
    }

    USUARIO_X_PERMISO {
        int id PK
        int permiso_id FK
        int usuario_id FK
    }

    DISPOSITIVO_CONFIANZA {
        int id PK
        int usuario_id FK
        string device_id
        string nombre
        text user_agent
        datetime ultimo_acceso
        datetime creado_en
        boolean es_confiable
    }

    TIPO_DOCUMENTO_PACIENTE ||--o{ PACIENTE : clasifica
    SEXO_BIOLOGICO ||--o{ PACIENTE : define
    PACIENTE ||--o{ ORDEN_LABORATORIO : tiene
    ESTADO_ORDEN ||--o{ ORDEN_LABORATORIO : controla
    ORDEN_LABORATORIO ||--o{ MUESTRA_FISICA : genera
    ORDEN_LABORATORIO ||--o{ EXAMEN_SOLICITADO : solicita
    CATALOGO_CUPS ||--o{ PARAMETRO_EXAMEN : contiene
    CATALOGO_CUPS ||--o{ EXAMEN_SOLICITADO : estandariza
    MUESTRA_FISICA o|--o{ EXAMEN_SOLICITADO : alimenta
    ESTADO_EXAMEN ||--o{ EXAMEN_SOLICITADO : controla
    EXAMEN_SOLICITADO ||--o{ RESULTADO_ANALITO : produce
    PARAMETRO_EXAMEN ||--o{ RESULTADO_ANALITO : parametriza
    LECTURA_EQUIPO_SERIAL o|--o{ RESULTADO_ANALITO : origina

    DEPARTAMENTO ||--o{ MUNICIPIO : contiene
    TIPO_ID ||--o{ USUARIO : identifica
    SEXO_USUARIO ||--o{ USUARIO : clasifica
    MUNICIPIO ||--o{ USUARIO : ubica
    TIPO_USUARIO ||--o{ PERMISO : agrupa
    PERMISO ||--o{ USUARIO_X_PERMISO : asigna
    USUARIO ||--o{ USUARIO_X_PERMISO : recibe
    USUARIO ||--o{ DISPOSITIVO_CONFIANZA : registra
```

## Restricciones relevantes

- Paciente tiene unicidad compuesta en tipo_documento + numero_documento.
- ParametroExamen tiene unicidad compuesta en cups + nombre_parametro.
- ResultadoAnalito tiene unicidad compuesta en examen_solicitado + parametro.
- DispositivoConfianza tiene unicidad compuesta en usuario + device_id.
- ExamenSolicitado puede existir sin muestra asociada porque la FK muestra es nullable.
- ResultadoAnalito puede existir sin lectura serial asociada porque la FK lectura_serial es nullable.

## Lectura rapida del dominio

- El flujo principal de laboratorio es: Paciente -> OrdenLaboratorio -> MuestraFisica / ExamenSolicitado -> ResultadoAnalito.
- CatalogoCups y ParametroExamen modelan el estandar tecnico de cada examen.
- LecturaEquipoSerial representa la entrada cruda desde equipos de laboratorio y puede alimentar resultados.
- El modulo usuarios es administrativo y de autenticacion, separado del flujo clinico.