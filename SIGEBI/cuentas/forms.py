"""Formulario de inicio de sesión del Release 1: correo electrónico y contraseña."""
from django import forms
from django.contrib.auth.forms import AuthenticationForm


class CorreoAuthenticationForm(AuthenticationForm):
    # El campo se llama `username` porque así lo espera Django; la persona ve "Correo electrónico".
    username = forms.EmailField(
        label='Correo electrónico',
        widget=forms.EmailInput(attrs={'autofocus': True, 'autocomplete': 'email'}),
    )
    # Un correo inexistente, una contraseña incorrecta o una cuenta inactiva dan el mismo mensaje.
    error_messages = {
        **AuthenticationForm.error_messages,
        'invalid_login': 'El correo o la contraseña no son correctos.',
    }
