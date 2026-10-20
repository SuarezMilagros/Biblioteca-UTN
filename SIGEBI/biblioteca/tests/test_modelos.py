import io

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase

from biblioteca.models import Autor, Categoria, Editorial, Ejemplar, Libro


def crear_base():
    """Crea categoría, autor y editorial para los libros de prueba."""
    return (
        Categoria.objects.create(nombre='Categoría de prueba'),
        Autor.objects.create(nombre='Ana', apellido='Prueba'),
        Editorial.objects.create(nombre='Editorial de prueba'),
    )


class IsbnOpcionalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.categoria, cls.autor, cls.editorial = crear_base()

    def crear_libro(self, titulo, isbn=None):
        datos = {
            'titulo': titulo,
            'categoria': self.categoria,
            'autor': self.autor,
            'editorial': self.editorial,
        }
        if isbn is not None:
            datos['isbn'] = isbn
        return Libro.objects.create(**datos)

    def test_libro_sin_isbn_se_guarda_con_cadena_vacia(self):
        libro = self.crear_libro('Sin ISBN')
        libro.refresh_from_db()
        self.assertEqual(libro.isbn, '')

    def test_libro_sin_isbn_pasa_la_validacion(self):
        libro = self.crear_libro('Sin ISBN', isbn='')
        libro.full_clean()

    def test_varios_libros_sin_isbn_no_chocan(self):
        self.crear_libro('Uno', isbn='')
        self.crear_libro('Dos', isbn='')
        self.assertEqual(Libro.objects.filter(isbn='').count(), 2)

    def test_isbn_repetido_esta_permitido(self):
        self.crear_libro('Edición 1', isbn='978-0-00-000099-0')
        self.crear_libro('Edición 2', isbn='978-0-00-000099-0')
        self.assertEqual(Libro.objects.filter(isbn='978-0-00-000099-0').count(), 2)


class IdInventarioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.categoria, cls.autor, cls.editorial = crear_base()
        cls.libro = Libro.objects.create(
            titulo='Libro de prueba',
            categoria=cls.categoria,
            autor=cls.autor,
            editorial=cls.editorial,
        )

    def test_id_inventario_es_opcional(self):
        ejemplar = Ejemplar.objects.create(codigo_inventario='TST-001', libro=self.libro)
        self.assertIsNone(ejemplar.id_inventario)
        ejemplar.full_clean()

    def test_varios_ejemplares_sin_id_inventario_no_chocan(self):
        Ejemplar.objects.create(codigo_inventario='TST-002', libro=self.libro)
        Ejemplar.objects.create(codigo_inventario='TST-003', libro=self.libro)
        self.assertEqual(Ejemplar.objects.filter(id_inventario__isnull=True).count(), 2)

    def test_id_inventario_distintos_son_validos(self):
        Ejemplar.objects.create(codigo_inventario='TST-004', libro=self.libro, id_inventario=1001)
        Ejemplar.objects.create(codigo_inventario='TST-005', libro=self.libro, id_inventario=1002)
        self.assertEqual(Ejemplar.objects.filter(id_inventario__in=[1001, 1002]).count(), 2)

    def test_id_inventario_repetido_se_rechaza_en_la_base(self):
        Ejemplar.objects.create(codigo_inventario='TST-006', libro=self.libro, id_inventario=2001)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Ejemplar.objects.create(codigo_inventario='TST-007', libro=self.libro, id_inventario=2001)

    def test_id_inventario_repetido_se_rechaza_en_la_validacion(self):
        Ejemplar.objects.create(codigo_inventario='TST-008', libro=self.libro, id_inventario=3001)
        otro = Ejemplar(codigo_inventario='TST-009', libro=self.libro, id_inventario=3001)
        with self.assertRaises(ValidationError) as contexto:
            otro.full_clean()
        self.assertIn('id_inventario', contexto.exception.message_dict)


class CodigoInventarioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.categoria, cls.autor, cls.editorial = crear_base()
        cls.libro = Libro.objects.create(
            titulo='Libro de prueba',
            categoria=cls.categoria,
            autor=cls.autor,
            editorial=cls.editorial,
        )

    def test_se_guarda_en_mayusculas_y_sin_espacios(self):
        ejemplar = Ejemplar.objects.create(codigo_inventario='  adm-900 ', libro=self.libro)
        ejemplar.refresh_from_db()
        self.assertEqual(ejemplar.codigo_inventario, 'ADM-900')

    def test_acepta_letras_y_numeros(self):
        ejemplar = Ejemplar.objects.create(codigo_inventario='ab12c', libro=self.libro)
        self.assertEqual(ejemplar.codigo_inventario, 'AB12C')

    def test_duplicado_ignorando_mayusculas_se_rechaza_en_la_base(self):
        Ejemplar.objects.create(codigo_inventario='ADM-901', libro=self.libro)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Ejemplar.objects.create(codigo_inventario='adm-901', libro=self.libro)

    def test_duplicado_ignorando_mayusculas_se_rechaza_en_la_validacion(self):
        Ejemplar.objects.create(codigo_inventario='ADM-902', libro=self.libro)
        otro = Ejemplar(codigo_inventario='adm-902', libro=self.libro)
        with self.assertRaises(ValidationError) as contexto:
            otro.full_clean()
        self.assertIn('Ya existe un ejemplar con ese código de inventario.', str(contexto.exception))

    def test_codigo_vacio_o_con_solo_espacios_no_es_valido(self):
        ejemplar = Ejemplar(codigo_inventario='   ', libro=self.libro)
        with self.assertRaises(ValidationError) as contexto:
            ejemplar.full_clean()
        self.assertIn('codigo_inventario', contexto.exception.message_dict)


class DatosDePruebaTests(TestCase):
    def cargar(self):
        call_command('cargar_datos_prueba', stdout=io.StringIO())

    def conteos(self):
        return {
            'categorias': Categoria.objects.count(),
            'autores': Autor.objects.count(),
            'editoriales': Editorial.objects.count(),
            'libros': Libro.objects.count(),
            'ejemplares': Ejemplar.objects.count(),
        }

    def test_cargar_datos_prueba_crea_el_conjunto_esperado(self):
        self.cargar()
        self.assertEqual(
            self.conteos(),
            {'categorias': 4, 'autores': 5, 'editoriales': 3, 'libros': 6, 'ejemplares': 10},
        )

    def test_cargar_datos_prueba_es_repetible(self):
        self.cargar()
        primera = self.conteos()
        self.cargar()
        self.assertEqual(self.conteos(), primera)

    def test_datos_de_prueba_no_inventan_id_inventario(self):
        self.cargar()
        self.assertFalse(Ejemplar.objects.exclude(id_inventario=None).exists())

    def test_disponibilidad_de_los_datos_de_prueba_sigue_calculandose_desde_prestamos(self):
        self.cargar()
        self.assertFalse(Ejemplar.objects.get(codigo_inventario='ADM-001').disponible)
        self.assertTrue(Ejemplar.objects.get(codigo_inventario='ADM-002').disponible)

    def test_cargar_datos_prueba_no_falla_con_registros_repetidos(self):
        # El ISBN, y los nombres de categorías, autores y editoriales, no son únicos.
        # La carga no debe romperse si ya existen registros con el mismo valor.
        categoria = Categoria.objects.create(nombre='Informática')
        Categoria.objects.create(nombre='Informática')
        autor = Autor.objects.create(nombre='Hugo', apellido='Ledesma')
        Autor.objects.create(nombre='Hugo', apellido='Ledesma')
        editorial = Editorial.objects.create(nombre='Ediciones del Valle')
        Editorial.objects.create(nombre='Ediciones del Valle')
        for titulo in ('Libro manual A', 'Libro manual B'):
            Libro.objects.create(
                titulo=titulo,
                isbn='978-0-00-000002-0',
                categoria=categoria,
                autor=autor,
                editorial=editorial,
            )

        self.cargar()
        self.cargar()

        ejemplar = Ejemplar.objects.get(codigo_inventario='PRG-001')
        self.assertEqual(ejemplar.libro.titulo, 'Fundamentos de Programación')
        self.assertEqual(Libro.objects.filter(titulo='Fundamentos de Programación').count(), 1)
        