from django.urls import path

from . import views

app_name = 'biblioteca'

urlpatterns = [
    path('', views.inicio, name='inicio'),

    path('categorias/', views.CategoriaListView.as_view(), name='categoria_list'),
    path('categorias/nueva/', views.CategoriaCreateView.as_view(), name='categoria_create'),
    path('categorias/<int:pk>/editar/', views.CategoriaUpdateView.as_view(), name='categoria_update'),

    path('autores/', views.AutorListView.as_view(), name='autor_list'),
    path('autores/nuevo/', views.AutorCreateView.as_view(), name='autor_create'),
    path('autores/<int:pk>/editar/', views.AutorUpdateView.as_view(), name='autor_update'),

    path('editoriales/', views.EditorialListView.as_view(), name='editorial_list'),
    path('editoriales/nueva/', views.EditorialCreateView.as_view(), name='editorial_create'),
    path('editoriales/<int:pk>/editar/', views.EditorialUpdateView.as_view(), name='editorial_update'),

    path('libros/', views.LibroListView.as_view(), name='libro_list'),
    path('libros/nuevo/', views.LibroCreateView.as_view(), name='libro_create'),
    path('libros/<int:pk>/', views.LibroDetailView.as_view(), name='libro_detail'),
    path('libros/<int:pk>/editar/', views.LibroUpdateView.as_view(), name='libro_update'),

    path('ejemplares/', views.EjemplarListView.as_view(), name='ejemplar_list'),
    path('ejemplares/nuevo/', views.EjemplarCreateView.as_view(), name='ejemplar_create'),
    path('ejemplares/<int:pk>/', views.EjemplarDetailView.as_view(), name='ejemplar_detail'),
    path('ejemplares/<int:pk>/editar/', views.EjemplarUpdateView.as_view(), name='ejemplar_update'),
]