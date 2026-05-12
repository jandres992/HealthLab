import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'HealthLab.settings')
django.setup()

from usuarios.serializers import DepartamentoSerializer
from usuarios.models import Departamento

print(DepartamentoSerializer(Departamento.objects.all(), many=True).data)
