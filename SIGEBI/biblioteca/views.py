from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db import IntegrityError, transaction
from django.shortcuts import render
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from .forms import AutorForm, CategoriaForm, EditorialForm, EjemplarForm, LibroForm
from .models import Autor, Categoria, Editorial, Ejemplar, Libro

ELEMENTOS_POR_PAGINA = 20
MENSAJE_DATO_REPETIDO = 'Ya existe un registro con esos datos. Revisá los valores e intentá de nuevo.'


@login_required
def inicio(request):
    return render(request, 'biblioteca/inicio.html')


class GuardarRegistroMixin:
    """Muestra un mensaje de éxito al guardar.

    Si la base rechaza el dato (por ejemplo, porque otra persona guardó el mismo
    código al mismo tiempo), vuelve al formulario con un error en lugar de dar un 500.
    `mensaje_exito` admite `{obj}`, que se reemplaza por el registro guardado.
    """

    mensaje_exito = ''

    def form_valid(self, form):
        try:
            # El savepoint deshace solo este guardado si la base lo rechaza.
            with transaction.atomic():
                respuesta = super().form_valid(form)
        except IntegrityError:
            form.add_error(None, MENSAJE_DATO_REPETIDO)
            return self.form_invalid(form)
        messages.success(self.request, self.mensaje_exito.format(obj=self.object))
        return respuesta


# ---------- Categorías, autores y editoriales ----------

class CategoriaListView(PermissionRequiredMixin, ListView):
    permission_required = 'biblioteca.view_categoria'
    model = Categoria
    template_name = 'biblioteca/categoria_list.html'
    ordering = ['nombre']
    paginate_by = ELEMENTOS_POR_PAGINA


class CategoriaCreateView(PermissionRequiredMixin, GuardarRegistroMixin, CreateView):
    permission_required = 'biblioteca.add_categoria'
    model = Categoria
    form_class = CategoriaForm
    template_name = 'biblioteca/categoria_form.html'
    success_url = reverse_lazy('biblioteca:categoria_list')
    mensaje_exito = 'Categoría "{obj}" registrada.'


class CategoriaUpdateView(PermissionRequiredMixin, GuardarRegistroMixin, UpdateView):
    permission_required = 'biblioteca.change_categoria'
    model = Categoria
    form_class = CategoriaForm
    template_name = 'biblioteca/categoria_form.html'
    success_url = reverse_lazy('biblioteca:categoria_list')
    mensaje_exito = 'Categoría "{obj}" actualizada.'


class AutorListView(PermissionRequiredMixin, ListView):
    permission_required = 'biblioteca.view_autor'
    model = Autor
    template_name = 'biblioteca/autor_list.html'
    ordering = ['apellido', 'nombre']
    paginate_by = ELEMENTOS_POR_PAGINA


class AutorCreateView(PermissionRequiredMixin, GuardarRegistroMixin, CreateView):
    permission_required = 'biblioteca.add_autor'
    model = Autor
    form_class = AutorForm
    template_name = 'biblioteca/autor_form.html'
    success_url = reverse_lazy('biblioteca:autor_list')
    mensaje_exito = 'Autor "{obj}" registrado.'


class AutorUpdateView(PermissionRequiredMixin, GuardarRegistroMixin, UpdateView):
    permission_required = 'biblioteca.change_autor'
    model = Autor
    form_class = AutorForm
    template_name = 'biblioteca/autor_form.html'
    success_url = reverse_lazy('biblioteca:autor_list')
    mensaje_exito = 'Autor "{obj}" actualizado.'


class EditorialListView(PermissionRequiredMixin, ListView):
    permission_required = 'biblioteca.view_editorial'
    model = Editorial
    template_name = 'biblioteca/editorial_list.html'
    ordering = ['nombre']
    paginate_by = ELEMENTOS_POR_PAGINA


class EditorialCreateView(PermissionRequiredMixin, GuardarRegistroMixin, CreateView):
    permission_required = 'biblioteca.add_editorial'
    model = Editorial
    form_class = EditorialForm
    template_name = 'biblioteca/editorial_form.html'
    success_url = reverse_lazy('biblioteca:editorial_list')
    mensaje_exito = 'Editorial "{obj}" registrada.'


class EditorialUpdateView(PermissionRequiredMixin, GuardarRegistroMixin, UpdateView):
    permission_required = 'biblioteca.change_editorial'
    model = Editorial
    form_class = EditorialForm
    template_name = 'biblioteca/editorial_form.html'
    success_url = reverse_lazy('biblioteca:editorial_list')
    mensaje_exito = 'Editorial "{obj}" actualizada.'


# ---------- Libros ----------

class LibroListView(PermissionRequiredMixin, ListView):
    permission_required = 'biblioteca.view_libro'
    model = Libro
    template_name = 'biblioteca/libro_list.html'
    ordering = ['titulo']
    paginate_by = ELEMENTOS_POR_PAGINA

    def get_queryset(self):
        queryset = super().get_queryset().select_related('autor', 'editorial', 'categoria')
        q = self.request.GET.get('q', '').strip()
        if q:
            # unaccent (PostgreSQL): "calculo" también encuentra "Cálculo I".
            queryset = queryset.filter(titulo__unaccent__icontains=q)
        return queryset

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['q'] = self.request.GET.get('q', '').strip()
        return contexto


class LibroDetailView(PermissionRequiredMixin, DetailView):
    permission_required = 'biblioteca.view_libro'
    model = Libro
    template_name = 'biblioteca/libro_detail.html'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['ejemplares'] = self.object.ejemplares.order_by('codigo_inventario')
        return contexto


class LibroCreateView(PermissionRequiredMixin, GuardarRegistroMixin, CreateView):
    permission_required = 'biblioteca.add_libro'
    model = Libro
    form_class = LibroForm
    template_name = 'biblioteca/libro_form.html'
    mensaje_exito = 'Libro "{obj}" registrado.'

    def get_success_url(self):
        return reverse('biblioteca:libro_detail', args=[self.object.pk])


class LibroUpdateView(PermissionRequiredMixin, GuardarRegistroMixin, UpdateView):
    permission_required = 'biblioteca.change_libro'
    model = Libro
    form_class = LibroForm
    template_name = 'biblioteca/libro_form.html'
    mensaje_exito = 'Libro "{obj}" actualizado.'

    def get_success_url(self):
        return reverse('biblioteca:libro_detail', args=[self.object.pk])


# ---------- Ejemplares ----------

class EjemplarListView(PermissionRequiredMixin, ListView):
    permission_required = 'biblioteca.view_ejemplar'
    model = Ejemplar
    template_name = 'biblioteca/ejemplar_list.html'
    ordering = ['codigo_inventario']
    paginate_by = ELEMENTOS_POR_PAGINA

    def get_queryset(self):
        return super().get_queryset().select_related('libro')


class EjemplarDetailView(PermissionRequiredMixin, DetailView):
    permission_required = 'biblioteca.view_ejemplar'
    model = Ejemplar
    template_name = 'biblioteca/ejemplar_detail.html'

    def get_queryset(self):
        return super().get_queryset().select_related('libro')


class EjemplarCreateView(PermissionRequiredMixin, GuardarRegistroMixin, CreateView):
    permission_required = 'biblioteca.add_ejemplar'
    model = Ejemplar
    form_class = EjemplarForm
    template_name = 'biblioteca/ejemplar_form.html'
    mensaje_exito = 'Ejemplar "{obj}" registrado.'

    def get_initial(self):
        inicial = super().get_initial()
        libro = self.request.GET.get('libro', '')
        if libro.isdigit():
            inicial['libro'] = int(libro)
        return inicial

    def get_success_url(self):
        # Al registrar un ejemplar, se vuelve al libro al que pertenece.
        return reverse('biblioteca:libro_detail', args=[self.object.libro_id])


class EjemplarUpdateView(PermissionRequiredMixin, GuardarRegistroMixin, UpdateView):
    permission_required = 'biblioteca.change_ejemplar'
    model = Ejemplar
    form_class = EjemplarForm
    template_name = 'biblioteca/ejemplar_form.html'
    mensaje_exito = 'Ejemplar "{obj}" actualizado.'

    def get_success_url(self):
        return reverse('biblioteca:ejemplar_detail', args=[self.object.pk])
        