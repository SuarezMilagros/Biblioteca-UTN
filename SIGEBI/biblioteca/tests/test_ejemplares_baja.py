"""Baja lógica de ejemplares y búsqueda por código de inventario (Release 1).

- Un ejemplar dado de baja (perdido, dañado, descarte u otro) conserva su historial
  y no se puede prestar. No se da de baja si está prestado. Se puede reactivar.
- En Ejemplares se busca por código, ID de inventario o título. Si el código
  coincide exacto, se abre directamente el ejemplar.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from biblioteca.forms import MENSAJE_EJEMPLAR_DADO_DE_BAJA
from biblioteca.models import Autor, Categoria, Editorial, Ejemplar, Libro, Persona, Prestamo
from cuentas.roles import BIBLIOTECARIO

CLAVE = 'clave-de-prueba-123'


class EjemplaresTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.bibliotecario = Usuario.objects.create_user(
            username='31222333', email='bibliotecario@example.com', password=CLAVE
        )
        cls.bibliotecario.groups.add(Group.objects.get(name=BIBLIOTECARIO))
        cls.sin_rol = Usuario.objects.create_user(username='30111222', email='sin.rol@example.com', password=CLAVE)
        cls.ana = Persona.objects.create(nombre='Ana', apellido='Pérez', documento='40111222', tipo=Persona.Tipo.ALUMNO)
        categoria = Categoria.objects.create(nombre='Matemática')
        autor = Autor.objects.create(nombre='Hugo', apellido='Ledesma')
        editorial = Editorial.objects.create(nombre='Ediciones del Valle')
        cls.calculo = Libro.objects.create(titulo='Cálculo I', categoria=categoria, autor=autor, editorial=editorial)
        cls.algebra = Libro.objects.create(titulo='Álgebra Lineal', categoria=categoria, autor=autor, editorial=editorial)
        cls.cal1 = Ejemplar.objects.create(codigo_inventario='CAL-001', id_inventario=501, libro=cls.calculo)
        cls.cal2 = Ejemplar.objects.create(codigo_inventario='CAL-002', libro=cls.calculo)
        cls.alg1 = Ejemplar.objects.create(codigo_inventario='ALG-001', libro=cls.algebra)
        cls.perdido = Ejemplar.objects.create(
            codigo_inventario='ALG-099', libro=cls.algebra, activo=False,
            motivo_baja=Ejemplar.MotivoBaja.PERDIDO, fecha_baja=timezone.localdate() - timedelta(days=10),
        )

    def setUp(self):
        self.client.force_login(self.bibliotecario)

    def dar_de_baja(self, ejemplar, motivo=Ejemplar.MotivoBaja.DANADO):
        return self.client.post(reverse('biblioteca:ejemplar_baja', args=[ejemplar.pk]), {'motivo_baja': motivo}, follow=True)

    def prestar(self, ejemplar):
        hoy = timezone.localdate()
        return Prestamo.objects.create(
            persona=self.ana, ejemplar=ejemplar, usuario_sistema=self.bibliotecario,
            fecha_prestamo=hoy, fecha_vencimiento=hoy + timedelta(days=14),
        )

    def listar(self, **parametros):
        return self.client.get(reverse('biblioteca:ejemplar_list'), parametros)


class BajaDeEjemplarTests(EjemplaresTestCase):
    def test_baja_guarda_motivo_y_fecha_y_conserva_el_registro(self):
        respuesta = self.dar_de_baja(self.cal2)
        self.assertContains(respuesta, 'quedó dado de baja (Dañado).')
        self.cal2.refresh_from_db()
        self.assertFalse(self.cal2.activo)
        self.assertEqual(self.cal2.motivo_baja, Ejemplar.MotivoBaja.DANADO)
        self.assertEqual(self.cal2.fecha_baja, timezone.localdate())
        self.assertFalse(self.cal2.disponible)

    def test_no_se_da_de_baja_un_ejemplar_prestado(self):
        self.prestar(self.cal1)
        respuesta = self.dar_de_baja(self.cal1)
        self.assertContains(respuesta, 'tiene un préstamo sin devolver.')
        self.cal1.refresh_from_db()
        self.assertTrue(self.cal1.activo)

    def test_el_motivo_es_obligatorio(self):
        respuesta = self.client.post(reverse('biblioteca:ejemplar_baja', args=[self.cal2.pk]), {}, follow=True)
        self.assertContains(respuesta, 'Elegí el motivo de la baja.')
        respuesta = self.dar_de_baja(self.cal2, motivo='ROBADO_POR_MARCIANOS')
        self.assertContains(respuesta, 'Elegí el motivo de la baja.')
        self.cal2.refresh_from_db()
        self.assertTrue(self.cal2.activo)

    def test_reactivar_limpia_los_datos_de_baja(self):
        respuesta = self.client.post(reverse('biblioteca:ejemplar_reactivar', args=[self.perdido.pk]), follow=True)
        self.assertContains(respuesta, 'volvió a estar activo.')
        self.perdido.refresh_from_db()
        self.assertTrue(self.perdido.activo)
        self.assertEqual((self.perdido.motivo_baja, self.perdido.fecha_baja), ('', None))
        self.assertTrue(self.perdido.disponible)

    def test_baja_y_reactivacion_solo_por_post_y_con_permiso(self):
        for nombre in ('biblioteca:ejemplar_baja', 'biblioteca:ejemplar_reactivar'):
            with self.subTest(url=nombre):
                self.assertEqual(self.client.get(reverse(nombre, args=[self.cal2.pk])).status_code, 405)
        self.client.force_login(self.sin_rol)
        respuesta = self.client.post(reverse('biblioteca:ejemplar_baja', args=[self.cal2.pk]), {'motivo_baja': 'PERDIDO'})
        self.assertEqual(respuesta.status_code, 403)
        self.cal2.refresh_from_db()
        self.assertTrue(self.cal2.activo)

    def test_la_base_exige_coherencia_entre_estado_y_datos_de_baja(self):
        casos = [
            {'activo': False, 'motivo_baja': '', 'fecha_baja': timezone.localdate()},
            {'activo': False, 'motivo_baja': 'PERDIDO', 'fecha_baja': None},
            {'activo': True, 'motivo_baja': 'PERDIDO', 'fecha_baja': None},
        ]
        for numero, datos in enumerate(casos):
            with self.subTest(datos=datos), self.assertRaises(IntegrityError), transaction.atomic():
                Ejemplar.objects.create(codigo_inventario=f'MAL-{numero}', libro=self.calculo, **datos)


class PrestamoDeEjemplarDadoDeBajaTests(EjemplaresTestCase):
    def test_no_ofrece_prestar(self):
        respuesta = self.client.get(reverse('biblioteca:ejemplar_detail', args=[self.perdido.pk]))
        self.assertContains(respuesta, 'Dado de baja')
        self.assertContains(respuesta, 'Perdido')
        self.assertNotContains(respuesta, reverse('biblioteca:prestamo_create', args=[self.perdido.pk]))
        self.assertContains(respuesta, 'Reactivar ejemplar')

    def test_el_formulario_de_prestamo_no_se_abre(self):
        respuesta = self.client.get(reverse('biblioteca:prestamo_create', args=[self.perdido.pk]), follow=True)
        self.assertRedirects(respuesta, reverse('biblioteca:ejemplar_detail', args=[self.perdido.pk]))
        self.assertContains(respuesta, MENSAJE_EJEMPLAR_DADO_DE_BAJA)

    def test_no_se_puede_prestar_por_post(self):
        respuesta = self.client.post(
            reverse('biblioteca:prestamo_create', args=[self.perdido.pk]),
            {'documento': self.ana.documento, 'fecha_prestamo': timezone.localdate().isoformat()},
        )
        self.assertIn(MENSAJE_EJEMPLAR_DADO_DE_BAJA, respuesta.context['form'].errors['__all__'])
        self.assertFalse(Prestamo.objects.filter(ejemplar=self.perdido).exists())


class ListadoYBusquedaDeEjemplaresTests(EjemplaresTestCase):
    def codigos(self, respuesta):
        return [e.codigo_inventario for e in respuesta.context['object_list']]

    def test_por_defecto_muestra_solo_activos(self):
        self.assertEqual(self.codigos(self.listar(todos='1')), ['ALG-001', 'CAL-001', 'CAL-002'])

    def test_filtra_dados_de_baja_y_todos(self):
        self.assertEqual(self.codigos(self.listar(estado='baja')), ['ALG-099'])
        self.assertEqual(len(self.codigos(self.listar(estado='todos'))), 4)

    def test_codigo_exacto_abre_el_ejemplar(self):
        for texto in ('CAL-002', ' cal-002 '):
            with self.subTest(texto=texto):
                self.assertRedirects(self.listar(q=texto), reverse('biblioteca:ejemplar_detail', args=[self.cal2.pk]))

    def test_codigo_exacto_de_un_ejemplar_dado_de_baja_tambien_lo_abre(self):
        self.assertRedirects(self.listar(q='alg-099'), reverse('biblioteca:ejemplar_detail', args=[self.perdido.pk]))

    def test_codigo_parcial_lista_coincidencias(self):
        self.assertEqual(self.codigos(self.listar(q='cal')), ['CAL-001', 'CAL-002'])

    def test_busca_por_id_de_inventario(self):
        self.assertEqual(self.codigos(self.listar(q='501')), ['CAL-001'])

    def test_busca_por_titulo_sin_tildes(self):
        self.assertEqual(self.codigos(self.listar(q='algebra')), ['ALG-001'])

    def test_sin_resultados(self):
        self.assertContains(self.listar(q='zzz'), 'No se encontraron ejemplares con «zzz».')

    def test_el_listado_muestra_el_estado(self):
        self.prestar(self.cal1)
        respuesta = self.listar(estado='todos')
        self.assertContains(respuesta, 'badge-prestado')
        self.assertContains(respuesta, 'badge-disponible')
        self.assertContains(respuesta, 'badge-baja')
