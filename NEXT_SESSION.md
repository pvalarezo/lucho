# NEXT_SESSION.md — Lucho

---

## Sesión actual — 2026-07-16

**v2.9.2 — Telegram polling eliminado: webhook unificado + docs actualizados**

### Entregables:

#### Telegram: Polling → Webhook unificado ✅
- `app/routers/webhook.py` reescrito con funcionalidad completa (transcripción, dedup, acks)
- Archivos eliminados: `app/bot.py`, `run_bot.py`, `lucho-bot.service`
- `scripts/setup_telegram_webhook.py` para configurar webhook
- `telegram.py` ahora incluye `set_webhook()`, `get_webhook_info()`, `delete_webhook()`
- Todos los MD actualizados: 2 servicios en vez de 3, sin referencias a polling

#### Meta Live — Cuenta WhatsApp lista ✅
- WhatsApp ya funciona, solo faltan crear los templates

---

## Próxima sesión — Prioridades

### 🔴 INMEDIATA — Arrancar y configurar

**1. Arrancar servicios**
- [ ] `systemctl --user start lucho-api lucho-tunnel`
- [ ] Verificar: `curl https://lucho-dev.apx5.com/`

**2. Configurar webhook de Telegram**
- [ ] `python scripts/setup_telegram_webhook.py`
- [ ] `python scripts/setup_telegram_webhook.py --info`
- [ ] Probar que el bot responde en Telegram

**3. Crear templates en Meta Business Manager**
- [ ] Usar `docs/whatsapp_templates.md` como guía
- [ ] Crear 4 templates: `document_reminder`, `project_reminder`, `pico_y_placa`, `daily_digest`
- [ ] Esperar aprobación Meta (24-48h)

### 🟡 MEDIA — Scheduler con templates

**4. Conectar templates en el scheduler**
- [ ] Implementar `send_template_message` en `whatsapp.py`
- [ ] `_send_document_reminder` → template en WhatsApp
- [ ] `_send_project_reminder` → template en WhatsApp
- [ ] `daily_digest` → resumen vía template WhatsApp
- [ ] Nuevo job: notificación pico y placa vía template

### 🟢 FASE 2 — Beta Cerrada

**5. Onboarding guiado**
- [ ] Diseñar 3 primeros mensajes de bienvenida
- [ ] Flujo: saludo → preguntar intereses → sugerir primer uso

**6. Métricas**
- [ ] % extracción correcta
- [ ] Retención D7 / D30
- [ ] Intención de pago

**7. Seguridad / LOPDP**
- [ ] Cifrado en reposo
- [ ] Política de privacidad

**8. Funcionalidades Ola 2**
- [ ] Fechas especiales (cumpleaños, aniversarios)
- [ ] Vacunas (hijos, mascotas)
- [ ] Suscripciones y servicios olvidados
- [ ] Control de gastos personales (tracking + ingresos)

### ⚪ FUTURO

- [ ] Whisper local ($0 transcripción)
- [ ] Skills adicionales (transporte, servicios básicos)
- [ ] Dashboard de métricas
- [ ] Fase 3: pagos, facturación SRI, fiscal/financiero

---

## Comandos rápidos

```bash
# Arrancar servicios
systemctl --user start lucho-api lucho-tunnel

# Logs
journalctl --user -u lucho-api -f
journalctl --user -u lucho-tunnel -f

# Webhook Telegram
python scripts/setup_telegram_webhook.py
python scripts/setup_telegram_webhook.py --info

# Git
git add -A && git commit -m "mensaje"
git tag vX.Y.Z -m "descripción"
```
