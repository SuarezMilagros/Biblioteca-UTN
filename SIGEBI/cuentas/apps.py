from django.apps import AppConfig
from django.db.models.signals import post_migrate


class CuentasConfig(AppConfig):
    name = 'cuentas'
    verbose_name = 'Cuentas y acceso'

    def ready(self):
        from .roles import configurar_roles

        # Se ejecuta después de cada `migrate`, cuando ya existen los permisos de biblioteca.
        post_migrate.connect(configurar_roles, sender=self, dispatch_uid='cuentas.configurar_roles')
