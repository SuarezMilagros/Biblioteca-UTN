"""Carreras de cada categoría del inventario (Release 2, S7-08).

La asignación acordada por el equipo se aplica a las categorías sin carrera:
con la migración (bases que ya tienen el inventario) y al importar el Excel (producción).
Lo asignado a mano no se pisa.
"""
from importlib import import_module

from django.apps import apps
from django.test import TestCase

from biblioteca.clasificacion import CARRERAS_POR_CATEGORIA, HIGIENE, TODAS, asignar_carreras_a_categorias
from biblioteca.importacion import FilaInventario, importar
from biblioteca.models import Carrera, Categoria

migracion = import_module('biblioteca.migrations.0012_carreras_de_las_categorias')


def nombres(categoria):
    return set(categoria.carreras.values_list('nombre', flat=True))


class AsignacionTests(TestCase):
    def test_todas_las_carreras_nombradas_existen(self):
        existentes = set(Carrera.objects.values_list('nombre', flat=True))
        for categoria, carreras in CARRERAS_POR_CATEGORIA.items():
            if carreras != TODAS:
                with self.subTest(categoria=categoria):
                    self.assertTrue(set(carreras) <= existentes, set(carreras) - existentes)

    def test_la_copia_de_la_migracion_coincide_con_la_aplicacion(self):
        self.assertEqual(migracion.CARRERAS_POR_CATEGORIA, CARRERAS_POR_CATEGORIA)

    def test_asigna_las_categorias_del_inventario(self):
        proyecto = Categoria.objects.create(nombre='Proyecto Final')
        diccionario = Categoria.objects.create(nombre='Diccionario')
        informatica = Categoria.objects.create(nombre='Informática')
        clasificadas = asignar_carreras_a_categorias()
        self.assertEqual({c.nombre for c in clasificadas}, {'Proyecto Final', 'Diccionario', 'Informática'})
        self.assertEqual(nombres(proyecto), {HIGIENE})
        self.assertEqual(diccionario.carreras.count(), 10)
        self.assertEqual(informatica.carreras.count(), 3)

    def test_compara_sin_tildes_ni_mayusculas(self):
        categoria = Categoria.objects.create(nombre='  ELECTRONICA ')
        asignar_carreras_a_categorias()
        self.assertEqual(categoria.carreras.count(), 2)

    def test_no_pisa_lo_asignado_a_mano(self):
        categoria = Categoria.objects.create(nombre='Física')
        programacion = Carrera.objects.get(nombre='Tecnicatura Universitaria en Programación')
        categoria.carreras.add(programacion)
        self.assertEqual(asignar_carreras_a_categorias(), [])
        self.assertEqual(list(categoria.carreras.all()), [programacion])

    def test_una_categoria_desconocida_queda_sin_carrera(self):
        categoria = Categoria.objects.create(nombre='Arte')
        asignar_carreras_a_categorias()
        self.assertFalse(categoria.carreras.exists())

    def test_se_puede_repetir(self):
        Categoria.objects.create(nombre='Química')
        asignar_carreras_a_categorias()
        self.assertEqual(asignar_carreras_a_categorias(), [])

    def test_la_migracion_hace_lo_mismo(self):
        mecanica = Categoria.objects.create(nombre='Mecánica')
        arte = Categoria.objects.create(nombre='Arte')
        migracion.asignar(apps, None)
        self.assertEqual(mecanica.carreras.count(), 3)
        self.assertFalse(arte.carreras.exists())


class ImportacionTests(TestCase):
    def fila(self, **cambios):
        datos = dict(
            numero=2, id_inventario=1, codigo='PF-001', codigo_provisorio=False, titulo='Proyecto Final. Avícola',
            autores=['Pérez, Ana'], editorial='UTN-FRT', categoria='Proyecto Final', isbn='', prestado=False,
            observaciones='', avisos=[], errores=[],
        )
        datos.update(cambios)
        return FilaInventario(**datos)

    def test_importar_asigna_carreras_a_las_categorias_nuevas(self):
        resultado = importar([self.fila()], guardar=True)
        self.assertEqual(resultado.categorias_clasificadas, ['Proyecto Final'])
        self.assertEqual(nombres(Categoria.objects.get(nombre='Proyecto Final')), {HIGIENE})

    def test_en_modo_prueba_no_queda_nada(self):
        resultado = importar([self.fila()], guardar=False)
        self.assertEqual(resultado.categorias_clasificadas, ['Proyecto Final'])
        self.assertFalse(Categoria.objects.exists())
