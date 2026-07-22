# Módulo de Vehículos — Especificación v1.0

---

## 1. Visión General

Lucho gestiona vehículos del usuario con reglas deterministas para Ecuador: matrícula, pico y placa, SOAT, RTV y mantenimientos. El usuario dicta la placa, Lucho calcula automáticamente las fechas clave usando el motor de reglas (`vehicle_rules.py`) y envía recordatorios proactivos.

Máximo **2 vehículos por usuario** (según plan de suscripción).

---

## 2. Experiencia de Usuario

### 2.1 Guardar un vehículo

> **Usuario**: "mi carro es un Toyota Corolla, placa PBC-1234, año 2020"
>
> **Lucho**: "Listo. PBC-1234 guardado. Pico y placa: lunes. Próxima matriculación: 2026-08-31."

### 2.2 Consultar vehículos

> **Usuario**: "¿qué carros tengo?"
>
> **Lucho**: "🚗 PBC-1234 — Toyota Corolla 2020 — Pico y placa: lunes — Matriculación: 2026-08-31"

### 2.3 Consultar por placa (API externa)

> **Usuario**: "consulta la placa PBC1234"
>
> **Lucho**: *[consulta API de vehículos]* "PBC1234 — Toyota Corolla 2020 — Cilindraje: 1800cc — Último año pagado: 2025 — Sin multas pendientes."

### 2.4 Registrar mantenimiento

> **Usuario**: "le hice cambio de aceite al PBC-1234, 45 dólares, 85000 km, en Tecnicentro"
>
> **Lucho**: "Registrado: cambio de aceite para PBC-1234, $45, 85000 km en Tecnicentro."

### 2.5 Recordatorios

> *[8:00 AM, día de pico y placa]* **Lucho**: "🚫 *Pico y placa* — PBC-1234 no circula hoy. Días restringidos: lunes."

---

## 3. Modelo de Datos

### 3.1 Tabla `vehicles`

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | UUID | PK |
| `user_id` | UUID FK | Dueño |
| `plate` | VARCHAR(16) | Placa en mayúsculas sin guión: "PBC1234" |
| `brand` | VARCHAR(64) | Marca |
| `model` | VARCHAR(64) | Modelo |
| `year` | INTEGER | Año |
| `color` | VARCHAR(32) | Color |
| `engine_number` | VARCHAR(64) | Número de motor |
| `chassis_number` | VARCHAR(64) | Número de chasis |
| `last_digit` | INTEGER | Último dígito de placa (calculado) |
| `pico_y_placa_days` | VARCHAR(64) | Días restringidos: "Lunes", "Lunes y Viernes" |
| `next_matriculation` | DATE | Próxima fecha de matriculación (calculada) |
| `soat_expiry` | DATE | Vencimiento SOAT |
| `rtv_expiry` | DATE | Vencimiento RTV |
| `notes` | TEXT | Notas adicionales |
| `deleted_at` | TIMESTAMPTZ | Soft delete |
| `created_at` | TIMESTAMPTZ | Fecha creación |
| `updated_at` | TIMESTAMPTZ | Última modificación |

### 3.2 Tabla `vehicle_maintenances`

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | UUID | PK |
| `vehicle_id` | UUID FK | Vehículo |
| `maintenance_type` | ENUM | `oil_change`, `brakes`, `tires`, `battery`, `general`, `other` |
| `description` | TEXT | Descripción |
| `cost` | FLOAT | Costo en USD |
| `mileage_km` | INTEGER | Kilometraje |
| `performed_at` | DATE | Fecha del mantenimiento |
| `performed_by` | VARCHAR(128) | Taller o mecánico |
| `next_at` | DATE | Próximo mantenimiento sugerido |
| `next_mileage_km` | INTEGER | Próximo kilometraje sugerido |
| `receipt_file_key` | VARCHAR(256) | Factura en MinIO |
| `notes` | TEXT | Notas |
| `created_at` | TIMESTAMPTZ | Fecha creación |
| `updated_at` | TIMESTAMPTZ | Última modificación |

### 3.3 ENUMs

```sql
maintenance_type: 'oil_change', 'brakes', 'tires', 'battery', 'general', 'other'
```

---

## 4. Motor de Reglas (`vehicle_rules.py`)

Determinista, sin acceso a base de datos. Calcula a partir de la placa:

| Regla | Lógica | Fuente |
|-------|--------|--------|
| **Matriculación** | Último dígito → mes. Fecha = último día hábil del mes. | ANT Ecuador |
| **Pico y placa** | Último dígito → días de restricción (Quito). | AMT Quito |
| **SOAT / RTV** | Anual, vence con la matrícula. | Ley de tránsito |

---

## 5. Tools del Agente

### 5.1 `save_vehicle` — ✅

```json
{
  "name": "save_vehicle",
  "description": "Guardar un vehículo. Calcula automáticamente pico y placa, matriculación, SOAT y RTV. Máximo 2 vehículos por usuario.",
  "parameters": {
    "plate": "Placa ecuatoriana (requerido).",
    "brand": "Marca.",
    "model": "Modelo.",
    "year": "Año.",
    "notes": "Notas."
  },
  "required": ["plate"]
}
```

### 5.2 `list_my_vehicles` — ✅

```json
{
  "name": "list_my_vehicles",
  "description": "Listar vehículos con pico y placa, matriculación, SOAT y RTV.",
  "parameters": {},
  "required": []
}
```

### 5.3 `add_maintenance` — ✅

```json
{
  "name": "add_maintenance",
  "description": "Registrar mantenimiento: cambio de aceite, frenos, llantas, batería, general.",
  "parameters": {
    "vehicle_id_or_plate": "ID o placa del vehículo (requerido).",
    "maintenance_type": "oil_change, brakes, tires, battery, general, other (requerido).",
    "description": "Descripción.",
    "cost": "Costo USD.",
    "mileage_km": "Kilometraje.",
    "performed_at": "Fecha YYYY-MM-DD.",
    "performed_by": "Taller.",
    "next_at": "Próximo mantenimiento YYYY-MM-DD.",
    "next_mileage_km": "Próximo kilometraje.",
    "file_key": "Foto factura MinIO."
  },
  "required": ["vehicle_id_or_plate", "maintenance_type"]
}
```

### 5.4 `list_maintenances` — ✅

```json
{
  "name": "list_maintenances",
  "description": "Historial de mantenimientos de un vehículo.",
  "parameters": {
    "vehicle_id_or_plate": "ID o placa (requerido)."
  },
  "required": ["vehicle_id_or_plate"]
}
```

### 5.5 `check_vehicle_info` — ✅

```json
{
  "name": "check_vehicle_info",
  "description": "Consultar API externa: datos SRI, matriculación, multas ANT por placa.",
  "parameters": {
    "plate": "Placa sin guión (requerido)."
  },
  "required": ["plate"]
}
```

### 5.6 `delete_vehicle` — ✅

```json
{
  "name": "delete_vehicle",
  "description": "Eliminar un vehículo (soft delete). Solo cuando el usuario pide explícitamente eliminar.",
  "parameters": {
    "plate": "Placa del vehículo a eliminar (requerido)."
  },
  "required": ["plate"]
}
```

### 5.7 `update_vehicle` — ✅

```json
{
  "name": "update_vehicle",
  "description": "Actualizar datos de un vehículo: placa, marca, modelo, año, color, notas. Si cambia la placa, recalcula pico y placa y matriculación.",
  "parameters": {
    "plate": "Placa actual (requerido para identificar).",
    "new_plate": "Nueva placa.",
    "brand": "Marca.",
    "model": "Modelo.",
    "year": "Año.",
    "color": "Color.",
    "notes": "Notas."
  },
  "required": ["plate"]
}
```

---

## 6. Scheduler

### 6.1 `_evaluate_vehicle_assets()` — Diario 8:00 AM

Recalcula reglas (`vehicle_rules.evaluate_vehicle_rules`) para cada vehículo activo. Si cambiaron `pico_y_placa_days` o `next_matriculation`, actualiza el registro.

### 6.2 `_evaluate_pico_y_placa()` — Diario 8:00 AM

Para cada vehículo, verifica si HOY es día de restricción. Si lo es, envía notificación:

- **Telegram**: mensaje directo
- **WhatsApp**: template `pico_y_placa` (es, aprobado)

**Template `pico_y_placa`** (es) — ya aprobado en Meta ✅

| Param | Contenido |
|-------|-----------|
| {{1}} | Placa |
| {{2}} | Días restringidos |

---

## 7. Reglas de Negocio

1. **Máximo 2 vehículos**: Controlado en `handle_save_vehicle` según `plan.features.max_vehicles`.
2. **Placa única**: No se puede duplicar placa para el mismo usuario (con `deleted_at IS NULL`).
3. **Placa sin guión**: `PBC-1234` → `PBC1234` automáticamente.
4. **Cálculo determinista**: `vehicle_rules.py` no usa DB — solo el último dígito de placa.
5. **Soft delete**: `deleted_at`, no borrado físico.
6. **API externa opcional**: `check_vehicle_info` consulta endpoint externo (requiere token).

---

## 8. Lo que YA existe

| Componente | Estado |
|------------|--------|
| `vehicles` tabla + modelo | ✅ |
| `vehicle_maintenances` tabla + modelo | ✅ |
| `vehicle_rules.py` — motor de reglas determinista | ✅ |
| `save_vehicle` tool — con límite por plan y dedup | ✅ |
| `list_my_vehicles` tool — pico y placa, matriculación, SOAT, RTV | ✅ |
| `add_maintenance` tool — tipo, costo, km, taller | ✅ |
| `list_maintenances` tool — historial por vehículo | ✅ |
| `check_vehicle_info` tool — API externa SRI/ANT | ✅ |
| `delete_vehicle` tool — soft delete (deleted_at) | ✅ |
| `update_vehicle` tool — actualiza campos y recalcula reglas si cambia placa | ✅ |
| `_evaluate_vehicle_assets` scheduler — recalcula reglas | ✅ |
| `_evaluate_pico_y_placa` scheduler — notificación diaria | ✅ |
| `pico_y_placa` WhatsApp template (es) aprobado | ✅ |
| `search_my_data` incluye vehículos | ✅ |

---

## 9. Mejoras pendientes

| Tarea | Prioridad |
|-------|-----------|
| Recordatorios SOAT/RTV (integrar con `_evaluate_documents`) | 🟡 Media |
| Pico y placa para otras ciudades (Cuenca, Guayaquil) | 🟢 Baja |
| Alertas de mantenimiento por kilometraje | ⚪ Futuro |

---

## 10. Fuera de Alcance (v1)

- ❌ Rastreo GPS
- ❌ Multas en tiempo real (solo consulta bajo demanda)
- ❌ Comparador de seguros
- ❌ Más de 2 vehículos (plan premium futuro)
