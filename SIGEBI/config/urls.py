from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from cuentas.forms import CorreoAuthenticationForm

urlpatterns = [
    path('admin/', admin.site.urls),
    path(
        'accounts/login/',
        auth_views.LoginView.as_view(
            template_name='registration/login.html',
            authentication_form=CorreoAuthenticationForm,
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
    path('', include('biblioteca.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
