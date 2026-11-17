"""Reglas de las reservas de libros físicos (Release 2, S8-02, D-R2-3 y D-R2-15).

Un lector puede reservar un libro de sus carreras si:
- está activo y no tiene préstamos vencidos;
- el libro tiene al menos un ejemplar activo (aunque ahora estén todos prestados);
- no tiene ya una reserva activa de ese libro;
- no tiene ya MAXIMO_RESERVAS_ACTIVAS reservas activas.
"""
from django.db import transaction
from django.utils import timezone

from .models import Libro, Persona, Reserva

MAXIMO_RESERVAS_ACTIVAS = 2
HORAS_PARA_RETIRAR = 48


class ReservaNoPermitida(Exception):
    def __init__(self, motivos):
        super().__init__(' '.join(motivos))
        self.motivos = motivos


def motivos_para_no_reservar(persona, libro):
    """Lista de motivos por los que no puede reservar ese libro (vacía: puede)."""
    motivos = []
    if not persona.activo:
        motivos.append('Tu cuenta está dada de baja en la biblioteca.')
    if persona.prestamos.filter(fecha_devolucion__isnull=True, fecha_vencimiento__lt=timezone.localdate()).exists():
        motivos.append('Tenés préstamos vencidos: devolvelos para poder reservar.')
    if not Libro.objects.de_las_carreras(persona.carreras.all()).filter(pk=libro.pk).exists():
        motivos.append('Este libro no es de tus carreras.')
    if not libro.ejemplares.filter(activo=True).exists():
        motivos.append('La biblioteca no tiene ejemplares de este libro para prestar.')
    activas = persona.reservas.filter(estado__in=Reserva.ACTIVAS)
    if activas.filter(libro=libro).exists():
        motivos.append('Ya tenés una reserva activa de este libro.')
    elif activas.count() >= MAXIMO_RESERVAS_ACTIVAS:
        motivos.append(f'Ya tenés {MAXIMO_RESERVAS_ACTIVAS} reservas activas, que es el máximo.')
    return motivos


def reservar(persona, libro):
    """Crea la reserva PENDIENTE. Bloquea la fila de la persona para que dos pedidos simultáneos
    no superen el máximo de reservas activas."""
    with transaction.atomic():
        persona = Persona.objects.select_for_update().get(pk=persona.pk)
        motivos = motivos_para_no_reservar(persona, libro)
        if motivos:
            raise ReservaNoPermitida(motivos)
        return Reserva.objects.create(persona=persona, libro=libro)


def cancelar(reserva):
    """El lector cancela una reserva que todavía está pendiente."""
    with transaction.atomic():
        reserva = Reserva.objects.select_for_update().get(pk=reserva.pk)
        if reserva.estado != Reserva.Estado.PENDIENTE:
            raise ReservaNoPermitida(['Solo se puede cancelar una reserva pendiente.'])
        reserva.estado = Reserva.Estado.CANCELADA
        reserva.save(update_fields=['estado'])
        return reserva
