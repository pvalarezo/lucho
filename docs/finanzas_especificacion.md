# Módulo de Finanzas Personales — Especificación v1.0

---

## 1. Visión General

Lucho lleva el control de ingresos y gastos del usuario mediante conversación natural por texto o audio. Sin PDFs, sin fotos de facturas (al menos en esta primera versión). El usuario simplemente le cuenta a Lucho lo que gastó o recibió, y Lucho organiza, resume y alerta.

---

## 2. Experiencia de Usuario (Actuando como usuario de Lucho)

### 2.1 Registrar un gasto

> **Usuario**: "gasté 20 dólares en almuerzo"
>
> **Lucho**: "Listo. Almuerzo: $20. Vas $380 en alimentación este mes, te quedan $120 del presupuesto."

> **Usuario**: "pagué 45 de gasolina"
>
> **Lucho**: "Anotado. Gasolina: $45. Vas $120 en transporte este mes."

> **Usuario**: "acabo de gastar 12.50 en el cine"
>
> **Lucho**: "¡Qué peli viste? 🍿 Cine: $12.50 en entretenimiento."

### 2.2 Registrar un ingreso

> **Usuario**: "recibí 800 de sueldo"
>
> **Lucho**: "¡Buenísimo! Ingreso: $800. Tu balance este mes: +$350."

> **Usuario**: "mi bro me pagó los 30 que le presté"
>
> **Lucho**: "Anotado. +$30 de pago recibido. ¿Querés que lo ponga como 'préstamo recuperado'?"

### 2.3 Consultar estado

> **Usuario**: "¿cuánto llevo gastado este mes?"
>
> **Lucho**: "Julio: $580 gastados de $1,000 presupuestados. Te quedan $420. Tu categoría top: alimentación ($230)."

> **Usuario**: "¿en qué gasté más?"
>
> **Lucho**: "Este mes: 1️⃣ Alimentación $230, 2️⃣ Transporte $120, 3️⃣ Servicios $95, 4️⃣ Entretenimiento $80, 5️⃣ Otros $55."

> **Usuario**: "mis gastos de la semana pasada"
>
> **Lucho**: "Semana 14-20 julio: $145 en 5 gastos. Lo más fuerte: súper $65 el martes."

### 2.4 Presupuestos

> **Usuario**: "ponme un presupuesto de 300 para comida al mes"
>
> **Lucho**: "Listo. Presupuesto: Alimentación $300/mes. Te aviso si te pasás."

> **Usuario**: "como voy con el presupuesto de comida"
>
> **Lucho**: "Comida: $230 de $300 (76%). Te quedan $70 para los próximos 10 días. Vas bien."

### 2.5 Alertas (vía scheduler)

> *[8:00 AM]* **Lucho**: "⚠️ Ya gastaste el 90% de tu presupuesto de entretenimiento este mes ($180 de $200). Te quedan $20."

> *[8:00 AM]* **Lucho**: "📊 Resumen semanal: gastaste $340 esta semana. La categoría con más gasto fue alimentación ($145)."

---

## 3. Modelo de Datos

### 3.1 Tabla `transactions`

```sql
CREATE TABLE transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),

    -- Tipo: 'expense' (gasto) o 'income' (ingreso)
    type transaction_type NOT NULL,  -- ENUM: 'expense', 'income'

    -- Monto (siempre positivo, el tipo define si es + o -)
    amount DECIMAL(12,2) NOT NULL CHECK (amount > 0),

    -- Categoría predefinida
    category transaction_category NOT NULL,
    -- ENUM: 'food', 'transport', 'housing', 'health',
    --       'entertainment', 'services', 'education',
    --       'clothing', 'salary', 'business', 'gift',
    --       'investment', 'other_income', 'other_expense'

    -- Descripción en lenguaje natural (lo que dijo el usuario)
    description VARCHAR(500),

    -- Fecha del gasto/ingreso (puede ser distinta a created_at)
    transaction_date TIMESTAMP NOT NULL DEFAULT now(),

    -- Notas adicionales
    notes TEXT,

    -- Cuenta o método de pago (opcional)
    payment_method VARCHAR(50),  -- 'cash', 'debit', 'credit', 'transfer'

    -- Metadatos flexibles
    attributes JSONB DEFAULT '{}',

    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX idx_transactions_user_id ON transactions(user_id);
CREATE INDEX idx_transactions_date ON transactions(transaction_date);
CREATE INDEX idx_transactions_type ON transactions(type);
CREATE INDEX idx_transactions_category ON transactions(category);
CREATE INDEX idx_transactions_user_date ON transactions(user_id, transaction_date DESC);
```

### 3.2 Tabla `budgets`

```sql
CREATE TABLE budgets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),

    -- Categoría a presupuestar
    category transaction_category NOT NULL,

    -- Monto del presupuesto
    amount DECIMAL(12,2) NOT NULL CHECK (amount > 0),

    -- Período: 'monthly' (mensual), 'weekly' (semanal)
    period budget_period NOT NULL DEFAULT 'monthly',
    -- ENUM: 'monthly', 'weekly'

    -- Alerta cuando se alcanza este % (ej: 80 = avisa al 80%)
    alert_threshold INTEGER NOT NULL DEFAULT 80 CHECK (alert_threshold BETWEEN 1 AND 100),

    -- ¿Activo?
    is_active BOOLEAN NOT NULL DEFAULT true,

    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX idx_budgets_user_id ON budgets(user_id);
CREATE UNIQUE INDEX idx_budgets_user_category ON budgets(user_id, category) WHERE is_active = true;
```

**Nota sobre ENUMs**: Se crearán dos ENUMs en PostgreSQL:
- `transaction_type`: `'expense'`, `'income'`
- `transaction_category`: `'food'`, `'transport'`, `'housing'`, `'health'`, `'entertainment'`, `'services'`, `'education'`, `'clothing'`, `'salary'`, `'business'`, `'gift'`, `'investment'`, `'other_income'`, `'other_expense'`
- `budget_period`: `'monthly'`, `'weekly'`

### 3.3 Categorías predefinidas — mapeo semántico

| Categoría | ENUM | Palabras clave (para el LLM) | Ejemplos |
|-----------|------|------------------------------|----------|
| 🍔 Alimentación | `food` | almuerzo, cena, súper, mercado, restaurante, delivery, comida | "gasté 20 en pollo asado" |
| 🚗 Transporte | `transport` | gasolina, taxi, bus, Uber, metro, pasaje, peaje | "pagué 45 de gasolina" |
| 🏠 Vivienda | `housing` | arriendo, renta, condominio, hipoteca, reparación | "pagué el arriendo 500" |
| 🏥 Salud | `health` | médico, dentista, farmacia, medicinas, seguro, consulta | "compré medicinas 35" |
| 🎮 Entretenimiento | `entertainment` | cine, Netflix, concierto, fiesta, juego, hobby | "entradas al cine 12.50" |
| ⚡ Servicios | `services` | luz, agua, internet, teléfono, gas, streaming | "pagué la luz 50" |
| 📚 Educación | `education` | curso, libro, universidad, colegio, taller | "curso online 60" |
| 👕 Ropa | `clothing` | ropa, zapatos, camisa, pantalón | "zapatos 80" |
| 💰 Salario | `salary` | sueldo, salario, quincena, honorarios | "recibí 800 de sueldo" |
| 💼 Negocio | `business` | venta, cliente, freelance, emprendimiento | "me pagaron 200 por el diseño" |
| 🎁 Regalo | `gift` | regalo, cumpleaños, navidad, detalle | "regalo para mi mamá 30" |
| 📈 Inversión | `investment` | inversión, acciones, crypto, ahorro | "compré 50 en acciones" |
| ➕ Otro ingreso | `other_income` | reembolso, préstamo recuperado, devolución | "me devolvieron 20" |
| ➖ Otro gasto | `other_expense` | cualquier cosa que no encaje | "gasté 15 en no sé qué" |

---

## 4. Tools del Agente

### 4.1 `add_transaction` — Registrar gasto o ingreso

```json
{
  "name": "add_transaction",
  "description": "Registra un gasto o ingreso en la cuenta personal del usuario.",
  "parameters": {
    "type": "object",
    "properties": {
      "type": {
        "type": "string",
        "enum": ["expense", "income"],
        "description": "'expense' si es un gasto, 'income' si es un ingreso"
      },
      "amount": {
        "type": "number",
        "description": "Monto en dólares (positivo)"
      },
      "category": {
        "type": "string",
        "description": "Categoría del gasto/ingreso. Ver tabla de categorías."
      },
      "description": {
        "type": "string",
        "description": "Descripción corta en lenguaje natural"
      },
      "transaction_date": {
        "type": "string",
        "description": "Fecha del gasto (YYYY-MM-DD). Si es hoy, omitir."
      },
      "payment_method": {
        "type": "string",
        "description": "Método de pago: 'cash', 'debit', 'credit', 'transfer'. Opcional."
      }
    },
    "required": ["type", "amount", "category", "description"]
  }
}
```

### 4.2 `list_transactions` — Consultar gastos

```json
{
  "name": "list_transactions",
  "description": "Consulta gastos e ingresos del usuario por período y categoría.",
  "parameters": {
    "type": "object",
    "properties": {
      "type": {
        "type": "string",
        "enum": ["expense", "income", "all"],
        "description": "Filtrar por tipo. Default: 'all'"
      },
      "category": {
        "type": "string",
        "description": "Filtrar por categoría. Opcional."
      },
      "period": {
        "type": "string",
        "enum": ["today", "yesterday", "this_week", "last_week", "this_month", "last_month", "custom"],
        "description": "Período a consultar. Default: 'this_month'"
      },
      "group_by": {
        "type": "string",
        "enum": ["none", "category", "day", "week"],
        "description": "Agrupar resultados. Default: 'none'"
      }
    },
    "required": []
  }
}
```

### 4.3 `get_balance` — Ver balance

```json
{
  "name": "get_balance",
  "description": "Obtiene el balance financiero del usuario: ingresos, gastos y saldo.",
  "parameters": {
    "type": "object",
    "properties": {
      "period": {
        "type": "string",
        "enum": ["this_month", "last_month", "this_year"],
        "description": "Período. Default: 'this_month'"
      }
    },
    "required": []
  }
}
```

### 4.4 `set_budget` — Configurar presupuesto

```json
{
  "name": "set_budget",
  "description": "Configura un presupuesto mensual o semanal por categoría.",
  "parameters": {
    "type": "object",
    "properties": {
      "category": {
        "type": "string",
        "description": "Categoría a presupuestar"
      },
      "amount": {
        "type": "number",
        "description": "Monto máximo del presupuesto"
      },
      "period": {
        "type": "string",
        "enum": ["monthly", "weekly"],
        "description": "Período del presupuesto. Default: 'monthly'"
      },
      "alert_threshold": {
        "type": "integer",
        "description": "Porcentaje al que alertar (ej: 80). Default: 80"
      }
    },
    "required": ["category", "amount"]
  }
}
```

### 4.5 `check_budget` — Revisar estado de presupuestos

```json
{
  "name": "check_budget",
  "description": "Revisa el estado de los presupuestos activos del usuario.",
  "parameters": {
    "type": "object",
    "properties": {
      "category": {
        "type": "string",
        "description": "Categoría específica. Si no se especifica, muestra todas."
      }
    },
    "required": []
  }
}
```

---

## 5. Flujo de Extracción con LLM

Cuando el usuario dice algo como *"gasté 20 dólares en almuerzo"*, el LLM debe extraer:

```json
{
  "type": "expense",
  "amount": 20.00,
  "category": "food",
  "description": "Almuerzo",
  "transaction_date": "2026-07-21",
  "payment_method": null
}
```

**Reglas de extracción**:
- Si el usuario dice "gasté", "pagué", "compré", "me costó" → `expense`
- Si el usuario dice "recibí", "cobré", "me pagaron", "ingresó" → `income`
- Si no se puede determinar la categoría → preguntar al usuario
- Monto siempre positivo, sin símbolos de moneda en el número
- Fecha: si no la menciona, es HOY

### Prompt de extracción para el router:

```
"transaction": 'Extrae: {"type": "expense|income", "amount": 0.00, "category": "CATEGORIA",
"description": "descripción", "transaction_date": "YYYY-MM-DD o null si es hoy"}.
CATEGORIAS GASTO: food, transport, housing, health, entertainment, services, education, clothing, other_expense.
CATEGORIAS INGRESO: salary, business, gift, investment, other_income.
Si el usuario dice "gasté/pagué/compré" → expense. Si dice "recibí/cobré/me pagaron" → income.
Si la categoría no es clara, usá la que mejor encaje según el contexto. Si realmente no sabés, usá other_expense o other_income.'
```

---

## 6. Scheduler — Alertas de Presupuesto

### Job diario (8:00 AM) — `_evaluate_budgets()`

Para cada usuario con presupuestos activos:
1. Consultar gastos del mes en curso para cada categoría con presupuesto
2. Calcular `% gastado = (gastado / presupuesto) * 100`
3. Si `% gastado >= alert_threshold` → enviar notificación

**Mensaje de alerta** (Telegram / WhatsApp directo dentro de 24h, template fuera de 24h):

> ⚠️ *Alerta de presupuesto*
> 🍔 Alimentación: $230 de $300 (76%)
> Te quedan $70 para los próximos 10 días.

### Template WhatsApp: `budget_alert` (a crear en Meta)

| Campo | Valor |
|-------|-------|
| Nombre | `budget_alert` |
| Categoría | `UTILITY` |
| Params | 5: {{1}}=emoji, {{2}}=categoría, {{3}}=gastado, {{4}}=presupuesto, {{5}}=porcentaje |

---

## 7. Resumen Mensual

Cada día 1 del mes a las 8:00 AM, el scheduler dispara `run_monthly_summary()`:

1. Calcula total de ingresos y gastos del mes anterior
2. Agrupa por categoría
3. Compara con presupuestos
4. Genera resumen vía LLM (usando datos reales de la DB, sin alucinar)

> 📊 *Resumen de julio*
> 💸 Gastaste $1,240 en total
> 💰 Ingresos: $1,500
> 📈 Balance: +$260
>
> Tu top 3:
> 🍔 Alimentación: $380 (31%)
> 🚗 Transporte: $220 (18%)
> ⚡ Servicios: $180 (15%)
>
> Presupuestos:
> ✅ Alimentación: $380 de $400 (95%)
> ⚠️ Entretenimiento: $195 de $200 (casi al límite)
>
> ¡Buen mes! ¿Querés ajustar algún presupuesto?

---

## 8. Reglas de Negocio (Deterministas)

1. **Un presupuesto por categoría activo**: No puede haber dos presupuestos activos para la misma categoría.
2. **Categoría obligatoria**: Todo gasto/ingreso DEBE tener categoría. Si el LLM no la puede inferir, preguntar.
3. **Montos positivos**: El campo `amount` siempre es positivo. El tipo (`expense`/`income`) define el signo.
4. **Períodos calendario**: "este mes" = 1 al último día del mes actual. "esta semana" = lunes a domingo.
5. **Balance = ingresos - gastos**: Simple, sin carry-over entre meses.
6. **Alertas no repetitivas**: Si ya se alertó del presupuesto hoy, no volver a alertar (marcar en `budgets.attributes`).

---

## 9. Implementación Técnica

### 9.1 Archivos a crear/modificar

| Archivo | Acción |
|---------|--------|
| `app/models/transaction.py` | 🆕 Transaction + Budget models |
| `app/models/__init__.py` | 🔧 Registrar nuevos modelos |
| `alembic/versions/` | 🆕 Migración: transactions + budgets + ENUMs |
| `app/agent/tools.py` | 🔧 +2 handlers, +3 tool schemas (add/list/get_balance) |
| `app/services/persistence.py` | 🔧 +persist_transaction, +persist_budget |
| `app/services/scheduler.py` | 🔧 +_evaluate_budgets, +run_monthly_summary |
| `app/services/search.py` | 🔧 +query_transactions, +get_balance |
| `app/services/llm/base.py` | 🔧 +transaction extraction prompt |
| `docs/whatsapp_templates.md` | 🔧 +budget_alert template spec |
| `tests/unit.py` | 🔧 +transaction/budget tests |

### 9.2 Tools totales después del módulo

| # | Tool | Módulo |
|---|------|--------|
| 1-22 | (existentes) | Vehículos, Docs, Eventos, etc. |
| 23 | `add_transaction` 🆕 | Finanzas |
| 24 | `list_transactions` 🆕 | Finanzas |
| 25 | `get_balance` 🆕 | Finanzas |
| 26 | `set_budget` 🆕 | Finanzas |
| 27 | `check_budget` 🆕 | Finanzas |

---

## 10. Fuera de Alcance (v1)

- ❌ Subir PDFs o fotos de facturas y extraer datos
- ❌ Sincronización con bancos
- ❌ Múltiples cuentas (efectivo, tarjetas separadas)
- ❌ Gastos compartidos avanzados (ya existe `shared_expenses` básico)
- ❌ Exportación a Excel/CSV
- ❌ Gráficos o visualizaciones
- ❌ Metas de ahorro
