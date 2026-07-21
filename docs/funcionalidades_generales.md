# Funcionalidades Generales de Lucho — Especificación v1.0

---

## 1. Onboarding de Nuevos Usuarios

### 1.1 Flujo (3 pasos)

```
Paso 0: Bienvenida
  ↓
  "👋 ¡Hola! Soy Lucho, tu asistente personal ecuatoriano..."
  Muestra todas las capacidades (vehículos, documentos, finanzas, etc.)
  "¿Cómo quieres que te llame?"
  ↓
Paso 1: Nombre
  ↓
  Usuario responde con su nombre ("Pato", "Juan")
  "¡Perfecto Pato! Tienes 7 días de prueba GRATIS..."
  ↓
Paso 2: Trial activo
  ↓
  Acceso completo por 7 días sin datos de pago
  Al expirar → flujo post-pago (cédula, email, nombre, políticas)
```

### 1.2 Estados

| Paso | `onboarding_step` | `onboarding_complete` |
|------|-------------------|-----------------------|
| Recién llegado | 0 | false |
| Nombre dado | 1 → 2 | false → true |
| Trial expirado | 3 → 6 | true (pero sin pago) |

### 1.3 Código

- `app/routers/whatsapp_webhook.py`: `_send_onboarding_step0()`, `_send_onboarding_step1()`
- `app/routers/webhook.py`: equivalentes para Telegram
- `app/services/user.py`: `check_access()`, `advance_post_pago_step()`

---

## 2. Sistema de Suscripción

### 2.1 Planes

| Plan | Trial | Vehículos | Precio |
|------|-------|-----------|--------|
| Trial | 7 días gratis | 2 | $0 |
| Básico | — | 2 | Por definir |
| Premium | — | Ilimitado | Por definir |

### 2.2 Tablas

| Tabla | Propósito |
|-------|-----------|
| `subscription_plans` | Planes disponibles con features JSONB |
| `subscriptions` | Suscripción activa del usuario (status, trial_ends_at) |
| `payments` | Pagos realizados |
| `subscription_invoices` | Facturas de suscripción |

### 2.3 Post-pago (al expirar trial)

```
Trial expira → onboarding_step = 3
  ↓
Paso 3: "¿Cuál es tu número de cédula?"
Paso 4: "¿Cuál es tu correo electrónico?"
Paso 5: "¿Cómo te llamas? (nombre completo)"
Paso 6: "¿Aceptas las políticas de privacidad?"
  ↓
Datos guardados en user_profiles
  ↓
Pendiente: integración de pago (Kushki/PayPhone) — Fase 3
```

---

## 3. WhatsApp-Specific

### 3.1 Debounce (anti-duplicados)

Meta envía el mismo mensaje múltiples veces. Lucho espera **3 segundos** después del último mensaje antes de procesar. Todos los mensajes en esa ventana se concatenan y procesan juntos.

```
Mensaje 1 a t=0s  ─┐
Mensaje 2 a t=1s  ─┤  espera 3s...
Mensaje 3 a t=2s  ─┘
                   ↓ t=5s
              Procesa "mensaje 1 + mensaje 2 + mensaje 3" juntos
```

**Código**: `app/routers/whatsapp_webhook.py` — función `_debounce_agent_call()`

### 3.2 Typing Indicator

Cada mensaje entrante recibe `send_typing(message_id)` → WhatsApp muestra los tres puntitos `...`.

### 3.3 Fotos y Documentos (manejo de media)

| Tipo | WhatsApp Type | Qué hace Lucho |
|------|--------------|----------------|
| Foto | `image` | Descarga → MinIO → `[foto: key]`. Si no hay texto: pregunta qué hacer. Si hay texto: procesa instrucción. |
| Documento | `document` | Descarga → MinIO → `[documento: nombre → key]`. Ídem. |
| Audio | `audio` | Descarga → MinIO → Whisper transcripción. |
| Sticker | `sticker` | "Todavía no puedo ver stickers 😅" |
| Video | `video` | "Todavía no sé procesar video" |

**Archivo sin instrucción**:
```
1. Descarga → MinIO
2. NO analiza, NO guarda
3. Responde: "📷 Recibí tu foto. ¿Querés que la analice, la guarde, o qué hacemos?"
4. No llama al LLM (respuesta inmediata desde el webhook)
```

**Archivo con instrucción**: 
```
1. Descarga → MinIO
2. Crea [foto: key] + texto del usuario
3. Envía al LLM con contexto completo
4. LLM decide tools a llamar (analyze_image, save_document, etc.)
```

### 3.4 Templates WhatsApp

| Template | Params | Estado |
|----------|--------|--------|
| `document_reminder` | 6 | ✅ es |
| `project_reminder` | 6 | ⚠️ en (pendiente es) |
| `pico_y_placa` | 2 | ✅ es |
| `daily_digest` | 1 | ✅ es |
| `event_reminder` | 5 | ⏳ Pendiente crear |
| `budget_alert` | 5 | ⏳ Pendiente crear |

---

## 4. Telegram

Telegram sigue el mismo flujo que WhatsApp pero sin restricciones:
- Sin debounce (Telegram no duplica)
- Sin typing indicator
- Sin límite de 24h para mensajes
- Markdown completo (sin restricciones de formato)
- Sin templates (mensajes directos siempre)

**Código**: `app/routers/webhook.py`

---

## 5. Infraestructura

### 5.1 Servicios

| Servicio | Puerto | Tecnología |
|----------|--------|-----------|
| Lucho API | 8000 | FastAPI + Uvicorn |
| Cloudflare Tunnel | 20241 | cloudflared → lucho-dev.apx5.com |
| PostgreSQL | 5432 | pgvector |
| Redis | 6379 | Memoria de sesión |
| MinIO | 9000 | Almacenamiento de archivos |

### 5.2 Systemd

```bash
systemctl --user start lucho-api lucho-tunnel
systemctl --user status lucho-api
journalctl --user -u lucho-api -f
```

### 5.3 APScheduler Jobs

| Job | Horario | Función |
|-----|---------|---------|
| `daily_rules` | 8:00 AM | Eventos, docs, proyectos, pico y placa, presupuestos |
| `daily_digest` | 8:00 AM | Resumen matutino personalizado |
| Ad-hoc | Bajo demanda | Recordatorios con hora exacta (DateTrigger) |

---

## 6. Skills Ecuador

7 skills precargadas que el LLM consulta bajo demanda:

| Skill | Dominio | Se carga... |
|-------|--------|-------------|
| `idioms.md` | Cultura | Siempre (modismos ecuatorianos) |
| `cuisine.md` | Cultura | Si pregunta de comida |
| `holidays.md` | Cultura | Si pregunta de feriados |
| `documents.md` | Legal | Si pregunta de trámites |
| `invoicing.md` | Tax | Si pregunta de facturación/SRI |
| `driving-restrictions.md` | Tránsito | Si pregunta de pico y placa |
| `registration.md` | Tránsito | Si pregunta de matriculación |

**Código**: `app/agent/skills/`

---

## 7. Herramientas Transversales

### 7.1 `update_last` — Corrección rápida

Corrige el último registro de un tipo sin preguntar. El LLM lo usa cuando el usuario dice "no, era...", "corregí...", "cambiale...".

```
Usuario: "Cita dentista lunes 3pm"
Lucho: guarda evento

Usuario: "no, era 4pm"
Lucho: update_last(entity_type="event", field="target_date", new_value="...T16:00")
```

**Tipos soportados**: `event`, `note`, `list`, `document`.

### 7.2 `get_my_summary` — Resumen rápido

Genera un resumen textual de los datos del usuario (vehículos, eventos, pendientes). El LLM decide si usarlo o no según el contexto. Menos usado que las búsquedas específicas.

### 7.3 `send_photo` — Envío de archivos

Envía al usuario una foto o documento desde MinIO usando el `file_key`. El LLM lo llama automáticamente cuando un resultado de búsqueda incluye `file_key`.

### 7.4 `check_vehicle_info` — Consulta externa

Consulta la API de ANT/SRI para obtener datos oficiales de un vehículo por placa: marca, modelo, año, multas, estado de matriculación. Documentado en el módulo de Vehículos.

---

## 8. Zona Horaria

**Regla no negociable (AGENTS.md §2.4)**:
- Todo se almacena en hora local Ecuador (America/Guayaquil, UTC-5)
- Cero conversiones de zona horaria
- `events.target_date` es `TIMESTAMP WITHOUT TIME ZONE`
- PostgreSQL, SO Linux, APScheduler → todo en hora Ecuador
