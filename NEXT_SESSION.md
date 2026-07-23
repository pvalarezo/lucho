# NEXT_SESSION.md — Lucho

---

## Sesión finalizada — 2026-07-23 — Fix recordatorios duplicados + Estrategia Tests v2.24.11

**v2.24.10 — Bugfix: recordatorios ad-hoc un solo mensaje.**
**v2.24.11 — Docs: pi_operations.md actualizado con estrategia de tests segura para producción.**

### Entregables de la sesión

| Qué | Archivo | Detalle |
|-----|---------|--------|
| Fix | `app/services/scheduler.py` | `send_whatsapp_template=False` en ad-hoc, evita duplicado. |
| Docs | `docs/pi_operations.md` | Estrategia de Tests: unit.py en PROD, integración solo en DEV. Backup OBLIGATORIO con verificación. |

### Cambios en pi_operations.md
- **Nueva sección**: "Estrategia de Tests" — explica que `pytest` NUNCA se usa en producción
- **Paso 4**: Backup OBLIGATORIO (antes que cualquier cambio) con verificación de tamaño
- **Paso 5**: `python tests/unit.py` (reemplaza a `pytest tests/ -q`)
- **Sección 3**: Procedimiento rápido restringido solo a docs/strings
- **Sección 5**: Comandos de diagnóstico con test unitario + nota de integración solo dev
- **Sección 8**: Notas reforzadas: NUNCA `pytest` en producción

---

## Sesión anterior — 2026-07-23 — Daily Digest opt-in v2.24.9

**v2.24.9 — Opt-in implementado. 46 tools, 612 tests (575 unit + 37 integration).**

### Entregables de la sesión

| Qué | Archivo | Detalle |
|-----|---------|--------|
| Especificación | `docs/modules/daily_digest_especificacion.md` | 11 secciones, spec completa |
| Columna BD | `user_profiles.daily_digest_enabled` | BOOLEAN DEFAULT FALSE |
| Migración | `43f1a001ba39` | Alembic migration |
| Tool | `set_daily_digest` | Tool #46 — handler + schema |
| Helper | `get_or_create_profile()` | En `app/services/user.py` |
| Filtro opt-in | `run_daily_digest()` | JOIN UserProfile, solo enabled=TRUE |
| Onboarding | WhatsApp + Telegram | Pregunta "¿Querés resumen cada mañana?" en step 2 |
| Tests | 6 tests nuevos | defaults, activate, deactivate, query filter, migration, handler |

### Métricas finales v2.24.9

| Métrica | v2.24.8 | v2.24.9 |
|---------|:-------:|:-------:|
| Tools | 45 | **46** |
| Tests unitarios | 567 | **575** |
| Tests integración | 31 | **37** |
| **Total tests** | 598 | **612** |

---

## Sesión anterior — 2026-07-23 — Suite de Integración v2.24.8

**v2.24.8 — 31 tests de integración contra PostgreSQL real. 598 tests totales.**

### Entregables de la sesión

| Qué | Archivo | Detalle |
|-----|---------|--------|
| TZ Docker local | `docker-compose.dev.yml` | Agregado `TZ` + `PGTZ` America/Guayaquil |
| TZ deploy VPS | `docs/deploy_vps_debian13.md` | `timedatectl` + `ALTER DATABASE SET timezone` |
| Pi ops | `docs/pi_operations.md` | Procedimiento completo de actualización para Pi (9 pasos) |
| Fixtures async | `tests/conftest.py` | `db_session`, `test_user`, `test_user_whatsapp` con rollback |
| Tests integración | `tests/test_integration.py` | 31 tests contra `lucho_test` real (3 conectividad, 4 user CRUD, 3 multi-tenant, 13 persistencia, 3 access check, 1 idempotency, 4 varios) |
| Pytest config | `pytest.ini` | `asyncio_mode=auto` |

### Métricas finales v2.24.8

| Métrica | v2.24.7 | v2.24.8 |
|---------|:-------:|:-------:|
| Tests unitarios | 567 | 567 |
| Tests integración | 0 | **31** |
| **Total tests** | 567 | **598** |
| DB de test | — | `lucho_test` (19 migrations) |

---

## Próxima sesión — Prioridades

### 🔴 Suite de integración (faltante)
- [ ] Mockear APIs externas (WhatsApp, Telegram, PayPhone, DeUna, LLMs)
- [ ] HTTP integration: httpx + ASGI transport contra endpoints reales
- [ ] Webhook idempotency tests e2e

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

## Sesión anterior — 2026-07-23 — Estabilización técnica v2.24.7

**v2.24.7 — 6 bloques de estabilización completados. 567 tests, Ruff 0, zona horaria Ecuador.**

| Bloque | Commit | Qué |
|--------|--------|-----|
| P0 Onboarding | `72e20fd` | Fix replicado en Telegram, 10 pruebas de regresión |
| P0 Seguridad | `1e6d6f6` | HMAC en DeUna, endpoint interno restringido, 22 pruebas |
| P0 Runtime | `2d4be42` | `select`/`timedelta` imports, F821 a cero |
| P1 Ruff | `e19f549` | 137 → 0 errores, 36 archivos limpiados |
| P1 Zona horaria | `797d42a` | UTC eliminado, `now_ec()` Ecuador, migración Alembic, 23 pruebas |
| P2 Versión/Docs | `fd56a67` | Versión auto-detectada de Git, ROADMAP/PROGRESS sincronizados |

---

## Sesión anterior — 2026-07-22 — Despliegue VPS + Extendida

**v2.24.2 desplegado en VPS Debian 13 (147.93.2.206) — 4 vCPU, 8 GB RAM, 148 GB SSD**
**v2.24.1 — Revisión 9 módulos + Monetización + Landing + Acentos + Español ecuatoriano (20 tags: v2.14 → v2.24)**
