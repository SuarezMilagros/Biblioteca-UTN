"""Ajustes de cuentas y seguridad (Release 1, grupos C y D de decisiones).

- CA-A9: dos altas o ediciones simultáneas con el mismo documento o correo no dan error 500.
- CA-A8 y CA-R5: si falla el envío del correo, la cuenta se crea igual y el reenvío avisa.
- La sesión dura 8 horas.
- El botón "Salir" muestra el nombre de la persona.
- La pantalla de ingreso ofrece recuperar la contraseña.
"""
import smtplib
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from cuentas.forms import UsuarioForm
from cuentas.roles import ADMINISTRATIVO, BIBLIOTECARIO

CLAVE = 'clave-de-prueba-123'


class AjustesTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.administrativo = Usuario.objects.create_user(
            username='32333444', email='administrativo@example.com', password=CLAVE,
            first_name='Ana', last_name='Administrativa',
        )
        cls.administrativo.groups.add(Group.objects.get(name=ADMINISTRATIVO))
        cls.bibliotecario = Usuario.objects.create_user(
            username='31222333', email='bibliotecario@example.com', password=CLAVE,
            first_name='Bruno', last_name='Biblio',
        )
        cls.bibliotecario.groups.add(Group.objects.get(name=BIBLIOTECARIO))

    def setUp(self):
        self.client.force_login(self.administrativo)

    def datos(self, **cambios):
        datos = {
            'username': '40111222', 'first_name': 'Lucía', 'last_name': 'Paz',
            'email': 'lucia.paz@example.com', 'rol': BIBLIOTECARIO, 'is_active': 'on',
        }
        datos.update(cambios)
        return datos

    def cantidad(self):
        return get_user_model().objects.count()


class AltasSimultaneasTests(AjustesTestCase):
    """Se simula que la otra alta ya se guardó: el formulario no ve el duplicado, pero la base sí."""

    def sin_validar_duplicados(self):
        return mock.patch.multiple(
            UsuarioForm,
            validate_unique=lambda form: None,
            clean_email=lambda form: form.cleaned_data['email'],
        )

    def test_documento_repetido_en_simultaneo(self):
        antes = self.cantidad()
        with self.sin_validar_duplicados():
            respuesta = self.client.post(reverse('cuentas:usuario_create'), self.datos(username=self.bibliotecario.username))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['form'].errors['username'], ['Ya existe una cuenta con ese documento.'])
        self.assertEqual(self.cantidad(), antes)
        self.assertEqual(len(mail.outbox), 0)

    def test_correo_repetido_en_simultaneo(self):
        antes = self.cantidad()
        with self.sin_validar_duplicados():
            respuesta = self.client.post(reverse('cuentas:usuario_create'), self.datos(email='BIBLIOTECARIO@example.com'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['form'].errors['email'], ['Ya existe una cuenta con ese correo.'])
        self.assertEqual(self.cantidad(), antes)

    def test_edicion_con_correo_repetido_en_simultaneo(self):
        otra = get_user_model().objects.create_user(
            username='40999888', email='otra@example.com', password=CLAVE, first_name='Otra', last_name='Cuenta'
        )
        otra.groups.add(Group.objects.get(name=BIBLIOTECARIO))
        url = reverse('cuentas:usuario_update', args=[otra.pk])
        with self.sin_validar_duplicados():
            respuesta = self.client.post(url, self.datos(username=otra.username, email=self.bibliotecario.email))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['form'].errors['email'], ['Ya existe una cuenta con ese correo.'])
        otra.refresh_from_db()
        self.assertEqual(otra.email, 'otra@example.com')


class FallaDelCorreoTests(AjustesTestCase):
    def test_si_falla_el_envio_la_cuenta_se_crea_y_se_avisa(self):
        with mock.patch('cuentas.views.enviar_correo_definicion', side_effect=smtplib.SMTPException('sin servidor')):
            respuesta = self.client.post(reverse('cuentas:usuario_create'), self.datos(), follow=True)
        self.assertTrue(get_user_model().objects.filter(username='40111222').exists())
        self.assertContains(respuesta, 'no se pudo enviar el correo de definición')

    def test_si_falla_el_reenvio_se_avisa_sin_error_500(self):
        cuenta = get_user_model().objects.create_user(
            username='40111222', email='lucia.paz@example.com', first_name='Lucía', last_name='Paz'
        )
        cuenta.set_unusable_password()
        cuenta.save()
        cuenta.groups.add(Group.objects.get(name=BIBLIOTECARIO))
        with mock.patch('cuentas.views.enviar_correo_definicion', side_effect=OSError('red caída')):
            respuesta = self.client.post(
                reverse('cuentas:usuario_reenviar_definicion', args=[cuenta.pk]), follow=True
            )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'No se pudo enviar el correo.')


class SesionYMenuTests(AjustesTestCase):
    def test_la_sesion_dura_ocho_horas(self):
        self.assertEqual(settings.SESSION_COOKIE_AGE, 8 * 60 * 60)
        self.client.get(reverse('biblioteca:inicio'))
        self.assertEqual(self.client.session.get_expiry_age(), 8 * 60 * 60)

    def test_el_boton_salir_muestra_el_nombre(self):
        respuesta = self.client.get(reverse('biblioteca:inicio'))
        self.assertContains(respuesta, 'Salir (Ana)')
        self.assertNotContains(respuesta, 'Salir (32333444)')

    def test_sin_nombre_muestra_el_documento(self):
        sin_nombre = get_user_model().objects.create_user(username='50111222', email='x@example.com', password=CLAVE)
        sin_nombre.groups.add(Group.objects.get(name=BIBLIOTECARIO))
        self.client.force_login(sin_nombre)
        self.assertContains(self.client.get(reverse('biblioteca:inicio')), 'Salir (50111222)')


class PantallaDeIngresoTests(TestCase):
    def test_ofrece_recuperar_la_contrasena(self):
        respuesta = self.client.get(reverse('login'))
        self.assertContains(respuesta, 'href="' + reverse('password_reset') + '"')
        self.assertContains(respuesta, '¿Olvidaste tu contraseña?')
