# SIGEBI — Sistema de Gestión de Biblioteca

Sistema web para la biblioteca de la **UTN Facultad Regional Tucumán, Extensión Áulica Concepción**.
Trabajo Final Integrador de la Tecnicatura Universitaria en Programación (Plan 2024).

- **Release 1 — Biblioteca física** (Sprints 1 a 6): catálogo (categorías, autores, editoriales, libros y
  ejemplares), personas, préstamos y devoluciones, préstamos vencidos, cuentas del personal con roles,
  importación del inventario en Excel e informes exportables.
- **Release 2 — Biblioteca virtual** (Sprints 7 y 8): portal para estudiantes y docentes con el catálogo y el
  material digital de sus carreras, material compartido con aprobación de la biblioteca, reservas de libros
  físicos, opiniones, código QR en cada ejemplar, avisos automáticos por correo, informe de demanda, informes
  en PDF y publicación en internet (Railway).

Documentación:

- [Manual de usuario](docs/manual-de-usuario.md), con capturas: parte del personal y parte de estudiantes y docentes.
- [Documentación técnica](docs/documentacion-tecnica.md): arquitectura, modelo de datos, reglas y decisiones.
- [Evidencias de pruebas](docs/evidencias-de-pruebas.md).
- [Evaluación económica](docs/evaluacion-economica.md).
- [Publicación en Railway](docs/despliegue-railway.md): cómo se publica el sistema en internet.

---

## 1. Requisitos

| Herramienta | Versión usada |
|---|---|
| Python | 3.13 |
| PostgreSQL | 16 |
| Django | 5.2.18 (se instala con `requirements.txt`) |
| Git | cualquier versión reciente |

## 2. Instalación

Los comandos se ejecutan desde la carpeta `SIGEBI/` del repositorio (la que tiene `manage.py`).

### 2.1. Clonar y crear el entorno virtual

```bash
git clone https://github.com/SuarezMilagros/Biblioteca-UTN.git
cd Biblioteca-UTN/SIGEBI
python -m venv .venv
```

Activar el entorno:

- macOS / Linux: `source .venv/bin/activate`
- Windows (PowerShell): `.venv\Scripts\Activate.ps1`

Instalar dependencias:

```bash
pip install -r requirements.txt
```

### 2.2. Crear la base de datos

Con un usuario administrador de PostgreSQL (por ejemplo `postgres`):

```sql
CREATE USER sigebi_user WITH PASSWORD 'elegí-una-contraseña' CREATEDB;
CREATE DATABASE sigebi OWNER sigebi_user;
```

`CREATEDB` hace falta para correr las pruebas: `manage.py test` crea una base temporal `test_sigebi`
y la borra al terminar. Si el usuario ya existe: `ALTER USER sigebi_user CREATEDB;`

La búsqueda sin tildes ("calculo" encuentra "Cálculo") usa la extensión `unaccent` de PostgreSQL.
La crea la migración `biblioteca.0006` cuando `sigebi_user` es dueño de la base, como arriba.
Si `migrate` falla con un error de permisos sobre `unaccent`, crearla una vez con el usuario administrador:

```sql
\c sigebi
CREATE EXTENSION IF NOT EXISTS unaccent;
```

### 2.3. Configurar el archivo `.env`

Copiar `SIGEBI/.env.example` como `SIGEBI/.env` y completar los valores. **El `.env` nunca se sube a Git.**

| Variable | Para qué sirve |
|---|---|
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | Conexión a PostgreSQL. |
| `DJANGO_SECRET_KEY` | Clave secreta de Django. Cada integrante genera la suya (ver abajo). |
| `DJANGO_DEBUG` | `True` en desarrollo, `False` en producción. |
| `DJANGO_ALLOWED_HOSTS` | Dominios que atiende el sistema, separados por coma. Con `DJANGO_DEBUG=True` puede quedar vacía. |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_USE_SSL`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL` | Correo real (ver sección 5). Si `EMAIL_HOST` queda vacía, los correos se muestran en la consola. |
| `MATERIAL_DIGITAL_ROOT` | Carpeta **no pública** de los PDF del material digital y de las fotos de perfil. Vacía: `SIGEBI/material_privado`. |
| `MEDIA_ROOT` | Carpeta de las portadas de los libros. Vacía: `SIGEBI/media`. |
| `DATABASE_URL`, `DJANGO_HTTPS`, `BREVO_API_KEY`, `SIGEBI_ADMIN_*`, `SIGEBI_DATOS_DEMO` | Solo en el servidor publicado (ver [Publicación en Railway](docs/despliegue-railway.md)). En una PC del equipo quedan vacías. |

Generar una clave secreta nueva:

```bash
python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
```

> **Rotación de la clave (decisión D7):** en el historial de Git quedó una clave de desarrollo antigua.
> No se reescribe el historial: cada integrante genera una clave nueva con el comando anterior y la
> pega en su `.env`. Al cambiarla, las sesiones abiertas se cierran y hay que volver a ingresar.

### 2.4. Migraciones y superusuario

```bash
python manage.py migrate
python manage.py createsuperuser
```

Al crear el superusuario **hay que cargar el correo**: el sistema inicia sesión por correo electrónico,
así que un superusuario sin correo no puede ingresar. El "nombre de usuario" que pide Django es el
número de documento.

`migrate` crea también:

- los grupos **Administrativo**, **Bibliotecario** y **Lector** (estudiantes y docentes) con sus permisos;
- las **10 carreras** de la Extensión Áulica (7 de pregrado y 3 de grado);
- si el inventario ya está cargado, las carreras de cada categoría del inventario real (migración `biblioteca.0012`).

### 2.5. Datos de prueba (opcional)

```bash
python manage.py cargar_datos_prueba
```

Carga categorías, autores, editoriales, libros, ejemplares, personas y préstamos de ejemplo.
Se puede ejecutar varias veces sin duplicar datos.

Para probar el portal de estudiantes y docentes con esos datos: asignar carreras a las categorías
(**Categorías → Editar**) y a una persona (**Personas → Editar**), y crearle la cuenta desde su ficha
(**Cuenta para el portal → Crear cuenta**). Sin `EMAIL_HOST`, el enlace para definir la contraseña aparece en la
consola de `runserver`.

### 2.6. Ejecutar

```bash
python manage.py runserver
```

Abrir <http://127.0.0.1:8000/> e ingresar con el correo y la contraseña del superusuario.
El superusuario crea las cuentas del personal desde **Cuentas** (ver el manual de usuario).

## 3. Pruebas

```bash
python manage.py test
```

Resultado esperado: **888 pruebas, OK** (tarda unos minutos). El detalle está en
[Evidencias de pruebas](docs/evidencias-de-pruebas.md).

## 4. Roles

| Rol | Puede |
|---|---|
| **Bibliotecario** | Catálogo, carreras, material digital, personas y sus cuentas del portal, préstamos, devoluciones, reservas, opiniones e informes. Cambiar su contraseña. |
| **Administrativo** | Todo lo del Bibliotecario, y además crear y editar cuentas de Bibliotecarios. |
| **Superusuario** | Todo, incluidas las cuentas Administrativas y el panel de administración de Django (`/admin/`). |
| **Lector** (alumno o profesor) | Solo el portal (`/portal/`): catálogo y material de **sus carreras**, reservas, opiniones, compartir material y su perfil. |

Los permisos se controlan en el servidor: escribir una dirección a mano no saltea el control (responde 403).
Un lector que escribe la dirección de un libro o material de otra carrera recibe "no encontrado".
No hay eliminación física de cuentas: se desactivan.

## 5. Correo real (decisión D-C6)

Se usa SMTP (por ejemplo, Gmail con una **contraseña de aplicación**). En el `.env` de quien tenga la cuenta:

```
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
EMAIL_HOST_USER=cuenta-de-la-biblioteca@gmail.com
EMAIL_HOST_PASSWORD=la-contraseña-de-aplicación
DEFAULT_FROM_EMAIL=SIGEBI <cuenta-de-la-biblioteca@gmail.com>
```

La contraseña va **solo** en el `.env`: nunca en Git ni en mensajes. Para comprobar la configuración:

```bash
python manage.py probar_correo tu-correo@ejemplo.com
```

El comando informa si el correo se envió o por qué falló, sin mostrar la contraseña.
Los enlaces para definir o recuperar la contraseña vencen en una hora.

En el servidor publicado (Railway) el SMTP está bloqueado: los correos salen por la API de **Brevo** con la
variable `BREVO_API_KEY` (si está, se usa en lugar de `EMAIL_HOST`). Ver `docs/despliegue-railway.md`.

## 6. Cargar el inventario desde Excel (Sprint 6)

El inventario que la biblioteca llevaba en Excel (una fila por ejemplar, con las columnas ID, NOMBRE, AUTOR,
CATEGORÍA, EDITORIAL, NUMERACIÓN, ISBN, OBSERVACIONES, FECHA DE INVENTARIO y Estado) se carga con un comando.
**Primero se corre en modo prueba**, que no guarda nada y muestra qué haría:

```bash
python manage.py importar_inventario ruta/al/inventario.xlsx
```

Con `--detalle` lista además cada aviso y los autores que se van a crear, para revisar cómo se separaron
nombre y apellido. Si el resultado es correcto, se guarda:

```bash
python manage.py importar_inventario ruta/al/inventario.xlsx --guardar
```

- Se puede correr varias veces: los ejemplares cuyo código ya existe se omiten.
- Las filas con problemas (ID o numeración repetidos, una celda con dos numeraciones, sin título o sin
  categoría) se **rechazan y se listan** con su número de fila; el resto se carga. Se corrigen en el Excel y se vuelve a importar.
- Los ejemplares sin numeración reciben un código provisorio `SN-<ID>` (por ejemplo, `SN-0045`), que se
  puede cambiar después desde **Ejemplares** cuando tengan su número físico.
- Los que en el Excel figuran como **prestados** se cargan disponibles y se listan: el préstamo se registra en
  SIGEBI con la persona y las fechas reales.
- Las reglas completas están en la [documentación técnica](docs/documentacion-tecnica.md), sección 11.

Conviene probarlo primero en una base de prueba (otra base en el `.env`) antes de la base definitiva.

## 7. Avisos automáticos por correo (S8-06)

Los correos "tu préstamo vence pronto" (2 días antes o menos) y "tu préstamo venció" los envía un comando:

```bash
python manage.py enviar_avisos --simular
python manage.py enviar_avisos
```

Con `--simular` solo muestra a quién se enviarían, sin enviar nada. Cada aviso se envía **una sola vez** por
préstamo y tipo, así que el comando se puede ejecutar varias veces en el día sin repetir correos. Solo se avisa
a personas con cuenta activa en el portal.

En el servidor se programa **una vez por día**:

- **Railway:** un segundo servicio del repositorio como *Cron Job* (ver [Publicación en Railway](docs/despliegue-railway.md)).
- **Linux:** con `cron`, por ejemplo `0 8 * * * cd /ruta/SIGEBI && .venv/bin/python manage.py enviar_avisos`.
- **Windows:** con el Programador de tareas, ejecutando `.venv\Scripts\python.exe manage.py enviar_avisos` desde la carpeta `SIGEBI`.

## 8. Otros comandos

| Comando | Para qué |
|---|---|
| `python manage.py probar_correo destino@ejemplo.com` | Comprueba la configuración del correo (sección 5). |
| `python manage.py importar_inventario archivo.xlsx [--guardar]` | Carga el inventario en Excel (sección 6). |
| `python manage.py cargar_datos_prueba` | Datos ficticios de prueba (sección 2.5). |
| `python manage.py preparar_sitio` | Solo en el servidor: migraciones, cuenta de administración y datos de prueba antes de cada publicación. |

## 9. Cambios de la Release 2

Para quien ya tenía instalada la Release 1, después de `git pull origin main`:

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py test
```

- **Dependencias nuevas:** `segno` (código QR), `fpdf2` con `defusedxml` y `fonttools` (informes en PDF), y
  `django-anymail`, `gunicorn` y `whitenoise` con las suyas (servidor publicado; en Windows gunicorn se instala
  pero no se usa).
- **Migraciones nuevas:** `biblioteca.0010` a `0019` y `cuentas.0003` (carreras, cuentas de lectores, material
  digital, reservas, avisos, opiniones, tipo de ejemplar y fotos de perfil).
- **Aplicación nueva:** `portal`, para estudiantes y docentes.
- **Carpeta nueva:** la de `MATERIAL_DIGITAL_ROOT` (por defecto `SIGEBI/material_privado`), que no se sube a Git
  y hay que incluir en las copias de seguridad junto con la base de datos.

## 10. Estructura del proyecto

```
Biblioteca-UTN/
├── README.md
├── docs/                     Manual, documentación técnica, pruebas, evaluación económica y capturas
└── SIGEBI/
    ├── manage.py
    ├── requirements.txt
    ├── .env.example          Plantilla de configuración (el .env real no se versiona)
    ├── config/               Configuración del proyecto (settings, urls, admin solo para superusuarios)
    ├── iniciar_servidor.sh   Arranque en el servidor publicado (collectstatic y gunicorn)
    ├── config/               Configuración del proyecto (settings, entorno.py, urls, admin solo para superusuarios)
    ├── biblioteca/           Sistema del personal: catálogo, carreras, personas, préstamos, reservas,
    │   │                     material digital, opiniones e informes
    │   ├── models.py         Entidades y restricciones de integridad
    │   ├── forms.py          Validaciones de los formularios
    │   ├── views.py          Pantallas y reglas de cada operación
    │   ├── reservas.py       Reglas de las reservas (reservar, confirmar, retirar, vencer)
    │   ├── revision_de_material.py, opiniones.py, avisos.py, demanda.py, qr.py
    │   │                     Reglas del material compartido, opiniones, avisos, demanda y QR
    │   ├── informes.py       Exportación CSV y PDF
    │   ├── importacion.py    Importación del inventario en Excel
    │   ├── management/commands/  importar_inventario, cargar_datos_prueba, enviar_avisos, preparar_sitio
    │   ├── migrations/
    │   ├── templates/
    │   └── tests/
    ├── portal/               Portal de estudiantes y docentes (catálogo, material, préstamos, reservas, perfil)
    ├── cuentas/              Cuentas, roles, login por correo, límite de intentos, cuentas de lectores, Mi perfil
    ├── interfaz/             Íconos y filtros de presentación compartidos (sin modelos)
    ├── templates/            Plantilla base, componentes compartidos, login, contraseñas y página 403
    └── static/               CSS y JavaScript
```

## 11. Flujo de trabajo del equipo

- Cada integrante trabaja en su rama (`emmanuel`, `milagros`, …) y los cambios llegan a `main` por Pull Request.
- Antes de empezar a trabajar: `git pull origin main`, `python manage.py migrate` y `python manage.py test`.
- Nunca se suben `.env`, archivos `.patch`, `staticfiles/`, `material_privado/` ni `.DS_Store` (están en `.gitignore`).

## 12. Limitaciones conocidas

- **Publicación:** SIGEBI se publica en Railway con HTTPS, gunicorn y WhiteNoise; los pasos están en
  `docs/despliegue-railway.md` (S8-09). Las portadas las sirve Django: alcanza para la biblioteca, pero con
  mucho tráfico convendría un almacenamiento de archivos aparte.
- **Sesión:** dura 8 horas; después hay que volver a ingresar.
- **Varios autores:** un libro tiene un solo autor; en el inventario importado los demás quedan en las
  observaciones del ejemplar.
- **Correo en el servidor publicado:** Brevo gratis reemplaza el remitente Gmail por una dirección suya y envía
  hasta 300 correos por día.
