"""Portal de estudiantes y docentes (Release 2).

Todo lo que se muestra acá se filtra en el servidor por la persona de la cuenta y sus carreras (D-R2-12).
"""
from django.db.models import Q
from django.views.generic import DetailView, ListView, TemplateView

from biblioteca.models import Categoria, Libro

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
