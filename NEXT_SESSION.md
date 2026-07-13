# NEXT_SESSION.md — Lucho

---

## Sesión actual — 2026-07-12 (REDISEÑO A AGENTE + OCR + DIGEST)

**Arquitectura de agente completada. OCR y resumen diario implementados.**

### Entregables de la sesión:
- ✅ System prompt unificado: `lucho_system_prompt.py`
- ✅ 12 tools con function calling
- ✅ Agent loop con tool-calling + memoria de conversación
- ✅ Skills Ecuador: modismos, matriculación ANT, pico y placa (3 MD)
- ✅ API vehicular externa (ANT/SRI/multas)
- ✅ Búsqueda en historial de chat (search_conversation)
- ✅ OCR documentos vía Anthropic Claude Vision (analyze_image)
- ✅ Resumen diario automático 8:00 AM (daily_digest con agente)
- ✅ Soporte para documentos/PDFs en Telegram
- ✅ Fotos adjuntables cross-entity (eventos, notas, documentos)
- ✅ Código viejo eliminado (router.py, extractor.py)
- ✅ PROGRESS.md, ROADMAP.md, NEXT_SESSION.md actualizados
- ⬚ Tests actualizados para reflejar nueva arquitectura

### Tags creados:
```
v2.0.0 — Rediseño a arquitectura de agente
v2.1.0 — OCR documentos, digest diario, documentos/PDFs
```

---

## Próxima sesión — Prioridades

### 🔴 ALTA PRIORIDAD

**1. Proyectos y Tareas**
Las tablas `projects` y `project_tasks` ya existen. Falta la tool:
- `save_project_task(project_name, content, due_date)` — guardar tarea en proyecto
- `list_project_tasks(project_name)` — listar tareas de un proyecto
- El agente debe detectar cuando el usuario habla de un proyecto y enrutar a esta tool

**2. Actualizar tests**
La suite de tests referencia el pipeline viejo. Actualizar para probar el agente con las 12 tools.

### 🟡 MEDIA PRIORIDAD

**3. Contactos**
La tabla `contacts` ya existe. Agregar tool:
- `save_contact(name, phone, relationship)` — guardar contacto
- `list_contacts()` — listar contactos
- Vincular contactos a gastos compartidos y eventos

**4. Envío de fotos al usuario**
Cuando el usuario pide "pasame mi cédula" o "mostrame el SOAT", Lucho debe enviar la imagen desde MinIO. Ya extrae los datos, falta enviar el archivo.

**5. Skills Ecuador adicionales**
- `sri/facturacion.md` — IVA, RUC, retenciones
- `legal/documentos.md` — Cédula, pasaporte, licencia

### 🟢 BAJA PRIORIDAD

**6. Web search tool para Lucho**
Consultar información actual ecuatoriana (feriados, cambios regulatorios).

**7. Dashboard de métricas**
Precisión del agente, retención, uso por tipo de tool.

---

## Inventario de funcionalidades

| # | Funcionalidad | Estado |
|---|--------------|--------|
| 1 | Vehículos (guardar, ANT/SRI) | ✅ Completo |
| 2 | Documentos (cédula, SOAT, OCR) | ✅ Completo |
| 3 | Eventos/Recordatorios + scheduler | ✅ Completo |
| 4 | Listas (compras, tareas) | ✅ Completo |
| 5 | Notas por tema | ✅ Completo |
| 6 | Gastos compartidos | ✅ Básico |
| 7 | Búsqueda (datos + historial) | ✅ Completo |
| 8 | Resumen diario automático | ✅ Completo |
| 9 | Correcciones | ✅ Completo |
| 10 | Conversación natural + memoria | ✅ Completo |
| 11 | Skills Ecuador | ✅ Completo |
| 12 | Proyectos y Tareas | ⬚ Pendiente |
| 13 | Contactos | ⬚ Pendiente |
| 14 | Envío de fotos al usuario | ⬚ Pendiente |

---

## Comandos rápidos

```bash
# Entorno
docker compose -f docker-compose.dev.yml up -d
python3 run_bot.py

# Git
git add -A && git commit -m "mensaje"
git tag v2.1.0 -m "OCR + digest diario"
```
