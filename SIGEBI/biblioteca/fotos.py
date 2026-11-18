"""Foto de perfil de alumnos y profesores (pedido de la profesora, 18/11/2026).

La sube la propia persona desde Mi perfil. Antes de guardarla se achica a LADO_MAXIMO píxeles y se vuelve a
grabar como JPEG: así ocupa poco y se descartan los datos que agrega el celular (por ejemplo, la ubicación).
"""
import io

from django import forms
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

MAXIMO_MB = 5
LADO_MAXIMO = 400
FORMATOS = {'JPEG', 'PNG', 'WEBP'}


def preparar_foto(archivo):
    """Valida la imagen y devuelve un JPEG chico, sin metadatos. Lanza ValidationError si no sirve."""
    if archivo.size > MAXIMO_MB * 1024 * 1024:
        raise forms.ValidationError(f'La foto pesa más de {MAXIMO_MB} MB.')
    try:
        archivo.seek(0)
        imagen = Image.open(archivo)
        formato = imagen.format
        imagen.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise forms.ValidationError('El archivo no es una imagen válida.')
    if formato not in FORMATOS:
        raise forms.ValidationError('Subí una foto en JPG, PNG o WEBP.')
    imagen = ImageOps.exif_transpose(imagen).convert('RGB')
    imagen.thumbnail((LADO_MAXIMO, LADO_MAXIMO))
    salida = io.BytesIO()
    imagen.save(salida, format='JPEG', quality=85)
    return ContentFile(salida.getvalue(), name='foto.jpg')


class FotoForm(forms.Form):
    foto = forms.FileField(
        label='Foto de perfil',
        help_text=f'JPG, PNG o WEBP, hasta {MAXIMO_MB} MB. Se ve en tu perfil y la ve el personal de la biblioteca.',
        widget=forms.FileInput(attrs={'accept': 'image/jpeg,image/png,image/webp'}),
    )

    def clean_foto(self):
        return preparar_foto(self.cleaned_data['foto'])


def guardar_foto(persona, contenido):
    """Reemplaza la foto de la persona y borra la anterior del disco."""
    anterior = persona.foto.name if persona.foto else ''
    persona.foto.save('foto.jpg', contenido, save=False)
    persona.save(update_fields=['foto'])
    if anterior:
        persona.foto.storage.delete(anterior)


def quitar_foto(persona):
    if persona.foto:
        nombre = persona.foto.name
        persona.foto = ''
        persona.save(update_fields=['foto'])
        persona._meta.get_field('foto').storage.delete(nombre)
