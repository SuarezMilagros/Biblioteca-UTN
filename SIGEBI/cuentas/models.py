"""Modelos propios de la app cuentas.

Las cuentas usan el modelo de usuario de Django. Acá solo se registran los intentos de acceso,
para limitar los ingresos fallidos y los pedidos de recuperación de contraseña (ver intentos.py).

Este archivo además hace falta para que Django emita la señal post_migrate de la app
(ver apps.py): sin models.py, esa señal no se envía y los grupos no se crean.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone

from biblioteca.almacenamiento import AlmacenPrivado, nombre_de_foto


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

    def __str__(self):
        return f'{self.get_tipo_display()}: {self.correo}'


class PerfilDelPersonal(models.Model):
    """Datos propios de una cuenta del personal que no están en el usuario de Django (revisión del 24/11/2026).

    Por ahora, la foto de perfil. Es privada, como la de alumnos y profesores: se guarda fuera de la carpeta
    pública y solo la ve su dueño. Los alumnos y profesores tienen la foto en su Persona.
    """

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_column='id_usuario', related_name='perfil_personal'
    )
    foto = models.ImageField(upload_to=nombre_de_foto, storage=AlmacenPrivado(), blank=True)

    class Meta:
        verbose_name = 'perfil del personal'
        verbose_name_plural = 'perfiles del personal'

    def __str__(self):
        return f'Perfil de {self.usuario}'
