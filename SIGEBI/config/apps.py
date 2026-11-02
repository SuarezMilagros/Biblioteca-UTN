"""Configuración de la app de administración: usa el sitio de config/admin.py."""
from django.contrib.admin.apps import AdminConfig


class SigebiAdminConfig(AdminConfig):
    default_site = 'config.admin.SuperusuariosAdminSite'
