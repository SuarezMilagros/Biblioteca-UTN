"""Informe de demanda (Release 2, S8-07).

- Período elegible; por defecto, los últimos 90 días.
- Por libro: préstamos, reservas, reservas sin ejemplar (pendientes o rechazadas) y ejemplares activos.
- "Conviene comprar más" cuando hubo más reservas sin ejemplar que ejemplares activos.
- Exportación CSV y acceso desde Informes.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from biblioteca import demanda
from biblioteca.models import Autor, Categoria, Editorial, Ejemplar, Libro, Persona, Prestamo, Reserva
from cuentas.roles import BIBLIOTECARIO

CLAVE = 'clave-de-prueba-123'


class DemandaTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bibliotecario = get_user_model().objects.create_user(username='31222333', password=CLAVE)
        cls.bibliotecario.groups.add(Group.objects.get(name=BIBLIOTECARIO))
        datos = {'autor': Autor.objects.create(nombre='Ana', apellido='Autora'), 'editorial': Editorial.objects.create(nombre='E'),
                 'categoria': Categoria.objects.create(nombre='Informática')}
        cls.python = Libro.objects.create(titulo='Python', **datos)
        cls.java = Libro.objects.create(titulo='Java', **datos)
        cls.redes = Libro.objects.create(titulo='Redes', **datos)
        cls.py1 = Ejemplar.objects.create(codigo_inventario='PY-1', libro=cls.python)
        cls.jv = [Ejemplar.objects.create(codigo_inventario=f'JV-{n}', libro=cls.java) for n in (1, 2, 3)]
        Ejemplar.objects.create(codigo_inventario='RED-1', libro=cls.redes, activo=False, motivo_baja='PERDIDO',
                                fecha_baja=timezone.localdate())
        cls.personas = [Persona.objects.create(nombre=f'P{n}', apellido='X', documento=f'4000000{n}', tipo='ALUMNO')
                        for n in range(6)]

    def setUp(self):
        self.client.force_login(self.bibliotecario)
        self.hoy = timezone.localdate()

    def reserva(self, persona, libro, estado='PENDIENTE', hace=0):
        datos = {}
        if estado == 'RECHAZADA':
            datos = dict(fecha_respuesta=timezone.now(), motivo_rechazo='No hay ejemplares', usuario_respuesta=self.bibliotecario)
        elif estado == 'CONFIRMADA':
            ejemplar = libro.ejemplares.filter(activo=True).exclude(reservas__estado='CONFIRMADA').first()
            datos = dict(ejemplar=ejemplar, fecha_respuesta=timezone.now(), vence_retiro=timezone.now() + timedelta(hours=48))
        reserva = Reserva.objects.create(persona=persona, libro=libro, estado=estado, **datos)
        Reserva.objects.filter(pk=reserva.pk).update(fecha_reserva=timezone.now() - timedelta(days=hace))
        return reserva

    def prestar(self, persona, ejemplar, hace=10):
        inicio = self.hoy - timedelta(days=hace)
        return Prestamo.objects.create(persona=persona, ejemplar=ejemplar, usuario_sistema=self.bibliotecario,
                                       fecha_prestamo=inicio, fecha_vencimiento=inicio + timedelta(days=14),
                                       fecha_devolucion=inicio + timedelta(days=7))

    def informe(self, consulta=''):
        return self.client.get(reverse('biblioteca:informe_demanda') + consulta)

    def por_titulo(self, respuesta):
        return {libro.titulo: libro for libro in respuesta.context['libros']}


class CalculoTests(DemandaTestCase):
    def test_criterio_un_ejemplar_y_varias_reservas_sin_confirmar_aparece_marcado(self):
        self.reserva(self.personas[0], self.python)
        self.reserva(self.personas[1], self.python)
        respuesta = self.informe()
        python = self.por_titulo(respuesta)['Python']
        self.assertEqual((python.total_reservas, python.reservas_sin_ejemplar, python.ejemplares_activos), (2, 2, 1))
        self.assertTrue(python.conviene_comprar)
        self.assertContains(respuesta, '<span class="badge badge-vencido">Conviene comprar más</span>', html=True)
        self.assertEqual(respuesta.context['cantidad_para_comprar'], 1)

    def test_una_sola_reserva_con_un_ejemplar_no_se_marca(self):
        self.reserva(self.personas[0], self.python)
        self.assertFalse(self.por_titulo(self.informe())['Python'].conviene_comprar)

    def test_sin_ejemplares_activos_cualquier_pedido_sin_atender_se_marca(self):
        self.reserva(self.personas[0], self.redes, estado='RECHAZADA')
        redes = self.por_titulo(self.informe())['Redes']
        self.assertEqual((redes.ejemplares_activos, redes.reservas_sin_ejemplar), (0, 1))
        self.assertTrue(redes.conviene_comprar)

    def test_solo_pendientes_y_rechazadas_cuentan_como_sin_ejemplar(self):
        self.reserva(self.personas[0], self.java, estado='CONFIRMADA')
        self.reserva(self.personas[1], self.java, estado='CANCELADA')
        self.reserva(self.personas[2], self.java, estado='RECHAZADA')
        self.reserva(self.personas[3], self.java)
        java = self.por_titulo(self.informe())['Java']
        self.assertEqual((java.total_reservas, java.reservas_sin_ejemplar, java.ejemplares_activos), (4, 2, 3))
        self.assertFalse(java.conviene_comprar)

    def test_los_prestamos_se_cuentan_bien_aunque_haya_varios_ejemplares(self):
        self.prestar(self.personas[0], self.jv[0])
        self.prestar(self.personas[1], self.jv[1])
        self.prestar(self.personas[2], self.jv[1], hace=30)
        self.reserva(self.personas[3], self.java)
        java = self.por_titulo(self.informe())['Java']
        self.assertEqual((java.total_prestamos, java.total_reservas, java.ejemplares_activos, java.demanda), (3, 1, 3, 4))

    def test_solo_aparecen_los_libros_con_pedidos(self):
        self.prestar(self.personas[0], self.py1)
        self.assertEqual(list(self.por_titulo(self.informe())), ['Python'])

    def test_los_marcados_van_primero(self):
        self.prestar(self.personas[0], self.jv[0])
        self.prestar(self.personas[1], self.jv[1])
        self.reserva(self.personas[2], self.python)
        self.reserva(self.personas[3], self.python)
        self.assertEqual([libro.titulo for libro in self.informe().context['libros']], ['Python', 'Java'])


class PeriodoTests(DemandaTestCase):
    def test_por_defecto_los_ultimos_90_dias(self):
        self.prestar(self.personas[0], self.py1, hace=89)
        self.prestar(self.personas[1], self.jv[0], hace=90)
        respuesta = self.informe()
        self.assertEqual((respuesta.context['desde'], respuesta.context['hasta']), (self.hoy - timedelta(days=89), self.hoy))
        self.assertEqual(list(self.por_titulo(respuesta)), ['Python'])
        self.assertContains(respuesta, f'Del {self.hoy - timedelta(days=89):%d/%m/%Y} al {self.hoy:%d/%m/%Y}')

    def test_periodo_elegido(self):
        self.prestar(self.personas[0], self.py1, hace=200)
        self.reserva(self.personas[1], self.java, hace=150)
        self.prestar(self.personas[2], self.jv[0], hace=5)
        desde, hasta = self.hoy - timedelta(days=210), self.hoy - timedelta(days=100)
        respuesta = self.informe(f'?desde={desde.isoformat()}&hasta={hasta.isoformat()}')
        self.assertEqual(sorted(self.por_titulo(respuesta)), ['Java', 'Python'])
        self.assertIsNone(respuesta.context['error_periodo'])

    def test_fecha_invalida_o_al_reves_vuelve_al_periodo_por_defecto(self):
        for consulta, error in (('?desde=31/12/2026', 'Alguna fecha no es válida'),
                                (f'?desde={self.hoy.isoformat()}&hasta={(self.hoy - timedelta(days=1)).isoformat()}',
                                 'La fecha &quot;desde&quot; es posterior a &quot;hasta&quot;')):
            with self.subTest(consulta=consulta):
                respuesta = self.informe(consulta)
                self.assertContains(respuesta, error)
                self.assertEqual(respuesta.context['desde'], self.hoy - timedelta(days=89))

    def test_solo_una_de_las_fechas(self):
        desde, hasta, error = demanda.leer_periodo('', (self.hoy - timedelta(days=10)).isoformat(), hoy=self.hoy)
        self.assertEqual((desde, hasta, error), (self.hoy - timedelta(days=89), self.hoy - timedelta(days=10), None))
        desde, hasta, error = demanda.leer_periodo((self.hoy - timedelta(days=10)).isoformat(), '', hoy=self.hoy)
        self.assertEqual((desde, hasta, error), (self.hoy - timedelta(days=10), self.hoy, None))

    def test_las_reservas_fuera_del_periodo_no_cuentan(self):
        self.reserva(self.personas[0], self.python, estado='RECHAZADA', hace=200)
        self.reserva(self.personas[1], self.python)
        python = self.por_titulo(self.informe())['Python']
        self.assertEqual((python.total_reservas, python.reservas_sin_ejemplar), (1, 1))


class FiltroYExportacionTests(DemandaTestCase):
    def setUp(self):
        super().setUp()
        self.reserva(self.personas[0], self.python)
        self.reserva(self.personas[1], self.python)
        self.prestar(self.personas[2], self.jv[0])

    def test_solo_los_que_conviene_comprar(self):
        respuesta = self.informe('?solo_comprar=1')
        self.assertEqual(list(self.por_titulo(respuesta)), ['Python'])

    def test_exportacion_csv(self):
        respuesta = self.informe('?formato=csv')
        self.assertEqual(respuesta['Content-Type'], 'text/csv; charset=utf-8')
        desde = self.hoy - timedelta(days=89)
        self.assertIn(f'sigebi-demanda-{desde:%Y%m%d}-{self.hoy:%Y%m%d}-', respuesta['Content-Disposition'])
        filas = respuesta.content.decode('utf-8-sig').splitlines()
        self.assertEqual(filas[0], 'Título;Autor;Categoría;Préstamos;Reservas;Reservas sin ejemplar;Ejemplares activos;Conviene comprar más')
        self.assertEqual(filas[1], 'Python;Autora, Ana;Informática;0;2;2;1;Sí')
        self.assertEqual(filas[2], 'Java;Autora, Ana;Informática;1;0;0;3;No')

    def test_el_csv_respeta_el_filtro(self):
        filas = self.informe('?solo_comprar=1&formato=csv').content.decode('utf-8-sig').splitlines()
        self.assertEqual(len(filas), 2)


class AccesoTests(DemandaTestCase):
    def test_se_llega_desde_informes(self):
        self.assertContains(self.client.get(reverse('biblioteca:informes')), reverse('biblioteca:informe_demanda'))

    def test_sin_permiso_de_reservas_no_entra(self):
        usuario = get_user_model().objects.create_user(username='consulta', password=CLAVE)
        usuario.user_permissions.add(Permission.objects.get(codename='view_prestamo'))
        self.client.force_login(usuario)
        self.assertEqual(self.informe().status_code, 403)
        self.assertNotContains(self.client.get(reverse('biblioteca:informes')), reverse('biblioteca:informe_demanda'))

    def test_sin_sesion_va_al_ingreso(self):
        self.client.logout()
        self.assertEqual(self.informe().status_code, 302)
