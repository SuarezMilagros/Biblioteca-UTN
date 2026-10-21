from django import forms

from .models import Autor, Categoria, Editorial, Ejemplar, Libro

MENSAJE_CODIGO_REPETIDO = 'Ya existe un ejemplar con ese código de inventario.'


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

    def _post_clean(self):
        # Si el formulario ya marcó el código (vacío o repetido), se conserva ese mensaje.
        # Ejemplar.clean() vuelve a exigir el código y, sin esto, el mensaje aparecería dos veces.
        mensajes_del_formulario = list(self._errors.get('codigo_inventario', []))
        super()._post_clean()
        if mensajes_del_formulario:
            self._errors['codigo_inventario'] = self.error_class(mensajes_del_formulario)