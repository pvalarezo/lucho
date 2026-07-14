# PROGRESS.md — Lucho

Estado actual de cada fase, módulo y entregable. Fase 1 completada con rediseño a agente.

---

## Fase 0 — Validación ✅ COMPLETADA
## Fase 1 — MVP Técnico ✅ COMPLETADA

### Versiones
| Tag | Fecha | Descripción |
|-----|-------|-------------|
| v2.8.0 | 2026-07-14 | WhatsApp Cloud API: send/receive, media, webhook, real _send_whatsapp(), dev setup docs |
| v2.7.0 | 2026-07-14 | Web search tool: DuckDuckGo (ddgs), consultas Ecuador actuales |
| v2.6.0 | 2026-07-13 | Refactor file_key, flujo archivos sin auto-save, regla #0 NUNCA MIENTAS, sin Markdown |
| v2.5.0 | 2026-07-13 | Tests actualizados: 267 unit offline (100%), suite + stress para agente |
| v2.4.0 | 2026-07-13 | Skills Ecuador: documentos, SRI facturación, gastronomía, feriados (7 skills total) |
| v2.3.0 | 2026-07-13 | Envío de fotos/docs: tool send_photo, búsqueda documentos, respuesta dict |
| v2.2.0 | 2026-07-12 | Proyectos/tareas, recordatorios unificados, contactos |
| v2.1.0 | 2026-07-12 | OCR documentos, digest diario, PDFs |
| v2.0.0 | 2026-07-12 | Rediseño a arquitectura de agente |

### Arquitectura — ✅ 100%
- Agente unificado: system prompt + 19 tools + conversation memory
- Skills Ecuador: 7 skills en 4 dominios (culture, transit, legal, tax)
- Estructura de skills en inglés (cumple AGENTS.md 2.1)
- Multi-LLM: DeepSeek (chat), Anthropic (visión/OCR), OpenAI (Whisper)
- Canal de notificaciones agnóstico: Telegram + placeholders WhatsApp/email/SMS
- file_key como clave universal de almacenamiento (fotos y documentos)
- MAX_TOOL_ROUNDS=5 para evitar mensajes "me enredé"

### Funcionalidades — 17 completadas

| # | Funcionalidad | Tools | Estado |
|---|--------------|-------|--------|
| 1 | Vehículos (guardar, ANT/SRI, pico y placa) | save_vehicle, check_vehicle_info | ✅ |
| 2 | Documentos (cédula, SOAT, garantía, OCR) | save_document, analyze_image | ✅ |
| 3 | Eventos/Recordatorios | save_event + scheduler | ✅ |
| 4 | Listas (compras, tareas) | save_list | ✅ |
| 5 | Notas por tema | save_note | ✅ |
| 6 | Gastos compartidos | save_expense | ✅ |
| 7 | Búsqueda (datos + historial chat) | search_my_data, search_conversation | ✅ |
| 8 | Resumen diario automático 8 AM | daily_digest | ✅ |
| 9 | Correcciones | update_last | ✅ |
| 10 | Conversación natural + memoria | Agente multi-turno | ✅ |
| 11 | Skills Ecuador | 7 MD + loader | ✅ |
| 12 | Proyectos y Tareas | save/list/complete_project_task | ✅ |
| 13 | Contactos (nombre, tel, email, WA) | save_contact, list_contacts | ✅ |
| 14 | Recordatorios unificados | Scheduler: eventos 15/7/3/0, docs 30/15/7, proyectos 7/3/1 | ✅ |
| 15 | Notificaciones multi-canal | notifications.py (Telegram + placeholders) | ✅ |
| 16 | Envío de fotos/docs al usuario | send_photo (detecta imagen vs documento, MinIO → Telegram) | ✅ |
| 17 | Web search MUNDIAL | web_search (DuckDuckGo ddgs, CUALQUIER tema, sin restricción) | ✅ |
| 18 | WhatsApp Cloud API | whatsapp_webhook, send/recibir mensajes, fotos, audio, docs | ✅ |
| 19 | Documentación dev setup | docs/development_setup.md | ✅ |

### Flujo de archivos — ✅ Refinado

| Escenario | Comportamiento |
|-----------|---------------|
| Archivo sin instrucción | Sube a MinIO, LLM pregunta qué hacer |
| Archivo con caption | Procesa según instrucción del usuario |
| Mensaje previo + archivo | Usa historial de conversación como contexto |
| Pedir archivo guardado | search_my_data → send_photo → envía el archivo |
| Regla #0 | NUNCA decir "guardé"/"envié" sin haber ejecutado la tool |

### Pendientes

| # | Tarea | Prioridad | Esfuerzo |
|---|-------|-----------|----------|
| ~~1~~ | ~~Web search tool~~ | ~~✅ Completado~~ | — |
| 2 | Indexado numerado en búsquedas | 🟢 Baja | — |
| 3 | Dashboard métricas | 🟢 Futuro | — |
| 4 | Skills adicionales (transporte, servicios básicos) | 🟢 Opcional | 40min |

### Infraestructura — ✅ 100%
- FastAPI, Docker Compose, Alembic, 18 tablas PostgreSQL + pgvector
- MinIO (fotos/documentos), Redis (configurado), sentence-transformers (embeddings locales)
- Bot Telegram polling + webhook prod-ready (ambos canales con upload a MinIO)
- APScheduler: daily_rules + daily_digest (8:00 AM)
- Tests: 267 unit offline + suite/stress integración

---

## Fase 2 — Beta Cerrada 📋 PLANEADA
## Fase 3 — Lanzamiento 📋 PLANEADA
## Fase 4 — SMB 📋 FUTURO
## Fase 5 — Expansión 📋 FUTURO

---

## Leyenda
- ✅ Completado
- 🔨 En progreso
- ⬚ Pendiente
