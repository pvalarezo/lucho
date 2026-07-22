# Módulo de Proyectos y Tareas — Especificación v1.0

---

## 1. Visión General

Lucho organiza proyectos del usuario como contenedores de tareas con fechas de entrega. A diferencia de las listas (ítems simples pendiente/hecho), los proyectos agrupan tareas con `due_date` y envían recordatorios anticipados. Simple: sin dependencias entre tareas, sin gestión formal de proyectos. El usuario dicta tareas, Lucho las asigna al proyecto correcto y recuerda antes de cada fecha límite.

---

## 2. Experiencia de Usuario

### 2.1 Crear proyecto y tareas

> **Usuario**: "proyecto Tienda Online: configurar pasarela de pago para el viernes, diseñar logo para el 30, comprar dominio"
>
> **Lucho**: "¡De ley! Creé el proyecto Tienda Online con 3 tareas:\n📝 Configurar pasarela de pago — vence viernes 24\n📝 Diseñar logo — vence 30 de julio\n📝 Comprar dominio — sin fecha"

> **Usuario**: "agrega al proyecto Tienda Online: configurar envíos para el 5 de agosto"
>
> **Lucho**: "Agregado: configurar envíos al proyecto Tienda Online. Vence 5 de agosto."

### 2.2 Recibir recordatorios

> *[8:00 AM, 7 días antes]* **Lucho**: "🟢 *Recordatorio de proyecto* — 📋 Tienda Online — 📝 Configurar pasarela de pago — Vence en 7 días (2026-07-24)"

> *[8:00 AM, 1 día antes]* **Lucho**: "🔴 *Recordatorio de proyecto* — 📋 Tienda Online — 📝 Configurar pasarela de pago — Vence mañana (2026-07-24)"

### 2.3 Consultar proyectos

> **Usuario**: "¿cómo va el proyecto Tienda Online?"
>
> **Lucho**: "📋 Tienda Online — 3 pendientes, 1 completada:\n📝 Configurar pasarela de pago — vence viernes\n📝 Diseñar logo — vence 30 julio\n📝 Configurar envíos — vence 5 agosto\n✅ Comprar dominio — completado"

### 2.4 Completar tareas

> **Usuario**: "ya compré el dominio"
>
> **Lucho**: "¡Bien! Marco 'Comprar dominio' como completado en Tienda Online. Te quedan 3 pendientes."

---

## 3. Modelo de Datos

### 3.1 Tabla `projects`

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | UUID | PK |
| `user_id` | UUID FK | Dueño |
| `name` | VARCHAR(256) | Nombre del proyecto: "Tienda Online", "Casa" |
| `status` | ENUM | `active`, `archived` |
| `created_at` | TIMESTAMPTZ | Fecha creación |
| `updated_at` | TIMESTAMPTZ | Última modificación |

**Índice único**: `idx_projects_user_name` sobre (`user_id`, `name`).

### 3.2 Tabla `project_tasks`

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | UUID | PK |
| `project_id` | UUID FK | Proyecto al que pertenece |
| `content` | TEXT | Descripción de la tarea |
| `status` | ENUM | `pending`, `done` |
| `due_date` | DATE nullable | Fecha de entrega |
| `reminder_sent` | BOOLEAN | ¿Ya se envió recordatorio de vencimiento? |
| `created_at` | TIMESTAMPTZ | Fecha creación |
| `completed_at` | TIMESTAMPTZ nullable | Cuándo se completó |

**Índices**: (`project_id`, `status`), (`due_date`).

### 3.3 ENUMs

```sql
project_status: 'active', 'archived'
task_status: 'pending', 'done'
```

### 3.4 Diferencia clave: Proyecto vs Lista

| | Proyecto | Lista |
|---|----------|-------|
| Tiene `due_date` | ✅ Sí | ❌ No |
| Recordatorios | ✅ Sí (7/3/1 días) | ❌ No |
| Agrupación | 1 proyecto → N tareas | 1 lista → N ítems |
| Índice único | `user_id + name` | No (puede haber listas duplicadas) |
| Estado contenedor | `active`/`archived` | No tiene |
| Herramienta | `save_project_task` | `save_list` |

---

## 4. Tools del Agente

### 4.1 `save_project_task` — Ya existe ✅

```json
{
  "name": "save_project_task",
  "description": "Agregar una tarea a un proyecto. Si el proyecto no existe, se crea automáticamente.",
  "parameters": {
    "project_name": "Nombre del proyecto.",
    "content": "Descripción de la tarea.",
    "due_date": "Fecha YYYY-MM-DD. Opcional."
  },
  "required": ["project_name", "content"]
}
```

### 4.2 `list_project_tasks` — Ya existe ✅

```json
{
  "name": "list_project_tasks",
  "description": "Listar tareas de un proyecto o de todos. Si no se pasa project_name, muestra todos los proyectos activos.",
  "parameters": {
    "project_name": "Nombre del proyecto. Opcional (lista todos).",
    "status": "'pending', 'done', o 'all'. Default: 'all'."
  },
  "required": []
}
```

### 4.3 `complete_project_task` — Ya existe ✅

```json
{
  "name": "complete_project_task",
  "description": "Marcar una tarea como completada (busca por coincidencia parcial en contenido).",
  "parameters": {
    "project_name": "Proyecto donde buscar.",
    "task_content": "Contenido de la tarea a completar."
  },
  "required": ["project_name", "task_content"]
}
```

### 4.4 `reopen_project_task` — ✅ Implementado

```json
{
  "name": "reopen_project_task",
  "description": "Reabrir una tarea completada (done → pending). Resetea reminder_sent.",
  "parameters": {
    "project_name": "Proyecto donde buscar.",
    "task_content": "Contenido de la tarea a reabrir (busca en completadas)."
  },
  "required": ["project_name", "task_content"]
}
```

### 4.5 `archive_project` — ✅ Implementado

```json
{
  "name": "archive_project",
  "description": "Archivar un proyecto (status → archived). Las tareas no se borran.",
  "parameters": {
    "project_name": "Nombre del proyecto a archivar."
  },
  "required": ["project_name"]
}
```

---

## 5. Motor de Recordatorios (Scheduler)

### 5.1 `_evaluate_project_tasks()` — CRON diario 8:00 AM

**Ventanas**: 7, 3, 1 días antes del `due_date`.

**Lógica**:
```
1. SELECT project_tasks con status='pending' y due_date entre HOY y HOY+7
2. Para cada tarea, calcular days_until
3. Si days_until coincide con una ventana (7, 3, 1) y reminder_sent == False:
   a. Enviar notificación (_send_project_reminder)
   b. Si days_until == 0: marcar reminder_sent = True
```

A diferencia de eventos (15/7/3/0), los proyectos usan ventanas más cortas (7/3/1) porque son operativos.

### 5.2 Canales

| Canal | Método |
|-------|--------|
| **Telegram** | `send_notification()` mensaje directo |
| **WhatsApp** | `send_template_message("project_reminder", "en", [...])` |

### 5.3 Template WhatsApp

**`project_reminder`** — Aprobado en inglés (`language_code="en"`). Pendiente traducción español.

| Param | Contenido |
|-------|-----------|
| {{1}} | Emoji urgencia |
| {{2}} | Nombre proyecto |
| {{3}} | Contenido tarea |
| {{4}} | Días texto |
| {{5}} | Fecha vencimiento |
| {{6}} | Contenido tarea (repeat) |

---

## 6. Formato de Respuesta

```
📋 *Tienda Online* — 3 pendientes

  🔴 Configurar pasarela de pago — vence HOY
  🟡 Diseñar logo — vence en 3 días (30 jul)
  🟢 Configurar envíos — vence en 11 días (5 ago)
```

---

## 7. Reglas de Negocio

1. **Proyecto único por nombre**: `idx_projects_user_name` garantiza unicidad. Si se intenta crear "Tienda Online" y ya existe, se agrega la tarea al existente.
2. **Tareas sin fecha**: `due_date` es opcional. Si no tiene fecha, no genera recordatorios.
3. **Recordatorio único**: `reminder_sent` evita múltiples notificaciones. Se resetea si la tarea se reabre.
4. **Archivado**: `project.status = 'archived'` oculta el proyecto sin borrar datos.
5. **Sin dependencias**: No hay tareas bloqueadas por otras. Simple y plano.

---

## 8. Lo que YA existe

| Componente | Estado |
|------------|--------|
| `projects` + `project_tasks` tablas | ✅ |
| `save_project_task` tool | ✅ |
| `list_project_tasks` tool — con/sin `project_name`, filtro `status` | ✅ |
| `complete_project_task` tool | ✅ |
| `reopen_project_task` tool — done → pending, resetea `reminder_sent` | ✅ |
| `archive_project` tool — `status = 'archived'`, no borra datos | ✅ |
| `_evaluate_project_tasks` scheduler (7/3/1 días) | ✅ |
| `_send_project_reminder` multicanal (Telegram + WhatsApp) | ✅ |
| Template `project_reminder` (en) aprobado | ✅ |
| Índices de búsqueda | ✅ |

---

## 9. Mejoras pendientes

| Tarea | Prioridad |
|-------|-----------|
| Template `project_reminder` en español | 🔴 Crítica (pendiente Meta) |
| Tareas con hora (no solo fecha) | 🟢 Baja |
