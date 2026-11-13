"""Catálogo por carrera con disponibilidad (Release 2, S7-05).

- El lector ve solo los libros de sus carreras (por la categoría de cada libro).
- Un libro de otra carrera responde 404, aunque se escriba la dirección.
- Cada libro muestra cuántos ejemplares hay disponibles, sin datos de préstamos ni de otras personas.
- Búsqueda por título, autor o ISBN sin distinguir tildes; filtros por carrera y por categoría.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from biblioteca.models import Autor, Carrera, Categoria, Editorial, Ejemplar, Libro, Persona, Prestamo
from cuentas.lectores import crear_cuenta_de_lector
from cuentas.roles import BIBLIOTECARIO

CLAVE = 'clave-de-prueba-123'
PROGRAMACION = 'Tecnicatura Universitaria en Programación'
LOGISTICA = 'Tecnicatura Universitaria en Logística'
MECANICA = 'Ingeniería Mecánica'


class CatalogoTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.programacion = Carrera.objects.get(nombre=PROGRAMACION)
        cls.logistica = Carrera.objects.get(nombre=LOGISTICA)
        cls.mecanica = Carrera.objects.get(nombre=MECANICA)
        cls.informatica = Categoria.objects.create(nombre='Informática')
        cls.informatica.carreras.add(cls.programacion)
        cls.administracion = Categoria.objects.create(nombre='Administración')
        cls.administracion.carreras.add(cls.logistica, cls.programacion)
        cls.taller = Categoria.objects.create(nombre='Taller')
        cls.taller.carreras.add(cls.mecanica)
        datos = {
            'autor': Autor.objects.create(nombre='Ana', apellido='Gómez'),
            'editorial': Editorial.objects.create(nombre='Alfaomega'),
        }
        cls.python = Libro.objects.create(titulo='Programación en Python', isbn='9789871234567',
                                          categoria=cls.informatica, **datos)
        cls.logistica_libro = Libro.objects.create(titulo='Gestión Logística', categoria=cls.administracion, **datos)
        cls.torneria = Libro.objects.create(titulo='Tornería Básica', categoria=cls.taller,
                                            autor=Autor.objects.create(nombre='Luis', apellido='Núñez'),
                                            editorial=datos['editorial'])

        # Ejemplares de Python: uno disponible, uno prestado y uno dado de baja.
        cls.bibliotecario = get_user_model().objects.create_user(
            username='31222333', email='bibliotecario@example.com', password=CLAVE
        )
        cls.bibliotecario.groups.add(Group.objects.get(name=BIBLIOTECARIO))
        Ejemplar.objects.create(codigo_inventario='PY-1', libro=cls.python)
        prestado = Ejemplar.objects.create(codigo_inventario='PY-2', libro=cls.python)
        Ejemplar.objects.create(codigo_inventario='PY-3', libro=cls.python, activo=False,
                                motivo_baja=Ejemplar.MotivoBaja.PERDIDO, fecha_baja=timezone.localdate())
        cls.otra_persona = Persona.objects.create(nombre='Carlos', apellido='Ruiz', documento='40999888', tipo='ALUMNO')
        hoy = timezone.localdate()
        Prestamo.objects.create(persona=cls.otra_persona, ejemplar=prestado, usuario_sistema=cls.bibliotecario,
                                fecha_prestamo=hoy, fecha_vencimiento=hoy + timedelta(days=14))

        cls.persona = Persona.objects.create(nombre='Ana', apellido='Pérez', documento='40111222', tipo='ALUMNO')
        cls.persona.carreras.add(cls.programacion)
        cls.lector = crear_cuenta_de_lector(cls.persona, 'ana.perez@alumnos.example.com')

    def setUp(self):
        self.client.force_login(self.lector)

    def catalogo(self, **parametros):
        return self.client.get(reverse('portal:catalogo'), parametros)

    def titulos(self, respuesta):
        return [libro.titulo for libro in respuesta.context['libros']]


class SoloSusCarrerasTests(CatalogoTestCase):
    def test_ve_los_libros_de_su_carrera(self):
        self.assertEqual(self.titulos(self.catalogo()), ['Gestión Logística', 'Programación en Python'])

    def test_con_varias_carreras_ve_todos_sin_repetir(self):
        # Administración es de Logística y de Programación: aparece una sola vez.
        self.persona.carreras.add(self.logistica, self.mecanica)
        self.assertEqual(
            self.titulos(self.catalogo()), ['Gestión Logística', 'Programación en Python', 'Tornería Básica']
        )

    def test_el_inicio_cuenta_cada_libro_una_vez(self):
        # Administración es de dos de sus carreras: el libro se cuenta una sola vez.
        self.persona.carreras.add(self.logistica)
        respuesta = self.client.get(reverse('portal:inicio'))
        self.assertEqual(respuesta.context['cantidad_libros'], 2)

    def test_un_libro_de_otra_carrera_no_se_puede_abrir(self):
        respuesta = self.client.get(reverse('portal:libro', args=[self.torneria.pk]))
        self.assertEqual(respuesta.status_code, 404)

    def test_un_libro_sin_carrera_no_aparece(self):
        sin_carrera = Categoria.objects.create(nombre='Varios')
        libro = Libro.objects.create(titulo='Sin clasificar', categoria=sin_carrera,
                                     autor=self.python.autor, editorial=self.python.editorial)
        self.assertNotIn('Sin clasificar', self.titulos(self.catalogo()))
        self.assertEqual(self.client.get(reverse('portal:libro', args=[libro.pk])).status_code, 404)

    def test_si_le_quitan_la_carrera_deja_de_verlo(self):
        self.persona.carreras.clear()
        self.assertEqual(self.titulos(self.catalogo()), [])
        self.assertContains(self.catalogo(), 'Todavía no hay libros para tus carreras')


class DisponibilidadTests(CatalogoTestCase):
    def test_cuenta_solo_los_activos_sin_prestar(self):
        libro = next(l for l in self.catalogo().context['libros'] if l.pk == self.python.pk)
        self.assertEqual((libro.ejemplares_disponibles, libro.ejemplares_activos), (1, 2))

    def test_el_detalle_muestra_la_disponibilidad(self):
        respuesta = self.client.get(reverse('portal:libro', args=[self.python.pk]))
        self.assertContains(respuesta, '1 disponible')
        self.assertContains(respuesta, 'de 2 ejemplares')
        self.assertContains(respuesta, 'Podés pedirlo prestado en la biblioteca.')

    def test_sin_ejemplares(self):
        respuesta = self.client.get(reverse('portal:libro', args=[self.logistica_libro.pk]))
        self.assertContains(respuesta, 'Sin ejemplares')

    def test_no_muestra_datos_de_prestamos_ni_de_otras_personas(self):
        for respuesta in (self.catalogo(), self.client.get(reverse('portal:libro', args=[self.python.pk]))):
            for dato in ('Ruiz', '40999888', 'PY-2', 'Vencimiento'):
                with self.subTest(dato=dato):
                    self.assertNotContains(respuesta, dato)

    def test_la_cantidad_de_consultas_no_depende_de_los_libros(self):
        with CaptureQueriesContext(connection) as pocas:
            self.catalogo()
        for numero in range(10):
            libro = Libro.objects.create(titulo=f'Libro {numero}', categoria=self.informatica,
                                         autor=self.python.autor, editorial=self.python.editorial)
            Ejemplar.objects.create(codigo_inventario=f'L-{numero}', libro=libro)
        with CaptureQueriesContext(connection) as muchas:
            self.catalogo()
        self.assertEqual(len(pocas), len(muchas))


class BusquedaYFiltrosTests(CatalogoTestCase):
    def test_busca_por_titulo_sin_tildes(self):
        self.assertEqual(self.titulos(self.catalogo(q='programacion')), ['Programación en Python'])

    def test_busca_por_autor(self):
        self.assertEqual(self.titulos(self.catalogo(q='gomez')), ['Gestión Logística', 'Programación en Python'])

    def test_busca_por_isbn_con_guiones(self):
        self.assertEqual(self.titulos(self.catalogo(q='978-987-1234')), ['Programación en Python'])

    def test_la_busqueda_no_muestra_libros_de_otras_carreras(self):
        self.assertEqual(self.titulos(self.catalogo(q='torneria')), [])
        self.assertContains(self.catalogo(q='torneria'), 'No hay libros que coincidan')

    def test_filtra_por_categoria(self):
        self.assertEqual(self.titulos(self.catalogo(categoria=self.informatica.pk)), ['Programación en Python'])

    def test_filtra_por_carrera(self):
        self.persona.carreras.add(self.mecanica)
        self.assertEqual(self.titulos(self.catalogo(carrera=self.mecanica.pk)), ['Tornería Básica'])

    def test_una_carrera_o_categoria_ajena_se_ignora(self):
        self.assertEqual(
            self.titulos(self.catalogo(carrera=self.mecanica.pk, categoria=self.taller.pk)),
            ['Gestión Logística', 'Programación en Python'],
        )
        self.assertEqual(len(self.titulos(self.catalogo(carrera='abc', categoria='xyz'))), 2)

    def test_las_categorias_del_filtro_son_solo_las_suyas(self):
        categorias = list(self.catalogo().context['categorias'])
        self.assertEqual(categorias, [self.administracion, self.informatica])

    def test_la_paginacion_conserva_los_filtros(self):
        for numero in range(25):
            Libro.objects.create(titulo=f'Python {numero:02d}', categoria=self.informatica,
                                 autor=self.python.autor, editorial=self.python.editorial)
        respuesta = self.catalogo(q='python')
        self.assertEqual(len(respuesta.context['libros']), 20)
        self.assertContains(respuesta, '?q=python&amp;page=2')


class AccesoAlCatalogoTests(CatalogoTestCase):
    def test_el_menu_tiene_catalogo_marcado(self):
        for url in (reverse('portal:catalogo'), reverse('portal:libro', args=[self.python.pk])):
            with self.subTest(url=url):
                self.assertContains(self.client.get(url), f'href="{reverse("portal:catalogo")}" aria-current="page"')

    def test_el_personal_y_sin_sesion_no_entran(self):
        self.client.force_login(self.bibliotecario)
        self.assertEqual(self.catalogo().status_code, 403)
        self.client.logout()
        respuesta = self.catalogo()
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse('login'), respuesta['Location'])
