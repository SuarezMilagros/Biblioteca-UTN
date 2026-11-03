"""Rol que muestra la cabecera (cuentas/contexto.py)."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.test import RequestFactory, TestCase

from cuentas.contexto import interfaz
from cuentas.roles import ADMINISTRATIVO, BIBLIOTECARIO


class RolDeLaCabeceraTests(TestCase):
    def rol(self, usuario):
        solicitud = RequestFactory().get('/')
        solicitud.user = usuario
        return interfaz(solicitud).get('rol_usuario')

    def test_sin_sesion_no_aporta_datos(self):
        solicitud = RequestFactory().get('/')
        solicitud.user = AnonymousUser()
        self.assertEqual(interfaz(solicitud), {})

    def test_cada_rol(self):
        Usuario = get_user_model()
        superusuario = Usuario.objects.create_superuser(username='1', email='a@example.com', password='x')
        biblio = Usuario.objects.create_user(username='2', email='b@example.com')
        biblio.groups.add(Group.objects.get(name=BIBLIOTECARIO))
        ambos = Usuario.objects.create_user(username='3', email='c@example.com')
        ambos.groups.add(Group.objects.get(name=BIBLIOTECARIO), Group.objects.get(name=ADMINISTRATIVO))
        sin_rol = Usuario.objects.create_user(username='4', email='d@example.com')
        self.assertEqual(self.rol(superusuario), 'Superusuario')
        self.assertEqual(self.rol(biblio), BIBLIOTECARIO)
        self.assertEqual(self.rol(ambos), ADMINISTRATIVO)
        self.assertEqual(self.rol(sin_rol), 'Sin rol')
