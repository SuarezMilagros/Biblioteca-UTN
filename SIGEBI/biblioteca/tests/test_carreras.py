"""Carreras y sus vínculos con personas y categorías (Release 2, S7-02).

- Las 10 carreras de la Extensión Áulica se cargan con una migración.
- El nombre de una carrera no se repite (sin distinguir mayúsculas).
- Una persona y una categoría pueden tener varias carreras.
- Una carrera con datos no se puede borrar.
- Un aviso muestra las categorías sin carrera, porque sus libros no se verían en el portal.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase
from django.urls import reverse

from biblioteca.models import Carrera, Categoria, Persona
from cuentas.roles import BIBLIOTECARIO

CLAVE = 'clave-de-prueba-123'
PROGRAMACION = 'Tecnicatura Universitaria en Programación'
SISTEMAS = 'Ingeniería en Sistemas de Información'


class CarrerasTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(
            username='31222333', email='bibliotecario@example.com', password=CLAVE
        )
        cls.usuario.groups.add(Group.objects.get(name=BIBLIOTECARIO))
        cls.programacion = Carrera.objects.get(nombre=PROGRAMACION)
        cls.sistemas = Carrera.objects.get(nombre=SISTEMAS)
        cls.persona = Persona.objects.create(
            nombre='Ana', apellido='Pérez', documento='40111222', tipo=Persona.Tipo.ALUMNO
        )
        cls.categoria = Categoria.objects.create(nombre='Informática')

    def setUp(self):
        self.client.force_login(self.usuario)


class CarrerasCargadasTests(CarrerasTestCase):
    def test_la_migracion_carga_las_10_carreras_de_la_extension(self):
        self.assertEqual(Carrera.objects.count(), 10)
        self.assertEqual(Carrera.objects.filter(nivel=Carrera.Nivel.PREGRADO).count(), 7)
        self.assertEqual(
            set(Carrera.objects.filter(nivel=Carrera.Nivel.GRADO).values_list('nombre', flat=True)),
            {SISTEMAS, 'Ingeniería Electrónica', 'Ingeniería Mecánica'},
        )

    def test_el_listado_muestra_las_carreras_ordenadas_por_nivel(self):
        respuesta = self.client.get(reverse('biblioteca:carrera_list'))
        nombres = [carrera.nombre for carrera in respuesta.context['object_list']]
        # Primero las 7 de pregrado y después las 3 de grado, cada grupo en orden alfabético.
        # El orden alfabético lo da la base: depende de su configuración regional (en Windows
        # suele ser la del español), así que se compara con el orden de la misma base y no con Python.
        en_orden = [
            *Carrera.objects.filter(nivel=Carrera.Nivel.PREGRADO).order_by('nombre').values_list('nombre', flat=True),
            *Carrera.objects.filter(nivel=Carrera.Nivel.GRADO).order_by('nombre').values_list('nombre', flat=True),
        ]
        self.assertEqual(len(nombres), 10)
        self.assertEqual(nombres, en_orden)
        self.assertContains(respuesta, PROGRAMACION)


class AltaDeCarrerasTests(CarrerasTestCase):
    def test_alta_de_una_carrera(self):
        respuesta = self.client.post(
            reverse('biblioteca:carrera_create'), {'nombre': '  Tecnicatura   en Redes ', 'nivel': 'PREGRADO'}
        )
        carrera = Carrera.objects.get(nombre='Tecnicatura en Redes')
        self.assertRedirects(respuesta, reverse('biblioteca:carrera_detail', args=[carrera.pk]))

    def test_nombre_repetido_sin_distinguir_mayusculas(self):
        respuesta = self.client.post(
            reverse('biblioteca:carrera_create'), {'nombre': PROGRAMACION.upper(), 'nivel': 'PREGRADO'}
        )
        self.assertContains(respuesta, 'Ya existe una carrera con ese nombre.')
        self.assertEqual(Carrera.objects.count(), 10)

    def test_la_base_tambien_rechaza_el_nombre_repetido(self):
        with self.assertRaises(IntegrityError):
            Carrera.objects.create(nombre=PROGRAMACION.lower(), nivel=Carrera.Nivel.PREGRADO)

    def test_editar_una_carrera_conservando_su_nombre(self):
        respuesta = self.client.post(
            reverse('biblioteca:carrera_update', args=[self.sistemas.pk]), {'nombre': SISTEMAS, 'nivel': 'GRADO'}
        )
        self.assertRedirects(respuesta, reverse('biblioteca:carrera_detail', args=[self.sistemas.pk]))


class CarrerasDePersonasYCategoriasTests(CarrerasTestCase):
    def datos_persona(self, **cambios):
        datos = {
            'nombre': 'Ana', 'apellido': 'Pérez', 'documento': '40111222', 'tipo': 'ALUMNO', 'legajo': '',
            'carreras': [self.programacion.pk, self.sistemas.pk],
        }
        datos.update(cambios)
        return datos

    def test_una_persona_puede_tener_varias_carreras(self):
        self.client.post(reverse('biblioteca:persona_update', args=[self.persona.pk]), self.datos_persona())
        self.assertEqual(set(self.persona.carreras.all()), {self.programacion, self.sistemas})

    def test_quitar_una_carrera_de_la_persona(self):
        self.persona.carreras.set([self.programacion, self.sistemas])
        self.client.post(
            reverse('biblioteca:persona_update', args=[self.persona.pk]),
            self.datos_persona(carreras=[self.sistemas.pk]),
        )
        self.assertEqual(list(self.persona.carreras.all()), [self.sistemas])

    def test_la_carrera_no_es_obligatoria_para_la_persona(self):
        respuesta = self.client.post(
            reverse('biblioteca:persona_create'), self.datos_persona(documento='40999888', carreras=[])
        )
        persona = Persona.objects.get(documento='40999888')
        self.assertRedirects(respuesta, reverse('biblioteca:persona_detail', args=[persona.pk]))
        self.assertFalse(persona.carreras.exists())

    def test_la_ficha_muestra_las_carreras_que_cursa_o_dicta(self):
        self.persona.carreras.set([self.programacion])
        respuesta = self.client.get(reverse('biblioteca:persona_detail', args=[self.persona.pk]))
        self.assertContains(respuesta, 'Carreras que cursa')
        self.assertContains(respuesta, PROGRAMACION)
        profesor = Persona.objects.create(nombre='Luis', apellido='Gómez', documento='20333444', tipo='PROFESOR')
        respuesta = self.client.get(reverse('biblioteca:persona_detail', args=[profesor.pk]))
        self.assertContains(respuesta, 'Carreras que dicta')
        self.assertContains(respuesta, 'Sin carrera asignada')

    def test_el_formulario_muestra_las_carreras_como_casillas(self):
        respuesta = self.client.get(reverse('biblioteca:persona_create'))
        self.assertContains(respuesta, '<legend>Carreras', html=False)
        self.assertContains(respuesta, 'type="checkbox" name="carreras"', count=10)

    def test_una_categoria_puede_tener_varias_carreras(self):
        self.client.post(
            reverse('biblioteca:categoria_update', args=[self.categoria.pk]),
            {'nombre': 'Informática', 'descripcion': '', 'carreras': [self.programacion.pk, self.sistemas.pk]},
        )
        self.assertEqual(set(self.categoria.carreras.all()), {self.programacion, self.sistemas})
        self.assertEqual(set(self.programacion.categorias.all()), {self.categoria})

    def test_la_base_no_repite_el_vinculo(self):
        self.persona.carreras.add(self.programacion)
        self.persona.carreras.add(self.programacion)
        self.assertEqual(self.persona.carreras.count(), 1)


class CarreraConDatosNoSeBorraTests(CarrerasTestCase):
    def test_no_se_borra_con_personas_o_categorias(self):
        casos = {
            'personas': lambda: self.persona.carreras.add(self.programacion),
            'categorías': lambda: self.categoria.carreras.add(self.programacion),
        }
        for caso, vincular in casos.items():
            with self.subTest(caso=caso):
                self.persona.carreras.clear()
                self.categoria.carreras.clear()
                vincular()
                with self.assertRaises(ProtectedError):
                    self.programacion.delete()

    def test_borrar_una_categoria_borra_sus_vinculos(self):
        self.categoria.carreras.add(self.programacion)
        self.categoria.delete()
        self.assertFalse(self.programacion.categorias.exists())


class CategoriasSinCarreraTests(CarrerasTestCase):
    def test_el_listado_de_categorias_avisa_las_que_no_tienen_carrera(self):
        respuesta = self.client.get(reverse('biblioteca:categoria_list'))
        self.assertContains(respuesta, '1 categoría todavía no tiene carrera.')
        self.assertContains(respuesta, 'Sin carrera')

    def test_filtrar_solo_las_que_faltan(self):
        clasificada = Categoria.objects.create(nombre='Diccionario')
        clasificada.carreras.add(self.programacion)
        respuesta = self.client.get(reverse('biblioteca:categoria_list'), {'sin_carrera': '1'})
        self.assertEqual([c.nombre for c in respuesta.context['object_list']], ['Informática'])

    def test_el_aviso_desaparece_cuando_todas_tienen_carrera(self):
        self.categoria.carreras.add(self.programacion)
        respuesta = self.client.get(reverse('biblioteca:categoria_list'))
        self.assertNotContains(respuesta, 'todavía no tiene')
        respuesta = self.client.get(reverse('biblioteca:carrera_list'))
        self.assertEqual(respuesta.context['categorias_sin_carrera'], [])

    def test_el_listado_de_carreras_tambien_avisa(self):
        respuesta = self.client.get(reverse('biblioteca:carrera_list'))
        self.assertContains(respuesta, 'Informática')
        self.assertContains(respuesta, '?sin_carrera=1')


class PermisosDeCarrerasTests(CarrerasTestCase):
    def urls(self):
        return [
            reverse('biblioteca:carrera_list'),
            reverse('biblioteca:carrera_create'),
            reverse('biblioteca:carrera_detail', args=[self.programacion.pk]),
            reverse('biblioteca:carrera_update', args=[self.programacion.pk]),
        ]

    def test_el_personal_accede(self):
        for url in self.urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_sin_rol_no_accede_ni_por_direccion_directa(self):
        sin_rol = get_user_model().objects.create_user(username='30111222', email='sin.rol@example.com', password=CLAVE)
        self.client.force_login(sin_rol)
        for url in self.urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_sin_sesion_va_al_login(self):
        self.client.logout()
        for url in self.urls():
            with self.subTest(url=url):
                respuesta = self.client.get(url)
                self.assertEqual(respuesta.status_code, 302)
                self.assertIn(reverse('login'), respuesta['Location'])

    def test_carrera_inexistente(self):
        respuesta = self.client.get(reverse('biblioteca:carrera_detail', args=[99999]))
        self.assertEqual(respuesta.status_code, 404)

    def test_el_menu_tiene_carreras_y_la_marca_como_activa(self):
        respuesta = self.client.get(reverse('biblioteca:carrera_detail', args=[self.programacion.pk]))
        self.assertContains(
            respuesta, f'href="{reverse("biblioteca:carrera_list")}" aria-current="page"'
        )
