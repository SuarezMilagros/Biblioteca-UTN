from django.contrib import admin

from .models import (
    AvisoPrestamo, Autor, Carrera, Categoria, Editorial, Ejemplar, Libro, MaterialDigital, Persona, Prestamo, Reserva,
)


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion')
    search_fields = ('nombre',)


@admin.register(Autor)
class AutorAdmin(admin.ModelAdmin):
    list_display = ('apellido', 'nombre')
    search_fields = ('apellido', 'nombre')


@admin.register(Editorial)
class EditorialAdmin(admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)


@admin.register(Libro)
class LibroAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'autor', 'editorial', 'categoria', 'isbn')
    list_filter = ('categoria',)
    search_fields = ('titulo', 'isbn', 'autor__apellido', 'autor__nombre')


@admin.register(Ejemplar)
class EjemplarAdmin(admin.ModelAdmin):
    list_display = ('codigo_inventario', 'libro', 'activo', 'esta_disponible')
    list_filter = ('activo', 'motivo_baja')
    search_fields = ('codigo_inventario', 'libro__titulo')

    @admin.display(boolean=True, description='Disponible')
    def esta_disponible(self, obj):
        return obj.disponible


@admin.register(Persona)
class PersonaAdmin(admin.ModelAdmin):
    list_display = ('apellido', 'nombre', 'documento', 'tipo', 'legajo', 'activo')
    list_filter = ('tipo', 'activo')
    search_fields = ('apellido', 'nombre', 'documento', 'legajo')


@admin.register(Prestamo)
class PrestamoAdmin(admin.ModelAdmin):
    list_display = (
        'ejemplar', 'persona', 'fecha_prestamo',
        'fecha_vencimiento', 'fecha_devolucion',
        'esta_vencido', 'usuario_sistema',
    )
    list_filter = ('fecha_vencimiento',)
    search_fields = ('ejemplar__codigo_inventario', 'persona__apellido', 'persona__documento')
    readonly_fields = ('usuario_sistema',)

    @admin.display(boolean=True, description='Vencido')
    def esta_vencido(self, obj):
        return obj.vencido

    def save_model(self, request, obj, form, change):
        if obj.usuario_sistema_id is None:
            obj.usuario_sistema = request.user
        super().save_model(request, obj, form, change)


@admin.register(Carrera)
class CarreraAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'nivel')
    list_filter = ('nivel',)
    search_fields = ('nombre',)


@admin.register(MaterialDigital)
class MaterialDigitalAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'tipo', 'carrera', 'estado', 'activo', 'fecha_carga')
    list_filter = ('tipo', 'estado', 'activo', 'carrera')
    search_fields = ('titulo', 'autores')


@admin.register(Reserva)
class ReservaAdmin(admin.ModelAdmin):
    list_display = ('libro', 'persona', 'estado', 'fecha_reserva', 'ejemplar', 'vence_retiro')
    list_filter = ('estado',)
    search_fields = ('libro__titulo', 'persona__apellido', 'persona__documento')


@admin.register(AvisoPrestamo)
class AvisoPrestamoAdmin(admin.ModelAdmin):
    """Solo consulta: los avisos los registra el comando enviar_avisos (S8-06)."""

    list_display = ('prestamo', 'tipo', 'fecha_envio')
    list_filter = ('tipo',)
    search_fields = ('prestamo__persona__apellido', 'prestamo__persona__documento', 'prestamo__ejemplar__codigo_inventario')
    list_select_related = ('prestamo__persona', 'prestamo__ejemplar')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
