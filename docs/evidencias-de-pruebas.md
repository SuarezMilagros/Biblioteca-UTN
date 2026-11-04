# SIGEBI — Evidencias de pruebas

**Release 1 — Biblioteca física.**

## 1. Cómo se ejecutan

Desde la carpeta `SIGEBI/`, con el entorno virtual activo y PostgreSQL funcionando:

```bash
python manage.py test
```

Django crea una base temporal (`test_sigebi`), aplica todas las migraciones, ejecuta las pruebas y borra la base al terminar.
Las pruebas usan la misma base que el sistema (PostgreSQL), no una base en memoria: así se verifican también las
restricciones de integridad y la búsqueda sin tildes (`unaccent`).

## 2. Resultado de referencia

Ejecución de verificación al preparar la documentación (04/11/2026), con Python 3.13, Django 5.2.18 y PostgreSQL 16:

```
Found 318 test(s).
Creating test database for alias 'default'...
System check identified no issues (0 silenced).
----------------------------------------------------------------------
Ran 318 tests

OK
Destroying test database for alias 'default'...
```

> Cada integrante del equipo debe ejecutar la suite en su equipo y registrar su propio resultado (sección 6).

## 3. Pruebas por módulo

### 3.1. Aplicación `biblioteca` (227 pruebas)

| Archivo | Pruebas | Qué verifica |
|---|---|---|
| `test_modelos.py` | 19 | Entidades, relaciones, restricciones de la base y disponibilidad calculada desde los préstamos. |
| `test_catalogo.py` | 35 | Alta, edición y consulta de categorías, autores, editoriales, libros y ejemplares; validaciones; acceso. |
| `test_codigo_obligatorio.py` | 4 | El código de inventario es obligatorio y se normaliza. |
| `test_busqueda.py` | 3 | Búsqueda de libros sin tildes (`unaccent`). |
| `test_interfaz.py` | 8 | Navegación accesible, mensajes, errores junto al campo y plantilla base sin texto suelto. |
| `test_semilla.py` | 3 | El comando `cargar_datos_prueba` es repetible y no duplica datos. |
| `test_personas.py` | 33 | Alta, consulta, edición, baja lógica y reactivación de personas; búsqueda; filtros; permisos. |
| `test_prestamos.py` | 40 | Préstamo con vencimiento a 14 días, controles, préstamos simultáneos, devolución y regla D8 en la base, listados. |
| `test_ejemplares_baja.py` | 18 | Baja lógica de ejemplares con motivo y fecha, coherencia en la base, búsqueda por código. |
| `test_informes.py` | 20 | Exportación CSV: formato para Excel, filtros, todas las páginas, protección contra fórmulas, permisos. |
| `test_importacion.py` | 27 | Importación del inventario en Excel: modo prueba sin cambios, carga repetible, código provisorio, varios autores, sin editorial, filas rechazadas, prestados, archivo inválido y limpieza de datos. |
| `test_rediseno.py` | 17 | Interfaz: indicadores reales del panel, aviso de vencidos, página de Informes, disponibilidad por libro, permisos y estructura accesible. |

### 3.2. Aplicación `cuentas` (87 pruebas)

| Archivo | Pruebas | Qué verifica |
|---|---|---|
| `test_roles.py` | 5 | Grupos y permisos de cada rol; acceso directo por URL. |
| `test_login.py` | 12 | Ingreso por correo, mensaje genérico, cuentas inactivas, correo repetido (desviación B). |
| `test_recuperacion.py` | 14 | Recuperación y cambio de contraseña; vencimiento del enlace. |
| `test_alta.py` | 22 | Alta, edición, desactivación y reenvío de cuentas; matriz de permisos; correo único en la base (desviación A). |
| `test_seguridad.py` | 6 | Panel de administración solo para superusuarios; `ALLOWED_HOSTS`; `STATIC_ROOT`. |
| `test_navegacion.py` | 7 | Menú según el rol y página "Acceso no permitido" (403). |
| `test_ajustes.py` | 9 | Altas simultáneas sin error 500 (CA-A9), falla del correo (CA-A8, CA-R5), sesión de 8 horas, botón Salir, enlace de recuperación. |
| `test_correo.py` | 10 | Configuración SMTP desde el entorno y comando `probar_correo` sin mostrar la contraseña. |
| `test_contexto.py` | 2 | Rol que muestra la cabecera según los grupos de la cuenta. |

### 3.3. Aplicación `interfaz` (4 pruebas)

| Archivo | Pruebas | Qué verifica |
|---|---|---|
| `tests.py` | 4 | Íconos decorativos (no toman foco), ícono desconocido sin error, iniciales y porcentajes. |

## 4. Verificación de que las pruebas detectan errores

Para las funcionalidades nuevas de Release 1 se hizo una verificación adicional: se introdujo a propósito un
error en el código y se comprobó que las pruebas fallaran. Luego se restauró el código.

| Error introducido | Pruebas que lo detectaron |
|---|---|
| Permitir dar de baja una persona con préstamos sin devolver | `test_no_se_da_de_baja_con_prestamos_sin_devolver` |
| No normalizar el documento | 4 pruebas de `test_personas` |
| Paginación que pierde los filtros | `test_la_paginacion_conserva_busqueda_y_estado` |
| Plazo de 7 días en lugar de 14 | 4 pruebas de `test_prestamos` |
| Prestar a una persona dada de baja | `test_persona_dada_de_baja_no_recibe_prestamos` |
| Aceptar en pantalla una devolución anterior al préstamo | `test_devolucion_anterior_al_prestamo_se_rechaza` (y la base la rechazó igual) |
| Quitar la restricción D8 de la base | `test_la_base_no_acepta_devolucion_anterior_al_prestamo` |
| No capturar préstamos simultáneos | `test_dos_prestamos_simultaneos_no_dan_error_500` |
| CSV sin BOM, con coma o sin protección contra fórmulas | Pruebas de formato de `test_informes` |
| Exportar solo la primera página | `test_exporta_todas_las_paginas` (ejemplares y préstamos) |
| Dar de baja un ejemplar prestado o prestar uno dado de baja | `test_ejemplares_baja` |
| Quitar la apertura directa por código exacto | 3 pruebas de búsqueda por código |
| Quitar la restricción de coherencia de baja | `test_la_base_exige_coherencia_entre_estado_y_datos_de_baja` |
| No capturar altas de cuentas simultáneas | 3 pruebas de `test_ajustes` |
| Importación: el modo prueba guarda los datos | `test_sin_guardar_no_queda_nada_en_la_base` |
| Importación: sin control de ID o numeración repetidos | 2 pruebas de `test_importacion` |
| Importación: no omitir los ejemplares ya cargados | `test_se_puede_repetir_sin_duplicar` |
| Importación: sin código provisorio | `test_sin_numeracion_recibe_codigo_provisorio` |

## 5. Pruebas manuales en el navegador

Además de la suite automática, se recorrieron en el navegador (escritorio de 1280 px y teléfono de 375–390 px)
los flujos principales con los datos de prueba: ingreso, préstamo, préstamo a un documento inexistente,
devolución con fecha inválida y válida, alta de persona con documento repetido, baja rechazada por préstamo
activo, baja y reactivación de ejemplares, menú según el rol, 403 y exportación de los tres informes CSV.
En ninguna pantalla hubo desplazamiento horizontal. Las capturas del [manual de usuario](manual-de-usuario.md)
son de esas pruebas.

El CSV exportado se abrió como planilla con LibreOffice y las columnas y tildes se vieron correctamente.

## 6. Pendientes de verificación del equipo

| Verificación | Responsable | Resultado |
|---|---|---|
| Ejecutar `python manage.py test` en cada equipo | Cada integrante | _completar_ |
| Abrir un CSV exportado con doble clic en **Microsoft Excel** | _completar_ | _completar_ |
| Prueba real de correo: `python manage.py probar_correo` y alta de una cuenta recibiendo el correo | Titular de la cuenta de correo | _completar_ |
| Subir una imagen de portada real desde el navegador | _completar_ | _completar_ |
| Instalación desde cero siguiendo el README | _completar_ | _completar_ |
