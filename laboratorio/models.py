"""
Modelos del módulo laboratorio — HealthLab LIMS.
Cubre las fases 1-6 del flujo clínico: configuración, orden médica,
toma de muestras, análisis, validación post-analítica e informes.

Reglas de integridad aplicadas aquí (§9.6):
- Entidades clínicas con historial completo (RNF-34.1) y versión optimista (RNF-31.2).
- Estados finales definidos en el catálogo (RN-10.1), no en el código.
- Claves foráneas PROTECT/RESTRICT: nada clínico se borra en cascada por accidente.
- El resultado copia el rango con el que se interpretó (RF-53).
"""
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from simple_history.models import HistoricalRecords


class VersionadoMixin(models.Model):
    """Control de versión optimista: `version` sube en cada guardado (RNF-31.2)."""
    version = models.PositiveIntegerField(default=1, editable=False)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            self.version = (self.version or 0) + 1
            campos = kwargs.get('update_fields')
            if campos is not None and 'version' not in campos:
                kwargs['update_fields'] = list(campos) + ['version']
        super().save(*args, **kwargs)


# ==========================================
# 0. Catálogos de dominio
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
    codigo = models.CharField(max_length=1, unique=True)
    descripcion = models.CharField(max_length=30)

    class Meta:
        db_table = 'sexo_biologico_Lab'

    def __str__(self):
        return self.descripcion


class EstadoOrden(models.Model):
    nombre = models.CharField(max_length=30, unique=True)
    descripcion = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        db_table = 'estado_orden_Lab'

    def __str__(self):
        return self.nombre


class EstadoExamen(models.Model):
    """
    Estados de un examen. `es_final` (RN-10.1) decide si el examen cuenta como
    cerrado para finalizar la orden: Validado y Anulado son finales; Repetir NO.
    """
    nombre = models.CharField(max_length=30, unique=True)
    descripcion = models.CharField(max_length=200, blank=True, null=True)
    es_final = models.BooleanField(default=False)

    class Meta:
        db_table = 'estado_examen_Lab'

    def __str__(self):
        return self.nombre


class EstadoMuestra(models.Model):
    nombre = models.CharField(max_length=40, unique=True)
    descripcion = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        db_table = 'estado_muestra_Lab'

    def __str__(self):
        return self.nombre


# ==========================================
# 1. Catálogos y estándares — FASE 1
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


class ParametroExamen(VersionadoMixin):
    """
    Valores de referencia de cada analito para un CUPS, segmentados por sexo y
    edad. Con historial: cada cambio de rango queda registrado y los resultados
    conservan la copia del rango con que se interpretaron (RF-53).
    """
    cups = models.ForeignKey(CatalogoCups, on_delete=models.PROTECT, related_name='parametros')
    nombre_parametro = models.CharField(max_length=100, help_text="Ej: 'Leucocitos'")
    unidades_medida = models.CharField(max_length=20, blank=True, null=True, help_text="Ej: 'cel/uL'")
    rango_referencia_minimo = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    rango_referencia_maximo = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    rango_texto = models.CharField(max_length=100, blank=True, null=True,
                                   help_text="Para valores cualitativos (Ej: 'Negativo')")
    rango_panico_minimo = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True,
                                              help_text="Valor crítico inferior.")
    rango_panico_maximo = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True,
                                              help_text="Valor crítico superior.")
    sexo_aplica = models.ForeignKey(SexoBiologico, on_delete=models.PROTECT, null=True, blank=True,
                                    related_name='parametros',
                                    help_text="Deje en blanco si el rango aplica para ambos sexos.")
    edad_minima_anios = models.PositiveSmallIntegerField(null=True, blank=True)
    edad_maxima_anios = models.PositiveSmallIntegerField(null=True, blank=True)
    metodo = models.CharField(max_length=100, blank=True, null=True, help_text="Método analítico (aparece en el informe, RF-63).")
    codigo_loinc = models.CharField(max_length=20, blank=True, null=True)
    unidad_ucum = models.CharField(max_length=30, blank=True, null=True)
    activo = models.BooleanField(default=True)
    # Vigencia (RF-53): un cambio de rango cierra esta versión y crea otra; nunca se edita la anterior.
    vigente_desde = models.DateField(default=timezone.localdate)
    vigente_hasta = models.DateField(null=True, blank=True)
    version_anterior = models.ForeignKey('self', on_delete=models.PROTECT, null=True, blank=True,
                                         related_name='versiones_posteriores')
    history = HistoricalRecords()

    class Meta:
        db_table = 'parametro_examen_Lab'

    @property
    def vigente(self):
        return self.activo and self.vigente_hasta is None

    def __str__(self):
        sexo = f" [{self.sexo_aplica.codigo}]" if self.sexo_aplica else ""
        edad = ""
        if self.edad_minima_anios is not None or self.edad_maxima_anios is not None:
            edad = f" {self.edad_minima_anios or 0}-{self.edad_maxima_anios or 'inf'}a"
        return f"{self.cups.codigo_cups} | {self.nombre_parametro}{sexo}{edad}"


class ConfiguracionEquipo(models.Model):
    """Analizadores conectados vía middleware (serial o TCP)."""
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
    nombre = models.CharField(max_length=100)
    codigo_equipo = models.CharField(max_length=30, unique=True)
    tipo_conexion = models.CharField(max_length=10, choices=TIPO_CONEXION_CHOICES, default='SERIAL')
    host_ip = models.CharField(max_length=50, null=True, blank=True)
    puerto = models.CharField(max_length=20, help_text="Baudrate para Serial o puerto TCP.")
    protocolo = models.CharField(max_length=10, choices=PROTOCOLO_CHOICES, default='HL7')
    activo = models.BooleanField(default=True)
    descripcion = models.TextField(blank=True, null=True)
    endpoint_destino = models.CharField(max_length=200, default='/api/v1/lecturas-serial/')
    token_middleware = models.CharField(max_length=80, unique=True, null=True, blank=True)
    # Gestión del equipo (RF-51)
    ESTADO_CHOICES = [
        ('operativo', 'Operativo'),
        ('mantenimiento', 'En mantenimiento'),
        ('fuera_servicio', 'Fuera de servicio'),
    ]
    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='operativo')
    calibracion_vigente_hasta = models.DateField(null=True, blank=True)
    ultimo_latido = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'configuracion_equipo_Lab'
        verbose_name = "Configuración de Equipo"
        verbose_name_plural = "Configuraciones de Equipos"

    def __str__(self):
        return f"{self.nombre} ({self.codigo_equipo})"

    def motivo_no_operativo(self, hoy=None):
        """None si puede procesar; si no, el motivo (RF-51)."""
        from django.utils import timezone  # noqa: PLC0415
        hoy = hoy or timezone.localdate()
        if not self.activo:
            return 'El equipo está inactivo.'
        if self.estado != 'operativo':
            return f"El equipo está en estado '{self.get_estado_display()}'."
        if self.calibracion_vigente_hasta and self.calibracion_vigente_hasta < hoy:
            return f'La calibración del equipo venció el {self.calibracion_vigente_hasta:%d/%m/%Y}.'
        return None


class CalibracionEquipo(models.Model):
    """Registro de calibraciones (RF-51)."""
    equipo = models.ForeignKey(ConfiguracionEquipo, on_delete=models.PROTECT, related_name='calibraciones')
    fecha = models.DateField()
    vigente_hasta = models.DateField()
    resultado = models.CharField(max_length=20, choices=[('conforme', 'Conforme'), ('no_conforme', 'No conforme')], default='conforme')
    realizada_por = models.CharField(max_length=120, help_text="Técnico o empresa que calibró.")
    certificado = models.CharField(max_length=120, blank=True, null=True)
    observacion = models.TextField(blank=True, null=True)
    registrada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                       related_name='calibraciones_registradas')
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'calibracion_equipo_Lab'
        ordering = ['-fecha']


class MantenimientoEquipo(models.Model):
    """Mantenimientos preventivos y correctivos (RF-51)."""
    TIPO_CHOICES = [('preventivo', 'Preventivo'), ('correctivo', 'Correctivo')]
    equipo = models.ForeignKey(ConfiguracionEquipo, on_delete=models.PROTECT, related_name='mantenimientos')
    tipo = models.CharField(max_length=12, choices=TIPO_CHOICES)
    fecha = models.DateField()
    descripcion = models.TextField()
    realizado_por = models.CharField(max_length=120)
    proximo = models.DateField(null=True, blank=True, help_text="Fecha del próximo mantenimiento preventivo.")
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                       related_name='mantenimientos_registrados')
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'mantenimiento_equipo_Lab'
        ordering = ['-fecha']


class LoteReactivo(models.Model):
    """Lotes de reactivo por equipo y analito (RF-52). No se procesa con un lote vencido."""
    equipo = models.ForeignKey(ConfiguracionEquipo, on_delete=models.PROTECT, null=True, blank=True, related_name='lotes_reactivo')
    nombre_parametro = models.CharField(max_length=100, blank=True, default='', help_text="Vacío = aplica a todos los analitos del equipo.")
    nombre = models.CharField(max_length=120)
    lote = models.CharField(max_length=60)
    fecha_vencimiento = models.DateField()
    fecha_apertura = models.DateField(null=True, blank=True)
    activo = models.BooleanField(default=True)
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                       related_name='lotes_registrados')
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'lote_reactivo_Lab'
        indexes = [models.Index(fields=['equipo', 'nombre_parametro', 'activo'])]

    def __str__(self):
        return f"{self.nombre} lote {self.lote}"

    def vencido(self, hoy=None):
        from django.utils import timezone  # noqa: PLC0415
        return self.fecha_vencimiento < (hoy or timezone.localdate())


# ==========================================
# 1c. Control de calidad interno — RF-50
# ==========================================

class LoteControl(models.Model):
    """Material de control con media y desviación estándar objetivo por analito y nivel."""
    equipo = models.ForeignKey(ConfiguracionEquipo, on_delete=models.PROTECT, related_name='lotes_control')
    nombre_parametro = models.CharField(max_length=100)
    nivel = models.PositiveSmallIntegerField(default=1, help_text="1 = normal, 2 = patológico, 3 = alto")
    lote = models.CharField(max_length=60)
    fecha_vencimiento = models.DateField()
    media_objetivo = models.DecimalField(max_digits=12, decimal_places=4)
    desviacion_objetivo = models.DecimalField(max_digits=12, decimal_places=4)
    unidades = models.CharField(max_length=20, blank=True, null=True)
    activo = models.BooleanField(default=True)
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                       related_name='lotes_control_registrados')
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'lote_control_Lab'
        indexes = [models.Index(fields=['equipo', 'nombre_parametro', 'activo'])]

    def __str__(self):
        return f"{self.nombre_parametro} N{self.nivel} lote {self.lote} ({self.equipo.codigo_equipo})"


class CorridaCCI(models.Model):
    """Una corrida de control: valor, z-score y evaluación por reglas de Westgard."""
    RESULTADO_CHOICES = [('aceptada', 'Aceptada'), ('advertencia', 'Advertencia'), ('rechazada', 'Rechazada')]
    lote_control = models.ForeignKey(LoteControl, on_delete=models.PROTECT, related_name='corridas')
    valor = models.DecimalField(max_digits=12, decimal_places=4)
    z_score = models.DecimalField(max_digits=8, decimal_places=3)
    resultado = models.CharField(max_length=12, choices=RESULTADO_CHOICES)
    reglas_violadas = models.JSONField(default=list, blank=True)
    fecha = models.DateTimeField(db_index=True)
    registrada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                       related_name='corridas_cci')
    lectura = models.ForeignKey('LecturaEquipoSerial', on_delete=models.PROTECT, null=True, blank=True)
    accion_correctiva = models.TextField(blank=True, null=True, help_text="Documentada por el bacteriólogo; libera un rechazo.")
    accion_correctiva_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                              related_name='acciones_correctivas_cci')
    fecha_accion_correctiva = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'corrida_cci_Lab'
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.lote_control} {self.fecha:%Y-%m-%d %H:%M} z={self.z_score} {self.resultado}"


class PoliticaCCI(models.Model):
    """Modo de la política de CCI por equipo y analito (RF-50.1). Por defecto: informativo."""
    MODO_CHOICES = [('informativo', 'Informativo'), ('advertencia', 'Advertencia'), ('bloqueante', 'Bloqueante')]
    equipo = models.ForeignKey(ConfiguracionEquipo, on_delete=models.PROTECT, related_name='politicas_cci')
    nombre_parametro = models.CharField(max_length=100)
    modo = models.CharField(max_length=12, choices=MODO_CHOICES, default='informativo')
    actualizada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                        related_name='politicas_cci_actualizadas')
    actualizada = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    class Meta:
        db_table = 'politica_cci_Lab'
        constraints = [models.UniqueConstraint(fields=['equipo', 'nombre_parametro'], name='unique_politica_cci_equipo_parametro')]

    def __str__(self):
        return f"{self.equipo.codigo_equipo} / {self.nombre_parametro}: {self.modo}"


# ==========================================
# 2. Pacientes — FASE 2
# ==========================================

REGIMEN_CHOICES = [
    ('Contributivo', 'Contributivo'),
    ('Subsidiado', 'Subsidiado'),
    ('Vinculado', 'Vinculado'),
    ('Particular', 'Particular'),
    ('Otro', 'Otro'),
]


class Paciente(VersionadoMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tipo_documento = models.ForeignKey(TipoDocumentoPaciente, on_delete=models.PROTECT, related_name='pacientes')
    numero_documento = models.CharField(max_length=20)
    primer_nombre = models.CharField(max_length=50)
    segundo_nombre = models.CharField(max_length=50, blank=True, null=True)
    primer_apellido = models.CharField(max_length=50)
    segundo_apellido = models.CharField(max_length=50, blank=True, null=True)
    fecha_nacimiento = models.DateField()
    sexo_biologico = models.ForeignKey(SexoBiologico, on_delete=models.PROTECT, related_name='pacientes')
    telefono = models.CharField(max_length=15, blank=True, null=True)
    correo_electronico = models.EmailField(max_length=100, blank=True, null=True)
    municipio_residencia = models.ForeignKey('usuarios.Municipio', on_delete=models.PROTECT, null=True, blank=True,
                                             related_name='pacientes')
    departamento_residencia = models.ForeignKey('usuarios.Departamento', on_delete=models.PROTECT, null=True,
                                                blank=True, related_name='pacientes')
    regimen_salud = models.CharField(max_length=20, choices=REGIMEN_CHOICES, default='Particular')
    consentimiento_habeas_data = models.BooleanField(default=False)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    class Meta:
        db_table = 'paciente_Lab'
        constraints = [
            models.UniqueConstraint(fields=['tipo_documento', 'numero_documento'], name='unique_documento_paciente'),
        ]

    def __str__(self):
        return f"{self.primer_nombre} {self.primer_apellido} ({self.tipo_documento.codigo} {self.numero_documento})"

    @property
    def nombre_completo(self):
        return ' '.join(p for p in (self.primer_nombre, self.segundo_nombre, self.primer_apellido, self.segundo_apellido) if p)


# ==========================================
# 3. Flujo operativo — FASES 2, 3 y 5
# ==========================================

FINALIDAD_CHOICES = [
    ('Atencion Parto', 'Atención Parto'),
    ('Atencion Recien Nacido', 'Atención Recién Nacido'),
    ('Atencion Planificacion Familiar', 'Planificación Familiar'),
    ('Deteccion Alteraciones Crecimiento', 'Crecimiento y Desarrollo'),
    ('Deteccion Alteraciones Joven', 'Detección Joven'),
    ('Deteccion Alteraciones Embarazo', 'Detección Embarazo'),
    ('Deteccion Alteraciones Adulto', 'Detección Adulto'),
    ('Deteccion Alteraciones Agudeza Visual', 'Agudeza Visual'),
    ('Deteccion Enfermedad Profesional', 'Enf. Profesional'),
    ('No Aplica', 'No Aplica'),
]

CAUSA_EXTERNA_CHOICES = [
    ('Accidente de trabajo', 'Accidente de trabajo'),
    ('Accidente de transito', 'Accidente de tránsito'),
    ('Accidente rabico', 'Accidente rábico'),
    ('Accidente ofidico', 'Accidente ofídico'),
    ('Otro tipo de accidente', 'Otro tipo de accidente'),
    ('Evento catastrofico', 'Evento catastrófico'),
    ('Lesion por agresion', 'Lesión por agresión'),
    ('Lesion auto infligida', 'Lesión auto infligida'),
    ('Sospecha maltrato fisico', 'Sospecha maltrato físico'),
    ('Sospecha abuso sexual', 'Sospecha abuso sexual'),
    ('Sospecha violencia sexual', 'Sospecha violencia sexual'),
    ('Sospecha maltrato emocional', 'Sospecha maltrato emocional'),
    ('Enfermedad general', 'Enfermedad general'),
    ('Enfermedad profesional', 'Enfermedad profesional'),
    ('Otra', 'Otra'),
]

TIPO_DIAGNOSTICO_CHOICES = [
    ('Impresion diagnostica', 'Impresión diagnóstica'),
    ('Confirmado nuevo', 'Confirmado nuevo'),
    ('Confirmado repetido', 'Confirmado repetido'),
]


class SecuenciaOrden(models.Model):
    """Contador diario para numerar órdenes sin colisiones (RNF-31.1). Se bloquea por fila."""
    fecha = models.DateField(unique=True)
    ultimo = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'secuencia_orden_Lab'


class OrdenLaboratorio(VersionadoMixin):
    """Orden médica. Vincula paciente y médico; campos RIPS (Res. 3374/2000)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    paciente = models.ForeignKey(Paciente, on_delete=models.PROTECT, related_name='ordenes')
    medico = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                               related_name='ordenes_solicitadas')
    numero_orden = models.CharField(max_length=30, unique=True, blank=True)
    fecha_orden = models.DateTimeField(auto_now_add=True)
    fecha_admision = models.DateTimeField(null=True, blank=True)
    usuario_admite = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                       related_name='ordenes_admitidas')
    observaciones_clinicas = models.TextField(blank=True, null=True)
    codigo_cie10 = models.CharField(max_length=10, blank=True, null=True)
    entidad_remitente = models.CharField(max_length=200, blank=True, null=True)
    convenio = models.CharField(max_length=100, blank=True, null=True)
    finalidad_consulta = models.CharField(max_length=40, choices=FINALIDAD_CHOICES, default='No Aplica')
    causa_externa = models.CharField(max_length=40, choices=CAUSA_EXTERNA_CHOICES, default='Enfermedad general')
    tipo_diagnostico = models.CharField(max_length=30, choices=TIPO_DIAGNOSTICO_CHOICES, default='Impresion diagnostica')
    estado_general = models.ForeignKey(EstadoOrden, on_delete=models.PROTECT, related_name='ordenes')
    # Cierre (FASE 6)
    fecha_finalizacion = models.DateTimeField(null=True, blank=True)
    finalizada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                       related_name='ordenes_finalizadas')
    informe_pendiente = models.BooleanField(default=False,
                                            help_text="True mientras el informe final se genera (RNF-40).")
    history = HistoricalRecords()

    class Meta:
        db_table = 'orden_laboratorio_Lab'
        indexes = [
            models.Index(fields=['-fecha_orden']),
            models.Index(fields=['estado_general', '-fecha_orden']),
        ]

    def __str__(self):
        return f"Orden {self.numero_orden} - {self.paciente}"


class MuestraFisica(VersionadoMixin):
    """Tubo o contenedor de muestra biológica (FASE 3)."""
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
    orden = models.ForeignKey(OrdenLaboratorio, on_delete=models.PROTECT, related_name='muestras')
    codigo_barras = models.CharField(max_length=50, unique=True)
    tipo_muestra = models.CharField(max_length=50, help_text="Ej: 'Sangre Total', 'Orina'")
    fecha_recoleccion = models.DateTimeField()
    estado_muestra = models.ForeignKey(EstadoMuestra, on_delete=models.PROTECT, null=True, blank=True,
                                       related_name='muestras')
    usuario_recolecta = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                          related_name='muestras_recolectadas')
    condicion_muestra = models.CharField(max_length=20, choices=CONDICION_CHOICES, default='Normal')
    motivo_rechazo = models.TextField(blank=True, null=True)
    # Trazabilidad de recepción y rechazo
    fecha_recepcion = models.DateTimeField(null=True, blank=True)
    recibida_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                     related_name='muestras_recibidas')
    fecha_rechazo = models.DateTimeField(null=True, blank=True)
    rechazada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                      related_name='muestras_rechazadas')
    # Cadena de custodia (RF-57)
    muestra_madre = models.ForeignKey('self', on_delete=models.PROTECT, null=True, blank=True, related_name='alicuotas',
                                      help_text="Muestra de la que se obtuvo esta alícuota.")
    ubicacion_actual = models.CharField(max_length=120, blank=True, default='')
    fecha_declarada_dispositivo = models.DateTimeField(null=True, blank=True,
                                                       help_text="Hora de toma declarada por el dispositivo (operación offline, RN-27).")
    history = HistoricalRecords()

    class Meta:
        db_table = 'muestra_fisica_Lab'
        indexes = [models.Index(fields=['-fecha_recoleccion'])]

    def __str__(self):
        return f"{self.tipo_muestra} [{self.codigo_barras}]"


class EventoMuestra(models.Model):
    """
    Cadena de custodia (RF-57, RNF-37): una fila inmutable por cada hecho de la
    muestra, con usuario, rol, hora del servidor y ubicación. Nunca se edita ni borra.
    """
    TIPO_CHOICES = [
        ('toma', 'Toma'),
        ('etiqueta', 'Impresión de etiqueta'),
        ('transporte', 'Transporte'),
        ('recepcion', 'Recepción en laboratorio'),
        ('alicuota', 'Alícuota'),
        ('almacenamiento', 'Almacenamiento'),
        ('analisis', 'Análisis'),
        ('rechazo', 'Rechazo'),
        ('descarte', 'Descarte'),
        ('nota', 'Nota'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    muestra = models.ForeignKey(MuestraFisica, on_delete=models.PROTECT, related_name='eventos')
    tipo = models.CharField(max_length=15, choices=TIPO_CHOICES)
    fecha = models.DateTimeField(db_index=True, help_text="Hora del servidor (RN-27).")
    fecha_declarada_dispositivo = models.DateTimeField(null=True, blank=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                related_name='eventos_muestra')
    rol = models.CharField(max_length=30, blank=True, default='')
    ubicacion = models.CharField(max_length=120, blank=True, default='')
    temperatura = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    observacion = models.TextField(blank=True, default='')
    muestra_relacionada = models.ForeignKey(MuestraFisica, on_delete=models.PROTECT, null=True, blank=True,
                                            related_name='eventos_relacionados',
                                            help_text="Alícuota creada o muestra madre, según el evento.")

    class Meta:
        db_table = 'evento_muestra_Lab'
        ordering = ['fecha']

    def __str__(self):
        return f"{self.muestra.codigo_barras} {self.tipo} {self.fecha:%Y-%m-%d %H:%M}"


class ExamenSolicitado(VersionadoMixin):
    """Examen de una orden. Su validación es la firma del bacteriólogo (RF-34.3)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    orden = models.ForeignKey(OrdenLaboratorio, on_delete=models.PROTECT, related_name='examenes_solicitados')
    cups = models.ForeignKey(CatalogoCups, on_delete=models.PROTECT)
    muestra = models.ForeignKey(MuestraFisica, on_delete=models.PROTECT, null=True, blank=True, related_name='examenes')
    estado_examen = models.ForeignKey(EstadoExamen, on_delete=models.PROTECT, related_name='examenes_solicitados')
    # Validación (FASE 5)
    validado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                     related_name='examenes_validados')
    fecha_validacion = models.DateTimeField(null=True, blank=True)
    # Rechazo
    motivo_rechazo = models.TextField(blank=True, null=True)
    rechazado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                      related_name='examenes_rechazados')
    fecha_rechazo = models.DateTimeField(null=True, blank=True)
    # Política de CCI al validar (RF-50.1.2): estado del CCI y justificación si el modo era Advertencia
    estado_cci_validacion = models.CharField(max_length=20, blank=True, default='')
    justificacion_cci = models.TextField(blank=True, null=True)
    # Anulación (RF-35.2)
    motivo_anulacion = models.TextField(blank=True, null=True)
    anulado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                    related_name='examenes_anulados')
    fecha_anulacion = models.DateTimeField(null=True, blank=True)
    history = HistoricalRecords()

    class Meta:
        db_table = 'examen_solicitado_Lab'
        indexes = [models.Index(fields=['estado_examen'])]

    def __str__(self):
        return f"{self.cups.descripcion} - Orden {self.orden.numero_orden}"


# ==========================================
# 4. Interfaz con analizadores y resultados — FASES 4 & 5
# ==========================================

class LecturaEquipoSerial(models.Model):
    """Trama cruda recibida desde el analizador vía middleware (FASE 4)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    equipo_origen = models.CharField(max_length=100, help_text="Ej: 'URIT-500C'")
    codigo_barras_leido = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    fecha_recepcion = models.DateTimeField(auto_now_add=True)
    trama_cruda = models.TextField(help_text="Evidencia de la cadena original enviada por el equipo.")
    datos_json = models.JSONField(help_text="Datos parseados en estructura clave-valor.")
    procesado = models.BooleanField(default=False)
    procesada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                      related_name='lecturas_procesadas')
    fecha_procesamiento = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'lectura_equipo_serial_Lab'
        indexes = [models.Index(fields=['-fecha_recepcion'])]

    def __str__(self):
        return f"{self.equipo_origen} - {self.fecha_recepcion:%Y-%m-%d %H:%M}"


class ResultadoAnalito(VersionadoMixin):
    """
    Valor de un analito. Guarda la copia del rango, unidades y versión del
    parámetro con que se interpretó (RF-53). Inmutable una vez validado el
    examen (RN-22): las correcciones crean una versión nueva en el historial.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    examen_solicitado = models.ForeignKey(ExamenSolicitado, on_delete=models.PROTECT, related_name='resultados')
    parametro = models.ForeignKey(ParametroExamen, on_delete=models.PROTECT)
    muestra = models.ForeignKey(MuestraFisica, on_delete=models.PROTECT, null=True, blank=True,
                                related_name='resultados')
    lectura_serial = models.ForeignKey(LecturaEquipoSerial, on_delete=models.PROTECT, null=True, blank=True)
    valor_resultado = models.CharField(max_length=100)
    valor_numerico = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    es_anormal = models.BooleanField(default=False)
    es_critico = models.BooleanField(default=False)
    # Escalado de críticos sin acuse (RF-54.1)
    critico_escalado = models.BooleanField(default=False)
    fecha_escalado = models.DateTimeField(null=True, blank=True)
    # Copia del rango aplicado (RF-53)
    unidades_aplicadas = models.CharField(max_length=20, blank=True, null=True)
    rango_min_aplicado = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    rango_max_aplicado = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    rango_texto_aplicado = models.CharField(max_length=100, blank=True, null=True)
    parametro_version = models.PositiveIntegerField(null=True, blank=True)
    metodo_aplicado = models.CharField(max_length=100, blank=True, null=True)
    # Trazabilidad analítica (RF-51, RF-52)
    equipo = models.ForeignKey(ConfiguracionEquipo, on_delete=models.PROTECT, null=True, blank=True, related_name='resultados')
    lote_reactivo = models.ForeignKey(LoteReactivo, on_delete=models.PROTECT, null=True, blank=True, related_name='resultados')
    lote_control = models.ForeignKey(LoteControl, on_delete=models.PROTECT, null=True, blank=True, related_name='resultados')
    comentario_bacteriologo = models.TextField(blank=True, null=True)
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                       related_name='resultados_registrados')
    fecha_procesamiento = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    class Meta:
        db_table = 'resultado_analito_Lab'
        constraints = [
            models.UniqueConstraint(fields=['examen_solicitado', 'parametro'], name='unique_resultado_parametro_examen'),
        ]

    def __str__(self):
        return f"{self.parametro.nombre_parametro}: {self.valor_resultado}"


# ==========================================
# 5. Informes y notificaciones — FASE 6
# ==========================================

class InformeResultados(models.Model):
    """
    PDF inmutable. Una orden puede tener varios informes (parcial, final,
    corregido); cada uno encadena el hash del anterior (RNF-34.2). Solo un
    informe final vigente por orden.
    """
    TIPO_CHOICES = [
        ('preliminar', 'Preliminar (sin validez legal)'),
        ('parcial', 'Parcial'),
        ('final', 'Final'),
        ('corregido', 'Corregido'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    orden = models.ForeignKey(OrdenLaboratorio, on_delete=models.PROTECT, related_name='informes')
    tipo = models.CharField(max_length=12, choices=TIPO_CHOICES, default='final')
    vigente = models.BooleanField(default=True)
    archivo_pdf = models.FileField(upload_to='informes/', null=True, blank=True)
    fecha_generacion = models.DateTimeField(auto_now_add=True)
    generado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                     related_name='informes_generados')
    hash_documento = models.CharField(max_length=64, blank=True, null=True,
                                      help_text="SHA-256 del PDF encadenado con el hash del informe anterior.")
    hash_anterior = models.CharField(max_length=64, blank=True, null=True)
    motivo = models.TextField(blank=True, null=True, help_text="Motivo (informes corregidos).")

    class Meta:
        db_table = 'informe_resultados_Lab'
        verbose_name = "Informe de Resultados"
        verbose_name_plural = "Informes de Resultados"
        ordering = ['-fecha_generacion']
        constraints = [
            models.UniqueConstraint(
                fields=['orden'], condition=models.Q(tipo='final', vigente=True),
                name='unique_informe_final_vigente_por_orden',
            ),
        ]

    def __str__(self):
        return f"Informe {self.tipo} {self.orden.numero_orden} — {self.fecha_generacion:%Y-%m-%d}"


class AcuseValorCritico(models.Model):
    """
    Comunicación de un valor crítico con acuse (RF-54): a quién, por qué medio,
    cuándo y confirmación por repetición (read-back). Sin acuse la orden no cierra (RN-25).
    """
    MEDIO_CHOICES = [('telefono', 'Teléfono'), ('presencial', 'Presencial'), ('sistema', 'Sistema'), ('otro', 'Otro')]
    resultado = models.OneToOneField(ResultadoAnalito, on_delete=models.PROTECT, related_name='acuse')
    comunicado_a = models.CharField(max_length=150, help_text="Nombre del médico o enfermera que recibió el valor.")
    medio = models.CharField(max_length=12, choices=MEDIO_CHOICES)
    read_back = models.BooleanField(default=False, help_text="El receptor repitió el valor (confirmación).")
    fecha_comunicacion = models.DateTimeField(help_text="Hora del servidor al registrar el acuse.")
    fecha_declarada = models.DateTimeField(null=True, blank=True, help_text="Hora en que se hizo la llamada, si fue antes.")
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='acuses_registrados')
    observacion = models.TextField(blank=True, default='')
    escalado = models.BooleanField(default=False)
    fecha_escalado = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'acuse_valor_critico_Lab'

    def __str__(self):
        return f"Acuse {self.resultado_id} → {self.comunicado_a}"


class ClaveIdempotencia(models.Model):
    """Reserva de `Idempotency-Key` con la respuesta original (RNF-33). Se purga a los 7 días."""
    huella = models.CharField(max_length=64, unique=True)
    clave = models.CharField(max_length=128)
    ruta = models.CharField(max_length=200)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='claves_idempotencia')
    equipo_origen = models.CharField(max_length=100, blank=True, default='')
    codigo_http = models.PositiveSmallIntegerField(null=True, blank=True)
    respuesta = models.JSONField(null=True, blank=True)
    completada = models.BooleanField(default=False)
    creada = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'clave_idempotencia_Lab'

    def __str__(self):
        return f'{self.ruta} {self.clave}'


class Notificacion(models.Model):
    TIPO_CHOICES = [
        ('resultado_listo', 'Resultado Listo'),
        ('resultados_parciales', 'Resultados Parciales'),
        ('muestra_rechazada', 'Muestra Rechazada'),
        ('examen_rechazado', 'Examen Rechazado'),
        ('examen_anulado', 'Examen Anulado'),
        ('alerta_critica', 'Alerta de Valor Crítico'),
        ('orden_finalizada', 'Orden Finalizada'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    destinatario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notificaciones')
    orden = models.ForeignKey(OrdenLaboratorio, on_delete=models.CASCADE, null=True, blank=True,
                              related_name='notificaciones')
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES)
    mensaje = models.TextField()
    leida = models.BooleanField(default=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_lectura = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'notificacion_Lab'
        ordering = ['-fecha_creacion']
        indexes = [models.Index(fields=['destinatario', 'leida'])]
        verbose_name = "Notificación"
        verbose_name_plural = "Notificaciones"

    def __str__(self):
        return f"[{self.tipo}] → {self.destinatario.username}"
