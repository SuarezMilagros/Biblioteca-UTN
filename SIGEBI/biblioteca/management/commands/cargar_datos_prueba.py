from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

from biblioteca.models import (
    Autor, Categoria, Editorial, Ejemplar, Libro, Persona, Prestamo,
)

CATEGORIAS = [
    ('Administración', 'Gestión y organización de empresas.'),
    ('Informática', 'Programación y bases de datos.'),
    ('Matemática', 'Análisis y álgebra.'),
    ('Contabilidad', ''),
]

AUTORES = [
    ('Laura', 'Benítez'),
    ('Martín', 'Quiroga'),
    ('Sofía', 'Navarro'),
    ('Hugo', 'Ledesma'),
    ('Carla', 'Ibarra'),
]

EDITORIALES = ['Editorial Norte', 'Ediciones del Valle', 'Editorial Horizonte']

# (título, isbn, categoría, apellido del autor, editorial, prefijo de inventario, cantidad de ejemplares)
LIBROS = [
    ('Administración', '978-0-00-000001-0', 'Administración', 'Benítez', 'Editorial Norte', 'ADM', 3),
    ('Fundamentos de Programación', '978-0-00-000002-0', 'Informática', 'Quiroga', 'Ediciones del Valle', 'PRG', 2),
    ('Bases de Datos Relacionales', '978-0-00-000003-0', 'Informática', 'Navarro', 'Editorial Horizonte', 'BDD', 1),
    ('Cálculo I', '978-0-00-000004-0', 'Matemática', 'Ledesma', 'Ediciones del Valle', 'CAL', 2),
    ('Contabilidad Básica', '978-0-00-000005-0', 'Contabilidad', 'Ibarra', 'Editorial Norte', 'CON', 1),
    ('Álgebra Lineal', '978-0-00-000006-0', 'Matemática', 'Ledesma', 'Editorial Horizonte', 'ALG', 1),
]

OBSERVACIONES = {'CAL-002': 'Tapa con rastros de humedad.'}

# (nombre, apellido, documento, tipo, legajo)
PERSONAS = [
    ('Juan', 'Pérez', '30111222', Persona.Tipo.ALUMNO, '12345'),
    ('María', 'López', '31222333', Persona.Tipo.ALUMNO, '12346'),
    ('Pedro', 'Gómez', '20333444', Persona.Tipo.PROFESOR, ''),
    ('Lucía', 'Ramos', '32444555', Persona.Tipo.ALUMNO, '12347'),
]

# (código de ejemplar, documento, días de préstamo, días de vencimiento, días de devolución)
# Los días son relativos a hoy: -2 significa "hace dos días".
PRESTAMOS = [
    ('ADM-001', '30111222', -2, 5, None),      # activo y vigente
    ('PRG-001', '31222333', -20, -6, None),    # activo y vencido
    ('ADM-002', '20333444', -30, -16, -18),    # ya devuelto
    ('CAL-001', '32444555', -1, 6, None),      # activo y vigente
]


class Command(BaseCommand):
    help = 'Carga datos de prueba ficticios. Se puede ejecutar más de una vez sin duplicar.'

    def handle(self, *args, **options):
        hoy = timezone.localdate()

        with transaction.atomic():
            categorias = {}
            for nombre, descripcion in CATEGORIAS:
                categorias[nombre], _ = Categoria.objects.get_or_create(
                    nombre=nombre, defaults={'descripcion': descripcion},
                )

            autores = {}
            for nombre, apellido in AUTORES:
                autores[apellido], _ = Autor.objects.get_or_create(
                    nombre=nombre, apellido=apellido,
                )

            editoriales = {}
            for nombre in EDITORIALES:
                editoriales[nombre], _ = Editorial.objects.get_or_create(nombre=nombre)

            ejemplares = {}
            for titulo, isbn, cat, apellido, edi, prefijo, cantidad in LIBROS:
                libro, _ = Libro.objects.get_or_create(
                    isbn=isbn,
                    defaults={
                        'titulo': titulo,
                        'categoria': categorias[cat],
                        'autor': autores[apellido],
                        'editorial': editoriales[edi],
                    },
                )
                for n in range(1, cantidad + 1):
                    codigo = f'{prefijo}-{n:03d}'
                    ejemplares[codigo], _ = Ejemplar.objects.get_or_create(
                        codigo_inventario=codigo,
                        defaults={
                            'libro': libro,
                            'observaciones': OBSERVACIONES.get(codigo, ''),
                        },
                    )

            personas = {}
            for nombre, apellido, documento, tipo, legajo in PERSONAS:
                personas[documento], _ = Persona.objects.get_or_create(
                    documento=documento,
                    defaults={
                        'nombre': nombre,
                        'apellido': apellido,
                        'tipo': tipo,
                        'legajo': legajo,
                    },
                )

            usuario, creado = get_user_model().objects.get_or_create(
                username='bibliotecario_prueba',
                defaults={'first_name': 'Bibliotecario', 'last_name': 'de Prueba'},
            )
            if creado:
                usuario.set_unusable_password()
                usuario.save()

            for codigo, documento, d_prestamo, d_venc, d_dev in PRESTAMOS:
                ejemplar = ejemplares[codigo]
                persona = personas[documento]
                if Prestamo.objects.filter(ejemplar=ejemplar, persona=persona).exists():
                    continue
                Prestamo.objects.create(
                    ejemplar=ejemplar,
                    persona=persona,
                    usuario_sistema=usuario,
                    fecha_prestamo=hoy + timedelta(days=d_prestamo),
                    fecha_vencimiento=hoy + timedelta(days=d_venc),
                    fecha_devolucion=None if d_dev is None else hoy + timedelta(days=d_dev),
                )

        self.stdout.write(self.style.SUCCESS('Datos de prueba cargados.'))
        self.stdout.write(
            f'Categorías: {Categoria.objects.count()} | Autores: {Autor.objects.count()} | '
            f'Editoriales: {Editorial.objects.count()} | Libros: {Libro.objects.count()} | '
            f'Ejemplares: {Ejemplar.objects.count()} | Personas: {Persona.objects.count()} | '
            f'Préstamos: {Prestamo.objects.count()}'
        )