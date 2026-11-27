"""Eliminar personas, libros, autores, editoriales, categorías y carreras, y dar de baja un libro (D-R2-30).

Pedido del equipo (27/11/2026). La regla es la misma para todo: **se elimina solo lo que no tiene historial ni
está en uso**. Lo que tiene historial (préstamos, reservas, opiniones) se da de baja, para no perderlo:

- Persona: sin préstamos, reservas, opiniones ni material compartido. Con historial, se da de baja (como hasta ahora).
  Si tenía cuenta del portal, la cuenta se elimina con ella.
- Libro: ni sus ejemplares ni el libro tienen préstamos, reservas u opiniones. Se elimina con sus ejemplares y su
  portada. Con historial, se da de baja: se dan de baja todos sus ejemplares y deja de verse en el portal.
- Autor, editorial y categoría: ningún libro los usa. Carrera: sin personas, categorías ni material digital.

Cada función `impedimentos_*` devuelve por qué no se puede eliminar (una lista vacía si se puede). La pantalla los
muestra antes de ofrecer el botón y la vista los vuelve a revisar al eliminar. La base también protege los datos
(`on_delete=PROTECT`): si entre medio alguien registró un préstamo, la eliminación se rechaza igual.
"""
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import Ejemplar, MaterialDigital, Opinion, Prestamo, Reserva


def cantidad(numero, singular, plural):
    return f'{numero} {singular if numero == 1 else plural}'


def impedimentos_persona(persona):
    partes = [
        cantidad(persona.prestamos.count(), 'préstamo', 'préstamos'),
        cantidad(persona.reservas.count(), 'reserva', 'reservas'),
        cantidad(persona.opiniones.count(), 'opinión', 'opiniones'),
    ]
    if persona.cuenta_id:
        materiales = MaterialDigital.objects.filter(usuario_carga_id=persona.cuenta_id).count()
        partes.append(cantidad(materiales, 'material compartido', 'materiales compartidos'))
    return [parte for parte in partes if not parte.startswith('0 ')]


def impedimentos_libro(libro):
    ejemplares = Ejemplar.objects.filter(libro=libro)
    partes = [
        cantidad(Prestamo.objects.filter(ejemplar__in=ejemplares).count(), 'préstamo', 'préstamos'),
        cantidad(Reserva.objects.filter(Q(libro=libro) | Q(ejemplar__in=ejemplares)).count(), 'reserva', 'reservas'),
        cantidad(Opinion.objects.filter(libro=libro).count(), 'opinión', 'opiniones'),
    ]
    return [parte for parte in partes if not parte.startswith('0 ')]


def impedimentos_por_libros(objeto):
    """Autor, editorial o categoría: no se eliminan mientras algún libro los use."""
    libros = objeto.libros.count()
    return [cantidad(libros, 'libro', 'libros')] if libros else []


def impedimentos_carrera(carrera):
    partes = [
        cantidad(carrera.personas.count(), 'persona', 'personas'),
        cantidad(carrera.categorias.count(), 'categoría', 'categorías'),
        cantidad(carrera.materiales.count(), 'material digital', 'materiales digitales'),
    ]
    return [parte for parte in partes if not parte.startswith('0 ')]


def texto_de_impedimentos(impedimentos):
    """'2 préstamos y 1 reserva'."""
    if len(impedimentos) <= 1:
        return ''.join(impedimentos)
    return ', '.join(impedimentos[:-1]) + ' y ' + impedimentos[-1]


def _borrar_archivos_al_confirmar(campos):
    archivos = [(campo.storage, campo.name) for campo in campos if campo]
    if archivos:
        transaction.on_commit(lambda: [almacen.delete(nombre) for almacen, nombre in archivos])


def eliminar_persona(persona):
    """Elimina la persona y, si tenía, su cuenta del portal (nunca una cuenta del personal)."""
    cuenta = persona.cuenta
    _borrar_archivos_al_confirmar([persona.foto])
    persona.delete()
    if cuenta is not None and not cuenta.is_staff and not cuenta.is_superuser:
        cuenta.delete()


def eliminar_libro(libro):
    """Elimina el libro con sus ejemplares y su portada."""
    _borrar_archivos_al_confirmar([libro.imagen])
    Ejemplar.objects.filter(libro=libro).delete()
    libro.delete()


# ---------------------------------------------------------------------------
# Baja de un libro: se dan de baja todos sus ejemplares activos
# ---------------------------------------------------------------------------

def libro_dado_de_baja(libro):
    """Un libro está dado de baja cuando tiene ejemplares y ninguno está activo."""
    ejemplares = Ejemplar.objects.filter(libro=libro)
    return ejemplares.exists() and not ejemplares.filter(activo=True).exists()


def impedimentos_baja_libro(libro):
    activos = Ejemplar.objects.filter(libro=libro, activo=True)
    if not activos.exists():
        return ['no tiene ejemplares activos']
    partes = [
        cantidad(Prestamo.objects.filter(ejemplar__in=activos, fecha_devolucion__isnull=True).count(),
                 'ejemplar prestado', 'ejemplares prestados'),
        cantidad(Reserva.objects.filter(libro=libro, estado__in=Reserva.ACTIVAS).count(),
                 'reserva pendiente o confirmada', 'reservas pendientes o confirmadas'),
    ]
    return [parte for parte in partes if not parte.startswith('0 ')]


def dar_de_baja_libro(libro, motivo):
    """Da de baja todos los ejemplares activos del libro con el mismo motivo y la fecha de hoy. Devuelve cuántos."""
    return Ejemplar.objects.filter(libro=libro, activo=True).update(
        activo=False, motivo_baja=motivo, fecha_baja=timezone.localdate()
    )


def reactivar_libro(libro):
    """Vuelve a habilitar los ejemplares que se dieron de baja con el libro. Devuelve cuántos.

    Son los de la última baja (mismo motivo y fecha): un ejemplar que ya estaba dado de baja antes, por ejemplo
    uno perdido, sigue dado de baja.
    """
    ultimo = Ejemplar.objects.filter(libro=libro, activo=False).order_by('-fecha_baja', '-pk').first()
    if ultimo is None:
        return 0
    return Ejemplar.objects.filter(
        libro=libro, activo=False, motivo_baja=ultimo.motivo_baja, fecha_baja=ultimo.fecha_baja
    ).update(activo=True, motivo_baja='', fecha_baja=None)
