# Módulo de Recordatorios — Especificación v1.0

---

## 1. Visión General

Lucho agenda, recuerda y notifica eventos y citas del usuario. Soporta recordatorios con días de anticipación (para planificación) y recordatorios de precisión sub-día ("avísame en 5 minutos"). El usuario habla naturalmente y Lucho extrae fecha, hora, título y recurrencia. Las notificaciones se entregan por Telegram y WhatsApp (template + mensaje directo).

---

## 2. Experiencia de Usuario

### 2.1 Agendar un evento

> **Usuario**: "cita con el dentista el lunes a las 3pm"
>
> **Lucho**: "Agendado: Cita con el dentista el lunes 27 de julio a las 3pm. ¿Te aviso unos días antes?"

> **Usuario**: "reunión equipo AURACORE todos los viernes 10am"
>
> **Lucho**: "Listo. Reunión equipo AURACORE todos los viernes a las 10am. Se repite semanalmente."

> **Usuario**: "recuérdame llamar a mamá en 10 minutos"
>
> **Lucho**: "¡Dale! Te aviso a las 3:25 PM para que llames a tu mamá."

### 2.2 Recibir recordatorios

> *[8:00 AM, 7 días antes]* **Lucho**: "🟢 *Recordatorio de evento* — 📌 Cita con el dentista — 📅 en 7 días (2026-08-03 15:00)"

> *[8:00 AM, 3 días antes]* **Lucho**: "🟡 *Recordatorio de evento* — 📌 Cita con el dentista — 📅 en 3 días (2026-08-03 15:00)"

> *[8:00 AM, día del evento]* **Lucho**: "🔴 *Recordatorio de evento* — 📌 Cita con el dentista — 📅 HOY a las 15:00"

> *[15:00, hora exacta]* **Lucho**: "🔴 *Recordatorio de evento* — 📌 Cita con el dentista — 📅 HOY a las 15:00" *(ad-hoc)*

### 2.3 Consultar eventos

> **Usuario**: "¿qué tengo esta semana?"
>
> **Lucho**: "Esta semana tenés:\n📅 Lunes 27 — Cita dentista 3pm\n📅 Viernes 31 — Reunión AURACORE 10am"

### 2.4 Completar o cancelar

> **Usuario**: "ya fui al dentista"
>
> **Lucho**: "¡Qué bien! Marco la cita del dentista como completada. ¿Todo bien?"

> **Usuario**: "cancelá la reunión del viernes"
>
> **Lucho**: "Listo. Reunión AURACORE del viernes cancelada."

---

## 3. Modelo de Datos

### 3.1 Tabla `events`

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | UUID | PK |
| `user_id` | UUID FK | Dueño |
| `asset_id` | UUID FK nullable | Evento vinculado a un asset (matriculación, SOAT) |
| `title` | VARCHAR(512) | Título corto |
| `description` | TEXT nullable | Detalles adicionales |
| `target_date` | **TIMESTAMP WITHOUT TZ** | Fecha y hora del evento (hora local Ecuador) |
| `certainty` | ENUM | `certain` (fecha fija) o `estimated` (aproximada) |
| `recurrence_rule` | JSONB nullable | `{"freq": "weekly", "interval": 1, "days": [4]}` |
| `status` | ENUM | `upcoming`, `done`, `cancelled`, `overdue` |
| `completed_at` | TIMESTAMPTZ nullable | Cuándo se completó |
| `created_at` | TIMESTAMPTZ | Fecha de creación |
| `updated_at` | TIMESTAMPTZ | Última modificación |

### 3.2 Tabla `reminders` (audit trail + idempotencia)

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | UUID | PK |
| `event_id` | UUID FK | Evento asociado |
| `days_before` | INTEGER | 15, 7, 3, 0 |
| `channel` | ENUM | `telegram`, `whatsapp` |
| `status` | ENUM | `pending`, `sent`, `acknowledged`, `failed` |
| `scheduled_for` | TIMESTAMPTZ | Cuándo debía enviarse |
| `sent_at` | TIMESTAMPTZ nullable | Cuándo se envió realmente |
| `message_text` | TEXT nullable | Mensaje exacto enviado |
| `user_response` | TEXT nullable | Respuesta del usuario |

**Propósito**: Evitar envíos duplicados. Antes de enviar un recordatorio, se verifica que no exista uno para el mismo `event_id + days_before`.

### 3.3 Zona Horaria

**Regla no negociable (AGENTS.md §2.4)**: Todas las fechas/horas en `events.target_date` se almacenan en hora local Ecuador (America/Guayaquil, UTC-5). Cero conversiones de zona horaria en el código. `datetime.now()` devuelve la hora del sistema (Ecuador).

### 3.4 ENUMs

```sql
event_certainty: 'certain', 'estimated'
event_status: 'upcoming', 'done', 'cancelled', 'overdue'
reminder_channel: 'telegram', 'whatsapp'
reminder_status: 'pending', 'sent', 'acknowledged', 'failed'
```

---

## 4. Tools del Agente

### 4.1 `save_event` — Agendar evento

```json
{
  "name": "save_event",
  "description": "Guardar un evento, cita, reunión o recordatorio con fecha y hora. El usuario será notificado automáticamente antes.",
  "parameters": {
    "type": "object",
    "properties": {
      "title": "Título corto. Ej: 'Cita dentista', 'Reunión banco'.",
      "target_date": "Fecha YYYY-MM-DD o YYYY-MM-DDTHH:MM. Si dice 'en 5 min' calculá la hora real. Si no menciona hora, solo fecha.",
      "description": "Detalles adicionales.",
      "recurrence": "'none', 'daily', 'weekly', 'monthly', 'yearly'.",
      "file_key": "Clave MinIO si el usuario adjuntó foto (receta, invitación)."
    },
    "required": ["title", "target_date"]
  }
}
```

**Flujo interno al guardar**:
1. `persist_event()` guarda en DB con hora local Ecuador
2. Si `target_date.hour != 0 OR target_date.minute != 0` → `schedule_event_reminder()` crea job ad-hoc
3. El job ad-hoc dispara `_send_event_reminder()` a la hora exacta
4. El CRON diario (8AM) evalúa las ventanas largas (15/7/3/0 días)

### 4.2 `list_my_events` — ✅ Implementado

```json
{
  "name": "list_my_events",
  "description": "Listar eventos con filtros por estado y período.",
  "parameters": {
    "status": "'upcoming', 'done', 'cancelled', 'overdue', 'all'. Default: 'upcoming'.",
    "period": "'today', 'tomorrow', 'this_week', 'next_week', 'this_month', 'all'. Default: 'all' (90 días)."
  },
  "required": []
}
```

### 4.3 `update_last` — Modificar o cancelar evento (existente)

El tool `update_last` permite modificar el último evento guardado. El LLM puede usarlo cuando el usuario dice "cancelá la cita", "cambia la fecha", "ya fui al dentista".

---

## 5. Motor de Recordatorios (Scheduler)

### 5.1 CRON diario — `_evaluate_events()`

**Horario**: 8:00 AM todos los días.

**Lógica**:
```
1. SELECT eventos con status='upcoming' y target_date entre HOY y HOY+15
2. Para cada evento, calcular days_until = (target_date - hoy).days
3. Si days_until coincide con una ventana (15, 7, 3, 0):
   a. Verificar que no exista reminder para ese event_id + days_before
   b. Enviar notificación (_send_event_reminder)
   c. Registrar en tabla reminders (idempotencia)
   d. Break (un recordatorio por evento por día)
```

**Ventanas**:
| Días antes | Emoji | Significado |
|-----------|-------|-------------|
| 15 | 🟢 | Planificación temprana |
| 7 | 🟢 | Una semana |
| 3 | 🟡 | Se acerca |
| 0 (HOY) | 🔴 | Es hoy |

### 5.2 Recordatorio ad-hoc — `schedule_event_reminder()`

**Cuándo**: Cuando el evento tiene hora específica (no es medianoche).

**Lógica**:
```
1. handle_save_event detecta target_date con hora != 00:00
2. Llama a schedule_event_reminder(event_id, target_datetime)
3. Crea un DateTrigger job en APScheduler para target_datetime exacto
4. Cuando se dispara: carga el evento de DB → _send_event_reminder()
```

**Precisión**: Al segundo. Usa `datetime.now()` del sistema (hora Ecuador).

**Protección**: Si `target_datetime <= now`, no agenda (ya pasó).

### 5.3 Canales de notificación

Cada recordatorio se envía por **dos canales**:

| Canal | Método | Restricción |
|-------|--------|-------------|
| **Telegram** | `send_notification()` → `telegram_svc.send_message()` | Sin restricción |
| **WhatsApp** | `send_template_message("event_reminder", ...)` | Sin restricción (template) |
| **WhatsApp** | `send_message()` (directo) | Ventana 24h (respaldo si template falla) |

La función `resolve_user_contact()` decide el canal primario: Telegram si tiene `telegram_id`, sino WhatsApp si tiene `whatsapp_id`.

---

## 6. Template WhatsApp

### `event_reminder` — Pendiente crear en Meta ⏳

| Param | Contenido | Ejemplo |
|-------|-----------|---------|
| {{1}} | Emoji urgencia | 🔴 |
| {{2}} | Título evento | Cita con el dentista |
| {{3}} | Días texto | HOY a las 15:00 |
| {{4}} | Fecha | 2026-08-03 15:00 |
| {{5}} | Título (repeat) | Cita con el dentista |

**Especificación completa**: `docs/whatsapp_templates.md` — Template 5.

---

## 7. Formato de Notificación

### Telegram (Markdown)

```
🔴 *Recordatorio de evento*

📌 *Cita con el dentista*
📝 Limpieza dental semestral
📅 Fecha: HOY a las 15:00 (2026-07-27 15:00)

Si ya pasó o querés cambiarlo, decime y lo actualizo.
```

### WhatsApp (texto directo, mismo formato)

Mismo contenido, WhatsApp renderiza *negrita* y soporta emojis.

---

## 8. Reglas de Negocio

1. **Confirmación antes de guardar**: El LLM debe confirmar lo que entendió. El usuario corrige en lenguaje natural.
2. **No duplicar**: `update_last` modifica en vez de crear nuevo evento si el usuario corrige inmediatamente.
3. **Detección de "ya pasó"**: Si el usuario dice "ya fui al dentista", el LLM busca el evento y lo marca `done`.
4. **Recurrencia**: Si `recurrence_rule` no es null, el scheduler diario encuentra el próximo evento de la serie.
5. **Eventos de vehículos**: `_evaluate_vehicle_assets` crea eventos automáticos de matriculación → se integran al mismo flujo.
6. **Hora local**: Nunca UTC. `datetime.now()` = hora Ecuador. `target_date` = TIMESTAMP WITHOUT TZ.
7. **Sub-día**: Si el evento es hoy con hora → job ad-hoc. Si es mañana o después → solo CRON diario.
8. **Eventos pasados**: Si `target_date < today` y `status=upcoming`, el scheduler diario los marca automáticamente `overdue`.

---

## 9. Lo que YA existe

| Componente | Estado |
|------------|--------|
| `Event` model con `target_date` TIMESTAMP | ✅ v2.11.2 |
| `Reminder` model (audit trail) | ✅ |
| `save_event` tool | ✅ |
| `list_my_events` tool — filtros por status y período | ✅ |
| `_evaluate_events` scheduler (15/7/3/0 días) + overdue automático | ✅ |
| `_send_event_reminder` multicanal | ✅ |
| `schedule_event_reminder` ad-hoc | ✅ v2.11.0 |
| `_ad_hoc_event_reminder` job handler | ✅ |
| Detección de duplicados vía `reminders` table | ✅ |
| Integración con vehículos (`_ensure_event`) | ✅ |
| `update_last` para modificar/cancelar | ✅ |
| Hora local Ecuador (cero TZ) | ✅ v2.11.2 |

---

## 10. Mejoras pendientes

| Tarea | Prioridad |
|-------|-----------|
| Template `event_reminder` en Meta | 🔴 Crítica |
| Procesar recurrencia correctamente (próximo evento de la serie) | 🟡 Media |
| Snooze / posponer recordatorio ("avisame en 10 min de nuevo") | 🟢 Baja |
| Invitaciones a calendario (.ics) | ⚪ Futuro |
| Integración Google Calendar | ⚪ Futuro |
