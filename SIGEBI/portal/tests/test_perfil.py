"""Mi perfil y Mis préstamos (Release 2, S7-06).

- El lector ve sus datos (sin poder editarlos), sus carreras y un enlace para cambiar la contraseña.
- Ve sus préstamos sin devolver, con el vencimiento (resaltado si venció), y su historial.
- Solo los suyos: nunca los de otra persona.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from biblioteca.models import Autor, Carrera, Categoria, Editorial, Ejemplar, Libro, Persona, Prestamo
from cuentas.lectores import crear_cuenta_de_lector
from cuentas.roles import BIBLIOTECARIO

CLAVE = 'clave-de-prueba-123'


class PerfilTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bibliotecario = get_user_model().objects.create_user(
            username='31222333', email='bibliotecario@example.com', password=CLAVE
        )
        cls.bibliotecario.groups.add(Group.objects.get(name=BIBLIOTECARIO))
        cls.programacion = Carrera.objects.get(nombre='Tecnicatura Universitaria en Programación')
        cls.persona = Persona.objects.create(
            nombre='Ana', apellido='Pérez', documento='40111222', tipo='ALUMNO', legajo='L-123'
        )
        cls.persona.carreras.add(cls.programacion)
        cls.lector = crear_cuenta_de_lector(cls.persona, 'ana.perez@alumnos.example.com')
        cls.otra = Persona.objects.create(nombre='Carlos', apellido='Ruiz', documento='40999888', tipo='ALUMNO')

        categoria = Categoria.objects.create(nombre='Informática')
        datos = {'autor': Autor.objects.create(nombre='A', apellido='B'),
                 'editorial': Editorial.objects.create(nombre='E'), 'categoria': categoria}
        cls.hoy = timezone.localdate()

        def prestar(persona, titulo, codigo, dias_atras, plazo=14, devuelto=False):
            ejemplar = Ejemplar.objects.create(codigo_inventario=codigo, libro=Libro.objects.create(titulo=titulo, **datos))
            inicio = cls.hoy - timedelta(days=dias_atras)
            return Prestamo.objects.create(
                persona=persona, ejemplar=ejemplar, usuario_sistema=cls.bibliotecario,
                fecha_prestamo=inicio, fecha_vencimiento=inicio + timedelta(days=plazo),
                fecha_devolucion=inicio + timedelta(days=3) if devuelto else None,
            )

        cls.al_dia = prestar(cls.persona, 'Python', 'PY-1', dias_atras=2)            # faltan 12 días
        cls.vencido = prestar(cls.persona, 'Java', 'JA-1', dias_atras=20)            # 6 días de atraso
        cls.devuelto = prestar(cls.persona, 'Redes', 'RE-1', dias_atras=40, devuelto=True)
        cls.ajeno = prestar(cls.otra, 'Libro de Carlos', 'CA-1', dias_atras=1)

    def setUp(self):
        self.client.force_login(self.lector)

    def perfil(self):
        return self.client.get(reverse('portal:perfil'))


class DatosTests(PerfilTestCase):
    def test_muestra_sus_datos_y_carreras(self):
        respuesta = self.perfil()
        for dato in ('Pérez, Ana', '40111222', 'L-123', 'ana.perez@alumnos.example.com',
                     'Tecnicatura Universitaria en Programación', 'Carreras que cursás'):
            with self.subTest(dato=dato):
                self.assertContains(respuesta, dato)

    def test_no_tiene_formulario_para_editar_datos(self):
        # El único formulario de la página es el botón Salir del menú; el contenido no tiene ninguno.
        html = self.perfil().content.decode()
        contenido = html[html.index('<main'):html.index('</main>')]
        self.assertNotIn('<form', contenido)
        self.assertNotIn('<input', contenido)

    def test_ofrece_cambiar_la_contrasena(self):
        self.assertContains(self.perfil(), f'href="{reverse("password_change")}"')

    def test_un_profesor_ve_carreras_que_dicta(self):
        self.persona.tipo = Persona.Tipo.PROFESOR
        self.persona.save()
        self.assertContains(self.perfil(), 'Carreras que dictás')


class PrestamosTests(PerfilTestCase):
    def test_separa_sin_devolver_e_historial(self):
        contexto = self.perfil().context
        self.assertEqual([p.pk for p in contexto['activos']], [self.vencido.pk, self.al_dia.pk])
        self.assertEqual([p.pk for p in contexto['devueltos']], [self.devuelto.pk])

    def test_muestra_cuanto_falta_o_el_atraso(self):
        respuesta = self.perfil()
        self.assertContains(respuesta, 'Faltan 12 días')
        self.assertContains(respuesta, '6 días de atraso')
        self.assertContains(respuesta, 'Tenés libros vencidos')

    def test_vence_hoy_y_manana(self):
        Prestamo.objects.filter(pk=self.al_dia.pk).update(fecha_vencimiento=self.hoy)
        Prestamo.objects.filter(pk=self.vencido.pk).update(fecha_vencimiento=self.hoy + timedelta(days=1))
        respuesta = self.perfil()
        self.assertContains(respuesta, 'Vence hoy')
        self.assertContains(respuesta, 'Vence mañana')
        self.assertNotContains(respuesta, 'Tenés libros vencidos')

    def test_nunca_muestra_prestamos_de_otra_persona(self):
        respuesta = self.perfil()
        self.assertNotContains(respuesta, 'Libro de Carlos')
        self.assertNotContains(respuesta, 'CA-1')
        self.assertNotContains(respuesta, 'Ruiz')

    def test_sin_prestamos(self):
        Prestamo.objects.filter(persona=self.persona).delete()
        respuesta = self.perfil()
        self.assertContains(respuesta, 'No tenés libros sin devolver.')
        self.assertContains(respuesta, 'Todavía no devolviste ningún préstamo.')

    def test_el_inicio_avisa_los_vencidos(self):
        respuesta = self.client.get(reverse('portal:inicio'))
        self.assertContains(respuesta, 'Tenés 1 préstamo vencido.')
        self.assertContains(respuesta, f'href="{reverse("portal:perfil")}"')

    def test_el_inicio_sin_vencidos_avisa_los_sin_devolver(self):
        Prestamo.objects.filter(pk=self.vencido.pk).update(fecha_devolucion=self.hoy)
        respuesta = self.client.get(reverse('portal:inicio'))
        self.assertContains(respuesta, 'Tenés 1 libro sin devolver.')
        self.assertNotContains(respuesta, 'vencido')


class AccesoAlPerfilTests(PerfilTestCase):
    def test_el_menu_tiene_mi_perfil_marcado(self):
        self.assertContains(self.perfil(), f'href="{reverse("portal:perfil")}" aria-current="page"')

    def test_el_personal_y_sin_sesion_no_entran(self):
        self.client.force_login(self.bibliotecario)
        self.assertEqual(self.perfil().status_code, 403)
        self.client.logout()
        respuesta = self.perfil()
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse('login'), respuesta['Location'])
