"""Revocación de refresh tokens (RNF-26): al desactivar, cambiar contraseña o quitar roles."""
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken


def revocar_tokens_de(usuario):
    """Envía a la lista negra todos los refresh tokens vigentes del usuario."""
    revocados = 0
    for token in OutstandingToken.objects.filter(user=usuario):
        _, creado = BlacklistedToken.objects.get_or_create(token=token)
        revocados += int(creado)
    return revocados
