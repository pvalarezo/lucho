# NEXT_SESSION.md — Lucho

---

## Sesión finalizada — 2026-07-19

**v2.9.4 — WhatsApp multimedia, stickers, anti-alucinación**

### Entregables completados:

#### 📷 WhatsApp Multimedia (problema #1)
- Imágenes: descarga de WhatsApp → subida a MinIO → `file_key` real para el agente
- Audio/Voz: descarga → MinIO → transcripción con Whisper → texto transcrito al agente
- Documentos: descarga → MinIO → `file_key` real
- Formato unificado con Telegram: `[foto: file_key] {instrucción}`

#### 😅 Stickers (problema #2)
- Respuesta amable: "Todavía no puedo ver stickers 😅. Mandame texto, foto o audio y con gusto te ayudo."
- Tipos desconocidos también responden con mensaje informativo

#### 🔗 Inyección de file_key
- Cuando un texto menciona "foto", "imagen", "guarda", etc., busca la foto más reciente (últimos 2 min) e inyecta su `file_key` en el contexto
- Resuelve el problema WhatsApp vs Telegram: en WhatsApp foto y texto son mensajes separados

#### ⚡ Foto sin instrucción
- Si solo hay foto sin texto, NO llama al agente. Envía confirmación rápida: "📷 Recibí tu foto. ¿Querés que la analice, la guarde, o qué hacemos?"
- Ahorra un round-trip al LLM

#### 🧠 System prompt anti-alucinación (problema #3)
- Regla #0 reescrita: lista explícita de tools de escritura OBLIGATORIAS
- Flujo obligatorio: **primero tool → si success → después confirmar**
- Ejemplos corregidos: ahora muestran el tool call ANTES del "guardé"
- Ejemplo agregado de save_list

#### 📨 Template WhatsApp
- `send_template_message` ahora acepta `body_params` para plantillas con variables
- Template `initial_greeting` probado: funciona con `language_code="en"` (Meta lo aprobó en inglés)

#### 🧹 Limpieza de datos
- PostgreSQL: 20 tablas truncadas
- MinIO: 6 objetos eliminados
- Plan de suscripción "Básico" re-sembrado

#### 🔄 Ida y vuelta Anthropic
- `chat_with_tools` implementado para AnthropicProvider (traducción OpenAI↔Anthropic)
- `agent_model` agregado al provider base (Haiku para routing, Sonnet para agent loop)
- Se revirtió a DeepSeek porque no hay API key de Anthropic configurada
- Código de Anthropic queda listo para cuando se active

### Archivos modificados (5):
| Archivo | Cambios |
|---------|---------|
| `app/routers/whatsapp_webhook.py` | +259 líneas: descarga multimedia, stickers, inyección file_key, foto sin instrucción, tipos desconocidos |
| `app/services/whatsapp.py` | +31 líneas: `send_template_message` acepta `body_params` |
| `app/agent/lucho_system_prompt.py` | +27 líneas: regla #0 reforzada, ejemplos corregidos |
| `app/services/llm/anthropic.py` | +183 líneas: `chat_with_tools` implementado |
| `app/services/llm/base.py` | +3 líneas: `agent_model` |

---

## Próxima sesión — Prioridades

### 🔴 INMEDIATA

**1. Crear templates en Meta Business Manager**
- [ ] Usar `docs/whatsapp_templates.md` como guía
- [ ] Crear 4 templates: `document_reminder`, `project_reminder`, `pico_y_placa`, `daily_digest`
- [ ] Agregar traducción `es` al template `initial_greeting`
- [ ] Esperar aprobación Meta (24-48h)

### 🟡 MEDIA

**2. Conectar templates en el scheduler**
- [ ] Implementar `send_template_message` con parámetros en notificaciones
- [ ] Recordatorios de documentos, proyectos, pico y placa, daily digest via template

**3. Flujo post-pago**
- [ ] Cuando trial expira: solicitar cédula, correo, nombre completo
- [ ] Enviar link de políticas de privacidad
- [ ] Registrar aceptación ("SI") en user_profiles

### 🟢 FASE 2

**4. Métricas** — % extracción correcta, retención D7/D30, intención de pago
**5. Ola 2** — cumpleaños, vacunas, suscripciones, control de gastos

### ⚪ FUTURO
- Whisper local ($0), skills adicionales, dashboard
- Fase 3: pagos reales (Kushki/PayPhone), facturación SRI
- Activar Anthropic Sonnet cuando se configure API key

---

## Comandos rápidos

```bash
# Arrancar servicios
systemctl --user start lucho-api lucho-tunnel

# Webhook Telegram
python scripts/setup_telegram_webhook.py

# Gestionar usuarios
python scripts/manage_users.py --list
python scripts/manage_users.py --activate 593987654321

# Limpiar BD para pruebas
python -c "
import asyncio
from app.database import async_session
from sqlalchemy import text
async def main():
    async with async_session() as s:
        await s.execute(text(\"SET session_replication_role = replica\"))
        tables = ['assets','caregiver_links','contacts','events','list_items','lists','messages','notes','payments','project_tasks','projects','reminders','shared_expense_participants','shared_expenses','subscription_invoices','subscriptions','topics','user_profiles','users']
        for t in tables:
            await s.execute(text(f'TRUNCATE TABLE \"{t}\" CASCADE'))
        await s.execute(text(\"SET session_replication_role = DEFAULT\"))
        await s.commit()
asyncio.run(main())
" && python scripts/seed_subscription_plans.py

# Git
git add -A && git commit -m "mensaje"
git tag vX.Y.Z -m "descripción"
```
