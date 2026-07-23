# Daily Digest — Especificación de Funcionalidad

**Módulo:** Resumen Matutino Diario  
**Versión del documento:** 1.0  
**Fecha:** 2026-07-23  
**Estado:** Parcialmente implementado — requiere ajustes de opt-in  

---

## 1. Descripción general

El Daily Digest es un resumen matutino diario que Lucho envía a cada usuario con
información relevante del día: pico y placa, eventos próximos, documentos por
vencer, y tareas pendientes. El mensaje es redactado en lenguaje natural por el
LLM, con tono cálido ecuatoriano.

Se ejecuta automáticamente a las **8:00 AM (hora Ecuador)** todos los días.

---

## 2. Principio de diseño

> **Regla no negociable (x3 en especificación del proyecto):**  
> "Todo digest/resumen proactivo es opt-in, nunca por defecto."

Extraído de `docs/lucho_especificaciones_proyecto.md`:
- Sección 6 (Mecanismo de comunicación): *"Todo digest/resumen proactivo es opt-in, nunca por defecto."*
- Sección 7 (Catálogo de funcionalidades): *"Resumen diario/semanal (opt-in)."*
- Sección 7 (Guardrails de producto): *"Todo digest/resumen proactivo es opt-in."*

---

## 3. Datos incluidos en el resumen

El digest recolecta los siguientes datos del usuario para construir el resumen
(vía `_build_digest()` en `app/services/scheduler.py`):

| Dato | Origen (tabla) | Ventana de tiempo | Condición |
|------|---------------|-------------------|-----------|
| 🚗 Vehículos y pico y placa | `vehicles` | Hoy (día de la semana) | Vehículo activo, no eliminado |
| 📅 Eventos próximos | `events` | Próximos 7 días | `status = 'upcoming'` |
| 📄 Documentos por vencer | `documents` | Próximos 30 días | `expiry_date` no nula, no eliminado |
| 📝 Pendientes | `list_items` | Los 10 más recientes | `status = 'pending'` |

**Si el usuario no tiene ningún dato en ninguna de estas categorías, NO se envía el digest.**

---

## 4. Generación del mensaje

### 4.1 Construcción del prompt

El backend (`_build_digest()`) prepara un prompt estructurado con los datos
recolectados y lo envía al agente (`process_message`) para que el LLM redacte
el mensaje final.

**Instrucciones al LLM:**
- Saludo de buenos días
- Resumen breve y cálido
- Tono ecuatoriano
- Incluir emojis de urgencia (🔴 HOY, 🟡 ≤3 días, 🟢 >3 días)
- Si hoy es día de pico y placa, advertir explícitamente (⚠️)

### 4.2 Ejemplo de salida esperada

```
☀️ ¡Buenos días, Patricio! Feliz jueves.

⚠️ Hoy tu Kia Sportage (GHI-7890) tiene pico y placa. No circula de 7:00 a 9:30 ni de 16:00 a 19:30.

📅 Tenés 2 cosas esta semana:
  🔴 Cita con el dentista — HOY a las 4pm
  🟡 Reunión de trabajo — viernes 9am

📄 Recordá: tu cédula vence en 18 días

📝 Pendientes:
  • Comprar arroz
  • Llamar a mamá

¡Que tengas un excelente día! 🇪🇨
```

---

## 5. Canales de envío

| Canal | Método | Template / Formato |
|-------|--------|-------------------|
| WhatsApp | `send_template_message()` | `daily_digest` (UTILITY, es) |
| Telegram | `send_message()` | Texto libre (sin restricciones de template) |

### 5.1 Template WhatsApp — `daily_digest`

| Campo | Valor |
|-------|-------|
| Nombre | `daily_digest` |
| Categoría | `UTILITY` |
| Idioma | `es` (Spanish) |
| Estado Meta | ✅ Aprobado |
| Header | "Resumen diario ☀️" |
| Body | `☀️ Tu resumen de hoy:\n\n{{1}}\n\n— Lucho` |

> Template de 1 variable de body. Sin CTAs para mantener categoría UTILITY.

---

## 6. Opt-in / Opt-out

### 6.1 Estado actual (v2.24.8)

El digest se envía a **todos los usuarios con `is_active = True`**, sin verificar
preferencia. Esto **viola la regla de opt-in** definida en la especificación
del proyecto.

### 6.2 Estado deseado

| Funcionalidad | Descripción |
|---------------|-------------|
| Campo en BD | `daily_digest_enabled BOOLEAN DEFAULT FALSE` en `user_profiles` |
| Tool | `set_daily_digest(enabled: bool)` para que el usuario active/desactive |
| Filtro en scheduler | Solo usuarios con `daily_digest_enabled = TRUE` |
| Activación inicial | Preguntar al final del onboarding si quiere recibir el resumen |
| Mensaje de activación | "☀️ ¿Querés que te mande un resumen cada mañana con tu día?" |
| Desactivación | "Perfecto, no te molesto más con el resumen. Si cambiás de opinión, decime." |

### 6.3 Flujo de opt-in en onboarding

```
Paso actual: nombre → acento → trial → FIN
Paso propuesto: nombre → acento → trial → ¿resumen diario? (SÍ/NO) → FIN
```

Si el usuario responde SÍ: `daily_digest_enabled = TRUE`.  
Si responde NO: `daily_digest_enabled = FALSE` (default).  
Si no responde (timeout): `daily_digest_enabled = FALSE`.

---

## 7. Modelo de datos

### 7.1 Tabla `user_profiles` — nueva columna

```sql
ALTER TABLE user_profiles
ADD COLUMN daily_digest_enabled BOOLEAN NOT NULL DEFAULT FALSE;
```

### 7.2 Tool schema — `set_daily_digest`

```json
{
    "name": "set_daily_digest",
    "description": "Activar o desactivar el resumen matutino diario. El usuario dice 'avisame cada mañana' o 'no me mandes más resúmenes'.",
    "parameters": {
        "type": "object",
        "properties": {
            "enabled": {
                "type": "boolean",
                "description": "True para activar, False para desactivar"
            }
        },
        "required": ["enabled"]
    }
}
```

### 7.3 Tool handler — `handle_set_daily_digest`

```python
async def handle_set_daily_digest(session, user_id, arguments):
    enabled = arguments["enabled"]
    # Get or create UserProfile
    profile = await get_or_create_profile(session, user_id)
    profile.daily_digest_enabled = enabled
    await session.flush()
    
    if enabled:
        return {"text": "☀️ ¡Listo! Te mandaré un resumen cada mañana a las 8am con tu pico y placa, eventos, y pendientes."}
    else:
        return {"text": "Entendido. No te enviaré más el resumen diario. Si cambiás de opinión, solo decime 'activa el resumen'."}
```

---

## 8. Cambios en el scheduler

### 8.1 `run_daily_digest()` — filtro de opt-in

```python
async def run_daily_digest():
    # ... existing code ...
    
    # ANTES: todos los usuarios activos
    # result = await session.execute(select(User).where(User.is_active == True))
    
    # DESPUÉS: solo usuarios con opt-in explícito
    result = await session.execute(
        select(User)
        .join(UserProfile, User.id == UserProfile.user_id)
        .where(
            User.is_active == True,
            UserProfile.daily_digest_enabled == True,
        )
    )
    users = result.scalars().all()
    # ... resto igual ...
```

### 8.2 `get_or_create_profile()` — helper nuevo

```python
async def get_or_create_profile(session, user_id):
    """Get or create a UserProfile for a user."""
    result = await session.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        profile = UserProfile(user_id=user_id)
        session.add(profile)
        await session.flush()
    return profile
```

---

## 9. Tests necesarios

| # | Test | Tipo |
|---|------|------|
| 1 | Usuario con `daily_digest_enabled = TRUE` recibe digest | Integración |
| 2 | Usuario con `daily_digest_enabled = FALSE` NO recibe digest | Integración |
| 3 | Usuario sin `UserProfile` NO recibe digest (default FALSE) | Integración |
| 4 | `_build_digest()` devuelve `None` si no hay datos | Unitario |
| 5 | Tool `set_daily_digest` activa correctamente | Integración |
| 6 | Tool `set_daily_digest` desactiva correctamente | Integración |
| 7 | Template WhatsApp `daily_digest` se renderiza con 1 variable | Unitario |
| 8 | Migración Alembic crea columna `daily_digest_enabled` | Unitario |

---

## 10. Documentos relacionados

| Documento | Relación |
|-----------|----------|
| `docs/lucho_especificaciones_proyecto.md` §6, §7 | Regla de opt-in, funcionalidad en núcleo transversal |
| `docs/funcionalidades_generales.md` §7.2 | `get_my_summary` — resumen on-demand (separado del digest) |
| `docs/whatsapp_templates.md` §Template 4 | Template `daily_digest` aprobado en Meta |
| `app/services/scheduler.py` L827-978 | Implementación actual (`run_daily_digest`, `_build_digest`) |
| `app/models/user_profile.py` | Modelo donde se agrega `daily_digest_enabled` |

---

## 11. Checklist de implementación

- [ ] 1. Agregar `daily_digest_enabled` a `UserProfile` (modelo)
- [ ] 2. Migración Alembic para la nueva columna
- [ ] 3. Tool `set_daily_digest` en `app/agent/tools.py`
- [ ] 4. Handler `handle_set_daily_digest` en `app/agent/tools.py`
- [ ] 5. `get_or_create_profile()` helper en `app/services/user.py`
- [ ] 6. Filtro `daily_digest_enabled = TRUE` en `run_daily_digest()`
- [ ] 7. Pregunta de opt-in en onboarding (WhatsApp + Telegram)
- [ ] 8. Tests: 4 unitarios + 4 integración
- [ ] 9. Actualizar `ALL_TOOLS` count (45 → 46)
- [ ] 10. Actualizar docs: PROGRESS, ROADMAP, NEXT_SESSION
