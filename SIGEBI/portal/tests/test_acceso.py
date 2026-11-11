"""Separar personal y lectores (Release 2, S7-04).

- Al ingresar, el personal va a su panel y el estudiante o docente, a su portal.
- Un lector recibe 403 en todas las pantallas del personal (se recorren todas las direcciones).
- El portal es solo para lectores: el personal recibe 403 y sin sesión se va al login.
- El menú y las pantallas compartidas (cambiar contraseña, acceso no permitido) se adaptan al rol.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import URLPattern, URLResolver, get_resolver, reverse

from biblioteca.models import Autor, Carrera, Categoria, Editorial, Libro, Persona
from cuentas.lectores import crear_cuenta_de_lector
from cuentas.roles import BIBLIOTECARIO

CLAVE = 'clave-de-prueba-123'
CORREO_LECTOR = 'ana.perez@alumnos.example.com'


def direcciones_de(espacio):
    """Todas las direcciones de un espacio de nombres (por ejemplo, 'biblioteca'), con 1 en cada parámetro."""
    resolver = next(
        patron for patron in get_resolver().url_patterns
        if isinstance(patron, URLResolver) and patron.namespace == espacio
    )
    direcciones = []
    for patron in resolver.url_patterns:
        if isinstance(patron, URLPattern):
            parametros = {nombre: 1 for nombre in patron.pattern.converters}
            direcciones.append(reverse(f'{espacio}:{patron.name}', kwargs=parametros))
    return direcciones


class AccesoTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bibliotecario = get_user_model().objects.create_user(
            username='31222333', email='bibliotecario@example.com', password=CLAVE
        )
        cls.bibliotecario.groups.add(Group.objects.get(name=BIBLIOTECARIO))
        cls.programacion = Carrera.objects.get(nombre='Tecnicatura Universitaria en Programación')
        cls.persona = Persona.objects.create(nombre='Ana', apellido='Pérez', documento='40111222', tipo='ALUMNO')
        cls.persona.carreras.add(cls.programacion)
        cls.lector = crear_cuenta_de_lector(cls.persona, CORREO_LECTOR)
        cls.lector.set_password(CLAVE)
        cls.lector.save()


class IngresoSegunElRolTests(AccesoTestCase):
    def ingresar(self, correo):
        return self.client.post(reverse('login'), {'username': correo, 'password': CLAVE}, follow=True)

    def test_el_lector_va_a_su_portal(self):
        respuesta = self.ingresar(CORREO_LECTOR)
        self.assertEqual(respuesta.redirect_chain[-1][0], reverse('portal:inicio'))
        self.assertContains(respuesta, 'Hola, Ana')

    def test_el_personal_va_a_su_panel(self):
        respuesta = self.ingresar('bibliotecario@example.com')
        self.assertEqual(respuesta.redirect_chain[-1][0], reverse('biblioteca:inicio'))
        self.assertEqual(respuesta.resolver_match.view_name, 'biblioteca:inicio')

    def test_el_login_ya_no_dice_exclusivo_para_el_personal(self):
        respuesta = self.client.get(reverse('login'))
        self.assertNotContains(respuesta, 'Acceso exclusivo para el personal')
        self.assertContains(respuesta, 'estudiantes y docentes')


class ElLectorNoEntraAlSistemaDelPersonalTests(AccesoTestCase):
    def setUp(self):
        self.client.force_login(self.lector)

    def test_todas_las_pantallas_del_personal_responden_403(self):
        direcciones = direcciones_de('biblioteca') + direcciones_de('cuentas')
        self.assertGreater(len(direcciones), 30)
        for url in direcciones:
            if url == reverse('biblioteca:inicio'):
                continue  # el inicio lo lleva a su portal (prueba aparte)
            for metodo in ('get', 'post'):
                with self.subTest(url=url, metodo=metodo):
                    self.assertEqual(getattr(self.client, metodo)(url).status_code, 403)

    def test_el_inicio_del_personal_lo_lleva_a_su_portal(self):
        self.assertRedirects(self.client.get(reverse('biblioteca:inicio')), reverse('portal:inicio'))

    def test_tampoco_entra_al_admin(self):
        respuesta = self.client.get(reverse('admin:index'))
        self.assertNotEqual(respuesta.status_code, 200)

    def test_el_menu_es_el_del_portal(self):
        respuesta = self.client.get(reverse('portal:inicio'))
        self.assertContains(respuesta, f'href="{reverse("portal:inicio")}" aria-current="page"')
        for nombre in ('biblioteca:prestamo_list', 'biblioteca:persona_list', 'biblioteca:informes', 'biblioteca:libro_list'):
            with self.subTest(enlace=nombre):
                self.assertNotContains(respuesta, f'href="{reverse(nombre)}"')
        self.assertContains(respuesta, f'href="{reverse("password_change")}"')

    def test_cambiar_contrasena_muestra_el_menu_del_portal(self):
        respuesta = self.client.get(reverse('password_change'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, f'href="{reverse("biblioteca:prestamo_list")}"')

    def test_la_pagina_de_acceso_no_permitido_vuelve_a_su_portal(self):
        respuesta = self.client.get(reverse('biblioteca:libro_list'))
        self.assertContains(respuesta, 'Esta página es para el personal de la biblioteca.', status_code=403)
        self.assertContains(respuesta, f'class="boton" href="{reverse("portal:inicio")}"', status_code=403)
        self.assertNotContains(respuesta, f'href="{reverse("biblioteca:prestamo_list")}"', status_code=403)

    def test_la_cabecera_no_muestra_el_aviso_de_vencidos(self):
        respuesta = self.client.get(reverse('portal:inicio'))
        self.assertNotContains(respuesta, 'aviso-vencidos')


class PortalSoloParaLectoresTests(AccesoTestCase):
    def test_sin_sesion_va_al_login(self):
        respuesta = self.client.get(reverse('portal:inicio'))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse('login'), respuesta['Location'])

    def test_el_personal_no_entra_al_portal(self):
        self.client.force_login(self.bibliotecario)
        self.assertEqual(self.client.get(reverse('portal:inicio')).status_code, 403)

    def test_una_cuenta_del_personal_vinculada_a_una_persona_no_entra(self):
        # Solo el rol Lector abre el portal, aunque la cuenta tenga una persona vinculada.
        otra = Persona.objects.create(nombre='Bruno', apellido='Díaz', documento='31222333', tipo='ALUMNO')
        otra.cuenta = self.bibliotecario
        otra.save()
        self.client.force_login(self.bibliotecario)
        self.assertEqual(self.client.get(reverse('portal:inicio')).status_code, 403)

    def test_una_cuenta_lector_sin_persona_no_entra(self):
        sin_persona = get_user_model().objects.create_user(username='50111222', email='x@example.com', password=CLAVE)
        sin_persona.groups.add(Group.objects.get(name='Lector'))
        self.client.force_login(sin_persona)
        self.assertEqual(self.client.get(reverse('portal:inicio')).status_code, 403)

    def test_una_cuenta_desactivada_no_entra(self):
        self.client.force_login(self.lector)
        self.persona.activo = False
        self.persona.save()
        respuesta = self.client.get(reverse('portal:inicio'))
        self.assertEqual(respuesta.status_code, 302)


class InicioDelPortalTests(AccesoTestCase):
    def setUp(self):
        self.client.force_login(self.lector)

    def test_muestra_sus_carreras_y_cuantos_libros_tiene(self):
        datos = {
            'autor': Autor.objects.create(nombre='Hugo', apellido='Ledesma'),
            'editorial': Editorial.objects.create(nombre='Pearson'),
        }
        informatica = Categoria.objects.create(nombre='Informática')
        informatica.carreras.add(self.programacion)
        mecanica = Categoria.objects.create(nombre='Mecánica')
        Libro.objects.create(titulo='Python', categoria=informatica, **datos)
        Libro.objects.create(titulo='Java', categoria=informatica, **datos)
        Libro.objects.create(titulo='Tornería', categoria=mecanica, **datos)
        respuesta = self.client.get(reverse('portal:inicio'))
        self.assertContains(respuesta, 'Tecnicatura Universitaria en Programación')
        self.assertEqual(respuesta.context['cantidad_libros'], 2)
        self.assertContains(respuesta, 'Alumno')
