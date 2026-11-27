"""Páginas de error propias en español: no encontrado (404), página vencida (CSRF) y error del servidor (500).

Antes, el sitio publicado (con DEBUG apagado) mostraba las páginas de Django en inglés y sin el diseño de SIGEBI,
por ejemplo cuando un alumno abría un libro de otra carrera. Las pruebas corren con DEBUG apagado, como el servidor.
"""
import re

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.http import HttpResponse
from django.template.loader import get_template
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import path, reverse
from django.views.defaults import server_error

from biblioteca.models import Autor, Carrera, Categoria, Editorial, Libro, Persona
from cuentas.lectores import crear_cuenta_de_lector
from cuentas.roles import BIBLIOTECARIO


def vista_que_falla(request):
    raise RuntimeError('falla a propósito para probar la página 500')


def vista_que_anda(request):
    return HttpResponse('ok')


# Rutas mínimas para provocar un error 500 real, pasando por el manejo de errores de Django.
urlpatterns = [path('falla/', vista_que_falla), path('anda/', vista_que_anda)]


class PaginaNoEncontradaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bibliotecario = get_user_model().objects.create_user(
            username='30111222', email='biblio@example.com', first_name='Carla', last_name='Díaz')
        cls.bibliotecario.groups.add(Group.objects.get(name=BIBLIOTECARIO))
        carreras = list(Carrera.objects.order_by('pk')[:2])
        cls.mi_carrera, cls.otra_carrera = carreras
        autor = Autor.objects.create(nombre='Ana', apellido='Ruiz')
        editorial = Editorial.objects.create(nombre='Norte')
        cls.categoria_ajena = Categoria.objects.create(nombre='Química')
        cls.categoria_ajena.carreras.add(cls.otra_carrera)
        cls.libro_ajeno = Libro.objects.create(titulo='Química orgánica avanzada', categoria=cls.categoria_ajena,
                                               autor=autor, editorial=editorial)
        persona = Persona.objects.create(nombre='Luis', apellido='Pérez', documento='40111222', tipo='ALUMNO')
        persona.carreras.add(cls.mi_carrera)
        cls.lector = crear_cuenta_de_lector(persona, 'luis@alumnos.example.com')

    def comprobar_pagina_propia(self, respuesta):
        self.assertEqual(respuesta.status_code, 404)
        self.assertTemplateUsed(respuesta, '404.html')
        contenido = respuesta.content.decode()
        self.assertIn('<html lang="es">', contenido)
        self.assertIn('No encontramos esta página', contenido)
        self.assertNotIn('Not Found', contenido)
        self.assertNotIn('The requested resource', contenido)
        return contenido

    def test_sin_sesion_muestra_la_pagina_propia_con_el_ingreso(self):
        contenido = self.comprobar_pagina_propia(self.client.get('/no-existe/'))
        self.assertIn(f'class="boton" href="{reverse("login")}"', contenido)
        self.assertIn('Ir al ingreso', contenido)

    def test_el_personal_ve_su_menu_y_vuelve_a_su_inicio(self):
        self.client.force_login(self.bibliotecario)
        contenido = self.comprobar_pagina_propia(self.client.get('/no-existe/'))
        self.assertIn('Préstamos', contenido)
        self.assertIn(f'class="boton" href="{reverse("biblioteca:inicio")}"', contenido)

    def test_un_libro_de_otra_carrera_muestra_la_pagina_propia_sin_revelar_el_libro(self):
        self.client.force_login(self.lector)
        respuesta = self.client.get(reverse('portal:libro', args=[self.libro_ajeno.pk]))
        contenido = self.comprobar_pagina_propia(respuesta)
        self.assertNotIn('Química orgánica avanzada', contenido)
        # El lector ve el menú del portal y vuelve al inicio del portal, no al del personal.
        self.assertIn('Explorar', contenido)
        self.assertIn(f'class="boton" href="{reverse("portal:inicio")}"', contenido)


class PaginaVencidaTests(TestCase):
    """Un formulario sin código de seguridad válido (CSRF) muestra la página propia, no la de Django."""

    def test_el_ingreso_sin_codigo_de_seguridad_muestra_la_pagina_vencida(self):
        cliente = Client(enforce_csrf_checks=True)
        respuesta = cliente.post(reverse('login'), {'username': 'alguien@example.com', 'password': 'x'})
        self.assertEqual(respuesta.status_code, 403)
        self.assertTemplateUsed(respuesta, '403_csrf.html')
        contenido = respuesta.content.decode()
        self.assertIn('La página venció', contenido)
        self.assertIn('no se guardó nada', contenido)
        self.assertNotIn('CSRF verification failed', contenido)
        self.assertNotIn('Forbidden', contenido)


@override_settings(ROOT_URLCONF='biblioteca.tests.test_paginas_de_error')
class ErrorDelServidorTests(TestCase):
    def test_un_error_inesperado_muestra_la_pagina_propia(self):
        cliente = Client(raise_request_exception=False)
        with self.assertLogs('django.request', level='ERROR'):
            respuesta = cliente.get('/falla/')
        self.assertEqual(respuesta.status_code, 500)
        contenido = respuesta.content.decode()
        self.assertIn('<html lang="es">', contenido)
        self.assertIn('Algo salió mal', contenido)
        self.assertIn('El error quedó registrado', contenido)
        self.assertNotIn('Server Error', contenido)
        self.assertNotIn('falla a propósito', contenido)  # el detalle no se le muestra al visitante

    def test_la_pagina_500_no_depende_de_la_base_ni_de_los_estaticos(self):
        # Si el error viene de la base, de la sesión o de los archivos estáticos, la página tiene que mostrarse igual:
        # no hereda de base.html ni usa etiquetas, salvo el comentario.
        with self.assertNumQueries(0):
            respuesta = server_error(RequestFactory().get('/'))
        self.assertEqual(respuesta.status_code, 500)
        self.assertIn('Volver al inicio', respuesta.content.decode())
        fuente = get_template('500.html').template.source
        etiquetas = set(re.findall(r'{%\s*(\w+)', fuente))
        self.assertEqual(etiquetas, {'comment', 'endcomment'})
        self.assertNotIn('{{', fuente)

    def test_las_paginas_que_andan_no_cambian(self):
        self.assertEqual(self.client.get('/anda/').content, b'ok')
