"""Configuración del correo real (Release 1, decisión D-C6).

- Sin EMAIL_HOST, el correo se muestra en la consola (desarrollo).
- Con EMAIL_HOST, se envía por SMTP con los datos de SIGEBI/.env.
- `python manage.py probar_correo` permite comprobarlo sin mostrar la contraseña.

La prueba real de extremo a extremo (que el correo llegue a una casilla) la hace el
equipo con la cuenta elegida; estas pruebas verifican la configuración y el comando.
"""
import io
import json
import os
import smtplib
import subprocess
import sys
from unittest import mock

from django.conf import settings
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

CODIGO = (
    'import json; from config import settings as s; '
    'print(json.dumps({"backend": s.EMAIL_BACKEND, "host": s.EMAIL_HOST, '
    '"puerto": getattr(s, "EMAIL_PORT", None), "tls": getattr(s, "EMAIL_USE_TLS", None), '
    '"ssl": getattr(s, "EMAIL_USE_SSL", None), "usuario": getattr(s, "EMAIL_HOST_USER", None), '
    '"remitente": s.DEFAULT_FROM_EMAIL, "timeout": getattr(s, "EMAIL_TIMEOUT", None)}))'
)
VARIABLES_DE_CORREO = [
    'EMAIL_HOST', 'EMAIL_PORT', 'EMAIL_USE_TLS', 'EMAIL_USE_SSL',
    'EMAIL_HOST_USER', 'EMAIL_HOST_PASSWORD', 'DEFAULT_FROM_EMAIL',
]


def cargar_settings(**variables):
    """Carga config/settings.py en un proceso nuevo con las variables de correo indicadas.

    Las variables de correo del entorno se reemplazan por cadenas vacías: así el .env de
    quien corre las pruebas no cambia el resultado (load_dotenv no pisa variables ya definidas).
    """
    entorno = {**os.environ, **{nombre: '' for nombre in VARIABLES_DE_CORREO}, **variables}
    return subprocess.run(
        [sys.executable, '-c', CODIGO], cwd=settings.BASE_DIR, env=entorno, capture_output=True, text=True
    )


class ConfiguracionDeCorreoTests(SimpleTestCase):
    def test_sin_servidor_el_correo_va_a_la_consola(self):
        resultado = cargar_settings()
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        datos = json.loads(resultado.stdout)
        self.assertEqual(datos['backend'], 'django.core.mail.backends.console.EmailBackend')
        self.assertEqual(datos['remitente'], 'SIGEBI <no-responder@localhost>')

    def test_con_servidor_se_usa_smtp_con_tls_por_defecto(self):
        resultado = cargar_settings(
            EMAIL_HOST='smtp.gmail.com', EMAIL_HOST_USER='biblioteca@example.com',
            EMAIL_HOST_PASSWORD='no-se-muestra', DEFAULT_FROM_EMAIL='SIGEBI <biblioteca@example.com>',
        )
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        datos = json.loads(resultado.stdout)
        self.assertEqual(datos['backend'], 'django.core.mail.backends.smtp.EmailBackend')
        self.assertEqual(
            (datos['host'], datos['puerto'], datos['tls'], datos['ssl'], datos['timeout']),
            ('smtp.gmail.com', 587, True, False, 10),
        )
        self.assertEqual(datos['usuario'], 'biblioteca@example.com')
        self.assertEqual(datos['remitente'], 'SIGEBI <biblioteca@example.com>')

    def test_ssl_en_el_puerto_465(self):
        resultado = cargar_settings(
            EMAIL_HOST='smtp.ejemplo.com', EMAIL_PORT='465', EMAIL_USE_TLS='False', EMAIL_USE_SSL='True'
        )
        datos = json.loads(resultado.stdout)
        self.assertEqual((datos['puerto'], datos['tls'], datos['ssl']), (465, False, True))

    def test_tls_y_ssl_juntos_es_un_error_claro(self):
        resultado = cargar_settings(EMAIL_HOST='smtp.ejemplo.com', EMAIL_USE_TLS='True', EMAIL_USE_SSL='True')
        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn('EMAIL_USE_TLS y EMAIL_USE_SSL no pueden estar las dos en True', resultado.stderr)

    def test_puerto_que_no_es_numero_es_un_error_claro(self):
        resultado = cargar_settings(EMAIL_HOST='smtp.ejemplo.com', EMAIL_PORT='quinientos')
        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn('EMAIL_PORT tiene que ser un número', resultado.stderr)


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    EMAIL_HOST='smtp.ejemplo.com', EMAIL_PORT=587, EMAIL_HOST_USER='biblioteca@example.com',
    EMAIL_HOST_PASSWORD='clave-secreta-que-no-se-muestra',
)
class ComandoProbarCorreoTests(SimpleTestCase):
    def ejecutar(self, *argumentos):
        salida = io.StringIO()
        call_command('probar_correo', *argumentos, stdout=salida)
        return salida.getvalue()

    def test_envia_el_correo_de_prueba(self):
        salida = self.ejecutar('destino@example.com')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['destino@example.com'])
        self.assertEqual(mail.outbox[0].subject, 'Prueba de correo de SIGEBI')
        self.assertIn('Correo de prueba enviado a destino@example.com.', salida)
        self.assertIn('smtp.ejemplo.com:587', salida)
        self.assertNotIn('clave-secreta-que-no-se-muestra', salida)

    def test_correo_invalido(self):
        with self.assertRaisesMessage(CommandError, 'no es un correo válido'):
            self.ejecutar('no-es-un-correo')
        self.assertEqual(len(mail.outbox), 0)

    def test_usuario_o_contrasena_rechazados(self):
        error = smtplib.SMTPAuthenticationError(535, b'Username and Password not accepted')
        with mock.patch('cuentas.management.commands.probar_correo.send_mail', side_effect=error):
            with self.assertRaises(CommandError) as contexto:
                self.ejecutar('destino@example.com')
        self.assertIn('rechazó el usuario o la contraseña', str(contexto.exception))
        self.assertNotIn('clave-secreta-que-no-se-muestra', str(contexto.exception))

    def test_servidor_inaccesible(self):
        with mock.patch('cuentas.management.commands.probar_correo.send_mail', side_effect=OSError('Connection refused')):
            with self.assertRaisesMessage(CommandError, 'No se pudo enviar el correo: OSError: Connection refused'):
                self.ejecutar('destino@example.com')

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend')
    def test_sin_servidor_avisa_que_se_muestra_en_consola(self):
        with mock.patch('cuentas.management.commands.probar_correo.send_mail'):
            salida = self.ejecutar('destino@example.com')
        self.assertIn('EMAIL_HOST está vacío', salida)
