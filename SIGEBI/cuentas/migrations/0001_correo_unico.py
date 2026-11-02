"""Correo único en las cuentas, sin distinguir mayúsculas (etapa 5, decisión D-C5).

Con la opción C el usuario es el de Django, y unique=True no alcanza: distingue mayúsculas
y no admite varios correos vacíos. Por eso el índice se crea en SQL, solo para correos no vacíos.
Si ya hay duplicados en la base, esta migración falla y hay que corregirlos antes.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunSQL(
            sql="CREATE UNIQUE INDEX cuentas_correo_unico ON auth_user (lower(email)) WHERE email <> '';",
            reverse_sql='DROP INDEX IF EXISTS cuentas_correo_unico;',
        ),
    ]
