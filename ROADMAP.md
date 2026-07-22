# ROADMAP.md — Lucho

Plan general del proyecto, fases, hitos y funcionalidades por ola.

---

## Fase 0 — Validación ✅ COMPLETADA
## Fase 1 — MVP Técnico ✅ COMPLETADA — v2.10.0

---

## Fase 2 — Beta Cerrada ✅ COMPLETADA — v2.13.0

**Versión actual:** v2.24.1 | **Tools:** 45 | **Tests:** 512/512 (100%)
**Canales:** Telegram (webhook) + WhatsApp Cloud API (webhook)
**Tablas:** 27 PostgreSQL + pgvector
**Docs:** 18 specs + funcionalidades

### ✅ Completado

#### Canales
- WhatsApp Cloud API: send/receive, media (fotos, docs, audio), webhook
- WhatsApp: typing indicator, debounce 3s
- Telegram: webhook unificado, sin restricciones de formato
- WhatsApp Templates: 4/5 creados (3 español, 1 inglés)

#### Sistema
- Onboarding guiado: bienvenida → nombre → trial 7 días
- Post-pago: cédula → email → nombre → políticas
- Suscripción: 3 planes (Básico $4.99, Premium $9.99, Familia $14.99), trial 7d, control de acceso, expiry automático
- Pagos: PayPhone (app+web), DeUna QR (Pichincha), transferencia bancaria
- Ciclo de vida automático: pre-aviso 3d antes, expiry + notificación, renovación
- Zona horaria Ecuador (cero conversiones TZ)
- System prompt reforzado anti-alucinaciones
- Skills Ecuador: 7 skills en 4 dominios
- Cloudflare Tunnel: lucho-dev.apx5.com

#### Módulos (9)
| Módulo | Tools | Estado |
|--------|-------|--------|
| 🚗 Vehículos | 5 | save, list, maintenance, check_info |
| 💰 Finanzas | 5 | add/list/get_balance/set/check_budget |
| 📄 Documentos | 1 + send_photo | Tabla independiente (v2.13.0) |
| 📅 Recordatorios | 1 + update_last | Ad-hoc + CRON diario |
| 📝 Listas | 1 | save_list |
| 📓 Notas y Apuntes | 1 | save_note + pgvector |
| 📋 Proyectos y Tareas | 3 | save/list/complete |
| 🔍 Búsqueda | 3 | semántica + determinista + web |
| 👤 Contactos | 2 | save/list |

#### Infraestructura
- APScheduler: CRON 8AM + jobs ad-hoc (DateTrigger)
- pgvector: semantic search en notes, list_items
- Redis: memoria de sesión
- MinIO: almacenamiento de archivos
- PostgreSQL 23 tablas + ENUMs

### 📋 Pendientes Fase 2
- [ ] Métricas: % extracción correcta, retención D7/D30, intención de pago
- [ ] Templates Meta: `event_reminder` (es), `project_reminder` (es), `budget_alert`

### Fase 2.5 — Monetización ✅ COMPLETADA (v2.15 → v2.21)
- 3 planes con precios reales + seed
- PayPhone + DeUna QR + transferencia
- Ciclo de vida automático (expiry + pre-aviso 3d)
- Billing info (personal/empresa/tercero)
- Key49 facturación electrónica SRI

---

## Fase 3 — Expansión 📋 PLANEADA

- [ ] APIs Ecuador: clima, noticias, CNE
- [ ] Módulos: temporizador, CRM ligero
- [ ] DeUna: gestionar credenciales reales de comercio
- [ ] Módulos nuevos priorizados: temporizador, clientes (CRM ligero)
- [ ] APIs Ecuador: clima, noticias, CNE

---

## Fase 4 — Expansión de Funcionalidades 📋 FUTURO

- [ ] Módulos: turnos, comidas, calificaciones
- [ ] Familia y cuidado (medicamentos, modo cuidado, remesas)
- [ ] APIs complejas: IESS, SRI, transporte público
- [ ] Google Calendar

---

## Fase 5 — SMB y Expansión Regional 📋 FUTURO

- [ ] Trámites y servicios empresariales
- [ ] RUC, patente, bomberos
- [ ] Base GRISBI/PowerFin (30+ empresas)
- [ ] Pico y placa parametrizable (Bogotá, Lima, CDMX)
- [ ] Recordatorios compartidos (premium)

---

## Ideas Exploradas

Ver [`docs/ideas_nuevos_modulos.md`](docs/ideas_nuevos_modulos.md) — brainstorming de nuevos módulos por perfil de usuario con 11 APIs externas propuestas.

---

## Leyenda
- ✅ Completado
- 🔨 En progreso
- 📋 Planeado
