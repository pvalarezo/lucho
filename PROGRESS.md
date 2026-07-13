# PROGRESS.md — Lucho

Estado actual de cada fase, módulo y entregable. Fase 1 completada el 2026-07-11.
Rediseño de arquitectura a agente completado el 2026-07-12.

---

## Fase 0 — Validación ✅ COMPLETADA

## Fase 1 — MVP Técnico ✅ COMPLETADA (2026-07-11)
## Fase 1.5 — Rediseño a Agente ✅ COMPLETADA (2026-07-12)

### Arquitectura del Agente — ✅ 100%
- System prompt unificado: `lucho_system_prompt.py` (identidad, personalidad, límites, reglas)
- 11 tools con function calling (DeepSeek): save_vehicle, save_document, save_event, save_list, save_note, save_expense, search_my_data, search_conversation, get_my_summary, update_last, check_vehicle_info
- Agent loop con tool-calling (máx 3 rondas)
- Memoria de conversación (historial desde PostgreSQL)
- Skills Ecuador: modismos, matriculación ANT, pico y placa Quito/Cuenca (3 MD + loader)
- Integración API externa: consulta vehicular ANT/SRI/multas por placa
- Código viejo eliminado: router.py, extractor.py (~350 líneas)
- Webhook de producción actualizado al agente
- Bot Telegram funcionando con agente (polling mode)

### Infraestructura y proyecto — ✅ 100%
- Estructura FastAPI, Docker Compose (dev + prod), Dockerfile, Alembic
- Multi-LLM (DeepSeek + Anthropic configurable), feature flags
- Suite de tests: 41/41 normal + 57/57 stress + 12/12 embeddings
- `.env` configurado con DeepSeek + PostgreSQL :5434

### Base de datos — ✅ 95%
- 19 tablas: users, messages, assets, events, reminders, topics, notes, lists, list_items, projects, project_tasks, contacts, caregiver_links, shared_expenses, shared_expense_participants, subscriptions, payments, subscription_invoices + alembic_version
- pgvector + HNSW indexes, GIN indexes, ENUMs, JSONB
- ⬚ Vista `searchable_content` — YA NO NECESARIA (agente busca cross-entity)

### Bot de Telegram — ✅ 100%
- Polling mode (dev) + webhook endpoint (prod-ready, usa agente)
- Typing indicator nativo, deduplicación, pipeline completo
- Resolver/crear usuario, persistir mensaje, confirmación editable

### Pipeline de IA (REEMPLAZADO por agente) — ✅ 100%
- ~~Router DeepSeek: 9 targets~~ → Agente unificado con 11 tools
- ~~Extractor DeepSeek: schemas por target_table~~ → Herramientas con schemas
- Guardrails: rechaza cultura general, clima, tareas escolares (vía system prompt)
- Meta-detección contextual (sin keywords manuales)
- Tool system: ejecución de APIs externas con auto-retry
- Respuestas naturales generadas por LLM (sin templates quemados)
- Memoria de conversación multi-turno

### Integraciones — ✅ 95%
- Whisper: transcripción de audio (OpenAI, opcional)
- Embeddings: sentence-transformers local (384 dims, gratuito) + OpenAI fallback
- MinIO: upload/download de documentos con fotos
- AI Vision: DeepSeek analiza imágenes sin caption, clasifica y pregunta
- API externa: consulta vehicular ANT/SRI/multas por placa
- ⬚ OCR/visión de facturas (DeepSeek Vision disponible, prompt pendiente)

### Motor de Reglas — ✅ 100%
- Matriculación por placa (ANT Ecuador), pico y placa (Quito/Cuenca)
- APScheduler cron diario (8:00 AM), recordatorios 15/7/3/0 días
- SOAT/RTV, eventos auto-generados para vehículos

### Núcleo Transversal — ✅ 100%
- Captura libre texto/audio/foto, múltiples instrucciones, recurrencias
- Búsqueda conversacional (pgvector semántico + ILIKE + historial de chat)
- Listas simples, notas por tema, proyectos, gastos compartidos

### "Lucho piensa" — ✅ 90%
- Cálculos: deadlines, pending items, vehículos con reglas
- Explicaciones contextuales (LLM sobre datos del usuario)
- Detección de patrones (pico y placa, vencimientos)
- Preparación de acciones (resúmenes, avisos)
- ⬚ Resumen diario/semanal programado (opt-in)

---

## Fase 2 — Beta Cerrada 📋 PLANEADA

**Usuarios:** 50-100 reales
**Canal:** Telegram

- [ ] Onboarding guiado (3 primeros mensajes diseñados)
- [ ] Métricas: % extracción correcta, retención D7/D30, intención de pago
- [ ] Seguridad y LOPDP: cifrado en reposo, política de privacidad
- [ ] OCR/Visión de facturas
- [ ] Funcionalidades Ola 2:
  - Documentos personales (cédula, pasaporte, licencia)
  - Fechas especiales (cumpleaños, aniversarios)
  - Vacunas (hijos, mascotas)
  - Suscripciones y servicios olvidados
  - Garantías de electrodomésticos
- [ ] Esquemas `projects`, `project_tasks`, contactos, gastos, suscripción
- [ ] Skills Ecuador adicionales (SRI facturación, IESS, legal)

---

## Fase 3 — Lanzamiento con Monetización 📋 PLANEADA
## Fase 4 — SMB 📋 FUTURO
## Fase 5 — Expansión 📋 FUTURO

---

## Mejoras implementadas post-Fase 1:

| # | Mejora | Tag |
|---|--------|-----|
| 1 | MinIO document upload/download | v1.4.0 |
| 2 | Smart photo handling | v1.4.1 |
| 3 | AI Vision analysis | v1.5.0 |
| 4 | Stronger meta detection | v1.5.1 |
| 5 | Contextual natural meta responses | v1.5.2 |
| 6 | Rediseño a arquitectura de agente | v2.0.0 |

---

## Leyenda
- ✅ Completado
- 🔨 En progreso
- ⬚ Pendiente
- ❌ Cancelado
