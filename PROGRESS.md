# PROGRESS.md — Lucho

Estado actual de cada fase, módulo y entregable. Fase 1 completada el 2026-07-11.

---

## Fase 0 — Validación ✅ COMPLETADA

## Fase 1 — MVP Técnico ✅ COMPLETADA (2026-07-11)

### Infraestructura y proyecto — ✅ 100%
- Estructura FastAPI, Docker Compose (dev + prod), Dockerfile, Alembic
- Multi-LLM (DeepSeek + Anthropic configurable), feature flags
- Suite de tests: 41/41 normal + 57/57 stress + 12/12 embeddings
- `.env` configurado con DeepSeek + PostgreSQL :5434

### Base de datos — ✅ 95%
- 19 tablas: users, messages, assets, events, reminders, topics, notes, lists, list_items, projects, project_tasks, contacts, caregiver_links, shared_expenses, shared_expense_participants, subscriptions, payments, subscription_invoices + alembic_version
- pgvector + HNSW indexes, GIN indexes, ENUMs, JSONB
- ⬚ Vista `searchable_content` (unifica notes + list_items + assets)

### Bot de Telegram — ✅ 100%
- Polling mode (dev) + webhook endpoint (prod-ready)
- Typing indicator nativo, deduplicación, pipeline completo
- Resolver/crear usuario, persistir mensaje, confirmación editable

### Pipeline de IA — ✅ 100%
- Router DeepSeek: 9 targets (asset, event, list_item, note, meta, search, correction, shared_expense, tool)
- Extractor DeepSeek: schemas por target_table, fecha actual en prompt
- Guardrails: rechaza cultura general, clima, tareas escolares
- Meta-detección vía LLM (sin keywords manuales)
- Tool system: ejecución de APIs externas con auto-retry
- Respuestas contextuales + templates híbridos

### Integraciones — ✅ 85%
- Whisper: transcripción de audio (OpenAI, opcional)
- Embeddings: sentence-transformers local (384 dims, gratuito) + OpenAI fallback
- ⬚ OCR/visión de facturas (DeepSeek Vision disponible)

### Motor de Reglas — ✅ 100%
- Matriculación por placa (ANT Ecuador), pico y placa (Quito/Cuenca)
- APScheduler cron diario (8:00 AM), recordatorios 15/7/3/0 días
- SOAT/RTV, eventos auto-generados para vehículos

### Núcleo Transversal — ✅ 100%
- Captura libre texto/audio/foto, múltiples instrucciones, recurrencias
- Búsqueda conversacional (pgvector semántico + ILIKE + contextual)
- Listas simples, notas por tema, proyectos, gastos compartidos

### "Lucho piensa" — ✅ 90%
- Cálculos: deadlines, pending items, vehículos con reglas
- Explicaciones contextuales (LLM sobre datos del usuario)
- Detección de patrones (pico y placa, vencimientos)
- Preparación de acciones (resúmenes, avisos)
- ⬚ Resumen diario/semanal programado (opt-in)

### Pendientes reales de Fase 1 (3 items):

| # | Tarea | Prioridad |
|---|-------|-----------|
| 1 | **Vista `searchable_content`** | Baja — ya funciona con queries separadas |
| 2 | **OCR/visión de facturas** | Media — DeepSeek tiene capacidad de visión |
| 3 | **Resumen diario/semanal programado** | Baja — search ya permite consultar bajo demanda |

---

## Fase 2 — Beta Cerrada ⬚ No iniciada
## Fase 3 — Lanzamiento ⬚ No iniciada
## Fase 4 — SMB ⬚ No iniciada
## Fase 5 — Expansión ⬚ No iniciada

---

## Leyenda
- ✅ Completado
- 🔨 En progreso
- ⬚ Pendiente
- ❌ Cancelado
