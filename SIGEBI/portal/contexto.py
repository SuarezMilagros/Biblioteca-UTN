"""Variables del portal para la cabecera común (reorganización del portal, 24/11/2026).

Solo para alumnos y profesores: los contadores del menú «Mi biblioteca».
- portal_prestamos_vencidos: sus préstamos sin devolver con el vencimiento pasado (junto a Préstamos).
- portal_reservas_para_retirar: sus reservas confirmadas y vigentes (junto a Reservas).

Solo lectura: dos consultas COUNT por pantalla.
"""
from django.utils import timezone

from cuentas.roles import es_lector


def avisos_del_lector(request):
    usuario = getattr(request, 'user', None)
    if usuario is None or not usuario.is_authenticated or not es_lector(usuario):
        return {}
    persona = getattr(usuario, 'persona', None)
    if persona is None:
        return {}
    from biblioteca.models import Reserva
    return {
        'portal_prestamos_vencidos': persona.prestamos.filter(
            fecha_devolucion__isnull=True, fecha_vencimiento__lt=timezone.localdate()
        ).count(),
        'portal_reservas_para_retirar': Reserva.objects.vigentes().filter(persona=persona).count(),
    }
