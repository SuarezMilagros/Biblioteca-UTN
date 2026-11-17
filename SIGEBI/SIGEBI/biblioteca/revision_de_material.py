"""Material compartido por alumnos y profesores (Release 2, S8-01, D-R2-7).

- Un lector sube material solo para sus carreras. Queda PENDIENTE y no lo ve nadie más que él.
- Un bibliotecario lo abre y lo aprueba (se publica) o lo rechaza con un motivo.
- En los dos casos se le avisa por correo a quien lo subió.
"""
import smtplib

from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from .models import MaterialDigital

# Para que nadie llene el almacenamiento con archivos que todavía nadie revisó.
MAXIMO_PENDIENTES_POR_PERSONA = 5


class RevisionNoPermitida(Exception):
    def __init__(self, motivo):
        super().__init__(motivo)
        self.motivo = motivo


def pendientes_de(usuario):
    return MaterialDigital.objects.filter(usuario_carga=usuario, estado=MaterialDigital.Estado.PENDIENTE).count()


def puede_subir(usuario):
    return pendientes_de(usuario) < MAXIMO_PENDIENTES_POR_PERSONA


def _bloquear_pendiente(material):
    material = MaterialDigital.objects.select_for_update().get(pk=material.pk)
    if material.estado != MaterialDigital.Estado.PENDIENTE:
        raise RevisionNoPermitida('Este material ya fue revisado.')
    return material


def aprobar(material, usuario):
    """Se publica: lo ven los alumnos y profesores de su carrera."""
    with transaction.atomic():
        material = _bloquear_pendiente(material)
        material.estado = MaterialDigital.Estado.APROBADO
        material.usuario_revision = usuario
        material.fecha_revision = timezone.now()
        material.save(update_fields=['estado', 'usuario_revision', 'fecha_revision'])
    return material


def rechazar(material, motivo, usuario):
    motivo = (motivo or '').strip()
    if not motivo:
        raise RevisionNoPermitida('Escribí el motivo del rechazo: se lo enviamos a quien lo subió.')
    with transaction.atomic():
        material = _bloquear_pendiente(material)
        material.estado = MaterialDigital.Estado.RECHAZADO
        material.motivo_rechazo = motivo
        material.usuario_revision = usuario
        material.fecha_revision = timezone.now()
        material.save(update_fields=['estado', 'motivo_rechazo', 'usuario_revision', 'fecha_revision'])
    return material


ASUNTOS = {
    MaterialDigital.Estado.APROBADO: 'Tu material ya está publicado',
    MaterialDigital.Estado.RECHAZADO: 'Tu material no pudo publicarse',
}


def avisar_por_correo(material):
    """Avisa a quien lo subió el resultado de la revisión.

    Devuelve False si no se pudo enviar (sin correo o falló el servidor). El material queda igual:
    el aviso es una ayuda, no una condición.
    """
    usuario = material.usuario_carga
    if not usuario.email or material.estado not in ASUNTOS:
        return False
    persona = getattr(usuario, 'persona', None)
    plantilla = f'biblioteca/correo/material_{material.estado.lower()}.txt'
    contexto = {'material': material, 'nombre': persona.nombre if persona else usuario.first_name}
    try:
        send_mail(
            f'{ASUNTOS[material.estado]}: {material.titulo}',
            render_to_string(plantilla, contexto),
            None,
            [usuario.email],
        )
    except (smtplib.SMTPException, OSError):
        return False
    return True
