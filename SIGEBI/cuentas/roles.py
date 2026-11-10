"""Roles del Release 1 y sus permisos.

Cada rol es un grupo de Django. La matriz de este archivo es la fuente de verdad:
después de cada `migrate` se crean los grupos y se les asignan estos permisos.

La matriz de operaciones está confirmada (decisión D-C5, 29/10/2026; ver
claude/arquitectura-cuentas-release-1.md).
"""
from django.contrib.auth.models import Group, Permission
from django.db.models import Q

ADMINISTRATIVO = 'Administrativo'
BIBLIOTECARIO = 'Bibliotecario'

# Personas y préstamos todavía no tienen pantallas: se protegen desde ya para cuando existan.
MODELOS_OPERATIVOS = [
    'categoria', 'autor', 'editorial', 'libro', 'ejemplar', 'persona', 'prestamo',
    # Release 2 (S7-02)
    'carrera',
]
ACCIONES_OPERATIVAS = ['view', 'add', 'change']


def _permisos_operativos():
    return [f'{accion}_{modelo}' for modelo in MODELOS_OPERATIVOS for accion in ACCIONES_OPERATIVAS]


PERMISOS_POR_ROL = {
    BIBLIOTECARIO: _permisos_operativos(),
    ADMINISTRATIVO: _permisos_operativos(),
}

# Permisos sobre cuentas del sistema (app auth). El Administrativo ve, da de alta y edita
# cuentas de bibliotecarios. No crea administrativos: eso lo hace solo el superusuario.
PERMISOS_DE_CUENTAS_POR_ROL = {
    BIBLIOTECARIO: [],
    ADMINISTRATIVO: ['view_user', 'add_user', 'change_user'],
}


def configurar_roles(sender=None, **kwargs):
    """Crea los grupos de roles y les asigna sus permisos. Se ejecuta después de cada migrate."""
    for nombre in PERMISOS_POR_ROL:
        grupo, _ = Group.objects.get_or_create(name=nombre)
        permisos = Permission.objects.filter(
            Q(content_type__app_label='biblioteca', codename__in=PERMISOS_POR_ROL[nombre])
            | Q(content_type__app_label='auth', codename__in=PERMISOS_DE_CUENTAS_POR_ROL.get(nombre, []))
        )
        grupo.permissions.set(permisos)
