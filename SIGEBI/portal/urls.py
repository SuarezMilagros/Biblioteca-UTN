from django.urls import path

from . import views

app_name = 'portal'

urlpatterns = [
    path('', views.InicioView.as_view(), name='inicio'),
    path('catalogo/', views.CatalogoView.as_view(), name='catalogo'),
    path('catalogo/<int:pk>/', views.LibroView.as_view(), name='libro'),
    path('catalogo/<int:pk>/reservar/', views.ReservarView.as_view(), name='reservar'),
    path('catalogo/<int:pk>/opinar/', views.OpinarView.as_view(), name='opinar'),
    path('reservas/<int:pk>/cancelar/', views.CancelarReservaView.as_view(), name='cancelar_reserva'),
    path('material/', views.MaterialView.as_view(), name='material'),
    path('material/compartir/', views.CompartirMaterialView.as_view(), name='material_compartir'),
    path('material/<int:pk>/archivo/', views.MaterialArchivoView.as_view(), name='material_archivo'),
    path('perfil/', views.PerfilView.as_view(), name='perfil'),
    path('perfil/reservas/', views.PerfilView.as_view(template_name='portal/perfil_reservas.html'), name='mis_reservas'),
    path('perfil/material/', views.PerfilView.as_view(template_name='portal/perfil_material.html'), name='mi_material'),
    path('perfil/sin-devolver/', views.PerfilView.as_view(template_name='portal/perfil_sin_devolver.html'),
         name='sin_devolver'),
    path('perfil/historial/', views.PerfilView.as_view(template_name='portal/perfil_historial.html'), name='historial'),
    path('perfil/foto/', views.FotoView.as_view(), name='foto'),
    path('perfil/foto/ver/', views.MiFotoView.as_view(), name='mi_foto'),
    path('perfil/foto/quitar/', views.QuitarFotoView.as_view(), name='quitar_foto'),
]
