from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from biblioteca.models import Autor, Categoria, Editorial, Ejemplar, Libro
from biblioteca.views import MENSAJE_DATO_REPETIDO

CLAVE = 'clave-de-prueba-123'
MENSAJE_CODIGO_REPETIDO = 'Ya existe un ejemplar con ese código de inventario.'


class CatalogoBaseTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(
            username='bibliotecario', email='bibliotecario@example.com', password=CLAVE
        )
        cls.usuario.groups.add(Group.objects.get(name='Bibliotecario'))
        cls.categoria = Categoria.objects.create(nombre='Matemática')
        cls.autor = Autor.objects.create(nombre='Hugo', apellido='Ledesma')
        cls.editorial = Editorial.objects.create(nombre='Ediciones del Valle')
        cls.libro = Libro.objects.create(
            titulo='Cálculo I',
            isbn='',
            categoria=cls.categoria,
            autor=cls.autor,
            editorial=cls.editorial,
        )
        cls.ejemplar = Ejemplar.objects.create(codigo_inventario='CAL-001', libro=cls.libro)

    def setUp(self):
        self.client.force_login(self.usuario)

    def datos_libro(self, **cambios):
        datos = {
            'titulo': 'Álgebra Lineal',
            'isbn': '',
            'categoria': self.categoria.pk,
            'autor': self.autor.pk,
            'editorial': self.editorial.pk,
        }
        datos.update(cambios)
        return datos


class AccesoTests(CatalogoBaseTestCase):
    NOMBRES_PROTEGIDOS = [
        'biblioteca:inicio',
        'biblioteca:categoria_list',
        'biblioteca:categoria_create',
        'biblioteca:autor_list',
        'biblioteca:autor_create',
        'biblioteca:editorial_list',
        'biblioteca:editorial_create',
        'biblioteca:libro_list',
        'biblioteca:libro_create',
        'biblioteca:ejemplar_list',
        'biblioteca:ejemplar_create',
    ]

    def test_pantallas_redirigen_al_login_si_no_hay_sesion(self):
        self.client.logout()
        for nombre in self.NOMBRES_PROTEGIDOS:
            with self.subTest(pantalla=nombre):
                respuesta = self.client.get(reverse(nombre))
                self.assertEqual(respuesta.status_code, 302)
                self.assertIn(reverse('login'), respuesta['Location'])

    def test_pantallas_con_identificador_redirigen_al_login(self):
        self.client.logout()
        urls = [
            reverse('biblioteca:categoria_update', args=[self.categoria.pk]),
            reverse('biblioteca:autor_update', args=[self.autor.pk]),
            reverse('biblioteca:editorial_update', args=[self.editorial.pk]),
            reverse('biblioteca:libro_detail', args=[self.libro.pk]),
            reverse('biblioteca:libro_update', args=[self.libro.pk]),
            reverse('biblioteca:ejemplar_detail', args=[self.ejemplar.pk]),
            reverse('biblioteca:ejemplar_update', args=[self.ejemplar.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                respuesta = self.client.get(url)
                self.assertEqual(respuesta.status_code, 302)
                self.assertIn(reverse('login'), respuesta['Location'])

    def test_alta_sin_sesion_no_guarda_nada(self):
        self.client.logout()
        respuesta = self.client.post(
            reverse('biblioteca:categoria_create'), {'nombre': 'Intrusa', 'descripcion': ''}
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(Categoria.objects.filter(nombre='Intrusa').exists())

    def test_login_y_logout_por_post(self):
        self.client.logout()
        respuesta = self.client.post(reverse('login'), {'username': 'bibliotecario@example.com', 'password': CLAVE})
        self.assertRedirects(respuesta, reverse('biblioteca:inicio'), fetch_redirect_response=False)
        respuesta = self.client.post(reverse('logout'))
        self.assertRedirects(respuesta, reverse('login'), fetch_redirect_response=False)

    def test_logout_por_get_no_esta_permitido(self):
        respuesta = self.client.get(reverse('logout'))
        self.assertEqual(respuesta.status_code, 405)


class CategoriaTests(CatalogoBaseTestCase):
    def test_alta_de_categoria(self):
        respuesta = self.client.post(
            reverse('biblioteca:categoria_create'), {'nombre': 'Informática', 'descripcion': 'Programación.'}
        )
        self.assertRedirects(respuesta, reverse('biblioteca:categoria_list'), fetch_redirect_response=False)
        self.assertTrue(Categoria.objects.filter(nombre='Informática').exists())

    def test_alta_sin_nombre_muestra_error(self):
        respuesta = self.client.post(reverse('biblioteca:categoria_create'), {'nombre': '', 'descripcion': ''})
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('nombre', respuesta.context['form'].errors)

    def test_nombre_de_categoria_puede_repetirse(self):
        # Decisión del modelo: el nombre de la categoría no es único.
        respuesta = self.client.post(
            reverse('biblioteca:categoria_create'), {'nombre': 'Matemática', 'descripcion': ''}
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(Categoria.objects.filter(nombre='Matemática').count(), 2)

    def test_edicion_de_categoria(self):
        respuesta = self.client.post(
            reverse('biblioteca:categoria_update', args=[self.categoria.pk]),
            {'nombre': 'Matemáticas', 'descripcion': ''},
        )
        self.assertEqual(respuesta.status_code, 302)
        self.categoria.refresh_from_db()
        self.assertEqual(self.categoria.nombre, 'Matemáticas')

    def test_listado_incluye_categorias(self):
        respuesta = self.client.get(reverse('biblioteca:categoria_list'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Matemática')


class AutorEditorialTests(CatalogoBaseTestCase):
    def test_alta_y_edicion_de_autor(self):
        self.client.post(reverse('biblioteca:autor_create'), {'nombre': 'Laura', 'apellido': 'Benítez'})
        self.assertTrue(Autor.objects.filter(apellido='Benítez').exists())
        self.client.post(
            reverse('biblioteca:autor_update', args=[self.autor.pk]),
            {'nombre': 'Hugo', 'apellido': 'Ledesma Gómez'},
        )
        self.autor.refresh_from_db()
        self.assertEqual(self.autor.apellido, 'Ledesma Gómez')

    def test_alta_de_autor_sin_apellido_muestra_error(self):
        respuesta = self.client.post(reverse('biblioteca:autor_create'), {'nombre': 'Laura', 'apellido': ''})
        self.assertIn('apellido', respuesta.context['form'].errors)

    def test_alta_y_edicion_de_editorial(self):
        self.client.post(reverse('biblioteca:editorial_create'), {'nombre': 'Editorial Norte'})
        self.assertTrue(Editorial.objects.filter(nombre='Editorial Norte').exists())
        self.client.post(
            reverse('biblioteca:editorial_update', args=[self.editorial.pk]), {'nombre': 'Ediciones del Valle SRL'}
        )
        self.editorial.refresh_from_db()
        self.assertEqual(self.editorial.nombre, 'Ediciones del Valle SRL')


class LibroTests(CatalogoBaseTestCase):
    def test_alta_de_libro_sin_isbn(self):
        respuesta = self.client.post(reverse('biblioteca:libro_create'), self.datos_libro(isbn=''))
        self.assertEqual(respuesta.status_code, 302)
        libro = Libro.objects.get(titulo='Álgebra Lineal')
        self.assertEqual(libro.isbn, '')
        self.assertRedirects(respuesta, reverse('biblioteca:libro_detail', args=[libro.pk]), fetch_redirect_response=False)

    def test_isbn_repetido_se_permite(self):
        # Decisión del modelo: el ISBN es opcional y no es único.
        Libro.objects.create(
            titulo='Cálculo I (copia)',
            isbn='978-0-00-000004-0',
            categoria=self.categoria,
            autor=self.autor,
            editorial=self.editorial,
        )
        respuesta = self.client.post(
            reverse('biblioteca:libro_create'), self.datos_libro(isbn='978-0-00-000004-0')
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(Libro.objects.filter(isbn='978-0-00-000004-0').count(), 2)

    def test_alta_de_libro_sin_autor_muestra_error(self):
        respuesta = self.client.post(reverse('biblioteca:libro_create'), self.datos_libro(autor=''))
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('autor', respuesta.context['form'].errors)

    def test_edicion_de_libro(self):
        respuesta = self.client.post(
            reverse('biblioteca:libro_update', args=[self.libro.pk]),
            self.datos_libro(titulo='Cálculo I (2.ª edición)', isbn='978-0-00-000004-0'),
        )
        self.assertEqual(respuesta.status_code, 302)
        self.libro.refresh_from_db()
        self.assertEqual(self.libro.titulo, 'Cálculo I (2.ª edición)')
        self.assertEqual(self.libro.isbn, '978-0-00-000004-0')

    def test_busqueda_por_titulo_parcial(self):
        respuesta = self.client.get(reverse('biblioteca:libro_list'), {'q': 'lculo'})
        self.assertEqual(respuesta.status_code, 200)
        titulos = [libro.titulo for libro in respuesta.context['object_list']]
        self.assertEqual(titulos, ['Cálculo I'])

    def test_busqueda_no_distingue_mayusculas(self):
        respuesta = self.client.get(reverse('biblioteca:libro_list'), {'q': 'LCULO'})
        self.assertEqual([libro.titulo for libro in respuesta.context['object_list']], ['Cálculo I'])

    def test_busqueda_sin_texto_muestra_todos(self):
        respuesta = self.client.get(reverse('biblioteca:libro_list'), {'q': ''})
        self.assertIn(self.libro, respuesta.context['object_list'])

    def test_busqueda_sin_resultados_muestra_mensaje(self):
        respuesta = self.client.get(reverse('biblioteca:libro_list'), {'q': 'zzz'})
        self.assertEqual(list(respuesta.context['object_list']), [])
        self.assertContains(respuesta, 'No se encontraron libros')

    def test_detalle_muestra_ejemplares_asociados(self):
        respuesta = self.client.get(reverse('biblioteca:libro_detail', args=[self.libro.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(list(respuesta.context['ejemplares']), [self.ejemplar])

    def test_detalle_de_libro_inexistente_da_404(self):
        respuesta = self.client.get(reverse('biblioteca:libro_detail', args=[999999]))
        self.assertEqual(respuesta.status_code, 404)


class EjemplarTests(CatalogoBaseTestCase):
    def datos_ejemplar(self, **cambios):
        datos = {
            'id_inventario': '5001',
            'codigo_inventario': 'cal-002',
            'libro': self.libro.pk,
            'observaciones': '',
        }
        datos.update(cambios)
        return datos

    def test_alta_con_ambos_identificadores(self):
        respuesta = self.client.post(reverse('biblioteca:ejemplar_create'), self.datos_ejemplar())
        self.assertEqual(respuesta.status_code, 302)
        ejemplar = Ejemplar.objects.get(id_inventario=5001)
        self.assertEqual(ejemplar.codigo_inventario, 'CAL-002')
        self.assertEqual(ejemplar.libro, self.libro)

    def test_alta_redirige_al_libro(self):
        respuesta = self.client.post(
            reverse('biblioteca:ejemplar_create'), self.datos_ejemplar(id_inventario='', codigo_inventario='CAL-004')
        )
        self.assertRedirects(respuesta, reverse('biblioteca:libro_detail', args=[self.libro.pk]), fetch_redirect_response=False)

    def test_alta_sin_id_inventario(self):
        respuesta = self.client.post(
            reverse('biblioteca:ejemplar_create'), self.datos_ejemplar(id_inventario='', codigo_inventario='CAL-003')
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertIsNone(Ejemplar.objects.get(codigo_inventario='CAL-003').id_inventario)

    def test_id_inventario_repetido_muestra_error(self):
        Ejemplar.objects.create(codigo_inventario='CAL-010', libro=self.libro, id_inventario=5002)
        respuesta = self.client.post(
            reverse('biblioteca:ejemplar_create'), self.datos_ejemplar(id_inventario='5002', codigo_inventario='CAL-011')
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('id_inventario', respuesta.context['form'].errors)
        self.assertFalse(Ejemplar.objects.filter(codigo_inventario='CAL-011').exists())

    def test_codigo_repetido_ignorando_mayusculas_muestra_error_en_el_campo(self):
        respuesta = self.client.post(
            reverse('biblioteca:ejemplar_create'), self.datos_ejemplar(id_inventario='', codigo_inventario='cal-001')
        )
        self.assertEqual(respuesta.status_code, 200)
        form = respuesta.context['form']
        self.assertEqual(list(form.errors['codigo_inventario']), [MENSAJE_CODIGO_REPETIDO])
        self.assertFalse(form.non_field_errors())
        self.assertEqual(Ejemplar.objects.filter(codigo_inventario='CAL-001').count(), 1)

    def test_codigo_vacio_muestra_un_solo_mensaje(self):
        respuesta = self.client.post(
            reverse('biblioteca:ejemplar_create'), self.datos_ejemplar(id_inventario='', codigo_inventario='   ')
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(respuesta.context['form'].errors['codigo_inventario']), 1)
        self.assertEqual(Ejemplar.objects.count(), 1)

    def test_codigo_de_otro_ejemplar_al_editar_muestra_error(self):
        Ejemplar.objects.create(codigo_inventario='CAL-002', libro=self.libro)
        respuesta = self.client.post(
            reverse('biblioteca:ejemplar_update', args=[self.ejemplar.pk]),
            self.datos_ejemplar(id_inventario='', codigo_inventario='cal-002'),
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('codigo_inventario', respuesta.context['form'].errors)
        self.ejemplar.refresh_from_db()
        self.assertEqual(self.ejemplar.codigo_inventario, 'CAL-001')

    def test_si_la_base_rechaza_el_guardado_vuelve_al_formulario(self):
        # Simula que otra persona guardó el mismo dato entre la validación y el guardado.
        with mock.patch.object(Ejemplar, 'save', side_effect=IntegrityError('clave repetida')):
            respuesta = self.client.post(
                reverse('biblioteca:ejemplar_create'),
                self.datos_ejemplar(id_inventario='', codigo_inventario='CAL-020'),
            )
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn(MENSAJE_DATO_REPETIDO, list(respuesta.context['form'].non_field_errors()))
        self.assertFalse(Ejemplar.objects.filter(codigo_inventario='CAL-020').exists())

    def test_formulario_de_alta_preselecciona_el_libro(self):
        respuesta = self.client.get(reverse('biblioteca:ejemplar_create'), {'libro': self.libro.pk})
        self.assertEqual(respuesta.context['form'].initial['libro'], self.libro.pk)

    def test_edicion_de_ejemplar(self):
        respuesta = self.client.post(
            reverse('biblioteca:ejemplar_update', args=[self.ejemplar.pk]),
            self.datos_ejemplar(id_inventario='5003', codigo_inventario='CAL-001', observaciones='Tapa dañada'),
        )
        self.assertEqual(respuesta.status_code, 302)
        self.ejemplar.refresh_from_db()
        self.assertEqual(self.ejemplar.id_inventario, 5003)
        self.assertEqual(self.ejemplar.observaciones, 'Tapa dañada')

    def test_detalle_de_ejemplar_muestra_disponibilidad(self):
        respuesta = self.client.get(reverse('biblioteca:ejemplar_detail', args=[self.ejemplar.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context['object'].disponible)

    def test_listado_de_ejemplares(self):
        respuesta = self.client.get(reverse('biblioteca:ejemplar_list'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'CAL-001')
