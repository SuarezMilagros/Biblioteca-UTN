"""Prepara el sitio publicado (S8-09): migraciones, cuenta de administración y datos de prueba.

Railway lo ejecuta antes de cada publicación ("Pre-deploy Command": python manage.py preparar_sitio).
Se puede repetir las veces que haga falta: no duplica nada y no cambia contraseñas.

Variables (se cargan en el panel de Railway, nunca en el código):
- SIGEBI_ADMIN_CORREO y SIGEBI_ADMIN_CLAVE: si están las dos y no hay una cuenta con ese correo, se crea un
  superusuario para entrar la primera vez. Si la cuenta ya existe, no se toca (tampoco su contraseña).
  Después del primer ingreso conviene borrar SIGEBI_ADMIN_CLAVE del panel y cambiar la contraseña en SIGEBI.
- SIGEBI_DATOS_DEMO=True: carga los datos ficticios de `cargar_datos_prueba` (libros, ejemplares, personas
  y préstamos de ejemplo) para mostrar el sistema.
"""
import os

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import transaction

from config.entorno import activado, valor


class Command(BaseCommand):
    help = 'Prepara el sitio publicado: migraciones, cuenta de administración y (opcional) datos de prueba.'

    def handle(self, *args, **options):
        call_command('migrate', interactive=False, stdout=self.stdout)
        self.crear_administrador()
        if activado(os.environ, 'SIGEBI_DATOS_DEMO'):
            call_command('cargar_datos_prueba', stdout=self.stdout)
        self.stdout.write(self.style.SUCCESS('Sitio preparado.'))

    def crear_administrador(self):
        correo = valor(os.environ, 'SIGEBI_ADMIN_CORREO').lower()
        clave = os.environ.get('SIGEBI_ADMIN_CLAVE', '')
        if not correo or not clave:
            self.stdout.write('Cuenta de administración: sin SIGEBI_ADMIN_CORREO y SIGEBI_ADMIN_CLAVE, no se crea.')
            return
        try:
            validate_email(correo)
        except ValidationError:
            raise CommandError(f'SIGEBI_ADMIN_CORREO no es un correo válido: "{correo}".')
        Usuario = get_user_model()
        if Usuario.objects.filter(email__iexact=correo).exists():
            self.stdout.write(f'Cuenta de administración: {correo} ya existe, no se modifica.')
            return
        usuario = Usuario(username=correo, email=correo, first_name='Administración', last_name='SIGEBI',
                          is_staff=True, is_superuser=True)
        try:
            validate_password(clave, usuario)
        except ValidationError as error:
            # Nunca se muestra la clave: solo por qué no sirve.
            raise CommandError('SIGEBI_ADMIN_CLAVE no sirve: ' + ' '.join(error.messages))
        with transaction.atomic():
            usuario.set_password(clave)
            usuario.save()
        self.stdout.write(self.style.SUCCESS(f'Cuenta de administración creada: {correo}.'))
