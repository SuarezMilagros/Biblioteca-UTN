"""Catálogo grande (Sprint 6, S6-11).

- Las listas desplegables largas (libro, autor, editorial, categoría) llevan la marca `data-buscador`,
  que main.js usa para agregarles un buscador. Sin JavaScript siguen siendo listas comunes.
- Los listados de ejemplares saben qué ejemplares están prestados sin hacer una consulta por fila.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from biblioteca.models import Autor, Categoria, Editorial, Ejemplar, Libro, Persona, Prestamo
from cuentas.roles import BIBLIOTECARIO


class CatalogoGrandeTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(
            username='31222333', email='bibliotecario@example.com', password='clave-de-prueba-123'
        )
        cls.usuario.groups.add(Group.objects.get(name=BIBLIOTECARIO))
        cls.datos = {
            'categoria': Categoria.objects.create(nombre='Matemáticas'),
            'autor': Autor.objects.create(nombre='Hugo', apellido='Ledesma'),
            'editorial': Editorial.objects.create(nombre='Pearson'),
        }
        cls.libro = Libro.objects.create(titulo='Cálculo I', **cls.datos)
        cls.persona = Persona.objects.create(
            nombre='Ana', apellido='Pérez', documento='40111222', tipo=Persona.Tipo.ALUMNO
        )

    def setUp(self):
        self.client.force_login(self.usuario)

    def crear_ejemplares(self, cantidad, desde=0, libro=None):
        """Crea ejemplares; uno de cada tres queda prestado."""
        hoy = timezone.localdate()
        for numero in range(desde, desde + cantidad):
            ejemplar = Ejemplar.objects.create(codigo_inventario=f'EJ-{numero:03d}', libro=libro or self.libro)
            if numero % 3 == 0:
                Prestamo.objects.create(
                    persona=self.persona, ejemplar=ejemplar, usuario_sistema=self.usuario,
                    fecha_prestamo=hoy, fecha_vencimiento=hoy + timedelta(days=14),
                )

    def consultas(self, url):
        with CaptureQueriesContext(connection) as capturadas:
            respuesta = self.client.get(url)
        self.assertEqual(respuesta.status_code, 200)
        return len(capturadas)


class BuscadorEnListasTests(CatalogoGrandeTestCase):
    def test_las_listas_largas_llevan_buscador(self):
        casos = {
            reverse('biblioteca:libro_create'): ('Buscar categoría', 'Buscar autor', 'Buscar editorial'),
            reverse('biblioteca:ejemplar_create'): ('Buscar libro por título',),
        }
        for url, textos in casos.items():
            respuesta = self.client.get(url)
            for texto in textos:
                with self.subTest(url=url, texto=texto):
                    self.assertContains(respuesta, f'data-buscador="{texto}"')

    def test_la_lista_sigue_teniendo_todas_las_opciones_sin_javascript(self):
        for numero in range(30):
            Libro.objects.create(titulo=f'Libro {numero:02d}', **self.datos)
        respuesta = self.client.get(reverse('biblioteca:ejemplar_create'))
        self.assertEqual(len(respuesta.context['form'].fields['libro'].queryset), 31)
        self.assertContains(respuesta, '>Libro 29</option>')

    def test_las_listas_cortas_no_llevan_buscador(self):
        respuesta = self.client.get(reverse('biblioteca:persona_create'))
        self.assertNotContains(respuesta, 'data-buscador')

    def test_agregar_ejemplar_desde_el_libro_lo_deja_elegido(self):
        respuesta = self.client.get(reverse('biblioteca:ejemplar_create') + f'?libro={self.libro.pk}')
        self.assertEqual(respuesta.context['form'].initial['libro'], self.libro.pk)


class ConsultasPorListadoTests(CatalogoGrandeTestCase):
    def test_el_listado_de_ejemplares_no_hace_una_consulta_por_fila(self):
        self.crear_ejemplares(3)
        con_pocos = self.consultas(reverse('biblioteca:ejemplar_list'))
        self.crear_ejemplares(15, desde=3)
        con_muchos = self.consultas(reverse('biblioteca:ejemplar_list'))
        self.assertEqual(con_pocos, con_muchos)

    def test_el_detalle_del_libro_no_hace_una_consulta_por_ejemplar(self):
        self.crear_ejemplares(2)
        con_pocos = self.consultas(reverse('biblioteca:libro_detail', args=[self.libro.pk]))
        self.crear_ejemplares(10, desde=2)
        con_muchos = self.consultas(reverse('biblioteca:libro_detail', args=[self.libro.pk]))
        self.assertEqual(con_pocos, con_muchos)

    def test_el_listado_muestra_el_estado_correcto(self):
        self.crear_ejemplares(2)  # EJ-000 prestado, EJ-001 disponible
        Ejemplar.objects.create(
            codigo_inventario='EJ-BAJA', libro=self.libro, activo=False,
            motivo_baja=Ejemplar.MotivoBaja.PERDIDO, fecha_baja=timezone.localdate(),
        )
        respuesta = self.client.get(reverse('biblioteca:ejemplar_list') + '?estado=todos')
        filas = {ejemplar.codigo_inventario: ejemplar for ejemplar in respuesta.context['object_list']}
        self.assertTrue(filas['EJ-000'].prestado)
        self.assertTrue(filas['EJ-001'].disponible)
        self.assertFalse(filas['EJ-BAJA'].disponible)
        self.assertContains(respuesta, 'badge-prestado', count=1)
        self.assertContains(respuesta, 'badge-disponible', count=1)
        self.assertContains(respuesta, 'badge-baja', count=1)


class EstadoDePrestamoTests(CatalogoGrandeTestCase):
    def test_con_estado_de_prestamo_no_vuelve_a_consultar(self):
        self.crear_ejemplares(2)
        ejemplares = list(Ejemplar.objects.con_estado_de_prestamo().order_by('codigo_inventario'))
        with self.assertNumQueries(0):
            self.assertEqual([ejemplar.prestado for ejemplar in ejemplares], [True, False])

    def test_sin_la_anotacion_consulta_la_base(self):
        self.crear_ejemplares(1)
        ejemplar = Ejemplar.objects.get(codigo_inventario='EJ-000')
        with self.assertNumQueries(1):
            self.assertTrue(ejemplar.prestado)

    def test_despues_de_devolver_el_estado_se_actualiza(self):
        self.crear_ejemplares(1)
        Prestamo.objects.update(fecha_devolucion=timezone.localdate())
        ejemplar = Ejemplar.objects.con_estado_de_prestamo().get(codigo_inventario='EJ-000')
        self.assertFalse(ejemplar.prestado)
        self.assertTrue(ejemplar.disponible)
