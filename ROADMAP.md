# ROADMAP.md — Lucho

Plan general del proyecto, fases, hitos y funcionalidades por ola.

---

## Fase 0 — Validación ✅ COMPLETADA
- Encuestas de validación de mercado
- Confirmación de interés y preferencia por WhatsApp como canal

---

## Fase 1 — MVP Técnico ✅ COMPLETADA — 2026-07-12

**Versión:** v2.9.3 | **Tools:** 19 | **Funcionalidades:** 19/19 completadas
**Skills Ecuador:** 7 skills en 4 dominios | **Tests:** 272/275 (98%)
**Canales:** Telegram (webhook) + WhatsApp Cloud API (webhook) — arquitectura unificada
**Entregables Fase 1:** ✅ 100% completado

### Pendientes para Fase 2:

---

## Fase 2 — Beta Cerrada 📋 PLANEADA

**Usuarios:** 50-100 reales
**Canales:** Telegram + WhatsApp

- [x] WhatsApp Cloud API integración completa ✅ v2.8.0
- [x] WhatsApp: reacción ⏳ + typing indicator + debounce 3s ✅ v2.9.3
- [x] WhatsApp Templates documentados (4 plantillas) ✅ v2.9.1
- [x] Telegram webhook unificado (adios polling) ✅ v2.9.2
- [x] Sistema de suscripción: planes, trial 7 días, control acceso ✅ v2.9.3
- [x] Onboarding guiado: bienvenida + nombre preferido ✅ v2.9.3
- [x] Seguridad: middleware check_access, usuarios inactivos rechazados ✅ v2.9.3
- [x] Proyectos y Tareas ✅ v2.2.0
- [x] Contactos ✅ v2.2.0
- [x] Envío de fotos al usuario ✅ v2.3.0
- [x] Skills Ecuador (7 skills) ✅ v2.4.0
- [x] Tests actualizados ✅ v2.5.0
- [x] Flujo de archivos refinado ✅ v2.6.0
- [x] OCR/Visión migrado a DeepSeek ✅ v2.9.0
- [ ] Crear templates en Meta Business Manager (documentados, falta crearlos)
- [ ] Conectar templates en scheduler (send_template_message)
- [ ] Flujo post-pago: datos adicionales + activación suscripción
- [ ] Métricas: % extracción correcta, retención D7/D30, intención de pago
- [ ] Funcionalidades Ola 2:
  - Fechas especiales (cumpleaños, aniversarios)
  - Vacunas (hijos, mascotas)
  - Suscripciones y servicios olvidados
  - Control de gastos personales (tracking + ingresos)

---

## Fase 3 — Lanzamiento con Monetización 📋 PLANEADA

- [ ] Integración de pago (Kushki/PayPhone)
- [ ] Facturación SRI de la suscripción (AuraFac)
- [x] Migración/expansión a WhatsApp Business API ✅ v2.8.0
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
- ❌ Cancelado
