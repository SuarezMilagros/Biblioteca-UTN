"""Envía un correo de prueba para comprobar la configuración de correo (D-C6).

Uso: python manage.py probar_correo destino@ejemplo.com

Nunca muestra la contraseña: solo informa el servidor, el puerto y el usuario.
"""
import smtplib

from anymail.exceptions import AnymailAPIError
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email

from cuentas.correo import ERRORES_DE_ENVIO


class Command(BaseCommand):
    help = 'Envía un correo de prueba para comprobar la configuración de correo de SIGEBI.'

    def add_arguments(self, parser):
        parser.add_argument('destino', help='Correo al que se envía la prueba.')

    def handle(self, *args, destino, **options):
        try:
            validate_email(destino)
        except ValidationError:
            raise CommandError(f'"{destino}" no es un correo válido.')

        if 'console' in settings.EMAIL_BACKEND:
            self.stdout.write(self.style.WARNING(
                'EMAIL_HOST está vacío: el correo no se envía, se muestra abajo en esta consola.'
            ))
        elif 'anymail.backends.brevo' in settings.EMAIL_BACKEND:
            self.stdout.write(f'Enviando con la API de Brevo (remitente: {settings.DEFAULT_FROM_EMAIL})...')
        else:
            self.stdout.write(
                f'Enviando con {settings.EMAIL_HOST}:{settings.EMAIL_PORT} '
                f'(usuario: {settings.EMAIL_HOST_USER or "sin usuario"})...'
            )

        try:
            send_mail(
                'Prueba de correo de SIGEBI',
                'Si recibiste este mensaje, el correo de SIGEBI está bien configurado.\n\n'
                'SIGEBI · Biblioteca UTN FRT Concepción\n',
                None,
                [destino],
            )
        except smtplib.SMTPAuthenticationError:
            raise CommandError(
                'El servidor rechazó el usuario o la contraseña. Revisá EMAIL_HOST_USER y '
                'EMAIL_HOST_PASSWORD en SIGEBI/.env (con Gmail, usá una contraseña de aplicación).'
            )
        except AnymailAPIError as error:
            if error.status_code in (401, 403):
                raise CommandError(
                    'Brevo rechazó la clave. Revisá BREVO_API_KEY en las variables del servicio '
                    '(Brevo > SMTP y API > Claves API) y que el remitente esté verificado en Brevo.'
                )
            if error.status_code is None:
                raise CommandError('No se pudo enviar el correo: no se pudo conectar con Brevo (api.brevo.com).')
            raise CommandError(f'No se pudo enviar el correo: Brevo respondió {error.status_code}.')
        except ERRORES_DE_ENVIO as error:
            raise CommandError(f'No se pudo enviar el correo: {error.__class__.__name__}: {error}')

        self.stdout.write(self.style.SUCCESS(f'Correo de prueba enviado a {destino}.'))
