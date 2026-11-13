from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models.functions import Coalesce, Upper
from django.utils import timezone

# Plazo del préstamo en días corridos (decisión D2). Es el único lugar donde se define.
PLAZO_PRESTAMO_DIAS = 14


class Carrera(models.Model):
    """Carrera de la Extensión Áulica (Release 2, S7-02)."""

    class Nivel(models.TextChoices):
        PREGRADO = 'PREGRADO', 'Pregrado'
        GRADO = 'GRADO', 'Grado'

    id_carrera = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=150)
    nivel = models.CharField(max_length=20, choices=Nivel.choices)

    class Meta:
        verbose_name = 'carrera'
        verbose_name_plural = 'carreras'
        # Primero las de pregrado y después las de grado ("PREGRADO" > "GRADO" alfabéticamente).
        ordering = ['-nivel', 'nombre']
        constraints = [
            models.UniqueConstraint(
                Upper('nombre'),
                name='carrera_nombre_unico',
                violation_error_message='Ya existe una carrera con ese nombre.',
            ),
        ]

    def __str__(self):
        return self.nombre


class Categoria(models.Model):
    id_categoria = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    # Un libro pertenece a las carreras de su categoría (D-R2-6): no se guardan aparte.
    carreras = models.ManyToManyField(
        Carrera,
        through='CategoriaCarrera',
        related_name='categorias',
        blank=True,
    )

    class Meta:
        verbose_name = 'categoría'
        verbose_name_plural = 'categorías'

    def __str__(self):
        return self.nombre


class Autor(models.Model):
    id_autor = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)

    class Meta:
        verbose_name = 'autor'
        verbose_name_plural = 'autores'

    def __str__(self):
        # Hay autores con solo apellido (por ejemplo, los cargados del inventario en Excel).
        return f'{self.apellido}, {self.nombre}' if self.nombre else self.apellido


class Editorial(models.Model):
    id_editorial = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=150)

    class Meta:
        verbose_name = 'editorial'
        verbose_name_plural = 'editoriales'

    def __str__(self):
        return self.nombre


class LibroQuerySet(models.QuerySet):
    def con_disponibilidad(self):
        """Agrega a cada libro `ejemplares_activos` y `ejemplares_disponibles`, en la misma consulta.

        Disponible = activo y sin un préstamo sin devolver. Lo usan el listado del personal y el
        catálogo del portal (S7-05), así los dos muestran siempre lo mismo.
        """
        prestamo_activo = Prestamo.objects.filter(ejemplar=models.OuterRef('pk'), fecha_devolucion__isnull=True)
        disponibles = (
            Ejemplar.objects.filter(libro=models.OuterRef('pk'), activo=True)
            .filter(~models.Exists(prestamo_activo))
            .order_by()
            .values('libro')
            .annotate(cantidad=models.Count('pk'))
            .values('cantidad')
        )
        return self.annotate(
            ejemplares_activos=models.Count('ejemplares', filter=models.Q(ejemplares__activo=True), distinct=True),
            ejemplares_disponibles=Coalesce(
                models.Subquery(disponibles, output_field=models.IntegerField()), 0
            ),
        )

    def de_las_carreras(self, carreras):
        """Libros cuya categoría corresponde a alguna de esas carreras (D-R2-6), sin repetir."""
        return self.filter(categoria__in=Categoria.objects.filter(carreras__in=carreras))


class Libro(models.Model):
    id_libro = models.BigAutoField(primary_key=True)
    titulo = models.CharField(max_length=255)
    isbn = models.CharField(max_length=20, blank=True)
    imagen = models.ImageField(upload_to='portadas/', blank=True)
    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.PROTECT,
        db_column='id_categoria',
        related_name='libros',
    )
    autor = models.ForeignKey(
        Autor,
        on_delete=models.PROTECT,
        db_column='id_autor',
        related_name='libros',
    )
    editorial = models.ForeignKey(
        Editorial,
        on_delete=models.PROTECT,
        db_column='id_editorial',
        related_name='libros',
    )

    objects = LibroQuerySet.as_manager()

    class Meta:
        verbose_name = 'libro'
        verbose_name_plural = 'libros'

    def __str__(self):
        return self.titulo


class EjemplarQuerySet(models.QuerySet):
    def con_estado_de_prestamo(self):
        """Agrega `con_prestamo_activo` a cada ejemplar en la misma consulta (S6-11).

        Así un listado sabe qué ejemplares están prestados sin hacer una consulta por fila;
        la propiedad `prestado` usa ese dato cuando está.
        """
        prestamo_activo = Prestamo.objects.filter(ejemplar=models.OuterRef('pk'), fecha_devolucion__isnull=True)
        return self.annotate(con_prestamo_activo=models.Exists(prestamo_activo))


class Ejemplar(models.Model):
    id_ejemplar = models.BigAutoField(primary_key=True)
    id_inventario = models.PositiveIntegerField(
        unique=True,
        null=True,
        blank=True,
        verbose_name='ID de inventario',
        help_text='Identificador numérico original del inventario. Opcional; único cuando tiene valor.',
    )
    codigo_inventario = models.CharField(
        max_length=30,
        verbose_name='código de inventario',
        help_text='Numeración física del ejemplar. Admite letras y números; se guarda en mayúsculas.',
    )
    observaciones = models.TextField(blank=True)
    libro = models.ForeignKey(
        Libro,
        on_delete=models.PROTECT,
        db_column='id_libro',
        related_name='ejemplares',
    )

    class MotivoBaja(models.TextChoices):
        PERDIDO = 'PERDIDO', 'Perdido'
        DANADO = 'DANADO', 'Dañado'
        DESCARTE = 'DESCARTE', 'Descarte'
        OTRO = 'OTRO', 'Otro'

    # Baja lógica: el ejemplar no se borra porque tiene historial de préstamos.
    activo = models.BooleanField(
        default=True,
        verbose_name='activo',
        help_text='Un ejemplar dado de baja no se puede prestar.',
    )
    motivo_baja = models.CharField(
        max_length=20, choices=MotivoBaja.choices, blank=True, verbose_name='motivo de baja'
    )
    fecha_baja = models.DateField(null=True, blank=True, verbose_name='fecha de baja')

    class Meta:
        verbose_name = 'ejemplar'
        verbose_name_plural = 'ejemplares'
        constraints = [
            models.UniqueConstraint(
                Upper('codigo_inventario'),
                name='codigo_inventario_unico',
                violation_error_message='Ya existe un ejemplar con ese código de inventario.',
            ),
            # Un ejemplar activo no tiene datos de baja; uno dado de baja tiene motivo y fecha.
            models.CheckConstraint(
                condition=(
                    models.Q(activo=True, motivo_baja='', fecha_baja__isnull=True)
                    | (models.Q(activo=False, fecha_baja__isnull=False) & ~models.Q(motivo_baja=''))
                ),
                name='ejemplar_baja_coherente',
                violation_error_message='Un ejemplar dado de baja necesita motivo y fecha de baja.',
            ),
        ]

    def __str__(self):
        return self.codigo_inventario

    @staticmethod
    def normalizar_codigo(valor):
        return (valor or '').strip().upper()

    def clean_fields(self, exclude=None):
        # Se normaliza antes de validar: "   " queda vacío y el campo da un solo error.
        self.codigo_inventario = self.normalizar_codigo(self.codigo_inventario)
        super().clean_fields(exclude=exclude)

    def save(self, *args, **kwargs):
        self.codigo_inventario = self.normalizar_codigo(self.codigo_inventario)
        super().save(*args, **kwargs)

    objects = EjemplarQuerySet.as_manager()

    @property
    def prestado(self):
        """Tiene un préstamo sin devolver. Si el ejemplar vino de `con_estado_de_prestamo()`, no consulta de nuevo."""
        if hasattr(self, 'con_prestamo_activo'):
            return self.con_prestamo_activo
        return self.prestamos.filter(fecha_devolucion__isnull=True).exists()

    @property
    def disponible(self):
        """Se puede prestar: está activo y no tiene un préstamo sin devolver."""
        return self.activo and not self.prestado


class Persona(models.Model):
    class Tipo(models.TextChoices):
        ALUMNO = 'ALUMNO', 'Alumno'
        PROFESOR = 'PROFESOR', 'Profesor'

    id_persona = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    documento = models.CharField(max_length=20, unique=True)
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    legajo = models.CharField(max_length=20, blank=True)
    # Carreras que cursa (alumno) o dicta (profesor). Puede tener varias (D-R2-5).
    carreras = models.ManyToManyField(
        Carrera,
        through='PersonaCarrera',
        related_name='personas',
        blank=True,
    )
    # Baja lógica: la persona no se borra porque tiene historial de préstamos.
    activo = models.BooleanField(
        default=True,
        verbose_name='activa',
        help_text='Una persona dada de baja no puede recibir préstamos nuevos.',
    )
    # Cuenta para ingresar al portal (Release 2, S7-03). Una persona tiene como máximo una (D-R2-10).
    cuenta = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column='id_usuario_sistema',
        related_name='persona',
    )

    class Meta:
        verbose_name = 'persona'
        verbose_name_plural = 'personas'

    def __str__(self):
        return f'{self.apellido}, {self.nombre}'

    @staticmethod
    def normalizar_documento(valor):
        """Quita espacios y puntos, y pasa a mayúsculas: "40.111.222" queda "40111222"."""
        return (valor or '').replace('.', '').replace(' ', '').strip().upper()

    def save(self, *args, **kwargs):
        self.documento = self.normalizar_documento(self.documento)
        super().save(*args, **kwargs)
        if self.cuenta_id:
            self.sincronizar_cuenta()

    def sincronizar_cuenta(self):
        """La cuenta refleja los datos de la persona: documento (usuario), nombre, apellido y si está activa.

        Así, dar de baja a la persona desactiva su cuenta y reactivarla la reactiva (D-R2-10).
        """
        get_user_model().objects.filter(pk=self.cuenta_id).update(
            username=self.documento,
            first_name=self.nombre,
            last_name=self.apellido,
            is_active=self.activo,
        )

    @property
    def tiene_prestamos_activos(self):
        return self.prestamos.filter(fecha_devolucion__isnull=True).exists()


class Prestamo(models.Model):
    id_prestamo = models.BigAutoField(primary_key=True)
    fecha_prestamo = models.DateField(default=timezone.localdate)
    fecha_vencimiento = models.DateField()
    fecha_devolucion = models.DateField(null=True, blank=True)
    persona = models.ForeignKey(
        Persona,
        on_delete=models.PROTECT,
        db_column='id_persona',
        related_name='prestamos',
    )
    ejemplar = models.ForeignKey(
        Ejemplar,
        on_delete=models.PROTECT,
        db_column='id_ejemplar',
        related_name='prestamos',
    )
    usuario_sistema = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        db_column='id_usuario_sistema',
        related_name='prestamos_registrados',
    )

    class Meta:
        verbose_name = 'préstamo'
        verbose_name_plural = 'préstamos'
        constraints = [
            models.UniqueConstraint(
                fields=['ejemplar'],
                condition=models.Q(fecha_devolucion__isnull=True),
                name='un_prestamo_activo_por_ejemplar',
                violation_error_message='El ejemplar ya tiene un préstamo activo.',
            ),
            models.CheckConstraint(
                condition=models.Q(fecha_vencimiento__gte=models.F('fecha_prestamo')),
                name='vencimiento_no_anterior_a_prestamo',
                violation_error_message='La fecha de vencimiento no puede ser anterior a la fecha de préstamo.',
            ),
            # Decisión D8: una devolución nunca es anterior al préstamo.
            models.CheckConstraint(
                condition=(
                    models.Q(fecha_devolucion__isnull=True)
                    | models.Q(fecha_devolucion__gte=models.F('fecha_prestamo'))
                ),
                name='devolucion_no_anterior_a_prestamo',
                violation_error_message='La fecha de devolución no puede ser anterior a la fecha de préstamo.',
            ),
        ]

    def __str__(self):
        return f'{self.ejemplar} → {self.persona}'

    @property
    def activo(self):
        return self.fecha_devolucion is None

    @property
    def vencido(self):
        return self.activo and self.fecha_vencimiento < timezone.localdate()

    @staticmethod
    def calcular_vencimiento(fecha_prestamo):
        return fecha_prestamo + timedelta(days=PLAZO_PRESTAMO_DIAS)


class PersonaCarrera(models.Model):
    """Una carrera que cursa o dicta una persona (tabla intermedia, D-R2-17)."""

    persona = models.ForeignKey(Persona, on_delete=models.CASCADE, db_column='id_persona')
    carrera = models.ForeignKey(Carrera, on_delete=models.PROTECT, db_column='id_carrera')

    class Meta:
        verbose_name = 'carrera de una persona'
        verbose_name_plural = 'carreras de las personas'
        constraints = [
            models.UniqueConstraint(fields=['persona', 'carrera'], name='persona_carrera_unica'),
        ]

    def __str__(self):
        return f'{self.persona} → {self.carrera}'


class CategoriaCarrera(models.Model):
    """Una carrera a la que corresponde una categoría (tabla intermedia, D-R2-17)."""

    categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE, db_column='id_categoria')
    carrera = models.ForeignKey(Carrera, on_delete=models.PROTECT, db_column='id_carrera')

    class Meta:
        verbose_name = 'carrera de una categoría'
        verbose_name_plural = 'carreras de las categorías'
        constraints = [
            models.UniqueConstraint(fields=['categoria', 'carrera'], name='categoria_carrera_unica'),
        ]

    def __str__(self):
        return f'{self.categoria} → {self.carrera}'
