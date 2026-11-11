"""Portal de estudiantes y docentes (Release 2).

Todo lo que se muestra acá se filtra en el servidor por la persona de la cuenta y sus carreras (D-R2-12).
"""
from django.views.generic import TemplateView

from biblioteca.models import Libro

from .acceso import LectorRequeridoMixin


class InicioView(LectorRequeridoMixin, TemplateView):
    template_name = 'portal/inicio.html'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        carreras = self.persona.carreras.all()
        contexto['persona'] = self.persona
        contexto['carreras'] = carreras
        # Un libro pertenece a las carreras de su categoría (D-R2-6).
        contexto['cantidad_libros'] = Libro.objects.filter(categoria__carreras__in=carreras).distinct().count()
        return contexto
