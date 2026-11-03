from django.apps import AppConfig


class InterfazConfig(AppConfig):
    """Sin modelos: solo etiquetas de plantilla de uso común ({% load interfaz %})."""

    name = 'interfaz'
    verbose_name = 'Interfaz'
