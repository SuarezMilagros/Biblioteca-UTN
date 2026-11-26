"""Límite de intentos de acceso (Release 2, R2-01).

- Ingreso: con 5 ingresos fallidos en 15 minutos para un mismo correo, ese correo queda bloqueado
  hasta que el primero de esos fallos tenga más de 15 minutos. Lo mismo con 20 fallos desde una
  misma IP, para quien prueba muchos correos distintos.
- Recuperación de contraseña: como máximo 3 pedidos por hora para un mismo correo y 10 desde una IP.
- Los correos inexistentes cuentan igual, así el bloqueo no revela qué cuentas existen.
- Un ingreso correcto borra los fallos de ese correo.

IP detrás del proxy de Railway (S8-09, 26/11/2026): todos los pedidos llegan desde el proxy, así que REMOTE_ADDR
es la misma para todo el mundo y 20 fallos de cualquier persona bloqueaban el ingreso de todas. En el servidor
publicado (CABECERA_IP_DEL_CLIENTE en la configuración) se toma la IP que el proxy de Railway pone en X-Real-IP:
el proxy reemplaza esa cabecera en cada pedido, así que el visitante no la puede inventar. Fuera de ese caso
(PC del equipo, sin proxy) la cabecera se ignora, porque cualquiera la podría mandar.
"""
import ipaddress
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import IntentoDeAcceso

INGRESO_MINUTOS = 15
INGRESO_MAXIMO_POR_CORREO = 5
INGRESO_MAXIMO_POR_IP = 20
RECUPERACION_MINUTOS = 60
RECUPERACION_MAXIMO_POR_CORREO = 3
RECUPERACION_MAXIMO_POR_IP = 10


def ip_valida(valor):
    try:
        return str(ipaddress.ip_address((valor or '').strip()))
    except ValueError:
        return None


def ip_de(request):
    """IP de quien hace el pedido: la que informa el proxy de confianza, si lo hay; si no, REMOTE_ADDR."""
    if request is None:
        return None
    cabecera = getattr(settings, 'CABECERA_IP_DEL_CLIENTE', None)
    if cabecera:
        ip = ip_valida(request.META.get(cabecera))
        if ip:
            return ip
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