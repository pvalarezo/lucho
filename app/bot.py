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

    # ---- 1. Show typing indicator (sutil, nativo de Telegram) ----
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

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
            routing = await router_svc.route_intent(content)
            target_table = routing.get("target_table", "note")

            # Extract fields
            extraction = {}
            if target_table != "search" and text:
                extraction = await extractor_svc.extract_fields(text, target_table)

            # Store extraction
            db_message.extraction_result = {
                "routing": routing,
                "target_table": target_table,
                "extraction": extraction,
            }
            await message_svc.update_message_status(session, db_message, MessageStatus.extracted)

            # Persist to target table
            await _persist(session, user.id, target_table, extraction, text, db_message.id)

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
