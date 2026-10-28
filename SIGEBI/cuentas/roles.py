"""Roles del Release 1 y sus permisos.

Cada rol es un grupo de Django. La matriz de este archivo es la fuente de verdad:
después de cada `migrate` se crean los grupos y se les asignan estos permisos.

La matriz es un borrador pendiente de confirmación (ver
claude/arquitectura-cuentas-release-1.md, decisión D-C5).
"""
from django.contrib.auth.models import Group, Permission

ADMINISTRATIVO = 'Administrativo'
BIBLIOTECARIO = 'Bibliotecario'

# Personas y préstamos todavía no tienen pantallas: se protegen desde ya para cuando existan.
MODELOS_OPERATIVOS = ['categoria', 'autor', 'editorial', 'libro', 'ejemplar', 'persona', 'prestamo']
ACCIONES_OPERATIVAS = ['view', 'add', 'change']


def _permisos_operativos():
    return [f'{accion}_{modelo}' for modelo in MODELOS_OPERATIVOS for accion in ACCIONES_OPERATIVAS]


PERMISOS_POR_ROL = {
    BIBLIOTECARIO: _permisos_operativos(),
    # Borrador: el Administrativo tiene todo lo del Bibliotecario.
    # Sus permisos sobre cuentas se agregan en el paso de cuentas.
    ADMINISTRATIVO: _permisos_operativos(),
}


def configurar_roles(sender=None, **kwargs):
    """Crea los grupos de roles y les asigna sus permisos. Se ejecuta después de cada migrate."""
    for nombre, codenames in PERMISOS_POR_ROL.items():
        grupo, _ = Group.objects.get_or_create(name=nombre)
        permisos = Permission.objects.filter(content_type__app_label='biblioteca', codename__in=codenames)
        grupo.permissions.set(permisos)
