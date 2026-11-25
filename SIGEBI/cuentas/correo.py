"""Correo para que una cuenta sin contraseña la defina (Release 1, etapa 5).

Usa el mismo enlace de recuperación de Django: vence a la hora y es de un solo uso.

ERRORES_DE_ENVIO: lo que puede fallar al enviar un correo, por SMTP (Gmail) o por la API de Brevo (Railway).
Todo el sistema lo usa para avisar "no se pudo enviar" en lugar de mostrar un error 500.
"""
import smtplib

from anymail.exceptions import AnymailError
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

ERRORES_DE_ENVIO = (smtplib.SMTPException, OSError, AnymailError)


def enviar_correo_definicion(request, usuario):
    uid = urlsafe_base64_encode(force_bytes(usuario.pk))
    token = default_token_generator.make_token(usuario)
    enlace = request.build_absolute_uri(
        reverse('password_reset_confirm', kwargs={'uidb64': uid, 'token': token})
    )
    contexto = {'usuario': usuario, 'enlace': enlace}
    asunto = render_to_string('registration/cuenta_definicion_asunto.txt', contexto).strip()
    cuerpo = render_to_string('registration/cuenta_definicion_correo.txt', contexto)
    send_mail(asunto, cuerpo, None, [usuario.email])
