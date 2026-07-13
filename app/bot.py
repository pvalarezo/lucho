"""Lucho Telegram Bot — polling-based bot for development.

Uses python-telegram-bot with polling (no webhook, no SSL, no public IP needed).
Handles text, photo, and voice messages through the Lucho Agent.

Run: python run_bot.py
"""

import asyncio
import logging

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
from app.services import user as user_svc
from app.services import message as message_svc
from app.services import whisper as whisper_svc
from app.agent import process_message

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
)
logger = logging.getLogger(__name__)


# =============================================================================
# COMMAND HANDLERS
# =============================================================================

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


# =============================================================================
# CORE MESSAGE HANDLER — delegates to the Lucho Agent
# =============================================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Process any incoming message through the Lucho Agent.

    Flow:
    1. Resolve user identity
    2. Handle voice/photo pre-processing (transcribe, upload)
    3. Save raw message
    4. Call the agent → response
    5. Send response
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

    # Show typing indicator
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    async with async_session() as session:
        try:
            # Dedup: skip if already processed
            if await _is_duplicate(session, chat_id, msg.message_id):
                logger.debug("Skipping duplicate msg %s from chat %s", msg.message_id, chat_id)
                return

            # Resolve/create user
            user = await user_svc.resolve_user_by_telegram(
                session=session,
                telegram_id=str(chat_id),
                first_name=user_tg.first_name or "",
                last_name=user_tg.last_name,
            )
            await session.flush()

            # ---- Voice/Audio: transcribe ----
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
                    await msg.reply_text(
                        f"📝 Entendido: _{transcription[:200]}_",
                        parse_mode="Markdown",
                    )
                else:
                    await msg.reply_text("❌ No pude transcribir el audio. ¿Podés escribirlo?")
                    await session.rollback()
                    return

            # ---- Photo: upload to MinIO, analyze with vision ----
            photo_object_key = None
            if has_photo:
                try:
                    largest_photo = msg.photo[-1]
                    file = await context.bot.get_file(largest_photo.file_id)
                    photo_bytes = await file.download_as_bytearray()
                    from app.services import minio as minio_svc
                    photo_object_key = await minio_svc.upload_file(
                        user_id=str(user.id),
                        file_bytes=bytes(photo_bytes),
                        filename=f"photo_{msg.message_id}.jpg",
                        content_type="image/jpeg",
                    )
                except Exception as exc:
                    logger.exception("Photo upload failed: %s", exc)

                # No caption → analyze and ask user
                if not text and not has_voice and photo_object_key:
                    from app.services import vision as vision_svc
                    analysis = await vision_svc.analyze_image(bytes(photo_bytes))

                    if analysis and analysis.get("suggested_action") == "guardar":
                        doc_type = analysis.get("document_type", "documento")
                        desc = analysis.get("description", "imagen")
                        await msg.reply_text(
                            f"📸 *Parece {desc}*\n\n"
                            f"¿Querés que la guarde como *{doc_type}* en tus documentos?\n"
                            f"Respondé _\"sí\"_ para guardar o decime qué es.",
                            parse_mode="Markdown",
                        )
                    elif analysis and analysis.get("suggested_action") == "ignorar":
                        await msg.reply_text(
                            f"📸 *{analysis.get('description', 'Esta imagen')}*\n\n"
                            f"No parece un documento. Si querés guardarla igual, "
                            f"decime de qué se trata.",
                            parse_mode="Markdown",
                        )
                    else:
                        await msg.reply_text(
                            "📸 *Guardé tu imagen.*\n\n"
                            "¿De qué se trata? Por ejemplo:\n"
                            "• _\"Mi cédula de identidad\"_\n"
                            "• _\"Factura del supermaxi\"_\n"
                            "• _\"SOAT de mi carro\"_\n"
                            "• _\"Garantía de la lavadora\"_\n\n"
                            "Respondeme con una descripción y la catalogo.",
                            parse_mode="Markdown",
                        )

                    # Save raw message and return — wait for user's text response
                    db_message = await message_svc.create_message(
                        session=session,
                        user_id=user.id,
                        channel=MessageChannel.telegram,
                        message_type=MessageType.photo,
                        text="[foto sin descripción]",
                        file_path=photo_object_key,
                    )
                    await session.commit()
                    return

            # ---- Save raw message ----
            db_message = await message_svc.create_message(
                session=session,
                user_id=user.id,
                channel=MessageChannel.telegram,
                message_type=message_type,
                text=text,
                file_path=photo_object_key or f"telegram://{chat_id}/{msg.message_id}",
                transcription=transcription,
            )
            await session.flush()

            # ---- Call the AGENT (the new unified pipeline) ----
            content = text or "[audio/photo message]"

            # If photo was linked from a previous photo-without-caption, attach the key
            if message_type == MessageType.text and not has_photo:
                from sqlalchemy import select, desc
                from app.models.message import Message
                last_msg_result = await session.execute(
                    select(Message).where(
                        Message.user_id == user.id,
                        Message.message_type == MessageType.photo,
                        Message.text == "[foto sin descripción]",
                    ).order_by(desc(Message.received_at)).limit(1)
                )
                last_photo = last_msg_result.scalar_one_or_none()
                if last_photo and last_photo.file_path:
                    # Enrich the message with photo context
                    content = f"[foto adjunta: {last_photo.file_path}] {content}"
                    last_photo.text = text
                    logger.info("Linked text response to photo: %s", last_photo.file_path)

            # THE AGENT CALL — this replaces ALL the old pipeline code
            response_text = await process_message(
                session=session,
                user_id=str(user.id),
                user_message=content,
            )

            # ---- Send response ----
            if response_text:
                await msg.reply_text(
                    response_text,
                    parse_mode="Markdown",
                )

            # Update message status
            db_message.extraction_result = {
                "agent_response": response_text,
                "telegram_message_id": msg.message_id,
            }
            await message_svc.update_message_status(session, db_message, MessageStatus.confirmed)
            await session.commit()

        except Exception as exc:
            logger.exception("Pipeline error for chat_id=%s: %s", chat_id, exc)
            await session.rollback()
            await msg.reply_text("❌ Tuvimos un error. ¿Podés intentar de nuevo?")


# =============================================================================
# DEDUPLICATION
# =============================================================================

async def _is_duplicate(session, chat_id: int, telegram_message_id: int) -> bool:
    """Check if a Telegram message was already processed."""
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


# =============================================================================
# APPLICATION FACTORY
# =============================================================================

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

    logger.info("Starting Lucho bot in polling mode (AGENT MODE)...")
    app = build_app()

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)

    logger.info("✅ Bot is running. Press Ctrl+C to stop.")

    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Shutting down...")
        await app.updater.stop()
        await app.stop()


if __name__ == "__main__":
    asyncio.run(main())
