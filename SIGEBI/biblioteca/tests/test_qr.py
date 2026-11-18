"""Código QR en cada ejemplar (Release 2, S8-05).

- La ficha del ejemplar muestra un QR con la dirección completa de esa ficha (generado en el servidor).
- Hoja de etiquetas para imprimir (código, título y QR) de un libro o de los ejemplares elegidos.
- Al escanear: el personal abre la ficha (pasando antes por el ingreso si no inició sesión);
  un lector recibe "Acceso no permitido".
"""
import re
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from biblioteca import qr
from biblioteca.models import Autor, Carrera, Categoria, Editorial, Ejemplar, Libro, Persona
from cuentas.lectores import crear_cuenta_de_lector
from cuentas.roles import BIBLIOTECARIO


def qr_esperado(direccion):
    return str(qr.svg(direccion))


class QRTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bibliotecario = get_user_model().objects.create_user(username='31222333', password='clave-de-prueba-123')
        cls.bibliotecario.groups.add(Group.objects.get(name=BIBLIOTECARIO))
        datos = {'autor': Autor.objects.create(nombre='A', apellido='B'), 'editorial': Editorial.objects.create(nombre='E'),
                 'categoria': Categoria.objects.create(nombre='Informática')}
        cls.python = Libro.objects.create(titulo='Python para principiantes', **datos)
        cls.java = Libro.objects.create(titulo='Java', **datos)
        cls.py2 = Ejemplar.objects.create(codigo_inventario='PY-2', libro=cls.python)
        cls.py1 = Ejemplar.objects.create(codigo_inventario='PY-1', libro=cls.python)
        cls.py_baja = Ejemplar.objects.create(codigo_inventario='PY-3', libro=cls.python, activo=False,
                                              motivo_baja='PERDIDO', fecha_baja=timezone.localdate())
        cls.jv1 = Ejemplar.objects.create(codigo_inventario='JV-1', libro=cls.java)
        persona = Persona.objects.create(nombre='Ana', apellido='Pérez', documento='40111222', tipo='ALUMNO')
        persona.carreras.add(Carrera.objects.get(nombre='Tecnicatura Universitaria en Programación'))
        cls.lector = crear_cuenta_de_lector(persona, 'ana.perez@alumnos.example.com')

    def setUp(self):
        self.client.force_login(self.bibliotecario)

    def etiquetas(self, consulta):
        return self.client.get(reverse('biblioteca:ejemplar_etiquetas') + consulta)

    def codigos(self, respuesta):
        return [ejemplar.codigo_inventario for ejemplar, _ in respuesta.context['etiquetas']]


class QRTests(QRTestCase):
    def test_la_direccion_es_la_ficha_completa(self):
        respuesta = self.client.get(reverse('biblioteca:ejemplar_detail', args=[self.py1.pk]))
        self.assertEqual(
            qr.direccion_de_la_ficha(respuesta.wsgi_request, self.py1), f'http://testserver/ejemplares/{self.py1.pk}/'
        )

    def test_la_ficha_muestra_el_qr_de_su_direccion(self):
        respuesta = self.client.get(reverse('biblioteca:ejemplar_detail', args=[self.py1.pk]))
        self.assertContains(respuesta, qr_esperado(f'http://testserver/ejemplares/{self.py1.pk}/'))
        self.assertNotContains(respuesta, qr_esperado(f'http://testserver/ejemplares/{self.py2.pk}/'))
        self.assertContains(respuesta, 'aria-label="Código QR de la ficha del ejemplar PY-1"')
        self.assertContains(respuesta, f'{reverse("biblioteca:ejemplar_etiquetas")}?ejemplar={self.py1.pk}')

    def test_el_qr_usa_el_dominio_con_el_que_se_entra(self):
        with override_settings(ALLOWED_HOSTS=['sigebi.example.com']):
            respuesta = self.client.get(reverse('biblioteca:ejemplar_detail', args=[self.py1.pk]),
                                        HTTP_HOST='sigebi.example.com', secure=True)
        self.assertContains(respuesta, qr_esperado(f'https://sigebi.example.com/ejemplares/{self.py1.pk}/'))

    def test_el_svg_es_un_qr_sin_tamano_fijo(self):
        dibujo = str(qr.svg('http://testserver/ejemplares/1/'))
        self.assertTrue(dibujo.startswith('<svg viewBox="0 0 '))
        self.assertIn('class="qr"', dibujo)
        self.assertNotIn('width=', dibujo.split('>')[0])

    def test_un_ejemplar_dado_de_baja_no_ofrece_imprimir_etiqueta(self):
        respuesta = self.client.get(reverse('biblioteca:ejemplar_detail', args=[self.py_baja.pk]))
        self.assertContains(respuesta, 'Código QR')
        self.assertNotContains(respuesta, 'Imprimir etiqueta')


class EtiquetasTests(QRTestCase):
    def test_de_un_libro_salen_sus_ejemplares_activos_en_orden(self):
        respuesta = self.etiquetas(f'?libro={self.python.pk}')
        self.assertEqual(self.codigos(respuesta), ['PY-1', 'PY-2'])
        self.assertContains(respuesta, 'Ejemplares de «Python para principiantes»')
        self.assertContains(respuesta, 'No se incluye 1 ejemplar dado de baja.')
        for ejemplar in (self.py1, self.py2):
            self.assertContains(respuesta, qr_esperado(f'http://testserver/ejemplares/{ejemplar.pk}/'))
        self.assertContains(respuesta, '<strong class="etiqueta-codigo">PY-1</strong>', html=True)
        self.assertContains(respuesta, 'Python para principiantes</span>')
        self.assertContains(respuesta, '2 etiquetas.')

    def test_de_los_ejemplares_elegidos(self):
        respuesta = self.etiquetas(f'?ejemplar={self.jv1.pk}&ejemplar={self.py2.pk}&ejemplar=abc&ejemplar=99999')
        self.assertEqual(self.codigos(respuesta), ['JV-1', 'PY-2'])
        self.assertNotContains(respuesta, qr_esperado(f'http://testserver/ejemplares/{self.py1.pk}/'))

    def test_un_dado_de_baja_elegido_no_se_imprime(self):
        respuesta = self.etiquetas(f'?ejemplar={self.py_baja.pk}')
        self.assertEqual(self.codigos(respuesta), [])
        self.assertContains(respuesta, 'No se incluye 1 ejemplar dado de baja.')
        self.assertContains(respuesta, 'No hay ejemplares activos elegidos.')

    def test_sin_elegir_nada(self):
        respuesta = self.etiquetas('')
        self.assertContains(respuesta, 'No hay ejemplares activos elegidos.')
        self.assertNotContains(respuesta, 'data-imprimir')

    def test_un_libro_que_no_existe_responde_404(self):
        self.assertEqual(self.etiquetas('?libro=99999').status_code, 404)

    def test_hay_un_maximo_por_hoja(self):
        with mock.patch('biblioteca.views.EjemplarEtiquetasView.MAXIMO', 1):
            respuesta = self.etiquetas(f'?libro={self.python.pk}')
        self.assertEqual(self.codigos(respuesta), ['PY-1'])
        self.assertContains(respuesta, 'Se muestran las primeras 1 etiquetas. Faltan 1')

    def test_avisa_si_se_entra_desde_la_misma_computadora(self):
        with override_settings(ALLOWED_HOSTS=['127.0.0.1', '192.168.0.10']):
            local = self.client.get(reverse('biblioteca:ejemplar_etiquetas') + f'?libro={self.python.pk}',
                                    HTTP_HOST='127.0.0.1:8000')
            red = self.client.get(reverse('biblioteca:ejemplar_etiquetas') + f'?libro={self.python.pk}',
                                  HTTP_HOST='192.168.0.10:8000')
        self.assertContains(local, 'un celular no puede abrir esa dirección')
        self.assertNotContains(red, 'un celular no puede abrir esa dirección')
        self.assertContains(red, qr_esperado(f'http://192.168.0.10:8000/ejemplares/{self.py1.pk}/'))

    def test_direcciones_locales(self):
        for host, local in (('localhost:8000', True), ('127.0.0.1', True), ('[::1]:8000', True),
                            ('192.168.0.10:8000', False), ('sigebi.example.com', False)):
            with self.subTest(host=host):
                pedido = mock.Mock(get_host=mock.Mock(return_value=host))
                self.assertEqual(qr.es_direccion_local(pedido), local)

    def test_la_hoja_no_choca_con_las_insignias_de_las_fichas(self):
        # `etiquetas` es la fila de insignias (Alumno, Activa…): la hoja de etiquetas usa otra clase.
        respuesta = self.etiquetas(f'?libro={self.python.pk}')
        self.assertContains(respuesta, '<div class="hoja-etiquetas">')
        estilos = (Path(settings.BASE_DIR) / 'static' / 'css' / 'estilos.css').read_text(encoding='utf-8')
        self.assertNotIn('.etiquetas { display: grid', estilos)
        self.assertIn('.etiquetas { display: flex', estilos)

    def test_el_boton_imprimir_y_los_estilos_de_impresion(self):
        respuesta = self.etiquetas(f'?libro={self.python.pk}')
        self.assertContains(respuesta, 'data-imprimir')
        estilos = (Path(settings.BASE_DIR) / 'static' / 'css' / 'estilos.css').read_text(encoding='utf-8')
        self.assertRegex(estilos, r'@media print \{[^@]*@page \{ size: A4')
        self.assertRegex(estilos, re.compile(r'@media print.*\.lateral, \.lateral-fondo, \.cabecera, \.pie, \.mensajes, \.no-imprimir \{ display: none', re.S))


class DondeSeEligenTests(QRTestCase):
    def test_la_lista_de_ejemplares_permite_elegir_los_activos(self):
        respuesta = self.client.get(reverse('biblioteca:ejemplar_list') + '?estado=todos')
        self.assertContains(respuesta, f'action="{reverse("biblioteca:ejemplar_etiquetas")}"')
        for ejemplar in (self.py1, self.py2, self.jv1):
            self.assertContains(respuesta, f'name="ejemplar" value="{ejemplar.pk}" form="form-etiquetas"')
        self.assertNotContains(respuesta, f'name="ejemplar" value="{self.py_baja.pk}"')
        self.assertContains(respuesta, 'Imprimir etiquetas de los elegidos')

    def test_la_ficha_del_libro_ofrece_sus_etiquetas(self):
        respuesta = self.client.get(reverse('biblioteca:libro_detail', args=[self.python.pk]))
        self.assertContains(respuesta, f'{reverse("biblioteca:ejemplar_etiquetas")}?libro={self.python.pk}')

    def test_la_dependencia_esta_en_requirements(self):
        requisitos = (Path(settings.BASE_DIR) / 'requirements.txt').read_text(encoding='ascii')
        self.assertIn('segno==', requisitos)


class AlEscanearTests(QRTestCase):
    def test_sin_sesion_pasa_por_el_ingreso_y_vuelve_a_la_ficha(self):
        self.client.logout()
        ficha = reverse('biblioteca:ejemplar_detail', args=[self.py1.pk])
        respuesta = self.client.get(ficha)
        self.assertRedirects(respuesta, f'{reverse("login")}?next={ficha}', fetch_redirect_response=False)

    def test_un_lector_recibe_acceso_no_permitido(self):
        self.client.force_login(self.lector)
        respuesta = self.client.get(reverse('biblioteca:ejemplar_detail', args=[self.py1.pk]))
        self.assertEqual(respuesta.status_code, 403)
        self.assertContains(respuesta, 'Acceso no permitido', status_code=403)
        self.assertContains(respuesta, 'Esta página es para el personal de la biblioteca.', status_code=403)

    def test_un_lector_tampoco_imprime_etiquetas(self):
        self.client.force_login(self.lector)
        self.assertEqual(self.etiquetas(f'?libro={self.python.pk}').status_code, 403)
