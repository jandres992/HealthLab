from rest_framework import serializers
from .models import (
    CatalogoCups, ParametroExamen, Paciente, OrdenLaboratorio,
    MuestraFisica, ExamenSolicitado, LecturaEquipoSerial, ResultadoAnalito
)

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