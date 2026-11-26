"""Límite de intentos de acceso (Release 2, R2-01).

- 5 ingresos fallidos en 15 minutos bloquean ese correo; 20 desde una IP bloquean esa IP.
- Mientras dura el bloqueo no se puede entrar, ni siquiera con la contraseña correcta.
- Un correo inexistente se bloquea igual que uno registrado: el bloqueo no revela qué cuentas existen.
- La recuperación de contraseña envía como máximo 3 correos por hora a una misma dirección.
- Detrás del proxy de Railway (S8-09) la IP sale de X-Real-IP: los fallos de un visitante no bloquean a los demás.
"""
from datetime import timedelta

from django.contrib.auth import SESSION_KEY, get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from cuentas import intentos
from cuentas.models import IntentoDeAcceso

CORREO = 'ana.perez@example.com'
CLAVE = 'clave-de-prueba-123'
MENSAJE_GENERICO = 'El correo o la contraseña no son correctos.'
MENSAJE_BLOQUEO = 'Hubo demasiados intentos fallidos. Esperá 15 minutos y volvé a intentar.'


class IntentosTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(username='31222333', email=CORREO, password=CLAVE)

    def ingresar(self, correo=CORREO, clave=CLAVE, ip='127.0.0.1'):
        return self.client.post(reverse('login'), {'username': correo, 'password': clave}, REMOTE_ADDR=ip)

    def fallar(self, veces, correo=CORREO, ip='127.0.0.1'):
        for _ in range(veces):
            respuesta = self.ingresar(correo, clave='clave-equivocada', ip=ip)
            self.assertContains(respuesta, MENSAJE_GENERICO)

    def envejecer_intentos(self, minutos):
        IntentoDeAcceso.objects.update(fecha=timezone.now() - timedelta(minutes=minutos))


class LimiteDeIngresoTests(IntentosTestCase):
    def test_con_cuatro_fallos_todavia_puede_entrar(self):
        self.fallar(4)
        self.assertRedirects(self.ingresar(), reverse('biblioteca:inicio'))

    def test_con_cinco_fallos_no_entra_ni_con_la_clave_correcta(self):
        self.fallar(5)
        respuesta = self.ingresar()
        self.assertContains(respuesta, MENSAJE_BLOQUEO)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_el_bloqueo_vence_a_los_quince_minutos(self):
        self.fallar(5)
        self.envejecer_intentos(intentos.INGRESO_MINUTOS + 1)
        self.assertRedirects(self.ingresar(), reverse('biblioteca:inicio'))

    def test_un_correo_inexistente_se_bloquea_igual(self):
        self.fallar(5, correo='nadie@example.com')
        self.assertContains(self.ingresar('nadie@example.com'), MENSAJE_BLOQUEO)

    def test_el_correo_no_distingue_mayusculas(self):
        self.fallar(5, correo='ANA.Perez@Example.com')
        self.assertContains(self.ingresar(), MENSAJE_BLOQUEO)

    def test_los_intentos_durante_el_bloqueo_no_se_registran(self):
        self.fallar(5)
        self.ingresar(clave='otra-clave-equivocada')
        self.assertEqual(IntentoDeAcceso.objects.count(), 5)

    def test_se_registra_el_correo_y_la_ip(self):
        self.fallar(1, correo=' Nadie@Example.com ', ip='10.0.0.7')
        intento = IntentoDeAcceso.objects.get()
        self.assertEqual(intento.tipo, IntentoDeAcceso.Tipo.INGRESO_FALLIDO)
        self.assertEqual(intento.correo, 'nadie@example.com')
        self.assertEqual(intento.ip, '10.0.0.7')

    def test_un_ingreso_correcto_borra_los_fallos_de_ese_correo(self):
        self.fallar(4)
        self.fallar(2, correo='otro@example.com')
        self.ingresar()
        self.assertFalse(IntentoDeAcceso.objects.filter(correo=CORREO).exists())
        self.assertEqual(IntentoDeAcceso.objects.filter(correo='otro@example.com').count(), 2)

    def test_el_bloqueo_de_un_correo_no_afecta_a_otro(self):
        otro = get_user_model().objects.create_user(username='40111222', email='otro@example.com', password=CLAVE)
        self.fallar(5)
        self.assertRedirects(self.ingresar(otro.email), reverse('biblioteca:inicio'))

    def test_veinte_fallos_desde_una_ip_bloquean_esa_ip(self):
        for numero in range(intentos.INGRESO_MAXIMO_POR_IP):
            self.fallar(1, correo=f'prueba{numero}@example.com', ip='10.0.0.9')
        self.assertContains(self.ingresar(ip='10.0.0.9'), MENSAJE_BLOQUEO)
        self.assertRedirects(self.ingresar(ip='10.0.0.10'), reverse('biblioteca:inicio'))

    def test_campos_vacios_no_registran_intentos(self):
        self.ingresar(correo='', clave='')
        self.assertFalse(IntentoDeAcceso.objects.exists())


class LimiteDeRecuperacionTests(IntentosTestCase):
    def pedir_recuperacion(self, correo=CORREO, ip='127.0.0.1'):
        return self.client.post(reverse('password_reset'), {'email': correo}, REMOTE_ADDR=ip)

    def test_tres_pedidos_por_hora_envian_correo_y_el_cuarto_no(self):
        for _ in range(intentos.RECUPERACION_MAXIMO_POR_CORREO):
            self.pedir_recuperacion()
        self.assertEqual(len(mail.outbox), 3)
        respuesta = self.pedir_recuperacion()
        # La pantalla es la misma: no revela que se alcanzó el límite.
        self.assertRedirects(respuesta, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 3)

    def test_despues_de_una_hora_se_puede_volver_a_pedir(self):
        for _ in range(intentos.RECUPERACION_MAXIMO_POR_CORREO):
            self.pedir_recuperacion()
        self.envejecer_intentos(intentos.RECUPERACION_MINUTOS + 1)
        self.pedir_recuperacion()
        self.assertEqual(len(mail.outbox), 4)

    def test_diez_pedidos_desde_una_ip_bloquean_esa_ip(self):
        for numero in range(intentos.RECUPERACION_MAXIMO_POR_IP):
            self.pedir_recuperacion(f'prueba{numero}@example.com', ip='10.0.0.9')
        self.pedir_recuperacion(ip='10.0.0.9')
        self.assertEqual(len(mail.outbox), 0)
        self.pedir_recuperacion(ip='10.0.0.10')
        self.assertEqual(len(mail.outbox), 1)

    def test_los_pedidos_no_cuentan_como_ingresos_fallidos(self):
        for _ in range(5):
            self.pedir_recuperacion()
        self.assertRedirects(self.ingresar(), reverse('biblioteca:inicio'))


class IntentosEnElAdminTests(IntentosTestCase):
    def test_el_superusuario_los_ve_pero_no_los_puede_crear_ni_editar(self):
        self.fallar(1)
        admin = get_user_model().objects.create_superuser(
            username='20111222', email='admin@example.com', password=CLAVE
        )
        self.client.force_login(admin)
        respuesta = self.client.get(reverse('admin:cuentas_intentodeacceso_changelist'))
        self.assertContains(respuesta, CORREO)
        self.assertEqual(self.client.get(reverse('admin:cuentas_intentodeacceso_add')).status_code, 403)

PROXY = '100.64.0.2'  # dirección del proxy de Railway: la misma para todos los visitantes


@override_settings(CABECERA_IP_DEL_CLIENTE='HTTP_X_REAL_IP')
class IpDetrasDelProxyTests(IntentosTestCase):
    """En Railway todos los pedidos llegan desde el proxy; la IP del visitante viene en X-Real-IP."""

    def ingresar_desde(self, visitante, correo=CORREO, clave=CLAVE):
        return self.client.post(reverse('login'), {'username': correo, 'password': clave},
                                REMOTE_ADDR=PROXY, HTTP_X_REAL_IP=visitante)

    def test_registra_la_ip_del_visitante_y_no_la_del_proxy(self):
        self.ingresar_desde('203.0.113.5', clave='clave-equivocada')
        self.assertEqual(IntentoDeAcceso.objects.get().ip, '203.0.113.5')

    def test_los_fallos_de_un_visitante_no_bloquean_a_otro(self):
        for numero in range(intentos.INGRESO_MAXIMO_POR_IP):
            self.ingresar_desde('203.0.113.5', correo=f'prueba{numero}@example.com', clave='x')
        self.assertContains(self.ingresar_desde('203.0.113.5'), MENSAJE_BLOQUEO)
        self.assertRedirects(self.ingresar_desde('198.51.100.7'), reverse('biblioteca:inicio'))

    def test_los_pedidos_de_recuperacion_tambien_se_cuentan_por_visitante(self):
        for numero in range(intentos.RECUPERACION_MAXIMO_POR_IP):
            self.client.post(reverse('password_reset'), {'email': f'prueba{numero}@example.com'},
                             REMOTE_ADDR=PROXY, HTTP_X_REAL_IP='203.0.113.5')
        self.client.post(reverse('password_reset'), {'email': CORREO}, REMOTE_ADDR=PROXY, HTTP_X_REAL_IP='198.51.100.7')
        self.assertEqual(len(mail.outbox), 1)  # el otro visitante sí recibe su correo
        self.assertEqual(mail.outbox[0].to, [CORREO])

    def test_acepta_ipv6(self):
        self.ingresar_desde('2001:db8::1', clave='clave-equivocada')
        self.assertEqual(IntentoDeAcceso.objects.get().ip, '2001:db8::1')

    def test_un_valor_que_no_es_una_ip_se_ignora(self):
        for valor in ('no-es-una-ip', '203.0.113.5, 198.51.100.7', '', '999.1.1.1'):
            with self.subTest(valor=valor):
                IntentoDeAcceso.objects.all().delete()
                self.ingresar_desde(valor, clave='clave-equivocada')
                self.assertEqual(IntentoDeAcceso.objects.get().ip, PROXY)


class SinProxyDeConfianzaTests(IntentosTestCase):
    """En una PC del equipo (sin proxy) la cabecera se ignora: cualquiera la podría inventar."""

    def test_ignora_x_real_ip(self):
        self.client.post(reverse('login'), {'username': CORREO, 'password': 'x'},
                         REMOTE_ADDR='10.0.0.1', HTTP_X_REAL_IP='203.0.113.5')
        self.assertEqual(IntentoDeAcceso.objects.get().ip, '10.0.0.1')

    def test_inventar_la_cabecera_no_saltea_el_bloqueo_por_ip(self):
        for numero in range(intentos.INGRESO_MAXIMO_POR_IP):
            self.client.post(reverse('login'), {'username': f'prueba{numero}@example.com', 'password': 'x'},
                             REMOTE_ADDR='10.0.0.9', HTTP_X_REAL_IP=f'203.0.113.{numero}')
        self.assertContains(self.ingresar(ip='10.0.0.9'), MENSAJE_BLOQUEO)
