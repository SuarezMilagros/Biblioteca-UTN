from django.contrib.postgres.operations import UnaccentExtension
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('biblioteca', '0005_ajustes_inventario'),
    ]

    operations = [
        # Instala la extensión `unaccent` de PostgreSQL, que permite buscar sin acentos.
        UnaccentExtension(),
    ]