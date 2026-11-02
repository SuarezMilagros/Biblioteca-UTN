"""Formularios de cuentas del Release 1: inicio de sesión y alta o edición de cuentas del sistema."""
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm

from .roles import ADMINISTRATIVO, BIBLIOTECARIO


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


class UsuarioForm(forms.ModelForm):
    """Alta y edición de cuentas del sistema (Administrativo y Bibliotecario).

    No hay campos de privilegios (superusuario, staff, permisos). El rol se elige aparte.
    """

    rol = forms.ChoiceField(label='Rol')

    class Meta:
        model = get_user_model()
        fields = ['username', 'first_name', 'last_name', 'email', 'is_active']
        labels = {
            'username': 'Documento',
            'first_name': 'Nombre',
            'last_name': 'Apellido',
            'email': 'Correo electrónico',
            'is_active': 'Cuenta activa',
        }
        error_messages = {
            'username': {'unique': 'Ya existe una cuenta con ese documento.'},
        }

    def __init__(self, *args, solicitante, **kwargs):
        super().__init__(*args, **kwargs)
        self.solicitante = solicitante
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True
        self.fields['email'].required = True

        rol_actual = None
        if self.instance.pk:
            grupo = self.instance.groups.filter(name__in=[ADMINISTRATIVO, BIBLIOTECARIO]).first()
            rol_actual = grupo.name if grupo else None
            self.fields['rol'].initial = rol_actual

        if self.instance.pk and self.instance.pk == solicitante.pk:
            # Nadie cambia su propio rol ni se desactiva a sí mismo.
            self.fields['rol'].choices = [(rol_actual or '', rol_actual or 'Sin rol')]
            self.fields['rol'].disabled = True
            self.fields['rol'].required = False
            self.fields['is_active'].disabled = True
        elif solicitante.is_superuser:
            self.fields['rol'].choices = [(ADMINISTRATIVO, ADMINISTRATIVO), (BIBLIOTECARIO, BIBLIOTECARIO)]
        else:
            # El Administrativo solo puede asignar el rol Bibliotecario.
            self.fields['rol'].choices = [(BIBLIOTECARIO, BIBLIOTECARIO)]

    def clean_email(self):
        correo = self.cleaned_data['email'].strip()
        cuentas = get_user_model().objects.filter(email__iexact=correo)
        if self.instance.pk:
            cuentas = cuentas.exclude(pk=self.instance.pk)
        if cuentas.exists():
            raise forms.ValidationError('Ya existe una cuenta con ese correo.')
        return correo
