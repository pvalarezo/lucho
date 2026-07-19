# PROGRESS.md — Lucho

Estado actual de cada fase, módulo y entregable. Fase 1 completada con rediseño a agente.

---

## Fase 0 — Validación ✅ COMPLETADA
## Fase 1 — MVP Técnico ✅ COMPLETADA

### Versiones
| Tag | Fecha | Descripción |
|-----|-------|-------------|
| v2.9.2 | 2026-07-16 | Telegram polling eliminado: migrado a webhook unificado. app/bot.py + run_bot.py + lucho-bot.service eliminados. Telegram y WhatsApp usan mismo patrón webhook vía lucho-api. Script setup_telegram_webhook.py para configurar. |
| v2.9.1 | 2026-07-16 | WhatsApp Templates: 4 plantillas documentadas (document_reminder, project_reminder, pico_y_placa, daily_digest) en docs/whatsapp_templates.md. Categoría UTILITY, listas para crear en Meta. |
| v2.9.0 | 2026-07-16 | OCR/Visión migrado a DeepSeek: extract_document_data + analyze_image usan deepseek-chat como primario. Código muerto eliminado en vision.py. Meta Live: config verificada, webhook confirmado, esperando aprobación. |
| v2.8.1 | 2026-07-15 | WhatsApp end-to-end tested: texto, foto, audio. Dedup, ack inmediato, fix PHONE_NUMBER_ID, fix OPENAI_API_KEY en .env |
| v2.8.0 | 2026-07-14 | WhatsApp Cloud API: send/receive, media, webhook, real _send_whatsapp(), dev setup docs, Cloudflare tunnel, systemd services |
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
- Canales: Telegram (webhook) + WhatsApp Cloud API (webhook vía Meta Cloud API)
- Cloudflare Tunnel: https://lucho-dev.apx5.com → localhost:8000
- Systemd user services: lucho-api, lucho-tunnel (disabled at boot, manual start)
- Telegram migrado a webhook (mismo endpoint que WhatsApp, sin proceso polling aparte)

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

### Meta Live — ⏳ Esperando aprobación
- Business verification: documentos enviados a Meta
- Webhook verificado: https://lucho-dev.apx5.com/whatsapp/webhook ✅
- Token permanente configurado ✅
- Pendiente: switch Desarrollo → Activo cuando Meta apruebe

### OCR/Visión — ✅ Migrado a DeepSeek
- `extract_document_data`: DeepSeek como primario, fallback Anthropic → OpenAI
- `analyze_image`: DeepSeek primario, fallback Anthropic
- Modelo: `deepseek-chat` (OpenAI-compatible vision)
- Transcripción audio: OpenAI Whisper se mantiene (único proveedor viable con STT)

### Pendientes

| # | Tarea | Prioridad | Esfuerzo |
|---|-------|-----------|----------|
| 1 | Activar app Meta en Live ✅ (cuenta WhatsApp lista) | ✅ Lista | — |
| 2 | Crear templates en Meta Business Manager (documentados en docs/whatsapp_templates.md) | 🔴 Inmediata | 30min |
| 3 | Eliminar Telegram polling → migrar a webhook unificado | ✅ Hecho v2.9.2 | — |
| 4 | Conectar templates en scheduler (send_template_message) | 🟡 Media | 2h |
| 5 | Indexado numerado en búsquedas | 🟢 Baja | — |
| 6 | Dashboard métricas | 🟢 Futuro | — |
| 7 | Skills adicionales (transporte, servicios básicos) | 🟢 Opcional | 40min |
| 8 | Whisper local (reducir costo transcripción a $0) | 🟢 Futuro | 2h |

### Infraestructura — ✅ 100%
- FastAPI, Docker Compose, Alembic, 18 tablas PostgreSQL + pgvector
- MinIO (fotos/documentos), Redis (configurado), sentence-transformers (embeddings locales)
- Telegram webhook (recibir y enviar mensajes)
- WhatsApp Cloud API webhook (recibir y enviar mensajes, verificado ✅)
- Cloudflare Tunnel para HTTPS público (lucho-dev.apx5.com)
- Systemd user services (manual start, no auto-boot)

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
