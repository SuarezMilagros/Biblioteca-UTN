"""Avisos automáticos por correo de los préstamos (Release 2, S8-06).

- "Vence pronto": préstamos sin devolver que vencen dentro de 2 días (o hoy).
- "Venció": préstamos sin devolver con el vencimiento pasado. Se envía una vez.
- Una sola vez por préstamo y tipo; nunca si ya se devolvió; solo a personas con cuenta activa y correo.
- Se puede ejecutar varias veces sin duplicar. Si el correo falla, se reintenta la próxima vez.
"""
import smtplib
from datetime import timedelta
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from biblioteca import avisos
from biblioteca.models import Autor, AvisoPrestamo, Carrera, Categoria, Editorial, Ejemplar, Libro, Persona, Prestamo
from cuentas.lectores import crear_cuenta_de_lector

VENCE_PRONTO = AvisoPrestamo.Tipo.VENCE_PRONTO
VENCIDO = AvisoPrestamo.Tipo.VENCIDO


class AvisosTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bibliotecario = get_user_model().objects.create_user(username='31222333', password='clave-de-prueba-123')
        programacion = Carrera.objects.get(nombre='Tecnicatura Universitaria en Programación')
        cls.libro = Libro.objects.create(
            titulo='Python', categoria=Categoria.objects.create(nombre='Informática'),
            autor=Autor.objects.create(nombre='A', apellido='B'), editorial=Editorial.objects.create(nombre='E'),
        )
        cls.ana = Persona.objects.create(nombre='Ana', apellido='Pérez', documento='40111222', tipo='ALUMNO')
        cls.ana.carreras.add(programacion)
        cls.cuenta_ana = crear_cuenta_de_lector(cls.ana, 'ana.perez@alumnos.example.com')
        cls.sin_cuenta = Persona.objects.create(nombre='Carlos', apellido='Ruiz', documento='40999888', tipo='ALUMNO')

    def setUp(self):
        self.hoy = timezone.localdate()
        self.numero = 0

    def prestar(self, persona=None, vence_en=2, devuelto=False):
        """Préstamo de 14 días que vence dentro de `vence_en` días (negativo: ya venció)."""
        self.numero += 1
        vencimiento = self.hoy + timedelta(days=vence_en)
        inicio = vencimiento - timedelta(days=14)
        return Prestamo.objects.create(
            persona=persona or self.ana, usuario_sistema=self.bibliotecario,
            ejemplar=Ejemplar.objects.create(codigo_inventario=f'PY-{self.numero}', libro=self.libro),
            fecha_prestamo=inicio, fecha_vencimiento=vencimiento,
            fecha_devolucion=self.hoy if devuelto else None,
        )

    def avisos_de(self, prestamo):
        return list(prestamo.avisos.values_list('tipo', flat=True))

    def ejecutar(self, *argumentos):
        salida, errores = StringIO(), StringIO()
        call_command('enviar_avisos', *argumentos, stdout=salida, stderr=errores)
        return salida.getvalue(), errores.getvalue()


class VenceProntoTests(AvisosTestCase):
    def test_avisa_dos_dias_antes(self):
        prestamo = self.prestar(vence_en=2)
        resultado = avisos.enviar_avisos()
        self.assertEqual(resultado.enviados[VENCE_PRONTO], [prestamo])
        self.assertEqual(self.avisos_de(prestamo), [VENCE_PRONTO])
        self.assertEqual(len(mail.outbox), 1)
        correo = mail.outbox[0]
        self.assertEqual(correo.to, ['ana.perez@alumnos.example.com'])
        self.assertEqual(correo.subject, 'Tu préstamo vence pronto: Python')
        self.assertIn('Hola, Ana:', correo.body)
        self.assertIn(f'en 2 días vence el préstamo de "Python" (ejemplar {prestamo.ejemplar.codigo_inventario})', correo.body)
        self.assertIn(f'Fecha de vencimiento: {prestamo.fecha_vencimiento:%d/%m/%Y}', correo.body)

    def test_tres_dias_antes_todavia_no(self):
        prestamo = self.prestar(vence_en=3)
        avisos.enviar_avisos()
        self.assertEqual(self.avisos_de(prestamo), [])
        self.assertEqual(len(mail.outbox), 0)

    def test_si_el_comando_no_corrio_antes_avisa_igual_manana_u_hoy(self):
        manana = self.prestar(vence_en=1)
        hoy = self.prestar(vence_en=0)
        avisos.enviar_avisos()
        self.assertEqual((self.avisos_de(manana), self.avisos_de(hoy)), ([VENCE_PRONTO], [VENCE_PRONTO]))
        cuerpos = sorted(correo.body for correo in mail.outbox)
        self.assertTrue(any('mañana vence el préstamo' in cuerpo for cuerpo in cuerpos))
        self.assertTrue(any('hoy vence el préstamo' in cuerpo for cuerpo in cuerpos))

    def test_un_prestamo_devuelto_no_recibe_avisos(self):
        for vence_en in (2, -3):
            self.prestar(vence_en=vence_en, devuelto=True)
        resultado = avisos.enviar_avisos()
        self.assertEqual(resultado.total_enviados, 0)
        self.assertFalse(AvisoPrestamo.objects.exists())


class VencidoTests(AvisosTestCase):
    def test_avisa_que_vencio_con_los_dias_de_atraso(self):
        prestamo = self.prestar(vence_en=-3)
        avisos.enviar_avisos()
        self.assertEqual(self.avisos_de(prestamo), [VENCIDO])
        correo = mail.outbox[0]
        self.assertEqual(correo.subject, 'Tu préstamo venció: Python')
        self.assertIn(f'venció el {prestamo.fecha_vencimiento:%d/%m/%Y} (hace 3 días)', correo.body)

    def test_un_dia_de_atraso_en_singular(self):
        self.prestar(vence_en=-1)
        avisos.enviar_avisos()
        self.assertIn('(hace 1 día)', mail.outbox[0].body)

    def test_un_vencido_no_recibe_vence_pronto(self):
        prestamo = self.prestar(vence_en=-1)
        avisos.enviar_avisos()
        self.assertEqual(self.avisos_de(prestamo), [VENCIDO])
        self.assertEqual(len(mail.outbox), 1)

    def test_el_aviso_de_vencido_no_se_repite_los_dias_siguientes(self):
        prestamo = self.prestar(vence_en=-1)
        avisos.enviar_avisos()
        avisos.enviar_avisos(hoy=self.hoy + timedelta(days=5))
        self.assertEqual(self.avisos_de(prestamo), [VENCIDO])
        self.assertEqual(len(mail.outbox), 1)

    def test_primero_vence_pronto_y_despues_vencido(self):
        prestamo = self.prestar(vence_en=2)
        avisos.enviar_avisos()
        avisos.enviar_avisos(hoy=self.hoy + timedelta(days=1))
        avisos.enviar_avisos(hoy=self.hoy + timedelta(days=3))
        self.assertEqual(sorted(self.avisos_de(prestamo)), sorted([VENCE_PRONTO, VENCIDO]))
        self.assertEqual([correo.subject.split(':')[0] for correo in mail.outbox],
                         ['Tu préstamo vence pronto', 'Tu préstamo venció'])

    def test_si_lo_devuelve_despues_del_primer_aviso_no_recibe_el_segundo(self):
        prestamo = self.prestar(vence_en=2)
        avisos.enviar_avisos()
        Prestamo.objects.filter(pk=prestamo.pk).update(fecha_devolucion=self.hoy)
        avisos.enviar_avisos(hoy=self.hoy + timedelta(days=3))
        self.assertEqual(self.avisos_de(prestamo), [VENCE_PRONTO])
        self.assertEqual(len(mail.outbox), 1)


class DestinatariosTests(AvisosTestCase):
    def test_sin_cuenta_no_se_avisa_y_se_informa(self):
        prestamo = self.prestar(persona=self.sin_cuenta, vence_en=-2)
        resultado = avisos.enviar_avisos()
        self.assertEqual(resultado.sin_correo, [prestamo])
        self.assertEqual(self.avisos_de(prestamo), [])
        self.assertEqual(len(mail.outbox), 0)

    def test_cuenta_sin_correo(self):
        get_user_model().objects.filter(pk=self.cuenta_ana.pk).update(email='')
        prestamo = self.prestar(vence_en=1)
        resultado = avisos.enviar_avisos()
        self.assertEqual(resultado.sin_correo, [prestamo])
        self.assertEqual(len(mail.outbox), 0)

    def test_persona_dada_de_baja_no_recibe_avisos(self):
        prestamo = self.prestar(vence_en=1)
        self.ana.activo = False
        self.ana.save()
        self.assertFalse(get_user_model().objects.get(pk=self.cuenta_ana.pk).is_active)
        resultado = avisos.enviar_avisos()
        self.assertEqual(resultado.sin_correo, [prestamo])
        self.assertEqual(len(mail.outbox), 0)

    def test_si_despues_le_crean_la_cuenta_recibe_el_aviso(self):
        prestamo = self.prestar(persona=self.sin_cuenta, vence_en=-2)
        avisos.enviar_avisos()
        self.sin_cuenta.carreras.add(Carrera.objects.get(nombre='Tecnicatura Universitaria en Programación'))
        crear_cuenta_de_lector(self.sin_cuenta, 'carlos.ruiz@alumnos.example.com')
        avisos.enviar_avisos()
        self.assertEqual(self.avisos_de(prestamo), [VENCIDO])
        self.assertEqual(mail.outbox[0].to, ['carlos.ruiz@alumnos.example.com'])


class SinDuplicadosTests(AvisosTestCase):
    def test_criterio_de_aceptacion_dos_ejecuciones_el_mismo_dia(self):
        self.prestar(vence_en=2)
        self.prestar(vence_en=-4)
        self.ejecutar()
        self.ejecutar()
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(AvisoPrestamo.objects.count(), 2)

    def test_cada_prestamo_recibe_su_aviso(self):
        self.prestar(vence_en=2)
        self.prestar(vence_en=1)
        avisos.enviar_avisos()
        self.assertEqual(len(mail.outbox), 2)

    def test_si_otra_ejecucion_lo_registro_a_la_vez_no_se_envia_dos_veces(self):
        prestamo = self.prestar(vence_en=-1)
        original = avisos.prestamos_para_avisar

        def con_otra_ejecucion(tipo, hoy):
            prestamos = list(original(tipo, hoy))
            if tipo == VENCIDO:
                # Otra ejecución registra el aviso entre la consulta y el envío.
                AvisoPrestamo.objects.create(prestamo=prestamo, tipo=VENCIDO)
            return prestamos

        with mock.patch('biblioteca.avisos.prestamos_para_avisar', side_effect=con_otra_ejecucion):
            resultado = avisos.enviar_avisos()
        self.assertEqual(resultado.total_enviados, 0)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(AvisoPrestamo.objects.count(), 1)

    def test_la_base_no_admite_dos_avisos_iguales(self):
        prestamo = self.prestar(vence_en=1)
        AvisoPrestamo.objects.create(prestamo=prestamo, tipo=VENCE_PRONTO)
        with self.assertRaises(IntegrityError), transaction.atomic():
            AvisoPrestamo.objects.create(prestamo=prestamo, tipo=VENCE_PRONTO)
        AvisoPrestamo.objects.create(prestamo=prestamo, tipo=VENCIDO)

    def test_si_el_correo_falla_no_se_registra_y_se_reintenta(self):
        prestamo = self.prestar(vence_en=1)
        with mock.patch('biblioteca.avisos.EmailMessage.send', side_effect=smtplib.SMTPException('caído')):
            resultado = avisos.enviar_avisos()
        self.assertEqual(resultado.fallidos, [prestamo])
        self.assertEqual(self.avisos_de(prestamo), [])
        avisos.enviar_avisos()
        self.assertEqual(self.avisos_de(prestamo), [VENCE_PRONTO])
        self.assertEqual(len(mail.outbox), 1)

    def test_un_error_de_conexion_tambien_se_reintenta(self):
        prestamo = self.prestar(vence_en=1)
        with mock.patch('biblioteca.avisos.EmailMessage.send', side_effect=ConnectionRefusedError()):
            resultado = avisos.enviar_avisos()
        self.assertEqual(resultado.fallidos, [prestamo])
        self.assertEqual(self.avisos_de(prestamo), [])


class ComandoTests(AvisosTestCase):
    def test_resumen_de_lo_enviado(self):
        self.prestar(vence_en=2)
        vencido = self.prestar(vence_en=-1)
        self.prestar(persona=self.sin_cuenta, vence_en=1)
        salida, errores = self.ejecutar()
        self.assertIn('Enviados "Vence pronto": 1', salida)
        self.assertIn('Enviados "Venció": 1', salida)
        self.assertIn(f'Pérez, Ana (40111222) · {vencido.ejemplar.codigo_inventario} "Python"', salida)
        self.assertIn('Sin cuenta activa o sin correo (no se avisa): 1', salida)
        self.assertIn('Ruiz, Carlos (40999888)', salida)
        self.assertIn('Total: 2 avisos enviados.', salida)
        self.assertEqual(errores, '')

    def test_sin_nada_para_avisar(self):
        salida, _ = self.ejecutar()
        self.assertIn('Enviados "Vence pronto": 0', salida)
        self.assertIn('Total: 0 avisos enviados.', salida)

    def test_un_solo_aviso_en_singular(self):
        self.prestar(vence_en=2)
        salida, _ = self.ejecutar()
        self.assertIn('Total: 1 aviso enviado.', salida)

    def test_simular_no_envia_ni_registra(self):
        self.prestar(vence_en=2)
        salida, _ = self.ejecutar('--simular')
        self.assertIn('MODO SIMULACIÓN', salida)
        self.assertIn('Se enviarían "Vence pronto": 1', salida)
        self.assertIn('Total: 1 aviso para enviar.', salida)
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(AvisoPrestamo.objects.exists())

    def test_informa_los_que_fallaron(self):
        self.prestar(vence_en=1)
        with mock.patch('biblioteca.avisos.EmailMessage.send', side_effect=smtplib.SMTPException('caído')):
            salida, errores = self.ejecutar()
        self.assertIn('No se pudieron enviar: 1. Se van a reintentar la próxima vez.', errores)
        self.assertIn('Pérez, Ana', errores)
        self.assertIn('Total: 0 avisos enviados.', salida)
