# Development Setup — Lucho

Cómo levantar y gestionar todos los servicios de Lucho en desarrollo.

---

## 1. Infraestructura (Docker)

```bash
cd /home/pvalarezo/auracore-apps/lucho
docker compose -f docker-compose.dev.yml up -d
```

| Servicio | Puerto | Consola |
|----------|--------|---------|
| PostgreSQL 16 + pgvector | 5434 | — |
| Redis | 6379 | — |
| MinIO | 9000 (API) / 9001 (consola) | http://localhost:9001 |

```bash
# Ver estado
docker compose -f docker-compose.dev.yml ps

# Apagar
docker compose -f docker-compose.dev.yml down
```

---

## 2. Variables de entorno

```bash
cp .env.example .env
# Editar .env con los valores reales
```

Variables clave:

| Variable | Descripción |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Token del bot de Telegram |
| `LLM_PROVIDER` | `deepseek` (default) |
| `DEEPSEEK_API_KEY` | API key de DeepSeek |
| `WHATSAPP_PHONE_NUMBER_ID` | De Meta Developers |
| `WHATSAPP_ACCESS_TOKEN` | De Meta Developers |
| `WHATSAPP_VERIFY_TOKEN` | Token que elijas para verificar webhook |

---

## 3. Servicios de Lucho

Lucho corre como **3 procesos independientes**. En desarrollo usamos **systemd user services** para que arranquen al boot y se reinicien si fallan.

### 3.1 FastAPI (API + webhooks)

```bash
# Iniciar
systemctl --user start lucho-api

# Detener
systemctl --user stop lucho-api

# Ver logs
journalctl --user -u lucho-api -f

# Manualmente (sin systemd)
cd /home/pvalarezo/auracore-apps/lucho
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Endpoints:
- `http://localhost:8000/` — health
- `http://localhost:8000/health` — health check
- `POST http://localhost:8000/telegram/webhook` — Telegram webhook
- `GET/POST http://localhost:8000/whatsapp/webhook` — WhatsApp webhook

### 3.2 Cloudflare Tunnel (HTTPS público)

```bash
# Iniciar
systemctl --user start lucho-tunnel

# Detener
systemctl --user stop lucho-tunnel

# Ver logs
journalctl --user -u lucho-tunnel -f

# Manualmente (sin systemd)
cloudflared tunnel run lucho-whatsapp
```

URL pública: `https://lucho-dev.apx5.com`

### 3.3 Telegram Bot (polling)

```bash
# Iniciar
systemctl --user start lucho-bot

# Detener
systemctl --user stop lucho-bot

# Ver logs
journalctl --user -u lucho-bot -f

# Manualmente (sin systemd)
cd /home/pvalarezo/auracore-apps/lucho
python3 run_bot.py
```

Bot: `@lucho_pvalarezo_bot`

---

## 4. Comandos rápidos

### Todo junto

```bash
# Arrancar todo
systemctl --user start lucho-api lucho-tunnel lucho-bot

# Detener todo
systemctl --user stop lucho-api lucho-tunnel lucho-bot

# Reiniciar todo
systemctl --user restart lucho-api lucho-tunnel lucho-bot

# Ver estado de todo
systemctl --user status lucho-api lucho-tunnel lucho-bot --no-pager
```

### Solo un servicio

```bash
# Reiniciar API después de cambiar código
systemctl --user restart lucho-api

# Reiniciar bot después de cambiar código
systemctl --user restart lucho-bot
```

### Verificar que funciona

```bash
# API local
curl http://localhost:8000/

# API pública (vía túnel)
curl https://lucho-dev.apx5.com/

# Webhook WhatsApp
curl "https://lucho-dev.apx5.com/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=lucho_webhook_2026&hub.challenge=test123"
# Debe devolver "test123" si el token coincide
```

---

## 5. Configuración inicial de Cloudflare Tunnel

Solo se hace **una vez**. El archivo `config.yml` ya existe.

```bash
# Instalar cloudflared
curl -sL "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64" -o ~/.local/bin/cloudflared
chmod +x ~/.local/bin/cloudflared

# Login (abre navegador)
cloudflared tunnel login

# Crear túnel
cloudflared tunnel create lucho-whatsapp

# DNS (apuntar subdominio al túnel)
cloudflared tunnel route dns lucho-whatsapp lucho-dev.apx5.com
```

Config: `~/.cloudflared/config.yml`
```yaml
tunnel: lucho-whatsapp
credentials-file: /home/pvalarezo/.cloudflared/<TUNNEL-UUID>.json

ingress:
  - hostname: lucho-dev.apx5.com
    service: http://localhost:8000
  - service: http_status:404
```

---

## 6. Systemd services (instalación)

Los archivos de servicio están en `~/.config/systemd/user/`. Se instalaron así:

```bash
# Una vez creados los archivos .service:
systemctl --user daemon-reload
systemctl --user enable lucho-api lucho-tunnel lucho-bot
systemctl --user start lucho-api lucho-tunnel lucho-bot
```

Para que corran sin sesión abierta (`linger=yes` ya está activado):
```bash
loginctl enable-linger pvalarezo
```

---

## 7. Servicios externos

| Servicio | URL/Acceso |
|----------|-----------|
| Meta Developers | https://developers.facebook.com/ |
| DeepSeek API | https://platform.deepseek.com/ |
| Telegram BotFather | https://t.me/BotFather |
| MinIO Console | http://localhost:9001 (minioadmin / minioadmin) |

---

## 8. Troubleshooting

```bash
# ¿Por qué no responde la API?
systemctl --user status lucho-api
journalctl --user -u lucho-api -n 20

# ¿El túnel está caído?
systemctl --user status lucho-tunnel
curl https://lucho-dev.apx5.com/

# ¿El bot no contesta en Telegram?
systemctl --user status lucho-bot
journalctl --user -u lucho-bot -n 20

# ¿La DB no conecta?
docker compose -f docker-compose.dev.yml ps
psql -h localhost -p 5434 -U lucho -d lucho

# Puerto ocupado
ss -tlnp | grep 8000
```
