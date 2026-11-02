"""Seguridad de la configuración (Release 1, etapa 7).

- El admin de Django es solo para superusuarios (ver config/admin.py).
- Los hosts permitidos se leen de DJANGO_ALLOWED_HOSTS (ver config/settings.py).
- collectstatic tiene una carpeta de destino definida.
"""
import json
import os
import subprocess
import sys

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from cuentas.roles import ADMINISTRATIVO

CLAVE = 'clave-de-prueba-muy-segura-7'


class AdminSoloParaSuperusuariosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        usuarios = get_user_model().objects
        cls.superusuario = usuarios.create_superuser(
            username='10000001', email='root@example.com', password=CLAVE,
        )
        cls.staff = usuarios.create_user(
            username='10000002', email='staff@example.com', password=CLAVE, is_staff=True,
        )
        cls.staff.groups.add(Group.objects.get(name=ADMINISTRATIVO))

    def assertVaAlLoginDelAdmin(self, respuesta):
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse('admin:login'), respuesta['Location'])

    def test_anonimo_no_entra_al_admin(self):
        self.assertVaAlLoginDelAdmin(self.client.get(reverse('admin:index')))

    def test_staff_sin_superusuario_no_entra_al_admin(self):
        self.client.force_login(self.staff)
        self.assertVaAlLoginDelAdmin(self.client.get(reverse('admin:index')))

    def test_superusuario_entra_al_admin(self):
        self.client.force_login(self.superusuario)
        self.assertEqual(self.client.get(reverse('admin:index')).status_code, 200)


class AllowedHostsTests(TestCase):
    def hosts_con_variable(self, valor):
        """Carga config/settings.py en un proceso nuevo, con DJANGO_ALLOWED_HOSTS fijada."""
        entorno = {**os.environ, 'DJANGO_ALLOWED_HOSTS': valor}
        codigo = 'import json; from config import settings; print(json.dumps(settings.ALLOWED_HOSTS))'
        resultado = subprocess.run(
            [sys.executable, '-c', codigo],
            cwd=settings.BASE_DIR,
            env=entorno,
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(resultado.stdout)

    def test_hosts_se_toman_de_la_variable_separados_por_coma(self):
        self.assertEqual(
            self.hosts_con_variable('sigebi.utn.edu.ar, 10.0.0.5'),
            ['sigebi.utn.edu.ar', '10.0.0.5'],
        )

    def test_variable_vacia_no_acepta_ningun_host(self):
        self.assertEqual(self.hosts_con_variable(''), [])


class ArchivosEstaticosTests(TestCase):
    def test_collectstatic_tiene_carpeta_de_destino(self):
        self.assertEqual(settings.STATIC_ROOT, settings.BASE_DIR / 'staticfiles')
