# NEXT_SESSION.md — Lucho

---

## Sesión actual — 2026-07-11 (MARATÓN)

**Avances completados en UNA sesión:**

### Bootstrap y estructura
- ✅ Archivos de control: AGENTS.md, ROADMAP.md, PROGRESS.md, NEXT_SESSION.md
- ✅ Git init (main) + .gitignore
- ✅ Estructura FastAPI: app/, models/, schemas/, routers/, services/, tools/, tests/
- ✅ Docker Compose dev: PostgreSQL 16+pgvector :5434, Redis :6379, MinIO :9000
- ✅ Alembic con migraciones automáticas (5+4 tablas)
- ✅ API REST con health check

### Pipeline de IA
- ✅ DeepSeek como LLM principal (router + extractor)
- ✅ Abstracción multi-LLM (AnthropicProvider + DeepSeekProvider)
- ✅ Router 9 targets: asset, event, list_item, note, meta, search, correction, shared_expense, tool
- ✅ Extractor con schemas por target_table
- ✅ Guardrails: rechaza cultura general, clima, tareas escolares
- ✅ Meta-detección vía LLM (sin keywords manuales)

### Bot Telegram
- ✅ Polling mode (sin SSL, sin IP pública)
- ✅ Typing indicator nativo (sin mensaje repetitivo)
- ✅ Pipeline completo: resolver usuario → persistir mensaje → router → extractor → persistir → confirmar
- ✅ Deduplicación de mensajes
- ✅ Transcripción Whisper para notas de voz
- ✅ Fotos con caption

### Persistencia y datos
- ✅ 9 tablas: users, messages, assets, events, reminders, topics, notes, lists, list_items
- ✅ Persistencia determinista con resolución de duplicados
- ✅ None-safety en todas las funciones de escritura

### Motor de reglas
- ✅ Matriculación por placa (ANT Ecuador)
- ✅ Pico y placa semanal (Quito/Cuenca)
- ✅ APScheduler cron diario (8:00 AM)
- ✅ Recordatorios escalonados (15/7/3/0 días)
- ✅ Eventos auto-generados para vehículos

### Búsqueda
- ✅ Búsqueda semántica (pgvector + ILIKE fallback)
- ✅ Búsqueda inteligente con extracción de parámetros
- ✅ Respuestas contextuales (LLM explica datos)
- ✅ Templates híbridos (zero LLM para preguntas comunes)
- ✅ Endpoints: /search/semantic, /deadlines, /pending

### Tools y extensibilidad
- ✅ Sistema de tools enchufables (API/MCP ready)
- ✅ check_plate_fines tool (simulada, lista para API real)
- ✅ Auto-retry con mensajes amigables

### Calidad
- ✅ Suite de tests: 41 casos, 9 categorías, **100% de acierto**
- ✅ Feature flags (CONTEXTUAL_RESPONSES)
- ✅ Embeddings: OpenAI + local (sentence-transformers)
- ✅ Spec actualizada a v1.7 con registro de riesgos

### Tags creados: v0.1.0 → v0.13.0 + v1.7.0 (15 tags)

---

## Próxima sesión

**Objetivo:** Fase 2 — Beta cerrada

**Tareas planificadas:**
1. Onboarding guiado (flujo de primeros 3 mensajes)
2. Dashboard de métricas (precisión router, retención)
3. Modelos faltantes: projects, contacts, shared_expenses, subscriptions
4. OCR/visión de facturas con DeepSeek Vision
5. Esquema searchable_content (vista unificada)
6. Seguridad: cifrado en reposo, política LOPDP
7. Preparar entorno de staging

**Comandos rápidos:**
```bash
# Entorno dev
docker compose -f docker-compose.dev.yml up -d
python3 run_bot.py

# API
uvicorn app.main:app --port 8000

# Tests
python3 tests/suite.py
```
