"""
Serializadores del módulo usuarios.

Regla RNF-38: las entidades de usuario exponen listas explícitas de campos.
Regla RNF-28: `password` nunca se devuelve; `is_staff`/`is_superuser` solo
los ve el Administrador.
"""
from django.contrib.auth import password_validation
from django.contrib.auth.hashers import check_password
from rest_framework import exceptions, serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .acciones import acciones_de
from .models import (
    Departamento, DispositivoConfianza, Municipio, Permiso, Sexo,
    TipoId, TipoUsuario, Usuario, UsuarioXPermiso,
)
from .roles import ETIQUETAS, roles_de


# ─────────────────────────────────────────────────────────────────────────────
# Catálogos
# ─────────────────────────────────────────────────────────────────────────────

class TipoIdSerializer(serializers.ModelSerializer):
    class Meta:
        model = TipoId
        fields = ['id', 'tipo_id', 'detalle', 'estado']


class SexoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sexo
        fields = ['id', 'sexo', 'descripcion']


class DepartamentoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Departamento
        fields = ['id', 'codigo', 'departamento']


class MunicipioSerializer(serializers.ModelSerializer):
    departamento_nombre = serializers.ReadOnlyField(source='departamento.departamento')

    class Meta:
        model = Municipio
        fields = ['id', 'codigo', 'municipio', 'departamento', 'departamento_nombre']


# ─────────────────────────────────────────────────────────────────────────────
# Roles
# ─────────────────────────────────────────────────────────────────────────────

class TipoUsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = TipoUsuario
        fields = ['id', 'tipo', 'descripcion']


class PermisoSerializer(serializers.ModelSerializer):
    tipo_usuario_nombre = serializers.ReadOnlyField(source='tipo_usuario.tipo')

    class Meta:
        model = Permiso
        fields = ['id', 'permiso', 'tipo_usuario', 'tipo_usuario_nombre']


class UsuarioXPermisoSerializer(serializers.ModelSerializer):
    usuario_username = serializers.ReadOnlyField(source='usuario.username')
    permiso_nombre = serializers.ReadOnlyField(source='permiso.permiso')
    rol = serializers.ReadOnlyField(source='permiso.tipo_usuario.tipo')

    class Meta:
        model = UsuarioXPermiso
        fields = ['id', 'usuario', 'usuario_username', 'permiso', 'permiso_nombre', 'rol']

    def validate(self, attrs):
        # RF-05.1: un usuario no puede modificar sus propios roles.
        solicitante = self.context['request'].user
        if attrs.get('usuario') == solicitante:
            raise exceptions.PermissionDenied('No puedes modificar tus propios roles.')
        return attrs


# ─────────────────────────────────────────────────────────────────────────────
# Dispositivos
# ─────────────────────────────────────────────────────────────────────────────

class DispositivoConfianzaSerializer(serializers.ModelSerializer):
    usuario_username = serializers.ReadOnlyField(source='usuario.username')

    class Meta:
        model = DispositivoConfianza
        fields = ['id', 'usuario', 'usuario_username', 'device_id', 'nombre',
                  'user_agent', 'es_confiable', 'ultimo_acceso', 'creado_en']
        read_only_fields = fields


# ─────────────────────────────────────────────────────────────────────────────
# Cuentas (gestión por el Administrador)
# ─────────────────────────────────────────────────────────────────────────────

class UsuarioSerializer(serializers.ModelSerializer):
    """Vista del Administrador: crea y edita cuentas; nunca devuelve la contraseña."""
    password = serializers.CharField(write_only=True, required=False, allow_blank=False)
    roles = serializers.SerializerMethodField(read_only=True)
    nombre_completo = serializers.ReadOnlyField()

    class Meta:
        model = Usuario
        fields = [
            'id', 'username', 'password', 'email',
            'tipo_id', 'numero_id', 'registro_profesional',
            'p_nombre', 's_nombre', 'p_apellido', 's_apellido', 'nombre_completo',
            'f_nacimiento', 'sexo', 'municipio_residencia', 'direccion_residencia',
            'telefono', 'avatar', 'recibir_notificaciones',
            'is_active', 'is_staff', 'is_superuser', 'roles', 'date_joined', 'last_login',
        ]
        read_only_fields = ['id', 'is_staff', 'is_superuser', 'roles', 'date_joined', 'last_login']

    def get_roles(self, obj):
        return sorted(roles_de(obj))

    def validate_password(self, valor):
        password_validation.validate_password(valor, self.instance)
        return valor

    def validate(self, attrs):
        if self.instance is None and not attrs.get('password'):
            raise serializers.ValidationError({'password': 'La contraseña es obligatoria al crear la cuenta.'})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop('password')
        usuario = Usuario(**validated_data)
        usuario.set_password(password)
        usuario.save()
        return usuario

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        if password:
            instance.set_password(password)
        return super().update(instance, validated_data)


# ─────────────────────────────────────────────────────────────────────────────
# Perfil propio (/usr/me/) — RF-05.2, BE-01
# ─────────────────────────────────────────────────────────────────────────────

class PerfilPropioSerializer(serializers.ModelSerializer):
    """Lo que un usuario ve y puede cambiar de sí mismo. Nunca roles ni banderas."""
    roles = serializers.SerializerMethodField(read_only=True)
    roles_etiquetas = serializers.SerializerMethodField(read_only=True)
    acciones = serializers.SerializerMethodField(read_only=True)
    nombre_completo = serializers.ReadOnlyField()

    class Meta:
        model = Usuario
        fields = [
            'id', 'username', 'email',
            'tipo_id', 'numero_id', 'registro_profesional',
            'p_nombre', 's_nombre', 'p_apellido', 's_apellido', 'nombre_completo',
            'f_nacimiento', 'sexo', 'municipio_residencia', 'direccion_residencia',
            'telefono', 'avatar', 'recibir_notificaciones',
            'roles', 'roles_etiquetas', 'acciones', 'last_login',
        ]
        read_only_fields = [
            'id', 'username', 'tipo_id', 'numero_id', 'registro_profesional',
            'p_nombre', 's_nombre', 'p_apellido', 's_apellido', 'f_nacimiento', 'sexo',
            'roles', 'roles_etiquetas', 'acciones', 'last_login',
        ]

    def get_roles(self, obj):
        return sorted(roles_de(obj))

    def get_roles_etiquetas(self, obj):
        return [ETIQUETAS[r] for r in sorted(roles_de(obj))]

    def get_acciones(self, obj):
        return acciones_de(obj)


class CambioContrasenaSerializer(serializers.Serializer):
    password_actual = serializers.CharField(write_only=True)
    password_nueva = serializers.CharField(write_only=True)

    def validate_password_actual(self, valor):
        usuario = self.context['request'].user
        if not check_password(valor, usuario.password):
            raise serializers.ValidationError('La contraseña actual no es correcta.')
        return valor

    def validate_password_nueva(self, valor):
        password_validation.validate_password(valor, self.context['request'].user)
        return valor


# ─────────────────────────────────────────────────────────────────────────────
# Login — RF-01, RF-01.1
# ─────────────────────────────────────────────────────────────────────────────

class TokenPersonalizadoSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        usuario = self.user

        roles = sorted(roles_de(usuario))
        if not roles and not usuario.is_superuser:
            # RF-01.1: sin rol no se puede usar el sistema.
            raise exceptions.PermissionDenied(
                'Usuario sin rol asignado; contacte al administrador.'
            )

        data['roles'] = roles
        data['roles_etiquetas'] = [ETIQUETAS[r] for r in roles]
        # Compatibilidad con la app Expo actual, que espera un único `rol`.
        data['rol'] = ETIQUETAS[roles[0]] if roles else ETIQUETAS['administrador']
        data['acciones'] = acciones_de(usuario)
        data['user'] = {
            'id': usuario.id,
            'username': usuario.username,
            'p_nombre': usuario.p_nombre or '',
            'p_apellido': usuario.p_apellido or '',
            'nombre_completo': usuario.nombre_completo,
            'email': usuario.email,
            'registro_profesional': usuario.registro_profesional,
        }
        return data

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['username'] = user.username
        token['nombre_completo'] = user.nombre_completo
        token['roles'] = sorted(roles_de(user))
        return token
