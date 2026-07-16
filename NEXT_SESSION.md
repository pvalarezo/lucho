# NEXT_SESSION.md — Lucho

---

## Sesión actual — 2026-07-16

**v2.9.0 — OCR/Visión migrado a DeepSeek + Meta Live verificado**

### Entregables de la sesión:

#### OCR/Visión — Migrado a DeepSeek
- ✅ `extract_document_data` ahora usa DeepSeek Vision como primario (antes solo Anthropic/OpenAI)
- ✅ Nueva función `_deepseek_ocr` que reusa `_deepseek_vision` con `OCR_EXTRACTION_PROMPT`
- ✅ Fallback: DeepSeek → Anthropic → OpenAI
- ✅ Código muerto eliminado: bloque duplicado en `analyze_image` (estaba después de `return None`)
- ✅ `analyze_image` (clasificación) ya funcionaba con DeepSeek, sin cambios

#### Transcripción de audio — Confirmado OpenAI Whisper
- ✅ DeepSeek no ofrece STT (solo chat + visión)
- ✅ MiniMax no ofrece STT (solo TTS)
- ✅ Kimi no ofrece STT (solo chat)
- ✅ OpenAI Whisper se mantiene como proveedor de transcripción

#### Meta Live — Configuración verificada
- ✅ WHATSAPP_PHONE_NUMBER_ID: 1181679805033971
- ✅ WHATSAPP_ACCESS_TOKEN: permanente configurado
- ✅ WHATSAPP_VERIFY_TOKEN: lucho_webhook_2026
- ✅ Webhook URL: https://lucho-dev.apx5.com/whatsapp/webhook
- ✅ Verificación de webhook: responde hub.challenge correctamente
- ✅ API + Tunnel corriendo
- ⏳ Pendiente: aprobación de business verification por Meta

---

## Próxima sesión — Prioridades

### 🔴 INMEDIATA

**1. Activar app Meta en Live**
- [ ] Esperar aprobación de business verification
- [x] Verificación de webhook confirmada
- [ ] Cambiar switch Desarrollo → Activo en consola Meta
- [ ] Probar con número real sin whitelist

### 🟡 MEDIA

**2. Notificaciones proactivas por WhatsApp**
- Templates de mensajes para recordatorios
- Fuera de la ventana de 24h: usar templates aprobados

**3. Lucho Bot (Telegram polling)**
- No está corriendo actualmente (solo systemd)
- Evaluar si mantener o migrar todo a webhook

### 🟢 BAJA

**4. Skills adicionales**
- Transporte, servicios básicos

**5. Dashboard de métricas**

**6. Whisper local**
- Evaluar migración de OpenAI Whisper → Whisper local para reducir costos a $0

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
