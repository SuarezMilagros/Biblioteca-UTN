"""Informe de préstamos por persona (pedido de la profesora, 18/11/2026).

Para un rango de fechas que elige el personal (como máximo MAXIMO_DIAS días, un mes) y por persona:
- prestamos: préstamos que empezaron en el rango;
- devueltos, sin_devolver y vencidos (sin devolver y con el vencimiento ya pasado), de esos mismos préstamos.

Por defecto, el mes actual hasta hoy. Solo aparecen las personas con algún préstamo en el rango.
"""
from datetime import date

from django.db import models
from django.utils import timezone

from .models import Persona

MAXIMO_DIAS = 31


def periodo_por_defecto(hoy=None):
    hoy = hoy or timezone.localdate()
    return hoy.replace(day=1), hoy


def leer_periodo(desde, hasta, hoy=None):
    """Convierte las fechas del formulario (aaaa-mm-dd). Devuelve (desde, hasta, error)."""
    por_defecto = periodo_por_defecto(hoy)
    if not desde and not hasta:
        return (*por_defecto, None)
    try:
        desde = date.fromisoformat(desde) if desde else por_defecto[0]
        hasta = date.fromisoformat(hasta) if hasta else por_defecto[1]
    except ValueError:
        return (*por_defecto, 'Alguna fecha no es válida: se muestra el mes actual.')
    if desde > hasta:
        return (*por_defecto, 'La fecha "desde" es posterior a "hasta": se muestra el mes actual.')
    if (hasta - desde).days + 1 > MAXIMO_DIAS:
        return (*por_defecto, f'El rango puede ser de hasta {MAXIMO_DIAS} días (un mes): se muestra el mes actual.')
    return desde, hasta, None


def informe_por_persona(desde, hasta, hoy=None):
    hoy = hoy or timezone.localdate()
    en_rango = models.Q(prestamos__fecha_prestamo__range=(desde, hasta))
    sin_devolver = en_rango & models.Q(prestamos__fecha_devolucion__isnull=True)
    return (
        Persona.objects.annotate(
            total_prestamos=models.Count('prestamos', filter=en_rango),
            devueltos=models.Count('prestamos', filter=en_rango & models.Q(prestamos__fecha_devolucion__isnull=False)),
            sin_devolver=models.Count('prestamos', filter=sin_devolver),
            vencidos=models.Count('prestamos', filter=sin_devolver & models.Q(prestamos__fecha_vencimiento__lt=hoy)),
        )
        .filter(total_prestamos__gt=0)
        .order_by('-total_prestamos', 'apellido', 'nombre', 'pk')
    )
