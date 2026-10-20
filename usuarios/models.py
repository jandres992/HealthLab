"""
Modelos del módulo usuarios — HealthLab LIMS.

Cuentas del personal, roles de negocio, catálogos de ubicación (DIVIPOLA),
dispositivos de confianza y bitácora de auditoría.
"""
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _
from simple_history.models import HistoricalRecords


# ─────────────────────────────────────────────────────────────────────────────
# Catálogos
# ─────────────────────────────────────────────────────────────────────────────

class TipoId(models.Model):
    tipo_id = models.CharField(max_length=3)
    detalle = models.CharField(max_length=180)
    estado = models.BooleanField(default=True)

    class Meta:
        db_table = 'tipo_id_Usuarios'
        verbose_name = 'Tipo de identificación'
        verbose_name_plural = 'Tipos de identificación'

    def __str__(self):
        return f'{self.tipo_id} - {self.detalle}'


class Sexo(models.Model):
    sexo = models.CharField(max_length=1)
    descripcion = models.CharField(max_length=20)

    class Meta:
        db_table = 'sexo_Usuarios'

    def __str__(self):
        return self.descripcion


class Departamento(models.Model):
    codigo = models.CharField(max_length=30)
    departamento = models.CharField(max_length=60)

    class Meta:
        db_table = 'departamento_Usuarios'

    def __str__(self):
        return self.departamento


class Municipio(models.Model):
    codigo = models.CharField(max_length=30)
    municipio = models.CharField(max_length=60)
    # PROTECT: un departamento con municipios no se puede borrar (RNF-30.2)
    departamento = models.ForeignKey(Departamento, on_delete=models.PROTECT, related_name='municipios')

    class Meta:
        db_table = 'municipio_Usuarios'

    def __str__(self):
        return f'{self.municipio} ({self.departamento})'


# ─────────────────────────────────────────────────────────────────────────────
# Usuario
# ─────────────────────────────────────────────────────────────────────────────

class Usuario(AbstractUser):
    tipo_id = models.ForeignKey(TipoId, on_delete=models.PROTECT, null=True, blank=True)
    numero_id = models.CharField(max_length=20, null=True, blank=True)
    p_nombre = models.CharField(max_length=60, blank=True, null=True, default='')
    s_nombre = models.CharField(max_length=60, blank=True, null=True, default='')
    p_apellido = models.CharField(max_length=60, blank=True, null=True, default='')
    s_apellido = models.CharField(max_length=60, blank=True, null=True, default='')
    f_nacimiento = models.DateField(blank=True, null=True)
    sexo = models.ForeignKey(Sexo, on_delete=models.PROTECT, blank=True, null=True)
    municipio_residencia = models.ForeignKey(Municipio, on_delete=models.PROTECT, blank=True, null=True)
    direccion_residencia = models.CharField(max_length=250, blank=True, null=True, default='')
    telefono = models.CharField(max_length=12, null=True, blank=True)
    avatar = models.ImageField(upload_to='avatares/', null=True, blank=True, verbose_name=_('Avatar'))

    # RF-05.4: registro profesional (ReTHUS / tarjeta profesional) para Médico y Bacteriólogo.
    # Aparece en el informe junto a la firma del bacteriólogo que valida.
    registro_profesional = models.CharField(
        max_length=40, null=True, blank=True,
        verbose_name=_('Registro profesional'),
        help_text=_('Número de registro ReTHUS o tarjeta profesional.'),
    )

    recibir_notificaciones = models.BooleanField(
        default=True,
        verbose_name=_('Recibir notificaciones del sistema'),
        help_text=_('Indica si el usuario desea recibir notificaciones.'),
    )

    # Historial de cambios de la cuenta (RNF-34.1). La contraseña nunca se historiza.
    history = HistoricalRecords(excluded_fields=['password', 'last_login'])

    class Meta:
        verbose_name = _('Usuario')
        verbose_name_plural = _('Usuarios')
        db_table = 'usuario_Usuarios'

    def __str__(self):
        return self.username

    @property
    def nombre_completo(self):
        partes = [self.p_nombre, self.s_nombre, self.p_apellido, self.s_apellido]
        nombre = ' '.join(p for p in partes if p)
        return nombre or self.get_full_name() or self.username


# ─────────────────────────────────────────────────────────────────────────────
# Roles
# ─────────────────────────────────────────────────────────────────────────────

class TipoUsuario(models.Model):
    tipo = models.CharField(max_length=30)
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'tipoUsuario_Usuarios'
        verbose_name = 'Tipo de Usuario'
        verbose_name_plural = 'Tipos de Usuario'

    def __str__(self):
        return self.tipo


class Permiso(models.Model):
    permiso = models.CharField(max_length=40)
    tipo_usuario = models.ForeignKey(TipoUsuario, on_delete=models.PROTECT, related_name='permisos')

    class Meta:
        db_table = 'permiso_Usuarios'
        verbose_name = 'Permiso'
        verbose_name_plural = 'Permisos'

    def __str__(self):
        return self.permiso


class UsuarioXPermiso(models.Model):
    """Asignación de un rol (vía Permiso → TipoUsuario) a un usuario. Auditable."""
    permiso = models.ForeignKey(Permiso, on_delete=models.PROTECT, related_name='asignaciones')
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='asignaciones_rol')
    history = HistoricalRecords()

    class Meta:
        db_table = 'usuarioxpermiso_Usuarios'
        constraints = [
            models.UniqueConstraint(fields=['usuario', 'permiso'], name='unique_usuario_permiso'),
        ]

    def __str__(self):
        return f'{self.usuario.username} → {self.permiso.permiso}'


# ─────────────────────────────────────────────────────────────────────────────
# Dispositivos de confianza
# ─────────────────────────────────────────────────────────────────────────────

class DispositivoConfianza(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='dispositivos_confianza')
    device_id = models.CharField(max_length=255, verbose_name=_('Identificador del Dispositivo'))
    nombre = models.CharField(max_length=100, verbose_name=_('Nombre del Dispositivo'),
                              help_text='Ej: Chrome en Windows')
    user_agent = models.TextField(blank=True, null=True)
    ultimo_acceso = models.DateTimeField(auto_now=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    es_confiable = models.BooleanField(default=False)

    class Meta:
        db_table = 'dispositivoConfianza_Usuarios'
        unique_together = ('usuario', 'device_id')
        verbose_name = 'Dispositivo de Confianza'
        verbose_name_plural = 'Dispositivos de Confianza'

    def __str__(self):
        return f'{self.nombre} - {self.usuario.username}'


# ─────────────────────────────────────────────────────────────────────────────
# Auditoría
# ─────────────────────────────────────────────────────────────────────────────

class Auditoria(models.Model):
    """
    Bitácora de solo inserción (RNF-25, RNF-34). Registra accesos, gestión de
    cuentas y roles, consultas y acciones sobre datos clínicos. No se actualiza
    ni se borra desde la aplicación; en PostgreSQL el rol de la aplicación no
    tiene UPDATE/DELETE sobre esta tabla.
    """
    usuario = models.ForeignKey(
        Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='auditoria'
    )
    username = models.CharField(max_length=150, blank=True, default='')
    roles = models.JSONField(default=list, blank=True)
    accion = models.CharField(max_length=60, db_index=True)
    entidad = models.CharField(max_length=60, blank=True, default='', db_index=True)
    entidad_id = models.CharField(max_length=64, blank=True, default='', db_index=True)
    detalle = models.JSONField(default=dict, blank=True)
    exito = models.BooleanField(default=True)
    ip = models.CharField(max_length=45, null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True, default='')
    device_id = models.CharField(max_length=255, blank=True, default='')
    fecha = models.DateTimeField(db_index=True)

    class Meta:
        db_table = 'auditoria_Usuarios'
        ordering = ['-fecha']
        verbose_name = 'Registro de auditoría'
        verbose_name_plural = 'Auditoría'

    def __str__(self):
        return f'[{self.fecha:%Y-%m-%d %H:%M}] {self.username or "-"} {self.accion}'
