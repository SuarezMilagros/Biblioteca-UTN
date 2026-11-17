"""Código QR de cada ejemplar (Release 2, S8-05, D-R2-26).

El QR tiene la dirección completa de la ficha del ejemplar en el sistema del personal. Se genera en el
servidor como SVG (se ve nítido en pantalla y al imprimir) con la biblioteca segno, que no tiene
dependencias. Al escanearlo:
- el personal abre la ficha (si no inició sesión, primero pasa por el ingreso);
- un lector recibe "Acceso no permitido", como en cualquier pantalla del personal.
"""
import segno
from django.http.request import split_domain_port
from django.urls import reverse
from django.utils.safestring import mark_safe

# Nivel de corrección M: el QR se sigue leyendo aunque la etiqueta tenga un raspón o una mancha (~15 %).
CORRECCION = 'm'
HOSTS_LOCALES = ('localhost', '127.0.0.1', '[::1]')


def direccion_de_la_ficha(request, ejemplar):
    """Dirección completa de la ficha, con el mismo dominio por el que se está usando el sistema."""
    return request.build_absolute_uri(reverse('biblioteca:ejemplar_detail', args=[ejemplar.pk]))


def svg(texto):
    """El QR de `texto` como SVG para insertar en la página. Sin tamaño fijo: lo define el CSS."""
    qr = segno.make(texto, error=CORRECCION)
    # El SVG solo tiene trazos del dibujo (no incluye el texto), así que se puede insertar tal cual.
    return mark_safe(qr.svg_inline(scale=1, border=2, omitsize=True, svgclass='qr', lineclass='qr-trazo'))


def es_direccion_local(request):
    """True si se está usando el sistema desde la misma computadora: un celular no abriría ese QR."""
    dominio, _ = split_domain_port(request.get_host())
    return dominio in HOSTS_LOCALES
