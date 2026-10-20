"""Versionado de rangos de referencia (RF-53): un cambio cierra la versión vigente y crea otra."""
from django.db import transaction
from django.utils import timezone

from laboratorio.domain.errores import ErrorDeDominio, NoEncontrado
from laboratorio.models import ParametroExamen
from usuarios import auditoria

CAMPOS_VERSIONADOS = (
    'unidades_medida', 'rango_referencia_minimo', 'rango_referencia_maximo', 'rango_texto',
    'rango_panico_minimo', 'rango_panico_maximo', 'sexo_aplica', 'edad_minima_anios', 'edad_maxima_anios', 'metodo',
)


def nueva_version(actor, parametro_id, cambios, request=None):
    """
    Si `cambios` toca algún campo versionado, crea una versión nueva vigente desde hoy
    y cierra la anterior (vigente_hasta = hoy). Los resultados ya interpretados
    conservan su copia del rango. Si no toca campos versionados, edita en sitio.
    Devuelve (parametro_resultante, se_creo_version).
    """
    with transaction.atomic():
        try:
            actual = ParametroExamen.objects.select_for_update().get(pk=parametro_id)
        except ParametroExamen.DoesNotExist:
            raise NoEncontrado('El parámetro no existe.')
        if actual.vigente_hasta is not None:
            raise ErrorDeDominio('Esta versión del parámetro ya está cerrada; edite la versión vigente.')

        toca_version = any(
            campo in cambios and cambios[campo] != getattr(actual, campo if campo != 'sexo_aplica' else 'sexo_aplica')
            for campo in CAMPOS_VERSIONADOS
        )
        if not toca_version:
            for campo, valor in cambios.items():
                setattr(actual, campo, valor)
            actual.save()
            auditoria.registrar(request, 'parametro.editar', 'ParametroExamen', actual.pk, {'campos': sorted(cambios)}, usuario=actor)
            return actual, False

        hoy = timezone.localdate()
        datos = {campo: getattr(actual, campo) for campo in CAMPOS_VERSIONADOS}
        datos.update({'cups': actual.cups, 'nombre_parametro': actual.nombre_parametro, 'activo': True,
                      'codigo_loinc': actual.codigo_loinc, 'unidad_ucum': actual.unidad_ucum})
        datos.update(cambios)
        nuevo = ParametroExamen.objects.create(version_anterior=actual, **datos)
        actual.vigente_hasta = hoy
        actual.save(update_fields=['vigente_hasta'])
        auditoria.registrar(request, 'parametro.nueva_version', 'ParametroExamen', nuevo.pk,
                            {'anterior': actual.pk, 'campos': sorted(cambios)}, usuario=actor)
    return nuevo, True
