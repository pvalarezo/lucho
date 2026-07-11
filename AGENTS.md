# AGENTS.md — Lucho Project

Instrucciones y reglas para agentes de codificación (IA) que trabajen en este proyecto.
Leer completamente antes de cualquier intervención en el código.

---

## 1. Identidad del Proyecto

| Campo | Valor |
|-------|-------|
| **Nombre** | Lucho |
| **Descripción** | Asistente personal conversacional de "segundo cerebro" por WhatsApp/Telegram para Ecuador y LatAm |
| **Empresa** | AURACORE SOLUCIONES SAS |
| **Desarrollador** | Patricio Valarezo |
| **Contacto** | patriciovalarezo@gmail.com |
| **Especificaciones** | `docs/lucho_especificaciones_proyecto.md` (v1.6) |

---

## 2. Reglas de Desarrollo

### 2.1 Idioma

| Contexto | Idioma |
|----------|--------|
| Código fuente (variables, funciones, clases, módulos, comentarios) | **Inglés** — sin excepción |
| Base de datos (nombres de DB, esquemas, tablas, columnas, índices, constraints, funciones, triggers) | **Inglés** — sin excepción |
| Mensajes de commit en Git | **Inglés** |
| Nombres de endpoints | **Inglés** |
| Documentación de proyecto (archivos `.md`, este documento) | **Español** |
| Contenido de cara al usuario final | **Español** |
| Chat / comunicación con el desarrollador (Patricio) | **Español** — siempre |

### 2.2 Base de Datos

- **Nombres de tablas en plural** (`users`, `assets`, `events`, `reminders`, `topics`, `notes`, `lists`, `list_items`, `projects`, `project_tasks`, etc.)
- **Nombres de columnas en singular** (`user_id`, `asset_type`, `target_date`, `created_at`, etc.)
- **Separador de palabras**: guión bajo (`snake_case`)
- **Primary keys**: `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
- **Timestamps**: siempre `TIMESTAMPTZ`, con `DEFAULT now()`
- **Discriminadores de tipo**: usar `ENUM` de PostgreSQL, no `TEXT` libre
- **JSONB**: para atributos flexibles por vertical; validación de forma en capa de aplicación (Pydantic), no en constraints de DB
- **Binario**: nunca se guarda en JSONB — solo referencia al bucket de MinIO

### 2.3 Versionamiento

- Versionamiento semántico de 3 niveles: `MAJOR.MINOR.PATCH`
- Usar **Git** con **tags** para cada versión
- Todo commit, tag y push se hace contra el repositorio configurado para el proyecto

### 2.4 Archivos de Control y Seguimiento

Archivos obligatorios en la raíz del proyecto. El agente debe leerlos al iniciar y actualizarlos al finalizar cada sesión:

| Archivo | Propósito |
|---------|-----------|
| `ROADMAP.md` | Plan general del proyecto, fases, hitos y funcionalidades por ola |
| `PROGRESS.md` | Estado actual de cada fase/módulo, lo completado y lo pendiente |
| `NEXT_SESSION.md` | Resumen corto de avances en la sesión actual + plan para la siguiente sesión |

El agente **debe** actualizar `NEXT_SESSION.md` con cada avance significativo, y `PROGRESS.md` al completar hitos.

---

## 3. Filosofía de Arquitectura (NO NEGOCIABLE)

```
Entrada libre → [IA: extracción/OCR/NLU] → Datos estructurados en PostgreSQL
                                                   ↓
                              [CÓDIGO DETERMINISTA: reglas + cron]
                                                   ↓
                              [IA: redacción del mensaje de salida]

Pregunta del usuario → [IA: retrieval semántico + generación] → Respuesta
```

- **IA en los bordes**: extracción de lenguaje natural, OCR/clasificación de imágenes, retrieval semántico, generación de texto de salida.
- **Código determinista en el centro**: motor de reglas, scheduler/cron, queries de agregación.
- El LLM nunca decide cuándo avisar ni qué regla aplica.
- El LLM nunca genera SQL libre contra la base de datos de producción de cara al usuario.
- Lucho es asistente **reactivo y programado**, no agente autónomo: prepara acciones, nunca las ejecuta solo.

### 3.1 Rutas de Lectura (dos rutas distintas)

| Ruta | Técnica | Cuándo se usa |
|------|---------|---------------|
| **Búsqueda semántica** | pgvector (`cosine_similarity`) | "¿dónde guardé la factura del refri?" |
| **Cálculo/agregación** | Catálogo fijo de queries parametrizadas | "¿cuánto llevo gastado en X?" |

- **Text2SQL solo para analítica interna** de AURACORE, contra réplica de solo lectura.
- Nunca Text2SQL abierto contra la base transaccional de cara al usuario final.

---

## 4. Stack Tecnológico

| Componente | Tecnología |
|------------|-----------|
| Backend | FastAPI (Python) |
| Base de datos | PostgreSQL + pgvector |
| Scheduler | APScheduler |
| Mensajería (MVP) | Telegram Bot API |
| Mensajería (producción) | WhatsApp Business API vía 360dialog |
| Almacenamiento | MinIO |
| Transcripción audio | Whisper |
| Pasarela de pago | Kushki o PayPhone |
| Facturación SRI | AuraFac/FacEC |
| Memoria de sesión | Redis |
| Infraestructura | Docker Compose (Traefik, MinIO, Redis, RabbitMQ) sobre Debian 13 |
| LLM routing/extracción | Claude Haiku 4.5 |
| LLM generación | Claude Sonnet 5 |

---

## 5. Modelo de Datos (Resumen)

### 5.1 Router de Intención

Orden de decisión para clasificar un mensaje entrante:
1. ¿Describe entidad persistente con atributos que generan eventos futuros? → `assets`
2. ¿No, pero tiene fecha propia? → `events`
3. ¿No, pero tiene estado pendiente/hecho? → `lists`/`list_items`
4. ¿Ninguna anterior? → `notes`

Proyectos: ruta ortogonal — si el mensaje menciona un proyecto, la tarea va a `project_tasks` directamente.

### 5.2 Tablas (16 + 1 vista)

| Módulo | Tablas |
|--------|--------|
| Identidad/mensajería | `users`, `messages` |
| Activos | `assets` |
| Eventos/recordatorios | `events`, `reminders` |
| Notas por tema | `topics`, `notes` |
| Listas | `lists`, `list_items` |
| Proyectos | `projects`, `project_tasks` |
| Contactos/terceros | `contacts`, `caregiver_links` |
| Gastos compartidos | `shared_expenses`, `shared_expense_participants` |
| Suscripción/facturación | `subscriptions`, `payments`, `subscription_invoices` |
| Búsqueda unificada | `searchable_content` (vista) |

---

## 6. Guardrails de Producto

- No responde preguntas de cultura general, clima, tareas de colegio.
- No improvisa asesoría legal/fiscal sin anclar a norma citable.
- No decide ni ejecuta pagos o trámites por su cuenta.
- Todo digest/resumen proactivo es opt-in.
- El usuario puede corregir o eliminar cualquier dato en cualquier momento.

---

## 7. Flujo Conversacional

1. Usuario envía texto/audio/foto (sin comandos, sin estructura).
2. **Ack inmediato**: "Recibido, dame un segundo."
3. **Extracción con LLM**: Whisper si es audio, OCR/visión si es foto.
4. **Confirmación editable**: Lucho muestra lo que entendió; el usuario corrige en lenguaje natural.
5. Persistencia en PostgreSQL.
6. Cron diario evalúa reglas deterministas → recordatorios proactivos con anticipación escalonada.
7. Búsqueda conversacional bajo demanda vía retrieval semántico.

---

## 8. Estrategia de LLMs

- **Haiku 4.5** (económico): routing de intención, clasificación, extracción de parámetros para queries.
- **Sonnet 5** (capacidad): extracción estructurada, generación de respuestas, cálculos explicados, retrieval complejo.
- **Whisper**: transcripción de audio.
- **Sonnet 5 con visión**: OCR/clasificación de facturas y documentos.

Costo controlado: no todo mensaje dispara el modelo más caro.

---

## 9. Comunicación con el Desarrollador

- **Idioma**: español, siempre.
- **Estilo**: claro, profesional, directo.
- **Antes de actuar**: confirmar decisiones de arquitectura o diseño que no estén explícitamente cubiertas en las especificaciones.
- **Al iniciar sesión**: leer `AGENTS.md`, `ROADMAP.md`, `PROGRESS.md`, `NEXT_SESSION.md` y `docs/lucho_especificaciones_proyecto.md`.
- **Al finalizar sesión**: actualizar `PROGRESS.md` y `NEXT_SESSION.md`.

---

## 10. Fase Actual

**Fase 1 — MVP técnico (Telegram primero)**

Entregables:
- Modelo de datos base: `assets`, `events`, `reminders` para 2 verticales (vehicular + gastos SRI)
- Bot de Telegram + backend FastAPI
- Pipeline de extracción de dos modelos (Haiku + Sonnet)
- Capa de confirmación editable
- Motor de reglas determinista + APScheduler (pico y placa + matriculación)
- Núcleo transversal + "Lucho piensa" en versión mínima
