# Módulo de Facturación y Cotizaciones — Especificación v1.0

> **Estado**: 📋 Propuesta — pendiente de aprobación e implementación
> **Solicitante**: Cliente Lucho
> **Stack SRI**: Key49 (AURACORE) para emisión y autorización

---

## 1. Visión General

Lucho permite a emprendedores y pequeños negocios en Ecuador crear **cotizaciones** (proformas) y emitir **facturas electrónicas** autorizadas por el SRI, todo por conversación natural de WhatsApp/Telegram. Sin apps extra, sin sistemas complejos. El usuario dicta los datos y Lucho se encarga del resto vía Key49.

**Público objetivo**: tiendas, peluquerías, consultorios, freelance, servicios profesionales, restaurantes pequeños — cualquier negocio que hoy factura en libretitas o Excel.

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

### 2.2 Convertir cotización en factura

> **Usuario**: "convierte la cotización 42 en factura"
>
> **Lucho**: "Factura emitida:"
> "🧾 *Factura #001-001-00000042*"
> "Cliente: Juan Pérez — Cédula: 1712345678"
> "📦 Total: $74.75 (IVA incluido)"
> "Estado: ✅ Autorizada por el SRI"
> "🔑 Clave de acceso: 1007202601110387543900110010040000000424999510811"
> ""
> "¿Te envío el PDF de la factura?"

### 2.3 Datos del cliente

> **Usuario**: "guarda los datos de Juan Pérez: 1712345678, juan@email.com, Quito"
>
> **Lucho**: "Cliente guardado: Juan Pérez — Cédula 1712345678 — juan@email.com"

### 2.4 Consultar facturas

> **Usuario**: "¿cuánto facturé este mes?"
>
> **Lucho**: "Julio 2026:"
> "🧾 5 facturas emitidas"
> "💰 Total facturado: $1,245.50"
> "📈 Promedio: $249.10 por factura"
> ""
> "Tu mejor cliente: Juan Pérez ($450.00)"

> **Usuario**: "mis facturas pendientes de cobro"
>
> **Lucho**: "2 facturas por cobrar ($320.00):"
> "🔴 #42 — Juan Pérez — $74.75 — vence 05/08"
> "🔴 #43 — María López — $245.25 — vence 10/08"

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

### 3.3 Tabla `billing_documents` — Cotizaciones y Facturas

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | UUID | PK |
| `user_id` | UUID FK | Dueño |
| `client_id` | UUID FK | Cliente |
| `document_type` | ENUM | `quote`, `invoice` |
| `quote_number` | VARCHAR(32) | COT-0001 (secuencial propio) |
| `invoice_number` | VARCHAR(32) | 001-001-000000042 (formato SRI) |
| `issue_date` | DATE | Fecha emisión |
| `due_date` | DATE nullable | Fecha vencimiento |
| `subtotal` | DECIMAL(12,2) | Sin IVA |
| `iva_amount` | DECIMAL(12,2) | IVA calculado |
| `total` | DECIMAL(12,2) | Con IVA |
| `status` | ENUM | `draft`, `sent`, `paid`, `cancelled` |
| `converted_from_id` | UUID FK nullable | Si es factura, de qué cotización viene |
| `key49_id` | VARCHAR(64) | ID en Key49 (solo facturas) |
| `sri_access_key` | VARCHAR(64) | Clave de acceso SRI (49 dígitos) |
| `sri_status` | VARCHAR(32) | `pending`, `authorized`, `rejected` |
| `notes` | TEXT | Notas / términos |
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
billing_document_type: 'quote', 'invoice'
billing_document_status: 'draft', 'sent', 'paid', 'cancelled'
billing_sri_status: 'pending', 'authorized', 'rejected'
```

---

## 4. Flujo de Facturación con Key49

```
Usuario: "factura para Juan Pérez: 2 camisetas a $15, 1 pantalón a $35"
        │
        ▼
┌─────────────────────────────────────────────┐
│  1. Lucho extrae datos con LLM             │
│     - Cliente: Juan Pérez, cédula 1712...  │
│     - Ítems: 2x Camiseta $15, 1x Pantalón $35 │
│     - Calcula subtotal, IVA 15%, total     │
│     - Muestra confirmación                 │
└─────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────┐
│  2. Guarda en billing_documents local      │
│     - status = 'draft'                     │
│     - sri_status = 'pending'               │
│     - Asigna secuencial                    │
└─────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────┐
│  3. Envía a Key49 (POST /v1/invoices)     │
│     - Mapea datos a formato Key49          │
│     - establishment: 001                   │
│     - issue_point: 001                     │
│     - Calcula base imponible               │
│     - 15% IVA con rate_code "4"           │
└─────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────┐
│  4. Scheduler poll Key49 (8 AM diario)     │
│     - GET /v1/invoices/:id → status        │
│     - AUTHORIZED → guarda access_key       │
│     - Actualiza sri_status                 │
└─────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────┐
│  5. Lucho notifica al usuario              │
│     "✅ Factura #42 autorizada por el SRI" │
│     "¿Te envío el PDF?"                   │
└─────────────────────────────────────────────┘
```

---

## 5. Tools del Agente (Propuesta)

### 5.1 `create_quote` — Crear cotización

```json
{
  "name": "create_quote",
  "description": "Crear una cotización/proforma para un cliente. No se envía al SRI.",
  "parameters": {
    "client_name": "Nombre del cliente.",
    "client_id_number": "Cédula o RUC (opcional).",
    "items": [{"description": "...", "quantity": 1, "unit_price": 15.00}],
    "notes": "Notas o términos."
  },
  "required": ["client_name", "items"]
}
```

### 5.2 `convert_quote_to_invoice` — Cotización → Factura

```json
{
  "name": "convert_quote_to_invoice",
  "description": "Convertir una cotización en factura electrónica. Se envía al SRI vía Key49.",
  "parameters": {
    "quote_number": "Número de cotización (ej: 'COT-0042').",
    "payment_method": "'01'=efectivo, '16'=débito, '19'=crédito, '20'=transferencia"
  },
  "required": ["quote_number"]
}
```

### 5.3 `create_invoice` — Factura directa

```json
{
  "name": "create_billing_invoice",
  "description": "Crear una factura electrónica directamente (sin cotización previa). Se envía al SRI vía Key49.",
  "parameters": {
    "client_name": "Nombre o Razón Social.",
    "client_id_type": "'cedula', 'ruc', 'pasaporte', 'consumidor_final'",
    "client_id_number": "Cédula o RUC.",
    "client_email": "Correo para envío de factura.",
    "items": [{"description": "...", "quantity": 1, "unit_price": 15.00}],
    "payment_method": "'01'=efectivo, '20'=transferencia. Default: '01'"
  },
  "required": ["client_name", "client_id_type", "client_id_number", "items"]
}
```

### 5.4 `list_my_invoices` — Consultar facturas

```json
{
  "name": "list_my_invoices",
  "description": "Consultar facturas y cotizaciones emitidas.",
  "parameters": {
    "document_type": "'quote', 'invoice', o 'all'. Default: 'all'.",
    "status": "'draft', 'sent', 'paid', 'cancelled', 'all'. Default: 'all'.",
    "period": "'this_month', 'last_month', 'this_year', 'all'."
  },
  "required": []
}
```

### 5.5 `mark_invoice_paid` — Marcar como pagada

```json
{
  "name": "mark_invoice_paid",
  "description": "Marcar una factura como pagada.",
  "parameters": {
    "invoice_number": "Número de factura (ej: '001-001-000000042').",
    "payment_method": "'01'=efectivo, '20'=transferencia.",
    "payment_date": "Fecha YYYY-MM-DD. Default: hoy."
  },
  "required": ["invoice_number"]
}
```

### 5.6 `save_billing_client` — Guardar cliente

```json
{
  "name": "save_billing_client",
  "description": "Guardar datos de un cliente frecuente.",
  "parameters": {
    "name": "Nombre o Razón Social.",
    "id_type": "'cedula', 'ruc', 'pasaporte', 'consumidor_final'.",
    "id_number": "Cédula (10) o RUC (13).",
    "email": "Correo.",
    "phone": "Teléfono.",
    "address": "Dirección."
  },
  "required": ["name", "id_number"]
}
```

### 5.7 `save_billing_product` — Guardar producto/servicio

```json
{
  "name": "save_billing_product",
  "description": "Guardar un producto o servicio del catálogo.",
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

### Fase A — Core (MVP)

| # | Tarea | Esfuerzo |
|---|-------|----------|
| 1 | Modelos: `billing_clients`, `billing_products`, `billing_documents`, `billing_document_items` | Medio |
| 2 | Migraciones | Bajo |
| 3 | Tool `create_invoice` + handler + integración Key49 | Medio |
| 4 | Tool `list_my_invoices` + handler | Bajo |
| 5 | Scheduler: polling Key49 para autorización SRI | Bajo |
| 6 | Tool `mark_invoice_paid` | Bajo |

### Fase B — Cotizaciones

| # | Tarea | Esfuerzo |
|---|-------|----------|
| 7 | Tool `create_quote` + handler | Bajo |
| 8 | Tool `convert_quote_to_invoice` | Medio |

### Fase C — Catálogo y Clientes

| # | Tarea | Esfuerzo |
|---|-------|----------|
| 9 | Tool `save_billing_client` + `save_billing_product` | Bajo |
| 10 | Búsqueda semántica de productos ("busca camisetas") | Medio |

### Esfuerzo total estimado: ~6-8 horas

---

## 7. Reglas de Negocio

1. **Secuenciales**: Lucho asigna automáticamente. Cotizaciones: `COT-0001`. Facturas: `001-001-000000001` (formato SRI).
2. **IVA 15%**: Aplica por defecto a todos los ítems. El usuario puede indicar "sin IVA" para productos exentos.
3. **Consumidor Final**: Si el cliente no da cédula/RUC, se usa `id_type=07`, `id=9999999999999`.
4. **Cotización → Factura**: Una cotización solo se convierte UNA vez en factura.
5. **Factura emitida = no editable**: Una vez enviada al SRI, no se modifica. Solo se puede anular.
6. **Key49 es obligatorio**: Sin API key de Key49, el módulo funciona en modo borrador (sin autorización SRI).
7. **Términos de pago**: Opcionales. "30 días", "contado", "50% anticipo".

---

## 8. Fuera de Alcance (v1)

- ❌ Notas de crédito / débito
- ❌ Retenciones de IVA / Impuesto a la Renta
- ❌ Guías de remisión
- ❌ Liquidaciones de compra
- ❌ Facturación recurrente automática
- ❌ Múltiples establecimientos / puntos de emisión
- ❌ Reportes avanzados (IVA cobrado, retenciones)
- ❌ Integración con contabilidad externa

---

## 9. Comparación con alternativas

| | **Lucho Facturación** | SIACO | QuickBooks | Facturación física |
|---|:---:|:---:|:---:|:---:|
| Interfaz | WhatsApp/Telegram | Web | Web/App | Papel |
| Curva aprendizaje | 0 (conversación) | Media | Alta | Baja |
| SRI automático | ✅ Key49 | ✅ | ❌ (Ecuador) | ❌ |
| Precio | Desde $9.99/mes | $15-30/mes | $25-50/mes | Imprenta |
| Catálogo productos | ✅ | ✅ | ✅ | ❌ |
| Cotizaciones | ✅ | ✅ | ✅ | Manual |
| Ideal para | Micro-negocios | PYMES | Empresas | Informal |
