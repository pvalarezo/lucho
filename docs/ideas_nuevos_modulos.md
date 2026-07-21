# Ideas de Nuevos Módulos y Funcionalidades para Lucho

Documento de brainstorming. Cada perfil de usuario aporta necesidades distintas.
Se evalúa: ¿ya existe en Lucho? ¿se puede hacer con LLM? ¿requiere API externa?

---

## 👷 Trabajador / Empleado

| Necesidad | Módulo | ¿Existe? | ¿LLM? | ¿API externa? |
|-----------|--------|----------|-------|---------------|
| Control de turnos (rotativos) | `turnos` | ❌ Nuevo | Extraer patrón del texto | No |
| Cálculo de horas extra | `turnos` | ❌ Nuevo | Cálculo simple, confirma con usuario | No |
| Recordatorio de pago (quincena) | `recordatorios` | ✅ | — | No |
| Control de días de vacaciones | `turnos` | ❌ Nuevo | Extraer y restar días | No |
| Control de gastos de transporte | `finanzas` | ✅ | — | No |
| Recordatorio de reunión sindical | `recordatorios` | ✅ | — | No |

**Módulo propuesto**: `turnos` — calendario laboral simple con turnos (mañana/tarde/noche), horas extra y vacaciones.

---

## 🏠 Ama de Casa

| Necesidad | Módulo | ¿Existe? | ¿LLM? | ¿API externa? |
|-----------|--------|----------|-------|---------------|
| Planificación semanal de comidas | `comidas` | ❌ Nuevo | LLM genera plan semanal | No |
| Control de despensa (qué falta) | `listas` | ✅ | — | No |
| Calendario de pagos del hogar | `recordatorios` | ✅ | — | No |
| Recetas guardadas por categoría | `notas` | ✅ | — | No |
| Lista de súper inteligente (por pasillo) | `listas` | 🟡 Extender | LLM organiza por categoría | No |
| Recordatorio de cumpleaños familiares | `recordatorios` | ✅ (con recurrencia) | — | No |
| Control de citas médicas familia | `recordatorios` | ✅ | — | No |

**Módulo propuesto**: `comidas` — planificador semanal con recetas, ingredientes y lista de compras generada automáticamente.

---

## 👩‍🏫 Profesora / Docente

| Necesidad | Módulo | ¿Existe? | ¿LLM? | ¿API externa? |
|-----------|--------|----------|-------|---------------|
| Calendario de clases semanal | `recordatorios` | ✅ (con recurrencia) | — | No |
| Registro de asistencia simple | `asistencia` | ❌ Nuevo | Extraer nombres y estados | No |
| Control de notas (simplificado) | `notas` | 🟡 Extender | LLM interpreta "Juan sacó 8" | No |
| Recordatorio de entrega de planificación | `recordatorios` | ✅ | — | No |
| Lista de materiales por clase | `listas` | ✅ | — | No |
| Horario de recreo / timbres | `recordatorios` | ✅ | — | No |
| Feriados y suspensión de clases | `skills` | ✅ (holidays.md) | — | No |

**Módulo propuesto**: `calificaciones` — registro simple de notas por estudiante con promedio automático.

---

## 🎓 Estudiante

| Necesidad | Módulo | ¿Existe? | ¿LLM? | ¿API externa? |
|-----------|--------|----------|-------|---------------|
| Horario de clases semanal | `recordatorios` | ✅ (con recurrencia) | — | No |
| Control de tareas con fechas | `proyectos` | ✅ | — | No |
| Recordatorio de exámenes | `recordatorios` | ✅ | — | No |
| Seguimiento de notas por materia | `calificaciones` | ❌ Nuevo | LLM calcula promedios | No |
| Resumen de lecturas (apuntes) | `notas` | ✅ | — | No |
| Links y recursos de estudio | `notas` | ✅ | — | No |
| Pomodoro / temporizador de estudio | `temporizador` | ❌ Nuevo | "avisame en 25 min" | No |

**Módulo propuesto**: `calificaciones` + `temporizador` (ambos ligeros, el segundo ya casi existe con ad-hoc reminders).

---

## 💼 Profesional Independiente

| Necesidad | Módulo | ¿Existe? | ¿LLM? | ¿API externa? |
|-----------|--------|----------|-------|---------------|
| Gestión de clientes (CRM ligero) | `clientes` | ❌ Nuevo | Extraer datos de cliente | No |
| Seguimiento de proyectos con hitos | `proyectos` | ✅ | — | No |
| Control de horas facturables | `facturacion` | ❌ Nuevo | LLM calcula totales | No |
| Recordatorio de reuniones | `recordatorios` | ✅ | — | No |
| Seguimiento de cotizaciones | `proyectos` | ✅ | — | No |
| Recordatorio de renovación de RUC | `documentos` | ✅ | — | No |
| Generación de facturas simples | `facturacion` | ❌ Nuevo | LLM estructura datos | SRI (Fase 3) |

**Módulo propuesto**: `clientes` — extensión de `contactos` con historial de interacciones, proyectos vinculados y estado de cotizaciones.

---

## 👔 Gerente / Líder de Equipo

| Necesidad | Módulo | ¿Existe? | ¿LLM? | ¿API externa? |
|-----------|--------|----------|-------|---------------|
| Dashboard de tareas del equipo | `equipo` | ❌ Nuevo | LLM resume estado | No |
| Seguimiento de objetivos (OKRs) | `objetivos` | ❌ Nuevo | LLM interpreta avances | No |
| Recordatorio de revisiones 1:1 | `recordatorios` | ✅ | — | No |
| Delegación de tareas | `proyectos` | 🟡 Extender | Asignar responsable | No |
| Reporte semanal automático | `reportes` | 🟡 Extender | LLM genera desde datos | No |
| Control de presupuesto del equipo | `finanzas` | ✅ | — | No |

**Módulo propuesto**: `objetivos` — metas trimestrales con % de avance y check-ins periódicos.

---

## 🔌 Integraciones con APIs Externas (Nuevas)

| API | Para qué | Módulo | Complejidad |
|-----|----------|--------|-------------|
| 🚗 ANT / SRI | Multas, matriculación, datos vehiculares | `vehiculos` | ✅ Ya existe |
| 🏦 Banco Central | Tipo de cambio, inflación | `finanzas` | Media |
| 🌦️ Clima Ecuador | Pronóstico diario | `general` | Baja |
| 📰 Noticias Ecuador | Titulares del día | `general` | Baja |
| 🏥 IESS | Aportes, citas médicas | `salud` | Alta |
| 🚌 Transporte público | Rutas, horarios | `transporte` | Media |
| ⚡ Empresa Eléctrica | Consumo, fecha de corte | `servicios` | Alta |
| 📱 CNT / Claro | Saldo, fecha de corte | `servicios` | Media |
| 🏢 SRI | Facturación electrónica | `facturacion` | Alta (Fase 3) |
| 💳 Kushki / PayPhone | Pagos | `pagos` | Alta (Fase 3) |
| 🗳️ CNE | Lugar de votación | `general` | Baja |

---

## 📊 Resumen: Nuevos Módulos Propuestos

| # | Módulo | Perfiles | Prioridad | Esfuerzo |
|---|--------|---------|-----------|----------|
| 1 | `turnos` | Trabajador | 🟡 Media | Medio |
| 2 | `comidas` | Ama de casa | 🟢 Baja | Medio |
| 3 | `calificaciones` | Estudiante, Profesor | 🟢 Baja | Bajo |
| 4 | `clientes` (CRM) | Profesional | 🟡 Media | Medio |
| 5 | `objetivos` (OKRs) | Gerente | 🟢 Baja | Medio |
| 6 | `temporizador` | Estudiante | 🟢 Baja | Bajo (casi existe) |
| 7 | APIs Ecuador (clima, noticias, CNE) | Todos | 🟡 Media | Bajo-Medio |

---

## 🎯 Recomendación de Prioridad

**Corto plazo** (próxima sesión):
- `temporizador` — ya casi existe, es extender ad-hoc reminders
- APIs Ecuador: clima + noticias — rápido, alto valor percibido

**Mediano plazo** (Fase 2 extendida):
- `clientes` — extensión natural de contactos
- `calificaciones` — nicho estudiantes, simple

**Largo plazo** (Fase 3+):
- `comidas`, `turnos`, `objetivos` — más complejos, requieren más diseño
- APIs complejas (IESS, SRI, bancos)
