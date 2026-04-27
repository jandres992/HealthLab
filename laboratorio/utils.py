"""
Utilidades compartidas del módulo laboratorio.
Centraliza la lógica de comparación de rangos y búsqueda de parámetros
para evitar duplicación entre views y serializers.
"""
import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation


def normalizar_texto(valor):
    """Normaliza texto a minúsculas sin acentos para comparación fuzzy."""
    if valor is None:
        return ''
    texto = str(valor).strip().lower()
    texto = unicodedata.normalize('NFKD', texto)
    return ''.join(ch for ch in texto if not unicodedata.combining(ch))


def buscar_valor_parametro(datos_json, nombre_parametro):
    """Busca el valor de un parámetro en un dict de datos JSON (fuzzy)."""
    if not isinstance(datos_json, dict):
        return None
    objetivo = normalizar_texto(nombre_parametro)
    mapa = {normalizar_texto(clave): valor for clave, valor in datos_json.items()}
    if objetivo in mapa:
        return mapa[objetivo]
    for clave, valor in mapa.items():
        if objetivo in clave or clave in objetivo:
            return valor
    return None


def calcular_edad_anios(fecha_nacimiento):
    """Calcula la edad en años completos desde la fecha de nacimiento."""
    hoy = date.today()
    return (
        hoy.year - fecha_nacimiento.year
        - ((hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day))
    )


def obtener_parametro_para_paciente(cups_id, nombre_parametro, paciente):
    """
    Retorna el ParametroExamen más específico (por sexo/edad) aplicable al paciente.
    Prioridad: sexo+edad > solo sexo > solo edad > universal (None en ambos).
    Si ninguno aplica, retorna el primero disponible como fallback.
    """
    # Importación local para evitar dependencias circulares al iniciar Django.
    from laboratorio.models import ParametroExamen  # noqa: PLC0415

    parametros = list(
        ParametroExamen.objects.filter(
            cups_id=cups_id, nombre_parametro=nombre_parametro
        ).select_related('sexo_aplica')
    )
    if not parametros:
        return None
    if len(parametros) == 1:
        return parametros[0]

    edad = calcular_edad_anios(paciente.fecha_nacimiento)
    sexo_codigo = paciente.sexo_biologico.codigo if paciente.sexo_biologico else None

    def _puntaje(p):
        sexo_match = p.sexo_aplica is None or (
            sexo_codigo is not None and p.sexo_aplica.codigo == sexo_codigo
        )
        edad_min_ok = p.edad_minima_anios is None or edad >= p.edad_minima_anios
        edad_max_ok = p.edad_maxima_anios is None or edad <= p.edad_maxima_anios
        if not (sexo_match and edad_min_ok and edad_max_ok):
            return -1
        score = 0
        if p.sexo_aplica is not None:
            score += 2
        if p.edad_minima_anios is not None or p.edad_maxima_anios is not None:
            score += 1
        return score

    candidatos = [(_puntaje(p), p) for p in parametros]
    candidatos = [(s, p) for s, p in candidatos if s >= 0]
    if not candidatos:
        return parametros[0]
    return max(candidatos, key=lambda x: x[0])[1]


def es_anormal(parametro, valor_resultado):
    """
    Evalúa si un valor está fuera de los rangos de referencia del parámetro.
    Retorna (es_anormal: bool, es_critico: bool).
    """
    try:
        valor_num = Decimal(str(valor_resultado).replace(',', '.').strip())
    except (InvalidOperation, AttributeError, TypeError):
        return False, False

    anormal = False
    critico = False

    if parametro.rango_referencia_minimo is not None and valor_num < parametro.rango_referencia_minimo:
        anormal = True
    if parametro.rango_referencia_maximo is not None and valor_num > parametro.rango_referencia_maximo:
        anormal = True

    if parametro.rango_panico_minimo is not None and valor_num < parametro.rango_panico_minimo:
        critico = True
    if parametro.rango_panico_maximo is not None and valor_num > parametro.rango_panico_maximo:
        critico = True

    return anormal, critico


def generar_pdf_orden(orden):
    """
    Genera el informe PDF de resultados de una OrdenLaboratorio.
    Retorna los bytes del PDF.
    """
    from io import BytesIO
    import datetime

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.graphics.barcode import qr
    from reportlab.graphics.shapes import Drawing
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, HRFlowable
    )

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    titulo_style = ParagraphStyle(
        'Titulo', parent=styles['Title'], fontSize=16, spaceAfter=4, alignment=TA_CENTER
    )
    subtitulo_style = ParagraphStyle(
        'Subtitulo', parent=styles['Normal'], fontSize=10, alignment=TA_CENTER, spaceAfter=8
    )
    seccion_style = ParagraphStyle(
        'Seccion', parent=styles['Heading3'], fontSize=10, spaceBefore=10, spaceAfter=4,
        textColor=colors.HexColor('#1a3a5c')
    )
    normal_style = styles['Normal']
    normal_style.fontSize = 9

    story = []

    # ─── Encabezado ───────────────────────────────────────────────────────────
    story.append(Paragraph("LABORATORIO CLÍNICO HEALTHLAB", titulo_style))
    story.append(Paragraph("Informe de Resultados de Laboratorio", subtitulo_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#1a3a5c')))
    story.append(Spacer(1, 0.4 * cm))

    # QR de verificación (orden y paciente) para lectura desde frontend o app clínica.
    qr_payload = (
        f"orden={orden.numero_orden};"
        f"paciente={orden.paciente.numero_documento if orden.paciente else ''};"
        f"fecha={orden.fecha_orden.strftime('%Y-%m-%d %H:%M:%S') if orden.fecha_orden else ''}"
    )
    qr_widget = qr.QrCodeWidget(qr_payload)
    bounds = qr_widget.getBounds()
    size = 2.5 * cm
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    qr_drawing = Drawing(size, size, transform=[size / width, 0, 0, size / height, 0, 0])
    qr_drawing.add(qr_widget)
    story.append(Paragraph("Verificación del informe (QR)", ParagraphStyle('QrLbl', parent=styles['Normal'], fontSize=8, alignment=TA_RIGHT)))
    story.append(qr_drawing)
    story.append(Spacer(1, 0.2 * cm))

    # ─── Datos del paciente ───────────────────────────────────────────────────
    paciente = orden.paciente
    story.append(Paragraph("DATOS DEL PACIENTE", seccion_style))
    datos_paciente = [
        ['Nombre completo:', f"{paciente.primer_nombre} {paciente.segundo_nombre or ''} {paciente.primer_apellido} {paciente.segundo_apellido or ''}".strip()],
        ['Documento:', f"{paciente.tipo_documento.codigo} {paciente.numero_documento}"],
        ['Fecha de nacimiento:', str(paciente.fecha_nacimiento)],
        ['Sexo biológico:', paciente.sexo_biologico.descripcion if paciente.sexo_biologico else 'N/A'],
    ]
    t_paciente = Table(datos_paciente, colWidths=[4 * cm, 13 * cm])
    t_paciente.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(t_paciente)
    story.append(Spacer(1, 0.3 * cm))

    # ─── Datos de la orden ────────────────────────────────────────────────────
    story.append(Paragraph("DATOS DE LA ORDEN", seccion_style))
    medico_nombre = 'N/A'
    if orden.medico:
        medico_nombre = f"{orden.medico.p_nombre or ''} {orden.medico.p_apellido or ''}".strip() or orden.medico.username
    datos_orden = [
        ['N° Orden:', orden.numero_orden],
        ['Fecha:', str(orden.fecha_orden.strftime('%d/%m/%Y %H:%M') if orden.fecha_orden else 'N/A')],
        ['Médico solicitante:', medico_nombre],
        ['CIE-10:', orden.codigo_cie10 or 'N/A'],
        ['Entidad / Convenio:', f"{orden.entidad_remitente or 'N/A'} / {orden.convenio or 'N/A'}"],
    ]
    if orden.observaciones_clinicas:
        datos_orden.append(['Observaciones:', orden.observaciones_clinicas])
    t_orden = Table(datos_orden, colWidths=[4 * cm, 13 * cm])
    t_orden.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(t_orden)
    story.append(Spacer(1, 0.5 * cm))

    # ─── Resultados por examen ─────────────────────────────────────────────────
    story.append(Paragraph("RESULTADOS", seccion_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Spacer(1, 0.2 * cm))

    examenes = orden.examenes_solicitados.prefetch_related(
        'resultados__parametro'
    ).select_related('cups').all()

    for examen in examenes:
        story.append(Paragraph(
            f"<b>{examen.cups.codigo_cups}</b> — {examen.cups.descripcion} "
            f"<font size='8' color='grey'>[{examen.estado_examen.nombre}]</font>",
            styles['Normal']
        ))
        resultados = list(examen.resultados.all())
        if resultados:
            cabecera = ['Parámetro', 'Resultado', 'Unidades', 'Rango Ref.', 'Pánico', 'Estado']
            filas = [cabecera]
            indices_anormales = []
            for i, r in enumerate(resultados, start=1):
                p = r.parametro
                rango = 'N/A'
                if p.rango_referencia_minimo is not None and p.rango_referencia_maximo is not None:
                    rango = f"{p.rango_referencia_minimo} – {p.rango_referencia_maximo}"
                elif p.rango_texto:
                    rango = p.rango_texto
                panico = 'N/A'
                if p.rango_panico_minimo is not None or p.rango_panico_maximo is not None:
                    panico = f"{p.rango_panico_minimo or '—'} / {p.rango_panico_maximo or '—'}"
                estado_txt = 'ANORMAL' if r.es_anormal else 'Normal'
                filas.append([
                    p.nombre_parametro,
                    r.valor_resultado,
                    p.unidades_medida or '',
                    rango,
                    panico,
                    estado_txt,
                ])
                if r.es_anormal:
                    indices_anormales.append(i)
                if r.comentario_bacteriologo:
                    filas.append(['  Obs.:', r.comentario_bacteriologo, '', '', '', ''])

            col_widths = [4.5 * cm, 2.5 * cm, 2 * cm, 3.5 * cm, 2.5 * cm, 2 * cm]
            t_res = Table(filas, colWidths=col_widths)
            t_res_style = [
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a3a5c')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('GRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#cccccc')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ]
            for idx in indices_anormales:
                t_res_style.append(('TEXTCOLOR', (1, idx), (1, idx), colors.red))
                t_res_style.append(('FONTNAME', (1, idx), (1, idx), 'Helvetica-Bold'))
                t_res_style.append(('TEXTCOLOR', (5, idx), (5, idx), colors.red))
            t_res.setStyle(TableStyle(t_res_style))
            story.append(t_res)
        else:
            story.append(Paragraph("<i>Sin resultados registrados.</i>", styles['Normal']))
        story.append(Spacer(1, 0.4 * cm))

    # ─── Área de firmado ──────────────────────────────────────────────────────
    story.append(Spacer(1, 1 * cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    firma_style = ParagraphStyle('Firma', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER)
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("__________________________________", firma_style))
    story.append(Paragraph("Firma del Bacteriólogo Responsable", firma_style))
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(
        f"Documento generado el {datetime.datetime.now().strftime('%d/%m/%Y a las %H:%M')}. "
        "Este informe es de carácter confidencial.",
        ParagraphStyle('Pie', parent=styles['Normal'], fontSize=7, textColor=colors.grey, alignment=TA_CENTER)
    ))

    doc.build(story)
    return buffer.getvalue()
