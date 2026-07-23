# Plan de estabilización técnica de Lucho

**Fecha de preparación:** 2026-07-23  
**Versión revisada:** v2.24.5  
**Objetivo:** estabilizar la base técnica antes de continuar con nuevas funcionalidades o ampliar la beta.

---

## 1. Resultado esperado

Al finalizar esta ola de trabajo, Lucho debe cumplir lo siguiente:

- Los flujos principales del agente no presentan errores de runtime conocidos.
- Los webhooks de pago rechazan solicitudes no autenticadas.
- Los endpoints internos no están disponibles públicamente en producción.
- Toda la aplicación respeta la política de hora local de Ecuador definida en `AGENTS.md`.
- Existen pruebas que ejecutan handlers reales con base de datos, no solo validaciones de esquemas y textos.
- Ruff no reporta errores.
- La versión mostrada por la API y la documentación coincide con el tag Git.
- `ROADMAP.md`, `PROGRESS.md` y `NEXT_SESSION.md` reflejan el estado real.

---

## 2. Diagnóstico de partida

### Validaciones ejecutadas

| Validación | Resultado |
|------------|-----------|
| Estado Git | Limpio, rama `main` |
| Tag en `HEAD` | `v2.24.5` |
| Compilación Python | Correcta con `python3 -m compileall` |
| Suite unitaria declarada | 512/512 aprobadas |
| Ruff | 137 errores |
| Archivos sensibles rastreados por nombre | No detectados |

### Limitación importante de las pruebas actuales

Las 512 pruebas verifican principalmente estructura del prompt, schemas de tools, presencia de handlers y contenido de skills. No ejecutan de forma suficiente los flujos reales contra base de datos. Por eso no detectaron nombres indefinidos encontrados por Ruff ni problemas de seguridad en endpoints.

---

## 3. Orden de trabajo recomendado

No desarrollar módulos nuevos hasta cerrar, como mínimo, los bloques P0 y P1.

1. **P0: cerrar vulnerabilidades de endpoints y pagos.**
2. **P0: corregir errores de runtime en tools.**
3. **P1: unificar la política temporal de Ecuador.**
4. **P1: crear pruebas reales de integración.**
5. **P1: dejar Ruff en cero.**
6. **P2: sincronizar versión y documentación.**
7. Ejecutar regresión completa y preparar una versión de estabilización.

---

## 4. P0 — Seguridad de endpoints

### 4.1 Proteger el webhook DeUna

**Problema:** `app/routers/deuna_webhook.py` declara que valida firmas, pero actualmente procesa el JSON sin autenticar el origen. Una referencia de pago válida podría utilizarse para intentar activar una suscripción.

**Tareas:**

- Confirmar el mecanismo oficial de firma o autenticación de DeUna para webhooks.
- Implementar la validación en `app/services/deuna.py` o en un servicio dedicado.
- Validar la firma usando el cuerpo crudo de la solicitud.
- Rechazar firmas ausentes o inválidas con HTTP `401`.
- Comparar firmas con una función resistente a ataques de temporización.
- Validar también el monto, moneda y referencia contra el pago pendiente almacenado.
- Evitar que una misma confirmación se procese dos veces.
- No registrar secretos ni cuerpos completos con datos personales.

**Criterios de aceptación:**

- Solicitud sin firma: HTTP `401`.
- Firma inválida: HTTP `401`.
- Firma válida y referencia inexistente: respuesta controlada sin activación.
- Firma válida pero monto o moneda incorrectos: no activa la suscripción.
- Reenvío del mismo evento: resultado idempotente, sin duplicar factura o notificación.
- Pruebas automatizadas para todos los casos anteriores.

> Si DeUna no ofrece una firma verificable, usar un secreto de webhook acordado con el proveedor y documentar claramente la limitación. No inventar un esquema criptográfico sin confirmar la documentación oficial.

### 4.2 Restringir `/internal/test-reminder`

**Problema:** `app/routers/internal_test.py` se monta siempre, no exige autenticación, crea eventos reales y contiene un número de WhatsApp por defecto.

**Tareas:**

- No incluir el router interno cuando `DEBUG=false`.
- Añadir una segunda barrera mediante token interno si debe mantenerse accesible en desarrollo remoto.
- Eliminar el número de WhatsApp predeterminado.
- Evitar que Swagger/OpenAPI de producción publique rutas internas.
- Añadir pruebas de disponibilidad por entorno.

**Criterios de aceptación:**

- En producción, `/internal/test-reminder` responde `404`.
- En desarrollo, requiere datos explícitos y autenticación si se accede remotamente.
- Ningún identificador personal queda escrito en el código.

### 4.3 Revisar los demás webhooks

- Confirmar que PayPhone mantiene validación HMAC obligatoria.
- Revisar idempotencia, monto, moneda, estado y referencia en PayPhone y DeUna.
- Comprobar que los errores no revelan secretos ni información financiera.

---

## 5. P0 — Errores de runtime en tools

### Problema

Ruff detectó usos de `select()` sin importación en `app/agent/tools.py`. Esto afecta varios handlers, incluidos flujos de vehículos, y puede producir `NameError` en producción.

### Tareas

- Importar `select` de SQLAlchemy de forma consistente.
- Revisar todos los errores `F821` antes de atender problemas de estilo.
- Ejecutar directamente cada handler afectado con una sesión de prueba.
- Revisar funciones de vehículos, suscripciones, listas, documentos, finanzas y facturación.
- Confirmar que todos los handlers filtran por `user_id` para mantener aislamiento multi-tenant.

### Criterios de aceptación

- Ruff no reporta `F821`.
- Cada una de las 45 tools tiene una prueba que llega hasta su handler o una justificación explícita si depende de un servicio externo.
- Los handlers principales se ejecutan contra PostgreSQL de pruebas.
- Una cuenta no puede leer ni modificar datos de otra cuenta.

---

## 6. P1 — Política de hora local Ecuador

### Problema

El código conserva una función `utcnow()`, usos de `datetime.now(timezone.utc)` y columnas `DateTime(timezone=True)`. Esto contradice la regla no negociable de `AGENTS.md`: hora local de Ecuador, sin conversiones de zona horaria en la aplicación.

### Archivos iniciales a revisar

- `app/models/base.py`
- `app/models/event.py`
- `app/models/reminder.py`
- `app/models/subscription.py`
- `app/models/billing.py`
- `app/routers/internal_test.py`
- `app/routers/deuna_webhook.py`
- `app/routers/payphone_webhook.py`
- `app/services/scheduler.py`
- Migraciones de Alembic

### Decisión previa necesaria

Antes de modificar masivamente los timestamps, confirmar el alcance exacto de la política:

1. `events.target_date` debe mantenerse como `TIMESTAMP WITHOUT TIME ZONE` y datetime naive de Ecuador.
2. Determinar si la regla también exige que timestamps técnicos como `created_at`, `paid_at` y fechas de autorización SRI sean naive locales.
3. Documentar una única convención y aplicarla de forma uniforme.

Según el texto actual de `AGENTS.md`, la intención es no usar UTC en la capa de aplicación. La implementación debe ajustarse a esa regla salvo decisión explícita de arquitectura que actualice primero la documentación.

### Criterios de aceptación

- No existen usos no justificados de `timezone.utc`, `utcnow`, `astimezone()` o `replace(tzinfo=...)`.
- `schedule_event_reminder()` utiliza `datetime.now()` y `DateTrigger` sin timezone.
- Los tests comprueban recordatorios alrededor de medianoche, cambio de día y ventanas sub-día.
- PostgreSQL, el sistema operativo y APScheduler están configurados para `America/Guayaquil`.
- Las migraciones preservan los datos existentes y tienen estrategia de reversión.

---

## 7. P1 — Fortalecer la estrategia de pruebas

### Problemas actuales

- `tests/unit.py` es un script propio, no una suite convencional de pytest.
- Una validación contiene `or True`, por lo que nunca puede fallar.
- La suite no detectó nombres indefinidos en handlers.
- `tests/suite.py` depende de servidor, LLM y servicios reales, y valida principalmente el estado del webhook.

### Tareas

- Adoptar `pytest` y `pytest-asyncio`.
- Separar pruebas en:
  - `tests/unit/`
  - `tests/integration/`
  - `tests/e2e/`
- Crear fixtures de PostgreSQL y Redis de pruebas.
- Mockear proveedores externos: Meta, Telegram, PayPhone, DeUna, Key49, OpenAI, Anthropic y DeepSeek.
- Probar handlers directamente, sin depender del LLM.
- Eliminar afirmaciones triviales como `or True`.
- Añadir cobertura para seguridad, multi-tenant, scheduler y transacciones.
- Configurar un comando único de validación local y CI.

### Casos mínimos obligatorios

- Guardar, listar, actualizar y eliminar entidades.
- Aislamiento entre dos usuarios.
- Duplicados e idempotencia.
- Fallos y timeouts de servicios externos.
- Webhooks con firmas válidas e inválidas.
- Recordatorios diarios y sub-día.
- Fechas límite alrededor de medianoche.
- Correcciones mediante `update_last`.
- Límites por plan de suscripción.
- Rollback ante fallos parciales.

### Criterios de aceptación

- Los errores de runtime intencionalmente introducidos en un handler provocan fallo de prueba.
- Las pruebas no llaman servicios externos reales por defecto.
- Existe un comando documentado que ejecuta lint y pruebas.
- La suite produce código de salida distinto de cero cuando falla una validación.

---

## 8. P1 — Ruff y calidad estática

### Estado inicial

`ruff check app tests scripts` reporta **137 errores**, incluidos:

- `F821`: nombres indefinidos.
- `F841`: variables asignadas pero no utilizadas.
- `F401`: imports no utilizados.
- `E712`: comparaciones booleanas no idiomáticas.
- `E741`: nombres ambiguos.
- `F541`: f-strings sin placeholders.
- Problemas de orden de imports en scripts de prueba.

### Estrategia

1. Corregir manualmente primero `F821` y cualquier error con impacto en runtime.
2. Ejecutar pruebas.
3. Aplicar correcciones seguras de Ruff para imports y estilo.
4. Revisar el diff antes de aceptar cambios automáticos.
5. Corregir manualmente el código muerto y nombres ambiguos.
6. Añadir configuración de Ruff a `pyproject.toml`.

### Criterios de aceptación

```bash
ruff check app tests scripts
```

Debe finalizar con código `0` y sin errores. No usar `# noqa` para ocultar fallos reales sin justificación documentada.

---

## 9. P2 — Versionado y documentación

### Inconsistencias detectadas

- Git está en `v2.24.5`.
- Los documentos principales todavía destacan `v2.24.1`.
- `.env.example` declara `APP_VERSION=0.4.0`.
- `app/config.py` usa `APP_VERSION=0.1.0` por defecto.
- Existen diferencias entre documentos sobre número de tablas, specs, proveedor de WhatsApp y fase actual.

### Tareas

- Definir una única fuente de verdad para la versión.
- Hacer que `/` y OpenAPI reporten la versión del release actual.
- Sincronizar `ROADMAP.md`, `PROGRESS.md` y `NEXT_SESSION.md`.
- Revisar el número real de tablas, migraciones, tools, tests y specs.
- Corregir referencias obsoletas a 360dialog si la implementación vigente usa Meta Cloud API.
- Registrar la estabilización en una versión semántica nueva.

### Criterios de aceptación

- Tag Git, API, `.env.example` y documentos muestran una versión coherente.
- Las métricas documentales se generan o verifican mediante comandos reproducibles.
- No quedan contradicciones conocidas entre arquitectura documentada e implementación.

---

## 10. Dependencias y entorno reproducible

### Tareas

- Añadir dependencias de desarrollo separadas o grupos en `pyproject.toml`.
- Fijar rangos suficientemente controlados para evitar actualizaciones incompatibles.
- Incluir Ruff, pytest y pytest-asyncio.
- Documentar Python soportado.
- Comprobar instalación limpia en entorno virtual.
- Evaluar CI para ejecutar lint y pruebas en cada push o pull request.

### Criterios de aceptación

Una instalación limpia puede ejecutar:

```bash
python3 -m compileall -q app tests scripts
ruff check app tests scripts
pytest
```

sin depender de configuración personal del desarrollador.

---

## 11. Plan sugerido para la sesión de mañana

### Bloque 1 — Seguridad

- [ ] Proteger o desactivar el router interno en producción.
- [ ] Eliminar el número personal predeterminado.
- [ ] Implementar validación verificable del webhook DeUna.
- [ ] Añadir controles de monto, moneda e idempotencia.

### Bloque 2 — Runtime

- [ ] Corregir todos los `F821`.
- [ ] Añadir pruebas de ejecución para handlers afectados.
- [ ] Ejecutar una regresión rápida de tools principales.

### Bloque 3 — Calidad

- [ ] Corregir el resto de errores Ruff.
- [ ] Eliminar la prueba con `or True`.
- [ ] Crear la base de pytest para seguridad y handlers.

### Bloque 4 — Tiempo y documentación

- [ ] Confirmar el alcance de la convención temporal.
- [ ] Preparar migración segura si corresponde.
- [ ] Sincronizar versión y documentos después de validar el código.

---

## 12. Comandos de control

```bash
# Estado inicial
git status --short --branch
git describe --tags --exact-match HEAD

# Sintaxis
python3 -m compileall -q app tests scripts

# Calidad estática
ruff check app tests scripts

# Suite actual
python3 tests/unit.py

# Suite nueva, cuando se migre a pytest
pytest -q

# Confirmar que no se introdujeron conversiones prohibidas
grep -RInE 'timezone\.utc|utcnow|astimezone\(|replace\(tzinfo=' app

# Revisar cambios antes del commit
git diff --check
git diff --stat
git status --short
```

---

## 13. Definición de terminado de la estabilización

La estabilización se considera completa únicamente cuando:

- [ ] Los webhooks de pago tienen autenticación, validación de datos e idempotencia probadas.
- [ ] Las rutas internas no están expuestas en producción.
- [ ] No hay errores `F821` ni fallos conocidos de runtime.
- [ ] Ruff termina sin errores.
- [ ] Las tools principales tienen pruebas de ejecución con aislamiento multi-tenant.
- [ ] La política de hora Ecuador está aplicada y probada de extremo a extremo.
- [ ] La suite completa pasa desde una instalación limpia.
- [ ] La API y la documentación muestran la versión correcta.
- [ ] `PROGRESS.md` y `NEXT_SESSION.md` registran los resultados reales.
- [ ] Se crea un tag semántico para la versión estabilizada.

---

## 14. Regla para esta ola

**No añadir nuevas funcionalidades mientras existan vulnerabilidades P0, errores de runtime conocidos o inconsistencias temporales capaces de afectar recordatorios y pagos.** Primero se estabiliza, luego se continúa con Fase 3.
