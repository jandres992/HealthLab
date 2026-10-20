"""Escala los valores críticos sin acuse (RF-54.1). Programar cada 5 minutos (cron / tarea)."""
from django.core.management.base import BaseCommand

from laboratorio.services.criticos import MINUTOS_ESCALADO, escalar_pendientes


class Command(BaseCommand):
    help = 'Notifica y marca los valores críticos que llevan más de N minutos sin acuse.'

    def add_arguments(self, parser):
        parser.add_argument('--minutos', type=int, default=MINUTOS_ESCALADO)

    def handle(self, *args, **options):
        n = escalar_pendientes(minutos=options['minutos'])
        self.stdout.write(self.style.SUCCESS(f'Críticos escalados: {n}'))
