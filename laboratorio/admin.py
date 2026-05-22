from django.contrib import admin

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

@admin.register(TipoDocumentoPaciente)
class TipoDocumentoPacienteAdmin(admin.ModelAdmin):
    list_display = ("codigo", "descripcion", "activo")
    search_fields = ("codigo", "descripcion")
    list_filter = ("activo",)

@admin.register(SexoBiologico)
class SexoBiologicoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "descripcion")
    search_fields = ("codigo", "descripcion")

@admin.register(EstadoOrden)
class EstadoOrdenAdmin(admin.ModelAdmin):
    list_display = ("nombre", "descripcion")
    search_fields = ("nombre",)

@admin.register(EstadoExamen)
class EstadoExamenAdmin(admin.ModelAdmin):
    list_display = ("nombre", "descripcion")
    search_fields = ("nombre",)

@admin.register(EstadoMuestra)
class EstadoMuestraAdmin(admin.ModelAdmin):
    list_display = ("nombre", "descripcion")
    search_fields = ("nombre",)

@admin.register(CatalogoCups)
class CatalogoCupsAdmin(admin.ModelAdmin):
    list_display = ("codigo_cups", "descripcion", "activo")
    search_fields = ("codigo_cups", "descripcion")
    list_filter = ("activo",)

@admin.register(ParametroExamen)
class ParametroExamenAdmin(admin.ModelAdmin):
    list_display = ("nombre_parametro", "cups", "sexo_aplica", "edad_minima_anios", "edad_maxima_anios")
    search_fields = ("nombre_parametro", "cups__codigo_cups", "cups__descripcion")
    list_filter = ("sexo_aplica",)
    autocomplete_fields = ("cups", "sexo_aplica")

@admin.register(ConfiguracionEquipo)
class ConfiguracionEquipoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "codigo_equipo", "tipo_conexion", "protocolo", "activo")
    search_fields = ("nombre", "codigo_equipo", "host_ip")
    list_filter = ("tipo_conexion", "protocolo", "activo")

@admin.register(Paciente)
class PacienteAdmin(admin.ModelAdmin):
    list_display = ("primer_nombre", "primer_apellido", "tipo_documento", "numero_documento", "regimen_salud", "activo")
    search_fields = ("numero_documento", "primer_nombre", "primer_apellido")
    list_filter = ("regimen_salud", "activo", "consentimiento_habeas_data")

@admin.register(OrdenLaboratorio)
class OrdenLaboratorioAdmin(admin.ModelAdmin):
    list_display = ("numero_orden", "paciente", "medico", "fecha_orden", "estado_general")
    search_fields = ("numero_orden", "paciente__numero_documento", "paciente__primer_nombre", "paciente__primer_apellido")
    list_filter = ("estado_general", "fecha_orden", "finalidad_consulta")
    autocomplete_fields = ("paciente", "medico", "usuario_admite", "estado_general")

@admin.register(MuestraFisica)
class MuestraFisicaAdmin(admin.ModelAdmin):
    list_display = ("codigo_barras", "tipo_muestra", "orden", "estado_muestra", "condicion_muestra")
    search_fields = ("codigo_barras", "orden__numero_orden")
    list_filter = ("estado_muestra", "condicion_muestra")
    autocomplete_fields = ("orden", "estado_muestra", "usuario_recolecta")

@admin.register(ExamenSolicitado)
class ExamenSolicitadoAdmin(admin.ModelAdmin):
    list_display = ("orden", "cups", "estado_examen", "validado_por")
    search_fields = ("orden__numero_orden", "cups__codigo_cups", "cups__descripcion")
    list_filter = ("estado_examen",)
    autocomplete_fields = ("orden", "cups", "muestra", "estado_examen", "validado_por")

@admin.register(LecturaEquipoSerial)
class LecturaEquipoSerialAdmin(admin.ModelAdmin):
    list_display = ("equipo_origen", "codigo_barras_leido", "fecha_recepcion", "procesado")
    search_fields = ("equipo_origen", "codigo_barras_leido")
    list_filter = ("procesado", "fecha_recepcion")

@admin.register(ResultadoAnalito)
class ResultadoAnalitoAdmin(admin.ModelAdmin):
    list_display = ("parametro", "examen_solicitado", "valor_resultado", "es_anormal", "es_critico")
    search_fields = ("parametro__nombre_parametro", "examen_solicitado__orden__numero_orden")
    list_filter = ("es_anormal", "es_critico", "fecha_procesamiento")
    autocomplete_fields = ("examen_solicitado", "parametro", "lectura_serial")

@admin.register(InformeResultados)
class InformeResultadosAdmin(admin.ModelAdmin):
    list_display = ("orden", "fecha_generacion", "generado_por")
    search_fields = ("orden__numero_orden", "hash_documento")
    autocomplete_fields = ("orden", "generado_por")

@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ("tipo", "destinatario", "orden", "leida", "fecha_creacion")
    search_fields = ("mensaje", "destinatario__username", "orden__numero_orden")
    list_filter = ("tipo", "leida", "fecha_creacion")
    autocomplete_fields = ("destinatario", "orden")
