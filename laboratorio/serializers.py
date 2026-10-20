"""
Serializadores del módulo laboratorio.

- Campos explícitos en toda entidad clínica (RNF-38).
- Los estados son de solo lectura: solo cambian por acciones de negocio (RN-23).
- Los serializadores de escritura (`*CrearSerializer`) validan formato; las
  reglas clínicas viven en services/ y domain/.
"""
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import (
    CatalogoCups, ConfiguracionEquipo, EstadoExamen, EstadoMuestra, EstadoOrden,
    ExamenSolicitado, InformeResultados, LecturaEquipoSerial, MuestraFisica,
    Notificacion, OrdenLaboratorio, Paciente, ParametroExamen, ResultadoAnalito,
    SexoBiologico, TipoDocumentoPaciente,
)


# ─────────────────────────────────────────────────────────────────────────────
# Catálogos
# ─────────────────────────────────────────────────────────────────────────────

class TipoDocumentoPacienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = TipoDocumentoPaciente
        fields = ['id', 'codigo', 'descripcion', 'activo']


class SexoBiologicoSerializer(serializers.ModelSerializer):
    class Meta:
        model = SexoBiologico
        fields = ['id', 'codigo', 'descripcion']


class EstadoOrdenSerializer(serializers.ModelSerializer):
    class Meta:
        model = EstadoOrden
        fields = ['id', 'nombre', 'descripcion']


class EstadoExamenSerializer(serializers.ModelSerializer):
    class Meta:
        model = EstadoExamen
        fields = ['id', 'nombre', 'descripcion', 'es_final']


class EstadoMuestraSerializer(serializers.ModelSerializer):
    class Meta:
        model = EstadoMuestra
        fields = ['id', 'nombre', 'descripcion']


class CatalogoCupsSerializer(serializers.ModelSerializer):
    class Meta:
        model = CatalogoCups
        fields = ['id', 'codigo_cups', 'descripcion', 'activo']


class ParametroExamenSerializer(serializers.ModelSerializer):
    sexo_aplica = serializers.SlugRelatedField(slug_field='codigo', queryset=SexoBiologico.objects.all(),
                                               required=False, allow_null=True)
    cups_codigo = serializers.ReadOnlyField(source='cups.codigo_cups')

    class Meta:
        model = ParametroExamen
        fields = ['id', 'cups', 'cups_codigo', 'nombre_parametro', 'unidades_medida',
                  'rango_referencia_minimo', 'rango_referencia_maximo', 'rango_texto',
                  'rango_panico_minimo', 'rango_panico_maximo',
                  'sexo_aplica', 'edad_minima_anios', 'edad_maxima_anios', 'metodo', 'codigo_loinc', 'unidad_ucum',
                  'activo', 'vigente_desde', 'vigente_hasta', 'version_anterior', 'version']
        read_only_fields = ['id', 'version', 'vigente_desde', 'vigente_hasta', 'version_anterior']


class ConfiguracionEquipoSerializer(serializers.ModelSerializer):
    """El token nunca se devuelve: solo lo entrega `regenerar-token` (RF-13.3)."""
    class Meta:
        model = ConfiguracionEquipo
        fields = ['id', 'nombre', 'codigo_equipo', 'tipo_conexion', 'host_ip', 'puerto',
                  'protocolo', 'activo', 'descripcion', 'endpoint_destino', 'estado', 'calibracion_vigente_hasta',
                  'ultimo_latido']
        read_only_fields = ['id', 'estado', 'calibracion_vigente_hasta', 'ultimo_latido']


# ─────────────────────────────────────────────────────────────────────────────
# Pacientes
# ─────────────────────────────────────────────────────────────────────────────

class PacienteSerializer(serializers.ModelSerializer):
    tipo_documento = serializers.SlugRelatedField(slug_field='codigo',
                                                  queryset=TipoDocumentoPaciente.objects.filter(activo=True))
    sexo_biologico = serializers.SlugRelatedField(slug_field='codigo', queryset=SexoBiologico.objects.all())
    nombre_completo = serializers.CharField(read_only=True)

    class Meta:
        model = Paciente
        fields = ['id', 'tipo_documento', 'numero_documento', 'primer_nombre', 'segundo_nombre',
                  'primer_apellido', 'segundo_apellido', 'nombre_completo', 'fecha_nacimiento',
                  'sexo_biologico', 'telefono', 'correo_electronico', 'municipio_residencia',
                  'departamento_residencia', 'regimen_salud', 'consentimiento_habeas_data',
                  'activo', 'fecha_creacion', 'version']
        read_only_fields = ['id', 'activo', 'fecha_creacion', 'version']

    def validate_consentimiento_habeas_data(self, valor):
        if self.instance is None and not valor:
            raise serializers.ValidationError('Debe registrarse la aceptación del tratamiento de datos (Ley 1581 de 2012).')
        return valor


# ─────────────────────────────────────────────────────────────────────────────
# Exámenes (lectura) y órdenes
# ─────────────────────────────────────────────────────────────────────────────

class ExamenSolicitadoSerializer(serializers.ModelSerializer):
    estado_examen = serializers.ReadOnlyField(source='estado_examen.nombre')
    estado_examen_nombre = serializers.ReadOnlyField(source='estado_examen.nombre')  # compatibilidad app Expo
    es_final = serializers.ReadOnlyField(source='estado_examen.es_final')
    cups_codigo = serializers.ReadOnlyField(source='cups.codigo_cups')
    cups_descripcion = serializers.ReadOnlyField(source='cups.descripcion')
    orden_numero = serializers.ReadOnlyField(source='orden.numero_orden')
    codigo_barras = serializers.ReadOnlyField(source='muestra.codigo_barras')
    paciente_nombre = serializers.SerializerMethodField()
    paciente_documento = serializers.ReadOnlyField(source='orden.paciente.numero_documento')
    validado_por_username = serializers.ReadOnlyField(source='validado_por.username')
    validado_por_nombre = serializers.CharField(source='validado_por.nombre_completo', read_only=True)
    validado_por_registro = serializers.ReadOnlyField(source='validado_por.registro_profesional')

    class Meta:
        model = ExamenSolicitado
        fields = ['id', 'orden', 'orden_numero', 'cups', 'cups_codigo', 'cups_descripcion', 'muestra',
                  'codigo_barras', 'estado_examen', 'estado_examen_nombre', 'es_final',
                  'paciente_nombre', 'paciente_documento',
                  'validado_por', 'validado_por_username', 'validado_por_nombre', 'validado_por_registro',
                  'fecha_validacion', 'estado_cci_validacion', 'justificacion_cci', 'motivo_rechazo', 'fecha_rechazo',
                  'motivo_anulacion', 'fecha_anulacion', 'version']
        read_only_fields = [f for f in fields if f not in ('orden', 'cups')]

    @extend_schema_field(serializers.CharField())
    def get_paciente_nombre(self, obj):
        return obj.orden.paciente.nombre_completo


class OrdenLaboratorioSerializer(serializers.ModelSerializer):
    """Lectura de una orden con sus exámenes."""
    estado_general = serializers.ReadOnlyField(source='estado_general.nombre')
    paciente_nombre = serializers.CharField(source='paciente.nombre_completo', read_only=True)
    paciente_documento = serializers.ReadOnlyField(source='paciente.numero_documento')
    medico_nombre = serializers.SerializerMethodField()
    examenes = ExamenSolicitadoSerializer(source='examenes_solicitados', many=True, read_only=True)

    class Meta:
        model = OrdenLaboratorio
        fields = ['id', 'numero_orden', 'paciente', 'paciente_nombre', 'paciente_documento',
                  'medico', 'medico_nombre', 'fecha_orden', 'fecha_admision', 'usuario_admite',
                  'observaciones_clinicas', 'codigo_cie10', 'entidad_remitente', 'convenio',
                  'finalidad_consulta', 'causa_externa', 'tipo_diagnostico', 'estado_general',
                  'fecha_finalizacion', 'finalizada_por', 'informe_pendiente', 'examenes', 'version']
        read_only_fields = fields

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_medico_nombre(self, obj):
        return obj.medico.nombre_completo if obj.medico else None


class OrdenCrearSerializer(serializers.Serializer):
    """Creación de orden con sus exámenes en una sola petición (RNF-29.1)."""
    paciente = serializers.PrimaryKeyRelatedField(queryset=Paciente.objects.filter(activo=True))
    examenes = serializers.ListField(child=serializers.CharField(), allow_empty=False,
                                     help_text='Lista de ids o códigos CUPS.')
    observaciones_clinicas = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    codigo_cie10 = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=10)
    entidad_remitente = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=200)
    convenio = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=100)
    finalidad_consulta = serializers.ChoiceField(choices=OrdenLaboratorio._meta.get_field('finalidad_consulta').choices, required=False)
    causa_externa = serializers.ChoiceField(choices=OrdenLaboratorio._meta.get_field('causa_externa').choices, required=False)
    tipo_diagnostico = serializers.ChoiceField(choices=OrdenLaboratorio._meta.get_field('tipo_diagnostico').choices, required=False)
    numero_orden = serializers.CharField(required=False, allow_blank=True, max_length=30)


class OrdenEditarSerializer(serializers.ModelSerializer):
    """Campos editables por el médico mientras la orden está Registrada."""
    class Meta:
        model = OrdenLaboratorio
        fields = ['observaciones_clinicas', 'codigo_cie10', 'entidad_remitente', 'convenio',
                  'finalidad_consulta', 'causa_externa', 'tipo_diagnostico']


class ExamenAgregarSerializer(serializers.Serializer):
    """Agregar un examen a una orden abierta."""
    orden = serializers.PrimaryKeyRelatedField(queryset=OrdenLaboratorio.objects.all())
    cups = serializers.PrimaryKeyRelatedField(queryset=CatalogoCups.objects.filter(activo=True))


# ─────────────────────────────────────────────────────────────────────────────
# Muestras
# ─────────────────────────────────────────────────────────────────────────────

class MuestraFisicaSerializer(serializers.ModelSerializer):
    estado_muestra = serializers.ReadOnlyField(source='estado_muestra.nombre')
    estado_muestra_nombre = serializers.ReadOnlyField(source='estado_muestra.nombre')  # compatibilidad
    orden_numero = serializers.ReadOnlyField(source='orden.numero_orden')
    paciente_nombre = serializers.CharField(source='orden.paciente.nombre_completo', read_only=True)
    usuario_recolecta_username = serializers.ReadOnlyField(source='usuario_recolecta.username')
    examenes = serializers.PrimaryKeyRelatedField(many=True, read_only=True)

    class Meta:
        model = MuestraFisica
        fields = ['id', 'orden', 'orden_numero', 'paciente_nombre', 'codigo_barras', 'tipo_muestra',
                  'fecha_recoleccion', 'estado_muestra', 'estado_muestra_nombre', 'usuario_recolecta',
                  'usuario_recolecta_username', 'condicion_muestra', 'motivo_rechazo',
                  'fecha_recepcion', 'recibida_por', 'fecha_rechazo', 'rechazada_por', 'muestra_madre', 'ubicacion_actual',
                  'fecha_declarada_dispositivo', 'examenes', 'version']
        read_only_fields = fields


class MuestraCrearSerializer(serializers.Serializer):
    orden = serializers.PrimaryKeyRelatedField(queryset=OrdenLaboratorio.objects.all())
    tipo_muestra = serializers.CharField(max_length=50)
    codigo_barras = serializers.CharField(max_length=50, required=False, allow_blank=True)
    fecha_recoleccion = serializers.DateTimeField(required=False)
    condicion_muestra = serializers.ChoiceField(choices=MuestraFisica.CONDICION_CHOICES, required=False)
    fecha_declarada_dispositivo = serializers.DateTimeField(required=False, allow_null=True)
    ubicacion = serializers.CharField(max_length=120, required=False, allow_blank=True)
    observacion = serializers.CharField(required=False, allow_blank=True)
    examenes = serializers.ListField(child=serializers.UUIDField(), required=False,
                                     help_text='Ids de exámenes a vincular; vacío = todos los pendientes o en Repetir.')

    def validate_codigo_barras(self, valor):
        valor = (valor or '').strip()
        if valor and MuestraFisica.objects.filter(codigo_barras=valor).exists():
            raise serializers.ValidationError('Ya existe una muestra con ese código de barras.')
        return valor


class RechazoSerializer(serializers.Serializer):
    motivo_rechazo = serializers.CharField()
    condicion_muestra = serializers.ChoiceField(choices=MuestraFisica.CONDICION_CHOICES, required=False)


class MotivoSerializer(serializers.Serializer):
    motivo = serializers.CharField()


# ─────────────────────────────────────────────────────────────────────────────
# Lecturas y resultados
# ─────────────────────────────────────────────────────────────────────────────

class LecturaEquipoSerialSerializer(serializers.ModelSerializer):
    class Meta:
        model = LecturaEquipoSerial
        fields = ['id', 'equipo_origen', 'codigo_barras_leido', 'fecha_recepcion', 'trama_cruda',
                  'datos_json', 'procesado', 'procesada_por', 'fecha_procesamiento']
        read_only_fields = ['id', 'fecha_recepcion', 'procesado', 'procesada_por', 'fecha_procesamiento']


class ResultadoAnalitoSerializer(serializers.ModelSerializer):
    parametro_nombre = serializers.ReadOnlyField(source='parametro.nombre_parametro')
    unidades = serializers.ReadOnlyField(source='unidades_aplicadas')
    examen_estado = serializers.ReadOnlyField(source='examen_solicitado.estado_examen.nombre')
    orden = serializers.ReadOnlyField(source='examen_solicitado.orden_id')

    class Meta:
        model = ResultadoAnalito
        fields = ['id', 'examen_solicitado', 'examen_estado', 'orden', 'parametro', 'parametro_nombre',
                  'muestra', 'lectura_serial', 'valor_resultado', 'valor_numerico', 'es_anormal', 'es_critico',
                  'unidades', 'unidades_aplicadas', 'rango_min_aplicado', 'rango_max_aplicado',
                  'rango_texto_aplicado', 'parametro_version', 'metodo_aplicado', 'equipo', 'lote_reactivo', 'lote_control',
                  'critico_escalado', 'tiene_acuse', 'comentario_bacteriologo',
                  'registrado_por', 'fecha_procesamiento', 'version']
        read_only_fields = fields

    tiene_acuse = serializers.SerializerMethodField()

    @extend_schema_field(serializers.BooleanField())
    def get_tiene_acuse(self, obj) -> bool:
        return hasattr(obj, 'acuse')


class ResultadoRegistrarSerializer(serializers.Serializer):
    examen_solicitado = serializers.PrimaryKeyRelatedField(queryset=ExamenSolicitado.objects.all())
    parametro = serializers.PrimaryKeyRelatedField(queryset=ParametroExamen.objects.filter(activo=True))
    valor_resultado = serializers.CharField(max_length=100)
    comentario_bacteriologo = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    equipo = serializers.PrimaryKeyRelatedField(queryset=ConfiguracionEquipo.objects.all(), required=False, allow_null=True)


# ─────────────────────────────────────────────────────────────────────────────
# Informes y notificaciones
# ─────────────────────────────────────────────────────────────────────────────

class InformeResultadosSerializer(serializers.ModelSerializer):
    orden_numero = serializers.ReadOnlyField(source='orden.numero_orden')
    generado_por_username = serializers.ReadOnlyField(source='generado_por.username')

    class Meta:
        model = InformeResultados
        fields = ['id', 'orden', 'orden_numero', 'tipo', 'vigente', 'archivo_pdf', 'fecha_generacion',
                  'generado_por', 'generado_por_username', 'hash_documento', 'hash_anterior', 'motivo']
        read_only_fields = fields


class NotificacionSerializer(serializers.ModelSerializer):
    destinatario_username = serializers.ReadOnlyField(source='destinatario.username')
    orden_numero = serializers.ReadOnlyField(source='orden.numero_orden')

    class Meta:
        model = Notificacion
        fields = ['id', 'destinatario', 'destinatario_username', 'orden', 'orden_numero', 'tipo',
                  'mensaje', 'leida', 'fecha_creacion', 'fecha_lectura']
        read_only_fields = fields
