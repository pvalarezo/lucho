# Módulo de Listas — Especificación v1.0

---

## 1. Visión General

Lucho organiza listas del usuario: compras, tareas pendientes, deseos, y cualquier colección de ítems con estado pendiente/hecho. El usuario dicta ítems naturalmente, Lucho los agrupa en listas, y permite consultar qué falta, qué ya se hizo, y marcar como completado.

---

## 2. Experiencia de Usuario

### 2.1 Crear una lista

> **Usuario**: "lista de compras: leche, pan, huevos, 2 libras de arroz"
>
> **Lucho**: "¡Listo! Agregué 4 ítems a tu lista de compras: leche, pan, huevos y arroz (2 libras)."

> **Usuario**: "apunta: llamar al banco, revisar el correo, pagar la luz"
>
> **Lucho**: "Anotado. 3 pendientes nuevos: llamar al banco, revisar el correo, pagar la luz."

### 2.2 Agregar ítems a una lista existente

> **Usuario**: "agrega cerveza y hielo a la lista de compras"
>
> **Lucho**: "Agregué cerveza y hielo a tu lista de compras. Ya tenés 6 ítems."

### 2.3 Consultar listas

> **Usuario**: "¿qué tengo en la lista de compras?"
>
> **Lucho**: "Lista de compras (4 pendientes):\n🥛 leche\n🍞 pan\n🥚 huevos\n🍚 arroz (2 libras)"

> **Usuario**: "¿qué tengo pendiente?"
>
> **Lucho**: "Tenés 7 pendientes:\n📋 Compras: leche, pan, huevos, arroz\n📋 Tareas: llamar al banco, revisar correo, pagar luz"

### 2.4 Marcar como completado

> **Usuario**: "ya compré la leche y el pan"
>
> **Lucho**: "Listo. Marqué leche y pan como comprados. Te faltan 2 en compras: huevos y arroz."

> **Usuario**: "completé todo lo de tareas"
>
> **Lucho**: "¡Bien! Las 3 tareas están completadas. ¿Querés que las archive o las dejo?"

---

## 3. Modelo de Datos

### 3.1 Tabla `lists`

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | UUID | PK |
| `user_id` | UUID FK | Dueño |
| `name` | VARCHAR(256) | Nombre: "compras", "tareas", "supermaxi" |
| `list_type` | ENUM | `shopping`, `tasks`, `generic` |
| `created_at` | TIMESTAMPTZ | Fecha creación |
| `updated_at` | TIMESTAMPTZ | Última modificación |

**Relación**: 1 lista → N ítems (`list_items`)

### 3.2 Tabla `list_items`

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | UUID | PK |
| `list_id` | UUID FK | Lista a la que pertenece |
| `content` | TEXT | Contenido del ítem: "leche", "llamar al banco" |
| `status` | ENUM | `pending`, `done` |
| `quantity` | VARCHAR(64) | "2 libras", "1 docena" |
| `created_at` | TIMESTAMPTZ | Cuándo se agregó |
| `completed_at` | TIMESTAMPTZ | Cuándo se completó |
| `embedding` | VECTOR(1024) | pgvector para búsqueda semántica |

**Índices**: `idx_list_items_list_status` sobre (`list_id`, `status`).

### 3.3 ENUMs

```sql
list_type: 'shopping', 'tasks', 'generic'
item_status: 'pending', 'done'
```

---

## 4. Tools del Agente

### 4.1 `save_list` — Ya existe ✅

```json
{
  "name": "save_list",
  "description": "Guardar ítems en una lista. Si la lista no existe, se crea automáticamente.",
  "parameters": {
    "list_name": "Nombre de la lista. Ej: 'compras', 'tareas', 'supermaxi'.",
    "items": ["leche", "pan", "huevos"],
    "quantity": "2 libras"
  },
  "required": ["list_name", "items"]
}
```

Si la lista ya existe → agrega ítems. Si no → la crea y agrega.

### 4.2 `list_items` — 🆕 Nueva (propuesta)

```json
{
  "name": "list_items",
  "description": "Consultar ítems de una lista específica o de todas. Usar cuando pregunta '¿qué tengo en compras?', 'mis pendientes', '¿qué me falta?'.",
  "parameters": {
    "list_name": "Nombre de la lista. Si no se pasa, muestra todas.",
    "status": "'pending', 'done', o 'all'. Default: 'pending'."
  },
  "required": []
}
```

### 4.3 `complete_item` — 🆕 Nueva (propuesta)

```json
{
  "name": "complete_item",
  "description": "Marcar uno o varios ítems como completados. Usar cuando dice 'ya compré X', 'marqué Y', 'completé Z'.",
  "parameters": {
    "list_name": "Lista donde buscar el ítem. Opcional (busca en todas).",
    "items": ["leche", "pan"],
    "mark_all": false
  },
  "required": ["items"]
}
```

**Alternativa**: El LLM puede usar `update_last` para modificar el estado del último ítem guardado, pero no escala para múltiples ítems.

---

## 5. Búsqueda de Listas

Ya funciona vía `search_my_data` con pgvector. Las consultas como "¿qué tengo pendiente?" ejecutan `list_pending_items()` que retorna ítems con `status = 'pending'`.

**Mejora pendiente**: La búsqueda semántica sobre `list_items.embedding` permite encontrar ítems por significado ("cosas del súper" → ítems de la lista "compras").

---

## 6. Scheduler

**No aplica.** Las listas no tienen fechas de vencimiento. Son colecciones de ítems con estado. No se envían recordatorios proactivos para listas.

Si en el futuro se agregan fechas de vencimiento a ítems individuales, se podría integrar con el scheduler existente (similar a `_evaluate_documents`).

---

## 7. Formato de Respuesta

Para WhatsApp, las listas usan formato simple con emojis (regla del system prompt v2.12.1):

```
📋 *Tus pendientes*

🛒 Compras (2):
  🥛 leche
  🍞 pan

📝 Tareas (1):
  ☎️ llamar al banco
```

**NUNCA tablas Markdown en WhatsApp.**

---

## 8. Reglas de Negocio

1. **Lista única por nombre**: No puede haber dos listas con el mismo nombre para el mismo usuario. Si se intenta crear "compras" y ya existe, se agregan ítems a la existente.
2. **Ítems sin duplicar**: Si el ítem con el mismo contenido ya existe en la lista y está `pending`, no duplicar. Preguntar si quiere agregar otra cantidad.
3. **Estado binario**: `pending` → `done`. No hay estados intermedios. Si el usuario dice "ya compré la leche", se marca `done`.
4. **Soft delete**: No implementado actualmente. Si se requiere, usar `deleted_at` en `lists`.
5. **Cantidad opcional**: `quantity` es informativo, no afecta lógica. "2 libras de arroz" → content="arroz", quantity="2 libras".

---

## 9. Lo que YA existe

| Componente | Estado |
|------------|--------|
| `lists` + `list_items` tablas | ✅ |
| `save_list` tool — create/update con prevención de duplicados | ✅ |
| `list_items` tool — consultar ítems por lista y status (pending/done/all) | ✅ |
| `complete_item` tool — marcar ítems como done (individual, múltiple, o mark_all) | ✅ |
| `delete_list` tool — eliminar lista completa con todos sus ítems | ✅ |
| `list_pending_items()` búsqueda | ✅ |
| pgvector en `list_items` | ✅ |
| Búsqueda semántica de ítems | ✅ |
| Prevención de duplicados — mismo contenido + pending en misma lista | ✅ |

---

## 10. Mejoras pendientes

| Tarea | Prioridad |
|-------|-----------|
| Ítems con fecha de vencimiento + recordatorios | 🟢 Baja |
| Compartir lista con otro usuario | ⚪ Futuro |
