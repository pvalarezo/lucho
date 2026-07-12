# Lucho — Asistente personal por WhatsApp/Telegram para Ecuador y LatAm

**Empresa creadora:** AURACORE SOLUCIONES SAS
**Desarrollador:** Patricio Valarezo
**Contacto:** patriciovalarezo@gmail.com
**Versión del documento:** 1.7 — Fase 1 completada: multi-LLM (DeepSeek), sistema de tools, respuestas contextuales, bot Telegram con polling. Ver sección 14 para cambios respecto a v1.6.

---

## 1. Idea general

Lucho es un asistente conversacional de "segundo cerebro" al que el usuario le habla o le manda fotos sin pensar en estructura. Lucho recuerda, organiza y encuentra lo que el usuario necesita después — y además calcula, explica y prepara cosas sobre esos datos, en vez de limitarse a lanzar alarmas.

El acceso es 100% conversacional (WhatsApp / Telegram), sin app nativa que instalar. La fricción cero de captura es la propuesta de valor central; cualquier decisión de producto que la comprometa (exigir estructura, exigir una app) va en contra del diseño.

## 2. Problema a resolver

- Las personas olvidan fechas y obligaciones que tienen costo real (multas de matriculación, mora de tarjeta, vencimiento de garantías, citas médicas).
- Las apps de "memoria"/recordatorios globales (Memorae, RecordAI, Zapia) no tienen profundidad regulatoria ni cultural de Ecuador/LatAm: no conocen SRI, IESS, matriculación por placa, pico y placa, tandas, créditos de tiendas, remesas.
- Esas mismas apps fallan en cosas básicas que generan frustración de usuarios pagantes: exigen ser muy específico, cobran por recordatorios desde foto, no manejan varias instrucciones en un mensaje, fallan con recurrencias complejas.
- Nadie está resolviendo el ángulo de cuidado familiar (recordatorios para adultos mayores, medicamentos) ni la economía informal latinoamericana (tandas, créditos de tienda, cooperativas).

## 3. Público objetivo

- Público general ecuatoriano (no un nicho profesional), inicialmente en Cuenca y expansión a otras ciudades.
- Perfil ancla: adulto con carro, tarjetas de crédito, posible RUC de persona natural o negocio pequeño.
- Extensión natural: base de clientes B2B existente de PowerFin ERP / GRISBI (30+ empresas) para la ola de funcionalidades SMB.

## 4. Diferenciador (por qué Lucho y no Memorae/RecordAI/Zapia)

1. **Profundidad Ecuador/LatAm real**, no genérica: reglas fiscales, vehiculares y de economía informal que ningún competidor global va a priorizar.
2. **Factura electrónica SRI de la propia suscripción** (vía AuraFac), diferenciador que ningún competidor extranjero puede ofrecer sin operar localmente.
3. **Arquitectura que corrige los fallos conocidos de la competencia**: confirmación editable inmediata, manejo de instrucciones múltiples en un mensaje, recurrencias complejas, sin cobrar por función básica de foto.
4. **Ángulo de cuidado familiar** (medicamentos, adultos mayores) como diferenciador emocional, no solo funcional.
5. Lucho **piensa, no solo recuerda**: calcula sobre los datos del usuario, explica anclado a norma citable, detecta patrones, y prepara acciones (nunca las ejecuta solo).

## 5. Filosofía de arquitectura: IA en los bordes, determinismo en el centro

Este es el principio no negociable del proyecto:

- **IA** se usa para: extracción de lenguaje natural no estructurado (texto/audio/foto), retrieval semántico, OCR/clasificación de imágenes, generación de lenguaje de salida (confirmaciones, respuestas, resúmenes).
- **Código determinista** se usa para: el motor de reglas (fechas ciertas: matriculación, pico y placa; fechas estimadas: mantenimiento), el scheduler/cron que decide cuándo avisar, y cualquier cálculo agregado sobre los datos del usuario.
- Ninguna decisión de "cuándo avisar" o "qué regla aplica" debe depender del criterio de un LLM. Esto es un requisito de confiabilidad y auditoría (LOPDP, reclamos de usuarios), no una preferencia estética.
- Lucho es un asistente **reactivo y programado**, no un agente autónomo que ejecuta acciones (pagos, trámites) por su cuenta. Puede *preparar* (link de pago, resumen, borrador de mensaje) pero el usuario siempre confirma.

```
Entrada libre → [IA: extracción / OCR / NLU] → Datos estructurados en PostgreSQL
                                                        ↓
                                    [Código determinista: reglas + cron]
                                                        ↓
                                    [IA: redacción del mensaje de salida]

Pregunta del usuario → [IA: retrieval semántico + generación] → Respuesta anclada a sus datos
```

### Decisión de build vs. frameworks de agentes de terceros

Se evaluó y **se descartó** construir sobre frameworks de agentes de terceros (tipo OpenClaw, Hermes Agent). Motivos:
- Diseñados para automatización personal de un solo usuario en su propia infraestructura, no para SaaS multi-tenant con datos financieros sensibles de terceros.
- Historial de seguridad problemático en el ecosistema (CVEs críticos, marketplaces de skills con contenido malicioso, instancias expuestas públicamente) — riesgo inaceptable para un producto que maneja cédulas, tarjetas, RUC.
- Su paradigma de "agente que aprende/decide" choca con el requisito de determinismo del motor de reglas.
- Se construye sobre stack propio (FastAPI + PostgreSQL + APScheduler), dando control total sobre aislamiento de datos, auditoría, cumplimiento LOPDP y facturación SRI.

## 6. Mecanismo de comunicación

**Canales:** Telegram primero (gratis, sin aprobación, prototipado rápido) para MVP y beta cerrada → migración/expansión a WhatsApp Business API (vía 360dialog) para lanzamiento público, dado que WhatsApp tiene mejor adopción general en Ecuador y los mensajes de recordatorio califican como plantillas de categoría "utilidad" (la más barata) bajo el modelo de precio por mensaje vigente desde julio 2025. Telegram se mantiene como canal secundario.

**Flujo conversacional:**
1. Usuario envía texto, audio o foto — sin comandos, sin estructura.
2. **Ack inmediato** ("Recibido, dame un segundo") para evitar ansiedad de latencia.
3. **Extracción con LLM** (transcripción Whisper si es audio, OCR/visión si es foto).
4. **Confirmación editable**: Lucho muestra lo que entendió en formato corto; el usuario corrige en lenguaje natural si algo falló, sin tener que reescribir todo el mensaje.
5. Persistencia en PostgreSQL.
6. Cron diario evalúa reglas deterministas y dispara recordatorios proactivos (texto o voz), con anticipación escalonada (ej. 15/7/3 días antes según el tipo de evento).
7. Búsqueda conversacional bajo demanda ("¿dónde guardé...?") en cualquier momento, vía retrieval semántico.

**Reglas de diseño de conversación:**
- Debe manejar varias instrucciones en un solo mensaje.
- Debe manejar recurrencias complejas (días específicos de la semana, cada N días).
- Todo digest/resumen proactivo es opt-in, nunca por defecto.
- El usuario puede corregir o borrar cualquier dato en cualquier momento.

## 7. Catálogo de funcionalidades

### Núcleo transversal (MVP)
- Captura libre: texto, audio, foto.
- Ack inmediato + confirmación editable.
- Búsqueda conversacional / memoria a largo plazo.
- Recurrencias complejas y múltiples instrucciones por mensaje.
- Listas simples (compras, pendientes).
- Recordatorios entre amigos/familiares.
- Resumen diario/semanal (opt-in).

### Lucho piensa, no solo recuerda (diferenciador central, MVP+)
- Cálculos sobre los datos del usuario ("¿cuánto llevo gastado en X?", "¿cuánto me falta pagar este año?").
- Explicaciones ancladas a norma ecuatoriana citable, aplicadas a los datos del propio usuario (nunca asesoría legal/fiscal genérica abierta).
- Detección de patrones y aviso proactivo (gasto que subió, factura duplicada, hábito de captura que bajó).
- Preparación de acciones (resumen para el contador, link de pago listo, mensaje redactado para un tercero) — el usuario siempre confirma la acción final.
- **Notas por tema** — el usuario dicta ideas/contenido libre bajo un tema que él mismo define (ej. "ideas de negocio"), acumulando con el tiempo; Lucho las lista o las sintetiza/organiza cuando se le pide. Candidato fuerte a ser el gancho de uso más frecuente de la app.
- **Proyectos** — agrupa bajo un nombre común (ej. "viaje a Salinas") sus propias tareas, cada una con estado pendiente/hecho y fecha límite opcional; Lucho sintetiza el avance del proyecto al preguntarle. Tablas propias y autocontenidas (no enlaza a listas ni eventos existentes), deliberadamente simple: sin dependencias entre tareas ni gestión formal de proyectos.

### Vehicular (Ola 1 — MVP)
- Matriculación por último dígito de placa.
- Pico y placa semanal (calculado al vuelo, no materializado en base de datos).
- Revisión técnica vehicular (RTV).
- SOAT.

### Vida cotidiana y documentos (Ola 2)
- Documentos personales: cédula, pasaporte, licencia.
- Fechas especiales (cumpleaños, aniversarios) con anticipación para regalo.
- Vacunas (hijos y mascotas).
- Suscripciones y servicios olvidados.
- Garantías de electrodomésticos (foto de factura → aviso antes de vencer).

### Familia y cuidado (diferenciador LatAm, Ola 2-3)
- Medicamentos y recetas.
- Modo cuidado familiar (un hijo configura recordatorios para un padre/madre mayor, interacción priorizando voz).
- Colegiatura y calendario escolar.
- Remesas (seguimiento de envíos/recepción desde el exterior).

### Fiscal y financiero (Ola 3 — gatillo de conversión a pago)
- Gastos deducibles SRI (foto de factura → categorización automática).
- Declaración de impuesto a la renta según noveno dígito de RUC.
- Diferidos de tarjeta de crédito multi-banco.
- Créditos de tiendas (Comandato, Artefacta, La Ganga y similares).
- Tandas / vacas / cadenas de ahorro.
- Cuotas y asambleas de cooperativas de ahorro y crédito (COAC).
- Gastos compartidos (split de grupo).
- Anexo de gastos para el contador.
- Factura SRI de la propia suscripción (vía AuraFac).

### Trámites y servicios (complementario, Ola 3-4)
- Servicios básicos (fecha de pago, cortes programados).
- Encomiendas/aduana.
- Pólizas de seguro (vida, salud, vehículo).
- Feriados y puentes (contexto de planificación).

### Cruce a negocio/SMB (Ola 4 — cross-sell a base GRISBI/PowerFin)
- RUC: renovación, actualización de actividad económica.
- Patente municipal.
- Permiso de Bomberos.
- IESS: aportes patronales, planillas, avisos de entrada/salida de empleados.
- Pagos a proveedores recurrentes.

### Futuro / no construir en el arranque (Ola 5)
- Recordatorios compartidos con pareja/familia (premium).
- Pagos asistidos (Lucho prepara, el usuario confirma).
- Integración con Google Calendar.
- Motor de pico y placa parametrizable por ciudad (expansión regional: Bogotá, Lima, CDMX).

### Guardrails de producto (aplican siempre, en todas las olas)
- No responde preguntas de cultura general, clima, tareas de colegio — nada fuera de la vida administrativa/financiera/personal registrada por el usuario.
- No improvisa asesoría legal/fiscal fuera de lo que puede anclar a una norma citable.
- No decide ni ejecuta pagos o trámites por su cuenta.
- Todo digest/resumen proactivo es opt-in.
- El usuario puede corregir o eliminar cualquier dato en cualquier momento; política de retención de datos visible, no solo en letra chica.

## 8. Stack tecnológico

- **Backend:** FastAPI (Python)
- **Base de datos:** PostgreSQL (JSONB para atributos flexibles por tipo de activo, extensión pgvector para búsqueda semántica — sin motor vectorial dedicado separado, dado el volumen por usuario)
- **Scheduler:** APScheduler (cron diario para evaluación de reglas)
- **Mensajería:** Telegram Bot API (MVP/beta) → WhatsApp Business API vía 360dialog (lanzamiento público)
- **Almacenamiento de archivos:** MinIO (fotos de documentos/facturas)
- **Transcripción de audio:** Whisper
- **Pasarela de pago:** Kushki o PayPhone (link de pago generado en chat, evitando comisión de tiendas de apps)
- **Facturación de la suscripción:** AuraFac/FacEC (SRI-compliant, ya desarrollado por AURACORE)
- **Infraestructura:** VPS limpio con Debian 13, todo desplegado vía Docker (Docker Compose): MinIO, Redis, RabbitMQ, aplicativo de proxy inverso y gestión de SSL (ej. Traefik). Sin servicios instalados directo en el host; cada componente vive en su propio contenedor.

## 8.1 Reglas de codificación

- **Idioma del código: inglés, sin excepción.** Nombres de variables, funciones, clases, módulos, comentarios de código, mensajes de commit, nombres de endpoints.
- **Base de datos en inglés.** Nombres de bases de datos, esquemas, tablas, columnas, índices, constraints, funciones/triggers de PostgreSQL — todo en inglés.
- **Nombres de tablas en plural** (`assets`, `events`, `reminders`, `users`, no `asset`, `event`, `reminder`, `user`).
- Documentación de proyecto (READMEs, este documento, comentarios de negocio) y contenido de cara al usuario final permanecen en español, siguiendo la convención ya establecida en el resto de proyectos de AURACORE/GRISBI.

## 9. Modelo de datos (esquema base, ampliable sin migración de esquema)

Tres tablas centrales (nombres en inglés, plural, según reglas de codificación):

- **`assets`**: qué posee o rastrea el usuario (`asset_type`, `name`, `attributes` JSONB con versión de esquema, soft delete). Un índice GIN sobre `attributes` habilita búsqueda flexible sin migrar columnas por cada tipo nuevo.
- **`events`**: qué va a pasar y cuándo (`target_date` como columna real e indexada — es lo que el cron filtra todos los días —, `certainty` cierta/estimada, `recurrence_rule` JSONB, `status`).
- **`reminders`**: cuándo y cómo se avisa (uno o varios por evento, con anticipación escalonada), con auditoría del mensaje realmente enviado y la respuesta del usuario.

**Reglas de diseño:**
- Regla general: todo lo que el cron necesita filtrar/ordenar en masa va en columna indexada (fecha, estado, tipo); todo lo que varía por vertical y se consulta caso por caso va en JSONB.
- La validación de la forma del JSONB se hace en la capa de aplicación (modelos Pydantic con discriminador por `asset_type`), no con constraints de base de datos — así se agregan tipos nuevos (Ola 3, Ola 4) sin migrar el esquema.
- Reglas recurrentes de alta frecuencia (pico y placa) se calculan al vuelo desde `assets.attributes`, no se materializan como filas — evita explosión de registros.
- Nunca se guarda el binario de fotos en JSONB; solo la referencia al bucket de MinIO.
- Campo `attributes_schema_version` como salvavidas para migrar datos si cambia la forma de un tipo ya existente.

## 9.1 Flujo de datos: escritura y rutas de lectura

**Escritura:** la captura (texto/audio/foto) se procesa como ya se describió (ack, extracción, confirmación editable) y se persiste en `assets`/`events`. Al guardar un `asset`, se genera también su embedding para la ruta de búsqueda.

**Lectura — dos rutas distintas según el tipo de pregunta, nunca una sola técnica genérica:**

1. **Búsqueda semántica** ("¿dónde guardé la factura del refri?"): embeddings + similitud vectorial. Se usa **pgvector** dentro de la misma instancia de PostgreSQL, no un motor vectorial dedicado (Qdrant) como en AuraContext — la escala por usuario (decenas/cientos de `assets`, no miles de documentos de un corpus legal) no justifica la complejidad operativa adicional de correr un servicio más.

2. **Cálculo/agregación** ("¿cuánto llevo gastado en X?", "¿cuánto me falta pagar este año?"): **no se usa Text2SQL abierto.** El LLM (modelo económico, ej. Haiku) solo extrae parámetros estructurados de la pregunta (métrica, categoría, rango de fechas) hacia un modelo Pydantic conocido. El backend traduce esos parámetros a una de un catálogo fijo de queries parametrizadas, pre-escritas y probadas, con el filtro `user_id` siempre inyectado por código — nunca confiado a una consulta generada por el modelo. Esto es una extensión directa del principio ya fijado (IA en los bordes, determinismo en el centro) aplicado a consultas: el LLM decide *qué se pregunta*, el código decide *cómo se consulta*.

**Por qué no Text2SQL genérico de cara al usuario final:** el catálogo de preguntas de Lucho es finito y conocido (a diferencia del caso de uso de KORA, que resuelve preguntas ad-hoc impredecibles para un analista de confianza sobre un esquema empresarial). Dejar que un LLM genere SQL libre contra una base multi-tenant con datos financieros introduce riesgo real de fuga de aislamiento entre usuarios, queries costosas sin revisión previa, y superficie de inyección — inaceptable dado el tipo de dato que maneja (cédulas, tarjetas, RUC).

**Dónde sí encaja Text2SQL/KORA en este proyecto:** como herramienta interna de analítica de producto para el propio equipo de AURACORE (ej. "¿cuántos usuarios activaron el módulo de deducibles SRI este mes?"), apuntando a una réplica de solo lectura o vistas agregadas/anonimizadas — no a la base de producción transaccional ni de cara al usuario final.

**Memoria conversacional de corto plazo:** Redis (ya en el stack) guarda el contexto inmediato de la conversación (último `asset`/`event` referenciado, con TTL corto) para resolver referencias como "esa cuota muévela a fin de mes" sin que el usuario tenga que repetir de qué habla. Es memoria efímera de sesión, separada de PostgreSQL como almacenamiento de largo plazo, y no se audita de la misma forma.

## 9.2 Notas por tema ("fuente de conocimiento" libre)

Un tercer tipo de entidad, distinto de `assets` (algo que se posee, campos conocidos por vertical) y `events` (algo que va a pasar, con fecha): **notas de texto libre agrupadas por tema que el propio usuario define**, sin estructura de campos fija (ideas de negocio, recetas, cualquier cosa que quiera ir acumulando). Sigue siendo una extensión de "Memoria en todas partes"/"Memoria a largo plazo", no una excepción al guardrail de no ser un asistente de propósito general: Lucho solo captura, organiza y devuelve lo que el usuario mismo dictó.

```sql
CREATE TABLE topics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX idx_topics_user_name ON topics (user_id, lower(name));

CREATE TABLE notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_id UUID NOT NULL REFERENCES topics(id),
    content TEXT NOT NULL,
    embedding VECTOR(1024),
    source_message_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_notes_topic ON notes (topic_id, created_at);
CREATE INDEX idx_notes_embedding ON notes USING hnsw (embedding vector_cosine_ops);
```

**Decisión de persistencia — se mantiene todo en PostgreSQL, sin motor NoSQL adicional ni archivos como almacenamiento primario:**
- "No estructurado" no requiere salir de Postgres: JSONB (ya usado en `assets.attributes`) y `TEXT` + `pgvector` cubren la flexibilidad de una base de documentos dentro del mismo motor, sin sumar un segundo sistema (backup, monitoreo, conexión adicional) para algo que ya se resuelve gratis en la base existente.
- **Archivos Markdown como almacenamiento primario quedan descartados para este caso**, a diferencia de AuraContext (donde sí funcionan porque hay un curador humano único, corpus semi-estático, y control de versiones vía git). `notes` tiene el perfil opuesto: miles de usuarios finales, escritura concurrente, sin curación humana, aislamiento estricto por usuario — un archivo por nota no da atomicidad transaccional, escala mal en número de archivos, y separa el índice de embeddings de la fuente de verdad.
- **Markdown sí tiene un rol, pero como formato de exportación bajo demanda** ("pásame mis ideas de negocio en un archivo"), generado al vuelo desde la tabla `notes` — nunca como el almacenamiento interno. Mismo patrón que el resumen de gastos para el contador.

**Router de intención — dos casos nuevos:**
- **Nueva nota a un tema**: Haiku detecta el tema (existente o nuevo, creado sin fricción si no existe) y el contenido.
- **Consulta de un tema**: listado crudo determinista (sin LLM, rápido y barato) o síntesis/resumen vía Sonnet cuando el usuario lo pide explícitamente — este es el caso donde "Lucho piensa, no solo recuerda" aplica a notas, no solo a cálculos financieros.

## 9.3 Listas (compras / tareas)

Un cuarto tipo de entidad, distinto de `notes` porque cada ítem tiene **estado** (pendiente/hecho) que cambia con el tiempo — no es contenido que solo se acumula, es contenido que se tacha y se consulta filtrado ("¿qué me falta?").

```sql
CREATE TABLE lists (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    list_type TEXT NOT NULL DEFAULT 'generic',  -- 'shopping','tasks','generic'
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE list_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    list_id UUID NOT NULL REFERENCES lists(id),
    content TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',  -- 'pending','done'
    quantity TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);
CREATE INDEX idx_list_items_list_status ON list_items (list_id, status);
```

Marcar un ítem como hecho o preguntar "qué falta" son operaciones deterministas sobre `status`, no interpretación de lenguaje repetida — el LLM solo participa en la captura (extraer ítems de una instrucción) y, opcionalmente, al leer la lista en voz de forma natural.

**Decisión de arquitectura resuelta:** se evaluó consolidar `topics`/`notes` y `lists`/`list_items` en un modelo genérico de "contenedores", pero se descartó — `status` (NULL para notas, significativo para listas) es comportamiento distinto disfrazado de mismo esquema, y complica cada query y el schema de extracción del LLM con lógica condicional por tipo. Se mantienen como tablas dedicadas (Opción A). Se compensan sus dos desventajas reales sin tocar el esquema:
- **Boilerplate repetido por módulo**: se resuelve con un repositorio/servicio genérico parametrizado (`BaseRepository[T]`) en la capa de aplicación, no en el esquema.
- **Búsqueda unificada** ("busca en todo lo que tengo guardado"): se resuelve con la vista `searchable_content` (ver sección 9.5), no con una tabla polimórfica.
- Donde ya existen discriminadores por tipo (`asset_type`, `list_type`), se usa `ENUM` de Postgres en vez de `TEXT` libre, para que el motor rechace valores inválidos al insertar en vez de depender de disciplina en el código de aplicación.

**Compartido entre usuarios (futuro, no bloquea MVP):** una tabla `list_shares (list_id, shared_with_user_id)` habilitaría listas compartidas (ej. lista de compras del hogar) sin cambiar el esquema base.

## 9.4 Router de intención: cómo Lucho decide a qué tabla va un mensaje

La pregunta clave no es "¿de qué habla el mensaje?", sino **"¿esto necesita existir después de este mensaje, con datos que otra parte del sistema va a volver a leer?"** — esa prueba es la que separa `assets` de todo lo demás, y evita que Lucho cree una entidad duplicada cada vez que el usuario menciona algo de pasada.

**Árbol de decisión (aplicado en orden):**
1. ¿Describe una entidad persistente con atributos identificadores que generan eventos futuros (placa, tarjeta, garantía)? → `assets`.
2. ¿No, pero tiene fecha propia? → `events` (+ `reminders`).
3. ¿No, pero tiene un estado que se puede marcar como hecho/pendiente? → `lists`/`list_items`.
4. Si no aplica ninguna de las anteriores → `notes` (contenido libre bajo un tema).

**Tres piezas técnicas que hacen esto confiable, no una suposición del modelo:**
- **Salida estructurada con enum cerrado**: el router (Haiku) devuelve `target_table` limitado a un conjunto fijo (`asset | event | list_item | note | shared_expense | search | correction`), nunca texto libre a interpretar después.
- **Resolución de entidad antes de escribir** (solo para `assets`): el backend busca coincidencias existentes por `asset_type` + similitud de nombre/embedding entre los `assets` del usuario antes de insertar. Si hay match razonable, es `UPDATE`; si no, es `INSERT`. Esta decisión es determinista, en código — el LLM solo aporta `asset_type` y los campos.
- **La confirmación editable es la red de seguridad**: si el router se equivoca (clasifica mal, o crea un duplicado), el usuario lo ve antes de que se persista y corrige en lenguaje natural. Los casos ambiguos reales que surjan en la beta se incorporan como ejemplos few-shot al prompt del router — iteración de prompt, no reentrenamiento.

## 9.5 Resto de módulos y tablas

**Identidad y mensajería (transversal):**
```sql
CREATE TABLE users ( ... )
CREATE TABLE messages ( ... )  -- log crudo: texto/audio/foto, transcripción, resultado de extracción; origen de source_message_id
```

**Contactos y terceros** (recordatorios entre amigos/familia, modo cuidado):
```sql
CREATE TABLE contacts ( ... )        -- destinatarios de recordatorios, registrados o no
CREATE TABLE caregiver_links ( ... ) -- vínculo cuidador–cuidado, modo cuidado familiar
```

**Gastos entre varias personas** (split de grupo, tandas/vacas, cuotas de cooperativas COAC):
```sql
CREATE TABLE shared_expenses ( ... )
CREATE TABLE shared_expense_participants ( ... )
```

**Suscripción, pago y facturación:**
```sql
CREATE TABLE subscriptions ( ... )
CREATE TABLE payments ( ... )
CREATE TABLE subscription_invoices ( ... )  -- referencia a la factura SRI emitida vía AuraFac
```

**Búsqueda unificada (vista, no tabla física):**
```sql
CREATE VIEW searchable_content AS
SELECT id, 'note' AS source_table, content AS text, embedding, created_at FROM notes
UNION ALL
SELECT id, 'list_item', content, embedding, created_at FROM list_items
UNION ALL
SELECT id, 'asset', name, NULL, created_at FROM assets;
```

Une `notes`, `list_items` y `assets` para la búsqueda global sin duplicar escritura ni crear una tabla polimórfica — el DDL completo de cada tabla (columnas, tipos, constraints) se define en la etapa de implementación, siguiendo los mismos patrones ya establecidos (UUID como PK, `user_id` siempre indexado, ENUM para discriminadores, timestamps con zona horaria).

**Resumen de módulos:** 8 módulos, 16 tablas + 1 vista — Identidad/mensajería, Activos, Eventos/recordatorios, Notas por tema, Listas, Contactos/terceros, Gastos compartidos, Suscripción/facturación.

## 9.6 Proyectos (tablas propias, autocontenidas)

Funcionalidad nueva, deliberadamente simple: un proyecto agrupa sus propias tareas bajo un nombre común (ej. "viaje a Salinas", "boda"). Se descartó el enfoque de enlaces polimórficos hacia `lists`/`events`/`notes` (propuesto inicialmente) por ser más complejo de lo necesario tanto para implementar como para que Lucho busque/edite con confiabilidad — cada consulta o corrección tendría que resolver primero a qué tabla apunta el enlace antes de actuar. Se prioriza simplicidad de uso y de mantenimiento sobre la elegancia de no duplicar un patrón de "ítem con estado".

```sql
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',  -- 'active' | 'archived'
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX idx_projects_user_name ON projects (user_id, lower(name));

CREATE TABLE project_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id),
    content TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',  -- 'pending' | 'done'
    due_date DATE,                            -- opcional, simple, sin escalonado
    reminder_sent BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);
CREATE INDEX idx_project_tasks_project_status ON project_tasks (project_id, status);
CREATE INDEX idx_project_tasks_due_date ON project_tasks (due_date) WHERE due_date IS NOT NULL;
```

Es, en la práctica, el mismo patrón determinista que `list_items` (estado pendiente/hecho, operaciones simples sobre `status`), con un `due_date` opcional para tareas que sí necesitan avisarse. A propósito no lleva anticipación escalonada como `events`/`reminders` — el cron diario revisa `project_tasks` con `due_date` próximo y `reminder_sent = false`, envía un único aviso simple, y marca `reminder_sent = true`. Si más adelante se necesita anticipación de 15/7/3 días para tareas de proyecto, se agrega ahí mismo sin tocar `events`.

**Cómo entra en el router (sección 9.4):** paso ortogonal al árbol de decisión de contenido. Si el mensaje menciona un proyecto ("para el viaje a Salinas, agrega comprar protector solar"), se resuelve el proyecto por nombre entre los existentes del usuario (creación sin fricción si no existe, mismo patrón que `topics`), y la tarea se inserta directamente en `project_tasks` — sin pasar por `lists` ni `events`. Buscar o marcar una tarea como hecha es una consulta directa a una sola tabla, filtrando por `project_id`.

**El valor real está en la síntesis:** "¿cómo va mi viaje a Salinas?" cuenta tareas hechas/pendientes y próximas fechas directamente desde `project_tasks` — una sola tabla, una sola consulta, sin resolver enlaces a otras.

**Guardrail:** Lucho organiza y sintetiza proyectos de la vida cotidiana del usuario — no es una herramienta de gestión de proyectos. Sin dependencias entre tareas, sin diagramas de Gantt, sin asignación formal de responsables más allá de compartir con un contacto. Pedir eso es scope creep fuera del pitch de Lucho.

## 10. Estrategia de LLMs

**Estrategia de dos modelos** (ya validada por AURACORE en AuraContext v2):
- **Modelo económico/rápido para routing y clasificación** (ej. Claude Haiku 4.5): clasifica intención del mensaje (nuevo recordatorio / búsqueda / corrección / pregunta de cálculo), mantiene el costo unitario controlado a escala.
- **Modelo de mayor capacidad para extracción y generación** (ej. Claude Sonnet 5): extracción estructurada de campos, generación de respuestas, cálculos explicados, retrieval semántico complejo.
- **Transcripción de audio:** Whisper.
- **OCR/visión de facturas y documentos:** el mismo modelo de generación (Sonnet 5) con capacidad de visión, o un paso de OCR dedicado si el volumen lo justifica más adelante.

Este enrutamiento por costo es lo que hace sostenible la unit economics de un plan de suscripción de bajo precio (US$2.99-4.99/mes): no todo mensaje debe disparar el modelo más caro.

## 11. Monetización (referencia, no requerido para el MVP técnico)

- Freemium: núcleo + 15-20 activos gratis.
- Plan individual: ~US$2.99-4.99/mes o ~US$25-30/año.
- Plan independiente/RUC: ~US$6.99-9.99/mes, incluye deducibles SRI + factura de la propia suscripción.
- Cobro vía pasarela local (Kushki/PayPhone), no tiendas de apps.

## 12. Roadmap de desarrollo

**Fase 0 — Validación (completada):** encuestas confirmaron interés e indicaron preferencia por WhatsApp como canal.

**Fase 1 — MVP técnico (Telegram primero):**
- Modelo de datos base (`assets`, `events`, `reminders`) para 2 verticales: vehicular + gastos SRI.
- Bot de Telegram + backend FastAPI.
- Pipeline de extracción de dos modelos (Haiku + Sonnet).
- Capa de confirmación editable (crítica, no postergar).
- Motor de reglas determinista + APScheduler para pico y placa + matriculación.
- Funcionalidades del bloque "Núcleo transversal" y "Lucho piensa, no solo recuerda" en su versión mínima.

**Fase 2 — Beta cerrada (50-100 usuarios reales):**
- Onboarding guiado (primeros 3 mensajes cuidadosamente diseñados).
- Métricas clave: % de extracción correcta sin corrección manual, retención D7/D30, intención de pago espontánea.
- Seguridad y LOPDP desde esta fase: cifrado en reposo, política de privacidad clara, retención de datos definida.
- Agregar Ola 2 (vida cotidiana y documentos) en paralelo, comparte casi toda la infraestructura del MVP.

**Fase 3 — Lanzamiento con monetización:**
- Integración de pago (Kushki/PayPhone) + facturación SRI de la suscripción vía AuraFac.
- Migración/expansión a WhatsApp Business API vía 360dialog.
- Soft launch monitoreando costo por usuario activo (LLM + mensajería) vs. ingreso.
- Ola 3 (fiscal/financiero) como gatillo de conversión a pago, priorizada según señal real de la beta.

**Fases posteriores:** Ola 4 (cruce a SMB, aprovechando base GRISBI/PowerFin) y Ola 5 (funcionalidades futuras) se evalúan con datos reales de adopción, no por adelantado.

## 13. Seguridad y cumplimiento

- Cifrado en reposo de documentos e imágenes sensibles (cédulas, tarjetas, facturas).
- Cumplimiento LOPDP: política de privacidad clara, comunicada en el onboarding, no solo en letra chica.
- Política de retención de datos definida y visible para el usuario.
- Auditoría: cada recordatorio enviado guarda el mensaje generado y la respuesta del usuario, para poder reconstruir qué pasó ante cualquier reclamo.

## 14. Cambios respecto a v1.6 (Decisiones de implementación — Fase 1)

### 14.1 Estrategia multi-LLM (DeepSeek como default)

**Cambio:** Se adoptó DeepSeek como proveedor principal de LLM, manteniendo Anthropic como alternativa configurable vía `LLM_PROVIDER` en `.env`.

**Motivo:**
- Costo ~10x menor: DeepSeek-V3 (~$0.27/MTok) vs Claude Sonnet (~$15/MTok).
- API OpenAI-compatible: mismo formato que Whisper, mínimo cambio de código.
- Sin restricciones geográficas en Ecuador/LatAm.
- Español sólido por entrenamiento multilingüe.

**Arquitectura:** Capa de abstracción `app/services/llm/` con providers intercambiables (AnthropicProvider, DeepSeekProvider). El router usa DeepSeek-chat para clasificación (económico) y extracción (capaz). Cambiar de proveedor es una línea en `.env`.

**Riesgo mitigado:** Sin vendor lock-in. Si DeepSeek falla, se vuelve a Anthropic sin tocar código.

### 14.2 Sistema de herramientas externas (API/MCP ready)

**Cambio:** Se implementó un sistema de tools enchufables (`app/tools/`) que permite consultar APIs externas desde el flujo conversacional.

**Motivo:**
- El usuario ecuatoriano necesita consultar sistemas reales (multas ANT, estado SRI, puntos licencia).
- Arquitectura preparada para MCP (Model Context Protocol) cuando esté maduro.

**Funcionamiento:**
1. Router (LLM) → identifica intención `tool` + `tool_name`
2. Extractor (LLM) → extrae parámetros (placa, cédula, etc.)
3. Tool executor (CÓDIGO) → llama la API externa
4. Response formatter → resultado formateado al usuario

**Principio intacto:** La IA decide QUÉ herramienta usar, pero el CÓDIGO la ejecuta. Nunca el LLM toca la API externa.

**Primera herramienta:** `check_plate_fines` — consulta multas de tránsito por placa (simulada en dev, lista para API real).

### 14.3 Respuestas contextuales (IA generando sobre datos del usuario)

**Cambio:** Las búsquedas ahora transforman datos crudos en respuestas conversacionales mediante LLM.

**Antes:** `🚗 *Tus vehículos:* • *ABC-1234* — Toyota Corolla`
**Ahora:** _"Tenés un Toyota Corolla con placa ABC-1234. Tu pico y placa es los jueves y la matriculación vence el 31 de agosto de 2026. ¿Querés que te avise con anticipación?"_

**Principio intacto:** El LLM solo formatea datos que YA están en la base. No inventa información. Si no hay datos, responde "No tengo vehículos registrados".

### 14.4 Bot Telegram con polling (desarrollo)

**Cambio:** Para desarrollo se usa polling (long polling) en vez de webhook. No requiere SSL, IP pública ni dominio.

**Migración a producción:** Cambiar a webhook es una línea de configuración. El endpoint `POST /telegram/webhook` ya está implementado y funcional.

### 14.5 Router con 9 targets (incluye meta + tool)

**Cambio:** El router ahora clasifica en 9 destinos (antes 7):
- `asset`, `event`, `list_item`, `note`, `meta`, `search`, `correction`, `shared_expense`, `tool`

**Meta:** Preguntas sobre Lucho mismo ("¿qué puedes hacer?"). Sin keywords manuales — el LLM decide.
**Tool:** Acciones externas (consultar multas, verificar trámites).

### 14.6 Stack tecnológico actualizado

| Componente | v1.6 (especificado) | v1.7 (implementado) |
|------------|---------------------|---------------------|
| LLM Router | Claude Haiku | DeepSeek-chat (configurable) |
| LLM Extractor | Claude Sonnet | DeepSeek-chat (configurable) |
| Mensajería dev | Webhook + SSL | Polling (sin infraestructura) |
| Tools externas | No contemplado | Sistema de tools enchufable |
| Respuestas | Datos crudos | Conversacionales (LLM) |
| Embeddings | pgvector | OpenAI text-embedding-3-small (opcional) |

### 14.7 Riesgos identificados y mitigaciones

| # | Riesgo | Mitigación |
|---|--------|------------|
| R1 | DeepSeek sin embeddings nativos | Embeddings vía OpenAI (opcional, `EMBEDDING_PROVIDER=none` por defecto). Alternativa: sentence-transformers local gratuito. Búsqueda ILIKE como fallback siempre disponible. |
| R2 | LLM puede alucinar al explicar datos | El prompt instruye "NUNCA inventes información que no está en los datos". Si alucina, la confirmación editable permite corregir. Auditoría: toda respuesta se guarda en `messages.extraction_result`. |
| R3 | API externa falla o cambia | Cada tool tiene timeout + error handling + fallback simulado en dev. El usuario ve "Error al consultar [servicio]. Intentá más tarde." |
| R4 | 9 targets = más clasificaciones erróneas | La confirmación editable es la red de seguridad. Métricas de precisión del router en beta (Fase 2). Iteración de prompts, no reentrenamiento. |
| R5 | Tools rompen guardrail "solo datos del usuario" | Las tools SOLO consultan información del usuario (sus multas, su placa, su RUC). No son búsquedas abiertas. Principio: "consulta sobre tus datos en sistemas externos", no "búsqueda genérica". |
| R6 | Costo extra por respuesta contextual | ~$0.0003 por mensaje adicional. Se usa el modelo barato (router_model) para formateo. Ajustable por feature flag. |
| R7 | Polling → Webhook en producción | El código de webhook está listo y probado. Migrar es cambiar `run_bot.py` por configurar el webhook en Telegram + Traefik para SSL. |
