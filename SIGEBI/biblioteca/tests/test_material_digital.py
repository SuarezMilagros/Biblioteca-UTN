"""Material digital (Release 2, S7-07).

- El personal sube PDF (hasta 20 MB, PDF de verdad) a una carrera; queda publicado.
- Los archivos se guardan fuera de la carpeta pública y no tienen dirección pública.
- El lector ve y abre solo el material aprobado y activo de sus carreras; lo demás responde 404.
- Baja lógica y reactivación.
"""
import os
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from biblioteca.models import Carrera, MaterialDigital, Persona
from cuentas.lectores import crear_cuenta_de_lector
from cuentas.roles import BIBLIOTECARIO

CLAVE = 'clave-de-prueba-123'
PDF = b'%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\ntrailer << /Root 1 0 R >>\n%%EOF\n'


def pdf(nombre='apunte.pdf', contenido=PDF):
    return SimpleUploadedFile(nombre, contenido, content_type='application/pdf')


class MaterialTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.carpeta = tempfile.mkdtemp(prefix='material-prueba-')
        cls.ajustes = override_settings(MATERIAL_DIGITAL_ROOT=cls.carpeta)
        cls.ajustes.enable()

    @classmethod
    def tearDownClass(cls):
        cls.ajustes.disable()
        shutil.rmtree(cls.carpeta, ignore_errors=True)
        super().tearDownClass()

    @classmethod
    def setUpTestData(cls):
        cls.bibliotecario = get_user_model().objects.create_user(
            username='31222333', email='bibliotecario@example.com', password=CLAVE
        )
        cls.bibliotecario.groups.add(Group.objects.get(name=BIBLIOTECARIO))
        cls.programacion = Carrera.objects.get(nombre='Tecnicatura Universitaria en Programación')
        cls.mecanica = Carrera.objects.get(nombre='Ingeniería Mecánica')
        cls.persona = Persona.objects.create(nombre='Ana', apellido='Pérez', documento='40111222', tipo='ALUMNO')
        cls.persona.carreras.add(cls.programacion)
        cls.lector = crear_cuenta_de_lector(cls.persona, 'ana.perez@alumnos.example.com')

    def setUp(self):
        self.client.force_login(self.bibliotecario)

    def subir(self, **cambios):
        datos = {
            'titulo': 'Apunte de Python', 'tipo': 'APUNTE', 'carrera': self.programacion.pk,
            'autores': 'Gómez, Luis', 'anio': '2025', 'descripcion': 'Primer parcial', 'archivo': pdf(),
        }
        datos.update(cambios)
        return self.client.post(reverse('biblioteca:material_create'), datos)

    def material(self, carrera=None, **cambios):
        datos = dict(
            titulo='Material', tipo='LIBRO', carrera=carrera or self.programacion, archivo=pdf(),
            estado=MaterialDigital.Estado.APROBADO, usuario_carga=self.bibliotecario,
            usuario_revision=self.bibliotecario, fecha_revision=timezone.now(),
        )
        datos.update(cambios)
        return MaterialDigital.objects.create(**datos)


class CargaDelPersonalTests(MaterialTestCase):
    def test_sube_un_pdf_y_queda_publicado(self):
        respuesta = self.subir()
        self.assertRedirects(respuesta, reverse('biblioteca:material_list'))
        material = MaterialDigital.objects.get()
        self.assertEqual(material.estado, MaterialDigital.Estado.APROBADO)
        self.assertEqual((material.usuario_carga, material.usuario_revision), (self.bibliotecario, self.bibliotecario))
        self.assertEqual((material.autores, material.anio), ('Gómez, Luis', 2025))

    def test_el_archivo_queda_fuera_de_la_carpeta_publica(self):
        self.subir()
        material = MaterialDigital.objects.get()
        ruta = material.archivo.path
        self.assertTrue(ruta.startswith(self.carpeta))
        self.assertTrue(os.path.exists(ruta))
        self.assertNotIn('apunte', os.path.basename(ruta))  # nombre al azar, no el original
        with self.assertRaises(ValueError):
            material.archivo.url

    def test_rechaza_un_archivo_que_no_es_pdf(self):
        respuesta = self.subir(archivo=pdf('virus.pdf', b'MZ\x90\x00 esto es un ejecutable'))
        self.assertContains(respuesta, 'El archivo no es un PDF válido.')
        self.assertFalse(MaterialDigital.objects.exists())

    def test_rechaza_otra_extension(self):
        respuesta = self.subir(archivo=pdf('apunte.docx'))
        self.assertContains(respuesta, 'Solo se aceptan archivos PDF.')

    @override_settings(MATERIAL_DIGITAL_MAXIMO_MB=1)
    def test_rechaza_un_archivo_demasiado_grande(self):
        grande = PDF + b'0' * (1024 * 1024)
        respuesta = self.subir(archivo=pdf(contenido=grande))
        self.assertContains(respuesta, 'El archivo pesa más de 1 MB.')
        self.assertFalse(MaterialDigital.objects.exists())

    def test_el_anio_no_puede_ser_futuro(self):
        respuesta = self.subir(anio=str(timezone.localdate().year + 1))
        self.assertContains(respuesta, 'Poné un año entre 1900 y')

    def test_editar_sin_cambiar_el_archivo(self):
        material = self.material()
        archivo_anterior = material.archivo.name
        respuesta = self.client.post(reverse('biblioteca:material_update', args=[material.pk]), {
            'titulo': 'Nuevo título', 'tipo': 'TESIS', 'carrera': self.programacion.pk,
            'autores': '', 'anio': '', 'descripcion': '',
        })
        self.assertRedirects(respuesta, reverse('biblioteca:material_list'))
        material.refresh_from_db()
        self.assertEqual((material.titulo, material.archivo.name), ('Nuevo título', archivo_anterior))

    def test_la_base_exige_coherencia_entre_estado_y_revision(self):
        casos = {
            'aprobado sin revisión': dict(usuario_revision=None, fecha_revision=None),
            'rechazado sin motivo': dict(estado=MaterialDigital.Estado.RECHAZADO),
            'pendiente con revisión': dict(estado=MaterialDigital.Estado.PENDIENTE),
            'año inválido': dict(anio=1500),
        }
        for caso, cambios in casos.items():
            with self.subTest(caso=caso), self.assertRaises(IntegrityError), transaction.atomic():
                self.material(**cambios)

    def test_baja_y_reactivacion(self):
        material = self.material()
        self.client.post(reverse('biblioteca:material_baja', args=[material.pk]))
        material.refresh_from_db()
        self.assertFalse(material.activo)
        self.client.post(reverse('biblioteca:material_reactivar', args=[material.pk]))
        material.refresh_from_db()
        self.assertTrue(material.activo)

    def test_el_personal_abre_el_pdf_aunque_este_dado_de_baja(self):
        material = self.material(titulo='Guía de Redes', activo=False)
        respuesta = self.client.get(reverse('biblioteca:material_archivo', args=[material.pk]))
        self.assertEqual(respuesta['Content-Type'], 'application/pdf')
        self.assertIn('guia-de-redes.pdf', respuesta['Content-Disposition'])
        self.assertEqual(b''.join(respuesta.streaming_content), PDF)

    def test_filtros_del_listado(self):
        self.material(titulo='Cálculo', tipo='LIBRO')
        self.material(titulo='Tornería', tipo='APUNTE', carrera=self.mecanica)
        self.material(titulo='Viejo', activo=False)
        listado = lambda **p: [m.titulo for m in self.client.get(reverse('biblioteca:material_list'), p).context['materiales']]
        self.assertEqual(sorted(listado()), ['Cálculo', 'Tornería'])
        self.assertEqual(listado(q='calculo'), ['Cálculo'])
        self.assertEqual(listado(carrera=self.mecanica.pk), ['Tornería'])
        self.assertEqual(listado(tipo='APUNTE'), ['Tornería'])
        self.assertEqual(listado(estado='baja'), ['Viejo'])


class PortalTests(MaterialTestCase):
    def setUp(self):
        self.client.force_login(self.lector)

    def titulos(self, **parametros):
        respuesta = self.client.get(reverse('portal:material'), parametros)
        return [material.titulo for material in respuesta.context['materiales']]

    def test_ve_solo_el_material_aprobado_y_activo_de_sus_carreras(self):
        self.material(titulo='Suyo')
        self.material(titulo='De otra carrera', carrera=self.mecanica)
        self.material(titulo='Dado de baja', activo=False)
        self.material(titulo='Pendiente', estado=MaterialDigital.Estado.PENDIENTE,
                      usuario_revision=None, fecha_revision=None)
        self.assertEqual(self.titulos(), ['Suyo'])

    def test_abre_el_pdf_de_su_carrera(self):
        material = self.material(titulo='Apunte')
        respuesta = self.client.get(reverse('portal:material_archivo', args=[material.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta['Content-Type'], 'application/pdf')

    def test_no_abre_lo_que_no_puede_ver_aunque_escriba_la_direccion(self):
        casos = {
            'otra carrera': self.material(carrera=self.mecanica),
            'dado de baja': self.material(activo=False),
            'pendiente': self.material(estado=MaterialDigital.Estado.PENDIENTE, usuario_revision=None, fecha_revision=None),
        }
        for caso, material in casos.items():
            with self.subTest(caso=caso):
                respuesta = self.client.get(reverse('portal:material_archivo', args=[material.pk]))
                self.assertEqual(respuesta.status_code, 404)

    def test_sin_sesion_no_se_descarga(self):
        material = self.material()
        self.client.logout()
        respuesta = self.client.get(reverse('portal:material_archivo', args=[material.pk]))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse('login'), respuesta['Location'])

    def test_el_lector_no_entra_a_las_pantallas_del_personal(self):
        material = self.material()
        for url in (reverse('biblioteca:material_list'), reverse('biblioteca:material_create'),
                    reverse('biblioteca:material_archivo', args=[material.pk])):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_busqueda_y_filtro_por_tipo(self):
        self.material(titulo='Programación en C', tipo='LIBRO', autores='Kernighan')
        self.material(titulo='Parcial resuelto', tipo='APUNTE')
        self.assertEqual(self.titulos(q='kernighan'), ['Programación en C'])
        self.assertEqual(self.titulos(tipo='APUNTE'), ['Parcial resuelto'])

    def test_el_menu_tiene_material_digital_marcado(self):
        respuesta = self.client.get(reverse('portal:material'))
        self.assertContains(respuesta, f'href="{reverse("portal:material")}" aria-current="page"')

    def test_sin_material(self):
        self.assertContains(self.client.get(reverse('portal:material')), 'Todavía no hay material para tus carreras')
