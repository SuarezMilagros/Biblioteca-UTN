from django.urls import path

from . import views

app_name = 'biblioteca'

urlpatterns = [
    path('', views.inicio, name='inicio'),
    path('informes/', views.InformesView.as_view(), name='informes'),

    path('categorias/', views.CategoriaListView.as_view(), name='categoria_list'),
    path('categorias/nueva/', views.CategoriaCreateView.as_view(), name='categoria_create'),
    path('categorias/<int:pk>/editar/', views.CategoriaUpdateView.as_view(), name='categoria_update'),

    path('carreras/', views.CarreraListView.as_view(), name='carrera_list'),
    path('carreras/nueva/', views.CarreraCreateView.as_view(), name='carrera_create'),
    path('carreras/<int:pk>/', views.CarreraDetailView.as_view(), name='carrera_detail'),
    path('carreras/<int:pk>/editar/', views.CarreraUpdateView.as_view(), name='carrera_update'),

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
    path('ejemplares/<int:pk>/prestar/', views.PrestamoCreateView.as_view(), name='prestamo_create'),
    path('ejemplares/<int:pk>/baja/', views.EjemplarBajaView.as_view(), name='ejemplar_baja'),
    path('ejemplares/<int:pk>/reactivar/', views.EjemplarReactivarView.as_view(), name='ejemplar_reactivar'),

    path('personas/', views.PersonaListView.as_view(), name='persona_list'),
    path('personas/nueva/', views.PersonaCreateView.as_view(), name='persona_create'),
    path('personas/<int:pk>/', views.PersonaDetailView.as_view(), name='persona_detail'),
    path('personas/<int:pk>/editar/', views.PersonaUpdateView.as_view(), name='persona_update'),
    path('personas/<int:pk>/baja/', views.PersonaBajaView.as_view(), name='persona_baja'),
    path('personas/<int:pk>/reactivar/', views.PersonaReactivarView.as_view(), name='persona_reactivar'),

    path('prestamos/', views.PrestamoListView.as_view(), name='prestamo_list'),
    path('prestamos/<int:pk>/devolver/', views.DevolucionView.as_view(), name='prestamo_devolver'),
]