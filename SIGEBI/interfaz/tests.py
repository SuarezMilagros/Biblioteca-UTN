"""Etiquetas de plantilla compartidas (app interfaz)."""
from django.contrib.auth import get_user_model
from django.template import Context, Template
from django.test import SimpleTestCase

from interfaz.templatetags.interfaz import ICONOS, iniciales, porcentaje


class IconosTests(SimpleTestCase):
    def test_el_icono_es_decorativo_y_no_toma_foco(self):
        html = Template("{% load interfaz %}{% icono 'libro' 'grande' %}").render(Context())
        self.assertIn('aria-hidden="true"', html)
        self.assertIn('focusable="false"', html)
        self.assertIn('class="icono grande"', html)
        self.assertIn(ICONOS['libro'], html)

    def test_un_icono_desconocido_no_rompe_la_pantalla(self):
        html = Template("{% load interfaz %}{% icono 'no-existe' %}").render(Context())
        self.assertIn(ICONOS['info'], html)


class FiltrosTests(SimpleTestCase):
    def test_iniciales(self):
        Usuario = get_user_model()
        self.assertEqual(iniciales(Usuario(username='31222333', first_name='ana', last_name='pérez')), 'AP')
        self.assertEqual(iniciales(Usuario(username='31222333')), '31')

    def test_porcentaje(self):
        self.assertEqual(porcentaje(1, 3), 33)
        self.assertEqual(porcentaje(5, 0), 0)
        self.assertEqual(porcentaje(None, 4), 0)
