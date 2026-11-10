"""Intentos de acceso en el Admin: solo lectura.

El superusuario puede consultarlos y borrarlos. Borrar los fallos de un correo lo desbloquea
antes de que pasen los 15 minutos.
"""
from django.contrib import admin

from .models import IntentoDeAcceso


@admin.register(IntentoDeAcceso)
class IntentoDeAccesoAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'tipo', 'correo', 'ip')
    list_filter = ('tipo',)
    search_fields = ('correo', 'ip')
    readonly_fields = ('fecha', 'tipo', 'correo', 'ip')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False