# PROGRESS.md — Lucho

Estado actual de cada fase, módulo y entregable. Fase 1 completada el 2026-07-11.
Rediseño de arquitectura a agente completado el 2026-07-12.

---

## Fase 0 — Validación ✅ COMPLETADA

## Fase 1 — MVP Técnico ✅ COMPLETADA (2026-07-11)
## Fase 1.5 — Rediseño a Agente ✅ COMPLETADA (2026-07-12)
## Fase 1.6 — OCR, Documentos, Digest ✅ COMPLETADA (2026-07-12)

### Arquitectura del Agente — ✅ 100%
- System prompt unificado: `lucho_system_prompt.py` (identidad, personalidad, límites)
- 12 tools con function calling: save_vehicle, save_document, save_event, save_list, save_note, save_expense, search_my_data, search_conversation, get_my_summary, update_last, check_vehicle_info, analyze_image
- Agent loop con tool-calling (máx 3 rondas)
- Memoria de conversación multi-turno (historial desde PostgreSQL)
- Skills Ecuador: modismos, matriculación ANT, pico y placa Quito/Cuenca (3 MD + loader automático)
- OCR de documentos: Anthropic Claude Vision extrae datos de fotos (cédula, SOAT, factura, garantía)
- API externa: consulta vehicular ANT/SRI/multas por placa (check_vehicle_info)
- Resumen diario automático (8:00 AM): vehículos, vencimientos, pendientes vía agente
- Soporte para documentos/PDFs (upload a MinIO desde Telegram)
- Fotos adjuntables a eventos, notas y documentos (photo_key cross-entity)
- Código viejo eliminado: router.py, extractor.py
- Webhook de producción actualizado al agente
- Bot Telegram funcionando con agente (polling mode)

### Infraestructura y proyecto — ✅ 100%
- Estructura FastAPI, Docker Compose (dev + prod), Dockerfile, Alembic
- Multi-LLM (DeepSeek + Anthropic + OpenAI configurable), feature flags
- `.env` configurado con DeepSeek + Anthropic + OpenAI + PostgreSQL :5434

### Base de datos — ✅ 95%
- 18 tablas: users, messages, assets, events, reminders, topics, notes, lists, list_items, projects, project_tasks, contacts, caregiver_links, shared_expenses, shared_expense_participants, subscriptions, payments, subscription_invoices
- pgvector + HNSW indexes, GIN indexes, ENUMs, JSONB

### Bot de Telegram — ✅ 100%
- Polling mode (dev) + webhook endpoint (prod-ready, usa agente)
- Typing indicator nativo, deduplicación
- Texto, fotos, voz, audio, documentos (PDF, DOC, etc.)

### Funcionalidades completadas

| # | Funcionalidad | Tools | Estado |
|---|--------------|-------|--------|
| 1 | Vehículos (guardar, consultar ANT/SRI) | save_vehicle, check_vehicle_info | ✅ |
| 2 | Documentos (cédula, SOAT, garantía) | save_document, analyze_image | ✅ |
| 3 | OCR/Visión de documentos | analyze_image (Anthropic Vision) | ✅ |
| 4 | Eventos/Recordatorios | save_event + scheduler | ✅ |
| 5 | Listas (compras, tareas) | save_list | ✅ |
| 6 | Notas por tema | save_note | ✅ |
| 7 | Gastos compartidos | save_expense | ✅ |
| 8 | Búsqueda (datos + historial chat) | search_my_data, search_conversation | ✅ |
| 9 | Resumen diario automático | daily_digest (8:00 AM) | ✅ |
| 10 | Correcciones | update_last | ✅ |
| 11 | Conversación natural con memoria | Agente multi-turno | ✅ |
| 12 | Skills Ecuador | 3 MD + loader | ✅ |

### Motor de Reglas — ✅ 100%
- Recordatorios unificados: eventos 15/7/3/0, documentos 30/15/7, proyectos 7/3/1
- Canal de notificaciones agnóstico: Telegram (hoy), WhatsApp/email/SMS (placeholders)
- Matriculación por placa (ANT Ecuador), pico y placa (Quito/Cuenca)
- APScheduler: daily_rules + daily_digest (8:00 AM)

### Pendientes reales

| # | Funcionalidad | Tablas existentes | Prioridad |
|---|--------------|-------------------|-----------|
| 1 | **Proyectos y Tareas** | projects, project_tasks | 🔴 Alta |
| 2 | **Contactos** | contacts | 🟡 Media |
| 3 | **Envío de fotos al usuario** | MinIO download | 🟡 Media |
| 4 | **Suscripción/Facturación** | subscriptions, payments | 🟢 Futuro |
| 5 | **Cuidadores (modo familia)** | caregiver_links | 🟢 Futuro |

---

## Fase 2 — Beta Cerrada 📋 PLANEADA
## Fase 3 — Lanzamiento con Monetización 📋 PLANEADA
## Fase 4 — SMB 📋 FUTURO
## Fase 5 — Expansión 📋 FUTURO

---

## Tags de versión

| Tag | Descripción |
|-----|-------------|
| v0.1.0 → v1.5.2 | MVP inicial (router + extractor) |
| v2.0.0 | Rediseño a arquitectura de agente |
| v2.1.0 | OCR documentos, digest diario, documentos/PDFs |

---

## Leyenda
- ✅ Completado
- 🔨 En progreso
- ⬚ Pendiente
- ❌ Cancelado
