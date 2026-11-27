"""Quita los datos ficticios que carga `cargar_datos_prueba` (S8-12), para dejar el sitio con el inventario real.

Uso (en la Console de Railway, con /app/.venv/bin/python):
    python manage.py quitar_datos_prueba              # modo prueba: muestra qué quitaría, no borra nada
    python manage.py quitar_datos_prueba --confirmar  # los quita

Solo toca lo que reconoce como datos de prueba, por los mismos datos fijos de `cargar_datos_prueba`:
- los ejemplares ADM-001, PRG-001, ... y los libros a los que pertenecen (con todos sus ejemplares);
- las personas de prueba (por documento) y sus cuentas del portal, si tenían;
- la cuenta «bibliotecario_prueba», que figura como quien registró los préstamos de prueba;
- los préstamos, avisos, reservas y opiniones de esos ejemplares, libros o personas;
- los autores, editoriales y categorías de prueba que ya no usa ningún libro (una categoría que también usa el
  inventario real, como «Informática», queda).

Todo se hace en una sola transacción: si algo no se puede quitar (por ejemplo, material digital que subió una
cuenta de prueba), no se quita nada y se informa. Antes hay que poner SIGEBI_DATOS_DEMO en False: si no, la
próxima publicación los vuelve a cargar.
"""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import ProtectedError, Q

from biblioteca.models import (
    Autor, AvisoPrestamo, Categoria, Editorial, Ejemplar, Libro, Opinion, Persona, Prestamo, Reserva,
)
from config.entorno import activado

from .cargar_datos_prueba import AUTORES, CATEGORIAS, EDITORIALES, LIBROS, PERSONAS

USUARIO_DE_PRUEBA = 'bibliotecario_prueba'


class Deshacer(Exception):
    """Sale de la transacción en modo prueba, para deshacer lo que se quitó."""


def codigos_de_prueba():
    return [f'{prefijo}-{n:03d}' for _, _, _, _, _, prefijo, cantidad in LIBROS for n in range(1, cantidad + 1)]


def contar_lo_que_queda():
    return (f'{Libro.objects.count()} libros, {Ejemplar.objects.count()} ejemplares, '
            f'{Persona.objects.count()} personas, {Prestamo.objects.count()} préstamos '
            f'y {Reserva.objects.count()} reservas')


def quitar(confirmar=False):
    """Quita los datos de prueba. Devuelve ([(qué, cantidad)], lo que queda en la base).

    Sin confirmar, hace exactamente lo mismo y lo deshace al final (como la importación del inventario).
    """
    Usuario = get_user_model()
    cantidades = []
    restante = ''

    def borrar(nombre, consulta):
        cantidad = consulta.count()
        consulta.delete()
        cantidades.append((nombre, cantidad))

    try:
        with transaction.atomic():
            libros = Libro.objects.filter(
                Q(ejemplares__codigo_inventario__in=codigos_de_prueba())
                | Q(titulo__in=[l[0] for l in LIBROS], isbn__in=[l[1] for l in LIBROS])
            ).distinct()
            libros_ids = list(libros.values_list('pk', flat=True))
            ejemplares = Ejemplar.objects.filter(libro__in=libros_ids)
            ejemplares_ids = list(ejemplares.values_list('pk', flat=True))
            personas_ids = list(Persona.objects.filter(documento__in=[p[2] for p in PERSONAS]).values_list('pk', flat=True))
            cuentas_ids = [c for c in Persona.objects.filter(pk__in=personas_ids).values_list('cuenta', flat=True) if c]
            usuario_prueba = Usuario.objects.filter(username=USUARIO_DE_PRUEBA, is_superuser=False).first()

            prestamos_ids = list(Prestamo.objects.filter(
                Q(ejemplar__in=ejemplares_ids) | Q(persona__in=personas_ids)
                | Q(usuario_sistema=usuario_prueba)
            ).values_list('pk', flat=True))
            borrar('Avisos de préstamos', AvisoPrestamo.objects.filter(prestamo__in=prestamos_ids))
            borrar('Reservas', Reserva.objects.filter(
                Q(libro__in=libros_ids) | Q(ejemplar__in=ejemplares_ids) | Q(persona__in=personas_ids)
                | Q(prestamo__in=prestamos_ids)
            ))
            borrar('Opiniones', Opinion.objects.filter(Q(libro__in=libros_ids) | Q(persona__in=personas_ids)))
            borrar('Préstamos', Prestamo.objects.filter(pk__in=prestamos_ids))
            borrar('Ejemplares', Ejemplar.objects.filter(pk__in=ejemplares_ids))
            # Las portadas y fotos de lo que se quita se borran del disco recién cuando se confirma.
            archivos = [(libro.imagen.storage, libro.imagen.name)
                        for libro in Libro.objects.filter(pk__in=libros_ids).exclude(imagen='')]
            archivos += [(persona.foto.storage, persona.foto.name)
                         for persona in Persona.objects.filter(pk__in=personas_ids).exclude(foto='')]
            borrar('Libros', Libro.objects.filter(pk__in=libros_ids))
            borrar('Personas', Persona.objects.filter(pk__in=personas_ids))
            # Cuentas del portal de las personas de prueba y la del bibliotecario de prueba (nunca una del personal real).
            cuentas = Usuario.objects.filter(pk__in=cuentas_ids, is_staff=False, is_superuser=False)
            if usuario_prueba is not None:
                cuentas = cuentas | Usuario.objects.filter(pk=usuario_prueba.pk)
            borrar('Cuentas de prueba', cuentas)

            autores = Q()
            for nombre, apellido in AUTORES:
                autores |= Q(nombre=nombre, apellido=apellido)
            borrar('Autores', Autor.objects.filter(autores, libros__isnull=True))
            borrar('Editoriales', Editorial.objects.filter(nombre__in=EDITORIALES, libros__isnull=True))
            borrar('Categorías', Categoria.objects.filter(nombre__in=[c[0] for c in CATEGORIAS], libros__isnull=True))
            restante = contar_lo_que_queda()
            if not confirmar:
                raise Deshacer
            transaction.on_commit(lambda: [almacen.delete(nombre) for almacen, nombre in archivos])
    except Deshacer:
        pass
    except ProtectedError as error:
        bloqueos = sorted({f'{objeto._meta.verbose_name}: {objeto}' for objeto in error.protected_objects})
        raise CommandError(
            'No se quitó nada: hay registros que dependen de los datos de prueba y este comando no borra. '
            'Quitarlos a mano o avisar al equipo de desarrollo: ' + '; '.join(bloqueos[:10]) + '.'
        )
    return cantidades, restante


class Command(BaseCommand):
    help = 'Quita los datos ficticios de cargar_datos_prueba. Sin --confirmar, solo muestra qué quitaría.'

    def add_arguments(self, parser):
        parser.add_argument('--confirmar', action='store_true', help='Quita los datos (sin esta opción no borra nada).')

    def handle(self, *args, confirmar, **options):
        if activado(os.environ, 'SIGEBI_DATOS_DEMO'):
            raise CommandError(
                'SIGEBI_DATOS_DEMO está activada: la próxima publicación volvería a cargar los datos de prueba. '
                'Ponela en False en Railway › Variables, publicá, y después corré este comando.'
            )
        cantidades, restante = quitar(confirmar=confirmar)
        escribir = self.stdout.write
        if confirmar:
            escribir(self.style.SUCCESS('Datos de prueba quitados.'))
        else:
            escribir(self.style.WARNING(
                'MODO PRUEBA: no se borró nada. Para quitarlos, repetí el comando con --confirmar.'
            ))
        escribir('')
        for nombre, cantidad in cantidades:
            escribir(f'{nombre}: {cantidad}')
        escribir('')
        escribir(f'{"Quedan" if confirmar else "Quedarían"} en la base: {restante}.')
