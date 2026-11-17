"""Material compartido por alumnos y profesores (Release 2, S8-01, D-R2-7).

- Un lector sube un PDF desde el portal, solo para sus carreras, aceptando la declaración de derechos de autor.
- Queda pendiente: no lo ve nadie más que quien lo subió (que lo sigue en Mi perfil).
- El personal lo ve en "Para revisar" (con indicador en el menú y en el inicio), abre el PDF y lo
  aprueba (se publica) o lo rechaza con motivo. En los dos casos se avisa por correo.
- Un lector puede tener como máximo 5 materiales esperando revisión.
"""
import smtplib
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from biblioteca import revision_de_material as reglas
from biblioteca.models import MaterialDigital, Persona
from biblioteca.tests.test_material_digital import CLAVE, MaterialTestCase, pdf
from cuentas.lectores import crear_cuenta_de_lector


class CompartidoTestCase(MaterialTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.bibliotecario.first_name, cls.bibliotecario.last_name = 'Laura', 'Gómez'
        cls.bibliotecario.save()
        cls.profesor = Persona.objects.create(nombre='Luis', apellido='Gómez', documento='20333444', tipo='PROFESOR')
        cls.profesor.carreras.add(cls.programacion, cls.mecanica)
        cls.cuenta_profesor = crear_cuenta_de_lector(cls.profesor, 'luis.gomez@frt.example.com')
        cls.otro = Persona.objects.create(nombre='Carlos', apellido='Ruiz', documento='40999888', tipo='ALUMNO')
        cls.otro.carreras.add(cls.programacion)
        cls.cuenta_otro = crear_cuenta_de_lector(cls.otro, 'carlos.ruiz@alumnos.example.com')

    def compartir(self, usuario=None, **cambios):
        self.client.force_login(usuario or self.lector)
        datos = {
            'titulo': 'Resumen de Python', 'tipo': 'APUNTE', 'carrera': self.programacion.pk,
            'autores': 'Pérez, Ana', 'anio': '2026', 'descripcion': 'Para el primer parcial',
            'archivo': pdf('resumen.pdf'), 'derechos': 'on',
        }
        datos.update(cambios)
        return self.client.post(reverse('portal:material_compartir'), datos, follow=True)

    def pendiente(self, usuario=None, **cambios):
        datos = dict(estado=MaterialDigital.Estado.PENDIENTE, usuario_carga=usuario or self.lector,
                     usuario_revision=None, fecha_revision=None, titulo='Resumen de Python')
        datos.update(cambios)
        return self.material(**datos)

    def recargar(self, material):
        material.refresh_from_db()
        return material


class CompartirDesdeElPortalTests(CompartidoTestCase):
    def test_sube_un_pdf_y_queda_pendiente(self):
        respuesta = self.compartir()
        material = MaterialDigital.objects.get()
        self.assertEqual(
            (material.titulo, material.carrera, material.estado, material.usuario_carga, material.activo),
            ('Resumen de Python', self.programacion, 'PENDIENTE', self.lector, True),
        )
        self.assertIsNone(material.usuario_revision)
        self.assertRedirects(respuesta, reverse('portal:perfil') + '#material-compartido')
        self.assertContains(respuesta, 'Recibimos &quot;Resumen de Python&quot;')
        self.assertContains(respuesta, 'En revisión')

    def test_hay_que_aceptar_la_declaracion_de_derechos(self):
        respuesta = self.compartir(derechos='')
        self.assertContains(respuesta, 'Para compartir el material tenés que aceptar esta declaración.')
        self.assertFalse(MaterialDigital.objects.exists())

    def test_la_pantalla_explica_los_derechos_de_autor(self):
        self.client.force_login(self.lector)
        respuesta = self.client.get(reverse('portal:material_compartir'))
        self.assertContains(respuesta, 'Derechos de autor')
        self.assertContains(respuesta, 'No subas libros escaneados')
        self.assertContains(respuesta, 'name="derechos"')

    def test_solo_puede_elegir_sus_carreras(self):
        respuesta = self.compartir(carrera=self.mecanica.pk)
        self.assertContains(respuesta, 'Seleccione una opción válida')
        self.assertFalse(MaterialDigital.objects.exists())

    def test_el_profesor_elige_entre_las_carreras_que_dicta(self):
        self.client.force_login(self.cuenta_profesor)
        formulario = self.client.get(reverse('portal:material_compartir')).context['form']
        self.assertEqual(set(formulario.fields['carrera'].queryset), {self.programacion, self.mecanica})
        self.compartir(usuario=self.cuenta_profesor, carrera=self.mecanica.pk)
        self.assertEqual(MaterialDigital.objects.get().carrera, self.mecanica)

    def test_con_una_sola_carrera_viene_elegida(self):
        self.client.force_login(self.lector)
        formulario = self.client.get(reverse('portal:material_compartir')).context['form']
        self.assertIsNone(formulario.fields['carrera'].empty_label)

    def test_se_valida_que_sea_un_pdf(self):
        respuesta = self.compartir(archivo=pdf('virus.pdf', b'MZ\x90\x00 no es un pdf'))
        self.assertContains(respuesta, 'El archivo no es un PDF válido.')
        self.assertFalse(MaterialDigital.objects.exists())

    def test_sin_carreras_no_puede_compartir(self):
        self.persona.carreras.clear()
        self.client.force_login(self.lector)
        respuesta = self.client.get(reverse('portal:material_compartir'))
        self.assertContains(respuesta, 'No tenés carreras asignadas.')
        self.assertNotContains(respuesta, 'Enviar a revisión')

    def test_maximo_de_pendientes(self):
        for numero in range(reglas.MAXIMO_PENDIENTES_POR_PERSONA):
            self.pendiente(titulo=f'Apunte {numero}')
        self.client.force_login(self.lector)
        self.assertContains(self.client.get(reverse('portal:material_compartir')), 'Ya tenés 5 materiales esperando revisión.')
        respuesta = self.compartir()
        self.assertContains(respuesta, 'Ya tenés 5 materiales esperando revisión. Cuando la biblioteca los revise')
        self.assertEqual(MaterialDigital.objects.count(), reglas.MAXIMO_PENDIENTES_POR_PERSONA)

    def test_lo_revisado_no_cuenta_para_el_maximo(self):
        for numero in range(reglas.MAXIMO_PENDIENTES_POR_PERSONA - 1):
            self.pendiente(titulo=f'Apunte {numero}')
        self.material(usuario_carga=self.lector, titulo='Ya aprobado')
        self.compartir()
        self.assertEqual(MaterialDigital.objects.filter(estado='PENDIENTE').count(), reglas.MAXIMO_PENDIENTES_POR_PERSONA)

    def test_el_personal_no_entra_a_compartir(self):
        self.client.force_login(self.bibliotecario)
        self.assertEqual(self.client.get(reverse('portal:material_compartir')).status_code, 403)

    def test_la_lista_del_portal_ofrece_compartir(self):
        self.client.force_login(self.lector)
        self.assertContains(self.client.get(reverse('portal:material')), reverse('portal:material_compartir'))

    def test_con_material_publicado_el_boton_de_compartir_sigue_arriba(self):
        self.material(titulo='Guía publicada')
        self.client.force_login(self.lector)
        respuesta = self.client.get(reverse('portal:material'))
        self.assertContains(respuesta, 'Guía publicada')
        self.assertContains(respuesta, f'<a class="boton" href="{reverse("portal:material_compartir")}">')


class VisibilidadTests(CompartidoTestCase):
    def test_lo_pendiente_no_lo_ve_nadie_mas(self):
        material = self.pendiente()
        self.client.force_login(self.cuenta_otro)
        self.assertNotContains(self.client.get(reverse('portal:material')), 'Resumen de Python')
        self.assertEqual(self.client.get(reverse('portal:material_archivo', args=[material.pk])).status_code, 404)

    def test_quien_lo_subio_lo_ve_en_su_perfil_y_lo_abre(self):
        material = self.pendiente()
        self.client.force_login(self.lector)
        self.assertNotContains(self.client.get(reverse('portal:material')), 'Resumen de Python')
        perfil = self.client.get(reverse('portal:perfil'))
        self.assertContains(perfil, 'Material que compartiste')
        self.assertContains(perfil, 'La biblioteca todavía no lo revisó.')
        respuesta = self.client.get(reverse('portal:material_archivo', args=[material.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta['Content-Type'], 'application/pdf')

    def test_el_perfil_muestra_cada_estado(self):
        self.pendiente(titulo='En espera')
        self.material(usuario_carga=self.lector, titulo='Aprobado')
        self.material(usuario_carga=self.lector, titulo='Rechazado', estado='RECHAZADO', motivo_rechazo='Está borroso.')
        self.material(usuario_carga=self.lector, titulo='Retirado', activo=False)
        self.material(titulo='De la biblioteca')
        self.client.force_login(self.lector)
        respuesta = self.client.get(reverse('portal:perfil'))
        self.assertEqual(
            {material.titulo for material in respuesta.context['materiales_compartidos']},
            {'En espera', 'Aprobado', 'Rechazado', 'Retirado'},
        )
        for texto in ('En revisión', 'Publicado', 'Está borroso.', 'Dado de baja'):
            self.assertContains(respuesta, texto)

    def test_aprobado_lo_ven_los_de_su_carrera(self):
        material = self.pendiente()
        reglas.aprobar(material, self.bibliotecario)
        self.client.force_login(self.cuenta_otro)
        self.assertContains(self.client.get(reverse('portal:material')), 'Resumen de Python')
        self.assertEqual(self.client.get(reverse('portal:material_archivo', args=[material.pk])).status_code, 200)

    def test_criterio_de_aceptacion_un_apunte_solo_aparece_despues_de_aprobarlo(self):
        self.compartir()
        self.client.force_login(self.cuenta_otro)
        self.assertNotContains(self.client.get(reverse('portal:material')), 'Resumen de Python')
        self.client.force_login(self.bibliotecario)
        self.client.post(reverse('biblioteca:material_aprobar', args=[MaterialDigital.objects.get().pk]))
        self.client.force_login(self.cuenta_otro)
        self.assertContains(self.client.get(reverse('portal:material')), 'Resumen de Python')


class RevisionTests(CompartidoTestCase):
    def test_para_revisar_lista_lo_pendiente_del_mas_viejo_al_mas_nuevo(self):
        nuevo = self.pendiente(titulo='Nuevo')
        viejo = self.pendiente(titulo='Viejo', usuario_carga=self.cuenta_otro)
        MaterialDigital.objects.filter(pk=viejo.pk).update(fecha_carga=timezone.now() - timedelta(days=2))
        self.material(titulo='Publicado')
        respuesta = self.client.get(reverse('biblioteca:material_list') + '?estado=pendientes')
        self.assertEqual([m.pk for m in respuesta.context['materiales']], [viejo.pk, nuevo.pk])
        self.assertContains(respuesta, 'Revisar')
        self.assertContains(respuesta, 'Pérez, Ana')

    def test_publicados_no_incluye_lo_pendiente_ni_lo_rechazado(self):
        self.pendiente(titulo='Pendiente')
        self.material(titulo='Rechazado', estado='RECHAZADO', motivo_rechazo='No')
        self.material(titulo='Publicado')
        respuesta = self.client.get(reverse('biblioteca:material_list'))
        self.assertEqual([m.titulo for m in respuesta.context['materiales']], ['Publicado'])
        self.assertContains(respuesta, 'esperando revisión')
        rechazados = self.client.get(reverse('biblioteca:material_list') + '?estado=rechazados')
        self.assertEqual([m.titulo for m in rechazados.context['materiales']], ['Rechazado'])

    def test_la_ficha_permite_abrir_el_pdf_y_decidir(self):
        material = self.pendiente()
        respuesta = self.client.get(reverse('biblioteca:material_revisar', args=[material.pk]))
        self.assertContains(respuesta, reverse('biblioteca:material_archivo', args=[material.pk]))
        self.assertContains(respuesta, 'Aprobar y publicar')
        self.assertContains(respuesta, 'Rechazar material')
        self.assertContains(respuesta, 'Alumno')
        self.assertEqual(self.client.get(reverse('biblioteca:material_archivo', args=[material.pk])).status_code, 200)

    def test_aprobar_publica_y_avisa_por_correo(self):
        material = self.pendiente()
        respuesta = self.client.post(reverse('biblioteca:material_aprobar', args=[material.pk]), follow=True)
        material = self.recargar(material)
        self.assertEqual((material.estado, material.usuario_revision), ('APROBADO', self.bibliotecario))
        self.assertIsNotNone(material.fecha_revision)
        self.assertRedirects(respuesta, reverse('biblioteca:material_list') + '?estado=pendientes')
        self.assertContains(respuesta, 'aprobado: ya se ve en el portal. Se le avisó por correo')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['ana.perez@alumnos.example.com'])
        self.assertEqual(mail.outbox[0].subject, 'Tu material ya está publicado: Resumen de Python')
        self.assertIn('Hola, Ana:', mail.outbox[0].body)
        self.assertIn('Tecnicatura Universitaria en Programación', mail.outbox[0].body)

    def test_rechazar_con_motivo_y_avisa_por_correo(self):
        material = self.pendiente()
        respuesta = self.client.post(
            reverse('biblioteca:material_rechazar', args=[material.pk]), {'motivo': '  Es un libro escaneado.  '}, follow=True,
        )
        material = self.recargar(material)
        self.assertEqual((material.estado, material.motivo_rechazo), ('RECHAZADO', 'Es un libro escaneado.'))
        self.assertContains(respuesta, 'rechazado. Se le avisó por correo')
        self.assertEqual(mail.outbox[0].subject, 'Tu material no pudo publicarse: Resumen de Python')
        self.assertIn('Motivo: Es un libro escaneado.', mail.outbox[0].body)
        self.client.force_login(self.cuenta_otro)
        self.assertNotContains(self.client.get(reverse('portal:material')), 'Resumen de Python')

    def test_sin_motivo_no_rechaza(self):
        material = self.pendiente()
        respuesta = self.client.post(reverse('biblioteca:material_rechazar', args=[material.pk]), {'motivo': ' '}, follow=True)
        self.assertContains(respuesta, 'Escribí el motivo del rechazo')
        self.assertEqual(self.recargar(material).estado, 'PENDIENTE')
        self.assertEqual(len(mail.outbox), 0)

    def test_no_se_revisa_dos_veces(self):
        material = self.pendiente()
        reglas.rechazar(material, 'No', self.bibliotecario)
        respuesta = self.client.post(reverse('biblioteca:material_aprobar', args=[material.pk]), follow=True)
        self.assertContains(respuesta, 'Este material ya fue revisado.')
        self.assertEqual(self.recargar(material).estado, 'RECHAZADO')
        self.assertEqual(len(mail.outbox), 0)

    def test_un_material_sin_revisar_no_genera_aviso(self):
        self.assertFalse(reglas.avisar_por_correo(self.pendiente()))
        self.assertEqual(len(mail.outbox), 0)

    def test_si_el_correo_falla_queda_aprobado_y_lo_advierte(self):
        material = self.pendiente()
        with mock.patch('biblioteca.revision_de_material.send_mail', side_effect=smtplib.SMTPException('caído')):
            respuesta = self.client.post(reverse('biblioteca:material_aprobar', args=[material.pk]), follow=True)
        self.assertEqual(self.recargar(material).estado, 'APROBADO')
        self.assertContains(respuesta, 'No se pudo enviar el correo de aviso.')

    def test_lo_pendiente_no_se_da_de_baja_ni_lo_rechazado_se_publica(self):
        pendiente = self.pendiente()
        rechazado = self.material(titulo='Rechazado', estado='RECHAZADO', motivo_rechazo='No')
        MaterialDigital.objects.filter(pk=rechazado.pk).update(activo=False)
        for nombre, material in (('material_baja', pendiente), ('material_reactivar', rechazado)):
            with self.subTest(nombre=nombre):
                respuesta = self.client.post(reverse(f'biblioteca:{nombre}', args=[material.pk]), follow=True)
                self.assertContains(respuesta, 'no está aprobado: primero hay que revisarlo.')
        self.assertTrue(self.recargar(pendiente).activo)
        self.assertFalse(self.recargar(rechazado).activo)

    def test_menu_e_inicio_muestran_lo_que_hay_para_revisar(self):
        self.pendiente()
        self.pendiente(usuario_carga=self.cuenta_otro)
        respuesta = self.client.get(reverse('biblioteca:inicio'))
        self.assertEqual(respuesta.context['material_para_revisar_total'], 2)
        self.assertEqual(respuesta.context['material_para_revisar'], 2)
        self.assertContains(respuesta, 'Material para revisar')
        self.assertContains(respuesta, '<span class="nav-contador" aria-label="2 para revisar">2</span>', html=True)

    def test_lo_que_sube_el_personal_sigue_publicandose_directo(self):
        self.client.post(reverse('biblioteca:material_create'), {
            'titulo': 'Guía', 'tipo': 'APUNTE', 'carrera': self.programacion.pk, 'archivo': pdf(),
        })
        material = MaterialDigital.objects.get()
        self.assertEqual((material.estado, material.usuario_revision), ('APROBADO', self.bibliotecario))
        self.assertEqual(len(mail.outbox), 0)
        respuesta = self.client.get(reverse('biblioteca:material_list'))
        self.assertContains(respuesta, 'Laura Gómez')
        self.assertContains(respuesta, 'Biblioteca')


class PermisosTests(CompartidoTestCase):
    def test_con_solo_ver_no_revisa(self):
        usuario = get_user_model().objects.create_user(username='consulta', password=CLAVE)
        usuario.user_permissions.add(Permission.objects.get(codename='view_materialdigital'))
        self.client.force_login(usuario)
        material = self.pendiente()
        respuesta = self.client.get(reverse('biblioteca:material_revisar', args=[material.pk]))
        self.assertNotContains(respuesta, 'Aprobar y publicar')
        self.assertEqual(self.client.post(reverse('biblioteca:material_aprobar', args=[material.pk])).status_code, 403)
        self.assertEqual(self.recargar(material).estado, 'PENDIENTE')

    def test_sin_permiso_es_403_antes_de_buscar_el_material(self):
        usuario = get_user_model().objects.create_user(username='sinpermisos', password=CLAVE)
        self.client.force_login(usuario)
        self.assertEqual(self.client.get(reverse('biblioteca:material_revisar', args=[999])).status_code, 403)
        self.assertEqual(self.client.post(reverse('biblioteca:material_rechazar', args=[999])).status_code, 403)

    def test_el_lector_no_revisa(self):
        material = self.pendiente(usuario_carga=self.cuenta_otro)
        self.client.force_login(self.lector)
        self.assertEqual(self.client.post(reverse('biblioteca:material_aprobar', args=[material.pk])).status_code, 403)
        self.assertEqual(self.recargar(material).estado, 'PENDIENTE')
