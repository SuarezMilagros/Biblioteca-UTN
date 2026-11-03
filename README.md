# SIGEBI — Sistema de Gestión de Biblioteca

Sistema web para administrar la biblioteca física de la **UTN Facultad Regional Tucumán, Extensión Áulica Concepción**.
Trabajo Final Integrador de la Tecnicatura Universitaria en Programación (Plan 2024).

**Release 1 — Biblioteca física**: catálogo (categorías, autores, editoriales, libros y ejemplares), personas,
préstamos y devoluciones, préstamos vencidos, cuentas del personal con roles e informes exportables en CSV.
La biblioteca virtual (Release 2) queda fuera de este alcance.

Documentación:

- [Manual de usuario](docs/manual-de-usuario.md), con capturas del sistema.
- [Documentación técnica](docs/documentacion-tecnica.md): arquitectura, modelo de datos, reglas y decisiones.
- [Evidencias de pruebas](docs/evidencias-de-pruebas.md).
- [Evaluación económica](docs/evaluacion-economica.md).

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

`migrate` crea también los grupos **Administrativo** y **Bibliotecario** con sus permisos.

### 2.5. Datos de prueba (opcional)

```bash
python manage.py cargar_datos_prueba
```

Carga categorías, autores, editoriales, libros, ejemplares, personas y préstamos de ejemplo.
Se puede ejecutar varias veces sin duplicar datos.

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

Resultado esperado: **268 pruebas, OK**. El detalle está en [Evidencias de pruebas](docs/evidencias-de-pruebas.md).

## 4. Roles

| Rol | Puede |
|---|---|
| **Bibliotecario** | Catálogo, personas, préstamos, devoluciones e informes. Cambiar su contraseña. |
| **Administrativo** | Todo lo del Bibliotecario, y además crear y editar cuentas de Bibliotecarios. |
| **Superusuario** | Todo, incluidas las cuentas Administrativas y el panel de administración de Django (`/admin/`). |

Los permisos se controlan en el servidor: escribir una dirección a mano no saltea el control (responde 403).
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

## 6. Estructura del proyecto

```
Biblioteca-UTN/
├── README.md
├── docs/                     Manual, documentación técnica, pruebas, evaluación económica y capturas
└── SIGEBI/
    ├── manage.py
    ├── requirements.txt
    ├── .env.example          Plantilla de configuración (el .env real no se versiona)
    ├── config/               Configuración del proyecto (settings, urls, admin solo para superusuarios)
    ├── biblioteca/           Catálogo, personas, préstamos, devoluciones e informes CSV
    │   ├── models.py         Entidades y restricciones de integridad
    │   ├── forms.py          Validaciones de los formularios
    │   ├── views.py          Pantallas y reglas de cada operación
    │   ├── informes.py       Exportación CSV
    │   ├── migrations/
    │   ├── templates/
    │   └── tests/
    ├── cuentas/              Cuentas del personal, roles, login por correo, recuperación de contraseña
    ├── templates/            Plantilla base, login, recuperación de contraseña y página 403
    └── static/               CSS y JavaScript
```

## 7. Flujo de trabajo del equipo

- Cada integrante trabaja en su rama (`emmanuel`, `milagros`, …) y los cambios llegan a `main` por Pull Request.
- Antes de empezar a trabajar: `git pull origin main`, `python manage.py migrate` y `python manage.py test`.
- Nunca se suben `.env`, archivos `.patch`, `staticfiles/` ni `.DS_Store` (están en `.gitignore`).

## 8. Limitaciones conocidas

- **Intentos de ingreso:** no hay límite de intentos fallidos de login. Se decidió no agregar dependencias
  nuevas en Release 1; queda como mejora para un despliegue en producción.
- **HTTPS y despliegue:** la configuración está preparada para desarrollo. Para producción hay que servir el
  sistema con HTTPS, `DJANGO_DEBUG=False`, `DJANGO_ALLOWED_HOSTS` con el dominio real y `collectstatic`.
- **Sesión:** dura 8 horas; después hay que volver a ingresar.
