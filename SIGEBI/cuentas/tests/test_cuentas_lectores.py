"""Cuentas de estudiantes y docentes (Release 2, S7-03).

- El Bibliotecario o el Administrativo crean la cuenta desde la ficha de la Persona.
- La persona tiene que estar activa y tener al menos una carrera; una persona no tiene dos cuentas.
- El usuario es el documento; no hay contraseña hasta que la persona la define desde el correo.
- La cuenta refleja a la persona: baja, reactivación y cambios de nombre o documento.
- Las cuentas de lectores no aparecen ni se editan en la pantalla Cuentas del personal.
"""
import smtplib
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from biblioteca.models import Carrera, Persona
from cuentas.models import IntentoDeAcceso
from cuentas.roles import ADMINISTRATIVO, BIBLIOTECARIO, LECTOR

CLAVE = 'clave-de-prueba-123'
CORREO = 'ana.perez@alumnos.example.com'


def crear_personal(documento, correo, rol):
    usuario = get_user_model().objects.create_user(username=documento, email=correo, password=CLAVE)
    usuario.groups.add(Group.objects.get(name=rol))
    return usuario


class CuentasDeLectoresTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bibliotecario = crear_personal('31222333', 'bibliotecario@example.com', BIBLIOTECARIO)
        cls.programacion = Carrera.objects.get(nombre='Tecnicatura Universitaria en Programación')
        cls.persona = Persona.objects.create(
            nombre='Ana', apellido='Pérez', documento='40111222', tipo=Persona.Tipo.ALUMNO
        )
        cls.persona.carreras.add(cls.programacion)

    def setUp(self):
        self.client.force_login(self.bibliotecario)

    def url_crear(self, persona=None):
        return reverse('biblioteca:persona_cuenta_create', args=[(persona or self.persona).pk])

    def crear(self, correo=CORREO, persona=None):
        return self.client.post(self.url_crear(persona), {'correo': correo})


class CrearCuentaTests(CuentasDeLectoresTestCase):
    def test_el_rol_lector_no_tiene_permisos(self):
        self.assertFalse(Group.objects.get(name=LECTOR).permissions.exists())

    def test_crea_la_cuenta_y_envia_el_correo(self):
        respuesta = self.crear()
        self.assertRedirects(respuesta, reverse('biblioteca:persona_detail', args=[self.persona.pk]))
        self.persona.refresh_from_db()
        cuenta = self.persona.cuenta
        self.assertEqual((cuenta.username, cuenta.email), ('40111222', CORREO))
        self.assertEqual((cuenta.first_name, cuenta.last_name), ('Ana', 'Pérez'))
        self.assertFalse(cuenta.has_usable_password())
        self.assertEqual(list(cuenta.groups.values_list('name', flat=True)), [LECTOR])
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [CORREO])
        self.assertIn('/accounts/reset/', mail.outbox[0].body)

    def test_el_administrativo_tambien_puede(self):
        self.client.force_login(crear_personal('32333444', 'administrativo@example.com', ADMINISTRATIVO))
        self.crear()
        self.persona.refresh_from_db()
        self.assertIsNotNone(self.persona.cuenta)

    def test_sin_rol_o_sin_sesion_no_puede(self):
        sin_rol = get_user_model().objects.create_user(username='30111222', email='x@example.com', password=CLAVE)
        self.client.force_login(sin_rol)
        self.assertEqual(self.client.get(self.url_crear()).status_code, 403)
        self.assertEqual(self.crear().status_code, 403)
        self.client.logout()
        respuesta = self.client.get(self.url_crear())
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse('login'), respuesta['Location'])
        self.persona.refresh_from_db()
        self.assertIsNone(self.persona.cuenta)

    def test_permisos_antes_de_buscar_la_persona(self):
        # Sin sesión: siempre al login, aunque la persona no exista o ya tenga cuenta.
        self.client.logout()
        for pk in (99999, self.persona.pk):
            with self.subTest(pk=pk):
                respuesta = self.client.get(reverse('biblioteca:persona_cuenta_create', args=[pk]))
                self.assertEqual(respuesta.status_code, 302)
                self.assertIn(reverse('login'), respuesta['Location'])
        # Sin rol: 403 aunque la persona ya tenga cuenta (no se revela nada).
        self.persona.cuenta = get_user_model().objects.create_user(username='40111222', email=CORREO)
        self.persona.save()
        sin_rol = get_user_model().objects.create_user(username='30111222', email='x@example.com', password=CLAVE)
        self.client.force_login(sin_rol)
        self.assertEqual(self.client.get(self.url_crear()).status_code, 403)

    def test_persona_sin_carrera(self):
        sin_carrera = Persona.objects.create(nombre='Luis', apellido='Gómez', documento='40222333', tipo='ALUMNO')
        respuesta = self.crear(persona=sin_carrera)
        self.assertContains(respuesta, 'No tiene ninguna carrera asignada')
        self.assertFalse(get_user_model().objects.filter(username='40222333').exists())

    def test_persona_dada_de_baja(self):
        Persona.objects.filter(pk=self.persona.pk).update(activo=False)
        respuesta = self.crear()
        self.assertContains(respuesta, 'Está dada de baja.')
        self.assertFalse(get_user_model().objects.filter(username='40111222').exists())

    def test_correo_repetido_sin_distinguir_mayusculas(self):
        respuesta = self.crear(correo='BIBLIOTECARIO@example.com')
        self.assertContains(respuesta, 'Ya existe una cuenta con ese correo.')

    def test_documento_que_ya_usa_una_cuenta_del_personal(self):
        bibliotecario_alumno = Persona.objects.create(
            nombre='Bruno', apellido='Díaz', documento='31222333', tipo='ALUMNO'
        )
        bibliotecario_alumno.carreras.add(self.programacion)
        respuesta = self.crear(correo='bruno@alumnos.example.com', persona=bibliotecario_alumno)
        self.assertContains(respuesta, 'Ya existe una cuenta del sistema con el documento 31222333.')

    def test_una_persona_no_tiene_dos_cuentas(self):
        self.crear()
        respuesta = self.client.get(self.url_crear())
        self.assertRedirects(respuesta, reverse('biblioteca:persona_detail', args=[self.persona.pk]))
        self.assertEqual(get_user_model().objects.filter(persona__isnull=False).count(), 1)

    def test_si_falla_el_correo_la_cuenta_se_crea_igual(self):
        with mock.patch('biblioteca.views.enviar_correo_definicion', side_effect=smtplib.SMTPException):
            respuesta = self.crear()
        self.persona.refresh_from_db()
        self.assertIsNotNone(self.persona.cuenta)
        self.assertContains(self.client.get(respuesta['Location']), 'no se pudo enviar el correo')

    def test_persona_inexistente(self):
        respuesta = self.client.get(reverse('biblioteca:persona_cuenta_create', args=[99999]))
        self.assertEqual(respuesta.status_code, 404)


class FichaDeLaPersonaTests(CuentasDeLectoresTestCase):
    def ficha(self):
        return self.client.get(reverse('biblioteca:persona_detail', args=[self.persona.pk]))

    def test_sin_cuenta_ofrece_crearla(self):
        self.assertContains(self.ficha(), self.url_crear())

    def test_sin_carrera_explica_que_falta(self):
        self.persona.carreras.clear()
        respuesta = self.ficha()
        self.assertNotContains(respuesta, self.url_crear())
        self.assertContains(respuesta, 'No tiene ninguna carrera asignada')

    def test_con_cuenta_muestra_el_correo_y_el_estado(self):
        self.crear()
        respuesta = self.ficha()
        self.assertContains(respuesta, CORREO)
        self.assertContains(respuesta, 'Falta definir la contraseña')
        self.assertContains(respuesta, 'Reenviar correo')

    def test_reenviar_el_correo(self):
        self.crear()
        self.client.post(reverse('biblioteca:persona_cuenta_reenviar', args=[self.persona.pk]))
        self.assertEqual(len(mail.outbox), 2)

    def test_no_reenvia_si_ya_definio_la_contrasena(self):
        self.crear()
        cuenta = get_user_model().objects.get(username='40111222')
        cuenta.set_password('clave-propia-456')
        cuenta.save()
        self.client.post(reverse('biblioteca:persona_cuenta_reenviar', args=[self.persona.pk]))
        self.assertEqual(len(mail.outbox), 1)
        self.assertContains(self.ficha(), 'Activa')


class LaCuentaReflejaALaPersonaTests(CuentasDeLectoresTestCase):
    def setUp(self):
        super().setUp()
        self.crear()
        self.persona.refresh_from_db()

    def cuenta(self):
        return get_user_model().objects.get(pk=self.persona.cuenta_id)

    def test_la_baja_desactiva_la_cuenta_y_la_reactivacion_la_activa(self):
        self.client.post(reverse('biblioteca:persona_baja', args=[self.persona.pk]))
        self.assertFalse(self.cuenta().is_active)
        self.client.post(reverse('biblioteca:persona_reactivar', args=[self.persona.pk]))
        self.assertTrue(self.cuenta().is_active)

    def test_corregir_nombre_y_documento_actualiza_la_cuenta(self):
        self.client.post(reverse('biblioteca:persona_update', args=[self.persona.pk]), {
            'nombre': 'Ana María', 'apellido': 'Pérez', 'documento': '40.111.223', 'tipo': 'ALUMNO', 'legajo': '',
            'carreras': [self.programacion.pk],
        })
        cuenta = self.cuenta()
        self.assertEqual((cuenta.username, cuenta.first_name), ('40111223', 'Ana María'))

    def test_el_documento_no_puede_ser_el_de_otra_cuenta(self):
        respuesta = self.client.post(reverse('biblioteca:persona_update', args=[self.persona.pk]), {
            'nombre': 'Ana', 'apellido': 'Pérez', 'documento': '31222333', 'tipo': 'ALUMNO', 'legajo': '',
            'carreras': [self.programacion.pk],
        })
        self.assertContains(respuesta, 'Ya existe una cuenta del sistema con ese documento.')
        self.assertEqual(self.cuenta().username, '40111222')


class PantallaCuentasDelPersonalTests(CuentasDeLectoresTestCase):
    def setUp(self):
        super().setUp()
        self.crear()
        self.lector = get_user_model().objects.get(username='40111222')
        self.superusuario = get_user_model().objects.create_superuser(
            username='20111222', email='admin@example.com', password=CLAVE
        )
        self.client.force_login(self.superusuario)

    def test_los_lectores_no_aparecen_en_cuentas(self):
        respuesta = self.client.get(reverse('cuentas:usuario_list'))
        self.assertNotIn(self.lector, respuesta.context['usuarios'])
        self.assertIn(self.bibliotecario, respuesta.context['usuarios'])

    def test_ni_el_superusuario_edita_un_lector_desde_cuentas(self):
        respuesta = self.client.get(reverse('cuentas:usuario_update', args=[self.lector.pk]))
        self.assertEqual(respuesta.status_code, 403)

    def test_la_cabecera_muestra_el_rol_lector(self):
        self.lector.set_password(CLAVE)
        self.lector.save()
        self.client.force_login(self.lector)
        respuesta = self.client.get(reverse('password_change'))
        self.assertEqual(respuesta.context['rol_usuario'], LECTOR)


class IntentoDeAccesoTests(TestCase):
    def test_se_muestra_con_su_tipo_y_correo(self):
        intento = IntentoDeAcceso(tipo=IntentoDeAcceso.Tipo.INGRESO_FALLIDO, correo='x@example.com')
        self.assertEqual(str(intento), 'Ingreso fallido: x@example.com')
