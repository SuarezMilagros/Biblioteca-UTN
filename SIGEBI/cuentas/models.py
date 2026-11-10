"""Modelos propios de la app cuentas.

Las cuentas usan el modelo de usuario de Django. Acá solo se registran los intentos de acceso,
para limitar los ingresos fallidos y los pedidos de recuperación de contraseña (ver intentos.py).

Este archivo además hace falta para que Django emita la señal post_migrate de la app
(ver apps.py): sin models.py, esa señal no se envía y los grupos no se crean.
"""
from django.db import models
from django.utils import timezone


class IntentoDeAcceso(models.Model):
    """Un ingreso fallido o un pedido de recuperación de contraseña."""

    class Tipo(models.TextChoices):
        INGRESO_FALLIDO = 'INGRESO_FALLIDO', 'Ingreso fallido'
        RECUPERACION = 'RECUPERACION', 'Pedido de recuperación'

    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    # Se guarda el correo escrito, aunque no exista ninguna cuenta con ese correo.
    correo = models.CharField(max_length=254)
    ip = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP')
    fecha = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        verbose_name = 'intento de acceso'
        verbose_name_plural = 'intentos de acceso'
        ordering = ['-fecha']

    def str(self):
        return f'{self.get_tipo_display()}: {self.correo}'