"""Dónde se guarda el material digital (Release 2, S7-07, D-R2-13).

Los PDF van a una carpeta que el servidor NO publica (MATERIAL_DIGITAL_ROOT, fuera de media/).
No tienen dirección pública: solo se abren a través de una vista que controla quién los pide
(el personal, o un lector de esa carrera). Así un enlace suelto no alcanza para descargarlos.
"""
import os
import uuid

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class AlmacenPrivado(FileSystemStorage):
    """Como el almacenamiento de archivos de Django, pero en MATERIAL_DIGITAL_ROOT y sin dirección pública."""

    def __init__(self):
        super().__init__()

    @property
    def base_location(self):
        # Se lee cada vez: así las pruebas pueden usar una carpeta temporal.
        return settings.MATERIAL_DIGITAL_ROOT

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    def url(self, name):
        raise ValueError('El material digital no tiene dirección pública: se abre desde su vista.')


def nombre_de_archivo(instancia, nombre_original):
    """Nombre al azar: no se puede adivinar ni choca con otro archivo. El título se usa al descargarlo."""
    return f'material/{uuid.uuid4().hex}.pdf'
