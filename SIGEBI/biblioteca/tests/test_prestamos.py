"""Préstamos y devoluciones (Release 1, decisiones D2, D4 y D8).

- El préstamo se registra desde el ejemplar y vence a los 14 días corridos (D2).
- Solo se presta a personas activas y si el ejemplar está disponible.
- La devolución no puede ser anterior al préstamo ni futura (D8), y la base lo garantiza.
Las pruebas llaman a las URLs directamente, no solo a los enlaces del menú.
"""
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from biblioteca.models import (
    PLAZO_PRESTAMO_DIAS, Autor, Categoria, Editorial, Ejemplar, Libro, Persona, Prestamo,
)
from biblioteca.views import ELEMENTOS_POR_PAGINA, MENSAJE_EJEMPLAR_YA_PRESTADO
from cuentas.roles import ADMINISTRATIVO, BIBLIOTECARIO

CLAVE = 'clave-de-prueba-123'


def fecha(dias):
    """Fecha relativa a hoy, como texto AAAA-MM-DD (lo que envía el formulario)."""
    return (timezone.localdate() + timedelta(days=dias)).isoformat()


class PrestamosTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.bibliotecario = Usuario.objects.create_user(
            username='31222333', email='bibliotecario@example.com', password=CLAVE
        )
        cls.bibliotecario.groups.add(Group.objects.get(name=BIBLIOTECARIO))
        cls.administrativo = Usuario.objects.create_user(
            username='32333444', email='administrativo@example.com', password=CLAVE
        )
        cls.administrativo.groups.add(Group.objects.get(name=ADMINISTRATIVO))
        cls.sin_rol = Usuario.objects.create_user(
            username='30111222', email='sin.rol@example.com', password=CLAVE
        )

        cls.ana = Persona.objects.create(
            nombre='Ana', apellido='Pérez', documento='40111222', tipo=Persona.Tipo.ALUMNO
        )
        cls.bruno = Persona.objects.create(
            nombre='Bruno', apellido='Gómez', documento='30222333', tipo=Persona.Tipo.PROFESOR
        )
        cls.carla = Persona.objects.create(
            nombre='Carla', apellido='Ruiz', documento='35444555', tipo=Persona.Tipo.ALUMNO, activo=False
        )
        categoria = Categoria.objects.create(nombre='Matemática')
        autor = Autor.objects.create(nombre='Hugo', apellido='Ledesma')
        editorial = Editorial.objects.create(nombre='Ediciones del Valle')
        cls.calculo = Libro.objects.create(titulo='Cálculo I', categoria=categoria, autor=autor, editorial=editorial)
        cls.algebra = Libro.objects.create(titulo='Álgebra', categoria=categoria, autor=autor, editorial=editorial)
        cls.ejemplar = Ejemplar.objects.create(codigo_inventario='CAL-001', libro=cls.calculo)
        cls.otro_ejemplar = Ejemplar.objects.create(codigo_inventario='ALG-001', libro=cls.algebra)
        cls.tercer_ejemplar = Ejemplar.objects.create(codigo_inventario='ALG-002', libro=cls.algebra)

    def setUp(self):
        self.client.force_login(self.bibliotecario)

    def url_prestar(self, ejemplar=None):
        return reverse('biblioteca:prestamo_create', args=[(ejemplar or self.ejemplar).pk])

    def prestar(self, ejemplar=None, **cambios):
        datos = {'documento': self.ana.documento, 'fecha_prestamo': fecha(0), 'fecha_vencimiento': ''}
        datos.update(cambios)
        return self.client.post(self.url_prestar(ejemplar), datos)

    def crear_prestamo(self, persona, ejemplar, dias_prestamo=-3, dias_vencimiento=11, dias_devolucion=None):
        hoy = timezone.localdate()
        return Prestamo.objects.create(
            persona=persona,
            ejemplar=ejemplar,
            usuario_sistema=self.bibliotecario,
            fecha_prestamo=hoy + timedelta(days=dias_prestamo),
            fecha_vencimiento=hoy + timedelta(days=dias_vencimiento),
            fecha_devolucion=None if dias_devolucion is None else hoy + timedelta(days=dias_devolucion),
        )

    def url_devolver(self, prestamo):
        return reverse('biblioteca:prestamo_devolver', args=[prestamo.pk])

    def errores(self, respuesta):
        return respuesta.context['form'].errors


class PermisosDePrestamosTests(PrestamosTestCase):
    def setUp(self):
        super().setUp()
        self.prestamo = self.crear_prestamo(self.bruno, self.otro_ejemplar)

    def urls(self):
        return [
            reverse('biblioteca:prestamo_list'),
            self.url_prestar(),
            self.url_devolver(self.prestamo),
        ]

    def test_sin_sesion_pide_ingresar(self):
        self.client.logout()
        for url in self.urls():
            with self.subTest(url=url):
                respuesta = self.client.get(url)
                self.assertEqual(respuesta.status_code, 302)
                self.assertIn(reverse('login'), respuesta['Location'])

    def test_usuario_sin_rol_no_presta_ni_devuelve(self):
        self.client.force_login(self.sin_rol)
        for url in self.urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.prestar().status_code, 403)
        self.assertEqual(self.client.post(self.url_devolver(self.prestamo), {'fecha_devolucion': fecha(0)}).status_code, 403)
        self.assertTrue(self.ejemplar.disponible)
        self.prestamo.refresh_from_db()
        self.assertIsNone(self.prestamo.fecha_devolucion)

    def test_bibliotecario_y_administrativo_operan_prestamos(self):
        for usuario in (self.bibliotecario, self.administrativo):
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)
                for url in self.urls():
                    self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_el_menu_tiene_el_enlace_a_prestamos(self):
        respuesta = self.client.get(reverse('biblioteca:inicio'))
        self.assertContains(respuesta, 'href="' + reverse('biblioteca:prestamo_list') + '"')


class RegistroDePrestamoTests(PrestamosTestCase):
    def test_el_formulario_propone_hoy_y_vencimiento_a_14_dias(self):
        self.assertEqual(PLAZO_PRESTAMO_DIAS, 14)
        respuesta = self.client.get(self.url_prestar())
        self.assertContains(respuesta, f'value="{fecha(0)}"')
        self.assertContains(respuesta, f'value="{fecha(14)}"')

    def test_prestamo_con_vencimiento_automatico(self):
        respuesta = self.prestar()
        self.assertRedirects(respuesta, reverse('biblioteca:ejemplar_detail', args=[self.ejemplar.pk]))
        prestamo = Prestamo.objects.get(ejemplar=self.ejemplar)
        hoy = timezone.localdate()
        self.assertEqual(prestamo.persona, self.ana)
        self.assertEqual(prestamo.fecha_prestamo, hoy)
        self.assertEqual(prestamo.fecha_vencimiento, hoy + timedelta(days=14))
        self.assertIsNone(prestamo.fecha_devolucion)
        self.assertEqual(prestamo.usuario_sistema, self.bibliotecario)
        self.assertFalse(self.ejemplar.disponible)

    def test_el_vencimiento_se_calcula_desde_la_fecha_de_prestamo(self):
        self.prestar(fecha_prestamo=fecha(-5))
        prestamo = Prestamo.objects.get(ejemplar=self.ejemplar)
        self.assertEqual(prestamo.fecha_vencimiento, timezone.localdate() + timedelta(days=9))

    def test_el_vencimiento_se_puede_corregir_a_mano(self):
        self.prestar(fecha_vencimiento=fecha(7))
        prestamo = Prestamo.objects.get(ejemplar=self.ejemplar)
        self.assertEqual(prestamo.fecha_vencimiento, timezone.localdate() + timedelta(days=7))

    def test_mensaje_de_exito_con_el_vencimiento(self):
        respuesta = self.client.post(
            self.url_prestar(), {'documento': '40111222', 'fecha_prestamo': fecha(0)}, follow=True
        )
        vence = (timezone.localdate() + timedelta(days=14)).strftime('%d/%m/%Y')
        self.assertContains(respuesta, f'Vence el {vence}.')

    def test_documento_con_puntos_encuentra_a_la_persona(self):
        self.prestar(documento='40.111.222')
        self.assertEqual(Prestamo.objects.get(ejemplar=self.ejemplar).persona, self.ana)

    def test_persona_inexistente(self):
        respuesta = self.prestar(documento='99999999')
        self.assertIn('No hay ninguna persona registrada con ese documento', str(self.errores(respuesta)['documento']))
        self.assertFalse(Prestamo.objects.exists())

    def test_persona_dada_de_baja_no_recibe_prestamos(self):
        respuesta = self.prestar(documento=self.carla.documento)
        self.assertIn('está dada de baja', str(self.errores(respuesta)['documento']))
        self.assertFalse(Prestamo.objects.exists())

    def test_fecha_de_prestamo_futura(self):
        respuesta = self.prestar(fecha_prestamo=fecha(1))
        self.assertIn('fecha_prestamo', self.errores(respuesta))
        self.assertFalse(Prestamo.objects.exists())

    def test_vencimiento_anterior_al_prestamo(self):
        respuesta = self.prestar(fecha_vencimiento=fecha(-1))
        self.assertIn('fecha_vencimiento', self.errores(respuesta))
        self.assertFalse(Prestamo.objects.exists())

    def test_datos_obligatorios(self):
        respuesta = self.client.post(self.url_prestar(), {})
        for campo in ('documento', 'fecha_prestamo'):
            with self.subTest(campo=campo):
                self.assertIn(campo, self.errores(respuesta))
        self.assertNotIn('fecha_vencimiento', self.errores(respuesta))
        self.assertFalse(Prestamo.objects.exists())

    def test_ejemplar_prestado_no_ofrece_el_formulario(self):
        self.crear_prestamo(self.bruno, self.ejemplar)
        respuesta = self.client.get(self.url_prestar(), follow=True)
        self.assertRedirects(respuesta, reverse('biblioteca:ejemplar_detail', args=[self.ejemplar.pk]))
        self.assertContains(respuesta, MENSAJE_EJEMPLAR_YA_PRESTADO)

    def test_ejemplar_prestado_no_se_vuelve_a_prestar(self):
        self.crear_prestamo(self.bruno, self.ejemplar)
        respuesta = self.prestar()
        self.assertIn(MENSAJE_EJEMPLAR_YA_PRESTADO, self.errores(respuesta)['__all__'])
        self.assertEqual(Prestamo.objects.filter(ejemplar=self.ejemplar).count(), 1)

    def test_dos_prestamos_simultaneos_no_dan_error_500(self):
        # Simula que otra persona prestó el ejemplar después de validar el formulario:
        # la base rechaza el segundo préstamo activo y se vuelve al formulario.
        self.crear_prestamo(self.bruno, self.ejemplar)
        with mock.patch.object(Ejemplar, 'disponible', new_callable=mock.PropertyMock, return_value=True):
            respuesta = self.prestar()
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn(MENSAJE_EJEMPLAR_YA_PRESTADO, self.errores(respuesta)['__all__'])
        self.assertEqual(Prestamo.objects.filter(ejemplar=self.ejemplar).count(), 1)

    def test_ejemplar_inexistente_da_404(self):
        respuesta = self.client.get(reverse('biblioteca:prestamo_create', args=[999999]))
        self.assertEqual(respuesta.status_code, 404)


class DevolucionTests(PrestamosTestCase):
    def setUp(self):
        super().setUp()
        self.prestamo = self.crear_prestamo(self.ana, self.ejemplar, dias_prestamo=-10, dias_vencimiento=4)

    def devolver(self, dias):
        return self.client.post(self.url_devolver(self.prestamo), {'fecha_devolucion': fecha(dias)})

    def test_el_formulario_propone_hoy(self):
        respuesta = self.client.get(self.url_devolver(self.prestamo))
        self.assertContains(respuesta, f'value="{fecha(0)}"')
        self.assertContains(respuesta, 'CAL-001')

    def test_devolucion_libera_el_ejemplar(self):
        respuesta = self.devolver(0)
        self.assertRedirects(respuesta, reverse('biblioteca:ejemplar_detail', args=[self.ejemplar.pk]))
        self.prestamo.refresh_from_db()
        self.assertEqual(self.prestamo.fecha_devolucion, timezone.localdate())
        self.assertTrue(self.ejemplar.disponible)

    def test_devolucion_en_una_fecha_pasada_valida(self):
        self.devolver(-2)
        self.prestamo.refresh_from_db()
        self.assertEqual(self.prestamo.fecha_devolucion, timezone.localdate() - timedelta(days=2))

    def test_devolucion_el_mismo_dia_del_prestamo(self):
        self.devolver(-10)
        self.prestamo.refresh_from_db()
        self.assertEqual(self.prestamo.fecha_devolucion, self.prestamo.fecha_prestamo)

    def test_devolucion_anterior_al_prestamo_se_rechaza(self):
        respuesta = self.devolver(-11)
        self.assertIn('no puede ser anterior a la fecha de préstamo', str(self.errores(respuesta)['fecha_devolucion']))
        self.prestamo.refresh_from_db()
        self.assertIsNone(self.prestamo.fecha_devolucion)

    def test_devolucion_futura_se_rechaza(self):
        respuesta = self.devolver(1)
        self.assertIn('no puede ser futura', str(self.errores(respuesta)['fecha_devolucion']))
        self.prestamo.refresh_from_db()
        self.assertIsNone(self.prestamo.fecha_devolucion)

    def test_devolucion_ya_registrada_no_se_repite(self):
        self.devolver(-1)
        respuesta = self.client.post(self.url_devolver(self.prestamo), {'fecha_devolucion': fecha(0)}, follow=True)
        self.assertContains(respuesta, 'ya tiene registrada su devolución')
        self.prestamo.refresh_from_db()
        self.assertEqual(self.prestamo.fecha_devolucion, timezone.localdate() - timedelta(days=1))

    def test_el_ejemplar_devuelto_se_puede_volver_a_prestar(self):
        self.devolver(0)
        self.prestar(documento=self.bruno.documento)
        self.assertEqual(Prestamo.objects.filter(ejemplar=self.ejemplar, fecha_devolucion__isnull=True).get().persona, self.bruno)


class RestriccionDeLaBaseTests(PrestamosTestCase):
    def test_la_base_no_acepta_devolucion_anterior_al_prestamo(self):
        # D8: aunque se saltee el formulario (por ejemplo, desde el Admin o el shell), la base lo impide.
        prestamo = self.crear_prestamo(self.ana, self.ejemplar, dias_prestamo=-5, dias_vencimiento=9)
        prestamo.fecha_devolucion = prestamo.fecha_prestamo - timedelta(days=1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            prestamo.save()

    def test_la_base_acepta_devolucion_el_mismo_dia(self):
        prestamo = self.crear_prestamo(self.ana, self.ejemplar, dias_prestamo=-5, dias_vencimiento=9)
        prestamo.fecha_devolucion = prestamo.fecha_prestamo
        prestamo.save()
        self.assertFalse(prestamo.activo)


class ListadoDePrestamosTests(PrestamosTestCase):
    def setUp(self):
        super().setUp()
        self.vigente = self.crear_prestamo(self.ana, self.ejemplar, dias_prestamo=-3, dias_vencimiento=11)
        self.vencido = self.crear_prestamo(self.bruno, self.otro_ejemplar, dias_prestamo=-20, dias_vencimiento=-6)
        self.devuelto = self.crear_prestamo(
            self.ana, self.tercer_ejemplar, dias_prestamo=-30, dias_vencimiento=-16, dias_devolucion=-18
        )

    def listar(self, **parametros):
        return list(self.client.get(reverse('biblioteca:prestamo_list'), parametros).context['object_list'])

    def test_por_defecto_muestra_los_sin_devolver_ordenados_por_vencimiento(self):
        self.assertEqual(self.listar(), [self.vencido, self.vigente])

    def test_filtra_vencidos(self):
        self.assertEqual(self.listar(estado='vencidos'), [self.vencido])

    def test_filtra_devueltos_y_todos(self):
        self.assertEqual(self.listar(estado='devueltos'), [self.devuelto])
        self.assertEqual(set(self.listar(estado='todos')), {self.vigente, self.vencido, self.devuelto})

    def test_estado_desconocido_muestra_los_sin_devolver(self):
        self.assertEqual(self.listar(estado='cualquiera'), [self.vencido, self.vigente])

    def test_un_prestamo_que_vence_hoy_no_esta_vencido(self):
        hoy = self.crear_prestamo(self.carla, self.tercer_ejemplar, dias_prestamo=-14, dias_vencimiento=0)
        self.assertNotIn(hoy, self.listar(estado='vencidos'))
        self.assertFalse(hoy.vencido)

    def test_busca_por_persona_sin_tildes_documento_codigo_y_titulo(self):
        casos = {
            'gomez': [self.vencido],
            '40.111.222': [self.vigente],
            'cal-001': [self.vigente],
            'algebra': [self.vencido],
        }
        for texto, esperado in casos.items():
            with self.subTest(texto=texto):
                self.assertEqual(self.listar(q=texto), esperado)

    def test_vencido_se_marca_y_ofrece_devolucion(self):
        respuesta = self.client.get(reverse('biblioteca:prestamo_list'))
        self.assertContains(respuesta, 'badge-vencido')
        self.assertContains(respuesta, 'href="' + self.url_devolver(self.vencido) + '"')

    def test_la_paginacion_conserva_los_filtros(self):
        for numero in range(ELEMENTOS_POR_PAGINA + 1):
            ejemplar = Ejemplar.objects.create(codigo_inventario=f'VEN-{numero:03d}', libro=self.calculo)
            self.crear_prestamo(self.ana, ejemplar, dias_prestamo=-20, dias_vencimiento=-5)
        respuesta = self.client.get(reverse('biblioteca:prestamo_list'), {'q': 'ven-', 'estado': 'vencidos'})
        self.assertContains(respuesta, '?q=ven-&amp;estado=vencidos&amp;page=2')


class PantallasRelacionadasTests(PrestamosTestCase):
    def test_ejemplar_disponible_ofrece_prestar(self):
        respuesta = self.client.get(reverse('biblioteca:ejemplar_detail', args=[self.ejemplar.pk]))
        self.assertContains(respuesta, 'href="' + self.url_prestar() + '"')
        self.assertContains(respuesta, 'Este ejemplar todavía no se prestó.')

    def test_ejemplar_prestado_muestra_a_quien_y_ofrece_devolucion(self):
        prestamo = self.crear_prestamo(self.ana, self.ejemplar)
        respuesta = self.client.get(reverse('biblioteca:ejemplar_detail', args=[self.ejemplar.pk]))
        self.assertContains(respuesta, 'Prestado a')
        self.assertContains(respuesta, 'Pérez, Ana')
        self.assertContains(respuesta, 'href="' + self.url_devolver(prestamo) + '"')
        self.assertNotContains(respuesta, 'href="' + self.url_prestar() + '"')

    def test_la_persona_ofrece_devolver_sus_prestamos_activos(self):
        prestamo = self.crear_prestamo(self.ana, self.ejemplar)
        respuesta = self.client.get(reverse('biblioteca:persona_detail', args=[self.ana.pk]))
        self.assertContains(respuesta, 'href="' + self.url_devolver(prestamo) + '"')
