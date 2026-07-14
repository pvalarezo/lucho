# NEXT_SESSION.md — Lucho

---

## Sesión actual — 2026-07-14

**v2.8.0 — WhatsApp Cloud API + infraestructura de desarrollo**

### Entregables de la sesión:

#### v2.7.0 → v2.7.1 — Web Search Tool
- ✅ Tool `web_search` con DuckDuckGo (ddgs) — tool #19
- ✅ Scope ampliado de Ecuador → MUNDIAL (cualquier tema)
- ✅ System prompt reforzado: "usá web_search SIEMPRE"

#### v2.8.0 — WhatsApp Cloud API
- ✅ `app/services/whatsapp.py`: cliente Cloud API (send_message, send_photo, send_template, download_media, verify_webhook)
- ✅ `app/routers/whatsapp_webhook.py`: GET (verify) + POST (receive messages)
- ✅ `app/services/user.py`: `resolve_user_by_phone()` para usuarios WhatsApp
- ✅ `app/services/notifications.py`: `_send_whatsapp()` real (ya no placeholder)
- ✅ `app/config.py`: WHATSAPP_PHONE_NUMBER_ID, ACCESS_TOKEN, VERIFY_TOKEN, API_VERSION
- ✅ `app/main.py`: router WhatsApp registrado
- ✅ `.env`: credenciales WhatsApp configuradas

#### Infraestructura de desarrollo
- ✅ Cloudflare Tunnel: `https://lucho-dev.apx5.com` → `localhost:8000`
- ✅ Systemd user services: `lucho-api`, `lucho-tunnel`, `lucho-bot` (disabled at boot)
- ✅ Webhook WhatsApp verificado ✅
- ✅ Mensajes entrantes: recibidos, usuario creado, persistidos, agente procesa
- ⚠️ Envío saliente: error #131030 (modo Desarrollo — falta lista blanca de recipients)
- ✅ `docs/development_setup.md`: guía completa de desarrollo

### Tags aplicados:
```
v2.8.0 — WhatsApp Cloud API integration + dev setup docs
v2.7.1 — Web search MUNDIAL, sin restricción de temas
v2.7.0 — Web search tool: DuckDuckGo ddgs
```

---

## Próxima sesión — Prioridades

### 🔴 INMEDIATA

**1. Testear WhatsApp end-to-end**
- [ ] Agregar número personal a lista blanca de recipients en Meta
- [ ] Mandar mensaje real desde WhatsApp personal → Lucho responde
- [ ] Probar: texto, foto, audio
- [ ] Verificar persistencia en DB y respuestas del agente

### 🟡 MEDIA

**2. Pasar app Meta a modo Live**
- Verificación de negocio en Meta (business verification)
- Cambiar webhook de test → producción
- Testear con usuarios reales

### 🟢 BAJA

**3. Indexado numerado en búsquedas**
Resultados numerados (1, 2, 3) y aceptar "el 2".

**4. Skills adicionales (opcional)**
- `services/transport.md` — Metro Quito, Metrovía, Tranvía Cuenca
- `services/utilities.md` — Planilla de luz, subsidios, tarifas

**5. Dashboard de métricas**
Precisión del agente, retención, uso por tipo de tool.

---

## Comandos rápidos

```bash
# Servicios
systemctl --user start lucho-api lucho-tunnel lucho-bot

# Logs
journalctl --user -u lucho-api -f
journalctl --user -u lucho-tunnel -f

# Git
git add -A && git commit -m "mensaje"
git tag vX.Y.Z -m "descripción"
```
