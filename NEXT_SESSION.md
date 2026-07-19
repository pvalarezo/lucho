# NEXT_SESSION.md — Lucho

---

## Sesión finalizada — 2026-07-18/19

**v2.9.3 — Suscripción, trial, onboarding, WhatsApp UX, debounce**

### Entregables completados:

#### 🗄️ Base de datos
- `subscription_plans`: catálogo de planes con features en JSONB (plan "Básico" creado)
- `user_profiles`: datos post-pago (cédula, correo, nombre completo, políticas)
- `users`: is_active=False (default), +preferred_name, +onboarding_step
- `subscriptions`: plan FK a subscription_plans, +payment_method, +renewal_type
- `payments`: +user_id FK, +payment_method

#### 🔐 Seguridad + Trial
- Trial 7 días automático al registrarse (plan Básico, todos los features)
- Middleware `check_access()` en webhooks Telegram + WhatsApp
- Estados: trial → active (post-pago) / expired (sin pago)
- `_ensure_trial_subscription()` fallback para usuarios sin suscripción

#### 👋 Onboarding 3 pasos
- Msg 1: Presentación Lucho + funcionalidades (con Patricio texts)
- Msg 2: "¿Cómo quieres que te llame?"
- Msg 3: "Perfecto *nombre*, 7 días GRATIS..."
- Campo `onboarding_step` (0→1→2→done)

#### 💬 WhatsApp UX
- ⏳ Reacción inmediata (reloj) al recibir mensaje
- Typing indicator oficial (3 puntitos vía `status:read` + `typing_indicator`)
- Debounce 3 segundos: espera silencio, procesa mensajes agrupados
- Webhook WhatsApp reescrito limpio con arquitectura save → debounce → process

#### 🏗️ Infraestructura
- Telegram polling eliminado → webhook unificado
- Scripts: `seed_subscription_plans.py`, `manage_users.py`, `setup_telegram_webhook.py`
- 2 servicios systemd (lucho-api + lucho-tunnel), antes eran 3
- Alembic migrations aplicadas correctamente

---

## Próxima sesión — Prioridades

### 🔴 INMEDIATA

**1. Crear templates en Meta Business Manager**
- [ ] Usar `docs/whatsapp_templates.md` como guía
- [ ] Crear 4 templates: `document_reminder`, `project_reminder`, `pico_y_placa`, `daily_digest`
- [ ] Esperar aprobación Meta (24-48h)

### 🟡 MEDIA

**2. Conectar templates en el scheduler**
- [ ] Implementar `send_template_message` con parámetros en `whatsapp.py`
- [ ] Recordatorios de documentos, proyectos, pico y placa, daily digest via template

**3. Flujo post-pago**
- [ ] Cuando trial expira: solicitar cédula, correo, nombre completo
- [ ] Enviar link de políticas de privacidad
- [ ] Registrar aceptación ("SI") en user_profiles

### 🟢 FASE 2

**4. Métricas** — % extracción correcta, retención D7/D30, intención de pago
**5. Ola 2** — cumpleaños, vacunas, suscripciones, control de gastos

### ⚪ FUTURO
- Whisper local ($0), skills adicionales, dashboard
- Fase 3: pagos reales (Kushki/PayPhone), facturación SRI

---

## Comandos rápidos

```bash
# Arrancar servicios
systemctl --user start lucho-api lucho-tunnel

# Webhook Telegram
python scripts/setup_telegram_webhook.py

# Gestionar usuarios
python scripts/manage_users.py --list
python scripts/manage_users.py --activate 593987654321

# Git
git add -A && git commit -m "mensaje"
git tag vX.Y.Z -m "descripción"
```
