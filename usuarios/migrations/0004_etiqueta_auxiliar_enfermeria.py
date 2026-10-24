"""Renombra el rol «Técnico de Enfermería» como «Auxiliar de Enfermería» en los catálogos.

La clave interna del rol (`tecnico_de_enfermeria`) no cambia: los nombres nuevos se
normalizan a la misma clave por los sinónimos de `usuarios/roles.py`.
"""
from django.db import migrations

TIPOS = {
    'Técnico de Enfermería': 'Auxiliar de Enfermería',
    'Tecnico de Enfermeria': 'Auxiliar de Enfermeria',
}
PERMISOS = {
    'permiso_técnico_de_enfermería': 'permiso_auxiliar_de_enfermería',
    'Acceso Tecnico de Enfermeria': 'Acceso Auxiliar de Enfermeria',
}


def renombrar(apps, tipos, permisos):
    TipoUsuario = apps.get_model('usuarios', 'TipoUsuario')
    Permiso = apps.get_model('usuarios', 'Permiso')
    for viejo, nuevo in tipos.items():
        TipoUsuario.objects.filter(tipo=viejo).update(tipo=nuevo)
    for viejo, nuevo in permisos.items():
        Permiso.objects.filter(permiso=viejo).update(permiso=nuevo)


def adelante(apps, schema_editor):
    renombrar(apps, TIPOS, PERMISOS)


def atras(apps, schema_editor):
    renombrar(apps, {v: k for k, v in TIPOS.items()}, {v: k for k, v in PERMISOS.items()})


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0003_seguridad_roles_auditoria'),
    ]

    operations = [
        migrations.RunPython(adelante, atras),
    ]
