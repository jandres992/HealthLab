from datetime import timedelta
from decimal import Decimal
from uuid import NAMESPACE_DNS, uuid5

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from laboratorio.models import (
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
            laboratorio_data = self._seed_laboratorio()
            self._stdout_counts()

        self.stdout.write(self.style.SUCCESS("Datos de prueba cargados correctamente."))
        self.stdout.write(
            "Usuarios creados/reutilizados: "
            f"{len(usuarios_data['usuarios'])}, Pacientes creados/reutilizados: {len(laboratorio_data['pacientes'])}"
        )

    def _seed_usuarios(self):
        tipos_id_data = [
            ("CC", "Cedula de ciudadania"),
            ("TI", "Tarjeta de identidad"),
            ("CE", "Cedula de extranjeria"),
            ("PA", "Pasaporte"),
            ("RC", "Registro civil"),
            ("PE", "Permiso especial"),
            ("PT", "Permiso temporal"),
            ("NU", "Numero unico"),
            ("AS", "Adulto sin identificacion"),
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
            ("F", "Femenino"),
            ("M", "Masculino"),
            ("I", "Intersexual"),
            ("N", "No especificado"),
            ("A", "Alterno 1"),
            ("B", "Alterno 2"),
            ("C", "Alterno 3"),
            ("D", "Alterno 4"),
            ("E", "Alterno 5"),
            ("G", "Alterno 6"),
        ]
        sexos = []
        for codigo, descripcion in sexos_data:
            obj, _ = Sexo.objects.update_or_create(
                sexo=codigo,
                defaults={"descripcion": descripcion},
            )
            sexos.append(obj)

        departamentos = []
        for index in range(1, 11):
            obj, _ = Departamento.objects.update_or_create(
                codigo=f"DEP{index:02d}",
                defaults={"departamento": f"Departamento {index}"},
            )
            departamentos.append(obj)

        municipios = []
        for index in range(1, 11):
            obj, _ = Municipio.objects.update_or_create(
                codigo=f"MUN{index:02d}",
                defaults={
                    "municipio": f"Municipio {index}",
                    "departamento": departamentos[index - 1],
                },
            )
            municipios.append(obj)

        tipos_usuario = []
        for index in range(1, 11):
            obj, _ = TipoUsuario.objects.update_or_create(
                tipo=f"Rol {index}",
                defaults={"descripcion": f"Perfil operativo de prueba {index}"},
            )
            tipos_usuario.append(obj)

        permisos = []
        for index in range(1, 11):
            obj, _ = Permiso.objects.update_or_create(
                permiso=f"permiso_{index:02d}",
                defaults={"tipo_usuario": tipos_usuario[index - 1]},
            )
            permisos.append(obj)

        usuarios = []
        for index in range(1, 11):
            username = f"usuario_prueba_{index:02d}"
            obj, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": f"usuario{index:02d}@healthlab.local",
                    "tipo_id": tipos_id[(index - 1) % len(tipos_id)],
                    "numero_id": f"10{index:08d}",
                    "p_nombre": f"Nombre{index}",
                    "s_nombre": f"Segundo{index}",
                    "p_apellido": f"Apellido{index}",
                    "s_apellido": f"Prueba{index}",
                    "f_nacimiento": timezone.now().date() - timedelta(days=9000 + index * 30),
                    "sexo": sexos[(index - 1) % len(sexos)],
                    "municipio_residencia": municipios[(index - 1) % len(municipios)],
                    "direccion_residencia": f"Calle {index} # {index + 10}-45",
                    "telefono": f"300000{index:04d}",
                    "recibir_notificaciones": index % 2 == 0,
                    "is_active": True,
                },
            )
            if not created:
                obj.email = f"usuario{index:02d}@healthlab.local"
                obj.tipo_id = tipos_id[(index - 1) % len(tipos_id)]
                obj.numero_id = f"10{index:08d}"
                obj.p_nombre = f"Nombre{index}"
                obj.s_nombre = f"Segundo{index}"
                obj.p_apellido = f"Apellido{index}"
                obj.s_apellido = f"Prueba{index}"
                obj.f_nacimiento = timezone.now().date() - timedelta(days=9000 + index * 30)
                obj.sexo = sexos[(index - 1) % len(sexos)]
                obj.municipio_residencia = municipios[(index - 1) % len(municipios)]
                obj.direccion_residencia = f"Calle {index} # {index + 10}-45"
                obj.telefono = f"300000{index:04d}"
                obj.recibir_notificaciones = index % 2 == 0
                obj.is_active = True
            obj.set_password("Prueba123*")
            obj.save()
            usuarios.append(obj)

        for index in range(1, 11):
            UsuarioXPermiso.objects.get_or_create(
                usuario=usuarios[index - 1],
                permiso=permisos[index - 1],
            )

        for index in range(1, 11):
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
            "tipos_id": tipos_id,
            "sexos": sexos,
            "departamentos": departamentos,
            "municipios": municipios,
            "tipos_usuario": tipos_usuario,
            "permisos": permisos,
            "usuarios": usuarios,
        }

    def _seed_laboratorio(self):
        tipo_documento_data = [
            ("CC", "Cedula de ciudadania"),
            ("TI", "Tarjeta de identidad"),
            ("CE", "Cedula de extranjeria"),
            ("PA", "Pasaporte"),
            ("RC", "Registro civil"),
            ("AS", "Adulto sin identificacion"),
            ("MS", "Menor sin identificacion"),
            ("PE", "Permiso especial"),
            ("PT", "Permiso temporal"),
            ("OT", "Otro documento"),
        ]
        tipos_documento = []
        for codigo, descripcion in tipo_documento_data:
            obj, _ = TipoDocumentoPaciente.objects.update_or_create(
                codigo=codigo,
                defaults={"descripcion": descripcion, "activo": True},
            )
            tipos_documento.append(obj)

        sexos_data = [
            ("F", "Femenino"),
            ("M", "Masculino"),
            ("I", "Intersexual"),
            ("N", "No especificado"),
            ("A", "Alterno 1"),
            ("B", "Alterno 2"),
            ("C", "Alterno 3"),
            ("D", "Alterno 4"),
            ("E", "Alterno 5"),
            ("G", "Alterno 6"),
        ]
        sexos = []
        for codigo, descripcion in sexos_data:
            obj, _ = SexoBiologico.objects.update_or_create(
                codigo=codigo,
                defaults={"descripcion": descripcion},
            )
            sexos.append(obj)

        estados_orden_data = [
            "Registrada",
            "En Toma de Muestra",
            "Muestra Recolectada",
            "En Proceso",
            "Pendiente Validacion",
            "Validada",
            "Reportada",
            "Entregada",
            "Anulada",
            "Archivada",
        ]
        estados_orden = []
        for nombre in estados_orden_data:
            obj, _ = EstadoOrden.objects.update_or_create(
                nombre=nombre,
                defaults={"descripcion": f"Estado de orden {nombre}"},
            )
            estados_orden.append(obj)

        estados_examen_data = [
            "Pendiente",
            "Muestra Recolectada",
            "En Análisis",
            "Validado",
            "Reportado",
            "Entregado",
            "Repetir",
            "Anulado",
            "En Espera",
            "Archivado",
        ]
        estados_examen = []
        for nombre in estados_examen_data:
            obj, _ = EstadoExamen.objects.update_or_create(
                nombre=nombre,
                defaults={"descripcion": f"Estado de examen {nombre}"},
            )
            estados_examen.append(obj)

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
                defaults={
                    "descripcion": f"Examen de prueba {index}",
                    "activo": True,
                },
            )
            catalogos.append(cups)

            nombre_parametro, unidad, minimo, maximo, rango_texto = parametros_base[index - 1]
            parametro, _ = ParametroExamen.objects.update_or_create(
                cups=cups,
                nombre_parametro=nombre_parametro,
                defaults={
                    "unidades_medida": unidad,
                    "rango_referencia_minimo": minimo,
                    "rango_referencia_maximo": maximo,
                    "rango_texto": rango_texto,
                },
            )
            parametros.append(parametro)

        pacientes = []
        for index in range(1, 11):
            paciente_id = uuid5(NAMESPACE_DNS, f"healthlab-paciente-{index}")
            paciente, _ = Paciente.objects.update_or_create(
                id=paciente_id,
                defaults={
                    "tipo_documento": tipos_documento[(index - 1) % len(tipos_documento)],
                    "numero_documento": f"20{index:08d}",
                    "primer_nombre": f"Paciente{index}",
                    "segundo_nombre": f"Demo{index}",
                    "primer_apellido": f"Apellido{index}",
                    "segundo_apellido": f"Clinico{index}",
                    "fecha_nacimiento": timezone.now().date() - timedelta(days=7000 + index * 40),
                    "sexo_biologico": sexos[(index - 1) % len(sexos)],
                    "telefono": f"310000{index:04d}",
                    "correo_electronico": f"paciente{index:02d}@healthlab.local",
                    "activo": True,
                },
            )
            pacientes.append(paciente)

        estado_registrada = EstadoOrden.objects.get(nombre="Registrada")
        ordenes = []
        for index in range(1, 11):
            orden_id = uuid5(NAMESPACE_DNS, f"healthlab-orden-{index}")
            orden, _ = OrdenLaboratorio.objects.update_or_create(
                id=orden_id,
                defaults={
                    "paciente": pacientes[index - 1],
                    "numero_orden": f"ORD-{index:05d}",
                    "observaciones_clinicas": f"Observacion clinica de prueba {index}",
                    "estado_general": estado_registrada,
                },
            )
            ordenes.append(orden)

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
                },
            )
            muestras.append(muestra)

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

        lecturas = []
        for index in range(1, 11):
            lectura_id = uuid5(NAMESPACE_DNS, f"healthlab-lectura-{index}")
            parametro = parametros[index - 1]
            valor = parametro.rango_referencia_minimo + Decimal("1.000")
            lectura, _ = LecturaEquipoSerial.objects.update_or_create(
                id=lectura_id,
                defaults={
                    "equipo_origen": f"Analizador Demo {index}",
                    "codigo_barras_leido": muestras[index - 1].codigo_barras,
                    "trama_cruda": f"RAW|{muestras[index - 1].codigo_barras}|{parametro.nombre_parametro}|{valor}",
                    "datos_json": {parametro.nombre_parametro: str(valor)},
                    "procesado": True,
                },
            )
            lecturas.append(lectura)

        resultados = []
        for index in range(1, 11):
            parametro = parametros[index - 1]
            valor = parametro.rango_referencia_minimo + Decimal("1.000")
            resultado, _ = ResultadoAnalito.objects.update_or_create(
                examen_solicitado=examenes[index - 1],
                parametro=parametro,
                defaults={
                    "lectura_serial": lecturas[index - 1],
                    "valor_resultado": str(valor),
                    "es_anormal": False,
                },
            )
            resultados.append(resultado)

        return {
            "tipos_documento": tipos_documento,
            "sexos": sexos,
            "estados_orden": estados_orden,
            "estados_examen": estados_examen,
            "catalogos": catalogos,
            "parametros": parametros,
            "pacientes": pacientes,
            "ordenes": ordenes,
            "muestras": muestras,
            "examenes": examenes,
            "lecturas": lecturas,
            "resultados": resultados,
        }

    def _stdout_counts(self):
        modelos = [
            ("laboratorio.TipoDocumentoPaciente", TipoDocumentoPaciente),
            ("laboratorio.SexoBiologico", SexoBiologico),
            ("laboratorio.EstadoOrden", EstadoOrden),
            ("laboratorio.EstadoExamen", EstadoExamen),
            ("laboratorio.CatalogoCups", CatalogoCups),
            ("laboratorio.ParametroExamen", ParametroExamen),
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
