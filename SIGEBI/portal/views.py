"""Portal de estudiantes y docentes (Release 2).

Todo lo que se muestra acá se filtra en el servidor por la persona de la cuenta y sus carreras (D-R2-12).
"""
from django.db.models import Q
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView

from biblioteca.models import Categoria, Libro, MaterialDigital
from biblioteca.views import abrir_pdf

from .acceso import LectorRequeridoMixin

LIBROS_POR_PAGINA = 20


class InicioView(LectorRequeridoMixin, TemplateView):
    template_name = 'portal/inicio.html'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        carreras = self.persona.carreras.all()
        contexto['persona'] = self.persona
        contexto['carreras'] = carreras
        # Un libro pertenece a las carreras de su categoría (D-R2-6).
        contexto['cantidad_libros'] = Libro.objects.de_las_carreras(carreras).count()
        sin_devolver = self.persona.prestamos.filter(fecha_devolucion__isnull=True)
        contexto['prestamos_sin_devolver'] = sin_devolver.count()
        contexto['prestamos_vencidos'] = sin_devolver.filter(fecha_vencimiento__lt=timezone.localdate()).count()
        return contexto


class PerfilView(LectorRequeridoMixin, TemplateView):
    """Mi perfil (S7-06): sus datos (solo lectura), sus carreras y sus préstamos. Nunca los de otra persona."""

    template_name = 'portal/perfil.html'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        hoy = timezone.localdate()
        prestamos = list(
            self.persona.prestamos.select_related('ejemplar__libro').order_by('-fecha_prestamo', '-pk')
        )
        activos = [prestamo for prestamo in prestamos if prestamo.activo]
        for prestamo in activos:
            # Positivo: faltan días. Cero: vence hoy. Negativo: días de atraso.
            prestamo.dias_restantes = (prestamo.fecha_vencimiento - hoy).days
            prestamo.dias_de_atraso = -prestamo.dias_restantes
        activos.sort(key=lambda prestamo: prestamo.fecha_vencimiento)
        contexto.update({
            'persona': self.persona,
            'carreras': self.persona.carreras.all(),
            'activos': activos,
            'devueltos': [prestamo for prestamo in prestamos if not prestamo.activo],
        })
        return contexto


def entero(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


class LibrosDeSusCarrerasMixin(LectorRequeridoMixin):
    """Los libros que puede ver el lector: los de sus carreras, con su disponibilidad (S7-05).

    El filtro está en el servidor: un libro de otra carrera no aparece ni se puede abrir con la dirección (D-R2-12).
    """

    def libros_visibles(self):
        return (
            Libro.objects.de_las_carreras(self.persona.carreras.all())
            .con_disponibilidad()
            .select_related('autor', 'editorial', 'categoria')
        )


class CatalogoView(LibrosDeSusCarrerasMixin, ListView):
    template_name = 'portal/catalogo.html'
    context_object_name = 'libros'
    paginate_by = LIBROS_POR_PAGINA

    def filtros(self):
        """Carrera y categoría elegidas. Si no son del lector (o no existen), se ignoran."""
        carreras = self.persona.carreras.all()
        categorias = Categoria.objects.filter(carreras__in=carreras).distinct().order_by('nombre')
        carrera = carreras.filter(pk=entero(self.request.GET.get('carrera'))).first()
        categoria = categorias.filter(pk=entero(self.request.GET.get('categoria'))).first()
        return carreras, categorias, carrera, categoria

    def get_queryset(self):
        _, _, carrera, categoria = self.filtros()
        libros = self.libros_visibles()
        if carrera:
            libros = libros.filter(categoria__carreras=carrera)
        if categoria:
            libros = libros.filter(categoria=categoria)
        q = self.request.GET.get('q', '').strip()
        if q:
            isbn = ''.join(c for c in q if c.isalnum())
            # unaccent (PostgreSQL): "calculo" también encuentra "Cálculo".
            busqueda = (
                Q(titulo__unaccent__icontains=q)
                | Q(autor__apellido__unaccent__icontains=q)
                | Q(autor__nombre__unaccent__icontains=q)
            )
            if isbn:
                busqueda |= Q(isbn__icontains=isbn)
            libros = libros.filter(busqueda)
        return libros.order_by('titulo', 'pk')

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        carreras, categorias, carrera, categoria = self.filtros()
        contexto.update({
            'carreras': carreras,
            'categorias': categorias,
            'carrera_elegida': carrera,
            'categoria_elegida': categoria,
            'q': self.request.GET.get('q', '').strip(),
        })
        contexto['hay_filtros'] = bool(contexto['q'] or carrera or categoria)
        return contexto


class LibroView(LibrosDeSusCarrerasMixin, DetailView):
    template_name = 'portal/libro.html'
    context_object_name = 'libro'

    def get_queryset(self):
        # Un libro de otra carrera responde 404, aunque se escriba la dirección a mano.
        return self.libros_visibles()


class MaterialDeSusCarrerasMixin(LectorRequeridoMixin):
    """Material que puede ver el lector: aprobado, activo y de sus carreras (D-R2-12)."""

    def material_visible(self):
        return MaterialDigital.objects.filter(
            carrera__in=self.persona.carreras.all(),
            estado=MaterialDigital.Estado.APROBADO,
            activo=True,
        )


class MaterialView(MaterialDeSusCarrerasMixin, ListView):
    template_name = 'portal/material.html'
    context_object_name = 'materiales'
    paginate_by = LIBROS_POR_PAGINA

    def get_queryset(self):
        materiales = self.material_visible().select_related('carrera')
        carrera = self.persona.carreras.filter(pk=entero(self.request.GET.get('carrera'))).first()
        if carrera:
            materiales = materiales.filter(carrera=carrera)
        tipo = self.request.GET.get('tipo', '')
        if tipo in MaterialDigital.Tipo.values:
            materiales = materiales.filter(tipo=tipo)
        q = self.request.GET.get('q', '').strip()
        if q:
            materiales = materiales.filter(Q(titulo__unaccent__icontains=q) | Q(autores__unaccent__icontains=q))
        return materiales.order_by('titulo', 'pk')

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        carreras = self.persona.carreras.all()
        carrera = carreras.filter(pk=entero(self.request.GET.get('carrera'))).first()
        tipo = self.request.GET.get('tipo', '')
        contexto.update({
            'carreras': carreras,
            'carrera_elegida': carrera,
            'tipos': MaterialDigital.Tipo.choices,
            'tipo_elegido': tipo if tipo in MaterialDigital.Tipo.values else '',
            'q': self.request.GET.get('q', '').strip(),
        })
        contexto['hay_filtros'] = bool(contexto['q'] or carrera or contexto['tipo_elegido'])
        return contexto


class MaterialArchivoView(MaterialDeSusCarrerasMixin, View):
    """Abre el PDF. Material de otra carrera, pendiente o dado de baja: 404, aunque se escriba la dirección."""

    def get(self, request, pk):
        return abrir_pdf(get_object_or_404(self.material_visible(), pk=pk))
