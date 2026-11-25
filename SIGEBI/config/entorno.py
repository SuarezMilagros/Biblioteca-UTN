"""Lectura de la configuración desde variables de entorno (S8-09, despliegue en Railway, 25/11/2026).

Son funciones sin efectos: reciben las variables (un dict, normalmente os.environ) y devuelven los valores
para config/settings.py. En una PC del equipo se usa SIGEBI/.env igual que antes; en Railway las variables se
cargan en el panel del servicio. Ninguna clave va en el código.
"""
from urllib.parse import unquote, urlparse

from django.core.exceptions import ImproperlyConfigured

VERDADERO = ('true', '1', 'si', 'sí')


def valor(variables, nombre, por_defecto=''):
    """La variable sin espacios. Si falta o quedó vacía, el valor por defecto."""
    return (variables.get(nombre) or '').strip() or por_defecto


def activado(variables, nombre, por_defecto='False'):
    return valor(variables, nombre, por_defecto).lower() in VERDADERO


def base_de_datos(variables):
    """Conexión a PostgreSQL.

    Con DATABASE_URL (Railway la da como postgresql://usuario:clave@servidor:puerto/base) se usa esa dirección;
    si no, las variables DB_NAME, DB_USER, DB_PASSWORD, DB_HOST y DB_PORT de siempre.
    """
    url = valor(variables, 'DATABASE_URL')
    if not url:
        return {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': valor(variables, 'DB_NAME', 'sigebi'),
            'USER': valor(variables, 'DB_USER', 'sigebi_user'),
            'PASSWORD': variables.get('DB_PASSWORD'),
            'HOST': valor(variables, 'DB_HOST', 'localhost'),
            'PORT': valor(variables, 'DB_PORT', '5432'),
        }
    partes = urlparse(url)
    if partes.scheme not in ('postgres', 'postgresql') or not partes.hostname or not partes.path.strip('/'):
        raise ImproperlyConfigured(
            'DATABASE_URL tiene que tener la forma postgresql://usuario:clave@servidor:puerto/base.'
        )
    return {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': unquote(partes.path.lstrip('/')),
        'USER': unquote(partes.username or ''),
        'PASSWORD': unquote(partes.password or ''),
        'HOST': partes.hostname,
        'PORT': str(partes.port or 5432),
        # Reutiliza la conexión entre pedidos y comprueba que siga viva antes de usarla.
        'CONN_MAX_AGE': 60,
        'CONN_HEALTH_CHECKS': True,
    }


def hosts_permitidos(variables):
    """DJANGO_ALLOWED_HOSTS, más la dirección pública que Railway asigna al servicio (RAILWAY_PUBLIC_DOMAIN)."""
    hosts = [host.strip() for host in valor(variables, 'DJANGO_ALLOWED_HOSTS').split(',') if host.strip()]
    publico = valor(variables, 'RAILWAY_PUBLIC_DOMAIN')
    if publico and publico not in hosts:
        hosts.append(publico)
    return hosts


def origenes_confiables(hosts):
    """Orígenes HTTPS que pueden enviar formularios (protección CSRF detrás del proxy de Railway)."""
    origenes = []
    for host in hosts:
        if host in ('*', 'localhost', '127.0.0.1', '[::1]'):
            continue
        origenes.append(f'https://*{host}' if host.startswith('.') else f'https://{host}')
    return origenes


def ajustes_de_https(variables):
    """Con DJANGO_HTTPS=True (en Railway): el sitio se atiende solo por HTTPS y las cookies viajan cifradas.

    Railway recibe la conexión HTTPS y se la pasa a Django avisando con X-Forwarded-Proto. En una PC del equipo
    queda apagado, así runserver sigue andando con http://127.0.0.1:8000.
    """
    if not activado(variables, 'DJANGO_HTTPS'):
        return {}
    return {
        'SECURE_PROXY_SSL_HEADER': ('HTTP_X_FORWARDED_PROTO', 'https'),
        'SECURE_SSL_REDIRECT': True,
        'SESSION_COOKIE_SECURE': True,
        'CSRF_COOKIE_SECURE': True,
        # El navegador recuerda por un día que este sitio va siempre por HTTPS.
        'SECURE_HSTS_SECONDS': 86400,
        # No se pide HTTPS para todos los subdominios ni la lista de precarga de los navegadores: el dominio
        # (por ejemplo, up.railway.app) es del proveedor, no de SIGEBI. check --deploy los avisa igual.
        'SILENCED_SYSTEM_CHECKS': ['security.W005', 'security.W021'],
    }


def ajustes_de_correo(variables):
    """Cómo se envían los correos (decisión D-C6, ampliada para Railway).

    - BREVO_API_KEY: por la API de Brevo (HTTPS). Railway bloquea el SMTP salvo en el plan Pro.
    - EMAIL_HOST: por SMTP (por ejemplo, Gmail con contraseña de aplicación), como en las PC del equipo.
    - Ninguna de las dos: se muestran en la consola (desarrollo).
    """
    ajustes = {'DEFAULT_FROM_EMAIL': valor(variables, 'DEFAULT_FROM_EMAIL', 'SIGEBI <no-responder@localhost>')}
    clave_brevo = valor(variables, 'BREVO_API_KEY')
    servidor = valor(variables, 'EMAIL_HOST')
    if clave_brevo:
        ajustes['EMAIL_BACKEND'] = 'anymail.backends.brevo.EmailBackend'
        # Si Brevo no responde, el envío se corta a los 10 segundos en lugar de colgar la pantalla.
        ajustes['ANYMAIL'] = {'BREVO_API_KEY': clave_brevo, 'REQUESTS_TIMEOUT': 10}
        ajustes['EMAIL_HOST'] = ''
        return ajustes
    ajustes['EMAIL_HOST'] = servidor
    if not servidor:
        ajustes['EMAIL_BACKEND'] = 'django.core.mail.backends.console.EmailBackend'
        return ajustes
    try:
        puerto = int(valor(variables, 'EMAIL_PORT', '587'))
    except ValueError:
        raise ImproperlyConfigured('EMAIL_PORT tiene que ser un número (por ejemplo, 587).')
    tls = activado(variables, 'EMAIL_USE_TLS', 'True')
    ssl = activado(variables, 'EMAIL_USE_SSL', 'False')
    if tls and ssl:
        raise ImproperlyConfigured('EMAIL_USE_TLS y EMAIL_USE_SSL no pueden estar las dos en True.')
    ajustes.update({
        'EMAIL_BACKEND': 'django.core.mail.backends.smtp.EmailBackend',
        'EMAIL_PORT': puerto,
        'EMAIL_HOST_USER': valor(variables, 'EMAIL_HOST_USER'),
        'EMAIL_HOST_PASSWORD': variables.get('EMAIL_HOST_PASSWORD', ''),
        'EMAIL_USE_TLS': tls,
        'EMAIL_USE_SSL': ssl,
        # Si el servidor no responde, el envío se corta a los 10 segundos en lugar de colgar la pantalla.
        'EMAIL_TIMEOUT': 10,
    })
    return ajustes
