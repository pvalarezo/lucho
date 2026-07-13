# NEXT_SESSION.md — Lucho

---

## Sesión actual — 2026-07-12 (REDISEÑO A AGENTE)

**Arquitectura de agente completada. Fase 1 cerrada con rediseño mayor.**

### Entregables de la sesión:
- ✅ System prompt unificado: `lucho_system_prompt.py` (identidad, personalidad, límites)
- ✅ 11 tools con function calling (DeepSeek): save_vehicle, save_document, save_event, save_list, save_note, save_expense, search_my_data, search_conversation, get_my_summary, update_last, check_vehicle_info
- ✅ Agent loop con tool-calling (máx 3 rondas)
- ✅ Memoria de conversación multi-turno (historial desde PostgreSQL)
- ✅ Skills Ecuador: modismos, matriculación ANT, pico y placa Quito/Cuenca (3 MD + loader automático)
- ✅ API externa: consulta vehicular ANT/SRI/multas por placa (check_vehicle_info)
- ✅ Búsqueda en historial de chat (search_conversation)
- ✅ Código viejo eliminado: router.py, extractor.py (~350 líneas menos)
- ✅ Webhook de producción actualizado al agente
- ✅ Bot Telegram funcionando con arquitectura de agente
- ✅ PROGRESS.md y NEXT_SESSION.md actualizados
- ⬚ Tests actualizados para reflejar nueva arquitectura

### Tags creados hoy:
```
v2.0.0 — Rediseño a arquitectura de agente
```

---

## Próxima sesión — Prioridades

### 🔴 ALTA PRIORIDAD

**1. OCR/Visión de facturas**
Extraer datos estructurados de facturas ecuatorianas usando DeepSeek Vision:
- RUC del emisor
- Total, subtotal, IVA
- Fecha de emisión
- Ítems o descripción
- Guardar como asset tipo "factura" con atributos JSONB

**2. Actualizar tests**
La suite de tests (tests/suite.py, tests/stress.py) referencia el pipeline viejo (router, extractor). Actualizar para probar el agente.

**3. Resumen diario/semanal programado**
APScheduler que arme un digest con:
- Próximos vencimientos (7 días)
- Pendientes sin completar
- Pico y placa del día
- Eventos del día
Enviar vía Telegram al usuario (opt-in).

### 🟡 MEDIA PRIORIDAD

**4. Skills Ecuador adicionales**
- `sri/facturacion.md` — IVA, RUC, retenciones, facturación electrónica
- `legal/documentos.md` — Cédula, pasaporte, licencia, vigencia, renovación
- `transito/multas.md` — Tipos de multas, cómo pagar, puntos licencia

**5. Mejorar manejo de fotos**
- Vincular fotos a documentos guardados
- Enviar foto del documento cuando el usuario la pide ("pasame mi cédula")

### 🟢 BAJA PRIORIDAD

**6. Web search tool para Lucho**
Usar DeepSeek search o DuckDuckGo para consultas de información actual ecuatoriana (feriados, cambios regulatorios).

**7. Dashboard de métricas**
Precisión del agente, retención, uso por tipo de tool.

---

## Comandos rápidos

```bash
# Entorno
docker compose -f docker-compose.dev.yml up -d
python3 run_bot.py

# API
uvicorn app.main:app --port 8000

# Tests
python3 tests/suite.py      # 41 casos (necesita actualización)
python3 tests/stress.py     # 57 casos (necesita actualización)
python3 tests/embeddings.py # 12 casos (semántica)

# Git
git add -A && git commit -m "mensaje"
git tag v2.0.0 -m "Arquitectura de agente"
git push --tags
```
