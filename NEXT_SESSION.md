# NEXT_SESSION.md — Lucho

---

## Sesión finalizada — 2026-07-23 — Estabilización técnica v2.24.7

**v2.24.7 — 6 bloques de estabilización completados. 567 tests, Ruff 0, zona horaria Ecuador.**

### Entregables

| Bloque | Commit | Qué |
|--------|--------|-----|
| P0 Onboarding | `72e20fd` | Fix replicado en Telegram, 10 pruebas de regresión |
| P0 Seguridad | `1e6d6f6` | HMAC en DeUna, endpoint interno restringido, 22 pruebas |
| P0 Runtime | `2d4be42` | `select`/`timedelta` imports, F821 a cero |
| P1 Ruff | `e19f549` | 137 → 0 errores, 36 archivos limpiados |
| P1 Zona horaria | `797d42a` | UTC eliminado, `now_ec()` Ecuador, migración Alembic, 23 pruebas |
| P2 Versión/Docs | `fd56a67` | Versión auto-detectada de Git, ROADMAP/PROGRESS sincronizados |

### Métricas finales v2.24.7

| Métrica | Antes | Después |
|---------|:-----:|:-------:|
| Tests | 512 | **567** |
| Ruff | 137 | **0** |
| UTC traces | 18 archivos | **0** |
| Endpoints inseguros | 2 | **0** |
| F821 runtime errors | 11 | **0** |

---

## Próxima sesión — Prioridades

### 🔴 Suite de integración
- [ ] pytest + pytest-asyncio + fixtures PostgreSQL
- [ ] Probar handlers reales contra base de datos (no solo schemas)
- [ ] Aislamiento multi-tenant, idempotencia de webhooks, rollback
- [ ] Mockear APIs externas (WhatsApp, Telegram, PayPhone, DeUna, LLMs)

### 🟡 Templates Meta
- [ ] `event_reminder` (es) — 5 params
- [ ] `budget_alert` (es) — 5 params
- [ ] `project_reminder` (es) — esperar traducción

### 🟡 Operaciones
- [ ] Métricas: % extracción correcta, retención D7/D30
- [ ] Key49 API key real
- [ ] DeUna credenciales reales

### 🟢 Fase 3
- [ ] APIs Ecuador: clima, noticias, CNE
- [ ] Módulos: temporizador, CRM ligero

---

## Sesión anterior — 2026-07-22 — Despliegue VPS

**v2.24.2 desplegado en VPS Debian 13 (147.93.2.206) — 4 vCPU, 8 GB RAM, 148 GB SSD**

---

## Sesión anterior — 2026-07-22 (sesión extendida, ~18 horas)

**v2.24.1 — Revisión 9 módulos + Monetización + Landing + Acentos + Español ecuatoriano**

---

### Entregables de la sesión (20 tags: v2.14 → v2.24)

| Fase | Tags | Qué |
|------|------|-----|
| Revisión módulos | v2.14 | 9 módulos: +12 tools, +88 tests, spec vehículos |
| Planes | v2.15 | Básico ($4.99), Premium ($9.99), Familia ($14.99) |
| Pagos | v2.16–18 | PayPhone + DeUna QR + transferencia bancaria |
| Ciclo vida | v2.19–19.1 | Expiry + pre-aviso 3d + webhooks + docs |
| SRI | v2.20–21 | BillingInfo + Key49 facturación electrónica |
| Docs | v2.21.1–22.2 | ROADMAP/PROGRESS/NEXT + deploy + landing |
| Cotizaciones | v2.22.0 | 4 models, 4 tools, IVA dinámico |
| Landing | v2.23.0 | holalucho.com — Tailwind, 8 secciones, responsive |
| Español EC | v2.23.1 | System prompt + tools + landing corregidos |
| Acentos | v2.24.0 | Costeño, serrano, amazónico, neutral |
| Datos reales | v2.24.1 | RUC, Produbanco, WhatsApp |

### Métricas finales

| Métrica | v2.13.0 | v2.24.1 | Delta |
|---------|:---:|:---:|:---:|
| Tools | 26 | **45** | +19 |
| Tests | 348 | **512** | +164 |
| Tablas | 23 | **27** | +4 |
| Skills | 7 | **10** | +3 acentos |
| Specs | 14 | **18** | +4 |
| Planes | 0 | **3** | |
| Pasarelas | 0 | **3** | |
| Tags | 1 | **21** | +20 |

---

### Entregables del despliegue VPS

| Componente | Estado |
|------------|:---:|
| PostgreSQL 17 + pgvector + 27 tablas | ✅ |
| Redis | ✅ |
| MinIO (bucket lucho) | ✅ |
| API FastAPI (4 workers en systemd) | ✅ |
| Nginx + Let's Encrypt SSL (3 dominios) | ✅ |
| Landing holalucho.com | ✅ |
| WhatsApp Cloud API webhook | ✅ probado |
| Planes de suscripción seed | ✅ |

### URLs correctas de webhooks

| Servicio | URL |
|----------|-----|
| WhatsApp | `https://api.holalucho.com/whatsapp/webhook` |
| Telegram | `https://api.holalucho.com/telegram/webhook` |
| PayPhone | `https://api.holalucho.com/webhooks/payphone` |
| DeUna | `https://api.holalucho.com/webhooks/deuna` |

---

## Próxima sesión — Prioridades

### 🔴 Credenciales pendientes
- [ ] `ANTHROPIC_API_KEY` — Claude (actualmente usa OpenAI)
- [ ] `PAYPHONE_CLIENT_ID/SECRET/STORE_ID`
- [ ] `DEUNA_API_KEY/MERCHANT_ID`
- [ ] `KEY49_API_KEY` — facturación SRI

### 🔴 Templates Meta
- [ ] `event_reminder` (es) — 5 params
- [ ] `budget_alert` (es) — 5 params
- [ ] `project_reminder` (es) — esperar traducción

### 🟡 Operaciones
- [ ] Métricas: % extracción correcta, retención D7/D30
- [ ] Configurar Telegram webhook

### 🟢 Fase 3
- [ ] APIs Ecuador: clima, noticias, CNE
- [ ] Módulos: temporizador, CRM ligero
- [ ] Facturación recurrente automática
