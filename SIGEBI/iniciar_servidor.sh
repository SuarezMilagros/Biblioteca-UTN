#!/bin/sh
# Arranque de SIGEBI en el servidor (Railway, S8-09).
# En Railway: Settings > Deploy > Custom Start Command = sh iniciar_servidor.sh
# Antes, Railway ya ejecutó "python manage.py preparar_sitio" (migraciones y cuenta de administración).
set -e

# Copia estilos, JavaScript e imágenes a staticfiles/, de donde los sirve WhiteNoise.
python manage.py collectstatic --noinput

# Servidor de producción. Railway indica el puerto en $PORT; 2 procesos alcanzan para la biblioteca.
# --timeout 60: los informes en PDF grandes tienen tiempo de generarse.
exec gunicorn config.wsgi --bind "0.0.0.0:${PORT:-8000}" --workers "${WEB_CONCURRENCY:-2}" \
    --timeout 60 --access-logfile - --error-logfile -
