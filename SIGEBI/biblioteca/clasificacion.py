"""Carreras de cada categoría del inventario (Release 2, S7-08).

Asignación acordada por el equipo el 10/11/2026. Un libro pertenece a las carreras de su categoría (D-R2-6),
así que con esto cada alumno o profesor ve los libros de sus carreras.

Se aplica en dos momentos:
- la migración 0012, sobre las categorías que ya existen (la base de cada integrante);
- `importar_inventario`, sobre las categorías que crea al cargar el Excel (la instalación de producción).

Solo se tocan las categorías que todavía no tienen ninguna carrera: lo que el personal haya asignado
a mano desde la pantalla Categorías no se pisa.
"""
from .importacion import clave
from .models import Carrera, Categoria

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

# Nombre de la categoría -> carreras. Los nombres se comparan sin tildes ni mayúsculas.
CARRERAS_POR_CATEGORIA = {
    # Los 82 libros son proyectos finales de Higiene y Seguridad (revisado el 10/11/2026).
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


def asignar_carreras_a_categorias():
    """Asigna carreras a las categorías conocidas que todavía no tienen ninguna.

    Devuelve la lista de categorías a las que se les asignaron carreras.
    """
    por_clave = {clave(nombre): carreras for nombre, carreras in CARRERAS_POR_CATEGORIA.items()}
    clasificadas = []
    for categoria in Categoria.objects.filter(carreras__isnull=True).order_by('nombre'):
        carreras = por_clave.get(clave(categoria.nombre))
        if carreras is None:
            continue
        if carreras == TODAS:
            elegidas = Carrera.objects.all()
        else:
            elegidas = Carrera.objects.filter(nombre__in=carreras)
        if elegidas:
            categoria.carreras.add(*elegidas)
            clasificadas.append(categoria)
    return clasificadas
