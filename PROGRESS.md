# PROGRESS.md — Lucho

Estado actual de cada fase, módulo y entregable. Fase 1 completada con rediseño a agente.

---

## Fase 0 — Validación ✅ COMPLETADA
## Fase 1 — MVP Técnico ✅ COMPLETADA (v2.10.0)

### Versiones
| Tag | Fecha | Descripción |
|-----|-------|-------------|
| v2.11.2 | 2026-07-21 | Hora local Ecuador: `TIMESTAMPTZ` → `TIMESTAMP`, cero conversiones TZ. System prompt incluye hora actual. Ad-hoc reminders 100% funcionales. |
| v2.11.1 | 2026-07-21 | System prompt reforzado: reglas no negociables PRIMERO, tabla tool↔intención, palabras prohibidas explícitas. DeepSeek ahora cumple tool calling. |
| v2.11.0 | 2026-07-21 | Ad-hoc event reminders: `events.target_date` migrado a `TIMESTAMPTZ` con hora. `schedule_event_reminder()` vía `DateTrigger`. `_send_event_reminder` arreglado (antes solo creaba DB records sin enviar). |
| v2.10.1 | 2026-07-21 | WhatsApp Templates: 4/4 verificados y probados con envío real. `project_reminder` usa `language_code="en"` temporal. Script `test_whatsapp_templates.py`. |
| v2.10.0 | 2026-07-20 | Módulo de Vehículos independiente (`vehicles` + `vehicle_maintenances`), 22 tools total. Flujo post-pago (cédula→email→nombre→políticas). Scheduler conectado a WhatsApp templates (4 tipos). Límite vehículos parametrizable por plan. Tests: 307/307 (100%). |
| v2.9.4 | 2026-07-19 | WhatsApp multimedia: descarga imágenes/audio/docs → MinIO, transcripción Whisper. Stickers, inyección file_key, foto sin instrucción. System prompt regla #0 reforzada. Template send_template_message con body_params. |
| v2.9.3 | 2026-07-18 | Suscripción (planes, trial 7 días), onboarding 3 pasos, WhatsApp (reacción, typing, debounce 3s). Tablas: subscription_plans, user_profiles. |
| v2.9.2 | 2026-07-16 | Telegram polling → webhook unificado. |
| v2.9.1 | 2026-07-16 | WhatsApp Templates documentados (4 plantillas). |
| v2.9.0 | 2026-07-16 | OCR/Visión → DeepSeek. Meta Live configurado. |
| v2.8.1 | 2026-07-15 | WhatsApp end-to-end tested. |
| v2.8.0 | 2026-07-14 | WhatsApp Cloud API: send/receive, media, webhook. |
| v2.7.0 | 2026-07-14 | Web search tool (DuckDuckGo). |
| v2.6.0 | 2026-07-13 | Refactor file_key, regla #0 NUNCA MIENTAS. |
| v2.5.0 | 2026-07-13 | Tests: 267 unit offline (100%). |
| v2.4.0 | 2026-07-13 | Skills Ecuador: 7 skills en 4 dominios. |
| v2.3.0 | 2026-07-13 | Envío de fotos/docs: tool send_photo. |
| v2.2.0 | 2026-07-12 | Proyectos/tareas, recordatorios unificados, contactos. |
| v2.1.0 | 2026-07-12 | OCR documentos, digest diario, PDFs. |
| v2.0.0 | 2026-07-12 | Rediseño a arquitectura de agente. |

### Arquitectura — ✅ 100%
- Agente unificado: system prompt + 22 tools + conversation memory
- Skills Ecuador: 7 skills en 4 dominios (culture, transit, legal, tax)
- Canales: Telegram (webhook) + WhatsApp Cloud API (webhook vía Meta Cloud API)
- Cloudflare Tunnel: https://lucho-dev.apx5.com → localhost:8000
- Systemd user services: lucho-api, lucho-tunnel (manual start)
- Telegram migrado a webhook (sin polling aparte)

### Base de Datos — 22 tablas
`users`, `user_profiles`, `messages`, `assets`, `events`, `reminders`, `topics`, `notes`, `lists`, `list_items`, `projects`, `project_tasks`, `contacts`, `caregiver_links`, `shared_expenses`, `shared_expense_participants`, `subscription_plans`, `subscriptions`, `payments`, `subscription_invoices`, **`vehicles`** 🆕, **`vehicle_maintenances`** 🆕

### Tools del Agente — 22 tools

| # | Tool | Módulo | Escritura |
|---|------|--------|-----------|
| 1 | `save_vehicle` | Vehículos 🆕 | ✍️ |
| 2 | `list_my_vehicles` | Vehículos 🆕 | 👁️ |
| 3 | `add_maintenance` | Vehículos 🆕 | ✍️ |
| 4 | `list_maintenances` | Vehículos 🆕 | 👁️ |
| 5 | `save_document` | Documentos | ✍️ |
| 6 | `save_event` | Eventos | ✍️ |
| 7 | `save_list` | Listas | ✍️ |
| 8 | `save_note` | Notas | ✍️ |
| 9 | `save_expense` | Gastos | ✍️ |
| 10 | `search_my_data` | Búsqueda | 👁️ |
| 11 | `search_conversation` | Búsqueda | 👁️ |
| 12 | `web_search` | Búsqueda | 👁️ |
| 13 | `analyze_image` | OCR/Visión | 👁️+✍️ |
| 14 | `get_my_summary` | Resumen | 👁️ |
| 15 | `save_project_task` | Proyectos | ✍️ |
| 16 | `list_project_tasks` | Proyectos | 👁️ |
| 17 | `complete_project_task` | Proyectos | ✍️ |
| 18 | `update_last` | Correcciones | ✍️ |
| 19 | `save_contact` | Contactos | ✍️ |
| 20 | `list_contacts` | Contactos | 👁️ |
| 21 | `check_vehicle_info` | Vehículos | 👁️ |
| 22 | `send_photo` | Archivos | ✍️ |

### Scheduler — ✅ Conectado a WhatsApp Templates

| Recordatorio | Template | body_params | Horario |
|-------------|----------|-------------|---------|
| Documento por vencer | `document_reminder` | 6 params (es) | 8:00 AM |
| Tarea de proyecto | `project_reminder` | 6 params (en ⚠️) | 8:00 AM |
| Pico y placa | `pico_y_placa` | 2 params (es) | 8:00 AM |
| Daily digest | `daily_digest` | 1 param (es) | 8:00 AM |
| **Eventos / Citas** 🆕 | **`event_reminder`** | **5 params (es, pendiente crear en Meta)** | **8:00 AM + ad-hoc** |

### Flujo de Suscripción — ✅ Completo
```
Nuevo usuario → Onboarding (pasos 0→1→2) → Trial 7 días
                                              ↓
                                    Trial expira (día 8)
                                              ↓
                              Post-pago (pasos 3→4→5→6)
                         cédula → email → nombre → políticas
                                              ↓
                                   Datos en user_profiles
                                              ↓
                                   Pendiente: pago (Fase 3)
```

### Meta Live — ✅ 4/5 templates aprobados
- `document_reminder` (es): ✅ aprobado y probado
- `project_reminder` (en): ⚠️ aprobado solo en inglés, `language_code="en"` temporal
- `pico_y_placa` (es): ✅ aprobado y probado
- `daily_digest` (es): ✅ aprobado y probado
- `event_reminder` (es): 🆕 **PENDIENTE crear en Meta** — 5 params
- `initial_greeting`: traducción español `es`
- Pendiente: aprobación `project_reminder` en español → revertir `language_code="en"` a `"es"`
- Pendiente: crear y aprobar `event_reminder` en Meta

### Tests — 308/308 (100%) ✅

---

## Fase 2 — Beta Cerrada 📋 EN PROGRESO

### Completado en Fase 2:
- [x] WhatsApp Cloud API integración completa
- [x] WhatsApp: reacción + typing indicator + debounce 3s
- [x] WhatsApp Templates: 4 plantillas creadas + documentadas
- [x] Telegram webhook unificado
- [x] Sistema de suscripción: planes, trial 7 días, control acceso
- [x] Onboarding guiado: bienvenida + nombre preferido
- [x] Seguridad: middleware check_access
- [x] Proyectos y Tareas
- [x] Contactos
- [x] Envío de fotos al usuario
- [x] Skills Ecuador (7 skills)
- [x] Flujo post-pago: 4 pasos + user_profiles
- [x] Módulo de Vehículos independiente
- [x] Scheduler conectado a WhatsApp templates
- [x] Ad-hoc reminders: "avísame en X minutos" funcional ✅
- [x] System prompt reforzado anti-alucinaciones
- [x] Hora local Ecuador en todo el stack (cero conversiones TZ)
- [x] Límite vehículos parametrizable por plan

### Pendientes Fase 2:
- [ ] Módulo de Finanzas Personales 🆕
- [ ] Métricas: % extracción correcta, retención D7/D30
- [ ] Ola 2: cumpleaños, vacunas, suscripciones, control de gastos

---

## Fase 3 — Lanzamiento con Monetización 📋 PLANEADA
- [ ] Integración de pago (Kushki/PayPhone)
- [ ] Webhook de pago (reactivación automática)
- [ ] Facturación SRI de la suscripción (AuraFac)
- [ ] Funcionalidades Ola 3 (fiscal/financiero)
- [ ] Familia y cuidado (medicamentos, modo cuidado, remesas)

## Fase 4 — SMB 📋 FUTURO
## Fase 5 — Expansión Regional 📋 FUTURO

---

## Leyenda
- ✅ Completado
- 🔨 En progreso
- 📋 Planeado
- 🆕 Nuevo en esta versión
