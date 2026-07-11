# ROADMAP.md — Lucho

Plan general del proyecto, fases, hitos y funcionalidades por ola.

---

## Fase 0 — Validación ✅ COMPLETADA
- Encuestas de validación de mercado
- Confirmación de interés y preferencia por WhatsApp como canal

---

## Fase 1 — MVP Técnico (Telegram primero) 🔨 EN PROGRESO

**Canal:** Telegram Bot API
**Objetivo:** Asistente funcional con núcleo transversal y 2 verticales

### Entregables pendientes:

#### Infraestructura y proyecto
- [ ] Estructura del proyecto FastAPI
- [ ] Docker Compose (PostgreSQL+pgvector, MinIO, Redis, RabbitMQ, Traefik)
- [ ] CI/CD básico

#### Base de datos
- [ ] Esquema: `users`, `messages`
- [ ] Esquema: `assets` (con JSONB + índice GIN)
- [ ] Esquema: `events`, `reminders`
- [ ] Esquema: `topics`, `notes` (con pgvector)
- [ ] Esquema: `lists`, `list_items`
- [ ] Vista: `searchable_content`

#### Bot de Telegram
- [ ] Webhook de recepción de mensajes (texto, audio, foto)
- [ ] Ack inmediato ("Recibido, dame un segundo")
- [ ] Confirmación editable

#### Pipeline de IA
- [ ] Integración Haiku 4.5 (routing de intención)
- [ ] Integración Sonnet 5 (extracción estructurada, generación)
- [ ] Integración Whisper (transcripción de audio)
- [ ] OCR/visión de facturas

#### Motor de Reglas (determinista)
- [ ] Regla: matriculación por último dígito de placa
- [ ] Regla: pico y placa semanal (calculado al vuelo)
- [ ] APScheduler: cron diario de evaluación
- [ ] Recordatorios con anticipación escalonada (15/7/3 días)

#### Núcleo Transversal
- [ ] Captura libre de texto
- [ ] Múltiples instrucciones por mensaje
- [ ] Recurrencias complejas
- [ ] Búsqueda conversacional (pgvector)
- [ ] Listas simples (compras, pendientes)
- [ ] Resumen diario/semanal (opt-in)

#### "Lucho piensa" (mínimo)
- [ ] Cálculos básicos sobre datos del usuario
- [ ] Explicaciones ancladas a norma citable
- [ ] Preparación de acciones (resumen, link de pago)

---

## Fase 2 — Beta Cerrada 📋 PLANEADA

**Usuarios:** 50-100 reales
**Canal:** Telegram (sin cambios)

- [ ] Onboarding guiado (3 primeros mensajes diseñados)
- [ ] Métricas: % extracción correcta, retención D7/D30, intención de pago
- [ ] Seguridad y LOPDP: cifrado en reposo, política de privacidad
- [ ] Funcionalidades Ola 2 (vida cotidiana y documentos):
  - Documentos personales (cédula, pasaporte, licencia)
  - Fechas especiales (cumpleaños, aniversarios)
  - Vacunas (hijos, mascotas)
  - Suscripciones y servicios olvidados
  - Garantías de electrodomésticos

---

## Fase 3 — Lanzamiento con Monetización 📋 PLANEADA

**Canal:** WhatsApp Business API (360dialog) + Telegram secundario

- [ ] Integración de pago (Kushki/PayPhone)
- [ ] Facturación SRI de la suscripción (AuraFac)
- [ ] Migración/expansión a WhatsApp
- [ ] Soft launch con monitoreo de costo por usuario vs. ingreso
- [ ] Funcionalidades Ola 3 (fiscal/financiero):
  - Gastos deducibles SRI
  - Declaración de impuesto a la renta
  - Diferidos de tarjeta de crédito
  - Créditos de tiendas
  - Tandas / vacas / cadenas de ahorro
  - Cuotas y asambleas de COAC
  - Gastos compartidos (split)
  - Anexo de gastos para contador
- [ ] Funcionalidades familia/cuidado:
  - Medicamentos y recetas
  - Modo cuidado familiar
  - Colegiatura y calendario escolar
  - Remesas

---

## Fase 4 — Cruce a SMB 📋 FUTURO

**Base:** GRISBI/PowerFin (30+ empresas)

- [ ] Trámites y servicios (servicios básicos, encomiendas, seguros, feriados)
- [ ] RUC empresarial (renovación, actividad económica)
- [ ] Patente municipal, permiso de bomberos
- [ ] IESS: aportes patronales, planillas, avisos entrada/salida
- [ ] Pagos a proveedores recurrentes

---

## Fase 5 — Expansión Regional y Premium 📋 FUTURO

- [ ] Recordatorios compartidos con pareja/familia (premium)
- [ ] Pagos asistidos (Lucho prepara, usuario confirma)
- [ ] Integración con Google Calendar
- [ ] Motor de pico y placa parametrizable por ciudad (Bogotá, Lima, CDMX)

---

## Leyenda

- ✅ Completado
- 🔨 En progreso
- 📋 Planeado
- ❌ Cancelado
