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
- **Límite de intentos:** detrás del proxy de Railway, SIGEBI toma la IP del visitante de `X-Real-IP` (el proxy
  la reemplaza en cada pedido); así los intentos fallidos de una persona no bloquean a las demás.

## Costos y límites (noviembre de 2026)

| Servicio | Plan | Qué incluye | Límite que importa |
|---|---|---|---|
| Railway | **Trial** | USD 5 de crédito por 30 días | Al vencer pasa a Free (USD 1/mes): el sitio se apaga a los pocos días. Los volúmenes de una cuenta Trial se borran 30 días después de vencido el crédito. |
| Railway | Hobby | USD 5/mes | Sin vencimiento. Pasar a Hobby **antes** de que venza el Trial para no perder nada. |
| Brevo | Gratis | 300 correos por día | El remitente Gmail se reemplaza por una dirección de Brevo (ver Paso 1). |

---

## Paso 0. Requisito: el código en `main`

Este despliegue necesita en `main` los cambios del S8-09 (gunicorn, WhiteNoise, Brevo, `preparar_sitio` e
`iniciar_servidor.sh`). Railway publica siempre desde `main`.

> **Publicado el 25/11/2026** en `https://biblioteca-utn-production.up.railway.app` (cuenta de Milagros, plan
> Trial). Esta guía quedó escrita en el orden que funcionó, con los tropiezos de ese día en «Problemas frecuentes».

## Paso 1. Brevo (correo)

1. Crear una cuenta gratis en **https://www.brevo.com** y completar el perfil que pide al entrar
   (organización: «Biblioteca UTN FRT Concepción»).
2. **Remitente:** Configuración (engranaje, abajo a la izquierda) › **Remitentes, dominios e IP dedicadas** ›
   **Remitentes** › **Añadir remitente**.
   - Nombre: `SIGEBI` · Email: el Gmail de SIGEBI.
   - Brevo manda un código de 6 dígitos a ese Gmail: ingresarlo para verificarlo.
   - Brevo no permite autenticar dominios gratuitos como gmail.com: al enviar reemplaza la dirección por una
     suya (del tipo `…@…t-sender-sib.com`). El nombre «SIGEBI» se mantiene. Es normal.
3. **Clave de la API:** Configuración › **SMTP y API** › pestaña **Claves API** (*no* la pestaña SMTP) ›
   **Generar una nueva clave API**, nombre `sigebi-railway`.
   - **Tiene que empezar con `xkeysib-`.** Si empieza con `xsmtpsib-` es la clave SMTP: no sirve (Railway
     bloquea el SMTP).
   - Copiarla en ese momento (no se vuelve a mostrar) y guardarla solo hasta pegarla en Railway.
4. Si al probar Brevo rechaza la clave aunque sea `xkeysib-`: perfil › **Seguridad** › **IP autorizadas** ›
   desactivar el bloqueo de IP desconocidas (la IP de Railway cambia, no conviene cargar una fija).

## Paso 2. Railway: proyecto y base de datos

1. Entrar a **https://railway.com** con la cuenta de GitHub **de quien es dueño del repositorio** (Milagros):
   así autoriza el acceso en el momento. Con otra cuenta, GitHub le pide a la dueña que apruebe la app.
2. **New Project** › **Deploy from GitHub repo** › `SuarezMilagros/Biblioteca-UTN`. El primer intento falla
   («Build failed»): todavía falta la configuración. Es normal.
3. **+ Create** › **Database** › **PostgreSQL**. Aparece el servicio «Postgres»: no se toca.

## Paso 3. Configuración del servicio SIGEBI (antes de las variables)

Clic en el servicio del repositorio (no en Postgres) › **Settings**:

| Sección | Campo | Valor |
|---|---|---|
| Source | **Root Directory** | `/SIGEBI` |
| Source | Branch | `main` |
| Deploy | **Pre-deploy Command** | `python manage.py preparar_sitio` |
| Deploy | **Custom Start Command** | `sh iniciar_servidor.sh` |
| Networking | **Generate Domain** | puerto **`8080`** |

- **Generar la dirección ahora**, antes de publicar: SIGEBI la lee al arrancar (`RAILWAY_PUBLIC_DOMAIN`). Si se
  genera después, la página da «Solicitud incorrecta (400)» hasta la próxima publicación (ver Problemas).
- **Volumen:** clic derecho sobre el servicio en el lienzo › **Attach Volume** › Mount path **`/data`**.

Railway junta los cambios en un aviso «Apply N changes» arriba a la izquierda: todavía **no** tocar Deploy.

## Paso 4. Variables del servicio SIGEBI

Servicio SIGEBI › **Variables** › **Raw Editor**. Cada línea es `NOMBRE="valor"`:

```
DATABASE_URL="${{Postgres.DATABASE_URL}}"
DJANGO_SECRET_KEY="(clave secreta nueva)"
DJANGO_DEBUG="False"
DJANGO_HTTPS="True"
DJANGO_ALLOWED_HOSTS="biblioteca-utn-production.up.railway.app"
MEDIA_ROOT="/data/media"
MATERIAL_DIGITAL_ROOT="/data/privado"
BREVO_API_KEY="(clave de la API de Brevo, empieza con xkeysib-)"
DEFAULT_FROM_EMAIL="SIGEBI <el-gmail-verificado-en-brevo@gmail.com>"
SIGEBI_ADMIN_CORREO="(correo para entrar como administración)"
SIGEBI_ADMIN_CLAVE="(contraseña: 8 o más caracteres, con letras y números)"
SIGEBI_DATOS_DEMO="True"
```

**Reglas (todos los errores del primer día fueron por esto):**
- Reemplazar **todo** el texto entre paréntesis por el dato real, **sin dejar `( )` ni `< >`**.
  La única que lleva `< >` es `DEFAULT_FROM_EMAIL`, porque es su formato: `SIGEBI <correo>`.
- `DATABASE_URL` va **tal cual**: Railway reemplaza `${{Postgres.DATABASE_URL}}` por la conexión a la base.
- `DJANGO_ALLOWED_HOSTS`: la dirección generada en el Paso 3, sin `https://` ni `/` al final.
- **Clave secreta:** una nueva, sin símbolos (los `#` o `$` pueden cortarse en el editor). En una PC del equipo:
  ```
  python -c "import secrets; print(secrets.token_urlsafe(50))"
  ```
- `SIGEBI_ADMIN_CLAVE` es la contraseña **exacta** de la cuenta que se crea la primera vez (si quedan `< >`,
  la contraseña los incluye). Después no se usa más: `preparar_sitio` nunca cambia una cuenta existente.
- `SIGEBI_DATOS_DEMO="True"` carga datos ficticios para mostrar el sistema; para el inventario real, `False`.

**Update Variables** y recién ahí **Deploy** en el aviso «Apply N changes». No usar «Redeploy» sobre una
publicación vieja con cambios pendientes: se publicaría sin ellos.

## Paso 5. Comprobar

1. **Deployments** › la publicación nueva (la de arriba) tiene que quedar **Active**. En **Deploy Logs**
   (no Build Logs) se ve: `Cuenta de administración creada: ...`, `Sitio preparado.`, `Mounting volume on ...`,
   `130 static files copied` y `Listening at: http://0.0.0.0:8080`. Las líneas de gunicorn aparecen en rojo
   porque van al canal de errores, pero dicen `[INFO]`: son normales.
2. Abrir la dirección: pantalla de ingreso con candado. Entrar con `SIGEBI_ADMIN_CORREO` y `SIGEBI_ADMIN_CLAVE`.
3. **Correo**, desde la **Console** del servicio (pestaña Console: una terminal dentro del servidor). Ahí
   `python` solo no existe: siempre con la ruta del entorno de Railway:
   ```
   /app/.venv/bin/python manage.py probar_correo tu-correo@gmail.com
   ```
   Tiene que decir `Correo de prueba enviado a ...` y llegar el mail (mirar Spam y Promociones).
4. **Archivos:** subir una portada, **Redeploy** desde Deployments, y comprobar que la portada sigue.

## Paso 6. Después del primer ingreso

1. En SIGEBI, **Cambiar contraseña**.
2. En Railway › Variables, **borrar `SIGEBI_ADMIN_CLAVE`** y Deploy.
3. **Para la profesora:** **Cuentas › Nueva cuenta** (Bibliotecario o Administrativo). Le llega el mail para
   definir su contraseña.
4. **Antes de que venza el Trial (30 días):** pasar a **Hobby** si el sitio tiene que seguir publicado.

## Comandos útiles en la Console de Railway

```
/app/.venv/bin/python manage.py changepassword correo@ejemplo.com   # nueva contraseña para una cuenta
/app/.venv/bin/python manage.py probar_correo correo@ejemplo.com    # prueba el envío por Brevo
/app/.venv/bin/python -c "import os; k=os.environ.get('BREVO_API_KEY',''); print(k[:8], len(k))"   # forma de la clave, sin mostrarla
```

## Problemas frecuentes

| Qué se ve | Causa | Qué hacer |
|---|---|---|
| «Build failed» y en Build Logs aparece la raíz (`SIGEBI/`, `docs/`, `README.md`) | Falta el Root Directory | Paso 3: `/SIGEBI` |
| Pre-deploy: `Falta DJANGO_SECRET_KEY` | Variables no cargadas en este servicio, sin aplicar, o la clave vacía por símbolos | Paso 4: revisar en el servicio SIGEBI (no en Postgres), clave sin símbolos, Deploy |
| Pre-deploy: `SIGEBI_ADMIN_CORREO no es un correo válido: "<...>"` | Quedaron los `< >` | Dejar solo el correo |
| Pre-deploy: `SIGEBI_ADMIN_CLAVE no sirve: ...` | Contraseña corta, común o solo números | Elegir otra |
| Pre-deploy: `could not translate host name` | `DATABASE_URL` mal escrita o la base se llama distinto | `${{Postgres.DATABASE_URL}}` con el nombre real del servicio |
| «Solicitud incorrecta (400)» al abrir la dirección | La dirección se generó después de publicar y no está en los hosts | `DJANGO_ALLOWED_HOSTS` con la dirección, y Deploy |
| «El correo o la contraseña no son correctos» con la cuenta de administración | La contraseña quedó distinta (por ejemplo, con `< >`) | Console: `changepassword` (ver Comandos útiles) |
| «Hubo demasiados intentos fallidos...» | 5 intentos fallidos con ese correo | Esperar 15 minutos |
| `probar_correo`: «Brevo rechazó la clave» | Clave SMTP (`xsmtpsib-`) en lugar de la API (`xkeysib-`), con `< >`, o IP bloqueada | Paso 1.3 y 1.4; corregir la variable y Deploy |
| Console: `python: command not found` | En el servidor Python está en el entorno de Railway | Usar `/app/.venv/bin/python` |
| La página se ve sin estilos | No corrió `collectstatic` | Start Command: `sh iniciar_servidor.sh` |
| Las portadas desaparecen al publicar | Sin volumen o Mount path distinto de `/data` | Paso 3 |
| Errores rojos en la consola del navegador (`/writing`, `/site_integration`) | Son de una extensión del navegador, no de SIGEBI | Ignorarlos |

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
