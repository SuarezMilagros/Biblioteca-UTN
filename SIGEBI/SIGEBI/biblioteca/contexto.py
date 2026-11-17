"""Variables de `biblioteca` para la cabecera común (registradas en config/settings.py).

- reservas_pendientes_total: reservas que esperan respuesta del personal (S8-03).
- material_para_revisar_total: material que subieron alumnos y profesores y espera revisión (S8-01).
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
    pendientes = 0
    if usuario.has_perm('biblioteca.view_reserva'):
        # S8-03: cantidad de reservas que esperan respuesta, junto a "Reservas" en el menú.
        from .models import Reserva
        pendientes = Reserva.objects.filter(estado=Reserva.Estado.PENDIENTE).count()
    material_para_revisar = 0
    if usuario.has_perm('biblioteca.view_materialdigital'):
        # S8-01: material que subieron alumnos y profesores y espera revisión, junto a "Material digital".
        from .models import MaterialDigital
        material_para_revisar = MaterialDigital.objects.filter(estado=MaterialDigital.Estado.PENDIENTE).count()
    return {
        'prestamos_vencidos_total': vencidos,
        'reservas_pendientes_total': pendientes,
        'material_para_revisar_total': material_para_revisar,
    }
