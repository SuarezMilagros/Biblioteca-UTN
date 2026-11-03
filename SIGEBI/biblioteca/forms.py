from django import forms
from django.utils import timezone

from .models import Autor, Categoria, Editorial, Ejemplar, Libro, Persona, Prestamo

MENSAJE_CODIGO_REPETIDO = 'Ya existe un ejemplar con ese código de inventario.'
MENSAJE_DOCUMENTO_REPETIDO = 'Ya existe una persona con ese documento.'
MENSAJE_EJEMPLAR_DADO_DE_BAJA = 'Este ejemplar está dado de baja: no se puede prestar.'


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


class CampoFecha(forms.DateField):
    """Fecha con el calendario del navegador (formato AAAA-MM-DD)."""

    def __init__(self, **kwargs):
        kwargs.setdefault('widget', forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'))
        super().__init__(**kwargs)


class PrestamoForm(forms.Form):
    """Registro de un préstamo desde un ejemplar.

    La persona se busca por documento. El vencimiento se completa a 14 días (D2)
    si se deja vacío, y se puede corregir a mano.
    """

    documento = forms.CharField(
        label='Documento de la persona',
        max_length=20,
        help_text='Si la persona no está registrada, primero dala de alta en Personas.',
    )
    fecha_prestamo = CampoFecha(label='Fecha de préstamo')
    fecha_vencimiento = CampoFecha(
        label='Fecha de vencimiento',
        required=False,
        help_text='Se completa sola: 14 días después del préstamo. Podés cambiarla si hace falta.',
    )

    def __init__(self, *args, ejemplar, **kwargs):
        super().__init__(*args, **kwargs)
        self.ejemplar = ejemplar
        self.persona = None
        if not self.is_bound:
            hoy = timezone.localdate()
            self.initial.setdefault('fecha_prestamo', hoy)
            self.initial.setdefault('fecha_vencimiento', Prestamo.calcular_vencimiento(hoy))

    def clean_documento(self):
        documento = Persona.normalizar_documento(self.cleaned_data['documento'])
        persona = Persona.objects.filter(documento__iexact=documento).first()
        if persona is None:
            raise forms.ValidationError(
                'No hay ninguna persona registrada con ese documento. Dala de alta en Personas.'
            )
        if not persona.activo:
            raise forms.ValidationError(f'"{persona}" está dada de baja: no puede recibir préstamos.')
        self.persona = persona
        return documento

    def clean_fecha_prestamo(self):
        fecha = self.cleaned_data['fecha_prestamo']
        if fecha > timezone.localdate():
            raise forms.ValidationError('La fecha de préstamo no puede ser futura.')
        return fecha

    def clean(self):
        datos = super().clean()
        if not self.ejemplar.activo:
            raise forms.ValidationError(MENSAJE_EJEMPLAR_DADO_DE_BAJA)
        if not self.ejemplar.disponible:
            raise forms.ValidationError('Este ejemplar ya está prestado. Primero hay que registrar su devolución.')
        fecha_prestamo = datos.get('fecha_prestamo')
        if fecha_prestamo is None:
            return datos
        vencimiento = datos.get('fecha_vencimiento')
        if vencimiento is None:
            datos['fecha_vencimiento'] = Prestamo.calcular_vencimiento(fecha_prestamo)
        elif vencimiento < fecha_prestamo:
            self.add_error('fecha_vencimiento', 'La fecha de vencimiento no puede ser anterior a la fecha de préstamo.')
        return datos


class DevolucionForm(forms.Form):
    """Registro de la devolución de un préstamo (decisión D8)."""

    fecha_devolucion = CampoFecha(label='Fecha de devolución')

    def __init__(self, *args, prestamo, **kwargs):
        super().__init__(*args, **kwargs)
        self.prestamo = prestamo
        if not self.is_bound:
            self.initial.setdefault('fecha_devolucion', timezone.localdate())

    def clean_fecha_devolucion(self):
        fecha = self.cleaned_data['fecha_devolucion']
        if fecha < self.prestamo.fecha_prestamo:
            raise forms.ValidationError(
                'La fecha de devolución no puede ser anterior a la fecha de préstamo '
                f'({self.prestamo.fecha_prestamo:%d/%m/%Y}).'
            )
        if fecha > timezone.localdate():
            raise forms.ValidationError('La fecha de devolución no puede ser futura.')
        return fecha


class EjemplarBajaForm(forms.Form):
    """Baja lógica de un ejemplar: se guarda el motivo y la fecha (hoy)."""

    motivo_baja = forms.ChoiceField(label='Motivo de la baja', choices=Ejemplar.MotivoBaja.choices)
