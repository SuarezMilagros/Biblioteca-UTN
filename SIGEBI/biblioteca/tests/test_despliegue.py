"""Despliegue en Railway (S8-09, 25/11/2026).

- La configuración sale de variables de entorno: DATABASE_URL, la dirección pública de Railway, HTTPS, carpetas
  en el volumen y correo por la API de Brevo (Railway bloquea el SMTP). En las PC del equipo todo sigue igual.
- Con DEBUG apagado: WhiteNoise sirve los estilos, Django sirve las portadas y los errores se ven en el registro.
- `preparar_sitio` (antes de cada publicación): migraciones, cuenta de administración y datos de prueba.
- Un error al enviar por Brevo se trata igual que uno de SMTP: aviso, nunca error 500.

La prueba de punta a punta (base vacía, preparar_sitio, iniciar_servidor.sh con gunicorn, HTTPS por el proxy,
portadas, fotos, PDF y altas con Brevo caído) se hizo a mano antes de entregar; acá se controla cada pieza.
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

import requests
from anymail.exceptions import AnymailAPIError, AnymailError
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from biblioteca import avisos
from biblioteca.models import Libro
from config import entorno
from cuentas.correo import ERRORES_DE_ENVIO
from cuentas.roles import ADMINISTRATIVO, BIBLIOTECARIO

from .test_avisos import AvisosTestCase
from .test_material_compartido import CompartidoTestCase
from .test_reservas_personal import ReservasPersonalTestCase

BASE = Path(settings.BASE_DIR)
VARIABLES_DEL_DESPLIEGUE = [
    'DATABASE_URL', 'DJANGO_ALLOWED_HOSTS', 'RAILWAY_PUBLIC_DOMAIN', 'DJANGO_HTTPS', 'MEDIA_ROOT',
    'MATERIAL_DIGITAL_ROOT', 'BREVO_API_KEY', 'EMAIL_HOST', 'EMAIL_PORT', 'EMAIL_USE_TLS', 'EMAIL_USE_SSL',
    'EMAIL_HOST_USER', 'EMAIL_HOST_PASSWORD', 'DEFAULT_FROM_EMAIL',
]
CODIGO = '''
import json
from config import settings as s
print(json.dumps({
    "debug": s.DEBUG, "hosts": s.ALLOWED_HOSTS, "csrf": s.CSRF_TRUSTED_ORIGINS,
    "proxy": getattr(s, "SECURE_PROXY_SSL_HEADER", None), "redirigir": getattr(s, "SECURE_SSL_REDIRECT", False),
    "cookie_sesion": getattr(s, "SESSION_COOKIE_SECURE", False), "cookie_csrf": getattr(s, "CSRF_COOKIE_SECURE", False),
    "hsts": getattr(s, "SECURE_HSTS_SECONDS", 0), "base": s.DATABASES["default"],
    "middleware": s.MIDDLEWARE[:2], "estaticos": s.STORAGES["staticfiles"]["BACKEND"],
    "media": str(s.MEDIA_ROOT), "privado": s.MATERIAL_DIGITAL_ROOT, "correo": s.EMAIL_BACKEND,
    "anymail": getattr(s, "ANYMAIL", None), "remitente": s.DEFAULT_FROM_EMAIL,
    "registro": s.LOGGING["root"], "registro_django": s.LOGGING["loggers"]["django"],
}))
'''
EN_RAILWAY = {
    'DJANGO_DEBUG': 'False', 'DJANGO_HTTPS': 'True', 'RAILWAY_PUBLIC_DOMAIN': 'sigebi-production.up.railway.app',
    'DATABASE_URL': 'postgresql://postgres:cl%40ve-con-arroba@postgres.railway.internal:5432/railway',
    'MEDIA_ROOT': '/data/media', 'MATERIAL_DIGITAL_ROOT': '/data/privado', 'BREVO_API_KEY': 'xkeysib-de-prueba',
    'DEFAULT_FROM_EMAIL': 'SIGEBI <biblioteca@example.com>',
}


def entorno_limpio(**variables):
    """El entorno de quien corre las pruebas, sin las variables del despliegue (el .env no las vuelve a poner:
    load_dotenv no pisa variables ya definidas, aunque estén vacías)."""
    return {**os.environ, **{nombre: '' for nombre in VARIABLES_DEL_DESPLIEGUE}, **variables}


def cargar_ajustes(**variables):
    resultado = subprocess.run([sys.executable, '-c', CODIGO], cwd=BASE, env=entorno_limpio(**variables),
                               capture_output=True, text=True)
    if resultado.returncode != 0:
        raise AssertionError(resultado.stderr)
    return json.loads(resultado.stdout)


class EntornoTests(SimpleTestCase):
    """Las funciones de config/entorno.py, una por una."""

    def test_base_de_datos_desde_database_url(self):
        base = entorno.base_de_datos({'DATABASE_URL': 'postgresql://usuario:cl%40ve%2Fx@servidor.interno:6543/biblio'})
        self.assertEqual(
            (base['NAME'], base['USER'], base['PASSWORD'], base['HOST'], base['PORT']),
            ('biblio', 'usuario', 'cl@ve/x', 'servidor.interno', '6543'),  # la clave puede tener caracteres raros
        )
        self.assertEqual(base['ENGINE'], 'django.db.backends.postgresql')
        self.assertEqual((base['CONN_MAX_AGE'], base['CONN_HEALTH_CHECKS']), (60, True))

    def test_database_url_sin_puerto_usa_el_5432_y_acepta_postgres(self):
        self.assertEqual(entorno.base_de_datos({'DATABASE_URL': 'postgres://u:c@h/b'})['PORT'], '5432')

    def test_database_url_mal_escrita_es_un_error_claro(self):
        for url in ('mysql://u:c@h/b', 'postgresql://u:c@h/', 'esto-no-es-una-url'):
            with self.subTest(url=url), self.assertRaisesMessage(ImproperlyConfigured, 'postgresql://usuario:clave@'):
                entorno.base_de_datos({'DATABASE_URL': url})

    def test_sin_database_url_usa_las_variables_de_siempre(self):
        base = entorno.base_de_datos({'DB_NAME': 'sigebi', 'DB_USER': 'yo', 'DB_PASSWORD': 'c', 'DB_HOST': 'localhost'})
        self.assertEqual((base['NAME'], base['USER'], base['PASSWORD'], base['HOST'], base['PORT']),
                         ('sigebi', 'yo', 'c', 'localhost', '5432'))
        self.assertNotIn('CONN_MAX_AGE', base)

    def test_la_direccion_publica_de_railway_se_agrega_sola(self):
        self.assertEqual(entorno.hosts_permitidos({'RAILWAY_PUBLIC_DOMAIN': 'sigebi.up.railway.app'}),
                         ['sigebi.up.railway.app'])
        self.assertEqual(
            entorno.hosts_permitidos({'DJANGO_ALLOWED_HOSTS': ' a.com, sigebi.up.railway.app ,',
                                      'RAILWAY_PUBLIC_DOMAIN': 'sigebi.up.railway.app'}),
            ['a.com', 'sigebi.up.railway.app'],  # sin repetir
        )
        self.assertEqual(entorno.hosts_permitidos({}), [])

    def test_origenes_confiables_solo_https_y_sin_los_locales(self):
        self.assertEqual(
            entorno.origenes_confiables(['sigebi.up.railway.app', 'localhost', '127.0.0.1', '.ejemplo.com', '*']),
            ['https://sigebi.up.railway.app', 'https://*.ejemplo.com'],
        )

    def test_https_solo_si_se_pide(self):
        self.assertEqual(entorno.ajustes_de_https({}), {})
        self.assertEqual(entorno.ajustes_de_https({'DJANGO_HTTPS': 'False'}), {})
        ajustes = entorno.ajustes_de_https({'DJANGO_HTTPS': 'True'})
        self.assertEqual(ajustes['SECURE_PROXY_SSL_HEADER'], ('HTTP_X_FORWARDED_PROTO', 'https'))
        self.assertTrue(ajustes['SECURE_SSL_REDIRECT'] and ajustes['SESSION_COOKIE_SECURE'] and ajustes['CSRF_COOKIE_SECURE'])
        self.assertEqual(ajustes['SECURE_HSTS_SECONDS'], 86400)

    def test_con_clave_de_brevo_se_usa_brevo_aunque_haya_smtp(self):
        ajustes = entorno.ajustes_de_correo({'BREVO_API_KEY': ' xkeysib-1 ', 'EMAIL_HOST': 'smtp.gmail.com'})
        self.assertEqual(ajustes['EMAIL_BACKEND'], 'anymail.backends.brevo.EmailBackend')
        self.assertEqual(ajustes['ANYMAIL'], {'BREVO_API_KEY': 'xkeysib-1', 'REQUESTS_TIMEOUT': 10})
        self.assertEqual(ajustes['EMAIL_HOST'], '')

    def test_sin_brevo_el_correo_sigue_como_antes(self):
        self.assertEqual(entorno.ajustes_de_correo({})['EMAIL_BACKEND'], 'django.core.mail.backends.console.EmailBackend')
        smtp = entorno.ajustes_de_correo({'EMAIL_HOST': 'smtp.gmail.com'})
        self.assertEqual((smtp['EMAIL_BACKEND'], smtp['EMAIL_PORT'], smtp['EMAIL_USE_TLS']),
                         ('django.core.mail.backends.smtp.EmailBackend', 587, True))
        self.assertNotIn('ANYMAIL', smtp)


class AjustesEnRailwayTests(SimpleTestCase):
    """config/settings.py cargado en un proceso nuevo, con las variables que se cargan en Railway."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.railway = cargar_ajustes(**EN_RAILWAY)
        cls.local = cargar_ajustes(DJANGO_DEBUG='True', DB_NAME='sigebi', DB_HOST='localhost')

    def test_atiende_la_direccion_de_railway_por_https(self):
        r = self.railway
        self.assertFalse(r['debug'])
        self.assertEqual(r['hosts'], ['sigebi-production.up.railway.app'])
        self.assertEqual(r['csrf'], ['https://sigebi-production.up.railway.app'])
        self.assertEqual(r['proxy'], ['HTTP_X_FORWARDED_PROTO', 'https'])
        self.assertTrue(r['redirigir'] and r['cookie_sesion'] and r['cookie_csrf'])
        self.assertEqual(r['hsts'], 86400)

    def test_usa_la_base_de_railway(self):
        base = self.railway['base']
        self.assertEqual((base['HOST'], base['NAME'], base['USER'], base['PASSWORD']),
                         ('postgres.railway.internal', 'railway', 'postgres', 'cl@ve-con-arroba'))

    def test_archivos_en_el_volumen_y_estilos_con_whitenoise(self):
        r = self.railway
        self.assertEqual((r['media'], r['privado']), ('/data/media', '/data/privado'))
        self.assertEqual(r['middleware'], ['django.middleware.security.SecurityMiddleware',
                                           'whitenoise.middleware.WhiteNoiseMiddleware'])
        self.assertEqual(r['estaticos'], 'whitenoise.storage.CompressedStaticFilesStorage')

    def test_correo_por_brevo(self):
        self.assertEqual(self.railway['correo'], 'anymail.backends.brevo.EmailBackend')
        self.assertEqual(self.railway['anymail']['BREVO_API_KEY'], 'xkeysib-de-prueba')
        self.assertEqual(self.railway['remitente'], 'SIGEBI <biblioteca@example.com>')

    def test_los_errores_se_ven_en_el_registro(self):
        self.assertEqual(self.railway['registro'], {'handlers': ['consola'], 'level': 'WARNING'})
        self.assertEqual(self.railway['registro_django']['level'], 'ERROR')

    def test_en_la_pc_del_equipo_nada_cambia(self):
        local = self.local
        self.assertTrue(local['debug'])
        self.assertIsNone(local['proxy'])
        self.assertFalse(local['redirigir'] or local['cookie_sesion'])
        self.assertEqual(local['hosts'], [])
        self.assertEqual((local['base']['NAME'], local['base']['HOST']), ('sigebi', 'localhost'))
        self.assertEqual(local['media'], str(BASE / 'media'))
        self.assertEqual(local['privado'], str(BASE / 'material_privado'))
        self.assertEqual(local['correo'], 'django.core.mail.backends.console.EmailBackend')

    def test_check_deploy_sin_avisos(self):
        resultado = subprocess.run(
            [sys.executable, 'manage.py', 'check', '--deploy', '--fail-level', 'WARNING'], cwd=BASE,
            env=entorno_limpio(**EN_RAILWAY, DJANGO_SECRET_KEY='x' * 30 + 'clave-larga-y-variada-1234567890-%$#'),
            capture_output=True, text=True,
        )
        self.assertEqual(resultado.returncode, 0, resultado.stderr + resultado.stdout)


class PortadasConDebugApagadoTests(TestCase):
    """Con DEBUG apagado (como en Railway), las portadas de MEDIA_ROOT se sirven; lo privado nunca."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.carpeta = Path(tempfile.mkdtemp(prefix='media-'))
        (cls.carpeta / 'portadas').mkdir()
        (cls.carpeta / 'portadas' / 'tapa.jpg').write_bytes(b'\xff\xd8\xff imagen de prueba')
        cls.privado = Path(tempfile.mkdtemp(prefix='privado-'))
        (cls.privado / 'fotos').mkdir()
        (cls.privado / 'fotos' / 'secreta.jpg').write_bytes(b'privada')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.carpeta, ignore_errors=True)
        shutil.rmtree(cls.privado, ignore_errors=True)
        super().tearDownClass()

    def get(self, ruta):
        with override_settings(DEBUG=False, MEDIA_ROOT=str(self.carpeta), MATERIAL_DIGITAL_ROOT=str(self.privado)):
            return self.client.get(ruta)

    def test_la_portada_se_sirve_sin_iniciar_sesion(self):
        respuesta = self.get('/media/portadas/tapa.jpg')
        self.assertEqual((respuesta.status_code, respuesta['Content-Type']), (200, 'image/jpeg'))
        self.assertEqual(b''.join(respuesta.streaming_content), b'\xff\xd8\xff imagen de prueba')

    def test_no_lista_carpetas_ni_muestra_lo_que_no_existe(self):
        for ruta in ('/media/portadas/', '/media/portadas/no-existe.jpg'):
            with self.subTest(ruta=ruta):
                self.assertEqual(self.get(ruta).status_code, 404)

    def test_no_se_puede_salir_de_media(self):
        # Django detecta el intento (SuspiciousFileOperation), responde 400 sin buscar el archivo y lo deja en el
        # registro del servidor (en Railway, en "Deploy Logs").
        with self.assertLogs('django.security', 'ERROR') as registro:
            for ruta in ('/media/../config/settings.py', '/media/%2e%2e/manage.py', '/media/portadas/../../manage.py'):
                with self.subTest(ruta=ruta):
                    respuesta = self.get(ruta)
                    self.assertEqual(respuesta.status_code, 400)
                    self.assertNotIn(b'SECRET_KEY', respuesta.content)
        self.assertIn('outside of the base path', registro.output[0])

    def test_lo_privado_no_se_alcanza_por_media(self):
        self.assertEqual(self.get('/media/fotos/secreta.jpg').status_code, 404)

    def test_la_direccion_de_las_portadas_es_la_de_siempre(self):
        self.assertEqual(reverse('archivo_publico', args=['portadas/tapa.jpg']), '/media/portadas/tapa.jpg')


def respuesta_de_brevo(estado=201, cuerpo=b'{"messageId": "<1@smtp-relay.brevo.com>"}'):
    respuesta = requests.models.Response()
    respuesta.status_code = estado
    respuesta._content = cuerpo
    respuesta.headers['Content-Type'] = 'application/json'
    respuesta.encoding = 'utf-8'
    respuesta.url = 'https://api.brevo.com/v3/smtp/email'
    return respuesta


@override_settings(EMAIL_BACKEND='anymail.backends.brevo.EmailBackend',
                   ANYMAIL={'BREVO_API_KEY': 'xkeysib-de-prueba', 'REQUESTS_TIMEOUT': 10},
                   DEFAULT_FROM_EMAIL='SIGEBI <biblioteca@example.com>')
class EnvioPorBrevoTests(SimpleTestCase):
    def test_arma_el_pedido_a_la_api_de_brevo(self):
        with mock.patch('requests.Session.request', return_value=respuesta_de_brevo()) as pedido:
            mail.send_mail('Asunto de prueba', 'Cuerpo del mensaje', None, ['lector@example.com'])
        datos = pedido.call_args.kwargs
        self.assertEqual((datos['method'], datos['url']), ('POST', 'https://api.brevo.com/v3/smtp/email'))
        self.assertEqual(datos['headers']['api-key'], 'xkeysib-de-prueba')
        self.assertEqual(datos['timeout'], 10)
        cuerpo = json.loads(datos['data'])
        self.assertEqual(cuerpo['sender'], {'name': 'SIGEBI', 'email': 'biblioteca@example.com'})
        self.assertEqual(cuerpo['to'], [{'email': 'lector@example.com'}])
        self.assertEqual((cuerpo['subject'], cuerpo['textContent']), ('Asunto de prueba', 'Cuerpo del mensaje'))

    def test_los_errores_de_brevo_estan_entre_los_errores_de_envio(self):
        self.assertTrue(issubclass(AnymailError, ERRORES_DE_ENVIO))
        with mock.patch('requests.Session.request', return_value=respuesta_de_brevo(401, b'{"code": "unauthorized"}')):
            with self.assertRaises(ERRORES_DE_ENVIO):
                mail.send_mail('A', 'B', None, ['lector@example.com'])
        with mock.patch('requests.Session.request', side_effect=requests.ConnectionError('sin red')):
            with self.assertRaises(ERRORES_DE_ENVIO):
                mail.send_mail('A', 'B', None, ['lector@example.com'])

    def ejecutar_probar_correo(self):
        salida = io.StringIO()
        call_command('probar_correo', 'destino@example.com', stdout=salida)
        return salida.getvalue()

    def test_probar_correo_con_brevo(self):
        with mock.patch('requests.Session.request', return_value=respuesta_de_brevo()):
            salida = self.ejecutar_probar_correo()
        self.assertIn('Enviando con la API de Brevo (remitente: SIGEBI <biblioteca@example.com>)', salida)
        self.assertIn('Correo de prueba enviado a destino@example.com.', salida)
        self.assertNotIn('xkeysib-de-prueba', salida)

    def test_probar_correo_con_la_clave_rechazada(self):
        with mock.patch('requests.Session.request', return_value=respuesta_de_brevo(401, b'{"code": "unauthorized"}')):
            with self.assertRaisesMessage(CommandError, 'Brevo rechazó la clave. Revisá BREVO_API_KEY'):
                self.ejecutar_probar_correo()

    def test_probar_correo_sin_conexion_con_brevo(self):
        with mock.patch('requests.Session.request', side_effect=requests.ConnectionError('sin red')):
            with self.assertRaisesMessage(CommandError, 'no se pudo conectar con Brevo (api.brevo.com)'):
                self.ejecutar_probar_correo()

    def test_probar_correo_con_otro_error_de_brevo(self):
        with mock.patch('requests.Session.request', return_value=respuesta_de_brevo(500, b'{}')):
            with self.assertRaisesMessage(CommandError, 'Brevo respondió 500'):
                self.ejecutar_probar_correo()


class FalloDeBrevoEnLasPantallasTests(TestCase):
    """Si Brevo falla, cada lugar que manda correo avisa igual que con SMTP (sin error 500)."""

    @classmethod
    def setUpTestData(cls):
        cls.administrativo = get_user_model().objects.create_user(
            username='32333444', email='administrativo@example.com', password='clave-de-prueba-123')
        cls.administrativo.groups.add(Group.objects.get(name=ADMINISTRATIVO))

    def test_alta_de_cuenta_avisa_que_no_salio_el_correo(self):
        self.client.force_login(self.administrativo)
        error = AnymailAPIError('Brevo no responde', status_code=503)
        with mock.patch('cuentas.views.enviar_correo_definicion', side_effect=error):
            respuesta = self.client.post(reverse('cuentas:usuario_create'), {
                'username': '40111222', 'first_name': 'Lucía', 'last_name': 'Paz',
                'email': 'lucia.paz@example.com', 'rol': BIBLIOTECARIO, 'is_active': 'on',
            }, follow=True)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'no se pudo enviar el correo de definición')
        self.assertTrue(get_user_model().objects.filter(email='lucia.paz@example.com').exists())



ERROR_DE_BREVO = AnymailAPIError('Brevo rechazó la clave', status_code=401)


class AvisosConBrevoCaidoTests(AvisosTestCase):
    def test_el_aviso_queda_para_la_proxima_vez(self):
        prestamo = self.prestar(vence_en=1)
        with mock.patch('biblioteca.avisos.EmailMessage.send', side_effect=ERROR_DE_BREVO):
            resultado = avisos.enviar_avisos()
        self.assertEqual(resultado.fallidos, [prestamo])
        self.assertEqual(self.avisos_de(prestamo), [])


class ReservasConBrevoCaidoTests(ReservasPersonalTestCase):
    def test_la_reserva_queda_confirmada_y_lo_advierte(self):
        reserva = self.pendiente()
        with mock.patch('biblioteca.reservas.send_mail', side_effect=ERROR_DE_BREVO):
            respuesta = self.post('reserva_confirmar', reserva, ejemplar=self.py1.pk)
        self.assertEqual(self.recargar(reserva).estado, 'CONFIRMADA')
        self.assertContains(respuesta, 'No se pudo enviar el correo de aviso.')


class MaterialConBrevoCaidoTests(CompartidoTestCase):
    def test_queda_aprobado_y_lo_advierte(self):
        material = self.pendiente()
        with mock.patch('biblioteca.revision_de_material.send_mail', side_effect=ERROR_DE_BREVO):
            respuesta = self.client.post(reverse('biblioteca:material_aprobar', args=[material.pk]), follow=True)
        self.assertEqual(self.recargar(material).estado, 'APROBADO')
        self.assertContains(respuesta, 'No se pudo enviar el correo de aviso.')


class PrepararSitioTests(TestCase):
    def preparar(self, **variables):
        limpio = {'SIGEBI_ADMIN_CORREO': '', 'SIGEBI_ADMIN_CLAVE': '', 'SIGEBI_DATOS_DEMO': '', **variables}
        salida = io.StringIO()
        with mock.patch.dict(os.environ, limpio):
            call_command('preparar_sitio', stdout=salida)
        return salida.getvalue()

    def test_crea_la_cuenta_de_administracion_una_sola_vez(self):
        salida = self.preparar(SIGEBI_ADMIN_CORREO=' Admin@Example.com ', SIGEBI_ADMIN_CLAVE='Railway-SIGEBI-2026')
        self.assertIn('Cuenta de administración creada: admin@example.com.', salida)
        self.assertIn('Sitio preparado.', salida)
        self.assertNotIn('Railway-SIGEBI-2026', salida)
        admin = get_user_model().objects.get(email='admin@example.com')
        self.assertTrue(admin.is_superuser and admin.is_staff and admin.is_active)
        self.assertTrue(admin.check_password('Railway-SIGEBI-2026'))
        self.assertTrue(self.client.login(username='admin@example.com', password='Railway-SIGEBI-2026'))
        # La segunda vez no la toca, aunque cambie la clave del panel.
        salida = self.preparar(SIGEBI_ADMIN_CORREO='admin@example.com', SIGEBI_ADMIN_CLAVE='Otra-Clave-Distinta-99')
        self.assertIn('admin@example.com ya existe, no se modifica.', salida)
        admin.refresh_from_db()
        self.assertTrue(admin.check_password('Railway-SIGEBI-2026'))
        self.assertEqual(get_user_model().objects.filter(is_superuser=True).count(), 1)

    def test_sin_las_variables_no_crea_ninguna_cuenta(self):
        salida = self.preparar(SIGEBI_ADMIN_CORREO='admin@example.com')
        self.assertIn('no se crea', salida)
        self.assertFalse(get_user_model().objects.filter(is_superuser=True).exists())

    def test_una_clave_debil_frena_sin_mostrarla(self):
        with self.assertRaises(CommandError) as contexto:
            self.preparar(SIGEBI_ADMIN_CORREO='admin@example.com', SIGEBI_ADMIN_CLAVE='12345678')
        self.assertIn('SIGEBI_ADMIN_CLAVE no sirve', str(contexto.exception))
        self.assertNotIn('12345678', str(contexto.exception))
        self.assertFalse(get_user_model().objects.filter(email='admin@example.com').exists())

    def test_un_correo_invalido_frena(self):
        with self.assertRaisesMessage(CommandError, 'SIGEBI_ADMIN_CORREO no es un correo válido'):
            self.preparar(SIGEBI_ADMIN_CORREO='no-es-correo', SIGEBI_ADMIN_CLAVE='Railway-SIGEBI-2026')

    def test_datos_de_prueba_solo_si_se_piden(self):
        self.preparar()
        self.assertFalse(Libro.objects.exists())
        salida = self.preparar(SIGEBI_DATOS_DEMO='True')
        self.assertIn('Datos de prueba cargados.', salida)
        self.assertEqual(Libro.objects.count(), 6)
        self.preparar(SIGEBI_DATOS_DEMO='True')
        self.assertEqual(Libro.objects.count(), 6)  # repetir no duplica

    def test_aplica_las_migraciones(self):
        with mock.patch('biblioteca.management.commands.preparar_sitio.call_command') as llamado:
            self.preparar()
        self.assertEqual(llamado.call_args_list[0].args, ('migrate',))
        self.assertEqual(llamado.call_args_list[0].kwargs['interactive'], False)


class ArchivosDelDespliegueTests(SimpleTestCase):
    def test_script_de_arranque(self):
        script = (BASE / 'iniciar_servidor.sh').read_text(encoding='utf-8')
        self.assertTrue(script.startswith('#!/bin/sh\n'))
        self.assertNotIn('\r', script)  # fin de línea de Linux
        self.assertIn('set -e', script)
        self.assertLess(script.index('python manage.py collectstatic --noinput'), script.index('exec gunicorn'))
        self.assertIn('exec gunicorn config.wsgi --bind "0.0.0.0:${PORT:-8000}"', script)
        self.assertIn('--timeout 60', script)

    def test_fin_de_linea_y_version_de_python(self):
        self.assertIn('*.sh text eol=lf', (BASE / '.gitattributes').read_text(encoding='utf-8'))
        self.assertEqual((BASE / '.python-version').read_text(encoding='utf-8').strip(), '3.13')

    def test_dependencias_fijadas(self):
        requisitos = (BASE / 'requirements.txt').read_text(encoding='ascii')
        for paquete in ('gunicorn==', 'whitenoise==', 'django-anymail==', 'requests=='):
            with self.subTest(paquete=paquete):
                self.assertIn(paquete, requisitos)

    def test_el_ejemplo_de_env_documenta_las_variables_nuevas(self):
        ejemplo = (BASE / '.env.example').read_text(encoding='utf-8')
        for variable in ('DATABASE_URL=', 'DJANGO_HTTPS=', 'BREVO_API_KEY=', 'MEDIA_ROOT=', 'SIGEBI_ADMIN_CORREO=',
                         'SIGEBI_ADMIN_CLAVE=', 'SIGEBI_DATOS_DEMO='):
            with self.subTest(variable=variable):
                self.assertIn(variable, ejemplo)
