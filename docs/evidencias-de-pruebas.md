# SIGEBI — Evidencias de pruebas

**Release 1 (biblioteca física) y Release 2 (biblioteca virtual).**

## 1. Cómo se ejecutan

Desde la carpeta `SIGEBI/`, con el entorno virtual activo y PostgreSQL funcionando:

```bash
python manage.py test
```

Django crea una base temporal (`test_sigebi`), aplica todas las migraciones, ejecuta las pruebas y borra la base al terminar.
Las pruebas usan la misma base que el sistema (PostgreSQL), no una base en memoria: así se verifican también las
restricciones de integridad y la búsqueda sin tildes (`unaccent`). Ninguna prueba envía correos reales ni usa
internet: el correo se simula y los archivos se guardan en carpetas temporales.

## 2. Resultado de referencia

Ejecución de verificación al preparar la documentación de la Release 2 (25/11/2026), con Python 3.13,
Django 5.2.18 y PostgreSQL 16, sobre el código de `main` después del PR #43:

```
Found 884 test(s).
Creating test database for alias 'default'...
System check identified no issues (0 silenced).
----------------------------------------------------------------------
Ran 884 tests in 91.006s

OK
Destroying test database for alias 'default'...
```

| Momento | Pruebas |
|---|---|
| Cierre del Sprint 3 | 70 |
| Cierre del Sprint 5 | 291 |
| Cierre de la Release 1 (Sprint 6) | 336 |
| Límite de intentos (PR #20) | 352 |
| Cierre del desarrollo del Sprint 7 (PR #28) | 480 |
| Versión actual (PR #43) | 884 |

> Cada integrante del equipo debe ejecutar la suite en su equipo y registrar su propio resultado (sección 7).

## 3. Pruebas por módulo

### 3.1. Aplicación `biblioteca` (614 pruebas)

| Archivo | Pruebas | Release | Qué verifica |
|---|---|---|---|
| `test_modelos.py` | 19 | 1 | Entidades, relaciones, restricciones de la base y disponibilidad calculada desde los préstamos. |
| `test_catalogo.py` | 35 | 1 | Alta, edición y consulta de categorías, autores, editoriales, libros y ejemplares; validaciones; acceso. |
| `test_codigo_obligatorio.py` | 4 | 1 | El código de inventario es obligatorio y se normaliza. |
| `test_busqueda.py` | 3 | 1 | Búsqueda de libros sin tildes (`unaccent`). |
| `test_interfaz.py` | 8 | 1 | Navegación accesible, mensajes, errores junto al campo y plantillas sin texto suelto. |
| `test_semilla.py` | 3 | 1 | El comando `cargar_datos_prueba` es repetible y no duplica datos. |
| `test_personas.py` | 33 | 1 | Alta, consulta, edición, baja lógica y reactivación de personas; búsqueda; filtros; permisos. |
| `test_prestamos.py` | 40 | 1 | Préstamo con vencimiento a 14 días, controles, préstamos simultáneos, devolución y regla D8 en la base, listados. |
| `test_ejemplares_baja.py` | 18 | 1 | Baja lógica de ejemplares con motivo y fecha, coherencia en la base, búsqueda por código. |
| `test_informes.py` | 20 | 1 | Exportación CSV: formato para Excel, filtros, todas las páginas, protección contra fórmulas, permisos. |
| `test_catalogo_grande.py` | 18 | 1 | Libros y Ejemplares se listan al buscar o con «Ver todos», buscador en las listas largas, listados sin una consulta por fila. |
| `test_importacion.py` | 27 | 1 | Importación del inventario en Excel: modo prueba, carga repetible, código provisorio, varios autores, filas rechazadas. |
| `test_rediseno.py` | 17 | 1 | Indicadores reales del panel, aviso de vencidos, página de Informes, permisos y estructura accesible. |
| `test_carreras.py` | 24 | 2 | Las 10 carreras por migración, nombre único, carreras de personas y categorías, aviso de categorías sin carrera, carrera en uso no se borra. |
| `test_clasificacion.py` | 10 | 2 | Carreras de cada categoría del inventario real, sin pisar lo asignado a mano. |
| `test_material_digital.py` | 19 | 2 | Carga del personal, PDF real de hasta 20 MB, archivos privados, baja lógica, descarga solo de las carreras propias. |
| `test_material_compartido.py` | 33 | 2 | Material de alumnos y profesores: pendiente hasta la aprobación, revisión, motivo de rechazo, correos, revisión simultánea. |
| `test_reservas_personal.py` | 52 | 2 | Confirmar y apartar 48 h, rechazar, retiro con préstamo, liberar, vencimiento automático, ejemplar apartado, confirmación simultánea. |
| `test_opiniones.py` | 34 | 2 | Solo quien tuvo el libro prestado, una por persona y libro, estrellas válidas, moderación, promedio con las aprobadas. |
| `test_avisos.py` | 26 | 2 | «Vence pronto» y «venció», una sola vez por préstamo y tipo, solo a cuentas activas, ejecución repetida y simultánea. |
| `test_qr.py` | 21 | 2 | QR con la dirección de la ficha, hojas de etiquetas, aviso de dirección local, el lector no abre la ficha. |
| `test_demanda.py` | 18 | 2 | Período, cantidades por libro, marca «Conviene comprar más», exportación y permisos. |
| `test_pedidos_de_la_profesora.py` | 28 | 2 | Menú, tipo de ejemplar, filtros, préstamos por persona y documento de 7 u 8 dígitos. |
| `test_revision_ux.py` | 23 | 2 | Revisión de UX/UI: ficha de la carrera con sus personas, personas por carrera, enlaces de salto del inicio. |
| `test_informes_pdf.py` | 27 | 2 | Cada informe en PDF con las mismas columnas y filas que el CSV, anchos de columna, permisos. |
| `test_volver_arriba_y_menu.py` | 12 | 2 | Botón «Volver arriba» y menú lateral sin barra de desplazamiento. |
| `test_despliegue.py` | 41 | 2 | Configuración por variables de entorno, HTTPS, correo por Brevo, `preparar_sitio` y archivos en el servidor publicado. |
| `test_migraciones.py` | 1 | 2 | Los modelos y las migraciones coinciden. |

### 3.2. Aplicación `cuentas` (153 pruebas)

| Archivo | Pruebas | Release | Qué verifica |
|---|---|---|---|
| `test_roles.py` | 5 | 1 | Grupos y permisos de cada rol; acceso directo por URL. |
| `test_login.py` | 13 | 1 | Ingreso por correo, mensaje genérico, cuentas inactivas, correo repetido (desviación B), texto de la pantalla. |
| `test_recuperacion.py` | 14 | 1 | Recuperación y cambio de contraseña; vencimiento del enlace. |
| `test_alta.py` | 22 | 1 | Alta, edición, desactivación y reenvío de cuentas; matriz de permisos; correo único en la base (desviación A). |
| `test_seguridad.py` | 6 | 1 | Panel de administración solo para superusuarios; `ALLOWED_HOSTS`; `STATIC_ROOT`. |
| `test_navegacion.py` | 7 | 1 | Menú según el rol y página "Acceso no permitido" (403). |
| `test_ajustes.py` | 9 | 1 | Altas simultáneas sin error 500, falla del correo, sesión de 8 horas, botón Salir. |
| `test_correo.py` | 10 | 1 | Configuración del correo desde el entorno y comando `probar_correo` sin mostrar la contraseña. |
| `test_contexto.py` | 2 | 1 | Rol que muestra la cabecera según los grupos de la cuenta. |
| `test_intentos.py` | 23 | 2 | Límite de intentos por correo y por IP, vencimiento a los 15 minutos, recuperación, Admin, IP real detrás del proxy. |
| `test_cuentas_lectores.py` | 24 | 2 | Cuenta del portal desde la ficha de la persona: requisitos, correo único, baja y reactivación. |
| `test_perfil_del_personal.py` | 18 | 2 | Mi perfil del personal y foto privada. |

### 3.3. Aplicación `portal` (113 pruebas, Release 2)

| Archivo | Pruebas | Qué verifica |
|---|---|---|
| `test_acceso.py` | 16 | Personal y lectores separados: un lector recibe 403 en **todas** las direcciones del personal y en el Admin. |
| `test_catalogo.py` | 22 | Solo libros de sus carreras, «no encontrado» para los de otra carrera, búsqueda, filtros y disponibilidad. |
| `test_perfil.py` | 13 | Datos de solo lectura y préstamos propios. |
| `test_perfil_en_partes_y_foto.py` | 26 | Perfil en partes, foto de perfil privada y redirección del ingreso. |
| `test_reservas_lector.py` | 24 | Reservar solo libros de sus carreras, máximo 2 reservas, no con vencidos, cancelar. |
| `test_inicio_y_contadores.py` | 12 | Inicio del portal con lo pendiente y contadores del menú. |

### 3.4. Aplicación `interfaz` (4 pruebas)

| Archivo | Pruebas | Qué verifica |
|---|---|---|
| `tests.py` | 4 | Íconos decorativos (no toman foco), ícono desconocido sin error, iniciales y porcentajes. |

## 4. Verificación de que las pruebas detectan errores

Para las funcionalidades nuevas se hizo una verificación adicional: se introdujo a propósito un error en el código
y se comprobó que las pruebas fallaran. Luego se restauró el código.

### 4.1. Release 1

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
| Listar todo el catálogo al entrar, sin búsqueda | 3 pruebas de `BuscarAntesDeListarTests` |
| Límite de intentos: no bloquear el ingreso, sin límite por IP o sin límite de recuperación | `test_intentos` |

### 4.2. Release 2

Durante el desarrollo, cada tarjeta se entregó después de una verificación de este tipo. Para este documento se
repitió sobre el código integrado en `main` con las reglas principales de la Release 2. Cada error se probó contra
las pruebas de su módulo:

| Error introducido | Pruebas que corrieron | Resultado |
|---|---|---|
| Reservas: 3 activas en lugar de 2 | `test_reservas_lector` (24) | Detectado: 1 falla |
| Reservas: permitir reservar con préstamos vencidos | `test_reservas_lector` (24) | Detectado: 2 fallas |
| Reservas: 72 horas para retirar en lugar de 48 | `test_reservas_personal` (52) | Detectado: 1 falla |
| Prestar un ejemplar apartado a otra persona | `test_reservas_personal` (52) | Detectado: 1 falla |
| Catálogo del portal: mostrar libros de todas las carreras | `portal/test_catalogo` (22) | Detectado: 7 fallas |
| Material: mostrar el de otras carreras | `test_material_digital` y `test_material_compartido` (52) | Detectado: 2 fallas |
| Material: mostrar en el portal el pendiente o rechazado | `test_material_digital` y `test_material_compartido` (52) | Detectado: 6 fallas |
| Material: aceptar un archivo que no es PDF | `test_material_digital` (19) | Detectado: 1 falla |
| Material compartido: publicarlo sin revisión | `test_material_compartido` (33) | Detectado: 3 fallas |
| Portal: dejar entrar a quien no es lector | `portal/test_acceso` (16) | Detectado: 1 falla |
| Crear la cuenta del portal a una persona sin carrera | `test_cuentas_lectores` (24) | Detectado: 2 fallas |
| Opiniones: opinar sin haber tenido el libro prestado | `test_opiniones` (34) | Detectado: 2 fallas |
| Opiniones: una opinión editada sigue publicada | `test_opiniones` (34) | Detectado: 2 errores |
| Avisos: 3 días de anticipación en lugar de 2 | `test_avisos` (26) | Detectado: 1 falla |
| Avisos: enviar a cuentas desactivadas | `test_avisos` (26) | Detectado: 1 falla |
| Demanda: marcar un libro con tantas reservas sin ejemplar como ejemplares | `test_demanda` (18) | Detectado: 1 falla |
| **Control:** agregar un comentario (no cambia nada) | `test_reservas_lector` (24) | Sin fallas, como se esperaba |

Las 16 modificaciones de reglas fueron detectadas y el control no produjo fallas. Se probó también quitar la línea
que deja el material compartido como pendiente: las pruebas no fallaron, pero ese cambio no altera el sistema,
porque pendiente ya es el estado por defecto del modelo.

## 5. Pruebas manuales en el navegador

**Release 1:** se recorrieron en el navegador (escritorio de 1280 px y teléfono de 375–390 px) los flujos
principales con los datos de prueba: ingreso, préstamo, préstamo a un documento inexistente, devolución con fecha
inválida y válida, alta de persona con documento repetido, baja rechazada por préstamo activo, baja y reactivación
de ejemplares, menú según el rol, 403 y exportación de los tres informes CSV. El CSV se abrió en LibreOffice y en
Microsoft Excel con las columnas y tildes correctas.

**Release 2:** para el [manual de usuario](manual-de-usuario.md) se recorrieron, con el inventario real y personas
ficticias, las 49 pantallas de las capturas, como bibliotecario, administrativo, alumno y profesor, en escritorio
(1280 px) y en teléfono (390 px): préstamo y devolución, reserva pendiente, confirmada y rechazada, opinión
publicada y pendiente, material compartido en revisión, crear cuenta del portal, carreras, categorías sin carrera,
etiquetas con QR, informe de demanda con un libro marcado y préstamos por persona. En ninguna pantalla hubo
desplazamiento horizontal.

## 6. Sitio publicado (Railway)

| Verificación | Resultado |
|---|---|
| El sitio abre con HTTPS y muestra la pantalla de ingreso | Hecha por el equipo (25/11/2026) |
| Ingreso con la cuenta de administración | Hecha por el equipo (25/11/2026) |
| Correo real por Brevo (`probar_correo`) | Hecha por el equipo: el correo llegó (25/11/2026) |
| Las portadas siguen después de volver a publicar (volumen `/data`) | _Pendiente_ |
| Copia de seguridad de la base y del volumen, con restauración de prueba | _Pendiente_ |

## 7. Verificaciones del equipo

### 7.1. Release 1

| Verificación | Responsable | Resultado |
|---|---|---|
| Ejecutar `python manage.py test` en cada equipo | Cada integrante | **336 pruebas OK**; informado por el equipo el 04/11/2026 |
| Abrir un CSV exportado con doble clic en **Microsoft Excel** | Equipo | Hecha; informada por el equipo el 04/11/2026 |
| Rotar la `SECRET_KEY` en el `.env` de cada integrante (decisión D7, sin registrar el valor) | Cada integrante | Milagros: hecha. Emmanuel: hecha (05/11/2026) |
| Prueba real de correo y alta de una cuenta recibiendo el correo | Milagros | Hecha; informada por el equipo el 04/11/2026 |
| Subir una imagen de portada real desde el navegador | Equipo | Hecha; informada por el equipo el 04/11/2026 |
| Instalación desde cero siguiendo el README | Equipo | Hecha; informada por el equipo el 05/11/2026 |

### 7.2. Release 2 (S7-09 y S8-08)

| Verificación | Responsable | Resultado |
|---|---|---|
| Suite en el equipo de Emmanuel | Emmanuel | 823 pruebas OK (24/11/2026) y 835 pruebas OK (24/11/2026), informadas al integrar los PR #39 y #40 |
| Suite completa en el equipo de cada integrante, con la versión final | Cada integrante | _A completar_ |
| Recorrido con un alumno, un profesor y un bibliotecario (Sprint 7) | Ana y Mariano | _A completar_ |
| Recorrido: reserva, confirmación, retiro y devolución | Ana y Mariano | _A completar_ |
| Recorrido: material compartido, carga, aprobación y descarga | Ana y Mariano | _A completar_ |
| Recorrido: opinión y moderación | Ana y Mariano | _A completar_ |
| Escanear un QR impreso con un celular | Ana y Mariano | _A completar_ |

> Para registrar un resultado: quién lo hizo, la fecha, si salió bien y, si algo falló, en qué paso y qué pasó.
