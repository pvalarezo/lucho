"""Lucho Telegram Bot — polling-based bot for development.

Uses python-telegram-bot with polling (no webhook, no SSL, no public IP needed).
Handles text, photo, and voice messages through the full Lucho pipeline.

Run: python run_bot.py
"""

import asyncio
import logging
import uuid

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from app.config import settings
from app.database import async_session
from app.models.message import MessageChannel, MessageType, MessageStatus
from app.services import telegram as telegram_svc
from app.services import user as user_svc
from app.services import message as message_svc
from app.services import router as router_svc
from app.services import extractor as extractor_svc
from app.services import persistence as persist_svc
from app.services import whisper as whisper_svc

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
)
logger = logging.getLogger(__name__)


# ---- Command handlers ----

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start — welcome and onboarding."""
    user = update.effective_user
    welcome = (
        f"👋 ¡Hola {user.first_name}! Soy *Lucho*, tu asistente personal.\n\n"
        f"Podés hablarme sin estructura. Te ayudo a recordar, organizar y encontrar:\n"
        f"• 🚗 *Matriculación y pico y placa* — decime tu placa\n"
        f"• 📅 *Recordatorios* — \"cita dentista el lunes\"\n"
        f"• 📝 *Listas* — \"comprar leche, pan y huevos\"\n"
        f"• 💡 *Notas* — \"idea de negocio: vender empanadas\"\n"
        f"• 💰 *Gastos* — \"pagué la cena $40 entre 4\"\n\n"
        f"Mandame un mensaje y empecemos 🚀"
    )
    await update.message.reply_text(welcome, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help."""
    help_text = (
        "🤖 *Lucho — Ayuda*\n\n"
        "Podés pedirme cosas como:\n"
        "• \"Mi carro es PBC-1234, recordame la matriculación\"\n"
        "• \"Cita con el doctor el 20 de agosto a las 3pm\"\n"
        "• \"Comprar arroz, atún y huevos\"\n"
        "• \"El SOAT de mi carro vence en diciembre\"\n"
        "• \"¿Cuándo es mi pico y placa?\"\n"
        "• \"¿Qué tengo pendiente esta semana?\"\n\n"
        "También podés mandarme *fotos* de facturas y *notas de voz*.\n\n"
        "Enviame lo que quieras, yo lo organizo. 😊"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


# ---- Message handler (core pipeline) ----

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Process any incoming message through the full Lucho pipeline:
    1. Resolve/create user
    2. Persist raw message
    3. Route intent (DeepSeek)
    4. Extract fields (DeepSeek)
    5. Persist to target table
    6. Send confirmation
    """
    msg = update.message
    if not msg:
        return

    chat = update.effective_chat
    chat_id = chat.id
    user_tg = update.effective_user

    # Determine message type
    text = msg.text or msg.caption
    has_photo = bool(msg.photo)
    has_voice = bool(msg.voice)
    has_audio = bool(msg.audio)

    if has_photo:
        message_type = MessageType.photo
    elif has_voice or has_audio:
        message_type = MessageType.audio
    else:
        message_type = MessageType.text

    # ---- 1. Show typing indicator ----
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    # ---- 1.5 Dedup: skip if this message was already processed ----
    if await _is_duplicate(session, chat_id, msg.message_id):
        logger.debug("Skipping duplicate message %s from chat %s", msg.message_id, chat_id)
        return

    # ---- 2. Process through pipeline ----
    async with async_session() as session:
        try:
            # Resolve/create user
            user = await user_svc.resolve_user_by_telegram(
                session=session,
                telegram_id=str(chat_id),
                first_name=user_tg.first_name or "",
                last_name=user_tg.last_name,
            )
            await session.flush()

            # Handle voice/audio: transcribe
            transcription = None
            if has_voice or has_audio:
                await msg.reply_text("🎙️ Transcribiendo tu audio...")
                file_obj = msg.voice or msg.audio
                file = await context.bot.get_file(file_obj.file_id)
                audio_bytes = await file.download_as_bytearray()
                transcription = await whisper_svc.transcribe_audio(
                    bytes(audio_bytes),
                    filename=f"voice_{chat_id}.ogg",
                )
                if transcription:
                    text = transcription
                    await msg.reply_text(f"📝 Entendido: _{transcription[:200]}_", parse_mode="Markdown")
                else:
                    await msg.reply_text("❌ No pude transcribir el audio. ¿Podés escribirlo?")
                    await session.rollback()
                    return

            # Handle photo: TODO OCR
            if has_photo:
                await msg.reply_text("📸 Recibí tu foto. La funcionalidad de leer facturas estará disponible pronto.")
                # For now, use caption as text
                if not text:
                    text = "[foto sin descripción]"

            # Persist raw message
            db_message = await message_svc.create_message(
                session=session,
                user_id=user.id,
                channel=MessageChannel.telegram,
                message_type=message_type,
                text=text,
                file_path=f"telegram://{chat_id}/{msg.message_id}",
                transcription=transcription,
            )
            await session.flush()

            # Route intent
            content = text or "[audio/photo message]"

            # Quick meta-check: user asking about Lucho's capabilities?
            if _is_meta_question(content):
                await msg.reply_text(HELP_TEXT, parse_mode="Markdown")
                await session.commit()
                return

            routing = await router_svc.route_intent(content)
            target_table = routing.get("target_table", "note")

            # Extract fields
            extraction = {}
            if target_table != "search" and text:
                extraction = await extractor_svc.extract_fields(text, target_table)

            # Store extraction + telegram_message_id for dedup
            db_message.extraction_result = {
                "routing": routing,
                "target_table": target_table,
                "extraction": extraction,
                "telegram_message_id": msg.message_id,
            }
            await message_svc.update_message_status(session, db_message, MessageStatus.extracted)

            # Persist to target table
            await _persist(session, user.id, target_table, extraction, text, db_message.id)

            # Handle corrections — update the last entity the user created
            if target_table == "correction":
                correction_reply = await _handle_correction(session, user.id, extraction, text)
                if correction_reply:
                    await msg.reply_text(correction_reply, parse_mode="Markdown")
                await message_svc.update_message_status(session, db_message, MessageStatus.confirmed)
                await session.commit()
                return

            # Handle search queries — actually search user data
            if target_table == "search":
                search_reply = await _handle_search(session, user.id, text)
                if search_reply:
                    await msg.reply_text(search_reply, parse_mode="Markdown")
                await message_svc.update_message_status(session, db_message, MessageStatus.confirmed)
                await session.commit()
                return

            # Build and send confirmation
            confirmation = _build_confirmation(target_table, extraction, text)
            if confirmation:
                await msg.reply_text(confirmation, parse_mode="Markdown")

            await message_svc.update_message_status(session, db_message, MessageStatus.confirmed)
            await session.commit()

        except Exception as exc:
            logger.exception("Pipeline error for chat_id=%s: %s", chat_id, exc)
            await session.rollback()
            await msg.reply_text("❌ Tuvimos un error. ¿Podés intentar de nuevo?")


# ---- Persistence helper ----

async def _persist(session, user_id, target_table, extraction, text, source_message_id):
    """Write extracted data to the correct target table."""
    if not extraction:
        return None

    match target_table:
        case "asset":
            return await persist_svc.persist_asset(
                session=session,
                user_id=user_id,
                asset_type=extraction.get("asset_type", "other"),
                name=extraction.get("name", text or "sin nombre"),
                attributes=extraction.get("attributes", {}),
                notes=extraction.get("notes"),
                source_message_id=source_message_id,
            )
        case "event":
            return await persist_svc.persist_event(
                session=session,
                user_id=user_id,
                title=extraction.get("title", text or "evento"),
                target_date=extraction.get("target_date", ""),
                description=extraction.get("description"),
                certainty=extraction.get("certainty", "certain"),
                recurrence_rule=extraction.get("recurrence_rule"),
            )
        case "list_item":
            return await persist_svc.persist_list_items(
                session=session,
                user_id=user_id,
                list_name=extraction.get("list_name", "general"),
                items=extraction.get("items", [text] if text else []),
                quantity=extraction.get("quantity"),
            )
        case "note":
            return await persist_svc.persist_note(
                session=session,
                user_id=user_id,
                topic_name=extraction.get("topic_name", "general"),
                content=extraction.get("content", text or ""),
                source_message_id=source_message_id,
            )
        case _:
            return None


# ---- Deduplication ----

async def _is_duplicate(session, chat_id: int, telegram_message_id: int) -> bool:
    """Check if a Telegram message was already processed (by message_id + chat_id)."""
    from sqlalchemy import select
    from app.models.message import Message
    from app.models.user import User

    result = await session.execute(
        select(Message.id).join(User).where(
            User.telegram_id == str(chat_id),
            Message.extraction_result.contains({"telegram_message_id": telegram_message_id}),
        ).limit(1)
    )
    return result.scalar_one_or_none() is not None


# ---- Meta-question detection ----

HELP_TEXT = (
    "🤖 *Lucho — ¿Qué puedo hacer por vos?*\n\n"
    "Soy tu asistente personal. Me hablás sin estructura y yo organizo:\n\n"
    "🚗 *Vehículos*\n"
    "_\"Mi carro es PBC-1234\"_ → Calculo matriculación, pico y placa, SOAT\n\n"
    "📅 *Recordatorios*\n"
    "_\"Cita dentista el lunes a las 3pm\"_ → Te aviso con anticipación\n\n"
    "📝 *Listas*\n"
    "_\"Comprar leche, pan y huevos\"_ → Creo tu lista de compras\n\n"
    "💡 *Notas*\n"
    "_\"Idea de negocio: exportar rosas\"_ → Guardo tus ideas por tema\n\n"
    "💰 *Gastos compartidos*\n"
    "_\"Cena $60 entre 4 personas\"_ → Calculo cuánto toca por persona\n\n"
    "🔍 *Buscar*\n"
    "_\"¿Cuándo vence mi SOAT?\"_ → Encuentro lo que guardaste\n\n"
    "Mandame *fotos* de facturas y *notas de voz*.\n"
    "Escribime lo que necesites, sin comandos. 😊"
)


async def _is_meta_question(text: str) -> bool:
    """Use a quick LLM call to detect if user is asking about Lucho himself."""
    # Also check keywords as fast path (0 cost, 0 latency)
    lower = text.lower().strip()
    fast_keywords = [
        "qué puedes hacer", "qué sabes hacer", "cómo funcionas",
        "ayuda", "help", "para qué sirves", "qué eres",
        "cómo me ayudas", "qué haces", "cómo te uso",
        "cómo funciona esto", "explicame", "explicame tus",
        "qué servicios", "capacidades",
    ]
    if any(kw in lower for kw in fast_keywords):
        return True

    # For ambiguous cases, ask the router
    routing = await router_svc.route_intent(text)
    # If router says 'search' but text looks like a capabilities question,
    # it's meta. Also detect if the user is asking about Lucho.
    return False  # default: not meta if no keyword match


# ---- Smart search: extract params first, then search ----

async def _handle_search(session, user_id, text: str) -> str | None:
    """
    Smart search: extract search parameters from the user's question,
    then run the appropriate deterministic query.
    """
    from app.services import search as search_svc
    from app.services.extractor import extract_fields

    # 1. Extract search intent from the question
    search_params = await _extract_search_params(text)
    search_type = search_params.get("search_type", "general")

    # 2. Route to the right query based on search_type
    if search_type in ("vehicle", "vehículo", "carro", "placa"):
        return await _search_vehicles(session, user_id)

    elif search_type in ("list", "lista", "compras", "pendientes", "pending"):
        return await _search_pending(session, user_id)

    elif search_type in ("deadline", "vencimiento", "cuándo", "próximo", "fechas"):
        return await _search_deadlines(session, user_id)

    elif search_type in ("note", "nota", "idea", "tema"):
        return await _search_notes(session, user_id)

    # 3. Fallback: search everything and return best match
    return await _search_all(session, user_id, text)


async def _extract_search_params(text: str) -> dict:
    """Use the extractor to understand what the user is searching for."""
    extraction = await extractor_svc.extract_fields(text, "search")
    if not extraction:
        return {"search_type": "general"}
    return extraction


async def _search_vehicles(session, user_id) -> str | None:
    """List all user vehicles with details."""
    from sqlalchemy import select
    from app.models.asset import Asset, AssetType

    result = await session.execute(
        select(Asset).where(
            Asset.user_id == user_id,
            Asset.asset_type == AssetType.vehicle,
            Asset.deleted_at.is_(None),
        )
    )
    vehicles = result.scalars().all()

    if not vehicles:
        return "No tenés vehículos registrados. Mandame tu placa y lo guardo. 🚗"

    lines = ["🚗 *Tus vehículos:*"]
    for v in vehicles:
        attrs = v.attributes or {}
        plate = attrs.get("plate", "Sin placa")
        brand = attrs.get("brand", "")
        model = attrs.get("model", "")
        pyp = attrs.get("pico_y_placa_days", "")
        matric = attrs.get("next_matriculation", "")

        desc = f"{brand} {model}".strip() or v.name
        lines.append(f"  • *{plate}* — {desc}")
        if pyp:
            lines.append(f"    Pico y placa: {pyp}")
        if matric:
            lines.append(f"    Matriculación: {matric}")

    return "\n".join(lines)


async def _search_pending(session, user_id) -> str | None:
    """List pending items across all lists."""
    from app.services import search as search_svc

    pending = await search_svc.list_pending_items(session, user_id)
    if not pending:
        return "No tenés nada pendiente. ¡Bien ahí! ✅"

    lines = ["📝 *Pendientes:*"]
    for item in pending[:10]:
        lines.append(f"  • [{item['list']}] {item['content']}")
    return "\n".join(lines)


async def _search_deadlines(session, user_id) -> str | None:
    """List upcoming deadlines."""
    from app.services import search as search_svc

    deadlines = await search_svc.upcoming_deadlines(session, user_id, days_ahead=90)
    if not deadlines:
        return "No tenés vencimientos próximos. ✅"

    lines = ["📅 *Próximos vencimientos:*"]
    for d in deadlines[:8]:
        emoji = "🔴" if d["days_left"] <= 7 else "🟡" if d["days_left"] <= 30 else "🟢"
        lines.append(f"{emoji} {d['title']}: {d['target_date']} ({d['days_left']} días)")
    return "\n".join(lines)


async def _search_notes(session, user_id) -> str | None:
    """List user's note topics."""
    from sqlalchemy import select, func
    from app.models.topic import Topic, Note

    result = await session.execute(
        select(Topic.name, func.count(Note.id))
        .join(Note, Note.topic_id == Topic.id)
        .where(Topic.user_id == user_id)
        .group_by(Topic.name)
        .order_by(func.count(Note.id).desc())
    )
    topics = [(row[0], row[1]) for row in result.fetchall()]

    if not topics:
        return "No tenés notas guardadas. Mandame una idea y la guardo. 💡"

    lines = ["💡 *Tus notas por tema:*"]
    for name, count in topics:
        lines.append(f"  • {name} ({count} nota{'s' if count != 1 else ''})")
    return "\n".join(lines)


async def _search_all(session, user_id, text: str) -> str | None:
    """Fallback: search everything."""
    # Give a summary of everything the user has
    parts = []

    v = await _search_vehicles(session, user_id)
    if v and "No tenés" not in v:
        parts.append(v)

    p = await _search_pending(session, user_id)
    if p and "No tenés" not in p:
        parts.append(p)

    d = await _search_deadlines(session, user_id)
    if d and "No tenés" not in d:
        parts.append(d)

    if parts:
        return "\n\n".join(parts)

    return "Todavía no tengo nada guardado. Mandame algo y empiezo a organizar. 🚀"


# ---- Confirmation builder ----

def _build_confirmation(target_table: str, extraction: dict, original_text: str | None) -> str:
    """Build a human-readable confirmation."""
    if not extraction:
        return ""

    match target_table:
        case "asset":
            at = extraction.get("asset_type", "otro")
            name = extraction.get("name", original_text or "nuevo")
            return (
                f"📋 Guardado: *{name}* ({at})\n"
                f"¿Está bien? Podés corregirme en cualquier momento."
            )
        case "event":
            title = extraction.get("title", original_text or "evento")
            td = extraction.get("target_date", "")
            ds = f" — {td}" if td else ""
            return f"📅 Agendado: *{title}*{ds}"
        case "list_item":
            ln = extraction.get("list_name", "general")
            items = extraction.get("items", [])
            its = "\n".join(f"  ✓ {i}" for i in items)
            return f"📝 Agregado a *{ln}*:\n{its}"
        case "note":
            topic = extraction.get("topic_name", "general")
            content = extraction.get("content", original_text or "")
            preview = content[:100] + "..." if len(content) > 100 else content
            return f"💡 Nota en *{topic}*:\n{preview}"
        case "shared_expense":
            desc = extraction.get("description", original_text or "gasto")
            amt = extraction.get("amount", 0)
            parts = extraction.get("participants", [])
            pp = amt / len(parts) if parts else amt
            return f"💰 *{desc}*\n${amt:.2f} ÷ {len(parts)} = ${pp:.2f} c/u"
        case _:
            return ""


# ---- Correction handler ----

async def _handle_correction(session, user_id, extraction: dict, text: str) -> str | None:
    """
    Handle user corrections. Updates the last entity the user interacted with.
    Example: "no, la cita es el 20" → updates the last event's date.
    """
    if not extraction:
        return "No entendí bien qué querés corregir. ¿Podés ser más específico?"

    original = extraction.get("original_target", "")
    corrected = extraction.get("corrected_fields", {})

    if not corrected:
        return "No detecté qué campos corregir. Decime qué dato querés cambiar."

    # Find the user's most recent entity (check events, notes, lists, assets)
    from sqlalchemy import select, desc
    from app.models.event import Event
    from app.models.topic import Note
    from app.models.list import ListItem
    from app.models.asset import Asset

    updated = []

    # Try last event
    result = await session.execute(
        select(Event).where(Event.user_id == user_id).order_by(desc(Event.created_at)).limit(1)
    )
    event = result.scalar_one_or_none()
    if event:
        for field, value in corrected.items():
            if hasattr(event, field):
                old = getattr(event, field)
                setattr(event, field, value)
                updated.append(f"{field}: {old} → {value}")
        if updated:
            return f"✅ Corregido en *{event.title}*:\n" + "\n".join(f"  • {u}" for u in updated)

    # Try last note
    result = await session.execute(
        select(Note).join(Note.topic).where(Note.topic.has(user_id=user_id)).order_by(desc(Note.created_at)).limit(1)
    )
    note = result.scalar_one_or_none()
    if note and "content" in corrected:
        old = note.content[:50]
        note.content = corrected["content"]
        return f"✅ Nota actualizada:\n  • contenido: _{old}..._ → _{corrected['content'][:50]}..._"

    return "No encontré algo reciente para corregir. ¿Querés ser más específico sobre qué dato modificar?"


# ---- Application factory ----

def build_app() -> Application:
    """Build and configure the Telegram bot application."""
    app = (
        Application.builder()
        .token(settings.TELEGRAM_BOT_TOKEN)
        .build()
    )

    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))

    # Messages (text, photo, voice, audio)
    app.add_handler(
        MessageHandler(
            filters.TEXT | filters.PHOTO | filters.VOICE | filters.AUDIO,
            handle_message,
        )
    )

    return app


async def main():
    """Entry point: start the bot with polling."""
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.error(
            "TELEGRAM_BOT_TOKEN is not set. Create a bot with @BotFather "
            "and add the token to .env"
        )
        return

    logger.info("Starting Lucho bot in polling mode...")
    app = build_app()

    # Start polling
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)

    logger.info("✅ Bot is running. Press Ctrl+C to stop.")
    logger.info("   Open Telegram and send a message to your bot!")

    # Keep running until interrupted
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Shutting down...")
        await app.updater.stop()
        await app.stop()


if __name__ == "__main__":
    asyncio.run(main())
