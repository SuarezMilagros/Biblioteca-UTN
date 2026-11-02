"""Informes exportables en CSV (Release 1, decisión D5).

El TFI exige exportar datos (PDF, Excel o CSV). Se eligió CSV con el módulo estándar
de Python, sin dependencias nuevas. El archivo se arma para que Excel en español lo
abra bien: separador punto y coma, acentos en UTF-8 con BOM y fechas dd/mm/aaaa.
"""
import csv

from django.http import HttpResponse
from django.utils import timezone

SEPARADOR = ';'
# Caracteres con los que Excel interpreta una celda como fórmula. Un dato cargado por
# alguien (por ejemplo, un apellido que empiece con "=") no debe ejecutarse al abrir el archivo.
INICIO_DE_FORMULA = ('=', '+', '-', '@', '\t', '\r')


def valor_seguro(valor):
    """Convierte el valor a texto para el CSV, sin dejar que Excel lo tome como fórmula."""
    if valor is None:
        return ''
    if hasattr(valor, 'strftime'):
        return valor.strftime('%d/%m/%Y')
    texto = str(valor)
    if texto.startswith(INICIO_DE_FORMULA):
        return "'" + texto
    return texto


def nombre_de_archivo(*partes):
    return '-'.join(['sigebi', *partes, timezone.localdate().isoformat()]) + '.csv'


def respuesta_csv(nombre_archivo, encabezados, filas):
    """Devuelve un CSV para descargar. `filas` es un iterable de listas de valores."""
    respuesta = HttpResponse(content_type='text/csv; charset=utf-8')
    respuesta['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    # El BOM le indica a Excel que el archivo está en UTF-8 (si no, muestra mal las tildes).
    respuesta.write('﻿')
    escritor = csv.writer(respuesta, delimiter=SEPARADOR)
    escritor.writerow(encabezados)
    for fila in filas:
        escritor.writerow([valor_seguro(valor) for valor in fila])
    return respuesta


class ExportarCSVMixin:
    """Agrega a un ListView la descarga en CSV de lo que se está viendo.

    Con `?formato=csv` se exportan todas las filas que cumplen la búsqueda y los
    filtros de la pantalla, no solo la página actual. La vista define
    `encabezados_csv`, `fila_csv(objeto)` y `nombre_csv()`; puede ajustar la consulta
    con `queryset_csv(queryset)`.
    """

    encabezados_csv = []

    def get(self, request, *args, **kwargs):
        if request.GET.get('formato') == 'csv':
            queryset = self.queryset_csv(self.get_queryset())
            return respuesta_csv(self.nombre_csv(), self.encabezados_csv, (self.fila_csv(o) for o in queryset))
        return super().get(request, *args, **kwargs)

    def queryset_csv(self, queryset):
        return queryset

    def nombre_csv(self):
        raise NotImplementedError

    def fila_csv(self, objeto):
        raise NotImplementedError
