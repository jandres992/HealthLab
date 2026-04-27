"""
Modelos del módulo laboratorio — HealthLab LIMS.
Cubre las fases 1-6 del flujo clínico: configuración, orden médica,
toma de muestras, análisis serial, validación post-analítica e informes.
"""
import uuid
from django.conf import settings
from django.db import models


# ==========================================
# 0. Tablas de Referencia (Catálogos de Dominio)
# ==========================================

class TipoDocumentoPaciente(models.Model):
    """Tipos de documento de identidad válidos en Colombia (RF-04)."""
    codigo = models.CharField(max_length=3, unique=True)
    descripcion = models.CharField(max_length=100)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = 'tipo_documento_paciente_Lab'

    def __str__(self):
        return f"{self.codigo} - {self.descripcion}"


class SexoBiologico(models.Model):
    """Sexo biológico del paciente (usado también para segmentación de rangos)."""
    codigo = models.CharField(max_length=1, unique=True)
    descripcion = models.CharField(max_length=30)

    class Meta:
        db_table = 'sexo_biologico_Lab'

    def __str__(self):
        return self.descripcion


class EstadoOrden(models.Model):
    """Estados posibles de una orden de laboratorio."""
    nombre = models.CharField(max_length=30, unique=True)
    descripcion = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        db_table = 'estado_orden_Lab'

    def __str__(self):
        return self.nombre


class EstadoExamen(models.Model):
    """Estados posibles de un examen solicitado."""
    nombre = models.CharField(max_length=30, unique=True)
    descripcion = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        db_table = 'estado_examen_Lab'

    def __str__(self):
        return self.nombre


class EstadoMuestra(models.Model):
    """Estados de la muestra física en el flujo pre-analítico (FASE 3)."""
    nombre = models.CharField(max_length=40, unique=True)
    descripcion = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        db_table = 'estado_muestra_Lab'

    def __str__(self):
        return self.nombre


# ==========================================
# 1. Catálogos y Estándares — FASE 1 (Configuración)
# ==========================================

class CatalogoCups(models.Model):
    """Códigos CUPS oficiales del Ministerio de Salud de Colombia."""
    codigo_cups = models.CharField(max_length=10, unique=True, help_text="Ej: '903895'")
    descripcion = models.CharField(max_length=255)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = 'catalogo_cups_Lab'

    def __str__(self):
        return f"{self.codigo_cups} - {self.descripcion}"


class ParametroExamen(models.Model):
    """
    Define los valores de referencia de cada analito para un CUPS.
    Soporta rangos segmentados por sexo biológico y grupo etario (FASE 1 — MinSalud).
    Un mismo parámetro puede tener múltiples filas con distintos rangos para
    diferentes combinaciones de sexo/edad.
    """
    cups = models.ForeignKey(CatalogoCups, on_delete=models.CASCADE, related_name='parametros')
    nombre_parametro = models.CharField(max_length=100, help_text="Ej: 'Leucocitos'")
    unidades_medida = models.CharField(max_length=20, blank=True, null=True, help_text="Ej: 'cel/uL'")
    # Rangos de referencia normales
    rango_referencia_minimo = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    rango_referencia_maximo = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    rango_texto = models.CharField(
        max_length=100, blank=True, null=True,
        help_text="Para valores cualitativos (Ej: 'Negativo')"
    )
    # Rangos de pánico / valores críticos
    rango_panico_minimo = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True,
        help_text="Valor crítico inferior: requiere alerta inmediata al médico."
    )
    rango_panico_maximo = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True,
        help_text="Valor crítico superior: requiere alerta inmediata al médico."
    )
    # Segmentación por sexo y edad — MinSalud (FASE 1)
    sexo_aplica = models.ForeignKey(
        SexoBiologico,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='parametros',
        help_text="Deje en blanco si el rango aplica para ambos sexos."
    )
    edad_minima_anios = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Edad mínima del paciente (inclusive) en años. Vacío = sin límite inferior."
    )
    edad_maxima_anios = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Edad máxima del paciente (inclusive) en años. Vacío = sin límite superior."
    )

    class Meta:
        db_table = 'parametro_examen_Lab'
        # Sin UniqueConstraint en (cups, nombre_parametro) para permitir rangos
        # diferenciados por sexo y grupo etario para el mismo parámetro.

    def __str__(self):
        sexo = f" [{self.sexo_aplica.codigo}]" if self.sexo_aplica else ""
        edad = ""
        if self.edad_minima_anios is not None or self.edad_maxima_anios is not None:
            edad = f" {self.edad_minima_anios or 0}-{self.edad_maxima_anios or 'inf'}a"
        return f"{self.cups.codigo_cups} | {self.nombre_parametro}{sexo}{edad}"


# ==========================================
# 1b. Configuración de Hardware — FASE 1
# ==========================================

class ConfiguracionEquipo(models.Model):
    """
    Registra los analizadores conectados al sistema vía middleware serial o TCP.
    Permite al Administrador configurar equipos (ej: URIT-500C, Mindray BC-5000).
    """
    TIPO_CONEXION_CHOICES = [
        ('SERIAL', 'Puerto Serial RS-232/USB'),
        ('TCP', 'Red TCP/IP (LIS)'),
    ]
    PROTOCOLO_CHOICES = [
        ('HL7', 'HL7 v2.x'),
        ('ASTM', 'ASTM E1381/E1394'),
        ('JSON', 'JSON propietario'),
        ('CSV', 'CSV / texto plano'),
    ]
    nombre = models.CharField(max_length=100, help_text="Ej: Analizador Hematológico Mindray BC-5000")
    codigo_equipo = models.CharField(max_length=30, unique=True, help_text="Identificador único del equipo")
    tipo_conexion = models.CharField(max_length=10, choices=TIPO_CONEXION_CHOICES, default='SERIAL')
    host_ip = models.CharField(
        max_length=50, null=True, blank=True,
        help_text="Dirección IP del equipo (solo para conexión TCP)."
    )
    puerto = models.CharField(
        max_length=20,
        help_text="Baudrate (ej: '9600') para Serial, o número de puerto TCP (ej: '5000')."
    )
    protocolo = models.CharField(max_length=10, choices=PROTOCOLO_CHOICES, default='HL7')
    activo = models.BooleanField(default=True)
    descripcion = models.TextField(blank=True, null=True)
    endpoint_destino = models.CharField(
        max_length=200,
        default='/api/v1/lecturas-serial/',
        help_text="Endpoint del backend al que el middleware debe enviar las tramas."
    )
    token_middleware = models.CharField(
        max_length=80,
        unique=True,
        null=True,
        blank=True,
        help_text="Token estático compartido con el middleware para autenticación de ingesta serial."
    )

    class Meta:
        db_table = 'configuracion_equipo_Lab'
        verbose_name = "Configuración de Equipo"
        verbose_name_plural = "Configuraciones de Equipos"

    def __str__(self):
        return f"{self.nombre} ({self.codigo_equipo})"


# ==========================================
# 2. Pacientes — FASE 2
# ==========================================

class Paciente(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tipo_documento = models.ForeignKey(
        TipoDocumentoPaciente,
        on_delete=models.RESTRICT,
        related_name='pacientes',
    )
    numero_documento = models.CharField(max_length=20)
    primer_nombre = models.CharField(max_length=50)
    segundo_nombre = models.CharField(max_length=50, blank=True, null=True)
    primer_apellido = models.CharField(max_length=50)
    segundo_apellido = models.CharField(max_length=50, blank=True, null=True)
    fecha_nacimiento = models.DateField()
    sexo_biologico = models.ForeignKey(
        SexoBiologico,
        on_delete=models.RESTRICT,
        related_name='pacientes',
    )
    telefono = models.CharField(max_length=15, blank=True, null=True)
    correo_electronico = models.EmailField(max_length=100, blank=True, null=True)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'paciente_Lab'
        constraints = [
            models.UniqueConstraint(
                fields=['tipo_documento', 'numero_documento'],
                name='unique_documento_paciente'
            )
        ]

    def __str__(self):
        return (
            f"{self.primer_nombre} {self.primer_apellido} "
            f"({self.tipo_documento.codigo} {self.numero_documento})"
        )


# ==========================================
# 3. Flujo Operativo — FASES 2, 3 y 5
# ==========================================

class OrdenLaboratorio(models.Model):
    """
    Orden médica de laboratorio. Vincula paciente y médico solicitante.
    Incluye campos RIPS obligatorios (Resolución 3374/2000) y datos de admisión.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    paciente = models.ForeignKey(Paciente, on_delete=models.RESTRICT, related_name='ordenes')
    # Médico solicitante — FASE 2
    medico = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ordenes_solicitadas',
        help_text="Médico que genera la orden clínica."
    )
    numero_orden = models.CharField(
        max_length=30, unique=True, blank=True,
        help_text="Auto-generado si no se proporciona. Formato: LAB-YYYYMMDD-NNNN"
    )
    fecha_orden = models.DateTimeField(auto_now_add=True)
    # Admisión en recepción — FASE 2
    fecha_admision = models.DateTimeField(
        null=True, blank=True,
        help_text="Fecha/hora en que el paciente fue admitido en recepción del laboratorio."
    )
    usuario_admite = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ordenes_admitidas',
        help_text="Auxiliar/recepcionista que gestionó la admisión."
    )
    observaciones_clinicas = models.TextField(blank=True, null=True)
    # Campos RIPS — Resolución 3374/2000 (FASES 2 & 7)
    codigo_cie10 = models.CharField(
        max_length=10, blank=True, null=True,
        help_text="Código diagnóstico CIE-10 del médico solicitante."
    )
    entidad_remitente = models.CharField(
        max_length=200, blank=True, null=True,
        help_text="Entidad o institución que remite al paciente."
    )
    convenio = models.CharField(
        max_length=100, blank=True, null=True,
        help_text="Convenio / aseguradora / EPS del paciente."
    )
    estado_general = models.ForeignKey(
        EstadoOrden,
        on_delete=models.RESTRICT,
        related_name='ordenes',
    )

    class Meta:
        db_table = 'orden_laboratorio_Lab'

    def __str__(self):
        return f"Orden {self.numero_orden} - {self.paciente}"


class MuestraFisica(models.Model):
    """
    Tubo o contenedor de muestra biológica. Incluye trazabilidad completa:
    estado, quién la recolectó y su condición visual (FASE 3).
    """
    CONDICION_CHOICES = [
        ('Normal', 'Normal'),
        ('Hemolizada', 'Hemolizada'),
        ('Lipemica', 'Lipémica'),
        ('Icterica', 'Ictérica'),
        ('Insuficiente', 'Volumen insuficiente'),
        ('Coagulada', 'Coagulada'),
        ('Contaminada', 'Contaminada'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    orden = models.ForeignKey(OrdenLaboratorio, on_delete=models.CASCADE, related_name='muestras')
    codigo_barras = models.CharField(max_length=50, unique=True)
    tipo_muestra = models.CharField(max_length=50, help_text="Ej: 'Sangre Total', 'Orina'")
    fecha_recoleccion = models.DateTimeField()
    # Trazabilidad pre-analítica — FASE 3
    estado_muestra = models.ForeignKey(
        EstadoMuestra,
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name='muestras',
        help_text="Estado actual de la muestra en el flujo pre-analítico."
    )
    usuario_recolecta = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='muestras_recolectadas',
        help_text="Auxiliar de enfermería / flebotomista que tomó la muestra."
    )
    condicion_muestra = models.CharField(
        max_length=20,
        choices=CONDICION_CHOICES,
        default='Normal',
        help_text="Condición visual de la muestra al analizarla."
    )
    motivo_rechazo = models.TextField(
        blank=True, null=True,
        help_text="Motivo de rechazo si la muestra fue rechazada por el bacteriólogo."
    )

    class Meta:
        db_table = 'muestra_fisica_Lab'

    def __str__(self):
        return f"{self.tipo_muestra} [{self.codigo_barras}]"


class ExamenSolicitado(models.Model):
    """
    Ítem individual de un examen en la orden. Registra la validación (o rechazo)
    por parte del bacteriólogo y quién la realizó (FASE 5).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    orden = models.ForeignKey(OrdenLaboratorio, on_delete=models.CASCADE, related_name='examenes_solicitados')
    cups = models.ForeignKey(CatalogoCups, on_delete=models.RESTRICT)
    muestra = models.ForeignKey(
        MuestraFisica, on_delete=models.SET_NULL, null=True, blank=True, related_name='examenes'
    )
    estado_examen = models.ForeignKey(
        EstadoExamen,
        on_delete=models.RESTRICT,
        related_name='examenes_solicitados',
    )
    # Validación post-analítica — FASE 5
    validado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='examenes_validados',
        help_text="Bacteriólogo que validó y firmó el resultado."
    )
    fecha_validacion = models.DateTimeField(
        null=True, blank=True,
        help_text="Fecha y hora en que el bacteriólogo validó el examen."
    )
    motivo_rechazo = models.TextField(
        blank=True, null=True,
        help_text="Motivo de rechazo. Se llena al rechazar el resultado."
    )

    class Meta:
        db_table = 'examen_solicitado_Lab'

    def __str__(self):
        return f"{self.cups.descripcion} - Orden {self.orden.numero_orden}"


# ==========================================
# 4. Interfaz Serial y Resultados — FASES 4 & 5
# ==========================================

class LecturaEquipoSerial(models.Model):
    """Trama cruda recibida desde el analizador vía middleware (FASE 4)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    equipo_origen = models.CharField(max_length=100, help_text="Ej: 'URIT-500C'")
    codigo_barras_leido = models.CharField(max_length=50, blank=True, null=True)
    fecha_recepcion = models.DateTimeField(auto_now_add=True)
    trama_cruda = models.TextField(help_text="Evidencia de la cadena original enviada por el equipo.")
    datos_json = models.JSONField(help_text="Datos parseados en estructura clave-valor.")
    procesado = models.BooleanField(
        default=False,
        help_text="True cuando los analitos ya fueron extraídos a ResultadoAnalito."
    )

    class Meta:
        db_table = 'lectura_equipo_serial_Lab'

    def __str__(self):
        return f"{self.equipo_origen} - {self.fecha_recepcion.strftime('%Y-%m-%d %H:%M')}"


class ResultadoAnalito(models.Model):
    """
    Valor de un analito. Incluye flag de anormalidad/criticidad calculado
    automáticamente y espacio para comentario del bacteriólogo (FASE 5).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    examen_solicitado = models.ForeignKey(ExamenSolicitado, on_delete=models.CASCADE, related_name='resultados')
    parametro = models.ForeignKey(ParametroExamen, on_delete=models.RESTRICT)
    lectura_serial = models.ForeignKey(LecturaEquipoSerial, on_delete=models.SET_NULL, null=True, blank=True)
    valor_resultado = models.CharField(max_length=100)
    es_anormal = models.BooleanField(default=False)
    es_critico = models.BooleanField(
        default=False,
        help_text="True si el valor supera los rangos de pánico definidos en ParametroExamen."
    )
    comentario_bacteriologo = models.TextField(
        blank=True, null=True,
        help_text="Observación clínica del bacteriólogo sobre este analito (FASE 5)."
    )
    fecha_procesamiento = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'resultado_analito_Lab'
        constraints = [
            models.UniqueConstraint(
                fields=['examen_solicitado', 'parametro'],
                name='unique_resultado_parametro_examen'
            )
        ]

    def __str__(self):
        return f"{self.parametro.nombre_parametro}: {self.valor_resultado}"


# ==========================================
# 5. Informes y Notificaciones — FASE 6
# ==========================================

class InformeResultados(models.Model):
    """
    PDF inmutable del informe de laboratorio. Se genera cuando la orden
    pasa a 'Finalizada' y todos sus exámenes están validados (FASE 6).
    El hash SHA-256 garantiza la inmutabilidad del documento.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    orden = models.OneToOneField(
        OrdenLaboratorio, on_delete=models.CASCADE, related_name='informe'
    )
    archivo_pdf = models.FileField(
        upload_to='informes/', null=True, blank=True,
        help_text="Archivo PDF del informe generado."
    )
    fecha_generacion = models.DateTimeField(auto_now_add=True)
    generado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='informes_generados',
    )
    hash_documento = models.CharField(
        max_length=64, blank=True, null=True,
        help_text="SHA-256 del contenido del PDF (garantía de inmutabilidad)."
    )

    class Meta:
        db_table = 'informe_resultados_Lab'
        verbose_name = "Informe de Resultados"
        verbose_name_plural = "Informes de Resultados"

    def __str__(self):
        return f"Informe {self.orden.numero_orden} — {self.fecha_generacion.strftime('%Y-%m-%d')}"


class Notificacion(models.Model):
    """
    Notificaciones internas del LIMS. Alerta al médico cuando el resultado
    está listo y al flebotomista/bacteriólogo en caso de rechazos (FASE 6).
    """
    TIPO_CHOICES = [
        ('resultado_listo', 'Resultado Listo'),
        ('muestra_rechazada', 'Muestra Rechazada'),
        ('examen_rechazado', 'Examen Rechazado'),
        ('alerta_critica', 'Alerta de Valor Crítico'),
        ('orden_finalizada', 'Orden Finalizada'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    destinatario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notificaciones',
    )
    orden = models.ForeignKey(
        OrdenLaboratorio,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notificaciones',
    )
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES)
    mensaje = models.TextField()
    leida = models.BooleanField(default=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_lectura = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'notificacion_Lab'
        ordering = ['-fecha_creacion']
        verbose_name = "Notificación"
        verbose_name_plural = "Notificaciones"

    def __str__(self):
        return f"[{self.tipo}] → {self.destinatario.username}"
