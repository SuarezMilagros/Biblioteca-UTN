"""Cambios pedidos por la profesora (18/11/2026).

- Menú: "Ejemplares" va en Catálogo y "Personas" en Gestión.
- Cada ejemplar tiene tipo: original, copia o tesis.
- Filtros: libros por tipo de ejemplar; ejemplares por tipo y categoría; personas por carrera y por alumno/profesor.
- Informe de préstamos por persona, con un rango de fechas elegido de hasta un mes.
- Documento: solo números, de 7 u 8 dígitos.
"""
import re
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from biblioteca import prestamos_por_persona
from biblioteca.models import Autor, Carrera, Categoria, Editorial, Ejemplar, Libro, Persona, Prestamo
from cuentas.roles import ADMINISTRATIVO, BIBLIOTECARIO

CLAVE = 'clave-de-prueba-123'


class PedidosTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.bibliotecario = Usuario.objects.create_user(username='31222333', email='biblio@example.com', password=CLAVE)
        cls.bibliotecario.groups.add(Group.objects.get(name=BIBLIOTECARIO))
        datos = {'autor': Autor.objects.create(nombre='A', apellido='B'), 'editorial': Editorial.objects.create(nombre='E')}
        cls.informatica = Categoria.objects.create(nombre='Informática')
        cls.fisica = Categoria.objects.create(nombre='Física')
        cls.python = Libro.objects.create(titulo='Python', categoria=cls.informatica, **datos)
        cls.tesis_redes = Libro.objects.create(titulo='Redes rurales', categoria=cls.informatica, **datos)
        cls.optica = Libro.objects.create(titulo='Óptica', categoria=cls.fisica, **datos)
        cls.py_original = Ejemplar.objects.create(codigo_inventario='PY-1', libro=cls.python)
        cls.py_copia = Ejemplar.objects.create(codigo_inventario='PY-2', libro=cls.python, tipo='COPIA')
        cls.tesis = Ejemplar.objects.create(codigo_inventario='TES-1', libro=cls.tesis_redes, tipo='TESIS')
        cls.optica_copia_baja = Ejemplar.objects.create(
            codigo_inventario='OPT-1', libro=cls.optica, tipo='COPIA', activo=False, motivo_baja='PERDIDO',
            fecha_baja=timezone.localdate(),
        )
        cls.programacion = Carrera.objects.get(nombre='Tecnicatura Universitaria en Programación')
        cls.mecanica = Carrera.objects.get(nombre='Ingeniería Mecánica')
        cls.ana = Persona.objects.create(nombre='Ana', apellido='Pérez', documento='40111222', tipo='ALUMNO')
        cls.ana.carreras.add(cls.programacion)
        cls.luis = Persona.objects.create(nombre='Luis', apellido='Gómez', documento='20333444', tipo='PROFESOR')
        cls.luis.carreras.add(cls.programacion, cls.mecanica)
        cls.eva = Persona.objects.create(nombre='Eva', apellido='Díaz', documento='4555666', tipo='ALUMNO')
        cls.eva.carreras.add(cls.mecanica)

    def setUp(self):
        self.client.force_login(self.bibliotecario)

    def listado(self, nombre, consulta):
        respuesta = self.client.get(reverse(f'biblioteca:{nombre}') + consulta)
        return respuesta, list(respuesta.context['object_list'])


class MenuTests(PedidosTestCase):
    def test_ejemplares_en_catalogo_y_personas_en_gestion(self):
        html = self.client.get(reverse('biblioteca:inicio')).content.decode()
        catalogo, gestion = html.index('>Catálogo</p>'), html.index('>Gestión</p>')
        ejemplares = html.index(f'href="{reverse("biblioteca:ejemplar_list")}"')
        personas = html.index(f'href="{reverse("biblioteca:persona_list")}"')
        self.assertTrue(catalogo < ejemplares < gestion)
        self.assertTrue(gestion < personas)
        self.assertLess(html.index(f'href="{reverse("biblioteca:libro_list")}"'), ejemplares)

    def test_la_ubicacion_de_cada_pantalla_coincide_con_el_menu(self):
        self.assertContains(self.client.get(reverse('biblioteca:ejemplar_list')), 'Catálogo / <strong>Ejemplares</strong>')
        self.assertContains(self.client.get(reverse('biblioteca:persona_list')), 'Gestión / <strong>Personas</strong>')
        self.assertContains(self.client.get(reverse('biblioteca:persona_detail', args=[self.ana.pk])), 'Gestión / Personas /')


class TipoDeEjemplarTests(PedidosTestCase):
    def test_por_defecto_es_original(self):
        self.assertEqual(Ejemplar.objects.create(codigo_inventario='X-1', libro=self.python).tipo, 'ORIGINAL')

    def test_se_elige_al_cargarlo(self):
        self.client.post(reverse('biblioteca:ejemplar_create'),
                         {'codigo_inventario': 'TES-2', 'libro': self.tesis_redes.pk, 'tipo': 'TESIS'})
        self.assertEqual(Ejemplar.objects.get(codigo_inventario='TES-2').tipo, 'TESIS')

    def test_sin_elegir_queda_original(self):
        self.client.post(reverse('biblioteca:ejemplar_create'), {'codigo_inventario': 'PY-9', 'libro': self.python.pk})
        self.assertEqual(Ejemplar.objects.get(codigo_inventario='PY-9').tipo, 'ORIGINAL')

    def test_un_tipo_inventado_se_rechaza(self):
        respuesta = self.client.post(reverse('biblioteca:ejemplar_create'),
                                     {'codigo_inventario': 'PY-8', 'libro': self.python.pk, 'tipo': 'REVISTA'})
        self.assertIn('tipo', respuesta.context['form'].errors)

    def test_el_formulario_muestra_el_tipo(self):
        # Hallado en el QA del Sprint 8: el campo existía en el formulario pero no en la pantalla.
        for url in (reverse('biblioteca:ejemplar_create'), reverse('biblioteca:ejemplar_update', args=[self.tesis.pk])):
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                self.assertIn('<select name="tipo"', html)
                for nombre in ('Original', 'Copia', 'Tesis'):
                    self.assertIn(f'>{nombre}</option>', html)

    def test_al_editar_una_copia_desde_la_pantalla_sigue_siendo_copia(self):
        # Envía solo los campos que la pantalla muestra, como lo haría el navegador. Sin el campo en la
        # plantilla, el tipo no viajaba y la copia quedaba guardada como original.
        url = reverse('biblioteca:ejemplar_update', args=[self.py_copia.pk])
        respuesta = self.client.get(url)
        html = respuesta.content.decode()
        formulario = html[html.index('<form method="post" class="formulario'):]
        formulario = formulario[:formulario.index('</form>')]
        nombres = set(re.findall(r'name="([a-z_]+)"', formulario)) - {'csrfmiddlewaretoken'}
        form = respuesta.context['form']
        datos = {nombre: form[nombre].value() or '' for nombre in nombres}
        self.assertEqual(datos.get('tipo'), 'COPIA')
        self.client.post(url, datos)
        self.py_copia.refresh_from_db()
        self.assertEqual(self.py_copia.tipo, 'COPIA')

    def test_se_ve_en_la_ficha_la_lista_y_el_libro(self):
        self.assertContains(self.client.get(reverse('biblioteca:ejemplar_detail', args=[self.tesis.pk])), '<dd>Tesis</dd>', html=True)
        lista = self.client.get(reverse('biblioteca:ejemplar_list') + '?todos=1')
        self.assertContains(lista, '<span class="badge badge-etiqueta">Copia</span>', html=True)
        libro = self.client.get(reverse('biblioteca:libro_detail', args=[self.python.pk]))
        self.assertContains(libro, '<td data-etiqueta="Tipo">Copia</td>', html=True)
        self.assertContains(libro, '<td data-etiqueta="Tipo">Original</td>', html=True)


class FiltrosTests(PedidosTestCase):
    def test_libros_por_tipo_de_ejemplar(self):
        _, libros = self.listado('libro_list', '?tipo=TESIS')
        self.assertEqual(libros, [self.tesis_redes])
        _, libros = self.listado('libro_list', '?tipo=COPIA')
        self.assertEqual(libros, [self.python])  # la copia de Óptica está dada de baja
        _, libros = self.listado('libro_list', '?tipo=ORIGINAL')
        self.assertEqual(libros, [self.python])

    def test_el_filtro_de_libros_no_altera_la_disponibilidad(self):
        _, libros = self.listado('libro_list', '?tipo=COPIA')
        self.assertEqual((libros[0].ejemplares_activos, libros[0].ejemplares_disponibles), (2, 2))

    def test_libros_con_un_tipo_invalido_se_ignora(self):
        respuesta, libros = self.listado('libro_list', '?tipo=OTRO')
        self.assertEqual(respuesta.context['tipo'], '')
        self.assertEqual(libros, [])  # sin búsqueda ni filtro válidos, se espera la búsqueda

    def test_ejemplares_por_tipo(self):
        _, ejemplares = self.listado('ejemplar_list', '?tipo=COPIA')
        self.assertEqual(ejemplares, [self.py_copia])
        _, ejemplares = self.listado('ejemplar_list', '?tipo=COPIA&estado=todos')
        self.assertEqual(ejemplares, [self.optica_copia_baja, self.py_copia])

    def test_ejemplares_por_categoria(self):
        _, ejemplares = self.listado('ejemplar_list', f'?categoria={self.informatica.pk}')
        self.assertEqual(ejemplares, [self.py_original, self.py_copia, self.tesis])
        respuesta, ejemplares = self.listado('ejemplar_list', f'?categoria={self.fisica.pk}&estado=todos&tipo=COPIA')
        self.assertEqual(ejemplares, [self.optica_copia_baja])
        self.assertContains(respuesta, f'<option value="{self.fisica.pk}" selected>Física</option>', html=True)

    def test_el_csv_de_ejemplares_respeta_los_filtros(self):
        respuesta = self.client.get(reverse('biblioteca:ejemplar_list') + '?tipo=TESIS&formato=csv')
        filas = respuesta.content.decode('utf-8-sig').splitlines()
        self.assertEqual(len(filas), 2)
        self.assertTrue(filas[1].startswith('TES-1;;Redes rurales;Tesis;'))

    def test_personas_por_tipo(self):
        _, personas = self.listado('persona_list', '?tipo=PROFESOR')
        self.assertEqual(personas, [self.luis])
        _, personas = self.listado('persona_list', '?tipo=ALUMNO')
        self.assertEqual(personas, [self.eva, self.ana])

    def test_personas_por_carrera(self):
        _, personas = self.listado('persona_list', f'?carrera={self.mecanica.pk}')
        self.assertEqual(personas, [self.eva, self.luis])
        respuesta, personas = self.listado('persona_list', f'?carrera={self.mecanica.pk}&tipo=ALUMNO')
        self.assertEqual(personas, [self.eva])
        self.assertContains(respuesta, '<option value="ALUMNO" selected>Alumnos</option>', html=True)
        self.assertContains(respuesta, 'Quitar filtros')


class InformePorPersonaTests(PedidosTestCase):
    def prestar(self, persona, ejemplar, empezo, vence_en=14, devuelto=False):
        return Prestamo.objects.create(
            persona=persona, ejemplar=ejemplar, usuario_sistema=self.bibliotecario,
            fecha_prestamo=empezo, fecha_vencimiento=empezo + timedelta(days=vence_en),
            fecha_devolucion=empezo + timedelta(days=3) if devuelto else None,
        )

    def informe(self, consulta=''):
        return self.client.get(reverse('biblioteca:informe_prestamos_por_persona') + consulta)

    def test_cuenta_por_persona_en_el_rango(self):
        hoy = timezone.localdate()
        desde = hoy - timedelta(days=20)
        self.prestar(self.ana, self.py_original, desde, devuelto=True)
        self.prestar(self.ana, self.py_copia, desde + timedelta(days=1), vence_en=2)  # vencido
        self.prestar(self.ana, self.tesis, hoy)  # sin devolver, al día
        self.prestar(self.luis, self.tesis, desde - timedelta(days=30), devuelto=True)  # fuera del rango
        respuesta = self.informe(f'?desde={desde.isoformat()}&hasta={hoy.isoformat()}')
        personas = list(respuesta.context['personas'])
        self.assertEqual(personas, [self.ana])
        ana = personas[0]
        self.assertEqual((ana.total_prestamos, ana.devueltos, ana.sin_devolver, ana.vencidos), (3, 1, 2, 1))
        self.assertContains(respuesta, reverse('biblioteca:persona_detail', args=[self.ana.pk]))

    def test_por_defecto_el_mes_actual(self):
        respuesta = self.informe()
        hoy = timezone.localdate()
        self.assertEqual((respuesta.context['desde'], respuesta.context['hasta']), (hoy.replace(day=1), hoy))

    def test_rango_de_hasta_31_dias(self):
        hoy = date(2026, 11, 18)
        self.assertEqual(prestamos_por_persona.leer_periodo('2026-10-01', '2026-10-31', hoy=hoy),
                         (date(2026, 10, 1), date(2026, 10, 31), None))
        desde, hasta, error = prestamos_por_persona.leer_periodo('2026-10-01', '2026-11-01', hoy=hoy)
        self.assertEqual((desde, hasta), (date(2026, 11, 1), hoy))
        self.assertEqual(error, 'El rango puede ser de hasta 31 días (un mes): se muestra el mes actual.')

    def test_fechas_invalidas_o_al_reves(self):
        hoy = date(2026, 11, 18)
        self.assertIn('no es válida', prestamos_por_persona.leer_periodo('18/11/2026', '', hoy=hoy)[2])
        self.assertIn('posterior', prestamos_por_persona.leer_periodo('2026-11-10', '2026-11-01', hoy=hoy)[2])
        self.assertEqual(prestamos_por_persona.leer_periodo('2026-11-10', '', hoy=hoy),
                         (date(2026, 11, 10), hoy, None))

    def test_el_error_se_muestra(self):
        respuesta = self.informe('?desde=2026-01-01&hasta=2026-06-30')
        self.assertContains(respuesta, 'El rango puede ser de hasta 31 días (un mes)')

    def test_exportacion_csv(self):
        hoy = timezone.localdate()
        self.prestar(self.luis, self.tesis, hoy, devuelto=False)
        respuesta = self.informe('?formato=csv')
        filas = respuesta.content.decode('utf-8-sig').splitlines()
        self.assertEqual(filas[0], 'Apellido;Nombre;Documento;Tipo;Préstamos;Devueltos;Sin devolver;Vencidos')
        self.assertEqual(filas[1], 'Gómez;Luis;20333444;Profesor;1;0;1;0')
        self.assertIn('sigebi-prestamos-por-persona-', respuesta['Content-Disposition'])

    def test_se_llega_desde_informes(self):
        self.assertContains(self.client.get(reverse('biblioteca:informes')),
                            reverse('biblioteca:informe_prestamos_por_persona'))

    def test_hace_falta_ver_personas_y_prestamos(self):
        usuario = get_user_model().objects.create_user(username='consulta', password=CLAVE)
        usuario.user_permissions.add(Permission.objects.get(codename='view_prestamo'))
        self.client.force_login(usuario)
        self.assertEqual(self.informe().status_code, 403)


class DocumentoTests(PedidosTestCase):
    def alta(self, documento):
        return self.client.post(reverse('biblioteca:persona_create'), {
            'nombre': 'Nueva', 'apellido': 'Persona', 'documento': documento, 'tipo': 'ALUMNO',
            'legajo': '', 'carreras': [self.programacion.pk],
        })

    def test_acepta_7_u_8_numeros(self):
        for documento in ('1234567', '12345678', ' 12.345.679 '):
            with self.subTest(documento=documento):
                self.alta(documento)
        self.assertEqual(
            sorted(Persona.objects.filter(apellido='Persona').values_list('documento', flat=True)),
            ['1234567', '12345678', '12345679'],
        )

    def test_rechaza_mas_de_8_menos_de_7_o_letras(self):
        for documento in ('123456789', '123456', '1234567A', 'AB123456', '１２３４５６７'):
            with self.subTest(documento=documento):
                respuesta = self.alta(documento)
                self.assertEqual(respuesta.context['form'].errors['documento'],
                                 ['El documento tiene que tener 7 u 8 números, sin letras.'])
        self.assertFalse(Persona.objects.filter(apellido='Persona').exists())

    def test_el_campo_no_deja_escribir_mas_de_8(self):
        respuesta = self.client.get(reverse('biblioteca:persona_create'))
        self.assertContains(respuesta, 'maxlength="8"')
        self.assertContains(respuesta, 'inputmode="numeric"')

    def test_cuentas_del_personal(self):
        administrativo = get_user_model().objects.create_user(username='32333444', email='admin@example.com', password=CLAVE)
        administrativo.groups.add(Group.objects.get(name=ADMINISTRATIVO))
        self.client.force_login(administrativo)
        datos = {'first_name': 'Lucía', 'last_name': 'Paz', 'email': 'lucia@example.com', 'rol': BIBLIOTECARIO,
                 'is_active': 'on'}
        respuesta = self.client.post(reverse('cuentas:usuario_create'), {**datos, 'username': 'lucia.paz'})
        self.assertEqual(respuesta.context['form'].errors['username'],
                         ['El documento tiene que tener 7 u 8 números, sin letras.'])
        self.client.post(reverse('cuentas:usuario_create'), {**datos, 'username': '40.111.999'})
        self.assertTrue(get_user_model().objects.filter(username='40111999').exists())

    def test_una_cuenta_vieja_con_otro_formato_se_puede_seguir_editando(self):
        administrativo = get_user_model().objects.create_user(username='32333444', email='admin@example.com', password=CLAVE)
        administrativo.groups.add(Group.objects.get(name=ADMINISTRATIVO))
        vieja = get_user_model().objects.create_user(username='bibliotecaria', email='vieja@example.com', password=CLAVE,
                                                     first_name='Vieja', last_name='Cuenta')
        vieja.groups.add(Group.objects.get(name=BIBLIOTECARIO))
        self.client.force_login(administrativo)
        self.client.post(reverse('cuentas:usuario_update', args=[vieja.pk]), {
            'username': 'bibliotecaria', 'first_name': 'Vieja', 'last_name': 'Cuenta Editada',
            'email': 'vieja@example.com', 'rol': BIBLIOTECARIO, 'is_active': 'on',
        })
        vieja.refresh_from_db()
        self.assertEqual(vieja.last_name, 'Cuenta Editada')
