import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'HealthLab.settings')
django.setup()

from usuarios.models import Departamento, Municipio

def seed_colombia():
    print("Iniciando carga de DIVIPOLA Colombia...")

    # 32 Departamentos de Colombia
    departamentos = [
        {"codigo": "91", "nombre": "Amazonas"},
        {"codigo": "05", "nombre": "Antioquia"},
        {"codigo": "81", "nombre": "Arauca"},
        {"codigo": "08", "nombre": "Atlántico"},
        {"codigo": "11", "nombre": "Bogotá, D.C."},
        {"codigo": "13", "nombre": "Bolívar"},
        {"codigo": "15", "nombre": "Boyacá"},
        {"codigo": "17", "nombre": "Caldas"},
        {"codigo": "18", "nombre": "Caquetá"},
        {"codigo": "85", "nombre": "Casanare"},
        {"codigo": "19", "nombre": "Cauca"},
        {"codigo": "20", "nombre": "Cesar"},
        {"codigo": "27", "nombre": "Chocó"},
        {"codigo": "23", "nombre": "Córdoba"},
        {"codigo": "25", "nombre": "Cundinamarca"},
        {"codigo": "94", "nombre": "Guainía"},
        {"codigo": "95", "nombre": "Guaviare"},
        {"codigo": "41", "nombre": "Huila"},
        {"codigo": "44", "nombre": "La Guajira"},
        {"codigo": "47", "nombre": "Magdalena"},
        {"codigo": "50", "nombre": "Meta"},
        {"codigo": "52", "nombre": "Nariño"},
        {"codigo": "54", "nombre": "Norte de Santander"},
        {"codigo": "86", "nombre": "Putumayo"},
        {"codigo": "63", "nombre": "Quindío"},
        {"codigo": "66", "nombre": "Risaralda"},
        {"codigo": "88", "nombre": "Archipiélago de San Andrés, Providencia y Santa Catalina"},
        {"codigo": "68", "nombre": "Santander"},
        {"codigo": "70", "nombre": "Sucre"},
        {"codigo": "73", "nombre": "Tolima"},
        {"codigo": "76", "nombre": "Valle del Cauca"},
        {"codigo": "97", "nombre": "Vaupés"},
        {"codigo": "99", "nombre": "Vichada"}
    ]

    for d in departamentos:
        obj, created = Departamento.objects.get_or_create(
            codigo=d["codigo"],
            defaults={"departamento": d["nombre"]}
        )
        if created:
            print(f"Departamento creado: {d['nombre']}")

    # Ciudades Capitales y Principales (Muestra representativa)
    municipios = [
        {"codigo": "91001", "nombre": "Leticia", "depto_codigo": "91"},
        {"codigo": "05001", "nombre": "Medellín", "depto_codigo": "05"},
        {"codigo": "05088", "nombre": "Bello", "depto_codigo": "05"},
        {"codigo": "05360", "nombre": "Itagüí", "depto_codigo": "05"},
        {"codigo": "05266", "nombre": "Envigado", "depto_codigo": "05"},
        {"codigo": "81001", "nombre": "Arauca", "depto_codigo": "81"},
        {"codigo": "08001", "nombre": "Barranquilla", "depto_codigo": "08"},
        {"codigo": "08758", "nombre": "Soledad", "depto_codigo": "08"},
        {"codigo": "11001", "nombre": "Bogotá, D.C.", "depto_codigo": "11"},
        {"codigo": "13001", "nombre": "Cartagena de Indias", "depto_codigo": "13"},
        {"codigo": "15001", "nombre": "Tunja", "depto_codigo": "15"},
        {"codigo": "17001", "nombre": "Manizales", "depto_codigo": "17"},
        {"codigo": "18001", "nombre": "Florencia", "depto_codigo": "18"},
        {"codigo": "85001", "nombre": "Yopal", "depto_codigo": "85"},
        {"codigo": "19001", "nombre": "Popayán", "depto_codigo": "19"},
        {"codigo": "20001", "nombre": "Valledupar", "depto_codigo": "20"},
        {"codigo": "27001", "nombre": "Quibdó", "depto_codigo": "27"},
        {"codigo": "23001", "nombre": "Montería", "depto_codigo": "23"},
        {"codigo": "25001", "nombre": "Agua de Dios", "depto_codigo": "25"},
        {"codigo": "25754", "nombre": "Soacha", "depto_codigo": "25"},
        {"codigo": "25175", "nombre": "Chía", "depto_codigo": "25"},
        {"codigo": "94001", "nombre": "Inírida", "depto_codigo": "94"},
        {"codigo": "95001", "nombre": "San José del Guaviare", "depto_codigo": "95"},
        {"codigo": "41001", "nombre": "Neiva", "depto_codigo": "41"},
        {"codigo": "44001", "nombre": "Riohacha", "depto_codigo": "44"},
        {"codigo": "47001", "nombre": "Santa Marta", "depto_codigo": "47"},
        {"codigo": "50001", "nombre": "Villavicencio", "depto_codigo": "50"},
        {"codigo": "52001", "nombre": "Pasto", "depto_codigo": "52"},
        {"codigo": "54001", "nombre": "San José de Cúcuta", "depto_codigo": "54"},
        {"codigo": "86001", "nombre": "Mocoa", "depto_codigo": "86"},
        {"codigo": "63001", "nombre": "Armenia", "depto_codigo": "63"},
        {"codigo": "66001", "nombre": "Pereira", "depto_codigo": "66"},
        {"codigo": "88001", "nombre": "San Andrés", "depto_codigo": "88"},
        {"codigo": "68001", "nombre": "Bucaramanga", "depto_codigo": "68"},
        {"codigo": "68276", "nombre": "Floridablanca", "depto_codigo": "68"},
        {"codigo": "70001", "nombre": "Sincelejo", "depto_codigo": "70"},
        {"codigo": "73001", "nombre": "Ibagué", "depto_codigo": "73"},
        {"codigo": "76001", "nombre": "Cali", "depto_codigo": "76"},
        {"codigo": "76520", "nombre": "Palmira", "depto_codigo": "76"},
        {"codigo": "76111", "nombre": "Buga", "depto_codigo": "76"},
        {"codigo": "76834", "nombre": "Tuluá", "depto_codigo": "76"},
        {"codigo": "76109", "nombre": "Buenaventura", "depto_codigo": "76"},
        {"codigo": "97001", "nombre": "Mitú", "depto_codigo": "97"},
        {"codigo": "99001", "nombre": "Puerto Carreño", "depto_codigo": "99"}
    ]

    for m in municipios:
        try:
            depto = Departamento.objects.get(codigo=m["depto_codigo"])
            obj, created = Municipio.objects.get_or_create(
                codigo=m["codigo"],
                defaults={"municipio": m["nombre"], "departamento": depto}
            )
            if created:
                print(f"  Municipio creado: {m['nombre']} ({depto.departamento})")
        except Departamento.DoesNotExist:
            print(f"  Error: Departamento {m['depto_codigo']} no existe.")

    print("Población de base de datos terminada.")

if __name__ == '__main__':
    seed_colombia()
