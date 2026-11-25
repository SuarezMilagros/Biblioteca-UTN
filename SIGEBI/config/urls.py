from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.static import serve

from cuentas.forms import CorreoAuthenticationForm, LimitadoPasswordResetForm


def archivo_publico(request, path):
    """Portadas de los libros (MEDIA_ROOT). Son públicas. Las sirve Django también con DEBUG apagado, porque en
    Railway no hay otro servidor delante: alcanza para la cantidad de visitas de la biblioteca (S8-09).
    Los PDF del material digital y las fotos de perfil NO pasan por acá: están en MATERIAL_DIGITAL_ROOT y se
    entregan solo a quien tiene permiso (biblioteca/almacenamiento.py)."""
    return serve(request, path, document_root=settings.MEDIA_ROOT)


urlpatterns = [
    path('admin/', admin.site.urls),
    path(
        'accounts/login/',
        auth_views.LoginView.as_view(
            template_name='registration/login.html',
            authentication_form=CorreoAuthenticationForm,
            # Si ya inició sesión (por ejemplo, en otra pestaña), no se le vuelve a pedir: va a donde iba.
            redirect_authenticated_user=True,
        ),
        name='login',
    ),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    # Recuperación de contraseña por correo. Cada ruta se declara aparte para no
    # traer el login y el logout que ya existen (ver cuentas/tests/test_recuperacion.py).
    path(
        'accounts/password_reset/',
        auth_views.PasswordResetView.as_view(
            email_template_name='registration/password_reset_email.txt',
            form_class=LimitadoPasswordResetForm,
        ),
        name='password_reset',
    ),
    path(
        'accounts/password_reset/done/',
        auth_views.PasswordResetDoneView.as_view(),
        name='password_reset_done',
    ),
    path(
        'accounts/reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(),
        name='password_reset_confirm',
    ),
    path(
        'accounts/reset/done/',
        auth_views.PasswordResetCompleteView.as_view(),
        name='password_reset_complete',
    ),
    # Cambio de contraseña para quien ya tiene sesión iniciada.
    path(
        'accounts/password_change/',
        auth_views.PasswordChangeView.as_view(),
        name='password_change',
    ),
    path(
        'accounts/password_change/done/',
        auth_views.PasswordChangeDoneView.as_view(),
        name='password_change_done',
    ),
    path('cuentas/', include('cuentas.urls')),
    path('portal/', include('portal.urls')),
    path(f"{settings.MEDIA_URL.lstrip('/')}<path:path>", archivo_publico, name='archivo_publico'),
    path('', include('biblioteca.urls')),
]
