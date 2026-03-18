from django.contrib import admin

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

admin.site.register(TipoDocumentoPaciente)
admin.site.register(SexoBiologico)
admin.site.register(EstadoOrden)
admin.site.register(EstadoExamen)
admin.site.register(CatalogoCups)
admin.site.register(ParametroExamen)
admin.site.register(Paciente)
admin.site.register(OrdenLaboratorio)
admin.site.register(MuestraFisica)
admin.site.register(ExamenSolicitado)
admin.site.register(LecturaEquipoSerial)
admin.site.register(ResultadoAnalito)
