# NEXT_SESSION.md — Lucho

---

## Sesión actual — 2026-07-13

**Envío de fotos al usuario (v2.3.0)**

### Entregables:
- ✅ Tool `send_photo`: agente puede enviar fotos/docs guardados cuando el usuario pide
- ✅ `handle_search_data` ahora incluye `photo_key` en resultados de vehículos y documentos
- ✅ Nueva sección de búsqueda de documentos (cédula, SOAT, pasaporte, garantía)
- ✅ `process_message` retorna `dict` con `text` + `photos[]` (backward-compatible)
- ✅ `bot.py` envía fotos vía `reply_photo` / documentos vía `reply_document`
- ✅ `webhook.py` envía fotos vía `telegram.send_photo()` (raw API)
- ✅ `scheduler.py` adaptado al nuevo formato de respuesta
- ✅ `telegram.py`: nueva función `send_photo()` (detecta imagen vs documento)
- ✅ System prompt actualizado: regla #7 para `send_photo`

### Tags:
```
v2.3.0 — Envío de fotos: tool send_photo, búsqueda docs, respuesta dict con photos[]
```

---

## Próxima sesión — Prioridades

### 🟡 MEDIA

**1. Skills Ecuador adicionales**
- `sri/facturacion.md` — IVA, RUC, retenciones, facturación electrónica
- `legal/documentos.md` — Cédula, pasaporte, licencia, vigencia, renovación

**2. Tests actualizados**
La suite de tests referencia el pipeline viejo. Actualizar para probar el agente con las 18 tools.

**3. Probar envío de fotos**
- Subir una cédula/SOAT real y probar "pasame mi cédula"
- Probar con documentos PDF

### 🟢 BAJA

**4. Web search tool**
Consultar información actual ecuatoriana (feriados, cambios regulatorios) vía DuckDuckGo.

**5. Dashboard de métricas**
Precisión del agente, retención, uso por tipo de tool.

---

## Comandos rápidos

```bash
# Entorno
docker compose -f docker-compose.dev.yml up -d
python3 run_bot.py

# Git
git add -A && git commit -m "mensaje"
git tag v2.3.0 -m "descripción"
```
