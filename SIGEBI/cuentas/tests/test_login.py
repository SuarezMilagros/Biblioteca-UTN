"""Inicio de sesión por correo electrónico (Release 1).

Un correo inexistente, una contraseña incorrecta, una cuenta inactiva o un correo
repetido muestran el mismo mensaje: así nadie puede averiguar qué cuentas existen.
"""
from django.contrib.auth import SESSION_KEY, authenticate, get_user_model
from django.test import TestCase
from django.urls import reverse

from cuentas.backends import CorreoBackend

CLAVE = 'clave-de-prueba-123'
MENSAJE_GENERICO = 'El correo o la contraseña no son correctos.'


class LoginPorCorreoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(
            username='31222333', email='ana.perez@example.com', password=CLAVE
        )

    def iniciar_sesion(self, correo, clave=CLAVE):
        return self.client.post(reverse('login'), {'username': correo, 'password': clave})

    def test_la_pantalla_pide_correo_electronico(self):
        respuesta = self.client.get(reverse('login'))
        self.assertContains(respuesta, 'Correo electrónico')

    def test_correo_y_contrasena_validos_inician_sesion(self):
        respuesta = self.iniciar_sesion('ana.perez@example.com')
        self.assertRedirects(respuesta, reverse('biblioteca:inicio'))
        self.assertIn(SESSION_KEY, self.client.session)

    def test_el_correo_no_distingue_mayusculas(self):
        respuesta = self.iniciar_sesion('ANA.Perez@Example.com')
        self.assertRedirects(respuesta, reverse('biblioteca:inicio'))

    def test_el_documento_no_inicia_sesion(self):
        respuesta = self.iniciar_sesion('31222333')
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_contrasena_incorrecta_muestra_mensaje_generico(self):
        respuesta = self.iniciar_sesion('ana.perez@example.com', clave='clave-equivocada-123')
        self.assertContains(respuesta, MENSAJE_GENERICO)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_correo_inexistente_muestra_el_mismo_mensaje(self):
        respuesta = self.iniciar_sesion('nadie@example.com')
        self.assertContains(respuesta, MENSAJE_GENERICO)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_cuenta_inactiva_muestra_el_mismo_mensaje(self):
        self.usuario.is_active = False
        self.usuario.save()
        respuesta = self.iniciar_sesion('ana.perez@example.com')
        self.assertContains(respuesta, MENSAJE_GENERICO)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_correo_repetido_no_inicia_sesion(self):
        get_user_model().objects.create_user(
            username='40555666', email='ANA.PEREZ@example.com', password=CLAVE
        )
        respuesta = self.iniciar_sesion('ana.perez@example.com')
        self.assertContains(respuesta, MENSAJE_GENERICO)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_campos_vacios_no_inician_sesion(self):
        respuesta = self.iniciar_sesion('', clave='')
        self.assertIn('username', respuesta.context['form'].errors)
        self.assertIn('password', respuesta.context['form'].errors)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_authenticate_de_django_usa_el_correo(self):
        self.assertEqual(authenticate(username='ana.perez@example.com', password=CLAVE), self.usuario)


class CorreoBackendTests(TestCase):
    def test_documento_no_autentica(self):
        usuario = get_user_model().objects.create_user(
            username='31222333', email='ana.perez@example.com', password=CLAVE
        )
        self.assertIsNone(CorreoBackend().authenticate(None, username=usuario.username, password=CLAVE))

    def test_correo_vacio_nunca_autentica(self):
        # Una cuenta sin correo no debe entrar con un correo vacío.
        get_user_model().objects.create_user(username='50777888', email='', password=CLAVE)
        self.assertIsNone(CorreoBackend().authenticate(None, username='', password=CLAVE))
