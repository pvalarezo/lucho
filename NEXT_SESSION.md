# NEXT_SESSION.md — Lucho

---

## Sesión actual — 2026-07-16

**v2.9.2 — Telegram polling eliminado: webhook unificado**

### Entregables de la sesión:

#### Telegram: Polling → Webhook unificado ✅
- `app/routers/webhook.py` reescrito con todas las funcionalidades de `bot.py`:
  - Transcripción de audio con Whisper
  - Deduplicación de mensajes
  - Ack inmediato ("Transcribiendo...", "📝 Entendido")
  - Manejo de fotos, documentos, y audio consistente con WhatsApp
- Archivos eliminados: `app/bot.py`, `run_bot.py`, `lucho-bot.service`
- `app/services/telegram.py` ahora incluye `set_webhook()`, `get_webhook_info()`, `delete_webhook()`
- `scripts/setup_telegram_webhook.py` para configurar el webhook
- `docs/development_setup.md` actualizado: 2 servicios en vez de 3
- Arquitectura unificada: Telegram y WhatsApp usan el mismo patrón webhook → lucho-api

#### Meta Live — Cuenta WhatsApp lista ✅
- La cuenta de WhatsApp ya está lista y funcional

---

## Próxima sesión — Prioridades

### 🔴 INMEDIATA

**1. Arrancar servicios y configurar webhook de Telegram**
- [ ] `systemctl --user start lucho-api lucho-tunnel`
- [ ] `python scripts/setup_telegram_webhook.py`
- [ ] Probar que el bot responde en Telegram vía webhook

**2. Crear templates en Meta Business Manager**
- [ ] Usar `docs/whatsapp_templates.md` como guía
- [ ] Crear 4 templates en Meta Developers
- [ ] Esperar aprobación (24-48h)

### 🟡 MEDIA

**3. Conectar templates en el scheduler**
- Modificar `_send_document_reminder` para usar `send_template_message` en WhatsApp
- Modificar `_send_project_reminder` para usar `send_template_message` en WhatsApp
- Agregar envío WhatsApp al `daily_digest`
- Agregar job de notificación pico y placa vía template

### 🟢 BAJA

**4. Whisper local** — transcripción sin costo de API
**5. Skills adicionales** — transporte, servicios básicos
**6. Dashboard de métricas**
**7. Fase 2** — onboarding guiado, métricas, fechas especiales, vacunas, suscripciones

---

## Comandos rápidos

```bash
# Servicios (solo 2 ahora)
systemctl --user start lucho-api lucho-tunnel

# Logs
journalctl --user -u lucho-api -f
journalctl --user -u lucho-tunnel -f

# Configurar webhook Telegram (una vez)
python scripts/setup_telegram_webhook.py
python scripts/setup_telegram_webhook.py --info

# Git
git add -A && git commit -m "mensaje"
git tag vX.Y.Z -m "descripción"
```
