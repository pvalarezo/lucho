# ROADMAP.md — Lucho

Plan general del proyecto, fases, hitos y funcionalidades por ola.

---

## Fase 0 — Validación ✅ COMPLETADA
- Encuestas de validación de mercado
- Confirmación de interés y preferencia por WhatsApp como canal

---

## Fase 1 — MVP Técnico (Telegram primero) ✅ COMPLETADA — 2026-07-11

**Canal:** Telegram Bot API (polling para dev, webhook listo para prod)
**LLM:** DeepSeek (router + extractor), configurable a Anthropic
**Resultado test suite:** 41/41 (100%) — ver `tests/suite.py`

### Entregables completados:

#### Infraestructura y proyecto
- [x] Estructura del proyecto FastAPI
- [x] Docker Compose (PostgreSQL+pgvector, MinIO, Redis, Traefik)
- [x] Docker Compose desarrollo (DB :5434, Redis :6379, MinIO :9000)
- [x] Alembic con async engine + migraciones
- [x] Abstracción multi-LLM (DeepSeek + Anthropic)
- [x] Sistema de tools enchufables (API/MCP ready)
- [x] Feature flags (CONTEXTUAL_RESPONSES)
- [x] Suite de tests (41 casos, 9 categorías)
- [ ] CI/CD básico

#### Base de datos
- [x] Esquema `users`, `messages`
- [x] Esquema `assets` (JSONB + GIN + pgvector)
- [x] Esquema `events`, `reminders`
- [x] Esquema `topics`, `notes` (pgvector + HNSW)
- [x] Esquema `lists`, `list_items` (ENUMs, pgvector)
- [ ] Esquema `projects`, `project_tasks`
- [ ] Esquema contactos, gastos, suscripción
- [ ] Vista `searchable_content`

#### Bot de Telegram
- [x] Webhook recepción mensajes (texto, photo, audio)
- [x] Polling para desarrollo (sin SSL/IP pública)
- [x] Typing indicator (nativo de Telegram)
- [x] Resolver/crear usuario por telegram_id
- [x] Persistir mensaje crudo con tracking por etapa
- [x] Confirmación editable por tipo de dato
- [x] Deduplicación de mensajes

#### Pipeline de IA
- [x] Router DeepSeek: 9 targets (asset, event, list_item, note, meta, search, correction, shared_expense, tool)
- [x] Extractor DeepSeek: schemas por target_table
- [x] Respuestas contextuales (LLM sobre datos del usuario)
- [x] Templates híbridos para preguntas comunes
- [x] Guardrails: rechaza cultura general, clima, tareas escolares
- [x] Meta-detección vía router (sin keywords)
- [x] Tool execution: consulta multas por placa

#### Integraciones
- [x] Whisper: transcripción de audio (OpenAI)
- [x] Embeddings: OpenAI + local (sentence-transformers)
- [ ] OCR/visión de facturas

#### Motor de Reglas (determinista)
- [x] Regla matriculación por placa (ANT Ecuador)
- [x] Pico y placa semanal (Quito/Cuenca)
- [x] APScheduler cron diario (8:00 AM)
- [x] Recordatorios escalonados (15/7/3/0 días)
- [x] SOAT / RTV (mismo mes que matriculación)

#### Núcleo Transversal
- [x] Captura libre de texto, audio, foto
- [x] Múltiples instrucciones por mensaje
- [x] Recurrencias complejas
- [x] Búsqueda conversacional (pgvector + ILIKE)
- [x] Listas simples (compras, pendientes)
- [x] Resumen diario/semanal opt-in (vía búsqueda)

#### "Lucho piensa" (mínimo)
- [x] Cálculos sobre datos del usuario (deadlines, pending)
- [x] Explicaciones contextuales (LLM sobre datos)
- [x] Detección de patrones (pico y placa, vencimientos)
- [x] Preparación de acciones (resumen, avisos)

#### Seguridad y mitigaciones
- [x] None-safety en todas las funciones de persistencia
- [x] Valores por defecto para campos NOT NULL
- [x] Mensajes ultra-cortos manejados sin LLM
- [x] Tool auto-retry con mensajes amigables

---

## Fase 2 — Beta Cerrada 📋 PLANEADA

**Usuarios:** 50-100 reales
**Canal:** Telegram

- [ ] Onboarding guiado (3 primeros mensajes diseñados)
- [ ] Métricas: % extracción correcta, retención D7/D30, intención de pago
- [ ] Seguridad y LOPDP: cifrado en reposo, política de privacidad
- [ ] Funcionalidades Ola 2:
  - Documentos personales (cédula, pasaporte, licencia)
  - Fechas especiales (cumpleaños, aniversarios)
  - Vacunas (hijos, mascotas)
  - Suscripciones y servicios olvidados
  - Garantías de electrodomésticos
- [ ] Integración OCR/visión de facturas
- [ ] Esquemas `projects`, `project_tasks`, contactos, gastos, suscripción
- [ ] Vista `searchable_content`

---

## Fase 3 — Lanzamiento con Monetización 📋 PLANEADA

- [ ] Integración de pago (Kushki/PayPhone)
- [ ] Facturación SRI de la suscripción (AuraFac)
- [ ] Migración/expansión a WhatsApp Business API
- [ ] Funcionalidades Ola 3 (fiscal/financiero)
- [ ] Familia y cuidado (medicamentos, modo cuidado, remesas)

---

## Fase 4 — Cruce a SMB 📋 FUTURO

- [ ] Trámites y servicios
- [ ] RUC empresarial, patente, bomberos, IESS
- [ ] Base GRISBI/PowerFin (30+ empresas)

---

## Fase 5 — Expansión Regional y Premium 📋 FUTURO

- [ ] Recordatorios compartidos (premium)
- [ ] Pagos asistidos
- [ ] Google Calendar
- [ ] Pico y placa parametrizable (Bogotá, Lima, CDMX)

---

## Leyenda

- ✅ Completado
- 🔨 En progreso
- 📋 Planeado
- ❌ Cancelado
