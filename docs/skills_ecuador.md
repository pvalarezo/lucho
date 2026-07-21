# Skills Ecuador — Conocimiento General Ecuatoriano

---

## 1. Visión General

Lucho tiene conocimiento precargado sobre Ecuador: cultura, trámites legales, impuestos, tránsito y gastronomía. Son archivos Markdown que el sistema carga como contexto adicional para el LLM, permitiendo respuestas precisas sin consumir APIs externas de búsqueda.

**Principio**: Antes de buscar en internet (`web_search`), Lucho verifica si tiene una skill ecuatoriana que cubra el tema. Si la skill lo cubre → respuesta local gratuita. Si no → DuckDuckGo.

---

## 2. Skills Disponibles (7)

| # | Skill | Dominio | Carga | Palabras clave |
|---|-------|--------|-------|----------------|
| 1 | `culture/idioms.md` | Modismos | **Siempre** | — |
| 2 | `culture/cuisine.md` | Gastronomía | Bajo demanda | comida, receta, encebollado, fanesca... |
| 3 | `culture/holidays.md` | Feriados | Bajo demanda | feriado, carnaval, navidad, puente... |
| 4 | `legal/documents.md` | Documentos legales | Bajo demanda | cédula, pasaporte, registro civil... |
| 5 | `tax/invoicing.md` | Facturación SRI | Bajo demanda | factura, SRI, IVA, RUC, impuesto... |
| 6 | `transit/driving-restrictions.md` | Pico y placa | Bajo demanda | pico y placa, restricción, Quito... |
| 7 | `transit/registration.md` | Matriculación | Bajo demanda | matriculación, SOAT, ANT, renovar... |

---

## 3. Cómo Funciona

### 3.1 Flujo de carga

```
1. Usuario envía mensaje
2. load_skills_for_message(mensaje) evalúa:
   a. Carga skills "always" (idioms.md siempre)
   b. Compara palabras del mensaje con keywords de cada skill
   c. Si hay match → carga la skill
3. Skills cargadas se concatenan como bloque de contexto
4. Se inyectan en el prompt del LLM como "Contexto de dominio ecuatoriano"
5. El LLM usa ese conocimiento para responder
```

### 3.2 Tipos de carga

| Tipo | Cuándo | Skills |
|------|--------|--------|
| **Always** | Cada mensaje, sin excepción | `idioms.md` |
| **On-demand** | Solo si el mensaje contiene keywords | Las otras 6 |

### 3.3 Ejemplo

```
Usuario: "¿cómo se hace el encebollado?"

load_skills_for_message() detecta keywords:
  ✅ "comida", "encebollado" → carga culture/cuisine.md
  ✅ always → carga culture/idioms.md

Contexto inyectado al LLM:
  ## Contexto de dominio ecuatoriano relevante
  [contenido de idioms.md]
  ---
  [contenido de cuisine.md con receta del encebollado]

LLM responde con la receta real del archivo, sin consumir API.
```

---

## 4. Estructura de Archivos

```
app/agent/skills/
├── __init__.py          ← Cargador (ALWAYS_SKILLS, ON_DEMAND_SKILLS, load_skills_for_message)
├── culture/
│   ├── cuisine.md       ← Gastronomía ecuatoriana (7991 chars)
│   ├── holidays.md      ← Feriados oficiales (6070 chars)
│   └── idioms.md        ← Modismos ecuatorianos (3724 chars)
├── legal/
│   └── documents.md     ← Trámites de documentos (6064 chars)
├── tax/
│   └── invoicing.md     ← Facturación electrónica SRI (7168 chars)
└── transit/
    ├── driving-restrictions.md ← Pico y placa (2146 chars)
    └── registration.md  ← Matriculación vehicular (1918 chars)
```

---

## 5. Cómo Dar Mantenimiento

### 5.1 Agregar una nueva skill

1. Crear el archivo `.md` en la carpeta del dominio correspondiente
2. El archivo debe empezar con `# Título` y tener al menos una tabla `|`
3. Agregar entrada en `ON_DEMAND_SKILLS` con sus keywords:

```python
# En app/agent/skills/__init__.py
ON_DEMAND_SKILLS = {
    ...
    "cultura/deportes.md": [
        "fútbol", "futbol", "ecuador", "selección", "seleccion",
        "liga pro", "barcelona", "emelec", "liga de quito",
    ],
}
```

4. El archivo se cargará automáticamente cuando el mensaje contenga esas palabras

### 5.2 Actualizar una skill existente

1. Editar el archivo `.md` directamente
2. Mantener estructura: `# Título`, `## Subtítulos`, tablas donde aplique
3. Si se agregan nuevos conceptos, agregar keywords correspondientes

### 5.3 Validación automática

Los tests unitarios validan que cada skill:
- Tenga al menos 500 caracteres de contenido
- Empiece con `#` (heading)
- Tenga al menos dos niveles de heading (`##`)
- Contenga al menos una tabla Markdown
- Tenga al menos 3 keywords en `ON_DEMAND_SKILLS`

```bash
python3 tests/unit.py  # Sección 4: Skill Loader
```

---

## 6. Código Clave

### 6.1 Archivos

| Archivo | Rol |
|---------|-----|
| `app/agent/skills/__init__.py` | Cargador: ALWAYS_SKILLS, ON_DEMAND_SKILLS, load_skills_for_message() |
| `app/agent/loop.py` (línea 66) | `skills_context = load_skills_for_message(user_message)` |
| `tests/unit.py` | Tests de validación de skills |

### 6.2 Funciones principales

```python
# Carga skills relevantes para un mensaje
def load_skills_for_message(user_message: str) -> str:
    # 1. Carga always-skills
    # 2. Busca keywords en on-demand skills
    # 3. Retorna bloque de contexto concatenado

# Lista todas las skills disponibles
def list_available_skills() -> list[str]:
    # Escanea skills/*.md recursivamente

# Carga el contenido de un archivo
def load_skill_content(relative_path: str) -> str:
    # Lee el archivo .md y retorna texto
```

---

## 7. Inyección en el LLM

Las skills se inyectan como **contexto de mensaje de usuario**, NO en el system prompt. Esto mantiene el system prompt corto y cacheable.

```python
# app/agent/loop.py
skills_context = load_skills_for_message(user_message)
if skills_context:
    # Se agrega al historial de mensajes como contexto adicional
    messages.append({"role": "user", "content": skills_context})
```

---

## 8. Reglas

1. **Skills primero, web_search después**: Si una skill cubre el tema, no se llama a DuckDuckGo.
2. **Sin modificar el system prompt**: Las skills son contexto de mensaje, no del sistema.
3. **Keywords en español**: Las palabras clave reflejan cómo habla un ecuatoriano real.
4. **Contenido estático**: Las skills son archivos Markdown, no requieren DB.
5. **Mantenimiento simple**: Editar `.md` + agregar keywords. Sin código.
