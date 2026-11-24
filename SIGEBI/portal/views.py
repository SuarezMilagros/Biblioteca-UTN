"""Portal de estudiantes y docentes (Release 2).

Todo lo que se muestra acá se filtra en el servidor por la persona de la cuenta y sus carreras (D-R2-12).
"""
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.urls import reverse
from django.views.generic import CreateView, DetailView, ListView, TemplateView

from biblioteca.forms import MaterialCompartidoForm
from biblioteca.fotos import MAXIMO_MB, FotoForm, guardar_foto, quitar_foto
from biblioteca.models import Categoria, Libro, MaterialDigital, Opinion, Persona, Reserva
from biblioteca.opiniones import MAXIMO_COMENTARIO, OpinionNoPermitida, opinar, tuvo_prestado
from biblioteca.revision_de_material import MAXIMO_PENDIENTES_POR_PERSONA, puede_subir
from biblioteca.reservas import (
    HORAS_PARA_RETIRAR, MAXIMO_RESERVAS_ACTIVAS, ReservaNoPermitida, cancelar, motivos_para_no_reservar, reservar,
    vencer_reservas,
)
from biblioteca.fotos import responder_foto
from biblioteca.views import abrir_pdf

from .acceso import LectorRequeridoMixin

LIBROS_POR_PAGINA = 20


def actividad_del_lector(persona, usuario):
    """Préstamos, reservas y material compartido de una persona. Nunca los de otra (D-R2-12).

    Lo usan el Inicio (lo pendiente) y las páginas de Mi biblioteca (Préstamos, Reservas y Material compartido).
    """
    hoy = timezone.localdate()
    prestamos = list(persona.prestamos.select_related('ejemplar__libro').order_by('-fecha_prestamo', '-pk'))
    activos = [prestamo for prestamo in prestamos if prestamo.activo]
    for prestamo in activos:
        # Positivo: faltan días. Cero: vence hoy. Negativo: días de atraso.
        prestamo.dias_restantes = (prestamo.fecha_vencimiento - hoy).days
        prestamo.dias_de_atraso = -prestamo.dias_restantes
    activos.sort(key=lambda prestamo: prestamo.fecha_vencimiento)
    vencer_reservas()
    reservas = list(persona.reservas.select_related('libro', 'ejemplar').order_by('-fecha_reserva', '-pk'))
    return {
        'persona': persona,
        'reservas_activas': [reserva for reserva in reservas if reserva.activa],
        'reservas_anteriores': [reserva for reserva in reservas if not reserva.activa][:10],
        'maximo_reservas': MAXIMO_RESERVAS_ACTIVAS,
        'activos': activos,
        'devueltos': [prestamo for prestamo in prestamos if not prestamo.activo],
        # S8-01: lo que compartió, con el estado de la revisión.
        'materiales_compartidos': list(
            usuario.materiales_subidos.select_related('carrera').order_by('-fecha_carga', '-pk')
        ),
    }


class InicioView(LectorRequeridoMixin, TemplateView):
    """Inicio del portal: primero lo que hay que hacer (retirar, devolver), después buscar y compartir."""

    template_name = 'portal/inicio.html'
    DIAS_PARA_AVISAR = 3

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        actividad = actividad_del_lector(self.persona, self.request.user)
        carreras = self.persona.carreras.all()
        activos = actividad['activos']
        contexto.update({
            'persona': self.persona,
            'carreras': carreras,
            # Un libro pertenece a las carreras de su categoría (D-R2-6).
            'cantidad_libros': Libro.objects.de_las_carreras(carreras).count(),
            'prestamos_sin_devolver': len(activos),
            'vencidos': [prestamo for prestamo in activos if prestamo.dias_restantes < 0],
            'vencen_pronto': [p for p in activos if 0 <= p.dias_restantes <= self.DIAS_PARA_AVISAR],
            'para_retirar': [r for r in actividad['reservas_activas'] if r.estado == Reserva.Estado.CONFIRMADA],
            'reservas_pendientes': [r for r in actividad['reservas_activas'] if r.estado == Reserva.Estado.PENDIENTE],
            'material_en_revision': [
                m for m in actividad['materiales_compartidos'] if m.estado == MaterialDigital.Estado.PENDIENTE
            ],
        })
        contexto['prestamos_vencidos'] = len(contexto['vencidos'])
        contexto['hay_pendientes'] = bool(contexto['vencidos'] or contexto['vencen_pronto'] or contexto['para_retirar'])
        return contexto


class MiBibliotecaView(LectorRequeridoMixin, TemplateView):
    """Páginas de Mi biblioteca: Préstamos (sin devolver e historial), Reservas y Material compartido.

    Reorganización del portal (24/11/2026): la actividad sale de Mi perfil, que queda solo para la cuenta.
    Cada URL elige su plantilla con `template_name`.
    """

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(actividad_del_lector(self.persona, self.request.user))
        contexto['cantidad_compartidos'] = len(contexto['materiales_compartidos'])
        return contexto


class PerfilView(LectorRequeridoMixin, TemplateView):
    """Mi perfil: la cuenta. Sus datos (solo lectura), sus carreras, su foto y el cambio de contraseña."""

    template_name = 'portal/perfil.html'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update({
            'persona': self.persona,
            'carreras': self.persona.carreras.all(),
            'form_foto': FotoForm(),
            'maximo_mb_foto': MAXIMO_MB,
        })
        return contexto


def entero(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


class LibrosDeSusCarrerasMixin(LectorRequeridoMixin):
    """Los libros que puede ver el lector: los de sus carreras, con su disponibilidad (S7-05).

    El filtro está en el servidor: un libro de otra carrera no aparece ni se puede abrir con la dirección (D-R2-12).
    """

    def libros_visibles(self):
        return (
            Libro.objects.de_las_carreras(self.persona.carreras.all())
            .con_disponibilidad()
            .con_opiniones()
            .select_related('autor', 'editorial', 'categoria')
        )


class CatalogoView(LibrosDeSusCarrerasMixin, ListView):
    template_name = 'portal/catalogo.html'
    context_object_name = 'libros'
    paginate_by = LIBROS_POR_PAGINA

    def filtros(self):
        """Carrera y categoría elegidas. Si no son del lector (o no existen), se ignoran."""
        carreras = self.persona.carreras.all()
        categorias = Categoria.objects.filter(carreras__in=carreras).distinct().order_by('nombre')
        carrera = carreras.filter(pk=entero(self.request.GET.get('carrera'))).first()
        categoria = categorias.filter(pk=entero(self.request.GET.get('categoria'))).first()
        return carreras, categorias, carrera, categoria

    def get_queryset(self):
        _, _, carrera, categoria = self.filtros()
        libros = self.libros_visibles()
        if carrera:
            libros = libros.filter(categoria__carreras=carrera)
        if categoria:
            libros = libros.filter(categoria=categoria)
        q = self.request.GET.get('q', '').strip()
        if q:
            isbn = ''.join(c for c in q if c.isalnum())
            # unaccent (PostgreSQL): "calculo" también encuentra "Cálculo".
            busqueda = (
                Q(titulo__unaccent__icontains=q)
                | Q(autor__apellido__unaccent__icontains=q)
                | Q(autor__nombre__unaccent__icontains=q)
            )
            if isbn:
                busqueda |= Q(isbn__icontains=isbn)
            libros = libros.filter(busqueda)
        return libros.order_by('titulo', 'pk')

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        carreras, categorias, carrera, categoria = self.filtros()
        contexto.update({
            'carreras': carreras,
            'categorias': categorias,
            'carrera_elegida': carrera,
            'categoria_elegida': categoria,
            'q': self.request.GET.get('q', '').strip(),
        })
        contexto['hay_filtros'] = bool(contexto['q'] or carrera or categoria)
        return contexto


class LibroView(LibrosDeSusCarrerasMixin, DetailView):
    template_name = 'portal/libro.html'
    context_object_name = 'libro'

    def get_queryset(self):
        # Un libro de otra carrera responde 404, aunque se escriba la dirección a mano.
        return self.libros_visibles()

    def get_context_data(self, **kwargs):
        vencer_reservas()
        contexto = super().get_context_data(**kwargs)
        contexto['reserva_activa'] = self.persona.reservas.filter(
            libro=self.object, estado__in=Reserva.ACTIVAS
        ).first()
        contexto['motivos_para_no_reservar'] = motivos_para_no_reservar(self.persona, self.object)
        contexto['horas_para_retirar'] = HORAS_PARA_RETIRAR
        # S8-04: opiniones aprobadas de todos, y la propia en cualquier estado.
        contexto['opiniones'] = (
            self.object.opiniones.filter(estado=Opinion.Estado.APROBADA)
            .select_related('persona').order_by('-fecha_opinion', '-pk')
        )
        contexto['mi_opinion'] = self.object.opiniones.filter(persona=self.persona).first()
        contexto['puede_opinar'] = tuvo_prestado(self.persona, self.object)
        contexto['maximo_comentario'] = MAXIMO_COMENTARIO
        return contexto


class OpinarView(LibrosDeSusCarrerasMixin, View):
    """El lector pone estrellas y un comentario a un libro que tuvo prestado (S8-04)."""

    http_method_names = ['post']

    def post(self, request, pk):
        libro = get_object_or_404(self.libros_visibles(), pk=pk)
        try:
            opinar(self.persona, libro, request.POST.get('estrellas'), request.POST.get('comentario'))
        except OpinionNoPermitida as error:
            messages.error(request, error.motivo)
        else:
            messages.success(request, 'Gracias por tu opinión. Se publica cuando la revise la biblioteca.')
        return redirect(reverse('portal:libro', args=[libro.pk]) + '#opiniones')


class ReservarView(LibrosDeSusCarrerasMixin, View):
    """El lector reserva un libro de sus carreras (S8-02). Las reglas están en biblioteca/reservas.py."""

    http_method_names = ['post']

    def post(self, request, pk):
        libro = get_object_or_404(self.libros_visibles(), pk=pk)
        try:
            reservar(self.persona, libro)
        except ReservaNoPermitida as error:
            for motivo in error.motivos:
                messages.error(request, motivo)
        else:
            messages.success(
                request,
                f'Reservaste "{libro}". Cuando la biblioteca la confirme, vas a tener '
                f'{HORAS_PARA_RETIRAR} horas para retirarlo.',
            )
        return redirect('portal:libro', pk=libro.pk)


class CancelarReservaView(LectorRequeridoMixin, View):
    """El lector cancela una de sus reservas, mientras siga pendiente."""

    http_method_names = ['post']

    def post(self, request, pk):
        reserva = get_object_or_404(self.persona.reservas, pk=pk)
        try:
            cancelar(reserva)
        except ReservaNoPermitida as error:
            messages.error(request, error.motivos[0])
        else:
            messages.success(request, f'Cancelaste la reserva de "{reserva.libro}".')
        return redirect('portal:mis_reservas')


class MaterialDeSusCarrerasMixin(LectorRequeridoMixin):
    """Material que puede ver el lector: aprobado, activo y de sus carreras (D-R2-12)."""

    def material_visible(self):
        return MaterialDigital.objects.filter(
            carrera__in=self.persona.carreras.all(),
            estado=MaterialDigital.Estado.APROBADO,
            activo=True,
        )


class MaterialView(MaterialDeSusCarrerasMixin, ListView):
    template_name = 'portal/material.html'
    context_object_name = 'materiales'
    paginate_by = LIBROS_POR_PAGINA

    def get_queryset(self):
        materiales = self.material_visible().select_related('carrera')
        carrera = self.persona.carreras.filter(pk=entero(self.request.GET.get('carrera'))).first()
        if carrera:
            materiales = materiales.filter(carrera=carrera)
        tipo = self.request.GET.get('tipo', '')
        if tipo in MaterialDigital.Tipo.values:
            materiales = materiales.filter(tipo=tipo)
        q = self.request.GET.get('q', '').strip()
        if q:
            materiales = materiales.filter(Q(titulo__unaccent__icontains=q) | Q(autores__unaccent__icontains=q))
        return materiales.order_by('titulo', 'pk')

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        carreras = self.persona.carreras.all()
        carrera = carreras.filter(pk=entero(self.request.GET.get('carrera'))).first()
        tipo = self.request.GET.get('tipo', '')
        contexto.update({
            'carreras': carreras,
            'carrera_elegida': carrera,
            'tipos': MaterialDigital.Tipo.choices,
            'tipo_elegido': tipo if tipo in MaterialDigital.Tipo.values else '',
            'cantidad_compartidos': self.request.user.materiales_subidos.count(),
            'q': self.request.GET.get('q', '').strip(),
        })
        contexto['hay_filtros'] = bool(contexto['q'] or carrera or contexto['tipo_elegido'])
        return contexto


class MaterialArchivoView(MaterialDeSusCarrerasMixin, View):
    """Abre el PDF. Material de otra carrera, pendiente o dado de baja: 404, aunque se escriba la dirección.

    Excepción (S8-01): quien subió un material siempre puede abrir el suyo, aunque esté pendiente o rechazado.
    """

    def get(self, request, pk):
        propios = MaterialDigital.objects.filter(usuario_carga=request.user)
        return abrir_pdf(get_object_or_404(self.material_visible() | propios, pk=pk))


class CompartirMaterialView(LectorRequeridoMixin, CreateView):
    """Un alumno o profesor sube material para sus carreras (S8-01). Queda pendiente hasta que la
    biblioteca lo revise; mientras tanto no lo ve nadie más."""

    form_class = MaterialCompartidoForm
    template_name = 'portal/material_compartir.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['persona'] = self.persona
        return kwargs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['puede_subir'] = puede_subir(self.request.user)
        contexto['maximo_pendientes'] = MAXIMO_PENDIENTES_POR_PERSONA
        contexto['tiene_carreras'] = self.persona.carreras.exists()
        return contexto

    def form_valid(self, form):
        with transaction.atomic():
            # Se bloquea la persona para que dos cargas simultáneas no pasen el máximo de pendientes.
            Persona.objects.select_for_update().get(pk=self.persona.pk)
            if not puede_subir(self.request.user):
                messages.error(
                    self.request,
                    f'Ya tenés {MAXIMO_PENDIENTES_POR_PERSONA} materiales esperando revisión. '
                    'Cuando la biblioteca los revise, vas a poder subir más.',
                )
                return self.form_invalid(form)
            material = form.save(commit=False)
            material.usuario_carga = self.request.user
            material.estado = MaterialDigital.Estado.PENDIENTE
            material.fecha_carga = timezone.now()
            material.save()
        messages.success(
            self.request,
            f'Recibimos "{material.titulo}". La biblioteca lo va a revisar antes de publicarlo; '
            'te avisamos por correo.',
        )
        return redirect('portal:mi_material')


class FotoView(LectorRequeridoMixin, View):
    """Sube o reemplaza la foto de perfil (pedido de la profesora)."""

    http_method_names = ['post']

    def post(self, request):
        form = FotoForm(request.POST, request.FILES)
        if form.is_valid():
            guardar_foto(self.persona, form.cleaned_data['foto'])
            messages.success(request, 'Actualizaste tu foto de perfil.')
        else:
            for error in form.errors.get('foto', []):
                messages.error(request, error)
        return redirect('portal:perfil')


class MiFotoView(LectorRequeridoMixin, View):
    """El lector ve su propia foto. Nunca la de otra persona: sale de la persona de su cuenta."""

    def get(self, request):
        return responder_foto(self.persona)


class QuitarFotoView(LectorRequeridoMixin, View):
    http_method_names = ['post']

    def post(self, request):
        quitar_foto(self.persona)
        messages.success(request, 'Quitaste tu foto de perfil.')
        return redirect('portal:perfil')
