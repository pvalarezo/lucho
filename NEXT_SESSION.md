# NEXT_SESSION.md — Lucho

---

## Sesión actual — 2026-07-16

**v2.9.1 — WhatsApp Templates documentados + OCR DeepSeek**

### Entregables de la sesión:

#### OCR/Visión — Migrado a DeepSeek ✅
- `extract_document_data` usa DeepSeek Vision como primario
- Nueva función `_deepseek_ocr` que reusa `_deepseek_vision` con `OCR_EXTRACTION_PROMPT`
- Fallback: DeepSeek → Anthropic → OpenAI
- Código muerto eliminado en `vision.py` (bloque duplicado)

#### Transcripción de audio — Análisis completado ✅
- DeepSeek, MiniMax, Kimi no ofrecen STT. OpenAI Whisper se mantiene.
- Alternativa futura: Whisper local ($0 costo)

#### Meta Live — Configuración verificada ✅
- WHATSAPP_PHONE_NUMBER_ID, ACCESS_TOKEN, VERIFY_TOKEN confirmados
- Webhook verificado: responde hub.challenge correctamente
- API + Tunnel corriendo
- ⏳ Pendiente: aprobación de business verification por Meta

#### WhatsApp Templates — Documentados ✅
- 4 templates diseñados y documentados en `docs/whatsapp_templates.md`
- Templates: `document_reminder`, `project_reminder`, `pico_y_placa`, `daily_digest`
- Categoría UTILITY, pendientes de creación en Meta y aprobación (24-48h)

---

## Próxima sesión — Prioridades

### 🔴 INMEDIATA

**1. Activar app Meta en Live**
- [ ] Verificar estado de business verification en Meta
- [ ] Cambiar switch Desarrollo → Activo en consola Meta
- [ ] Probar mensaje desde número real sin whitelist

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

**4. Lucho Bot (Telegram polling)**
- No está corriendo actualmente
- Evaluar si mantener o migrar todo a webhook

### 🟢 BAJA

**5. Whisper local** — transcripción sin costo de API
**6. Skills adicionales** — transporte, servicios básicos
**7. Dashboard de métricas**

---

## Comandos rápidos

```bash
# Servicios
systemctl --user start lucho-api lucho-tunnel

# Logs
journalctl --user -u lucho-api -f
journalctl --user -u lucho-tunnel -f

# Git
git add -A && git commit -m "mensaje"
git tag vX.Y.Z -m "descripción"
```
