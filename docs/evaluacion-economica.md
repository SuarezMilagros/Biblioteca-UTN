# SIGEBI — Evaluación económica

> Valores en pesos argentinos (ARS), calculados en noviembre de 2026. Las horas salen de la dedicación que informó
> el equipo (sección 1.1); el valor hora, de un relevamiento salarial público del sector (sección 2). Cada supuesto
> está indicado en su tabla: si el equipo registra en Trello horas reales distintas, se reemplazan y se recalculan
> los totales con las mismas fórmulas.

La consigna del TFI pide: proponer una mejora concreta sobre el sistema original, estimar las horas, definir un valor
hora, calcular el costo del sistema original y el de la ampliación, y presentar el presupuesto total con la mejora.

| Concepto | En este documento |
|---|---|
| **Sistema original** | SIGEBI tal como se entrega: Release 1 (biblioteca física) y Release 2 (biblioteca virtual) |
| **Mejora propuesta** | Asistente con IA: "subo un ejercicio y me dice qué libro me ayuda" (decisión del equipo, 13/11/2026) |

## 1. Horas del sistema original

### 1.1. Supuestos (informados por el equipo)

- Cada sprint duró **una semana**; se consideran **5 días de trabajo** por sprint.
- Cada integrante trabajó **entre 4 y 6 horas por día**; el presupuesto usa el **promedio de 5 horas**.
- **Release 1 (Sprints 1 a 6):** 3 integrantes (Emmanuel, Milagros y Ana).
- **Release 2 (Sprints 7 y 8):** 4 integrantes; Mariano se sumó en el Sprint 7.

Horas de un sprint = integrantes × 5 días × horas por día.

| Escenario | Horas por día | Sprint de la Release 1 (3 integrantes) | Sprint de la Release 2 (4 integrantes) |
|---|---|---|---|
| Mínimo | 4 | 60 | 80 |
| **Promedio (se usa en el presupuesto)** | **5** | **75** | **100** |
| Máximo | 6 | 90 | 120 |

### 1.2. Horas por sprint

| Sprint | Tareas principales | Horas (promedio) |
|---|---|---|
| Sprint 1 | Organización, alcance, análisis del inventario, modelo entidad-relación y revisión con el profesor | 75 |
| Sprint 2 | Entorno, proyecto Django, PostgreSQL, modelos, migraciones, Admin y datos de prueba | 75 |
| Sprint 3 | Pantallas del catálogo, búsqueda sin tildes, ajustes del inventario y auditoría del repositorio | 75 |
| Sprint 4 | Personas, préstamos con vencimiento, devoluciones, vencidos, baja de ejemplares, búsqueda por código | 75 |
| Sprint 5 | Cuentas y roles, recuperación de contraseña, seguridad, correo, informes CSV, rediseño, documentación y pruebas | 75 |
| Sprint 6 | Validación con datos reales, importación del inventario en Excel, catálogo grande, manual y cierre de la Release 1 | 75 |
| **Subtotal Release 1** | | **450** (rango: 360 a 540) |
| Sprint 7 | Límite de intentos, DER de la Release 2, carreras, cuentas de lectores, portal, catálogo por carrera, Mi perfil y material digital | 100 |
| Sprint 8 | Material compartido, reservas, opiniones, QR, avisos por correo, informe de demanda, pedidos de la profesora, revisión de UX/UI, informes en PDF, publicación en Railway y documentación | 100 |
| **Subtotal Release 2** | | **200** (rango: 160 a 240) |
| **Total del sistema original** | | **650** (rango: 520 a 780) |

> - El Sprint 8 se extendió algunos días más allá de la semana planificada (del 16/11 al 25/11/2026). Si el equipo
>   registró horas de esos días, se suman acá.
> - Como referencia académica, el TFI (Plan 2024) prevé **95 horas cátedra** de desarrollo por estudiante
>   (95 × 45 minutos ≈ 71 horas reloj). El equipo informó una dedicación mayor.

## 2. Valor hora

Se toma el **salario de mercado de un desarrollador junior** en Argentina: es el perfil que corresponde a un equipo
de estudiantes avanzados de la Tecnicatura.

| Concepto | Valor |
|---|---|
| Rol de referencia | Desarrollador de software **junior** (0 a 2 años de experiencia), en relación de dependencia |
| Fuente | Encuesta de Sueldos **Sysarmy 2026.1** (análisis de OpenQube, datos de diciembre de 2025 a febrero de 2026), mediana del salario **bruto mensual** en pesos. Es la edición más reciente publicada al preparar este documento |
| Salario bruto mensual (mediana) | $ 1.538.500 |
| Horas mensuales de una jornada completa | 160 (40 horas semanales × 4 semanas) |
| **Valor hora (ARS)** | **$ 9.616** (1.538.500 ÷ 160, redondeado) |

**Otras referencias (para comparar; no se usan en el cálculo):**

| Referencia | Valor hora aproximado | Observación |
|---|---|---|
| Desarrollador **semi senior**, Sysarmy 2026.1 (mediana $ 2.501.629 mensuales) | $ 15.635 | Perfil de 2 a 5 años de experiencia. |
| Honorarios sugeridos de consejos profesionales de informática (abril de 2026, otras jurisdicciones): "Programación de software" | $ 84.680 a $ 93.980 | Honorario de un **profesional independiente matriculado**: incluye sus costos, impuestos y aportes, por eso es mucho mayor que un salario. |
| Colegio de Graduados en Ciencia y Tecnología Informática de Tucumán | _a consultar_ | Publica una [tabla de honorarios sugeridos](https://www.colegioinfotuc.com.ar/honorarios-sugeridos/) a septiembre de 2026. Es la referencia local si se quiere presupuestar como servicio profesional. |

> **Limitaciones del valor elegido.** La mediana es de enero de 2026: los salarios en pesos subieron desde entonces,
> así que el valor está algo por debajo del de noviembre. Tampoco incluye las contribuciones patronales. Si el sistema
> se presupuestara como servicio profesional independiente, corresponde usar la tabla del Colegio de Tucumán.

## 3. Costo del sistema original

```
Costo del sistema original = Horas del sistema original × Valor hora
```

| Concepto | Mínimo | **Promedio** | Máximo |
|---|---|---|---|
| Horas de la Release 1 | 360 | **450** | 540 |
| Horas de la Release 2 | 160 | **200** | 240 |
| Horas del sistema original | 520 | **650** | 780 |
| Valor hora | $ 9.616 | **$ 9.616** | $ 9.616 |
| Costo de la Release 1 | $ 3.461.760 | **$ 4.327.200** | $ 5.192.640 |
| Costo de la Release 2 | $ 1.538.560 | **$ 1.923.200** | $ 2.307.840 |
| **Costo del sistema original** | $ 5.000.320 | **$ 6.250.400** | $ 7.500.480 |

## 4. Mejora propuesta: asistente con IA para encontrar libros

### 4.1. Qué aporta

Hoy un alumno busca en el catálogo por título, autor o ISBN: tiene que saber qué libro necesita. Muchas veces lo
que tiene es un **ejercicio** y no sabe qué libro lo ayuda.

**La mejora:** en el portal, el alumno escribe o pega el ejercicio, o sube una foto. SIGEBI le pide a un modelo de IA
que elija, entre los libros **de sus carreras**, los 3 a 5 que mejor lo ayudan, con el motivo de cada uno. La pantalla
muestra la disponibilidad de cada libro y el botón **Reservar**.

**Reglas:**

- Nunca resuelve el ejercicio: solo recomienda libros del catálogo de la biblioteca.
- No se envían datos personales del alumno: solo el ejercicio y la lista de libros de sus carreras.
- Si el servicio de IA no responde, el portal sigue funcionando igual (catálogo, reservas y material).
- Un límite de consultas por persona y por día controla el costo.

**Beneficio:** los alumnos encuentran el libro que necesitan sin depender del horario de la biblioteca, se usan más
los libros que ya existen y el informe de demanda incorpora lo que se busca y no hay.

**Limitación conocida:** el catálogo tiene título, autor y categoría, pero no los temas de cada libro. Para títulos
genéricos ("Proyecto final", "Apuntes") la IA no tiene de dónde deducir el contenido. Por eso la mejora agrega a cada
libro un campo **temas**, que la biblioteca carga o revisa.

### 4.2. Estimación de horas de la ampliación

Estimación por analogía con la Release 2, que ya tiene portal, permisos por carrera, correo y publicación en internet:
la mejora se apoya en todo eso.

| Tarea | Horas estimadas |
|---|---|
| Análisis y diseño: reglas, qué datos se envían, formato de la respuesta | 4 |
| Campo "temas" en el libro: migración, formulario y carga asistida para revisar | 8 |
| Servicio de recomendación: llamada a la API de IA con respuesta estructurada, límite de tiempo y funcionamiento sin el servicio | 8 |
| Pantalla del portal: ejercicio en texto o foto, resultados con disponibilidad y botón Reservar | 6 |
| Límite de consultas por persona y registro de consultas para controlar el costo | 4 |
| Pruebas automáticas (con respuestas simuladas, sin gastar en el servicio) y prueba con ejercicios reales | 6 |
| Documentación: manual y documentación técnica | 2 |
| Publicación: clave del servicio en Railway y límite de gasto mensual | 2 |
| **Total de la ampliación** | **40** |

### 4.3. Costo de la ampliación

```
Costo de la ampliación = Horas de la ampliación × Valor hora
```

| Concepto | Valor |
|---|---|
| Horas de la ampliación | 40 |
| Valor hora | $ 9.616 |
| **Costo de la ampliación** | **$ 384.640** |

## 5. Presupuesto total con la mejora

```
Presupuesto total = Costo del sistema original + Costo de la ampliación
```

| Concepto | Mínimo | **Promedio** | Máximo |
|---|---|---|---|
| Costo del sistema original | $ 5.000.320 | **$ 6.250.400** | $ 7.500.480 |
| Costo de la ampliación (asistente con IA) | $ 384.640 | **$ 384.640** | $ 384.640 |
| **Presupuesto total de desarrollo** | $ 5.384.960 | **$ 6.635.040** | $ 7.885.120 |

## 6. Costos de funcionamiento (no son horas de desarrollo)

Valores en dólares, convertidos al dólar oficial del Banco Nación (venta) del 25/11/2026: **$ 1.630**.

| Concepto | Costo mensual | En pesos por mes | Observación |
|---|---|---|---|
| Servidor y base de datos (Railway, plan Hobby) | USD 5 | $ 8.150 | Incluye USD 5 de uso, suficiente para el uso de la biblioteca. Hoy se usa el Trial (USD 5 de crédito por 30 días). |
| Correo (Brevo, plan gratuito) | USD 0 | $ 0 | Hasta 300 correos por día. |
| Dominio propio | — | — | No hace falta: se usa la dirección de Railway con HTTPS incluido. Un dominio propio es opcional. |
| Licencias | — | $ 0 | Python, Django y PostgreSQL son de código abierto. |
| **Subtotal sin la mejora** | **USD 5** | **$ 8.150** | **$ 97.800 por año** |

**Servicio de IA de la mejora.** Se cobra por uso: por millón de tokens de entrada (lo que se envía) y de salida (la
respuesta). Una consulta envía unos 4.800 tokens (instrucciones, unos 100 títulos de las carreras del alumno y el
ejercicio, o su foto reducida) y recibe unos 1.500 tokens.

| Modelo (Anthropic, precios por millón de tokens, noviembre de 2026) | Entrada | Salida | Costo por consulta | 1.000 consultas por mes | En pesos por mes |
|---|---|---|---|---|---|
| **Claude Opus 5.5** (modelo de uso general; se usa en el presupuesto) | USD 4 | USD 20 | USD 0,049 | USD 49,20 | $ 80.196 |
| Claude Sonnet 5.5 | USD 2 | USD 10 | USD 0,025 | USD 24,60 | $ 40.098 |
| Claude Haiku 5.5 (el más económico) | USD 0,10 | USD 0,50 | USD 0,0012 | USD 1,23 | $ 2.005 |

- **1.000 consultas por mes** es un supuesto para dimensionar (por ejemplo, 250 alumnos que hacen 4 consultas por mes).
  El costo crece en proporción a las consultas, y el límite por persona y por día lo acota.
- El presupuesto toma **Claude Opus 5.5** como techo: **USD 49,20 por mes, unos $ 962.000 por año**.
- Antes de implementar conviene comparar los tres modelos con ejercicios reales. Si un modelo más económico recomienda
  igual de bien, el costo baja mucho: con Claude Haiku 5.5 son unos $ 24.000 por año.
- Las pruebas automáticas simulan la respuesta del servicio, así que el desarrollo no genera este costo.
- **Hay que acordar con el tutor y la biblioteca quién paga el servicio**, y configurar un límite de gasto mensual
  en la cuenta del proveedor.

| Resumen anual de funcionamiento | En pesos |
|---|---|
| Servidor y base de datos | $ 97.800 |
| Servicio de IA (Claude Opus 5.5, 1.000 consultas por mes) | $ 962.352 |
| **Total anual con la mejora** | **$ 1.060.152** |

## 7. Fuentes

- Encuesta de Sueldos Sysarmy 2026.1, [resultados de OpenQube](https://sueldos.openqube.io/encuesta-sueldos-2026.01/) y
  [publicación de Sysarmy](https://sysarmy.com/blog/posts/resultados-de-la-encuesta-de-sueldos-2026-1/); medianas por
  seniority citadas en [Teclab — Cuánto cobra un programador en Argentina en 2026](https://teclab.edu.ar/tecnologia-y-desarrollo/cuanto-cobra-un-programador-en-argentina/).
- Tablas de honorarios sugeridos de consejos profesionales de informática (abril de 2026) y
  [Colegio de Graduados en Ciencia y Tecnología Informática de Tucumán — Honorarios sugeridos](https://www.colegioinfotuc.com.ar/honorarios-sugeridos/).
- Precios de los modelos de IA: [Anthropic — Pricing](https://platform.claude.com/docs/en/about-claude/pricing).
- Precio de Railway y límites de Brevo: ver [Publicación en Railway](despliegue-railway.md).
- Dólar oficial: [Banco de la Nación Argentina](https://www.bna.com.ar/), cotización de venta del 25/11/2026.
- Dedicación del equipo: informada por los integrantes (sprints de una semana, 4 a 6 horas diarias).
