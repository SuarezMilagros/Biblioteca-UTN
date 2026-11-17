from django.urls import path

from . import views

app_name = 'portal'

urlpatterns = [
    path('', views.InicioView.as_view(), name='inicio'),
    path('catalogo/', views.CatalogoView.as_view(), name='catalogo'),
    path('catalogo/<int:pk>/', views.LibroView.as_view(), name='libro'),
    path('catalogo/<int:pk>/reservar/', views.ReservarView.as_view(), name='reservar'),
    path('reservas/<int:pk>/cancelar/', views.CancelarReservaView.as_view(), name='cancelar_reserva'),
    path('material/', views.MaterialView.as_view(), name='material'),
    path('material/compartir/', views.CompartirMaterialView.as_view(), name='material_compartir'),
    path('material/<int:pk>/archivo/', views.MaterialArchivoView.as_view(), name='material_archivo'),
    path('perfil/', views.PerfilView.as_view(), name='perfil'),
]
