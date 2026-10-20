# models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _


class TipoId(models.Model):
    tipo_id = models.CharField(max_length=3)
    detalle = models.CharField(max_length=180)
    estado = models.BooleanField(default=True)

    class Meta:
        db_table = 'tipo_id_Usuarios'


class Sexo(models.Model):
    sexo = models.CharField(max_length=1)
    descripcion = models.CharField(max_length=20)

    class Meta:
        db_table = 'sexo_Usuarios'


class Municipio(models.Model):
    codigo = models.CharField(max_length=30)
    municipio = models.CharField(max_length=60)
    departamento = models.ForeignKey('Departamento', models.DO_NOTHING)

    class Meta:
        db_table = 'municipio_Usuarios'


class Departamento(models.Model):
    codigo = models.CharField(max_length=30)
    departamento = models.CharField(max_length=60)

    class Meta:
        db_table = 'departamento_Usuarios'

class Usuario(AbstractUser):
    tipo_id = models.ForeignKey('TipoId', models.DO_NOTHING, null=True, blank=True)
    numero_id = models.CharField(max_length=20, null=True, blank=True)
    p_nombre = models.CharField(max_length=60, blank=True, null=True, default="")
    s_nombre = models.CharField(max_length=60, blank=True, null=True, default="")
    p_apellido = models.CharField(max_length=60, blank=True, null=True, default="")
    s_apellido = models.CharField(max_length=60, blank=True, null=True, default="")
    f_nacimiento = models.DateField(blank=True, null=True)
    sexo = models.ForeignKey('Sexo', models.DO_NOTHING, blank=True, null=True, default="")
    municipio_residencia = models.ForeignKey('Municipio', models.DO_NOTHING, blank=True, null=True, default="")
    direccion_residencia = models.CharField(max_length=250, blank=True, null=True, default="")
    telefono = models.CharField(max_length=12, null=True, blank=True)
    avatar = models.ImageField(upload_to='avatares/', null=True, blank=True, verbose_name=_('Avatar'))


    # Nuevo campo solicitado
    recibir_notificaciones = models.BooleanField(
        default=True,
        verbose_name=_('Recibir notificaciones del sistema'),
        help_text=_('Indica si el usuario desea recibir correos electrónicos informativos.')
    )

    class Meta:
        verbose_name = _('Usuario')
        verbose_name_plural = _('Usuarios')
        db_table = 'usuario_Usuarios'

    def __str__(self):
        return self.username


class TipoUsuario(models.Model):
    tipo = models.CharField(max_length=30)
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'tipoUsuario_Usuarios'
        verbose_name = "Tipo de Usuario"
        verbose_name_plural = "Tipos de Usuario"

    def __str__(self):
        return self.tipo


class Permiso(models.Model):
    permiso = models.CharField(max_length=40)
    tipo_usuario = models.ForeignKey('TipoUsuario', models.DO_NOTHING)

    class Meta:
        db_table = 'permiso_Usuarios'
        verbose_name = "Permiso"
        verbose_name_plural = "Permisos"

    def __str__(self):
        return self.permiso


class UsuarioXPermiso(models.Model):
    permiso = models.ForeignKey('Permiso', models.DO_NOTHING)
    usuario = models.ForeignKey('Usuario', models.DO_NOTHING)

    class Meta:
        db_table = 'usuarioxpermiso_Usuarios'


class DispositivoConfianza(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='dispositivos_confianza')
    device_id = models.CharField(max_length=255, verbose_name=_("Identificador del Dispositivo"))
    nombre = models.CharField(max_length=100, verbose_name=_("Nombre del Dispositivo"),
                              help_text="Ej: Chrome en Windows")
    user_agent = models.TextField(blank=True, null=True)
    ultimo_acceso = models.DateTimeField(auto_now=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    es_confiable = models.BooleanField(default=False)

    class Meta:
        db_table = 'dispositivoConfianza_Usuarios'
        unique_together = ('usuario', 'device_id')
        verbose_name = "Dispositivo de Confianza"
        verbose_name_plural = "Dispositivos de Confianza"

    def __str__(self):
        return f"{self.nombre} - {self.usuario.username}"