"""Botón «Volver arriba» y barra lateral sin barra de desplazamiento (pedido del equipo, 25/11/2026).

- «Volver arriba»: botón flotante fijo, abajo a la derecha. Empieza oculto; main.js lo muestra recién cuando
  se bajó más de 400 px (si no se hace scroll, no aparece) y al tocarlo sube y deja el foco en el contenido.
- Barra lateral: sin la barra gris de desplazamiento. El menú es un poco más compacto para que entre completo en
  las pantallas comunes; si no entra, se sigue desplazando y una sombra avisa que hay más opciones.

El comportamiento en el navegador (aparece al bajar, sube al tocarlo, no se alcanza con Tab mientras está oculto,
el menú del celular lo tapa, no se imprime) se comprobó con Playwright; acá se controla lo que lo hace posible.
"""
import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from biblioteca.models import Persona
from cuentas.lectores import crear_cuenta_de_lector
from cuentas.roles import BIBLIOTECARIO

ESTATICOS = Path(settings.BASE_DIR) / 'static'


def regla(css, selector):
    """El bloque de declaraciones de la primera regla que empieza exactamente con `selector {`."""
    inicio = css.index(selector + ' {')
    return css[inicio:css.index('}', inicio) + 1]


class BotonEnLasPantallasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bibliotecario = get_user_model().objects.create_user(username='31222333', password='clave-de-prueba-123')
        cls.bibliotecario.groups.add(Group.objects.get(name=BIBLIOTECARIO))
        ana = Persona.objects.create(nombre='Ana', apellido='Pérez', documento='40111222', tipo='ALUMNO')
        cls.lector = crear_cuenta_de_lector(ana, 'ana@alumnos.example.com')

    def boton(self, respuesta):
        html = respuesta.content.decode()
        self.assertEqual(html.count('data-volver-arriba'), 1)
        inicio = html.index('<button type="button" class="volver-arriba"')
        return html[inicio:html.index('</button>', inicio) + len('</button>')]

    def test_el_personal_y_los_lectores_lo_tienen_y_empieza_oculto(self):
        for usuario, pantalla in ((self.bibliotecario, 'biblioteca:inicio'), (self.lector, 'portal:inicio')):
            with self.subTest(pantalla=pantalla):
                self.client.force_login(usuario)
                boton = self.boton(self.client.get(reverse(pantalla)))
                self.assertIn(' hidden ', boton)  # sin JavaScript no aparece nunca
                self.assertIn('title="Volver arriba"', boton)
                self.assertIn('<span class="sr-only">Volver arriba</span>', boton)  # nombre para lectores de pantalla
                self.assertIn('M12 19V5', boton)  # flecha hacia arriba

    def test_va_despues_del_contenido_y_antes_del_script(self):
        self.client.force_login(self.bibliotecario)
        html = self.client.get(reverse('biblioteca:inicio')).content.decode()
        self.assertLess(html.index('</main>'), html.index('data-volver-arriba'))
        self.assertLess(html.index('data-volver-arriba'), html.index('js/main.js'))

    def test_la_pantalla_de_ingreso_no_lo_tiene(self):
        self.assertNotContains(self.client.get(reverse('login')), 'data-volver-arriba')


class ComportamientoDelBotonTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        js = (ESTATICOS / 'js' / 'main.js').read_text(encoding='utf-8')
        inicio = js.index("// ---------- Botón «Volver arriba» ----------")
        cls.js = js[inicio:js.index('// ----------', inicio + 10)]
        cls.css = (ESTATICOS / 'css' / 'estilos.css').read_text(encoding='utf-8')

    def test_aparece_solo_despues_de_bajar_400_px(self):
        self.assertIn('const VOLVER_ARRIBA_DESDE = 400;', self.js)
        self.assertIn("volverArriba.classList.toggle('es-visible', window.scrollY > VOLVER_ARRIBA_DESDE);", self.js)
        self.assertIn('volverArriba.hidden = false;', self.js)

    def test_escucha_el_scroll_sin_frenar_la_pagina(self):
        self.assertIn("window.addEventListener('scroll', ", self.js)
        self.assertIn('{ passive: true }', self.js)
        self.assertIn('window.requestAnimationFrame(actualizarVolverArriba)', self.js)  # una vez por cuadro

    def test_sube_respetando_reducir_movimiento_y_deja_el_foco_en_el_contenido(self):
        self.assertIn("window.matchMedia('(prefers-reduced-motion: reduce)').matches", self.js)
        self.assertIn("window.scrollTo({ top: 0, behavior: sinAnimacion ? 'auto' : 'smooth' });", self.js)
        self.assertIn("document.getElementById('contenido')", self.js)
        self.assertIn('contenido.focus({ preventScroll: true });', self.js)

    def test_es_un_boton_flotante_fijo_que_empieza_invisible(self):
        boton = regla(self.css, '.volver-arriba')
        for declaracion in ('position: fixed;', 'right: 1.5rem; bottom: 1.5rem;', 'opacity: 0; visibility: hidden;',
                            'width: 48px; height: 48px;', 'border-radius: 50%;'):
            with self.subTest(declaracion=declaracion):
                self.assertIn(declaracion, boton)
        self.assertIn('opacity: 1; visibility: visible;', regla(self.css, '.volver-arriba.es-visible'))

    def test_queda_debajo_del_menu_del_celular_y_no_se_imprime(self):
        capa = int(re.search(r'z-index: (\d+);', regla(self.css, '.volver-arriba')).group(1))
        fondo_del_menu = int(re.search(r'\.js \.lateral-fondo \{ position: fixed; inset: 0; z-index: (\d+);', self.css).group(1))
        self.assertGreater(capa, 20)  # por encima de la cabecera fija
        self.assertLess(capa, fondo_del_menu)  # con el menú abierto, el fondo oscuro lo tapa
        self.assertIn('@media print { .volver-arriba { display: none !important; } }', self.css)

    def test_en_el_celular_es_un_poco_mas_chico_y_respeta_el_borde_de_la_pantalla(self):
        self.assertIn('.volver-arriba { right: 1rem; bottom: max(1rem, env(safe-area-inset-bottom)); width: 44px; height: 44px; }', self.css)


class BarraLateralTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.css = (ESTATICOS / 'css' / 'estilos.css').read_text(encoding='utf-8')
        cls.lateral = regla(cls.css, '.lateral')

    def test_no_muestra_barra_de_desplazamiento(self):
        self.assertIn('scrollbar-width: none;', self.lateral)  # Firefox y Chrome/Edge actuales
        self.assertIn('.lateral::-webkit-scrollbar { display: none; }', self.css)  # Safari y versiones anteriores

    def test_igual_se_puede_desplazar_y_una_sombra_avisa_que_hay_mas(self):
        self.assertIn('overflow-y: auto;', self.lateral)
        self.assertEqual(self.lateral.count('no-repeat local'), 2)  # tapas que se mueven con el menú
        self.assertEqual(self.lateral.count('no-repeat scroll'), 2)  # sombras fijas arriba y abajo

    def test_el_menu_es_mas_compacto(self):
        self.assertIn('padding: 0.45rem 0.75rem;', regla(self.css, '.nav-enlace'))
        self.assertIn('@media (min-width: 901px) and (max-height: 860px) {', self.css)
