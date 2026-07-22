# Módulo de Búsqueda — Especificación v1.0

---

## 1. Visión General

Lucho encuentra cualquier cosa que el usuario haya guardado. Tres modos de búsqueda: semántica (pgvector, "¿dónde guardé la factura del refri?"), determinista (queries parametrizadas, "¿cuánto llevo gastado?"), e internet (DuckDuckGo, "¿qué es el RUC?"). El usuario pregunta en lenguaje natural; Lucho decide qué modo usar y devuelve resultados precisos de SUS datos, no información genérica.

**Principio de arquitectura**: Nunca Text2SQL abierto. El LLM extrae parámetros de búsqueda; el código determinista ejecuta la query correcta.

---

## 2. Experiencia de Usuario

### 2.1 Búsqueda semántica

> **Usuario**: "¿dónde guardé la factura del internet?"
>
> **Lucho**: "Encontré esto:\n📄 Factura internet junio — vence 2026-07-15\n📄 Contrato NetLife — sin vencimiento\n¿Querés que te mande la foto?"

> **Usuario**: "busca lo del carro"
>
> **Lucho**: "🚗 PBC-1234 — Chevrolet Spark\n   Pico y placa: lunes\n   Matriculación: octubre 2026\n📄 SOAT PBC-1234 — vence 2026-12-15"

### 2.2 Búsqueda determinista

> **Usuario**: "¿qué tengo pendiente?"
>
> **Lucho**: "7 pendientes:\n📝 Compras: leche, pan, huevos (2 libras)\n📋 Tienda Online: configurar pasarela de pago, diseñar logo"

> **Usuario**: "¿qué me vence este mes?"
>
> **Lucho**: "Julio:\n🔴 SOAT PBC-1234 — vence en 15 días (2026-07-28)\n🟡 Licencia conducir — vence en 25 días (2026-08-07)"

### 2.3 Búsqueda en internet

> **Usuario**: "¿cuánto está el pasaje de bus Quito-Guayaquil?"
>
> **Lucho**: "Según internet, entre $12 y $15. ¿Querés que anote algo?"

> **Usuario**: "¿qué dice la nueva ley de facturación electrónica?"
>
> **Lucho**: *[Resultados de web_search]* "¿Querés que guarde algo de esto?"

---

## 3. Arquitectura de Búsqueda

```
Pregunta del usuario
        │
        ▼
┌──────────────────────────────────────┐
│  LLM: ¿qué tipo de búsqueda es?     │
│                                      │
│  ¿Pregunta por sus datos?           │
│    → search_my_data (pgvector)      │
│  ¿Pregunta por conocimiento general?│
│    → web_search (DuckDuckGo)        │
│  ¿Pregunta por historial?           │
│    → search_conversation            │
└──────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────┐
│  CÓDIGO DETERMINISTA                │
│  (NUNCA Text2SQL del LLM)           │
│                                      │
│  search.py:                         │
│  ├─ semantic_search()  pgvector     │
│  ├─ upcoming_deadlines()            │
│  ├─ list_pending_items()            │
│  ├─ search_by_text()  ILIKE        │
│  └─ spending_by_category()          │
└──────────────────────────────────────┘
        │
        ▼
    Resultados reales de la DB
```

---

## 4. Modos de Búsqueda

### 4.1 Búsqueda Semántica — `search_my_data`

**Tecnología**: pgvector + cosine similarity.

**Tablas indexadas**:
| Tabla | Columna | Índice |
|-------|---------|--------|
| `notes` | `embedding` | HNSW |
| `list_items` | `embedding` | (automático) |
| `documents` | `name` | (listado, no vectorial aún) |

**Flujo**:
```
1. Usuario: "¿dónde guardé la factura del refri?"
2. LLM: search_my_data(query="factura refri", search_type="all")
3. Se genera embedding del query
4. pgvector calcula cosine_similarity contra notes.embedding, list_items.embedding, assets.embedding
5. Se ordenan resultados por similitud descendente
6. LLM presenta los top-K resultados
```

### 4.2 Búsqueda Determinista

Catálogo fijo de queries parametrizadas. El LLM nunca genera SQL.

| search_type | Query | Qué devuelve |
|-------------|-------|--------------|
| `deadlines` | `upcoming_deadlines()` | Eventos próximos (días, certeza) |
| `pending` | `list_pending_items()` | Ítems pendientes de todas las listas |
| `vehicles` | `Asset` query | Vehículos del usuario |
| `all` | Todas las anteriores | Búsqueda completa |

**Flujo**:
```
1. Usuario: "¿qué tengo pendiente?"
2. LLM: search_my_data(search_type="pending")
3. Se ejecuta list_pending_items() — SQL fijo
4. Resultados categorizados por lista
5. LLM los presenta
```

### 4.3 Búsqueda en Internet — `web_search`

**Tecnología**: DuckDuckGo (gratis, sin API key).

**Cuándo usarla**: SIEMPRE que el usuario pregunte algo que no está en sus datos personales.

**Regla del system prompt**:
```
Si te preguntan algo que no son sus datos personales
(deportes, cultura, historia, restaurantes, noticias, LO QUE SEA),
usá web_search SIEMPRE. Es gratis, no hay restricción de temas.
Respondé en 1-2 líneas y cerrá ofreciendo guardar algo.
```

### 4.4 Búsqueda en Conversaciones — `search_conversation`

Busca en el historial de mensajes del usuario. Útil para "¿qué me dijiste sobre...?" o "¿cuándo hablamos de...?".

---

## 5. Tools del Agente

### 5.1 `search_my_data` — Ya existe ✅

```json
{
  "name": "search_my_data",
  "description": "Buscar en TODOS los datos del usuario con pgvector o queries deterministas.",
  "parameters": {
    "query": "Lo que el usuario busca, en sus propias palabras.",
    "search_type": "'vehicles', 'pending', 'deadlines', 'notes', 'all'"
  },
  "required": ["query"]
}
```

### 5.2 `web_search` — Ya existe ✅

```json
{
  "name": "web_search",
  "description": "Buscar CUALQUIER cosa en internet. Sin restricciones. DuckDuckGo gratis.",
  "parameters": {
    "query": "Términos de búsqueda."
  },
  "required": ["query"]
}
```

### 5.3 `search_conversation` — Ya existe ✅

```json
{
  "name": "search_conversation",
  "description": "Buscar en el historial de conversaciones con el usuario.",
  "parameters": {
    "query": "Qué buscar en conversaciones anteriores."
  },
  "required": ["query"]
}
```

---

## 6. Implementación Técnica

### 6.1 `semantic_search()` — pgvector

```python
# Búsqueda por similitud de coseno en 3 tablas
async def semantic_search(session, user_id, query_embedding, top_k=5):
    # 1. Buscar en notes.embedding (pgvector HNSW)
    Note.embedding.cosine_distance(query_embedding)
    
    # 2. Buscar en list_items.embedding
    ListItem.embedding.cosine_distance(query_embedding)
    
    # 3. Listar documents por nombre (sin embedding aún)
    Document.name ILIKE query
    
    # 4. Ordenar por similitud, devolver top_k
```

### 6.2 `spending_by_category()` — Gastos por categoría ✅

```python
# Usa datos reales de transactions
async def spending_by_category(session, user_id, category, days=30):
    SELECT category, SUM(amount), COUNT(*)
    FROM transactions
    WHERE type='expense' AND user_id=X AND transaction_date >= since
    GROUP BY category
    ORDER BY SUM(amount) DESC
```

```python
SELECT events WHERE status='upcoming' 
  AND target_date BETWEEN now AND now+30days
  ORDER BY target_date
```

### 6.3 `list_pending_items()` — Pendientes

```python
SELECT list_items JOIN lists 
  WHERE status='pending' AND list.user_id=X
  ORDER BY created_at
```

### 6.4 `search_by_text()` — ILIKE (fallback)

Cuando no hay embeddings disponibles, búsqueda textual con `ILIKE %query%` sobre `notes.content` y `list_items.content`.

---

## 7. Reglas de Negocio

1. **NUNCA Text2SQL**: El LLM solo decide `search_type` y `query`. El SQL es fijo y pre-escrito.
2. **Datos reales primero**: `search_my_data` antes que `web_search`. Si el usuario pregunta algo que podría estar en su DB, buscar ahí primero.
3. **Internet como último recurso**: Solo `web_search` si claramente no son datos personales.
4. **Privacidad**: Los embeddings se generan y almacenan localmente. No se envían datos del usuario a APIs externas para búsqueda.
5. **Resultados con `file_key`**: Si un resultado incluye `file_key`, el LLM debe ofrecer `send_photo` inmediatamente.

---

## 8. Lo que YA existe

| Componente | Estado |
|------------|--------|
| `semantic_search()` pgvector (notes, list_items, documents) | ✅ |
| `upcoming_deadlines()` | ✅ |
| `list_pending_items()` | ✅ |
| `search_by_text()` ILIKE | ✅ |
| `spending_by_category()` — datos reales de `transactions` | ✅ |
| `search_my_data` tool | ✅ |
| `web_search` tool (DuckDuckGo) | ✅ |
| `search_conversation` tool | ✅ |
| Embeddings en notes, list_items | ✅ |
| Índice HNSW en notes.embedding | ✅ |

---

## 9. Mejoras pendientes

| Tarea | Prioridad |
|-------|-----------|
| Embeddings para `documents` (búsqueda vectorial, no solo listado) | 🟡 Media |
| Embeddings para `projects` y `project_tasks` | 🟡 Media |
| `transactions` en búsqueda semántica | 🟡 Media |
| Búsqueda por fecha: "¿qué guardé en marzo?" | 🟢 Baja |
| Vista `searchable_content` materializada | 🟢 Baja |
| Full-text search PostgreSQL (tsvector) | 🟢 Baja |
