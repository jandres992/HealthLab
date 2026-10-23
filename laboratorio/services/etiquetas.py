"""
Etiqueta de la muestra (RF-60, RF-60.1, RF-60.2, BE-26).

Genera un PDF con el código de barras Code 128 del código de la muestra y, en
texto legible, el paciente, su documento, la orden, el tipo de muestra y la
fecha de la toma. Hay dos formatos:

- ``individual``: una etiqueta por página de 50 × 25 mm, para impresora de etiquetas.
- ``hoja``: hoja carta con una cuadrícula de 3 × 10 etiquetas, para impresora común.

Cada impresión o reimpresión queda en la cadena de custodia (evento ``etiqueta``)
y en la bitácora de auditoría.
"""
import io

from django.db import transaction
from django.utils import timezone

from laboratorio.domain import estados as E
from laboratorio.domain.errores import ErrorDeDominio, ErrorDeValidacion, NoEncontrado
from laboratorio.models import MuestraFisica
from laboratorio.services.custodia import registrar_evento
from usuarios import auditoria

FORMATOS = ('individual', 'hoja')
MAX_COPIAS = 30

# Etiqueta individual (impresora de etiquetas)
ANCHO_INDIVIDUAL_MM = 50
ALTO_INDIVIDUAL_MM = 25

# Hoja carta tipo 3 × 10 (66,7 × 25,4 mm por etiqueta)
COLUMNAS_HOJA = 3
FILAS_HOJA = 10
ANCHO_HOJA_ETIQUETA_MM = 66.7
ALTO_HOJA_ETIQUETA_MM = 25.4
MARGEN_SUPERIOR_HOJA_MM = 12.7
MARGEN_IZQUIERDO_HOJA_MM = 4.8
SEPARACION_COLUMNAS_MM = 3.2


def datos_etiqueta(muestra):
    """Textos que se imprimen en la etiqueta, a partir de los datos guardados."""
    orden = muestra.orden
    paciente = orden.paciente
    nombre = ' '.join(filter(None, [paciente.primer_apellido, paciente.segundo_apellido,
                                    paciente.primer_nombre, paciente.segundo_nombre]))
    tipo_doc = paciente.tipo_documento.codigo if paciente.tipo_documento_id else ''
    fecha = timezone.localtime(muestra.fecha_recoleccion).strftime('%d/%m/%Y %H:%M') if muestra.fecha_recoleccion else ''
    return {
        'codigo': muestra.codigo_barras,
        'paciente': nombre.upper(),
        'documento': f'{tipo_doc} {paciente.numero_documento}'.strip(),
        'orden': orden.numero_orden,
        'tipo_muestra': muestra.tipo_muestra or '',
        'fecha_toma': fecha,
    }


def _recortar(texto, fuente, tamano, ancho_max):
    """Recorta el texto con '…' para que quepa en el ancho disponible."""
    from reportlab.pdfbase.pdfmetrics import stringWidth  # noqa: PLC0415

    if stringWidth(texto, fuente, tamano) <= ancho_max:
        return texto
    while texto and stringWidth(texto + '…', fuente, tamano) > ancho_max:
        texto = texto[:-1]
    return texto + '…'


MODULO_MAX_MM = 0.33
MODULO_MIN_MM = 0.19   # por debajo, muchos lectores no distinguen las barras
ZONA_SILENCIO_MODULOS = 10   # espacio en blanco a cada lado que exige Code 128


def _codigo_barras(valor, ancho_total, alto):
    """
    Code 128 con el módulo más ancho que quepa en `ancho_total`, dejando a cada lado
    una zona en blanco de 10 módulos (se cuenta hasta el borde de la etiqueta).
    Devuelve solo las barras; quien dibuja las centra.
    """
    from reportlab.graphics.barcode import code128  # noqa: PLC0415
    from reportlab.lib.units import mm  # noqa: PLC0415

    referencia = code128.Code128(valor, barHeight=alto, barWidth=1, humanReadable=False, quiet=False)
    modulos = referencia.width  # con barWidth=1, el ancho es el número de módulos
    modulo = ancho_total / (modulos + 2 * ZONA_SILENCIO_MODULOS)
    modulo = min(MODULO_MAX_MM * mm, max(MODULO_MIN_MM * mm, modulo))
    return code128.Code128(valor, barHeight=alto, barWidth=modulo, humanReadable=False, quiet=False)


def _dibujar_etiqueta(c, x, y, ancho, alto, d, borde=False):
    """Dibuja una etiqueta con esquina inferior izquierda en (x, y)."""
    from reportlab.lib import colors  # noqa: PLC0415
    from reportlab.lib.units import mm  # noqa: PLC0415

    margen = 1.8 * mm
    util = ancho - 2 * margen
    if borde:
        c.setStrokeColor(colors.HexColor('#c8c8c8'))
        c.setLineWidth(0.3)
        c.rect(x, y, ancho, alto)
    c.setFillColor(colors.black)

    # Línea 1: paciente
    c.setFont('Helvetica-Bold', 7)
    c.drawString(x + margen, y + alto - margen - 6, _recortar(d['paciente'], 'Helvetica-Bold', 7, util))
    # Línea 2: documento y orden
    c.setFont('Helvetica', 6)
    c.drawString(x + margen, y + alto - margen - 13, _recortar(f"{d['documento']} · {d['orden']}", 'Helvetica', 6, util))

    # Código de barras
    alto_barras = alto * 0.36
    barra = _codigo_barras(d['codigo'], ancho, alto_barras)
    y_barras = y + margen + 13
    barra.drawOn(c, x + (ancho - barra.width) / 2, y_barras)

    # Código legible bajo las barras
    c.setFont('Helvetica-Bold', 7)
    c.drawCentredString(x + ancho / 2, y + margen + 6.5, d['codigo'])
    # Línea final: tipo de muestra y fecha de toma
    c.setFont('Helvetica', 5.5)
    c.drawCentredString(x + ancho / 2, y + margen,
                        _recortar(f"{d['tipo_muestra']} · {d['fecha_toma']}", 'Helvetica', 5.5, util))


def generar_pdf(muestra, formato='individual', copias=1):
    """Devuelve los bytes del PDF de la etiqueta. No registra nada."""
    from reportlab.lib.pagesizes import letter  # noqa: PLC0415
    from reportlab.lib.units import mm  # noqa: PLC0415
    from reportlab.pdfgen import canvas  # noqa: PLC0415

    d = datos_etiqueta(muestra)
    buffer = io.BytesIO()
    if formato == 'individual':
        ancho, alto = ANCHO_INDIVIDUAL_MM * mm, ALTO_INDIVIDUAL_MM * mm
        c = canvas.Canvas(buffer, pagesize=(ancho, alto))
        c.setTitle(f'Etiqueta {d["codigo"]}')
        for _ in range(copias):
            _dibujar_etiqueta(c, 0, 0, ancho, alto, d)
            c.showPage()
    else:
        c = canvas.Canvas(buffer, pagesize=letter)
        c.setTitle(f'Etiquetas {d["codigo"]}')
        _, alto_pagina = letter
        ancho_e, alto_e = ANCHO_HOJA_ETIQUETA_MM * mm, ALTO_HOJA_ETIQUETA_MM * mm
        for i in range(copias):
            fila, columna = divmod(i, COLUMNAS_HOJA)
            x = MARGEN_IZQUIERDO_HOJA_MM * mm + columna * (ancho_e + SEPARACION_COLUMNAS_MM * mm)
            y = alto_pagina - MARGEN_SUPERIOR_HOJA_MM * mm - (fila + 1) * alto_e
            _dibujar_etiqueta(c, x, y, ancho_e, alto_e, d, borde=True)
        c.showPage()
    c.save()
    return buffer.getvalue()


def validar_parametros(formato, copias):
    formato = (formato or 'individual').strip().lower()
    if formato not in FORMATOS:
        raise ErrorDeValidacion('Formato de etiqueta no válido. Use "individual" u "hoja".', campo='formato')
    try:
        copias = int(copias or 1)
    except (TypeError, ValueError):
        raise ErrorDeValidacion('El número de copias debe ser un número entero.', campo='copias')
    if not 1 <= copias <= MAX_COPIAS:
        raise ErrorDeValidacion(f'El número de copias debe estar entre 1 y {MAX_COPIAS}.', campo='copias')
    return formato, copias


def imprimir_etiqueta(actor, muestra_id, formato='individual', copias=1, request=None):
    """
    Genera la etiqueta y registra la impresión (o reimpresión) en la cadena de custodia
    y en la auditoría. Devuelve (bytes del PDF, nombre del archivo, es_reimpresion).
    """
    formato, copias = validar_parametros(formato, copias)
    with transaction.atomic():
        try:
            muestra = MuestraFisica.objects.select_for_update().select_related(
                'estado_muestra', 'orden__paciente__tipo_documento').get(pk=muestra_id)
        except MuestraFisica.DoesNotExist:
            raise NoEncontrado('La muestra no existe.')
        if muestra.estado_muestra and muestra.estado_muestra.nombre == E.MUESTRA_DESCARTADA:
            raise ErrorDeDominio('La muestra fue descartada; no se imprimen etiquetas.')

        pdf = generar_pdf(muestra, formato, copias)
        es_reimpresion = muestra.eventos.filter(tipo='etiqueta').exists()
        accion = 'Reimpresión' if es_reimpresion else 'Impresión'
        registrar_evento(actor, muestra, 'etiqueta',
                         observacion=f'{accion} de etiqueta ({formato}, {copias} copia{"s" if copias > 1 else ""})')
        auditoria.registrar(request, 'muestra.etiqueta_reimprimir' if es_reimpresion else 'muestra.etiqueta_imprimir',
                            'MuestraFisica', muestra.pk,
                            {'codigo_barras': muestra.codigo_barras, 'formato': formato, 'copias': copias},
                            usuario=actor)
    return pdf, f'etiqueta_{muestra.codigo_barras}.pdf', es_reimpresion
