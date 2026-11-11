"""Asigna carreras a las categorías del inventario que ya existen (Release 2, S7-08).

La asignación es la de `biblioteca/clasificacion.py` (acordada por el equipo el 10/11/2026).
Acá va copiada a propósito: una migración tiene que hacer siempre lo mismo, aunque después
cambie el código de la aplicación.

Solo toca las categorías sin ninguna carrera, así que no pisa lo asignado a mano.
En una base sin el inventario (por ejemplo, la de las pruebas) no hace nada.
"""
import unicodedata

from django.db import migrations

TODAS = 'todas'
VIDEOJUEGOS = 'Tecnicatura Universitaria en Desarrollo y Producción de Videojuegos'
PROGRAMACION = 'Tecnicatura Universitaria en Programación'
MANTENIMIENTO = 'Tecnicatura Universitaria en Mantenimiento Industrial'
MECATRONICA = 'Tecnicatura Universitaria en Mecatrónica'
HIGIENE = 'Tecnicatura Universitaria en Higiene y Seguridad en el Trabajo'
LOGISTICA = 'Tecnicatura Universitaria en Logística'
SISTEMAS = 'Ingeniería en Sistemas de Información'
ELECTRONICA = 'Ingeniería Electrónica'
MECANICA = 'Ingeniería Mecánica'

CARRERAS_POR_CATEGORIA = {
    'Proyecto Final': [HIGIENE],
    'Electrónica': [ELECTRONICA, MECATRONICA],
    'Informática': [PROGRAMACION, VIDEOJUEGOS, SISTEMAS],
    'Matemáticas': TODAS,
    'Física': TODAS,
    'Mecánica': [MECANICA, MANTENIMIENTO, MECATRONICA],
    'Administración y negocios': [LOGISTICA, SISTEMAS],
    'Química': TODAS,
    'Diccionario': TODAS,
    'Sociedad': TODAS,
    'Dibujo': [MECANICA, ELECTRONICA, MANTENIMIENTO, MECATRONICA],
}


def clave(texto):
    sin_tildes = ''.join(c for c in unicodedata.normalize('NFKD', texto) if not unicodedata.combining(c))
    return ' '.join(sin_tildes.casefold().split())


def asignar(apps, schema_editor):
    Carrera = apps.get_model('biblioteca', 'Carrera')
    Categoria = apps.get_model('biblioteca', 'Categoria')
    por_clave = {clave(nombre): carreras for nombre, carreras in CARRERAS_POR_CATEGORIA.items()}
    for categoria in Categoria.objects.filter(carreras__isnull=True):
        carreras = por_clave.get(clave(categoria.nombre))
        if carreras is None:
            continue
        elegidas = Carrera.objects.all() if carreras == TODAS else Carrera.objects.filter(nombre__in=carreras)
        categoria.carreras.add(*elegidas)


class Migration(migrations.Migration):

    dependencies = [
        ('biblioteca', '0011_carreras_de_la_extension'),
    ]

    # Al volver atrás no se quita nada: lo que haya quedado asignado se puede corregir desde Categorías.
    operations = [
        migrations.RunPython(asignar, migrations.RunPython.noop),
    ]
