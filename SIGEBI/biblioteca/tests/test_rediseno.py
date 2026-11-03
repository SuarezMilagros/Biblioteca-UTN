"""Rediseño de la interfaz: datos que muestran el panel, los informes y la cabecera.

Las pantallas solo leen datos; estas pruebas verifican que los números sean los reales,
que cada rol vea solo lo que le corresponde y que la estructura accesible se conserve.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from biblioteca.models import Autor, Categoria, Editorial, Ejemplar, Libro, Persona, Prestamo
from cuentas.roles import ADMINISTRATIVO, BIBLIOTECARIO

CLAVE = 'clave-de-prueba-123'


class RedisenoTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.bibliotecario = Usuario.objects.create_user(
            username='31222333', email='bibliotecario@example.com', password=CLAVE,
            first_name='Bruno', last_name='Biblio',
        )
        cls.bibliotecario.groups.add(Group.objects.get(name=BIBLIOTECARIO))
        cls.administrativo = Usuario.objects.create_user(
            username='32333444', email='administrativo@example.com', password=CLAVE, first_name='Ana'
        )
        cls.administrativo.groups.add(Group.objects.get(name=ADMINISTRATIVO))
        cls.sin_rol = Usuario.objects.create_user(username='30111222', email='sin.rol@example.com', password=CLAVE)

        cls.ana = Persona.objects.create(nombre='Ana', apellido='Pérez', documento='40111222', tipo=Persona.Tipo.ALUMNO)
        cls.bruno = Persona.objects.create(
            nombre='Bruno', apellido='Gómez', documento='30222333', tipo=Persona.Tipo.PROFESOR
        )
        Persona.objects.create(nombre='Carla', apellido='Ruiz', documento='35444555', tipo=Persona.Tipo.ALUMNO, activo=False)
        datos = {
            'categoria': Categoria.objects.create(nombre='Matemática'),
            'autor': Autor.objects.create(nombre='Hugo', apellido='Ledesma'),
            'editorial': Editorial.objects.create(nombre='Ediciones del Valle'),
        }
        cls.calculo = Libro.objects.create(titulo='Cálculo I', **datos)
        cls.algebra = Libro.objects.create(titulo='Álgebra', **datos)
        cls.cal1 = Ejemplar.objects.create(codigo_inventario='CAL-001', libro=cls.calculo)
        cls.cal2 = Ejemplar.objects.create(codigo_inventario='CAL-002', libro=cls.calculo)
        cls.cal3 = Ejemplar.objects.create(codigo_inventario='CAL-003', libro=cls.calculo)
        Ejemplar.objects.create(
            codigo_inventario='CAL-099', libro=cls.calculo, activo=False,
            motivo_baja=Ejemplar.MotivoBaja.PERDIDO, fecha_baja=timezone.localdate(),
        )
        hoy = timezone.localdate()
        # CAL-001 prestado y vencido; CAL-002 prestado al día; CAL-003 devuelto (disponible).
        cls.vencido = Prestamo.objects.create(
            persona=cls.ana, ejemplar=cls.cal1, usuario_sistema=cls.bibliotecario,
            fecha_prestamo=hoy - timedelta(days=20), fecha_vencimiento=hoy - timedelta(days=6),
        )
        cls.al_dia = Prestamo.objects.create(
            persona=cls.bruno, ejemplar=cls.cal2, usuario_sistema=cls.bibliotecario,
            fecha_prestamo=hoy - timedelta(days=2), fecha_vencimiento=hoy + timedelta(days=12),
        )
        Prestamo.objects.create(
            persona=cls.ana, ejemplar=cls.cal3, usuario_sistema=cls.bibliotecario,
            fecha_prestamo=hoy - timedelta(days=30), fecha_vencimiento=hoy - timedelta(days=16),
            fecha_devolucion=hoy - timedelta(days=18),
        )

    def setUp(self):
        self.client.force_login(self.bibliotecario)


class PanelPrincipalTests(RedisenoTestCase):
    def test_indicadores_reales(self):
        contexto = self.client.get(reverse('biblioteca:inicio')).context
        self.assertEqual(contexto['prestamos_sin_devolver'], 2)
        self.assertEqual(contexto['prestamos_vencidos'], 1)
        self.assertEqual(contexto['ejemplares_activos'], 3)
        self.assertEqual(contexto['ejemplares_disponibles'], 1)  # CAL-003; el dado de baja no cuenta
        self.assertEqual(contexto['personas_activas'], 2)
        self.assertEqual(contexto['libros_total'], 2)

    def test_proximos_vencimientos_ordenados_y_con_devolucion(self):
        respuesta = self.client.get(reverse('biblioteca:inicio'))
        self.assertEqual(list(respuesta.context['proximos_vencimientos']), [self.vencido, self.al_dia])
        self.assertContains(respuesta, 'href="' + reverse('biblioteca:prestamo_devolver', args=[self.vencido.pk]) + '"')

    def test_la_busqueda_rapida_va_a_ejemplares(self):
        respuesta = self.client.get(reverse('biblioteca:inicio'))
        self.assertContains(respuesta, 'action="' + reverse('biblioteca:ejemplar_list') + '"')

    def test_sin_permisos_no_muestra_indicadores(self):
        self.client.force_login(self.sin_rol)
        respuesta = self.client.get(reverse('biblioteca:inicio'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn('prestamos_sin_devolver', respuesta.context)
        self.assertNotContains(respuesta, 'Próximos vencimientos')

    def test_el_superusuario_tiene_acceso_al_panel_de_administracion(self):
        superusuario = get_user_model().objects.create_superuser(
            username='10000001', email='super@example.com', password=CLAVE
        )
        self.client.force_login(superusuario)
        self.assertContains(self.client.get(reverse('biblioteca:inicio')), 'href="' + reverse('admin:index') + '"')


class CabeceraTests(RedisenoTestCase):
    def test_aviso_de_vencidos_y_rol(self):
        respuesta = self.client.get(reverse('biblioteca:libro_list'))
        self.assertEqual(respuesta.context['prestamos_vencidos_total'], 1)
        self.assertEqual(respuesta.context['rol_usuario'], BIBLIOTECARIO)
        self.assertContains(respuesta, 'href="' + reverse('biblioteca:prestamo_list') + '?estado=vencidos"')

    def test_sin_vencidos_no_hay_aviso(self):
        self.vencido.fecha_devolucion = timezone.localdate()
        self.vencido.save()
        respuesta = self.client.get(reverse('biblioteca:libro_list'))
        self.assertNotContains(respuesta, 'aviso-vencidos')

    def test_sin_permiso_de_prestamos_no_se_cuentan_vencidos(self):
        self.client.force_login(self.sin_rol)
        respuesta = self.client.get(reverse('biblioteca:inicio'))
        self.assertEqual(respuesta.context['prestamos_vencidos_total'], 0)
        self.assertEqual(respuesta.context['rol_usuario'], 'Sin rol')

    def test_estructura_accesible(self):
        respuesta = self.client.get(reverse('biblioteca:inicio'))
        for marca in ('href="#contenido"', 'id="contenido"', 'aria-label="Principal"',
                      'aria-controls="menu-lateral"', 'aria-expanded="false"', 'role="status"'):
            with self.subTest(marca=marca):
                self.assertContains(respuesta, marca)

    def test_la_pantalla_de_ingreso_no_muestra_el_menu(self):
        self.client.logout()
        respuesta = self.client.get(reverse('login'))
        self.assertNotContains(respuesta, 'aria-label="Principal"')
        self.assertNotContains(respuesta, 'modal-confirmar')


class InformesTests(RedisenoTestCase):
    def test_estadisticas_reales(self):
        contexto = self.client.get(reverse('biblioteca:informes')).context
        self.assertEqual(contexto['prestamos'], {'al_dia': 1, 'vencidos': 1, 'devueltos': 1, 'total': 3})
        self.assertEqual(contexto['ejemplares'], {'disponibles': 1, 'prestados': 2, 'baja': 1, 'total': 4})
        self.assertEqual(
            contexto['personas'], {'activas': 2, 'baja': 1, 'alumnos': 1, 'profesores': 1, 'total': 3}
        )

    def test_enlaces_a_las_exportaciones_existentes(self):
        respuesta = self.client.get(reverse('biblioteca:informes'))
        for enlace in ('?estado=vencidos&amp;formato=csv', '?estado=vigentes&amp;formato=csv'):
            self.assertContains(respuesta, reverse('biblioteca:prestamo_list') + enlace)
        self.assertContains(respuesta, reverse('biblioteca:ejemplar_list') + '?formato=csv')
        self.assertContains(respuesta, reverse('biblioteca:persona_list') + '?formato=csv')

    def test_permisos(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse('biblioteca:informes')).status_code, 302)
        self.client.force_login(self.sin_rol)
        self.assertEqual(self.client.get(reverse('biblioteca:informes')).status_code, 403)
        self.client.force_login(self.administrativo)
        self.assertEqual(self.client.get(reverse('biblioteca:informes')).status_code, 200)


class ListadoDeLibrosTests(RedisenoTestCase):
    def test_disponibilidad_por_libro(self):
        libros = {libro.titulo: libro for libro in self.client.get(reverse('biblioteca:libro_list')).context['object_list']}
        self.assertEqual((libros['Cálculo I'].ejemplares_activos, libros['Cálculo I'].ejemplares_disponibles), (3, 1))
        self.assertEqual((libros['Álgebra'].ejemplares_activos, libros['Álgebra'].ejemplares_disponibles), (0, 0))

    def test_muestra_el_estado_de_cada_libro(self):
        respuesta = self.client.get(reverse('biblioteca:libro_list'))
        self.assertContains(respuesta, '1 disponible')
        self.assertContains(respuesta, 'Sin ejemplares')


class FichaDePersonaTests(RedisenoTestCase):
    def test_resumen_de_prestamos(self):
        contexto = self.client.get(reverse('biblioteca:persona_detail', args=[self.ana.pk])).context
        self.assertEqual(len(contexto['prestamos']), 2)
        self.assertEqual(contexto['prestamos_sin_devolver'], 1)
        self.assertEqual(contexto['prestamos_vencidos'], 1)

    def test_la_baja_pide_confirmacion(self):
        respuesta = self.client.get(reverse('biblioteca:persona_detail', args=[self.bruno.pk]))
        self.assertContains(respuesta, 'data-confirmar=')
        self.assertContains(respuesta, 'action="' + reverse('biblioteca:persona_baja', args=[self.bruno.pk]) + '"')
