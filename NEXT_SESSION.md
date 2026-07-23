# NEXT_SESSION.md — Lucho

---

## Próxima sesión — Estabilización técnica desde v2.24.6

Se realizó una revisión integral del repositorio el 2026-07-23. Antes de continuar con nuevas funcionalidades, trabajar el plan detallado:

**[`docs/plan_estabilizacion_v2.24.6.md`](docs/plan_estabilizacion_v2.24.6.md)**

### Hallazgo al incorporar v2.24.6

- La corrección remota se incorporó correctamente en la rama local.
- WhatsApp ahora deja `onboarding_step=0` al completar y protege el flujo post-pago con `not user.onboarding_complete`.
- **Telegram conserva el defecto equivalente:** deja `onboarding_step=3` y entra al flujo post-pago sin comprobar `onboarding_complete`.
- El commit `v2.24.6` no añadió pruebas de regresión.
- Antes de los demás bloques P0, completar el arreglo en Telegram y probar ambos canales.

### Orden prioritario

1. **P0 Onboarding:** completar en Telegram el arreglo de v2.24.6 y añadir regresión para ambos canales.
2. **P0 Seguridad:** autenticar el webhook DeUna y restringir `/internal/test-reminder`.
3. **P0 Runtime:** corregir los `F821` de `app/agent/tools.py`, especialmente usos de `select()` sin importar.
4. **P1 Zona horaria:** eliminar inconsistencias con UTC y aplicar la política de hora local Ecuador.
5. **P1 Pruebas:** añadir pruebas reales de handlers, webhooks, multi-tenant y scheduler.
6. **P1 Calidad:** reducir los 137 errores de Ruff a cero.
7. **P2 Consistencia:** sincronizar versión de API y documentación con Git.

### Línea base verificada

- Base funcional remota: `v2.24.6`, con corrección del choque entre onboarding y post-pago en WhatsApp.
- Compilación previa: correcta.
- Suite declarada: 512/512, con cobertura insuficiente de ejecución real.
- Ruff: 137 errores en la revisión inicial.
- Regla de la sesión: no añadir módulos nuevos hasta cerrar P0 y P1.

---

## Sesión finalizada — 2026-07-22 — Despliegue VPS

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
