"""Quitar los datos de prueba del sitio publicado antes de cargar el inventario real (S8-12)."""
import io
import os
import shutil
import tempfile
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from biblioteca.models import (
    Autor, Carrera, Categoria, Editorial, Ejemplar, Libro, MaterialDigital, Opinion, Persona, Prestamo, Reserva,
)
from cuentas.lectores import crear_cuenta_de_lector
from cuentas.roles import BIBLIOTECARIO

PDF = b'%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\ntrailer << /Root 1 0 R >>\n%%EOF\n'


class QuitarDatosDePruebaTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.carpeta = tempfile.mkdtemp(prefix='quitar-prueba-')
        cls.ajustes = override_settings(MEDIA_ROOT=cls.carpeta, MATERIAL_DIGITAL_ROOT=cls.carpeta)
        cls.ajustes.enable()

    @classmethod
    def tearDownClass(cls):
        cls.ajustes.disable()
        shutil.rmtree(cls.carpeta, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        call_command('cargar_datos_prueba', stdout=io.StringIO())
        # Datos reales: un libro del inventario en la categoría Informática (que también usan los datos de prueba),
        # una persona, un préstamo registrado por el personal y la cuenta de administración.
        self.admin = get_user_model().objects.create_superuser('admin@example.com', 'admin@example.com', 'x-12345678')
        self.bibliotecaria = get_user_model().objects.create_user(username='20999888', email='ana@example.com')
        self.bibliotecaria.groups.add(Group.objects.get(name=BIBLIOTECARIO))
        informatica = Categoria.objects.get(nombre='Informática')
        self.libro_real = Libro.objects.create(
            titulo='Sistemas operativos', categoria=informatica,
            autor=Autor.objects.create(nombre='Andrew S.', apellido='Tanenbaum'),
            editorial=Editorial.objects.create(nombre='Pearson'))
        self.ejemplar_real = Ejemplar.objects.create(libro=self.libro_real, codigo_inventario='25609', id_inventario=1)
        self.persona_real = Persona.objects.create(nombre='Rosa', apellido='Medina', documento='41222333', tipo='ALUMNO')
        hoy = timezone.localdate()
        Prestamo.objects.create(ejemplar=self.ejemplar_real, persona=self.persona_real, usuario_sistema=self.bibliotecaria,
                                fecha_prestamo=hoy, fecha_vencimiento=hoy + timedelta(days=7))

    def quitar(self, *opciones):
        salida = io.StringIO()
        call_command('quitar_datos_prueba', *opciones, stdout=salida)
        return salida.getvalue()

    def comprobar_que_lo_real_sigue(self):
        self.assertEqual(list(Libro.objects.all()), [self.libro_real])
        self.assertEqual(list(Ejemplar.objects.all()), [self.ejemplar_real])
        self.assertEqual(list(Persona.objects.all()), [self.persona_real])
        self.assertEqual(Prestamo.objects.get().ejemplar, self.ejemplar_real)
        self.assertTrue(get_user_model().objects.filter(pk__in=[self.admin.pk, self.bibliotecaria.pk]).count() == 2)
        # La categoría compartida queda; las otras de prueba, los autores y editoriales de prueba se van.
        self.assertEqual(list(Categoria.objects.values_list('nombre', flat=True)), ['Informática'])
        self.assertEqual(list(Autor.objects.values_list('apellido', flat=True)), ['Tanenbaum'])
        self.assertEqual(list(Editorial.objects.values_list('nombre', flat=True)), ['Pearson'])

    def test_sin_confirmar_no_borra_nada_y_muestra_lo_que_quitaria(self):
        antes = (Libro.objects.count(), Ejemplar.objects.count(), Persona.objects.count(), Prestamo.objects.count())
        salida = self.quitar()
        self.assertIn('MODO PRUEBA: no se borró nada', salida)
        self.assertIn('Libros: 6', salida)
        self.assertIn('Ejemplares: 10', salida)
        self.assertIn('Personas: 4', salida)
        self.assertIn('Préstamos: 4', salida)
        self.assertIn('Quedarían en la base: 1 libros, 1 ejemplares, 1 personas, 1 préstamos y 0 reservas.', salida)
        self.assertEqual(
            (Libro.objects.count(), Ejemplar.objects.count(), Persona.objects.count(), Prestamo.objects.count()), antes)
        self.assertTrue(get_user_model().objects.filter(username='bibliotecario_prueba').exists())

    def test_con_confirmar_quita_solo_los_datos_de_prueba(self):
        salida = self.quitar('--confirmar')
        self.assertIn('Datos de prueba quitados.', salida)
        self.assertIn('Quedan en la base: 1 libros, 1 ejemplares, 1 personas, 1 préstamos y 0 reservas.', salida)
        self.comprobar_que_lo_real_sigue()
        self.assertFalse(get_user_model().objects.filter(username='bibliotecario_prueba').exists())
        # Repetirlo no hace nada.
        self.assertIn('Libros: 0', self.quitar('--confirmar'))
        self.comprobar_que_lo_real_sigue()

    def test_tambien_quita_lo_que_se_hizo_con_los_datos_de_prueba(self):
        # En el sitio publicado se probó con los datos de prueba: un alumno de prueba con cuenta, una reserva,
        # una opinión, un ejemplar agregado a un libro de prueba y su portada.
        persona = Persona.objects.get(documento='30111222')
        cuenta = crear_cuenta_de_lector(persona, 'juan@alumnos.example.com')
        libro = Ejemplar.objects.get(codigo_inventario='ADM-001').libro
        agregado = Ejemplar.objects.create(libro=libro, codigo_inventario='ADM-099')
        Reserva.objects.create(persona=persona, libro=libro)
        Opinion.objects.create(persona=persona, libro=libro, estrellas=5, comentario='Muy bueno')
        libro.imagen = SimpleUploadedFile('tapa.png', b'\x89PNG\r\n\x1a\n', content_type='image/png')
        libro.save()
        portada = os.path.join(self.carpeta, libro.imagen.name)
        self.assertTrue(os.path.exists(portada))

        with self.captureOnCommitCallbacks(execute=True):
            salida = self.quitar('--confirmar')

        self.assertIn('Reservas: 1', salida)
        self.assertIn('Opiniones: 1', salida)
        self.assertIn('Ejemplares: 11', salida)
        self.assertFalse(Ejemplar.objects.filter(pk=agregado.pk).exists())
        self.assertFalse(get_user_model().objects.filter(pk=cuenta.pk).exists())
        self.assertFalse(os.path.exists(portada))
        self.comprobar_que_lo_real_sigue()

    def test_si_algo_depende_de_los_datos_de_prueba_no_quita_nada(self):
        persona = Persona.objects.get(documento='31222333')
        persona.carreras.add(Carrera.objects.order_by('pk').first())
        cuenta = crear_cuenta_de_lector(persona, 'maria@alumnos.example.com')
        MaterialDigital.objects.create(
            titulo='Apunte', tipo='APUNTE', carrera=persona.carreras.get(), usuario_carga=cuenta,
            archivo=SimpleUploadedFile('apunte.pdf', PDF, content_type='application/pdf'))
        libros = Libro.objects.count()
        with self.assertRaisesMessage(CommandError, 'No se quitó nada'):
            self.quitar('--confirmar')
        self.assertEqual(Libro.objects.count(), libros)
        self.assertTrue(Persona.objects.filter(pk=persona.pk).exists())

    def test_no_corre_si_la_carga_de_datos_de_prueba_sigue_activada(self):
        with mock.patch.dict(os.environ, {'SIGEBI_DATOS_DEMO': 'True'}):
            with self.assertRaisesMessage(CommandError, 'SIGEBI_DATOS_DEMO está activada'):
                self.quitar('--confirmar')
        self.assertEqual(Libro.objects.count(), 7)
