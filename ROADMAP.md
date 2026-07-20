# ROADMAP.md — Lucho

Plan general del proyecto, fases, hitos y funcionalidades por ola.

---

## Fase 0 — Validación ✅ COMPLETADA
- Encuestas de validación de mercado
- Confirmación de interés y preferencia por WhatsApp como canal

---

## Fase 1 — MVP Técnico ✅ COMPLETADA — v2.10.0

**Versión actual:** v2.10.0 | **Tools:** 22 | **Funcionalidades:** 22/22
**Skills Ecuador:** 7 skills en 4 dominios | **Tests:** 307/307 (100%)
**Canales:** Telegram (webhook) + WhatsApp Cloud API (webhook)
**Tablas:** 22 PostgreSQL + pgvector
**Entregables Fase 1:** ✅ 100% completado

---

## Fase 2 — Beta Cerrada 🔨 EN PROGRESO

**Usuarios:** 50-100 reales
**Canales:** Telegram + WhatsApp

### ✅ Completado
- WhatsApp Cloud API integración completa
- WhatsApp: reacción + typing indicator + debounce 3s
- WhatsApp Templates: 4 plantillas creadas en Meta (en revisión)
- Telegram webhook unificado
- Sistema de suscripción: planes, trial 7 días, control acceso
- Onboarding guiado: bienvenida + nombre preferido
- Seguridad: middleware check_access
- Proyectos y Tareas (save/list/complete)
- Contactos (save/list)
- Envío de fotos al usuario (send_photo)
- Skills Ecuador (7 skills)
- Flujo post-pago: cédula → email → nombre → políticas
- Módulo de Vehículos independiente (vehicles + vehicle_maintenances)
- Scheduler conectado a WhatsApp templates
- Límite vehículos parametrizable por plan

### 📋 Pendientes Fase 2
- [ ] **Módulo de Finanzas Personales** — tracking de ingresos/gastos, presupuestos, categorías
- [ ] Métricas: % extracción correcta, retención D7/D30, intención de pago
- [ ] Funcionalidades Ola 2:
  - Fechas especiales (cumpleaños, aniversarios)
  - Vacunas (hijos, mascotas)
  - Suscripciones y servicios olvidados
  - Control de gastos personales (parte del módulo finanzas)

---

## Fase 3 — Lanzamiento con Monetización 📋 PLANEADA

- [ ] Integración de pago (Kushki/PayPhone)
- [ ] Webhook de pago (reactivación automática)
- [ ] Facturación SRI de la suscripción (AuraFac)
- [ ] Funcionalidades Ola 3 (fiscal/financiero)
- [ ] Familia y cuidado (medicamentos, modo cuidado, remesas)

---

## Fase 4 — Cruce a SMB 📋 FUTURO

- [ ] Trámites y servicios
- [ ] RUC empresarial, patente, bomberos, IESS
- [ ] Base GRISBI/PowerFin (30+ empresas)

---

## Fase 5 — Expansión Regional y Premium 📋 FUTURO

- [ ] Recordatorios compartidos (premium)
- [ ] Pagos asistidos
- [ ] Google Calendar
- [ ] Pico y placa parametrizable (Bogotá, Lima, CDMX)

---

## Leyenda

- ✅ Completado
- 🔨 En progreso
- 📋 Planeado
