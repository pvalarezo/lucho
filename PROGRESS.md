# PROGRESS.md — Lucho

Estado actual de cada fase, módulo y entregable.  
Se actualiza al completar hitos significativos.

---

## Fase 0 — Validación

| Estado | Fecha | Detalle |
|--------|-------|---------|
| ✅ | — | Encuestas de validación completadas |
| ✅ | — | Preferencia WhatsApp confirmada |

---

## Fase 1 — MVP Técnico (Telegram primero)

**Estado general:** 🔨 En progreso — Inicio: 2026-07-11

### Infraestructura y proyecto
| Tarea | Estado | Fecha | Notas |
|-------|--------|-------|-------|
| Estructura del proyecto FastAPI | ✅ | 2026-07-11 | app/, routers/, models/, schemas/, services/ |
| Docker Compose (producción) | ✅ | 2026-07-11 | PostgreSQL+pgvector, MinIO, Redis, Traefik, app |
| Docker Compose (desarrollo) | ✅ | 2026-07-11 | Redis + MinIO solamente, app en local, DB externa |
| Dockerfile | ✅ | 2026-07-11 | Python 3.12-slim + uvicorn |
| Alembic config (async) | ✅ | 2026-07-11 | env.py configurado con modelos y async engine |
| .env configurado | ✅ | 2026-07-11 | PostgreSQL localhost:5433, Redis/MinIO en Docker |
| .env.example | ✅ | 2026-07-11 | Actualizado con patrón dev |
| CI/CD básico | ⬚ Pendiente | — | — |

### Base de datos
| Tarea | Estado | Fecha | Notas |
|-------|--------|-------|-------|
| Modelo `users` | ✅ | 2026-07-11 | SQLAlchemy + Pydantic |
| Modelo `messages` | ✅ | 2026-07-11 | Con ENUMs, JSONB, timestamps por etapa |
| Modelo `assets` | ✅ | 2026-07-11 | JSONB + GIN + pgvector Vector(1024) + soft delete |
| Modelo `events` | ✅ | 2026-07-11 | target_date indexada, recurrence_rule JSONB |
| Modelo `reminders` | ✅ | 2026-07-11 | Con auditoría de mensaje enviado |
| Migración inicial | ✅ | 2026-07-11 | 5 tablas + pgvector extension creadas en PG 16 Docker :5434 |
| Esquema `topics`, `notes` | ⬚ Pendiente | — | — |
| Esquema `lists`, `list_items` | ⬚ Pendiente | — | — |
| Esquema `projects`, `project_tasks` | ⬚ Pendiente | — | — |
| Esquema contactos, gastos, suscripción | ⬚ Pendiente | — | — |
| Vista `searchable_content` | ⬚ Pendiente | — | — |

### Bot de Telegram
| Tarea | Estado | Fecha | Notas |
|-------|--------|-------|-------|
| Webhook recepción mensajes | ✅ | 2026-07-11 | POST /telegram/webhook — texto, photo, audio |
| Ack inmediato | ⬚ Pendiente | — | Estructura lista, falta enviar mensaje a Telegram API |
| Confirmación editable | ⬚ Pendiente | — | — |

### Pipeline de IA
| Tarea | Estado | Fecha | Notas |
|-------|--------|-------|-------|
| Integración Haiku 4.5 | ⬚ Pendiente | — | — |
| Integración Sonnet 5 | ⬚ Pendiente | — | — |
| Integración Whisper | ⬚ Pendiente | — | — |
| OCR/visión de facturas | ⬚ Pendiente | — | — |

### Motor de Reglas
| Tarea | Estado | Fecha | Notas |
|-------|--------|-------|-------|
| Regla matriculación por placa | ⬚ Pendiente | — | — |
| Pico y placa semanal | ⬚ Pendiente | — | — |
| APScheduler cron diario | ⬚ Pendiente | — | — |
| Recordatorios escalonados | ⬚ Pendiente | — | — |

### Núcleo Transversal
| Tarea | Estado | Fecha | Notas |
|-------|--------|-------|-------|
| Captura libre de texto | ⬚ Pendiente | — | — |
| Múltiples instrucciones | ⬚ Pendiente | — | — |
| Recurrencias complejas | ⬚ Pendiente | — | — |
| Búsqueda conversacional | ⬚ Pendiente | — | — |
| Listas simples | ⬚ Pendiente | — | — |
| Resumen diario/semanal opt-in | ⬚ Pendiente | — | — |

### "Lucho piensa" (mínimo)
| Tarea | Estado | Fecha | Notas |
|-------|--------|-------|-------|
| Cálculos sobre datos | ⬚ Pendiente | — | — |
| Explicaciones con norma citable | ⬚ Pendiente | — | — |
| Preparación de acciones | ⬚ Pendiente | — | — |

---

## Fase 2 — Beta Cerrada
**Estado:** ⬚ No iniciada

## Fase 3 — Lanzamiento con Monetización
**Estado:** ⬚ No iniciada

## Fase 4 — Cruce a SMB
**Estado:** ⬚ No iniciada

## Fase 5 — Expansión Regional y Premium
**Estado:** ⬚ No iniciada

---

## Leyenda

- ✅ Completado
- 🔨 En progreso
- ⬚ Pendiente
- ❌ Cancelado
- ⚠️ Bloqueado
