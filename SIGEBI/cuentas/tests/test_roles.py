"""Permisos por rol sobre el catálogo y los módulos operativos (Release 1).

Las pruebas usan acceso directo a las URLs, no solo los enlaces del menú.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from biblioteca.models import Autor, Categoria, Editorial, Ejemplar, Libro

CLAVE = 'clave-de-prueba-123'
ADMINISTRATIVO = 'Administrativo'
BIBLIOTECARIO = 'Bibliotecario'
MODELOS_OPERATIVOS = ['categoria', 'autor', 'editorial', 'libro', 'ejemplar', 'persona', 'prestamo']


def crear_usuario(documento, correo, grupo=None):
    usuario = get_user_model().objects.create_user(username=documento, email=correo, password=CLAVE)
    if grupo:
        usuario.groups.add(Group.objects.get_or_create(name=grupo)[0])
    return usuario


class PermisosDelCatalogoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.categoria = Categoria.objects.create(nombre='Matemática')
        cls.autor = Autor.objects.create(nombre='Hugo', apellido='Ledesma')
        cls.editorial = Editorial.objects.create(nombre='Ediciones del Valle')
        cls.libro = Libro.objects.create(
            titulo='Cálculo I', isbn='', categoria=cls.categoria, autor=cls.autor, editorial=cls.editorial
        )
        cls.ejemplar = Ejemplar.objects.create(codigo_inventario='CAL-001', libro=cls.libro)
        cls.sin_grupo = crear_usuario('30111222', 'sin.grupo@example.com')
        cls.bibliotecario = crear_usuario('31222333', 'bibliotecario@example.com', BIBLIOTECARIO)
        cls.administrativo = crear_usuario('32333444', 'administrativo@example.com', ADMINISTRATIVO)

    def urls_de_lectura(self):
        return [
            reverse('biblioteca:categoria_list'),
            reverse('biblioteca:autor_list'),
            reverse('biblioteca:editorial_list'),
            reverse('biblioteca:libro_list'),
            reverse('biblioteca:libro_detail', args=[self.libro.pk]),
            reverse('biblioteca:ejemplar_list'),
            reverse('biblioteca:ejemplar_detail', args=[self.ejemplar.pk]),
        ]

    def urls_de_edicion(self):
        return [
            reverse('biblioteca:categoria_create'),
            reverse('biblioteca:categoria_update', args=[self.categoria.pk]),
            reverse('biblioteca:autor_create'),
            reverse('biblioteca:autor_update', args=[self.autor.pk]),
            reverse('biblioteca:editorial_create'),
            reverse('biblioteca:editorial_update', args=[self.editorial.pk]),
            reverse('biblioteca:libro_create'),
            reverse('biblioteca:libro_update', args=[self.libro.pk]),
            reverse('biblioteca:ejemplar_create'),
            reverse('biblioteca:ejemplar_update', args=[self.ejemplar.pk]),
        ]

    def test_usuario_sin_grupo_no_ve_ninguna_pantalla_del_catalogo(self):
        self.client.force_login(self.sin_grupo)
        for url in self.urls_de_lectura() + self.urls_de_edicion():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_usuario_sin_grupo_no_puede_guardar_cambios(self):
        self.client.force_login(self.sin_grupo)
        respuesta = self.client.post(
            reverse('biblioteca:categoria_create'), {'nombre': 'Intrusa', 'descripcion': ''}
        )
        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(Categoria.objects.filter(nombre='Intrusa').exists())
        respuesta = self.client.post(
            reverse('biblioteca:categoria_update', args=[self.categoria.pk]),
            {'nombre': 'Cambiada', 'descripcion': ''},
        )
        self.assertEqual(respuesta.status_code, 403)
        self.categoria.refresh_from_db()
        self.assertEqual(self.categoria.nombre, 'Matemática')

    def test_bibliotecario_y_administrativo_operan_el_catalogo(self):
        for usuario in (self.bibliotecario, self.administrativo):
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)
                for url in self.urls_de_lectura() + self.urls_de_edicion():
                    self.assertEqual(self.client.get(url).status_code, 200, url)
                respuesta = self.client.post(
                    reverse('biblioteca:categoria_update', args=[self.categoria.pk]),
                    {'nombre': 'Matemática', 'descripcion': ''},
                )
                self.assertEqual(respuesta.status_code, 302)

    def test_grupos_tienen_los_permisos_operativos_del_rol(self):
        for nombre in (BIBLIOTECARIO, ADMINISTRATIVO):
            with self.subTest(grupo=nombre):
                permisos = set(
                    Group.objects.get(name=nombre).permissions.values_list('content_type__app_label', 'codename')
                )
                esperados = {
                    ('biblioteca', f'{accion}_{modelo}')
                    for modelo in MODELOS_OPERATIVOS
                    for accion in ('view', 'add', 'change')
                }
                faltan = esperados - permisos
                self.assertFalse(faltan, f'Faltan permisos: {sorted(faltan)}')

    def test_bibliotecario_no_tiene_permisos_sobre_usuarios(self):
        permisos = Group.objects.get(name=BIBLIOTECARIO).permissions.values_list(
            'content_type__app_label', flat=True
        )
        self.assertNotIn('auth', set(permisos))
