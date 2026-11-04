"""Catálogo grande (Sprint 6, S6-11).

- Libros y Ejemplares se listan al buscar, filtrar o pedir «Ver todos»; al entrar solo se muestra el total.
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
        con_pocos = self.consultas(reverse('biblioteca:ejemplar_list') + '?todos=1')
        self.crear_ejemplares(15, desde=3)
        con_muchos = self.consultas(reverse('biblioteca:ejemplar_list') + '?todos=1')
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


class BuscarAntesDeListarTests(CatalogoGrandeTestCase):
    """Libros y Ejemplares: al entrar no se lista el catálogo; se lista al buscar, filtrar o pedir «Ver todos»."""

    def test_al_entrar_a_libros_no_se_listan_registros(self):
        Libro.objects.create(titulo='Física', **self.datos)
        respuesta = self.client.get(reverse('biblioteca:libro_list'))
        self.assertFalse(respuesta.context['object_list'])
        self.assertContains(respuesta, 'El catálogo tiene 2 títulos.')
        self.assertContains(respuesta, 'href="?todos=1"')
        self.assertNotContains(respuesta, 'Cálculo I</a>')

    def test_al_entrar_a_ejemplares_no_se_listan_registros(self):
        self.crear_ejemplares(4)
        respuesta = self.client.get(reverse('biblioteca:ejemplar_list'))
        self.assertFalse(respuesta.context['object_list'])
        self.assertContains(respuesta, 'Hay 4 ejemplares activos.')
        self.assertNotContains(respuesta, 'EJ-001</a>')
        self.assertNotContains(respuesta, 'Exportar CSV')

    def test_al_entrar_no_se_consulta_el_listado(self):
        self.crear_ejemplares(3)
        with CaptureQueriesContext(connection) as capturadas:
            self.client.get(reverse('biblioteca:ejemplar_list'))
        sobre_ejemplares = [c['sql'] for c in capturadas.captured_queries if 'FROM "biblioteca_ejemplar"' in c['sql']]
        # Solo se cuenta el total; no se trae ninguna fila de ejemplares.
        self.assertEqual(len(sobre_ejemplares), 1)
        self.assertTrue(sobre_ejemplares[0].startswith('SELECT COUNT(*)'))

    def test_al_buscar_se_listan_los_resultados(self):
        Libro.objects.create(titulo='Física', **self.datos)
        respuesta = self.client.get(reverse('biblioteca:libro_list'), {'q': 'calculo'})
        self.assertEqual([libro.titulo for libro in respuesta.context['object_list']], ['Cálculo I'])

    def test_ver_todos_lista_y_la_paginacion_lo_conserva(self):
        for numero in range(25):
            Libro.objects.create(titulo=f'Libro {numero:02d}', **self.datos)
        respuesta = self.client.get(reverse('biblioteca:libro_list'), {'todos': '1'})
        self.assertEqual(len(respuesta.context['object_list']), 20)
        self.assertContains(respuesta, '?todos=1&amp;page=2')
        self.assertContains(respuesta, 'Quitar búsqueda')

    def test_un_filtro_de_estado_tambien_lista(self):
        Ejemplar.objects.create(
            codigo_inventario='EJ-BAJA', libro=self.libro, activo=False,
            motivo_baja=Ejemplar.MotivoBaja.PERDIDO, fecha_baja=timezone.localdate(),
        )
        respuesta = self.client.get(reverse('biblioteca:ejemplar_list'), {'estado': 'baja'})
        self.assertEqual([ejemplar.codigo_inventario for ejemplar in respuesta.context['object_list']], ['EJ-BAJA'])

    def test_el_csv_sigue_exportando_todo_sin_buscar(self):
        self.crear_ejemplares(3)
        respuesta = self.client.get(reverse('biblioteca:ejemplar_list'), {'formato': 'csv'})
        self.assertEqual(respuesta['Content-Type'], 'text/csv; charset=utf-8')
        self.assertEqual(respuesta.content.decode('utf-8-sig').count('EJ-00'), 3)

    def test_catalogo_vacio_ofrece_cargar_el_primer_libro(self):
        Libro.objects.all().delete()
        respuesta = self.client.get(reverse('biblioteca:libro_list'))
        self.assertContains(respuesta, 'Todavía no hay libros registrados.')
        self.assertNotContains(respuesta, 'Ver todos los libros')
