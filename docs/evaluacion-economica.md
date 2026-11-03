# SIGEBI — Evaluación económica

> **Documento para completar por el equipo.** Las horas y la tarifa tienen que salir del registro real del
> equipo (Trello, cierres de sprint) y de una tarifa de referencia que el equipo elija y cite. Acá no se
> inventaron valores: los campos `_completar_` quedan para el equipo. La estructura sigue lo que pide el TFI:
> mejora concreta, horas, valor hora, costo original, costo de la ampliación y presupuesto total.

## 1. Sistema original: SIGEBI Release 1 (biblioteca física)

Sistema web para el personal de la biblioteca: catálogo, ejemplares, personas, préstamos, devoluciones,
vencidos, cuentas con roles e informes CSV. Ver la [documentación técnica](documentacion-tecnica.md).

### 1.1. Horas de Release 1

| Sprint / etapa | Tareas principales | Horas |
|---|---|---|
| Sprint 1 | Organización, alcance, análisis del inventario, modelo entidad-relación y revisión con el profesor | _completar_ |
| Sprint 2 | Entorno, proyecto Django, PostgreSQL, modelos, migraciones, Admin y datos de prueba | _completar_ |
| Sprint 3 | Pantallas del catálogo, búsqueda sin tildes, pruebas | _completar_ |
| Sprint 4 | Cuentas y roles, login por correo, recuperación de contraseña, seguridad, personas, préstamos y devoluciones | _completar_ |
| Sprint 5 | Baja de ejemplares, búsqueda por código, informes CSV, correo, documentación y pruebas | _completar_ |
| **Total Release 1** | | **_completar_** |

> El TFI (Plan 2024) prevé **95 horas cátedra** de desarrollo del sistema por estudiante. Si el equipo usa
> ese valor como base, debe indicar cómo lo convierte a horas reloj (habitualmente 1 hora cátedra = 45 minutos;
> confirmarlo con la cátedra).

### 1.2. Valor hora

| Concepto | Valor |
|---|---|
| Rol de referencia (por ejemplo, desarrollador junior o semi-senior) | _completar_ |
| Fuente de la tarifa (relevamiento salarial, consejo profesional u otra, con fecha) | _completar_ |
| **Valor hora (ARS)** | **_completar_** |

### 1.3. Costo del sistema original

```
Costo original = Horas de Release 1 × Valor hora
```

| Concepto | Valor |
|---|---|
| Horas de Release 1 | _completar_ |
| Valor hora | _completar_ |
| **Costo original** | **_completar_** |

## 2. Mejora propuesta: Release 2 — Biblioteca virtual

### 2.1. Qué aporta

La biblioteca ya tiene su operación física sistematizada. La mejora propuesta extiende SIGEBI a
**estudiantes y docentes**, que hoy tienen que acercarse a la biblioteca para saber si un libro está disponible:

- Acceso de estudiantes y docentes con su propia cuenta.
- Consulta del catálogo y de la disponibilidad desde cualquier lugar.
- Material digital (PDF) organizado por carrera y materia, con consulta y descarga.
- Solicitud virtual de préstamo de libros físicos, que el personal confirma desde SIGEBI.

**Beneficio concreto:** menos consultas presenciales para saber si hay un ejemplar, menos tiempo de
atención en el mostrador y acceso al material digital fuera del horario de la biblioteca.

### 2.2. Estimación de horas de la ampliación

| Tarea | Horas estimadas |
|---|---|
| Análisis y diseño: nuevas entidades (material digital, carrera, materia, solicitud), ajustes al modelo | _completar_ |
| Cuentas de estudiantes y docentes (alta, vínculo con PERSONA, permisos) | _completar_ |
| Catálogo público con disponibilidad | _completar_ |
| Carga, clasificación, consulta y descarga de material digital | _completar_ |
| Solicitudes virtuales de préstamo y confirmación por el personal | _completar_ |
| Pruebas automáticas y manuales | _completar_ |
| Documentación y manual | _completar_ |
| Despliegue (servidor, HTTPS, almacenamiento de archivos) | _completar_ |
| **Total de la ampliación** | **_completar_** |

### 2.3. Costo de la ampliación

```
Costo de la ampliación = Horas de la ampliación × Valor hora
```

| Concepto | Valor |
|---|---|
| Horas de la ampliación | _completar_ |
| Valor hora | _completar_ |
| **Costo de la ampliación** | **_completar_** |

## 3. Presupuesto total con la mejora

```
Presupuesto total = Costo original + Costo de la ampliación
```

| Concepto | Valor |
|---|---|
| Costo original (Release 1) | _completar_ |
| Costo de la ampliación (Release 2) | _completar_ |
| **Presupuesto total** | **_completar_** |

### 3.1. Costos que no son horas de desarrollo (si corresponde)

| Concepto | Valor |
|---|---|
| Servidor o alojamiento (mensual o anual) | _completar_ |
| Dominio y certificado HTTPS | _completar_ |
| Almacenamiento del material digital | _completar_ |
| Cuenta de correo | _completar_ |

Las herramientas usadas (Python, Django, PostgreSQL) son de código abierto y no tienen costo de licencia.
