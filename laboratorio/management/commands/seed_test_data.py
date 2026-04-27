"""
Comando de seed de datos de prueba para HealthLab LIMS.
Garantiza al menos 10 registros base por tabla principal,
incluyendo los nuevos modelos de las fases 1-6.
"""
from datetime import timedelta
from decimal import Decimal
from uuid import NAMESPACE_DNS, uuid5

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from laboratorio.models import (
    CatalogoCups,
    ConfiguracionEquipo,
    EstadoExamen,
    EstadoMuestra,
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
from usuarios.models import (
    Departamento,
    DispositivoConfianza,
    Municipio,
    Permiso,
    Sexo,
    TipoId,
    TipoUsuario,
    UsuarioXPermiso,
)

User = get_user_model()


class Command(BaseCommand):
    help = "Carga datos de prueba y garantiza al menos 10 registros base por tabla principal."

    def handle(self, *args, **options):
        with transaction.atomic():
            usuarios_data = self._seed_usuarios()
            laboratorio_data = self._seed_laboratorio(usuarios_data)
            self._stdout_counts()

        self.stdout.write(self.style.SUCCESS("Datos de prueba cargados correctamente."))
        self.stdout.write(
            "Usuarios creados/reutilizados: "
            f"{len(usuarios_data['usuarios'])}, "
            f"Pacientes creados/reutilizados: {len(laboratorio_data['pacientes'])}"
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Usuarios
    # ─────────────────────────────────────────────────────────────────────────

    def _seed_usuarios(self):
        # Nombres y datos de usuarios del personal médico colombiano
        personal_medico_data = [
            ("carlos_moreno", "Dr. Carlos", "", "Moreno", "García", "1965-10-15", "M", "1015234567", "300 325 4567"),
            ("maria_santos", "Dra. María", "del", "Santos", "López", "1972-05-22", "F", "1015234568", "300 325 4568"),
            ("fernando_ruiz", "Fernando", "", "Ruiz", "Martínez", "1968-08-30", "M", "1015234569", "300 325 4569"),
            ("sandra_vera", "Sandra", "Patricia", "Vera", "Ruiz", "1975-11-18", "F", "1015234570", "300 325 4570"),
            ("jorge_pena", "Jorge", "Alberto", "Peña", "Vásquez", "1970-03-12", "M", "1015234571", "300 325 4571"),
            ("helena_gomez", "Helena", "", "Gómez", "Sánchez", "1978-07-25", "F", "1015234572", "300 325 4572"),
            ("ricardo_flores", "Ricardo", "Javier", "Flores", "González", "1967-01-08", "M", "1015234573", "300 325 4573"),
            ("patricia_castro", "Patricia", "Rosa", "Castro", "Díaz", "1980-09-14", "F", "1015234574", "300 325 4574"),
            ("luis_torres", "Luis", "Carlos", "Torres", "Mendoza", "1969-06-20", "M", "1015234575", "300 325 4575"),
            ("catalina_ramirez", "Catalina", "", "Ramírez", "Herrera", "1976-12-03", "F", "1015234576", "300 325 4576"),
        ]
        
        tipos_id_data = [
            ("CC", "Cédula de ciudadanía"),
            ("TI", "Tarjeta de identidad"),
            ("CE", "Cédula de extranjería"),
            ("PA", "Pasaporte"),
            ("RC", "Registro civil"),
            ("PE", "Permiso especial"),
            ("PT", "Permiso temporal"),
            ("NU", "Número único"),
            ("AS", "Adulto sin identificación"),
            ("OT", "Otro documento"),
        ]
        tipos_id = []
        for tipo_id, detalle in tipos_id_data:
            obj, _ = TipoId.objects.update_or_create(
                tipo_id=tipo_id,
                defaults={"detalle": detalle, "estado": True},
            )
            tipos_id.append(obj)

        sexos_data = [
            ("F", "Femenino"), ("M", "Masculino"), ("I", "Intersexual"),
            ("N", "No especificado"), ("A", "Alterno 1"), ("B", "Alterno 2"),
            ("C", "Alterno 3"), ("D", "Alterno 4"), ("E", "Alterno 5"), ("G", "Alterno 6"),
        ]
        sexos = []
        sexos_dict = {}
        for codigo, descripcion in sexos_data:
            obj, _ = Sexo.objects.update_or_create(
                sexo=codigo, defaults={"descripcion": descripcion}
            )
            sexos.append(obj)
            sexos_dict[codigo] = obj

        # Departamentos reales de Colombia
        departamentos_reales = [
            ("05", "Antioquia"), ("08", "Atlántico"), ("11", "Bogotá, D.C."),
            ("13", "Bolívar"), ("15", "Boyacá"), ("17", "Caldas"),
            ("18", "Caquetá"), ("19", "Cauca"), ("20", "Cesar"),
            ("23", "Córdoba"),
        ]
        departamentos = []
        for codigo, nombre in departamentos_reales:
            obj, _ = Departamento.objects.update_or_create(
                codigo=codigo,
                defaults={"departamento": nombre},
            )
            departamentos.append(obj)

        # Municipios reales de Colombia
        municipios_reales = [
            ("05001", "Medellín", 0), ("05002", "Abejorral", 0), ("05003", "Abriaquí", 0),
            ("08001", "Barranquilla", 1), ("08002", "Polonuevo", 1), ("08003", "Ponedera", 1),
            ("11001", "Bogotá", 2), ("11002", "Soacha", 2), ("13001", "Cartagena", 3),
            ("23001", "Montería", 9),
        ]
        municipios = []
        for codigo, nombre, dep_idx in municipios_reales:
            obj, _ = Municipio.objects.update_or_create(
                codigo=codigo,
                defaults={"municipio": nombre, "departamento": departamentos[dep_idx]},
            )
            municipios.append(obj)

        # 5 roles del documento de requerimientos (Documento1.pdf)
        tipos_usuario = [
            ("Médico", "Personal médico autorizado para generar órdenes y consultar resultados"),
            ("Bacteriólogo", "Profesional de laboratorio que valida, firma y rechaza resultados"),
            ("Administrador", "Gestión integral del sistema, usuarios, equipos y configuración"),
            ("Técnico de Enfermería", "Flebotomista encargado de toma, etiquetado y trazabilidad de muestras"),
            ("Auditor", "Control de calidad, verificación CUPS, métricas y exportación RIPS"),
        ]
        tipos_usuario_objs = []
        for tipo, descripcion in tipos_usuario:
            obj, _ = TipoUsuario.objects.update_or_create(
                tipo=tipo,
                defaults={"descripcion": descripcion},
            )
            tipos_usuario_objs.append(obj)

        permisos = []
        for tipo_obj in tipos_usuario_objs:
            permiso_code = f"permiso_{tipo_obj.tipo.lower().replace(' ', '_')}"
            obj, _ = Permiso.objects.update_or_create(
                permiso=permiso_code,
                defaults={"tipo_usuario": tipo_obj},
            )
            permisos.append(obj)

        # Crear usuarios del personal médico
        usuarios = []
        for index, (username, p_nombre, s_nombre, p_apellido, s_apellido, f_nac, sexo_code, doc_id, telefono) in enumerate(personal_medico_data):
            obj, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": f"{username}@healthlab.local",
                    "tipo_id": tipos_id[0],  # CC
                    "numero_id": doc_id,
                    "p_nombre": p_nombre,
                    "s_nombre": s_nombre,
                    "p_apellido": p_apellido,
                    "s_apellido": s_apellido,
                    "f_nacimiento": f_nac,
                    "sexo": sexos_dict[sexo_code],
                    "municipio_residencia": municipios[index % len(municipios)],
                    "direccion_residencia": f"Calle {45 + index} # {20 + index * 5}-{80 + index * 3}",
                    "telefono": telefono,
                    "recibir_notificaciones": index % 2 == 0,
                    "is_active": True,
                },
            )
            if not created:
                obj.email = f"{username}@healthlab.local"
                obj.is_active = True
                obj.recibir_notificaciones = index % 2 == 0
                obj.save()
            obj.set_password("Prueba123*")
            obj.save()
            usuarios.append(obj)

        # Asignación de roles a usuarios de prueba según el documento:
        # 0,1 = Médico, 2,3 = Bacteriólogo, 4 = Administrador,
        # 5,6 = Técnico de Enfermería, 7,8 = Auditor, 9 = Administrador
        rol_map = {0: 0, 1: 0, 2: 1, 3: 1, 4: 2, 5: 3, 6: 3, 7: 4, 8: 4, 9: 2}
        for idx, usuario in enumerate(usuarios):
            permiso = permisos[rol_map[idx]]
            UsuarioXPermiso.objects.get_or_create(
                usuario=usuario,
                permiso=permiso,
            )

        for index in range(1, min(11, len(usuarios) + 1)):
            DispositivoConfianza.objects.update_or_create(
                usuario=usuarios[index - 1],
                device_id=f"device-{index:02d}",
                defaults={
                    "nombre": f"Dispositivo {index}",
                    "user_agent": f"HealthLab Mobile Test Agent {index}",
                    "es_confiable": True,
                },
            )

        return {
            "tipos_id": tipos_id, "sexos": sexos, "departamentos": departamentos,
            "municipios": municipios, "tipos_usuario": tipos_usuario_objs,
            "permisos": permisos, "usuarios": usuarios,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Laboratorio
    # ─────────────────────────────────────────────────────────────────────────

    def _seed_laboratorio(self, usuarios_data):
        usuarios = usuarios_data['usuarios']

        # ── Tipos de documento ────────────────────────────────────────────────
        tipo_documento_data = [
            ("CC", "Cedula de ciudadania"), ("TI", "Tarjeta de identidad"),
            ("CE", "Cedula de extranjeria"), ("PA", "Pasaporte"),
            ("RC", "Registro civil"), ("AS", "Adulto sin identificacion"),
            ("MS", "Menor sin identificacion"), ("PE", "Permiso especial"),
            ("PT", "Permiso temporal"), ("OT", "Otro documento"),
        ]
        tipos_documento = []
        for codigo, descripcion in tipo_documento_data:
            obj, _ = TipoDocumentoPaciente.objects.update_or_create(
                codigo=codigo, defaults={"descripcion": descripcion, "activo": True}
            )
            tipos_documento.append(obj)

        # ── Sexos biológicos ──────────────────────────────────────────────────
        sexos_data = [
            ("F", "Femenino"), ("M", "Masculino"), ("I", "Intersexual"),
            ("N", "No especificado"), ("A", "Alterno 1"), ("B", "Alterno 2"),
            ("C", "Alterno 3"), ("D", "Alterno 4"), ("E", "Alterno 5"), ("G", "Alterno 6"),
        ]
        sexos = []
        for codigo, descripcion in sexos_data:
            obj, _ = SexoBiologico.objects.update_or_create(
                codigo=codigo, defaults={"descripcion": descripcion}
            )
            sexos.append(obj)

        sexo_f = SexoBiologico.objects.get(codigo='F')
        sexo_m = SexoBiologico.objects.get(codigo='M')

        # ── Estados de orden ──────────────────────────────────────────────────
        estados_orden_data = [
            "Registrada", "En Toma de Muestra", "Muestra Recolectada",
            "En Proceso", "Pendiente Validacion", "Validada", "Finalizada",
            "Reportada", "Entregada", "Anulada",
        ]
        estados_orden = []
        for nombre in estados_orden_data:
            obj, _ = EstadoOrden.objects.update_or_create(
                nombre=nombre, defaults={"descripcion": f"Estado de orden: {nombre}"}
            )
            estados_orden.append(obj)

        # ── Estados de examen ─────────────────────────────────────────────────
        estados_examen_data = [
            "Pendiente", "Muestra Recolectada", "En Análisis", "Validado",
            "Reportado", "Entregado", "Repetir", "Anulado", "En Espera", "Archivado",
        ]
        estados_examen = []
        for nombre in estados_examen_data:
            obj, _ = EstadoExamen.objects.update_or_create(
                nombre=nombre, defaults={"descripcion": f"Estado de examen: {nombre}"}
            )
            estados_examen.append(obj)

        # ── Estados de muestra (FASE 3) ───────────────────────────────────────
        estados_muestra_data = [
            ("Recolectada", "Muestra tomada por el flebotomista"),
            ("Recibida en Laboratorio", "Ingresada al laboratorio central por el bacteriólogo"),
            ("En Proceso", "Siendo analizada en el equipo"),
            ("Rechazada", "Rechazada por condición inadecuada"),
            ("Almacenada", "Guardada en refrigeración pour revisión posterior"),
            ("Descartada", "Eliminada según protocolo de bioseguridad"),
            ("En Transporte", "En camino al laboratorio"),
            ("Pendiente Analisis", "Esperando turno de análisis"),
            ("Completada", "Análisis finalizado"),
            ("Repetir Toma", "Se requiere nueva extracción"),
        ]
        estados_muestra = []
        for nombre, descripcion in estados_muestra_data:
            obj, _ = EstadoMuestra.objects.update_or_create(
                nombre=nombre, defaults={"descripcion": descripcion}
            )
            estados_muestra.append(obj)

        # ── Catálogos CUPS y parámetros ───────────────────────────────────────
        # Parámetros con rangos diferenciados por sexo (FASE 1)
        parametros_base = [
            ("Leucocitos", "cel/uL", Decimal("4.000"), Decimal("11.000"), None),
            ("Hemoglobina", "g/dL", Decimal("12.000"), Decimal("16.000"), None),
            ("Hematocrito", "%", Decimal("36.000"), Decimal("48.000"), None),
            ("Plaquetas", "10^3/uL", Decimal("150.000"), Decimal("450.000"), None),
            ("Glucosa", "mg/dL", Decimal("70.000"), Decimal("100.000"), None),
            ("Creatinina", "mg/dL", Decimal("0.600"), Decimal("1.300"), None),
            ("Urea", "mg/dL", Decimal("15.000"), Decimal("40.000"), None),
            ("Colesterol", "mg/dL", Decimal("120.000"), Decimal("200.000"), None),
            ("Trigliceridos", "mg/dL", Decimal("0.000"), Decimal("150.000"), None),
            ("Proteinas", "g/dL", Decimal("6.000"), Decimal("8.300"), None),
        ]

        catalogos = []
        parametros = []
        for index in range(1, 11):
            cups, _ = CatalogoCups.objects.update_or_create(
                codigo_cups=f"90{index:04d}",
                defaults={"descripcion": f"Examen de prueba {index}", "activo": True},
            )
            catalogos.append(cups)

            nombre_p, unidad, minimo, maximo, rango_texto = parametros_base[index - 1]
            # Rango universal (sin sexo ni edad)
            param, _ = ParametroExamen.objects.get_or_create(
                cups=cups,
                nombre_parametro=nombre_p,
                sexo_aplica=None,
                edad_minima_anios=None,
                edad_maxima_anios=None,
                defaults={
                    "unidades_medida": unidad,
                    "rango_referencia_minimo": minimo,
                    "rango_referencia_maximo": maximo,
                    "rango_texto": rango_texto,
                },
            )
            parametros.append(param)

        # Ejemplo de rango diferenciado por sexo para Hemoglobina (FASE 1)
        cups_hemo = catalogos[1]  # Hemoglobina está en indice 1
        ParametroExamen.objects.get_or_create(
            cups=cups_hemo, nombre_parametro="Hemoglobina",
            sexo_aplica=sexo_m, edad_minima_anios=None, edad_maxima_anios=None,
            defaults={
                "unidades_medida": "g/dL",
                "rango_referencia_minimo": Decimal("13.500"),
                "rango_referencia_maximo": Decimal("17.500"),
                "rango_panico_minimo": Decimal("7.000"),
                "rango_panico_maximo": Decimal("20.000"),
            },
        )
        ParametroExamen.objects.get_or_create(
            cups=cups_hemo, nombre_parametro="Hemoglobina",
            sexo_aplica=sexo_f, edad_minima_anios=None, edad_maxima_anios=None,
            defaults={
                "unidades_medida": "g/dL",
                "rango_referencia_minimo": Decimal("12.000"),
                "rango_referencia_maximo": Decimal("16.000"),
                "rango_panico_minimo": Decimal("7.000"),
                "rango_panico_maximo": Decimal("20.000"),
            },
        )

        # ── Configuraciones de equipos (FASE 1) ───────────────────────────────
        equipos_data = [
            ("URIT-500C-01", "Hematología URIT-500C", "SERIAL", None, "9600", "ASTM"),
            ("MINDRAY-BC5000-01", "Hematología Mindray BC-5000", "TCP", "192.168.1.100", "5000", "HL7"),
            ("COBAS-C111-01", "Bioquímica Roche COBAS c111", "TCP", "192.168.1.101", "5001", "HL7"),
            ("SYSMEX-XN350-01", "Hematología Sysmex XN-350", "SERIAL", None, "9600", "ASTM"),
            ("DIRUI-H500-01", "Uroanálisis DIRUI H-500", "SERIAL", None, "9600", "CSV"),
            ("TOSOH-G11-01", "HbA1c Tosoh G11", "TCP", "192.168.1.102", "5002", "HL7"),
            ("URIT-3000-01", "Urina URIT-3000", "SERIAL", None, "19200", "ASTM"),
            ("MINDRAY-BS800-01", "Bioquímica Mindray BS-800", "TCP", "192.168.1.103", "5003", "HL7"),
            ("ROCHE-COMPACT-01", "Coagulación Roche Compact", "SERIAL", None, "9600", "ASTM"),
            ("BIOBASE-BK200-01", "Bioquímica Biobase BK-200", "TCP", "192.168.1.104", "5004", "JSON"),
        ]
        for codigo, nombre, tipo, ip, puerto, protocolo in equipos_data:
            ConfiguracionEquipo.objects.update_or_create(
                codigo_equipo=codigo,
                defaults={
                    "nombre": nombre,
                    "tipo_conexion": tipo,
                    "host_ip": ip,
                    "puerto": puerto,
                    "protocolo": protocolo,
                    "activo": True,
                },
            )

        # ── Pacientes con nombres reales colombianos ──────────────────────────
        pacientes_data = [
            ("Juan", "Diego", "García", "López", "87654321", "1985-03-15", "M", "300 555 1234"),
            ("María", "Alejandra", "Rodríguez", "Martínez", "87654322", "1992-07-22", "F", "300 555 1235"),
            ("Carlos", "Andrés", "Sánchez", "Gómez", "87654323", "1978-11-08", "M", "300 555 1236"),
            ("Rosa", "María", "Pérez", "Vásquez", "87654324", "1995-05-30", "F", "300 555 1237"),
            ("Luis", "Fernando", "López", "Ruiz", "87654325", "1980-09-18", "M", "300 555 1238"),
            ("Catalina", "Marcela", "González", "Díaz", "87654326", "1988-01-25", "F", "300 555 1239"),
            ("José", "Miguel", "Hernández", "Ramírez", "87654327", "1975-06-12", "M", "300 555 1240"),
            ("Patricia", "Inés", "Flores", "Herrera", "87654328", "1990-10-20", "F", "300 555 1241"),
            ("Francisco", "Alberto", "Torres", "Mendoza", "87654329", "1982-02-14", "M", "300 555 1242"),
            ("Silvia", "Del Carmen", "Vargas", "Gutiérrez", "87654330", "1987-08-09", "F", "300 555 1243"),
        ]
        pacientes = []
        for index, (p_nombre, s_nombre, p_apellido, s_apellido, doc_id, f_nac, sexo_code, tel) in enumerate(pacientes_data):
            paciente_id = uuid5(NAMESPACE_DNS, f"healthlab-paciente-{doc_id}")
            paciente, _ = Paciente.objects.update_or_create(
                id=paciente_id,
                defaults={
                    "tipo_documento": tipos_documento[0],  # CC
                    "numero_documento": doc_id,
                    "primer_nombre": p_nombre,
                    "segundo_nombre": s_nombre,
                    "primer_apellido": p_apellido,
                    "segundo_apellido": s_apellido,
                    "fecha_nacimiento": f_nac,
                    "sexo_biologico": sexo_m if sexo_code == "M" else sexo_f,
                    "telefono": tel,
                    "correo_electronico": f"{p_nombre.lower()}.{p_apellido.lower()}@email.com",
                    "activo": True,
                },
            )
            pacientes.append(paciente)

        # ── Órdenes de laboratorio con datos clínicos reales ─────────────────
        diagnosticos_cie10 = [
            ("E11.9", "Diabetes mellitus tipo 2 sin complicaciones"),
            ("I10.9", "Hipertensión esencial"),
            ("J45.9", "Asma, no especificada"),
            ("M79.3", "Miositis, no especificada"),
            ("N18.3", "Enfermedad renal crónica estadio 3"),
            ("B20", "Enfermedad por VIH"),
            ("C34.9", "Neoplasia maligna de pulmón, no especificada"),
            ("F41.1", "Trastorno de ansiedad generalizada"),
            ("D53.9", "Deficiencia de nutrientes, no especificada"),
            ("I21.9", "Infarto agudo de miocardio, no especificado"),
        ]
        
        convenios_afiliacion = ["EPS SURA", "EPS COOMEVA", "EPS SANITAS", "Particular", "EPS SALUD BOLÍVAR"]
        
        ordenamientos_clinicos = [
            "Chequeo general de salud",
            "Control de diabetes mellitus",
            "Evaluación por hipertensión arterial",
            "Seguimiento post-operatorio",
            "Evaluación preoperatoria",
            "Sospecha de infección",
            "Solicitud flebotomía para hemograma",
            "Tamizaje de enfermedades crónicas",
            "Validación de diagnóstico clínico",
            "Revisión de perfil lipídico",
        ]
        
        estado_registrada = EstadoOrden.objects.get(nombre="Registrada")
        medico_demo = usuarios[0]  # Using first medical user
        ordenes = []
        for index in range(1, 11):
            orden_id = uuid5(NAMESPACE_DNS, f"healthlab-orden-{index}")
            codigo_cie10, _ = diagnosticos_cie10[index - 1]
            orden, _ = OrdenLaboratorio.objects.update_or_create(
                id=orden_id,
                defaults={
                    "paciente": pacientes[index - 1],
                    "medico": medico_demo,
                    "numero_orden": f"LAB-20260319-{index:04d}",
                    "observaciones_clinicas": ordenamientos_clinicos[index - 1],
                    "estado_general": estado_registrada,
                    "codigo_cie10": codigo_cie10,
                    "entidad_remitente": f"Clínica Metropolitana de Medellín" if index % 2 else "Centro de Salud Municipal",
                    "convenio": convenios_afiliacion[index % len(convenios_afiliacion)],
                },
            )
            ordenes.append(orden)

        # ── Muestras físicas (con estado y usuario_recolecta) — FASE 3 ────────
        estado_recolectada = EstadoMuestra.objects.get(nombre="Recolectada")
        flebotomista = usuarios[1]
        muestras = []
        for index in range(1, 11):
            muestra_id = uuid5(NAMESPACE_DNS, f"healthlab-muestra-{index}")
            muestra, _ = MuestraFisica.objects.update_or_create(
                id=muestra_id,
                defaults={
                    "orden": ordenes[index - 1],
                    "codigo_barras": f"MUE-TEST-{index:04d}",
                    "tipo_muestra": "Sangre Total" if index % 2 else "Suero",
                    "fecha_recoleccion": timezone.now() - timedelta(hours=index),
                    "estado_muestra": estado_recolectada,
                    "usuario_recolecta": flebotomista,
                    "condicion_muestra": "Normal",
                },
            )
            muestras.append(muestra)

        # ── Exámenes solicitados ──────────────────────────────────────────────
        estado_pendiente = EstadoExamen.objects.get(nombre="Pendiente")
        examenes = []
        for index in range(1, 11):
            examen_id = uuid5(NAMESPACE_DNS, f"healthlab-examen-{index}")
            examen, _ = ExamenSolicitado.objects.update_or_create(
                id=examen_id,
                defaults={
                    "orden": ordenes[index - 1],
                    "cups": catalogos[index - 1],
                    "muestra": muestras[index - 1],
                    "estado_examen": estado_pendiente,
                },
            )
            examenes.append(examen)

        # ── Lecturas seriales con valores clínicos realistas ──────────────────
        valores_clinicos_realistas = [
            Decimal("8.5"),    # Leucocitos: dentro del rango
            Decimal("14.2"),   # Hemoglobina: dentro del rango
            Decimal("42.1"),   # Hematocrito: dentro del rango
            Decimal("245.0"),  # Plaquetas: dentro del rango
            Decimal("105.3"),  # Glucosa: ligeramente elevada
            Decimal("0.95"),   # Creatinina: dentro del rango
            Decimal("32.5"),   # Urea: dentro del rango
            Decimal("195.8"),  # Colesterol: dentro del rango
            Decimal("128.4"),  # Triglicéridos: dentro del rango
            Decimal("7.2"),    # Proteínas: dentro del rango
        ]
        
        lecturas = []
        for index in range(1, 11):
            lectura_id = uuid5(NAMESPACE_DNS, f"healthlab-lectura-{index}")
            parametro = parametros[index - 1]
            valor = valores_clinicos_realistas[index - 1]
            lectura, _ = LecturaEquipoSerial.objects.update_or_create(
                id=lectura_id,
                defaults={
                    "equipo_origen": f"Analizador Hematológico {index % 3 + 1}",
                    "codigo_barras_leido": muestras[index - 1].codigo_barras,
                    "trama_cruda": f"RAW|{muestras[index - 1].codigo_barras}|{parametro.nombre_parametro}|{valor}",
                    "datos_json": {parametro.nombre_parametro: str(valor)},
                    "procesado": True,
                },
            )
            lecturas.append(lectura)

        # ── Resultados de analitos con análisis clínico ───────────────────────
        resultados = []
        valores_anormales_indices = [4]  # Solo glucosa (índice 4) será anormal
        for index in range(1, 11):
            parametro = parametros[index - 1]
            valor = valores_clinicos_realistas[index - 1]
            es_anormal_flag = index - 1 in valores_anormales_indices
            
            resultado, _ = ResultadoAnalito.objects.update_or_create(
                examen_solicitado=examenes[index - 1],
                parametro=parametro,
                defaults={
                    "lectura_serial": lecturas[index - 1],
                    "valor_resultado": str(valor),
                    "es_anormal": es_anormal_flag,
                    "es_critico": False,
                    "comentario_bacteriologo": "Resultado dentro de los límites normales" if not es_anormal_flag else "Glucosa elevada - requiere seguimiento",
                },
            )
            resultados.append(resultado)

        return {
            "tipos_documento": tipos_documento, "sexos": sexos,
            "estados_orden": estados_orden, "estados_examen": estados_examen,
            "estados_muestra": estados_muestra, "catalogos": catalogos,
            "parametros": parametros, "pacientes": pacientes,
            "ordenes": ordenes, "muestras": muestras,
            "examenes": examenes, "lecturas": lecturas, "resultados": resultados,
        }

    # ─────────────────────────────────────────────────────────────────────────

    def _stdout_counts(self):
        from laboratorio.models import (  # noqa: PLC0415
            CatalogoCups, ConfiguracionEquipo, EstadoExamen, EstadoMuestra,
            EstadoOrden, ExamenSolicitado, LecturaEquipoSerial, MuestraFisica,
            OrdenLaboratorio, Paciente, ParametroExamen, ResultadoAnalito,
            SexoBiologico, TipoDocumentoPaciente,
        )
        modelos = [
            ("laboratorio.TipoDocumentoPaciente", TipoDocumentoPaciente),
            ("laboratorio.SexoBiologico", SexoBiologico),
            ("laboratorio.EstadoOrden", EstadoOrden),
            ("laboratorio.EstadoExamen", EstadoExamen),
            ("laboratorio.EstadoMuestra", EstadoMuestra),
            ("laboratorio.CatalogoCups", CatalogoCups),
            ("laboratorio.ParametroExamen", ParametroExamen),
            ("laboratorio.ConfiguracionEquipo", ConfiguracionEquipo),
            ("laboratorio.Paciente", Paciente),
            ("laboratorio.OrdenLaboratorio", OrdenLaboratorio),
            ("laboratorio.MuestraFisica", MuestraFisica),
            ("laboratorio.ExamenSolicitado", ExamenSolicitado),
            ("laboratorio.LecturaEquipoSerial", LecturaEquipoSerial),
            ("laboratorio.ResultadoAnalito", ResultadoAnalito),
            ("usuarios.TipoId", TipoId),
            ("usuarios.Sexo", Sexo),
            ("usuarios.Departamento", Departamento),
            ("usuarios.Municipio", Municipio),
            ("usuarios.Usuario", User),
            ("usuarios.TipoUsuario", TipoUsuario),
            ("usuarios.Permiso", Permiso),
            ("usuarios.UsuarioXPermiso", UsuarioXPermiso),
            ("usuarios.DispositivoConfianza", DispositivoConfianza),
        ]
        for nombre, modelo in modelos:
            self.stdout.write(f"{nombre}: {modelo.objects.count()}")
