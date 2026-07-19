"""Telegram webhook — receive messages from Telegram Bot API.

This is the SINGLE entry point for Telegram messages (replaces the old
polling bot in app/bot.py). Flow is identical to WhatsApp webhook:

1. Receive update from Telegram
2. Deduplication check
3. Resolve/create user
4. Upload media to MinIO (photos, audio, documents)
5. Transcribe audio via Whisper
6. Persist raw message
7. Send typing indicator
8. Call the Lucho Agent → response
9. Send files (if any) + text response via Telegram
"""

import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db
from app.models.message import MessageChannel, MessageType, MessageStatus
from app.models.message import Message as MessageModel
from app.services import minio as minio_svc
from app.services import telegram as telegram_svc
from app.services import user as user_svc
from app.services import message as message_svc
from app.services import whisper as whisper_svc
from app.agent import process_message

logger = logging.getLogger(__name__)
router = APIRouter(tags=["telegram"], prefix="/telegram")


# =============================================================================
# WEBHOOK ENDPOINT (POST only — Telegram pushes updates here)
# =============================================================================


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    """
    Process incoming Telegram update through the Lucho Agent.

    Telegram sends a JSON Update object:
    {
      "update_id": 123456789,
      "message": {
        "message_id": 100,
        "chat": {"id": 123456, "first_name": "Patricio", ...},
        "text": "hola Lucho",
        ...
      }
    }
    """
    body = await request.json()
    logger.debug("Telegram webhook: update_id=%s", body.get("update_id"))

    # ---- 1. Extract message from Telegram update ----
    msg = body.get("message") or body.get("edited_message")
    if not msg:
        # Could be other update types (callback_query, etc.) — ignore for now
        return {"status": "no_message"}

    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    if not chat_id:
        return {"status": "no_chat_id"}

    message_id = msg.get("message_id")
    text = msg.get("text") or msg.get("caption")
    photo = msg.get("photo")
    audio_or_voice = msg.get("audio") or msg.get("voice")
    document = msg.get("document")

    # ---- 2. Deduplication: skip if already processed ----
    if await _is_duplicate(session, chat_id, message_id):
        logger.debug("Skipping duplicate Telegram msg %s from chat %s", message_id, chat_id)
        return {"status": "duplicate"}

    # ---- 3. Determine message type ----
    if photo:
        message_type = MessageType.photo
    elif audio_or_voice:
        message_type = MessageType.audio
    elif document:
        message_type = MessageType.photo  # treat documents like files (store in MinIO)
    else:
        message_type = MessageType.text

    # ---- 4. Resolve or create user ----
    user = await user_svc.resolve_user_by_telegram(
        session=session,
        telegram_id=str(chat_id),
        first_name=chat.get("first_name", ""),
        last_name=chat.get("last_name"),
    )
    await session.flush()

    # ---- 5. Onboarding: if new user, send welcome messages first ----
    if not user.onboarding_complete:
        await _send_onboarding_messages_telegram(chat_id, user)
        user.onboarding_complete = True
        await session.commit()
        return {"status": "onboarding_sent"}

    # ---- 6. Access check (trial/active subscription required) ----
    access = await user_svc.check_access(session, str(user.id))
    if not access.allowed:
        await telegram_svc.send_message(chat_id, access.reason)
        await session.commit()
        return {"status": "access_denied", "reason": access.reason}

    # ---- 5. Audio/Voice: download, upload to MinIO, transcribe ----
    transcription = None
    file_object_key = None

    if audio_or_voice:
        file_id = audio_or_voice.get("file_id")
        if file_id:
            # Send immediate ack — transcribing takes time
            await telegram_svc.send_message(chat_id, "🎙️ Transcribiendo tu audio...")

            audio_bytes = await telegram_svc.download_file(file_id)
            if audio_bytes:
                file_object_key = await minio_svc.upload_file(
                    user_id=str(user.id),
                    file_bytes=audio_bytes,
                    filename=f"voice_{chat_id}_{message_id}.ogg",
                    content_type="audio/ogg",
                )

                transcription = await whisper_svc.transcribe_audio(
                    audio_bytes,
                    filename=f"voice_{chat_id}_{message_id}.ogg",
                )

                if transcription:
                    text = transcription
                    await telegram_svc.send_message(
                        chat_id,
                        f"📝 Entendido: {transcription[:200]}",
                    )
                else:
                    await telegram_svc.send_message(
                        chat_id,
                        "❌ No pude transcribir el audio. ¿Podés escribirlo?",
                    )
                    await session.commit()
                    return {"status": "transcription_failed"}

    # ---- 6. Photo: upload to MinIO, let agent handle analysis ----
    if photo:
        try:
            # Pick largest photo (last in array)
            largest_photo = photo[-1]
            photo_bytes = await telegram_svc.download_file(largest_photo["file_id"])
            if photo_bytes:
                file_object_key = await minio_svc.upload_file(
                    user_id=str(user.id),
                    file_bytes=photo_bytes,
                    filename=f"photo_{chat_id}_{message_id}.jpg",
                    content_type="image/jpeg",
                )
        except Exception as exc:
            logger.exception("Telegram webhook photo upload failed: %s", exc)

        # Include file_key context for the agent (always, with or without caption)
        if not text and file_object_key:
            text = f"[foto: {file_object_key}]"
        elif text and file_object_key:
            text = f"[foto: {file_object_key}] {text}"

    # ---- 7. Document (PDF, DOC, etc.): upload to MinIO ----
    if document and not photo:
        doc_name = document.get("file_name", "documento")
        try:
            doc_bytes = await telegram_svc.download_file(document["file_id"])
            if doc_bytes:
                doc_object_key = await minio_svc.upload_file(
                    user_id=str(user.id),
                    file_bytes=doc_bytes,
                    filename=f"doc_{chat_id}_{message_id}_{doc_name}",
                    content_type=document.get("mime_type", "application/octet-stream"),
                )
                if not text:
                    text = f"[documento: {doc_name} → {doc_object_key}]"
                else:
                    text = f"{text}\n[documento adjunto: {doc_name} → {doc_object_key}]"
        except Exception as exc:
            logger.exception("Telegram webhook document upload failed: %s", exc)

    file_path = file_object_key or f"telegram://{chat_id}/{message_id}"

    if not text:
        logger.warning("Telegram message %s without extractable text", message_id)
        return {"status": "no_text"}

    # ---- 8. Persist raw message ----
    db_message = await message_svc.create_message(
        session=session,
        user_id=user.id,
        channel=MessageChannel.telegram,
        message_type=message_type,
        text=text,
        file_path=file_path,
        transcription=transcription,
    )
    await session.flush()

    # ---- 9. Send typing indicator ----
    await telegram_svc.send_typing(chat_id)

    # ---- 10. Call the Lucho Agent ----
    logger.info("Calling agent for user=%s chat_id=%s: %s", user.id, chat_id, text[:100])
    response = await process_message(
        session=session,
        user_id=str(user.id),
        user_message=text,
    )

    response_text = response.get("text", "") if isinstance(response, dict) else response
    files = response.get("files", []) if isinstance(response, dict) else []

    # ---- 11. Send files first (if any) ----
    for file_info in files:
        file_key = file_info.get("file_key", "")
        caption = file_info.get("caption", "")
        if not file_key:
            continue
        try:
            file_bytes = await minio_svc.download_file(file_key)
            if file_bytes:
                filename = file_info.get("filename", file_key.split("/")[-1])
                await telegram_svc.send_photo(
                    chat_id=chat_id,
                    photo_bytes=file_bytes,
                    caption=caption if caption else None,
                    filename=filename,
                )
                logger.info("Sent %s to chat_id=%s via Telegram webhook", filename, chat_id)
        except Exception as exc:
            logger.exception("Telegram webhook file send failed '%s': %s", file_key, exc)

    # ---- 12. Send text response ----
    if response_text:
        # Skip redundant text when photo was sent successfully
        skip_text = (
            files
            and len(response_text) < 80
            and any(phrase in response_text.lower() for phrase in [
                "aquí está", "aquí tenés", "listo", "acá está"
            ])
        )
        if not skip_text:
            await telegram_svc.send_message(chat_id, response_text)

    # ---- 13. Update message status ----
    db_message.extraction_result = {
        "agent_response": response_text,
        "files_sent": len(files),
        "telegram_message_id": message_id,
    }
    await message_svc.update_message_status(session, db_message, MessageStatus.confirmed)

    # Mark onboarding as complete after first successful interaction
    if not user.onboarding_complete:
        user.onboarding_complete = True

    await session.commit()

    logger.info(
        "Telegram webhook processed: chat_id=%s msg_id=%s type=%s response_len=%d",
        chat_id,
        message_id,
        message_type.value,
        len(response_text),
    )

    return {"status": "processed", "chat_id": chat_id, "message_id": message_id}


# =============================================================================
# DEDUPLICATION
# =============================================================================


async def _is_duplicate(session: AsyncSession, chat_id: int, telegram_message_id: int) -> bool:
    """Check if a Telegram message ID was already processed."""
    from sqlalchemy import select
    from app.models.user import User

    result = await session.execute(
        select(MessageModel.id)
        .join(User)
        .where(
            User.telegram_id == str(chat_id),
            MessageModel.extraction_result.contains(
                {"telegram_message_id": telegram_message_id}
            ),
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def _send_onboarding_messages_telegram(chat_id: int, user) -> None:
    """
    Send onboarding welcome messages (2 messages) for new users via Telegram.
    """
    name = user.first_name or ""

    # ---- Message 1: Welcome + presentation ----
    msg1 = (
        f"👋 ¡Hola {name}!\n\n"
        f"Soy *Lucho*, tu asistente personal ecuatoriano 🇪🇨\n"
        f"Fui creado por AURACORE para ser tu *segundo cerebro*: "
        f"recordar, organizar y encontrar tu información personal.\n\n"
        f"*¿Qué puedo hacer por vos?*\n\n"
        f"🚗 *Vehículos* — Guardar tu placa, alertas de pico y placa, "
        f"fechas de matriculación\n\n"
        f"📄 *Documentos* — Guardar SOAT, cédula, facturas, garantías "
        f"con fecha de vencimiento\n\n"
        f"📅 *Recordatorios* — Citas, eventos, fechas importantes "
        f"con anticipación\n\n"
        f"📝 *Listas y notas* — Compras, tareas, ideas organizadas por tema\n\n"
        f"📋 *Proyectos* — Tareas agrupadas con fechas de entrega\n\n"
        f"💰 *Gastos compartidos* — Dividir cuentas entre amigos\n\n"
        f"🔍 *Búsqueda* — Encontrar todo lo que guardaste "
        f"y también buscar en internet\n\n"
        f"Mandame lo que necesités sin estructura, "
        f"yo lo organizo. ¡Hablame como a un amigo!"
    )
    await telegram_svc.send_message(chat_id, msg1)

    # ---- Message 2: Ask for name + trial info ----
    msg2 = (
        f"⚡ *¿Cómo querés que te llame?*\n\n"
        f"Decime tu nombre y empezamos.\n\n"
        f"🎉 *Tenés 7 días de prueba GRATIS* con acceso a "
        f"todas las funcionalidades. No necesitamos ningún dato "
        f"personal ni de pago durante este tiempo.\n\n"
        f"Al finalizar la prueba, si querés continuar, "
        f"elegís tu plan y completás tu registro. "
        f"Por ahora, ¡disfrutá Lucho sin compromisos! 🚀"
    )
    await telegram_svc.send_message(chat_id, msg2)
