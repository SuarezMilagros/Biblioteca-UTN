"""Opiniones sobre los libros (Release 2, S8-04, D-R2-29).

- Opina solo quien tuvo el libro prestado: 1 a 5 estrellas y comentario opcional. Una por persona y libro (editable).
- Queda pendiente hasta que el personal la aprueba o la rechaza. Editarla la vuelve a revisión.
- El portal muestra el promedio y las opiniones aprobadas, marcadas como "Lectura verificada".
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from biblioteca import opiniones as reglas
from biblioteca.models import (
    Autor, AvisoPrestamo, Carrera, Categoria, Editorial, Ejemplar, Libro, Opinion, Persona, Prestamo,
)
from cuentas.lectores import crear_cuenta_de_lector
from cuentas.roles import BIBLIOTECARIO
from interfaz.templatetags.interfaz import estrellas

CLAVE = 'clave-de-prueba-123'


class OpinionesTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bibliotecario = get_user_model().objects.create_user(username='31222333', password=CLAVE)
        cls.bibliotecario.groups.add(Group.objects.get(name=BIBLIOTECARIO))
        programacion = Carrera.objects.get(nombre='Tecnicatura Universitaria en Programación')
        informatica = Categoria.objects.create(nombre='Informática')
        informatica.carreras.add(programacion)
        taller = Categoria.objects.create(nombre='Taller')
        taller.carreras.add(Carrera.objects.get(nombre='Ingeniería Mecánica'))
        datos = {'autor': Autor.objects.create(nombre='A', apellido='B'), 'editorial': Editorial.objects.create(nombre='E')}
        cls.python = Libro.objects.create(titulo='Python', categoria=informatica, **datos)
        cls.java = Libro.objects.create(titulo='Java', categoria=informatica, **datos)
        cls.torneria = Libro.objects.create(titulo='Tornería', categoria=taller, **datos)
        cls.py1 = Ejemplar.objects.create(codigo_inventario='PY-1', libro=cls.python)
        cls.py2 = Ejemplar.objects.create(codigo_inventario='PY-2', libro=cls.python)
        cls.py3 = Ejemplar.objects.create(codigo_inventario='PY-3', libro=cls.python)
        cls.tor1 = Ejemplar.objects.create(codigo_inventario='TOR-1', libro=cls.torneria)
        cls.personas, cls.cuentas = [], []
        for numero, (nombre, apellido) in enumerate([('Ana', 'Pérez'), ('Carlos', 'Ruiz'), ('Luis', 'Gómez')]):
            persona = Persona.objects.create(nombre=nombre, apellido=apellido, documento=f'4011122{numero}', tipo='ALUMNO')
            persona.carreras.add(programacion)
            cls.personas.append(persona)
            cls.cuentas.append(crear_cuenta_de_lector(persona, f'{nombre.lower()}@alumnos.example.com'))
        cls.ana, cls.carlos, cls.luis = cls.personas
        cls.cuenta_ana, cls.cuenta_carlos, cls.cuenta_luis = cls.cuentas

    def prestar(self, persona, ejemplar, devuelto=True):
        inicio = timezone.localdate() - timedelta(days=20)
        return Prestamo.objects.create(
            persona=persona, ejemplar=ejemplar, usuario_sistema=self.bibliotecario,
            fecha_prestamo=inicio, fecha_vencimiento=inicio + timedelta(days=14),
            fecha_devolucion=timezone.localdate() if devuelto else None,
        )

    def opinar(self, cuenta, libro, estrellas='5', comentario='Muy claro'):
        self.client.force_login(cuenta)
        return self.client.post(reverse('portal:opinar', args=[libro.pk]),
                                {'estrellas': estrellas, 'comentario': comentario}, follow=True)

    def opinion(self, persona, libro, estrellas, estado='APROBADA', comentario=''):
        revisada = estado != 'PENDIENTE'
        return Opinion.objects.create(
            persona=persona, libro=libro, estrellas=estrellas, estado=estado, comentario=comentario,
            usuario_revision=self.bibliotecario if revisada else None, fecha_revision=timezone.now() if revisada else None,
        )

    def ver_libro(self, cuenta, libro):
        self.client.force_login(cuenta)
        return self.client.get(reverse('portal:libro', args=[libro.pk]))


class QuienPuedeOpinarTests(OpinionesTestCase):
    def test_criterio_quien_nunca_lo_tuvo_prestado_no_puede_opinar(self):
        respuesta = self.ver_libro(self.cuenta_ana, self.python)
        self.assertFalse(respuesta.context['puede_opinar'])
        self.assertContains(respuesta, 'Vas a poder opinar sobre este libro cuando lo hayas tenido prestado.')
        self.assertNotContains(respuesta, 'name="estrellas"')
        respuesta = self.opinar(self.cuenta_ana, self.python)
        self.assertContains(respuesta, 'Solo pueden opinar quienes tuvieron este libro prestado.')
        self.assertFalse(Opinion.objects.exists())

    def test_quien_lo_tuvo_prestado_opina_y_queda_pendiente(self):
        self.prestar(self.ana, self.py2)
        respuesta = self.opinar(self.cuenta_ana, self.python, '4', '  Me sirvió para el parcial.  ')
        self.assertContains(respuesta, 'Gracias por tu opinión. Se publica cuando la revise la biblioteca.')
        opinion = Opinion.objects.get()
        self.assertEqual((opinion.persona, opinion.libro, opinion.estrellas, opinion.comentario, opinion.estado),
                         (self.ana, self.python, 4, 'Me sirvió para el parcial.', 'PENDIENTE'))
        self.assertContains(respuesta, 'En revisión')

    def test_un_prestamo_sin_devolver_tambien_cuenta(self):
        self.prestar(self.ana, self.py1, devuelto=False)
        self.opinar(self.cuenta_ana, self.python)
        self.assertEqual(Opinion.objects.count(), 1)

    def test_haber_tenido_otro_libro_no_alcanza(self):
        self.prestar(self.ana, self.tor1)
        self.opinar(self.cuenta_ana, self.python)
        self.assertFalse(Opinion.objects.exists())

    def test_el_comentario_es_opcional(self):
        self.prestar(self.ana, self.py1)
        self.opinar(self.cuenta_ana, self.python, '3', '')
        self.assertEqual(Opinion.objects.get().comentario, '')

    def test_estrellas_invalidas(self):
        self.prestar(self.ana, self.py1)
        for valor in ('0', '6', 'abc', ''):
            with self.subTest(valor=valor):
                respuesta = self.opinar(self.cuenta_ana, self.python, valor)
                self.assertContains(respuesta, 'Elegí de 1 a 5 estrellas.')
        self.assertFalse(Opinion.objects.exists())

    def test_comentario_demasiado_largo(self):
        self.prestar(self.ana, self.py1)
        respuesta = self.opinar(self.cuenta_ana, self.python, '5', 'x' * (reglas.MAXIMO_COMENTARIO + 1))
        self.assertContains(respuesta, 'El comentario puede tener hasta 1000 caracteres.')
        self.assertFalse(Opinion.objects.exists())
        self.opinar(self.cuenta_ana, self.python, '5', 'x' * reglas.MAXIMO_COMENTARIO)
        self.assertEqual(Opinion.objects.count(), 1)

    def test_un_libro_de_otra_carrera_responde_404(self):
        self.prestar(self.ana, self.tor1)
        self.client.force_login(self.cuenta_ana)
        respuesta = self.client.post(reverse('portal:opinar', args=[self.torneria.pk]), {'estrellas': '5'})
        self.assertEqual(respuesta.status_code, 404)
        self.assertFalse(Opinion.objects.exists())

    def test_solo_por_post(self):
        self.client.force_login(self.cuenta_ana)
        self.assertEqual(self.client.get(reverse('portal:opinar', args=[self.python.pk])).status_code, 405)

    def test_el_personal_no_opina_desde_el_portal(self):
        self.client.force_login(self.bibliotecario)
        self.assertEqual(self.client.post(reverse('portal:opinar', args=[self.python.pk]), {'estrellas': '5'}).status_code, 403)


class EditarTests(OpinionesTestCase):
    def test_volver_a_opinar_edita_la_misma_y_vuelve_a_revision(self):
        self.prestar(self.ana, self.py1)
        self.opinar(self.cuenta_ana, self.python, '5', 'Excelente')
        opinion = Opinion.objects.get()
        reglas.revisar(opinion, Opinion.Estado.APROBADA, self.bibliotecario)
        respuesta = self.opinar(self.cuenta_ana, self.python, '3', 'Lo releí: le faltan ejercicios')
        opinion.refresh_from_db()
        self.assertEqual(Opinion.objects.count(), 1)
        self.assertEqual((opinion.estrellas, opinion.comentario, opinion.estado), (3, 'Lo releí: le faltan ejercicios', 'PENDIENTE'))
        self.assertIsNone(opinion.usuario_revision)
        self.assertIsNone(opinion.fecha_revision)
        self.assertContains(respuesta, 'Guardar cambios')
        self.assertContains(respuesta, 'Si la editás, vuelve a revisión.')

    def test_el_formulario_trae_su_opinion(self):
        self.prestar(self.ana, self.py1)
        self.opinar(self.cuenta_ana, self.python, '2', 'Regular')
        respuesta = self.ver_libro(self.cuenta_ana, self.python)
        self.assertContains(respuesta, '<input type="radio" name="estrellas" value="2" required checked>', html=True)
        self.assertContains(respuesta, '>Regular</textarea>')

    def test_nunca_ve_como_propia_la_opinion_de_otra_persona(self):
        self.prestar(self.carlos, self.py1)
        self.opinion(self.ana, self.python, 2, estado='PENDIENTE', comentario='Comentario privado de Ana')
        respuesta = self.ver_libro(self.cuenta_carlos, self.python)
        self.assertIsNone(respuesta.context['mi_opinion'])
        self.assertNotContains(respuesta, 'Comentario privado de Ana')
        self.assertContains(respuesta, 'Enviar opinión')

    def test_una_rechazada_se_puede_reenviar(self):
        self.prestar(self.ana, self.py1)
        opinion = self.opinion(self.ana, self.python, 1, estado='RECHAZADA', comentario='Insulto')
        respuesta = self.ver_libro(self.cuenta_ana, self.python)
        self.assertContains(respuesta, 'No se publicó')
        self.opinar(self.cuenta_ana, self.python, '2', 'No me gustó')
        opinion.refresh_from_db()
        self.assertEqual(opinion.estado, 'PENDIENTE')


class PublicacionTests(OpinionesTestCase):
    def test_criterio_solo_se_ve_despues_de_aprobada(self):
        pendiente = self.opinion(self.ana, self.python, 5, estado='PENDIENTE', comentario='Recomendado')
        self.assertNotContains(self.ver_libro(self.cuenta_carlos, self.python), 'Recomendado')
        reglas.revisar(pendiente, Opinion.Estado.APROBADA, self.bibliotecario)
        respuesta = self.ver_libro(self.cuenta_carlos, self.python)
        self.assertContains(respuesta, 'Recomendado')
        self.assertContains(respuesta, 'Lectura verificada')
        self.assertContains(respuesta, '<strong>Ana P.</strong>', html=True)
        self.assertNotContains(respuesta, 'Pérez')

    def test_una_rechazada_no_se_publica(self):
        self.opinion(self.ana, self.python, 1, estado='RECHAZADA', comentario='Fuera de lugar')
        self.assertNotContains(self.ver_libro(self.cuenta_carlos, self.python), 'Fuera de lugar')

    def test_promedio_solo_de_las_aprobadas(self):
        self.opinion(self.ana, self.python, 5)
        self.opinion(self.carlos, self.python, 4)
        self.opinion(self.luis, self.python, 1, estado='PENDIENTE')
        libro = Libro.objects.con_opiniones().get(pk=self.python.pk)
        self.assertEqual((libro.promedio_estrellas, libro.cantidad_opiniones), (4.5, 2))
        respuesta = self.ver_libro(self.cuenta_luis, self.python)
        self.assertContains(respuesta, 'aria-label="4,5 de 5 estrellas, 2 opiniones"')
        self.assertContains(respuesta, '2 opiniones</a>')

    def test_el_promedio_no_se_altera_por_la_cantidad_de_ejemplares(self):
        self.opinion(self.ana, self.python, 5)
        self.opinion(self.carlos, self.python, 2)
        libro = Libro.objects.con_disponibilidad().con_opiniones().get(pk=self.python.pk)
        self.assertEqual((libro.ejemplares_activos, libro.promedio_estrellas, libro.cantidad_opiniones), (3, 3.5, 2))

    def test_el_catalogo_muestra_el_promedio(self):
        self.opinion(self.ana, self.python, 4)
        self.client.force_login(self.cuenta_carlos)
        respuesta = self.client.get(reverse('portal:catalogo'))
        libros = {libro.titulo: libro for libro in respuesta.context['libros']}
        self.assertEqual((libros['Python'].promedio_estrellas, libros['Python'].cantidad_opiniones), (4.0, 1))
        self.assertEqual(libros['Java'].cantidad_opiniones, 0)
        self.assertContains(respuesta, 'aria-label="4 de 5 estrellas, 1 opinión"')

    def test_sin_opiniones(self):
        respuesta = self.ver_libro(self.cuenta_ana, self.java)
        self.assertContains(respuesta, 'Todavía no hay opiniones publicadas sobre este libro.')

    def test_estrellas_en_pantalla(self):
        self.assertEqual(estrellas(None), '')
        self.assertEqual(str(estrellas(4.5, 2)).count('estrella-llena'), 4)
        self.assertEqual(str(estrellas(4.6)).count('estrella-llena'), 5)
        self.assertIn('aria-label="3 de 5 estrellas"', str(estrellas(3)))
        self.assertIn('aria-label="3,7 de 5 estrellas, 1 opinión"', str(estrellas(3.66, 1)))


class RevisionTests(OpinionesTestCase):
    def setUp(self):
        self.client.force_login(self.bibliotecario)

    def test_la_lista_muestra_las_pendientes_de_la_mas_vieja_a_la_mas_nueva(self):
        nueva = self.opinion(self.ana, self.python, 5, estado='PENDIENTE')
        vieja = self.opinion(self.carlos, self.python, 3, estado='PENDIENTE')
        Opinion.objects.filter(pk=vieja.pk).update(fecha_opinion=timezone.now() - timedelta(days=1))
        self.opinion(self.luis, self.python, 4)
        respuesta = self.client.get(reverse('biblioteca:opinion_list'))
        self.assertEqual([o.pk for o in respuesta.context['opiniones']], [vieja.pk, nueva.pk])
        self.assertContains(respuesta, 'Aprobar')
        aprobadas = self.client.get(reverse('biblioteca:opinion_list') + '?estado=aprobadas')
        self.assertEqual([o.persona for o in aprobadas.context['opiniones']], [self.luis])
        self.assertNotContains(aprobadas, 'Aprobar</button>')

    def test_aprobar(self):
        opinion = self.opinion(self.ana, self.python, 5, estado='PENDIENTE')
        respuesta = self.client.post(reverse('biblioteca:opinion_aprobar', args=[opinion.pk]), follow=True)
        opinion.refresh_from_db()
        self.assertEqual((opinion.estado, opinion.usuario_revision), ('APROBADA', self.bibliotecario))
        self.assertIsNotNone(opinion.fecha_revision)
        self.assertContains(respuesta, 'aprobada: ya se ve en el portal.')

    def test_el_resumen_dice_opinion_y_opiniones_bien_escrito(self):
        self.opinion(self.ana, self.python, 5, estado='PENDIENTE')
        self.assertContains(self.client.get(reverse('biblioteca:opinion_list')), '1 opinión</p>')
        self.opinion(self.carlos, self.python, 4, estado='PENDIENTE')
        self.assertContains(self.client.get(reverse('biblioteca:opinion_list')), '2 opiniones</p>')

    def test_rechazar(self):
        opinion = self.opinion(self.ana, self.python, 1, estado='PENDIENTE')
        respuesta = self.client.post(reverse('biblioteca:opinion_rechazar', args=[opinion.pk]), follow=True)
        opinion.refresh_from_db()
        self.assertEqual(opinion.estado, 'RECHAZADA')
        self.assertContains(respuesta, 'rechazada.')

    def test_no_se_revisa_dos_veces(self):
        opinion = self.opinion(self.ana, self.python, 5)
        respuesta = self.client.post(reverse('biblioteca:opinion_rechazar', args=[opinion.pk]), follow=True)
        self.assertContains(respuesta, 'Esta opinión ya fue revisada.')
        opinion.refresh_from_db()
        self.assertEqual(opinion.estado, 'APROBADA')

    def test_menu_con_las_pendientes(self):
        self.opinion(self.ana, self.python, 5, estado='PENDIENTE')
        respuesta = self.client.get(reverse('biblioteca:inicio'))
        self.assertEqual(respuesta.context['opiniones_pendientes_total'], 1)
        self.assertContains(respuesta, f'href="{reverse("biblioteca:opinion_list")}"')

    def test_con_solo_ver_no_revisa(self):
        usuario = get_user_model().objects.create_user(username='consulta', password=CLAVE)
        usuario.user_permissions.add(Permission.objects.get(codename='view_opinion'))
        self.client.force_login(usuario)
        opinion = self.opinion(self.ana, self.python, 5, estado='PENDIENTE')
        self.assertNotContains(self.client.get(reverse('biblioteca:opinion_list')), 'Aprobar</button>')
        self.assertEqual(self.client.post(reverse('biblioteca:opinion_aprobar', args=[opinion.pk])).status_code, 403)

    def test_sin_permiso_es_403_antes_de_buscar_la_opinion(self):
        usuario = get_user_model().objects.create_user(username='sinpermisos', password=CLAVE)
        self.client.force_login(usuario)
        self.assertEqual(self.client.get(reverse('biblioteca:opinion_list')).status_code, 403)
        self.assertEqual(self.client.post(reverse('biblioteca:opinion_aprobar', args=[999])).status_code, 403)
        self.assertNotContains(self.client.get(reverse('biblioteca:inicio')), 'Opiniones')

    def test_un_lector_no_revisa(self):
        opinion = self.opinion(self.carlos, self.python, 5, estado='PENDIENTE')
        self.client.force_login(self.cuenta_ana)
        self.assertEqual(self.client.post(reverse('biblioteca:opinion_aprobar', args=[opinion.pk])).status_code, 403)


class RestriccionesDeLaBaseTests(OpinionesTestCase):
    def test_una_opinion_por_persona_y_libro(self):
        self.opinion(self.ana, self.python, 5)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.opinion(self.ana, self.python, 4)

    def test_estrellas_de_1_a_5(self):
        for valor in (0, 6):
            with self.subTest(valor=valor), self.assertRaises(IntegrityError), transaction.atomic():
                self.opinion(self.ana, self.python, valor)

    def test_el_estado_coincide_con_la_revision(self):
        casos = {
            'aprobada sin revisión': dict(estado='APROBADA'),
            'pendiente con revisión': dict(estado='PENDIENTE', usuario_revision_id=None, fecha_revision=timezone.now()),
        }
        for caso, datos in casos.items():
            with self.subTest(caso=caso), self.assertRaises(IntegrityError), transaction.atomic():
                Opinion.objects.create(persona=self.ana, libro=self.python, estrellas=3, **datos)

    def test_un_prestamo_con_avisos_no_se_borra(self):
        prestamo = self.prestar(self.ana, self.py1, devuelto=False)
        AvisoPrestamo.objects.create(prestamo=prestamo, tipo=AvisoPrestamo.Tipo.VENCIDO)
        with self.assertRaises(ProtectedError):
            prestamo.delete()
