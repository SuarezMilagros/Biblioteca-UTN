"""Informes exportables en CSV (Release 1, decisión D5).

Cada listado exporta lo que se está viendo: misma búsqueda y mismo filtro, todas
las páginas. El archivo se abre bien en Excel en español (punto y coma, UTF-8 con
BOM, fechas dd/mm/aaaa) y no ejecuta fórmulas escritas en los datos.
"""
import csv
import io
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from biblioteca.informes import valor_seguro
from biblioteca.models import Autor, Categoria, Editorial, Ejemplar, Libro, Persona, Prestamo
from biblioteca.views import ELEMENTOS_POR_PAGINA
from cuentas.roles import ADMINISTRATIVO, BIBLIOTECARIO

CLAVE = 'clave-de-prueba-123'


class InformesTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.bibliotecario = Usuario.objects.create_user(
            username='31222333', email='bibliotecario@example.com', password=CLAVE,
            first_name='Bruno', last_name='Biblio',
        )
        cls.bibliotecario.groups.add(Group.objects.get(name=BIBLIOTECARIO))
        cls.administrativo = Usuario.objects.create_user(
            username='32333444', email='administrativo@example.com', password=CLAVE
        )
        cls.administrativo.groups.add(Group.objects.get(name=ADMINISTRATIVO))
        cls.sin_rol = Usuario.objects.create_user(username='30111222', email='sin.rol@example.com', password=CLAVE)

        cls.ana = Persona.objects.create(
            nombre='Ana', apellido='Pérez', documento='40111222', tipo=Persona.Tipo.ALUMNO, legajo='A-100'
        )
        cls.bruno = Persona.objects.create(
            nombre='Bruno', apellido='Gómez', documento='30222333', tipo=Persona.Tipo.PROFESOR
        )
        cls.carla = Persona.objects.create(
            nombre='Carla', apellido='Ruiz', documento='35444555', tipo=Persona.Tipo.ALUMNO, activo=False
        )
        cls.libro = Libro.objects.create(
            titulo='Cálculo I', isbn='978-987-1', categoria=Categoria.objects.create(nombre='Matemática'),
            autor=Autor.objects.create(nombre='Hugo', apellido='Ledesma'),
            editorial=Editorial.objects.create(nombre='Ediciones del Valle'),
        )
        cls.cal1 = Ejemplar.objects.create(codigo_inventario='CAL-001', id_inventario=101, libro=cls.libro)
        cls.cal2 = Ejemplar.objects.create(codigo_inventario='CAL-002', libro=cls.libro, observaciones='Tapa rota')
        cls.cal3 = Ejemplar.objects.create(codigo_inventario='CAL-003', libro=cls.libro)

        hoy = timezone.localdate()
        cls.vigente = Prestamo.objects.create(
            persona=cls.ana, ejemplar=cls.cal1, usuario_sistema=cls.bibliotecario,
            fecha_prestamo=hoy - timedelta(days=3), fecha_vencimiento=hoy + timedelta(days=11),
        )
        cls.vencido = Prestamo.objects.create(
            persona=cls.bruno, ejemplar=cls.cal2, usuario_sistema=cls.bibliotecario,
            fecha_prestamo=hoy - timedelta(days=20), fecha_vencimiento=hoy - timedelta(days=6),
        )
        cls.devuelto = Prestamo.objects.create(
            persona=cls.ana, ejemplar=cls.cal3, usuario_sistema=cls.bibliotecario,
            fecha_prestamo=hoy - timedelta(days=30), fecha_vencimiento=hoy - timedelta(days=16),
            fecha_devolucion=hoy - timedelta(days=18),
        )

    def setUp(self):
        self.client.force_login(self.bibliotecario)

    def exportar(self, nombre_url, **parametros):
        return self.client.get(reverse(nombre_url), {'formato': 'csv', **parametros})

    def filas(self, respuesta):
        """Lee el CSV como lo haría Excel: quita el BOM y separa por punto y coma."""
        texto = respuesta.content.decode('utf-8-sig')
        return list(csv.reader(io.StringIO(texto), delimiter=';'))

    def fecha(self, dias):
        return (timezone.localdate() + timedelta(days=dias)).strftime('%d/%m/%Y')


class FormatoDelArchivoTests(InformesTestCase):
    def test_se_descarga_como_csv_con_fecha_en_el_nombre(self):
        respuesta = self.exportar('biblioteca:prestamo_list', estado='vencidos')
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta['Content-Type'], 'text/csv; charset=utf-8')
        hoy = timezone.localdate().isoformat()
        self.assertEqual(
            respuesta['Content-Disposition'], f'attachment; filename="sigebi-prestamos-vencidos-{hoy}.csv"'
        )

    def test_utf8_con_bom_y_punto_y_coma_para_excel(self):
        respuesta = self.exportar('biblioteca:ejemplar_list')
        self.assertTrue(respuesta.content.startswith('﻿'.encode('utf-8')))
        encabezado = respuesta.content.decode('utf-8-sig').splitlines()[0]
        self.assertTrue(encabezado.startswith('Código de inventario;ID de inventario;Título;'))

    def test_una_formula_escrita_en_los_datos_no_se_ejecuta(self):
        Persona.objects.create(nombre='X', apellido='=HYPERLINK("http://malo")', documento='1', tipo=Persona.Tipo.ALUMNO)
        filas = self.filas(self.exportar('biblioteca:persona_list'))
        apellidos = [fila[0] for fila in filas[1:]]
        self.assertIn('\'=HYPERLINK("http://malo")', apellidos)
        self.assertNotIn('=HYPERLINK("http://malo")', apellidos)

    def test_valor_seguro(self):
        casos = {None: '', '+54 381': "'+54 381", '-1': "'-1", '@a': "'@a", 'CAL-001': 'CAL-001', 7: '7'}
        for valor, esperado in casos.items():
            with self.subTest(valor=valor):
                self.assertEqual(valor_seguro(valor), esperado)
        self.assertEqual(valor_seguro(timezone.localdate().replace(day=5, month=3, year=2026)), '05/03/2026')


class InformeDeEjemplaresTests(InformesTestCase):
    def test_columnas_y_disponibilidad(self):
        filas = self.filas(self.exportar('biblioteca:ejemplar_list'))
        self.assertEqual(filas[0], [
            'Código de inventario', 'ID de inventario', 'Título', 'Autor', 'Editorial',
            'Categoría', 'ISBN', 'Disponibilidad', 'Observaciones',
        ])
        self.assertEqual(filas[1:], [
            ['CAL-001', '101', 'Cálculo I', 'Ledesma, Hugo', 'Ediciones del Valle', 'Matemática', '978-987-1', 'Prestado', ''],
            ['CAL-002', '', 'Cálculo I', 'Ledesma, Hugo', 'Ediciones del Valle', 'Matemática', '978-987-1', 'Prestado', 'Tapa rota'],
            ['CAL-003', '', 'Cálculo I', 'Ledesma, Hugo', 'Ediciones del Valle', 'Matemática', '978-987-1', 'Disponible', ''],
        ])

    def test_exporta_todas_las_paginas(self):
        for numero in range(ELEMENTOS_POR_PAGINA + 5):
            Ejemplar.objects.create(codigo_inventario=f'EXT-{numero:03d}', libro=self.libro)
        filas = self.filas(self.exportar('biblioteca:ejemplar_list'))
        self.assertEqual(len(filas) - 1, Ejemplar.objects.count())


class InformeDePrestamosTests(InformesTestCase):
    def codigos(self, respuesta):
        return [fila[0] for fila in self.filas(respuesta)[1:]]

    def test_por_defecto_exporta_los_sin_devolver(self):
        self.assertEqual(self.codigos(self.exportar('biblioteca:prestamo_list')), ['CAL-002', 'CAL-001'])

    def test_vencidos_con_dias_de_atraso(self):
        filas = self.filas(self.exportar('biblioteca:prestamo_list', estado='vencidos'))
        self.assertEqual(filas[0], [
            'Código de inventario', 'Título', 'Apellido y nombre', 'Documento', 'Tipo',
            'Fecha de préstamo', 'Vencimiento', 'Devolución', 'Estado', 'Días de atraso', 'Registrado por',
        ])
        self.assertEqual(filas[1:], [[
            'CAL-002', 'Cálculo I', 'Gómez, Bruno', '30222333', 'Profesor',
            self.fecha(-20), self.fecha(-6), '', 'Vencido', '6', 'Bruno Biblio',
        ]])

    def test_devueltos(self):
        filas = self.filas(self.exportar('biblioteca:prestamo_list', estado='devueltos'))
        self.assertEqual([(f[0], f[7], f[8], f[9]) for f in filas[1:]], [('CAL-003', self.fecha(-18), 'Devuelto', '')])

    def test_respeta_la_busqueda(self):
        self.assertEqual(self.codigos(self.exportar('biblioteca:prestamo_list', estado='todos', q='perez')), ['CAL-001', 'CAL-003'])

    def test_exporta_todas_las_paginas(self):
        for numero in range(ELEMENTOS_POR_PAGINA + 5):
            ejemplar = Ejemplar.objects.create(codigo_inventario=f'VEN-{numero:03d}', libro=self.libro)
            Prestamo.objects.create(
                persona=self.ana, ejemplar=ejemplar, usuario_sistema=self.bibliotecario,
                fecha_prestamo=timezone.localdate() - timedelta(days=20),
                fecha_vencimiento=timezone.localdate() - timedelta(days=5),
            )
        self.assertEqual(len(self.codigos(self.exportar('biblioteca:prestamo_list', estado='vencidos'))), ELEMENTOS_POR_PAGINA + 6)


class InformeDePersonasTests(InformesTestCase):
    def test_columnas_y_prestamos_sin_devolver(self):
        filas = self.filas(self.exportar('biblioteca:persona_list'))
        self.assertEqual(filas[0], ['Apellido', 'Nombre', 'Documento', 'Tipo', 'Legajo', 'Estado', 'Préstamos sin devolver'])
        self.assertEqual(filas[1:], [
            ['Gómez', 'Bruno', '30222333', 'Profesor', '', 'Activa', '1'],
            ['Pérez', 'Ana', '40111222', 'Alumno', 'A-100', 'Activa', '1'],
        ])

    def test_respeta_el_estado_y_lo_pone_en_el_nombre(self):
        respuesta = self.exportar('biblioteca:persona_list', estado='baja')
        self.assertEqual([f[0] for f in self.filas(respuesta)[1:]], ['Ruiz'])
        self.assertIn('sigebi-personas-baja-', respuesta['Content-Disposition'])


class PermisosYPantallasTests(InformesTestCase):
    NOMBRES = ['biblioteca:ejemplar_list', 'biblioteca:prestamo_list', 'biblioteca:persona_list']

    def test_sin_sesion_pide_ingresar(self):
        self.client.logout()
        for nombre in self.NOMBRES:
            with self.subTest(nombre=nombre):
                respuesta = self.exportar(nombre)
                self.assertEqual(respuesta.status_code, 302)
                self.assertIn(reverse('login'), respuesta['Location'])

    def test_usuario_sin_rol_no_exporta(self):
        self.client.force_login(self.sin_rol)
        for nombre in self.NOMBRES:
            with self.subTest(nombre=nombre):
                self.assertEqual(self.exportar(nombre).status_code, 403)

    def test_bibliotecario_y_administrativo_exportan(self):
        for usuario in (self.bibliotecario, self.administrativo):
            self.client.force_login(usuario)
            for nombre in self.NOMBRES:
                with self.subTest(usuario=usuario.username, nombre=nombre):
                    self.assertEqual(self.exportar(nombre)['Content-Type'], 'text/csv; charset=utf-8')

    def test_el_boton_exporta_con_los_filtros_de_la_pantalla(self):
        respuesta = self.client.get(reverse('biblioteca:prestamo_list'), {'q': 'perez', 'estado': 'todos', 'page': '1'})
        self.assertContains(respuesta, 'href="?q=perez&amp;estado=todos&amp;formato=csv"')

    def test_sin_resultados_no_ofrece_exportar(self):
        respuesta = self.client.get(reverse('biblioteca:persona_list'), {'q': 'nadie'})
        self.assertNotContains(respuesta, 'Exportar CSV')

    def test_sin_formato_se_ve_la_pantalla_normal(self):
        respuesta = self.client.get(reverse('biblioteca:ejemplar_list'))
        self.assertEqual(respuesta['Content-Type'], 'text/html; charset=utf-8')
        self.assertContains(respuesta, 'Exportar CSV')
