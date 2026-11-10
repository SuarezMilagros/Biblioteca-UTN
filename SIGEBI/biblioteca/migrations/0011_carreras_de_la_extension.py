"""Carga las carreras de la Extensión Áulica Concepción (Release 2, S7-02).

La lista la informó la biblioteca el 10/11/2026. Se carga con una migración para que todas las
instalaciones (la de cada integrante y la de producción) tengan exactamente las mismas carreras.
Si una carrera ya existe con ese nombre, no se duplica.
"""
from django.db import migrations

CARRERAS = [
    ('Tecnicatura Universitaria en Desarrollo y Producción de Videojuegos', 'PREGRADO'),
    ('Tecnicatura Universitaria en Programación', 'PREGRADO'),
    ('Tecnicatura Universitaria en Mantenimiento Industrial', 'PREGRADO'),
    ('Tecnicatura Universitaria en Mecatrónica', 'PREGRADO'),
    ('Tecnicatura Universitaria en Higiene y Seguridad en el Trabajo', 'PREGRADO'),
    ('Tecnicatura Universitaria en Logística', 'PREGRADO'),
    ('Tecnicatura Universitaria en Energías Sustentables', 'PREGRADO'),
    ('Ingeniería en Sistemas de Información', 'GRADO'),
    ('Ingeniería Electrónica', 'GRADO'),
    ('Ingeniería Mecánica', 'GRADO'),
]


def cargar_carreras(apps, schema_editor):
    Carrera = apps.get_model('biblioteca', 'Carrera')
    for nombre, nivel in CARRERAS:
        if not Carrera.objects.filter(nombre__iexact=nombre).exists():
            Carrera.objects.create(nombre=nombre, nivel=nivel)


class Migration(migrations.Migration):

    dependencies = [
        ('biblioteca', '0010_carreras'),
    ]

    # Al volver atrás no se borra nada: la migración 0010 elimina la tabla completa.
    operations = [
        migrations.RunPython(cargar_carreras, migrations.RunPython.noop),
    ]
