# PROGRESS.md — Lucho

Estado actual de cada fase, módulo y entregable.

---

## Fase 0 — Validación ✅ COMPLETADA
## Fase 1 — MVP Técnico ✅ COMPLETADA

### Versiones
| Tag | Fecha | Descripción |
|-----|-------|-------------|
| v2.24.6 | 2026-07-22 | Fix: onboarding_step=0 al completar, evita choque con post-pago. + guard en post-pago. |
| v2.24.5 | 2026-07-22 | Onboarding: paso de acento regional (costeño/serrano/amazónico/neutral). |
| v2.24.9 | 2026-07-23 | Daily Digest: opt-in, tool set_daily_digest, pregunta en onboarding, 6 tests |
| v2.24.8 | 2026-07-23 | Suite de integración: 31 tests contra PostgreSQL, DB lucho_test, TZ Docker+deploy, Pi ops |
| v2.24.7 | 2026-07-23 | Estabilización: onboarding Telegram, seguridad webhooks, Ruff 0, zona horaria Ecuador, versión auto-detectada. 567 tests. |
| v2.24.0 | 2026-07-22 | Acentos regionales: costeño, serrano, amazónico, neutral. 45 tools, 512 tests. |
| v2.23.0 | 2026-07-22 | Landing page holalucho.com — Tailwind, 8 secciones, responsive. |
| v2.22.0 | 2026-07-22 | Módulo Cotizaciones: 4 models, 4 tools, IVA dinámico. |
| v2.21.0 | 2026-07-22 | Key49: facturación electrónica SRI (AURACORE). |
| v2.20.0 | 2026-07-22 | BillingInfo + invoice SRI fields + update_billing_info tool. |
| v2.19.0 | 2026-07-22 | Ciclo de vida automático: expiry, pre-aviso 3d, webhook DeUna. |
| v2.18.0 | 2026-07-22 | DeUna QR (Pichincha) como 3ª opción de pago. |
| v2.17.0 | 2026-07-22 | Tabla business_info + transferencia bancaria desde DB. |
| v2.16.0 | 2026-07-22 | PayPhone: API client + webhook + subscribe_to_plan tool. |
| v2.15.0 | 2026-07-22 | 3 planes con precios reales + seed script. |
| v2.14.0 | 2026-07-22 | Revisión completa 9 módulos: +12 tools, +88 tests, spec vehículos. |
| v2.13.0 | 2026-07-21 | Tabla `documents` independiente. `assets` eliminado. `shared_expenses` eliminado. |
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

### Base de Datos — 27 tablas
`users`, `user_profiles`, `messages`, `documents`, `events`, `reminders`, `topics`, `notes`, `lists`, `list_items`, `projects`, `project_tasks`, `contacts`, `caregiver_links`, `vehicles`, `vehicle_maintenances`, `transactions`, `budgets`, `subscription_plans`, `subscriptions`, `payments`, `subscription_invoices`, `business_info`, `billing_info`, `billing_clients`, `billing_products`, `billing_documents`, `billing_document_items`

### Tools del Agente — 45 tools

| # | Tool | Módulo |
|---|------|--------|
| 1-5 | `save_vehicle`, `list_my_vehicles`, `add_maintenance`, `list_maintenances`, `check_vehicle_info` | Vehículos |
| 6-7 | `delete_vehicle`, `update_vehicle` | Vehículos |
| 8-9 | `save_document`, `list_my_documents` | Documentos |
| 10-11 | `save_event`, `list_my_events` | Recordatorios |
| 12-15 | `save_list`, `list_items`, `complete_item`, `delete_list` | Listas |
| 16-18 | `save_note`, `list_my_notes`, `delete_note` | Notas |
| 19-20 | `save_project_task`, `list_project_tasks` | Proyectos |
| 21-23 | `complete_project_task`, `reopen_project_task`, `archive_project` | Proyectos |
| 24-26 | `save_contact`, `list_contacts`, `delete_contact` | Contactos |
| 27-31 | `add_transaction`, `list_transactions`, `get_balance`, `set_budget`, `check_budget` | Finanzas |
| 32-35 | `create_quote`, `list_my_quotes`, `save_billing_client`, `save_billing_product` | Cotizaciones |
| 36-38 | `search_my_data`, `search_conversation`, `web_search` | Búsqueda |
| 39 | `analyze_image` | OCR/Visión |
| 40 | `get_my_summary` | Resumen |
| 41 | `update_last` | Correcciones |
| 42 | `send_photo` | Archivos |
| 43 | `subscribe_to_plan` | Suscripción |
| 44 | `update_billing_info` | Facturación |
| 45 | `set_accent` | Acentos |

### Scheduler — 8:00 AM diario
| Recordatorio | Template | Ventanas |
|-------------|----------|----------|
| Documentos | `document_reminder` (es) | 30/15/7 días |
| Proyectos | `project_reminder` (en) | 7/3/1 días |
| Eventos | `event_reminder` (⏳) | 15/7/3/0 días + ad-hoc |
| Pico y placa | `pico_y_placa` (es) | Solo HOY |
| Presupuestos | `budget_alert` (⏳) | Diario |
| Suscripciones | — | Expiry + pre-aviso 3d |
| Daily digest | `daily_digest` (es) | Diario |
| Resumen mensual | — | Día 1 del mes |

### Documentación — 15 specs
`finanzas`, `documentos`, `recordatorios`, `listas`, `notas_apuntes`, `proyectos_tareas`, `busqueda`, `contactos`, `vehiculos`, `funcionalidades_generales`, `skills_ecuador`, `ideas_nuevos_modulos`, `whatsapp_templates`, `lucho_especificaciones_proyecto`

### Tests — 612/612 (100%) ✅ | Ruff — 0 errores ✅

---

## Fase 2 — Beta Cerrada ✅ COMPLETADA

### Pendientes menores Fase 2:
- [ ] Métricas: % extracción correcta, retención D7/D30
- [ ] Templates Meta: `event_reminder` (es), `project_reminder` (es), `budget_alert`
- [x] ~~Pruebas de integración con base de datos real (pytest + fixtures PostgreSQL)~~ ✅ v2.24.8

---

## Fase 2.5 — Monetización ✅ COMPLETADA

### Suscripciones
- 3 planes: Básico ($4.99), Premium ($9.99), Familia ($14.99)
- Features por plan en JSONB (max_vehicles, max_documents, file_storage_mb, caregiver_mode, etc.)
- Trial 7 días automático
- Seed script: `scripts/seed_subscription_plans.py`

### Pagos
- PayPhone: API client + webhook (activación automática)
- DeUna QR: API client + webhook (Pichincha + otros bancos)
- Transferencia bancaria: datos desde tabla `business_info`

### Ciclo de vida
- Scheduler diario: marca expired + pre-aviso 3 días
- check_access: mensaje amigable con link de renovación
- Notificaciones por Telegram y WhatsApp

---

### Despliegue VPS — v2.24.2 ✅
- VPS Debian 13: 4 vCPU, 8 GB RAM, 148 GB SSD, IP 147.93.2.206
- PostgreSQL 17 + pgvector, Redis, MinIO
- API 4 workers via systemd
- Nginx + SSL Let's Encrypt (holalucho.com, www, api)
- WhatsApp Cloud API webhook probado y funcionando
- Landing page servida desde Nginx

---

## Fase 3 — Lanzamiento con Monetización 📋 PLANEADA
- [ ] Facturación SRI de la suscripción (AuraFac/FacEC)
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
