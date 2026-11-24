"""Pedidos de la profesora sobre Mi perfil y el ingreso (18/11/2026).

- Quien ya inició sesión y cae en la pantalla de ingreso (por ejemplo, con ?next= de un PDF) va directo a donde iba.
- Mi perfil se divide en páginas (Mis reservas, Material que compartí, Sin devolver, Historial), con enlaces en el menú.
- Foto de perfil opcional: la sube el propio lector; se achica, se graba como JPEG sin metadatos y es privada.
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

from biblioteca.models import Carrera, Persona
from cuentas.lectores import crear_cuenta_de_lector
from cuentas.roles import BIBLIOTECARIO

CLAVE = 'clave-de-prueba-123'


def imagen(formato='PNG', tamano=(1200, 800), nombre='foto.png', con_ubicacion=False):
    salida = io.BytesIO()
    datos = {}
    if con_ubicacion:
        exif = Image.Exif()
        exif[0x010F] = 'Telefono de prueba'  # Fabricante: un metadato que no tiene que quedar.
        datos['exif'] = exif
    Image.new('RGB', tamano, (200, 50, 20)).save(salida, format=formato, **datos)
    return SimpleUploadedFile(nombre, salida.getvalue(), content_type=f'image/{formato.lower()}')


class PerfilTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.carpeta = tempfile.mkdtemp(prefix='fotos-prueba-')
        cls.ajustes = override_settings(MATERIAL_DIGITAL_ROOT=cls.carpeta)
        cls.ajustes.enable()

    @classmethod
    def tearDownClass(cls):
        cls.ajustes.disable()
        shutil.rmtree(cls.carpeta, ignore_errors=True)
        super().tearDownClass()

    @classmethod
    def setUpTestData(cls):
        cls.bibliotecario = get_user_model().objects.create_user(username='31222333', email='biblio@example.com', password=CLAVE)
        cls.bibliotecario.groups.add(Group.objects.get(name=BIBLIOTECARIO))
        programacion = Carrera.objects.get(nombre='Tecnicatura Universitaria en Programación')
        cls.ana = Persona.objects.create(nombre='Ana', apellido='Pérez', documento='40111222', tipo='ALUMNO')
        cls.ana.carreras.add(programacion)
        cls.cuenta_ana = crear_cuenta_de_lector(cls.ana, 'ana@alumnos.example.com')
        cls.carlos = Persona.objects.create(nombre='Carlos', apellido='Ruiz', documento='40999888', tipo='ALUMNO')
        cls.carlos.carreras.add(programacion)
        cls.cuenta_carlos = crear_cuenta_de_lector(cls.carlos, 'carlos@alumnos.example.com')

    def setUp(self):
        self.client.force_login(self.cuenta_ana)

    def subir(self, archivo):
        return self.client.post(reverse('portal:foto'), {'foto': archivo}, follow=True)

    def recargar(self):
        self.ana.refresh_from_db()
        return self.ana


class IngresoConSesionTests(PerfilTestCase):
    def test_con_sesion_iniciada_va_directo_a_donde_iba(self):
        destino = reverse('portal:mis_reservas')
        respuesta = self.client.get(reverse('login') + f'?next={destino}')
        self.assertRedirects(respuesta, destino)

    def test_sin_destino_va_a_su_inicio(self):
        respuesta = self.client.get(reverse('login'), follow=True)
        self.assertEqual(respuesta.resolver_match.view_name, 'portal:inicio')

    def test_un_destino_de_otro_sitio_no_se_sigue(self):
        respuesta = self.client.get(reverse('login') + '?next=https://otro-sitio.example.com/')
        self.assertNotIn('otro-sitio', respuesta.get('Location', ''))

    def test_sin_sesion_sigue_mostrando_el_ingreso(self):
        self.client.logout()
        self.assertContains(self.client.get(reverse('login')), 'Ingresar')


class NavegacionDelPortalTests(PerfilTestCase):
    """Reorganización del portal (24/11/2026): Explorar, Mi biblioteca y, abajo, Mi perfil (la cuenta)."""

    PAGINAS = {
        'sin_devolver': ('Préstamos', 'sin_devolver'),
        'historial': ('Préstamos', 'sin_devolver'),
        'mis_reservas': ('Reservas', 'mis_reservas'),
        'material': ('Material digital', 'material'),
        'mi_material': ('Material digital', 'material'),
    }

    def menu(self, html):
        return html[html.index('<nav class="navegacion"'):html.index('</nav>', html.index('<nav class="navegacion"'))]

    def test_cada_pagina_marca_su_entrada_del_menu(self):
        for nombre, (titulo, entrada) in self.PAGINAS.items():
            with self.subTest(pagina=nombre):
                respuesta = self.client.get(reverse(f'portal:{nombre}'))
                self.assertContains(respuesta, f'<h1>{titulo}</h1>', html=True)
                self.assertIn(f'href="{reverse(f"portal:{entrada}")}" aria-current="page"', self.menu(respuesta.content.decode()))

    def test_grupos_del_menu_en_orden(self):
        menu = self.menu(self.client.get(reverse('portal:inicio')).content.decode())
        posiciones = [menu.index(texto) for texto in (
            f'href="{reverse("portal:inicio")}"', '>Explorar</p>', f'href="{reverse("portal:catalogo")}"',
            f'href="{reverse("portal:material")}"', '>Mi biblioteca</p>', f'href="{reverse("portal:sin_devolver")}"',
            f'href="{reverse("portal:mis_reservas")}"',
        )]
        self.assertEqual(posiciones, sorted(posiciones))
        self.assertNotIn(reverse('portal:perfil') + '"', menu)  # Mi perfil va abajo, con la cuenta
        self.assertNotIn(reverse('portal:historial'), menu)  # el historial es una pestaña de Préstamos
        self.assertNotIn(reverse('portal:mi_material'), menu)  # "Lo que compartí" es una pestaña de Material

    def test_mi_perfil_esta_abajo_con_la_cuenta_y_en_la_cabecera(self):
        html = self.client.get(reverse('portal:inicio')).content.decode()
        pie = html[html.index('<div class="lateral-pie">'):html.index('</aside>')]
        self.assertIn(f'href="{reverse("portal:perfil")}"', pie)
        self.assertLess(pie.index(reverse('portal:perfil')), pie.index(reverse('password_change')))
        self.assertIn(f'<a class="perfil perfil-enlace" href="{reverse("portal:perfil")}"', html)

    def test_el_perfil_es_solo_la_cuenta(self):
        respuesta = self.client.get(reverse('portal:perfil'))
        self.assertContains(respuesta, 'Mis datos')
        self.assertContains(respuesta, 'Foto de perfil')
        for otra in ('mis_reservas', 'sin_devolver', 'historial', 'mi_material'):
            self.assertNotContains(respuesta, f'class="cifra" href="{reverse(f"portal:{otra}")}"')

    def test_pestanas_de_prestamos_y_de_material(self):
        historial = self.client.get(reverse('portal:historial'))
        self.assertContains(historial, f'<a href="{reverse("portal:historial")}" aria-current="page" class="activa">Historial</a>', html=True)
        self.assertContains(historial, f'href="{reverse("portal:sin_devolver")}"')
        compartido = self.client.get(reverse('portal:mi_material'))
        self.assertContains(compartido, f'href="{reverse("portal:mi_material")}" aria-current="page" class="activa"')
        self.assertContains(self.client.get(reverse('portal:material')), 'De mis carreras')

    def test_las_direcciones_anteriores_redirigen(self):
        for vieja, nueva in (('/portal/perfil/reservas/', 'mis_reservas'), ('/portal/perfil/material/', 'mi_material'),
                             ('/portal/perfil/sin-devolver/', 'sin_devolver'), ('/portal/perfil/historial/', 'historial')):
            with self.subTest(vieja=vieja):
                self.assertRedirects(self.client.get(vieja), reverse(f'portal:{nueva}'), status_code=302)

    def test_el_personal_no_entra(self):
        self.client.force_login(self.bibliotecario)
        for nombre in ('sin_devolver', 'historial', 'mis_reservas', 'mi_material'):
            with self.subTest(pagina=nombre):
                self.assertEqual(self.client.get(reverse(f'portal:{nombre}')).status_code, 403)

    def test_el_menu_del_personal_no_cambia(self):
        self.client.force_login(self.bibliotecario)
        html = self.client.get(reverse('biblioteca:inicio')).content.decode()
        self.assertNotIn(reverse('portal:mis_reservas'), html)
        self.assertNotIn('>Mi biblioteca</p>', html)
        self.assertNotIn('perfil-enlace', html)


class FotoTests(PerfilTestCase):
    def test_sube_su_foto_y_se_achica_a_jpeg(self):
        respuesta = self.subir(imagen())
        self.assertContains(respuesta, 'Actualizaste tu foto de perfil.')
        ana = self.recargar()
        self.assertTrue(ana.foto.name.startswith('fotos/') and ana.foto.name.endswith('.jpg'))
        with ana.foto.open('rb') as archivo:
            guardada = Image.open(archivo)
            self.assertEqual(guardada.format, 'JPEG')
            self.assertLessEqual(max(guardada.size), 400)
            self.assertEqual(guardada.size, (400, 267))

    def test_se_descartan_los_metadatos_del_celular(self):
        self.subir(imagen(formato='JPEG', nombre='foto.jpg', con_ubicacion=True))
        with self.recargar().foto.open('rb') as archivo:
            self.assertEqual(len(Image.open(archivo).getexif()), 0)

    def test_se_ve_en_el_perfil_y_en_la_cabecera(self):
        self.subir(imagen())
        respuesta = self.client.get(reverse('portal:perfil'))
        self.assertContains(respuesta, f'src="{reverse("portal:mi_foto")}?v=', count=2)
        self.assertNotContains(respuesta, reverse('biblioteca:persona_foto', args=[self.ana.pk]))
        self.assertContains(respuesta, 'Quitar la foto')

    def test_sin_foto_se_ven_las_iniciales(self):
        respuesta = self.client.get(reverse('portal:perfil'))
        self.assertContains(respuesta, '<span class="avatar avatar-grande" aria-hidden="true">AP</span>', html=True)
        self.assertNotContains(respuesta, 'Quitar la foto')

    def test_rechaza_archivos_que_no_son_imagenes(self):
        archivo = SimpleUploadedFile('foto.png', b'esto no es una imagen', content_type='image/png')
        respuesta = self.subir(archivo)
        self.assertContains(respuesta, 'El archivo no es una imagen válida.')
        self.assertFalse(self.recargar().foto)

    def test_rechaza_otros_formatos(self):
        respuesta = self.subir(imagen(formato='GIF', nombre='foto.gif'))
        self.assertContains(respuesta, 'Subí una foto en JPG, PNG o WEBP.')
        self.assertFalse(self.recargar().foto)

    def test_rechaza_fotos_muy_pesadas(self):
        with override_settings(DATA_UPLOAD_MAX_MEMORY_SIZE=None):
            from biblioteca import fotos
            fotos_maximo = fotos.MAXIMO_MB
            fotos.MAXIMO_MB = 0
            try:
                respuesta = self.subir(imagen())
            finally:
                fotos.MAXIMO_MB = fotos_maximo
        self.assertContains(respuesta, 'La foto pesa más de 0 MB.')
        self.assertFalse(self.recargar().foto)

    def test_reemplazarla_borra_la_anterior(self):
        self.subir(imagen())
        anterior = self.recargar().foto.name
        self.subir(imagen(formato='JPEG', nombre='otra.jpg'))
        ana = self.recargar()
        self.assertNotEqual(ana.foto.name, anterior)
        self.assertFalse(ana.foto.storage.exists(anterior))

    def test_quitarla(self):
        self.subir(imagen())
        nombre = self.recargar().foto.name
        respuesta = self.client.post(reverse('portal:quitar_foto'), follow=True)
        self.assertContains(respuesta, 'Quitaste tu foto de perfil.')
        ana = self.recargar()
        self.assertFalse(ana.foto)
        self.assertFalse(ana._meta.get_field('foto').storage.exists(nombre))

    def test_la_foto_no_tiene_direccion_publica(self):
        self.subir(imagen())
        self.assertNotIn('/media/', self.client.get(reverse('portal:perfil')).content.decode())

    def test_la_ven_la_persona_y_el_personal_pero_no_otro_lector(self):
        self.subir(imagen())
        propia = self.client.get(reverse('portal:mi_foto'))
        self.assertEqual((propia.status_code, propia['Content-Type']), (200, 'image/jpeg'))
        url = reverse('biblioteca:persona_foto', args=[self.ana.pk])
        self.assertEqual(self.client.get(url).status_code, 403)  # la dirección del personal, ni siquiera la suya
        self.client.force_login(self.bibliotecario)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertContains(self.client.get(reverse('biblioteca:persona_detail', args=[self.ana.pk])), f'src="{url}?v=')
        self.client.force_login(self.cuenta_carlos)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.get(reverse('portal:mi_foto')).status_code, 404)  # Carlos no tiene foto
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)
        self.assertEqual(self.client.get(reverse('portal:mi_foto')).status_code, 302)

    def test_sin_foto_responde_404(self):
        self.assertEqual(self.client.get(reverse('portal:mi_foto')).status_code, 404)

    def test_solo_por_post(self):
        self.assertEqual(self.client.get(reverse('portal:foto')).status_code, 405)
        self.assertEqual(self.client.get(reverse('portal:quitar_foto')).status_code, 405)

    def test_el_personal_no_sube_fotos_desde_el_portal(self):
        self.client.force_login(self.bibliotecario)
        self.assertEqual(self.client.post(reverse('portal:foto'), {'foto': imagen()}).status_code, 403)
