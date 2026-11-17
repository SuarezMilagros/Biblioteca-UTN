"""Reglas de las reservas de libros físicos (Release 2, S8-02 y S8-03, D-R2-3, D-R2-14 a D-R2-16 y D-R2-19).

Un lector puede reservar un libro de sus carreras si:
- está activo y no tiene préstamos vencidos;
- el libro tiene al menos un ejemplar activo (aunque ahora estén todos prestados);
- no tiene ya una reserva activa de ese libro;
- no tiene ya MAXIMO_RESERVAS_ACTIVAS reservas activas.
"""
import smtplib
from datetime import timedelta

from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.template.loader import render_to_string
from django.utils import timezone

from .models import Ejemplar, Libro, Persona, Prestamo, Reserva

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


def vencer_reservas():
    """Pasa a VENCIDA las confirmadas cuyo plazo de retiro ya pasó (D-R2-19).

    No hace falta una tarea programada: se llama antes de mostrar o de cambiar reservas.
    Devuelve cuántas vencieron.
    """
    return Reserva.objects.filter(
        estado=Reserva.Estado.CONFIRMADA, vence_retiro__lte=timezone.now()
    ).update(estado=Reserva.Estado.VENCIDA)


def reservar(persona, libro):
    """Crea la reserva PENDIENTE. Bloquea la fila de la persona para que dos pedidos simultáneos
    no superen el máximo de reservas activas."""
    vencer_reservas()
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


# ---------- Lado del personal (S8-03) ----------

def ejemplares_para_apartar(libro):
    """Ejemplares de ese libro que se pueden apartar ahora."""
    return Ejemplar.objects.disponibles().filter(libro=libro).order_by('codigo_inventario')


def _bloquear(reserva, estado_esperado, mensaje):
    reserva = Reserva.objects.select_for_update().get(pk=reserva.pk)
    if reserva.estado != estado_esperado:
        raise ReservaNoPermitida([mensaje])
    return reserva


def confirmar(reserva, ejemplar, usuario):
    """Aparta el ejemplar por HORAS_PARA_RETIRAR horas. La base garantiza que un ejemplar no
    quede apartado dos veces (D-R2-16); si dos personas confirman a la vez, una recibe el error."""
    vencer_reservas()
    try:
        with transaction.atomic():
            reserva = _bloquear(reserva, Reserva.Estado.PENDIENTE, 'Esta reserva ya no está pendiente.')
            ejemplar = Ejemplar.objects.select_for_update().get(pk=ejemplar.pk)
            if ejemplar.libro_id != reserva.libro_id:
                raise ReservaNoPermitida(['Ese ejemplar no es del libro reservado.'])
            if not ejemplares_para_apartar(reserva.libro).filter(pk=ejemplar.pk).exists():
                raise ReservaNoPermitida(['Ese ejemplar ya no está disponible. Elegí otro.'])
            ahora = timezone.now()
            reserva.estado = Reserva.Estado.CONFIRMADA
            reserva.ejemplar = ejemplar
            reserva.usuario_respuesta = usuario
            reserva.fecha_respuesta = ahora
            reserva.vence_retiro = ahora + timedelta(hours=HORAS_PARA_RETIRAR)
            reserva.save()
    except IntegrityError:
        raise ReservaNoPermitida(['Ese ejemplar acaba de quedar apartado para otra reserva. Elegí otro.'])
    return reserva


def rechazar(reserva, motivo, usuario):
    motivo = (motivo or '').strip()
    if not motivo:
        raise ReservaNoPermitida(['Escribí el motivo del rechazo: se lo enviamos a la persona.'])
    with transaction.atomic():
        reserva = _bloquear(reserva, Reserva.Estado.PENDIENTE, 'Esta reserva ya no está pendiente.')
        reserva.estado = Reserva.Estado.RECHAZADA
        reserva.motivo_rechazo = motivo
        reserva.usuario_respuesta = usuario
        reserva.fecha_respuesta = timezone.now()
        reserva.save()
    return reserva


def retirar(reserva, usuario):
    """La persona retira el ejemplar apartado: se registra el préstamo de siempre (14 días)."""
    vencer_reservas()
    with transaction.atomic():
        reserva = _bloquear(
            reserva, Reserva.Estado.CONFIRMADA, 'Esta reserva no está lista para retirar (puede haber vencido).'
        )
        if not reserva.persona.activo:
            raise ReservaNoPermitida(['La persona está dada de baja: no puede recibir préstamos.'])
        hoy = timezone.localdate()
        prestamo = Prestamo.objects.create(
            persona=reserva.persona, ejemplar=reserva.ejemplar, usuario_sistema=usuario,
            fecha_prestamo=hoy, fecha_vencimiento=Prestamo.calcular_vencimiento(hoy),
        )
        reserva.estado = Reserva.Estado.RETIRADA
        reserva.prestamo = prestamo
        reserva.save()
    return reserva


def liberar(reserva):
    """El personal libera una reserva confirmada (por ejemplo, la persona avisó que no la retira)."""
    with transaction.atomic():
        reserva = _bloquear(reserva, Reserva.Estado.CONFIRMADA, 'Solo se puede liberar una reserva confirmada.')
        reserva.estado = Reserva.Estado.CANCELADA
        reserva.ejemplar = None
        reserva.save()
    return reserva


def reserva_vigente_de(ejemplar):
    """La reserva confirmada vigente que tiene apartado ese ejemplar, o None."""
    return Reserva.objects.vigentes().select_related('persona').filter(ejemplar=ejemplar).first()


ASUNTOS = {
    Reserva.Estado.CONFIRMADA: 'Tu reserva está lista para retirar',
    Reserva.Estado.RECHAZADA: 'Tu reserva no pudo aceptarse',
}


def avisar_por_correo(reserva):
    """Avisa a la persona que su reserva se confirmó o se rechazó.

    Devuelve False si no se pudo enviar (la persona no tiene cuenta o falló el servidor de correo).
    La reserva queda igual: el aviso es una ayuda, no una condición.
    """
    cuenta = reserva.persona.cuenta
    if cuenta is None or not cuenta.email or reserva.estado not in ASUNTOS:
        return False
    plantilla = f'biblioteca/correo/reserva_{reserva.estado.lower()}.txt'
    try:
        send_mail(
            f'{ASUNTOS[reserva.estado]}: {reserva.libro.titulo}',
            render_to_string(plantilla, {'reserva': reserva}),
            None,
            [cuenta.email],
        )
    except (smtplib.SMTPException, OSError):
        return False
    return True
