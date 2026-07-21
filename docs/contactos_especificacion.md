# Módulo de Contactos — Especificación v1.0

---

## 1. Visión General

Lucho guarda y organiza los contactos personales del usuario: nombres, teléfonos, relaciones, y datos de contacto. El usuario dicta la información naturalmente y Lucho la archiva para consulta rápida. En el futuro, los contactos podrán vincularse a gastos compartidos, recordatorios y al modo cuidado (caregiver).

---

## 2. Experiencia de Usuario

### 2.1 Guardar un contacto

> **Usuario**: "contacto: Juan Pérez, teléfono 0991234567, es mi primo"
>
> **Lucho**: "Listo. Guardé a Juan Pérez — primo, 0991234567."

> **Usuario**: "agrega a María, email maria@email.com, es del trabajo"
>
> **Lucho**: "Anotado. María, colega del trabajo, maria@email.com."

### 2.2 Consultar contactos

> **Usuario**: "¿qué contactos tengo?"
>
> **Lucho**: "Tenés 3 contactos:\n👤 Juan Pérez — primo, 0991234567\n👤 María — colega, maria@email.com\n👤 Dr. López — médico, 0998887776"

> **Usuario**: "busca el contacto de Juan"
>
> **Lucho**: "Juan Pérez — primo. Tel: 0991234567."

---

## 3. Modelo de Datos

### 3.1 Tabla `contacts`

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | UUID | PK |
| `user_id` | UUID FK | Dueño |
| `name` | VARCHAR(256) | Nombre completo |
| `phone_number` | VARCHAR(32) | Teléfono |
| `email` | VARCHAR(256) | Correo electrónico |
| `telegram_id` | VARCHAR(64) | Usuario de Telegram |
| `whatsapp_id` | VARCHAR(64) | Número WhatsApp |
| `relationship` | VARCHAR(64) | "friend", "family", "colleague", "parent", etc. |
| `is_emergency_contact` | BOOLEAN | Contacto de emergencia |
| `contact_notes` | VARCHAR(512) | Notas adicionales |
| `created_at` | TIMESTAMPTZ | Fecha creación |
| `updated_at` | TIMESTAMPTZ | Última modificación |

### 3.2 Tabla `caregiver_links` (modo cuidado — futuro)

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | UUID | PK |
| `caregiver_user_id` | UUID FK | Usuario cuidador |
| `cared_for_user_id` | UUID FK | Usuario a cargo |
| `cared_for_contact_id` | UUID FK | Contacto relacionado |
| `is_active` | BOOLEAN | ¿Vínculo activo? |
| `created_at` | TIMESTAMPTZ | Fecha creación |
| `updated_at` | TIMESTAMPTZ | Última modificación |

---

## 4. Tools del Agente

### 4.1 `save_contact` — Ya existe ✅

```json
{
  "name": "save_contact",
  "description": "Guardar un contacto personal: nombre, teléfono, email, relación.",
  "parameters": {
    "name": "Nombre completo del contacto.",
    "phone_number": "Número de teléfono.",
    "email": "Correo electrónico.",
    "relationship": "'friend', 'family', 'colleague', 'parent', 'partner', 'other'.",
    "notes": "Notas adicionales."
  },
  "required": ["name"]
}
```

### 4.2 `list_contacts` — Ya existe ✅

```json
{
  "name": "list_contacts",
  "description": "Listar todos los contactos guardados del usuario.",
  "parameters": {},
  "required": []
}
```

---

## 5. Formato de Respuesta

```
👤 *Contactos*

  Juan Pérez — primo
  📞 0991234567

  María — colega
  📧 maria@email.com

  Dr. López — médico
  📞 0998887776
```

---

## 6. Reglas de Negocio

1. **Nombre único**: No duplicar contactos con el mismo nombre. Si ya existe, actualizar datos.
2. **Datos parciales**: Solo el nombre es requerido. Teléfono, email, etc. son opcionales.
3. **Relación libre**: `relationship` es texto libre, no ENUM. El LLM normaliza según contexto.

---

## 7. Lo que YA existe

| Componente | Estado |
|------------|--------|
| `contacts` tabla | ✅ |
| `caregiver_links` tabla | ✅ |
| `save_contact` tool | ✅ |
| `list_contacts` tool | ✅ |

---

## 8. Mejoras pendientes

| Tarea | Prioridad |
|-------|-----------|
| Tool `search_contact` (buscar por nombre parcial) | 🟡 Media |
| Tool `delete_contact` | 🟢 Baja |
| Vincular contactos a shared expenses | 🟢 Baja |
| Modo cuidado (caregiver_links funcional) | ⚪ Futuro |
| Importar contactos del teléfono | ⚪ Futuro |
