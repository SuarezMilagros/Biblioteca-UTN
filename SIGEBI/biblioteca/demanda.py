"""Informe de demanda: qué libros se piden más de lo que la biblioteca puede prestar (Release 2, S8-07, D-R2-28).

Para un período (por defecto, los últimos DIAS_POR_DEFECTO días) y por libro:
- total_prestamos: préstamos que empezaron en el período.
- total_reservas: reservas pedidas en el período, en cualquier estado.
- reservas_sin_ejemplar: de esas, las que nunca recibieron un ejemplar (pendientes o rechazadas).
- ejemplares_activos: ejemplares que hoy se pueden prestar o apartar (no dados de baja).

"Conviene comprar más" cuando hubo más reservas sin ejemplar que ejemplares activos: la demanda que no se
pudo atender supera lo que la biblioteca tiene. Solo aparecen los libros con algún préstamo o reserva en el período.
"""
from datetime import date, timedelta

from django.db import models
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import Ejemplar, Libro, Prestamo, Reserva

DIAS_POR_DEFECTO = 90
SIN_EJEMPLAR = [Reserva.Estado.PENDIENTE, Reserva.Estado.RECHAZADA]


def periodo_por_defecto(hoy=None):
    hoy = hoy or timezone.localdate()
    return hoy - timedelta(days=DIAS_POR_DEFECTO - 1), hoy


def leer_periodo(desde, hasta, hoy=None):
    """Convierte las fechas del formulario (aaaa-mm-dd). Devuelve (desde, hasta, error)."""
    por_defecto = periodo_por_defecto(hoy)
    if not desde and not hasta:
        return (*por_defecto, None)
    try:
        desde = date.fromisoformat(desde) if desde else por_defecto[0]
        hasta = date.fromisoformat(hasta) if hasta else por_defecto[1]
    except ValueError:
        return (*por_defecto, f'Alguna fecha no es válida: se muestran los últimos {DIAS_POR_DEFECTO} días.')
    if desde > hasta:
        return (*por_defecto, f'La fecha "desde" es posterior a "hasta": se muestran los últimos {DIAS_POR_DEFECTO} días.')
    return desde, hasta, None


def _cantidad(consulta, campo):
    subconsulta = consulta.order_by().values(campo).annotate(cantidad=models.Count('pk')).values('cantidad')
    return Coalesce(models.Subquery(subconsulta, output_field=models.IntegerField()), 0)


def informe_de_demanda(desde, hasta):
    """Libros con préstamos o reservas en el período, con sus cantidades y la marca `conviene_comprar`."""
    libro = models.OuterRef('pk')
    prestamos = Prestamo.objects.filter(ejemplar__libro=libro, fecha_prestamo__range=(desde, hasta))
    reservas = Reserva.objects.filter(libro=libro, fecha_reserva__date__range=(desde, hasta))
    return (
        Libro.objects.annotate(
            total_prestamos=_cantidad(prestamos, 'ejemplar__libro'),
            total_reservas=_cantidad(reservas, 'libro'),
            reservas_sin_ejemplar=_cantidad(reservas.filter(estado__in=SIN_EJEMPLAR), 'libro'),
            ejemplares_activos=_cantidad(Ejemplar.objects.filter(libro=libro, activo=True), 'libro'),
        )
        .filter(models.Q(total_prestamos__gt=0) | models.Q(total_reservas__gt=0))
        .annotate(
            demanda=models.F('total_prestamos') + models.F('total_reservas'),
            conviene_comprar=models.Case(
                models.When(reservas_sin_ejemplar__gt=models.F('ejemplares_activos'), then=models.Value(True)),
                default=models.Value(False),
                output_field=models.BooleanField(),
            ),
        )
        .select_related('autor', 'categoria')
        .order_by('-conviene_comprar', '-reservas_sin_ejemplar', '-demanda', 'titulo', 'pk')
    )
