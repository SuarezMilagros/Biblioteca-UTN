"""Importación del inventario en Excel desde el navegador (S8-12).

En el sitio publicado la consola de Railway no permite subir archivos: la pantalla Ejemplares › Importar desde Excel
hace lo mismo que el comando importar_inventario, en dos pasos (revisar sin guardar y guardar).
"""
import io
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from openpyxl import Workbook

from biblioteca.models import Ejemplar, Libro, Persona
from biblioteca.views import CLAVE_DE_IMPORTACION
from cuentas.lectores import crear_cuenta_de_lector
from cuentas.roles import BIBLIOTECARIO

from .test_importacion import ENCABEZADO, fila

URL = reverse('biblioteca:importar_inventario')


def excel(filas, encabezado=ENCABEZADO, nombre='inventario.xlsx'):
    libro = Workbook()
    planilla = libro.active
    planilla.title = 'Biblioteca Anexo'
    planilla.append([None, 'INVENTARIO BIBLIOTECA ANEXO CONCEPCIÓN'])
    planilla.append([None] + encabezado)
    for valores in filas:
        planilla.append([None] + valores)
    contenido = io.BytesIO()
    libro.save(contenido)
    return SimpleUploadedFile(nombre, contenido.getvalue(),
                              content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


def inventario():
    """Tres ejemplares buenos (uno prestado y otro sin numeración) y dos filas con la misma numeración."""
    return excel([
        fila(1, numeracion=25609),
        fila(2, numeracion=25610, titulo='Física', autor='Paul A. Tipler', categoria='Física', editorial='Reverté', estado='Prestado'),
        fila(3, titulo='Química', autor='Raymond Chang', categoria='Química', numeracion=' - '),
        fila(4, titulo='Dibujo técnico', numeracion=777),
        fila(5, titulo='Dibujo técnico', numeracion=777),
    ])


class ImportarDesdeLaPantallaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bibliotecario = get_user_model().objects.create_user(
            username='30111222', email='biblio@example.com', first_name='Carla', last_name='Díaz')
        cls.bibliotecario.groups.add(Group.objects.get(name=BIBLIOTECARIO))

    def setUp(self):
        self.client.force_login(self.bibliotecario)

    def revisar(self, archivo=None):
        return self.client.post(URL, {'archivo': archivo or inventario()})

    def guardar(self, huella=None):
        if huella is None:
            huella = self.client.session[CLAVE_DE_IMPORTACION]['huella']
        return self.client.post(URL, {'guardar': '1', 'huella': huella})

    def test_ejemplares_muestra_el_boton_y_la_pantalla_pide_el_archivo(self):
        listado = self.client.get(reverse('biblioteca:ejemplar_list')).content.decode()
        self.assertIn(f'href="{URL}"', listado)
        respuesta = self.client.get(URL)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'enctype="multipart/form-data"')
        self.assertContains(respuesta, 'name="archivo"')
        self.assertContains(respuesta, 'Revisar el archivo')

    def test_revisar_muestra_lo_que_pasaria_sin_guardar_nada(self):
        respuesta = self.revisar()
        self.assertEqual(respuesta.status_code, 200)
        contenido = respuesta.content.decode()
        self.assertIn('todavía no se guardó nada', contenido)
        self.assertEqual(respuesta.context['resultado'].ejemplares_nuevos, 3)
        self.assertEqual(respuesta.context['resultado'].provisorios, 1)
        # Las dos filas con la misma numeración se rechazan y se informan con su número de fila.
        self.assertIn('Filas rechazadas (2)', contenido)
        self.assertIn('La numeración 777 está repetida', contenido)
        self.assertIn('Figuraban como prestados (1)', contenido)
        self.assertIn('Guardar 3 ejemplares', contenido)
        # El botón Guardar manda la huella del archivo revisado, que es el que quedó en la sesión.
        huella = self.client.session[CLAVE_DE_IMPORTACION]['huella']
        self.assertIn(f'<input type="hidden" name="huella" value="{huella}">', contenido)
        self.assertEqual(Ejemplar.objects.count(), 0)
        self.assertEqual(Libro.objects.count(), 0)

    def test_guardar_carga_el_archivo_revisado_y_lo_registra(self):
        self.revisar()
        with self.assertLogs('biblioteca', level='INFO') as registro:
            respuesta = self.guardar()
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Inventario guardado')
        self.assertEqual(
            sorted(Ejemplar.objects.values_list('codigo_inventario', flat=True)), ['25609', '25610', 'SN-0003'])
        self.assertIn('Inventario importado por 30111222 desde "inventario.xlsx": 3 ejemplares nuevos',
                      registro.output[0])
        # El prestado se puede abrir para registrar el préstamo.
        self.assertContains(respuesta, f'href="{reverse("biblioteca:ejemplar_list")}?q=25610"')
        # El archivo no queda en la sesión: no se puede guardar dos veces.
        self.assertNotIn(CLAVE_DE_IMPORTACION, self.client.session)

    def test_no_se_guarda_sin_revisar_ni_con_otra_huella(self):
        sin_revisar = self.client.post(URL, {'guardar': '1', 'huella': 'a' * 64})
        self.assertRedirects(sin_revisar, URL)
        self.revisar()
        otra = self.client.post(URL, {'guardar': '1', 'huella': 'b' * 64}, follow=True)
        self.assertRedirects(otra, URL)
        self.assertContains(otra, 'No hay un archivo revisado para guardar')
        self.assertEqual(Ejemplar.objects.count(), 0)

    def test_repetir_la_importacion_no_duplica(self):
        self.revisar()
        self.guardar()
        respuesta = self.revisar(inventario())
        resultado = respuesta.context['resultado']
        self.assertEqual(resultado.ejemplares_nuevos, 0)
        self.assertEqual(len(resultado.omitidas), 3)
        self.assertContains(respuesta, 'No hay ejemplares nuevos para guardar.')
        self.assertNotContains(respuesta, 'name="guardar"')
        self.assertEqual(Ejemplar.objects.count(), 3)

    def test_archivos_que_no_sirven_se_explican_en_el_formulario(self):
        casos = [
            (SimpleUploadedFile('inventario.xls', b'viejo'), 'Solo se aceptan archivos de Excel .xlsx'),
            (SimpleUploadedFile('inventario.xlsx', b'no es un excel'),
             '&quot;inventario.xlsx&quot; no es un archivo de Excel (.xlsx) válido.'),
            (excel([fila(1)], encabezado=['ID', 'NOMBRE', 'AUTOR']), 'Faltan columnas en el encabezado'),
        ]
        for archivo, mensaje in casos:
            with self.subTest(archivo=archivo.name):
                respuesta = self.revisar(archivo)
                self.assertEqual(respuesta.status_code, 200)
                self.assertContains(respuesta, mensaje)
                self.assertIsNone(respuesta.context['resultado'])
                self.assertNotIn(CLAVE_DE_IMPORTACION, self.client.session)

    def test_un_archivo_demasiado_grande_se_rechaza(self):
        with mock.patch('biblioteca.forms.IMPORTACION_MAXIMO_MB', 0):
            respuesta = self.revisar()
        self.assertContains(respuesta, 'El archivo pesa más de 0 MB.')
        self.assertIsNone(respuesta.context['resultado'])


class QuienPuedeImportarTests(TestCase):
    def test_sin_sesion_va_al_ingreso(self):
        respuesta = self.client.get(URL)
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(respuesta['Location'].startswith(reverse('login')))

    def test_un_lector_no_puede_importar(self):
        persona = Persona.objects.create(nombre='Luis', apellido='Pérez', documento='40111222', tipo='ALUMNO')
        self.client.force_login(crear_cuenta_de_lector(persona, 'luis@alumnos.example.com'))
        self.assertEqual(self.client.get(URL).status_code, 403)
        self.assertEqual(self.client.post(URL, {'archivo': inventario()}).status_code, 403)
        self.assertEqual(Ejemplar.objects.count(), 0)

    def test_sin_permiso_para_crear_libros_no_ve_el_boton_ni_la_pantalla(self):
        usuario = get_user_model().objects.create_user(username='solo-mira', email='mira@example.com')
        usuario.user_permissions.add(*Permission.objects.filter(codename__in=['view_ejemplar', 'add_ejemplar']))
        self.client.force_login(usuario)
        self.assertNotIn(f'href="{URL}"', self.client.get(reverse('biblioteca:ejemplar_list')).content.decode())
        self.assertEqual(self.client.get(URL).status_code, 403)
