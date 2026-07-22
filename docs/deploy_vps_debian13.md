# Lucho — Guía de Despliegue en VPS Linux (Debian 13)

> **Sin Docker** · Debian 13 · **Todo como root** · Mismo VPS: landing + API
> **Dominio**: `holalucho.com` · **API**: `api.holalucho.com`
> **🤖 Pi-ready**: Ejecutable secuencialmente. Cero interacciones manuales.
> **⏱️ Tiempo**: 20-25 minutos.

---

## 0. Pre-vuelo para Pi 🤖

Pedile a Patricio que cree `/root/deploy_vars.env` en el VPS:

```bash
# ── Datos que Pi necesita antes de desplegar ──

# Dominio
DOMAIN=holalucho.com
API_DOMAIN=api.holalucho.com

# PostgreSQL
DB_PASSWORD=cambiar_por_password_seguro_32_chars

# MinIO
MINIO_PASSWORD=cambiar_por_password_seguro_32_chars

# Telegram Bot (de @BotFather)
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghikl

# WhatsApp Cloud API (de Meta Business)
WHATSAPP_PHONE_NUMBER_ID=123456789
WHATSAPP_ACCESS_TOKEN=EAAx...
WHATSAPP_VERIFY_TOKEN=lucho_verify_token_32_chars

# Anthropic (Claude API)
ANTHROPIC_API_KEY=sk-ant-...

# OpenAI (Whisper + Embeddings)
OPENAI_API_KEY=sk-...

# PayPhone (cuenta comercio Ecuador)
PAYPHONE_CLIENT_ID=...
PAYPHONE_CLIENT_SECRET=...
PAYPHONE_STORE_ID=...
PAYPHONE_WEBHOOK_SECRET=...

# DeUna (Pichincha)
DEUNA_API_KEY=...
DEUNA_MERCHANT_ID=...

# Key49 (facturación SRI)
KEY49_API_KEY=k49_...
```

> 🤖 **Pi**: Lo primero que hacés al entrar al VPS es `source /root/deploy_vars.env`. Luego ejecutás las secciones en orden.

---

## 1. Requisitos del VPS

| Recurso | Mínimo | Recomendado |
|---------|:---:|:---:|
| CPU | 2 vCPU | 4 vCPU |
| RAM | 4 GB | 8 GB |
| Disco | 20 GB SSD | 40 GB SSD |
| SO | Debian 13 (Trixie) | |
| IP | Pública estática | |

---

## 2. Preparación del Sistema

```bash
# Actualizar paquetes
apt update && apt upgrade -y
apt install -y curl wget git build-essential nginx certbot python3-certbot-nginx ufw

# Firewall
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# Directorio de trabajo
mkdir -p /root/lucho

echo "✅ Sistema preparado"
```

---

## 3. Instalar Dependencias

### 3.1 Python 3.12+

```bash
apt install -y python3 python3-pip python3-venv python3-dev
```

### 3.2 PostgreSQL 17 + pgvector

```bash
apt install -y postgresql postgresql-contrib postgresql-server-dev-17 git

# pgvector
cd /tmp
git clone --branch v0.7.4 https://github.com/pgvector/pgvector.git
cd pgvector
make
make install

# Base de datos
su - postgres -c "psql -c \"CREATE USER lucho WITH PASSWORD '${DB_PASSWORD}';\""
su - postgres -c "psql -c \"CREATE DATABASE lucho OWNER lucho;\""
su - postgres -c "psql -d lucho -c \"CREATE EXTENSION IF NOT EXISTS vector;\""
su - postgres -c "psql -d lucho -c \"CREATE EXTENSION IF NOT EXISTS \\\"uuid-ossp\\\";\""

echo "✅ PostgreSQL 17 + pgvector"
```

### 3.3 Redis

```bash
apt install -y redis-server
systemctl enable --now redis-server
```

### 3.4 MinIO

```bash
wget -q https://dl.min.io/server/minio/release/linux-amd64/minio -O /usr/local/bin/minio
chmod +x /usr/local/bin/minio

mkdir -p /data/minio

tee /etc/default/minio <<EOF
MINIO_ROOT_USER=lucho_admin
MINIO_ROOT_PASSWORD=${MINIO_PASSWORD}
MINIO_VOLUMES="/data/minio"
MINIO_OPTS="--console-address :9001"
EOF

tee /etc/systemd/system/minio.service <<'SVC_EOF'
[Unit]
Description=MinIO
After=network.target

[Service]
User=root
Group=root
EnvironmentFile=/etc/default/minio
ExecStart=/usr/local/bin/minio server $MINIO_VOLUMES $MINIO_OPTS
Restart=always

[Install]
WantedBy=multi-user.target
SVC_EOF

systemctl daemon-reload
systemctl enable --now minio

# MinIO client + bucket
wget -q https://dl.min.io/client/mc/release/linux-amd64/mc -O /usr/local/bin/mc
chmod +x /usr/local/bin/mc
mc alias set local http://localhost:9000 lucho_admin "${MINIO_PASSWORD}"
mc mb local/lucho
mc anonymous set download local/lucho

echo "✅ MinIO — consola en http://$(hostname -I | awk '{print $1}'):9001"
```

---

## 4. Clonar y Configurar Lucho

### 4.1 Clonar

```bash
cd /root/lucho
git clone https://github.com/AURACORE-SOLUCIONES/lucho.git app
cd app
```

### 4.2 Entorno virtual

```bash
python3 -m venv venv
source venv/bin/activate
pip install -U pip wheel
pip install -r requirements.txt
```

### 4.3 Variables de entorno

```bash
cat > /root/lucho/app/.env <<EOF
# ── Generado por Pi ──

DATABASE_URL=postgresql+asyncpg://lucho:${DB_PASSWORD}@localhost:5432/lucho
REDIS_URL=redis://localhost:6379/0

MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=lucho_admin
MINIO_SECRET_KEY=${MINIO_PASSWORD}
MINIO_BUCKET=lucho

TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}

WHATSAPP_PHONE_NUMBER_ID=${WHATSAPP_PHONE_NUMBER_ID}
WHATSAPP_ACCESS_TOKEN=${WHATSAPP_ACCESS_TOKEN}
WHATSAPP_VERIFY_TOKEN=${WHATSAPP_VERIFY_TOKEN}
WHATSAPP_API_VERSION=v22.0

LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
ANTHROPIC_HAIKU_MODEL=claude-3-5-haiku-latest
ANTHROPIC_SONNET_MODEL=claude-3-5-sonnet-latest
OPENAI_API_KEY=${OPENAI_API_KEY}
EMBEDDING_PROVIDER=openai
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

PAYPHONE_CLIENT_ID=${PAYPHONE_CLIENT_ID}
PAYPHONE_CLIENT_SECRET=${PAYPHONE_CLIENT_SECRET}
PAYPHONE_STORE_ID=${PAYPHONE_STORE_ID}
PAYPHONE_API_URL=https://api.payphone.app
PAYPHONE_WEBHOOK_SECRET=${PAYPHONE_WEBHOOK_SECRET}

DEUNA_API_KEY=${DEUNA_API_KEY}
DEUNA_MERCHANT_ID=${DEUNA_MERCHANT_ID}

KEY49_API_KEY=${KEY49_API_KEY}
KEY49_ESTABLISHMENT=001
KEY49_ISSUE_POINT=001

VEHICLE_INFO_API_URL=http://131.161.221.131:2356/v1/info/all/vehicle/
VEHICLE_INFO_API_TOKEN=

DEBUG=false
LOG_LEVEL=INFO
CONTEXTUAL_RESPONSES=true
IVA_RATE=15.0
EOF

chmod 600 /root/lucho/app/.env
echo "✅ .env generado"
```

### 4.4 Migrar base de datos

```bash
cd /root/lucho/app
source venv/bin/activate
python -m alembic upgrade head
python scripts/seed_subscription_plans.py
python scripts/seed_business_info.py

echo "✅ Base de datos migrada y sembrada"
```

---

## 5. Configurar Systemd

```bash
tee /etc/systemd/system/lucho-api.service <<EOF
[Unit]
Description=Lucho API
After=network.target postgresql.service redis-server.service

[Service]
User=root
Group=root
WorkingDirectory=/root/lucho/app
Environment=PATH=/root/lucho/app/venv/bin:/usr/local/bin:/usr/bin:/bin
EnvironmentFile=/root/lucho/app/.env
ExecStart=/root/lucho/app/venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 4
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now lucho-api
systemctl status lucho-api --no-pager

echo "✅ lucho-api corriendo"
```

---

## 6. Nginx + Landing + SSL

### 6.1 Arquitectura

```
                  ┌──────────────────────────────┐
                  │        VPS Debian 13          │
                  │                               │
Internet ────────▶│  Nginx :80/:443              │
                  │  ├─ holalucho.com → /var/www  │  Landing
                  │  └─ api.holalucho.com → :8000 │  API
                  │                               │
                  │  PostgreSQL :5432  Redis :6379│
                  │  MinIO :9000                  │
                  └──────────────────────────────┘
```

### 6.2 Landing page

```bash
mkdir -p /var/www/holalucho
cp -r /root/lucho/app/landing/* /var/www/holalucho/
echo "✅ Landing desplegada"
```

### 6.3 Nginx

```bash
tee /etc/nginx/sites-available/holalucho <<'NGX_EOF'
# ── Landing: holalucho.com ──
server {
    listen 80;
    server_name holalucho.com www.holalucho.com;
    root /var/www/holalucho;
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }

    location ~* \.(jpg|jpeg|png|gif|ico|css|js|svg|woff2)$ {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}

# ── API: api.holalucho.com ──
server {
    listen 80;
    server_name api.holalucho.com;

    location /webhooks/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 30s;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }

    client_max_body_size 20M;
}
NGX_EOF

ln -sf /etc/nginx/sites-available/holalucho /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo "✅ Nginx: holalucho.com + api.holalucho.com"
```

### 6.4 SSL (Let's Encrypt)

```bash
certbot --nginx -d holalucho.com -d www.holalucho.com -d api.holalucho.com \
  --non-interactive --agree-tos --email patriciovalarezo@gmail.com

certbot renew --dry-run
echo "✅ SSL configurado"
```

### 6.5 Webhooks

| Servicio | URL |
|----------|-----|
| Telegram | `https://api.holalucho.com/webhooks/telegram` |
| WhatsApp | `https://api.holalucho.com/webhooks/whatsapp` |
| PayPhone | `https://api.holalucho.com/webhooks/payphone` |
| DeUna | `https://api.holalucho.com/webhooks/deuna` |

---

## 7. Verificar Despliegue

```bash
#!/bin/bash
echo "🔍 Verificando Lucho..."
echo ""

for svc in postgresql redis-server minio nginx lucho-api; do
    if systemctl is-active --quiet $svc 2>/dev/null; then
        echo "  ✅ $svc"
    else
        echo "  ❌ $svc"
    fi
done

echo ""
echo "── API ──"
curl -s -o /dev/null -w "  HTTP %{http_code}\n" http://localhost:8000/health

echo "── Landing ──"
curl -s -o /dev/null -w "  HTTP %{http_code}\n" http://localhost:80

echo "── Nginx API ──"
curl -s -o /dev/null -w "  HTTP %{http_code}\n" -H "Host: api.holalucho.com" http://localhost:80/health

echo ""
echo "── Red ──"
PUBLIC_IP=$(curl -s ifconfig.me 2>/dev/null || echo "?")
echo "  IP: $PUBLIC_IP"
echo "  🌐 https://holalucho.com"
echo "  🔗 https://api.holalucho.com"

echo ""
df -h / | tail -1 | awk '{print "  Disco: " $3 " / " $2 " (" $5 ")"}'
echo ""
echo "✅ Verificación completa"
```

---

## 8. Comandos de Mantenimiento

```bash
# Ver logs
journalctl -u lucho-api --since "10 min ago"

# Reiniciar
systemctl restart lucho-api

# Actualizar código
cd /root/lucho/app
git pull
source venv/bin/activate
pip install -r requirements.txt
python -m alembic upgrade head
systemctl restart lucho-api

# Backup DB
su - postgres -c "pg_dump lucho" > /root/backup_lucho_$(date +%Y%m%d).sql

# Liberar espacio
journalctl --vacuum-time=7d
```

---

## 9. DNS

Antes de certbot, verificá que estos registros apunten a la IP del VPS:

| Tipo | Nombre | Valor |
|------|--------|-------|
| A | `holalucho.com` | IP del VPS |
| CNAME | `www.holalucho.com` | `holalucho.com` |
| A | `api.holalucho.com` | IP del VPS |

> 🤖 **Pi**: `dig holalucho.com +short` debe devolver la IP antes de ejecutar certbot.

---

## 10. Estructura de Archivos

```
/root/lucho/app/              ← Código fuente
├── venv/                     ← Python virtualenv
├── .env                      ← Variables de entorno
├── app/                      ← FastAPI
├── alembic/                  ← Migraciones
├── landing/                  ← Landing page (fuente)
└── scripts/                  ← Seeds

/var/www/holalucho/           ← Landing page (servida por Nginx)

/etc/systemd/system/
├── lucho-api.service
└── minio.service

/etc/nginx/sites-available/
└── holalucho
```

---

## 11. Troubleshooting

```bash
# API no inicia
journalctl -u lucho-api -n 50 --no-pager
systemctl status postgresql

# Probar DB
cd /root/lucho/app && source venv/bin/activate
python -c "from app.database import async_session; print('OK')"

# Webhooks no llegan
nginx -t
tail -f /var/log/nginx/access.log
ufw status

# MinIO
systemctl status minio
curl -s http://localhost:9000
```

---

## 12. Checklist de Seguridad

- [ ] `.env` con `chmod 600`
- [ ] PostgreSQL solo en localhost
- [ ] UFW: solo 22, 80, 443
- [ ] SSL con renovación automática
- [ ] SSH solo con key, no contraseña
