"""Opiniones sobre los libros (Release 2, S8-04, D-R2-29).

- Opina solo quien tuvo prestado algún ejemplar del libro (por eso se muestran como "verificadas").
- Una opinión por persona y libro: si vuelve a opinar, se edita la misma.
- Toda opinión nueva o editada queda PENDIENTE hasta que un bibliotecario la aprueba o la rechaza.
- Solo las aprobadas se publican y cuentan para el promedio de estrellas.
"""
from django.db import transaction
from django.utils import timezone

from .models import Opinion, Prestamo

MAXIMO_COMENTARIO = 1000


class OpinionNoPermitida(Exception):
    def __init__(self, motivo):
        super().__init__(motivo)
        self.motivo = motivo


def tuvo_prestado(persona, libro):
    """True si la persona tuvo (o tiene) prestado algún ejemplar de ese libro."""
    return Prestamo.objects.filter(persona=persona, ejemplar__libro=libro).exists()


def opinar(persona, libro, estrellas, comentario=''):
    """Crea la opinión, o edita la que ya tenía. En los dos casos queda pendiente de revisión."""
    if not tuvo_prestado(persona, libro):
        raise OpinionNoPermitida('Solo pueden opinar quienes tuvieron este libro prestado.')
    try:
        estrellas = int(estrellas)
    except (TypeError, ValueError):
        estrellas = 0
    if not 1 <= estrellas <= 5:
        raise OpinionNoPermitida('Elegí de 1 a 5 estrellas.')
    comentario = (comentario or '').strip()
    if len(comentario) > MAXIMO_COMENTARIO:
        raise OpinionNoPermitida(f'El comentario puede tener hasta {MAXIMO_COMENTARIO} caracteres.')
    with transaction.atomic():
        opinion, _ = Opinion.objects.select_for_update().get_or_create(
            persona=persona, libro=libro, defaults={'estrellas': estrellas},
        )
        opinion.estrellas = estrellas
        opinion.comentario = comentario
        opinion.estado = Opinion.Estado.PENDIENTE
        opinion.usuario_revision = None
        opinion.fecha_revision = None
        opinion.fecha_opinion = timezone.now()
        opinion.save()
    return opinion


def revisar(opinion, estado, usuario):
    """El personal aprueba o rechaza una opinión pendiente."""
    with transaction.atomic():
        opinion = Opinion.objects.select_for_update().get(pk=opinion.pk)
        if opinion.estado != Opinion.Estado.PENDIENTE:
            raise OpinionNoPermitida('Esta opinión ya fue revisada.')
        opinion.estado = estado
        opinion.usuario_revision = usuario
        opinion.fecha_revision = timezone.now()
        opinion.save(update_fields=['estado', 'usuario_revision', 'fecha_revision'])
    return opinion
