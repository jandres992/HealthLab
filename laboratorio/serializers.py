import uuid
from decimal import Decimal, InvalidOperation

from rest_framework import serializers

from .models import (
    CatalogoCups,
    EstadoExamen,
    EstadoOrden,
    ExamenSolicitado,
    LecturaEquipoSerial,
    MuestraFisica,
    OrdenLaboratorio,
    Paciente,
    ParametroExamen,
    ResultadoAnalito,
    SexoBiologico,
    TipoDocumentoPaciente,
)


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


class CatalogoCupsSerializer(serializers.ModelSerializer):
    class Meta:
        model = CatalogoCups
        fields = '__all__'


class ParametroExamenSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParametroExamen
        fields = '__all__'


class PacienteSerializer(serializers.ModelSerializer):
    # SlugRelatedField permite enviar/recibir 'CC', 'F', etc. en lugar de PKs,
    # manteniendo compatibilidad con la API anterior.
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

    class Meta:
        model = OrdenLaboratorio
        fields = '__all__'
        read_only_fields = ('id', 'fecha_orden')

    def create(self, validated_data):
        if not validated_data.get('estado_general'):
            validated_data['estado_general'] = EstadoOrden.objects.get(nombre='Registrada')
        return super().create(validated_data)


class MuestraFisicaSerializer(serializers.ModelSerializer):
    codigo_barras = serializers.CharField(max_length=50, required=False)

    class Meta:
        model = MuestraFisica
        fields = '__all__'
        read_only_fields = ('id',)

    def create(self, validated_data):
        if not validated_data.get('codigo_barras'):
            validated_data['codigo_barras'] = f"MUE-{uuid.uuid4().hex[:12].upper()}"
        return super().create(validated_data)


class ExamenSolicitadoSerializer(serializers.ModelSerializer):
    estado_examen = serializers.SlugRelatedField(
        slug_field='nombre',
        queryset=EstadoExamen.objects.all(),
        required=False,
    )

    class Meta:
        model = ExamenSolicitado
        fields = '__all__'
        read_only_fields = ('id',)

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
    class Meta:
        model = ResultadoAnalito
        fields = '__all__'
        read_only_fields = ('id', 'fecha_procesamiento')

    def _calcular_anormalidad(self, parametro, valor_resultado):
        if valor_resultado is None or parametro is None:
            return False
        try:
            valor_numerico = Decimal(str(valor_resultado).replace(',', '.').strip())
        except (InvalidOperation, AttributeError):
            return False
        if parametro.rango_referencia_minimo is not None and valor_numerico < parametro.rango_referencia_minimo:
            return True
        if parametro.rango_referencia_maximo is not None and valor_numerico > parametro.rango_referencia_maximo:
            return True
        return False

    def create(self, validated_data):
        validated_data['es_anormal'] = self._calcular_anormalidad(
            validated_data.get('parametro'),
            validated_data.get('valor_resultado'),
        )
        return super().create(validated_data)

    def update(self, instance, validated_data):
        parametro = validated_data.get('parametro', instance.parametro)
        valor_resultado = validated_data.get('valor_resultado', instance.valor_resultado)
        validated_data['es_anormal'] = self._calcular_anormalidad(parametro, valor_resultado)
        return super().update(instance, validated_data)



class CatalogoCupsSerializer(serializers.ModelSerializer):
    class Meta:
        model = CatalogoCups
        fields = '__all__'


class ParametroExamenSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParametroExamen
        fields = '__all__'


class PacienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Paciente
        fields = '__all__'
        read_only_fields = ('id', 'fecha_creacion')


class OrdenLaboratorioSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrdenLaboratorio
        fields = '__all__'
        read_only_fields = ('id', 'fecha_orden')


class MuestraFisicaSerializer(serializers.ModelSerializer):
    class Meta:
        model = MuestraFisica
        fields = '__all__'
        read_only_fields = ('id',)

    def create(self, validated_data):
        if not validated_data.get('codigo_barras'):
            validated_data['codigo_barras'] = f"MUE-{uuid.uuid4().hex[:12].upper()}"
        return super().create(validated_data)


class ExamenSolicitadoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamenSolicitado
        fields = '__all__'
        read_only_fields = ('id',)


class LecturaEquipoSerialSerializer(serializers.ModelSerializer):
    class Meta:
        model = LecturaEquipoSerial
        fields = '__all__'
        read_only_fields = ('id', 'fecha_recepcion')


class ResultadoAnalitoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResultadoAnalito
        fields = '__all__'
        read_only_fields = ('id', 'fecha_procesamiento')

    def _calcular_anormalidad(self, parametro, valor_resultado):
        if valor_resultado is None or parametro is None:
            return False

        try:
            valor_numerico = Decimal(str(valor_resultado).replace(',', '.').strip())
        except (InvalidOperation, AttributeError):
            return False

        if parametro.rango_referencia_minimo is not None and valor_numerico < parametro.rango_referencia_minimo:
            return True
        if parametro.rango_referencia_maximo is not None and valor_numerico > parametro.rango_referencia_maximo:
            return True
        return False

    def create(self, validated_data):
        validated_data['es_anormal'] = self._calcular_anormalidad(
            validated_data.get('parametro'),
            validated_data.get('valor_resultado'),
        )
        return super().create(validated_data)

    def update(self, instance, validated_data):
        parametro = validated_data.get('parametro', instance.parametro)
        valor_resultado = validated_data.get('valor_resultado', instance.valor_resultado)
        validated_data['es_anormal'] = self._calcular_anormalidad(parametro, valor_resultado)
        return super().update(instance, validated_data)