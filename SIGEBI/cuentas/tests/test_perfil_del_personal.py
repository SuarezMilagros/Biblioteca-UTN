"""Mi perfil del personal (revisión de UX/UI, 24/11/2026).

Bibliotecarios y administrativos tienen su página «Mi perfil», como alumnos y profesores en el portal:
sus datos, una foto opcional y el cambio de contraseña. Se llega desde la cabecera y desde el pie del menú.
La foto es privada: solo la ve su dueño, se achica y se graba como JPEG sin metadatos.
"""
import io
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from biblioteca.models import Persona
from cuentas.lectores import crear_cuenta_de_lector
from cuentas.models import PerfilDelPersonal
from cuentas.roles import ADMINISTRATIVO, BIBLIOTECARIO

CLAVE = 'clave-de-prueba-123'
URLS = ('cuentas:perfil', 'cuentas:perfil_foto', 'cuentas:perfil_foto_ver', 'cuentas:perfil_quitar_foto')


def imagen(formato='PNG', tamano=(1200, 800), nombre='foto.png'):
    salida = io.BytesIO()
    Image.new('RGB', tamano, (20, 80, 200)).save(salida, format=formato)
    return SimpleUploadedFile(nombre, salida.getvalue(), content_type=f'image/{formato.lower()}')


class PerfilDelPersonalTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.carpeta = tempfile.mkdtemp(prefix='fotos-personal-')
        cls.ajustes = override_settings(MATERIAL_DIGITAL_ROOT=cls.carpeta)
        cls.ajustes.enable()

    @classmethod
    def tearDownClass(cls):
        cls.ajustes.disable()
        shutil.rmtree(cls.carpeta, ignore_errors=True)
        super().tearDownClass()

    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.bibliotecario = Usuario.objects.create_user(
            username='31222333', email='bruno@example.com', password=CLAVE, first_name='Bruno', last_name='Biblio'
        )
        cls.bibliotecario.groups.add(Group.objects.get(name=BIBLIOTECARIO))
        cls.administrativo = Usuario.objects.create_user(
            username='32333444', email='adela@example.com', password=CLAVE, first_name='Adela', last_name='Admin'
        )
        cls.administrativo.groups.add(Group.objects.get(name=ADMINISTRATIVO))
        ana = Persona.objects.create(nombre='Ana', apellido='Pérez', documento='40111222', tipo='ALUMNO')
        cls.lector = crear_cuenta_de_lector(ana, 'ana@alumnos.example.com')

    def setUp(self):
        self.client.force_login(self.bibliotecario)

    def subir(self, archivo):
        return self.client.post(reverse('cuentas:perfil_foto'), {'foto': archivo}, follow=True)

    def perfil(self, usuario=None):
        return PerfilDelPersonal.objects.filter(usuario=usuario or self.bibliotecario).first()


class PaginaDelPerfilTests(PerfilDelPersonalTestCase):
    def test_muestra_sus_datos(self):
        respuesta = self.client.get(reverse('cuentas:perfil'))
        self.assertContains(respuesta, '<h1>Bruno Biblio</h1>', html=True)
        for dato in ('31222333', 'bruno@example.com', 'Bibliotecario'):
            self.assertContains(respuesta, f'<dd>{dato}</dd>', html=True)
        self.assertContains(respuesta, f'href="{reverse("password_change")}"')
        self.assertContains(respuesta, 'Subir una foto (opcional)')
        self.assertContains(respuesta, 'hasta 5 MB')

    def test_entrar_no_crea_nada(self):
        self.client.get(reverse('cuentas:perfil'))
        self.assertFalse(PerfilDelPersonal.objects.exists())

    def test_el_bibliotecario_pide_los_cambios_y_el_administrativo_los_hace(self):
        self.assertContains(self.client.get(reverse('cuentas:perfil')), 'pedíselo a un administrativo')
        self.client.force_login(self.administrativo)
        respuesta = self.client.get(reverse('cuentas:perfil'))
        self.assertContains(respuesta, f'href="{reverse("cuentas:usuario_update", args=[self.administrativo.pk])}"')
        self.assertContains(respuesta, '<dd>Administrativo</dd>', html=True)

    def test_se_llega_desde_la_cabecera_y_desde_el_menu(self):
        respuesta = self.client.get(reverse('biblioteca:inicio'))
        url = reverse('cuentas:perfil')
        self.assertContains(respuesta, f'<a class="perfil perfil-enlace" href="{url}" title="Mi perfil">')
        html = respuesta.content.decode()
        pie = html[html.index('<div class="lateral-pie">'):]
        self.assertIn(f'href="{url}"', pie[:pie.index('</div>')])
        self.assertIn('aria-current="page"', self.client.get(url).content.decode().split(f'<a class="nav-enlace" href="{url}"')[1][:30])

    def test_un_alumno_o_profesor_no_entra(self):
        self.client.force_login(self.lector)
        for nombre in URLS:
            with self.subTest(url=nombre):
                self.assertEqual(self.client.get(reverse(nombre)).status_code, 403)
                self.assertEqual(self.client.post(reverse(nombre)).status_code, 403)
        menu = self.client.get(reverse('portal:inicio'))
        self.assertNotContains(menu, reverse('cuentas:perfil'))

    def test_sin_sesion_pide_ingresar(self):
        self.client.logout()
        for nombre in URLS:
            with self.subTest(url=nombre):
                respuesta = self.client.get(reverse(nombre))
                self.assertEqual(respuesta.status_code, 302)
                self.assertTrue(respuesta['Location'].startswith(reverse('login')))


class FotoDelPersonalTests(PerfilDelPersonalTestCase):
    def test_sube_su_foto_y_se_achica_a_jpeg(self):
        respuesta = self.subir(imagen())
        self.assertContains(respuesta, 'Actualizaste tu foto de perfil.')
        perfil = self.perfil()
        self.assertTrue(perfil.foto.name.startswith('fotos/') and perfil.foto.name.endswith('.jpg'))
        with perfil.foto.open('rb') as archivo:
            guardada = Image.open(archivo)
            self.assertEqual((guardada.format, guardada.size), ('JPEG', (400, 267)))
            self.assertEqual(len(guardada.getexif()), 0)

    def test_se_ve_en_el_perfil_y_en_la_cabecera(self):
        self.subir(imagen())
        respuesta = self.client.get(reverse('cuentas:perfil'))
        self.assertContains(respuesta, f'src="{reverse("cuentas:perfil_foto_ver")}?v=', count=2)
        self.assertContains(respuesta, 'Cambiar la foto')
        self.assertContains(respuesta, 'Quitar la foto')
        self.assertNotIn('/media/', respuesta.content.decode())
        # En cualquier otra pantalla también se ve en la cabecera.
        self.assertContains(self.client.get(reverse('biblioteca:inicio')), f'src="{reverse("cuentas:perfil_foto_ver")}?v=', count=1)

    def test_sin_foto_se_ven_las_iniciales(self):
        respuesta = self.client.get(reverse('cuentas:perfil'))
        self.assertContains(respuesta, '<span class="avatar avatar-grande" aria-hidden="true">BB</span>', html=True)
        self.assertNotContains(respuesta, 'Quitar la foto')
        self.assertNotContains(respuesta, reverse('cuentas:perfil_foto_ver'))

    def test_solo_la_ve_su_duenio(self):
        self.subir(imagen())
        respuesta = self.client.get(reverse('cuentas:perfil_foto_ver'))
        self.assertEqual((respuesta.status_code, respuesta['Content-Type']), (200, 'image/jpeg'))
        self.assertEqual(respuesta['Cache-Control'], 'private, max-age=86400')
        # La dirección no tiene identificador: otra cuenta del personal recibe la suya (que no existe), nunca esta.
        self.client.force_login(self.administrativo)
        self.assertEqual(self.client.get(reverse('cuentas:perfil_foto_ver')).status_code, 404)

    def test_sin_foto_responde_404(self):
        self.assertEqual(self.client.get(reverse('cuentas:perfil_foto_ver')).status_code, 404)
        PerfilDelPersonal.objects.create(usuario=self.bibliotecario)
        self.assertEqual(self.client.get(reverse('cuentas:perfil_foto_ver')).status_code, 404)

    def test_reemplazarla_borra_la_anterior(self):
        self.subir(imagen())
        anterior = self.perfil().foto.name
        self.subir(imagen(formato='JPEG', nombre='otra.jpg'))
        perfil = self.perfil()
        self.assertNotEqual(perfil.foto.name, anterior)
        self.assertFalse(perfil.foto.storage.exists(anterior))
        self.assertEqual(PerfilDelPersonal.objects.count(), 1)

    def test_quitarla_la_borra_del_disco(self):
        self.subir(imagen())
        nombre = self.perfil().foto.name
        respuesta = self.client.post(reverse('cuentas:perfil_quitar_foto'), follow=True)
        self.assertContains(respuesta, 'Quitaste tu foto de perfil.')
        perfil = self.perfil()
        self.assertFalse(perfil.foto)
        self.assertFalse(perfil._meta.get_field('foto').storage.exists(nombre))

    def test_quitar_sin_foto_no_falla(self):
        respuesta = self.client.post(reverse('cuentas:perfil_quitar_foto'), follow=True)
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(PerfilDelPersonal.objects.exists())

    def test_rechaza_lo_que_no_es_una_foto(self):
        respuesta = self.subir(SimpleUploadedFile('foto.png', b'no es una imagen', content_type='image/png'))
        self.assertContains(respuesta, 'El archivo no es una imagen válida.')
        respuesta = self.subir(imagen(formato='GIF', nombre='foto.gif'))
        self.assertContains(respuesta, 'Subí una foto en JPG, PNG o WEBP.')
        self.assertFalse(PerfilDelPersonal.objects.exclude(foto='').exists())

    def test_sin_archivo_avisa(self):
        respuesta = self.client.post(reverse('cuentas:perfil_foto'), {}, follow=True)
        self.assertContains(respuesta, 'Este campo es obligatorio.')

    def test_cada_cuenta_tiene_su_foto(self):
        self.subir(imagen())
        self.client.force_login(self.administrativo)
        self.subir(imagen(formato='JPEG', nombre='otra.jpg'))
        self.assertEqual(PerfilDelPersonal.objects.exclude(foto='').count(), 2)
        self.assertNotEqual(self.perfil().foto.name, self.perfil(self.administrativo).foto.name)

    def test_solo_por_post(self):
        self.assertEqual(self.client.get(reverse('cuentas:perfil_foto')).status_code, 405)
        self.assertEqual(self.client.get(reverse('cuentas:perfil_quitar_foto')).status_code, 405)
