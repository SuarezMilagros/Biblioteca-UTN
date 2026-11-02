"""Alta, edición y permisos de cuentas del sistema (Release 1, etapa 5).

Las pruebas llaman a las URLs directamente, no solo a los enlaces del menú.
"""
import io
from re import search

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from cuentas.roles import ADMINISTRATIVO, BIBLIOTECARIO

CLAVE = 'clave-de-prueba-123'
CLAVE_NUEVA = 'clave-nueva-456-segura'


def enlace_del_ultimo_correo():
    return search(r'http://testserver(\S+)', mail.outbox[-1].body).group(1)


class CuentasTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.superusuario = Usuario.objects.create_superuser(
            username='10000001', email='superusuario@example.com', password=CLAVE
        )
        cls.administrativo = Usuario.objects.create_user(
            username='32333444', email='administrativo@example.com', password=CLAVE,
            first_name='Ana', last_name='Administrativa',
        )
        cls.administrativo.groups.add(Group.objects.get(name=ADMINISTRATIVO))
        cls.otro_administrativo = Usuario.objects.create_user(
            username='32333555', email='otro.administrativo@example.com', password=CLAVE,
            first_name='Otro', last_name='Administrativo',
        )
        cls.otro_administrativo.groups.add(Group.objects.get(name=ADMINISTRATIVO))
        cls.bibliotecario = Usuario.objects.create_user(
            username='31222333', email='bibliotecario@example.com', password=CLAVE,
            first_name='Bruno', last_name='Biblio',
        )
        cls.bibliotecario.groups.add(Group.objects.get(name=BIBLIOTECARIO))

    def datos(self, **cambios):
        datos = {
            'username': '40111222',
            'first_name': 'Lucía',
            'last_name': 'Paz',
            'email': 'lucia.paz@example.com',
            'rol': BIBLIOTECARIO,
            'is_active': 'on',
        }
        datos.update(cambios)
        return datos

    def cantidad_de_cuentas(self):
        return get_user_model().objects.count()


class ListadoYPermisosTests(CuentasTestCase):
    def test_sin_sesion_pide_ingresar(self):
        respuesta = self.client.get(reverse('cuentas:usuario_list'))
        self.assertEqual(respuesta.status_code, 302)

    def test_bibliotecario_no_gestiona_cuentas(self):
        self.client.force_login(self.bibliotecario)
        self.assertEqual(self.client.get(reverse('cuentas:usuario_list')).status_code, 403)
        self.assertEqual(self.client.get(reverse('cuentas:usuario_create')).status_code, 403)
        antes = self.cantidad_de_cuentas()
        respuesta = self.client.post(reverse('cuentas:usuario_create'), self.datos())
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(self.cantidad_de_cuentas(), antes)

    def test_administrativo_y_superusuario_ven_el_listado(self):
        for usuario in (self.administrativo, self.superusuario):
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)
                self.assertEqual(self.client.get(reverse('cuentas:usuario_list')).status_code, 200)

    def test_administrativo_no_abre_ni_edita_administrativos_ni_superusuarios(self):
        self.client.force_login(self.administrativo)
        for objetivo in (self.otro_administrativo, self.superusuario):
            url = reverse('cuentas:usuario_update', args=[objetivo.pk])
            with self.subTest(objetivo=objetivo.username):
                self.assertEqual(self.client.get(url).status_code, 403)
                nombre_antes = (objetivo.first_name, objetivo.last_name)
                datos = self.datos(username=objetivo.username, email=objetivo.email, rol=ADMINISTRATIVO)
                self.assertEqual(self.client.post(url, datos).status_code, 403)
                objetivo.refresh_from_db()
                self.assertEqual((objetivo.first_name, objetivo.last_name), nombre_antes)


class AltaDeCuentasTests(CuentasTestCase):
    def test_administrativo_da_de_alta_un_bibliotecario_sin_contrasena(self):
        self.client.force_login(self.administrativo)
        respuesta = self.client.post(reverse('cuentas:usuario_create'), self.datos())
        self.assertRedirects(respuesta, reverse('cuentas:usuario_list'))
        usuario = get_user_model().objects.get(username='40111222')
        self.assertFalse(usuario.has_usable_password())
        self.assertTrue(usuario.is_active)
        self.assertEqual(usuario.email, 'lucia.paz@example.com')
        self.assertEqual((usuario.first_name, usuario.last_name), ('Lucía', 'Paz'))
        self.assertEqual(list(usuario.groups.values_list('name', flat=True)), [BIBLIOTECARIO])

    def test_el_alta_envia_el_correo_de_definicion(self):
        self.client.force_login(self.administrativo)
        self.client.post(reverse('cuentas:usuario_create'), self.datos())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['lucia.paz@example.com'])
        self.assertIn('SIGEBI', mail.outbox[0].subject)
        self.assertIn('/accounts/reset/', mail.outbox[0].body)

    def test_el_enlace_de_definicion_permite_elegir_la_contrasena(self):
        self.client.force_login(self.administrativo)
        self.client.post(reverse('cuentas:usuario_create'), self.datos())
        self.client.logout()

        respuesta = self.client.get(enlace_del_ultimo_correo(), follow=True)
        self.assertTrue(respuesta.context['validlink'])
        url_de_clave = respuesta.redirect_chain[-1][0]
        respuesta = self.client.post(
            url_de_clave, {'new_password1': CLAVE_NUEVA, 'new_password2': CLAVE_NUEVA}
        )
        self.assertRedirects(respuesta, reverse('password_reset_complete'))
        self.assertIsNotNone(authenticate(username='lucia.paz@example.com', password=CLAVE_NUEVA))

    def test_datos_obligatorios(self):
        self.client.force_login(self.administrativo)
        antes = self.cantidad_de_cuentas()
        respuesta = self.client.post(reverse('cuentas:usuario_create'), {})
        self.assertEqual(respuesta.status_code, 200)
        errores = respuesta.context['form'].errors
        for campo in ('username', 'first_name', 'last_name', 'email', 'rol'):
            with self.subTest(campo=campo):
                self.assertIn(campo, errores)
        self.assertEqual(self.cantidad_de_cuentas(), antes)

    def test_documento_repetido_se_rechaza(self):
        self.client.force_login(self.administrativo)
        antes = self.cantidad_de_cuentas()
        respuesta = self.client.post(
            reverse('cuentas:usuario_create'), self.datos(username=self.bibliotecario.username)
        )
        self.assertEqual(
            respuesta.context['form'].errors['username'], ['Ya existe una cuenta con ese documento.']
        )
        self.assertEqual(self.cantidad_de_cuentas(), antes)

    def test_correo_repetido_se_rechaza_sin_distinguir_mayusculas(self):
        self.client.force_login(self.administrativo)
        antes = self.cantidad_de_cuentas()
        respuesta = self.client.post(
            reverse('cuentas:usuario_create'), self.datos(email=self.bibliotecario.email.upper())
        )
        self.assertEqual(respuesta.context['form'].errors['email'], ['Ya existe una cuenta con ese correo.'])
        self.assertEqual(self.cantidad_de_cuentas(), antes)

    def test_administrativo_solo_asigna_bibliotecario(self):
        self.client.force_login(self.administrativo)
        antes = self.cantidad_de_cuentas()
        respuesta = self.client.post(reverse('cuentas:usuario_create'), self.datos(rol=ADMINISTRATIVO))
        self.assertIn('rol', respuesta.context['form'].errors)
        self.assertEqual(self.cantidad_de_cuentas(), antes)

    def test_superusuario_puede_crear_un_administrativo(self):
        self.client.force_login(self.superusuario)
        self.client.post(reverse('cuentas:usuario_create'), self.datos(rol=ADMINISTRATIVO))
        usuario = get_user_model().objects.get(username='40111222')
        self.assertEqual(list(usuario.groups.values_list('name', flat=True)), [ADMINISTRATIVO])


class EdicionDeCuentasTests(CuentasTestCase):
    def test_administrativo_edita_un_bibliotecario_y_lo_desactiva(self):
        self.client.force_login(self.administrativo)
        pagina = self.client.get(reverse('cuentas:usuario_update', args=[self.bibliotecario.pk]))
        # En la plantilla, `user` tiene que ser quien está conectado, no la cuenta que se edita.
        self.assertEqual(pagina.context['user'].pk, self.administrativo.pk)
        datos = self.datos(
            username=self.bibliotecario.username,
            email=self.bibliotecario.email,
            first_name='Bruno',
            last_name='Editado',
        )
        datos.pop('is_active')  # sin la casilla marcada, la cuenta queda desactivada
        respuesta = self.client.post(reverse('cuentas:usuario_update', args=[self.bibliotecario.pk]), datos)
        self.assertRedirects(respuesta, reverse('cuentas:usuario_list'))
        self.bibliotecario.refresh_from_db()
        self.assertEqual(self.bibliotecario.last_name, 'Editado')
        self.assertFalse(self.bibliotecario.is_active)
        self.assertIsNone(authenticate(username=self.bibliotecario.email, password=CLAVE))

    def test_nadie_cambia_su_propio_rol_ni_se_desactiva(self):
        self.client.force_login(self.administrativo)
        datos = self.datos(
            username=self.administrativo.username,
            email=self.administrativo.email,
            first_name='Ana',
            last_name='Nueva',
            rol=BIBLIOTECARIO,
        )
        datos.pop('is_active')
        respuesta = self.client.post(reverse('cuentas:usuario_update', args=[self.administrativo.pk]), datos)
        self.assertRedirects(respuesta, reverse('cuentas:usuario_list'))
        self.administrativo.refresh_from_db()
        self.assertEqual(self.administrativo.last_name, 'Nueva')  # los datos sí se editan
        self.assertTrue(self.administrativo.is_active)
        self.assertEqual(list(self.administrativo.groups.values_list('name', flat=True)), [ADMINISTRATIVO])


class ReenvioDeDefinicionTests(CuentasTestCase):
    def test_reenvia_el_correo_a_una_cuenta_sin_contrasena(self):
        self.client.force_login(self.administrativo)
        self.client.post(reverse('cuentas:usuario_create'), self.datos())
        usuario = get_user_model().objects.get(username='40111222')
        respuesta = self.client.post(
            reverse('cuentas:usuario_reenviar_definicion', args=[usuario.pk]), follow=True
        )
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[1].to, ['lucia.paz@example.com'])
        self.assertContains(respuesta, 'Correo de definición reenviado.')

    def test_no_reenvia_a_una_cuenta_con_contrasena(self):
        self.client.force_login(self.administrativo)
        respuesta = self.client.post(
            reverse('cuentas:usuario_reenviar_definicion', args=[self.bibliotecario.pk]), follow=True
        )
        self.assertEqual(len(mail.outbox), 0)
        self.assertContains(respuesta, 'ya tiene contraseña')

    def test_el_reenvio_solo_acepta_post(self):
        self.client.force_login(self.administrativo)
        url = reverse('cuentas:usuario_reenviar_definicion', args=[self.bibliotecario.pk])
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_bibliotecario_no_reenvia(self):
        self.client.force_login(self.bibliotecario)
        url = reverse('cuentas:usuario_reenviar_definicion', args=[self.administrativo.pk])
        self.assertEqual(self.client.post(url).status_code, 403)
        self.assertEqual(len(mail.outbox), 0)


class PermisosDeCuentasTests(CuentasTestCase):
    def test_administrativo_tiene_permisos_sobre_cuentas_de_bibliotecarios(self):
        permisos = set(Group.objects.get(name=ADMINISTRATIVO).permissions.values_list(
            'content_type__app_label', 'codename'
        ))
        for codename in ('view_user', 'add_user', 'change_user'):
            with self.subTest(codename=codename):
                self.assertIn(('auth', codename), permisos)
        self.assertNotIn(('auth', 'delete_user'), permisos)


class CorreoUnicoEnLaBaseTests(TestCase):
    def test_la_base_no_acepta_dos_correos_iguales_sin_distinguir_mayusculas(self):
        Usuario = get_user_model()
        Usuario.objects.create(username='50000001', email='mismo@example.com')
        with self.assertRaises(IntegrityError), transaction.atomic():
            Usuario.objects.create(username='50000002', email='MISMO@example.com')

    def test_varias_cuentas_sin_correo_son_posibles(self):
        Usuario = get_user_model()
        Usuario.objects.create(username='50000003', email='')
        Usuario.objects.create(username='50000004', email='')
        self.assertEqual(Usuario.objects.filter(email='').count(), 2)


class SeedDeCuentasTests(TestCase):
    def test_repetir_el_seed_no_cambia_la_clave_y_completa_la_cuenta(self):
        call_command('cargar_datos_prueba', stdout=io.StringIO())
        usuario = get_user_model().objects.get(username='bibliotecario_prueba')
        usuario.set_password(CLAVE)
        usuario.email = ''
        usuario.save()
        usuario.groups.clear()

        call_command('cargar_datos_prueba', stdout=io.StringIO())

        usuario.refresh_from_db()
        self.assertTrue(usuario.check_password(CLAVE))
        self.assertEqual(usuario.email, 'bibliotecario.prueba@example.com')
        self.assertEqual(list(usuario.groups.values_list('name', flat=True)), [BIBLIOTECARIO])
