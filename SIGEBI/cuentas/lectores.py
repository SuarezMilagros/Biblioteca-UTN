"""Cuentas de estudiantes y docentes (Release 2, S7-03).

La crea el personal desde la ficha de la Persona (D-R2-1). La persona no tiene contraseña:
la define con el enlace que le llega por correo, igual que las cuentas del personal.
El usuario de Django es el documento, como en las cuentas del personal.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction

from .roles import LECTOR


def requisitos_para_cuenta(persona):
    """Motivos por los que todavía no se le puede crear la cuenta (lista vacía: se puede)."""
    motivos = []
    if persona.cuenta_id:
        motivos.append('Ya tiene una cuenta.')
    if not persona.activo:
        motivos.append('Está dada de baja.')
    if not persona.carreras.exists():
        motivos.append('No tiene ninguna carrera asignada: sin carrera no vería ningún libro.')
    return motivos


def crear_cuenta_de_lector(persona, correo):
    """Crea la cuenta, la vincula a la persona y le asigna el rol Lector. No envía el correo."""
    with transaction.atomic():
        cuenta = get_user_model()(
            username=persona.documento,
            email=correo,
            first_name=persona.nombre,
            last_name=persona.apellido,
            is_active=persona.activo,
        )
        # Nadie escribe ni ve una contraseña: la define la persona desde el correo.
        cuenta.set_unusable_password()
        cuenta.save()
        cuenta.groups.add(Group.objects.get(name=LECTOR))
        persona.cuenta = cuenta
        persona.save(update_fields=['cuenta'])
    return cuenta
