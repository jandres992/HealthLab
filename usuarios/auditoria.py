"""
Bitácora de auditoría (RNF-25, RNF-34).

`registrar()` escribe una fila inmutable con quién, cuándo, con qué rol,
desde dónde y qué hizo. Se llama dentro de la misma transacción que la
acción auditada (RNF-29.3); nunca se envuelve en un try/except que la omita.
"""
from django.utils import timezone

from .roles import roles_de


def _ip_de(request):
    if request is None:
        return None
    reenviado = request.META.get('HTTP_X_FORWARDED_FOR')
    if reenviado:
        return reenviado.split(',')[0].strip()[:45]
    return (request.META.get('REMOTE_ADDR') or '')[:45] or None


def registrar(request, accion, entidad=None, entidad_id=None, detalle=None, usuario=None, exito=True):
    """
    Crea un registro de auditoría.

    - request: petición HTTP (puede ser None en comandos de gestión).
    - accion: clave corta, p. ej. 'login.exito', 'usuario.crear', 'examen.aprobar'.
    - entidad / entidad_id: qué se tocó, p. ej. ('Usuario', 12) u ('OrdenLaboratorio', uuid).
    - detalle: dict serializable con el contexto necesario (sin contraseñas ni tokens).
    """
    from .models import Auditoria  # noqa: PLC0415

    if usuario is None and request is not None:
        candidato = getattr(request, 'user', None)
        usuario = candidato if getattr(candidato, 'is_authenticated', False) else None

    datos = request.data if request is not None and hasattr(request, 'data') else {}
    device_id = None
    if isinstance(datos, dict):
        device_id = datos.get('device_id')
    if not device_id and request is not None:
        device_id = request.META.get('HTTP_X_DEVICE_ID')

    return Auditoria.objects.create(
        usuario=usuario,
        username=(getattr(usuario, 'username', None) or (detalle or {}).get('username') or '')[:150],
        roles=sorted(roles_de(usuario)) if usuario else [],
        accion=accion[:60],
        entidad=(entidad or '')[:60],
        entidad_id=str(entidad_id)[:64] if entidad_id is not None else '',
        detalle=detalle or {},
        exito=exito,
        ip=_ip_de(request),
        user_agent=(request.META.get('HTTP_USER_AGENT', '') if request is not None else '')[:300],
        device_id=(str(device_id) if device_id else '')[:255],
        fecha=timezone.now(),
    )
