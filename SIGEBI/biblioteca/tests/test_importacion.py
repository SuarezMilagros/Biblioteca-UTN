"""Importación del inventario en Excel (Sprint 6, S6-10).

Cada prueba arma un .xlsx chico con el mismo formato que el inventario real de la biblioteca:
una fila de título, el encabezado y una fila por ejemplar.
"""
import io
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, TestCase
from openpyxl import Workbook

from biblioteca.importacion import (
    SIN_AUTOR, SIN_EDITORIAL, extraer_isbn, fecha_de_inventario, leer_planilla, nombre_y_apellido,
    separar_autores,
)
from biblioteca.models import Autor, Categoria, Editorial, Ejemplar, Libro, Prestamo

ENCABEZADO = [
    'ID', 'NOMBRE', 'AUTOR', 'CATEGORÍA', 'EDITORIAL', 'NUMERACIÓN', 'ISBN', 'OBSERVACIONES',
    'FECHA DE INVENTARIO', 'Estado',
]
FECHA = datetime(2024, 10, 14)


def fila(id_, titulo='Cálculo I', autor='Hugo Ledesma', categoria='Matemáticas', editorial='Pearson',
         numeracion=None, isbn=' - ', observaciones='Nuevo', fecha=FECHA, estado='Disponible'):
    numeracion = 1000 + id_ if numeracion is None else numeracion
    return [id_, titulo, autor, categoria, editorial, numeracion, isbn, observaciones, fecha, estado]


class ConPlanilla:
    def setUp(self):
        super().setUp()
        self.carpeta = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.carpeta)

    def planilla(self, filas, encabezado=ENCABEZADO, nombre='inventario.xlsx', hoja='Biblioteca Anexo'):
        libro = Workbook()
        planilla = libro.active
        planilla.title = hoja
        # Igual que el Excel real: columna A vacía, título arriba y encabezado debajo.
        planilla.append([None, 'INVENTARIO BIBLIOTECA ANEXO CONCEPCIÓN'])
        planilla.append([None] + encabezado)
        for valores in filas:
            planilla.append([None] + valores)
        ruta = self.carpeta / nombre
        libro.save(ruta)
        return ruta

    def importar(self, ruta, *opciones):
        salida = io.StringIO()
        call_command('importar_inventario', str(ruta), *opciones, stdout=salida)
        return salida.getvalue()


class ImportacionTests(ConPlanilla, TestCase):
    def test_importa_el_catalogo_y_los_ejemplares(self):
        ruta = self.planilla([
            fila(1, isbn='ISBN 978-607-442-388-4', numeracion=25609),
            fila(2, isbn='ISBN 978-607-442-388-4', numeracion=25610),
            fila(3, titulo='Física', autor='Paul A. Tipler', categoria='Física', editorial='Reverté S.A.'),
        ])

        salida = self.importar(ruta, '--guardar')

        self.assertIn('Datos guardados', salida)
        self.assertEqual(Ejemplar.objects.count(), 3)
        self.assertEqual(Libro.objects.count(), 2)
        ejemplar = Ejemplar.objects.get(codigo_inventario='25609')
        self.assertEqual(ejemplar.id_inventario, 1)
        self.assertTrue(ejemplar.activo)
        self.assertTrue(ejemplar.disponible)
        libro = ejemplar.libro
        self.assertEqual(libro.titulo, 'Cálculo I')
        self.assertEqual(libro.isbn, '978-607-442-388-4')
        self.assertEqual((libro.autor.nombre, libro.autor.apellido), ('Hugo', 'Ledesma'))
        self.assertEqual(libro.categoria.nombre, 'Matemáticas')
        self.assertEqual(libro.editorial.nombre, 'Pearson')
        self.assertEqual(libro.ejemplares.count(), 2)
        self.assertEqual(ejemplar.observaciones, 'Nuevo\nInventariado el 14/10/2024.')

    def test_sin_guardar_no_queda_nada_en_la_base(self):
        ruta = self.planilla([fila(1), fila(2, titulo='Física')])

        salida = self.importar(ruta)

        self.assertIn('MODO PRUEBA', salida)
        self.assertIn('Ejemplares nuevos: 2', salida)
        for modelo in (Ejemplar, Libro, Autor, Editorial, Categoria):
            with self.subTest(modelo=modelo.__name__):
                self.assertFalse(modelo.objects.exists())

    def test_se_puede_repetir_sin_duplicar(self):
        ruta = self.planilla([fila(1), fila(2), fila(3, titulo='Física')])
        self.importar(ruta, '--guardar')

        salida = self.importar(ruta, '--guardar')

        self.assertIn('Ejemplares nuevos: 0', salida)
        self.assertIn('Ya cargados antes (se omiten): 3', salida)
        self.assertEqual(Ejemplar.objects.count(), 3)
        self.assertEqual(Libro.objects.count(), 2)
        self.assertEqual(Autor.objects.count(), 1)

    def test_usa_el_catalogo_existente_sin_distinguir_tildes_ni_mayusculas(self):
        categoria = Categoria.objects.create(nombre='Matematicas')
        editorial = Editorial.objects.create(nombre='PEARSON')
        autor = Autor.objects.create(nombre='hugo', apellido='ledesma')
        libro = Libro.objects.create(titulo='calculo i', categoria=categoria, autor=autor, editorial=editorial)

        self.importar(self.planilla([fila(1)]), '--guardar')

        self.assertEqual(Ejemplar.objects.get().libro, libro)
        self.assertEqual(Categoria.objects.count(), 1)
        self.assertEqual(Editorial.objects.count(), 1)
        self.assertEqual(Autor.objects.count(), 1)

    def test_titulos_que_solo_difieren_en_mayusculas_son_el_mismo_libro(self):
        ruta = self.planilla([
            fila(1, titulo='Instrumentación Electrónica'),
            fila(2, titulo='Instrumentación electrónica'),
        ])
        self.importar(ruta, '--guardar')
        self.assertEqual(Libro.objects.count(), 1)
        self.assertEqual(Libro.objects.get().ejemplares.count(), 2)

    def test_sin_numeracion_recibe_codigo_provisorio(self):
        ruta = self.planilla([fila(45, numeracion=' - '), fila(7, numeracion='')])

        salida = self.importar(ruta, '--guardar')

        self.assertTrue(Ejemplar.objects.filter(codigo_inventario='SN-0045', id_inventario=45).exists())
        self.assertTrue(Ejemplar.objects.filter(codigo_inventario='SN-0007').exists())
        self.assertIn('con código provisorio SN-: 2', salida)

    def test_numeracion_con_letras_se_conserva_en_mayusculas(self):
        self.importar(self.planilla([fila(1, numeracion='1874t')]), '--guardar')
        self.assertEqual(Ejemplar.objects.get().codigo_inventario, '1874T')

    def test_varios_autores_queda_el_primero_y_los_demas_en_observaciones(self):
        ruta = self.planilla([fila(1, autor='David A. Patterson\nJohn L. Hennessy')])

        self.importar(ruta, '--guardar')

        ejemplar = Ejemplar.objects.get()
        self.assertEqual((ejemplar.libro.autor.nombre, ejemplar.libro.autor.apellido), ('David A.', 'Patterson'))
        self.assertIn('Otros autores: John L. Hennessy.', ejemplar.observaciones)
        self.assertEqual(Autor.objects.count(), 1)

    def test_sin_editorial_y_sin_autor(self):
        ruta = self.planilla([fila(1, editorial=' - ', autor=None), fila(2, editorial=None, autor=' - ')])

        salida = self.importar(ruta, '--guardar', '--detalle')

        self.assertEqual(Editorial.objects.get().nombre, SIN_EDITORIAL)
        self.assertEqual(Autor.objects.get().apellido, SIN_AUTOR)
        self.assertIn(f'Sin autor: se asigna "{SIN_AUTOR}"', salida)

    def test_id_repetido_rechaza_ambas_filas_y_carga_las_demas(self):
        ruta = self.planilla([
            fila(227, titulo='Proyecto A', numeracion=' - '),
            fila(227, titulo='Proyecto B', numeracion=' - '),
            fila(228),
        ])

        salida = self.importar(ruta, '--guardar')

        self.assertEqual(list(Ejemplar.objects.values_list('id_inventario', flat=True)), [228])
        self.assertIn('Filas rechazadas: 2', salida)
        self.assertIn('El ID 227 está repetido en el Excel (filas 3, 4).', salida)
        self.assertNotIn('SN-0227', salida)

    def test_numeracion_repetida_rechaza_ambas_filas(self):
        ruta = self.planilla([fila(18, numeracion=29297), fila(19, numeracion=29297), fila(20)])

        salida = self.importar(ruta, '--guardar')

        self.assertEqual(Ejemplar.objects.count(), 1)
        self.assertIn('La numeración 29297 está repetida en el Excel (filas 3, 4).', salida)

    def test_celda_con_dos_numeraciones_se_rechaza(self):
        salida = self.importar(self.planilla([fila(55, numeracion='6056\n1907')]), '--guardar')

        self.assertFalse(Ejemplar.objects.exists())
        self.assertIn('La numeración tiene más de un valor ("6056 / 1907")', salida)

    def test_id_que_ya_usa_otro_ejemplar_se_rechaza(self):
        self.importar(self.planilla([fila(1, numeracion=500)]), '--guardar')

        salida = self.importar(self.planilla([fila(1, numeracion=501)], nombre='otro.xlsx'), '--guardar')

        self.assertEqual(Ejemplar.objects.count(), 1)
        self.assertIn('El ID 1 ya lo tiene el ejemplar 500.', salida)

    def test_fila_sin_titulo_o_sin_categoria_se_rechaza(self):
        ruta = self.planilla([fila(1, titulo=None), fila(2, categoria=' - '), fila(3)])

        salida = self.importar(ruta, '--guardar')

        self.assertEqual(Ejemplar.objects.count(), 1)
        self.assertIn('Falta el título', salida)
        self.assertIn('Falta la categoría', salida)

    def test_prestado_se_carga_disponible_y_se_informa_sin_inventar_el_prestamo(self):
        ruta = self.planilla([fila(8, numeracion=44, estado='Prestado'), fila(9)])

        salida = self.importar(ruta, '--guardar')

        ejemplar = Ejemplar.objects.get(codigo_inventario='44')
        self.assertTrue(ejemplar.disponible)
        self.assertFalse(Prestamo.objects.exists())
        self.assertIn('En el inventario de Excel figuraba como prestado.', ejemplar.observaciones)
        self.assertIn('Figuraban como prestados en el Excel (1)', salida)
        self.assertIn('Fila 3: 44', salida)

    def test_detalle_lista_avisos_y_autores_nuevos(self):
        ruta = self.planilla([fila(1, isbn='ISBN 987-9406', autor='Kaoru Ishikawa')])

        salida = self.importar(ruta, '--detalle')

        self.assertIn('ISBN no reconocido ("ISBN 987-9406")', salida)
        self.assertIn('Fila 3: apellido "Ishikawa", nombre "Kaoru"', salida)


class ArchivoTests(ConPlanilla, TestCase):
    def test_archivo_inexistente(self):
        with self.assertRaisesMessage(CommandError, 'No existe el archivo'):
            self.importar(self.carpeta / 'no-existe.xlsx')

    def test_archivo_que_no_es_excel(self):
        ruta = self.carpeta / 'inventario.xlsx'
        ruta.write_text('ID;NOMBRE\n1;Cálculo', encoding='utf-8')
        with self.assertRaisesMessage(CommandError, 'no es un archivo de Excel (.xlsx) válido'):
            self.importar(ruta)

    def test_faltan_columnas_obligatorias(self):
        ruta = self.planilla([[1, 'Cálculo I']], encabezado=['ID', 'NOMBRE', 'ISBN'])
        with self.assertRaisesMessage(CommandError, 'Faltan columnas en el encabezado: autor, categoria, editorial, numeracion.'):
            self.importar(ruta)

    def test_sin_encabezado(self):
        ruta = self.planilla([[1, 2, 3]], encabezado=['A', 'B', 'C'])
        with self.assertRaisesMessage(CommandError, 'No se encontró el encabezado'):
            self.importar(ruta)

    def test_hoja_inexistente(self):
        with self.assertRaisesMessage(CommandError, 'No existe la hoja "Otra". Hojas del archivo: Biblioteca Anexo.'):
            self.importar(self.planilla([fila(1)]), '--hoja', 'Otra')

    def test_las_filas_vacias_se_saltean(self):
        ruta = self.planilla([fila(1), [None] * 10, fila(2)])
        _, filas = leer_planilla(ruta)
        self.assertEqual([fila_leida.id_inventario for fila_leida in filas], [1, 2])


class LimpiezaDeDatosTests(SimpleTestCase):
    def test_separar_autores(self):
        casos = {
            'Koontz. Weihrich. Cannice': ['Koontz', 'Weihrich', 'Cannice'],
            'Sears Zemansky\nYoung Freedman': ['Sears Zemansky', 'Young Freedman'],
            'Terman y Pettit': ['Terman', 'Pettit'],
            'Kendall & Kendall': ['Kendall', 'Kendall'],
            'Lic. Guillermo Martinez Guzman': ['Guillermo Martinez Guzman'],
            'A. Bruce Carlson': ['A. Bruce Carlson'],
            'B.P. Lathi': ['B.P. Lathi'],
            'Arthur I. Vogel': ['Arthur I. Vogel'],
            ' - ': [],
            None: [],
        }
        for texto, esperado in casos.items():
            with self.subTest(texto=texto):
                self.assertEqual(separar_autores(texto), esperado)

    def test_nombre_y_apellido(self):
        casos = {
            'Kaoru Ishikawa': ('Kaoru', 'Ishikawa'),
            'Palavecino': ('', 'Palavecino'),
            'Armando E. De Giusti': ('Armando E.', 'De Giusti'),
            'Frank Ayres JR': ('Frank', 'Ayres Jr.'),
            'Torres, Rodrigo Manuel Iván': ('Rodrigo Manuel Iván', 'Torres'),
        }
        for texto, esperado in casos.items():
            with self.subTest(texto=texto):
                self.assertEqual(nombre_y_apellido(texto), esperado)

    def test_extraer_isbn(self):
        casos = {
            'ISBN 978-607-442-388-4': '978-607-442-388-4',
            'ISBN- 13: 978-970-10-6524-2\nISBN-10: 970-10-6524-7': '978-970-10-6524-2',
            'ISBN-10: 970-10-6524-7\nISBN-13: 978-970-10-6524-2': '978-970-10-6524-2',
            'ISBN 0-07-019092-5': '0-07-019092-5',
            'ISBN 13 978-970-10-6111-4\nISBN 970-10-6111-X': '978-970-10-6111-4',
            'ISBN 84-283-199-X': '',  # le falta un dígito en el Excel
            '0000000000': '',  # relleno, no un ISBN
            ' - ': '',
        }
        for texto, esperado in casos.items():
            with self.subTest(texto=texto):
                self.assertEqual(extraer_isbn(texto), esperado)

    def test_fecha_de_inventario(self):
        self.assertEqual(fecha_de_inventario(FECHA), (FECHA.date(), ''))
        self.assertEqual(
            fecha_de_inventario('miércoles, 16 de octubre de 2024'), (datetime(2024, 10, 16).date(), '')
        )
        self.assertEqual(fecha_de_inventario('octubre'), (None, 'octubre'))
        self.assertEqual(fecha_de_inventario(None), (None, ''))

    def test_autor_sin_nombre_se_muestra_solo_con_apellido(self):
        self.assertEqual(str(Autor(nombre='', apellido='Palavecino')), 'Palavecino')
        self.assertEqual(str(Autor(nombre='Kaoru', apellido='Ishikawa')), 'Ishikawa, Kaoru')
