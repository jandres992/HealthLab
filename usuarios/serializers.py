from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import (
    TipoId, Sexo, Municipio, Departamento, Usuario,
    TipoUsuario, Permiso, UsuarioXPermiso, DispositivoConfianza
)

class TipoIdSerializer(serializers.ModelSerializer):
    class Meta:
        model = TipoId
        fields = '__all__'

class SexoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sexo
        fields = '__all__'

class DepartamentoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Departamento
        fields = '__all__'

class MunicipioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Municipio
        fields = '__all__'

class TipoUsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = TipoUsuario
        fields = '__all__'

class PermisoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permiso
        fields = '__all__'

class UsuarioXPermisoSerializer(serializers.ModelSerializer):
    class Meta:
        model = UsuarioXPermiso
        fields = '__all__'

class DispositivoConfianzaSerializer(serializers.ModelSerializer):
    class Meta:
        model = DispositivoConfianza
        fields = '__all__'
        read_only_fields = ('ultimo_acceso', 'creado_en')

class UsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        # Exponemos los campos principales. Al heredar de AbstractUser, hay campos como 'is_staff' o 'is_active' que también podrías incluir si los necesitas.
        fields = [
            'id', 'username', 'password', 'email', 'tipo_id', 'numero_id',
            'p_nombre', 's_nombre', 'p_apellido', 's_apellido', 'f_nacimiento',
            'sexo', 'municipio_residencia', 'direccion_residencia', 'telefono',
            'avatar', 'recibir_notificaciones', 'is_active'
        ]
        # Ocultamos la contraseña en las respuestas GET por seguridad
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def create(self, validated_data):
        # Usamos el método set_password para aplicar el hash seguro de Django
        password = validated_data.pop('password', None)
        usuario = Usuario(**validated_data)
        if password:
            usuario.set_password(password)
        usuario.save()
        return usuario

    def update(self, instance, validated_data):
        # Si envían una nueva contraseña, la encriptamos antes de actualizar
        password = validated_data.pop('password', None)
        if password:
            instance.set_password(password)
        return super().update(instance, validated_data)

class TokenPersonalizadoSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Agregamos datos personalizados al payload del token
        token['username'] = user.username
        # Manejamos los nombres asumiendo que pueden ser nulos según tu modelo
        nombre = getattr(user, 'p_nombre', '') or ''
        apellido = getattr(user, 'p_apellido', '') or ''
        token['nombre_completo'] = f"{nombre} {apellido}".strip()

        return token