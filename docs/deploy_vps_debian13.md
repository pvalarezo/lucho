# Lucho — Guía de Despliegue en VPS Linux (Debian 13)

> **Sin Docker** · Debian 13 (Trixie) · IP pública · PostgreSQL + Redis + MinIO + Nginx

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

# Crear base de datos y usuario
sudo -u postgres psql <<EOF
CREATE USER lucho WITH PASSWORD 'TU_PASSWORD_SEGURO';
CREATE DATABASE lucho OWNER lucho;
\c lucho
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
EOF
```

### 3.3 Redis

```bash
sudo apt install -y redis-server
sudo systemctl enable --now redis-server
```

### 3.4 MinIO (Object Storage)

```bash
# Descargar binario
wget https://dl.min.io/server/minio/release/linux-amd64/minio -O /usr/local/bin/minio
chmod +x /usr/local/bin/minio

# Crear directorio de datos
sudo mkdir -p /data/minio
sudo chown lucho:lucho /data/minio

# Crear archivo de entorno
cat > /etc/default/minio <<EOF
MINIO_ROOT_USER=lucho_admin
MINIO_ROOT_PASSWORD=TU_MINIO_PASSWORD_SEGURO
MINIO_VOLUMES="/data/minio"
MINIO_OPTS="--console-address :9001"
EOF

# Crear systemd service para MinIO
sudo tee /etc/systemd/system/minio.service <<EOF
[Unit]
Description=MinIO
After=network.target

[Service]
User=lucho
Group=lucho
EnvironmentFile=/etc/default/minio
ExecStart=/usr/local/bin/minio server \$MINIO_VOLUMES \$MINIO_OPTS
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now minio

# Crear bucket para Lucho
# (después de instalar minio-client)
wget https://dl.min.io/client/mc/release/linux-amd64/mc -O /usr/local/bin/mc
chmod +x /usr/local/bin/mc
mc alias set local http://localhost:9000 lucho_admin TU_MINIO_PASSWORD_SEGURO
mc mb local/lucho
mc anonymous set download local/lucho
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

### 4.3 Configurar variables de entorno

```bash
cp .env.example .env
nano .env
```

**Variables mínimas para producción:**

```bash
# ---- Base de Datos ----
DATABASE_URL=postgresql+asyncpg://lucho:TU_PASSWORD_SEGURO@localhost:5432/lucho

# ---- Redis ----
REDIS_URL=redis://localhost:6379/0

# ---- MinIO ----
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=lucho_admin
MINIO_SECRET_KEY=TU_MINIO_PASSWORD_SEGURO
MINIO_BUCKET=lucho

# ---- Telegram ----
TELEGRAM_BOT_TOKEN=TU_BOT_TOKEN

# ---- WhatsApp ----
WHATSAPP_PHONE_NUMBER_ID=TU_PHONE_NUMBER_ID
WHATSAPP_ACCESS_TOKEN=TU_ACCESS_TOKEN
WHATSAPP_VERIFY_TOKEN=TU_VERIFY_TOKEN

# ---- LLM ----
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=TU_API_KEY
OPENAI_API_KEY=TU_OPENAI_KEY

# ---- PayPhone ----
PAYPHONE_CLIENT_ID=TU_CLIENT_ID
PAYPHONE_CLIENT_SECRET=TU_CLIENT_SECRET
PAYPHONE_STORE_ID=TU_STORE_ID
PAYPHONE_WEBHOOK_SECRET=TU_WEBHOOK_SECRET

# ---- DeUna ----
DEUNA_API_KEY=TU_API_KEY
DEUNA_MERCHANT_ID=TU_MERCHANT_ID

# ---- Key49 ----
KEY49_API_KEY=TU_K49_API_KEY
KEY49_ESTABLISHMENT=001
KEY49_ISSUE_POINT=001

# ---- App ----
DEBUG=false
LOG_LEVEL=INFO
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

## 6. Configurar Nginx + SSL

### 6.1 Nginx reverse proxy

```bash
# Reemplazar TU_DOMINIO.com con tu dominio real
sudo tee /etc/nginx/sites-available/lucho <<EOF
server {
    listen 80;
    server_name TU_DOMINIO.com api.TU_DOMINIO.com;

    # Webhook endpoints (necesitan cliente real de las pasarelas)
    location /webhooks/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 30s;
    }

    # API y webhooks de mensajería
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 60s;
    }

    client_max_body_size 20M;
}

# Redirigir tráfico HTTP a HTTPS (después de certbot)
# server {
#     listen 80;
#     server_name TU_DOMINIO.com;
#     return 301 https://\$server_name\$request_uri;
# }
EOF

sudo ln -s /etc/nginx/sites-available/lucho /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

### 6.2 SSL con Let's Encrypt

```bash
# Obtener certificados
sudo certbot --nginx -d TU_DOMINIO.com -d api.TU_DOMINIO.com

# Renovación automática
sudo certbot renew --dry-run
```

---

## 7. Verificar Despliegue

```bash
# API
curl http://localhost:8000/health

# Servicios
sudo systemctl status lucho-api
sudo systemctl status postgresql
sudo systemctl status redis-server
sudo systemctl status minio
sudo systemctl status nginx

# Logs
sudo journalctl -u lucho-api -f
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

## 9. Estructura de Archivos en el VPS

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

## 10. Troubleshooting

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

## 11. Checklist de Seguridad

- [ ] `.env` con permisos 600 (`chmod 600 .env`)
- [ ] PostgreSQL solo escucha en localhost (`listen_addresses = 'localhost'`)
- [ ] Redis con contraseña (`requirepass` en `/etc/redis/redis.conf`)
- [ ] MinIO con credenciales fuertes
- [ ] UFW activo con solo puertos 22, 80, 443
- [ ] SSL con Let's Encrypt (renovación automática)
- [ ] API keys rotadas periódicamente
- [ ] Logs con rotación (`journalctl --vacuum-time=30d`)
- [ ] Usuario `lucho` sin acceso SSH por contraseña (solo SSH key)
