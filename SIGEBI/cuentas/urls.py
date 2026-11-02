from django.urls import path

from . import views

app_name = 'cuentas'

urlpatterns = [
    path('', views.UsuarioListView.as_view(), name='usuario_list'),
    path('nueva/', views.UsuarioCreateView.as_view(), name='usuario_create'),
    path('<int:pk>/editar/', views.UsuarioUpdateView.as_view(), name='usuario_update'),
    path(
        '<int:pk>/reenviar-definicion/',
        views.ReenviarDefinicionView.as_view(),
        name='usuario_reenviar_definicion',
    ),
]
