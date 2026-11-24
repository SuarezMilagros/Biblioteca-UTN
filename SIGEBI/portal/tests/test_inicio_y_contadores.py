"""Reorganización del portal (24/11/2026): el Inicio muestra lo pendiente y el menú tiene contadores.

- Inicio: préstamos vencidos, reservas listas para retirar y préstamos que vencen en 3 días o menos;
  si no hay nada, "Estás al día". Además, buscar en el catálogo y acceso al material digital.
- Menú: "Préstamos" cuenta los vencidos y "Reservas" las listas para retirar. Sin nada pendiente, sin número.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from biblioteca.models import Autor, Carrera, Categoria, Editorial, Ejemplar, Libro, Persona, Prestamo, Reserva
from cuentas.lectores import crear_cuenta_de_lector
from cuentas.roles import BIBLIOTECARIO


class InicioTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bibliotecario = get_user_model().objects.create_user(username='31222333', password='clave-de-prueba-123')
        cls.bibliotecario.groups.add(Group.objects.get(name=BIBLIOTECARIO))
        programacion = Carrera.objects.get(nombre='Tecnicatura Universitaria en Programación')
        categoria = Categoria.objects.create(nombre='Informática')
        categoria.carreras.add(programacion)
        datos = {'autor': Autor.objects.create(nombre='A', apellido='B'), 'editorial': Editorial.objects.create(nombre='E'),
                 'categoria': categoria}
        cls.libros = [Libro.objects.create(titulo=titulo, **datos) for titulo in ('Python', 'Java', 'Redes', 'Algoritmos')]
        cls.ejemplares = [Ejemplar.objects.create(codigo_inventario=f'EJ-{n}', libro=libro)
                          for n, libro in enumerate(cls.libros)]
        cls.ana = Persona.objects.create(nombre='Ana', apellido='Pérez', documento='40111222', tipo='ALUMNO')
        cls.ana.carreras.add(programacion)
        cls.cuenta = crear_cuenta_de_lector(cls.ana, 'ana@alumnos.example.com')
        cls.otro = Persona.objects.create(nombre='Carlos', apellido='Ruiz', documento='40999888', tipo='ALUMNO')

    def setUp(self):
        self.client.force_login(self.cuenta)
        self.hoy = timezone.localdate()

    def prestar(self, ejemplar, vence_en, persona=None):
        vencimiento = self.hoy + timedelta(days=vence_en)
        return Prestamo.objects.create(
            persona=persona or self.ana, ejemplar=ejemplar, usuario_sistema=self.bibliotecario,
            fecha_prestamo=vencimiento - timedelta(days=14), fecha_vencimiento=vencimiento,
        )

    def lista_para_retirar(self, libro, ejemplar, persona=None):
        ahora = timezone.now()
        return Reserva.objects.create(
            persona=persona or self.ana, libro=libro, ejemplar=ejemplar, estado='CONFIRMADA',
            fecha_respuesta=ahora, vence_retiro=ahora + timedelta(hours=48),
        )

    def inicio(self):
        return self.client.get(reverse('portal:inicio'))


class InicioTests(InicioTestCase):
    def test_sin_nada_pendiente_esta_al_dia(self):
        respuesta = self.inicio()
        self.assertContains(respuesta, 'Estás al día')
        self.assertFalse(respuesta.context['hay_pendientes'])

    def test_muestra_los_vencidos_con_su_atraso(self):
        self.prestar(self.ejemplares[0], vence_en=-3)
        respuesta = self.inicio()
        self.assertContains(respuesta, 'Tenés 1 préstamo vencido.')
        self.assertContains(respuesta, f'vencido. <a href="{reverse("portal:sin_devolver")}">Ver mis préstamos</a>')
        self.assertContains(respuesta, 'Devolvé «Python»')
        self.assertContains(respuesta, '(3 días de atraso)')
        self.assertNotContains(respuesta, '«Python» vence')  # un vencido no se repite como "vence pronto"
        self.assertNotContains(respuesta, 'Estás al día')

    def test_muestra_las_reservas_listas_para_retirar(self):
        self.lista_para_retirar(self.libros[1], self.ejemplares[1])
        respuesta = self.inicio()
        self.assertContains(respuesta, 'Retirá «Java»: tu reserva está lista')
        self.assertContains(respuesta, 'Ejemplar EJ-1')

    def test_avisa_lo_que_vence_en_tres_dias_o_menos(self):
        self.prestar(self.ejemplares[0], vence_en=0)
        self.prestar(self.ejemplares[1], vence_en=1)
        self.prestar(self.ejemplares[2], vence_en=3)
        self.prestar(self.ejemplares[3], vence_en=4)
        respuesta = self.inicio()
        self.assertContains(respuesta, '«Python» vence hoy')
        self.assertContains(respuesta, '«Java» vence mañana')
        self.assertContains(respuesta, '«Redes» vence en 3 días')
        self.assertNotContains(respuesta, '«Algoritmos» vence')
        self.assertContains(respuesta, 'Tenés 4 libros sin devolver.')

    def test_cuenta_lo_que_espera_a_la_biblioteca(self):
        Reserva.objects.create(persona=self.ana, libro=self.libros[2])
        respuesta = self.inicio()
        self.assertContains(respuesta, '1 reserva esperando confirmación de la biblioteca.')
        self.assertNotContains(respuesta, 'Retirá «Redes»')  # pendiente no es "lista para retirar"
        self.assertContains(respuesta, 'Estás al día')

    def test_nunca_muestra_lo_de_otra_persona(self):
        self.prestar(self.ejemplares[0], vence_en=-2, persona=self.otro)
        self.lista_para_retirar(self.libros[1], self.ejemplares[1], persona=self.otro)
        respuesta = self.inicio()
        self.assertContains(respuesta, 'Estás al día')
        self.assertNotContains(respuesta, 'Python')

    def test_ofrece_buscar_en_el_catalogo(self):
        respuesta = self.inicio()
        self.assertContains(respuesta, f'<form method="get" action="{reverse("portal:catalogo")}"')
        self.assertContains(respuesta, 'Hay 4 títulos de tus carreras.')


class ContadoresDelMenuTests(InicioTestCase):
    def enlace(self, respuesta, nombre):
        html = respuesta.content.decode()
        inicio = html.index(f'href="{reverse(f"portal:{nombre}")}"', html.index('<nav class="navegacion"'))
        return html[inicio:html.index('</a>', inicio)]

    def test_sin_pendientes_no_hay_numeros(self):
        respuesta = self.inicio()
        self.assertNotIn('nav-contador', self.enlace(respuesta, 'sin_devolver'))
        self.assertNotIn('nav-contador', self.enlace(respuesta, 'mis_reservas'))

    def test_prestamos_cuenta_los_vencidos(self):
        self.prestar(self.ejemplares[0], vence_en=-1)
        self.prestar(self.ejemplares[1], vence_en=-5)
        self.prestar(self.ejemplares[2], vence_en=5)
        self.prestar(self.ejemplares[3], vence_en=-5, persona=self.otro)
        self.assertIn('aria-label="2 vencidos">2</span>', self.enlace(self.inicio(), 'sin_devolver'))

    def test_reservas_cuenta_las_listas_para_retirar(self):
        self.lista_para_retirar(self.libros[0], self.ejemplares[0])
        Reserva.objects.create(persona=self.ana, libro=self.libros[1])  # pendiente: no cuenta
        self.assertIn('aria-label="1 para retirar">1</span>', self.enlace(self.inicio(), 'mis_reservas'))

    def test_una_reserva_vencida_no_cuenta(self):
        reserva = self.lista_para_retirar(self.libros[0], self.ejemplares[0])
        Reserva.objects.filter(pk=reserva.pk).update(vence_retiro=timezone.now() - timedelta(hours=1))
        # En una pantalla que no actualiza los vencimientos (el catálogo), el contador solo tiene que ignorarla.
        catalogo = self.client.get(reverse('portal:catalogo'))
        self.assertNotIn('nav-contador', self.enlace(catalogo, 'mis_reservas'))
        self.assertEqual(Reserva.objects.get(pk=reserva.pk).estado, 'CONFIRMADA')

    def test_el_personal_no_recibe_estos_contadores(self):
        self.client.force_login(self.bibliotecario)
        respuesta = self.client.get(reverse('biblioteca:inicio'))
        self.assertNotIn('portal_prestamos_vencidos', respuesta.context)
