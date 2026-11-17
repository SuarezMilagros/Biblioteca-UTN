"""Los modelos y las migraciones coinciden (control general, agregado en S8-05).

Si alguien cambia un modelo (un campo, una restricción) y se olvida de crear la migración, la base real
no tendría ese cambio aunque el código lo diga. Este test lo detecta: falla si falta una migración.
"""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase


class MigracionesTests(TestCase):
    def test_no_falta_ninguna_migracion(self):
        salida = StringIO()
        try:
            call_command('makemigrations', '--check', '--dry-run', stdout=salida, stderr=StringIO())
        except SystemExit:
            self.fail(f'Hay cambios en los modelos sin migración. Ejecutá "python manage.py makemigrations".\n{salida.getvalue()}')
