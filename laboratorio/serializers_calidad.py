"""Serializadores de la Fase 2: custodia, calidad, críticos, equipos y lotes (campos explícitos, RNF-38)."""
from rest_framework import serializers

from .models import (
    AcuseValorCritico, CalibracionEquipo, ConfiguracionEquipo, CorridaCCI, EventoMuestra,
    LoteControl, LoteReactivo, MantenimientoEquipo, PoliticaCCI,
)


# ── Custodia ──────────────────────────────────────────────────────────────────

class EventoMuestraSerializer(serializers.ModelSerializer):
    usuario_username = serializers.ReadOnlyField(source='usuario.username')
    muestra_codigo = serializers.ReadOnlyField(source='muestra.codigo_barras')
    muestra_relacionada_codigo = serializers.ReadOnlyField(source='muestra_relacionada.codigo_barras')

    class Meta:
        model = EventoMuestra
        fields = ['id', 'muestra', 'muestra_codigo', 'tipo', 'fecha', 'fecha_declarada_dispositivo', 'usuario',
                  'usuario_username', 'rol', 'ubicacion', 'temperatura', 'observacion', 'muestra_relacionada',
                  'muestra_relacionada_codigo']
        read_only_fields = fields


class EventoAnotarSerializer(serializers.Serializer):
    tipo = serializers.ChoiceField(choices=['transporte', 'almacenamiento', 'analisis', 'nota'])
    ubicacion = serializers.CharField(max_length=120, required=False, allow_blank=True)
    observacion = serializers.CharField(required=False, allow_blank=True)
    temperatura = serializers.DecimalField(max_digits=5, decimal_places=1, required=False, allow_null=True)


class AlicuotaSerializer(serializers.Serializer):
    tipo_muestra = serializers.CharField(max_length=50, required=False)
    codigo_barras = serializers.CharField(max_length=50, required=False, allow_blank=True)
    ubicacion = serializers.CharField(max_length=120, required=False, allow_blank=True)


# ── Equipos y lotes ───────────────────────────────────────────────────────────

class CalibracionEquipoSerializer(serializers.ModelSerializer):
    class Meta:
        model = CalibracionEquipo
        fields = ['id', 'equipo', 'fecha', 'vigente_hasta', 'resultado', 'realizada_por', 'certificado', 'observacion',
                  'registrada_por', 'creada']
        read_only_fields = ['id', 'equipo', 'registrada_por', 'creada']


class MantenimientoEquipoSerializer(serializers.ModelSerializer):
    nuevo_estado = serializers.ChoiceField(choices=ConfiguracionEquipo.ESTADO_CHOICES, required=False, write_only=True)

    class Meta:
        model = MantenimientoEquipo
        fields = ['id', 'equipo', 'tipo', 'fecha', 'descripcion', 'realizado_por', 'proximo', 'registrado_por', 'creado',
                  'nuevo_estado']
        read_only_fields = ['id', 'equipo', 'registrado_por', 'creado']


class CambioEstadoEquipoSerializer(serializers.Serializer):
    estado = serializers.ChoiceField(choices=ConfiguracionEquipo.ESTADO_CHOICES)
    motivo = serializers.CharField(required=False, allow_blank=True)


class LoteReactivoSerializer(serializers.ModelSerializer):
    vencido = serializers.SerializerMethodField()
    equipo_codigo = serializers.ReadOnlyField(source='equipo.codigo_equipo')

    class Meta:
        model = LoteReactivo
        fields = ['id', 'equipo', 'equipo_codigo', 'nombre_parametro', 'nombre', 'lote', 'fecha_vencimiento',
                  'fecha_apertura', 'activo', 'vencido', 'registrado_por', 'creado']
        read_only_fields = ['id', 'registrado_por', 'creado', 'vencido']

    def get_vencido(self, obj) -> bool:
        return obj.vencido()


# ── Control de calidad ────────────────────────────────────────────────────────

class LoteControlSerializer(serializers.ModelSerializer):
    equipo_codigo = serializers.ReadOnlyField(source='equipo.codigo_equipo')

    class Meta:
        model = LoteControl
        fields = ['id', 'equipo', 'equipo_codigo', 'nombre_parametro', 'nivel', 'lote', 'fecha_vencimiento',
                  'media_objetivo', 'desviacion_objetivo', 'unidades', 'activo', 'registrado_por', 'creado']
        read_only_fields = ['id', 'registrado_por', 'creado']


class CorridaCCISerializer(serializers.ModelSerializer):
    lote_descripcion = serializers.CharField(source='lote_control.__str__', read_only=True)
    nombre_parametro = serializers.ReadOnlyField(source='lote_control.nombre_parametro')
    nivel = serializers.ReadOnlyField(source='lote_control.nivel')
    equipo = serializers.ReadOnlyField(source='lote_control.equipo_id')
    registrada_por_username = serializers.ReadOnlyField(source='registrada_por.username')

    class Meta:
        model = CorridaCCI
        fields = ['id', 'lote_control', 'lote_descripcion', 'nombre_parametro', 'nivel', 'equipo', 'valor', 'z_score',
                  'resultado', 'reglas_violadas', 'fecha', 'registrada_por', 'registrada_por_username', 'lectura',
                  'accion_correctiva', 'accion_correctiva_por', 'fecha_accion_correctiva']
        read_only_fields = fields


class CorridaRegistrarSerializer(serializers.Serializer):
    lote_control = serializers.PrimaryKeyRelatedField(queryset=LoteControl.objects.filter(activo=True))
    valor = serializers.DecimalField(max_digits=12, decimal_places=4)


class AccionCorrectivaSerializer(serializers.Serializer):
    accion_correctiva = serializers.CharField()


class PoliticaCCISerializer(serializers.ModelSerializer):
    equipo_codigo = serializers.ReadOnlyField(source='equipo.codigo_equipo')

    class Meta:
        model = PoliticaCCI
        fields = ['id', 'equipo', 'equipo_codigo', 'nombre_parametro', 'modo', 'actualizada_por', 'actualizada']
        read_only_fields = ['id', 'actualizada_por', 'actualizada']


class PoliticaDefinirSerializer(serializers.Serializer):
    equipo = serializers.PrimaryKeyRelatedField(queryset=ConfiguracionEquipo.objects.all())
    nombre_parametro = serializers.CharField(max_length=100)
    modo = serializers.ChoiceField(choices=PoliticaCCI.MODO_CHOICES)


class EstadoCCISerializer(serializers.Serializer):
    equipo = serializers.IntegerField()
    nombre_parametro = serializers.CharField()
    estado = serializers.CharField()
    modo = serializers.CharField()
    propuesta = serializers.DictField()


# ── Críticos ──────────────────────────────────────────────────────────────────

class AcuseValorCriticoSerializer(serializers.ModelSerializer):
    registrado_por_username = serializers.ReadOnlyField(source='registrado_por.username')

    class Meta:
        model = AcuseValorCritico
        fields = ['id', 'resultado', 'comunicado_a', 'medio', 'read_back', 'fecha_comunicacion', 'fecha_declarada',
                  'registrado_por', 'registrado_por_username', 'observacion', 'escalado', 'fecha_escalado']
        read_only_fields = fields


class AcuseRegistrarSerializer(serializers.Serializer):
    comunicado_a = serializers.CharField(max_length=150)
    medio = serializers.ChoiceField(choices=AcuseValorCritico.MEDIO_CHOICES)
    read_back = serializers.BooleanField()
    fecha_declarada = serializers.DateTimeField(required=False, allow_null=True)
    observacion = serializers.CharField(required=False, allow_blank=True)


class AprobarSerializer(serializers.Serializer):
    justificacion_cci = serializers.CharField(required=False, allow_blank=True, allow_null=True)
