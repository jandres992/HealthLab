import os
import sys

# Add the project directory to the python path
sys.path.append('/home/andres/aplicaciones/HealthLab')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'HealthLab.settings')

import django
django.setup()

from laboratorio.models import CatalogoCups, ParametroExamen, SexoBiologico

def run_seed():
    print("Iniciando parametrización de CUPS y parámetros para Colombia...")
    # 1. Sexos Biológicos
    sexo_m, _ = SexoBiologico.objects.get_or_create(codigo='M', defaults={'descripcion': 'Masculino'})
    sexo_f, _ = SexoBiologico.objects.get_or_create(codigo='F', defaults={'descripcion': 'Femenino'})

    # 2. Datos de CUPS y Parámetros
    data = [
        {
            "cups": "902207",
            "descripcion": "HEMOGRAMA I (HEMOGLOBINA HEMATOCRITO RECUENTO DE ERITROCITOS INDICES ERITROCITARIOS)",
            "parametros": [
                {
                    "nombre": "Hemoglobina", "unidades": "g/dL",
                    "rangos": [
                        {"sexo": sexo_m, "min": 13.0, "max": 17.0},
                        {"sexo": sexo_f, "min": 12.0, "max": 15.0}
                    ]
                },
                {
                    "nombre": "Hematocrito", "unidades": "%",
                    "rangos": [
                        {"sexo": sexo_m, "min": 40.0, "max": 50.0},
                        {"sexo": sexo_f, "min": 36.0, "max": 45.0}
                    ]
                },
                {
                    "nombre": "Eritrocitos", "unidades": "millones/uL",
                    "rangos": [
                        {"sexo": sexo_m, "min": 4.5, "max": 5.9},
                        {"sexo": sexo_f, "min": 4.0, "max": 5.2}
                    ]
                }
            ]
        },
        {
            "cups": "902209",
            "descripcion": "HEMOGRAMA III",
            "parametros": [
                {
                    "nombre": "Leucocitos", "unidades": "mil/uL",
                    "rangos": [
                        {"sexo": None, "min": 4.5, "max": 11.0}
                    ]
                },
                {
                    "nombre": "Neutrófilos", "unidades": "%",
                    "rangos": [
                        {"sexo": None, "min": 40.0, "max": 74.0}
                    ]
                },
                {
                    "nombre": "Linfocitos", "unidades": "%",
                    "rangos": [
                        {"sexo": None, "min": 19.0, "max": 48.0}
                    ]
                },
                {
                    "nombre": "Plaquetas", "unidades": "mil/uL",
                    "rangos": [
                        {"sexo": None, "min": 150.0, "max": 400.0}
                    ]
                }
            ]
        },
        {
            "cups": "903841",
            "descripcion": "GLUCOSA EN SUERO LCR U OTRO FLUIDO",
            "parametros": [
                {
                    "nombre": "Glucosa", "unidades": "mg/dL",
                    "rangos": [
                        {"sexo": None, "min": 70.0, "max": 100.0}
                    ]
                }
            ]
        },
        {
            "cups": "903825",
            "descripcion": "CREATININA EN SUERO U OTROS FLUIDOS",
            "parametros": [
                {
                    "nombre": "Creatinina", "unidades": "mg/dL",
                    "rangos": [
                        {"sexo": sexo_m, "min": 0.7, "max": 1.3},
                        {"sexo": sexo_f, "min": 0.6, "max": 1.1}
                    ]
                }
            ]
        },
        {
            "cups": "903856",
            "descripcion": "NITROGENO UREICO [BUN]",
            "parametros": [
                {
                    "nombre": "BUN", "unidades": "mg/dL",
                    "rangos": [
                        {"sexo": None, "min": 7.0, "max": 20.0}
                    ]
                }
            ]
        },
        {
            "cups": "903815",
            "descripcion": "COLESTEROL TOTAL",
            "parametros": [
                {
                    "nombre": "Colesterol Total", "unidades": "mg/dL",
                    "rangos": [
                        {"sexo": None, "min": 0.0, "max": 200.0}
                    ]
                }
            ]
        },
        {
            "cups": "903818",
            "descripcion": "COLESTEROL DE ALTA DENSIDAD [HDL]",
            "parametros": [
                {
                    "nombre": "HDL", "unidades": "mg/dL",
                    "rangos": [
                        {"sexo": sexo_m, "min": 40.0, "max": 100.0},
                        {"sexo": sexo_f, "min": 50.0, "max": 100.0}
                    ]
                }
            ]
        },
        {
            "cups": "903866",
            "descripcion": "TRIGLICERIDOS",
            "parametros": [
                {
                    "nombre": "Triglicéridos", "unidades": "mg/dL",
                    "rangos": [
                        {"sexo": None, "min": 0.0, "max": 150.0}
                    ]
                }
            ]
        },
        {
            "cups": "907106",
            "descripcion": "UROANALISIS CON SEDIMENTO Y DENSIDAD",
            "parametros": [
                {
                    "nombre": "Aspecto", "unidades": "",
                    "rangos": [{"sexo": None, "min": None, "max": None, "texto": "Límpido"}]
                },
                {
                    "nombre": "Color", "unidades": "",
                    "rangos": [{"sexo": None, "min": None, "max": None, "texto": "Amarillo"}]
                },
                {
                    "nombre": "Densidad", "unidades": "",
                    "rangos": [{"sexo": None, "min": 1.005, "max": 1.030}]
                },
                {
                    "nombre": "pH", "unidades": "",
                    "rangos": [{"sexo": None, "min": 4.5, "max": 8.0}]
                },
                {
                    "nombre": "Proteínas", "unidades": "",
                    "rangos": [{"sexo": None, "min": None, "max": None, "texto": "Negativo"}]
                },
                {
                    "nombre": "Glucosa en Orina", "unidades": "",
                    "rangos": [{"sexo": None, "min": None, "max": None, "texto": "Negativo"}]
                },
                {
                    "nombre": "Cetonas", "unidades": "",
                    "rangos": [{"sexo": None, "min": None, "max": None, "texto": "Negativo"}]
                },
                {
                    "nombre": "Sangre Oculta", "unidades": "",
                    "rangos": [{"sexo": None, "min": None, "max": None, "texto": "Negativo"}]
                },
                {
                    "nombre": "Leucocitos", "unidades": "x campo",
                    "rangos": [{"sexo": None, "min": 0.0, "max": 5.0}]
                },
                {
                    "nombre": "Hematíes", "unidades": "x campo",
                    "rangos": [{"sexo": None, "min": 0.0, "max": 3.0}]
                },
                {
                    "nombre": "Bacterias", "unidades": "",
                    "rangos": [{"sexo": None, "min": None, "max": None, "texto": "Escasas"}]
                }
            ]
        },
        {
            "cups": "906914",
            "descripcion": "PRUEBA DE EMBARAZO EN ORINA",
            "parametros": [
                {
                    "nombre": "GCH CUALITATIVA EN ORINA", "unidades": "",
                    "rangos": [{"sexo": sexo_f, "min": None, "max": None, "texto": "Negativo"}]
                }
            ]
        },
        {
            "cups": "903843",
            "descripcion": "HEMOGLOBINA GLICOSILADA (HBA1C)",
            "parametros": [
                {
                    "nombre": "HbA1c", "unidades": "%",
                    "rangos": [{"sexo": None, "min": 4.0, "max": 5.6}]
                }
            ]
        },
        {
            "cups": "903803",
            "descripcion": "ACIDO URICO",
            "parametros": [
                {
                    "nombre": "Ácido Úrico", "unidades": "mg/dL",
                    "rangos": [
                        {"sexo": sexo_m, "min": 3.4, "max": 7.0},
                        {"sexo": sexo_f, "min": 2.4, "max": 6.0}
                    ]
                }
            ]
        },
        {
            "cups": "904903",
            "descripcion": "HORMONA ESTIMULANTE DEL TIROIDES (TSH)",
            "parametros": [
                {
                    "nombre": "TSH", "unidades": "uUI/mL",
                    "rangos": [{"sexo": None, "min": 0.4, "max": 4.0}]
                }
            ]
        },
        {
            "cups": "906913",
            "descripcion": "PRUEBA DE EMBARAZO EN SUERO",
            "parametros": [
                {
                    "nombre": "GCH CUANTITATIVA EN SUERO", "unidades": "mUI/mL",
                    "rangos": [{"sexo": sexo_f, "min": 0.0, "max": 5.0}]
                }
            ]
        }
    ]

    total_cups = 0
    total_params = 0

    for item in data:
        cups_obj, created = CatalogoCups.objects.get_or_create(
            codigo_cups=item["cups"],
            defaults={"descripcion": item["descripcion"], "activo": True}
        )
        if created:
            total_cups += 1

        for param in item["parametros"]:
            for rango in param["rangos"]:
                # Use get_or_create to avoid duplicates if run multiple times
                p, p_created = ParametroExamen.objects.get_or_create(
                    cups=cups_obj,
                    nombre_parametro=param["nombre"],
                    sexo_aplica=rango.get("sexo"),
                    defaults={
                        "unidades_medida": param.get("unidades"),
                        "rango_referencia_minimo": rango.get("min"),
                        "rango_referencia_maximo": rango.get("max"),
                        "rango_texto": rango.get("texto"),
                    }
                )
                if p_created:
                    total_params += 1

    print(f"✅ Parametrización completada: {total_cups} CUPS nuevos creados, {total_params} rangos de parámetros registrados.")

if __name__ == '__main__':
    run_seed()
