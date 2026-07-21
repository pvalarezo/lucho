# NEXT_SESSION.md — Lucho

---

## Sesión finalizada — 2026-07-21

**v2.11.2 — Ad-hoc reminders + Prompt reforzado + Hora local Ecuador**

### Entregables completados en esta sesión:

#### 📨 WhatsApp Templates — 4/4 verificados (v2.10.1)
- `document_reminder` (es): ✅ probado
- `project_reminder` (en): ✅ probado (pendiente traducción español)
- `pico_y_placa` (es): ✅ probado
- `daily_digest` (es): ✅ probado
- Script `test_whatsapp_templates.py` funcional

#### 🐛 Eventos NUNCA se enviaban — Arreglado (v2.10.2)
- `_evaluate_events` solo creaba registros en `reminders`, nunca despachaba
- Ahora envía notificación real (Telegram + WhatsApp template) como docs/projects
- Template `event_reminder` especificado (5 params, pendiente crear en Meta)

#### ⏰ Ad-hoc reminders sub-día (v2.11.0)
- `events.target_date`: `DATE` → `TIMESTAMPTZ` (fecha+hora)
- `schedule_event_reminder()`: job DateTrigger a la hora exacta
- `handle_save_event` dispara job cuando el evento tiene hora específica
- "recuérdame en 3 minutos" → job se dispara a los 3 min exactos

#### 🔧 System prompt reforzado (v2.11.1)
- Reglas no negociables PRIMERO (antes que personalidad)
- Tabla explícita: "si el usuario dice X → llamá tool Y"
- Palabras PROHIBIDAS: "guardé", "agendado", "listo" sin tool call
- DeepSeek ahora cumple tool calling (antes mentía)
- Prompt incluye hora actual para cálculos correctos

#### 🕐 Hora local Ecuador (v2.11.2)
- `TIMESTAMPTZ` → `TIMESTAMP WITHOUT TIME ZONE`
- Eliminadas TODAS las conversiones UTC/ZonInfo/astimezone
- `persist_event`: naive datetime guardado directo
- `schedule_event_reminder`: `datetime.now()` + `DateTrigger` hora sistema
- Display muestra hora Ecuador directamente
- Regla agregada a AGENTS.md

### Archivos modificados (13):
| Archivo | Cambio |
|---------|--------|
| `app/models/event.py` | 🔧 DATE → DateTime(timezone=False) |
| `app/services/scheduler.py` | 🔧 _evaluate_events envía, schedule_event_reminder, sin TZ |
| `app/services/persistence.py` | 🔧 Sin conversión UTC, naive datetime directo |
| `app/services/search.py` | 🔧 upcoming_deadlines sin timezone |
| `app/agent/tools.py` | 🔧 handle_save_event → schedule_event_reminder |
| `app/agent/lucho_system_prompt.py` | 🔧 Reescritura completa, hora actual en prompt |
| `app/schemas/event.py` | 🔧 date → datetime |
| `app/services/llm/base.py` | 🔧 Extraction prompt incluye hora |
| `app/main.py` | 🔧 Router internal_test |
| `app/routers/internal_test.py` | 🆕 Endpoint de prueba ad-hoc |
| `scripts/test_whatsapp_templates.py` | 🆕 + event_reminder test |
| `docs/whatsapp_templates.md` | 🔧 Template 5: event_reminder |
| `AGENTS.md` | 🔧 Sección 2.4 Zona Horaria, Fase 2 |
| `alembic/versions/` | 🆕 2 migraciones (DATE→TIMESTAMPTZ→TIMESTAMP) |
| `PROGRESS.md`, `NEXT_SESSION.md` | 📝 Actualizados |

### Tests: 308/308 (100%) ✅

---

## Próxima sesión — Prioridades

### 🔴 INMEDIATA

**1. Módulo de Finanzas Personales** 🆕
- [ ] Tablas: `transactions` (ingreso/gasto, monto, categoría, fecha, cuenta, notas)
- [ ] Tablas: `budgets` (presupuesto mensual por categoría)
- [ ] Categorías predefinidas: alimentación, transporte, vivienda, salud, entretenimiento, servicios, otros
- [ ] Tools: `add_transaction`, `list_transactions`, `get_balance`, `set_budget`, `check_budget`
- [ ] Scheduler: alerta cuando se excede presupuesto
- [ ] Resumen mensual: "gastaste $X este mes, tu categoría top fue..."

### 🟡 ESPERA

**2. Templates en Meta**
- [x] `document_reminder` (es), `pico_y_placa` (es), `daily_digest` (es) — aprobados
- [x] `project_reminder` (en) — aprobado, esperando traducción español
- [ ] `event_reminder` (es) — PENDIENTE crear en Meta (5 params, espec en docs/whatsapp_templates.md)
- [ ] Revertir `language_code="en"` → `"es"` en project_reminder cuando se apruebe

### 🟢 FASE 2

**3. Métricas** — % extracción correcta, retención D7/D30, intención de pago
**4. Ola 2** — cumpleaños, vacunas, suscripciones, control de gastos

### ⚪ FUTURO
- Whisper local, Anthropic Sonnet, dashboard, Fase 3 pagos

---

## Comandos rápidos

```bash
# Arrancar servicios
systemctl --user start lucho-api lucho-tunnel

# Probar templates WhatsApp
python3 scripts/test_whatsapp_templates.py 593993832368

# Probar ad-hoc reminder
curl -X POST http://localhost:8000/internal/test-reminder \
  -H "Content-Type: application/json" \
  -d '{"whatsapp_id":"593993832368","title":"Test","minutes_from_now":2}'

# Unit tests
python3 tests/unit.py

# Migraciones
python3 -m alembic upgrade head

# Git
git add -A && git commit -m "mensaje"
git tag vX.Y.Z -m "descripción"
```
