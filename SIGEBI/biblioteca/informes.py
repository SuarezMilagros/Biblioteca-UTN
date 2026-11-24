"""Informes exportables en CSV (Release 1, decisión D5) y en PDF (pedido del equipo, 24/11/2026).

CSV: con el módulo estándar de Python. El archivo se arma para que Excel en español lo abra bien:
separador punto y coma, acentos en UTF-8 con BOM y fechas dd/mm/aaaa.

PDF: con fpdf2 (puro Python, no necesita instalar nada en el sistema operativo). Tiene las mismas
columnas y filas que el CSV, en una tabla con encabezado repetido en cada hoja y número de página.
"""
import csv

from django.http import HttpResponse
from django.utils import timezone
from fpdf import FPDF
from fpdf.enums import TableCellFillMode
from fpdf.fonts import FontFace

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


def texto_pdf(valor):
    """El valor como texto para el PDF. Las fuentes estándar del PDF usan Latin-1, que tiene todas las letras del
    español; un carácter fuera de ese juego (por ejemplo, un emoji) se reemplaza por "?" en lugar de fallar."""
    if valor is None:
        return ''
    texto = valor.strftime('%d/%m/%Y') if hasattr(valor, 'strftime') else str(valor)
    return texto.encode('latin-1', 'replace').decode('latin-1')


class InformePDF(FPDF):
    def __init__(self, titulo, detalle, horizontal):
        super().__init__(orientation='L' if horizontal else 'P', unit='mm', format='A4')
        self.titulo, self.detalle = texto_pdf(titulo), texto_pdf(detalle)
        self.set_margins(12, 12, 12)
        self.set_auto_page_break(auto=True, margin=14)
        self.alias_nb_pages()
        self.set_title(self.titulo)
        self.set_author('SIGEBI - Biblioteca UTN FRT')

    def header(self):
        self.set_font('Helvetica', 'B', 13)
        self.cell(0, 7, self.titulo, new_x='LMARGIN', new_y='NEXT')
        self.set_font('Helvetica', '', 8.5)
        self.set_text_color(95, 102, 114)
        generado = timezone.localtime().strftime('%d/%m/%Y %H:%M')
        self.cell(0, 5, texto_pdf(f'{self.detalle} · Generado el {generado}'), new_x='LMARGIN', new_y='NEXT')
        self.set_text_color(0, 0, 0)
        self.ln(3)

    def footer(self):
        self.set_y(-10)
        self.set_font('Helvetica', '', 7.5)
        self.set_text_color(95, 102, 114)
        self.cell(0, 5, texto_pdf('SIGEBI · Biblioteca UTN FRT, Extensión Áulica Concepción'), align='L')
        self.cell(0, 5, f'Página {self.page_no()} de {{nb}}', align='R')


RELLENO = 1.5  # mm de margen interno a cada lado de la celda
ANCHO_MAXIMO = 70  # mm: un texto más largo ocupa varias líneas


def ancho_de(pdf, texto, negrita=False):
    pdf.set_font(style='B' if negrita else '')
    return pdf.get_string_width(texto) + 2 * RELLENO + 0.5


def anchos_de_columnas(pdf, encabezados, filas):
    """Calcula el ancho de cada columna (en mm) para que ninguna palabra quede cortada.

    Cada columna recibe al menos el ancho de su palabra más larga; el espacio que sobra se reparte
    según cuánto más necesita cada una para mostrar su texto en una sola línea.
    Si ni siquiera entran las palabras, se achica la letra.
    """
    disponible = pdf.epw
    while True:
        minimos, naturales = [], []
        for i, encabezado in enumerate(encabezados):
            columna = [fila[i] for fila in filas]
            palabras = [(p, True) for p in encabezado.split()] + [(p, False) for v in columna for p in v.split()]
            minimo = max([ancho_de(pdf, p, n) for p, n in palabras] or [2 * RELLENO])
            natural = max([ancho_de(pdf, encabezado, True)] + [ancho_de(pdf, v) for v in columna])
            minimos.append(minimo)
            naturales.append(max(minimo, min(natural, ANCHO_MAXIMO)))
        if sum(minimos) <= disponible or pdf.font_size_pt <= 6:
            break
        pdf.set_font(size=pdf.font_size_pt - 0.5)
    if sum(naturales) <= disponible:
        return [n * disponible / sum(naturales) for n in naturales]
    if sum(minimos) >= disponible:
        return minimos
    faltante = [n - m for n, m in zip(naturales, minimos)]
    sobrante = disponible - sum(minimos)
    return [m + sobrante * f / sum(faltante) for m, f in zip(minimos, faltante)]


def respuesta_pdf(nombre_archivo, titulo, detalle, encabezados, filas):
    """Devuelve un PDF para descargar con la tabla del informe. Con muchas columnas, la hoja va apaisada."""
    filas = [[texto_pdf(valor) for valor in fila] for fila in filas]
    encabezados = [texto_pdf(encabezado) for encabezado in encabezados]
    pdf = InformePDF(titulo, detalle, horizontal=len(encabezados) > 6)
    pdf.add_page()
    if not filas:
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(0, 8, 'No hay datos para este informe.')
    else:
        pdf.set_font('Helvetica', '', 8 if len(encabezados) > 6 else 9)
        anchos = anchos_de_columnas(pdf, encabezados, filas)
        pdf.set_font(style='')
        with pdf.table(
            col_widths=anchos, width=sum(anchos), align='LEFT', text_align='LEFT',
            line_height=pdf.font_size * 1.45, padding=(1.2, RELLENO), v_align='MIDDLE',
            # El encabezado se repite arriba de cada hoja.
            headings_style=FontFace(emphasis='BOLD', color=(180, 48, 14), fill_color=(255, 240, 234)),
            cell_fill_color=(245, 246, 248), cell_fill_mode=TableCellFillMode.ROWS,
            borders_layout='HORIZONTAL_LINES',
        ) as tabla:
            fila_de_titulos = tabla.row()
            for encabezado in encabezados:
                fila_de_titulos.cell(encabezado)
            for fila in filas:
                fila_pdf = tabla.row()
                for valor in fila:
                    fila_pdf.cell(valor)
    respuesta = HttpResponse(bytes(pdf.output()), content_type='application/pdf')
    respuesta['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    return respuesta


class ExportarCSVMixin:
    """Agrega a un ListView la descarga en CSV o en PDF de lo que se está viendo.

    Con `?formato=csv` o `?formato=pdf` se exportan todas las filas que cumplen la búsqueda y los
    filtros de la pantalla, no solo la página actual. La vista define
    `encabezados_csv`, `fila_csv(objeto)` y `nombre_csv()`; puede ajustar la consulta
    con `queryset_csv(queryset)`. Para el PDF usa además `titulo_informe` y `detalle_informe()`.
    """

    encabezados_csv = []
    titulo_informe = 'Informe'

    def get(self, request, *args, **kwargs):
        formato = request.GET.get('formato')
        if formato in ('csv', 'pdf'):
            filas = (self.fila_csv(o) for o in self.queryset_csv(self.get_queryset()))
            if formato == 'csv':
                return respuesta_csv(self.nombre_csv(), self.encabezados_csv, filas)
            nombre = self.nombre_csv().removesuffix('.csv') + '.pdf'
            return respuesta_pdf(nombre, self.titulo_informe, self.detalle_informe(), self.encabezados_csv, filas)
        return super().get(request, *args, **kwargs)

    def detalle_informe(self):
        """Qué incluye el informe (filtros y búsqueda). Se muestra debajo del título del PDF."""
        q = self.request.GET.get('q', '').strip()
        return f'Búsqueda: «{q}»' if q else 'Sin búsqueda'

    def queryset_csv(self, queryset):
        return queryset

    def nombre_csv(self):
        raise NotImplementedError

    def fila_csv(self, objeto):
        raise NotImplementedError
