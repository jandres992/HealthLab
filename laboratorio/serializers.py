"""
Serializers del módulo laboratorio — HealthLab LIMS.
Cubre las fases 1-6 del flujo clínico.
"""
import datetime
import uuid
from decimal import Decimal, InvalidOperation

from rest_framework import serializers

from .models import (
    CatalogoCups,
    ConfiguracionEquipo,
    EstadoExamen,
    EstadoMuestra,
    EstadoOrden,
    ExamenSolicitado,
    InformeResultados,
    LecturaEquipoSerial,
    MuestraFisica,
    Notificacion,
    OrdenLaboratorio,
    Paciente,
    ParametroExamen,
    ResultadoAnalito,
    SexoBiologico,
    TipoDocumentoPaciente,
)
from .utils import es_anormal


# ─────────────────────────────────────────────────────────────────────────────
# Catálogos de dominio
# ─────────────────────────────────────────────────────────────────────────────

class TipoDocumentoPacienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = TipoDocumentoPaciente
        fields = '__all__'


class SexoBiologicoSerializer(serializers.ModelSerializer):
    class Meta:
        model = SexoBiologico
        fields = '__all__'


class EstadoOrdenSerializer(serializers.ModelSerializer):
    class Meta:
        model = EstadoOrden
        fields = '__all__'


class EstadoExamenSerializer(serializers.ModelSerializer):
    class Meta:
        model = EstadoExamen
        fields = '__all__'


class EstadoMuestraSerializer(serializers.ModelSerializer):
    class Meta:
        model = EstadoMuestra
        fields = '__all__'


# ─────────────────────────────────────────────────────────────────────────────
# FASE 1 — Catálogos y configuración
# ─────────────────────────────────────────────────────────────────────────────

class CatalogoCupsSerializer(serializers.ModelSerializer):
    class Meta:
        model = CatalogoCups
        fields = '__all__'


class ParametroExamenSerializer(serializers.ModelSerializer):
    """
    Permite enviar el sexo_aplica como código (ej: 'M', 'F') o como PK.
    Expone todos los campos nuevos de segmentación por sexo/edad y pánico.
    """
    sexo_aplica = serializers.SlugRelatedField(
        slug_field='codigo',
        queryset=SexoBiologico.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = ParametroExamen
        fields = '__all__'


class ConfiguracionEquipoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfiguracionEquipo
        fields = '__all__'
        extra_kwargs = {
            'token_middleware': {'write_only': True},
        }


# ─────────────────────────────────────────────────────────────────────────────
# FASE 2 — Pacientes y órdenes
# ─────────────────────────────────────────────────────────────────────────────

class PacienteSerializer(serializers.ModelSerializer):
    tipo_documento = serializers.SlugRelatedField(
        slug_field='codigo',
        queryset=TipoDocumentoPaciente.objects.filter(activo=True),
    )
    sexo_biologico = serializers.SlugRelatedField(
        slug_field='codigo',
        queryset=SexoBiologico.objects.all(),
    )

    class Meta:
        model = Paciente
        fields = '__all__'
        read_only_fields = ('id', 'fecha_creacion')


class OrdenLaboratorioSerializer(serializers.ModelSerializer):
    estado_general = serializers.SlugRelatedField(
        slug_field='nombre',
        queryset=EstadoOrden.objects.all(),
        required=False,
    )
    # Campos de solo lectura para presentación enriquecida
    paciente_nombre = serializers.SerializerMethodField(read_only=True)
    medico_nombre = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = OrdenLaboratorio
        fields = '__all__'
        read_only_fields = ('id', 'fecha_orden', 'paciente_nombre', 'medico_nombre')

    def get_paciente_nombre(self, obj):
        return f"{obj.paciente.primer_nombre} {obj.paciente.primer_apellido}"

    def get_medico_nombre(self, obj):
        if not obj.medico:
            return None
        return (
            f"{obj.medico.p_nombre or ''} {obj.medico.p_apellido or ''}".strip()
            or obj.medico.username
        )

    def create(self, validated_data):
        # Auto-generar numero_orden si no se proporciona
        if not validated_data.get('numero_orden'):
            hoy = datetime.date.today()
            prefijo = f"LAB-{hoy.strftime('%Y%m%d')}-"
            count = OrdenLaboratorio.objects.filter(numero_orden__startswith=prefijo).count()
            validated_data['numero_orden'] = f"{prefijo}{count + 1:04d}"
        # Estado por defecto: Registrada
        if not validated_data.get('estado_general'):
            validated_data['estado_general'] = EstadoOrden.objects.get(nombre='Registrada')
        return super().create(validated_data)


# ─────────────────────────────────────────────────────────────────────────────
# FASE 3 — Muestras físicas
# ─────────────────────────────────────────────────────────────────────────────

class MuestraFisicaSerializer(serializers.ModelSerializer):
    codigo_barras = serializers.CharField(max_length=50, required=False)
    estado_muestra = serializers.SlugRelatedField(
        slug_field='nombre',
        queryset=EstadoMuestra.objects.all(),
        required=False,
        allow_null=True,
    )
    estado_muestra_nombre = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = MuestraFisica
        fields = '__all__'
        read_only_fields = ('id', 'estado_muestra_nombre')

    def get_estado_muestra_nombre(self, obj):
        return obj.estado_muestra.nombre if obj.estado_muestra else None

    def create(self, validated_data):
        if not validated_data.get('codigo_barras'):
            validated_data['codigo_barras'] = f"MUE-{uuid.uuid4().hex[:12].upper()}"
        # Estado inicial: Recolectada
        if not validated_data.get('estado_muestra'):
            try:
                validated_data['estado_muestra'] = EstadoMuestra.objects.get(nombre='Recolectada')
            except EstadoMuestra.DoesNotExist:
                pass
        return super().create(validated_data)


# ─────────────────────────────────────────────────────────────────────────────
# FASES 4 & 5 — Exámenes, lecturas seriales y resultados
# ─────────────────────────────────────────────────────────────────────────────

class ExamenSolicitadoSerializer(serializers.ModelSerializer):
    estado_examen = serializers.SlugRelatedField(
        slug_field='nombre',
        queryset=EstadoExamen.objects.all(),
        required=False,
    )
    estado_examen_nombre = serializers.SerializerMethodField(read_only=True)
    validado_por_username = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ExamenSolicitado
        fields = '__all__'
        read_only_fields = ('id', 'estado_examen_nombre', 'validado_por_username')

    def get_estado_examen_nombre(self, obj):
        return obj.estado_examen.nombre if obj.estado_examen else None

    def get_validado_por_username(self, obj):
        return obj.validado_por.username if obj.validado_por else None

    def create(self, validated_data):
        if not validated_data.get('estado_examen'):
            validated_data['estado_examen'] = EstadoExamen.objects.get(nombre='Pendiente')
        return super().create(validated_data)


class LecturaEquipoSerialSerializer(serializers.ModelSerializer):
    class Meta:
        model = LecturaEquipoSerial
        fields = '__all__'
        read_only_fields = ('id', 'fecha_recepcion')


class ResultadoAnalitoSerializer(serializers.ModelSerializer):
    es_critico = serializers.BooleanField(read_only=True)

    class Meta:
        model = ResultadoAnalito
        fields = '__all__'
        read_only_fields = ('id', 'fecha_procesamiento', 'es_anormal', 'es_critico')

    def _calcular_flags(self, parametro, valor_resultado, examen_solicitado=None):
        """
        Calcula es_anormal y es_critico. Si hay examen asociado, intenta usar
        el rango específico para el sexo/edad del paciente.
        """
        parametro_efectivo = parametro
        if examen_solicitado and parametro:
            from .utils import obtener_parametro_para_paciente  # noqa: PLC0415
            try:
                paciente = examen_solicitado.orden.paciente
                p = obtener_parametro_para_paciente(
                    parametro.cups_id, parametro.nombre_parametro, paciente
                )
                if p:
                    parametro_efectivo = p
            except Exception:
                pass
        if parametro_efectivo is None:
            return False, False
        return es_anormal(parametro_efectivo, valor_resultado)

    def create(self, validated_data):
        param = validated_data.get('parametro')
        valor = validated_data.get('valor_resultado')
        examen = validated_data.get('examen_solicitado')
        anormal, critico = self._calcular_flags(param, valor, examen)
        validated_data['es_anormal'] = anormal
        validated_data['es_critico'] = critico
        return super().create(validated_data)

    def update(self, instance, validated_data):
        param = validated_data.get('parametro', instance.parametro)
        valor = validated_data.get('valor_resultado', instance.valor_resultado)
        examen = validated_data.get('examen_solicitado', instance.examen_solicitado)
        anormal, critico = self._calcular_flags(param, valor, examen)
        validated_data['es_anormal'] = anormal
        validated_data['es_critico'] = critico
        return super().update(instance, validated_data)


# ─────────────────────────────────────────────────────────────────────────────
# FASE 6 — Informes y notificaciones
# ─────────────────────────────────────────────────────────────────────────────

class InformeResultadosSerializer(serializers.ModelSerializer):
    orden_numero = serializers.SerializerMethodField(read_only=True)
    generado_por_username = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = InformeResultados
        fields = '__all__'
        read_only_fields = ('id', 'fecha_generacion', 'hash_documento', 'orden_numero', 'generado_por_username')

    def get_orden_numero(self, obj):
        return obj.orden.numero_orden

    def get_generado_por_username(self, obj):
        return obj.generado_por.username if obj.generado_por else None


class NotificacionSerializer(serializers.ModelSerializer):
    destinatario_username = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Notificacion
        fields = '__all__'
        read_only_fields = ('id', 'fecha_creacion', 'destinatario_username')

    def get_destinatario_username(self, obj):
        return obj.destinatario.username
