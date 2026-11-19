"""Reservas de libros físicos, lado del personal (Release 2, S8-03).

- El personal ve las reservas pendientes, las que esperan retiro y las anteriores.
- Confirma una pendiente apartando un ejemplar disponible por 48 horas, o la rechaza con un motivo.
- En los dos casos se le avisa a la persona por correo; si el correo falla, la reserva queda igual.
- Al retirar se registra el préstamo de siempre. Una confirmada se puede liberar.
- Pasadas las 48 horas, la reserva vence sola y el ejemplar vuelve a estar disponible.
- Un ejemplar apartado no está disponible: no se presta a otra persona ni se da de baja.
"""
import smtplib
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from biblioteca import reservas as reglas
from biblioteca.models import (
    Autor, Carrera, Categoria, Editorial, Ejemplar, Libro, Persona, Prestamo, Reserva,
)
from cuentas.lectores import crear_cuenta_de_lector
from cuentas.roles import BIBLIOTECARIO

CLAVE = 'clave-de-prueba-123'


class ReservasPersonalTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bibliotecario = get_user_model().objects.create_user(
            username='31222333', email='bibliotecario@example.com', password=CLAVE,
            first_name='Laura', last_name='Gómez',
        )
        cls.bibliotecario.groups.add(Group.objects.get(name=BIBLIOTECARIO))
        programacion = Carrera.objects.get(nombre='Tecnicatura Universitaria en Programación')
        informatica = Categoria.objects.create(nombre='Informática')
        informatica.carreras.add(programacion)
        datos = {'autor': Autor.objects.create(nombre='A', apellido='B'), 'editorial': Editorial.objects.create(nombre='E')}
        cls.python = Libro.objects.create(titulo='Python', categoria=informatica, **datos)
        cls.java = Libro.objects.create(titulo='Java', categoria=informatica, **datos)
        cls.py1 = Ejemplar.objects.create(codigo_inventario='PY-1', libro=cls.python)
        cls.py2 = Ejemplar.objects.create(codigo_inventario='PY-2', libro=cls.python)
        cls.jv1 = Ejemplar.objects.create(codigo_inventario='JV-1', libro=cls.java)
        cls.ana = Persona.objects.create(nombre='Ana', apellido='Pérez', documento='40111222', tipo='ALUMNO')
        cls.ana.carreras.add(programacion)
        cls.cuenta_ana = crear_cuenta_de_lector(cls.ana, 'ana.perez@alumnos.example.com')
        cls.carlos = Persona.objects.create(nombre='Carlos', apellido='Ruiz', documento='40999888', tipo='ALUMNO')
        cls.carlos.carreras.add(programacion)

    def setUp(self):
        self.client.force_login(self.bibliotecario)

    def pendiente(self, persona=None, libro=None):
        return Reserva.objects.create(persona=persona or self.ana, libro=libro or self.python)

    def confirmada(self, persona=None, ejemplar=None, horas_restantes=48):
        ejemplar = ejemplar or self.py1
        ahora = timezone.now()
        return Reserva.objects.create(
            persona=persona or self.ana, libro=ejemplar.libro, ejemplar=ejemplar, estado='CONFIRMADA',
            usuario_respuesta=self.bibliotecario, fecha_respuesta=ahora - timedelta(hours=1),
            vence_retiro=ahora + timedelta(hours=horas_restantes),
        )

    def post(self, nombre, reserva, **datos):
        return self.client.post(reverse(f'biblioteca:{nombre}', args=[reserva.pk]), datos, follow=True)

    def recargar(self, reserva):
        reserva.refresh_from_db()
        return reserva


class ListaTests(ReservasPersonalTestCase):
    def test_por_defecto_muestra_las_pendientes_con_los_ejemplares_disponibles(self):
        self.pendiente()
        self.confirmada(persona=self.carlos, ejemplar=self.jv1)
        respuesta = self.client.get(reverse('biblioteca:reserva_list'))
        self.assertEqual(respuesta.context['estado'], 'pendientes')
        reservas = list(respuesta.context['reservas'])
        self.assertEqual([r.persona for r in reservas], [self.ana])
        self.assertEqual(reservas[0].disponibles, 2)
        self.assertContains(respuesta, 'Responder')

    def test_una_pendiente_sin_ejemplares_disponibles_lo_dice(self):
        self.pendiente(libro=self.java)
        self.confirmada(persona=self.carlos, ejemplar=self.jv1)
        Reserva.objects.filter(persona=self.carlos).update(libro=self.java)
        respuesta = self.client.get(reverse('biblioteca:reserva_list'))
        self.assertEqual(list(respuesta.context['reservas'])[0].disponibles, 0)
        self.assertContains(respuesta, 'Ninguno')

    def test_las_pendientes_van_de_la_mas_antigua_a_la_mas_nueva(self):
        nueva = self.pendiente()
        vieja = self.pendiente(persona=self.carlos)
        Reserva.objects.filter(pk=vieja.pk).update(fecha_reserva=timezone.now() - timedelta(days=1))
        respuesta = self.client.get(reverse('biblioteca:reserva_list'))
        self.assertEqual([r.pk for r in respuesta.context['reservas']], [vieja.pk, nueva.pk])

    def test_para_retirar_muestra_las_confirmadas_vigentes(self):
        self.pendiente(persona=self.carlos)
        reserva = self.confirmada()
        respuesta = self.client.get(reverse('biblioteca:reserva_list') + '?estado=para_retirar')
        self.assertEqual(list(respuesta.context['reservas']), [reserva])
        self.assertContains(respuesta, 'PY-1')

    def test_anteriores_muestra_las_terminadas(self):
        self.pendiente(persona=self.carlos)
        rechazada = Reserva.objects.create(
            persona=self.ana, libro=self.java, estado='RECHAZADA', motivo_rechazo='No hay',
            usuario_respuesta=self.bibliotecario, fecha_respuesta=timezone.now(),
        )
        respuesta = self.client.get(reverse('biblioteca:reserva_list') + '?estado=anteriores')
        self.assertEqual(list(respuesta.context['reservas']), [rechazada])
        self.assertContains(respuesta, 'Rechazada')

    def test_un_estado_desconocido_muestra_las_pendientes(self):
        respuesta = self.client.get(reverse('biblioteca:reserva_list') + '?estado=cualquiera')
        self.assertEqual(respuesta.context['estado'], 'pendientes')
        self.assertContains(respuesta, 'No hay reservas pendientes.')

    def test_las_confirmadas_vencidas_pasan_a_anteriores_al_abrir_la_lista(self):
        reserva = self.confirmada(horas_restantes=-1)
        respuesta = self.client.get(reverse('biblioteca:reserva_list') + '?estado=para_retirar')
        self.assertEqual(list(respuesta.context['reservas']), [])
        self.assertEqual(self.recargar(reserva).estado, 'VENCIDA')

    def test_las_pestanas_cuentan_pendientes_y_para_retirar(self):
        self.pendiente()
        self.pendiente(persona=self.carlos)
        self.confirmada(persona=self.carlos, ejemplar=self.jv1)
        respuesta = self.client.get(reverse('biblioteca:reserva_list'))
        self.assertEqual((respuesta.context['cantidad_pendientes'], respuesta.context['cantidad_para_retirar']), (2, 1))


class ConfirmarTests(ReservasPersonalTestCase):
    def test_confirma_apartando_el_ejemplar_por_48_horas_y_avisa_por_correo(self):
        reserva = self.pendiente()
        antes = timezone.now()
        respuesta = self.post('reserva_confirmar', reserva, ejemplar=self.py2.pk)
        reserva = self.recargar(reserva)
        self.assertEqual((reserva.estado, reserva.ejemplar, reserva.usuario_respuesta), ('CONFIRMADA', self.py2, self.bibliotecario))
        self.assertGreaterEqual(reserva.vence_retiro, antes + timedelta(hours=48))
        self.assertLessEqual(reserva.vence_retiro, timezone.now() + timedelta(hours=48))
        self.assertContains(respuesta, 'Reserva confirmada: se apartó PY-2')
        self.assertContains(respuesta, 'Se le avisó por correo.')
        self.assertEqual(len(mail.outbox), 1)
        correo = mail.outbox[0]
        self.assertEqual(correo.to, ['ana.perez@alumnos.example.com'])
        self.assertEqual(correo.subject, 'Tu reserva está lista para retirar: Python')
        self.assertIn('PY-2', correo.body)
        self.assertIn(timezone.localtime(reserva.vence_retiro).strftime('%d/%m/%Y'), correo.body)

    def test_el_ejemplar_apartado_deja_de_estar_disponible(self):
        reserva = self.pendiente()
        self.post('reserva_confirmar', reserva, ejemplar=self.py1.pk)
        self.assertFalse(Ejemplar.objects.get(pk=self.py1.pk).disponible)
        self.assertTrue(Ejemplar.objects.get(pk=self.py1.pk).apartado)
        self.assertEqual(list(Ejemplar.objects.disponibles().filter(libro=self.python)), [self.py2])
        self.assertEqual(Libro.objects.con_disponibilidad().get(pk=self.python.pk).ejemplares_disponibles, 1)

    def test_no_aparta_un_ejemplar_ya_apartado(self):
        self.confirmada(persona=self.carlos, ejemplar=self.py1)
        reserva = self.pendiente()
        respuesta = self.post('reserva_confirmar', reserva, ejemplar=self.py1.pk)
        self.assertContains(respuesta, 'Ese ejemplar ya no está disponible. Elegí otro.')
        self.assertEqual(self.recargar(reserva).estado, 'PENDIENTE')
        self.assertEqual(len(mail.outbox), 0)

    def test_no_aparta_un_ejemplar_prestado(self):
        Prestamo.objects.create(
            persona=self.carlos, ejemplar=self.py1, usuario_sistema=self.bibliotecario,
            fecha_prestamo=timezone.localdate(), fecha_vencimiento=timezone.localdate() + timedelta(days=14),
        )
        reserva = self.pendiente()
        respuesta = self.post('reserva_confirmar', reserva, ejemplar=self.py1.pk)
        self.assertContains(respuesta, 'Ese ejemplar ya no está disponible.')
        self.assertEqual(self.recargar(reserva).estado, 'PENDIENTE')

    def test_no_aparta_un_ejemplar_de_otro_libro(self):
        reserva = self.pendiente()
        respuesta = self.post('reserva_confirmar', reserva, ejemplar=self.jv1.pk)
        self.assertContains(respuesta, 'Ese ejemplar no es del libro reservado.')
        self.assertEqual(self.recargar(reserva).estado, 'PENDIENTE')

    def test_no_confirma_dos_veces(self):
        reserva = self.pendiente()
        self.post('reserva_confirmar', reserva, ejemplar=self.py1.pk)
        respuesta = self.post('reserva_confirmar', reserva, ejemplar=self.py2.pk)
        self.assertContains(respuesta, 'Esta reserva ya no está pendiente.')
        self.assertEqual(self.recargar(reserva).ejemplar, self.py1)

    def test_sin_ejemplar_elegido_responde_404(self):
        reserva = self.pendiente()
        respuesta = self.client.post(reverse('biblioteca:reserva_confirmar', args=[reserva.pk]))
        self.assertEqual(respuesta.status_code, 404)

    def test_si_dos_confirman_el_mismo_ejemplar_a_la_vez_la_base_lo_impide(self):
        self.confirmada(persona=self.carlos, ejemplar=self.py1)
        reserva = self.pendiente()
        with mock.patch.object(reglas, 'ejemplares_para_apartar', return_value=Ejemplar.objects.all()):
            with self.assertRaisesMessage(reglas.ReservaNoPermitida, 'acaba de quedar apartado para otra reserva'):
                reglas.confirmar(reserva, self.py1, self.bibliotecario)
        self.assertEqual(self.recargar(reserva).estado, 'PENDIENTE')

    def test_si_el_correo_falla_la_reserva_queda_confirmada_y_lo_advierte(self):
        reserva = self.pendiente()
        with mock.patch('biblioteca.reservas.send_mail', side_effect=smtplib.SMTPException('caído')):
            respuesta = self.post('reserva_confirmar', reserva, ejemplar=self.py1.pk)
        self.assertEqual(self.recargar(reserva).estado, 'CONFIRMADA')
        self.assertContains(respuesta, 'No se pudo enviar el correo de aviso.')

    def test_si_la_persona_no_tiene_cuenta_pide_avisarle_por_otro_medio(self):
        reserva = self.pendiente(persona=self.carlos)
        respuesta = self.post('reserva_confirmar', reserva, ejemplar=self.py1.pk)
        self.assertEqual(self.recargar(reserva).estado, 'CONFIRMADA')
        self.assertContains(respuesta, 'La persona no tiene cuenta: avisale por otro medio.')
        self.assertEqual(len(mail.outbox), 0)


class RechazarTests(ReservasPersonalTestCase):
    def test_rechaza_con_motivo_y_avisa_por_correo(self):
        reserva = self.pendiente()
        respuesta = self.post('reserva_rechazar', reserva, motivo='  El libro está en reparación.  ')
        reserva = self.recargar(reserva)
        self.assertEqual((reserva.estado, reserva.motivo_rechazo), ('RECHAZADA', 'El libro está en reparación.'))
        self.assertEqual(reserva.usuario_respuesta, self.bibliotecario)
        self.assertIsNotNone(reserva.fecha_respuesta)
        self.assertContains(respuesta, 'Reserva de &quot;Pérez, Ana&quot; rechazada.')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'Tu reserva no pudo aceptarse: Python')
        self.assertIn('Motivo: El libro está en reparación.', mail.outbox[0].body)

    def test_sin_motivo_no_rechaza(self):
        reserva = self.pendiente()
        respuesta = self.post('reserva_rechazar', reserva, motivo='   ')
        self.assertContains(respuesta, 'Escribí el motivo del rechazo')
        self.assertEqual(self.recargar(reserva).estado, 'PENDIENTE')
        self.assertEqual(len(mail.outbox), 0)

    def test_no_rechaza_una_confirmada(self):
        reserva = self.confirmada()
        respuesta = self.post('reserva_rechazar', reserva, motivo='No')
        self.assertContains(respuesta, 'Esta reserva ya no está pendiente.')
        self.assertEqual(self.recargar(reserva).estado, 'CONFIRMADA')

    def test_el_lector_ve_el_motivo_en_su_perfil(self):
        reserva = self.pendiente()
        self.post('reserva_rechazar', reserva, motivo='No hay ejemplares en condiciones.')
        self.client.force_login(self.cuenta_ana)
        self.assertContains(self.client.get(reverse('portal:mis_reservas')), 'No hay ejemplares en condiciones.')


class RetirarYLiberarTests(ReservasPersonalTestCase):
    def test_al_retirar_se_registra_el_prestamo(self):
        reserva = self.confirmada()
        respuesta = self.post('reserva_retirar', reserva)
        reserva = self.recargar(reserva)
        self.assertEqual(reserva.estado, 'RETIRADA')
        prestamo = reserva.prestamo
        hoy = timezone.localdate()
        self.assertEqual((prestamo.persona, prestamo.ejemplar, prestamo.usuario_sistema), (self.ana, self.py1, self.bibliotecario))
        self.assertEqual((prestamo.fecha_prestamo, prestamo.fecha_vencimiento), (hoy, Prestamo.calcular_vencimiento(hoy)))
        self.assertContains(respuesta, 'Préstamo registrado: PY-1')
        self.assertTrue(Ejemplar.objects.get(pk=self.py1.pk).prestado)
        self.assertFalse(Ejemplar.objects.get(pk=self.py1.pk).apartado)

    def test_no_retira_una_vencida(self):
        reserva = self.confirmada(horas_restantes=-1)
        respuesta = self.post('reserva_retirar', reserva)
        self.assertContains(respuesta, 'Esta reserva no está lista para retirar (puede haber vencido).')
        self.assertEqual(self.recargar(reserva).estado, 'VENCIDA')
        self.assertFalse(Prestamo.objects.exists())

    def test_no_retira_si_la_persona_esta_dada_de_baja(self):
        reserva = self.confirmada(persona=self.carlos)
        Persona.objects.filter(pk=self.carlos.pk).update(activo=False)
        respuesta = self.post('reserva_retirar', reserva)
        self.assertContains(respuesta, 'La persona está dada de baja: no puede recibir préstamos.')
        self.assertEqual(self.recargar(reserva).estado, 'CONFIRMADA')
        self.assertFalse(Prestamo.objects.exists())

    def test_liberar_deja_el_ejemplar_disponible(self):
        reserva = self.confirmada()
        respuesta = self.post('reserva_liberar', reserva)
        reserva = self.recargar(reserva)
        self.assertEqual((reserva.estado, reserva.ejemplar), ('CANCELADA', None))
        self.assertTrue(Ejemplar.objects.get(pk=self.py1.pk).disponible)
        self.assertContains(respuesta, 'el ejemplar vuelve a estar disponible')

    def test_no_libera_una_pendiente(self):
        reserva = self.pendiente()
        respuesta = self.post('reserva_liberar', reserva)
        self.assertContains(respuesta, 'Solo se puede liberar una reserva confirmada.')
        self.assertEqual(self.recargar(reserva).estado, 'PENDIENTE')

    def test_las_acciones_solo_se_aceptan_por_post(self):
        reserva = self.pendiente()
        for nombre in ('reserva_confirmar', 'reserva_rechazar', 'reserva_retirar', 'reserva_liberar'):
            with self.subTest(nombre=nombre):
                self.assertEqual(self.client.get(reverse(f'biblioteca:{nombre}', args=[reserva.pk])).status_code, 405)


class VencimientoTests(ReservasPersonalTestCase):
    def test_una_confirmada_vencida_libera_el_ejemplar_aunque_nadie_la_marque(self):
        reserva = self.confirmada(horas_restantes=-1)
        self.assertEqual(reserva.estado, 'CONFIRMADA')
        self.assertTrue(Ejemplar.objects.get(pk=self.py1.pk).disponible)
        self.assertEqual(Ejemplar.objects.disponibles().filter(libro=self.python).count(), 2)

    def test_vencer_reservas_marca_solo_las_vencidas(self):
        vencida = self.confirmada(horas_restantes=-1)
        vigente = self.confirmada(persona=self.carlos, ejemplar=self.py2)
        pendiente = self.pendiente(libro=self.java)
        self.assertEqual(reglas.vencer_reservas(), 1)
        self.assertEqual(
            [self.recargar(r).estado for r in (vencida, vigente, pendiente)], ['VENCIDA', 'CONFIRMADA', 'PENDIENTE']
        )

    def test_el_perfil_del_lector_la_muestra_vencida(self):
        self.confirmada(horas_restantes=-1)
        self.client.force_login(self.cuenta_ana)
        respuesta = self.client.get(reverse('portal:mis_reservas'))
        self.assertContains(respuesta, 'No se retiró a tiempo.')
        self.assertEqual(Reserva.objects.get().estado, 'VENCIDA')

    def test_el_detalle_del_libro_en_el_portal_actualiza_el_vencimiento(self):
        self.confirmada(horas_restantes=-1)
        self.client.force_login(self.cuenta_ana)
        respuesta = self.client.get(reverse('portal:libro', args=[self.python.pk]))
        self.assertEqual(Reserva.objects.get().estado, 'VENCIDA')
        self.assertIsNone(respuesta.context['reserva_activa'])


class PrestamoDeUnEjemplarApartadoTests(ReservasPersonalTestCase):
    def prestar(self, ejemplar, persona):
        return self.client.post(
            reverse('biblioteca:prestamo_create', args=[ejemplar.pk]),
            {'documento': persona.documento, 'fecha_prestamo': timezone.localdate().isoformat()}, follow=True,
        )

    def test_el_formulario_avisa_que_esta_apartado(self):
        self.confirmada()
        respuesta = self.client.get(reverse('biblioteca:prestamo_create', args=[self.py1.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Este ejemplar está apartado para <strong>Pérez, Ana</strong>')

    def test_no_se_presta_a_otra_persona(self):
        reserva = self.confirmada()
        respuesta = self.prestar(self.py1, self.carlos)
        self.assertContains(respuesta, 'Este ejemplar está apartado para Pérez, Ana hasta el')
        self.assertContains(respuesta, 'Prestá otro ejemplar del libro.')
        self.assertFalse(Prestamo.objects.exists())
        self.assertEqual(self.recargar(reserva).estado, 'CONFIRMADA')

    def test_prestarlo_a_quien_lo_reservo_marca_la_reserva_como_retirada(self):
        reserva = self.confirmada()
        self.prestar(self.py1, self.ana)
        reserva = self.recargar(reserva)
        self.assertEqual(reserva.estado, 'RETIRADA')
        self.assertEqual(reserva.prestamo, Prestamo.objects.get())

    def test_un_prestamo_normal_no_toca_las_reservas_de_otros_ejemplares(self):
        reserva = self.confirmada(ejemplar=self.py2)
        self.prestar(self.py1, self.ana)
        self.assertEqual(self.recargar(reserva).estado, 'CONFIRMADA')

    def test_no_se_da_de_baja(self):
        self.confirmada()
        respuesta = self.client.post(
            reverse('biblioteca:ejemplar_baja', args=[self.py1.pk]), {'motivo_baja': 'PERDIDO'}, follow=True,
        )
        self.assertContains(respuesta, 'está apartado por una reserva. Liberá la reserva primero.')
        self.assertTrue(Ejemplar.objects.get(pk=self.py1.pk).activo)

    def test_la_ficha_del_ejemplar_muestra_para_quien_esta_apartado(self):
        reserva = self.confirmada()
        respuesta = self.client.get(reverse('biblioteca:ejemplar_detail', args=[self.py1.pk]))
        self.assertContains(respuesta, 'Apartado para')
        self.assertContains(respuesta, reverse('biblioteca:reserva_detail', args=[reserva.pk]))
        self.assertContains(respuesta, '<span class="badge badge-info">Apartado</span>', html=True)
        self.assertNotContains(respuesta, 'Dar de baja')

    def test_la_exportacion_csv_lo_marca_apartado(self):
        self.confirmada()
        respuesta = self.client.get(reverse('biblioteca:ejemplar_list') + '?formato=csv')
        filas = [fila.split(';') for fila in respuesta.content.decode('utf-8-sig').splitlines()]
        columna = filas[0].index('Estado')
        estados = {fila[0]: fila[columna] for fila in filas[1:]}
        self.assertEqual(estados, {'JV-1': 'Disponible', 'PY-1': 'Apartado', 'PY-2': 'Disponible'})


class PantallasTests(ReservasPersonalTestCase):
    def test_el_detalle_de_una_pendiente_ofrece_confirmar_y_rechazar(self):
        self.confirmada(persona=self.carlos, ejemplar=self.py1)
        reserva = self.pendiente()
        respuesta = self.client.get(reverse('biblioteca:reserva_detail', args=[reserva.pk]))
        self.assertEqual(list(respuesta.context['ejemplares_para_apartar']), [self.py2])
        self.assertContains(respuesta, 'Confirmar y apartar')
        self.assertContains(respuesta, 'Rechazar reserva')
        self.assertContains(respuesta, '<option value="%d">PY-2</option>' % self.py2.pk, html=True)

    def test_sin_ejemplares_disponibles_solo_se_puede_rechazar(self):
        self.confirmada(persona=self.carlos, ejemplar=self.jv1)
        reserva = self.pendiente(libro=self.java)
        respuesta = self.client.get(reverse('biblioteca:reserva_detail', args=[reserva.pk]))
        self.assertContains(respuesta, 'No hay ejemplares disponibles de este libro ahora.')
        self.assertNotContains(respuesta, 'Confirmar y apartar')
        self.assertContains(respuesta, 'Rechazar reserva')

    def test_avisa_si_la_persona_tiene_prestamos_vencidos(self):
        inicio = timezone.localdate() - timedelta(days=30)
        Prestamo.objects.create(
            persona=self.ana, ejemplar=self.jv1, usuario_sistema=self.bibliotecario,
            fecha_prestamo=inicio, fecha_vencimiento=inicio + timedelta(days=14),
        )
        reserva = self.pendiente()
        respuesta = self.client.get(reverse('biblioteca:reserva_detail', args=[reserva.pk]))
        self.assertContains(respuesta, 'La persona tiene 1 préstamo vencido sin devolver.')

    def test_un_prestamo_al_dia_no_se_cuenta_como_vencido(self):
        hoy = timezone.localdate()
        Prestamo.objects.create(
            persona=self.ana, ejemplar=self.jv1, usuario_sistema=self.bibliotecario,
            fecha_prestamo=hoy, fecha_vencimiento=hoy + timedelta(days=14),
        )
        reserva = self.pendiente()
        respuesta = self.client.get(reverse('biblioteca:reserva_detail', args=[reserva.pk]))
        self.assertEqual(respuesta.context['prestamos_vencidos'], 0)
        self.assertNotContains(respuesta, 'vencido sin devolver')

    def test_el_detalle_de_una_confirmada_ofrece_retirar_y_liberar(self):
        reserva = self.confirmada()
        respuesta = self.client.get(reverse('biblioteca:reserva_detail', args=[reserva.pk]))
        self.assertContains(respuesta, 'Registrar retiro y prestar')
        self.assertContains(respuesta, 'Liberar ejemplar')
        self.assertNotContains(respuesta, 'Rechazar reserva')

    def test_el_detalle_de_una_terminada_no_ofrece_acciones(self):
        reserva = self.confirmada(horas_restantes=-1)
        respuesta = self.client.get(reverse('biblioteca:reserva_detail', args=[reserva.pk]))
        self.assertContains(respuesta, 'Vencida')
        self.assertNotContains(respuesta, '<form method="post" action="/reservas/')

    def test_menu_e_inicio_muestran_las_pendientes(self):
        self.pendiente()
        self.pendiente(persona=self.carlos)
        respuesta = self.client.get(reverse('biblioteca:inicio'))
        self.assertEqual(respuesta.context['reservas_pendientes_total'], 2)
        self.assertEqual(respuesta.context['reservas_pendientes'], 2)
        self.assertContains(respuesta, 'Reservas pendientes')
        self.assertContains(respuesta, f'href="{reverse("biblioteca:reserva_list")}"')

    def test_inicio_no_cuenta_un_apartado_como_disponible(self):
        self.confirmada()
        respuesta = self.client.get(reverse('biblioteca:inicio'))
        self.assertEqual(respuesta.context['ejemplares_disponibles'], 2)

    def test_informes_cuentan_los_apartados(self):
        self.confirmada()
        respuesta = self.client.get(reverse('biblioteca:informes'))
        self.assertEqual(respuesta.context['ejemplares']['apartados'], 1)
        self.assertEqual(respuesta.context['ejemplares']['disponibles'], 2)
        self.assertContains(respuesta, 'Apartados por reservas')

    def test_el_portal_no_cuenta_el_apartado_como_disponible(self):
        self.confirmada(persona=self.carlos)
        self.client.force_login(self.cuenta_ana)
        respuesta = self.client.get(reverse('portal:libro', args=[self.python.pk]))
        self.assertEqual(respuesta.context['libro'].ejemplares_disponibles, 1)


class PermisosTests(ReservasPersonalTestCase):
    def test_con_solo_ver_no_responde(self):
        usuario = get_user_model().objects.create_user(username='consulta', password=CLAVE)
        usuario.user_permissions.add(Permission.objects.get(codename='view_reserva'))
        self.client.force_login(usuario)
        reserva = self.pendiente()
        self.assertContains(self.client.get(reverse('biblioteca:reserva_list')), 'Ver')
        respuesta = self.client.get(reverse('biblioteca:reserva_detail', args=[reserva.pk]))
        self.assertNotContains(respuesta, 'Confirmar y apartar')
        self.assertEqual(
            self.client.post(reverse('biblioteca:reserva_confirmar', args=[reserva.pk]), {'ejemplar': self.py1.pk}).status_code,
            403,
        )
        self.assertEqual(self.recargar(reserva).estado, 'PENDIENTE')

    def test_sin_permiso_es_403_antes_de_buscar_la_reserva(self):
        usuario = get_user_model().objects.create_user(username='sinpermisos', password=CLAVE)
        self.client.force_login(usuario)
        self.assertEqual(self.client.get(reverse('biblioteca:reserva_detail', args=[999])).status_code, 403)
        self.assertEqual(self.client.post(reverse('biblioteca:reserva_retirar', args=[999])).status_code, 403)

    def test_el_menu_muestra_reservas_solo_con_permiso(self):
        self.assertContains(self.client.get(reverse('biblioteca:inicio')), f'href="{reverse("biblioteca:reserva_list")}"')
        usuario = get_user_model().objects.create_user(username='sinpermisos', password=CLAVE)
        self.client.force_login(usuario)
        self.assertNotContains(self.client.get(reverse('biblioteca:inicio')), 'Reservas')
