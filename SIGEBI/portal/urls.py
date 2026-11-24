from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = 'portal'

# Reorganización del portal (24/11/2026): Explorar (Catálogo, Material digital), Mi biblioteca (Préstamos,
# Reservas) y Mi perfil (la cuenta). "Lo que compartí" es una pestaña de Material digital.
urlpatterns = [
    path('', views.InicioView.as_view(), name='inicio'),
    # Explorar
    path('catalogo/', views.CatalogoView.as_view(), name='catalogo'),
    path('catalogo/<int:pk>/', views.LibroView.as_view(), name='libro'),
    path('catalogo/<int:pk>/reservar/', views.ReservarView.as_view(), name='reservar'),
    path('catalogo/<int:pk>/opinar/', views.OpinarView.as_view(), name='opinar'),
    path('material/', views.MaterialView.as_view(), name='material'),
    path('material/compartido/', views.MiBibliotecaView.as_view(template_name='portal/material_compartido.html'),
         name='mi_material'),
    path('material/compartir/', views.CompartirMaterialView.as_view(), name='material_compartir'),
    path('material/<int:pk>/archivo/', views.MaterialArchivoView.as_view(), name='material_archivo'),
    # Mi biblioteca
    path('prestamos/', views.MiBibliotecaView.as_view(template_name='portal/prestamos_sin_devolver.html'),
         name='sin_devolver'),
    path('prestamos/historial/', views.MiBibliotecaView.as_view(template_name='portal/prestamos_historial.html'),
         name='historial'),
    path('reservas/', views.MiBibliotecaView.as_view(template_name='portal/reservas.html'), name='mis_reservas'),
    path('reservas/<int:pk>/cancelar/', views.CancelarReservaView.as_view(), name='cancelar_reserva'),
    # Cuenta
    path('perfil/', views.PerfilView.as_view(), name='perfil'),
    path('perfil/foto/', views.FotoView.as_view(), name='foto'),
    path('perfil/foto/ver/', views.MiFotoView.as_view(), name='mi_foto'),
    path('perfil/foto/quitar/', views.QuitarFotoView.as_view(), name='quitar_foto'),
    # Direcciones anteriores a la reorganización: siguen funcionando (enlaces guardados o en correos).
    path('perfil/reservas/', RedirectView.as_view(pattern_name='portal:mis_reservas')),
    path('perfil/material/', RedirectView.as_view(pattern_name='portal:mi_material')),
    path('perfil/sin-devolver/', RedirectView.as_view(pattern_name='portal:sin_devolver')),
    path('perfil/historial/', RedirectView.as_view(pattern_name='portal:historial')),
]
