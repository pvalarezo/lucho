# Módulo de Cotizaciones — Especificación v1.1

> **Estado**: 🔨 En implementación — Fase 0 (Cotizaciones)
> **Futuro**: Facturación electrónica SRI vía Key49 (Fase 1)
> **IVA**: Configurable (no hardcodeado) — desde `business_info.iva_rate`

---

## 1. Visión General

Lucho permite a emprendedores y pequeños negocios en Ecuador crear **cotizaciones** (proformas) profesionales por conversación natural de WhatsApp/Telegram. Sin apps extra, sin sistemas complejos.

La facturación electrónica SRI vía Key49 se implementará en una fase futura.

**Público objetivo**: tiendas, peluquerías, consultorios, freelance, servicios profesionales — cualquier negocio que hoy cotiza informalmente.

---

## 2. Experiencia de Usuario

### 2.1 Crear una cotización

> **Usuario**: "cotización para Juan Pérez: 2 camisetas a $15, 1 pantalón a $35, con IVA"
>
> **Lucho**: "📋 *Cotización para Juan Pérez*"
> "👕 2x Camiseta — $30.00"
> "👖 1x Pantalón — $35.00"
> "📦 Subtotal: $65.00"
> "🧾 IVA 15%: $9.75"
> "💰 Total: $74.75"
> ""
> "¿La envío por WhatsApp o querés agregar algo más?"

> **Usuario**: "envíala"
>
> **Lucho**: "Listo. Cotización #COT-0042 enviada a Juan Pérez. ¿La guardo para convertirla en factura después?"

### 2.2 Consultar cotizaciones

> **Usuario**: "¿qué cotizaciones tengo?"
>
> **Lucho**: "3 cotizaciones este mes:\n📋 #COT-0042 — Juan Pérez — $74.75 — pendiente\n📋 #COT-0043 — María López — $120.00 — enviada\n📋 #COT-0044 — TechCorp — $450.00 — enviada"

### 2.3 Datos del cliente

> **Usuario**: "guarda los datos de Juan Pérez: 1712345678, juan@email.com, Quito"
>
> **Lucho**: "Cliente guardado: Juan Pérez — Cédula 1712345678 — juan@email.com"

### 2.4 Catálogo de productos

> **Usuario**: "agrega a mi catálogo: Camiseta algodón a $15"
>
> **Lucho**: "Producto guardado: Camiseta algodón — $15.00 (+IVA)."

> **Usuario**: "cotización para Juan: 2 camisetas de algodón y 1 pantalón"
>
> **Lucho**: *(busca en catálogo)* "📋 *Cotización para Juan Pérez*\n👕 2x Camiseta algodón — $30.00\n👖 1x Pantalón — $35.00\n📦 Subtotal: $65.00\n🧾 IVA 15%: $9.75\n💰 Total: $74.75"

---

## 3. Modelo de Datos

### 3.1 Tabla `billing_clients` — Clientes

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | UUID | PK |
| `user_id` | UUID FK | Dueño (emprendedor) |
| `name` | VARCHAR(256) | Nombre o Razón Social |
| `id_type` | ENUM | `cedula`, `ruc`, `pasaporte`, `consumidor_final` |
| `id_number` | VARCHAR(32) | Cédula (10) o RUC (13) |
| `email` | VARCHAR(256) | Correo |
| `phone` | VARCHAR(32) | Teléfono |
| `address` | VARCHAR(512) | Dirección |
| `notes` | TEXT | Notas |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | |

### 3.2 Tabla `billing_products` — Productos/Servicios

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | UUID | PK |
| `user_id` | UUID FK | Dueño |
| `name` | VARCHAR(256) | Nombre: "Camiseta algodón", "Consulta general" |
| `code` | VARCHAR(32) | Código interno (opcional) |
| `unit_price` | DECIMAL(12,2) | Precio unitario sin IVA |
| `has_iva` | BOOLEAN | ¿Aplica IVA 15%? Default: true |
| `unit_of_measure` | VARCHAR(16) | "UNIDAD", "KG", "HORA" |
| `is_active` | BOOLEAN | |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | |

### 3.3 Tabla `billing_documents` — Cotizaciones

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | UUID | PK |
| `user_id` | UUID FK | Dueño |
| `client_id` | UUID FK nullable | Cliente (opcional, puede ser texto libre) |
| `client_name` | VARCHAR(256) | Nombre del cliente |
| `client_id_number` | VARCHAR(32) nullable | Cédula/RUC (opcional) |
| `document_type` | ENUM | `quote` (futuro: `invoice`) |
| `quote_number` | VARCHAR(16) | COT-0001 (secuencial automático) |
| `issue_date` | DATE | Fecha emisión |
| `valid_until` | DATE nullable | Válida hasta |
| `subtotal` | DECIMAL(12,2) | Sin IVA |
| `iva_rate` | DECIMAL(5,2) | Tasa IVA aplicada (ej: 15.00) |
| `iva_amount` | DECIMAL(12,2) | IVA calculado |
| `total` | DECIMAL(12,2) | Con IVA |
| `status` | ENUM | `draft`, `sent`, `accepted`, `rejected`, `expired` |
| `notes` | TEXT | Términos / notas |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | |

### 3.4 Tabla `billing_document_items` — Ítems

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | UUID | PK |
| `document_id` | UUID FK | Cotización o factura |
| `product_id` | UUID FK nullable | Producto del catálogo (opcional) |
| `description` | VARCHAR(512) | Descripción en la factura |
| `quantity` | DECIMAL(10,2) | Cantidad |
| `unit_price` | DECIMAL(12,2) | Precio unitario sin IVA |
| `discount` | DECIMAL(12,2) | Descuento |
| `has_iva` | BOOLEAN | ¿Aplica IVA? |
| `line_total` | DECIMAL(12,2) | Total de la línea |

### 3.5 ENUMs

```sql
billing_id_type: 'cedula', 'ruc', 'pasaporte', 'consumidor_final'
billing_document_type: 'quote'  -- futuro: 'invoice'
billing_document_status: 'draft', 'sent', 'accepted', 'rejected', 'expired'
```

---

## 4. Cálculo de IVA

El % de IVA **NO está hardcodeado**. Se obtiene de:

1. `BusinessInfo.iva_rate` (nuevo campo en la tabla `business_info`)
2. Config fallback: `IVA_RATE` en `.env` (default: 15.0)

Esto permite ajustar la tasa sin tocar código cuando el SRI cambie el IVA (como pasó de 12% → 15% en 2024).

---

## 5. Tools del Agente (Fase 0 — Cotizaciones)

### 5.1 `create_quote` — Crear cotización ✅

```json
{
  "name": "create_quote",
  "description": "Crear una cotización/proforma para un cliente. Calcula automáticamente subtotal, IVA y total.",
  "parameters": {
    "client_name": "Nombre del cliente.",
    "client_id_number": "Cédula o RUC (opcional).",
    "items": [{"description": "...", "quantity": 1, "unit_price": 15.00}],
    "notes": "Términos o validez (ej: 'válido por 15 días')."
  },
  "required": ["client_name", "items"]
}
```

### 5.2 `list_my_quotes` — Consultar cotizaciones ✅

```json
{
  "name": "list_my_quotes",
  "description": "Consultar cotizaciones emitidas.",
  "parameters": {
    "status": "'draft', 'sent', 'accepted', 'rejected', 'expired', 'all'. Default: 'all'.",
    "period": "'this_month', 'last_month', 'all'. Default: 'this_month'."
  },
  "required": []
}
```

### 5.3 `save_billing_client` — Guardar cliente ✅

```json
{
  "name": "save_billing_client",
  "description": "Guardar datos de un cliente frecuente para usarlo en cotizaciones.",
  "parameters": {
    "name": "Nombre o Razón Social.",
    "id_type": "'cedula', 'ruc', 'pasaporte', 'consumidor_final'.",
    "id_number": "Cédula o RUC.",
    "email": "Correo.",
    "phone": "Teléfono.",
    "address": "Dirección."
  },
  "required": ["name", "id_number"]
}
```

### 5.4 `save_billing_product` — Guardar producto ✅

```json
{
  "name": "save_billing_product",
  "description": "Guardar un producto o servicio en el catálogo para usarlo en cotizaciones.",
  "parameters": {
    "name": "Nombre del producto/servicio.",
    "unit_price": "Precio unitario sin IVA.",
    "has_iva": "¿Aplica IVA? Default: true.",
    "code": "Código interno (opcional)."
  },
  "required": ["name", "unit_price"]
}
```

---

## 6. Plan de Implementación

### Fase 0 — Cotizaciones ✅ (esta sesión)

| # | Tarea | Estado |
|---|-------|:--:|
| 1 | `iva_rate` en `BusinessInfo` + config | ✅ |
| 2 | Modelos: `billing_clients`, `billing_products`, `billing_documents`, `billing_document_items` | ✅ |
| 3 | `create_quote` + `list_my_quotes` tools | ✅ |
| 4 | `save_billing_client` + `save_billing_product` tools | ✅ |
| 5 | Cálculo IVA dinámico desde `business_info.iva_rate` | ✅ |

### Fase 1 — Facturación SRI (futuro)

| # | Tarea |
|---|-------|
| 1 | `create_invoice` → Key49 (`POST /v1/invoices`) |
| 2 | `convert_quote_to_invoice` tool |
| 3 | Scheduler: polling Key49 para autorización |
| 4 | `mark_invoice_paid` tool |

---

## 7. Reglas de Negocio

1. **Secuenciales automáticos**: Cotizaciones: `COT-0001`, `COT-0002`, etc. Gestionado por Lucho.
2. **IVA dinámico**: Leído de `business_info.iva_rate`. Si no existe, usa `IVA_RATE` de config (default 15.0).
3. **Ítems con/sin IVA**: Un ítem puede marcarse `has_iva=false` (productos exentos).
4. **Cliente opcional**: Se puede cotizar sin guardar cliente (nombre libre).
5. **Catálogo opcional**: Se pueden crear ítems sin usar el catálogo de productos.
6. **Cotización editable**: Mientras esté en `draft`, se puede modificar. Al marcar `sent`, es final.

---

## 8. Fuera de Alcance

- ❌ Facturación electrónica SRI (Fase 1)
- ❌ Notas de crédito / débito
- ❌ Retenciones de IVA / Impuesto a la Renta
- ❌ Guías de remisión
- ❌ Facturación recurrente
- ❌ Múltiples establecimientos
- ❌ Integración con contabilidad externa
