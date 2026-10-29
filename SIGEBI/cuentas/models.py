"""La app cuentas no tiene modelos propios: usa el modelo de usuario de Django.

Este archivo hace falta para que Django emita la señal post_migrate de la app
(ver apps.py): sin models.py, esa señal no se envía y los grupos no se crean.
"""
