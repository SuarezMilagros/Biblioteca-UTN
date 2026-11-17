"""Envía por correo los avisos de préstamos que vencen pronto o ya vencieron (Release 2, S8-06).

Uso:
    python manage.py enviar_avisos             # envía los avisos que falten
    python manage.py enviar_avisos --simular   # solo muestra a quién se enviarían, sin enviar ni registrar

Se puede ejecutar varias veces: cada aviso se envía una sola vez por préstamo y tipo.
En producción se programa una vez por día (S8-09). Las reglas están en biblioteca/avisos.py.
"""
from django.core.management.base import BaseCommand

from biblioteca.avisos import DIAS_DE_ANTICIPACION, enviar_avisos
from biblioteca.models import AvisoPrestamo


def linea(prestamo):
    persona = prestamo.persona
    return (f'  - {persona} ({persona.documento}) · {prestamo.ejemplar.codigo_inventario} '
            f'"{prestamo.ejemplar.libro.titulo}" · vence {prestamo.fecha_vencimiento:%d/%m/%Y}')


class Command(BaseCommand):
    help = (f'Envía los avisos por correo de préstamos que vencen en {DIAS_DE_ANTICIPACION} días o menos y de '
            'préstamos vencidos. Cada aviso se envía una sola vez.')

    def add_arguments(self, parser):
        parser.add_argument('--simular', action='store_true', help='Muestra qué enviaría, sin enviar ni registrar nada.')

    def handle(self, *args, simular, **options):
        resultado = enviar_avisos(simular=simular)
        escribir = self.stdout.write
        if simular:
            escribir(self.style.WARNING('MODO SIMULACIÓN: no se envió ni se registró nada.'))
        verbo = 'Se enviarían' if simular else 'Enviados'
        for tipo in AvisoPrestamo.Tipo:
            prestamos = resultado.enviados[tipo]
            escribir(f'{verbo} "{tipo.label}": {len(prestamos)}')
            for prestamo in prestamos:
                escribir(linea(prestamo))
        if resultado.sin_correo:
            escribir(f'Sin cuenta activa o sin correo (no se avisa): {len(resultado.sin_correo)}')
            for prestamo in resultado.sin_correo:
                escribir(linea(prestamo))
        if resultado.fallidos:
            self.stderr.write(self.style.ERROR(
                f'No se pudieron enviar: {len(resultado.fallidos)}. Se van a reintentar la próxima vez.'
            ))
            for prestamo in resultado.fallidos:
                self.stderr.write(linea(prestamo))
        total = resultado.total_enviados
        resumen = f'Total: {total} aviso{"" if total == 1 else "s"} {"para enviar" if simular else "enviado" + ("" if total == 1 else "s")}.'
        escribir(self.style.SUCCESS(resumen) if not resultado.fallidos else resumen)
