from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from biblioteca.models import Autor, Categoria, Editorial, Libro


class BusquedaSinAcentosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        categoria = Categoria.objects.create(nombre='Matemática')
        autor = Autor.objects.create(nombre='Hugo', apellido='Ledesma')
        editorial = Editorial.objects.create(nombre='Ediciones del Valle')
        Libro.objects.create(titulo='Cálculo I', categoria=categoria, autor=autor, editorial=editorial)
        Libro.objects.create(titulo='Álgebra Lineal', categoria=categoria, autor=autor, editorial=editorial)

    def setUp(self):
        usuario = get_user_model().objects.create_user(username='buscador', password='clave-de-prueba-123')
        self.client.force_login(usuario)

    def buscar(self, texto):
        return self.client.get(reverse('biblioteca:libro_list'), {'q': texto})

    def test_busqueda_sin_tilde_encuentra_titulo_con_tilde(self):
        respuesta = self.buscar('calculo')
        self.assertContains(respuesta, 'Cálculo I')

    def test_busqueda_con_tilde_encuentra_titulo_con_tilde(self):
        respuesta = self.buscar('cálculo')
        self.assertContains(respuesta, 'Cálculo I')

    def test_busqueda_no_muestra_libros_que_no_coinciden(self):
        respuesta = self.buscar('calculo')
        self.assertNotContains(respuesta, 'Álgebra Lineal')