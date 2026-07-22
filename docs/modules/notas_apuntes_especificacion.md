# Módulo de Notas y Apuntes — Especificación v1.0

---

## 1. Visión General

Lucho guarda notas, apuntes, ideas e información libre del usuario, organizada por temas. A diferencia de las listas (accionables, con estado pendiente/hecho), las notas son información de referencia: datos que el usuario quiere recordar, consultar o recuperar después. El usuario dicta la nota, Lucho la archiva bajo un tema, y la encuentra al instante cuando la necesita.

---

## 2. Experiencia de Usuario

### 2.1 Guardar una nota

> **Usuario**: "anota: el WiFi de la oficina es AURACORE2024 y la clave es Lucho123"
>
> **Lucho**: "Anotado en tecnología. WiFi oficina guardado."

> **Usuario**: "apunta una idea de negocio: delivery de almuerzos saludables para oficinas en Quito"
>
> **Lucho**: "¡Qué buena idea! La guardé en ideas de negocio. ¿Querés que le agregue algo más?"

> **Usuario**: "receta de locro de papas: papas, queso, aguacate, cebolla, ajo, comino, leche"
>
> **Lucho**: "Guardada la receta de locro de papas en cocina. 7 ingredientes."

### 2.2 Buscar una nota

> **Usuario**: "¿cuál es el WiFi de la oficina?"
>
> **Lucho**: "WiFi: AURACORE2024 / Clave: Lucho123. Lo anotaste en tecnología."

> **Usuario**: "busca mis ideas de negocio"
>
> **Lucho**: "Tenés 3 ideas de negocio guardadas:\n💡 Delivery de almuerzos saludables\n💡 Tienda online de artesanías\n💡 Consultoría de marketing digital"

> **Usuario**: "¿cómo se hace el locro de papas?"
>
> **Lucho**: "Tu receta de locro: papas, queso, aguacate, cebolla, ajo, comino, leche. La guardaste en cocina."

### 2.3 Notas con foto

> **Usuario**: *[envía foto de una pizarra con ideas]* "guarda esto como ideas para el proyecto"
>
> **Lucho**: "Guardé la foto en ideas para el proyecto. ¿Querés que le agregue texto descriptivo?"

---

## 3. Modelo de Datos

### 3.1 Tabla `topics`

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | UUID | PK |
| `user_id` | UUID FK | Dueño |
| `name` | VARCHAR(256) | Nombre del tema: "tecnología", "ideas de negocio", "cocina" |
| `created_at` | TIMESTAMPTZ | Fecha creación |
| `updated_at` | TIMESTAMPTZ | Última modificación |

**Índice único**: `idx_topics_user_name` sobre (`user_id`, `name`). Un usuario no puede tener dos temas con el mismo nombre.

**Relación**: 1 tema → N notas (`notes`)

### 3.2 Tabla `notes`

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | UUID | PK |
| `topic_id` | UUID FK | Tema al que pertenece |
| `content` | TEXT | Contenido completo de la nota |
| `embedding` | VECTOR(1024) | pgvector para búsqueda semántica |
| `source_message_id` | UUID FK nullable | Mensaje origen (trazabilidad) |
| `created_at` | TIMESTAMPTZ | Fecha creación |
| `updated_at` | TIMESTAMPTZ | Última modificación |

**Índice**: `idx_notes_embedding` HNSW sobre `embedding` para búsqueda semántica rápida.

### 3.3 ¿Cómo se relacionan `topics` y `notes`?

```
topics                         notes
┌──────────────────┐          ┌──────────────────────────┐
│ id: abc-123      │───<     │ id: n1                   │
│ user_id: pato    │          │ topic_id: abc-123        │
│ name: "cocina"   │          │ content: "Receta locro:  │
└──────────────────┘          │   papas, queso,..."      │
                              │ embedding: [0.1, -0.3...]│
                              └──────────────────────────┘
```

- **Sin estado**: Las notas no tienen `status` (a diferencia de `list_items`). Son solo texto.
- **Sin fecha de vencimiento**: No generan recordatorios.
- **Búsqueda semántica**: `pgvector` encuentra notas por significado, no solo por keyword.

---

## 4. Tools del Agente

### 4.1 `save_note` — Ya existe ✅

```json
{
  "name": "save_note",
  "description": "Guardar una nota, idea, apunte o información libre del usuario, organizada por tema. Si el tema no existe, se crea automáticamente.",
  "parameters": {
    "topic": "Tema o categoría. Ej: 'tecnología', 'ideas de negocio', 'cocina', 'general'. Si no es claro, usar 'general'.",
    "content": "Contenido completo de la nota.",
    "file_key": "Clave MinIO si el usuario adjuntó foto."
  },
  "required": ["topic", "content"]
}
```

### 4.2 `search_my_data` — Ya existe ✅ (busca notas)

La búsqueda semántica con `search_my_data` ya incluye `notes` en los resultados. Cuando el usuario pregunta "¿cuál es mi WiFi?", el pgvector encuentra la nota relevante.

### 4.3 `list_my_notes` — 🆕 Nueva (propuesta)

```json
{
  "name": "list_my_notes",
  "description": "Listar notas del usuario, por tema o todas. Usar cuando pregunta '¿qué notas tengo?', 'mis apuntes de cocina', '¿qué ideas guardé?'.",
  "parameters": {
    "topic": "Filtrar por tema. Si no se pasa, muestra todas las notas agrupadas por tema."
  },
  "required": []
}
```

---

## 5. Búsqueda de Notas

### 5.1 Búsqueda semántica (pgvector)

Las notas tienen embeddings generados por el modelo configurado. La búsqueda `semantic_search()` en `app/services/search.py` incluye `notes`:

```python
# Búsqueda en notas por similitud de coseno
select(Note.id, Note.content, ...)
  .where(Note.embedding.isnot(None))
  .order_by(Note.embedding.cosine_distance(query_embedding))
```

### 5.2 Búsqueda por texto (ILIKE)

También soporta búsqueda textual para keywords exactas:

```python
Note.content.ilike(f"%{query}%")
```

### 5.3 Flujo de búsqueda típico

```
Usuario: "¿cuál es el WiFi?"
  ↓
LLM: search_my_data("WiFi oficina")
  ↓
search.py: pgvector cosine_similarity sobre notes.embedding
  ↓
Resultado: nota "WiFi AURACORE2024 / Lucho123" (similitud 0.92)
  ↓
LLM: "Tu WiFi es AURACORE2024, clave Lucho123. Guardado en tecnología."
```

---

## 6. Scheduler

**No aplica.** Las notas no tienen fechas ni estados. Son información estática de referencia. No hay recordatorios ni notificaciones para notas.

---

## 7. Formato de Respuesta

WhatsApp: simple con emojis, sin tablas:

```
📝 *Tecnología*

  🔐 WiFi oficina: AURACORE2024 / Lucho123
  💻 IP impresora: 192.168.1.50
  📧 Correo soporte: help@aura-core.com

🍳 *Cocina*

  🥣 Receta locro: papas, queso, aguacate, cebolla...
```

---

## 8. Reglas de Negocio

1. **Tema único por nombre**: `idx_topics_user_name` garantiza que un usuario no tenga dos temas iguales. Si se guarda en "cocina" y ya existe, se agrega la nota al tema existente.
2. **Tema "general" como fallback**: Si el LLM no puede determinar el tema, usa `"general"`.
3. **Sin estado**: Las notas no se completan ni cancelan. Si el usuario quiere eliminar una nota, se usa soft delete.
4. **Contenido libre**: No hay límite de estructura. Puede ser texto, números, listas informales.
5. **Embeddings automáticos**: Al guardar una nota, se genera automáticamente el embedding para búsqueda semántica.
6. **Foto adjunta**: `file_key` en el JSONB de la nota permite vincular imágenes a notas.

---

## 9. Lo que YA existe

| Componente | Estado |
|------------|--------|
| `topics` + `notes` tablas | ✅ |
| `save_note` tool — con `file_key` para vincular fotos | ✅ |
| `list_my_notes` tool — listar notas agrupadas por tema | ✅ |
| `delete_note` tool — eliminar nota por tema + búsqueda de contenido | ✅ |
| `semantic_search()` con pgvector | ✅ |
| Búsqueda textual ILIKE | ✅ |
| `persist_note()` crea tema si no existe + embebe file_key en contenido | ✅ |
| Embeddings automáticos | ✅ |
| Índice HNSW en `notes.embedding` | ✅ |

---

## 10. Mejoras pendientes

| Tarea | Prioridad |
|-------|-----------|
| Notas con formato enriquecido (listas, bullets) | 🟢 Baja |
| Exportar notas a PDF/texto | ⚪ Futuro |
