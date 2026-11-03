"""Variables de `biblioteca` para la cabecera común (registradas en config/settings.py).

- prestamos_vencidos_total: préstamos sin devolver con el vencimiento pasado. Se muestra como
  aviso en la cabecera (visibilidad del estado del sistema). Vale 0 si la persona no puede ver préstamos.

Solo lectura: una consulta COUNT por pantalla, únicamente con sesión iniciada.
"""
from django.utils import timezone

from .models import Prestamo


def interfaz(request):
    usuario = getattr(request, 'user', None)
    if usuario is None or not usuario.is_authenticated:
        return {}
    vencidos = 0
    if usuario.has_perm('biblioteca.view_prestamo'):
        vencidos = Prestamo.objects.filter(
            fecha_devolucion__isnull=True, fecha_vencimiento__lt=timezone.localdate()
        ).count()
    return {'prestamos_vencidos_total': vencidos}
