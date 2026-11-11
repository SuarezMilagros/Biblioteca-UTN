"""Acceso al portal (Release 2, S7-04): solo estudiantes y docentes con cuenta (rol Lector)."""
from django.contrib.auth.mixins import AccessMixin

from cuentas.roles import es_lector


class LectorRequeridoMixin(AccessMixin):
    """Sin sesión, al login. Con sesión pero sin ser lector (por ejemplo, el personal), 403.

    Deja en `self.persona` la persona de la cuenta: todo lo que ve el lector sale de ella (sus carreras).
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        persona = getattr(request.user, 'persona', None)
        if persona is None or not es_lector(request.user):
            return self.handle_no_permission()
        self.persona = persona
        return super().dispatch(request, *args, **kwargs)
