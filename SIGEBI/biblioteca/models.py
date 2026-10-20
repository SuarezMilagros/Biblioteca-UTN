from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Upper
from django.utils import timezone


class Categoria(models.Model):
    id_categoria = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)

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
        return f'{self.apellido}, {self.nombre}'


class Editorial(models.Model):
    id_editorial = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=150)

    class Meta:
        verbose_name = 'editorial'
        verbose_name_plural = 'editoriales'

    def __str__(self):
        return self.nombre


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

    class Meta:
        verbose_name = 'libro'
        verbose_name_plural = 'libros'

    def __str__(self):
        return self.titulo


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

    class Meta:
        verbose_name = 'ejemplar'
        verbose_name_plural = 'ejemplares'
        constraints = [
            models.UniqueConstraint(
                Upper('codigo_inventario'),
                name='codigo_inventario_unico',
                violation_error_message='Ya existe un ejemplar con ese código de inventario.',
            ),
        ]

    def __str__(self):
        return self.codigo_inventario

    @staticmethod
    def normalizar_codigo(valor):
        return (valor or '').strip().upper()

    def clean(self):
        super().clean()
        self.codigo_inventario = self.normalizar_codigo(self.codigo_inventario)
        if not self.codigo_inventario:
            raise ValidationError({'codigo_inventario': 'Este campo es obligatorio.'})

    def save(self, *args, **kwargs):
        self.codigo_inventario = self.normalizar_codigo(self.codigo_inventario)
        super().save(*args, **kwargs)

    @property
    def disponible(self):
        return not self.prestamos.filter(fecha_devolucion__isnull=True).exists()


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

    class Meta:
        verbose_name = 'persona'
        verbose_name_plural = 'personas'

    def __str__(self):
        return f'{self.apellido}, {self.nombre}'


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
        ]

    def __str__(self):
        return f'{self.ejemplar} → {self.persona}'

    @property
    def activo(self):
        return self.fecha_devolucion is None

    @property
    def vencido(self):
        return self.activo and self.fecha_vencimiento < timezone.localdate()