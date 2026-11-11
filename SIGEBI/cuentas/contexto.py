"""Variables de `cuentas` para la cabecera común (registradas en config/settings.py).

- rol_usuario: nombre del rol de quien está conectado (Superusuario, Administrativo,
  Bibliotecario, Lector o «Sin rol»), según los grupos definidos en cuentas/roles.py.
- es_lector: True para estudiantes y docentes. base.html les muestra el menú del portal (S7-04).
- url_inicio: nombre de la pantalla de inicio de cada uno (panel del personal o portal).
"""
from .roles import ADMINISTRATIVO, BIBLIOTECARIO, LECTOR


def interfaz(request):
    usuario = getattr(request, 'user', None)
    if usuario is None or not usuario.is_authenticated:
        return {}
    if usuario.is_superuser:
        return {'rol_usuario': 'Superusuario', 'es_lector': False, 'url_inicio': 'biblioteca:inicio'}
    roles = set(
        usuario.groups.filter(name__in=[ADMINISTRATIVO, BIBLIOTECARIO, LECTOR]).values_list('name', flat=True)
    )
    # Si tuviera más de un grupo, se informa el de más privilegios.
    rol_usuario = next((rol for rol in (ADMINISTRATIVO, BIBLIOTECARIO, LECTOR) if rol in roles), 'Sin rol')
    es_lector = rol_usuario == LECTOR
    return {
        'rol_usuario': rol_usuario,
        'es_lector': es_lector,
        'url_inicio': 'portal:inicio' if es_lector else 'biblioteca:inicio',
    }
