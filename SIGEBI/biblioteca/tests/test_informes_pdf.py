"""Informes en PDF (pedido del equipo, 24/11/2026).

Cada listado que se exporta en CSV también se exporta en PDF, con las mismas columnas y filas (misma búsqueda,
mismos filtros, todas las páginas). El PDF tiene título, qué incluye, fecha de generación, encabezado repetido
en cada hoja y número de página. En Informes, cada descarga ofrece CSV y PDF juntos.
"""
import random
import re
import string
import zlib
from datetime import timedelta

from django.contrib.auth.models import Permission
from django.test import SimpleTestCase
from django.urls import reverse
from django.utils import timezone

from biblioteca.informes import InformePDF, anchos_de_columnas, respuesta_pdf, texto_pdf
from biblioteca.models import Ejemplar, Persona

from .test_informes import InformesTestCase

A4_HORIZONTAL = '/MediaBox [0 0 841.89 595.28]'
A4_VERTICAL = '/MediaBox [0 0 595.28 841.89]'


def texto_del_pdf(contenido):
    """El texto que dibuja el PDF (fpdf2 comprime cada hoja con zlib; las fuentes estándar usan Latin-1).

    Cada flujo se lee con la cantidad exacta de bytes que declara su `/Length`. Antes se buscaba hasta
    "endstream" y, si los datos comprimidos terminaban en el byte "\\r" (pasa en ~0,5 % de los PDF, según la hora
    de generación), ese byte se perdía y el texto no aparecía: el test fallaba aunque el PDF estuviera bien.
    """
    partes = [contenido.decode('latin-1')]
    for encabezado in re.finditer(rb'<<(?:(?!>>).)*?/Length (\d+)(?:(?!>>).)*>>\s*stream\r?\n', contenido, re.S):
        inicio = encabezado.end()
        flujo = contenido[inicio:inicio + int(encabezado.group(1))]
        if b'/FlateDecode' in encabezado.group(0):
            try:
                flujo = zlib.decompress(flujo)
            except zlib.error as error:  # nunca en silencio: un flujo ilegible tiene que hacer fallar la prueba
                raise AssertionError(f'Flujo comprimido ilegible en el byte {inicio}: {error}') from error
        partes.append(flujo.decode('latin-1'))
    # Un mismo renglón puede escribirse en partes, por ejemplo "(Página 1 de ) Tj (3) Tj".
    return re.sub(r'\) Tj \(', '', '\n'.join(partes))


class InformesPDFTestCase(InformesTestCase):
    def pdf(self, nombre_url, **parametros):
        return self.client.get(reverse(nombre_url), {'formato': 'pdf', **parametros})

    def texto(self, respuesta):
        return texto_del_pdf(respuesta.content)


class FormatoDelPDFTests(InformesPDFTestCase):
    def test_se_descarga_como_pdf_con_el_mismo_nombre_que_el_csv(self):
        hoy = timezone.localdate().isoformat()
        respuesta = self.pdf('biblioteca:prestamo_list', estado='vencidos')
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta['Content-Type'], 'application/pdf')
        self.assertEqual(
            respuesta['Content-Disposition'], f'attachment; filename="sigebi-prestamos-vencidos-{hoy}.pdf"'
        )
        self.assertTrue(respuesta.content.startswith(b'%PDF-'))

    def test_titulo_lo_que_incluye_y_fecha_de_generacion(self):
        texto = self.texto(self.pdf('biblioteca:prestamo_list', estado='vencidos', q='Gómez'))
        self.assertIn('(Préstamos)', texto)
        self.assertIn('Vencidos · Búsqueda: «Gómez» · Generado el ' + timezone.localdate().strftime('%d/%m/%Y'), texto)
        self.assertIn('SIGEBI · Biblioteca UTN FRT', texto)
        self.assertIn('Página 1 de 1', texto)

    def test_trae_las_mismas_filas_que_el_csv(self):
        texto = self.texto(self.pdf('biblioteca:prestamo_list', estado='vencidos'))
        self.assertIn('(CAL-002)', texto)
        self.assertIn('(Gómez, Bruno)', texto)
        self.assertIn(f'({(timezone.localdate() - timedelta(days=6)):%d/%m/%Y})', texto)
        self.assertNotIn('(CAL-001)', texto)  # está al día
        self.assertNotIn('(CAL-003)', texto)  # ya se devolvió

    def test_respeta_los_filtros_de_la_pantalla(self):
        Ejemplar.objects.create(
            codigo_inventario='CAL-009', libro=self.libro, activo=False,
            motivo_baja=Ejemplar.MotivoBaja.PERDIDO, fecha_baja=timezone.localdate(),
        )
        activos = self.texto(self.pdf('biblioteca:ejemplar_list'))
        self.assertIn('(CAL-001)', activos)
        self.assertNotIn('(CAL-009)', activos)
        baja = self.texto(self.pdf('biblioteca:ejemplar_list', estado='baja'))
        self.assertIn('Dados de baja · Sin búsqueda', baja)
        self.assertIn('(CAL-009)', baja)
        self.assertNotIn('(CAL-001)', baja)

    def test_exporta_todas_las_paginas_no_solo_la_que_se_ve(self):
        for numero in range(30):
            Persona.objects.create(nombre='N', apellido=f'Apellido{numero:02}', documento=f'4100{numero:04}', tipo='ALUMNO')
        texto = self.texto(self.pdf('biblioteca:persona_list', page=2))
        self.assertIn('(Apellido00)', texto)
        self.assertIn('(Apellido29)', texto)

    def test_con_muchas_filas_repite_el_encabezado_y_numera_las_hojas(self):
        for numero in range(90):
            Persona.objects.create(nombre='N', apellido=f'Apellido{numero:02}', documento=f'4100{numero:04}', tipo='ALUMNO')
        texto = self.texto(self.pdf('biblioteca:persona_list'))
        hojas = int(re.search(r'Página 1 de (\d+)', texto).group(1))
        self.assertGreater(hojas, 1)
        self.assertIn(f'Página {hojas} de {hojas}', texto)
        self.assertEqual(texto.count('(Préstamos sin devolver)'), hojas)

    def test_sin_datos_lo_dice(self):
        texto = self.texto(self.pdf('biblioteca:ejemplar_list', q='no-existe-nada'))
        self.assertIn('No hay datos para este informe.', texto)
        self.assertIn('Búsqueda: «no-existe-nada»', texto)

    def test_con_muchas_columnas_la_hoja_va_apaisada(self):
        self.assertIn(A4_HORIZONTAL, self.pdf('biblioteca:ejemplar_list').content.decode('latin-1'))  # 12 columnas
        respuesta = respuesta_pdf('x.pdf', 'T', 'D', ['Uno', 'Dos'], [['a', 'b']])
        self.assertIn(A4_VERTICAL, respuesta.content.decode('latin-1'))

    def test_un_dato_con_parentesis_o_formula_no_rompe_el_pdf(self):
        Persona.objects.create(nombre='X', apellido='=HYPERLINK("http://malo") (sic)', documento='1', tipo='ALUMNO')
        respuesta = self.pdf('biblioteca:persona_list')
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn(r'=HYPERLINK\("http://malo"\) \(sic\)', self.texto(respuesta))

    def test_sin_permiso_no_se_descarga(self):
        self.client.force_login(self.sin_rol)
        for nombre in ('biblioteca:prestamo_list', 'biblioteca:ejemplar_list', 'biblioteca:persona_list',
                       'biblioteca:informe_demanda', 'biblioteca:informe_prestamos_por_persona'):
            with self.subTest(informe=nombre):
                self.assertEqual(self.pdf(nombre).status_code, 403)

    def test_otro_formato_muestra_la_pantalla(self):
        respuesta = self.client.get(reverse('biblioteca:prestamo_list'), {'formato': 'xlsx'})
        self.assertEqual(respuesta['Content-Type'], 'text/html; charset=utf-8')


class CadaInformeEnPDFTests(InformesPDFTestCase):
    def test_personas_con_sus_filtros(self):
        texto = self.texto(self.pdf('biblioteca:persona_list', tipo='PROFESOR'))
        self.assertIn('(Personas)', texto)
        self.assertIn('Activas · Profesores · Sin búsqueda', texto)
        self.assertIn('(Gómez)', texto)
        self.assertNotIn('(Pérez)', texto)

    def test_ejemplares_con_tipo_y_categoria(self):
        texto = self.texto(self.pdf(
            'biblioteca:ejemplar_list', tipo='ORIGINAL', categoria=self.libro.categoria_id, estado='todos'
        ))
        self.assertIn('Todos · Tipo: Original · Categoría: Matemática · Sin búsqueda', texto)
        self.assertIn('(Tapa rota)', texto)

    def test_demanda_con_su_periodo(self):
        hoy = timezone.localdate()
        desde = hoy - timedelta(days=40)
        respuesta = self.pdf('biblioteca:informe_demanda', desde=desde.isoformat(), hasta=hoy.isoformat(), solo_comprar='1')
        self.assertEqual(
            respuesta['Content-Disposition'],
            f'attachment; filename="sigebi-demanda-{desde:%Y%m%d}-{hoy:%Y%m%d}-{hoy.isoformat()}.pdf"',
        )
        texto = self.texto(respuesta)
        self.assertIn('(Informe de demanda)', texto)
        self.assertIn(f'Del {desde:%d/%m/%Y} al {hoy:%d/%m/%Y} · Solo los que conviene comprar', texto)

    def test_prestamos_por_persona_con_su_periodo(self):
        hoy = timezone.localdate()
        desde = hoy - timedelta(days=25)
        texto = self.texto(self.pdf(
            'biblioteca:informe_prestamos_por_persona', desde=desde.isoformat(), hasta=hoy.isoformat()
        ))
        self.assertIn('(Préstamos por persona)', texto)
        self.assertIn(f'Préstamos que empezaron del {desde:%d/%m/%Y} al {hoy:%d/%m/%Y}', texto)
        self.assertIn('(Pérez)', texto)


class BotonesDeExportarTests(InformesPDFTestCase):
    def test_cada_listado_ofrece_csv_y_pdf_con_sus_filtros(self):
        casos = {
            'biblioteca:prestamo_list': {'estado': 'vencidos'},
            'biblioteca:ejemplar_list': {'estado': 'todos', 'todos': '1'},
            'biblioteca:persona_list': {'tipo': 'ALUMNO'},
            'biblioteca:informe_demanda': {},
            'biblioteca:informe_prestamos_por_persona': {},
        }
        for nombre, parametros in casos.items():
            with self.subTest(listado=nombre):
                html = self.client.get(reverse(nombre), parametros).content.decode()
                self.assertIn('Exportar CSV', html)
                self.assertIn('Exportar PDF', html)
                for clave, valor in parametros.items():
                    self.assertRegex(html, rf'href="\?[^"]*{clave}={valor}[^"]*formato=pdf')

    def test_el_boton_pdf_no_lleva_la_pagina(self):
        for numero in range(25):
            Persona.objects.create(nombre='N', apellido=f'Apellido{numero:02}', documento=f'4100{numero:04}', tipo='ALUMNO')
        html = self.client.get(reverse('biblioteca:persona_list'), {'page': 2}).content.decode()
        boton = re.search(r'href="([^"]*formato=pdf[^"]*)"', html).group(1)
        self.assertNotIn('page=', boton)

    def test_informes_ofrece_cada_descarga_en_csv_y_en_pdf(self):
        html = self.client.get(reverse('biblioteca:informes')).content.decode()
        descargas = {
            'prestamo_list': ['estado=vencidos&amp;', 'estado=vigentes&amp;', 'estado=todos&amp;'],
            'ejemplar_list': ['', 'estado=todos&amp;'],
            'persona_list': ['', 'estado=todas&amp;'],
        }
        for vista, filtros in descargas.items():
            for filtro in filtros:
                for formato in ('csv', 'pdf'):
                    with self.subTest(vista=vista, filtro=filtro, formato=formato):
                        self.assertIn(f'href="{reverse(f"biblioteca:{vista}")}?{filtro}formato={formato}"', html)
        self.assertEqual(html.count('formato=pdf'), 7)
        self.assertEqual(html.count('formato=csv'), 7)

    def test_sin_permiso_de_personas_no_ve_sus_descargas(self):
        self.sin_rol.user_permissions.add(Permission.objects.get(codename='view_prestamo'))
        self.client.force_login(self.sin_rol)
        html = self.client.get(reverse('biblioteca:informes')).content.decode()
        self.assertIn(reverse('biblioteca:prestamo_list') + '?estado=todos&amp;formato=pdf', html)
        self.assertNotIn(reverse('biblioteca:persona_list') + '?', html)


class LectorDePDFDeLasPruebasTests(SimpleTestCase):
    """El lector que usan estas pruebas no puede depender del azar de la compresión."""

    def flujo_que_termina_en_retorno(self):
        azar = random.Random(0)  # siempre los mismos textos: la prueba es repetible
        for _ in range(5000):
            relleno = ''.join(azar.choices(string.ascii_letters, k=azar.randint(1, 40)))
            texto = f'BT (No hay datos para este informe.) Tj ({relleno}) Tj ET'.encode('latin-1')
            comprimido = zlib.compress(texto)
            if comprimido.endswith(b'\r'):
                return texto, comprimido
        self.fail('No se encontró un flujo que termine en \\r')

    def test_lee_un_flujo_comprimido_que_termina_en_retorno_de_carro(self):
        texto, comprimido = self.flujo_que_termina_en_retorno()
        pdf = (b'%PDF-1.3\n4 0 obj\n<<\n/Filter /FlateDecode\n/Length ' + str(len(comprimido)).encode()
               + b'\n>>\nstream\n' + comprimido + b'\nendstream\nendobj\n%%EOF\n')
        self.assertIn('No hay datos para este informe.', texto_del_pdf(pdf))

    def test_un_flujo_roto_hace_fallar_la_prueba(self):
        pdf = b'%PDF-1.3\n4 0 obj\n<<\n/Filter /FlateDecode\n/Length 5\n>>\nstream\nroto!\nendstream\nendobj\n'
        with self.assertRaisesMessage(AssertionError, 'Flujo comprimido ilegible'):
            texto_del_pdf(pdf)

    def test_lee_los_pdf_de_verdad_aunque_terminen_en_retorno_de_carro(self):
        azar = random.Random(0)
        con_retorno = 0
        for intento in range(20000):  # hasta probar 3 PDF cuyo flujo comprimido termina en \r
            busqueda = ''.join(azar.choices(string.ascii_lowercase, k=azar.randint(1, 30)))
            contenido = respuesta_pdf('x.pdf', 'Ejemplares', f'Búsqueda: «{busqueda}»', ['A'], []).content
            with self.subTest(busqueda=busqueda):
                self.assertIn('No hay datos para este informe.', texto_del_pdf(contenido))
            if re.search(rb'\r\nendstream', contenido):
                con_retorno += 1
                if con_retorno == 3:
                    break
        self.assertEqual(con_retorno, 3, 'No se llegó a probar el caso del \\r')


class ArmadoDelPDFTests(SimpleTestCase):
    def test_texto_pdf(self):
        self.assertEqual(texto_pdf(None), '')
        self.assertEqual(texto_pdf(timezone.localdate().replace(year=2026, month=3, day=5)), '05/03/2026')
        self.assertEqual(texto_pdf('Pérez, Ñandú'), 'Pérez, Ñandú')  # el español entra en Latin-1
        self.assertEqual(texto_pdf('Libro 😀'), 'Libro ?')  # lo que no entra se reemplaza, no falla
        self.assertEqual(texto_pdf(7), '7')

    def anchos(self, encabezados, filas, horizontal=True):
        pdf = InformePDF('T', 'D', horizontal=horizontal)
        pdf.add_page()
        pdf.set_font('Helvetica', '', 8)
        return pdf, anchos_de_columnas(pdf, encabezados, filas)

    def test_ninguna_palabra_queda_cortada(self):
        encabezados = ['Código de inventario', 'Tipo', 'Estado', 'Documento', 'Observaciones']
        filas = [['ADM-001', 'Original', 'Disponible', '30111222', 'Tapa con rastros de humedad ' * 4]]
        pdf, anchos = self.anchos(encabezados, filas)
        for i, ancho in enumerate(anchos):
            palabras = encabezados[i].split() + filas[0][i].split()
            pdf.set_font(style='B')
            mas_larga = max(pdf.get_string_width(p) for p in palabras)
            with self.subTest(columna=encabezados[i]):
                self.assertGreater(ancho, mas_larga)
        self.assertAlmostEqual(sum(anchos), pdf.epw, places=3)

    def test_el_texto_largo_se_lleva_el_espacio_que_sobra(self):
        pdf, anchos = self.anchos(['Código', 'Observaciones'], [['A-1', 'Un texto muy largo ' * 20]])
        self.assertGreater(anchos[1], anchos[0] * 4)

    def test_si_no_entra_todo_en_una_linea_el_espacio_va_a_quien_mas_lo_necesita(self):
        largo = 'Un texto muy largo que no entra en una sola línea ' * 3
        pdf, anchos = self.anchos(['Código', 'Título', 'Autor', 'Observaciones', 'Notas'], [['A-1', largo, largo, largo, largo]])
        self.assertAlmostEqual(sum(anchos), pdf.epw, places=3)
        pdf.set_font(style='B')
        self.assertLess(anchos[0], pdf.get_string_width('Código') + 6)  # al código le alcanza con su palabra
        self.assertTrue(all(ancho > anchos[0] * 3 for ancho in anchos[1:]))

    def test_con_demasiadas_columnas_achica_la_letra(self):
        encabezados = [f'Encabezadolargo{n}' for n in range(30)]
        pdf, anchos = self.anchos(encabezados, [['x'] * 30])
        self.assertLess(pdf.font_size_pt, 8)
        self.assertGreaterEqual(pdf.font_size_pt, 6)
