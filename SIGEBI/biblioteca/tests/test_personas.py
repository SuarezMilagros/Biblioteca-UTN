"""Gestión de personas: alta, consulta, edición y baja lógica (Release 1, decisión D4).

Las pruebas llaman a las URLs directamente, no solo a los enlaces del menú.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from biblioteca.forms import MENSAJE_DOCUMENTO_REPETIDO
from biblioteca.models import Autor, Categoria, Editorial, Ejemplar, Libro, Persona, Prestamo
from biblioteca.views import ELEMENTOS_POR_PAGINA
from cuentas.roles import ADMINISTRATIVO, BIBLIOTECARIO

CLAVE = 'clave-de-prueba-123'


class PersonasTestCase(TestCase):
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
            nombre='Ana', apellido='Pérez', documento='40111222', tipo=Persona.Tipo.ALUMNO, legajo='A-100'
        )
        cls.bruno = Persona.objects.create(
            nombre='Bruno', apellido='Gómez', documento='30222333', tipo=Persona.Tipo.PROFESOR
        )
        cls.carla = Persona.objects.create(
            nombre='Carla', apellido='Ruiz', documento='35444555', tipo=Persona.Tipo.ALUMNO, activo=False
        )

        libro = Libro.objects.create(
            titulo='Cálculo I',
            categoria=Categoria.objects.create(nombre='Matemática'),
            autor=Autor.objects.create(nombre='Hugo', apellido='Ledesma'),
            editorial=Editorial.objects.create(nombre='Ediciones del Valle'),
        )
        cls.ejemplar = Ejemplar.objects.create(codigo_inventario='CAL-001', libro=libro)
        cls.otro_ejemplar = Ejemplar.objects.create(codigo_inventario='CAL-002', libro=libro)

    def setUp(self):
        self.client.force_login(self.bibliotecario)

    def datos(self, **cambios):
        datos = {
            'nombre': 'Lucía',
            'apellido': 'Paz',
            'documento': '41222333',
            'tipo': Persona.Tipo.ALUMNO,
            'legajo': '',
        }
        datos.update(cambios)
        return datos

    def prestar(self, persona, ejemplar, devuelto=False):
        hoy = timezone.localdate()
        return Prestamo.objects.create(
            persona=persona,
            ejemplar=ejemplar,
            usuario_sistema=self.bibliotecario,
            fecha_prestamo=hoy - timedelta(days=3),
            fecha_vencimiento=hoy + timedelta(days=11),
            fecha_devolucion=hoy if devuelto else None,
        )

    def listar(self, **parametros):
        return self.client.get(reverse('biblioteca:persona_list'), parametros)

    def personas_listadas(self, respuesta):
        return list(respuesta.context['object_list'])


class PermisosDePersonasTests(PersonasTestCase):
    def urls(self):
        return [
            reverse('biblioteca:persona_list'),
            reverse('biblioteca:persona_create'),
            reverse('biblioteca:persona_detail', args=[self.ana.pk]),
            reverse('biblioteca:persona_update', args=[self.ana.pk]),
        ]

    def test_sin_sesion_pide_ingresar(self):
        self.client.logout()
        for url in self.urls():
            with self.subTest(url=url):
                respuesta = self.client.get(url)
                self.assertEqual(respuesta.status_code, 302)
                self.assertIn(reverse('login'), respuesta['Location'])

    def test_usuario_sin_rol_no_entra(self):
        self.client.force_login(self.sin_rol)
        for url in self.urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
        respuesta = self.client.post(reverse('biblioteca:persona_baja', args=[self.ana.pk]))
        self.assertEqual(respuesta.status_code, 403)
        self.ana.refresh_from_db()
        self.assertTrue(self.ana.activo)

    def test_bibliotecario_y_administrativo_gestionan_personas(self):
        for usuario in (self.bibliotecario, self.administrativo):
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)
                for url in self.urls():
                    self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_el_menu_tiene_el_enlace_a_personas(self):
        respuesta = self.client.get(reverse('biblioteca:inicio'))
        self.assertContains(respuesta, 'href="' + reverse('biblioteca:persona_list') + '"')

    def test_la_seccion_personas_se_marca_como_activa(self):
        respuesta = self.listar()
        self.assertContains(respuesta, 'href="' + reverse('biblioteca:persona_list') + '" aria-current="page"')


class AltaYEdicionDePersonasTests(PersonasTestCase):
    def test_alta_de_una_persona(self):
        respuesta = self.client.post(reverse('biblioteca:persona_create'), self.datos(), follow=True)
        persona = Persona.objects.get(documento='41222333')
        self.assertRedirects(respuesta, reverse('biblioteca:persona_detail', args=[persona.pk]))
        self.assertContains(respuesta, 'Persona &quot;Paz, Lucía&quot; registrada.')
        self.assertTrue(persona.activo)
        self.assertEqual(persona.tipo, Persona.Tipo.ALUMNO)

    def test_datos_obligatorios(self):
        antes = Persona.objects.count()
        respuesta = self.client.post(reverse('biblioteca:persona_create'), {})
        self.assertEqual(respuesta.status_code, 200)
        errores = respuesta.context['form'].errors
        for campo in ('nombre', 'apellido', 'documento', 'tipo'):
            with self.subTest(campo=campo):
                self.assertIn(campo, errores)
        self.assertNotIn('legajo', errores)
        self.assertEqual(Persona.objects.count(), antes)

    def test_el_documento_se_guarda_sin_puntos_ni_espacios(self):
        self.client.post(reverse('biblioteca:persona_create'), self.datos(documento=' 41.222.333 '))
        self.assertTrue(Persona.objects.filter(documento='41222333').exists())

    def test_documento_repetido_se_rechaza_aunque_tenga_puntos(self):
        antes = Persona.objects.count()
        respuesta = self.client.post(reverse('biblioteca:persona_create'), self.datos(documento='40.111.222'))
        self.assertEqual(respuesta.context['form'].errors['documento'], [MENSAJE_DOCUMENTO_REPETIDO])
        self.assertEqual(Persona.objects.count(), antes)

    def test_documento_solo_con_puntos_es_obligatorio(self):
        respuesta = self.client.post(reverse('biblioteca:persona_create'), self.datos(documento=' . . '))
        self.assertIn('documento', respuesta.context['form'].errors)

    def test_tipo_invalido_se_rechaza(self):
        respuesta = self.client.post(reverse('biblioteca:persona_create'), self.datos(tipo='VISITANTE'))
        self.assertIn('tipo', respuesta.context['form'].errors)

    def test_edicion_de_una_persona(self):
        url = reverse('biblioteca:persona_update', args=[self.ana.pk])
        datos = self.datos(nombre='Ana María', apellido='Pérez', documento='40111222', legajo='A-101')
        respuesta = self.client.post(url, datos)
        self.assertRedirects(respuesta, reverse('biblioteca:persona_detail', args=[self.ana.pk]))
        self.ana.refresh_from_db()
        self.assertEqual((self.ana.nombre, self.ana.legajo), ('Ana María', 'A-101'))

    def test_la_edicion_no_puede_tomar_el_documento_de_otra_persona(self):
        url = reverse('biblioteca:persona_update', args=[self.ana.pk])
        respuesta = self.client.post(url, self.datos(documento=self.bruno.documento))
        self.assertEqual(respuesta.context['form'].errors['documento'], [MENSAJE_DOCUMENTO_REPETIDO])
        self.ana.refresh_from_db()
        self.assertEqual(self.ana.documento, '40111222')

    def test_el_formulario_no_permite_cambiar_el_estado(self):
        # La baja se hace con su botón, no desde el formulario de edición.
        url = reverse('biblioteca:persona_update', args=[self.ana.pk])
        self.client.post(url, self.datos(documento='40111222', activo=''))
        self.ana.refresh_from_db()
        self.assertTrue(self.ana.activo)


class ListadoYBusquedaDePersonasTests(PersonasTestCase):
    def test_por_defecto_muestra_solo_activas(self):
        self.assertEqual(self.personas_listadas(self.listar()), [self.bruno, self.ana])

    def test_filtra_dadas_de_baja_y_todas(self):
        self.assertEqual(self.personas_listadas(self.listar(estado='baja')), [self.carla])
        self.assertEqual(self.personas_listadas(self.listar(estado='todas')), [self.bruno, self.ana, self.carla])

    def test_estado_desconocido_muestra_activas(self):
        self.assertEqual(self.personas_listadas(self.listar(estado='cualquiera')), [self.bruno, self.ana])

    def test_busca_por_apellido_sin_tildes(self):
        self.assertEqual(self.personas_listadas(self.listar(q='perez')), [self.ana])

    def test_busca_por_documento_aunque_tenga_puntos(self):
        self.assertEqual(self.personas_listadas(self.listar(q='40.111')), [self.ana])

    def test_busca_por_legajo(self):
        self.assertEqual(self.personas_listadas(self.listar(q='a-100')), [self.ana])

    def test_la_busqueda_respeta_el_estado(self):
        self.assertEqual(self.personas_listadas(self.listar(q='ruiz')), [])
        self.assertEqual(self.personas_listadas(self.listar(q='ruiz', estado='baja')), [self.carla])

    def test_la_paginacion_conserva_busqueda_y_estado(self):
        for numero in range(ELEMENTOS_POR_PAGINA + 1):
            Persona.objects.create(
                nombre=f'Persona {numero}', apellido='Zárate', documento=f'5000{numero:04d}',
                tipo=Persona.Tipo.ALUMNO, activo=False,
            )
        respuesta = self.listar(q='zarate', estado='baja')
        self.assertContains(respuesta, '?q=zarate&amp;estado=baja&amp;page=2')

    def test_sin_resultados_muestra_un_mensaje(self):
        self.assertContains(self.listar(q='nadie'), 'No se encontraron personas con «nadie».')


class BajaLogicaDePersonasTests(PersonasTestCase):
    def dar_de_baja(self, persona):
        return self.client.post(reverse('biblioteca:persona_baja', args=[persona.pk]), follow=True)

    def test_dar_de_baja_conserva_el_registro(self):
        respuesta = self.dar_de_baja(self.bruno)
        self.assertContains(respuesta, 'quedó dada de baja.')
        self.bruno.refresh_from_db()
        self.assertFalse(self.bruno.activo)
        self.assertTrue(Persona.objects.filter(pk=self.bruno.pk).exists())

    def test_no_se_da_de_baja_con_prestamos_sin_devolver(self):
        self.prestar(self.ana, self.ejemplar)
        respuesta = self.dar_de_baja(self.ana)
        self.assertContains(respuesta, 'tiene préstamos sin devolver.')
        self.ana.refresh_from_db()
        self.assertTrue(self.ana.activo)

    def test_se_da_de_baja_si_todos_sus_prestamos_estan_devueltos(self):
        self.prestar(self.ana, self.ejemplar, devuelto=True)
        self.dar_de_baja(self.ana)
        self.ana.refresh_from_db()
        self.assertFalse(self.ana.activo)

    def test_reactivar(self):
        respuesta = self.client.post(reverse('biblioteca:persona_reactivar', args=[self.carla.pk]), follow=True)
        self.assertContains(respuesta, 'volvió a estar activa.')
        self.carla.refresh_from_db()
        self.assertTrue(self.carla.activo)

    def test_baja_y_reactivacion_solo_aceptan_post(self):
        for nombre, persona in (('biblioteca:persona_baja', self.bruno), ('biblioteca:persona_reactivar', self.carla)):
            with self.subTest(url=nombre):
                self.assertEqual(self.client.get(reverse(nombre, args=[persona.pk])).status_code, 405)
        self.bruno.refresh_from_db()
        self.carla.refresh_from_db()
        self.assertTrue(self.bruno.activo)
        self.assertFalse(self.carla.activo)

    def test_persona_inexistente_da_404(self):
        self.assertEqual(self.client.post(reverse('biblioteca:persona_baja', args=[999999])).status_code, 404)


class DetalleDePersonaTests(PersonasTestCase):
    def test_muestra_datos_e_historial_de_prestamos(self):
        self.prestar(self.ana, self.ejemplar)
        self.prestar(self.ana, self.otro_ejemplar, devuelto=True)
        respuesta = self.client.get(reverse('biblioteca:persona_detail', args=[self.ana.pk]))
        self.assertContains(respuesta, '40111222')
        self.assertContains(respuesta, 'CAL-001')
        self.assertContains(respuesta, 'CAL-002')
        self.assertContains(respuesta, 'Sin devolver')
        self.assertContains(respuesta, 'Devuelto')
        self.assertContains(respuesta, 'Dar de baja')

    def test_prestamo_vencido_se_marca(self):
        hoy = timezone.localdate()
        Prestamo.objects.create(
            persona=self.bruno, ejemplar=self.ejemplar, usuario_sistema=self.bibliotecario,
            fecha_prestamo=hoy - timedelta(days=20), fecha_vencimiento=hoy - timedelta(days=6),
        )
        respuesta = self.client.get(reverse('biblioteca:persona_detail', args=[self.bruno.pk]))
        self.assertContains(respuesta, 'badge-vencido')

    def test_persona_dada_de_baja_ofrece_reactivar(self):
        respuesta = self.client.get(reverse('biblioteca:persona_detail', args=[self.carla.pk]))
        self.assertContains(respuesta, 'Dada de baja')
        self.assertContains(respuesta, 'Reactivar')
        self.assertNotContains(respuesta, 'Dar de baja</button>')


class InicioTests(PersonasTestCase):
    def test_el_panel_de_administracion_solo_se_ofrece_al_superusuario(self):
        respuesta = self.client.get(reverse('biblioteca:inicio'))
        self.assertNotContains(respuesta, 'href="' + reverse('admin:index') + '"')
        superusuario = get_user_model().objects.create_superuser(
            username='10000001', email='super@example.com', password=CLAVE
        )
        self.client.force_login(superusuario)
        respuesta = self.client.get(reverse('biblioteca:inicio'))
        self.assertContains(respuesta, 'href="' + reverse('admin:index') + '"')
