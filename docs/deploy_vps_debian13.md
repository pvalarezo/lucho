# Lucho — Guía de Despliegue en VPS Linux (Debian 13)

> **Sin Docker** · Debian 13 (Trixie) · Mismo VPS: landing page + API
> **Dominio**: `holalucho.com` · **API**: `api.holalucho.com`
> **🤖 Pi-ready**: Todas las secciones son ejecutables secuencialmente por un agente Pi.
> **⏱️ Tiempo estimado**: 25-35 minutos con Pi.

---

## 0. Pre-vuelo para Pi 🤖

Antes de empezar, Pi necesita que le proporciones estos datos. Creá un archivo
`/home/lucho/deploy_vars.env` en el VPS con este contenido:

```bash
# ── Pedile a Patricio estos datos antes de desplegar ──

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

> 🤖 **Pi**: leé este archivo con `source deploy_vars.env` antes de ejecutar cualquier comando.
> Las variables se usarán en los templates de configuración más abajo.

---

## 1. Requisitos del VPS

| Recurso | Mínimo | Recomendado |
|---------|:---:|:---:|
| CPU | 2 vCPU | 4 vCPU |
| RAM | 4 GB | 8 GB |
| Disco | 20 GB SSD | 40 GB SSD |
| SO | Debian 13 (Trixie) | Debian 13 |
| IP | Pública estática | Pública estática |

---

## 2. Preparación del Sistema

### 2.1 Actualizar paquetes

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl wget git build-essential nginx certbot python3-certbot-nginx ufw
```

### 2.2 Configurar firewall

```bash
sudo ufw allow 22/tcp      # SSH
sudo ufw allow 80/tcp      # HTTP
sudo ufw allow 443/tcp     # HTTPS
sudo ufw enable
```

### 2.3 Crear usuario de aplicación

```bash
sudo useradd -m -s /bin/bash lucho
sudo usermod -aG sudo lucho
sudo su - lucho
```

---

## 3. Instalar Dependencias

### 3.1 Python 3.12+

```bash
sudo apt install -y python3 python3-pip python3-venv python3-dev
```

### 3.2 PostgreSQL 17 + pgvector

```bash
# Instalar PostgreSQL
sudo apt install -y postgresql postgresql-contrib

# Instalar pgvector desde fuentes
sudo apt install -y postgresql-server-dev-17 git
cd /tmp
git clone --branch v0.7.4 https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install

# Crear base de datos y usuario (NO INTERACTIVO)
sudo -u postgres psql <<EOF
CREATE USER lucho WITH PASSWORD '${DB_PASSWORD}';
CREATE DATABASE lucho OWNER lucho;
\c lucho
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
EOF

echo "✅ PostgreSQL 17 + pgvector listo"
```

### 3.3 Redis

```bash
sudo apt install -y redis-server
sudo systemctl enable --now redis-server
```

### 3.4 MinIO (Object Storage)

```bash
# Descargar binario
sudo wget -q https://dl.min.io/server/minio/release/linux-amd64/minio -O /usr/local/bin/minio
sudo chmod +x /usr/local/bin/minio

# Crear directorio de datos
sudo mkdir -p /data/minio
sudo chown lucho:lucho /data/minio

# Crear archivo de entorno (NO INTERACTIVO)
sudo tee /etc/default/minio <<EOF
MINIO_ROOT_USER=lucho_admin
MINIO_ROOT_PASSWORD=${MINIO_PASSWORD}
MINIO_VOLUMES="/data/minio"
MINIO_OPTS="--console-address :9001"
EOF

# Crear systemd service para MinIO
sudo tee /etc/systemd/system/minio.service <<'SVC_EOF'
[Unit]
Description=MinIO
After=network.target

[Service]
User=lucho
Group=lucho
EnvironmentFile=/etc/default/minio
ExecStart=/usr/local/bin/minio server $MINIO_VOLUMES $MINIO_OPTS
Restart=always

[Install]
WantedBy=multi-user.target
SVC_EOF

sudo systemctl daemon-reload
sudo systemctl enable --now minio

# Instalar minio-client y crear bucket (NO INTERACTIVO)
sudo wget -q https://dl.min.io/client/mc/release/linux-amd64/mc -O /usr/local/bin/mc
sudo chmod +x /usr/local/bin/mc
mc alias set local http://localhost:9000 lucho_admin "${MINIO_PASSWORD}"
mc mb local/lucho
mc anonymous set download local/lucho

echo "✅ MinIO listo — consola en http://$(hostname -I | awk '{print $1}'):9001"
```

---

## 4. Clonar y Configurar Lucho

### 4.1 Clonar repositorio

```bash
cd /home/lucho
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

### 4.3 Configurar variables de entorno (NO INTERACTIVO)

```bash
# Generar .env desde template
cat > /home/lucho/app/.env <<EOF
# ── Generado por Pi el $(date) ──

# Base de Datos
DATABASE_URL=postgresql+asyncpg://lucho:${DB_PASSWORD}@localhost:5432/lucho

# Redis
REDIS_URL=redis://localhost:6379/0

# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=lucho_admin
MINIO_SECRET_KEY=${MINIO_PASSWORD}
MINIO_BUCKET=lucho

# Telegram
TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}

# WhatsApp
WHATSAPP_PHONE_NUMBER_ID=${WHATSAPP_PHONE_NUMBER_ID}
WHATSAPP_ACCESS_TOKEN=${WHATSAPP_ACCESS_TOKEN}
WHATSAPP_VERIFY_TOKEN=${WHATSAPP_VERIFY_TOKEN}
WHATSAPP_API_VERSION=v22.0

# LLM
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
ANTHROPIC_HAIKU_MODEL=claude-3-5-haiku-latest
ANTHROPIC_SONNET_MODEL=claude-3-5-sonnet-latest
OPENAI_API_KEY=${OPENAI_API_KEY}
EMBEDDING_PROVIDER=openai
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# PayPhone
PAYPHONE_CLIENT_ID=${PAYPHONE_CLIENT_ID}
PAYPHONE_CLIENT_SECRET=${PAYPHONE_CLIENT_SECRET}
PAYPHONE_STORE_ID=${PAYPHONE_STORE_ID}
PAYPHONE_API_URL=https://api.payphone.app
PAYPHONE_WEBHOOK_SECRET=${PAYPHONE_WEBHOOK_SECRET}

# DeUna
DEUNA_API_KEY=${DEUNA_API_KEY}
DEUNA_MERCHANT_ID=${DEUNA_MERCHANT_ID}

# Key49
KEY49_API_KEY=${KEY49_API_KEY}
KEY49_ESTABLISHMENT=001
KEY49_ISSUE_POINT=001

# Vehículos
VEHICLE_INFO_API_URL=http://131.161.221.131:2356/v1/info/all/vehicle/
VEHICLE_INFO_API_TOKEN=

# App
DEBUG=false
LOG_LEVEL=INFO
CONTEXTUAL_RESPONSES=true
IVA_RATE=15.0
EOF

chmod 600 /home/lucho/app/.env
echo "✅ .env generado con permisos seguros"
```

### 4.4 Migrar base de datos

```bash
source venv/bin/activate
python -m alembic upgrade head
python scripts/seed_subscription_plans.py
python scripts/seed_business_info.py
```

---

## 5. Configurar Systemd

### 5.1 API principal

```bash
sudo tee /etc/systemd/system/lucho-api.service <<EOF
[Unit]
Description=Lucho API
After=network.target postgresql.service redis-server.service

[Service]
User=lucho
Group=lucho
WorkingDirectory=/home/lucho/app
Environment=PATH=/home/lucho/app/venv/bin:/usr/local/bin:/usr/bin:/bin
EnvironmentFile=/home/lucho/app/.env
ExecStart=/home/lucho/app/venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 4
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
```

### 5.2 Habilitar servicios

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now lucho-api
sudo systemctl status lucho-api
```

---

## 6. Configurar Nginx + Landing Page + SSL

### 6.1 Arquitectura

```
                  ┌─────────────────────────────────┐
                  │         VPS Debian 13            │
                  │                                  │
Internet ────────▶│  Nginx (puerto 80/443)          │
                  │  ├─ holalucho.com → /var/www/   │  ← Landing page
                  │  └─ api.holalucho.com → :8000   │  ← Lucho API
                  │                                  │
                  │  PostgreSQL :5432  Redis :6379  │
                  │  MinIO :9000                     │
                  └─────────────────────────────────┘
```

### 6.2 Crear landing page

```bash
sudo mkdir -p /var/www/holalucho
sudo chown -R lucho:lucho /var/www/holalucho

# Landing page simple (reemplazar con tu HTML real)
cat > /var/www/holalucho/index.html <<'LANDING'
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Lucho — Tu asistente personal</title>
    <style>
        body { font-family: -apple-system, sans-serif; display: flex; justify-content: center;
               align-items: center; min-height: 100vh; margin: 0; background: #0f172a; color: #e2e8f0; }
        main { text-align: center; padding: 2rem; }
        h1 { font-size: 3rem; color: #38bdf8; }
        p { font-size: 1.2rem; opacity: 0.8; }
    </style>
</head>
<body>
    <main>
        <h1>🚀 Lucho</h1>
        <p>Tu asistente personal de segundo cerebro por WhatsApp.</p>
        <p>Próximamente...</p>
    </main>
</body>
</html>
LANDING

echo "✅ Landing page creada en /var/www/holalucho"
```

### 6.3 Nginx multi-dominio (NO INTERACTIVO)

```bash
sudo tee /etc/nginx/sites-available/holalucho <<'NGX_EOF'
# ── Landing page: holalucho.com ──
server {
    listen 80;
    server_name holalucho.com www.holalucho.com;
    root /var/www/holalucho;
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }

    # Cache estáticos
    location ~* \.(jpg|jpeg|png|gif|ico|css|js|svg|woff2)$ {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}

# ── Lucho API: api.holalucho.com ──
server {
    listen 80;
    server_name api.holalucho.com;

    # Webhooks — necesitan IP real del cliente
    location /webhooks/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 30s;
    }

    # API + mensajería
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

sudo ln -sf /etc/nginx/sites-available/holalucho /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

echo "✅ Nginx configurado: holalucho.com + api.holalucho.com"
```

### 6.4 SSL con Let's Encrypt (todos los subdominios)

```bash
# Obtener certificados para todos los subdominios de una vez
sudo certbot --nginx -d holalucho.com -d www.holalucho.com -d api.holalucho.com --non-interactive --agree-tos --email patriciovalarezo@gmail.com

# Verificar renovación automática
sudo certbot renew --dry-run

echo "✅ SSL configurado para holalucho.com, www.holalucho.com, api.holalucho.com"
```

### 6.5 URLs de Webhooks (para configurar en cada plataforma)

| Servicio | Webhook URL |
|----------|-------------|
| Telegram | `https://api.holalucho.com/webhooks/telegram` |
| WhatsApp | `https://api.holalucho.com/webhooks/whatsapp` |
| PayPhone | `https://api.holalucho.com/webhooks/payphone` |
| DeUna | `https://api.holalucho.com/webhooks/deuna` |

---

## 7. Verificar Despliegue (script para Pi)

```bash
#!/bin/bash
# verify_deploy.sh — ejecutar después del despliegue para validar todo

echo "🔍 Verificando despliegue de Lucho..."
echo ""

# 1. Servicios del sistema
echo "── Servicios ──"
for svc in postgresql redis-server minio nginx lucho-api; do
    if systemctl is-active --quiet $svc 2>/dev/null; then
        echo "  ✅ $svc está corriendo"
    else
        echo "  ❌ $svc NO está corriendo"
    fi
done

# 2. API responde
echo ""
echo "── API ──"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null)
if [ "$HTTP_CODE" = "200" ]; then
    echo "  ✅ API responde (HTTP $HTTP_CODE)"
else
    echo "  ❌ API no responde (HTTP $HTTP_CODE)"
fi

# 3. PostgreSQL
echo ""
echo "── Base de Datos ──"
if sudo -u postgres psql -lqt 2>/dev/null | grep -q lucho; then
    echo "  ✅ Base de datos 'lucho' existe"
else
    echo "  ❌ Base de datos no encontrada"
fi

# 4. Redis
echo ""
echo "── Redis ──"
if redis-cli ping 2>/dev/null | grep -q PONG; then
    echo "  ✅ Redis responde"
else
    echo "  ❌ Redis no responde"
fi

# 5. MinIO
echo ""
echo "── MinIO ──"
MINIO_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:9000 2>/dev/null)
if [ "$MINIO_CODE" = "403" ] || [ "$MINIO_CODE" = "200" ]; then
    echo "  ✅ MinIO responde (HTTP $MINIO_CODE)"
else
    echo "  ❌ MinIO no responde"
fi

# 6. Nginx
echo ""
echo "── Nginx ──"
NGINX_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:80 2>/dev/null)
if [ -n "$NGINX_CODE" ]; then
    echo "  ✅ Nginx responde (HTTP $NGINX_CODE)"
else
    echo "  ⚠️  Nginx podría no estar configurado aún"
fi

# 6. Nginx — landing page
echo ""
echo "── Landing Page ──"
LANDING_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:80 2>/dev/null)
if [ "$LANDING_CODE" = "200" ]; then
    echo "  ✅ Landing page responde (HTTP $LANDING_CODE)"
else
    echo "  ⚠️  Landing page: HTTP $LANDING_CODE"
fi

# 7. Nginx — API
echo ""
echo "── Nginx API ──"
API_CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "Host: api.holalucho.com" http://localhost:80/health 2>/dev/null)
if [ "$API_CODE" = "200" ]; then
    echo "  ✅ API vía Nginx responde (HTTP $API_CODE)"
else
    echo "  ⚠️  API vía Nginx: HTTP $API_CODE"
fi

# 8. Puerto público
echo ""
echo "── Red ──"
PUBLIC_IP=$(curl -s ifconfig.me 2>/dev/null || echo "desconocida")
echo "  IP pública: $PUBLIC_IP"
echo "  Landing: https://holalucho.com"
echo "  API: https://api.holalucho.com"
echo "  Webhooks:"
echo "    Telegram:  https://api.holalucho.com/webhooks/telegram"
echo "    WhatsApp:  https://api.holalucho.com/webhooks/whatsapp"
echo "    PayPhone:  https://api.holalucho.com/webhooks/payphone"
echo "    DeUna:    https://api.holalucho.com/webhooks/deuna"

# 8. Espacio en disco
echo ""
echo "── Disco ──"
df -h / | tail -1 | awk '{print "  " $3 " usado de " $2 " (" $5 ")"}'

echo ""
echo "✅ Verificación completada."
```

---

## 8. Comandos de Mantenimiento

```bash
# Reiniciar API
sudo systemctl restart lucho-api

# Ver logs
sudo journalctl -u lucho-api --since "10 min ago"

# Actualizar código
cd /home/lucho/app
git pull
source venv/bin/activate
pip install -r requirements.txt
python -m alembic upgrade head
sudo systemctl restart lucho-api

# Backup de base de datos
pg_dump -U lucho lucho > /backups/lucho_$(date +%Y%m%d).sql

# Espacio en disco
df -h
sudo journalctl --vacuum-time=7d
```

---

## 9. Configurar DNS

Antes de ejecutar certbot, asegurate de que estos registros DNS apunten a la IP del VPS:

| Tipo | Nombre | Valor |
|------|--------|-------|
| A | `holalucho.com` | IP del VPS |
| CNAME | `www.holalucho.com` | `holalucho.com` |
| A | `api.holalucho.com` | IP del VPS |

> 🤖 **Pi**: verificá con `dig holalucho.com +short` que resuelva a la IP correcta antes de ejecutar certbot.

---

## 11. Estructura de Archivos en el VPS

```
/home/lucho/
├── app/                          # Código fuente
│   ├── venv/                     # Entorno virtual Python
│   ├── .env                      # Variables de entorno
│   ├── app/                      # Aplicación
│   ├── alembic/                  # Migraciones
│   ├── scripts/                  # Scripts de seed
│   └── tests/                    # Tests
│
/backups/                         # Backups de DB
│
/etc/
├── systemd/system/
│   ├── lucho-api.service         # API
│   └── minio.service             # MinIO
├── nginx/sites-available/
│   └── lucho                     # Reverse proxy
└── default/
    └── minio                     # MinIO env vars
```

---

## 12. Troubleshooting

### La API no inicia

```bash
# Ver logs detallados
sudo journalctl -u lucho-api -n 50 --no-pager

# Verificar que PostgreSQL corre
sudo systemctl status postgresql

# Probar conexión a DB manualmente
source /home/lucho/app/venv/bin/activate
python -c "from app.database import async_session; print('OK')"
```

### Webhooks no llegan

```bash
# Verificar Nginx
sudo nginx -t
sudo tail -f /var/log/nginx/access.log

# Verificar firewall
sudo ufw status

# Verificar que el dominio resuelve
dig TU_DOMINIO.com
```

### MinIO no accesible

```bash
# Consola MinIO: http://TU_IP:9001
sudo systemctl status minio
sudo journalctl -u minio -n 20
```

---

## 13. Checklist de Seguridad

- [ ] `.env` con permisos 600 (`chmod 600 .env`)
- [ ] PostgreSQL solo escucha en localhost (`listen_addresses = 'localhost'`)
- [ ] Redis con contraseña (`requirepass` en `/etc/redis/redis.conf`)
- [ ] MinIO con credenciales fuertes
- [ ] UFW activo con solo puertos 22, 80, 443
- [ ] SSL con Let's Encrypt (renovación automática)
- [ ] API keys rotadas periódicamente
- [ ] Logs con rotación (`journalctl --vacuum-time=30d`)
- [ ] Usuario `lucho` sin acceso SSH por contraseña (solo SSH key)
