"""Importación del inventario en Excel que usaba la biblioteca (Sprint 6, tarjeta S6-10).

Cada fila del Excel es un ejemplar físico. Decisiones del equipo (03/11/2026):

- I1. Sin numeración: se asigna un código provisorio ``SN-<ID>`` (por ejemplo, SN-0045), editable después.
- I2. Varios autores en una celda: el libro queda con el primero; los demás van a las observaciones.
- I3. Sin editorial: se usa la editorial "Sin editorial".
- I4. Se lee el archivo .xlsx directamente (openpyxl).
- I5. ID o numeración repetidos en el Excel, o una celda con dos numeraciones: la fila se rechaza y se informa.
- I6. "Prestado" en el Excel: el ejemplar se carga disponible y se informa. El préstamo se registra a mano,
  porque el Excel no dice a quién ni desde cuándo (no se inventan personas ni fechas).
- I7. La fecha de inventario se guarda en las observaciones del ejemplar.
- I8. Nombre y apellido del autor: la última palabra es el apellido (se revisa con --detalle).

La lectura (``leer_planilla``) no toca la base. La carga (``importar``) trabaja dentro de una transacción:
en modo prueba la deshace al final, así el informe muestra exactamente lo que pasaría al guardar.
"""
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from .models import Autor, Categoria, Editorial, Ejemplar, Libro

SIN_EDITORIAL = 'Sin editorial'
SIN_AUTOR = 'Sin autor'
PREFIJO_PROVISORIO = 'SN-'

# Encabezado del Excel (sin tildes y en mayúsculas) -> dato.
COLUMNAS = {
    'ID': 'id',
    'NOMBRE': 'titulo',
    'TITULO': 'titulo',
    'AUTOR': 'autor',
    'CATEGORIA': 'categoria',
    'EDITORIAL': 'editorial',
    'NUMERACION': 'numeracion',
    'ISBN': 'isbn',
    'OBSERVACIONES': 'observaciones',
    'FECHA DE INVENTARIO': 'fecha',
    'ESTADO': 'estado',
}
OBLIGATORIAS = ('id', 'titulo', 'autor', 'categoria', 'editorial', 'numeracion')
FILAS_PARA_BUSCAR_ENCABEZADO = 20

VALORES_VACIOS = {'', '-', '--', '—', '–', '- -'}
MESES = {
    'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6, 'julio': 7,
    'agosto': 8, 'septiembre': 9, 'setiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12,
}


class ErrorDePlanilla(Exception):
    """El archivo no se puede leer o no tiene las columnas necesarias."""


# ---------------------------------------------------------------------------
# Limpieza de valores
# ---------------------------------------------------------------------------

def sin_tildes(texto):
    descompuesto = unicodedata.normalize('NFKD', texto)
    return ''.join(c for c in descompuesto if not unicodedata.combining(c))


def clave(texto):
    """Forma de comparar nombres: sin tildes, sin mayúsculas y con espacios simples."""
    return ' '.join(sin_tildes(texto).casefold().split())


def lineas(valor):
    """Devuelve las líneas no vacías de una celda. Un guion solo cuenta como vacío."""
    if valor is None:
        return []
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    texto = str(valor).replace('\r\n', '\n').replace('\r', '\n')
    resultado = [' '.join(linea.split()) for linea in texto.split('\n')]
    resultado = [linea for linea in resultado if linea]
    if len(resultado) == 1 and resultado[0] in VALORES_VACIOS:
        return []
    return resultado


def texto(valor):
    """Celda en una sola línea."""
    return ' '.join(lineas(valor))


def entero(valor):
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor
    if isinstance(valor, float) and valor.is_integer():
        return int(valor)
    contenido = texto(valor)
    return int(contenido) if contenido.isdigit() else None


# Un punto separa autores ("Koontz. Weihrich") solo si lo precede una palabra de dos letras o más:
# así no se cortan las iniciales ("A. Bruce Carlson", "B.P. Lathi", "Arthur I. Vogel").
_SEPARADOR_DE_AUTORES_CON_PUNTO = re.compile(r'(?<=[^\W\d_]{2})\.\s+')
# Otros separadores: punto y coma, barra, "&" e "y" ("Terman y Pettit").
_SEPARADORES_DE_AUTORES = re.compile(r'\s*[;/&]\s*|\s+y\s+')
# Títulos que se quitan del nombre ("Lic. Guillermo Martinez Guzman").
_TITULOS = re.compile(r'^(lic|ing|dr|dra|prof|mg|mgter|arq|cr|cra|sr|sra)\.\s*', re.IGNORECASE)
_PARTICULAS = {'de', 'del', 'la', 'las', 'los', 'van', 'von', 'di', 'da', 'du', 'le'}
_SUFIJOS = {'jr', 'jr.', 'sr', 'sr.', 'hijo'}


def separar_autores(valor):
    autores = []
    for linea in lineas(valor):
        for parte in _SEPARADORES_DE_AUTORES.split(linea):
            for nombre in _SEPARADOR_DE_AUTORES_CON_PUNTO.split(_TITULOS.sub('', parte.strip())):
                nombre = ' '.join(_TITULOS.sub('', nombre.strip()).split()).strip(' ,')
                if nombre and nombre not in VALORES_VACIOS:
                    autores.append(nombre)
    return autores


def nombre_y_apellido(nombre_completo):
    """Separa nombre y apellido (decisión I8).

    "Apellido, Nombre" se respeta. Si no hay coma, la última palabra es el apellido, junto con
    las partículas que la preceden ("Armando E. De Giusti" -> "De Giusti") y sufijos como "Jr.".
    """
    if nombre_completo.count(',') == 1:
        apellido, nombre = (parte.strip() for parte in nombre_completo.split(','))
        if apellido and nombre:
            return nombre, apellido
    palabras = nombre_completo.replace(',', ' ').split()
    sufijo = []
    if len(palabras) > 1 and palabras[-1].lower() in _SUFIJOS:
        sufijo = [palabras.pop().capitalize().rstrip('.') + '.']
    corte = len(palabras) - 1
    while corte > 1 and palabras[corte - 1].lower() in _PARTICULAS:
        corte -= 1
    return ' '.join(palabras[:corte]), ' '.join(palabras[corte:] + sufijo)


_CANDIDATO_ISBN = re.compile(r'[0-9][0-9\- ]{8,20}[0-9Xx]')


def extraer_isbn(valor):
    """Devuelve el ISBN de la celda (prefiere el de 13 dígitos) o '' si no reconoce ninguno."""
    encontrados = {}
    for candidato in _CANDIDATO_ISBN.findall(texto(valor).replace('\xa0', ' ')):
        digitos = re.sub(r'[^0-9Xx]', '', candidato).upper()
        if len(digitos) in (10, 13):
            formateado = candidato.replace(' ', '').strip('-')
            encontrados.setdefault(len(digitos), formateado if len(formateado) <= 20 else digitos)
    return encontrados.get(13) or encontrados.get(10) or ''


def fecha_de_inventario(valor):
    """Devuelve (fecha, texto_original). Acepta fechas de Excel y textos como '16 de octubre de 2024'."""
    if isinstance(valor, datetime):
        return valor.date(), ''
    if isinstance(valor, date):
        return valor, ''
    contenido = texto(valor)
    if not contenido:
        return None, ''
    coincidencia = re.search(r'(\d{1,2}) de ([a-záéíóú]+) de (\d{4})', contenido.lower())
    if coincidencia and sin_tildes(coincidencia.group(2)) in MESES:
        dia, mes, anio = coincidencia.groups()
        try:
            return date(int(anio), MESES[sin_tildes(mes)], int(dia)), ''
        except ValueError:
            pass
    return None, contenido


# ---------------------------------------------------------------------------
# Lectura del Excel
# ---------------------------------------------------------------------------

@dataclass
class FilaInventario:
    numero: int
    id_inventario: int | None = None
    titulo: str = ''
    autores: list = field(default_factory=list)
    categoria: str = ''
    editorial: str = ''
    codigo: str = ''
    codigo_provisorio: bool = False
    isbn: str = ''
    observaciones: str = ''
    prestado: bool = False
    errores: list = field(default_factory=list)
    avisos: list = field(default_factory=list)

    @property
    def valida(self):
        return not self.errores


def _ubicar_encabezado(filas):
    for indice, fila in enumerate(filas[:FILAS_PARA_BUSCAR_ENCABEZADO]):
        columnas = {}
        for posicion, valor in enumerate(fila):
            dato = COLUMNAS.get(clave(texto(valor)).upper())
            if dato and dato not in columnas:
                columnas[dato] = posicion
        if 'id' in columnas and 'titulo' in columnas:
            faltan = [dato for dato in OBLIGATORIAS if dato not in columnas]
            if faltan:
                raise ErrorDePlanilla(
                    'Faltan columnas en el encabezado: ' + ', '.join(sorted(faltan)) + '.'
                )
            return indice, columnas
    raise ErrorDePlanilla(
        'No se encontró el encabezado (una fila con las columnas ID y NOMBRE) '
        f'en las primeras {FILAS_PARA_BUSCAR_ENCABEZADO} filas.'
    )


def _armar_fila(numero, valores, columnas):
    def celda(dato):
        posicion = columnas.get(dato)
        return valores[posicion] if posicion is not None and posicion < len(valores) else None

    fila = FilaInventario(numero=numero)
    observaciones = lineas(celda('observaciones'))

    fila.id_inventario = entero(celda('id'))
    if fila.id_inventario is None:
        fila.errores.append(f'ID inválido o vacío ("{texto(celda("id"))}").')

    fila.titulo = texto(celda('titulo'))
    if not fila.titulo:
        fila.errores.append('Falta el título (columna NOMBRE).')
    elif len(fila.titulo) > Libro._meta.get_field('titulo').max_length:
        fila.errores.append('El título supera los 255 caracteres.')

    fila.autores = separar_autores(celda('autor'))
    if not fila.autores:
        fila.autores = [SIN_AUTOR]
        fila.avisos.append(f'Sin autor: se asigna "{SIN_AUTOR}".')
    elif len(fila.autores) > 1:
        observaciones.append('Otros autores: ' + '; '.join(fila.autores[1:]) + '.')

    fila.categoria = texto(celda('categoria'))
    if not fila.categoria:
        fila.errores.append('Falta la categoría.')

    fila.editorial = texto(celda('editorial')) or SIN_EDITORIAL

    numeracion = lineas(celda('numeracion'))
    if len(numeracion) > 1 or (numeracion and len(numeracion[0].split()) > 1):
        fila.errores.append(
            'La numeración tiene más de un valor ("' + ' / '.join(numeracion) + '"): corregirla en el Excel.'
        )
    elif numeracion:
        fila.codigo = Ejemplar.normalizar_codigo(numeracion[0])
    elif fila.id_inventario is not None:
        fila.codigo = f'{PREFIJO_PROVISORIO}{fila.id_inventario:04d}'
        fila.codigo_provisorio = True
    if len(fila.codigo) > Ejemplar._meta.get_field('codigo_inventario').max_length:
        fila.errores.append('La numeración supera los 30 caracteres.')

    isbn_original = texto(celda('isbn'))
    fila.isbn = extraer_isbn(celda('isbn'))
    if isbn_original and not fila.isbn:
        fila.avisos.append(f'ISBN no reconocido ("{isbn_original}"): el libro queda sin ISBN.')

    fecha, fecha_sin_formato = fecha_de_inventario(celda('fecha'))
    if fecha:
        observaciones.append(f'Inventariado el {fecha:%d/%m/%Y}.')
    elif fecha_sin_formato:
        observaciones.append(f'Fecha de inventario: {fecha_sin_formato}.')

    estado = clave(texto(celda('estado')))
    if estado == 'prestado':
        fila.prestado = True
        observaciones.append('En el inventario de Excel figuraba como prestado.')
    elif estado not in ('', 'disponible'):
        fila.avisos.append(f'Estado desconocido ("{texto(celda("estado"))}"): se carga disponible.')

    fila.observaciones = '\n'.join(observaciones)
    return fila


def _marcar_repetidos(filas):
    # El código provisorio sale del ID: si el ID se repite, ya se informa por el ID.
    for nombre, obtener in (
        ('El ID {} está repetido', lambda fila: fila.id_inventario),
        ('La numeración {} está repetida', lambda fila: None if fila.codigo_provisorio else fila.codigo or None),
    ):
        apariciones = defaultdict(list)
        for fila in filas:
            valor = obtener(fila)
            if valor is not None:
                apariciones[valor].append(fila)
        for valor, repetidas in apariciones.items():
            if len(repetidas) > 1:
                numeros = ', '.join(str(fila.numero) for fila in repetidas)
                for fila in repetidas:
                    fila.errores.append(nombre.format(valor) + f' en el Excel (filas {numeros}).')


def leer_planilla(ruta, hoja=None):
    """Lee el Excel y devuelve (nombre de la hoja, filas). No toca la base de datos."""
    from openpyxl import load_workbook
    from openpyxl.utils.exceptions import InvalidFileException
    from zipfile import BadZipFile

    try:
        libro = load_workbook(ruta, read_only=True, data_only=True)
    except FileNotFoundError:
        raise ErrorDePlanilla(f'No existe el archivo "{ruta}".')
    except (InvalidFileException, BadZipFile, KeyError, OSError):
        raise ErrorDePlanilla(f'"{ruta}" no es un archivo de Excel (.xlsx) válido.')
    try:
        if hoja is None:
            planilla = libro.worksheets[0]
        elif hoja in libro.sheetnames:
            planilla = libro[hoja]
        else:
            raise ErrorDePlanilla(
                f'No existe la hoja "{hoja}". Hojas del archivo: ' + ', '.join(libro.sheetnames) + '.'
            )
        todas = [list(valores) for valores in planilla.iter_rows(values_only=True)]
        nombre_hoja = planilla.title
    finally:
        libro.close()

    indice_encabezado, columnas = _ubicar_encabezado(todas)
    filas = []
    for indice in range(indice_encabezado + 1, len(todas)):
        valores = todas[indice]
        if not any(texto(valor) for valor in valores):
            continue
        filas.append(_armar_fila(indice + 1, valores, columnas))
    _marcar_repetidos(filas)
    return nombre_hoja, filas


# ---------------------------------------------------------------------------
# Carga en la base
# ---------------------------------------------------------------------------

@dataclass
class Resultado:
    filas_leidas: int = 0
    ejemplares_nuevos: int = 0
    provisorios: int = 0
    omitidas: list = field(default_factory=list)      # (fila, código) ya cargadas antes
    rechazadas: list = field(default_factory=list)    # (fila, id, motivo)
    avisos: list = field(default_factory=list)        # (fila, código, aviso)
    prestados: list = field(default_factory=list)     # (fila, código)
    nuevos: Counter = field(default_factory=Counter)  # modelo -> cantidad creada
    autores_nuevos: list = field(default_factory=list)


class _Catalogo:
    """Busca o crea categorías, autores, editoriales y libros sin duplicarlos (sin distinguir tildes ni mayúsculas)."""

    def __init__(self):
        self.cache = {}
        self.creados_en_fila = []

    def _obtener(self, tipo, llave, buscar, crear):
        if (tipo, llave) in self.cache:
            return self.cache[(tipo, llave)]
        objeto = buscar()
        if objeto is None:
            objeto = crear()
            self.creados_en_fila.append((tipo, llave, objeto))
        self.cache[(tipo, llave)] = objeto
        return objeto

    def descartar_fila(self):
        for tipo, llave, _ in self.creados_en_fila:
            self.cache.pop((tipo, llave), None)
        self.creados_en_fila = []

    def confirmar_fila(self):
        creados, self.creados_en_fila = self.creados_en_fila, []
        return creados

    def categoria(self, nombre):
        return self._obtener(
            'categoria', clave(nombre),
            lambda: _buscar(Categoria.objects.all(), nombre=nombre),
            lambda: Categoria.objects.create(nombre=nombre),
        )

    def editorial(self, nombre):
        return self._obtener(
            'editorial', clave(nombre),
            lambda: _buscar(Editorial.objects.all(), nombre=nombre),
            lambda: Editorial.objects.create(nombre=nombre),
        )

    def autor(self, nombre_completo):
        nombre, apellido = ('', SIN_AUTOR) if nombre_completo == SIN_AUTOR else nombre_y_apellido(nombre_completo)
        return self._obtener(
            'autor', clave(nombre_completo),
            lambda: _buscar(Autor.objects.all(), nombre=nombre, apellido=apellido),
            lambda: Autor.objects.create(nombre=nombre, apellido=apellido),
        )

    def libro(self, fila, autor, editorial, categoria):
        return self._obtener(
            'libro', (clave(fila.titulo), autor.pk, editorial.pk),
            lambda: _buscar(Libro.objects.filter(autor=autor, editorial=editorial), titulo=fila.titulo),
            lambda: Libro.objects.create(
                titulo=fila.titulo, isbn=fila.isbn, autor=autor, editorial=editorial, categoria=categoria
            ),
        )


def _buscar(consulta, **campos):
    """Primer registro cuyos campos coinciden sin distinguir tildes ni mayúsculas."""
    filtro = {f'{campo}__unaccent__iexact': valor for campo, valor in campos.items()}
    return consulta.filter(**filtro).order_by('pk').first()


def importar(filas, guardar=False):
    """Carga las filas válidas. Con guardar=False hace todo y lo deshace al final (modo prueba)."""
    resultado = Resultado(filas_leidas=len(filas))
    catalogo = _Catalogo()

    with transaction.atomic():
        for fila in filas:
            if not fila.valida:
                resultado.rechazadas.append((fila.numero, fila.id_inventario, ' '.join(fila.errores)))
                continue
            if Ejemplar.objects.filter(codigo_inventario__iexact=fila.codigo).exists():
                resultado.omitidas.append((fila.numero, fila.codigo))
                continue
            otro = Ejemplar.objects.filter(id_inventario=fila.id_inventario).first()
            if otro is not None:
                resultado.rechazadas.append((
                    fila.numero, fila.id_inventario,
                    f'El ID {fila.id_inventario} ya lo tiene el ejemplar {otro.codigo_inventario}.',
                ))
                continue
            try:
                with transaction.atomic():
                    categoria = catalogo.categoria(fila.categoria)
                    autor = catalogo.autor(fila.autores[0])
                    editorial = catalogo.editorial(fila.editorial)
                    libro = catalogo.libro(fila, autor, editorial, categoria)
                    ejemplar = Ejemplar(
                        id_inventario=fila.id_inventario,
                        codigo_inventario=fila.codigo,
                        libro=libro,
                        observaciones=fila.observaciones,
                    )
                    ejemplar.full_clean()
                    ejemplar.save()
            except (ValidationError, IntegrityError) as error:
                catalogo.descartar_fila()
                motivo = '; '.join(error.messages) if isinstance(error, ValidationError) else str(error)
                resultado.rechazadas.append((fila.numero, fila.id_inventario, f'No se pudo guardar: {motivo}'))
                continue

            for tipo, _, objeto in catalogo.confirmar_fila():
                resultado.nuevos[tipo] += 1
                if tipo == 'autor':
                    resultado.autores_nuevos.append((fila.numero, objeto.nombre, objeto.apellido))
            resultado.ejemplares_nuevos += 1
            resultado.provisorios += fila.codigo_provisorio
            if fila.prestado:
                resultado.prestados.append((fila.numero, fila.codigo))
            for aviso in fila.avisos:
                resultado.avisos.append((fila.numero, fila.codigo, aviso))

        if not guardar:
            transaction.set_rollback(True)
    return resultado
