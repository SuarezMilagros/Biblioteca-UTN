from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Count, Exists, IntegerField, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, FormView, ListView, TemplateView, UpdateView

from .forms import (
    MENSAJE_EJEMPLAR_DADO_DE_BAJA, AutorForm, CategoriaForm, DevolucionForm, EditorialForm,
    EjemplarBajaForm, EjemplarForm, LibroForm, PersonaForm, PrestamoForm,
)
from .informes import ExportarCSVMixin, nombre_de_archivo
from .models import Autor, Categoria, Editorial, Ejemplar, Libro, Persona, Prestamo

ELEMENTOS_POR_PAGINA = 20
MENSAJE_DATO_REPETIDO = 'Ya existe un registro con esos datos. Revisá los valores e intentá de nuevo.'


def prestamo_activo_de(ejemplar_ref):
    """Subconsulta: el ejemplar indicado tiene un préstamo sin devolver."""
    return Exists(Prestamo.objects.filter(ejemplar=ejemplar_ref, fecha_devolucion__isnull=True))


@login_required
def inicio(request):
    """Panel principal: indicadores y próximos vencimientos (solo lectura, según los permisos)."""
    usuario = request.user
    hoy = timezone.localdate()
    contexto = {'hoy': hoy}
    if usuario.has_perm('biblioteca.view_prestamo'):
        sin_devolver = Prestamo.objects.filter(fecha_devolucion__isnull=True)
        contexto['prestamos_sin_devolver'] = sin_devolver.count()
        contexto['prestamos_vencidos'] = sin_devolver.filter(fecha_vencimiento__lt=hoy).count()
        contexto['proximos_vencimientos'] = sin_devolver.select_related('persona', 'ejemplar__libro').order_by(
            'fecha_vencimiento', 'pk'
        )[:6]
    if usuario.has_perm('biblioteca.view_ejemplar'):
        activos = Ejemplar.objects.filter(activo=True)
        contexto['ejemplares_activos'] = activos.count()
        contexto['ejemplares_disponibles'] = activos.filter(~prestamo_activo_de(OuterRef('pk'))).count()
    if usuario.has_perm('biblioteca.view_persona'):
        contexto['personas_activas'] = Persona.objects.filter(activo=True).count()
    if usuario.has_perm('biblioteca.view_libro'):
        contexto['libros_total'] = Libro.objects.count()
    return render(request, 'biblioteca/inicio.html', contexto)


class InformesView(LoginRequiredMixin, TemplateView):
    """Resumen estadístico y acceso a los informes CSV (D5). Muestra solo lo que cada rol puede ver."""

    template_name = 'biblioteca/informes.html'
    permisos = ('biblioteca.view_ejemplar', 'biblioteca.view_prestamo', 'biblioteca.view_persona')

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not any(request.user.has_perm(p) for p in self.permisos):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        usuario = self.request.user
        hoy = timezone.localdate()
        if usuario.has_perm('biblioteca.view_ejemplar'):
            activos = Ejemplar.objects.filter(activo=True)
            prestados = activos.filter(prestamo_activo_de(OuterRef('pk'))).count()
            total_activos = activos.count()
            contexto['ejemplares'] = {
                'disponibles': total_activos - prestados,
                'prestados': prestados,
                'baja': Ejemplar.objects.filter(activo=False).count(),
                'total': Ejemplar.objects.count(),
            }
        if usuario.has_perm('biblioteca.view_prestamo'):
            sin_devolver = Prestamo.objects.filter(fecha_devolucion__isnull=True)
            vencidos = sin_devolver.filter(fecha_vencimiento__lt=hoy).count()
            total_sin_devolver = sin_devolver.count()
            contexto['prestamos'] = {
                'al_dia': total_sin_devolver - vencidos,
                'vencidos': vencidos,
                'devueltos': Prestamo.objects.filter(fecha_devolucion__isnull=False).count(),
                'total': Prestamo.objects.count(),
            }
        if usuario.has_perm('biblioteca.view_persona'):
            contexto['personas'] = {
                'activas': Persona.objects.filter(activo=True).count(),
                'baja': Persona.objects.filter(activo=False).count(),
                'alumnos': Persona.objects.filter(activo=True, tipo=Persona.Tipo.ALUMNO).count(),
                'profesores': Persona.objects.filter(activo=True, tipo=Persona.Tipo.PROFESOR).count(),
                'total': Persona.objects.count(),
            }
        return contexto


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
        # Para mostrar en el listado cuántos ejemplares activos tiene cada libro y cuántos están disponibles.
        disponibles = (
            Ejemplar.objects.filter(libro=OuterRef('pk'), activo=True)
            .filter(~prestamo_activo_de(OuterRef('pk')))
            .order_by()
            .values('libro')
            .annotate(cantidad=Count('pk'))
            .values('cantidad')
        )
        queryset = super().get_queryset().select_related('autor', 'editorial', 'categoria').annotate(
            ejemplares_activos=Count('ejemplares', filter=Q(ejemplares__activo=True), distinct=True),
            ejemplares_disponibles=Coalesce(Subquery(disponibles, output_field=IntegerField()), 0),
        )
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
        contexto['ejemplares'] = self.object.ejemplares.con_estado_de_prestamo().order_by('codigo_inventario')
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

# Filtro del listado de ejemplares: valor del parámetro `estado` -> filtro sobre `activo`.
ESTADOS_DE_EJEMPLAR = {
    'activos': {'activo': True},
    'baja': {'activo': False},
    'todos': {},
}


class EjemplarListView(PermissionRequiredMixin, ExportarCSVMixin, ListView):
    permission_required = 'biblioteca.view_ejemplar'
    model = Ejemplar
    template_name = 'biblioteca/ejemplar_list.html'
    ordering = ['codigo_inventario']
    paginate_by = ELEMENTOS_POR_PAGINA

    # Informe del catálogo de ejemplares (D5).
    encabezados_csv = [
        'Código de inventario', 'ID de inventario', 'Título', 'Autor', 'Editorial',
        'Categoría', 'ISBN', 'Estado', 'Motivo de baja', 'Fecha de baja', 'Observaciones',
    ]

    def estado(self):
        estado = self.request.GET.get('estado', 'activos')
        return estado if estado in ESTADOS_DE_EJEMPLAR else 'activos'

    def get(self, request, *args, **kwargs):
        # Búsqueda por código de inventario (mostrador): si el código coincide exacto,
        # se abre directamente ese ejemplar.
        q = request.GET.get('q', '').strip()
        if q and request.GET.get('formato') != 'csv':
            exacto = Ejemplar.objects.filter(codigo_inventario__iexact=Ejemplar.normalizar_codigo(q)).first()
            if exacto is not None:
                return redirect('biblioteca:ejemplar_detail', pk=exacto.pk)
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        queryset = (
            super().get_queryset().select_related('libro').con_estado_de_prestamo()
            .filter(**ESTADOS_DE_EJEMPLAR[self.estado()])
        )
        q = self.request.GET.get('q', '').strip()
        if q:
            filtro = Q(codigo_inventario__icontains=q) | Q(libro__titulo__unaccent__icontains=q)
            if q.isdigit():
                filtro |= Q(id_inventario=int(q))
            queryset = queryset.filter(filtro)
        return queryset

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['q'] = self.request.GET.get('q', '').strip()
        contexto['estado'] = self.estado()
        return contexto

    def queryset_csv(self, queryset):
        # `get_queryset` ya trae `con_prestamo_activo` (con_estado_de_prestamo).
        return queryset.select_related('libro__autor', 'libro__editorial', 'libro__categoria')

    def nombre_csv(self):
        return nombre_de_archivo('ejemplares', self.estado())

    def fila_csv(self, ejemplar):
        libro = ejemplar.libro
        if not ejemplar.activo:
            estado = 'Dado de baja'
        else:
            estado = 'Prestado' if ejemplar.con_prestamo_activo else 'Disponible'
        return [
            ejemplar.codigo_inventario, ejemplar.id_inventario, libro.titulo, libro.autor,
            libro.editorial, libro.categoria, libro.isbn, estado,
            ejemplar.get_motivo_baja_display(), ejemplar.fecha_baja, ejemplar.observaciones,
        ]


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
        contexto['form_baja'] = EjemplarBajaForm()
        return contexto


class EjemplarBajaView(PermissionRequiredMixin, View):
    """Baja lógica de un ejemplar (perdido, dañado, descarte u otro). Conserva su historial."""

    permission_required = 'biblioteca.change_ejemplar'
    http_method_names = ['post']

    def post(self, request, pk):
        ejemplar = get_object_or_404(Ejemplar, pk=pk)
        form = EjemplarBajaForm(request.POST)
        if not ejemplar.activo:
            messages.info(request, f'El ejemplar {ejemplar} ya estaba dado de baja.')
        elif ejemplar.prestado:
            messages.error(
                request, f'No se puede dar de baja el ejemplar {ejemplar}: tiene un préstamo sin devolver.'
            )
        elif not form.is_valid():
            messages.error(request, 'Elegí el motivo de la baja.')
        else:
            ejemplar.activo = False
            ejemplar.motivo_baja = form.cleaned_data['motivo_baja']
            ejemplar.fecha_baja = timezone.localdate()
            ejemplar.save(update_fields=['activo', 'motivo_baja', 'fecha_baja'])
            messages.success(
                request, f'El ejemplar {ejemplar} quedó dado de baja ({ejemplar.get_motivo_baja_display()}).'
            )
        return redirect('biblioteca:ejemplar_detail', pk=ejemplar.pk)


class EjemplarReactivarView(PermissionRequiredMixin, View):
    permission_required = 'biblioteca.change_ejemplar'
    http_method_names = ['post']

    def post(self, request, pk):
        ejemplar = get_object_or_404(Ejemplar, pk=pk)
        if ejemplar.activo:
            messages.info(request, f'El ejemplar {ejemplar} ya estaba activo.')
        else:
            ejemplar.activo = True
            ejemplar.motivo_baja = ''
            ejemplar.fecha_baja = None
            ejemplar.save(update_fields=['activo', 'motivo_baja', 'fecha_baja'])
            messages.success(request, f'El ejemplar {ejemplar} volvió a estar activo.')
        return redirect('biblioteca:ejemplar_detail', pk=ejemplar.pk)


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


class PersonaListView(PermissionRequiredMixin, ExportarCSVMixin, ListView):
    permission_required = 'biblioteca.view_persona'
    model = Persona
    template_name = 'biblioteca/persona_list.html'
    ordering = ['apellido', 'nombre']
    paginate_by = ELEMENTOS_POR_PAGINA

    # Informe de personas (D5, agregado a pedido del equipo).
    encabezados_csv = ['Apellido', 'Nombre', 'Documento', 'Tipo', 'Legajo', 'Estado', 'Préstamos sin devolver']

    def queryset_csv(self, queryset):
        return queryset.annotate(
            sin_devolver=Count('prestamos', filter=Q(prestamos__fecha_devolucion__isnull=True))
        )

    def nombre_csv(self):
        return nombre_de_archivo('personas', self.estado())

    def fila_csv(self, persona):
        return [
            persona.apellido, persona.nombre, persona.documento, persona.get_tipo_display(),
            persona.legajo, 'Activa' if persona.activo else 'Dada de baja', persona.sin_devolver,
        ]

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
        prestamos = list(
            self.object.prestamos.select_related('ejemplar__libro').order_by('-fecha_prestamo', '-pk')
        )
        contexto['prestamos'] = prestamos
        # Resumen para la ficha de la persona (se calcula sobre la lista ya cargada, sin consultas extra).
        contexto['prestamos_sin_devolver'] = sum(1 for prestamo in prestamos if prestamo.activo)
        contexto['prestamos_vencidos'] = sum(1 for prestamo in prestamos if prestamo.vencido)
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


class PrestamoListView(PermissionRequiredMixin, ExportarCSVMixin, ListView):
    permission_required = 'biblioteca.view_prestamo'
    model = Prestamo
    template_name = 'biblioteca/prestamo_list.html'
    paginate_by = ELEMENTOS_POR_PAGINA

    # Informes de préstamos sin devolver, vencidos, devueltos o todos (D5): exporta el filtro elegido.
    encabezados_csv = [
        'Código de inventario', 'Título', 'Apellido y nombre', 'Documento', 'Tipo',
        'Fecha de préstamo', 'Vencimiento', 'Devolución', 'Estado', 'Días de atraso', 'Registrado por',
    ]

    def queryset_csv(self, queryset):
        return queryset.select_related('usuario_sistema')

    def nombre_csv(self):
        return nombre_de_archivo('prestamos', self.estado())

    def fila_csv(self, prestamo):
        hoy = timezone.localdate()
        if prestamo.vencido:
            estado, atraso = 'Vencido', (hoy - prestamo.fecha_vencimiento).days
        elif prestamo.activo:
            estado, atraso = 'Sin devolver', 0
        else:
            estado, atraso = 'Devuelto', ''
        persona = prestamo.persona
        usuario = prestamo.usuario_sistema
        return [
            prestamo.ejemplar.codigo_inventario, prestamo.ejemplar.libro.titulo, persona,
            persona.documento, persona.get_tipo_display(), prestamo.fecha_prestamo,
            prestamo.fecha_vencimiento, prestamo.fecha_devolucion, estado, atraso,
            usuario.get_full_name() or usuario.get_username(),
        ]

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
        if not self.ejemplar.activo:
            messages.error(request, MENSAJE_EJEMPLAR_DADO_DE_BAJA)
            return redirect('biblioteca:ejemplar_detail', pk=self.ejemplar.pk)
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
