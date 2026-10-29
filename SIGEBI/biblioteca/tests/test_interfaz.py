from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from biblioteca.models import Autor, Categoria, Editorial, Ejemplar, Libro


class InterfazTests(TestCase):
    """Comprueba lo que la interfaz debe mostrar. Si una plantilla cambia, estas pruebas avisan."""

    @classmethod
    def setUpTestData(cls):
        cls.categoria = Categoria.objects.create(nombre='Matemática')
        cls.autor = Autor.objects.create(nombre='Hugo', apellido='Ledesma')
        cls.editorial = Editorial.objects.create(nombre='Ediciones del Valle')
        cls.libro = Libro.objects.create(
            titulo='Cálculo I',
            categoria=cls.categoria,
            autor=cls.autor,
            editorial=cls.editorial,
        )
        Ejemplar.objects.create(codigo_inventario='CAL-001', libro=cls.libro)

    def setUp(self):
        usuario = get_user_model().objects.create_user(username='interfaz', password='clave-de-prueba-123')
        usuario.groups.add(Group.objects.get(name='Bibliotecario'))
        self.client.force_login(usuario)

    def test_navegacion_con_salto_al_contenido_y_salida_por_post(self):
        respuesta = self.client.get(reverse('biblioteca:inicio'))
        self.assertContains(respuesta, 'href="#contenido"')
        self.assertContains(respuesta, 'id="contenido"')
        self.assertContains(respuesta, 'aria-label="Principal"')
        self.assertContains(respuesta, 'action="' + reverse('logout') + '"')

    def test_seccion_activa_se_marca_en_la_navegacion(self):
        respuesta = self.client.get(reverse('biblioteca:libro_list'))
        self.assertContains(respuesta, 'href="' + reverse('biblioteca:libro_list') + '" aria-current="page"')
        self.assertNotContains(respuesta, 'href="' + reverse('biblioteca:autor_list') + '" aria-current="page"')

    def test_formulario_de_libro_admite_archivos(self):
        respuesta = self.client.get(reverse('biblioteca:libro_create'))
        self.assertContains(respuesta, 'enctype="multipart/form-data"')

    def test_error_se_muestra_junto_al_campo(self):
        respuesta = self.client.post(
            reverse('biblioteca:ejemplar_create'),
            {'id_inventario': '', 'codigo_inventario': 'cal-001', 'libro': self.libro.pk, 'observaciones': ''},
        )
        self.assertContains(respuesta, 'campo-error')
        self.assertContains(respuesta, 'Ya existe un ejemplar con ese código de inventario.')

    def test_mensaje_de_exito_se_anuncia(self):
        respuesta = self.client.post(
            reverse('biblioteca:categoria_create'),
            {'nombre': 'Informática', 'descripcion': ''},
            follow=True,
        )
        self.assertContains(respuesta, 'role="status"')
        self.assertContains(respuesta, 'registrada.')

    def test_busqueda_conserva_el_texto_escrito(self):
        respuesta = self.client.get(reverse('biblioteca:libro_list'), {'q': 'cal'})
        self.assertContains(respuesta, 'value="cal"')