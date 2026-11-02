"""Menú según el rol y página de acceso no permitido (Release 1, etapa 6).

El enlace a Cuentas solo se muestra a quien puede ver el listado. Ocultarlo no
alcanza como seguridad: las vistas ya devuelven 403 (ver test_alta.py); acá se
comprueba lo que ve cada rol y que el 403 tenga una página propia de SIGEBI.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from cuentas.roles import ADMINISTRATIVO, BIBLIOTECARIO

CLAVE = 'clave-de-prueba-123'


class NavegacionPorRolTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.superusuario = Usuario.objects.create_superuser(
            username='10000001', email='superusuario@example.com', password=CLAVE
        )
        cls.administrativo = Usuario.objects.create_user(
            username='32333444', email='administrativo@example.com', password=CLAVE
        )
        cls.administrativo.groups.add(Group.objects.get(name=ADMINISTRATIVO))
        cls.bibliotecario = Usuario.objects.create_user(
            username='31222333', email='bibliotecario@example.com', password=CLAVE
        )
        cls.bibliotecario.groups.add(Group.objects.get(name=BIBLIOTECARIO))

    def enlace_a(self, nombre_url):
        return 'href="' + reverse(nombre_url) + '"'

    def test_administrativo_y_superusuario_ven_el_enlace_a_cuentas(self):
        for usuario in (self.administrativo, self.superusuario):
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)
                respuesta = self.client.get(reverse('biblioteca:inicio'))
                self.assertContains(respuesta, self.enlace_a('cuentas:usuario_list'))

    def test_bibliotecario_no_ve_el_enlace_a_cuentas(self):
        self.client.force_login(self.bibliotecario)
        respuesta = self.client.get(reverse('biblioteca:inicio'))
        self.assertNotContains(respuesta, self.enlace_a('cuentas:usuario_list'))

    def test_todos_los_roles_ven_cambiar_contrasena(self):
        for usuario in (self.bibliotecario, self.administrativo, self.superusuario):
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)
                respuesta = self.client.get(reverse('biblioteca:inicio'))
                self.assertContains(respuesta, self.enlace_a('password_change'))
                self.assertEqual(self.client.get(reverse('password_change')).status_code, 200)

    def test_sin_sesion_no_hay_menu(self):
        respuesta = self.client.get(reverse('login'))
        self.assertNotContains(respuesta, self.enlace_a('cuentas:usuario_list'))
        self.assertNotContains(respuesta, self.enlace_a('password_change'))

    def test_la_seccion_cuentas_se_marca_como_activa(self):
        self.client.force_login(self.administrativo)
        respuesta = self.client.get(reverse('cuentas:usuario_list'))
        self.assertContains(respuesta, self.enlace_a('cuentas:usuario_list') + ' aria-current="page"')
        self.assertNotContains(respuesta, self.enlace_a('biblioteca:libro_list') + ' aria-current="page"')

    def test_cambiar_contrasena_se_marca_como_activa(self):
        self.client.force_login(self.bibliotecario)
        respuesta = self.client.get(reverse('password_change'))
        self.assertContains(respuesta, self.enlace_a('password_change') + ' aria-current="page"')


class PaginaDeAccesoNoPermitidoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bibliotecario = get_user_model().objects.create_user(
            username='31222333', email='bibliotecario@example.com', password=CLAVE
        )
        cls.bibliotecario.groups.add(Group.objects.get(name=BIBLIOTECARIO))

    def test_el_403_usa_la_pagina_de_sigebi(self):
        self.client.force_login(self.bibliotecario)
        for url in (reverse('cuentas:usuario_list'), reverse('cuentas:usuario_create')):
            with self.subTest(url=url):
                respuesta = self.client.get(url)
                self.assertEqual(respuesta.status_code, 403)
                self.assertTemplateUsed(respuesta, '403.html')
                self.assertContains(respuesta, 'Acceso no permitido', status_code=403)
                # Se ve dentro del diseño de SIGEBI, con el menú y el camino de vuelta.
                self.assertContains(respuesta, 'aria-label="Principal"', status_code=403)
                self.assertContains(respuesta, self.enlace_a('biblioteca:inicio'), status_code=403)

    def enlace_a(self, nombre_url):
        return 'href="' + reverse(nombre_url) + '"'
