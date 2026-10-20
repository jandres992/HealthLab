"""
Máquinas de estado de examen, orden y muestra (§5.2–5.4, RN-10, RN-23).

Los nombres de estado viven en los catálogos de la base de datos; aquí están
las transiciones permitidas y las reglas para derivar el estado de la orden.
Qué estados de examen son finales lo dice `EstadoExamen.es_final` (RN-10.1);
las constantes de abajo son los valores con los que se siembra el catálogo.
"""
from .errores import ErrorDeConfiguracion, TransicionInvalida

# ── Examen ────────────────────────────────────────────────────────────────────
EXAMEN_PENDIENTE = 'Pendiente'
EXAMEN_MUESTRA_RECOLECTADA = 'Muestra Recolectada'
EXAMEN_EN_ANALISIS = 'En Análisis'
EXAMEN_EN_ESPERA = 'En Espera'
EXAMEN_REPETIR = 'Repetir'
EXAMEN_VALIDADO = 'Validado'
EXAMEN_ANULADO = 'Anulado'

EXAMEN_ESTADOS_FINALES = frozenset({EXAMEN_VALIDADO, EXAMEN_ANULADO})

TRANSICIONES_EXAMEN = {
    EXAMEN_PENDIENTE: {EXAMEN_MUESTRA_RECOLECTADA, EXAMEN_EN_ANALISIS, EXAMEN_ANULADO},
    EXAMEN_MUESTRA_RECOLECTADA: {EXAMEN_EN_ANALISIS, EXAMEN_REPETIR, EXAMEN_ANULADO},
    EXAMEN_EN_ANALISIS: {EXAMEN_VALIDADO, EXAMEN_REPETIR, EXAMEN_EN_ESPERA, EXAMEN_ANULADO},
    EXAMEN_EN_ESPERA: {EXAMEN_EN_ANALISIS, EXAMEN_VALIDADO, EXAMEN_REPETIR, EXAMEN_ANULADO},
    EXAMEN_REPETIR: {EXAMEN_MUESTRA_RECOLECTADA, EXAMEN_EN_ANALISIS, EXAMEN_ANULADO},
    EXAMEN_VALIDADO: set(),   # inmutable (RN-22); una corrección es una versión nueva
    EXAMEN_ANULADO: set(),
}

# ── Orden ─────────────────────────────────────────────────────────────────────
ORDEN_REGISTRADA = 'Registrada'
ORDEN_EN_PROCESO = 'En Proceso'
ORDEN_RESULTADOS_PARCIALES = 'Resultados Parciales'
ORDEN_FINALIZADA = 'Finalizada'
ORDEN_ANULADA = 'Anulada'

ORDEN_ESTADOS_FINALES = frozenset({ORDEN_FINALIZADA, ORDEN_ANULADA})

# ── Muestra ───────────────────────────────────────────────────────────────────
MUESTRA_RECOLECTADA = 'Recolectada'
MUESTRA_RECIBIDA = 'Recibida en Laboratorio'
MUESTRA_RECHAZADA = 'Rechazada'

TRANSICIONES_MUESTRA = {
    MUESTRA_RECOLECTADA: {MUESTRA_RECIBIDA, MUESTRA_RECHAZADA},
    MUESTRA_RECIBIDA: {MUESTRA_RECHAZADA},
    MUESTRA_RECHAZADA: set(),
}


# ── Acceso a los catálogos ────────────────────────────────────────────────────

def estado_examen(nombre):
    """Devuelve el EstadoExamen del catálogo; lo crea con su bandera es_final si falta."""
    from laboratorio.models import EstadoExamen  # noqa: PLC0415
    obj, _ = EstadoExamen.objects.get_or_create(
        nombre=nombre, defaults={'es_final': nombre in EXAMEN_ESTADOS_FINALES}
    )
    return obj


def estado_orden(nombre):
    from laboratorio.models import EstadoOrden  # noqa: PLC0415
    obj, _ = EstadoOrden.objects.get_or_create(nombre=nombre)
    return obj


def estado_muestra(nombre):
    from laboratorio.models import EstadoMuestra  # noqa: PLC0415
    obj, _ = EstadoMuestra.objects.get_or_create(nombre=nombre)
    return obj


# ── Reglas ────────────────────────────────────────────────────────────────────

def validar_transicion_examen(desde, hacia):
    permitidas = TRANSICIONES_EXAMEN.get(desde)
    if permitidas is None:
        raise ErrorDeConfiguracion(f"Estado de examen desconocido: '{desde}'.")
    if hacia not in permitidas:
        raise TransicionInvalida(
            f"Un examen en estado '{desde}' no puede pasar a '{hacia}'.",
            estado_actual=desde, estado_solicitado=hacia,
        )


def validar_transicion_muestra(desde, hacia):
    permitidas = TRANSICIONES_MUESTRA.get(desde)
    if permitidas is None:
        raise ErrorDeConfiguracion(f"Estado de muestra desconocido: '{desde}'.")
    if hacia not in permitidas:
        raise TransicionInvalida(
            f"Una muestra en estado '{desde}' no puede pasar a '{hacia}'.",
            estado_actual=desde, estado_solicitado=hacia,
        )


def examen_es_final(examen):
    return bool(examen.estado_examen.es_final)


def pendientes_para_finalizar(examenes):
    """Exámenes que impiden finalizar la orden (RN-10): todo lo que no sea final."""
    return [e for e in examenes if not examen_es_final(e)]


def puede_finalizar(examenes):
    """(bool, pendientes). Exige todos finales y al menos uno Validado."""
    examenes = list(examenes)
    if not examenes:
        return False, []
    pendientes = pendientes_para_finalizar(examenes)
    if pendientes:
        return False, pendientes
    hay_validado = any(e.estado_examen.nombre == EXAMEN_VALIDADO for e in examenes)
    return hay_validado, []


def calcular_estado_orden(examenes, estado_actual=None):
    """
    Deriva el estado de la orden a partir de sus exámenes (§5.3).
    Una orden ya Finalizada o Anulada no se reabre por esta vía.
    """
    examenes = list(examenes)
    if estado_actual in ORDEN_ESTADOS_FINALES:
        return estado_actual
    if not examenes:
        return ORDEN_REGISTRADA

    nombres = [e.estado_examen.nombre for e in examenes]
    if all(n == EXAMEN_ANULADO for n in nombres):
        return ORDEN_ANULADA
    finalizable, _ = puede_finalizar(examenes)
    if finalizable:
        return ORDEN_FINALIZADA
    if any(n == EXAMEN_VALIDADO for n in nombres):
        return ORDEN_RESULTADOS_PARCIALES
    if any(n in (EXAMEN_EN_ANALISIS, EXAMEN_EN_ESPERA, EXAMEN_REPETIR) for n in nombres):
        return ORDEN_EN_PROCESO
    return ORDEN_REGISTRADA
