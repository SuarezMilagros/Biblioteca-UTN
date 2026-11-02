from django import forms

from .models import Autor, Categoria, Editorial, Ejemplar, Libro, Persona

MENSAJE_CODIGO_REPETIDO = 'Ya existe un ejemplar con ese código de inventario.'
MENSAJE_DOCUMENTO_REPETIDO = 'Ya existe una persona con ese documento.'


class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ['nombre', 'descripcion']


class AutorForm(forms.ModelForm):
    class Meta:
        model = Autor
        fields = ['nombre', 'apellido']


class EditorialForm(forms.ModelForm):
    class Meta:
        model = Editorial
        fields = ['nombre']


class LibroForm(forms.ModelForm):
    class Meta:
        model = Libro
        fields = ['titulo', 'isbn', 'imagen', 'categoria', 'autor', 'editorial']
        labels = {
            'isbn': 'ISBN (opcional)',
            'imagen': 'Imagen de portada (opcional)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['categoria'].queryset = Categoria.objects.order_by('nombre')
        self.fields['autor'].queryset = Autor.objects.order_by('apellido', 'nombre')
        self.fields['editorial'].queryset = Editorial.objects.order_by('nombre')


class EjemplarForm(forms.ModelForm):
    class Meta:
        model = Ejemplar
        fields = ['id_inventario', 'codigo_inventario', 'libro', 'observaciones']
        labels = {
            'id_inventario': 'ID de inventario (opcional)',
            'codigo_inventario': 'Código de inventario (numeración)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['libro'].queryset = Libro.objects.order_by('titulo')

    def clean_codigo_inventario(self):
        # Se compara sin distinguir mayúsculas, igual que la restricción de la base.
        codigo = Ejemplar.normalizar_codigo(self.cleaned_data['codigo_inventario'])
        otros = Ejemplar.objects.filter(codigo_inventario__iexact=codigo)
        if self.instance.pk is not None:
            otros = otros.exclude(pk=self.instance.pk)
        if otros.exists():
            raise forms.ValidationError(MENSAJE_CODIGO_REPETIDO)
        return codigo


class PersonaForm(forms.ModelForm):
    """Alta y edición de personas. La baja y la reactivación se hacen con botones aparte."""

    class Meta:
        model = Persona
        fields = ['nombre', 'apellido', 'documento', 'tipo', 'legajo']
        labels = {
            'documento': 'Documento',
            'tipo': 'Tipo',
            'legajo': 'Legajo (opcional)',
        }
        help_texts = {
            'documento': 'Sin puntos ni espacios; si los escribís, se quitan al guardar.',
        }
        error_messages = {
            'documento': {'unique': MENSAJE_DOCUMENTO_REPETIDO},
        }

    def clean_documento(self):
        documento = Persona.normalizar_documento(self.cleaned_data['documento'])
        if not documento:
            raise forms.ValidationError('Este campo es obligatorio.')
        otras = Persona.objects.filter(documento__iexact=documento)
        if self.instance.pk is not None:
            otras = otras.exclude(pk=self.instance.pk)
        if otras.exists():
            raise forms.ValidationError(MENSAJE_DOCUMENTO_REPETIDO)
        return documento

    def clean_legajo(self):
        return self.cleaned_data['legajo'].strip()
