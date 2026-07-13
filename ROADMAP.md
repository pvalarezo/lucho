# ROADMAP.md — Lucho

Plan general del proyecto, fases, hitos y funcionalidades por ola.

---

## Fase 0 — Validación ✅ COMPLETADA
- Encuestas de validación de mercado
- Confirmación de interés y preferencia por WhatsApp como canal

---

## Fase 1 — MVP Técnico (Telegram primero) ✅ COMPLETADA — 2026-07-11

**Canal:** Telegram Bot API (polling para dev, webhook listo para prod)
**Arquitectura:** Agente unificado con 12 tools (DeepSeek function calling)
**Visión/OCR:** Anthropic Claude Vision para documentos
**Versión:** v2.1.0

### Entregables completados:

#### Infraestructura y proyecto
- [x] Estructura del proyecto FastAPI
- [x] Docker Compose (PostgreSQL+pgvector, MinIO, Redis, Traefik)
- [x] Alembic con async engine + migraciones
- [x] Multi-LLM (DeepSeek para chat, Anthropic para visión, OpenAI para Whisper)
- [x] Sistema de tools enchufables (12 tools con function calling)
- [x] Agente unificado: system prompt + tools + conversation memory
- [x] Skills Ecuador (modismos, matriculación, pico y placa)
- [x] OCR de documentos (Anthropic Claude Vision)
- [x] Resumen diario automático (8:00 AM)
- [x] API vehicular externa (ANT/SRI/multas)
- [ ] CI/CD básico

#### Base de datos
- [x] 18 tablas: users, messages, assets, events, reminders, topics, notes, lists, list_items, projects, project_tasks, contacts, caregiver_links, shared_expenses, shared_expense_participants, subscriptions, payments, subscription_invoices
- [x] pgvector + HNSW + GIN indexes, ENUMs, JSONB

#### Bot de Telegram
- [x] Polling para desarrollo + webhook listo para prod
- [x] Texto, fotos, voz, audio, documentos (PDF)
- [x] Typing indicator, deduplicación
- [x] Memoria de conversación multi-turno

#### Funcionalidades
- [x] Vehículos: guardar, consultar ANT/SRI, pico y placa, matriculación
- [x] Documentos: cédula, SOAT, garantía, factura (con OCR)
- [x] Eventos/Recordatorios con scheduler (15/7/3/0 días)
- [x] Listas (compras, tareas, pendientes)
- [x] Notas por tema
- [x] Gastos compartidos
- [x] Búsqueda semántica + historial de chat
- [x] Resumen diario automático
- [x] Correcciones de datos
- [x] Conversación natural con personalidad ecuatoriana
- [ ] Proyectos y Tareas
- [ ] Contactos
- [ ] Envío de fotos al usuario

---

## Fase 2 — Beta Cerrada 📋 PLANEADA

**Usuarios:** 50-100 reales
**Canal:** Telegram

- [ ] Onboarding guiado (3 primeros mensajes diseñados)
- [ ] Métricas: % extracción correcta, retención D7/D30, intención de pago
- [ ] Seguridad y LOPDP: cifrado en reposo, política de privacidad
- [ ] Proyectos y Tareas (completar tool pendiente de Fase 1)
- [ ] Contactos (completar tool pendiente de Fase 1)
- [ ] Envío de fotos al usuario (completar pendiente de Fase 1)
- [ ] Funcionalidades Ola 2:
  - Fechas especiales (cumpleaños, aniversarios)
  - Vacunas (hijos, mascotas)
  - Suscripciones y servicios olvidados
  - Control de gastos personales (tracking + ingresos)
- [ ] Skills Ecuador adicionales (SRI facturación, IESS, legal)

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
