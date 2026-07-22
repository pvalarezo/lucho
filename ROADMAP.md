# ROADMAP.md — Lucho

Plan general del proyecto, fases, hitos y funcionalidades por ola.

---

## Fase 0 — Validación ✅ COMPLETADA
## Fase 1 — MVP Técnico ✅ COMPLETADA — v2.10.0

---

## Fase 2 — Beta Cerrada ✅ COMPLETADA — v2.13.0

**Versión actual:** v2.14.0 | **Tools:** 38 | **Tests:** 444/444 (100%)
**Canales:** Telegram (webhook) + WhatsApp Cloud API (webhook)
**Tablas:** 23 PostgreSQL + pgvector
**Docs:** 14 especificaciones de módulos + funcionalidades

### ✅ Completado

#### Canales
- WhatsApp Cloud API: send/receive, media (fotos, docs, audio), webhook
- WhatsApp: typing indicator, debounce 3s
- Telegram: webhook unificado, sin restricciones de formato
- WhatsApp Templates: 4/5 creados (3 español, 1 inglés)

#### Sistema
- Onboarding guiado: bienvenida → nombre → trial 7 días
- Post-pago: cédula → email → nombre → políticas
- Suscripción: planes, trial, control de acceso, middleware
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
- [ ] Tools pendientes: `list_my_documents`, `list_items`, `complete_item`, `list_my_notes`

---

## Fase 3 — Lanzamiento con Monetización 📋 PLANEADA

- [ ] Integración de pago (Kushki/PayPhone)
- [ ] Webhook de pago (reactivación automática)
- [ ] Facturación SRI de la suscripción (AuraFac)
- [ ] Métricas y analytics
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
