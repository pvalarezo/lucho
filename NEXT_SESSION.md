# NEXT_SESSION.md — Lucho

---

## Sesión actual — 2026-07-11 (MARATÓN COMPLETADA)

**Fase 1 del MVP 100% completada en una sesión.**

### Entregables:
- ✅ 19 tablas PostgreSQL + pgvector + migraciones
- ✅ Bot Telegram con polling (funcionando)
- ✅ Pipeline IA: DeepSeek router (9 targets) + extractor + tool system
- ✅ Embeddings locales (sentence-transformers, gratuito)
- ✅ AI Vision: análisis de imágenes sin caption
- ✅ Motor vehicular: matriculación, pico y placa, cron diario
- ✅ Búsqueda semántica + contextual + templates híbridos
- ✅ MinIO: upload/download de documentos
- ✅ Suite de tests: 41/41 normal + 57/57 stress + 12/12 embeddings
- ✅ 23 tags: v0.1.0 → v1.5.2

### Tags creados hoy:
```
v0.1.0 → v0.2.0 → v0.2.1 → v0.3.0 → v0.4.0 → v0.5.0 → v0.6.0
→ v0.7.0 → v0.8.0 → v0.9.0 → v0.9.1 → v0.9.2 → v0.10.0
→ v0.10.1 → v0.10.2 → v0.10.3 → v0.10.4 → v0.11.0 → v0.12.0
→ v0.13.0 → v1.0.0 → v1.1.0 → v1.2.0 → v1.3.0 → v1.3.1
→ v1.4.0 → v1.4.1 → v1.5.0 → v1.5.1 → v1.5.2
```

---

## Próxima sesión — Prioridades

### 🔴 ALTA PRIORIDAD

**1. Documento de sistema (System Prompt / Knowledge Base)**
Crear un documento `SYSTEM.md` o `app/knowledge/base.py` que contenga:
- Identidad de Lucho: quién es, personalidad, tono
- Capacidades completas: qué puede y qué no puede hacer
- Límites y guardrails: hasta dónde llega
- Contexto Ecuador: regulaciones, cultura, modismos
- Formato de respuestas: cómo debe contestar

Este documento se inyecta en los prompts del LLM para que TODAS las respuestas (meta, confirmaciones, búsquedas) sean naturales y contextuales, sin textos quemados en código. Es la "personalidad" de Lucho.

**2. Vista `searchable_content`**
Crear la vista SQL que unifica notes + list_items + assets para búsqueda global.

**3. OCR/Visión de facturas**
Extraer datos estructurados de facturas ecuatorianas (RUC, total, fecha, ítems) usando DeepSeek Vision.

### 🟡 MEDIA PRIORIDAD

**4. Resumen diario/semanal programado**
APScheduler que envíe un digest al usuario con: próximos vencimientos, pendientes, pico y placa del día.

**5. Mejorar extracción de documentos**
- Extraer `document_type` (cédula vs pasaporte vs licencia)
- Alertas de vencimiento para documentos
- Vincular eventos automáticos a documentos

### 🟢 BAJA PRIORIDAD

**6. Comandos de voz mejorados**
Mejorar el flujo de notas de voz con confirmación más natural.

**7. Dashboard de métricas**
Precisión del router, retención, uso por tipo de mensaje.

---

## Comandos rápidos

```bash
# Entorno
docker compose -f docker-compose.dev.yml up -d
python3 run_bot.py

# API
uvicorn app.main:app --port 8000

# Tests
python3 tests/suite.py      # 41 casos
python3 tests/stress.py     # 57 casos (ortografía, contexto)
python3 tests/embeddings.py # 12 casos (semántica)
```
