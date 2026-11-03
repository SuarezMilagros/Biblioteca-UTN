"""Variables de `cuentas` para la cabecera común (registradas en config/settings.py).

- rol_usuario: nombre del rol de quien está conectado (Superusuario, Administrativo,
  Bibliotecario o «Sin rol»), según los grupos definidos en cuentas/roles.py.
"""
from .roles import ADMINISTRATIVO, BIBLIOTECARIO


def interfaz(request):
    usuario = getattr(request, 'user', None)
    if usuario is None or not usuario.is_authenticated:
        return {}
    if usuario.is_superuser:
        return {'rol_usuario': 'Superusuario'}
    roles = set(usuario.groups.filter(name__in=[ADMINISTRATIVO, BIBLIOTECARIO]).values_list('name', flat=True))
    # Si tuviera los dos grupos, se informa el de más privilegios.
    for rol in (ADMINISTRATIVO, BIBLIOTECARIO):
        if rol in roles:
            return {'rol_usuario': rol}
    return {'rol_usuario': 'Sin rol'}
