from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (
	Departamento,
	DispositivoConfianza,
	Municipio,
	Permiso,
	Sexo,
	TipoId,
	TipoUsuario,
	Usuario,
	UsuarioXPermiso,
)


@admin.register(TipoId)
class TipoIdAdmin(admin.ModelAdmin):
	list_display = ("tipo_id", "detalle", "estado")
	list_filter = ("estado",)
	search_fields = ("tipo_id", "detalle")
	ordering = ("tipo_id",)


@admin.register(Sexo)
class SexoAdmin(admin.ModelAdmin):
	list_display = ("sexo", "descripcion")
	search_fields = ("sexo", "descripcion")
	ordering = ("sexo",)


@admin.register(Departamento)
class DepartamentoAdmin(admin.ModelAdmin):
	list_display = ("codigo", "departamento")
	search_fields = ("codigo", "departamento")
	ordering = ("departamento",)


@admin.register(Municipio)
class MunicipioAdmin(admin.ModelAdmin):
	list_display = ("codigo", "municipio", "departamento")
	list_filter = ("departamento",)
	search_fields = ("codigo", "municipio", "departamento__departamento")
	ordering = ("departamento__departamento", "municipio")
	autocomplete_fields = ("departamento",)


@admin.register(TipoUsuario)
class TipoUsuarioAdmin(admin.ModelAdmin):
	list_display = ("tipo", "descripcion")
	search_fields = ("tipo", "descripcion")
	ordering = ("tipo",)


@admin.register(Permiso)
class PermisoAdmin(admin.ModelAdmin):
	list_display = ("permiso", "tipo_usuario")
	list_filter = ("tipo_usuario",)
	search_fields = ("permiso", "tipo_usuario__tipo")
	ordering = ("permiso",)
	autocomplete_fields = ("tipo_usuario",)


class UsuarioXPermisoInline(admin.TabularInline):
	model = UsuarioXPermiso
	extra = 0
	autocomplete_fields = ("permiso",)


@admin.register(Usuario)
class UsuarioAdmin(BaseUserAdmin):
	list_display = (
		"username",
		"email",
		"p_nombre",
		"p_apellido",
		"tipo_id",
		"numero_id",
		"is_staff",
		"is_active",
		"recibir_notificaciones",
	)
	list_filter = (
		"is_staff",
		"is_superuser",
		"is_active",
		"recibir_notificaciones",
		"tipo_id",
		"sexo",
		"municipio_residencia__departamento",
	)
	search_fields = (
		"username",
		"email",
		"numero_id",
		"p_nombre",
		"p_apellido",
		"telefono",
	)
	ordering = ("username",)
	readonly_fields = ("last_login", "date_joined")
	autocomplete_fields = ("tipo_id", "sexo", "municipio_residencia")
	inlines = (UsuarioXPermisoInline,)

	fieldsets = (
		(None, {"fields": ("username", "password")}),
		(
			"Informacion personal",
			{
				"fields": (
					"first_name",
					"last_name",
					"email",
					"p_nombre",
					"s_nombre",
					"p_apellido",
					"s_apellido",
					"avatar",
				)
			},
		),
		(
			"Identificacion y contacto",
			{
				"fields": (
					"tipo_id",
					"numero_id",
					"f_nacimiento",
					"sexo",
					"municipio_residencia",
					"direccion_residencia",
					"telefono",
					"recibir_notificaciones",
				)
			},
		),
		(
			"Permisos Django",
			{"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
		),
		("Fechas importantes", {"fields": ("last_login", "date_joined")}),
	)

	add_fieldsets = (
		(
			None,
			{
				"classes": ("wide",),
				"fields": (
					"username",
					"email",
					"password1",
					"password2",
					"is_active",
					"is_staff",
					"is_superuser",
				),
			},
		),
	)


@admin.register(UsuarioXPermiso)
class UsuarioXPermisoAdmin(admin.ModelAdmin):
	list_display = ("usuario", "permiso")
	list_filter = ("permiso__tipo_usuario",)
	search_fields = ("usuario__username", "permiso__permiso", "permiso__tipo_usuario__tipo")
	autocomplete_fields = ("usuario", "permiso")


@admin.register(DispositivoConfianza)
class DispositivoConfianzaAdmin(admin.ModelAdmin):
	list_display = (
		"usuario",
		"nombre",
		"device_id",
		"es_confiable",
		"ultimo_acceso",
		"creado_en",
	)
	list_filter = ("es_confiable", "creado_en", "ultimo_acceso")
	search_fields = ("usuario__username", "nombre", "device_id", "user_agent")
	ordering = ("-ultimo_acceso",)
	autocomplete_fields = ("usuario",)
