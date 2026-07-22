# Módulo de Documentos — Especificación v1.0

---

## 1. Visión General

Lucho guarda, organiza y recuerda documentos personales del usuario: cédula, pasaporte, licencia, SOAT, facturas, garantías, pólizas de seguro, y cualquier documento con fecha de vencimiento. El usuario puede enviar el documento como foto, PDF, o simplemente describirlo por texto. Lucho lo archiva, alerta antes de que venza, y lo recupera al instante cuando se lo piden.

---

## 2. Experiencia de Usuario

### 2.1 Guardar un documento por texto

> **Usuario**: "mi cédula es 1712345678, vence en 2029"
>
> **Lucho**: "Listo Pato. Guardé tu cédula 1712345678. Vence en 2029, te aviso unos meses antes."

> **Usuario**: "el SOAT del carro PBC-1234 vence el 15 de diciembre"
>
> **Lucho**: "Anotado. SOAT de PBC-1234 vence el 2026-12-15. Te recuerdo 30, 15 y 7 días antes."

### 2.2 Guardar un documento con foto

> **Usuario**: *[envía foto de la licencia de conducir]*
>
> **Lucho**: "Recibí la foto. ¿Qué documento es y cuándo vence?"
>
> **Usuario**: "licencia de conducir, vence 2028-03-10"
>
> **Lucho**: "Guardada tu licencia de conducir con la foto. Vence 2028-03-10."

### 2.3 Recuperar un documento

> **Usuario**: "pásame mi SOAT"
>
> **Lucho**: *[envía la foto del SOAT]* "Tu SOAT de PBC-1234. Vence 2026-12-15, te quedan 148 días."

> **Usuario**: "¿qué documentos tengo guardados?"
>
> **Lucho**: "Tenés 5 documentos:\n🆔 Cédula — vence 2029-05-10\n🚗 SOAT PBC-1234 — vence 2026-12-15\n🚗 SOAT PBC-5678 — vence 2027-08-01\n📄 Factura internet — sin vencimiento\n🛡️ Póliza de seguro — vence 2027-01-20"

### 2.4 Consultar vencimientos

> **Usuario**: "¿qué documentos me vencen pronto?"
>
> **Lucho**: "Próximos vencimientos:\n🔴 SOAT PBC-1234 — vence en 15 días (2026-12-15)\n🟡 Licencia de conducir — vence en 3 meses (2027-03-10)\n🟢 Cédula — vence en 2 años (2029-05-10)"

---

## 3. Modelo de Datos

### 3.1 Tabla existente: `assets` (con `asset_type = 'document'`)

Ya implementado. Los documentos usan la tabla `assets` con `asset_type = 'document'`. El modelo actual es:

| Columna | Tipo | Uso en documentos |
|---------|------|-------------------|
| `id` | UUID | PK |
| `user_id` | UUID FK | Dueño |
| `asset_type` | ENUM | Siempre `'document'` |
| `name` | VARCHAR(256) | Nombre descriptivo: "Cédula de Patricio", "SOAT PBC-1234" |
| `attributes` | JSONB | `document_type`, `expiry_date`, `entity_name`, `file_key` |
| `notes` | TEXT | Notas adicionales |
| `deleted_at` | TIMESTAMP | Soft delete |
| `created_at` | TIMESTAMP | Fecha de creación |
| `updated_at` | TIMESTAMP | Última modificación |

### 3.2 Estructura del JSONB `attributes` para documentos

```json
{
  "document_type": "cedula",        // REQUERIDO. Ver tipos abajo
  "document_number": "1712345678",  // Número de documento (nuevo 🆕)
  "expiry_date": "2029-05-10",      // Fecha de vencimiento (ISO)
  "entity_name": "Registro Civil",  // Entidad emisora
  "file_key": "user_id/photo_123.jpg",  // Referencia MinIO
  "file_keys": ["key1.jpg", "key2.jpg"], // Multi-archivo 🆕
  "tags": ["personal", "legal"],    // Etiquetas para búsqueda 🆕
  "renewal_url": "https://...",     // Link para renovar 🆕
}
```

### 3.3 Tipos de documento predefinidos

| Tipo | ENUM/Constante | Ejemplos | ¿Tiene vencimiento? |
|------|---------------|----------|---------------------|
| 🆔 Cédula | `cedula` | Cédula de identidad, DNI | ✅ Sí (10 años) |
| 🛂 Pasaporte | `pasaporte` | Pasaporte ecuatoriano | ✅ Sí (5-10 años) |
| 🚗 Licencia | `licencia` | Licencia de conducir | ✅ Sí (5 años) |
| 🚗 SOAT | `soat` | Seguro Obligatorio Automotor | ✅ Sí (1 año) |
| 🛡️ Seguro | `seguro` | Póliza de seguro, salud, vida | ✅ Sí |
| 📄 Factura | `factura` | Factura electrónica, ticket | ❌ No |
| 🔧 Garantía | `garantia` | Garantía de electrodoméstico | ✅ Sí |
| 📝 Certificado | `certificado` | Certificado laboral, médico | A veces |
| 📋 Escritura | `escritura` | Escritura de propiedad | ❌ No |
| 🏦 Contrato | `contrato` | Contrato de arriendo, servicio | ✅ Sí |
| 💳 Tarjeta | `tarjeta` | Tarjeta de crédito, débito | ✅ Sí |
| 📸 Otro | `otro` | Cualquier otro documento | Variable |

### 3.4 Documento con estado (tracking de ciclo de vida) 🆕

Propuesta: agregar un campo `status` en el JSONB para trackear si el documento fue renovado:

```
attributes.status: "active" | "expired" | "pending_renewal" | "archived"
```

El scheduler marcaría automáticamente como `expired` si pasó la fecha sin renovación registrada.

---

## 4. Tools del Agente

### 4.1 `save_document` — Ya existe ✅ (reforzar)

```json
{
  "name": "save_document",
  "description": "Guardar un documento personal: cédula, pasaporte, licencia, SOAT, factura, garantía, seguro, contrato, o cualquier documento. Si tiene fecha de vencimiento, Lucho te recordará antes.",
  "parameters": {
    "type": "object",
    "properties": {
      "document_type": {
        "type": "string",
        "description": "Tipo de documento: cedula, pasaporte, licencia, soat, seguro, factura, garantia, certificado, escritura, contrato, tarjeta, otro."
      },
      "name": {
        "type": "string",
        "description": "Nombre descriptivo. Ej: 'Cédula de Patricio', 'SOAT PBC-1234', 'Factura internet junio'."
      },
      "document_number": {
        "type": "string",
        "description": "Número del documento si el usuario lo menciona. Ej: '1712345678', 'PBC-1234'."
      },
      "expiry_date": {
        "type": "string",
        "description": "Fecha de vencimiento YYYY-MM-DD. Si el documento no vence, omitir."
      },
      "entity_name": {
        "type": "string",
        "description": "Entidad emisora. Ej: 'Registro Civil', 'ANT', 'Seguros Equinoccial'."
      },
      "notes": {
        "type": "string",
        "description": "Notas adicionales."
      },
      "file_key": {
        "type": "string",
        "description": "Clave MinIO. Viene de analyze_image o [foto: X]."
      }
    },
    "required": ["document_type", "name"]
  }
}
```

### 4.2 `list_my_documents` — 🆕 Nueva

```json
{
  "name": "list_my_documents",
  "description": "Listar los documentos del usuario. Usar cuando pregunta '¿qué documentos tengo?', 'mis documentos', 'mostrame mis SOAT'.",
  "parameters": {
    "type": "object",
    "properties": {
      "document_type": {
        "type": "string",
        "description": "Filtrar por tipo de documento. Opcional."
      },
      "status": {
        "type": "string",
        "enum": ["all", "active", "expiring_soon", "expired"],
        "description": "Estado. Default: 'all'. 'expiring_soon' = vence en 30 días."
      }
    },
    "required": []
  }
}
```

### 4.3 `search_documents` — 🆕 Nueva (o integrar en `search_my_data`)

La búsqueda de documentos ya funciona vía `search_my_data` con pgvector. Mantener así, pero asegurar que los resultados incluyan `document_type`, `expiry_date`, `file_key`.

---

## 5. Flujo de Recepción de Fotos y Documentos

### 5.1 Regla fundamental

**Lucho NUNCA analiza ni guarda una foto o documento automáticamente.** Siempre espera instrucciones explícitas del usuario. Esto evita guardar contenido no deseado y respeta la privacidad.

### 5.2 Foto SIN instrucción (el usuario solo envía la imagen)

```
1. WhatsApp webhook recibe imagen sin texto
2. Se descarga de Meta y se sube a MinIO → genera file_key
3. Se crea mensaje interno: "[foto: user_id/photo_123.jpg]"
4. Debounce de 3 segundos (por si el usuario está escribiendo)
5. Se detecta: photo-only + sin caption
6. Se responde INMEDIATAMENTE sin llamar al LLM:
   "📷 Recibí tu foto. ¿Querés que la analice, la guarde, o qué hacemos?"
7. NO se llama a analyze_image
8. NO se guarda nada en la base de datos
9. Se espera la respuesta del usuario con instrucciones
```

**Código**: `app/routers/whatsapp_webhook.py` líneas 446-459

```python
has_photo_only = all(m.message_type == MessageType.photo for m in pending)
is_photo_placeholder = all(
    (m.text or "").startswith("[foto:") and (m.text or "").count(" ") == 0
    for m in pending
)
if has_photo_only and is_photo_placeholder:
    await whatsapp_svc.send_message(
        phone,
        "📷 Recibí tu foto. ¿Querés que la analice, la guarde, o qué hacemos?",
    )
    # Retorna SIN llamar al agente ni a analyze_image
```

### 5.3 Foto CON instrucción (el usuario escribe texto junto con la imagen)

```
1. WhatsApp webhook recibe imagen + texto: "guardame esta factura"
2. Se descarga y sube a MinIO → file_key
3. Se crea mensaje: "[foto: user_id/photo_123.jpg] guardame esta factura"
4. Debounce: si llegan más mensajes en 3s, se concatenan
5. Se envía al agente (LLM) con el contexto completo
6. El LLM evalúa la instrucción y decide qué tools llamar
7. Para fotos: analyze_image (extraer datos visibles) + save_document (guardar)
8. Para documentos: save_document con los datos indicados
```

**System prompt relacionado**:
```
ARCHIVO SIN INSTRUCCIÓN:
  → NO analices. Preguntá "¿Querés que lo analice o lo guarde?"

ARCHIVO CON INSTRUCCIÓN:
  → Ejecutá la instrucción. analyze_image + save_document si es foto.
```

### 5.4 Foto en mensaje posterior (el usuario hace referencia a una foto anterior)

```
1. Usuario envió foto hace unos mensajes (ya tiene file_key)
2. Ahora escribe: "guardala como mi cédula"
3. El sistema detecta palabras clave ("foto", "guardala", "esa imagen")
4. Inyecta el file_key de la foto más reciente en el contexto:
   "[foto: user_id/photo_123.jpg] guardala como mi cédula"
5. El LLM recibe el file_key y llama a save_document con él
```

**Código**: `app/routers/whatsapp_webhook.py` líneas 427-438

### 5.5 Flujo OCR + Documento

Cuando el usuario da instrucciones explícitas de analizar/guardar:

```
1. Usuario envía foto + "guardame esta factura" o "analiza este documento"
2. LLM recibe el contexto con file_key + instrucción
3. LLM llama a analyze_image(file_key) → extrae datos visibles (número, fecha, entidad)
4. LLM llama a save_document con los datos extraídos + file_key
5. Scheduler evaluará el expiry_date para recordatorios futuros
6. El documento queda guardado, buscable y enviable vía send_photo
```

### 5.6 Tipos de archivo soportados

| Tipo | WhatsApp type | Extensión | Se puede analizar? |
|------|--------------|-----------|-------------------|
| Foto | `image` | .jpg, .png, .webp | ✅ analyze_image |
| Documento | `document` | .pdf, .doc, .xlsx | ❌ Solo guardar |
| Audio | `audio` | .ogg | ✅ Whisper (transcripción) |
| Sticker | `sticker` | .webp | ❌ No soportado |
| Video | `video` | .mp4 | ❌ No soportado |

---

## 6. Scheduler — Recordatorios de Vencimiento

### Ya implementado ✅

`_evaluate_documents()` corre a las 8:00 AM. Escanea todos los `assets` con `asset_type = 'document'` que tengan `expiry_date` en el JSONB.

**Ventanas**: 30, 15, 7 días antes del vencimiento.

**Canales**:
- Telegram: mensaje directo con detalles
- WhatsApp: template `document_reminder` (es, 6 params)

### Propuesta de mejora 🆕

Agregar ventana de **60 días** para documentos críticos (cédula, pasaporte) que requieren trámites largos.

---

## 7. Template WhatsApp

### `document_reminder` — Ya creado y aprobado ✅

| Param | Contenido | Ejemplo |
|-------|-----------|---------|
| {{1}} | Emoji urgencia | 🔴 |
| {{2}} | Nombre documento | SOAT PBC-1234 |
| {{3}} | Tipo documento | soat |
| {{4}} | Días texto | en 7 días |
| {{5}} | Fecha vencimiento | 2026-12-15 |
| {{6}} | Nombre (repeat) | SOAT PBC-1234 |

### Body del template:

```
Hola. Te informo que:

📄 {{1}} {{2}} ({{3}})
Vence: {{4}} ({{5}})

Si ya lo renovaste, responde "ya renové {{6}}" y lo actualizo.
```

---

## 8. Flujo de Renovación (marcar como renovado) 🆕

> **Usuario**: "ya renové el SOAT de PBC-1234, ahora vence 2027-12-15"
>
> **Lucho**: (busca el documento existente → actualiza expiry_date)
> "¡Listo! SOAT PBC-1234 actualizado. Nuevo vencimiento: 2027-12-15."

El LLM debe usar `update_last` o buscar el documento y regenerarlo con nueva fecha.

**Alternativa más robusta**: Crear tool `renew_document` que:
1. Busca el documento por nombre/tipo
2. Actualiza `expiry_date` en attributes
3. Opcionalmente recibe nueva foto (`file_key`)

---

## 9. Búsqueda de Documentos

Ya funciona vía `search_my_data` con pgvector. Los documentos con `expiry_date` aparecen en `upcoming_deadlines()`. Las mejoras necesarias:

- Incluir `document_type` y `entity_name` en resultados de búsqueda
- Permitir filtrar por tipo: "buscá mis SOAT"
- Devolver `file_key` para que el LLM llame a `send_photo` inmediatamente

---

## 10. Reglas de Negocio

1. **Detección de duplicados**: Si el usuario guarda un documento con el mismo `name` y `document_type`, actualizar en vez de duplicar.
2. **Expiry obligatorio para ciertos tipos**: SOAT, cédula, pasaporte, licencia, seguro DEBEN tener `expiry_date`. Si el usuario no lo da, preguntar.
3. **file_key único vs múltiple**: Un documento puede tener varias fotos (anverso/reverso). Soportar `file_keys` array.
4. **Soft delete**: Nunca borrar físicamente. `deleted_at` = soft delete. "eliminá mi SOAT viejo" → soft delete.
5. **Documentos sin vencimiento**: Facturas, escrituras, certificados sin fecha → no generar recordatorios.

---

## 11. Implementación Técnica

### 11.1 Lo que YA existe

| Componente | Estado |
|------------|--------|
| `Document` model — tabla dedicada (v2.13.0), 13 columnas + pgvector embedding | ✅ |
| `save_document` tool — create/update con dedup (mismo name+type = update) | ✅ |
| `save_document` — `document_number` y `tags` expuestos al LLM | ✅ |
| `list_my_documents` tool — filtros por `document_type` y `status` (all/active/expiring_soon/expired) | ✅ |
| `file_keys` array (JSONB) — soporte para múltiples fotos (anverso/reverso) | ✅ |
| `status` tracking — ENUM `document_status` (active/expired/archived) en modelo | ✅ |
| `_evaluate_documents` scheduler — ventanas 30/15/7 días antes del vencimiento | ✅ |
| `document_reminder` WhatsApp template (es) — 6 body params, aprobado | ✅ |
| `analyze_image` + OCR | ✅ |
| MinIO storage con `file_key` | ✅ |
| `search_my_data` con pgvector — incluye documentos en resultados | ✅ |
| `send_photo` — enviar documento guardado al usuario | ✅ |
| Flujo foto SIN instrucción — no analiza, pregunta primero | ✅ |
| Flujo foto CON instrucción — analyze_image + save_document | ✅ |
| Renovación vía `save_document` — dedup actualiza expiry_date sin duplicar | ✅ |

### 11.2 Pendientes / Mejoras futuras

| Tarea | Prioridad | Esfuerzo | Notas |
|-------|-----------|----------|-------|
| Ventana 60 días para docs críticos (cédula, pasaporte) | 🟢 Baja | Bajo | Agregar a `DOCUMENT_WINDOWS` solo para esos tipos |
| Scheduler: marcar docs vencidos como `status=expired` | 🟡 Media | Bajo | Hoy no se actualiza automáticamente al pasar la fecha |
| Mejorar OCR prompt para docs ecuatorianos | 🟡 Media | Medio | Afinar system prompt para formatos locales |
| Template `document_reminder` con botón "Renové" | 🟢 Baja | Medio (Meta) | Requiere aprobación de Meta |

---

## 12. Fuera de Alcance (v1)

- ❌ Validación automática de números de cédula con Registro Civil
- ❌ Verificación de SOAT con base de la ANT
- ❌ Firma digital o validación legal de documentos
- ❌ OCR de tablas complejas en facturas
- ❌ Compartir documento con otro usuario de Lucho
