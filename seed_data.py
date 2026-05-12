import os
import django
import random
from datetime import date, timedelta
from django.utils import timezone

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'HealthLab.settings')
django.setup()

from django.contrib.auth import get_user_model
from laboratorio.models import (
    TipoDocumentoPaciente, SexoBiologico, EstadoOrden, EstadoExamen, EstadoMuestra,
    CatalogoCups, ParametroExamen, Paciente, OrdenLaboratorio, MuestraFisica,
    ExamenSolicitado, ResultadoAnalito, ConfiguracionEquipo, Notificacion, InformeResultados
)
from usuarios.models import TipoId, Sexo, Municipio, Departamento, TipoUsuario, Permiso, UsuarioXPermiso

Usuario = get_user_model()

def seed():
    print("Iniciando inyección de datos reales para Laboratorio Nivel 2...")

    # 1. Limpiar datos existentes en orden inverso de dependencias
    print("Limpiando base de datos...")
    
    # Notificaciones e Informes
    Notificacion.objects.all().delete()
    InformeResultados.objects.all().delete()
    
    # Resultados y Exámenes
    ResultadoAnalito.objects.all().delete()
    ExamenSolicitado.objects.all().delete()
    
    # Muestras y Órdenes
    MuestraFisica.objects.all().delete()
    OrdenLaboratorio.objects.all().delete()
    
    # Pacientes y Configuración
    Paciente.objects.all().delete()
    ParametroExamen.objects.all().delete()
    CatalogoCups.objects.all().delete()
    ConfiguracionEquipo.objects.all().delete()
    
    # Estados y Referencias de Laboratorio
    EstadoMuestra.objects.all().delete()
    EstadoExamen.objects.all().delete()
    EstadoOrden.objects.all().delete()
    SexoBiologico.objects.all().delete()
    TipoDocumentoPaciente.objects.all().delete()
    
    # Usuarios y Permisos
    UsuarioXPermiso.objects.all().delete()
    Permiso.objects.all().delete()
    Usuario.objects.all().delete() # Importante borrar usuarios antes que sus catálogos
    TipoUsuario.objects.all().delete()
    Municipio.objects.all().delete()
    Departamento.objects.all().delete()
    Sexo.objects.all().delete()
    TipoId.objects.all().delete()
    
    # 2. Configuración Base (Usuarios y Roles)
    print("Creando catálogos de usuarios...")
    ti_cc, _ = TipoId.objects.get_or_create(tipo_id='CC', detalle='Cédula de Ciudadanía')
    ti_ce, _ = TipoId.objects.get_or_create(tipo_id='CE', detalle='Cédula de Extranjería')
    ti_ti, _ = TipoId.objects.get_or_create(tipo_id='TI', detalle='Tarjeta de Identidad')
    
    s_m, _ = Sexo.objects.get_or_create(sexo='M', descripcion='Masculino')
    s_f, _ = Sexo.objects.get_or_create(sexo='F', descripcion='Femenino')

    dep_ant, _ = Departamento.objects.get_or_create(codigo='05', departamento='Antioquia')
    mun_med, _ = Municipio.objects.get_or_create(codigo='05001', municipio='Medellín', departamento=dep_ant)
    
    # Roles
    roles_nombres = ['Administrador', 'Medico', 'Tecnico de Enfermeria', 'Bacteriologo', 'Auditor']
    roles_objs = {}
    for r_nom in roles_nombres:
        rol, _ = TipoUsuario.objects.get_or_create(tipo=r_nom)
        roles_objs[r_nom] = rol
        # Crear permiso genérico para el rol
        Permiso.objects.get_or_create(permiso=f"Acceso {r_nom}", tipo_usuario=rol)

    # Usuarios de prueba
    def create_user(username, role_name, p_nom, p_ape):
        u, created = Usuario.objects.get_or_create(
            username=username,
            defaults={
                'p_nombre': p_nom,
                'p_apellido': p_ape,
                'is_staff': True,
                'tipo_id': ti_cc,
                'numero_id': str(random.randint(1000000, 9999999)),
                'sexo': s_m if username != 'bacteriologo' else s_f,
                'municipio_residencia': mun_med,
            }
        )
        if created:
            u.set_password('admin123')
            u.save()
        
        # Asignar rol
        permiso = Permiso.objects.filter(tipo_usuario=roles_objs[role_name]).first()
        UsuarioXPermiso.objects.get_or_create(usuario=u, permiso=permiso)
        return u

    admin_user = create_user('admin', 'Administrador', 'Andres', 'Gomez')
    medico_user = create_user('medico', 'Medico', 'Juan', 'Perez')
    tec_user = create_user('tecnico', 'Tecnico de Enfermeria', 'Maria', 'Lopez')
    bac_user = create_user('bacteriologo', 'Bacteriologo', 'Elena', 'Rodriguez')

    # 3. Catálogos de Laboratorio
    print("Creando catálogos de laboratorio y CIE-10...")
    td_cc, _ = TipoDocumentoPaciente.objects.get_or_create(codigo='CC', descripcion='Cédula de Ciudadanía')
    sb_m, _ = SexoBiologico.objects.get_or_create(codigo='M', descripcion='Masculino')
    sb_f, _ = SexoBiologico.objects.get_or_create(codigo='F', descripcion='Femenino')

    # Estados
    eo_reg, _ = EstadoOrden.objects.get_or_create(nombre='Registrada')
    eo_adm, _ = EstadoOrden.objects.get_or_create(nombre='Admitida')
    eo_fin, _ = EstadoOrden.objects.get_or_create(nombre='Finalizada')

    ee_pen, _ = EstadoExamen.objects.get_or_create(nombre='Pendiente')
    ee_ana, _ = EstadoExamen.objects.get_or_create(nombre='En Análisis')
    ee_val, _ = EstadoExamen.objects.get_or_create(nombre='Validado')

    em_pen, _ = EstadoMuestra.objects.get_or_create(nombre='Pendiente')
    em_rec, _ = EstadoMuestra.objects.get_or_create(nombre='Recolectada')
    em_lab, _ = EstadoMuestra.objects.get_or_create(nombre='Recibida en Laboratorio')

    # CUPS y Parámetros
    cups_data = [
        ('903895', 'Hemoglobina [Hb]', [('Hemoglobina', 'g/dL', 12, 16, 7, 20)]),
        ('903866', 'Creatinina en suero', [('Creatinina', 'mg/dL', 0.7, 1.3, 0.4, 5.0)]),
        ('903859', 'Glucosa en suero', [('Glucosa', 'mg/dL', 70, 100, 40, 400)]),
        ('903439', 'Hormona Estimulante de la Tiroides [TSH]', [('TSH', 'uIU/mL', 0.4, 4.5, 0.1, 50)]),
    ]

    for c_cod, c_desc, params in cups_data:
        cups, _ = CatalogoCups.objects.get_or_create(codigo_cups=c_cod, descripcion=c_desc)
        for p_nom, p_uni, p_min, p_max, p_pan_min, p_pan_max in params:
            ParametroExamen.objects.get_or_create(
                cups=cups,
                nombre_parametro=p_nom,
                unidades_medida=p_uni,
                rango_referencia_minimo=p_min,
                rango_referencia_maximo=p_max,
                rango_panico_minimo=p_pan_min,
                rango_panico_maximo=p_pan_max
            )

    # CIE-10
    cie10_codes = [
        ('E109', 'Diabetes mellitus insulinodependiente sin complicaciones'),
        ('I10X', 'Hipertensión esencial (primaria)'),
        ('N189', 'Enfermedad renal crónica, no especificada'),
        ('Z000', 'Examen médico general'),
        ('R509', 'Fiebre, no especificada'),
    ]

    # 4. Datos de Pacientes y Órdenes
    print("Generando pacientes y órdenes reales...")
    pacientes_data = [
        ('10203040', 'Carlos', 'Alberto', 'Gomez', 'Restrepo', '1985-05-20', sb_m),
        ('20304050', 'Ana', 'Maria', 'Suarez', 'Velez', '1992-11-15', sb_f),
        ('30405060', 'Luis', 'Fernando', 'Torres', 'Marin', '1970-02-10', sb_m),
        ('40506070', 'Martha', 'Lucia', 'Rojas', 'Henao', '1965-08-30', sb_f),
    ]

    for doc, p1, p2, a1, a2, fnac, sex in pacientes_data:
        p = Paciente.objects.create(
            tipo_documento=td_cc,
            numero_documento=doc,
            primer_nombre=p1,
            segundo_nombre=p2,
            primer_apellido=a1,
            segundo_apellido=a2,
            fecha_nacimiento=fnac,
            sexo_biologico=sex,
            municipio_residencia=mun_med,
            departamento_residencia=dep_ant,
            regimen_salud='Contributivo',
            consentimiento_habeas_data=True
        )

        # Crear una orden para cada paciente
        cie = random.choice(cie10_codes)[0]
        orden = OrdenLaboratorio.objects.create(
            paciente=p,
            medico=medico_user,
            numero_orden=f"LAB-{date.today().strftime('%Y%m%d')}-{random.randint(1000, 9999)}",
            codigo_cie10=cie,
            estado_general=eo_adm,
            usuario_admite=tec_user,
            fecha_admision=timezone.now()
        )

        # Añadir exámenes a la orden
        selected_cups = random.sample(list(CatalogoCups.objects.all()), 2)
        for cups in selected_cups:
            ExamenSolicitado.objects.create(
                orden=orden,
                cups=cups,
                estado_examen=ee_pen
            )

    print("Inyección completada con éxito.")

if __name__ == "__main__":
    seed()
