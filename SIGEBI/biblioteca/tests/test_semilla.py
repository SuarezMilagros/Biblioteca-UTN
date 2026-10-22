import io
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from biblioteca.models import Ejemplar, Libro, Persona, Prestamo


class SemillaDatosPruebaTests(TestCase):
    def cargar(self):
        salida = io.StringIO()
        call_command('cargar_datos_prueba', stdout=salida)
        return salida.getvalue()

    def test_prestamo_activo_de_otra_persona_no_rompe_la_carga(self):
        # Caso real: el ejemplar ya está prestado a otra persona cuando se corre la semilla.
        self.cargar()
        ejemplar = Ejemplar.objects.get(codigo_inventario='ADM-001')
        Prestamo.objects.filter(ejemplar=ejemplar).delete()
        otra_persona = Persona.objects.get(documento='20333444')
        hoy = timezone.localdate()
        Prestamo.objects.create(
            ejemplar=ejemplar,
            persona=otra_persona,
            usuario_sistema=get_user_model().objects.get(username='bibliotecario_prueba'),
            fecha_prestamo=hoy,
            fecha_vencimiento=hoy + timedelta(days=7),
        )

        salida = self.cargar()

        activos = Prestamo.objects.filter(ejemplar=ejemplar, fecha_devolucion__isnull=True)
        self.assertEqual(activos.count(), 1)
        self.assertEqual(activos.get().persona, otra_persona)
        self.assertIn('ADM-001', salida)

    def test_libro_editado_desde_el_sistema_no_se_duplica(self):
        self.cargar()
        libro = Ejemplar.objects.get(codigo_inventario='ADM-001').libro
        libro.titulo = 'Administración General'
        libro.isbn = '978-9-99-999999-9'
        libro.save()
        cantidad_de_libros = Libro.objects.count()

        self.cargar()

        self.assertEqual(Libro.objects.count(), cantidad_de_libros)
        self.assertEqual(Ejemplar.objects.get(codigo_inventario='ADM-001').libro, libro)

    def test_prestamos_no_se_repiten_al_volver_a_correr(self):
        self.cargar()
        cantidad_de_prestamos = Prestamo.objects.count()

        self.cargar()

        self.assertEqual(Prestamo.objects.count(), cantidad_de_prestamos)