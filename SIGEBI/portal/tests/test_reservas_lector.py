"""Reservas de libros físicos, lado del lector (Release 2, S8-02).

- Reserva un libro de sus carreras que tenga ejemplares activos, aunque ahora estén todos prestados.
- No puede: dado de baja, con préstamos vencidos, con una reserva activa de ese libro o con 2 activas.
- Ve sus reservas en Mi perfil y cancela las pendientes.
- La base garantiza una reserva activa por persona y libro, y la coherencia de cada estado.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from biblioteca.models import Autor, Carrera, Categoria, Editorial, Ejemplar, Libro, Persona, Prestamo, Reserva
from biblioteca.reservas import MAXIMO_RESERVAS_ACTIVAS, motivos_para_no_reservar
from cuentas.lectores import crear_cuenta_de_lector
from cuentas.roles import BIBLIOTECARIO

CLAVE = 'clave-de-prueba-123'


class ReservasTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bibliotecario = get_user_model().objects.create_user(
            username='31222333', email='bibliotecario@example.com', password=CLAVE
        )
        cls.bibliotecario.groups.add(Group.objects.get(name=BIBLIOTECARIO))
        cls.programacion = Carrera.objects.get(nombre='Tecnicatura Universitaria en Programación')
        informatica = Categoria.objects.create(nombre='Informática')
        informatica.carreras.add(cls.programacion)
        taller = Categoria.objects.create(nombre='Taller')
        taller.carreras.add(Carrera.objects.get(nombre='Ingeniería Mecánica'))
        datos = {'autor': Autor.objects.create(nombre='A', apellido='B'), 'editorial': Editorial.objects.create(nombre='E')}
        cls.python = Libro.objects.create(titulo='Python', categoria=informatica, **datos)
        cls.java = Libro.objects.create(titulo='Java', categoria=informatica, **datos)
        cls.redes = Libro.objects.create(titulo='Redes', categoria=informatica, **datos)
        cls.torneria = Libro.objects.create(titulo='Tornería', categoria=taller, **datos)
        for libro in (cls.python, cls.java, cls.redes, cls.torneria):
            Ejemplar.objects.create(codigo_inventario=f'{libro.titulo[:3].upper()}-1', libro=libro)
        cls.persona = Persona.objects.create(nombre='Ana', apellido='Pérez', documento='40111222', tipo='ALUMNO')
        cls.persona.carreras.add(cls.programacion)
        cls.lector = crear_cuenta_de_lector(cls.persona, 'ana.perez@alumnos.example.com')

    def setUp(self):
        self.client.force_login(self.lector)

    def reservar(self, libro):
        return self.client.post(reverse('portal:reservar', args=[libro.pk]), follow=True)

    def activas(self):
        return list(self.persona.reservas.filter(estado__in=Reserva.ACTIVAS).values_list('libro__titulo', flat=True))

    def prestar(self, persona, libro, dias_atras=0):
        inicio = timezone.localdate() - timedelta(days=dias_atras)
        return Prestamo.objects.create(
            persona=persona, ejemplar=libro.ejemplares.first(), usuario_sistema=self.bibliotecario,
            fecha_prestamo=inicio, fecha_vencimiento=inicio + timedelta(days=14),
        )


class ReservarTests(ReservasTestCase):
    def test_reserva_un_libro_de_su_carrera(self):
        respuesta = self.reservar(self.python)
        self.assertContains(respuesta, 'Reservaste &quot;Python&quot;')
        reserva = Reserva.objects.get()
        self.assertEqual((reserva.persona, reserva.libro, reserva.estado), (self.persona, self.python, 'PENDIENTE'))
        self.assertIsNone(reserva.ejemplar)

    def test_puede_reservar_aunque_esten_todos_prestados(self):
        otra = Persona.objects.create(nombre='Carlos', apellido='Ruiz', documento='40999888', tipo='ALUMNO')
        self.prestar(otra, self.python)
        self.reservar(self.python)
        self.assertEqual(self.activas(), ['Python'])

    def test_no_reserva_dos_veces_el_mismo_libro(self):
        self.reservar(self.python)
        respuesta = self.reservar(self.python)
        self.assertContains(respuesta, 'Ya tenés una reserva activa de este libro.')
        self.assertEqual(Reserva.objects.count(), 1)

    def test_maximo_de_reservas_activas(self):
        self.reservar(self.python)
        self.reservar(self.java)
        respuesta = self.reservar(self.redes)
        self.assertContains(respuesta, f'Ya tenés {MAXIMO_RESERVAS_ACTIVAS} reservas activas, que es el máximo.')
        self.assertEqual(sorted(self.activas()), ['Java', 'Python'])

    def test_con_un_prestamo_vencido_no_puede(self):
        self.prestar(self.persona, self.java, dias_atras=20)
        respuesta = self.reservar(self.python)
        self.assertContains(respuesta, 'Tenés préstamos vencidos')
        self.assertFalse(Reserva.objects.exists())

    def test_con_un_prestamo_al_dia_si_puede(self):
        self.prestar(self.persona, self.java, dias_atras=2)
        self.reservar(self.python)
        self.assertEqual(self.activas(), ['Python'])

    def test_sin_ejemplares_activos_no_puede(self):
        self.python.ejemplares.update(activo=False, motivo_baja='PERDIDO', fecha_baja=timezone.localdate())
        respuesta = self.reservar(self.python)
        self.assertContains(respuesta, 'no tiene ejemplares de este libro')
        self.assertFalse(Reserva.objects.exists())

    def test_un_libro_de_otra_carrera_responde_404(self):
        respuesta = self.client.post(reverse('portal:reservar', args=[self.torneria.pk]))
        self.assertEqual(respuesta.status_code, 404)
        self.assertFalse(Reserva.objects.exists())

    def test_la_regla_de_la_carrera_tambien_esta_en_el_servicio(self):
        # La vista ya responde 404, pero la regla no depende solo de la vista.
        self.assertIn('Este libro no es de tus carreras.', motivos_para_no_reservar(self.persona, self.torneria))

    def test_una_persona_dada_de_baja_no_puede(self):
        # Con la baja la cuenta se desactiva y no puede ni ingresar; la regla igual se controla.
        Persona.objects.filter(pk=self.persona.pk).update(activo=False)
        self.persona.refresh_from_db()
        self.assertIn('Tu cuenta está dada de baja en la biblioteca.', motivos_para_no_reservar(self.persona, self.python))

    def test_una_cancelada_libera_el_cupo(self):
        self.reservar(self.python)
        self.reservar(self.java)
        self.client.post(reverse('portal:cancelar_reserva', args=[self.persona.reservas.get(libro=self.python).pk]))
        self.reservar(self.redes)
        self.assertEqual(sorted(self.activas()), ['Java', 'Redes'])

    def test_solo_por_post(self):
        self.assertEqual(self.client.get(reverse('portal:reservar', args=[self.python.pk])).status_code, 405)


class PantallasTests(ReservasTestCase):
    def test_el_detalle_ofrece_reservar(self):
        respuesta = self.client.get(reverse('portal:libro', args=[self.python.pk]))
        self.assertContains(respuesta, 'Reservar este libro')
        self.assertContains(respuesta, '48 horas')

    def test_el_detalle_muestra_la_reserva_activa(self):
        self.reservar(self.python)
        respuesta = self.client.get(reverse('portal:libro', args=[self.python.pk]))
        self.assertNotContains(respuesta, 'Reservar este libro')
        self.assertContains(respuesta, 'La biblioteca todavía no la confirmó.')

    def test_el_detalle_explica_por_que_no_puede(self):
        self.prestar(self.persona, self.java, dias_atras=20)
        respuesta = self.client.get(reverse('portal:libro', args=[self.python.pk]))
        self.assertNotContains(respuesta, 'Reservar este libro')
        self.assertContains(respuesta, 'Tenés préstamos vencidos')

    def test_mi_perfil_muestra_activas_y_anteriores(self):
        self.reservar(self.python)
        self.reservar(self.java)
        self.client.post(reverse('portal:cancelar_reserva', args=[self.persona.reservas.get(libro=self.java).pk]))
        contexto = self.client.get(reverse('portal:perfil')).context
        self.assertEqual([r.libro.titulo for r in contexto['reservas_activas']], ['Python'])
        self.assertEqual([r.libro.titulo for r in contexto['reservas_anteriores']], ['Java'])


class CancelarTests(ReservasTestCase):
    def test_cancela_una_pendiente(self):
        self.reservar(self.python)
        reserva = Reserva.objects.get()
        respuesta = self.client.post(reverse('portal:cancelar_reserva', args=[reserva.pk]), follow=True)
        self.assertContains(respuesta, 'Cancelaste la reserva de &quot;Python&quot;.')
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, 'CANCELADA')

    def test_no_cancela_una_confirmada(self):
        reserva = Reserva.objects.create(
            persona=self.persona, libro=self.python, estado='CONFIRMADA', ejemplar=self.python.ejemplares.first(),
            fecha_respuesta=timezone.now(), vence_retiro=timezone.now() + timedelta(hours=48),
            usuario_respuesta=self.bibliotecario,
        )
        respuesta = self.client.post(reverse('portal:cancelar_reserva', args=[reserva.pk]), follow=True)
        self.assertContains(respuesta, 'Solo se puede cancelar una reserva pendiente.')
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, 'CONFIRMADA')

    def test_no_cancela_la_reserva_de_otra_persona(self):
        otra = Persona.objects.create(nombre='Carlos', apellido='Ruiz', documento='40999888', tipo='ALUMNO')
        ajena = Reserva.objects.create(persona=otra, libro=self.python)
        respuesta = self.client.post(reverse('portal:cancelar_reserva', args=[ajena.pk]))
        self.assertEqual(respuesta.status_code, 404)
        ajena.refresh_from_db()
        self.assertEqual(ajena.estado, 'PENDIENTE')


class RestriccionesDeLaBaseTests(ReservasTestCase):
    def test_una_sola_reserva_activa_por_persona_y_libro(self):
        Reserva.objects.create(persona=self.persona, libro=self.python)
        with self.assertRaises(IntegrityError):
            Reserva.objects.create(persona=self.persona, libro=self.python)

    def test_se_puede_volver_a_reservar_despues_de_cancelar(self):
        Reserva.objects.create(persona=self.persona, libro=self.python, estado='CANCELADA')
        Reserva.objects.create(persona=self.persona, libro=self.python)
        self.assertEqual(Reserva.objects.count(), 2)

    def test_un_ejemplar_no_se_aparta_dos_veces(self):
        ejemplar = self.python.ejemplares.first()
        otra = Persona.objects.create(nombre='Carlos', apellido='Ruiz', documento='40999888', tipo='ALUMNO')
        datos = dict(libro=self.python, estado='CONFIRMADA', ejemplar=ejemplar, fecha_respuesta=timezone.now(),
                     vence_retiro=timezone.now() + timedelta(hours=48))
        Reserva.objects.create(persona=self.persona, **datos)
        with self.assertRaises(IntegrityError):
            Reserva.objects.create(persona=otra, **datos)

    def test_cada_estado_con_sus_datos(self):
        ejemplar = self.python.ejemplares.first()
        ahora = timezone.now()
        casos = {
            'pendiente con ejemplar': dict(ejemplar=ejemplar),
            'confirmada sin ejemplar': dict(estado='CONFIRMADA', fecha_respuesta=ahora, vence_retiro=ahora),
            'rechazada sin motivo': dict(estado='RECHAZADA', fecha_respuesta=ahora),
            'retirada sin préstamo': dict(estado='RETIRADA', ejemplar=ejemplar, fecha_respuesta=ahora, vence_retiro=ahora),
        }
        for caso, cambios in casos.items():
            with self.subTest(caso=caso), self.assertRaises(IntegrityError), transaction.atomic():
                Reserva.objects.create(persona=self.persona, libro=self.python, **cambios)


class AccesoTests(ReservasTestCase):
    def test_el_personal_no_reserva_y_sin_sesion_va_al_login(self):
        self.client.force_login(self.bibliotecario)
        self.assertEqual(self.client.post(reverse('portal:reservar', args=[self.python.pk])).status_code, 403)
        self.client.logout()
        respuesta = self.client.post(reverse('portal:reservar', args=[self.python.pk]))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse('login'), respuesta['Location'])
