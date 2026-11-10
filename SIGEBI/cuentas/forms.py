"""Formularios de cuentas: inicio de sesión, recuperación de contraseña y alta o edición de cuentas."""
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm

from . import intentos
from .models import IntentoDeAcceso
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
        'bloqueado': 'Hubo demasiados intentos fallidos. Esperá 15 minutos y volvé a intentar.',
    }

    def clean(self):
        correo = self.cleaned_data.get('username')
        ip = intentos.ip_de(self.request)
        # Mientras está bloqueado no se prueba la contraseña, aunque sea la correcta.
        if correo and intentos.ingreso_bloqueado(correo, ip):
            raise forms.ValidationError(self.error_messages['bloqueado'], code='bloqueado')
        try:
            datos = super().clean()
        except forms.ValidationError:
            if correo:
                intentos.registrar(IntentoDeAcceso.Tipo.INGRESO_FALLIDO, correo, ip)
            raise
        if self.user_cache is not None:
            intentos.borrar_fallos_de_ingreso(correo)
        return datos


class LimitadoPasswordResetForm(PasswordResetForm):
    """Recuperación de contraseña con límite de pedidos.

    Si se supera el límite no se envía el correo, pero la pantalla es la misma:
    así no se revela nada sobre el correo ni sobre el límite.
    """

    def save(self, *args, request=None, **kwargs):
        correo = self.cleaned_data['email']
        ip = intentos.ip_de(request)
        if intentos.recuperacion_bloqueada(correo, ip):
            return
        intentos.registrar(IntentoDeAcceso.Tipo.RECUPERACION, correo, ip)
        super().save(*args, request=request, **kwargs)


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