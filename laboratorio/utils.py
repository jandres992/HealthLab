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


def generar_pdf_orden(orden, preliminar=False):
    """
    Genera el informe PDF de resultados de una OrdenLaboratorio.
    Retorna los bytes del PDF.
    Diseño profesional para Laboratorio Nivel 2.
    """
    from io import BytesIO
    import datetime
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, HRFlowable
    )

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )
    styles = getSampleStyleSheet()
    
    # Estilos personalizados premium
    h1_style = ParagraphStyle('H1', parent=styles['Heading1'], fontSize=18, alignment=TA_CENTER, textColor=colors.HexColor('#003366'), spaceAfter=2)
    h2_style = ParagraphStyle('H2', parent=styles['Normal'], fontSize=10, alignment=TA_CENTER, textColor=colors.grey, spaceAfter=10)
    preliminar_style = ParagraphStyle('Preliminar', parent=styles['Normal'], fontSize=20, alignment=TA_CENTER, textColor=colors.red, spaceAfter=10, fontName='Helvetica-Bold')
    label_style = ParagraphStyle('Label', parent=styles['Normal'], fontSize=9, fontName='Helvetica-Bold')
    val_style = ParagraphStyle('Value', parent=styles['Normal'], fontSize=9)
    sect_header = ParagraphStyle('Sect', parent=styles['Normal'], fontSize=10, fontName='Helvetica-Bold', textColor=colors.white, backColor=colors.HexColor('#003366'), leftIndent=5, rightIndent=5, spaceBefore=10, spaceAfter=5)

    story = []

    # ─── CABECERA PRELIMINAR ───
    if preliminar:
        story.append(Paragraph("INFORME PRELIMINAR - SIN VALIDEZ LEGAL", preliminar_style))
        story.append(Spacer(1, 0.5 * cm))

    # ─── LOGO Y CABECERA ───
    story.append(Paragraph("HEALTHLAB LIMS - SOLUCIONES CLÍNICAS", h1_style))
    story.append(Paragraph("Laboratorio Clínico de Alta Complejidad (Nivel 2)", h2_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#003366')))
    story.append(Spacer(1, 0.5 * cm))

    # ─── INFORMACIÓN DEL PACIENTE ───
    paciente = orden.paciente
    p_data = [
        [Paragraph("<b>PACIENTE:</b>", label_style), Paragraph(f"{paciente.primer_nombre} {paciente.primer_apellido}".upper(), val_style), 
         Paragraph("<b>DOCUMENTO:</b>", label_style), Paragraph(f"{paciente.tipo_documento.codigo} {paciente.numero_documento}", val_style)],
        [Paragraph("<b>EDAD:</b>", label_style), Paragraph(f"{calcular_edad_anios(paciente.fecha_nacimiento)} Años", val_style),
         Paragraph("<b>SEXO:</b>", label_style), Paragraph(paciente.sexo_biologico.descripcion if paciente.sexo_biologico else 'N/A', val_style)],
        [Paragraph("<b>FECHA ORDEN:</b>", label_style), Paragraph(orden.fecha_orden.strftime('%d/%m/%Y %H:%M') if orden.fecha_orden else 'N/A', val_style),
         Paragraph("<b>NÚMERO ORDEN:</b>", label_style), Paragraph(orden.numero_orden, val_style)]
    ]
    t_pac = Table(p_data, colWidths=[3*cm, 6*cm, 3*cm, 6*cm])
    t_pac.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
    story.append(t_pac)
    story.append(Spacer(1, 0.5 * cm))

    # ─── INFORMACIÓN CLÍNICA ───
    c_data = [
        [Paragraph("<b>MÉDICO:</b>", label_style), Paragraph(f"{orden.medico.p_nombre} {orden.medico.p_apellido}" if orden.medico else "PARTICULAR", val_style)],
        [Paragraph("<b>ENTIDAD:</b>", label_style), Paragraph(orden.entidad_remitente or "PARTICULAR", val_style)],
        [Paragraph("<b>DIAGNÓSTICO:</b>", label_style), Paragraph(f"{orden.codigo_cie10 or 'N/A'}", val_style)]
    ]
    t_clin = Table(c_data, colWidths=[3*cm, 15*cm])
    story.append(t_clin)
    story.append(Spacer(1, 0.5 * cm))

    # ─── RESULTADOS AGRUPADOS ───
    story.append(Paragraph(" REPORTE DETALLADO DE RESULTADOS", sect_header))
    
    if preliminar:
        # En preliminar mostramos todo lo que tenga al menos un resultado
        examenes = orden.examenes_solicitados.filter(resultados__isnull=False).distinct().prefetch_related('resultados__parametro')
    else:
        examenes = orden.examenes_solicitados.filter(estado_examen__nombre='Validado').prefetch_related('resultados__parametro')
    
    if not examenes.exists():
        story.append(Paragraph("<i>No hay estudios validados para mostrar en este informe.</i>", val_style))
    else:
        for ex in examenes:
            status_text = f" [{ex.estado_examen.nombre}]" if preliminar else ""
            story.append(Spacer(1, 0.3*cm))
            story.append(Paragraph(f"ESTUDIO: <b>{ex.cups.descripcion.upper()}</b> {status_text}", label_style))
            story.append(Spacer(1, 0.2*cm))
            
            res_data = [['PARÁMETRO', 'RESULTADO', 'UNIDADES', 'RANGOS DE REFERENCIA']]
            for r in ex.resultados.all():
                p = r.parametro
                r_min = p.rango_referencia_minimo if p.rango_referencia_minimo is not None else ""
                r_max = p.rango_referencia_maximo if p.rango_referencia_maximo is not None else ""
                rango_str = f"{r_min} - {r_max}" if r_min or r_max else (p.rango_texto or "N/A")
                
                # Resaltar anormales
                val_display = r.valor_resultado
                if r.es_anormal:
                    val_display = f"<b>{val_display} *</b>"
                
                res_data.append([p.nombre_parametro, val_display, p.unidades_medida or "", rango_str])
            
            t_res = Table(res_data, colWidths=[6*cm, 3*cm, 3*cm, 6*cm])
            t_res.setStyle(TableStyle([
                ('FONTSIZE', (0,0), (-1,-1), 8),
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f2f2f2')),
                ('LINEBELOW', (0,0), (-1,0), 1, colors.black),
                ('ALIGN', (1,0), (1,-1), 'CENTER'),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                ('TOPPADDING', (0,0), (-1,-1), 4),
            ]))
            story.append(t_res)
            if ex.motivo_rechazo:
                story.append(Paragraph(f"Nota: {ex.motivo_rechazo}", val_style))

    # ─── PIE DE PÁGINA ───
    story.append(Spacer(1, 2*cm))
    if not preliminar:
        story.append(HRFlowable(width="30%", thickness=1, color=colors.black, alignment=TA_LEFT))
        story.append(Paragraph("Firma Electrónica - Bacteriólogo Responsable", val_style))
    else:
        story.append(Paragraph("<b>DOCUMENTO PRELIMINAR - PENDIENTE DE VALIDACIÓN FINAL</b>", ParagraphStyle('Warn', parent=val_style, textColor=colors.red)))
        
    story.append(Paragraph(f"Informe generado el {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", h2_style))

    doc.build(story)
    return buffer.getvalue()
