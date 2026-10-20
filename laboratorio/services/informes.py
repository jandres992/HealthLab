"""Generación y resguardo de informes PDF con hash encadenado (RF-37, RNF-34.2)."""
import hashlib

from django.core.files.base import ContentFile

from laboratorio.models import InformeResultados
from laboratorio.utils import generar_pdf_orden


def hash_encadenado(pdf_bytes, hash_anterior):
    h = hashlib.sha256()
    h.update(pdf_bytes)
    if hash_anterior:
        h.update(hash_anterior.encode('ascii'))
    return h.hexdigest()


def generar_pdf(orden, tipo):
    """Bytes del PDF según el tipo de informe. Preliminar/parcial: sin validez legal."""
    return generar_pdf_orden(orden, preliminar=(tipo != 'final'))


def generar_informe(orden, tipo, actor, motivo=None):
    """
    Genera el PDF, lo guarda con su hash encadenado al informe anterior de la
    orden y lo marca vigente (desmarcando el anterior del mismo tipo).
    Debe llamarse dentro de la transacción del caso de uso: si falla, nada
    queda a medias (RNF-29.2).
    """
    pdf_bytes = generar_pdf(orden, tipo)
    anterior = InformeResultados.objects.filter(orden=orden).order_by('-fecha_generacion').first()
    hash_anterior = anterior.hash_documento if anterior else None

    InformeResultados.objects.filter(orden=orden, tipo=tipo, vigente=True).update(vigente=False)
    informe = InformeResultados(
        orden=orden, tipo=tipo, vigente=True, generado_por=actor,
        hash_anterior=hash_anterior, hash_documento=hash_encadenado(pdf_bytes, hash_anterior), motivo=motivo,
    )
    prefijo = '' if tipo == 'final' else f'{tipo.upper()}_'
    informe.archivo_pdf.save(f"{prefijo}informe_{orden.numero_orden}.pdf", ContentFile(pdf_bytes), save=False)
    informe.save()
    return informe, pdf_bytes


def verificar_cadena(orden):
    """Recorre los informes de la orden y comprueba que la cadena de hashes esté intacta."""
    informes = list(InformeResultados.objects.filter(orden=orden).order_by('fecha_generacion'))
    esperado_anterior = None
    for informe in informes:
        if informe.hash_anterior != esperado_anterior:
            return False, informe
        if informe.archivo_pdf:
            with informe.archivo_pdf.open('rb') as f:
                if hash_encadenado(f.read(), informe.hash_anterior) != informe.hash_documento:
                    return False, informe
        esperado_anterior = informe.hash_documento
    return True, None
