# NEXT_SESSION.md — Lucho

---

## Sesión finalizada — 2026-07-21 (sesión extendida)

**v2.12.4 — Módulo de Finanzas Personales completo + mejoras UX**

### Entregables completados en esta sesión:

#### 📨 WhatsApp Templates verificados (v2.10.1)
- 4/4 templates probados con envío real
- `project_reminder` usa `language_code="en"` temporal

#### 🐛 Eventos arreglados (v2.10.2)
- `_evaluate_events` ahora SÍ envía notificaciones (antes solo creaba DB records)
- Template `event_reminder` especificado

#### ⏰ Ad-hoc reminders sub-día (v2.11.0)
- `events.target_date` → `TIMESTAMP` con hora
- `schedule_event_reminder()` vía `DateTrigger`
- "avísame en 3 minutos" → job dispara exacto

#### 🔧 System prompt reforzado (v2.11.1)
- Reglas no negociables PRIMERO
- Tabla tool↔intención explícita
- DeepSeek ahora cumple tool calling

#### 🕐 Hora local Ecuador (v2.11.2)
- Cero conversiones UTC/ZoneInfo
- `AGENTS.md` §2.4: regla de zona horaria

#### 💰 Módulo de Finanzas Personales (v2.12.0)
- Tablas: `transactions` + `budgets` con 3 ENUMs
- 5 tools: `add_transaction`, `list_transactions`, `get_balance`, `set_budget`, `check_budget`
- `_evaluate_budgets`: alerta diaria al exceder presupuesto
- `shared_expenses` eliminado (reemplazado por `add_transaction`)
- `save_expense` tool eliminado
- Tools totales: 22 → 26

#### 📱 Mejoras UX (v2.12.1–v2.12.4)
- Formato WhatsApp: prohibido tablas, solo emojis + bullets
- Sin reacción ⏳ — solo typing indicator "..."
- Onboarding actualizado (WhatsApp + Telegram)
- System prompt completo con 26 tools

### Archivos modificados (20+):
| Archivo | Cambio |
|---------|--------|
| `app/models/transaction.py` | 🆕 Transaction + Budget + ENUMs |
| `app/models/__init__.py` | 🔧 Registro + limpieza shared_expenses |
| `app/models/event.py` | 🔧 DATE → DateTime(timezone=False) |
| `app/models/shared_expense.py` | 🗑️ Eliminado |
| `app/services/persistence.py` | 🔧 +persist_transaction, +persist_budget, -shared |
| `app/services/scheduler.py` | 🔧 +_evaluate_budgets, sin TZ, ad-hoc |
| `app/services/search.py` | 🔧 upcoming_deadlines sin timezone |
| `app/services/llm/base.py` | 🔧 +transaction extraction, -shared_expense |
| `app/agent/tools.py` | 🔧 +5 finance handlers, -save_expense |
| `app/agent/lucho_system_prompt.py` | 🔧 Reescritura, 26 tools, formato WA |
| `app/routers/whatsapp_webhook.py` | 🔧 Sin ⏳, onboarding con finanzas |
| `app/routers/webhook.py` | 🔧 Onboarding Telegram con finanzas |
| `app/routers/internal_test.py` | 🆕 Endpoint prueba ad-hoc |
| `scripts/test_whatsapp_templates.py` | 🆕 Test 5 templates |
| `docs/finanzas_especificacion.md` | 🆕 Especificación completa |
| `docs/whatsapp_templates.md` | 🔧 +event_reminder, +budget_alert |
| `AGENTS.md` | 🔧 §2.4 Zona Horaria, Fase 2 |
| `PROGRESS.md`, `NEXT_SESSION.md` | 📝 Actualizados |
| `tests/unit.py` | 🔧 22→26 tools, nuevos handlers |
| `alembic/versions/` | 🆕 3 migraciones |

### Tests: 348/348 (100%) ✅

---

## Próxima sesión — Prioridades

### 🔴 INMEDIATA

**1. Probar Finanzas en profundidad**
- [ ] Probar todos los flujos con datos reales
- [ ] Ajustar categorías según feedback
- [ ] Verificar alertas de presupuesto

**2. Templates pendientes en Meta**
- [ ] `event_reminder` (es) — 5 params, crear en Meta
- [ ] `budget_alert` (es) — 5 params, crear en Meta
- [ ] `project_reminder` (es) — esperar traducción español
- [ ] Revertir `language_code="en"` → `"es"` cuando se apruebe

### 🟡 FASE 2

**3. Métricas** — % extracción correcta, retención D7/D30, intención de pago
**4. Ola 2** — cumpleaños, vacunas, suscripciones

### ⚪ FUTURO
- Whisper local, Anthropic Sonnet, dashboard, Fase 3 pagos

---

## Comandos rápidos

```bash
# Arrancar servicios
systemctl --user start lucho-api lucho-tunnel

# Probar templates
python3 scripts/test_whatsapp_templates.py 593993832368

# Probar ad-hoc reminder
curl -X POST http://localhost:8000/internal/test-reminder \
  -H "Content-Type: application/json" \
  -d '{"whatsapp_id":"593993832368","title":"Test","minutes_from_now":2}'

# Tests
python3 tests/unit.py

# Migraciones
python3 -m alembic upgrade head
```
