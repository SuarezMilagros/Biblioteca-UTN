"""Carga en SIGEBI el inventario en Excel que usaba la biblioteca (Sprint 6, S6-10).

Uso:
    python manage.py importar_inventario inventario.xlsx            # modo prueba: no guarda nada
    python manage.py importar_inventario inventario.xlsx --detalle  # además lista avisos y autores nuevos
    python manage.py importar_inventario inventario.xlsx --guardar  # guarda

Se puede correr varias veces: los ejemplares cuyo código ya existe se omiten.
Las decisiones sobre datos incompletos están en biblioteca/importacion.py.
"""
from django.core.management.base import BaseCommand, CommandError

from biblioteca.importacion import ErrorDePlanilla, importar, leer_planilla


class Command(BaseCommand):
    help = 'Importa el inventario en Excel (.xlsx) de la biblioteca. Sin --guardar, solo muestra qué haría.'

    def add_arguments(self, parser):
        parser.add_argument('archivo', help='Ruta del archivo .xlsx.')
        parser.add_argument('--hoja', help='Nombre de la hoja. Por defecto, la primera.')
        parser.add_argument('--guardar', action='store_true', help='Guarda los datos (sin esta opción no se guarda nada).')
        parser.add_argument('--detalle', action='store_true', help='Lista cada aviso y los autores nuevos para revisarlos.')

    def handle(self, *args, archivo, hoja, guardar, detalle, **options):
        try:
            nombre_hoja, filas = leer_planilla(archivo, hoja)
        except ErrorDePlanilla as error:
            raise CommandError(str(error))

        resultado = importar(filas, guardar=guardar)
        escribir = self.stdout.write

        escribir(f'Archivo: {archivo} (hoja "{nombre_hoja}")')
        if guardar:
            escribir(self.style.SUCCESS('Datos guardados.'))
        else:
            escribir(self.style.WARNING(
                'MODO PRUEBA: no se guardó nada. Para guardar, repetí el comando con --guardar.'
            ))

        escribir('')
        escribir(f'Filas leídas: {resultado.filas_leidas}')
        escribir(f'Ejemplares nuevos: {resultado.ejemplares_nuevos}'
                 f' (con código provisorio SN-: {resultado.provisorios})')
        escribir(f'Ya cargados antes (se omiten): {len(resultado.omitidas)}')
        escribir(f'Filas rechazadas: {len(resultado.rechazadas)}')
        nuevos = resultado.nuevos
        escribir(
            f'Nuevos en el catálogo: {nuevos["libro"]} libros, {nuevos["autor"]} autores, '
            f'{nuevos["editorial"]} editoriales, {nuevos["categoria"]} categorías'
        )
        if resultado.categorias_clasificadas:
            escribir('Categorías con carreras asignadas: ' + ', '.join(resultado.categorias_clasificadas))

        if resultado.rechazadas:
            escribir('')
            escribir(self.style.ERROR('Filas rechazadas (corregirlas en el Excel y volver a importar):'))
            for numero, id_inventario, motivo in resultado.rechazadas:
                escribir(f'  Fila {numero} (ID {id_inventario if id_inventario is not None else "-"}): {motivo}')

        if resultado.prestados:
            escribir('')
            escribir(self.style.WARNING(
                f'Figuraban como prestados en el Excel ({len(resultado.prestados)}). Se cargaron disponibles: '
                'si siguen prestados, registrar el préstamo en SIGEBI.'
            ))
            for numero, codigo in resultado.prestados:
                escribir(f'  Fila {numero}: {codigo}')

        escribir('')
        escribir(f'Avisos: {len(resultado.avisos)}' + ('' if detalle else ' (ver con --detalle)'))
        if detalle:
            for numero, codigo, aviso in resultado.avisos:
                escribir(f'  Fila {numero} ({codigo}): {aviso}')
            escribir('')
            escribir(f'Autores nuevos ({len(resultado.autores_nuevos)}). Revisar nombre y apellido:')
            for numero, nombre, apellido in resultado.autores_nuevos:
                escribir(f'  Fila {numero}: apellido "{apellido}", nombre "{nombre}"')
