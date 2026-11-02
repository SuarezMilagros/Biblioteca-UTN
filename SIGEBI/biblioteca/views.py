from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, FormView, ListView, UpdateView

from .forms import (
    AutorForm, CategoriaForm, DevolucionForm, EditorialForm, EjemplarForm, LibroForm, PersonaForm,
    PrestamoForm,
)
from .models import Autor, Categoria, Editorial, Ejemplar, Libro, Persona, Prestamo

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

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        prestamos = self.object.prestamos.select_related('persona').order_by('-fecha_prestamo', '-pk')
        contexto['prestamos'] = prestamos
        contexto['prestamo_activo'] = next((p for p in prestamos if p.activo), None)
        return contexto


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


# ---------- Personas ----------

# Filtro del listado de personas: valor del parámetro `estado` -> filtro sobre `activo`.
ESTADOS_DE_PERSONA = {
    'activas': {'activo': True},
    'baja': {'activo': False},
    'todas': {},
}


class PersonaListView(PermissionRequiredMixin, ListView):
    permission_required = 'biblioteca.view_persona'
    model = Persona
    template_name = 'biblioteca/persona_list.html'
    ordering = ['apellido', 'nombre']
    paginate_by = ELEMENTOS_POR_PAGINA

    def estado(self):
        estado = self.request.GET.get('estado', 'activas')
        return estado if estado in ESTADOS_DE_PERSONA else 'activas'

    def get_queryset(self):
        queryset = super().get_queryset().filter(**ESTADOS_DE_PERSONA[self.estado()])
        q = self.request.GET.get('q', '').strip()
        if q:
            # unaccent (PostgreSQL): "perez" también encuentra "Pérez".
            documento = Persona.normalizar_documento(q)
            queryset = queryset.filter(
                Q(apellido__unaccent__icontains=q)
                | Q(nombre__unaccent__icontains=q)
                | Q(documento__icontains=documento)
                | Q(legajo__icontains=q)
            )
        return queryset

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['q'] = self.request.GET.get('q', '').strip()
        contexto['estado'] = self.estado()
        return contexto


class PersonaDetailView(PermissionRequiredMixin, DetailView):
    permission_required = 'biblioteca.view_persona'
    model = Persona
    template_name = 'biblioteca/persona_detail.html'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['prestamos'] = (
            self.object.prestamos.select_related('ejemplar__libro').order_by('-fecha_prestamo', '-pk')
        )
        return contexto


class PersonaCreateView(PermissionRequiredMixin, GuardarRegistroMixin, CreateView):
    permission_required = 'biblioteca.add_persona'
    model = Persona
    form_class = PersonaForm
    template_name = 'biblioteca/persona_form.html'
    mensaje_exito = 'Persona "{obj}" registrada.'

    def get_success_url(self):
        return reverse('biblioteca:persona_detail', args=[self.object.pk])


class PersonaUpdateView(PermissionRequiredMixin, GuardarRegistroMixin, UpdateView):
    permission_required = 'biblioteca.change_persona'
    model = Persona
    form_class = PersonaForm
    template_name = 'biblioteca/persona_form.html'
    mensaje_exito = 'Persona "{obj}" actualizada.'

    def get_success_url(self):
        return reverse('biblioteca:persona_detail', args=[self.object.pk])


class PersonaBajaView(PermissionRequiredMixin, View):
    """Baja lógica: la persona queda inactiva y conserva su historial de préstamos."""

    permission_required = 'biblioteca.change_persona'
    http_method_names = ['post']

    def post(self, request, pk):
        persona = get_object_or_404(Persona, pk=pk)
        if not persona.activo:
            messages.info(request, f'"{persona}" ya estaba dada de baja.')
        elif persona.tiene_prestamos_activos:
            messages.error(
                request,
                f'No se puede dar de baja a "{persona}": tiene préstamos sin devolver.',
            )
        else:
            persona.activo = False
            persona.save(update_fields=['activo'])
            messages.success(request, f'"{persona}" quedó dada de baja.')
        return redirect('biblioteca:persona_detail', pk=persona.pk)


class PersonaReactivarView(PermissionRequiredMixin, View):
    permission_required = 'biblioteca.change_persona'
    http_method_names = ['post']

    def post(self, request, pk):
        persona = get_object_or_404(Persona, pk=pk)
        if persona.activo:
            messages.info(request, f'"{persona}" ya estaba activa.')
        else:
            persona.activo = True
            persona.save(update_fields=['activo'])
            messages.success(request, f'"{persona}" volvió a estar activa.')
        return redirect('biblioteca:persona_detail', pk=persona.pk)


# ---------- Préstamos y devoluciones ----------

MENSAJE_EJEMPLAR_YA_PRESTADO = 'Este ejemplar ya está prestado. Primero hay que registrar su devolución.'

# Filtro del listado de préstamos: valor del parámetro `estado` -> (título, filtro, orden).
ESTADOS_DE_PRESTAMO = {
    'vigentes': ('Sin devolver', lambda qs, hoy: qs.filter(fecha_devolucion__isnull=True),
                 ['fecha_vencimiento', 'pk']),
    'vencidos': ('Vencidos', lambda qs, hoy: qs.filter(fecha_devolucion__isnull=True, fecha_vencimiento__lt=hoy),
                 ['fecha_vencimiento', 'pk']),
    'devueltos': ('Devueltos', lambda qs, hoy: qs.filter(fecha_devolucion__isnull=False),
                  ['-fecha_devolucion', '-pk']),
    'todos': ('Todos', lambda qs, hoy: qs, ['-fecha_prestamo', '-pk']),
}


class PrestamoListView(PermissionRequiredMixin, ListView):
    permission_required = 'biblioteca.view_prestamo'
    model = Prestamo
    template_name = 'biblioteca/prestamo_list.html'
    paginate_by = ELEMENTOS_POR_PAGINA

    def estado(self):
        estado = self.request.GET.get('estado', 'vigentes')
        return estado if estado in ESTADOS_DE_PRESTAMO else 'vigentes'

    def get_queryset(self):
        _, filtrar, orden = ESTADOS_DE_PRESTAMO[self.estado()]
        queryset = filtrar(
            Prestamo.objects.select_related('persona', 'ejemplar__libro'), timezone.localdate()
        ).order_by(*orden)
        q = self.request.GET.get('q', '').strip()
        if q:
            queryset = queryset.filter(
                Q(persona__apellido__unaccent__icontains=q)
                | Q(persona__nombre__unaccent__icontains=q)
                | Q(persona__documento__icontains=Persona.normalizar_documento(q))
                | Q(ejemplar__codigo_inventario__icontains=q)
                | Q(ejemplar__libro__titulo__unaccent__icontains=q)
            )
        return queryset

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['q'] = self.request.GET.get('q', '').strip()
        contexto['estado'] = self.estado()
        contexto['estados'] = [(clave, titulo) for clave, (titulo, _, _) in ESTADOS_DE_PRESTAMO.items()]
        return contexto


class PrestamoCreateView(PermissionRequiredMixin, FormView):
    """Préstamo de un ejemplar. Quien lo registra queda guardado como usuario del sistema."""

    permission_required = 'biblioteca.add_prestamo'
    form_class = PrestamoForm
    template_name = 'biblioteca/prestamo_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.ejemplar = get_object_or_404(Ejemplar.objects.select_related('libro'), pk=kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        if not self.ejemplar.disponible:
            messages.error(request, MENSAJE_EJEMPLAR_YA_PRESTADO)
            return redirect('biblioteca:ejemplar_detail', pk=self.ejemplar.pk)
        return super().get(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['ejemplar'] = self.ejemplar
        return kwargs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['ejemplar'] = self.ejemplar
        return contexto

    def form_valid(self, form):
        try:
            # Si otra persona prestó el mismo ejemplar al mismo tiempo, la base lo rechaza
            # (un préstamo activo por ejemplar) y se vuelve al formulario sin error 500.
            with transaction.atomic():
                prestamo = Prestamo.objects.create(
                    ejemplar=self.ejemplar,
                    persona=form.persona,
                    usuario_sistema=self.request.user,
                    fecha_prestamo=form.cleaned_data['fecha_prestamo'],
                    fecha_vencimiento=form.cleaned_data['fecha_vencimiento'],
                )
        except IntegrityError:
            form.add_error(None, MENSAJE_EJEMPLAR_YA_PRESTADO)
            return self.form_invalid(form)
        messages.success(
            self.request,
            f'Préstamo registrado: {self.ejemplar} a "{prestamo.persona}". '
            f'Vence el {prestamo.fecha_vencimiento:%d/%m/%Y}.',
        )
        return redirect('biblioteca:ejemplar_detail', pk=self.ejemplar.pk)


class DevolucionView(PermissionRequiredMixin, FormView):
    permission_required = 'biblioteca.change_prestamo'
    form_class = DevolucionForm
    template_name = 'biblioteca/devolucion_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.prestamo = get_object_or_404(
            Prestamo.objects.select_related('persona', 'ejemplar__libro'), pk=kwargs['pk']
        )
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        if not self.prestamo.activo:
            messages.info(request, 'Este préstamo ya tiene registrada su devolución.')
            return redirect('biblioteca:ejemplar_detail', pk=self.prestamo.ejemplar_id)
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if not self.prestamo.activo:
            messages.info(request, 'Este préstamo ya tiene registrada su devolución.')
            return redirect('biblioteca:ejemplar_detail', pk=self.prestamo.ejemplar_id)
        return super().post(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['prestamo'] = self.prestamo
        return kwargs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['prestamo'] = self.prestamo
        return contexto

    def form_valid(self, form):
        self.prestamo.fecha_devolucion = form.cleaned_data['fecha_devolucion']
        self.prestamo.save(update_fields=['fecha_devolucion'])
        messages.success(
            self.request,
            f'Devolución registrada: {self.prestamo.ejemplar} vuelve a estar disponible.',
        )
        return redirect('biblioteca:ejemplar_detail', pk=self.prestamo.ejemplar_id)
