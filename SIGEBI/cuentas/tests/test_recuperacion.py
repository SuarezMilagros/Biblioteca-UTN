"""Recuperación y cambio de contraseña (Release 1).

El enlace se envía por correo solo a cuentas activas con contraseña definida.
Quien lo pide recibe la misma respuesta exista o no la cuenta. El enlace vence
a la hora y deja de servir después de cambiar la contraseña.
"""
from datetime import datetime, timedelta
from re import search
from unittest import mock

from django.contrib.auth import SESSION_KEY, get_user_model
from django.contrib.auth.tokens import PasswordResetTokenGenerator, default_token_generator
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

CORREO = 'ana.perez@example.com'
CLAVE_VIEJA = 'clave-vieja-123'
CLAVE_NUEVA = 'clave-nueva-456-segura'


def enlace_del_ultimo_correo():
    return search(r'http://testserver(\S+)', mail.outbox[-1].body).group(1)


class RecuperacionDeClaveTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(
            username='31222333', email=CORREO, password=CLAVE_VIEJA
        )

    def pedir_recuperacion(self, correo):
        return self.client.post(reverse('password_reset'), {'email': correo})

    def url_de_enlace(self, token=None):
        uid = urlsafe_base64_encode(force_bytes(self.usuario.pk))
        token = token or default_token_generator.make_token(self.usuario)
        return reverse('password_reset_confirm', kwargs={'uidb64': uid, 'token': token})

    def url_para_elegir_clave(self):
        # Al abrir el enlace, Django guarda el token en la sesión y lo cambia por "set-password".
        uid = urlsafe_base64_encode(force_bytes(self.usuario.pk))
        return reverse('password_reset_confirm', kwargs={'uidb64': uid, 'token': 'set-password'})

    def elegir_clave(self, clave=CLAVE_NUEVA):
        return self.client.post(
            self.url_para_elegir_clave(), {'new_password1': clave, 'new_password2': clave}
        )

    def test_la_pantalla_pide_el_correo(self):
        respuesta = self.client.get(reverse('password_reset'))
        self.assertContains(respuesta, 'Correo electrónico')

    def test_correo_registrado_envia_un_enlace(self):
        respuesta = self.pedir_recuperacion(CORREO)
        self.assertRedirects(respuesta, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [CORREO])
        self.assertIn('SIGEBI', mail.outbox[0].subject)

    def test_el_enlace_del_correo_abre_el_formulario(self):
        self.pedir_recuperacion(CORREO)
        respuesta = self.client.get(enlace_del_ultimo_correo(), follow=True)
        self.assertTrue(respuesta.context['validlink'])
        self.assertContains(respuesta, 'Nueva contraseña')

    def test_correo_inexistente_responde_igual_y_no_envia(self):
        respuesta_registrado = self.pedir_recuperacion(CORREO)
        mail.outbox.clear()
        respuesta_inexistente = self.pedir_recuperacion('nadie@example.com')
        self.assertEqual(respuesta_inexistente.status_code, respuesta_registrado.status_code)
        self.assertEqual(respuesta_inexistente.url, respuesta_registrado.url)
        self.assertEqual(len(mail.outbox), 0)

    def test_cuenta_inactiva_no_recibe_correo(self):
        self.usuario.is_active = False
        self.usuario.save()
        self.pedir_recuperacion(CORREO)
        self.assertEqual(len(mail.outbox), 0)

    def test_cuenta_sin_contrasena_no_recibe_correo(self):
        # Django no envía enlaces a cuentas sin contraseña definida. Esas cuentas
        # definen su contraseña con el correo de alta (etapa 5).
        self.usuario.set_unusable_password()
        self.usuario.save()
        self.pedir_recuperacion(CORREO)
        self.assertEqual(len(mail.outbox), 0)

    def test_enlace_alterado_no_sirve(self):
        token = default_token_generator.make_token(self.usuario)
        alterado = token[:-1] + ('0' if token[-1] != '0' else '1')
        respuesta = self.client.get(self.url_de_enlace(token=alterado), follow=True)
        self.assertFalse(respuesta.context['validlink'])

    def test_enlace_dentro_de_la_hora_sirve(self):
        # El token se crea con la hora real. La validación se hace 59 minutos después.
        enlace = self.url_de_enlace()
        dentro_de_59_minutos = datetime.now() + timedelta(minutes=59)
        with mock.patch.object(
            PasswordResetTokenGenerator, '_now', return_value=dentro_de_59_minutos
        ):
            respuesta = self.client.get(enlace, follow=True)
        self.assertTrue(respuesta.context['validlink'])

    def test_enlace_vencido_no_sirve(self):
        # Igual que antes, pero la validación se hace 61 minutos después.
        enlace = self.url_de_enlace()
        despues_de_61_minutos = datetime.now() + timedelta(minutes=61)
        with mock.patch.object(
            PasswordResetTokenGenerator, '_now', return_value=despues_de_61_minutos
        ):
            respuesta = self.client.get(enlace, follow=True)
        self.assertFalse(respuesta.context['validlink'])

    def test_el_enlace_sirve_una_sola_vez(self):
        enlace = self.url_de_enlace()
        self.client.get(enlace, follow=True)
        respuesta = self.elegir_clave()
        self.assertRedirects(respuesta, reverse('password_reset_complete'))
        respuesta = self.client.get(enlace)
        self.assertFalse(respuesta.context['validlink'])

    def test_la_clave_nueva_reemplaza_a_la_anterior(self):
        self.client.get(self.url_de_enlace(), follow=True)
        self.elegir_clave()
        self.assertFalse(self.client.login(username=CORREO, password=CLAVE_VIEJA))
        self.assertTrue(self.client.login(username=CORREO, password=CLAVE_NUEVA))


class CambioDeClaveTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(
            username='31222333', email=CORREO, password=CLAVE_VIEJA
        )

    def test_sin_sesion_pide_ingresar(self):
        respuesta = self.client.get(reverse('password_change'))
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(respuesta.url.startswith(reverse('login')))

    def test_cambia_la_clave_y_mantiene_la_sesion(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.post(reverse('password_change'), {
            'old_password': CLAVE_VIEJA,
            'new_password1': CLAVE_NUEVA,
            'new_password2': CLAVE_NUEVA,
        })
        self.assertRedirects(respuesta, reverse('password_change_done'))
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password(CLAVE_NUEVA))
        self.assertIn(SESSION_KEY, self.client.session)

    def test_la_clave_actual_incorrecta_no_cambia_nada(self):
        self.client.force_login(self.usuario)
        respuesta = self.client.post(reverse('password_change'), {
            'old_password': 'clave-equivocada-123',
            'new_password1': CLAVE_NUEVA,
            'new_password2': CLAVE_NUEVA,
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('old_password', respuesta.context['form'].errors)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password(CLAVE_VIEJA))
