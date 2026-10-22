from django import forms
from django.core.exceptions import ValidationError
from django.test import TestCase

from biblioteca.forms import EjemplarForm
from biblioteca.models import Autor, Categoria, Editorial, Ejemplar, Libro


class FormularioGenericoDeEjemplar(forms.ModelForm):
    # Formulario sin ajustes especiales para el código, como el del admin.
    class Meta:
        model = Ejemplar
        fields = ['codigo_inventario', 'libro']


class CodigoObligatorioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        categoria = Categoria.objects.create(nombre='Matemática')
        autor = Autor.objects.create(nombre='Hugo', apellido='Ledesma')
        editorial = Editorial.objects.create(nombre='Ediciones del Valle')
        cls.libro = Libro.objects.create(
            titulo='Cálculo I', categoria=categoria, autor=autor, editorial=editorial,
        )

    def test_modelo_con_codigo_vacio_da_un_solo_mensaje(self):
        ejemplar = Ejemplar(codigo_inventario='', libro=self.libro)
        with self.assertRaises(ValidationError) as contexto:
            ejemplar.full_clean()
        self.assertEqual(len(contexto.exception.message_dict['codigo_inventario']), 1)

    def test_modelo_con_solo_espacios_da_un_solo_mensaje(self):
        ejemplar = Ejemplar(codigo_inventario='   ', libro=self.libro)
        with self.assertRaises(ValidationError) as contexto:
            ejemplar.full_clean()
        self.assertEqual(len(contexto.exception.message_dict['codigo_inventario']), 1)

    def test_formulario_de_ejemplar_con_codigo_vacio_da_un_solo_mensaje(self):
        formulario = EjemplarForm(data={
            'id_inventario': '', 'codigo_inventario': '', 'libro': self.libro.pk, 'observaciones': '',
        })
        self.assertFalse(formulario.is_valid())
        self.assertEqual(len(formulario.errors['codigo_inventario']), 1)

    def test_formulario_generico_con_codigo_vacio_da_un_solo_mensaje(self):
        formulario = FormularioGenericoDeEjemplar(data={'codigo_inventario': '', 'libro': self.libro.pk})
        self.assertFalse(formulario.is_valid())
        self.assertEqual(len(formulario.errors['codigo_inventario']), 1)