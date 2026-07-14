# NEXT_SESSION.md — Lucho

---

## Sesión actual — 2026-07-13

**v2.6.0 — Refactor file_key, flujo archivos, regla #0**

### Entregables de la sesión:

#### v2.4.0 — Skills Ecuador (7 skills)
- ✅ `culture/idioms.md`, `cuisine.md`, `holidays.md`
- ✅ `legal/documents.md` — Cédula, pasaporte, licencia, partidas
- ✅ `tax/invoicing.md` — IVA 15%, RUC, facturación electrónica, retenciones
- ✅ `transit/registration.md`, `driving-restrictions.md`
- ✅ Estructura migrada a inglés, loader con keywords

#### v2.5.0 — Tests
- ✅ `tests/unit.py` — 267 tests offline (100% pass)
- ✅ `tests/suite.py` — 10 categorías para arquitectura agente
- ✅ `tests/stress.py` — 10 categorías de estrés

#### v2.6.0 — Refactor mayor
- ✅ `photo_key` → `file_key` en 6 archivos (clave universal de almacenamiento)
- ✅ `MAX_TOOL_ROUNDS` 3 → 5 (evita "me enredé")
- ✅ Flujo de archivos: NADA se guarda automático, siempre pregunta
- ✅ `save_document`: agregado parámetro `file_key` al schema
- ✅ `webhook.py`: upload de fotos/documentos a MinIO (paridad con bot.py)
- ✅ System prompt: regla #0 "NUNCA MIENTAS", `[foto: X]` y `[documento: ...]` documentados
- ✅ Respuestas sin Markdown (elimina errores 400 con nombres de archivo)
- ✅ `telegram.py`: fallback si Markdown falla → plain text

### Tags aplicados:
```
v2.6.0 — file_key rename, no auto-save, regla #0 NUNCA MIENTAS, webhook parity, no Markdown
v2.5.0 — Tests: 267 unit offline + suite + stress
v2.4.0 — Skills Ecuador: 7 skills en 4 dominios
v2.3.0 — Envío de fotos: tool send_photo, búsqueda docs, respuesta dict
```

---

## Próxima sesión — Prioridades

### 🟡 MEDIA

**1. Web search tool**
Consultar información actual ecuatoriana (feriados, cambios regulatorios) vía DuckDuckGo.

### 🟢 BAJA

**2. Indexado numerado en búsquedas**
Para evitar búsqueda frágil por nombre: presentar resultados numerados (1, 2, 3) y aceptar "el 2".

**3. Skills adicionales (opcional)**
- `services/transport.md` — Metro Quito, Metrovía, Tranvía Cuenca, buses
- `services/utilities.md` — Planilla de luz, subsidios, tarifas

**4. Dashboard de métricas**
Precisión del agente, retención, uso por tipo de tool.

---

## Comandos rápidos

```bash
# Entorno
docker compose -f docker-compose.dev.yml up -d
python3 run_bot.py

# Git
git add -A && git commit -m "mensaje"
git tag v2.6.0 -m "descripción"
```
