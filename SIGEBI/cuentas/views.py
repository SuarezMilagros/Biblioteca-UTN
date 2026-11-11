"""Alta, listado y edición de cuentas del sistema (Release 1, etapa 5).

Cada vista exige su permiso de Django. Además, el Administrativo solo gestiona
bibliotecarios (ver `puede_gestionar`).
"""
import smtplib

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from .correo import enviar_correo_definicion
from .forms import UsuarioForm
from .roles import ADMINISTRATIVO, BIBLIOTECARIO, es_lector

ROLES_DEL_SISTEMA = [ADMINISTRATIVO, BIBLIOTECARIO]
ERRORES_DE_ENVIO = (smtplib.SMTPException, OSError)


def puede_gestionar(solicitante, usuario):
    """Indica si el solicitante puede ver y editar la cuenta.

    - Cada persona puede editar sus propios datos. Rol y estado quedan bloqueados en el formulario.
    - El superusuario gestiona cualquier cuenta.
    - El Administrativo solo gestiona bibliotecarios: nunca administrativos ni superusuarios.
    - Las cuentas de estudiantes y docentes no se gestionan acá, sino desde la ficha de su persona (S7-03).
    """
    if es_lector(usuario):
        return False
    if usuario.pk == solicitante.pk or solicitante.is_superuser:
        return True
    return not usuario.is_superuser and usuario.groups.filter(name=BIBLIOTECARIO).exists()


def guardar_cuenta(form, guardar):
    """Ejecuta `guardar` y, si la base rechaza un documento o correo repetido, lo marca en el formulario.

    Pasa cuando dos personas dan de alta (o editan) la misma cuenta al mismo tiempo:
    las dos pasan la validación del formulario, pero la base acepta solo la primera
    (CA-A9). En lugar de un error 500, se muestra el error junto al campo.
    Devuelve True si se guardó.
    """
    try:
        with transaction.atomic():
            guardar()
    except IntegrityError:
        Usuario = get_user_model()
        otras = Usuario.objects.exclude(pk=form.instance.pk) if form.instance.pk else Usuario.objects.all()
        if otras.filter(username=form.cleaned_data.get('username')).exists():
            form.add_error('username', 'Ya existe una cuenta con ese documento.')
        elif otras.filter(email__iexact=form.cleaned_data.get('email', '')).exists():
            form.add_error('email', 'Ya existe una cuenta con ese correo.')
        else:
            form.add_error(None, 'No se pudo guardar la cuenta. Revisá los datos e intentá de nuevo.')
        return False
    return True


def asignar_rol(usuario, nombre_rol):
    """Deja a la cuenta con un único rol. Un valor vacío (cuenta propia) no cambia nada."""
    if nombre_rol:
        usuario.groups.set([Group.objects.get(name=nombre_rol)])


class UsuarioListView(PermissionRequiredMixin, ListView):
    permission_required = 'auth.view_user'
    template_name = 'cuentas/usuario_list.html'
    context_object_name = 'usuarios'

    def get_queryset(self):
        cuentas = get_user_model().objects.filter(groups__name__in=ROLES_DEL_SISTEMA).distinct()
        texto = self.request.GET.get('q', '').strip()
        if texto:
            cuentas = cuentas.filter(
                Q(username__icontains=texto)
                | Q(first_name__icontains=texto)
                | Q(last_name__icontains=texto)
                | Q(email__icontains=texto)
            )
        return cuentas.order_by('last_name', 'first_name', 'username')

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        usuarios = list(contexto['usuarios'])
        for usuario in usuarios:
            usuario.puede_editar = puede_gestionar(self.request.user, usuario)
        contexto['usuarios'] = usuarios
        contexto['q'] = self.request.GET.get('q', '').strip()
        return contexto


class UsuarioCreateView(PermissionRequiredMixin, CreateView):
    permission_required = 'auth.add_user'
    model = get_user_model()
    form_class = UsuarioForm
    template_name = 'cuentas/usuario_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['solicitante'] = self.request.user
        return kwargs

    def form_valid(self, form):
        usuario = form.save(commit=False)
        # Nadie escribe ni ve una contraseña: la define la persona desde el correo.
        usuario.set_unusable_password()

        def guardar():
            usuario.save()
            asignar_rol(usuario, form.cleaned_data['rol'])

        if not guardar_cuenta(form, guardar):
            usuario.pk = None
            return self.form_invalid(form)
        try:
            enviar_correo_definicion(self.request, usuario)
        except ERRORES_DE_ENVIO:
            messages.warning(
                self.request,
                'La cuenta se creó, pero no se pudo enviar el correo de definición. '
                'Podés reenviarlo desde la edición de la cuenta.',
            )
        else:
            messages.success(
                self.request,
                f'Cuenta creada. Se envió a {usuario.email} un correo para definir la contraseña.',
            )
        return redirect('cuentas:usuario_list')


class UsuarioUpdateView(PermissionRequiredMixin, UpdateView):
    permission_required = 'auth.change_user'
    model = get_user_model()
    form_class = UsuarioForm
    template_name = 'cuentas/usuario_form.html'
    # Sin este nombre, Django pone la cuenta editada en `user` y tapa al usuario conectado en base.html.
    context_object_name = 'cuenta'

    def get_object(self, queryset=None):
        usuario = super().get_object(queryset)
        if not puede_gestionar(self.request.user, usuario):
            raise PermissionDenied
        return usuario

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['solicitante'] = self.request.user
        return kwargs

    def form_valid(self, form):
        def guardar():
            usuario = form.save()
            asignar_rol(usuario, form.cleaned_data['rol'])

        if not guardar_cuenta(form, guardar):
            return self.form_invalid(form)
        messages.success(self.request, 'Cuenta actualizada.')
        return redirect('cuentas:usuario_list')


class ReenviarDefinicionView(PermissionRequiredMixin, View):
    """Vuelve a enviar el correo de definición a una cuenta que todavía no tiene contraseña."""

    permission_required = 'auth.change_user'
    http_method_names = ['post']

    def post(self, request, pk):
        usuario = get_object_or_404(get_user_model(), pk=pk)
        if not puede_gestionar(request.user, usuario):
            raise PermissionDenied
        if usuario.has_usable_password():
            messages.error(request, 'Esta cuenta ya tiene contraseña. Podés usar "Olvidé mi contraseña".')
        elif not usuario.is_active:
            messages.error(request, 'Activá la cuenta antes de reenviar el correo.')
        elif not usuario.email:
            messages.error(request, 'La cuenta no tiene correo cargado.')
        else:
            try:
                enviar_correo_definicion(request, usuario)
            except ERRORES_DE_ENVIO:
                messages.error(request, 'No se pudo enviar el correo. Intentá de nuevo más tarde.')
            else:
                messages.success(request, 'Correo de definición reenviado.')
        return redirect('cuentas:usuario_update', pk=usuario.pk)
