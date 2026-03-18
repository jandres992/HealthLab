import uuid
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
    """Sexo biológico del paciente."""
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


# ==========================================
# 1. Catálogos y Estándares (Normativa)
# ==========================================

class CatalogoCups(models.Model):
    codigo_cups = models.CharField(max_length=10, unique=True, help_text="Ej: '903895'")
    descripcion = models.CharField(max_length=255)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.codigo_cups} - {self.descripcion}"


class ParametroExamen(models.Model):
    cups = models.ForeignKey(CatalogoCups, on_delete=models.CASCADE, related_name='parametros')
    nombre_parametro = models.CharField(max_length=100, help_text="Ej: 'Leucocitos'")
    unidades_medida = models.CharField(max_length=20, blank=True, null=True, help_text="Ej: 'cel/uL'")
    rango_referencia_minimo = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    rango_referencia_maximo = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    rango_texto = models.CharField(max_length=100, blank=True, null=True, help_text="Para valores cualitativos (Ej: 'Negativo')")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['cups', 'nombre_parametro'], name='unique_parametro_por_cups')
        ]

    def __str__(self):
        return f"{self.cups.codigo_cups} | {self.nombre_parametro}"


# ==========================================
# 2. Pacientes (Datos Demográficos)
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
        constraints = [
            models.UniqueConstraint(fields=['tipo_documento', 'numero_documento'], name='unique_documento_paciente')
        ]

    def __str__(self):
        return f"{self.primer_nombre} {self.primer_apellido} ({self.tipo_documento.codigo} {self.numero_documento})"


# ==========================================
# 3. Flujo Operativo (Órdenes, Muestras y Exámenes)
# ==========================================

class OrdenLaboratorio(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    paciente = models.ForeignKey(Paciente, on_delete=models.RESTRICT, related_name='ordenes')
    numero_orden = models.CharField(max_length=20, unique=True)
    fecha_orden = models.DateTimeField(auto_now_add=True)
    observaciones_clinicas = models.TextField(blank=True, null=True)
    estado_general = models.ForeignKey(
        EstadoOrden,
        on_delete=models.RESTRICT,
        related_name='ordenes',
    )

    def __str__(self):
        return f"Orden {self.numero_orden} - {self.paciente}"


class MuestraFisica(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    orden = models.ForeignKey(OrdenLaboratorio, on_delete=models.CASCADE, related_name='muestras')
    codigo_barras = models.CharField(max_length=50, unique=True)
    tipo_muestra = models.CharField(max_length=50, help_text="Ej: 'Sangre Total', 'Orina'")
    fecha_recoleccion = models.DateTimeField()

    def __str__(self):
        return f"{self.tipo_muestra} [{self.codigo_barras}]"


class ExamenSolicitado(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    orden = models.ForeignKey(OrdenLaboratorio, on_delete=models.CASCADE, related_name='examenes_solicitados')
    cups = models.ForeignKey(CatalogoCups, on_delete=models.RESTRICT)
    muestra = models.ForeignKey(MuestraFisica, on_delete=models.SET_NULL, null=True, blank=True, related_name='examenes')
    estado_examen = models.ForeignKey(
        EstadoExamen,
        on_delete=models.RESTRICT,
        related_name='examenes_solicitados',
    )

    def __str__(self):
        return f"{self.cups.descripcion} - Orden {self.orden.numero_orden}"


# ==========================================
# 4. Interfaz Serial y Resultados
# ==========================================

class LecturaEquipoSerial(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    equipo_origen = models.CharField(max_length=100, help_text="Ej: 'URIT-500C'")
    codigo_barras_leido = models.CharField(max_length=50, blank=True, null=True)
    fecha_recepcion = models.DateTimeField(auto_now_add=True)
    trama_cruda = models.TextField(help_text="Evidencia de la cadena original")
    datos_json = models.JSONField(help_text="Datos parseados en estructura clave-valor")
    procesado = models.BooleanField(default=False, help_text="Indica si ya se extrajo hacia resultado_analito")

    def __str__(self):
        return f"{self.equipo_origen} - {self.fecha_recepcion.strftime('%Y-%m-%d %H:%M')}"


class ResultadoAnalito(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    examen_solicitado = models.ForeignKey(ExamenSolicitado, on_delete=models.CASCADE, related_name='resultados')
    parametro = models.ForeignKey(ParametroExamen, on_delete=models.RESTRICT)
    lectura_serial = models.ForeignKey(LecturaEquipoSerial, on_delete=models.SET_NULL, null=True, blank=True)
    valor_resultado = models.CharField(max_length=100)
    es_anormal = models.BooleanField(default=False)
    fecha_procesamiento = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['examen_solicitado', 'parametro'], name='unique_resultado_parametro_examen')
        ]

    def __str__(self):
        return f"{self.parametro.nombre_parametro}: {self.valor_resultado}"