from django.contrib import admin

from .models import Autor, Categoria, Editorial, Ejemplar, Libro, Persona, Prestamo


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
    list_display = ('codigo_inventario', 'libro', 'esta_disponible')
    search_fields = ('codigo_inventario', 'libro__titulo')

    @admin.display(boolean=True, description='Disponible')
    def esta_disponible(self, obj):
        return obj.disponible


@admin.register(Persona)
class PersonaAdmin(admin.ModelAdmin):
    list_display = ('apellido', 'nombre', 'documento', 'tipo', 'legajo')
    list_filter = ('tipo',)
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