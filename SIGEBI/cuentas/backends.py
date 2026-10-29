"""Inicio de sesión con correo electrónico (Release 1).

El nombre de usuario de Django es el documento. La persona entra con su correo
y su contraseña, y este backend busca la cuenta por correo.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class CorreoBackend(ModelBackend):
    """Busca la cuenta por correo, sin distinguir mayúsculas.

    Si el correo no corresponde a exactamente una cuenta, no autentica a nadie:
    así un correo repetido no abre la puerta a ninguna de las cuentas.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username:
            return None
        cuentas = list(get_user_model().objects.filter(email__iexact=username)[:2])
        if len(cuentas) != 1:
            # Igual que ModelBackend: se calcula un hash para que el tiempo de respuesta
            # no revele si el correo existe.
            get_user_model()().set_password(password)
            return None
        usuario = cuentas[0]
        if usuario.check_password(password) and self.user_can_authenticate(usuario):
            return usuario
        return None
