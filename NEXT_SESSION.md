# NEXT_SESSION.md — Lucho

---

## Sesión finalizada — 2026-07-21

**v2.10.1 — WhatsApp Templates verificados + test script**

### Entregables completados en esta sesión:

#### 🧪 Tests ajustados post v2.9.4
- Tool count: 18 → 19 → 22
- Guardrail check: "capital de Francia" → "NUNCA MIENTAS"
- Short prompt: recortado de 519 → 452 chars
- Unit tests: 307/307 (100%)

#### 📨 WhatsApp Templates corregidos
- `document_reminder`: 6 params, `{{2}}`=`{{6}}` (variables repetidas → Meta no permite)
- `project_reminder`: 6 params, `{{3}}`=`{{6}}`
- `pico_y_placa`: sin cambios (2 params)
- `daily_digest`: recreado como UTILITY (sin CTA, con firma "— Lucho")
- Las 4 plantillas creadas en Meta, en revisión

#### ⏰ Scheduler conectado a WhatsApp templates
- `_send_document_reminder`: WhatsApp template con 6 body_params
- `_send_project_reminder`: WhatsApp template con 6 body_params
- `_evaluate_pico_y_placa`: nueva función diaria, template 2 params
- `run_daily_digest`: multicanal (Telegram + WhatsApp template)
- Import `whatsapp_svc` agregado

#### 📝 Flujo post-pago
- `AccessResult` extendido con `post_pago_step`
- `check_access()` inicia flujo al expirar trial
- `advance_post_pago_step()`: 4 pasos (cédula → email → nombre → políticas)
- WhatsApp + Telegram sincronizados
- Datos guardados en `user_profiles` (id_number, email, full_name, privacy_accepted)

#### 🚗 Módulo de Vehículos independiente
- Tablas: `vehicles` + `vehicle_maintenances` (Alembic migration)
- Tools nuevas: `list_my_vehicles`, `add_maintenance`, `list_maintenances`
- `save_vehicle` migrado de Assets → Vehicles
- Límite parametrizable: `plan.features.max_vehicles` (default 2)
- Scheduler actualizado a tabla `vehicles`
- `check_vehicle_info`: consulta API externa ANT/SRI/multas (sin tabla multas)

### Archivos modificados (14):
| Archivo | Cambio |
|---------|--------|
| `app/models/vehicle.py` | 🆕 Vehicle + VehicleMaintenance + MaintenanceType |
| `app/models/__init__.py` | 🔧 Registro modelos nuevos |
| `alembic/versions/9a5e88f1a576_*.py` | 🆕 Migración autogenerada |
| `app/agent/tools.py` | 🔧 save_vehicle → vehicles, +3 handlers, 22 tools total |
| `app/agent/lucho_system_prompt.py` | 🔧 Short prompt recortado 452 chars |
| `app/services/scheduler.py` | 🔧 Vehicle queries, _evaluate_pico_y_placa, digest |
| `app/services/user.py` | 🔧 AccessResult, check_access, advance_post_pago_step |
| `app/routers/whatsapp_webhook.py` | 🔧 Post-pago flow, paso 3-6 |
| `app/routers/webhook.py` | 🔧 Post-pago flow (Telegram) |
| `scripts/seed_subscription_plans.py` | 🔧 max_vehicles: 2 |
| `docs/whatsapp_templates.md` | 🔧 Plantillas corregidas |
| `tests/unit.py` | 🔧 19→22 tools, guardrail, handler_map |
| `PROGRESS.md` | 📝 v2.10.0 |
| `ROADMAP.md` | 📝 Actualizado |

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

**2. Templates en Meta** — 3/4 aprobados en español
- [x] 4 plantillas creadas
- [x] `initial_greeting` traducido a español
- [x] `document_reminder` (es) — ✅ aprobado y probado
- [x] `pico_y_placa` (es) — ✅ aprobado y probado
- [x] `daily_digest` (es) — ✅ aprobado y probado
- [x] `project_reminder` (en) — ⚠️ aprobado solo en inglés, usando `language_code="en"` temporal
- [ ] Esperar aprobación de `project_reminder` en español para revertir a `language_code="es"`

### 🟢 FASE 2

**3. Métricas** — % extracción correcta, retención D7/D30, intención de pago
**4. Ola 2** — cumpleaños, vacunas, suscripciones, control de gastos

### ⚪ FUTURO
- Whisper local ($0), skills adicionales, dashboard
- Fase 3: pagos reales (Kushki/PayPhone), facturación SRI
- Activar Anthropic Sonnet cuando se configure API key
- Revertir `project_reminder` a `language_code="es"` cuando Meta apruebe la traducción

---

## Comandos rápidos

```bash
# Probar templates WhatsApp
python3 scripts/test_whatsapp_templates.py 593993832368
python3 scripts/test_whatsapp_templates.py 593993832368 --template document_reminder
```

```bash
# Arrancar servicios
systemctl --user start lucho-api lucho-tunnel

# Webhook Telegram
python scripts/setup_telegram_webhook.py

# Gestionar usuarios
python scripts/manage_users.py --list
python scripts/manage_users.py --activate 593987654321

# Aplicar migraciones
python -m alembic upgrade head

# Sembrar planes de suscripción
python scripts/seed_subscription_plans.py

# Unit tests
python tests/unit.py

# Git
git add -A && git commit -m "mensaje"
git tag vX.Y.Z -m "descripción"
```
