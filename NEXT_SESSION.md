# NEXT_SESSION.md — Lucho

---

## Sesión finalizada — 2026-07-21 (sesión extendida, ~8 horas)

**v2.13.0 — Finanzas + Documentos independiente + 14 specs + brainstorming**

---

### Entregables de la sesión (10 tags)

| Tag | Qué |
|-----|-----|
| v2.10.1 | Templates WhatsApp 4/4 verificados |
| v2.10.2 | Eventos arreglados (no enviaban) + event_reminder spec |
| v2.11.0 | Ad-hoc reminders sub-día (DateTrigger) |
| v2.11.1 | System prompt reforzado anti-alucinaciones |
| v2.11.2 | Hora local Ecuador (cero TZ) |
| v2.12.0 | Módulo Finanzas Personales |
| v2.12.1 | Formato WhatsApp sin tablas |
| v2.12.2 | Prompt incluye finanzas |
| v2.12.3 | Sin ⏳, solo typing indicator |
| v2.12.4 | Onboarding actualizado + docs |
| v2.13.0 | Tabla `documents` independiente, `assets` y `shared_expenses` eliminados |

---

### Archivos creados (13 docs)

| Documento | Tipo |
|-----------|------|
| `docs/finanzas_especificacion.md` | Módulo |
| `docs/documentos_especificacion.md` | Módulo |
| `docs/recordatorios_especificacion.md` | Módulo |
| `docs/listas_especificacion.md` | Módulo |
| `docs/notas_apuntes_especificacion.md` | Módulo |
| `docs/proyectos_tareas_especificacion.md` | Módulo |
| `docs/busqueda_especificacion.md` | Módulo |
| `docs/contactos_especificacion.md` | Módulo |
| `docs/funcionalidades_generales.md` | Sistema |
| `docs/skills_ecuador.md` | Funcionalidad |
| `docs/ideas_nuevos_modulos.md` | Brainstorming |
| `scripts/test_whatsapp_templates.py` | Testing |
| `app/routers/internal_test.py` | Testing |

---

### Cambios estructurales

- `assets` table → eliminada (reemplazada por `documents`)
- `shared_expenses` + `shared_expense_participants` → eliminados (reemplazados por `transactions`)
- `events.target_date` → DATE → TIMESTAMP (hora local Ecuador)
- `save_expense` tool → eliminado (reemplazado por `add_transaction`)
- `Asset` model → eliminado
- `persist_asset()` → eliminado (reemplazado por `persist_document()`)
- Tools: 22 → 26 (5 finanzas + 4 docs - 1 save_expense - 4 removals)
- Tablas: 22 → 23
- Tests: 307 → 348

---

## Próxima sesión — Prioridades

### 🔴 INMEDIATA

**1. Completar tools pendientes**
- [ ] `list_my_documents` — listar docs con filtros
- [ ] `list_items` — consultar ítems por lista
- [ ] `complete_item` — marcar ítems como hechos
- [ ] `list_my_notes` — listar notas por tema

**2. Templates Meta**
- [ ] `event_reminder` (es) — crear en Meta (5 params)
- [ ] `budget_alert` (es) — crear en Meta (5 params)
- [ ] `project_reminder` (es) — esperar traducción

### 🟡 FASE 2 FINAL

**3. Métricas** — extracción correcta, retención D7/D30, intención de pago

### 🟢 FASE 3

**4. Módulos rápidos** — temporizador (extender ad-hoc), APIs Ecuador (clima, noticias)
**5. Pagos** — Kushki/PayPhone, facturación SRI
