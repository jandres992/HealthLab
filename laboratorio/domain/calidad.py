"""
Política de control de calidad al validar (RF-50.1, RN-24).

Estados del CCI del día para un (equipo, analito):
  'no_aplica'  — el equipo no tiene materiales de control definidos para el analito
  'no_corrido' — hay controles definidos pero hoy no se corrió ninguno
  'rechazado'  — la última corrida de hoy fue rechazada y no tiene acción correctiva
  'aceptado'   — hay corrida de hoy aceptada (o rechazo con acción correctiva documentada)

Modos (RF-50.1): informativo < advertencia < bloqueante.
"""
from .errores import ErrorDeDominio

MODOS = ('informativo', 'advertencia', 'bloqueante')
ESTADOS_QUE_IMPIDEN = ('no_corrido', 'rechazado')


def modo_mas_estricto(modos):
    peso = {m: i for i, m in enumerate(MODOS)}
    return max(modos, key=lambda m: peso.get(m, 0)) if modos else 'informativo'


def estado_cci_del_dia(equipo, nombre_parametro, hoy):
    """Calcula el estado a partir de LoteControl y CorridaCCI (consulta la BD)."""
    from laboratorio.models import CorridaCCI, LoteControl  # noqa: PLC0415

    lotes = LoteControl.objects.filter(equipo=equipo, nombre_parametro=nombre_parametro, activo=True)
    if not lotes.exists():
        return 'no_aplica'
    corridas = list(CorridaCCI.objects.filter(lote_control__in=lotes, fecha__date=hoy).order_by('fecha'))
    if not corridas:
        return 'no_corrido'
    # Por nivel: la última corrida manda; un rechazo se libera con acción correctiva.
    ultima_por_lote = {}
    for c in corridas:
        ultima_por_lote[c.lote_control_id] = c
    for c in ultima_por_lote.values():
        if c.resultado == 'rechazada' and not c.accion_correctiva:
            return 'rechazado'
    return 'aceptado'


def aplicar_politica(modo, estado, justificacion):
    """
    Decide si se puede validar con el estado de CCI dado.
    - informativo: siempre.
    - advertencia: si el estado impide, exige justificación.
    - bloqueante: si el estado impide, 409.
    """
    if estado not in ESTADOS_QUE_IMPIDEN:
        return
    if modo == 'bloqueante':
        raise ErrorDeDominio(
            f'Control de calidad del día: {estado}. La política del analito es bloqueante; '
            'registre una corrida aceptada o una acción correctiva.',
            estado='cci_bloqueante', estado_cci=estado,
        )
    if modo == 'advertencia' and not (justificacion or '').strip():
        raise ErrorDeDominio(
            f'Control de calidad del día: {estado}. Debe indicar una justificación para validar.',
            estado='cci_requiere_justificacion', estado_cci=estado,
        )
