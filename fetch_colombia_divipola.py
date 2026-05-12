import os
import django
import urllib.request
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'HealthLab.settings')
django.setup()

from usuarios.models import Departamento, Municipio

def seed_divipola_completa():
    print("Descargando base de datos completa de DIVIPOLA (Datos Abiertos Colombia)...")
    url = "https://www.datos.gov.co/resource/gdxc-w37w.json?$limit=2000"
    
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            
        print(f"Descargados {len(data)} registros. Procesando...")
        
        departamentos_cache = {}
        municipios_creados = 0
        
        for item in data:
            depto_codigo = item.get('cod_dpto')
            depto_nombre = item.get('dpto')
            muni_codigo = item.get('cod_mpio')
            muni_nombre = item.get('nom_mpio')
            
            if not all([depto_codigo, depto_nombre, muni_codigo, muni_nombre]):
                continue
                
            depto_codigo = depto_codigo.strip()
            depto_nombre = depto_nombre.strip()
            muni_codigo = muni_codigo.strip()
            muni_nombre = muni_nombre.strip()
            
            if depto_codigo not in departamentos_cache:
                depto_obj, created = Departamento.objects.get_or_create(
                    codigo=depto_codigo,
                    defaults={'departamento': depto_nombre}
                )
                departamentos_cache[depto_codigo] = depto_obj
            else:
                depto_obj = departamentos_cache[depto_codigo]
                
            muni_obj, created = Municipio.objects.get_or_create(
                codigo=muni_codigo,
                defaults={
                    'municipio': muni_nombre,
                    'departamento': depto_obj
                }
            )
            if created:
                municipios_creados += 1
                
        print(f"Población completada. Se crearon {municipios_creados} nuevos municipios.")
        print(f"Total de Departamentos: {Departamento.objects.count()}")
        print(f"Total de Municipios: {Municipio.objects.count()}")
        
    except Exception as e:
        print(f"Error al descargar o procesar los datos: {e}")

if __name__ == '__main__':
    seed_divipola_completa()
