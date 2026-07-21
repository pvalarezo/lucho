# PROGRESS.md — Lucho

Estado actual de cada fase, módulo y entregable.

---

## Fase 0 — Validación ✅ COMPLETADA
## Fase 1 — MVP Técnico ✅ COMPLETADA

### Versiones
| Tag | Fecha | Descripción |
|-----|-------|-------------|
| v2.13.0 | 2026-07-21 | Tabla `documents` independiente. `assets` eliminado. `shared_expenses` eliminado. 23 tablas, 26 tools, 348 tests. |
| v2.12.0 | 2026-07-21 | Módulo Finanzas: `transactions` + `budgets`, 5 tools. `shared_expenses` eliminado. |
| v2.11.2 | 2026-07-21 | Hora local Ecuador: TIMESTAMPTZ → TIMESTAMP sin TZ. |
| v2.11.1 | 2026-07-21 | System prompt reforzado anti-alucinaciones. |
| v2.11.0 | 2026-07-21 | Ad-hoc reminders sub-día vía DateTrigger. |
| v2.10.1 | 2026-07-21 | WhatsApp Templates 4/4 verificados. |
| v2.10.0 | 2026-07-20 | Vehículos independiente + post-pago + scheduler templates. |

### Arquitectura — ✅ 100%
- Agente unificado: system prompt + 26 tools + conversation memory
- Skills Ecuador: 7 skills en 4 dominios
- Canales: Telegram (webhook) + WhatsApp Cloud API (webhook)
- Cloudflare Tunnel: https://lucho-dev.apx5.com → localhost:8000
- Systemd user services: lucho-api, lucho-tunnel

### Base de Datos — 23 tablas
`users`, `user_profiles`, `messages`, `documents`, `events`, `reminders`, `topics`, `notes`, `lists`, `list_items`, `projects`, `project_tasks`, `contacts`, `caregiver_links`, `vehicles`, `vehicle_maintenances`, `transactions`, `budgets`, `subscription_plans`, `subscriptions`, `payments`, `subscription_invoices`, `subscription_plans`

### Tools del Agente — 26 tools

| # | Tool | Módulo |
|---|------|--------|
| 1-4 | `save_vehicle`, `list_my_vehicles`, `add_maintenance`, `list_maintenances` | Vehículos |
| 5 | `save_document` | Documentos |
| 6 | `save_event` | Recordatorios |
| 7 | `save_list` | Listas |
| 8 | `save_note` | Notas |
| 9-11 | `search_my_data`, `search_conversation`, `web_search` | Búsqueda |
| 12 | `analyze_image` | OCR/Visión |
| 13 | `get_my_summary` | Resumen |
| 14-16 | `save_project_task`, `list_project_tasks`, `complete_project_task` | Proyectos |
| 17 | `update_last` | Correcciones |
| 18-19 | `save_contact`, `list_contacts` | Contactos |
| 20 | `check_vehicle_info` | Vehículos |
| 21 | `send_photo` | Archivos |
| 22-26 | `add_transaction`, `list_transactions`, `get_balance`, `set_budget`, `check_budget` | Finanzas |

### Scheduler — 8:00 AM diario
| Recordatorio | Template | Ventanas |
|-------------|----------|----------|
| Documentos | `document_reminder` (es) | 30/15/7 días |
| Proyectos | `project_reminder` (en) | 7/3/1 días |
| Eventos | `event_reminder` (⏳) | 15/7/3/0 días + ad-hoc |
| Pico y placa | `pico_y_placa` (es) | Solo HOY |
| Presupuestos | `budget_alert` (⏳) | Diario |
| Daily digest | `daily_digest` (es) | Diario |

### Documentación — 14 specs
`finanzas`, `documentos`, `recordatorios`, `listas`, `notas_apuntes`, `proyectos_tareas`, `busqueda`, `contactos`, `funcionalidades_generales`, `skills_ecuador`, `ideas_nuevos_modulos`, `whatsapp_templates`

### Tests — 348/348 (100%) ✅

---

## Fase 2 — Beta Cerrada ✅ COMPLETADA

### Pendientes menores Fase 2:
- [ ] Métricas: % extracción correcta, retención D7/D30
- [ ] Templates Meta: `event_reminder` (es), `project_reminder` (es), `budget_alert`
- [ ] Tools: `list_my_documents`, `list_items`, `complete_item`, `list_my_notes`

---

## Fase 3 — Lanzamiento con Monetización 📋 PLANEADA
- [ ] Integración de pago (Kushki/PayPhone)
- [ ] Facturación SRI (AuraFac)
- [ ] Métricas y analytics
- [ ] Módulos: temporizador, clientes (CRM ligero)
- [ ] APIs Ecuador: clima, noticias, CNE

## Fase 4 — Expansión 📋 FUTURO
## Fase 5 — SMB y Regional 📋 FUTURO

---

## Leyenda
- ✅ Completado
- 🔨 En progreso
- 📋 Planeado
