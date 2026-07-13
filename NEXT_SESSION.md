# NEXT_SESSION.md — Lucho

---

## Sesión actual — 2026-07-12 (MARATÓN v2.0 → v2.2.0)

**Rediseño completo a arquitectura de agente. 3 versiones en una sesión.**

### Entregables:
- ✅ Arquitectura de agente: system prompt unificado + 17 tools con function calling
- ✅ Agent loop con tool-calling + memoria de conversación multi-turno
- ✅ Skills Ecuador: modismos, matriculación ANT, pico y placa (3 MD + loader)
- ✅ API vehicular externa (ANT/SRI/multas por placa)
- ✅ Búsqueda en historial de chat
- ✅ OCR documentos vía Anthropic Claude Vision (cédula, SOAT, factura)
- ✅ Resumen diario automático 8:00 AM (daily_digest)
- ✅ Soporte documentos/PDFs en Telegram
- ✅ Fotos adjuntables cross-entity (eventos, notas, documentos)
- ✅ Proyectos y Tareas (3 tools + recordatorios)
- ✅ Contactos (2 tools: save + list, con email y WhatsApp)
- ✅ Recordatorios unificados: eventos 15/7/3/0, documentos 30/15/7, proyectos 7/3/1
- ✅ Canal de notificaciones agnóstico: Telegram + placeholders WhatsApp/email/SMS
- ✅ Código viejo eliminado (router.py, extractor.py)
- ✅ Webhook producción actualizado al agente
- ✅ 19 columnas nuevas (contacts.email)
- ✅ PROGRESS.md, ROADMAP.md, NEXT_SESSION.md actualizados

### Tags:
```
v2.0.0 — Rediseño a arquitectura de agente
v2.1.0 — OCR documentos, digest diario, documentos/PDFs
v2.2.0 — Proyectos/tareas, recordatorios unificados, contactos
```

---

## Próxima sesión — Prioridades

### 🔴 ALTA

**1. Envío de fotos al usuario**
Cuando el usuario pide "pasame mi cédula" o "mostrame el SOAT", Lucho debe enviar la imagen desde MinIO. Ya extrae datos, falta enviar el archivo como foto de Telegram.

### 🟡 MEDIA

**2. Skills Ecuador adicionales**
- `sri/facturacion.md` — IVA, RUC, retenciones, facturación electrónica
- `legal/documentos.md` — Cédula, pasaporte, licencia, vigencia, renovación

**3. Tests actualizados**
La suite de tests referencia el pipeline viejo. Actualizar para probar el agente con las 17 tools.

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
