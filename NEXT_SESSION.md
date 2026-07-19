# NEXT_SESSION.md — Lucho

---

## Sesión actual — 2026-07-18

**v2.9.3 — Sistema de suscripción, trial, onboarding y control de acceso**

### Entregables:

#### Tablas nuevas ✅
- `subscription_plans`: catálogo de planes con features en JSONB
- `user_profiles`: datos post-pago (cédula, correo, nombre completo, políticas)

#### Modelos modificados ✅
- `users`: is_active default=False, +preferred_name, +onboarding_complete
- `subscriptions`: plan FK a subscription_plans, +payment_method, +renewal_type
- `payments`: +user_id FK, +payment_method

#### Sistema de Trial + Acceso ✅
- Nuevos usuarios: trial 7 días, plan Básico, acceso completo
- Middleware `check_access()` en ambos webhooks
- Estados: trial → active (post-pago) / expired (sin pago)

#### Onboarding guiado ✅
- Webhook envía bienvenida con info de trial + "¿cómo querés que te llame?"
- System prompt actualizado con instrucciones de onboarding
- `onboarding_complete = True` automático tras primera interacción exitosa

#### Scripts ✅
- `scripts/seed_subscription_plans.py`: crea el plan Básico
- `scripts/manage_users.py`: listar, activar, desactivar usuarios

---

## Próxima sesión — Prioridades

### 🔴 INMEDIATA — Puesta en marcha

**1. Correr migración y seed**
- [ ] `python3 -m alembic upgrade head`
- [ ] `python scripts/seed_subscription_plans.py`

**2. Arrancar servicios y configurar webhook**
- [ ] `systemctl --user start lucho-api lucho-tunnel`
- [ ] `python scripts/setup_telegram_webhook.py`

**3. Probar flujo completo**
- [ ] Escribir desde un número NUEVO en WhatsApp/Telegram
- [ ] Verificar que recibe el mensaje de bienvenida trial
- [ ] Verificar que puede interactuar normalmente
- [ ] `python scripts/manage_users.py --list` para ver el usuario creado

**4. Crear templates en Meta Business Manager**
- [ ] Usar `docs/whatsapp_templates.md` como guía
- [ ] Crear 4 templates en Meta Developers

### 🟡 MEDIA

**5. Conectar templates en el scheduler**
- [ ] Implementar `send_template_message` en `whatsapp.py`
- [ ] Recordatorios de documentos, proyectos, pico y placa, daily digest

**6. Post-pago: flujo de activación**
- [ ] Cuando el trial expira y el usuario paga:
  - [ ] Solicitar cédula, correo, nombre completo
  - [ ] Enviar link de políticas de privacidad
  - [ ] Registrar aceptación ("SI")
  - [ ] Activar suscripción (status = active)

### 🟢 FASE 2 — Beta Cerrada

**7. Métricas** — % extracción correcta, retención D7/D30, intención de pago
**8. Funcionalidades Ola 2** — cumpleaños, vacunas, suscripciones, control de gastos

### ⚪ FUTURO

- [ ] Whisper local ($0 transcripción)
- [ ] Dashboard de métricas
- [ ] Fase 3: pagos reales (Kushki/PayPhone), facturación SRI

---

## Comandos rápidos

```bash
# Migración
python3 -m alembic upgrade head
python scripts/seed_subscription_plans.py

# Arrancar servicios
systemctl --user start lucho-api lucho-tunnel

# Webhook Telegram
python scripts/setup_telegram_webhook.py
python scripts/setup_telegram_webhook.py --info

# Gestionar usuarios
python scripts/manage_users.py --list
python scripts/manage_users.py --activate 593987654321
python scripts/manage_users.py --show 593987654321

# Logs
journalctl --user -u lucho-api -f

# Git
git add -A && git commit -m "mensaje"
git tag vX.Y.Z -m "descripción"
```
