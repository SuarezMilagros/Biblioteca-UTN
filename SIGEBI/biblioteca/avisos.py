"""Avisos por correo de los préstamos (Release 2, S8-06, D-R2-27).

`enviar_avisos()` manda dos tipos de aviso a los préstamos sin devolver:
- VENCE_PRONTO: vence dentro de DIAS_DE_ANTICIPACION días (o hoy). Se cuenta desde hoy y no solo el día
  exacto: si el comando no corrió algún día, el aviso igual sale.
- VENCIDO: ya venció. Se envía una vez, no todos los días.

Reglas:
- Cada aviso se envía una sola vez por préstamo y tipo (la base lo garantiza con AvisoPrestamo).
- Solo a personas con cuenta activa y correo. Un préstamo devuelto no recibe avisos.
- Si el correo falla, el aviso no se registra: se vuelve a intentar la próxima vez.
- Se puede ejecutar varias veces en el día, incluso dos a la vez, sin duplicar correos.
"""
import smtplib
from dataclasses import dataclass, field
from datetime import timedelta

from django.core.mail import EmailMessage, get_connection
from django.db import IntegrityError, transaction
from django.template.loader import render_to_string
from django.utils import timezone

from .models import AvisoPrestamo, Prestamo

DIAS_DE_ANTICIPACION = 2

ASUNTOS = {
    AvisoPrestamo.Tipo.VENCE_PRONTO: 'Tu préstamo vence pronto',
    AvisoPrestamo.Tipo.VENCIDO: 'Tu préstamo venció',
}


@dataclass
class Resultado:
    enviados: dict = field(default_factory=lambda: {tipo: [] for tipo in AvisoPrestamo.Tipo})
    sin_correo: list = field(default_factory=list)
    fallidos: list = field(default_factory=list)

    @property
    def total_enviados(self):
        return sum(len(prestamos) for prestamos in self.enviados.values())


def prestamos_para_avisar(tipo, hoy):
    """Préstamos sin devolver que corresponden a ese tipo de aviso y todavía no lo recibieron."""
    sin_devolver = Prestamo.objects.filter(fecha_devolucion__isnull=True).exclude(avisos__tipo=tipo)
    if tipo == AvisoPrestamo.Tipo.VENCE_PRONTO:
        prestamos = sin_devolver.filter(
            fecha_vencimiento__gte=hoy, fecha_vencimiento__lte=hoy + timedelta(days=DIAS_DE_ANTICIPACION)
        )
    else:
        prestamos = sin_devolver.filter(fecha_vencimiento__lt=hoy)
    return prestamos.select_related('persona__cuenta', 'ejemplar__libro').order_by('fecha_vencimiento', 'pk')


def correo_de(prestamo):
    """El correo de la persona, si tiene cuenta activa con correo. Si no, None."""
    cuenta = prestamo.persona.cuenta
    if cuenta is None or not cuenta.is_active or not cuenta.email:
        return None
    return cuenta.email


def mensaje(prestamo, tipo, hoy):
    dias = (prestamo.fecha_vencimiento - hoy).days
    contexto = {'prestamo': prestamo, 'persona': prestamo.persona, 'dias': dias, 'dias_de_atraso': -dias}
    cuerpo = render_to_string(f'biblioteca/correo/aviso_{tipo.lower()}.txt', contexto)
    return f'{ASUNTOS[tipo]}: {prestamo.ejemplar.libro.titulo}', cuerpo


def enviar_avisos(hoy=None, simular=False):
    """Envía los avisos pendientes y devuelve un Resultado. Con simular=True no envía ni registra nada."""
    hoy = hoy or timezone.localdate()
    resultado = Resultado()
    conexion = None if simular else get_connection()
    for tipo in AvisoPrestamo.Tipo:
        for prestamo in prestamos_para_avisar(tipo, hoy):
            correo = correo_de(prestamo)
            if correo is None:
                resultado.sin_correo.append(prestamo)
                continue
            if simular:
                resultado.enviados[tipo].append(prestamo)
                continue
            asunto, cuerpo = mensaje(prestamo, tipo, hoy)
            try:
                with transaction.atomic():
                    # Primero se registra: si otra ejecución ya lo registró, la base lo rechaza y no se envía dos veces.
                    AvisoPrestamo.objects.create(prestamo=prestamo, tipo=tipo)
                    # Si el envío falla, la excepción deshace el registro y el aviso queda para la próxima vez.
                    EmailMessage(asunto, cuerpo, None, [correo], connection=conexion).send()
            except IntegrityError:
                continue
            except (smtplib.SMTPException, OSError):
                resultado.fallidos.append(prestamo)
                continue
            resultado.enviados[tipo].append(prestamo)
    return resultado
