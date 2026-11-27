"""Eliminar personas, libros, autores, editoriales, categorías y carreras, y dar de baja un libro (D-R2-30).

Regla: se elimina solo lo que no tiene historial ni está en uso; lo que tiene historial se da de baja.
"""
import os
import shutil
import tempfile
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from biblioteca import views
from biblioteca.models import (
    Autor, Carrera, Categoria, CategoriaCarrera, Editorial, Ejemplar, Libro, Opinion, Persona, Prestamo, Reserva,
)
from cuentas.lectores import crear_cuenta_de_lector
from cuentas.roles import ADMINISTRATIVO, BIBLIOTECARIO, MODELOS_QUE_SE_ELIMINAN


class EliminarTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.carpeta = tempfile.mkdtemp(prefix='eliminar-prueba-')
        cls.ajustes = override_settings(MEDIA_ROOT=cls.carpeta, MATERIAL_DIGITAL_ROOT=cls.carpeta)
        cls.ajustes.enable()

    @classmethod
    def tearDownClass(cls):
        cls.ajustes.disable()
        shutil.rmtree(cls.carpeta, ignore_errors=True)
        super().tearDownClass()

    @classmethod
    def setUpTestData(cls):
        cls.bibliotecaria = get_user_model().objects.create_user(username='20999888', email='ana@example.com')
        cls.bibliotecaria.groups.add(Group.objects.get(name=BIBLIOTECARIO))
        cls.carrera = Carrera.objects.order_by('pk').first()
        cls.categoria = Categoria.objects.create(nombre='Informática')
        cls.categoria.carreras.add(cls.carrera)
        cls.autor = Autor.objects.create(nombre='Andrew S.', apellido='Tanenbaum')
        cls.editorial = Editorial.objects.create(nombre='Pearson')
        cls.libro = Libro.objects.create(titulo='Sistemas operativos', categoria=cls.categoria, autor=cls.autor,
                                         editorial=cls.editorial)
        cls.ejemplar_1 = Ejemplar.objects.create(libro=cls.libro, codigo_inventario='25609')
        cls.ejemplar_2 = Ejemplar.objects.create(libro=cls.libro, codigo_inventario='25610')
        cls.persona = Persona.objects.create(nombre='Rosa', apellido='Medina', documento='41222333', tipo='ALUMNO')
        cls.persona.carreras.add(cls.carrera)

    def setUp(self):
        self.client.force_login(self.bibliotecaria)

    def prestar(self, ejemplar=None, devuelto=False):
        hoy = timezone.localdate()
        return Prestamo.objects.create(
            ejemplar=ejemplar or self.ejemplar_1, persona=self.persona, usuario_sistema=self.bibliotecaria,
            fecha_prestamo=hoy - timedelta(days=3), fecha_vencimiento=hoy + timedelta(days=11),
            fecha_devolucion=hoy if devuelto else None)

    def eliminar(self, clave, objeto, **kwargs):
        return self.client.post(reverse(f'biblioteca:{clave}_eliminar', args=[objeto.pk]), **kwargs)

    def mensajes(self, respuesta):
        return [str(m) for m in respuesta.context['messages']]


class EliminarPersonaTests(EliminarTestCase):
    def test_sin_historial_se_elimina_con_su_cuenta_del_portal(self):
        cuenta = crear_cuenta_de_lector(self.persona, 'rosa@alumnos.example.com')
        ficha = self.client.get(reverse('biblioteca:persona_detail', args=[self.persona.pk])).content.decode()
        self.assertIn(f'action="{reverse("biblioteca:persona_eliminar", args=[self.persona.pk])}"', ficha)
        self.assertIn('Se elimina la persona y, si tiene, su cuenta del portal.', ficha)

        respuesta = self.eliminar('persona', self.persona, follow=True)

        self.assertRedirects(respuesta, reverse('biblioteca:persona_list'))
        self.assertIn('Se eliminó «Medina, Rosa».', self.mensajes(respuesta))
        self.assertFalse(Persona.objects.filter(pk=self.persona.pk).exists())
        self.assertFalse(get_user_model().objects.filter(pk=cuenta.pk).exists())
        self.assertTrue(get_user_model().objects.filter(pk=self.bibliotecaria.pk).exists())

    def test_con_historial_no_se_elimina_y_se_sugiere_la_baja(self):
        self.prestar(devuelto=True)
        Reserva.objects.create(persona=self.persona, libro=self.libro)
        ficha = self.client.get(reverse('biblioteca:persona_detail', args=[self.persona.pk])).content.decode()
        self.assertIn('No se puede eliminar: tiene 1 préstamo y 1 reserva.', ficha)
        self.assertNotIn(f'action="{reverse("biblioteca:persona_eliminar", args=[self.persona.pk])}"', ficha)

        respuesta = self.eliminar('persona', self.persona, follow=True)

        self.assertRedirects(respuesta, reverse('biblioteca:persona_detail', args=[self.persona.pk]))
        self.assertIn('No se puede eliminar «Medina, Rosa»: tiene 1 préstamo y 1 reserva. Podés darla de baja: '
                      'no recibe préstamos nuevos y conserva su historial.', self.mensajes(respuesta))
        self.assertTrue(Persona.objects.filter(pk=self.persona.pk).exists())

    def test_si_el_historial_aparece_justo_antes_la_base_lo_protege(self):
        # Entre que se mostró la ficha y se confirmó, alguien registró un préstamo: la base no deja borrar.
        self.prestar()
        sin_controles = {**views.REGLAS_PARA_ELIMINAR['persona'], 'impedimentos': lambda persona: []}
        with mock.patch.dict(views.REGLAS_PARA_ELIMINAR, {'persona': sin_controles}):
            respuesta = self.eliminar('persona', self.persona, follow=True)
        self.assertIn('No se puede eliminar «Medina, Rosa»: tiene datos que dependen de este registro.',
                      self.mensajes(respuesta)[0])
        self.assertTrue(Persona.objects.filter(pk=self.persona.pk).exists())


class EliminarLibroTests(EliminarTestCase):
    def test_sin_historial_se_elimina_con_sus_ejemplares_y_su_portada(self):
        self.libro.imagen = SimpleUploadedFile('tapa.png', b'\x89PNG\r\n\x1a\n', content_type='image/png')
        self.libro.save()
        portada = os.path.join(self.carpeta, self.libro.imagen.name)
        self.assertTrue(os.path.exists(portada))

        with self.captureOnCommitCallbacks(execute=True):
            respuesta = self.eliminar('libro', self.libro, follow=True)

        self.assertRedirects(respuesta, reverse('biblioteca:libro_list'))
        self.assertFalse(Libro.objects.filter(pk=self.libro.pk).exists())
        self.assertFalse(Ejemplar.objects.filter(libro_id=self.libro.pk).exists())
        self.assertFalse(os.path.exists(portada))
        # El autor, la editorial y la categoría quedan.
        self.assertTrue(Autor.objects.filter(pk=self.autor.pk).exists())

    def test_con_historial_no_se_elimina(self):
        self.prestar(self.ejemplar_2, devuelto=True)
        Opinion.objects.create(persona=self.persona, libro=self.libro, estrellas=4)
        ficha = self.client.get(reverse('biblioteca:libro_detail', args=[self.libro.pk])).content.decode()
        self.assertIn('No se puede eliminar: tiene 1 préstamo y 1 opinión. Podés darlo de baja', ficha)
        respuesta = self.eliminar('libro', self.libro, follow=True)
        self.assertIn('No se puede eliminar «Sistemas operativos»: tiene 1 préstamo y 1 opinión.',
                      self.mensajes(respuesta)[0])
        self.assertEqual(Ejemplar.objects.filter(libro=self.libro).count(), 2)


class DarDeBajaLibroTests(EliminarTestCase):
    def dar_de_baja(self, motivo='DESCARTE'):
        return self.client.post(reverse('biblioteca:libro_baja', args=[self.libro.pk]), {'motivo_baja': motivo},
                                follow=True)

    def test_da_de_baja_todos_los_ejemplares_y_deja_de_verse_en_el_portal(self):
        perdido = Ejemplar.objects.create(libro=self.libro, codigo_inventario='25611', activo=False,
                                          motivo_baja='PERDIDO', fecha_baja=timezone.localdate() - timedelta(days=90))
        lector = crear_cuenta_de_lector(self.persona, 'rosa@alumnos.example.com')
        self.client.force_login(lector)
        self.assertContains(self.client.get(reverse('portal:catalogo')), 'Sistemas operativos')
        self.client.force_login(self.bibliotecaria)

        respuesta = self.dar_de_baja()

        self.assertIn('«Sistemas operativos» quedó dado de baja: 2 ejemplares dados de baja. Ya no se ve en el portal.',
                      self.mensajes(respuesta))
        self.assertContains(respuesta, 'Dado de baja')
        self.assertContains(respuesta, 'Reactivar libro')
        hoy = timezone.localdate()
        for ejemplar in (self.ejemplar_1, self.ejemplar_2):
            ejemplar.refresh_from_db()
            self.assertEqual((ejemplar.activo, ejemplar.motivo_baja, ejemplar.fecha_baja), (False, 'DESCARTE', hoy))
        perdido.refresh_from_db()
        self.assertEqual(perdido.motivo_baja, 'PERDIDO')
        # El historial queda y el libro no se ve ni se abre en el portal.
        self.assertTrue(Libro.objects.filter(pk=self.libro.pk).exists())
        self.client.force_login(lector)
        self.assertNotContains(self.client.get(reverse('portal:catalogo')), 'Sistemas operativos')
        self.assertEqual(self.client.get(reverse('portal:libro', args=[self.libro.pk])).status_code, 404)

        # Reactivar vuelve a habilitar los de esta baja; el que estaba perdido de antes sigue dado de baja.
        self.client.force_login(self.bibliotecaria)
        respuesta = self.client.post(reverse('biblioteca:libro_reactivar', args=[self.libro.pk]), follow=True)
        self.assertIn('«Sistemas operativos» volvió a estar activo: 2 ejemplares habilitados.', self.mensajes(respuesta))
        self.assertEqual(set(Ejemplar.objects.filter(libro=self.libro, activo=True)), {self.ejemplar_1, self.ejemplar_2})
        perdido.refresh_from_db()
        self.assertFalse(perdido.activo)

    def test_no_se_da_de_baja_con_un_ejemplar_prestado_o_una_reserva_activa(self):
        self.prestar()
        Reserva.objects.create(persona=self.persona, libro=self.libro)
        ficha = self.client.get(reverse('biblioteca:libro_detail', args=[self.libro.pk])).content.decode()
        self.assertIn('No se puede dar de baja: tiene 1 ejemplar prestado y 1 reserva pendiente o confirmada.', ficha)
        self.assertNotIn(f'action="{reverse("biblioteca:libro_baja", args=[self.libro.pk])}"', ficha)
        respuesta = self.dar_de_baja()
        self.assertIn('No se puede dar de baja «Sistemas operativos»: 1 ejemplar prestado y 1 reserva pendiente o '
                      'confirmada.', self.mensajes(respuesta)[0])
        self.assertEqual(Ejemplar.objects.filter(libro=self.libro, activo=True).count(), 2)

    def test_hay_que_elegir_el_motivo(self):
        respuesta = self.dar_de_baja(motivo='')
        self.assertIn('Elegí el motivo de la baja.', self.mensajes(respuesta))
        self.assertEqual(Ejemplar.objects.filter(libro=self.libro, activo=True).count(), 2)

    def test_un_libro_sin_ejemplares_no_esta_dado_de_baja(self):
        libro = Libro.objects.create(titulo='Redes', categoria=self.categoria, autor=self.autor, editorial=self.editorial)
        respuesta = self.client.get(reverse('biblioteca:libro_detail', args=[libro.pk]))
        self.assertNotContains(respuesta, 'Dado de baja')
        self.assertNotContains(respuesta, 'Dar de baja el libro')
        self.assertEqual(
            self.client.post(reverse('biblioteca:libro_reactivar', args=[libro.pk])).status_code, 302)


class EliminarDatosDelCatalogoTests(EliminarTestCase):
    def test_autor_editorial_y_categoria_en_uso_no_se_eliminan(self):
        for clave, objeto in (('autor', self.autor), ('editorial', self.editorial), ('categoria', self.categoria)):
            with self.subTest(clave):
                pagina = self.client.get(reverse(f'biblioteca:{clave}_update', args=[objeto.pk])).content.decode()
                self.assertIn('No se puede eliminar: tiene 1 libro.', pagina)
                respuesta = self.eliminar(clave, objeto, follow=True)
                self.assertRedirects(respuesta, reverse(f'biblioteca:{clave}_update', args=[objeto.pk]))
                self.assertTrue(type(objeto).objects.filter(pk=objeto.pk).exists())

    def test_autor_editorial_y_categoria_sin_libros_se_eliminan(self):
        sin_uso = [
            ('autor', Autor.objects.create(nombre='Ana', apellido='Ruiz'), 'biblioteca:autor_list'),
            ('editorial', Editorial.objects.create(nombre='Norte'), 'biblioteca:editorial_list'),
            ('categoria', Categoria.objects.create(nombre='Química'), 'biblioteca:categoria_list'),
        ]
        sin_uso[2][1].carreras.add(self.carrera)
        for clave, objeto, lista in sin_uso:
            with self.subTest(clave):
                pagina = self.client.get(reverse(f'biblioteca:{clave}_update', args=[objeto.pk])).content.decode()
                self.assertIn(f'action="{reverse(f"biblioteca:{clave}_eliminar", args=[objeto.pk])}"', pagina)
                self.assertRedirects(self.eliminar(clave, objeto), reverse(lista))
                self.assertFalse(type(objeto).objects.filter(pk=objeto.pk).exists())
        # La categoría se fue con su relación con la carrera; la carrera queda.
        self.assertFalse(CategoriaCarrera.objects.filter(categoria_id=sin_uso[2][1].pk).exists())
        self.assertTrue(Carrera.objects.filter(pk=self.carrera.pk).exists())

    def test_carrera_en_uso_no_se_elimina_y_sin_uso_si(self):
        ficha = self.client.get(reverse('biblioteca:carrera_detail', args=[self.carrera.pk])).content.decode()
        self.assertIn('No se puede eliminar: tiene 1 persona y 1 categoría.', ficha)
        self.eliminar('carrera', self.carrera)
        self.assertTrue(Carrera.objects.filter(pk=self.carrera.pk).exists())

        nueva = Carrera.objects.create(nombre='Tecnicatura en Prueba', nivel=self.carrera.nivel)
        self.assertRedirects(self.eliminar('carrera', nueva), reverse('biblioteca:carrera_list'))
        self.assertFalse(Carrera.objects.filter(pk=nueva.pk).exists())


class QuienPuedeEliminarTests(EliminarTestCase):
    def urls(self):
        return [
            reverse('biblioteca:persona_eliminar', args=[self.persona.pk]),
            reverse('biblioteca:libro_eliminar', args=[self.libro.pk]),
            reverse('biblioteca:libro_baja', args=[self.libro.pk]),
            reverse('biblioteca:libro_reactivar', args=[self.libro.pk]),
            reverse('biblioteca:autor_eliminar', args=[self.autor.pk]),
            reverse('biblioteca:editorial_eliminar', args=[self.editorial.pk]),
            reverse('biblioteca:categoria_eliminar', args=[self.categoria.pk]),
            reverse('biblioteca:carrera_eliminar', args=[self.carrera.pk]),
        ]

    def test_los_roles_del_personal_pueden_eliminar_solo_lo_previsto(self):
        for rol in (BIBLIOTECARIO, ADMINISTRATIVO):
            permisos = set(Group.objects.get(name=rol).permissions.values_list('codename', flat=True))
            for modelo in MODELOS_QUE_SE_ELIMINAN:
                self.assertIn(f'delete_{modelo}', permisos)
            for modelo in ('ejemplar', 'prestamo', 'reserva', 'opinion', 'materialdigital'):
                self.assertNotIn(f'delete_{modelo}', permisos)

    def test_un_lector_no_puede_y_eliminar_solo_acepta_post(self):
        self.assertEqual(self.client.get(self.urls()[0]).status_code, 405)
        self.client.force_login(crear_cuenta_de_lector(self.persona, 'rosa@alumnos.example.com'))
        for url in self.urls():
            with self.subTest(url):
                self.assertEqual(self.client.post(url, {'motivo_baja': 'DESCARTE'}).status_code, 403)
        self.assertEqual(Persona.objects.count(), 1)
        self.assertEqual(Ejemplar.objects.filter(activo=True).count(), 2)

    def test_sin_permiso_de_eliminar_no_ve_la_seccion(self):
        usuario = get_user_model().objects.create_user(username='solo-edita', email='edita@example.com')
        usuario.user_permissions.add(*Permission.objects.filter(
            codename__in=['view_persona', 'view_libro', 'change_autor', 'view_carrera']))
        self.client.force_login(usuario)
        paginas = [
            reverse('biblioteca:persona_detail', args=[self.persona.pk]),
            reverse('biblioteca:libro_detail', args=[self.libro.pk]),
            reverse('biblioteca:autor_update', args=[self.autor.pk]),
            reverse('biblioteca:carrera_detail', args=[self.carrera.pk]),
        ]
        for pagina in paginas:
            with self.subTest(pagina):
                contenido = self.client.get(pagina).content.decode()
                self.assertNotIn('id="titulo-eliminar"', contenido)
                self.assertNotIn('Dar de baja el libro', contenido)
        self.assertEqual(self.eliminar('autor', Autor.objects.create(nombre='X', apellido='Y')).status_code, 403)
