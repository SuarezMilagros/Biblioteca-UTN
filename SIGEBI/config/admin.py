"""Sitio de administración de Django, solo para superusuarios.

Django deja entrar a cualquier cuenta con is_staff. Acá, además, hace falta ser superusuario.
La app de administración usa este sitio gracias a SigebiAdminConfig (ver config/apps.py).
"""
from django.contrib.admin import AdminSite


class SuperusuariosAdminSite(AdminSite):
    def has_permission(self, request):
        return request.user.is_active and request.user.is_superuser
