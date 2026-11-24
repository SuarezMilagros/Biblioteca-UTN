"""Revisión de UX/UI (24/11/2026).

- Carreras: la ficha de una carrera lista sus alumnos y profesores activos, en pestañas y con paginado.
- Inicio del personal: enlaces de salto a cada parte del panel, indicadores compactos y hasta 5 vencimientos.
- Espaciado: un solo criterio para la separación entre botones y entre bloques.
"""
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from biblioteca.models import Autor, Carrera, Categoria, Editorial, Ejemplar, Libro, Persona, Prestamo
from biblioteca.views import ELEMENTOS_POR_PAGINA
from cuentas.lectores import crear_cuenta_de_lector
from cuentas.roles import BIBLIOTECARIO

CLAVE = 'clave-de-prueba-123'
PROGRAMACION = 'Tecnicatura Universitaria en Programación'


class PersonasDeLaCarreraTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bibliotecario = get_user_model().objects.create_user(username='31222333', password=CLAVE)
        cls.bibliotecario.groups.add(Group.objects.get(name=BIBLIOTECARIO))
        cls.programacion = Carrera.objects.get(nombre=PROGRAMACION)
        cls.otra = Carrera.objects.exclude(pk=cls.programacion.pk).first()

        def persona(apellido, documento, tipo='ALUMNO', carrera=None, **datos):
            nueva = Persona.objects.create(nombre='N', apellido=apellido, documento=documento, tipo=tipo, **datos)
            nueva.carreras.add(carrera or cls.programacion)
            return nueva

        cls.ana = persona('Aguirre', '40000001', legajo='L-1')
        cls.beto = persona('Benítez', '40000002')
        cls.inactivo = persona('Inactivo', '40000003', activo=False)
        cls.de_otra = persona('Otracarrera', '40000004', carrera=cls.otra)
        cls.profe = persona('Profesora', '30000001', tipo='PROFESOR')
        cls.cuenta_ana = crear_cuenta_de_lector(cls.ana, 'ana@alumnos.example.com')
        cls.persona = persona  # para crear más en cada prueba

    def setUp(self):
        self.client.force_login(self.bibliotecario)

    def ficha(self, **parametros):
        return self.client.get(reverse('biblioteca:carrera_detail', args=[self.programacion.pk]), parametros)

    def test_por_defecto_lista_los_alumnos_activos_de_la_carrera(self):
        respuesta = self.ficha()
        self.assertContains(respuesta, '<h2>Alumnos y profesores activos</h2>', html=True)
        self.assertEqual(list(respuesta.context['personas']), [self.ana, self.beto])
        self.assertContains(respuesta, f'href="{reverse("biblioteca:persona_detail", args=[self.ana.pk])}"')
        self.assertContains(respuesta, '<td data-etiqueta="Legajo" data-prefijo="Legajo">L-1</td>', html=True)
        self.assertContains(respuesta, '<td data-etiqueta="Documento" data-prefijo="DNI">40000001</td>', html=True)
        self.assertContains(respuesta, '<table class="tabla tabla-compacta">')
        self.assertNotContains(respuesta, 'Inactivo')
        self.assertNotContains(respuesta, 'Otracarrera')
        self.assertNotContains(respuesta, 'Profesora, N')

    def test_muestra_quien_tiene_cuenta_del_portal(self):
        html = self.ficha().content.decode()

        def fila(persona):
            inicio = html.index(f'>{persona}</a>')
            return html[inicio:html.index('</tr>', inicio)]

        self.assertIn('Tiene cuenta', fila(self.ana))  # Ana tiene cuenta del portal
        self.assertNotIn('Sin cuenta', fila(self.ana))
        self.assertIn('Sin cuenta', fila(self.beto))
        self.assertNotIn('Tiene cuenta', fila(self.beto))

    def test_la_pestania_profesores(self):
        respuesta = self.ficha(tipo='profesores')
        self.assertEqual(list(respuesta.context['personas']), [self.profe])
        self.assertContains(respuesta, 'href="?tipo=profesores#personas" aria-current="page" class="activa"')
        self.assertContains(respuesta, 'href="?tipo=alumnos#personas">')

    def test_las_pestanias_muestran_cuantos_hay(self):
        respuesta = self.ficha()
        self.assertContains(respuesta, 'Alumnos <span class="nav-contador nav-contador-suave">2</span>')
        self.assertContains(respuesta, 'Profesores <span class="nav-contador nav-contador-suave">1</span>')

    def test_un_tipo_desconocido_muestra_alumnos(self):
        self.assertEqual(self.ficha(tipo='otra-cosa').context['tipo'], 'alumnos')

    def test_paginado_de_a_20_conservando_la_pestania(self):
        for numero in range(ELEMENTOS_POR_PAGINA + 3):
            self.persona(f'Zeta{numero:02}', f'4100{numero:04}')
        primera = self.ficha(tipo='alumnos')
        self.assertEqual(len(primera.context['personas']), ELEMENTOS_POR_PAGINA)
        self.assertContains(primera, 'Página 1 de 2')
        self.assertContains(primera, 'href="?tipo=alumnos&amp;page=2"')
        segunda = self.ficha(tipo='alumnos', page=2)
        self.assertEqual(len(segunda.context['personas']), 5)  # 25 alumnos activos en total
        self.assertEqual(segunda.context['personas'][4].apellido, 'Zeta22')
        self.assertEqual(self.ficha(tipo='alumnos', page=99).context['page_obj'].number, 2)
        self.assertEqual(self.ficha(tipo='alumnos', page='x').context['page_obj'].number, 1)

    def test_sin_personas_lo_dice(self):
        respuesta = self.client.get(reverse('biblioteca:carrera_detail', args=[self.otra.pk]), {'tipo': 'profesores'})
        self.assertContains(respuesta, 'No hay profesores activos en esta carrera.')

    def test_sin_permiso_de_personas_no_las_ve(self):
        usuario = get_user_model().objects.create_user(username='35000000', password=CLAVE)
        usuario.user_permissions.add(Permission.objects.get(codename='view_carrera'))
        self.client.force_login(usuario)
        respuesta = self.ficha()
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, 'Alumnos y profesores activos')
        self.assertNotContains(respuesta, 'Aguirre')
        self.assertNotIn('personas', respuesta.context)


class InicioDelPersonalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bibliotecario = get_user_model().objects.create_user(username='31222333', password=CLAVE)
        cls.bibliotecario.groups.add(Group.objects.get(name=BIBLIOTECARIO))

    def setUp(self):
        self.client.force_login(self.bibliotecario)

    def test_enlaces_de_salto_a_cada_parte(self):
        respuesta = self.client.get(reverse('biblioteca:inicio'))
        html = respuesta.content.decode()
        self.assertContains(respuesta, '<nav class="saltos" aria-label="Ir a una parte del panel">')
        self.assertNotContains(respuesta, 'En esta página:')  # sin texto de más: las píldoras se explican solas
        self.assertNotContains(respuesta, '{#')  # ningún comentario de la plantilla se ve en la página
        for destino, texto in (('resumen', 'Resumen'), ('titulo-vencimientos', 'Vencimientos'), ('titulo-accesos', 'Accesos rápidos')):
            with self.subTest(destino=destino):
                enlace = html[html.index(f'<a class="salto" href="#{destino}">'):]
                enlace = enlace[:enlace.index('</a>')]
                self.assertIn('M12 5v14', enlace)  # flecha hacia abajo: se queda en esta página
                self.assertTrue(enlace.endswith(texto))
                self.assertEqual(html.count(f'id="{destino}"'), 1)  # el destino existe y no se repite
        # Los enlaces van antes de lo que saltean.
        self.assertLess(html.index('class="saltos"'), html.index('class="indicadores"'))

    def test_sin_permiso_de_prestamos_no_ofrece_ese_salto(self):
        usuario = get_user_model().objects.create_user(username='35000000', password=CLAVE)
        usuario.user_permissions.add(Permission.objects.get(codename='view_ejemplar'))
        self.client.force_login(usuario)
        html = self.client.get(reverse('biblioteca:inicio')).content.decode()
        self.assertNotIn('href="#titulo-vencimientos"', html)
        self.assertIn('href="#titulo-accesos"', html)

    def test_cada_indicador_tiene_icono_y_texto(self):
        html = self.client.get(reverse('biblioteca:inicio')).content.decode()
        self.assertEqual(html.count('class="indicador-icono"'), html.count('class="indicador-texto"'))
        self.assertEqual(html.count('class="indicador-texto"'), 6)

    def test_muestra_hasta_cinco_vencimientos(self):
        categoria = Categoria.objects.create(nombre='Informática')
        libro = Libro.objects.create(
            titulo='Python', categoria=categoria, autor=Autor.objects.create(nombre='A', apellido='B'),
            editorial=Editorial.objects.create(nombre='E'),
        )
        persona = Persona.objects.create(nombre='Ana', apellido='Pérez', documento='40111222', tipo='ALUMNO')
        hoy = timezone.localdate()
        for numero in range(7):
            Prestamo.objects.create(
                persona=persona, ejemplar=Ejemplar.objects.create(codigo_inventario=f'PY-{numero}', libro=libro),
                usuario_sistema=self.bibliotecario, fecha_prestamo=hoy - timedelta(days=10),
                fecha_vencimiento=hoy + timedelta(days=numero),
            )
        respuesta = self.client.get(reverse('biblioteca:inicio'))
        codigos = [p.ejemplar.codigo_inventario for p in respuesta.context['proximos_vencimientos']]
        self.assertEqual(codigos, ['PY-0', 'PY-1', 'PY-2', 'PY-3', 'PY-4'])  # los que vencen antes
        self.assertContains(respuesta, f'href="{reverse("biblioteca:prestamo_list")}">Ver todos</a>')
        # En el celular, cada vencimiento ocupa tres renglones (tabla compacta) y la fecha lleva "Vence".
        self.assertContains(respuesta, '<table class="tabla tabla-compacta">')
        self.assertContains(respuesta, '<td data-etiqueta="Vence" data-prefijo="Vence">', count=5)

    def test_el_acceso_a_informes_menciona_csv_y_pdf(self):
        self.assertContains(self.client.get(reverse('biblioteca:inicio')), 'Estadísticas y exportación en CSV o PDF')


class EspaciadoTests(SimpleTestCase):
    """El espaciado sale de una escala única en la hoja de estilos (la revisión visual se hizo con capturas)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.css = (Path(settings.BASE_DIR) / 'static' / 'css' / 'estilos.css').read_text(encoding='utf-8')

    def test_la_escala_esta_definida(self):
        self.assertIn('--espacio-botones: 0.75rem', self.css)
        self.assertIn('--espacio-acciones: 0.5rem', self.css)
        self.assertIn('--espacio-bloques: 1.25rem', self.css)

    def test_los_grupos_de_botones_la_usan(self):
        for regla in (
            '.botones-encabezado { display: flex; flex-wrap: wrap; gap: var(--espacio-botones); }',
            '.accesos { display: grid; gap: var(--espacio-botones); }',
            '.acciones > a + a, .acciones > a + form, .acciones > form + a, .acciones > form + form '
            '{ margin-left: var(--espacio-acciones); }',
            '.tarjeta > form + form, .tarjeta > form + .formulario-baja',
        ):
            with self.subTest(regla=regla[:40]):
                self.assertIn(regla, self.css)

    def test_en_el_celular_el_panel_y_las_tablas_compactas_son_mas_cortos(self):
        celular = self.css[self.css.index('/* En el celular, cada indicador es solo su nombre y su número'):]
        celular = celular[:celular.index('\n}\n')]
        self.assertIn('.indicador .indicador-icono, .indicador-detalle { display: none; }', celular)
        self.assertIn('.tabla-compacta td[data-etiqueta]::before { display: none; }', celular)
        self.assertIn('.tabla-compacta td[data-prefijo]::before { display: inline; content: attr(data-prefijo) " ";', celular)
        self.assertIn('@media (max-width: 640px) {\n    /* En el celular, cada indicador', self.css)

    def test_las_acciones_en_formulario_conservan_su_separacion(self):
        # Antes `margin: 0` anulaba el espacio entre «Editar» y «Dar de baja» en Material digital.
        self.assertIn('.acciones form.en-linea { display: inline; margin-block: 0; }', self.css)
        self.assertNotIn('.acciones form.en-linea { display: inline; margin: 0; }', self.css)

    def test_los_saltos_son_pildoras_visibles(self):
        for regla in ('border-radius: 999px; background: var(--naranja-suave);', 'min-height: 36px;',
                      '.salto:focus-visible { outline: none; box-shadow: var(--foco); }'):
            with self.subTest(regla=regla):
                self.assertIn(regla, self.css)

    def test_el_salto_no_queda_tapado_por_la_cabecera(self):
        self.assertIn(':target { scroll-margin-top: 84px; }', self.css)


class VersionDeLosEstaticosTests(TestCase):
    """Después de una actualización, el navegador tiene que pedir la hoja de estilos nueva, no usar la guardada."""

    def setUp(self):
        self.client.force_login(get_user_model().objects.create_user(username='31222333', password=CLAVE))

    def huella(self, ruta):
        import hashlib
        return hashlib.sha256((Path(settings.BASE_DIR) / 'static' / ruta).read_bytes()).hexdigest()[:10]

    def test_css_y_js_llevan_la_version_de_su_contenido(self):
        respuesta = self.client.get(reverse('biblioteca:inicio'))
        self.assertContains(respuesta, f'href="/static/css/estilos.css?v={self.huella("css/estilos.css")}"')
        self.assertContains(respuesta, f'src="/static/js/main.js?v={self.huella("js/main.js")}"')

    def test_si_el_archivo_cambia_cambia_la_direccion(self):
        import shutil
        import tempfile
        from django.template import Context, Template
        from django.test import override_settings
        carpeta = Path(tempfile.mkdtemp(prefix='estaticos-'))
        self.addCleanup(shutil.rmtree, carpeta, ignore_errors=True)
        (carpeta / 'css').mkdir()
        archivo = carpeta / 'css' / 'prueba.css'
        plantilla = Template("{% load interfaz %}{% estatico 'css/prueba.css' %}")
        with override_settings(STATICFILES_DIRS=[carpeta]):
            archivo.write_text('body { color: red; }')
            antes = plantilla.render(Context())
            self.assertEqual(antes, plantilla.render(Context()))  # sin cambios, la misma dirección
            archivo.write_text('body { color: blue; }')
            despues = plantilla.render(Context())
        self.assertTrue(antes.startswith('/static/css/prueba.css?v='))
        self.assertNotEqual(antes, despues)

    def test_un_archivo_que_no_existe_sale_sin_version(self):
        from django.template import Context, Template
        html = Template("{% load interfaz %}{% estatico 'css/no-existe.css' %}").render(Context())
        self.assertEqual(html, '/static/css/no-existe.css')


class ComentariosDePlantillaTests(SimpleTestCase):
    def test_ningun_comentario_de_una_linea_ocupa_varias(self):
        """`{# ... #}` solo sirve en una línea: partido en varias, Django lo muestra como texto en la página."""
        base = Path(settings.BASE_DIR)
        for plantilla in sorted(base.glob('**/templates/**/*.html')):
            for numero, linea in enumerate(plantilla.read_text(encoding='utf-8').splitlines(), 1):
                if '{#' in linea:
                    with self.subTest(plantilla=str(plantilla.relative_to(base)), linea=numero):
                        self.assertIn('#}', linea[linea.index('{#'):])
