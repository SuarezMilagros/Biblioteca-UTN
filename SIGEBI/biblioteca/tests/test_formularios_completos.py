"""Cada pantalla con formulario muestra todos los campos de su formulario (control general, QA del Sprint 8).

El QA del Sprint 8 encontró que el campo "Tipo" del ejemplar existía en el formulario pero no en la pantalla:
las pruebas enviaban el dato directamente y no lo notaban, y al editar una copia desde la pantalla se guardaba
como original. Esta prueba recorre las pantallas de alta y edición y compara los campos del formulario con los
que realmente aparecen en el HTML.
"""
import re
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings
from django.urls import reverse

from biblioteca.models import Autor, Carrera, Categoria, Editorial, Ejemplar, Libro, Persona
from cuentas.lectores import crear_cuenta_de_lector
from cuentas.roles import ADMINISTRATIVO

CARPETA = tempfile.mkdtemp(prefix='sigebi-formularios-')


@override_settings(MATERIAL_DIGITAL_ROOT=CARPETA)
class FormulariosCompletosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.administrativo = get_user_model().objects.create_user(
            username='31222333', email='admin@example.com', first_name='Ana', last_name='Gómez')
        cls.administrativo.groups.add(Group.objects.get(name=ADMINISTRATIVO))
        cls.carrera = Carrera.objects.order_by('pk').first()
        cls.categoria = Categoria.objects.create(nombre='Informática')
        cls.categoria.carreras.add(cls.carrera)
        cls.libro = Libro.objects.create(titulo='Python', categoria=cls.categoria,
                                         autor=Autor.objects.create(nombre='Ana', apellido='Ruiz'),
                                         editorial=Editorial.objects.create(nombre='Norte'))
        cls.ejemplar = Ejemplar.objects.create(codigo_inventario='PY-1', libro=cls.libro, tipo='COPIA')
        cls.persona = Persona.objects.create(nombre='Luis', apellido='Pérez', documento='40111222', tipo='ALUMNO')
        cls.persona.carreras.add(cls.carrera)
        cls.lector = crear_cuenta_de_lector(cls.persona, 'luis@alumnos.example.com')

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(CARPETA, ignore_errors=True)

    def campos_que_faltan(self, url):
        respuesta = self.client.get(url)
        self.assertEqual(respuesta.status_code, 200, url)
        nombres = set(re.findall(r'name="([a-z_0-9]+)"', respuesta.content.decode()))
        formulario = respuesta.context['form']
        return [campo for campo in formulario.fields if formulario[campo].html_name not in nombres]

    def test_pantallas_del_personal(self):
        self.client.force_login(self.administrativo)
        pantallas = [
            reverse('biblioteca:categoria_create'), reverse('biblioteca:categoria_update', args=[self.categoria.pk]),
            reverse('biblioteca:carrera_create'), reverse('biblioteca:carrera_update', args=[self.carrera.pk]),
            reverse('biblioteca:autor_create'), reverse('biblioteca:editorial_create'),
            reverse('biblioteca:libro_create'), reverse('biblioteca:libro_update', args=[self.libro.pk]),
            reverse('biblioteca:ejemplar_create'), reverse('biblioteca:ejemplar_update', args=[self.ejemplar.pk]),
            reverse('biblioteca:persona_create'), reverse('biblioteca:persona_update', args=[self.persona.pk]),
            reverse('biblioteca:material_create'), reverse('biblioteca:prestamo_create', args=[self.ejemplar.pk]),
            reverse('cuentas:usuario_create'),
        ]
        for url in pantallas:
            with self.subTest(url=url):
                self.assertEqual(self.campos_que_faltan(url), [])

    def test_compartir_material_en_el_portal(self):
        self.client.force_login(self.lector)
        self.assertEqual(self.campos_que_faltan(reverse('portal:material_compartir')), [])
