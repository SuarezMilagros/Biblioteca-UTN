"""Límite de intentos de acceso (Release 2, R2-01).

- Ingreso: con 5 ingresos fallidos en 15 minutos para un mismo correo, ese correo queda bloqueado
  hasta que el primero de esos fallos tenga más de 15 minutos. Lo mismo con 20 fallos desde una
  misma IP, para quien prueba muchos correos distintos.
- Recuperación de contraseña: como máximo 3 pedidos por hora para un mismo correo y 10 desde una IP.
- Los correos inexistentes cuentan igual, así el bloqueo no revela qué cuentas existen.
- Un ingreso correcto borra los fallos de ese correo.
"""
from datetime import timedelta

from django.utils import timezone

from .models import IntentoDeAcceso

INGRESO_MINUTOS = 15
INGRESO_MAXIMO_POR_CORREO = 5
INGRESO_MAXIMO_POR_IP = 20
RECUPERACION_MINUTOS = 60
RECUPERACION_MAXIMO_POR_CORREO = 3
RECUPERACION_MAXIMO_POR_IP = 10


def ip_de(request):
    """IP de quien hace el pedido. Detrás de un proxy (despliegue) hay que revisar de dónde se toma."""
    if request is None:
        return None
    return request.META.get('REMOTE_ADDR') or None


def normalizar(correo):
    return (correo or '').strip().lower()


def cantidad_reciente(tipo, minutos, **filtro):
    desde = timezone.now() - timedelta(minutes=minutos)
    return IntentoDeAcceso.objects.filter(tipo=tipo, fecha__gte=desde, **filtro).count()


def supera_el_limite(tipo, minutos, correo, ip, maximo_por_correo, maximo_por_ip):
    if cantidad_reciente(tipo, minutos, correo=normalizar(correo)) >= maximo_por_correo:
        return True
    return ip is not None and cantidad_reciente(tipo, minutos, ip=ip) >= maximo_por_ip


def ingreso_bloqueado(correo, ip):
    return supera_el_limite(
        IntentoDeAcceso.Tipo.INGRESO_FALLIDO, INGRESO_MINUTOS, correo, ip,
        INGRESO_MAXIMO_POR_CORREO, INGRESO_MAXIMO_POR_IP,
    )


def recuperacion_bloqueada(correo, ip):
    return supera_el_limite(
        IntentoDeAcceso.Tipo.RECUPERACION, RECUPERACION_MINUTOS, correo, ip,
        RECUPERACION_MAXIMO_POR_CORREO, RECUPERACION_MAXIMO_POR_IP,
    )


def registrar(tipo, correo, ip):
    IntentoDeAcceso.objects.create(tipo=tipo, correo=normalizar(correo), ip=ip)


def borrar_fallos_de_ingreso(correo):
    IntentoDeAcceso.objects.filter(
        tipo=IntentoDeAcceso.Tipo.INGRESO_FALLIDO, correo=normalizar(correo)
    ).delete()