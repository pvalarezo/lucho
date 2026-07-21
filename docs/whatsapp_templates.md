# WhatsApp Templates — Lucho

Plantillas de mensajes para notificaciones proactivas fuera de la ventana de 24h.
Deben crearse en Meta Business Manager y ser aprobadas por Meta antes de usarse.

---

## Dónde crear las plantillas

1. Ir a https://developers.facebook.com/
2. Seleccionar la app de Lucho
3. **WhatsApp** → **Administrador de plantillas** → **Crear plantilla**
4. Llenar cada template según las especificaciones abajo
5. Enviar a revisión (Meta tarda 24-48h en aprobar)

---

## Template 1: `document_reminder`

**Recordatorio de documento por vencer** (SOAT, cédula, licencia, garantía, etc.)

| Campo | Valor |
|-------|-------|
| Nombre | `document_reminder` |
| Categoría | `UTILITY` |
| Idioma | `es` (Spanish) |

### Header (tipo Texto)

```
Recordatorio de documento 📄
```

### Body

```
Hola. Te informo que:

📄 {{1}} {{2}} ({{3}})
Vence: {{4}} ({{5}})

Si ya lo renovaste, responde "ya renové {{6}}" y lo actualizo.
```

### Variables

| # | Muestra | Descripción |
|---|---------|-------------|
| {{1}} | 🔴 | Emoji de urgencia (🔴 ≤7 días, 🟡 ≤15, 🟢 ≤30) |
| {{2}} | SOAT PBC1234 | Nombre del documento |
| {{3}} | soat | Tipo de documento |
| {{4}} | en 7 días | Texto descriptivo del vencimiento |
| {{5}} | 2026-07-22 | Fecha de vencimiento (ISO) |
| {{6}} | SOAT PBC1234 | Nombre del documento (igual que {{2}}, repetido por regla de Meta) |

> ⚠️ `{{2}}` y `{{6}}` tienen el mismo valor (nombre del documento). Meta no permite repetir la misma variable en el body, por eso se usa un número distinto. El código debe enviar `body_params[1]` y `body_params[5]` con el mismo string.

### Ejemplo renderizado

> Hola. Te informo que:
>
> 📄 🔴 SOAT PBC1234 (soat)
> Vence: en 7 días (2026-07-22)
>
> Si ya lo renovaste, responde "ya renové SOAT PBC1234" y lo actualizo.

---

## Template 2: `project_reminder`

**Recordatorio de tarea de proyecto por vencer**

| Campo | Valor |
|-------|-------|
| Nombre | `project_reminder` |
| Categoría | `UTILITY` |
| Idioma | `es` (Spanish) |

### Header (tipo Texto)

```
Recordatorio de proyecto 📋
```

### Body

```
Hola. Te informo que:

📋 {{1}} Proyecto: {{2}}
Tarea: {{3}}
Vence: {{4}} ({{5}})

Cuando la termines, responde "completé {{6}}".
```

### Variables

| # | Muestra | Descripción |
|---|---------|-------------|
| {{1}} | 🟡 | Emoji de urgencia (🔴 ≤1 día, 🟡 ≤3, 🟢 ≤7) |
| {{2}} | Tienda Online | Nombre del proyecto |
| {{3}} | Configurar pasarela de pago | Contenido de la tarea |
| {{4}} | en 3 días | Texto descriptivo del vencimiento |
| {{5}} | 2026-07-19 | Fecha de vencimiento (ISO) |
| {{6}} | Configurar pasarela de pago | Contenido de la tarea (igual que {{3}}, repetido por regla de Meta) |

> ⚠️ `{{3}}` y `{{6}}` tienen el mismo valor (contenido de la tarea). Meta no permite repetir la misma variable en el body.

### Ejemplo renderizado

> Hola. Te informo que:
>
> 📋 🟡 Proyecto: Tienda Online
> Tarea: Configurar pasarela de pago
> Vence: en 3 días (2026-07-19)
>
> Cuando la termines, responde "completé Configurar pasarela de pago".

---

## Template 3: `pico_y_placa`

**Aviso de restricción vehicular Pico y Placa**

| Campo | Valor |
|-------|-------|
| Nombre | `pico_y_placa` |
| Categoría | `UTILITY` |
| Idioma | `es` (Spanish) |

### Header (tipo Texto)

```
Pico y Placa 🚗
```

### Body

```
⚠️ Tu vehículo {{1}} tiene pico y placa {{2}}.
```

### Variables

| # | Muestra | Descripción |
|---|---------|-------------|
| {{1}} | PBC1234 | Placa del vehículo |
| {{2}} | mañana viernes | Día(s) de restricción |

### Ejemplo renderizado

> ⚠️ Tu vehículo PBC1234 tiene pico y placa mañana viernes.

---

## Template 4: `daily_digest`

**Resumen matutino diario generado por IA**

| Campo | Valor |
|-------|-------|
| Nombre | `daily_digest` |
| Categoría | `UTILITY` |
| Idioma | `es` (Spanish) |

### Header (tipo Texto)

```
Resumen diario ☀️
```

### Body

```
☀️ Tu resumen de hoy:

{{1}}

—
Lucho
```

### Variables

| # | Muestra | Descripción |
|---|---------|-------------|
| {{1}} | (texto generado por IA) | Resumen completo del día |

> ⚠️ Body con texto fijo al inicio (`☀️ Tu resumen de hoy:`) y al cierre (`— Lucho`). Sin CTAs ni preguntas para que Meta lo clasifique como UTILITY.

---

## Template 5: `event_reminder` 🆕

**Recordatorio de evento/cita** (reuniones, citas médicas, cumpleaños, etc.)

| Campo | Valor |
|-------|-------|
| Nombre | `event_reminder` |
| Categoría | `UTILITY` |
| Idioma | `es` (Spanish) |

### Header (tipo Texto)

```
Recordatorio de evento 📌
```

### Body

```
Hola. Te recuerdo que:

📌 {{1}} {{2}}
📅 Fecha: {{3}} ({{4}})

Si ya pasó o querés cambiarlo, responde "actualizar {{5}}".
```

### Variables

| # | Muestra | Descripción |
|---|---------|-------------|
| {{1}} | 🔴 | Emoji de urgencia (🔴 HOY, 🟡 ≤3 días, 🟢 >3) |
| {{2}} | Cita con el dentista | Título del evento |
| {{3}} | HOY | Texto descriptivo (HOY, mañana, en 7 días) |
| {{4}} | 2026-07-22 | Fecha del evento (ISO) |
| {{5}} | Cita con el dentista | Título del evento (igual que {{2}}, repetido por regla de Meta) |

> ⚠️ `{{2}}` y `{{5}}` tienen el mismo valor (título del evento). Meta no permite repetir la misma variable en el body.

### Ejemplo renderizado

> Hola. Te recuerdo que:
>
> 📌 🔴 Cita con el dentista
> 📅 Fecha: HOY (2026-07-22)
>
> Si ya pasó o querés cambiarlo, responde "actualizar Cita con el dentista".

---

## Resumen para creación rápida

| # | Nombre | Header | Body vars | Categoría |
|---|--------|--------|-----------|-----------|
| 1 | `document_reminder` | Recordatorio de documento 📄 | 6 | UTILITY |
| 2 | `project_reminder` | Recordatorio de proyecto 📋 | 6 | UTILITY |
| 3 | `pico_y_placa` | Pico y Placa 🚗 | 2 | UTILITY |
| 4 | `daily_digest` | Buenos días ☀️ | 1 | UTILITY |
| 5 | `event_reminder` 🆕 | Recordatorio de evento 📌 | 5 | UTILITY |

---

## Notas importantes

- **Categoría UTILITY**: Para notificaciones transaccionales/recordatorios. No requiere opt-in de marketing.
- **Tiempo de aprobación**: 24-48 horas hábiles.
- **Sin botones ni acciones**: En esta primera versión los templates no llevan botones interactivos. Se pueden agregar en el futuro (ej. "Marcar como completado").
- **El código ya está listo**: `send_template_message()` en `app/services/whatsapp.py` acepta `template_name` y `language_code`. Solo falta conectar el scheduler.

---

## Pendiente post-aprobación

Cuando Meta apruebe los templates, modificar `app/services/scheduler.py` para que:
- `_send_document_reminder` → use `send_template_message("document_reminder", ...)`
- `_send_project_reminder` → use `send_template_message("project_reminder", ...)`
- `run_daily_digest` → agregar envío WhatsApp con `send_template_message("daily_digest", ...)`
- Agregar job de pico y placa con `send_template_message("pico_y_placa", ...)`
