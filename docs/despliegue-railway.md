# SIGEBI — Publicación en Railway (S8-09)

Guía para publicar SIGEBI en internet, para que la profesora (o cualquiera con el enlace) lo pueda usar.
Se usa **Railway** (servidor y base de datos) y **Brevo** (envío de correos). Los dos tienen planes gratuitos.

> **Seguridad.** Las claves (de Django, de Brevo, de la cuenta de administración) se escriben **solo** en el
> panel de Railway. Nunca en el código, en un mensaje, en una captura ni en el chat.

## Qué se arma

```
GitHub (rama main) ──► Railway: servicio "SIGEBI" ──► https://sigebi-production.up.railway.app
                               │  gunicorn + Django (iniciar_servidor.sh)
                               │  volumen /data: portadas, PDF del material, fotos
                               ├─► Railway: base PostgreSQL
                               └─► Brevo (API por HTTPS): correos de alta, recuperación y avisos
```

- Cada vez que se integra un PR en `main`, Railway publica la versión nueva sola.
- Antes de cada publicación corre `python manage.py preparar_sitio`: aplica las migraciones, crea la cuenta de
  administración (si no existe) y, si se pide, carga los datos de prueba.
- **Por qué Brevo:** Railway bloquea el envío por SMTP (Gmail) en los planes Trial, Free y Hobby. Brevo envía
  por HTTPS, que no está bloqueado.

## Costos y límites (noviembre de 2026)

| Servicio | Plan | Qué incluye | Límite que importa |
|---|---|---|---|
| Railway | **Trial** | USD 5 de crédito por 30 días | Al vencer pasa a Free (USD 1/mes): el sitio se apaga a los pocos días. Los volúmenes de una cuenta Trial se borran 30 días después de vencido el crédito. |
| Railway | Hobby | USD 5/mes | Sin vencimiento. Pasar a Hobby **antes** de que venza el Trial para no perder nada. |
| Brevo | Gratis | 300 correos por día | El remitente Gmail se reemplaza por una dirección de Brevo (ver Paso 1). |

---

## Paso 0. Requisito: el código en `main`

Este despliegue necesita los cambios del ZIP `sigebi-despliegue-railway.zip` ya integrados en `main`
(gunicorn, WhiteNoise, Brevo, `preparar_sitio` e `iniciar_servidor.sh`).

## Paso 1. Brevo (correo)

1. Crear una cuenta gratis en **https://www.brevo.com** (con el correo de la biblioteca o del equipo).
   Completar el perfil que pide al entrar (nombre, organización: «Biblioteca UTN FRT Concepción»).
2. **Remitente:** menú del perfil (arriba a la derecha) › **Senders, Domains & Dedicated IPs** › **Senders** ›
   **Add a sender**.
   - From name: `SIGEBI`
   - From email: el Gmail de SIGEBI (el mismo de `DEFAULT_FROM_EMAIL` en sus `.env`).
   - Brevo manda un código de 6 dígitos a ese Gmail: ingresarlo para verificarlo.
   - **Aviso:** Brevo no permite autenticar dominios gratuitos como gmail.com, así que al enviar reemplaza la
     dirección por una suya (del tipo `…@…t-sender-sib.com`). El nombre «SIGEBI» se mantiene. Para la
     demostración alcanza; para que salga con una dirección propia hace falta un dominio.
3. **Clave de la API:** menú del perfil › **SMTP & API** › pestaña **API Keys** › **Generate a new API key**.
   Nombre: `sigebi-railway`. **Copiarla en ese momento** (después no se vuelve a mostrar) y guardarla solo
   hasta pegarla en Railway (Paso 4).

## Paso 2. Railway: proyecto, base de datos y servicio

1. Entrar a **https://railway.com** con la cuenta de GitHub. Si Railway indica que la prueba está limitada
   («Limited Trial»), seguir sus indicaciones para verificar la cuenta.
2. **New Project** › **Deploy from GitHub repo** › elegir `SuarezMilagros/Biblioteca-UTN`.
   - Si el repositorio no aparece, hay que darle acceso a Railway en GitHub. Como el repositorio es de
     Milagros, GitHub le pide a ella que apruebe la instalación de la app de Railway: **Milagros tiene que
     aceptar** ese pedido (le llega por mail o en GitHub › Settings › Applications).
   - El primer intento de publicación va a fallar: todavía falta la configuración. Es normal.
3. **Base de datos:** en el proyecto, **+ Create** (o **New**) › **Database** › **PostgreSQL**. Se crea un
   servicio «Postgres». No hace falta tocar nada.

## Paso 3. Configuración del servicio SIGEBI

Hacer clic en el servicio del repositorio (no en Postgres) › **Settings**:

| Sección | Campo | Valor |
|---|---|---|
| Source | **Root Directory** | `/SIGEBI` |
| Source | Branch | `main` |
| Deploy | **Pre-deploy Command** | `python manage.py preparar_sitio` |
| Deploy | **Custom Start Command** | `sh iniciar_servidor.sh` |
| Deploy | Restart Policy | On Failure (el que viene) |

**Volumen** (para que las portadas, los PDF y las fotos no se borren en cada publicación): en el lienzo del
proyecto, clic derecho sobre el servicio SIGEBI › **Attach Volume** (o `Ctrl + K` › «Volume»).
**Mount path: `/data`**.

## Paso 4. Variables del servicio SIGEBI

Servicio SIGEBI › **Variables** › **Raw Editor**. Pegar esto y **completar** lo que está entre `<...>`:

```
DATABASE_URL=${{Postgres.DATABASE_URL}}
DJANGO_SECRET_KEY=<clave secreta nueva, ver abajo>
DJANGO_DEBUG=False
DJANGO_HTTPS=True
MEDIA_ROOT=/data/media
MATERIAL_DIGITAL_ROOT=/data/privado
BREVO_API_KEY=<la clave de Brevo del Paso 1>
DEFAULT_FROM_EMAIL=SIGEBI <el-gmail-de-sigebi@gmail.com>
SIGEBI_ADMIN_CORREO=<correo para entrar como administración>
SIGEBI_ADMIN_CLAVE=<contraseña de al menos 8 caracteres, no solo números ni muy común>
SIGEBI_DATOS_DEMO=True
```

- `DATABASE_URL=${{Postgres.DATABASE_URL}}` se escribe **tal cual**: Railway lo reemplaza por la conexión a la
  base del Paso 2 (si el servicio de la base tiene otro nombre, usar ese nombre en lugar de `Postgres`).
- **Clave secreta nueva** (no usar la del `.env` de nadie). En una PC del equipo, con el entorno virtual activo:
  ```
  python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
  ```
  copiar el resultado y pegarlo en `DJANGO_SECRET_KEY`.
- `DJANGO_ALLOWED_HOSTS` no hace falta: la dirección pública de Railway se agrega sola.
- `SIGEBI_DATOS_DEMO=True` carga libros, ejemplares, personas y préstamos ficticios para mostrar el sistema.
  Si van a cargar el inventario real, ponerla en `False` (o borrarla) antes.

Guardar (**Update Variables** / **Deploy**). Railway vuelve a publicar.

## Paso 5. Dirección pública

Servicio SIGEBI › **Settings** › **Networking** › **Generate Domain**. Si pide un puerto, poner el que aparece
en **Deploy Logs** en la línea `Listening at: http://0.0.0.0:XXXX` (normalmente `8080`).

Queda una dirección del tipo `https://sigebi-production.up.railway.app`.

## Paso 6. Comprobar

1. **Deployments** › la última publicación tiene que quedar en verde (**Active / Success**).
   En **Deploy Logs** se ve, en orden:
   - `Cuenta de administración creada: ...` y `Sitio preparado.` (del Pre-deploy)
   - `... static files copied ...` y `Listening at: http://0.0.0.0:...` (del arranque)
2. Abrir la dirección: tiene que aparecer la pantalla de ingreso de SIGEBI, con candado (HTTPS).
3. Entrar con `SIGEBI_ADMIN_CORREO` y `SIGEBI_ADMIN_CLAVE`.
4. **Correo:** en SIGEBI, **Cuentas › Nueva cuenta**, crear una cuenta de bibliotecario con un correo propio.
   Tiene que llegar el mail «definí tu contraseña» (mirar también en Spam). Otra forma: servicio SIGEBI › menú
   «⋯» › consola (si está disponible) y `python manage.py probar_correo tu-correo@ejemplo.com`.
5. **Archivos:** subir una portada a un libro y volver a publicar (Deployments › Redeploy): la portada sigue.

## Paso 7. Después del primer ingreso

1. En SIGEBI, **Cambiar contraseña** de la cuenta de administración.
2. En Railway › Variables, **borrar `SIGEBI_ADMIN_CLAVE`** (ya no hace falta; la cuenta existente no se toca).
3. **Para la profesora:** crearle una cuenta desde **Cuentas › Nueva cuenta** (rol Bibliotecario o
   Administrativo). Le llega el mail para definir su contraseña.

## Problemas frecuentes

| Qué se ve | Causa | Qué hacer |
|---|---|---|
| Deploy Logs: `Falta DJANGO_SECRET_KEY` | No se cargó la variable | Paso 4 |
| Pre-deploy: `SIGEBI_ADMIN_CLAVE no sirve: ...` | La contraseña es muy corta, muy común o solo números | Elegir otra y volver a publicar |
| Pre-deploy: `connection ... failed` / `could not translate host name` | `DATABASE_URL` mal escrita o el servicio de la base se llama distinto | Paso 4: `${{Postgres.DATABASE_URL}}` con el nombre real |
| `Bad Request (400)` al abrir la dirección | La dirección no está en los hosts permitidos (por ejemplo, un dominio propio) | Agregarla en `DJANGO_ALLOWED_HOSTS` |
| La página se ve sin estilos | No corrió `collectstatic` | Revisar que el Start Command sea `sh iniciar_servidor.sh` |
| «No se pudo enviar el correo» | Clave de Brevo mal copiada o remitente sin verificar | Paso 1; en Deploy Logs aparece el detalle |
| Las portadas desaparecen al publicar | No hay volumen o el Mount path no es `/data` | Paso 3 |
| `Root Directory` / `manage.py not found` | Falta `/SIGEBI` como Root Directory | Paso 3 |

## Avisos automáticos de préstamos (opcional)

Los avisos por correo de préstamos por vencer y vencidos (S8-06) se envían con
`python manage.py enviar_avisos`. En Railway se puede programar como **Cron Job**: un segundo servicio del mismo
repositorio, con las mismas variables (sin volumen), Root Directory `/SIGEBI`, Start Command
`python manage.py enviar_avisos` y Cron Schedule `0 11 * * *` (todos los días a las 8:00 de Argentina; Railway usa
hora UTC). Consume crédito del Trial: activarlo solo si hace falta para la demostración.

## Qué hace cada archivo

| Archivo | Para qué |
|---|---|
| `SIGEBI/iniciar_servidor.sh` | `collectstatic` y arranque de gunicorn en el puerto que indica Railway |
| `SIGEBI/biblioteca/management/commands/preparar_sitio.py` | Migraciones, cuenta de administración y datos de prueba (Pre-deploy) |
| `SIGEBI/config/entorno.py` | Lee la configuración de las variables de entorno (base, HTTPS, correo) |
| `SIGEBI/.python-version` | Railway usa Python 3.13 |
| `SIGEBI/.gitattributes` | El script `.sh` siempre con fin de línea de Linux, aunque se edite en Windows |
