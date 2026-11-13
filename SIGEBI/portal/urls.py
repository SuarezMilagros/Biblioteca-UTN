from django.urls import path

from . import views

app_name = 'portal'

urlpatterns = [
    path('', views.InicioView.as_view(), name='inicio'),
    path('catalogo/', views.CatalogoView.as_view(), name='catalogo'),
    path('catalogo/<int:pk>/', views.LibroView.as_view(), name='libro'),
    path('perfil/', views.PerfilView.as_view(), name='perfil'),
]
